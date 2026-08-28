"""竞赛演示的异步运行任务：真实六阶段、重启关闭与取消一致性。

任务台账只记录公开进度和已脱敏的失败码。它不保存模型原文、密钥或证据正文；
前端只轮询台账，绝不自己推进任何阶段。
"""
from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
)
TASK_ID_PREFIX = "DEMO-RUN"
ACTIVE_STATUSES = {"queued", "running"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
                self._tasks[str(task["task_id"])] = task

    def _new_task(self, case_id: str, run_body: dict[str, Any]) -> dict[str, Any]:
        task_id = f"{TASK_ID_PREFIX}-{uuid.uuid4().hex[:12].upper()}"
        now = _iso_now()
        return {
            "task_id": task_id,
            "stage_schema_version": STAGE_SCHEMA_VERSION,
            "case_id": case_id,
            "run_body": run_body,
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
        }

    def create(self, case_id: str, run_body: dict[str, Any], executor: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
        """创建任务；同案例活动任务必须复用，不能因重复点击产生第二次调用。"""
        with self._lock:
            for task in self._tasks.values():
                if task.get("case_id") == case_id and task.get("status") in ACTIVE_STATUSES:
                    return task
            task = self._new_task(case_id, run_body)
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
            if task is None or task.get("status") in {"cancelled", "interrupted"}:
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
            if task is None or task.get("status") in {"cancelled", "interrupted"}:
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
            if task.get("status") in {"cancelled", "interrupted"}:
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
                if task is None or task.get("status") in {"cancelled", "interrupted"}:
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
        if view.get("status") in {"failed", "cancelled", "interrupted"}:
            # 失败或不可读终态只展示阶段和失败码；结果正文不能被下载接口或
            # 任务轮询误当作可导出成果。
            view["result"] = None
        return view

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
