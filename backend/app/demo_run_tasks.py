"""竞赛演示的异步运行任务：真实六阶段、重启关闭与取消一致性。

任务台账只记录公开进度和已脱敏的失败码。它不保存模型原文、密钥或证据正文；
前端只轮询台账，绝不自己推进任何阶段。
"""
from __future__ import annotations

import json
import hashlib
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


STAGE_SCHEMA_VERSION = "demo_task_v2"
STAGE_ORDER = (
    "evidence_load",
    "rule_calculation",
    "knowledge_retrieval",
    "agent_collaboration",
    "evidence_validation",
    "structured_output",
)
AGENT_ROLE_ORDER = ("challenge", "counter", "review")
STAGE_STATUSES = ("pending", "running", "completed", "skipped", "degraded", "failed")
TASK_STATUSES = (
    "queued", "running", "completed", "degraded", "failed", "cancelled", "interrupted",
    "expired",
)
TASK_ID_PREFIX = "DEMO-RUN"
ACTIVE_STATUSES = {"queued", "running"}


class IdempotencyConflict(ValueError):
    """同一幂等键绑定了不同请求；服务端必须返回 409 而不是重复调用。"""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _retention_seconds() -> int:
    """读取结果保留期；异常配置回退到七天，避免形成永久台账。"""

    try:
        return max(3600, min(30 * 24 * 3600, int(os.getenv("AUDITTRACE_DEMO_TASK_RETENTION_HOURS", "168")) * 3600))
    except (TypeError, ValueError):
        return 7 * 24 * 3600


def _request_digest(case_id: str, run_body: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"case_id": case_id, "request": run_body},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def result_expiry_iso() -> str:
    """返回公开结果的绝对到期时间，供本地与远程台账共用。"""

    return (datetime.now(timezone.utc) + timedelta(seconds=_retention_seconds())).isoformat()


class DemoRunTaskStore:
    """线程安全的演示任务台账（内存 + JSON）。

    重启时无法安全续接已经中断的 Python 工作线程，因此把旧活动任务显式结算为
    ``interrupted``；这比恢复一个永远不会继续的“running”状态更诚实。
    """

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="demo-run")
        self._load_existing_tasks()

    def _file_path(self, task_id: str) -> Path:
        safe = "".join(ch for ch in task_id if ch.isalnum() or ch == "-")
        return self.directory / f"{safe}.json"

    def _load_file(self, task_id: str) -> dict[str, Any] | None:
        path = self._file_path(task_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _save_file(self, task: dict[str, Any]) -> None:
        path = self._file_path(str(task["task_id"]))
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(task, handle, ensure_ascii=False, indent=2)
        tmp.replace(path)

    def _load_existing_tasks(self) -> None:
        """加载既有台账，并关闭服务重启前未完成的任务。"""
        with self._lock:
            for path in sorted(self.directory.glob("DEMO-RUN-*.json")):
                task = self._load_file(path.stem)
                if task is None or not task.get("task_id"):
                    continue
                task.setdefault("stage_schema_version", STAGE_SCHEMA_VERSION)
                task.setdefault("non_interruptible", False)
                task.setdefault("steps", {})
                task.setdefault("agent_steps", {})
                if task.get("status") in ACTIVE_STATUSES:
                    task["status"] = "interrupted"
                    task["failure_code"] = "TASK_INTERRUPTED_BY_RESTART"
                    task["error"] = "服务重启前的后台任务无法安全续接，已如实关闭。"
                    task["result"] = None
                    for stage in STAGE_ORDER:
                        item = task["steps"].setdefault(stage, {"status": "pending", "detail": "未记录"})
                        if item.get("status") in {"pending", "running"}:
                            task["steps"][stage] = {
                                "status": "skipped",
                                "detail": "服务重启导致任务中断，后续阶段未执行。",
                                "updated_at": _iso_now(),
                            }
                    for role in AGENT_ROLE_ORDER:
                        item = task["agent_steps"].setdefault(role, {"status": "pending", "detail": "未记录"})
                        if item.get("status") in {"pending", "running"}:
                            task["agent_steps"][role] = {
                                "status": "skipped",
                                "detail": "服务重启导致任务中断，未调用或未完成。",
                                "updated_at": _iso_now(),
                            }
                    task["updated_at"] = _iso_now()
                    self._save_file(task)
                elif task.get("status") in {"completed", "degraded"} and self._is_expired(task):
                    task["status"] = "expired"
                    task["failure_code"] = "TASK_RESULT_EXPIRED"
                    task["error"] = "演示结果已超过公开保留期。"
                    task["result"] = None
                    task["updated_at"] = _iso_now()
                    self._save_file(task)
                self._tasks[str(task["task_id"])] = task

    def _new_task(self, case_id: str, run_body: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        task_id = f"{TASK_ID_PREFIX}-{uuid.uuid4().hex[:12].upper()}"
        now = _iso_now()
        digest = _request_digest(case_id, run_body)
        return {
            "task_id": task_id,
            "stage_schema_version": STAGE_SCHEMA_VERSION,
            "case_id": case_id,
            "retry_of_task_id": run_body.get("retry_of_task_id"),
            "run_body": run_body,
            "request_sha256": digest,
            "idempotency_key_sha256": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest() if idempotency_key else None,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "non_interruptible": False,
            "steps": {stage: {"status": "pending", "detail": "等待开始"} for stage in STAGE_ORDER},
            "agent_steps": {role: {"status": "pending", "detail": "等待开始"} for role in AGENT_ROLE_ORDER},
            "run_id": None,
            "failure_code": None,
            "error": None,
            "result": None,
            "result_expires_at": None,
        }

    @staticmethod
    def _is_expired(task: dict[str, Any]) -> bool:
        value = str(task.get("result_expires_at") or "").strip()
        if not value:
            return False
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")) <= datetime.now(timezone.utc)
        except ValueError:
            return False

    def _expire_if_needed(self, task: dict[str, Any]) -> None:
        if task.get("status") not in {"completed", "degraded"} or not self._is_expired(task):
            return
        task["status"] = "expired"
        task["failure_code"] = "TASK_RESULT_EXPIRED"
        task["error"] = "演示结果已超过公开保留期。"
        task["result"] = None
        task["updated_at"] = _iso_now()
        self._save_file(task)

    def create(
        self,
        case_id: str,
        run_body: dict[str, Any],
        executor: Callable[[dict[str, Any]], Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """创建任务；同案例活动任务必须复用，不能因重复点击产生第二次调用。"""
        digest = _request_digest(case_id, run_body)
        idempotency_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest() if idempotency_key else None
        with self._lock:
            for task in self._tasks.values():
                self._expire_if_needed(task)
                if idempotency_digest and task.get("idempotency_key_sha256") == idempotency_digest:
                    if task.get("request_sha256") != digest:
                        raise IdempotencyConflict("该 Idempotency-Key 已绑定另一份请求。")
                    return task
                if (
                    task.get("case_id") == case_id
                    and task.get("request_sha256") == digest
                    and task.get("status") in ACTIVE_STATUSES
                ):
                    return task
            task = self._new_task(case_id, run_body, idempotency_key=idempotency_key)
            self._tasks[task["task_id"]] = task
            self._save_file(task)
        self._executor.submit(self._run_wrapper, task["task_id"], executor)
        return self.get(task["task_id"]) or task

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                task = self._load_file(task_id)
                if task is not None:
                    self._tasks[task_id] = task
            if task is not None:
                self._expire_if_needed(task)
            return task

    def is_cancelled(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id) or self._load_file(task_id)
            return bool(task and task.get("status") == "cancelled")

    def update_stage(self, task_id: str, stage: str, status: str, detail: str) -> None:
        if stage not in STAGE_ORDER:
            return
        if status not in STAGE_STATUSES:
            raise ValueError(f"unknown stage status: {status}")
        with self._lock:
            task = self._tasks.get(task_id) or self._load_file(task_id)
            if task is None or task.get("status") in {
                "completed", "degraded", "failed", "cancelled", "interrupted", "expired",
            }:
                return
            current = task["steps"].setdefault(stage, {"status": "pending", "detail": "等待开始"}).get("status", "pending")
            rank = {"pending": 0, "running": 1, "completed": 2, "degraded": 2, "skipped": 2, "failed": 2}
            if rank[status] < rank.get(current, 0):
                return
            stage_index = STAGE_ORDER.index(stage)
            if status in {"running", "completed", "degraded", "failed"} and any(
                task["steps"].setdefault(previous, {"status": "pending", "detail": "等待开始"}).get("status")
                not in {"completed", "degraded", "failed", "skipped"}
                for previous in STAGE_ORDER[:stage_index]
            ):
                # 后端业务节点必须按六阶段顺序写入；乱序事件被丢弃，避免页面
                # 显示一个尚未载入证据却已经“完成”的后续阶段。
                return
            task["steps"][stage] = {"status": status, "detail": detail, "updated_at": _iso_now()}
            # 从协作阶段起可能已经发生外部调用；取消端点必须明确拒绝，而不能
            # 标记为 cancelled 后再被后台真实结果覆盖。
            if stage == "agent_collaboration" and status == "running":
                task["non_interruptible"] = True
            task["updated_at"] = _iso_now()
            self._save_file(task)

    def update_agent_step(self, task_id: str, role: str, status: str, detail: str) -> None:
        if role not in AGENT_ROLE_ORDER:
            return
        with self._lock:
            task = self._tasks.get(task_id) or self._load_file(task_id)
            if task is None or task.get("status") in {
                "completed", "degraded", "failed", "cancelled", "interrupted", "expired",
            }:
                return
            task["agent_steps"][role] = {"status": status, "detail": detail, "updated_at": _iso_now()}
            task["updated_at"] = _iso_now()
            self._save_file(task)

    def update_task(self, task_id: str, **fields: Any) -> None:
        with self._lock:
            task = self._tasks.get(task_id) or self._load_file(task_id)
            if task is None:
                return
            # 取消/重启中断是不可覆盖的终态：后台 Agent 返回即使晚到，也不能
            # 把 run_id、result 或 completed 状态写回已取消任务。
            if task.get("status") in {
                "completed", "degraded", "failed", "cancelled", "interrupted", "expired",
            }:
                return
            task.update(fields)
            task["updated_at"] = _iso_now()
            self._save_file(task)

    def cancel(self, task_id: str) -> dict[str, Any] | None:
        """取消可中断任务；协作阶段起返回可识别的不可中断结果。"""
        with self._lock:
            task = self._tasks.get(task_id) or self._load_file(task_id)
            if task is None or task.get("status") not in ACTIVE_STATUSES:
                return None
            if task.get("non_interruptible"):
                return {**task, "cancel_rejected": True, "failure_code": "TASK_NON_INTERRUPTIBLE"}
            task["status"] = "cancelled"
            task["failure_code"] = "TASK_CANCELLED"
            task["error"] = "用户在外部模型调用前取消了任务。"
            for stage in STAGE_ORDER:
                item = task["steps"].setdefault(stage, {"status": "pending", "detail": "等待开始"})
                if item.get("status") in {"pending", "running"}:
                    task["steps"][stage] = {
                        "status": "skipped",
                        "detail": "任务已取消，阶段未执行。",
                        "updated_at": _iso_now(),
                    }
            for role in AGENT_ROLE_ORDER:
                item = task["agent_steps"].setdefault(role, {"status": "pending", "detail": "等待开始"})
                if item.get("status") in {"pending", "running"}:
                    task["agent_steps"][role] = {
                        "status": "skipped",
                        "detail": "任务已取消，角色未调用。",
                        "updated_at": _iso_now(),
                    }
            task["updated_at"] = _iso_now()
            self._save_file(task)
            return task

    def _run_wrapper(self, task_id: str, executor: Callable[[dict[str, Any]], Any]) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.get("status") == "cancelled":
                return
            task["status"] = "running"
            task["updated_at"] = _iso_now()
            self._save_file(task)
        try:
            executor(task)
        except Exception as error:  # noqa: BLE001 - worker 边界负责失败关闭
            with self._lock:
                task = self._tasks.get(task_id) or self._load_file(task_id)
                if task is None or task.get("status") in {
                    "completed", "degraded", "failed", "cancelled", "interrupted", "expired",
                }:
                    return
                task["status"] = "failed"
                task["failure_code"] = "TASK_EXECUTION_ERROR"
                task["error"] = f"{type(error).__name__}: {str(error)[:400]}"
                self._save_file(task)

    def snapshot(self, task_id: str) -> dict[str, Any] | None:
        task = self.get(task_id)
        if task is None:
            return None
        # JSON round-trip gives callers a stable detached view and excludes request body.
        view = json.loads(json.dumps(task, ensure_ascii=False))
        view.pop("run_body", None)
        view.pop("non_interruptible", None)
        view.pop("_file_path", None)
        if view.get("status") in {"failed", "cancelled", "interrupted", "expired"}:
            # 失败或不可读终态只展示阶段和失败码；结果正文不能被下载接口或
            # 任务轮询误当作可导出成果。
            view["result"] = None
        return view

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class SupabaseDemoRunTaskStore:
    """公开演示任务的 Supabase 台账实现。

    核心案例仍可运行在 local 模式；只有公开 task/result 通过 service-role
    适配器写入共享 Postgres。Web 进程退出时不重放模型调用，下一次读取会
    将过期租约结算为 ``interrupted``。
    """

    def __init__(self, client: Any) -> None:
        self.client = client
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="demo-run")
        self._owner = f"web-{uuid.uuid4().hex[:16]}"
        try:
            self._lease_seconds = max(30, min(900, int(os.getenv("AUDITTRACE_DEMO_TASK_LEASE_SECONDS", "180"))))
        except (TypeError, ValueError):
            self._lease_seconds = 180

    @staticmethod
    def _row_to_task(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        task = dict(row)
        task["run_body"] = task.get("request_payload") if isinstance(task.get("request_payload"), dict) else {}
        task["steps"] = task.get("steps") if isinstance(task.get("steps"), dict) else {}
        task["agent_steps"] = task.get("agent_steps") if isinstance(task.get("agent_steps"), dict) else {}
        task.setdefault("stage_schema_version", STAGE_SCHEMA_VERSION)
        task.setdefault("non_interruptible", False)
        return task

    @staticmethod
    def _public_task(task: dict[str, Any]) -> dict[str, Any]:
        view = json.loads(json.dumps(task, ensure_ascii=False))
        view.pop("run_body", None)
        view.pop("request_payload", None)
        view.pop("request_sha256", None)
        view.pop("idempotency_key_sha256", None)
        view.pop("lease_token", None)
        view.pop("lease_owner", None)
        view.pop("lease_until", None)
        view.pop("version", None)
        if view.get("status") in {"failed", "cancelled", "interrupted", "expired"}:
            view["result"] = None
        return view

    def _persist(self, task: dict[str, Any], *, expected_version: int | None = None) -> dict[str, Any] | None:
        fields = {
            "status": task.get("status"),
            "steps": task.get("steps") or {},
            "agent_steps": task.get("agent_steps") or {},
            "run_id": task.get("run_id"),
            "failure_code": task.get("failure_code"),
            "error": task.get("error"),
            "result": task.get("result"),
            "result_expires_at": task.get("result_expires_at"),
            "non_interruptible": bool(task.get("non_interruptible")),
        }
        if task.get("status") in {"completed", "degraded", "failed", "cancelled", "interrupted", "expired"}:
            fields.update({"lease_token": None, "lease_owner": None, "lease_until": None})
        version = int(task.get("version") if expected_version is None else expected_version)
        return self.client.update_demo_run_task(
            task_id=str(task["task_id"]),
            values=fields,
            expected_version=version,
            lease_token=str(task.get("lease_token") or "") or None,
        )

    def _mutate(self, task_id: str, updater: Callable[[dict[str, Any]], None]) -> dict[str, Any] | None:
        for _ in range(5):
            task = self.get(task_id)
            if task is None or task.get("status") in {
                "completed", "degraded", "failed", "cancelled", "interrupted", "expired",
            }:
                return task
            expected = int(task.get("version") or 0)
            updater(task)
            saved = self._persist(task, expected_version=expected)
            if saved:
                return self._row_to_task(saved)
        return self.get(task_id)

    def create(
        self,
        case_id: str,
        run_body: dict[str, Any],
        executor: Callable[[dict[str, Any]], Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        from .supabase_adapter import SupabaseConflict, SupabaseRequestError

        digest = _request_digest(case_id, run_body)
        idempotency_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest() if idempotency_key else None
        with self._lock:
            if idempotency_digest:
                existing = self.client.find_demo_run_task_by_idempotency(idempotency_key_sha256=idempotency_digest)
                if existing:
                    if str(existing.get("request_sha256") or "") != digest:
                        raise IdempotencyConflict("该 Idempotency-Key 已绑定另一份请求。")
                    return self._public_task(self._row_to_task(existing) or existing)
            active = self.client.find_active_demo_run_task(case_id=case_id, request_sha256=digest)
            if active:
                return self._public_task(self._row_to_task(active) or active)
            now = _iso_now()
            task_id = f"{TASK_ID_PREFIX}-{uuid.uuid4().hex[:12].upper()}"
            row = {
                "task_id": task_id,
                "stage_schema_version": STAGE_SCHEMA_VERSION,
                "case_id": case_id,
                "retry_of_task_id": run_body.get("retry_of_task_id"),
                "task_kind": str(run_body.get("kind") or "fixed_public_demo"),
                "request_payload": run_body,
                "request_sha256": digest,
                "idempotency_key_sha256": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest() if idempotency_key else None,
                "status": "queued",
                "created_at": now,
                "updated_at": now,
                "non_interruptible": False,
                "steps": {stage: {"status": "pending", "detail": "等待开始"} for stage in STAGE_ORDER},
                "agent_steps": {role: {"status": "pending", "detail": "等待开始"} for role in AGENT_ROLE_ORDER},
                "run_id": None,
                "failure_code": None,
                "error": None,
                "result": None,
                "result_expires_at": None,
                "version": 0,
            }
            try:
                inserted = self.client.insert_demo_run_task(row)
            except SupabaseRequestError as error:
                # partial unique index 竞争时，返回已经成功插入的同请求任务。
                active = self.client.find_active_demo_run_task(case_id=case_id, request_sha256=digest)
                if active:
                    return self._public_task(self._row_to_task(active) or active)
                raise SupabaseConflict("演示任务创建发生并发冲突。") from error
            task = self._row_to_task(inserted) or row
            if os.getenv("AUDITTRACE_DEMO_EXECUTOR_MODE", "web").strip().lower() == "worker":
                # Worker 模式由独立进程按数据库租约领取；Web 只入队，不在
                # 请求进程中偷偷启动线程，也不会把付费 Worker 误写进默认 Blueprint。
                return self._public_task(task)
            claimed = self.client.claim_demo_run_task(
                task_id=task_id,
                owner=self._owner,
                lease_seconds=self._lease_seconds,
            )
            if claimed:
                claimed_task = self._row_to_task(claimed) or task
                self._executor.submit(self._run_wrapper, claimed_task, executor)
                task = claimed_task
            return self._public_task(task)

    def claim_next(self) -> dict[str, Any] | None:
        """Worker 模式领取一个 queued 任务；返回含租约的内部任务。"""

        claimed = self.client.claim_next_demo_run_task(owner=self._owner, lease_seconds=self._lease_seconds)
        return self._row_to_task(claimed)

    def _run_wrapper(self, task: dict[str, Any], executor: Callable[[dict[str, Any]], Any]) -> None:
        task_id = str(task["task_id"])
        stop = threading.Event()
        lease_token = str(task.get("lease_token") or "")

        def heartbeat() -> None:
            while not stop.wait(max(10.0, self._lease_seconds / 3)):
                try:
                    if not self.client.heartbeat_demo_run_task(
                        task_id=task_id,
                        owner=self._owner,
                        lease_token=lease_token,
                        lease_seconds=self._lease_seconds,
                    ):
                        return
                except Exception:  # noqa: BLE001 - 后续 CAS 会阻止失租写入
                    return

        thread = threading.Thread(target=heartbeat, name=f"heartbeat-{task_id}", daemon=True)
        thread.start()
        lease_token_context = None
        try:
            from .supabase_adapter import install_worker_lease_guard

            lease_token_context = install_worker_lease_guard(
                lambda: self.client.demo_run_task_lease_current(
                    task_id=task_id,
                    owner=self._owner,
                    lease_token=lease_token,
                )
            )
            # 业务层在下载、模型调用和最终落盘前会读取此探针；租约失效
            # 时旧 worker 不能继续产生高成本或覆盖新结果。
            request = getattr(executor, "__audittrace_request__", None)
            if request is not None:
                request.state.audittrace_worker_lease_probe = lambda: self.client.demo_run_task_lease_current(
                    task_id=task_id,
                    owner=self._owner,
                    lease_token=lease_token,
                )
            executor(task)
        except Exception as error:  # noqa: BLE001 - worker boundary fail closed
            self.update_task(
                task_id,
                status="failed",
                failure_code="TASK_EXECUTION_ERROR",
                error="任务执行异常，详情已记录在服务端日志。",
            )
        finally:
            stop.set()
            thread.join(timeout=2)
            if lease_token_context is not None:
                from .supabase_adapter import reset_worker_lease_guard

                reset_worker_lease_guard(lease_token_context)

    def get(self, task_id: str) -> dict[str, Any] | None:
        self.client.interrupt_expired_demo_run_tasks()
        task = self._row_to_task(self.client.get_demo_run_task(task_id))
        if task and task.get("status") in {"completed", "degraded"} and DemoRunTaskStore._is_expired(task):
            expected = int(task.get("version") or 0)
            task["status"] = "expired"
            task["failure_code"] = "TASK_RESULT_EXPIRED"
            task["error"] = "演示结果已超过公开保留期。"
            task["result"] = None
            self._persist(task, expected_version=expected)
            task = self._row_to_task(self.client.get_demo_run_task(task_id))
        return task

    def snapshot(self, task_id: str) -> dict[str, Any] | None:
        task = self.get(task_id)
        return self._public_task(task) if task else None

    def is_cancelled(self, task_id: str) -> bool:
        task = self.get(task_id)
        return bool(task and task.get("status") == "cancelled")

    def update_stage(self, task_id: str, stage: str, status: str, detail: str) -> None:
        if stage not in STAGE_ORDER or status not in STAGE_STATUSES:
            if stage in STAGE_ORDER:
                raise ValueError(f"unknown stage status: {status}")
            return
        rank = {"pending": 0, "running": 1, "completed": 2, "degraded": 2, "skipped": 2, "failed": 2}

        def updater(task: dict[str, Any]) -> None:
            steps = task.setdefault("steps", {})
            current = steps.setdefault(stage, {"status": "pending", "detail": "等待开始"}).get("status", "pending")
            if rank[status] < rank.get(current, 0):
                return
            index = STAGE_ORDER.index(stage)
            if status in {"running", "completed", "degraded", "failed"} and any(
                steps.setdefault(previous, {"status": "pending", "detail": "等待开始"}).get("status")
                not in {"completed", "degraded", "failed", "skipped"}
                for previous in STAGE_ORDER[:index]
            ):
                return
            steps[stage] = {"status": status, "detail": detail, "updated_at": _iso_now()}
            if stage == "agent_collaboration" and status == "running":
                task["non_interruptible"] = True

        self._mutate(task_id, updater)

    def update_agent_step(self, task_id: str, role: str, status: str, detail: str) -> None:
        if role not in AGENT_ROLE_ORDER:
            return

        def updater(task: dict[str, Any]) -> None:
            task.setdefault("agent_steps", {})[role] = {"status": status, "detail": detail, "updated_at": _iso_now()}

        self._mutate(task_id, updater)

    def update_task(self, task_id: str, **fields: Any) -> None:
        def updater(task: dict[str, Any]) -> None:
            task.update(fields)

        self._mutate(task_id, updater)

    def cancel(self, task_id: str) -> dict[str, Any] | None:
        task = self.get(task_id)
        if task is None or task.get("status") not in ACTIVE_STATUSES:
            return None
        if task.get("non_interruptible"):
            return {**self._public_task(task), "cancel_rejected": True, "failure_code": "TASK_NON_INTERRUPTIBLE"}
        cancelled = self.client.cancel_demo_run_task(task_id=task_id)
        return self._public_task(self._row_to_task(cancelled)) if cancelled else None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


_store: DemoRunTaskStore | None = None
_store_lock = threading.Lock()


def get_store(base_dir: Path | str) -> DemoRunTaskStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = DemoRunTaskStore(base_dir)
        return _store


def reset_store() -> None:
    global _store
    with _store_lock:
        if _store is not None:
            _store.shutdown()
            _store = None
