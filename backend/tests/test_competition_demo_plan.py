from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import agents as agents_module
from backend.app.agents import ROLE_PROMPTS, run_agent_chain
from backend.app.main import app
from backend.app.public_model import PublicModelLedger, PublicModelQuotaError, QuotaConfig, build_cache_key
from backend.app.schemas import RuleResult


def test_public_model_ledger_enforces_ip_and_cache_key_scope(tmp_path: Path) -> None:
    ledger = PublicModelLedger(
        tmp_path,
        config=QuotaConfig(per_ip=1, global_window=4, max_concurrent=2, daily_runs=4),
    )
    reservation = ledger.reserve("198.51.100.7")
    with pytest.raises(PublicModelQuotaError):
        ledger.reserve("198.51.100.7")
    ledger.settle(reservation, input_tokens=12, output_tokens=8)
    key_a = build_cache_key(case_id="CASE_A", year=2026, rule_ids=["R2", "R1"], source_snapshot_id="S1", prompt_version="P1", model_id="deepseek-v4-flash", supplement_hash="A")
    key_b = build_cache_key(case_id="CASE_A", year=2026, rule_ids=["R1", "R2"], source_snapshot_id="S1", prompt_version="P1", model_id="deepseek-v4-flash", supplement_hash="B")
    assert key_a != key_b
    ledger.put_cache(key_a, {"run_id": "RUN-1"})
    assert ledger.get_cache(key_a) == {"run_id": "RUN-1"}


def test_demo_readonly_contracts_are_available() -> None:
    client = TestClient(app)
    evaluation = client.get("/api/evaluations/current")
    assert evaluation.status_code == 200
    assert evaluation.json()["evaluation_id"] == "EVAL-20260811-COMPETITION-8CASE-V1"
    samples = client.get("/api/supplement-samples")
    assert samples.status_code == 200
    assert {item["sample_id"] for item in samples.json()["samples"]} == {"aging", "receipts"}


def test_summary_case_directory_is_compact() -> None:
    client = TestClient(app)
    response = client.get("/api/cases?summary=true")
    assert response.status_code == 200
    assert len(response.content) < 100_000
    assert all(set(item) >= {"case_id", "company_name", "available_years"} for item in response.json()["cases"])


def test_prompt_v3_runs_all_three_roles_with_structured_provider_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    assert all(ROLE_PROMPTS[role].strip() for role in ("challenge", "counter", "review"))
    assert "basis_limitation" in ROLE_PROMPTS["review"]
    assert "trend_limitation" in ROLE_PROMPTS["review"]
    assert "未达到/不可评价" in ROLE_PROMPTS["review"]
    result = RuleResult(
        rule_id="R1",
        status="candidate",
        source_validation={},
        metrics={"three_year_trend_available": False},
        risk_card={
            "screening_strength": "standard",
            "basis_limitation": "应收账款仅有净额/报表列示额，未达到专业目标的账面余额口径。",
            "trend_limitation": "缺少第三年，持续期间和周转趋势不可评价。",
        },
    )

    def fake_provider(**kwargs):
        role = kwargs["payload"]["role"]
        output = {
            "schema_version": "agent_output_v2",
            "run_id": "RUN-PROMPT-V3",
            "role": role,
            "rule_id": "R1",
            "status": "candidate" if role != "review" else "retain",
            "claims": [{"text": "需要回查本次证据支持的事项", "evidence_ids": ["E1"], "support_status": "supported"}],
            "normal_explanations": [],
            "data_gaps": ["期后回款资料"],
            "requested_materials": ["期后回款资料"],
            "reason_for_status": "仅依据当前证据包形成待核查草稿",
            "draft_title": "待核查事项" if role == "review" else "",
            "draft_observation": "建议回查证据并由人工决定" if role == "review" else "",
            "ai_recommendation": "retain" if role == "review" else "not_applicable",
        }
        return output, 5, f"response-{role}", f"input-{role}", 10, 5

    monkeypatch.setattr(agents_module, "_call_model", fake_provider)
    steps = run_agent_chain(
        run_id="RUN-PROMPT-V3",
        rule_result=result,
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "登记的原文片段"}],
        enabled=True,
        api_key="test-key",
        base_url="https://example.invalid",
        model_id="deepseek-v4-flash",
    )
    assert [step.role for step in steps] == ["challenge", "counter", "review"]
    assert [step.status for step in steps] == ["completed", "completed", "completed"]
    assert all(step.prompt_version == "agent_prompt_v3" for step in steps)
    review = steps[-1].output
    assert review is not None
    assert "程序边界" in review.draft_observation
    assert "趋势不可评价" in review.draft_observation
