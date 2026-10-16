"""合成报告隔离验证使用者记录、所有权和修订冲突，不调用外部模型。"""
import time
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import connectivity_api
from app.connectivity_engine import calculate
from app.connectivity_schemas import ConnectivityRun, ReportDocument
from test_connectivity_engine import relationship


def completed(client, task_id):
    for _ in range(100):
        response = client.get(f"/api/connectivity/runs/{task_id}")
        assert response.status_code == 200
        task = response.json()
        if task["status"] not in {"queued", "running"}:
            assert task["status"] == "completed", task
            return task
        time.sleep(.02)
    pytest.fail("本地修订未在规定时间内完成")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    rows, check = relationship("EQ-001", ["1", "10000"], ["left", "right"], ["亿元", "万元"])
    document = ReportDocument(document_id="SYNTHETIC", case_id="SYN-PAIR", company_id="SYN", company="合成企业",
        report_type="AR", period="2025", source_url="https://example.invalid/synthetic")
    run = ConnectivityRun(run_id="SYN-RUN", company="合成企业", period="2025", documents=[document],
        occurrences=rows, checks=[calculate(check, rows)], dataset_role="synthetic")
    monkeypatch.setattr(connectivity_api, "load_registry", lambda root: [document])
    monkeypatch.setattr(connectivity_api, "demo_task_supabase_enabled", lambda: False)
    monkeypatch.setattr(connectivity_api, "run_pipeline", lambda *args, **kwargs: run.model_copy(deep=True))
    app = FastAPI()
    app.include_router(connectivity_api.build_router(tmp_path, lambda request: None, lambda: None))
    with TestClient(app) as client:
        assert client.get("/api/connectivity/bootstrap").status_code == 200
        response = client.post("/api/connectivity/runs", json={"pair_id": "SYN-PAIR", "mode": "calculation_only"})
        yield client, app, completed(client, response.json()["task_id"])


def test_reading_and_observation_keep_facts_and_parent(workspace):
    client, app, original = workspace
    endpoint = f'/api/connectivity/runs/{original["task_id"]}/reviews'
    body = {"expected_revision": 1, "action": "reading_confirmation", "check_ids": ["SYN-CHECK"],
        "reason": "已阅读原文与未知条件", "action_id": "review-action-001"}
    with TestClient(app) as stranger:
        stranger.get("/api/connectivity/bootstrap")
        assert stranger.post(endpoint, json=body).status_code == 403
    response = client.post(endpoint, json=body)
    assert response.status_code == 200
    child = completed(client, response.json()["task_id"])
    assert child["result"]["parent_run_id"] == "SYN-RUN"
    assert child["result"]["result_revision"] == 2
    before = deepcopy(original["result"]["checks"][0])
    after = deepcopy(child["result"]["checks"][0])
    assert after.pop("review_status") == "read_confirmed"
    before.pop("review_status")
    assert before == after
    assert client.post(endpoint, json=body).json()["task_id"] == child["task_id"]
    assert client.post(endpoint, json={**body, "reason": "换了不同内容"}).status_code == 409
    assert client.post(endpoint, json={**body, "action_id": "review-action-002"}).status_code == 409
    note_body = {"expected_revision": 2, "action": "personal_observation", "check_ids": ["SYN-CHECK"],
        "reason": "保留进一步了解事项", "observation": "个人对统计范围的疑问", "action_id": "observation-action-003"}
    response = client.post(f'/api/connectivity/runs/{child["task_id"]}/reviews', json=note_body)
    assert response.status_code == 200
    noted = completed(client, response.json()["task_id"])
    assert noted["result"]["checks"] == child["result"]["checks"]
    assert len(noted["result"]["professional_notes"]) == 1
    assert noted["result"]["professional_notes"][0]["observation"] == note_body["observation"]
    original_again = completed(client, original["task_id"])
    assert original_again["result"] == original["result"]
    for format_name in ["json", "csv", "docx"]:
        assert client.get(f'/api/connectivity/runs/{noted["task_id"]}/export/{format_name}').status_code == 200


def test_forged_source_correction_rejected_and_real_correction_recalculated(workspace):
    client, _, original = workspace
    endpoint = f'/api/connectivity/runs/{original["task_id"]}/corrections'
    check = deepcopy(original["result"]["checks"][0])
    body = {"expected_revision": 1, "check": check, "reason": "补充具体关系说明", "action_id": "correction-action-001"}
    check["relationship_evidence"][0]["quote"] = "本原文并不存在的组成解释"
    assert client.post(endpoint, json=body).status_code == 422
    body["check"] = deepcopy(original["result"]["checks"][0])
    body["check"]["title"] = "更正后关系名称"
    body["check"]["calculation"] = {"residual": "999"}
    body["check"]["calculation_status"] = "made_up_success"
    response = client.post(endpoint, json=body)
    assert response.status_code == 200
    child = completed(client, response.json()["task_id"])
    assert child["result"]["checks"][0]["calculation"]["residual"] == "0"
    assert child["result"]["checks"][0]["calculation_status"] == "consistent"
    assert child["result"]["checks"][0]["review_status"] == "demo_modified"
    assert child["result"]["reviews"][0]["before"]["title"] != "更正后关系名称"
    assert client.post(endpoint, json=body).json()["task_id"] == child["task_id"]
