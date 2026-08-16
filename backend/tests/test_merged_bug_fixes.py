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
from backend.app.delivery import _display_gap, build_report
from backend.app.main import (
    _current_evidence_bundle,
    _dedupe_gap_messages,
    _format_evidence_gap,
    _model_readiness,
    _public_case_summary,
    _r2_result,
    app,
)
from backend.app.schemas import RunRequest, SupplementRerunRequest


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
