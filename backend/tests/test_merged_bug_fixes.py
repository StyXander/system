"""审迹智链合并 Bug 清单修复与上线验证测试 (AT-001 ~ AT-014, A1 ~ A7)。

覆盖模型就绪判定、确定性备用回退、R2 来源闸门纯净性、资料缺口中文格式化、
证据去重与常规运行 0 补充、补充续分析清除备用标记、案例目录来源标签等。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app import main as app_module
from backend.app import agents as agents_module
from backend.app.delivery import _display_gap, build_report
from backend.app.main import (
    _current_evidence_bundle,
    _dedupe_gap_messages,
    _format_evidence_gap,
    _model_readiness,
    _record_provider_run_feedback,
    _public_case_summary,
    _r2_result,
    app,
)
from backend.app.schemas import AgentStep, RuleResult, RunRequest, SupplementRerunRequest


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_and_status_model_fields(client: TestClient) -> None:
    """AT-001 & AT-002: /api/health 与 /api/status.model 提供就绪兼容字段。"""
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    health = health_resp.json()
    assert "full_analysis_ready" in health
    assert "full_analysis_reason_code" in health
    assert "full_analysis_message" in health
    assert "deterministic_backup_available" in health
    assert health["deterministic_backup_available"] is True

    status_resp = client.get("/api/status")
    assert status_resp.status_code == 200
    status = status_resp.json()
    model = status.get("model", {})
    assert "full_analysis_ready" in model
    assert "deterministic_backup_available" in model


def test_model_readiness_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-001: 只有 API Key、配额密钥与账本额度均具备时，full_analysis_ready 才为 True。"""
    # 场景 1：无 API Key
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AUDITTRACE_OPENAI_API_KEY", "")
    monkeypatch.setenv("AUDITTRACE_MODEL_API_KEY", "")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "secret-must-be-at-least-32-chars-long-abc")
    info1 = _model_readiness()
    assert not info1["full_analysis_ready"]
    assert info1["full_analysis_reason_code"] == "api_key_missing"
    assert info1["deterministic_backup_available"] is True

    # 场景 2：公网模式且缺少配额密钥
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123456")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "true")
    info2 = _model_readiness()
    assert not info2["full_analysis_ready"]
    assert info2["full_analysis_reason_code"] == "public_quota_secret_missing"
    assert info2["deterministic_backup_available"] is True

    # 场景 3：公网模式且配额密钥短于 32 位
    monkeypatch.setenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "too-short")
    info3 = _model_readiness()
    assert not info3["full_analysis_ready"]
    assert info3["full_analysis_reason_code"] == "public_quota_secret_invalid"
    assert info3["deterministic_backup_available"] is True


def test_force_deterministic_backup_direct_run(client: TestClient) -> None:
    """AT-003: 即使没有已存 run_id，POST /api/runs 携带 force_deterministic_backup=True 也可直接执行。"""
    payload = {
        "case_id": "STD_DEV_T0",
        "current_year": 2024,
        "rule_ids": ["R1"],
        "run_mode": "full_analysis",
        "force_deterministic_backup": True,
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_mode"] == "deterministic_backup"
    assert data["run_completeness"] in ("complete_demo_fallback", "complete_demo_fallback_with_gaps")
    assert data["context"].get("continuation_mode") == "explicit_deterministic_backup"


def test_r2_missing_field_preserves_source_validation_purity() -> None:
    """AT-004: R2 字段缺失走 DATA_GAP，不污染来源技术闸门 (source_validation.valid 保持 True)。"""
    result = _r2_result(
        rows=[],  # 空字段输入
        source_issues=[],
        min_gap=0.08,
    )
    assert result.status == "DATA_GAP"
    sv = result.source_validation
    assert (sv.get("status") if isinstance(sv, dict) else sv.status) == "passed"
    assert len(sv.get("issues", []) if isinstance(sv, dict) else sv.issues) == 0
    assert len(result.risk_card.get("data_gaps", [])) > 0


def test_format_evidence_gap_and_deduplication() -> None:
    """AT-005: 资料缺口格式化为人类可读中文短句，不泄漏 Python dict repr。"""
    raw_gap_dict = {
        "question_id": "Q-01",
        "type": "数据缺口",
        "message": "缺少 2023 年期初应收账款数据",
    }
    text = _format_evidence_gap(raw_gap_dict)
    assert "Q-01 · 数据缺口：缺少 2023 年期初应收账款数据" == text
    assert "{" not in text

    # 测试去重
    items = [
        raw_gap_dict,
        {"question_id": "Q-01", "type": "数据缺口", "message": "缺少 2023 年期初应收账款数据"},
        "缺少 2022 年营业收入",
        "缺少 2022 年营业收入",
    ]
    deduped = _dedupe_gap_messages(items)
    assert len(deduped) == 2
    assert "Q-01 · 数据缺口：缺少 2023 年期初应收账款数据" in deduped
    assert "缺少 2022 年营业收入" in deduped


def test_normal_run_evidence_bundle_has_zero_supplement(client: TestClient) -> None:
    """AT-006: 常规案例运行不会把 case 基础字段错误地变成 supplement_evidence。"""
    payload = {
        "case_id": "STD_DEV_T0",
        "current_year": 2024,
        "rule_ids": ["R1"],
        "run_mode": "calculation_only",
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    supplement_evidence = data["evidence_bundle"].get("supplement_evidence", [])
    assert len(supplement_evidence) == 0


def test_public_case_summary_source_labels() -> None:
    """AT-008: 案例目录摘要正确输出中文标签与机器可读来源。"""
    std_case = {"case_id": "STD_DEV_T0", "company_name": "标准股份", "available_years": [2024, 2023]}
    jack_case = {"case_id": "JACK_TECH_2024", "company_name": "杰克科技", "available_years": [2024]}
    cninfo_case = {"case_id": "CNINFO_600938_T0_20260326", "company_name": "中海油", "available_years": [2024], "registry_mode": "cninfo_official_auto"}
    synthetic_case = {"case_id": "SYNTH_01", "company_name": "合成制造", "available_years": [2024], "sample_type": "synthetic"}

    assert _public_case_summary(std_case)["source_label"] == "标准股份开发案例"
    assert _public_case_summary(jack_case)["source_label"] == "手工登记案例"
    assert _public_case_summary(cninfo_case)["source_label"] == "巨潮年报抓取"
    assert _public_case_summary(synthetic_case)["source_label"] == "合成样例"
    assert _public_case_summary(std_case)["registry_mode"] == "built_in"
    assert _public_case_summary(jack_case)["source_type"] == "manual_registered"
    assert _public_case_summary(cninfo_case)["registry_mode"] == "cninfo_official_auto"
    assert _public_case_summary(cninfo_case)["source_type"] == "official_annual_report"


def test_delivery_display_gap_deduplication() -> None:
    """AT-005: delivery 报告导出中资料缺口能正确格式化并去重。"""
    disp1 = _display_gap({"question_id": "Q-R1", "type": "资料缺口", "message": "待回查期后回款"})
    disp2 = _display_gap("待索取主要销售合同")
    assert disp1 == "Q-R1 · 资料缺口：待回查期后回款"
    assert disp2 == "待索取主要销售合同"


def test_unified_readiness_contract_between_health_and_status(client: TestClient) -> None:
    """AT-017: /api/health 与 /api/status 在相同请求下输出一致的真实模型就绪判定。"""
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()

    status_resp = client.get("/api/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()

    # 验证 AT-017 根级别名与 model 对象严格一致
    assert status_data.get("readiness_contract_version") == "model_readiness_v1"
    assert status_data["full_analysis_ready"] == status_data["model"]["full_analysis_ready"]
    assert status_data["full_analysis_reason_code"] == status_data["model"]["full_analysis_reason_code"]
    assert status_data["full_analysis_message"] == status_data["model"]["full_analysis_message"]
    assert status_data["deterministic_backup_available"] == status_data["model"]["deterministic_backup_available"]

    # 验证 health 与 status 一致
    assert health_data["full_analysis_ready"] == status_data["model"]["full_analysis_ready"]
    assert health_data["full_analysis_reason_code"] == status_data["model"]["full_analysis_reason_code"]
    assert health_data["deterministic_backup_available"] == status_data["model"]["deterministic_backup_available"]


def test_model_readiness_incorporates_provider_snapshot(monkeypatch) -> None:
    """AT-015: _model_readiness 在公开模式下会融合供应商就绪快照与熔断状态。"""
    from backend.app.provider_readiness import (
        ProviderSnapshot,
        reset_provider_readiness,
    )

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-valid-key")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "x" * 32)
    monkeypatch.setenv("AUDITTRACE_PROVIDER_PROBE_ENABLED", "true")
    reset_provider_readiness()

    # 模拟供应商余额耗尽
    exhausted_snap = ProviderSnapshot(
        status="unavailable",
        reason_code="provider_balance_exhausted",
        message="供应商账户余额不足",
        checked_at="2026-08-17T00:00:00Z",
        expires_at="2026-08-17T00:05:00Z",
        source="probe",
        stale=False,
    )
    with patch("backend.app.main.get_provider_snapshot", return_value=exhausted_snap):
        readiness = _model_readiness()
        assert readiness["full_analysis_ready"] is False
        assert readiness["full_analysis_reason_code"] == "provider_balance_exhausted"
        assert readiness["deterministic_backup_available"] is True
        assert readiness["provider"]["status"] == "unavailable"

    # 模拟供应商就绪
    ready_snap = ProviderSnapshot(
        status="ready",
        reason_code="ready",
        message="供应商鉴权与余额均就绪",
        checked_at="2026-08-17T00:00:00Z",
        expires_at="2026-08-17T00:05:00Z",
        source="probe",
        stale=False,
    )
    with patch("backend.app.main.get_provider_snapshot", return_value=ready_snap):
        readiness_ok = _model_readiness()
        assert readiness_ok["full_analysis_ready"] is True
        assert readiness_ok["full_analysis_reason_code"] == "ready"
        assert readiness_ok["provider"]["status"] == "ready"


def test_probe_disabled_snapshot_closes_status_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-BACKEND: provider_probe_disabled 不能由 /api/status 传播成 ready。"""
    from backend.app.provider_readiness import ProviderSnapshot

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-unverified-provider")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "false")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "false")
    unverified = ProviderSnapshot(
        status="unavailable",
        reason_code="provider_probe_disabled",
        message="未开启主动探测，尚未验证真实模型可运行性。",
        checked_at="2026-08-20T00:00:00Z",
        expires_at="2026-08-20T00:05:00Z",
        source="default",
        stale=False,
        paid_probe_performed=False,
        next_action_code="enable_provider_probe_or_run_live",
    )

    with patch("backend.app.main.get_provider_snapshot", return_value=unverified):
        readiness = _model_readiness()
        assert readiness["full_analysis_ready"] is False
        assert readiness["full_analysis_reason_code"] == "provider_probe_disabled"
        assert readiness["provider"]["status"] == "unavailable"


@pytest.mark.parametrize(
    ("provider_error", "expected_code"),
    [
        (ValueError("模型工具参数超过本角色输出上限"), "MODEL_TOOL_OUTPUT_TRUNCATED"),
        (ValueError("模型调用了未声明的输出工具"), "MODEL_TOOL_CALL_CONTRACT_ERROR"),
    ],
)
def test_tool_argument_failures_keep_distinct_diagnostic_codes(
    monkeypatch: pytest.MonkeyPatch,
    provider_error: ValueError,
    expected_code: str,
) -> None:
    """REQ-BACKEND: OpenCode 工具参数失败保留稳定子类，而非统一不可诊断码。"""
    def raise_provider_error(**_kwargs):
        raise provider_error

    monkeypatch.setattr(agents_module, "_call_model", raise_provider_error)
    steps = agents_module.run_agent_chain(
        run_id="RUN-TOOL-DIAGNOSTIC",
        rule_result=RuleResult(rule_id="R1", status="candidate", source_validation={}, metrics={}, risk_card={}),
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "已登记证据"}],
        enabled=True,
        api_key="test-key",
        base_url="https://opencode.ai/zen/go/v1",
        model_id="deepseek-v4-flash",
    )

    assert steps[0].failure_stage == "tool_arguments"
    assert steps[0].failure_code == expected_code
    assert [step.status for step in steps[1:]] == ["skipped", "skipped"]


def test_provider_feedback_uses_schema_failure_code_and_actual_failure_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-BACKEND: 运行反馈必须读取 AgentStep.failure_code，而非不存在的 error_code。"""
    recorded: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        app_module,
        "record_provider_failure",
        lambda code, detail, base_url=None: recorded.append((code, detail, str(base_url))),
    )
    monkeypatch.setattr(app_module, "record_provider_success", lambda **_kwargs: pytest.fail("失败运行不得记为成功"))

    _record_provider_run_feedback(
        [
            AgentStep(
                role="challenge",
                status="provider_unavailable",
                detail="供应商鉴权失败，已关闭本次调用。",
                failure_stage="provider",
                failure_code="MODEL_PROVIDER_AUTH_FAILED",
                provider_call_performed=True,
            ),
            AgentStep(role="counter", status="skipped", detail="前一角色失败，未调用。", failure_code="PREVIOUS_ROLE_FAILED"),
        ],
        model_id="deepseek-v4-flash",
        base_url="https://opencode.ai/zen/go/v1",
    )

    assert recorded == [(
        "MODEL_PROVIDER_AUTH_FAILED",
        "供应商鉴权失败，已关闭本次调用。",
        "https://opencode.ai/zen/go/v1",
    )]


def test_demo_agent_steps_candidate_retention_logic() -> None:
    """BUG-2: 演示模式下无缺口的 candidate 规则结果正确推荐 retain（保留为待核查候选）。"""
    from backend.app.schemas import RuleResult
    from backend.app.main import _demo_agent_steps

    candidate_rule_result = RuleResult(
        rule_id="R1",
        status="candidate",
        screening_status="candidate",
        risk_card={
            "rule_id": "R1",
            "title": "应收账款增幅显著高于营业收入",
            "observation": "应收增速 25.5%，收入增速 2.1%，差异超过强阈值。",
            "data_gaps": [],
            "requested_materials": ["大额销售合同", "期后回款凭证"],
        },
        source_validation={"issues": []},
        metrics={"ar_growth": 0.255, "rev_growth": 0.021},
    )

    steps = _demo_agent_steps(
        run_id="RUN-TEST-CANDIDATE",
        rule_result=candidate_rule_result,
        evidence_bundle={"field_evidence": [{"evidence_id": "EV-001"}], "evidence_gaps": []},
        model_id="demo-deterministic-v1",
        analysis_route="risk_candidate",
    )
    assert len(steps) == 3
    review_step = next(s for s in steps if s.role == "review")
    assert review_step.output.status == "retain"
    assert review_step.output.ai_recommendation == "retain"


def test_agent_output_schema_supports_top_5_claims() -> None:
    """BUG-5: AgentOutput Schema 与 Top 5 待核查事项对齐，支持至多 5 条主张。"""
    from backend.app.schemas import AgentOutput, AgentClaim

    claims = [
        AgentClaim(text=f"待核查事项 {i+1}：关键事实描述", evidence_ids=["EV-001"], support_status="supported")
        for i in range(5)
    ]
    output = AgentOutput(
        schema_version="agent_output_v2",
        run_id="RUN-TEST-TOP5",
        role="review",
        rule_id="R1",
        analysis_conclusion="risk_candidate",
        status="retain",
        claims=claims,
        normal_explanations=[],
        data_gaps=[],
        requested_materials=["销售明细账"],
        reason_for_status="5条主张均有证据编号支持，建议保留为待核查候选。",
        draft_title="Top 5 待核查事项建议草稿",
        draft_observation="应收增速与收入增速背离显著。",
        ai_recommendation="retain",
    )
    assert len(output.claims) == 5


def test_global_exception_handler_returns_ai_notice() -> None:
    """BUG-4: 全局未捕获异常返回 500 时必须强制携带 AI 免责声明。"""
    test_client = TestClient(app, raise_server_exceptions=False)
    with patch("backend.app.main._visible_case_records", side_effect=RuntimeError("Simulated unhandled system error")):
        response = test_client.get("/api/status")
        assert response.status_code == 500
        data = response.json()
        assert "ai_generated_content_notice" in data
        assert data["ai_generated_content_notice"] == "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
        assert "RuntimeError" in data.get("detail", "")


def test_cases_endpoint_defaults_to_standard_case_first() -> None:
    """默认首选案例必须始终为标准股份内置开发案例 STD_DEV_T0。"""
    test_client = TestClient(app)
    response = test_client.get("/api/cases?summary=true")
    assert response.status_code == 200
    cases = response.json().get("cases", [])
    assert len(cases) > 0
    assert cases[0]["case_id"] == "STD_DEV_T0"
    assert "标准股份" in (cases[0].get("company_alias") or cases[0].get("company_name") or "")


def test_status_endpoint_returns_provider_channel_metadata() -> None:
    """测试 /api/status 接口返回安全的供应商通道元数据。"""
    test_client = TestClient(app)
    response = test_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    model_meta = data.get("model", {})
    assert "provider_kind" in model_meta
    assert "provider_label" in model_meta
    assert "provider_host" in model_meta
    assert "next_action_code" in model_meta
    assert "DEEPSEEK_API_KEY" not in str(data)
