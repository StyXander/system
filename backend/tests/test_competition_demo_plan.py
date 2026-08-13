from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from backend.app import agents as agents_module
from backend.app.agents import ProviderCallError, ROLE_PROMPTS, _strict_tool_base_url, run_agent_chain
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
            "normal_explanations": (
                [{"text": "季节性可能解释当前变化", "evidence_ids": ["E1"], "support_status": "supported"}]
                if role == "counter"
                else []
            ),
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
    counter = steps[1].output
    assert counter is not None
    assert counter.normal_explanations[0].support_status == "unverified_hypothesis"
    assert "待验证假设" in counter.normal_explanations[0].text
    review = steps[-1].output
    assert review is not None
    assert "程序边界" in review.draft_observation
    assert "趋势不可评价" in review.draft_observation


def test_non_candidate_route_still_runs_three_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    result = RuleResult(
        rule_id="R1",
        status="RULE_NOT_TRIGGERED",
        source_validation={},
        metrics={"three_year_trend_available": True},
        risk_card={"observation": "程序结果未触发，仍需复核潜在漏判。"},
    )
    calls: list[str] = []

    def fake_provider(**kwargs):
        role = kwargs["payload"]["role"]
        calls.append(role)
        review = role == "review"
        status = "retain" if review else "defer"
        return (
            {
                "schema_version": "agent_output_v2",
                "run_id": "RUN-NEGATIVE",
                "role": role,
                "rule_id": "R1",
                "analysis_conclusion": "no_trigger_confirmed",
                "status": status,
                "claims": [{"text": "当前证据支持程序未触发复核", "evidence_ids": ["E1"], "support_status": "supported"}],
                "normal_explanations": [],
                "data_gaps": [],
                "requested_materials": [],
                "reason_for_status": "仅依据本次证据包",
                "draft_title": "未触发结果复核" if review else "",
                "draft_observation": "未发现足以推翻程序结果的证据" if review else "",
                "ai_recommendation": "retain" if review else "not_applicable",
            },
            1,
            f"response-{role}",
            f"input-{role}",
            10,
            5,
        )

    monkeypatch.setattr(agents_module, "_call_model", fake_provider)
    steps = run_agent_chain(
        run_id="RUN-NEGATIVE",
        rule_result=result,
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "程序未触发"}],
        enabled=True,
        api_key="test-key",
        base_url="https://example.invalid",
        model_id="deepseek-v4-flash",
        analysis_route="negative_confirmation",
    )
    assert calls == ["challenge", "counter", "review"]
    assert [step.status for step in steps] == ["completed", "completed", "completed"]
    assert steps[-1].output is not None
    assert steps[-1].output.analysis_conclusion == "no_trigger_confirmed"


def test_empty_evidence_route_still_calls_three_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    result = RuleResult(
        rule_id="R1",
        status="DATA_GAP",
        source_validation={"issues": ["缺少可回查来源"]},
        metrics={},
        risk_card={"data_gaps": ["缺少连续年度字段"]},
    )
    calls: list[str] = []

    def fake_provider(**kwargs):
        role = kwargs["payload"]["role"]
        calls.append(role)
        review = role == "review"
        return (
            {
                "schema_version": "agent_output_v2",
                "run_id": "RUN-EMPTY-EVIDENCE",
                "role": role,
                "rule_id": "R1",
                "analysis_conclusion": "data_gap",
                "status": "defer",
                "claims": [],
                "normal_explanations": [],
                "data_gaps": ["缺少可回查证据"],
                "requested_materials": ["补充官方年报字段或原文定位"],
                "reason_for_status": "证据包为空，只能登记数据缺口",
                "draft_title": "数据缺口复核" if review else "",
                "draft_observation": "当前没有可引用证据，需补充资料后复核" if review else "",
                "ai_recommendation": "defer" if review else "not_applicable",
            },
            1,
            f"response-{role}",
            f"input-{role}",
            10,
            5,
        )

    monkeypatch.setattr(agents_module, "_call_model", fake_provider)
    steps = run_agent_chain(
        run_id="RUN-EMPTY-EVIDENCE",
        rule_result=result,
        evidence_bundle={"field_evidence": [], "rag_evidence": [], "supplement_evidence": []},
        enabled=True,
        api_key="test-key",
        base_url="https://example.invalid",
        model_id="deepseek-v4-flash",
        analysis_route="evidence_gap_review",
    )
    assert calls == ["challenge", "counter", "review"]
    assert [step.status for step in steps] == ["completed", "completed", "completed"]
    assert steps[-1].output is not None
    assert steps[-1].output.claims == []
    assert steps[-1].output.analysis_conclusion == "data_gap"


def test_all_seed_cases_enter_three_role_external_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A full-analysis request must reach the provider for every tracked demo case."""

    import backend.app.main as main_module

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setattr(main_module, "_enforce_public_model_quota", lambda _request: None)
    monkeypatch.setattr(main_module, "_public_model_ledger", lambda: PublicModelLedger(tmp_path))

    route_conclusions = {
        "risk_candidate": "risk_candidate",
        "negative_confirmation": "no_trigger_confirmed",
        "industry_review": "industry_boundary",
        "evidence_gap_review": "data_gap",
    }

    def fake_provider(**kwargs):
        payload = kwargs["payload"]
        role = payload["role"]
        route = payload["analysis_route"]
        evidence_ids = payload["output_contract"]["allowed_evidence_ids"]
        assert evidence_ids
        is_review = role == "review"
        if route == "risk_candidate":
            status = "candidate" if role == "challenge" else "defer" if role == "counter" else "retain"
        elif route == "negative_confirmation":
            status = "retain" if is_review else "defer"
        else:
            status = "defer"
        return (
            {
                "schema_version": "agent_output_v2",
                "run_id": payload["run_id"],
                "role": role,
                "rule_id": payload["rule_result"]["rule_id"],
                "analysis_conclusion": route_conclusions[route],
                "status": status,
                "claims": [{"text": "Evidence-bound model review.", "evidence_ids": [evidence_ids[0]], "support_status": "supported"}],
                "normal_explanations": [],
                "data_gaps": [],
                "requested_materials": [],
                "reason_for_status": "The result is limited to the supplied evidence packet.",
                "draft_title": "External model review" if is_review else "",
                "draft_observation": "External model review is retained for human confirmation." if is_review else "",
                "ai_recommendation": status if is_review else "not_applicable",
            },
            1,
            f"response-{payload['run_id']}-{role}",
            f"input-{payload['run_id']}-{role}",
            10,
            5,
        )

    monkeypatch.setattr(agents_module, "_call_model", fake_provider)
    client = TestClient(app)
    listing = client.get("/api/cases?summary=true")
    assert listing.status_code == 200
    cases = listing.json()["cases"]
    assert len(cases) == 51
    for item in cases:
        detail = client.get(f"/api/cases/{item['case_id']}")
        assert detail.status_code == 200, item["case_id"]
        detail_body = detail.json()
        years = [int(year) for year in detail_body.get("available_years") or [] if str(year).isdigit()]
        year = max(years or [2024])
        response = client.post(
            "/api/runs",
            json={"case_id": item["case_id"], "current_year": year, "rule_ids": ["R1", "R2"], "run_mode": "full_analysis"},
        )
        assert response.status_code == 200, (item["case_id"], response.text[:500])
        body = response.json()
        assert body["model_check"]["status"] == "model_success", item["case_id"]
        assert body["provider_call_count"] == 3, item["case_id"]
        assert {step["role"] for step in body["agent_steps"] if step["status"] == "completed"} == {"challenge", "counter", "review"}


def test_provider_balance_error_is_not_reported_as_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def insufficient_balance(**_kwargs):
        raise HTTPError("https://example.invalid", 402, "", {}, BytesIO(b"{}"))

    monkeypatch.setattr(agents_module, "_call_model", insufficient_balance)
    with pytest.raises(ProviderCallError) as error:
        agents_module._call_model_with_transient_retry(
            api_key="test-key",
            base_url="https://example.invalid",
            model_id="deepseek-v4-flash",
            role="challenge",
            payload={"run_id": "RUN-BALANCE", "rule_result": {"rule_id": "R1"}},
            analysis_route="risk_candidate",
        )
    assert error.value.failure_code == "MODEL_PROVIDER_BALANCE_EXHAUSTED"


def test_opencode_region_gate_has_actionable_failure_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def region_gate(**_kwargs):
        raise HTTPError(
            "https://opencode.ai/zen/go/v1/chat/completions",
            403,
            "",
            {},
            BytesIO(b'{"type":"error","error":{"type":"RegionError","message":"requires explicit opt in: https://opencode.ai/workspace/wrk_demo/go"}}'),
        )

    monkeypatch.setattr(agents_module, "_call_model", region_gate)
    with pytest.raises(ProviderCallError) as caught:
        agents_module._call_model_with_transient_retry(
            api_key="test-key",
            base_url="https://opencode.ai/zen/go/v1",
            model_id="deepseek-v4-flash",
            role="challenge",
            payload={"run_id": "RUN-REGION", "rule_result": {"rule_id": "R1"}},
            analysis_route="risk_candidate",
        )
    assert caught.value.failure_code == "MODEL_PROVIDER_REGION_OPT_IN_REQUIRED"
    assert "wrk_demo" in caught.value.detail


def test_provider_failure_records_remaining_roles_as_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    def insufficient_balance(**_kwargs):
        raise HTTPError("https://example.invalid", 402, "", {}, BytesIO(b"{}"))

    monkeypatch.setattr(agents_module, "_call_model", insufficient_balance)
    steps = run_agent_chain(
        run_id="RUN-BALANCE-CHAIN",
        rule_result=RuleResult(rule_id="R1", status="candidate", source_validation={}, metrics={}, risk_card={}),
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "最小证据片段"}],
        enabled=True,
        api_key="test-key",
        base_url="https://example.invalid",
        model_id="deepseek-v4-flash",
    )
    assert [step.role for step in steps] == ["challenge", "counter", "review"]
    assert steps[0].status == "provider_quota_exhausted"
    assert steps[0].failure_code == "MODEL_PROVIDER_BALANCE_EXHAUSTED"
    assert [step.status for step in steps[1:]] == ["skipped", "skipped"]


def test_opencode_go_base_url_does_not_receive_native_deepseek_beta_suffix() -> None:
    assert _strict_tool_base_url("https://opencode.ai/zen/go/v1") == "https://opencode.ai/zen/go/v1"
    assert _strict_tool_base_url("https://api.deepseek.com") == "https://api.deepseek.com/beta"
