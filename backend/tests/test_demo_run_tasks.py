"""固定案例分阶段演示运行任务（G2）单元测试。

覆盖：任务 Schema、六阶段单调推进、角色逐步状态、活动任务去重、
取消边界、worker 失败关闭、快照不泄露请求体、终态 run_id 一致性。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from backend.app.demo_run_tasks import (
    AGENT_ROLE_ORDER,
    STAGE_ORDER,
    DemoRunTaskStore,
    reset_store,
)


@pytest.fixture
def store(tmp_path: Path):
    demo_store = DemoRunTaskStore(tmp_path)
    yield demo_store
    demo_store.shutdown()


def _held_task(store: DemoRunTaskStore) -> tuple[str, threading.Event]:
    """创建仍在运行中的任务：worker 停在 executor 内，进度写入不会被终态闸门丢弃。

    存储层故意拒绝写进已结束的任务，所以从主线程补写进度的测试必须先卡住
    worker，否则结果取决于线程调度，变成偶发失败。
    """

    hold = threading.Event()
    entered = threading.Event()

    def executor(_task: dict) -> None:
        entered.set()
        # 超时必须远大于调度抖动：worker 一旦自己醒来就会把任务写成终态，
        # 存储层随即丢弃测试补写的进度，竞争又回来了。调用方都在 finally 里释放。
        hold.wait(timeout=30)

    task = store.create("STD_DEV_T0", {"current_year": 2025}, executor)
    assert entered.wait(timeout=30)
    return str(task["task_id"]), hold


def test_new_task_schema_has_six_stages_and_three_roles(store: DemoRunTaskStore) -> None:
    seen: dict[str, str] = {}

    def executor(task: dict):
        seen["task_id"] = task["task_id"]

    task = store.create("STD_DEV_T0", {"current_year": 2025, "rule_ids": ["R1"]}, executor)
    assert task["task_id"].startswith("DEMO-RUN-")
    assert list(task["steps"].keys()) == list(STAGE_ORDER)
    assert list(task["agent_steps"].keys()) == list(AGENT_ROLE_ORDER)
    assert task["status"] in {"queued", "running"}
    for stage in STAGE_ORDER:
        assert task["steps"][stage]["status"] == "pending"
    assert task["run_id"] is None
    assert task["failure_code"] is None


def test_stage_updates_are_monotonic_and_cannot_regress(store: DemoRunTaskStore) -> None:
    task_id, hold = _held_task(store)
    try:
        store.update_stage(task_id, "evidence_load", "running", "读取中")
        store.update_stage(task_id, "evidence_load", "completed", "读取完成")
        # 完成后的阶段不能退回运行中或待处理
        store.update_stage(task_id, "evidence_load", "running", "不应回退")
        store.update_stage(task_id, "evidence_load", "pending", "不应回退")
        assert store.get(task_id)["steps"]["evidence_load"]["status"] == "completed"
        assert "不应回退" not in store.get(task_id)["steps"]["evidence_load"]["detail"]
    finally:
        hold.set()


def test_stage_updates_reject_out_of_order_progress(store: DemoRunTaskStore) -> None:
    task_id, hold = _held_task(store)
    try:
        store.update_stage(task_id, "knowledge_retrieval", "running", "不应越过规则计算")
        assert store.get(task_id)["steps"]["knowledge_retrieval"]["status"] == "pending"
        store.update_stage(task_id, "evidence_load", "completed", "载入完成")
        store.update_stage(task_id, "rule_calculation", "completed", "计算完成")
        store.update_stage(task_id, "knowledge_retrieval", "completed", "检索完成")
        assert store.get(task_id)["steps"]["knowledge_retrieval"]["status"] == "completed"
    finally:
        hold.set()


def test_agent_steps_progress_per_role(store: DemoRunTaskStore) -> None:
    task_id, hold = _held_task(store)
    try:
        store.update_agent_step(task_id, "challenge", "completed", "质疑完成 1/3")
        store.update_agent_step(task_id, "counter", "completed", "反证完成 2/3")
        store.update_agent_step(task_id, "review", "skipped", "前置失败")
        view = store.snapshot(task_id)
        assert view["agent_steps"]["challenge"]["status"] == "completed"
        assert view["agent_steps"]["review"]["status"] == "skipped"
    finally:
        hold.set()


def test_same_active_case_reuses_task_and_does_not_create_second_run(store: DemoRunTaskStore) -> None:
    import threading

    release = threading.Event()
    calls: list[str] = []

    def executor(task: dict):
        calls.append(task["task_id"])
        release.wait(timeout=5)

    first = store.create("STD_DEV_T0", {"current_year": 2025}, executor)
    # 同一案例仍在运行时重复点击应复用同一任务
    second = store.create("STD_DEV_T0", {"current_year": 2025}, executor)
    assert second["task_id"] == first["task_id"]
    assert len(calls) == 1
    release.set()
    assert calls == [first["task_id"]]


def test_cancel_active_task_and_reject_terminal(store: DemoRunTaskStore) -> None:
    release = threading.Event()

    def executor(task: dict):
        release.wait(timeout=5)

    task = store.create("JACK_603337_T0_20250415", {"current_year": 2024}, executor)
    task_id = task["task_id"]
    # 等到后端真的把任务推进到 running 再取消；固定 sleep 会在调度慢时误判。
    deadline = time.time() + 5
    while time.time() < deadline and store.get(task_id)["status"] != "running":
        time.sleep(0.02)
    assert store.get(task_id)["status"] == "running"
    cancelled = store.cancel(task_id)
    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
    assert cancelled["failure_code"] == "TASK_CANCELLED"
    assert store.cancel(task_id) is None
    release.set()


def test_worker_exception_closes_task_and_marks_stages(store: DemoRunTaskStore) -> None:
    def failing(_task: dict):
        raise RuntimeError("来源不可达")

    task = store.create("STD_DEV_T0", {"current_year": 2025}, failing)
    task_id = task["task_id"]
    deadline = time.time() + 5
    while time.time() < deadline:
        view = store.snapshot(task_id)
        if view["status"] == "failed":
            break
        time.sleep(0.05)
    view = store.snapshot(task_id)
    assert view["status"] == "failed"
    assert view["failure_code"] == "TASK_EXECUTION_ERROR"
    assert "RuntimeError" in (view["error"] or "")


def test_failed_terminal_snapshot_never_exposes_result(store: DemoRunTaskStore) -> None:
    task_id, hold = _held_task(store)
    try:
        store.update_task(task_id, status="failed", result={"run_id": "RUN-FAILED"}, failure_code="RAG_FAILED")
        view = store.snapshot(task_id)
    finally:
        hold.set()
    assert view["status"] == "failed"
    assert view["result"] is None


def test_snapshot_excludes_run_body(store: DemoRunTaskStore) -> None:
    task = store.create("STD_DEV_T0", {"current_year": 2025, "planned_materiality": 100}, lambda _t: None)
    view = store.snapshot(task["task_id"])
    assert "run_body" not in view


def test_store_restores_task_from_json_after_restart(tmp_path: Path) -> None:
    first = DemoRunTaskStore(tmp_path)
    task_id, hold = _held_task(first)
    try:
        first.update_stage(task_id, "evidence_load", "completed", "载入完成")
        first.update_stage(task_id, "rule_calculation", "completed", "计算完成")
    finally:
        hold.set()
    first.shutdown()

    # 模拟服务重启：新存储实例从 JSON 台账恢复同一任务
    second = DemoRunTaskStore(tmp_path)
    recovered = second.get(task_id)
    second.shutdown()
    assert recovered is not None
    assert recovered["task_id"] == task_id
    assert recovered["steps"]["rule_calculation"]["status"] == "completed"
    assert recovered["steps"]["rule_calculation"]["detail"] == "计算完成"


def test_update_stage_rejects_unknown_status(store: DemoRunTaskStore) -> None:
    task = store.create("STD_DEV_T0", {"current_year": 2025}, lambda _t: None)
    with pytest.raises(ValueError):
        store.update_stage(task["task_id"], "evidence_load", "mystery", "x")
