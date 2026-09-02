"""队列 CAS、预热原子幂等、checkpoint 与公网检索 owner 合同。"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import BackgroundTasks, HTTPException
from starlette.requests import Request

from backend.app import main as main_module
from backend.app.auth import UserIdentity
from backend.app.schemas import CachePrewarmRequest, RagRetrieveRequest, RunRequest
from backend.app.supabase_adapter import SupabaseClient, SupabaseConflict


ROOT = Path(__file__).resolve().parents[2]


def _request(*, idempotency_key: str | None = None) -> Request:
    headers = [] if idempotency_key is None else [(b"idempotency-key", idempotency_key.encode("ascii"))]
    return Request({"type": "http", "headers": headers, "client": ("test", 1), "method": "POST", "path": "/"})


def test_requeue_uses_original_failed_status_and_attempt_and_second_tab_gets_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def requeue_pipeline_task(self, **kwargs: Any) -> None:
            calls.append(kwargs)
            if len(calls) > 1:
                raise SupabaseConflict("stale tab")

    identity = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner")
    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(main_module, "request_identity", lambda _request: identity)
    monkeypatch.setattr(main_module, "identity_for_task", lambda _request: identity.as_public_dict())
    monkeypatch.setattr(main_module, "_save_task", lambda _root, task: task)
    task = {"task_id": "CNINFO-CAS12345", "status": "queued", "request": {"company_query": "600000"}}

    main_module._queue_pipeline_task(
        BackgroundTasks(), task, task["request"], _request(),
        requeue=True, expected_status="failed", expected_attempt=2,
    )
    with pytest.raises(HTTPException) as stale:
        main_module._queue_pipeline_task(
            BackgroundTasks(), task, task["request"], _request(),
            requeue=True, expected_status="failed", expected_attempt=2,
        )
    assert stale.value.status_code == 409
    assert calls[0]["expected_status"] == "failed"
    assert calls[0]["expected_attempt"] == 2
    assert calls[1]["expected_status"] == "failed"
    assert calls[1]["expected_attempt"] == 2


@pytest.mark.parametrize("queue_status", ["queued", "running", "completed"])
def test_retry_route_rejects_nonfailed_database_states_before_local_rewrite(
    monkeypatch: pytest.MonkeyPatch,
    queue_status: str,
) -> None:
    task = {
        "task_id": "CNINFO-STRICT123",
        "status": queue_status,
        "attempt": 3,
        "tenant_id": "tenant-1",
        "requested_by": "user-1",
        "request": {"company_query": "600000"},
        "persistence": {"queue_status": queue_status},
    }
    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "_read_pipeline_task", lambda _task_id: deepcopy(task))
    monkeypatch.setattr(main_module, "authorize_pipeline_task", lambda *_args: None)
    monkeypatch.setattr(main_module, "queue_retry", lambda *_args, **_kwargs: pytest.fail("不应改写本地状态"))

    with pytest.raises(HTTPException) as rejected:
        main_module.retry_cninfo_pipeline(task["task_id"], BackgroundTasks(), _request())
    assert rejected.value.status_code == 409


def test_retry_and_confirm_routes_forward_remote_failed_cas_without_type_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = {
        "task_id": "CNINFO-ROUTECAS1",
        "status": "needs_human",
        "attempt": 2,
        "tenant_id": "tenant-1",
        "requested_by": "user-1",
        "request": {"company_query": "测试公司"},
        "error": {"code": "COMPANY_AMBIGUOUS", "detail": {"candidates": [{"ticker": "600000"}]}},
        "persistence": {"queue_status": "failed"},
    }
    forwarded: list[dict[str, Any]] = []
    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "_read_pipeline_task", lambda _task_id: deepcopy(base))
    monkeypatch.setattr(main_module, "authorize_pipeline_task", lambda *_args: None)
    monkeypatch.setattr(main_module, "load_task", lambda *_args: None)
    monkeypatch.setattr(main_module, "_save_task", lambda _root, task: task)

    def retry(_root: Path, _task_id: str, *, request_update: dict[str, Any] | None = None) -> dict[str, Any]:
        queued = deepcopy(base)
        queued["status"] = "queued"
        if request_update:
            queued["request"].update(request_update)
        return queued

    monkeypatch.setattr(main_module, "queue_retry", retry)
    monkeypatch.setattr(
        main_module,
        "_queue_pipeline_task",
        lambda *_args, **kwargs: forwarded.append(kwargs),
    )

    retried = main_module.retry_cninfo_pipeline(base["task_id"], BackgroundTasks(), _request())
    confirmed = main_module.confirm_cninfo_company(
        base["task_id"],
        SimpleNamespace(ticker="600000"),
        BackgroundTasks(),
        _request(),
    )
    assert retried["status"] == "queued"
    assert confirmed["confirmed_ticker"] == "600000"
    assert len(forwarded) == 2
    assert all(call["expected_status"] == "failed" and call["expected_attempt"] == 2 for call in forwarded)


def test_prewarm_reuses_batch_and_task_ids_for_same_owner_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner")
    local_tasks: dict[str, dict[str, Any]] = {}
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def enqueue_prewarm_batch(self, **kwargs: Any) -> None:
            calls.append(deepcopy(kwargs))

    def materialize(_root: Path, task_id: str, payload: dict[str, Any], *, attempt: int) -> dict[str, Any]:
        task = local_tasks.setdefault(
            task_id,
            {"task_id": task_id, "status": "queued", "request": deepcopy(payload), "attempt": attempt},
        )
        task["request"] = deepcopy(payload)
        return deepcopy(task)

    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "require_authenticated", lambda _request: identity)
    monkeypatch.setattr(main_module, "identity_for_task", lambda _request: identity.as_public_dict())
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(main_module, "materialize_task", materialize)
    monkeypatch.setattr(main_module, "load_task", lambda _root, task_id: deepcopy(local_tasks.get(task_id)))
    monkeypatch.setattr(
        main_module,
        "_save_task",
        lambda _root, task: local_tasks.__setitem__(task["task_id"], deepcopy(task)) or task,
    )
    monkeypatch.setattr(main_module, "create_refresh_job", lambda *_args, **_kwargs: {})
    body = CachePrewarmRequest(companies=["600000", "000001"], years=2, analysis_mode="rag_only")

    first = main_module.prewarm_catalog(body, BackgroundTasks(), _request(idempotency_key="same-key-123"))
    second = main_module.prewarm_catalog(body, BackgroundTasks(), _request(idempotency_key="same-key-123"))

    assert first["batch_id"] == second["batch_id"]
    assert [item["task_id"] for item in first["tasks"]] == [item["task_id"] for item in second["tasks"]]
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert all(task["request_payload"]["requested_by_identity"]["user_id"] == "user-1" for task in calls[0]["tasks"])


def test_schema_reaps_third_crash_before_claiming_next_and_prewarm_is_one_rpc() -> None:
    schema = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8")
    claim = schema[schema.index("create or replace function public.claim_pipeline_task"):]
    assert claim.index("attempt >= 3") < claim.index("select * into claimed")
    assert "LEASE_RETRY_EXHAUSTED" in claim
    assert "status = 'running' and lease_until < now() and attempt < 3" in claim
    atomic = schema[schema.index("create or replace function public.enqueue_prewarm_batch"):]
    assert "pg_advisory_xact_lock" in atomic
    assert "insert into public.cache_prewarm_batches" in atomic
    assert "insert into public.pipeline_tasks" in atomic
    assert "prewarm idempotency key payload mismatch" in atomic


def test_adapter_checkpoint_query_is_exact_tenant_and_task(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object.__new__(SupabaseClient)
    observed: dict[str, Any] = {}

    def select_table(table: str, **kwargs: Any) -> list[dict[str, Any]]:
        observed.update({"table": table, **kwargs})
        return [{"pipeline_task_id": "CNINFO-CHECK123", "tenant_id": "tenant-A", "payload": {}}]

    monkeypatch.setattr(client, "select_table", select_table)
    row = client.get_analysis_run_by_pipeline_task(
        pipeline_task_id="CNINFO-CHECK123",
        tenant_id="tenant-A",
    )
    assert row and row["tenant_id"] == "tenant-A"
    assert observed["filters"] == {
        "pipeline_task_id": "eq.CNINFO-CHECK123",
        "tenant_id": "eq.tenant-A",
    }


def test_worker_task_id_produces_stable_run_id_and_persisted_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, Any]] = []

    class FakeClient:
        def persist_run(self, **kwargs: Any) -> dict[str, Any]:
            persisted.append(deepcopy(kwargs))
            return {"backend": "supabase", "run_id": kwargs["run"]["run_id"]}

    request = _request()
    request.state.audittrace_pipeline_task_id = "CNINFO-CHECKPOINT1"
    request.state.audittrace_worker_lease_probe = lambda: True
    context = {
        "case_id": "PUBLIC_CASE",
        "t0": "2026-04-30",
        "model_transfer_allowed": False,
        "request_identity": {"user_id": "user-A", "tenant_id": "tenant-A", "role": "owner"},
    }
    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(main_module, "_case_record", lambda *_args, **_kwargs: {"case_id": "PUBLIC_CASE", "sample_type": "public"})
    monkeypatch.setattr(main_module, "save_run", lambda _root, response: response)

    def execute() -> Any:
        return main_module._execute_run(
            context=context,
            sources=[],
            rule_ids=[],
            run_mode="calculation_only",
            r2_min_gap=0.0,
            planned_materiality=None,
            r1_gap_threshold=0.15,
            r1_strong_gap_threshold=0.30,
            r1_absolute_threshold=0.0,
            http_request=request,
            run_prefix="RUN-V7",
        )

    first = execute()
    second = execute()
    assert first.run_id == second.run_id
    assert first.context["pipeline_task_id"] == "CNINFO-CHECKPOINT1"
    assert len(persisted) == 2
    assert all(call["pipeline_task_id"] == "CNINFO-CHECKPOINT1" for call in persisted)
    assert all(call["tenant_id"] == "tenant-A" for call in persisted)


def test_local_public_retrieval_is_persisted_with_current_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, Any]] = []
    identity = UserIdentity(user_id="user-A", tenant_id="tenant-A", role="member")
    case = {"case_id": "PUBLIC_CASE", "sample_type": "public", "company_name": "公开企业"}

    class FakeClient:
        def get_remote_rag_status(self, **_kwargs: Any) -> dict[str, Any]:
            return {
                "status": "ready",
                "case_scope": "PUBLIC:PUBLIC_CASE",
                "rag_snapshot_id": "SNAP-A",
                "index_version": "rag-v1.2-case-isolated-hash-ngram-faiss-20260728",
                "chunk_count": 0,
            }

        def persist_rag_retrieval(self, **kwargs: Any) -> None:
            persisted.append(kwargs)

    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "_identity_tenant", lambda *_args, **_kwargs: "tenant-A")
    monkeypatch.setattr(main_module, "_case_record", lambda *_args, **_kwargs: case)
    monkeypatch.setattr(main_module, "authorize_case_access", lambda *_args: identity)
    monkeypatch.setattr(main_module, "request_identity", lambda _request: identity)
    monkeypatch.setattr(main_module, "get_case", lambda *_args, **_kwargs: case)
    monkeypatch.setattr(main_module, "retrieve", lambda *_args, **_kwargs: {"retrieval_id": "RET-OWNER123", "results": []})
    monkeypatch.setattr(
        main_module,
        "rag_status",
        lambda *_args, **_kwargs: {
            "status": "ready",
            "rag_snapshot_id": "SNAP-A",
            "index_version": "rag-v1.2-case-isolated-hash-ngram-faiss-20260728",
            "chunk_count": 0,
        },
    )
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: FakeClient())

    result = main_module.rag_retrieve(
        RagRetrieveRequest(query="信用政策", case_id="PUBLIC_CASE", company_name="公开企业"),
        _request(),
    )
    assert result["retrieval_id"] == "RET-OWNER123"
    assert persisted[0]["owner_tenant_id"] == "tenant-A"
    assert persisted[0]["requested_by"] == "user-A"
    assert persisted[0]["payload"]["case_id"] == "PUBLIC_CASE"


def test_public_retrieval_log_does_not_trust_local_copy_for_other_owner_or_anonymous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = {"case_id": "PUBLIC_CASE", "sample_type": "public", "company_name": "公开企业"}
    current_tenant: dict[str, str | None] = {"value": "tenant-A"}

    class FakeClient:
        def get_rag_retrieval(self, _retrieval_id: str, *, owner_tenant_id: str | None) -> dict[str, Any] | None:
            if owner_tenant_id != "tenant-A":
                return None
            return {
                "case_id": "PUBLIC_CASE",
                "tenant_id": "tenant-A",
                "payload": {"retrieval_id": "RET-PRIVATEA", "case_id": "PUBLIC_CASE", "results": []},
            }

    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "_identity_tenant", lambda *_args, **_kwargs: current_tenant["value"])
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(main_module, "get_retrieval", lambda *_args: pytest.fail("公网不得读取无 owner 本机日志"))
    monkeypatch.setattr(main_module, "_case_record", lambda *_args, **_kwargs: case)
    monkeypatch.setattr(main_module, "authorize_case_access", lambda *_args: None)

    assert main_module.read_retrieval_log("RET-PRIVATEA", _request())["retrieval_id"] == "RET-PRIVATEA"
    for other in ("tenant-B", None):
        current_tenant["value"] = other
        with pytest.raises(HTTPException) as hidden:
            main_module.read_retrieval_log("RET-PRIVATEA", _request())
        assert hidden.value.status_code == 404


def test_remote_private_case_is_not_shadowed_by_same_id_global_public_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = "STD-R1-2024-001"
    global_public = {
        "case_id": case_id,
        "sample_type": "public",
        "tenant_id": None,
        "source_snapshot_id": "PUBLIC-SNAPSHOT",
        "financial_fields": [{"field_id": "public", "year": 2024, "value": 1}],
    }
    private_a = {
        "case_id": case_id,
        "sample_type": "internal",
        "tenant_id": "tenant-A",
        "source_snapshot_id": "PRIVATE-A-SNAPSHOT",
        "financial_fields": [{"field_id": "private-a", "year": 2024, "value": 999}],
    }

    class FakeClient:
        def get_case_bundle(self, _case_id: str, *, tenant_id: str | None) -> dict[str, Any] | None:
            assert tenant_id == "tenant-A"
            return deepcopy(private_a)

    def local_case(_root: Path, _case_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
        # 模拟旧全局内置/公开案例与远端租户私有案例使用完全相同的 case_id。
        return None if tenant_id else deepcopy(global_public)

    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "get_case", local_case)
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: FakeClient())

    resolved = main_module._case_record(case_id, tenant_id="tenant-A")
    assert resolved and resolved["tenant_id"] == "tenant-A"
    assert resolved["financial_fields"][0]["value"] == 999


def test_public_field_overlay_survives_get_and_run_without_leaking_to_other_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = "PUBLIC_OVERLAY_CASE"
    current_tenant = {"value": "tenant-A"}
    current_identity = {
        "tenant-A": UserIdentity(user_id="user-A", tenant_id="tenant-A", role="owner"),
        "tenant-B": UserIdentity(user_id="user-B", tenant_id="tenant-B", role="owner"),
    }
    base_rows = [
        {"field_id": "revenue_2025", "field_kind": "revenue", "year": 2025, "value": 1000},
        {"field_id": "revenue_2024", "field_kind": "revenue", "year": 2024, "value": 900},
        {"field_id": "accounts_receivable_2025", "field_kind": "accounts_receivable", "year": 2025, "value": 100},
        {"field_id": "accounts_receivable_2024", "field_kind": "accounts_receivable", "year": 2024, "value": 90},
    ]
    local_public = {
        "case_id": case_id,
        "sample_type": "public",
        "tenant_id": None,
        "source_snapshot_id": "SNAP-PUBLIC",
        "financial_fields": deepcopy(base_rows),
    }

    class FakeClient:
        def get_case_bundle(self, _case_id: str, *, tenant_id: str | None) -> dict[str, Any]:
            rows = deepcopy(base_rows)
            if tenant_id == "tenant-A":
                next(row for row in rows if row["field_id"] == "accounts_receivable_2025")["value"] = 777
            return {
                **deepcopy(local_public),
                "company_name": "公开公司",
                "t0": "2026-04-30",
                "financial_fields": rows,
                "documents": [],
            }

    def local_case(_root: Path, _case_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
        return None if tenant_id else deepcopy(local_public)

    captured_cases: list[dict[str, Any]] = []
    monkeypatch.setattr(main_module, "supabase_enabled", lambda: True)
    monkeypatch.setattr(main_module, "get_case", local_case)
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(main_module, "_identity_tenant", lambda *_args, **_kwargs: current_tenant["value"])
    monkeypatch.setattr(main_module, "authorize_case_access", lambda *_args: current_identity[current_tenant["value"]])
    monkeypatch.setattr(main_module, "authorize_model_transfer", lambda *_args: False)
    monkeypatch.setattr(main_module, "request_identity", lambda _request: current_identity[current_tenant["value"]])
    monkeypatch.setattr(main_module, "_ensure_public_standard_sources", lambda *_args: None)
    monkeypatch.setattr(
        main_module,
        "evaluate_industry_gate",
        lambda **_kwargs: {"fit_level": "applicable", "specialized_rule": None},
    )

    def remote_sources(case: dict[str, Any], _year: int, _rules: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        captured_cases.append(deepcopy(case))
        return ({"case_id": case_id, "t0": "2026-04-30", "model_transfer_allowed": False}, [])

    monkeypatch.setattr(main_module, "_remote_period_sources", remote_sources)
    monkeypatch.setattr(main_module, "_execute_run", lambda **kwargs: kwargs)

    for tenant, expected in (("tenant-A", 777), ("tenant-B", 100)):
        current_tenant["value"] = tenant
        detail = main_module.get_case_detail(case_id, _request())
        detail_value = next(row["value"] for row in detail["financial_fields"] if row["field_id"] == "accounts_receivable_2025")
        assert detail_value == expected
        main_module.run_rules(RunRequest(case_id=case_id, current_year=2025, rule_ids=["R1"]), _request())
        run_value = next(
            row["value"]
            for row in captured_cases[-1]["financial_fields"]
            if row["field_id"] == "accounts_receivable_2025"
        )
        assert run_value == expected
