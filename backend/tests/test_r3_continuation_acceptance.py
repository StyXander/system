"""R3：补充材料父子任务、差异和结构化导出验收。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.demo_run_tasks import DemoRunTaskStore
from backend.app.main import app


@pytest.mark.requires_full_corpus
def test_supplement_parent_child_and_docx_export_share_run_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """补充样例必须形成独立子运行，原字段和导出边界不能被静默覆盖。"""

    import backend.app.main as main_module

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "false")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "false")
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    store = DemoRunTaskStore(tmp_path / "demo-tasks")
    monkeypatch.setattr(main_module, "_get_demo_run_store", lambda: store)
    client = TestClient(app)
    try:
        parent_response = client.post(
            "/api/runs",
            json={
                "case_id": "STD_DEV_T0",
                "current_year": 2025,
                "rule_ids": ["R1"],
                "run_mode": "full_analysis",
                "force_deterministic_backup": True,
            },
        )
        assert parent_response.status_code == 200, parent_response.text[:500]
        parent = parent_response.json()
        parent_id = parent["run_id"]
        original_field_ids = {
            row.get("field_id")
            for row in parent.get("evidence_bundle", {}).get("field_evidence", [])
            if row.get("field_id")
        }

        supplement_response = client.post(
            "/api/supplements/from-sample",
            json={
                "parent_run_id": parent_id,
                "sample_id": "receipts",
                "bound_rule_ids": ["R1"],
                "as_of_date": "2026-04-30",
            },
        )
        assert supplement_response.status_code == 200, supplement_response.text[:500]
        supplement = supplement_response.json()
        supplement_id = supplement["supplement_id"]
        assert supplement["parent_run_id"] == parent_id
        assert supplement["status"] == "ready_for_rerun"

        task_response = client.post(
            f"/api/supplements/{supplement_id}/rerun-task",
            json={"run_mode": "full_analysis", "force_deterministic_backup": True},
        )
        assert task_response.status_code == 202, task_response.text[:500]
        task_id = task_response.json()["task_id"]
        assert task_response.json()["stage_schema_version"] == "demo_task_v2"
        assert task_response.json()["parent_run_id"] == parent_id
        assert task_response.json()["supplement_id"] == supplement_id

        deadline = time.time() + 30
        task = None
        while time.time() < deadline:
            task_response = client.get(f"/api/demo/runs/{task_id}")
            assert task_response.status_code == 200
            task = task_response.json()
            if task["status"] not in {"queued", "running"}:
                break
            time.sleep(0.05)
        assert task is not None
        assert task["status"] in {"completed", "degraded"}, task
        assert list(task["steps"]) == [
            "evidence_load",
            "rule_calculation",
            "knowledge_retrieval",
            "agent_collaboration",
            "evidence_validation",
            "structured_output",
        ]
        child = task["result"]
        assert child and child["run_id"] == task["run_id"]
        assert child["run_id"] != parent_id
        assert child["parent_run_id"] == parent_id
        assert child["context"]["parent_run_id"] == parent_id
        assert child["context"]["supplement_id"] == supplement_id
        delta = child["context"].get("supplement_delta") or {}
        assert delta["parent_run_id"] == parent_id
        assert delta["supplement_evidence_count"] >= 1
        assert child["context"]["source_snapshot_id"].endswith(f"+{supplement_id}")
        child_field_ids = {
            row.get("field_id")
            for row in child.get("evidence_bundle", {}).get("field_evidence", [])
            if row.get("field_id")
        }
        assert original_field_ids <= child_field_ids

        result_response = client.get(f"/api/demo/runs/{task_id}/result")
        assert result_response.status_code == 200
        assert result_response.json()["run_id"] == child["run_id"]
        stored_response = client.get(f"/api/runs/{child['run_id']}")
        assert stored_response.status_code == 200
        assert stored_response.json()["run"]["run_id"] == child["run_id"]

        docx_response = client.get(f"/api/runs/{child['run_id']}/report.docx")
        assert docx_response.status_code == 200
        assert docx_response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert docx_response.content[:2] == b"PK"

        # 与前端 JSON/CSV 导出使用同一组身份字段；失败/取消/中断任务不会进入此断言。
        export_identity = {
            "run_id": child["run_id"],
            "parent_run_id": child["context"]["parent_run_id"],
            "supplement_id": child["context"]["supplement_id"],
            "supplement_delta": delta,
            "knowledge_snapshot_id": child["context"].get("knowledge_snapshot_id"),
            "ai_generated_content_notice": child.get("context", {}).get("ai_generated_content_notice"),
        }
        assert export_identity["run_id"] == stored_response.json()["run"]["run_id"]
        assert export_identity["parent_run_id"] == parent_id
        assert export_identity["supplement_id"] == supplement_id
    finally:
        store.shutdown()
