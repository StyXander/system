"""演示任务取消、重启中断和后台晚到结果的终态合同。"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from backend.app.demo_run_tasks import DemoRunTaskStore


def _wait_for_status(store: DemoRunTaskStore, task_id: str, status: str) -> None:
    deadline = time.time() + 5
    while time.time() < deadline:
        task = store.get(task_id)
        if task and task.get("status") == status:
            return
        time.sleep(0.01)
    raise AssertionError(f"任务未进入 {status}: {task_id}")


def test_cancelled_terminal_cannot_be_overwritten_by_late_result(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def executor(task: dict[str, object]) -> None:
        started.set()
        release.wait(timeout=5)
        # 模拟不可中断外部调用返回后的迟到写入。
        store.update_task(
            str(task["task_id"]),
            run_id="RUN-LATE",
            result={"run_id": "RUN-LATE"},
            status="completed",
        )

    store = DemoRunTaskStore(tmp_path)
    try:
        task = store.create("STD_DEV_T0", {"case_id": "STD_DEV_T0"}, executor)
        assert started.wait(timeout=5)
        cancelled = store.cancel(task["task_id"])
        assert cancelled and cancelled["status"] == "cancelled"
        release.set()
        time.sleep(0.1)
        snapshot = store.snapshot(task["task_id"])
        assert snapshot and snapshot["status"] == "cancelled"
        assert snapshot["run_id"] is None
        assert snapshot["result"] is None
    finally:
        release.set()
        store.shutdown()


def test_service_restart_marks_active_task_interrupted(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def executor(_task: dict[str, object]) -> None:
        started.set()
        release.wait(timeout=5)

    first = DemoRunTaskStore(tmp_path)
    task = first.create("STD_DEV_T0", {"case_id": "STD_DEV_T0"}, executor)
    assert started.wait(timeout=5)
    second = DemoRunTaskStore(tmp_path)
    try:
        snapshot = second.snapshot(task["task_id"])
        assert snapshot and snapshot["status"] == "interrupted"
        assert snapshot["failure_code"] == "TASK_INTERRUPTED_BY_RESTART"
        assert all(item["status"] == "skipped" for item in snapshot["steps"].values())
        assert snapshot["result"] is None
    finally:
        release.set()
        first.shutdown()
        second.shutdown()
