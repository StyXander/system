from __future__ import annotations

from io import BytesIO
from pathlib import Path
import json
import time
import uuid
from urllib.error import HTTPError
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app import agents as agents_module
from backend.app.agents import (
    ProviderCallError,
    ROLE_PROMPTS,
    _strict_tool_base_url,
    compact_evidence_bundle,
    minimize_model_context,
    run_agent_chain,
)
from backend.app.cases import annotate_financial_field_rows_quality, financial_field_candidate_quality_issues
from backend.app.field_extraction import _line_candidates
from backend.app.delivery import cache_run, replay_cache
from backend.app.main import (
    _cached_run_for_new_request,
    _client_identity,
    _configured_cors_origins,
    _dedupe_gap_messages,
    _demo_external_model_enabled,
    _enrich_model_check,
    _model_readiness,
    _r2_result,
    _replay_remote_cache_payload,
    _validate_trusted_proxy_configuration,
    app,
)
from backend.app.public_model import PublicModelLedger, PublicModelQuotaError, QuotaConfig, build_cache_key
from backend.app.schemas import (
    AgentOutput,
    AgentStep,
    CNInfoFieldConfirmation,
    HumanReviewRequest,
    ModelCheck,
    RuleResult,
    RunResponse,
    StoredRunResponse,
    SupplementRerunRequest,
)


def test_demo_external_model_is_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """竞赛本机默认进入真实模型链，用户仍可明确关闭以演示备用路径。"""
    monkeypatch.delenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", raising=False)
    assert _demo_external_model_enabled() is True
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "false")
    assert _demo_external_model_enabled() is False


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("模型输出的run_id、role或rule_id与本次运行不一致", "MODEL_RUN_BINDING_ERROR"),
        ("候选风险路线的质疑角色只能返回candidate", "MODEL_ROLE_STATUS_ERROR"),
        ("有证据或非缺口路线必须至少保留一条模型主张", "MODEL_CLAIMS_REQUIRED"),
        ("未获支持的解释必须明确标为待验证假设", "MODEL_HYPOTHESIS_LABEL_MISSING"),
    ],
)
def test_semantic_failures_have_actionable_stable_codes(message: str, expected: str) -> None:
    assert agents_module._semantic_failure_code(message) == expected
    payload = agents_module._semantic_correction_payload({"output_contract": {}}, expected)
    correction = payload["semantic_correction"]
    assert correction["previous_failure_code"] == expected
    assert "修正要求" in correction["instruction"]


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


def test_cache_key_covers_actual_model_input_and_expired_reservations(tmp_path: Path) -> None:
    key_a = build_cache_key(
        case_id="CASE_A",
        year=2026,
        rule_ids=["R1"],
        source_snapshot_id="S1",
        prompt_version="P1",
        model_id="M1",
        supplement_hash=None,
        input_fingerprint="threshold-and-evidence-a",
    )
    key_b = build_cache_key(
        case_id="CASE_A",
        year=2026,
        rule_ids=["R1"],
        source_snapshot_id="S1",
        prompt_version="P1",
        model_id="M1",
        supplement_hash=None,
        input_fingerprint="threshold-and-evidence-b",
    )
    assert key_a != key_b

    ledger = PublicModelLedger(
        tmp_path,
        config=QuotaConfig(per_ip=1, global_window=1, max_concurrent=1, reservation_ttl_seconds=1),
    )
    reservation = ledger.reserve("198.51.100.9")
    with ledger._connect() as connection:
        connection.execute(
            "update model_usage set reserved_at=? where reservation_id=?",
            (time.time() - 2, reservation),
        )
    assert ledger.reserve("198.51.100.9")


def test_cached_model_result_uses_current_request_evidence_metadata() -> None:
    output = AgentOutput(
        schema_version="agent_output_v2",
        run_id="RUN-OLD",
        role="review",
        rule_id="R1",
        analysis_conclusion="risk_candidate",
        status="retain",
        reason_for_status="证据约束草稿待人工复核。",
    )
    result = RuleResult(
        rule_id="R1",
        status="candidate",
        source_validation={"status": "passed", "issues": []},
        metrics={},
        agent_steps=[AgentStep(role="review", status="completed", detail="完成", output=output)],
        ai_draft=output.model_dump(mode="json"),
    )
    cached = RunResponse(
        run_id="RUN-OLD",
        status="candidate",
        context={"case_id": "CASE-A", "old_marker": True},
        source_validation={"status": "passed", "issues": []},
        sources=[{"evidence_id": "E1", "document_id": "DOC-OLD"}],
        rule_results=[result],
        model_check=ModelCheck(status="model_success", detail="完成"),
        evidence_bundle={"case_id": "CASE-A", "field_evidence": [{"document_id": "DOC-OLD"}]},
        retrievals=[{"retrieval_id": "RET-OLD"}],
        final_ai_draft={"items": [output.model_dump(mode="json")]},
        input_tokens=120,
        output_tokens=30,
        duration_ms=900,
        provider_call_count=3,
    )
    rebound = _cached_run_for_new_request(
        cached,
        run_id="RUN-NEW",
        context={"case_id": "CASE-A", "current_marker": True},
        sources=[{"evidence_id": "E1", "document_id": "DOC-NEW"}],
        source_validation={"status": "passed", "issues": ["CURRENT"]},
        evidence_bundle={"case_id": "CASE-A", "field_evidence": [{"document_id": "DOC-NEW"}]},
        retrievals=[{"retrieval_id": "RET-NEW"}],
        cache_key_hash="CACHE-1",
    )
    assert rebound.run_id == "RUN-NEW"
    assert rebound.context["current_marker"] is True
    assert rebound.context["cache_source_run_id"] == "RUN-OLD"
    assert rebound.context["cache_source_model_usage"]["provider_call_count"] == 3
    assert rebound.context["external_model_call_performed"] is False
    assert rebound.sources[0]["document_id"] == "DOC-NEW"
    assert rebound.evidence_bundle["field_evidence"][0]["document_id"] == "DOC-NEW"
    assert rebound.retrievals[0]["retrieval_id"] == "RET-NEW"
    assert rebound.rule_results[0].agent_steps[0].output.run_id == "RUN-NEW"
    assert rebound.rule_results[0].ai_draft["run_id"] == "RUN-NEW"
    assert rebound.input_tokens == 0
    assert rebound.output_tokens == 0
    assert rebound.duration_ms == 0
    assert rebound.provider_call_count == 0
    assert rebound.model_check.provider_call_count == 0
    assert rebound.rule_results[0].agent_steps[0].provider_call_performed is False


def test_cache_replay_reports_zero_fresh_model_usage(tmp_path: Path) -> None:
    """已批准的原运行可保留轨迹，但回放运行本身必须明确为零调用。"""

    source = RunResponse(
        run_id="RUN-CACHE-SOURCE",
        status="candidate",
        context={"case_id": "STD_DEV_T0", "execution_mode": "external_live"},
        source_validation={"status": "passed", "issues": []},
        sources=[],
        rule_results=[],
        model_check=ModelCheck(
            status="model_success",
            model_id="model-a",
            detail="completed",
            execution_mode="external_live",
            input_tokens=120,
            output_tokens=30,
            duration_ms=900,
            provider_call_count=3,
        ),
        execution_mode="external_live",
        input_tokens=120,
        output_tokens=30,
        duration_ms=900,
        provider_call_count=3,
    )
    stored = StoredRunResponse(
        run=source,
        human_review=HumanReviewRequest(
            status="保留为待核查候选",
            reviewer="专业复核人",
            export_approved=True,
            reviewer_type="human",
        ),
    )
    metadata = cache_run(tmp_path, stored)
    replayed = replay_cache(tmp_path, metadata["cache_id"])
    assert replayed is not None
    assert replayed.execution_mode == "cache_replay"
    assert replayed.cache_hit is True
    assert replayed.provider_call_count == 0
    assert replayed.model_check.provider_call_count == 0
    assert replayed.context["external_model_call_performed"] is False
    assert replayed.context["cache_source_model_usage"]["provider_call_count"] == 3

    remote_payload = {
        **metadata,
        "stored": stored.model_dump(mode="json"),
    }
    remote_replay = _replay_remote_cache_payload(remote_payload, metadata["cache_id"])
    assert remote_replay.execution_mode == "cache_replay"
    assert remote_replay.provider_call_count == 0
    assert remote_replay.context["external_model_call_performed"] is False
    assert remote_replay.context["cache_source_model_usage"]["input_tokens"] == 120


def test_auto_candidate_quality_gate_and_minimal_model_payload() -> None:
    suspicious = {
        "field_kind": "accounts_receivable",
        "value": 4.0,
        "unit": "元",
        "source_unit": "元",
        "extraction_method": "pdf_text_heuristic_candidate",
        "source_review_status": "auto_extracted_pending_human_page_confirmation",
        "raw_excerpt": "应收账款 | 4 | 8,110,758,258.05 | 7,293,628,386.69",
    }
    assert financial_field_candidate_quality_issues(suspicious)
    assert not financial_field_candidate_quality_issues({**suspicious, "source_review_status": "human_corrected"})
    cross_year = annotate_financial_field_rows_quality(
        [
            {
                **suspicious,
                "value": 594_000.0,
                "year": 2024,
                "source_unit": "千元",
                "unit": "元",
            },
            {
                **suspicious,
                "value": 415_558_761_000.0,
                "year": 2025,
                "source_unit": "千元",
                "unit": "元",
            },
        ]
    )
    assert all(any("连续年度金额相差" in issue for issue in row["candidate_quality_issues"]) for row in cross_year)
    human_rows = annotate_financial_field_rows_quality(
        [{**row, "source_review_status": "human_confirmed"} for row in cross_year]
    )
    assert all(not row["candidate_quality_issues"] for row in human_rows)
    structured_rows = annotate_financial_field_rows_quality(
        [
            {
                **suspicious,
                "value": 1_000_000.0,
                "year": 2023,
                "extraction_method": "registered_structured_field",
                "source_review_status": "technical_crosscheck_pending_human_confirmation",
            },
            {
                **suspicious,
                "value": 50_000_000.0,
                "year": 2024,
                "extraction_method": "registered_structured_field",
                "source_review_status": "technical_crosscheck_pending_human_confirmation",
            },
        ]
    )
    assert all(
        not any("连续年度金额相差" in issue for issue in row["candidate_quality_issues"])
        for row in structured_rows
    )
    candidates = _line_candidates(
        ["应收账款", "4", "8,110,758,258.05", "7,293,628,386.69"],
        0,
        term="应收账款",
    )
    assert candidates[0][0] == 8_110_758_258.05

    compact = compact_evidence_bundle(
        {
            "field_evidence": [{
                "evidence_id": "E1",
                "source_file": "private-path-13800138000.pdf",
                "document_id": "DOC-621700198001010011",
                "excerpt": "公开年报中的必要原文",
            }],
            "rag_evidence": [{"evidence_id": "E1", "excerpt": "重复的RAG片段"}],
            "supplement_evidence": [{"evidence_id": "E2", "excerpt": "独立补充证据"}],
        }
    )
    assert [item["evidence_id"] for item in compact] == ["E1", "E2"]
    assert "source_file" not in compact[0]
    assert "document_id" not in compact[0]
    minimized = minimize_model_context(
        {
            "risk_card": {
                "field_evidence": [{"file_sha256": "1234567890123456", "value": 10, "pdf_page": 4}],
                "observation": "保留程序观察",
            },
            "request_identity": {"user_id": "private"},
        }
    )
    assert minimized == {
        "risk_card": {"field_evidence": [{"value": 10, "pdf_page": 4}], "observation": "保留程序观察"}
    }
    assert CNInfoFieldConfirmation(
        field_id="provision_coverage_ratio_2025",
        decision="confirm",
        reviewer="专业复核人",
    ).field_id == "provision_coverage_ratio_2025"
    with pytest.raises(ValueError):
        CNInfoFieldConfirmation(field_id="../../secret_2025", decision="confirm", reviewer="专业复核人")


def test_demo_readonly_contracts_are_available() -> None:
    client = TestClient(app)
    evaluation = client.get("/api/evaluations/current")
    assert evaluation.status_code == 200
    assert evaluation.json()["evaluation_id"] == "EVAL-20260828-RELEASE-CANDIDATE-V1"
    assert evaluation.json()["current_pointer_status"] == "valid"
    # 新评估只为三案技术评估建立骨架；旧八案评估仍作为历史记录保留。
    payload = evaluation.json()
    assert len(payload["cases"]) == 3
    assert {case["case_id"] for case in payload["cases"]} == {
        "CNINFO_000858_T0_20260430",
        "CNINFO_600938_T0_20260326",
        "STD_DEV_T0",
    }
    for case in payload["cases"]:
        assert set(case["groups"]) == {"B0", "B1", "B2", "B3"}
        assert all(group["status"] == "not_started" for group in case["groups"].values())
    samples = client.get("/api/supplement-samples")
    assert samples.status_code == 200
    assert {item["sample_id"] for item in samples.json()["samples"]} == {"aging", "receipts"}


def test_public_demo_prefers_frozen_seed_rag_in_a_fresh_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """15 案新命名空间也必须走冻结片段，不依赖开发机旧 FAISS 目录。"""

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    monkeypatch.setenv("AUDITTRACE_RUNTIME_NAMESPACE", f"seed-priority-{uuid.uuid4().hex}")
    client = TestClient(app)

    seed_case_id = "CNINFO_000858_T0_20260430"
    status = client.get(f"/api/rag/status?case_id={seed_case_id}")
    assert status.status_code == 200
    assert status.json()["index_status"] == "seed_snapshot"
    assert status.json()["runtime_ready"] is True

    retrieved = client.post(
        "/api/rag/retrieve",
        json={"case_id": seed_case_id, "query": "应收账款", "top_k": 5},
    )
    assert retrieved.status_code == 200, retrieved.text
    assert retrieved.json()["filter"]["retrieval_mode"] == "tracked_demo_excerpts"
    assert retrieved.json()["case_id"] == seed_case_id


def test_summary_case_directory_is_compact() -> None:
    client = TestClient(app)
    response = client.get("/api/cases?summary=true")
    assert response.status_code == 200
    cases = response.json()["cases"]
    assert all(
        set(item) >= {
            "case_id",
            "company_name",
            "available_years",
            "registry_mode",
            "source_type",
        }
        for item in cases
    )
    # 开发机目录会长期积累历史合成案例（当前 pytest 命名空间已有数百个），
    # 因此合同以“单案例摘要足够轻量”为准：每个案例只携带选择器所需元数据，
    # 完整元数据始终由详情接口返回；总量只设宽松上限防止意外膨胀。
    import json

    for item in cases:
        assert len(json.dumps(item, ensure_ascii=False)) <= 400
    assert len(response.content) < 400_000


def test_model_readiness_keeps_configuration_separate_from_public_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.provider_readiness import ProviderSnapshot

    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", raising=False)
    assert _model_readiness()["full_analysis_reason_code"] == "api_key_missing"

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    assert _model_readiness()["full_analysis_reason_code"] == "public_quota_secret_missing"
    monkeypatch.setenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "x" * 32)

    class ReadyLedger:
        def quota_snapshot(self, _client_id=None):
            return {"global_remaining_15m": 2, "daily_runs_remaining": 4, "active": 0, "max_concurrent": 2}

    monkeypatch.setattr("backend.app.main._public_model_ledger", lambda: ReadyLedger())
    # 已配置的 Key、额度账本和历史状态都不能代替当前 provider 探测或真实运行。
    monkeypatch.setattr(
        "backend.app.main.get_provider_snapshot",
        lambda: ProviderSnapshot(
            status="unavailable",
            reason_code="provider_probe_disabled",
            message="主动探测未开启，当前真实模型可运行性尚未验证。",
            checked_at="2026-08-20T00:00:00Z",
            expires_at="2026-08-20T00:05:00Z",
            source="default",
            stale=False,
            paid_probe_performed=False,
            next_action_code="enable_provider_probe_or_run_live",
        ),
    )
    unverified = _model_readiness()
    assert unverified["full_analysis_ready"] is False
    assert unverified["full_analysis_reason_code"] == "provider_probe_disabled"

    class EmptyLedger:
        def quota_snapshot(self, _client_id=None):
            return {"global_remaining_15m": 0, "daily_runs_remaining": 4, "active": 0, "max_concurrent": 2}

    monkeypatch.setattr("backend.app.main._public_model_ledger", lambda: EmptyLedger())
    exhausted = _model_readiness()
    assert exhausted["full_analysis_reason_code"] == "quota_exhausted"
    assert exhausted["deterministic_backup_available"] is True


def _mock_opencode_response(payload: dict) -> MagicMock:
    """构造仅在内存返回的 OpenAI 兼容响应，确保合同测试绝不触网。"""
    response = MagicMock()
    response.read.return_value = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response.__enter__.return_value = response
    return response


@pytest.mark.parametrize(
    ("response_payload", "failure_code"),
    [
        (
            {"choices": [{"finish_reason": "length", "message": {"tool_calls": []}}]},
            "MODEL_TOOL_OUTPUT_TRUNCATED",
        ),
        (
            {
                "choices": [{
                    "finish_reason": "tool_calls",
                    "message": {"tool_calls": [{"function": {"name": "unexpected_tool", "arguments": "{}"}}]},
                }],
            },
            "MODEL_TOOL_CALL_CONTRACT_ERROR",
        ),
    ],
)
def test_opencode_tool_contract_uses_distinct_safe_error_codes(
    monkeypatch: pytest.MonkeyPatch,
    response_payload: dict,
    failure_code: str,
) -> None:
    """REQ-BACKEND: 截断与错误工具名必须给出不同、且不泄露凭据的失败码。"""
    monkeypatch.setattr(agents_module, "urlopen", lambda *_args, **_kwargs: _mock_opencode_response(response_payload))

    with pytest.raises(agents_module.ToolArgumentsError) as caught:
        agents_module._call_model(
            api_key="test-key-never-sent",
            base_url="https://opencode.ai/zen/go/v1",
            model_id="deepseek-v4-flash",
            role="challenge",
            payload={"run_id": "RUN-OPENCODE-CONTRACT", "rule_result": {"rule_id": "R1"}},
        )

    assert caught.value.failure_code == failure_code
    assert "test-key-never-sent" not in caught.value.detail


def test_r2_missing_fields_are_data_gaps_not_source_failures() -> None:
    result = _r2_result(
        [{"field_id": "revenue_current", "value": 100.0, "evidence_id": "E-R2-1"}],
        [],
        0.0,
    )
    assert result.status == "DATA_GAP"
    assert result.source_validation["issues"] == []
    assert result.risk_card["data_gaps"] == ["缺少R2字段：operating_cash_flow_current、operating_cash_flow_previous、revenue_previous"]


def test_gap_messages_and_evidence_ids_are_stable_and_deduplicated() -> None:
    gaps = _dedupe_gap_messages(
        [
            {"question_id": "RAG-Q1", "type": "retrieval_no_hit", "message": "请回查原文"},
            {"question_id": "RAG-Q1", "type": "retrieval_no_hit", "message": "请回查原文"},
        ]
    )
    assert gaps == ["RAG-Q1 · retrieval_no_hit：请回查原文"]
    request = SupplementRerunRequest(run_mode="full_analysis")
    assert request.force_deterministic_backup is False


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
                "claims": (
                    [{"text": "Evidence-bound model review.", "evidence_ids": [evidence_ids[0]], "support_status": "supported"}]
                    if evidence_ids
                    else []
                ),
                "normal_explanations": [],
                "data_gaps": [],
                "requested_materials": [],
                "reason_for_status": "The result is limited to the supplied evidence packet.",
                "draft_title": "External model review" if is_review else "",
                "draft_observation": "程序边界：趋势不可评价；External model review is retained for human confirmation." if is_review else "",
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
        assert body["model_check"]["status"] == "model_success", (
            item["case_id"],
            [
                {
                    "role": step.get("role"),
                    "status": step.get("status"),
                    "failure_code": step.get("failure_code"),
                    "detail": step.get("detail"),
                }
                for step in body.get("agent_steps") or []
            ],
        )
        assert body["provider_call_count"] == 3, item["case_id"]
        assert {step["role"] for step in body["agent_steps"] if step["status"] == "completed"} == {"challenge", "counter", "review"}


def test_demo_run_task_api_shows_real_staged_progress(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """G2：POST /api/demo/runs 返回 202，轮询得到后端真实六阶段，终态可读 RunResponse。"""
    import backend.app.main as main_module
    from backend.app.demo_run_tasks import DemoRunTaskStore

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "false")
    monkeypatch.setattr(
        main_module,
        "_run_rag_for_analysis",
        lambda **_kwargs: ([], [], [], None),
    )
    demo_store = DemoRunTaskStore(tmp_path / "demo-tasks")
    monkeypatch.setattr(main_module, "_get_demo_run_store", lambda: demo_store)
    client = TestClient(app)
    try:
        created = client.post(
            "/api/demo/runs",
            json={"case_id": "STD_DEV_T0", "current_year": 2025, "rule_ids": ["R1", "R2"], "run_mode": "full_analysis"},
        )
        assert created.status_code == 202, created.text
        payload = created.json()
        task_id = payload["task_id"]
        assert task_id.startswith("DEMO-RUN-")
        assert payload["status"] in {"queued", "running"}
        assert payload["stage_schema_version"] == "demo_task_v2"
        assert list(payload["steps"]) == ["evidence_load", "rule_calculation", "knowledge_retrieval", "agent_collaboration", "evidence_validation", "structured_output"]

        deadline = time.time() + 120
        task = None
        while time.time() < deadline:
            task = client.get(f"/api/demo/runs/{task_id}").json()
            if task["status"] not in {"queued", "running"}:
                break
            time.sleep(0.2)
        assert task is not None and task["status"] in {"completed", "degraded", "failed"}
        assert task["run_id"] and task["run_id"].startswith("RUN-")
        for stage_name, stage in task["steps"].items():
            assert stage["status"] in {"completed", "skipped", "failed", "degraded", "pending"}, stage_name
        if task["status"] != "failed":
            assert task["steps"]["structured_output"]["status"] == "completed"
            assert "RUN-" in task["steps"]["structured_output"]["detail"]
        agent_steps = task["agent_steps"]
        assert set(agent_steps.keys()) == {"challenge", "counter", "review"}

        result_response = client.get(f"/api/demo/runs/{task_id}/result")
        assert result_response.status_code == 200
        run = result_response.json()
        assert run["run_id"] == task["run_id"]

        # 终态任务不可取消；未知任务 404
        assert client.post(f"/api/demo/runs/{task_id}/cancel").status_code == 409
        assert client.get("/api/demo/runs/DEMO-RUN-UNKNOWN").status_code == 404
    finally:
        demo_store.shutdown()


def test_rag_and_sensitive_data_fail_closed_in_all_case_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.main as main_module

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    provider_calls: list[str] = []
    monkeypatch.setattr(agents_module, "_call_model", lambda **_kwargs: provider_calls.append("called"))
    client = TestClient(app)

    monkeypatch.setattr(
        main_module,
        "_run_rag_for_analysis",
        lambda **_kwargs: ([], [], [], "forced-rag-failure"),
    )
    rag_failed = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2024, "rule_ids": ["R1"], "run_mode": "full_analysis"},
    )
    assert rag_failed.status_code == 200
    assert rag_failed.json()["model_check"]["status"] == "not_attempted_rag_failure"
    assert provider_calls == []

    monkeypatch.setattr(
        main_module,
        "_run_rag_for_analysis",
        lambda **_kwargs: (
            [],
            [{"evidence_id": "RAG-E1", "excerpt": "联系人手机号 13800138000", "review_status": "pending"}],
            [],
            None,
        ),
    )
    sensitive = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2024, "rule_ids": ["R1"], "run_mode": "full_analysis"},
    )
    assert sensitive.status_code == 200
    assert sensitive.json()["model_check"]["status"] == "sensitive_data_blocked"
    assert sensitive.json()["context"]["privacy_scan"]["status"] == "blocked"
    assert provider_calls == []


def test_sensitive_data_fail_closed_for_non_demo_public_prescreen(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.main as main_module

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "false")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "false")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "false")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    provider_calls: list[str] = []
    monkeypatch.setattr(agents_module, "_call_model", lambda **_kwargs: provider_calls.append("called"))
    monkeypatch.setattr(
        main_module,
        "_run_rag_for_analysis",
        lambda **_kwargs: (
            [],
            [{"evidence_id": "RAG-E1", "excerpt": "联系人手机号 13800138000", "review_status": "pending"}],
            [],
            None,
        ),
    )
    response = TestClient(app).post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2024, "rule_ids": ["R1"], "run_mode": "full_analysis"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["context"]["external_model_call_planned"] is True
    assert body["context"]["privacy_scan"]["status"] == "blocked"
    assert body["model_check"]["status"] == "sensitive_data_blocked"
    assert body["rule_results"][0]["agent_steps"][0]["failure_code"] == "SENSITIVE_DATA_BLOCKED"
    assert provider_calls == []


def test_shared_public_demo_rejects_arbitrary_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    response = TestClient(app).post(
        "/api/cases/import",
        data={"authorized": "true", "desensitized": "true"},
        files={"file": ("case.zip", b"not-a-zip", "application/zip")},
    )
    assert response.status_code == 403

    client = TestClient(app)
    forbidden_requests = [
        client.post(
            "/api/cases/STD_DEV_T0/fields/confirm",
            json={"field_id": "revenue_2024", "decision": "confirm", "reviewer": "anonymous", "reason": "demo"},
        ),
        client.post(
            "/api/runs/RUN-NOT-REAL/review",
            json={
                "status": "保留为待核查候选",
                "note": "anonymous approval",
                "reviewer": "anonymous",
                "export_approved": True,
                "reviewer_type": "human",
            },
        ),
        client.post(
            "/api/cache/prewarm",
            json={"companies": ["002594"], "years": 3, "analysis_mode": "rag_only", "rule_ids": ["R1"]},
        ),
        client.post("/api/cache/refresh/002594"),
        client.post(
            "/api/pipelines/cninfo",
            json={"company_query": "999999", "years": 3, "analysis_mode": "rag_only", "rule_ids": ["R1"]},
        ),
    ]
    assert [item.status_code for item in forbidden_requests] == [403, 403, 403, 403, 403]


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
    assert steps[0].provider_call_performed is True
    assert [step.status for step in steps[1:]] == ["skipped", "skipped"]


def test_provider_timeout_has_distinct_code_and_does_not_blind_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def provider_timeout(**_kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("provider response exceeded window")

    monkeypatch.setattr(agents_module, "_call_model", provider_timeout)
    steps = run_agent_chain(
        run_id="RUN-TIMEOUT-CHAIN",
        rule_result=RuleResult(rule_id="R1", status="candidate", source_validation={}, metrics={}, risk_card={}),
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "最小证据片段"}],
        enabled=True,
        api_key="test-key",
        base_url="https://example.invalid",
        model_id="deepseek-v4-flash",
    )

    assert calls == 1
    assert steps[0].status == "provider_unreachable"
    assert steps[0].failure_code == "MODEL_PROVIDER_TIMEOUT"
    assert steps[0].provider_call_count == 1
    assert steps[0].model_attempt_history[0]["validation"] == "MODEL_PROVIDER_TIMEOUT"
    assert [step.status for step in steps[1:]] == ["skipped", "skipped"]


def test_model_generated_sensitive_data_stops_later_roles_and_keeps_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def sensitive_provider(**kwargs):
        role = kwargs["payload"]["role"]
        calls.append(role)
        return (
            {
                "schema_version": "agent_output_v2",
                "run_id": "RUN-SENSITIVE-OUTPUT",
                "role": role,
                "rule_id": "R1",
                "analysis_conclusion": "risk_candidate",
                "status": "candidate",
                "claims": [
                    {
                        "text": "请联系 13800138000 进一步核实证据。",
                        "evidence_ids": ["E1"],
                        "support_status": "supported",
                    }
                ],
                "normal_explanations": [],
                "data_gaps": [],
                "requested_materials": [],
                "reason_for_status": "仅依据当前证据包。",
                "draft_title": "",
                "draft_observation": "",
                "ai_recommendation": "not_applicable",
            },
            12,
            "response-sensitive",
            "input-sensitive",
            23,
            7,
        )

    monkeypatch.setattr(agents_module, "_call_model", sensitive_provider)
    steps = run_agent_chain(
        run_id="RUN-SENSITIVE-OUTPUT",
        rule_result=RuleResult(
            rule_id="R1",
            status="candidate",
            source_validation={},
            metrics={},
            risk_card={},
        ),
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "已登记证据"}],
        enabled=True,
        api_key="test-key",
        base_url="https://example.invalid",
        model_id="deepseek-v4-flash",
    )
    assert calls == ["challenge"]
    assert [step.status for step in steps] == ["MODEL_OUTPUT_INVALID", "skipped", "skipped"]
    blocked = steps[0]
    assert blocked.failure_stage == "policy"
    assert blocked.failure_code == "MODEL_OUTPUT_SENSITIVE_DATA"
    assert blocked.output is None
    assert blocked.provider_call_performed is True
    assert blocked.input_tokens == 23
    assert blocked.output_tokens == 7
    assert "13800138000" not in blocked.detail
    assert "claims[0].text" in blocked.detail
    check = _enrich_model_check(
        ModelCheck(status="MODEL_OUTPUT_INVALID", model_id="deepseek-v4-flash", detail="blocked"),
        [RuleResult(rule_id="R1", status="candidate", source_validation={}, metrics={}, agent_steps=steps)],
    )
    assert check.provider_call_count == 1
    assert check.input_tokens == 23
    assert check.output_tokens == 7
    assert check.duration_ms == 12
    assert check.execution_mode == "unavailable"


def test_proxy_identity_and_cors_are_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def request(client: str, forwarded: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [(b"x-forwarded-for", forwarded.encode("ascii"))],
                "client": (client, 443),
                "server": ("audittrace.local", 443),
                "scheme": "https",
                "query_string": b"",
            }
        )

    monkeypatch.delenv("AUDITTRACE_TRUSTED_PROXY_HOPS", raising=False)
    monkeypatch.delenv("AUDITTRACE_TRUSTED_PROXY_CIDRS", raising=False)
    assert _client_identity(request("203.0.113.10", "198.51.100.7")) == "203.0.113.10"

    monkeypatch.setenv("AUDITTRACE_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setenv("AUDITTRACE_TRUSTED_PROXY_CIDRS", "203.0.113.0/24")
    _validate_trusted_proxy_configuration()
    assert _client_identity(request("203.0.113.10", "198.51.100.7")) == "198.51.100.7"
    assert _client_identity(request("192.0.2.10", "198.51.100.8")) == "192.0.2.10"
    assert _client_identity(request("203.0.113.10", "not-an-ip")) == "203.0.113.10"

    monkeypatch.setenv("AUDITTRACE_TRUSTED_PROXY_CIDRS", "0.0.0.0/0")
    with pytest.raises(RuntimeError):
        _validate_trusted_proxy_configuration()
    monkeypatch.setenv("AUDITTRACE_TRUSTED_PROXY_CIDRS", "")
    with pytest.raises(RuntimeError):
        _validate_trusted_proxy_configuration()

    monkeypatch.setenv(
        "AUDITTRACE_CORS_ORIGINS",
        "https://audit.example/,http://127.0.0.1:5173,https://audit.example",
    )
    assert _configured_cors_origins() == ["https://audit.example", "http://127.0.0.1:5173"]
    for invalid_origin in ("*", "https://*.example", "https://example.com/path", "https://example.com@evil.test"):
        monkeypatch.setenv("AUDITTRACE_CORS_ORIGINS", invalid_origin)
        with pytest.raises(RuntimeError):
            _configured_cors_origins()


def test_cache_fill_has_owner_identity_and_expiry(tmp_path: Path) -> None:
    ledger = PublicModelLedger(
        tmp_path,
        config=QuotaConfig(cache_fill_ttl_seconds=1),
    )
    owner, first_event = ledger.acquire_cache_fill("same-input")
    assert owner is True
    waiter_owner, waiter_event = ledger.acquire_cache_fill("same-input")
    assert waiter_owner is False
    assert waiter_event is first_event

    with ledger._inflight_lock:
        ledger._inflight["same-input"] = (first_event, time.monotonic() - 2)
    replacement_owner, replacement_event = ledger.acquire_cache_fill("same-input")
    assert replacement_owner is True
    assert replacement_event is not first_event
    assert first_event.is_set()

    ledger.complete_cache_fill("same-input", first_event)
    still_waiting_owner, still_waiting_event = ledger.acquire_cache_fill("same-input")
    assert still_waiting_owner is False
    assert still_waiting_event is replacement_event
    ledger.complete_cache_fill("same-input", replacement_event)
    next_owner, _next_event = ledger.acquire_cache_fill("same-input")
    assert next_owner is True


def test_opencode_go_base_url_does_not_receive_native_deepseek_beta_suffix() -> None:
    assert _strict_tool_base_url("https://opencode.ai/zen/go/v1") == "https://opencode.ai/zen/go/v1"
    assert _strict_tool_base_url("https://opencode.ai/zen/go/v1/") == "https://opencode.ai/zen/go/v1"
    assert _strict_tool_base_url("https://api.deepseek.com") == "https://api.deepseek.com/beta"


def test_strict_tool_base_url_rejects_misconfigured_contracts() -> None:
    """配置错误必须返回稳定码并提示填写基础地址，不能把错误地址发给供应商。"""
    from backend.app.agents import ToolArgumentsError

    for invalid_url in (
        "https://opencode.ai/zen/go/v1/chat/completions",
        "https://example.com/v1/v1/chat/completions",
        "http://opencode.ai/zen/go/v1",
        "opencode.ai/zen/go/v1",
        "https://opencode.ai/zen/go/v1/v1",
        "https://中文字符.example.com/v1",
    ):
        with pytest.raises(ToolArgumentsError) as excinfo:
            _strict_tool_base_url(invalid_url)
        assert excinfo.value.failure_code == "MODEL_PROVIDER_BASE_URL_INVALID"
        assert "基础地址" in excinfo.value.detail


def test_provider_timeout_defaults_to_one_hundred_twenty_seconds_and_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDITTRACE_PROVIDER_TIMEOUT_SECONDS", raising=False)
    assert agents_module._provider_timeout_seconds() == 120.0
    monkeypatch.setenv("AUDITTRACE_PROVIDER_TIMEOUT_SECONDS", "5")
    assert agents_module._provider_timeout_seconds() == 10.0
    monkeypatch.setenv("AUDITTRACE_PROVIDER_TIMEOUT_SECONDS", "999")
    assert agents_module._provider_timeout_seconds() == 120.0
    monkeypatch.setenv("AUDITTRACE_PROVIDER_TIMEOUT_SECONDS", "invalid")
    assert agents_module._provider_timeout_seconds() == 120.0
