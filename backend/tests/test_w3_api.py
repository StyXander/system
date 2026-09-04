"""W3 回归：R1/R2确定性计算、来源闸门、三Agent失败关闭和运行日志。"""

import pytest
from fastapi.testclient import TestClient

from backend.app.agents import _agent_output_tool_for, validate_agent_output
from backend.app import cases as cases_module
from backend.app import main as main_module
from backend.app.main import app


client = TestClient(app)


def _authorize_standard_for_model_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """仅在模型状态机单测中模拟已经由真人完成的传输许可。"""
    original = cases_module._standard_case

    def authorized(workspace_root):
        case = original(workspace_root)
        case["model_transfer_allowed"] = True
        case["legal_sample_confirmation_status"] = "test_only_authorized"
        return case

    monkeypatch.setattr(cases_module, "_standard_case", authorized)


def _rule(body: dict, rule_id: str) -> dict:
    return next(result for result in body["rule_results"] if result["rule_id"] == rule_id)


def test_health_without_key_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["service_status"] == "ready"
    assert response.json()["model_status"] == "config_missing"


@pytest.mark.requires_full_corpus
def test_r1_2023_is_candidate_and_deterministic_without_model() -> None:
    response = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "rule_ids": ["R1"], "check_model": False},
    )
    body = response.json()
    result = _rule(body, "R1")
    assert response.status_code == 200
    assert body["status"] == "candidate"
    assert round(result["metrics"]["growth_gap"], 6) == round(0.268393, 6)
    assert result["agent_steps"][0]["status"] == "not_requested"
    assert len(body["sources"]) == 4


@pytest.mark.requires_full_corpus
def test_r2_blocks_cross_sign_cashflow_growth_without_forcing_candidate() -> None:
    response = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "rule_ids": ["R2"], "check_model": False},
    )
    body = response.json()
    result = _rule(body, "R2")
    source_ids = {row["evidence_id"] for row in body["sources"]}
    assert response.status_code == 200
    assert result["status"] == "DATA_NOT_COMPARABLE"  # 2023/2022 OCF 跨期变号，百分比同比不宜展示。
    assert result["metrics"]["operating_cash_flow_growth"] is None
    assert result["metrics"]["growth_gap"] is None
    assert result["metrics"]["net_profit_cashflow_gap"] is None  # 2023 净利润为负，不展示该比率。
    assert "同比不宜比较" in result["risk_card"]["title"]
    assert {"STD_CFO_2023", "STD_CFO_2022", "STD_NP_2023"}.issubset(source_ids)
    assert result["agent_steps"][0]["status"] == "not_applicable"


@pytest.mark.requires_full_corpus
def test_agent_chain_reports_missing_configuration_without_fake_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize_standard_for_model_test(monkeypatch)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    response = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "rule_ids": ["R1"], "check_model": True},
    )
    body = response.json()
    result = _rule(body, "R1")
    assert response.status_code == 200
    assert body["model_check"]["status"] == "config_missing"
    assert result["agent_steps"][0]["status"] == "config_missing"
    assert result["agent_steps"][0]["prompt_version"] == "agent_prompt_v3"
    assert result["agent_steps"][0]["output"] is None


@pytest.mark.requires_full_corpus
def test_public_demo_limits_only_anonymous_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize_standard_for_model_test(monkeypatch)
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_MODEL_RUN_LIMIT", "1")
    monkeypatch.setenv("AUDITTRACE_MODEL_RUN_GLOBAL_LIMIT", "10")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with main_module._PUBLIC_MODEL_REQUEST_LOCK:
        main_module._PUBLIC_MODEL_REQUESTS_BY_IP.clear()
        main_module._PUBLIC_MODEL_REQUESTS_GLOBAL.clear()

    first = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "rule_ids": ["R1"], "check_model": True},
    )
    second = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "rule_ids": ["R1"], "check_model": True},
    )
    deterministic = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "rule_ids": ["R1"], "check_model": False},
    )

    assert first.status_code == 200
    assert first.json()["model_check"]["status"] == "config_missing"
    assert second.status_code == 429
    assert deterministic.status_code == 200


def test_invalid_agent_evidence_id_is_blocked() -> None:
    invalid_payload = {
        "schema_version": "agent_output_v1",
        "run_id": "RUN-W3-TEST",
        "role": "challenge",
        "rule_id": "R1",
        "status": "candidate",
        "claims": [{"text": "需要进一步了解。", "evidence_ids": ["NOT_IN_BUNDLE"]}],
        "normal_explanations": [],
        "data_gaps": [],
        "requested_materials": [],
        "reason_for_status": "仅作校验测试。",
    }
    with pytest.raises(ValueError, match="evidence_id"):
        validate_agent_output(
            invalid_payload,
            run_id="RUN-W3-TEST",
            role="challenge",
            rule_id="R1",
            allowed_evidence_ids={"STD_REV_2023"},
        )


def test_strict_model_contract_binds_review_to_its_own_status_and_run() -> None:
    tool = _agent_output_tool_for("review", "R1", "RUN-W3-STRICT")
    properties = tool["function"]["parameters"]["properties"]
    assert tool["function"]["strict"] is True
    assert properties["run_id"]["enum"] == ["RUN-W3-STRICT"]
    assert properties["role"]["enum"] == ["review"]
    assert properties["rule_id"]["enum"] == ["R1"]
    assert properties["status"]["enum"] == ["retain", "downgrade", "defer"]


def test_run_log_can_be_read_and_human_review_is_persisted() -> None:
    created = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "rule_ids": ["R1", "R2"], "check_model": False},
    )
    run_id = created.json()["run_id"]
    loaded = client.get(f"/api/runs/{run_id}")
    reviewed = client.post(
        f"/api/runs/{run_id}/review",
        json={"status": "保留为待核查候选", "note": "开发样例的人工复核记录。"},
    )
    assert loaded.status_code == 200
    assert len(loaded.json()["run"]["rule_results"]) == 2
    assert reviewed.status_code == 200
    assert reviewed.json()["human_review"]["status"] == "保留为待核查候选"


def test_unknown_period_is_rejected() -> None:
    response = client.post("/api/runs", json={"case_id": "STD_DEV_T0", "current_year": 2022})
    assert response.status_code == 422
