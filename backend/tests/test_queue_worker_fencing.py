"""公网队列 worker 的租约 fencing、撤权复核与 checkpoint 回归。"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from backend.app import auth as auth_module
from backend.app import worker
from backend.app.auth import authorize_model_transfer, request_identity
from backend.app.supabase_adapter import SupabaseError, SupabaseLeaseLost, assert_worker_lease


TASK_ID = "CNINFO-QUEUE1234"
LEASE_TOKEN = "11111111-1111-4111-8111-111111111111"


class FakeQueueClient:
    """只实现 worker 合同；调用记录用于确认 token 与状态决策。"""

    def __init__(self) -> None:
        self.task: dict[str, Any] | None = {
            "task_id": TASK_ID,
            "tenant_id": "tenant-1",
            "requested_by": "user-1",
            "request_payload": {
                "company_query": "600000",
                "requested_by_identity": {
                    "user_id": "user-1",
                    "tenant_id": "tenant-1",
                    # 快照角色故意不同，worker 必须使用成员表中的当前角色。
                    "role": "owner",
                },
            },
            "attempt": 2,
            "lease_token": LEASE_TOKEN,
        }
        self.membership: dict[str, Any] | None = {
            "organization_id": "tenant-1",
            "user_id": "user-1",
            "role": "reviewer",
            "active": True,
        }
        self.heartbeats: list[dict[str, Any]] = []
        self.completed: list[dict[str, Any]] = []
        self.failed: list[dict[str, Any]] = []
        self.fail_heartbeat_at: int | None = None
        self.analysis_checkpoint: dict[str, Any] | None = None

    def claim_pipeline_task(self, *, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        assert worker_id == "worker-A"
        assert lease_seconds == 90
        return self.task

    def get_active_membership(self, *, user_id: str, tenant_id: str) -> dict[str, Any] | None:
        assert (user_id, tenant_id) == ("user-1", "tenant-1")
        return self.membership

    def heartbeat_pipeline_task(self, **kwargs: Any) -> None:
        self.heartbeats.append(kwargs)
        if self.fail_heartbeat_at == len(self.heartbeats):
            raise SupabaseLeaseLost("stale token")

    def get_analysis_run_by_pipeline_task(
        self,
        *,
        pipeline_task_id: str,
        tenant_id: str,
    ) -> dict[str, Any] | None:
        assert pipeline_task_id == TASK_ID
        assert tenant_id == "tenant-1"
        return self.analysis_checkpoint

    def complete_pipeline_task(self, **kwargs: Any) -> None:
        self.completed.append(kwargs)

    def fail_pipeline_task(self, **kwargs: Any) -> None:
        self.failed.append(kwargs)


def _wire_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake: FakeQueueClient,
) -> None:
    """把 worker 限定在临时目录和进程内假队列，测试不会访问网络或正式 runtime。"""

    monkeypatch.setattr(worker, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(worker, "_workspace_root", lambda: tmp_path)


def _assert_no_heartbeat_thread() -> None:
    """每次单任务执行后都应回收心跳线程，防止测试或部署进程积累后台线程。"""

    assert not any(thread.name == f"heartbeat-{TASK_ID}" and thread.is_alive() for thread in threading.enumerate())


def test_worker_passes_lease_token_and_uses_fresh_membership_role(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = FakeQueueClient()
    _wire_worker(monkeypatch, tmp_path, fake)
    executed: dict[str, Any] = {}

    def execute(task_id: str, payload: dict[str, Any], request: worker.WorkerRequest) -> None:
        identity = request_identity(request)
        executed.update({"task_id": task_id, "payload": payload, "identity": identity})

    monkeypatch.setattr(worker, "_execute_cninfo_task", execute)
    monkeypatch.setattr(
        worker,
        "load_task",
        lambda _root, _task_id: (
            None
            if not executed
            else {"task_id": TASK_ID, "status": "completed", "request": fake.task["request_payload"]}
        ),
    )
    monkeypatch.setattr(worker, "materialize_task", lambda *_args, **_kwargs: {})

    assert worker.run_once(worker_id="worker-A", lease_seconds=90) is True
    assert executed["task_id"] == TASK_ID
    assert executed["identity"].role == "reviewer"
    assert executed["identity"].source == "worker"
    assert executed["identity"].tenant_id == "tenant-1"
    assert len(fake.heartbeats) >= 2
    assert all(call["lease_token"] == LEASE_TOKEN for call in fake.heartbeats)
    assert fake.completed[0]["lease_token"] == LEASE_TOKEN
    assert fake.completed[0]["result"]["status"] == "completed"
    assert fake.failed == []
    _assert_no_heartbeat_thread()


def test_stale_worker_stops_at_guard_and_never_reports_over_new_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = FakeQueueClient()
    # 两次显式阶段探针成功；模拟持久化写入前的第三次探针发现 token 已失效。
    fake.fail_heartbeat_at = 3
    _wire_worker(monkeypatch, tmp_path, fake)
    side_effects: list[str] = []

    def execute(_task_id: str, _payload: dict[str, Any], _request: worker.WorkerRequest) -> None:
        assert_worker_lease()
        side_effects.append("persisted")

    monkeypatch.setattr(worker, "_execute_cninfo_task", execute)
    monkeypatch.setattr(worker, "load_task", lambda *_args: None)
    monkeypatch.setattr(worker, "materialize_task", lambda *_args, **_kwargs: {})

    assert worker.run_once(worker_id="worker-A", lease_seconds=90) is True
    assert side_effects == []
    assert len(fake.heartbeats) == 3
    # 丢租约后连 fail 都不能写，否则可能清掉新 worker 的租约或错误结果。
    assert fake.completed == []
    assert fake.failed == []
    _assert_no_heartbeat_thread()


@pytest.mark.parametrize(
    "membership",
    [
        None,
        {"organization_id": "tenant-1", "user_id": "user-1", "role": "owner", "active": False},
        {"organization_id": "tenant-2", "user_id": "user-1", "role": "owner", "active": True},
        {"organization_id": "tenant-1", "user_id": "user-2", "role": "owner", "active": True},
        {"organization_id": "tenant-1", "user_id": "user-1", "role": "unknown", "active": True},
    ],
)
def test_revoked_or_mismatched_membership_fails_closed_without_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    membership: dict[str, Any] | None,
) -> None:
    fake = FakeQueueClient()
    fake.membership = membership
    _wire_worker(monkeypatch, tmp_path, fake)
    monkeypatch.setattr(worker, "_execute_cninfo_task", lambda *_args: pytest.fail("撤权任务不得执行"))

    assert worker.run_once(worker_id="worker-A", lease_seconds=90) is True
    assert fake.completed == []
    assert fake.failed[0]["lease_token"] == LEASE_TOKEN
    assert fake.failed[0]["retry"] is False
    assert fake.failed[0]["error"]["code"] == "WORKER_AUTHORIZATION_REVOKED"
    _assert_no_heartbeat_thread()


def test_identity_snapshot_mismatch_is_not_repaired_from_untrusted_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = FakeQueueClient()
    fake.task["request_payload"]["requested_by_identity"]["tenant_id"] = "tenant-other"
    _wire_worker(monkeypatch, tmp_path, fake)
    monkeypatch.setattr(worker, "_execute_cninfo_task", lambda *_args: pytest.fail("身份不一致任务不得执行"))

    assert worker.run_once(worker_id="worker-A", lease_seconds=90) is True
    assert fake.failed[0]["retry"] is False
    assert fake.failed[0]["error"]["code"] == "WORKER_AUTHORIZATION_REVOKED"
    assert fake.completed == []


def test_completed_checkpoint_only_repairs_queue_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = FakeQueueClient()
    _wire_worker(monkeypatch, tmp_path, fake)
    checkpoint = {
        "task_id": TASK_ID,
        "status": "completed",
        "request": fake.task["request_payload"],
        "result": {"status": "rag_ready"},
    }
    monkeypatch.setattr(worker, "load_task", lambda *_args: checkpoint)
    monkeypatch.setattr(worker, "materialize_task", lambda *_args, **_kwargs: pytest.fail("checkpoint 不应重建"))
    monkeypatch.setattr(worker, "_execute_cninfo_task", lambda *_args: pytest.fail("checkpoint 不应重跑模型"))

    assert worker.run_once(worker_id="worker-A", lease_seconds=90) is True
    assert fake.completed[0]["result"] is checkpoint
    assert fake.failed == []


def test_remote_analysis_checkpoint_completes_without_repeating_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = FakeQueueClient()
    fake.analysis_checkpoint = {
        "pipeline_task_id": TASK_ID,
        "tenant_id": "tenant-1",
        "payload": {
            "run_id": "RUN-V7-CHECKPOINT",
            "status": "candidate",
            "run_completeness": "complete_full_analysis",
            "context": {"case_id": "CASE-1", "pipeline_task_id": TASK_ID},
        },
    }
    _wire_worker(monkeypatch, tmp_path, fake)
    monkeypatch.setattr(worker, "load_task", lambda *_args: None)
    monkeypatch.setattr(worker, "materialize_task", lambda *_args, **_kwargs: pytest.fail("远程 checkpoint 不应重建任务"))
    monkeypatch.setattr(worker, "_execute_cninfo_task", lambda *_args: pytest.fail("远程 checkpoint 不应重跑模型"))

    assert worker.run_once(worker_id="worker-A", lease_seconds=90) is True
    recovered = fake.completed[0]["result"]
    assert recovered["status"] == "completed"
    assert recovered["result"]["analysis"]["run_id"] == "RUN-V7-CHECKPOINT"
    assert recovered["result"]["checkpoint_recovered"] is True
    assert fake.failed == []


def test_needs_human_maps_to_failed_so_confirm_can_use_failed_state_cas(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = FakeQueueClient()
    _wire_worker(monkeypatch, tmp_path, fake)
    executed = False
    needs_human = {
        "task_id": TASK_ID,
        "status": "needs_human",
        "request": fake.task["request_payload"],
        "error": {
            "code": "COMPANY_AMBIGUOUS",
            "detail": {"candidates": [{"ticker": "600000"}]},
        },
    }

    def execute(*_args: Any) -> None:
        nonlocal executed
        executed = True

    monkeypatch.setattr(worker, "_execute_cninfo_task", execute)
    monkeypatch.setattr(worker, "load_task", lambda *_args: needs_human if executed else None)
    monkeypatch.setattr(worker, "materialize_task", lambda *_args, **_kwargs: {})

    assert worker.run_once(worker_id="worker-A", lease_seconds=90) is True
    assert fake.completed == []
    assert fake.failed[0]["retry"] is False
    assert fake.failed[0]["error"] is needs_human
    assert fake.failed[0]["lease_token"] == LEASE_TOKEN


def test_missing_lease_token_never_starts_or_reports_task(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = FakeQueueClient()
    fake.task["lease_token"] = None
    _wire_worker(monkeypatch, tmp_path, fake)
    monkeypatch.setattr(worker, "_execute_cninfo_task", lambda *_args: pytest.fail("无 token 任务不得执行"))

    with pytest.raises(SupabaseLeaseLost):
        worker.run_once(worker_id="worker-A", lease_seconds=90)
    assert fake.heartbeats == []
    assert fake.completed == []
    assert fake.failed == []


def test_membership_service_failure_requeues_without_executing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = FakeQueueClient()

    def unavailable(**_kwargs: Any) -> None:
        raise SupabaseError("temporary")

    fake.get_active_membership = unavailable  # type: ignore[method-assign]
    _wire_worker(monkeypatch, tmp_path, fake)
    monkeypatch.setattr(worker, "_execute_cninfo_task", lambda *_args: pytest.fail("成员状态未知时不得执行"))

    assert worker.run_once(worker_id="worker-A", lease_seconds=90) is True
    assert fake.failed[0]["retry"] is True
    assert fake.failed[0]["lease_token"] == LEASE_TOKEN
    assert fake.failed[0]["error"]["code"] == "WORKER_EXECUTION_FAILED"


def test_worker_identity_rechecks_membership_and_exact_consent_for_each_model_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class ConsentClient:
        def get_active_membership(self, **kwargs: Any) -> dict[str, Any]:
            calls.append({"kind": "membership", **kwargs})
            return {"organization_id": "tenant-1", "user_id": "user-1", "role": "reviewer", "active": True}

        def get_active_model_transfer_consent(self, **kwargs: Any) -> dict[str, Any]:
            calls.append({"kind": "consent", **kwargs})
            return {"id": "consent-1"}

    monkeypatch.setattr(auth_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(auth_module, "get_supabase_client", lambda: ConsentClient())
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    request = worker.WorkerRequest(
        {"user_id": "user-1", "tenant_id": "tenant-1", "role": "reviewer"},
        task_id=TASK_ID,
        lease_probe=lambda: True,
    )
    case = {"case_id": "CASE-1", "tenant_id": "tenant-1", "sample_type": "authorized_deidentified"}

    # Agent 编排会在每个角色前调用同一 model_recheck；这里连续两次代表两个角色。
    assert authorize_model_transfer(request, case) is True
    assert authorize_model_transfer(request, case) is True
    membership_calls = [call for call in calls if call["kind"] == "membership"]
    consent_calls = [call for call in calls if call["kind"] == "consent"]
    assert len(membership_calls) == 2
    assert len(consent_calls) == 2
    assert all(call["tenant_id"] == "tenant-1" and call["user_id"] == "user-1" for call in consent_calls)
    assert all(call["case_id"] == "CASE-1" and call["case_tenant_id"] == "tenant-1" for call in consent_calls)
    assert all(call["provider"] == "api.deepseek.com" for call in consent_calls)
    assert all(call["model_id"] == "deepseek-v4-flash" for call in consent_calls)
    assert all(call["transmission_scope"] for call in consent_calls)
