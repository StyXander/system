"""2026-10-17 整改项的单测：年度不回退、质量失败关闭、确定性入口、硬门禁、加性残差、声明分派。

全部使用合成输入，不引入企业研究数值，也不调用外部模型。
"""
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import connectivity_api
from app.connectivity_engine import calculate
from app.connectivity_extraction import _extract_tables, _quality
from app.connectivity_delivery import export_fingerprint, export_run, verify_export_same_source
from app.connectivity_overview import build_overview
from app.connectivity_pipeline import candidate_checks
from app.connectivity_schemas import (AdjustmentRecord, ConnectivityRun, DisclosureOccurrence, EvidenceRef,
    ReportDocument, notice_for)
from app.connectivity_engine import numeric_unit
from test_connectivity_engine import relationship

QUOTE = "合成企业2025年，同一统计范围。原文明示完整且互不重叠的组成关系、单位和公式。"


def document(**kwargs):
    base = dict(document_id="SYN", case_id="SYN-PAIR", company_id="SYN", company="合成企业",
                report_type="ESG", period="2025", source_url="https://example.invalid/synthetic")
    base.update(kwargs)
    return ReportDocument(**base)


def row(index, label, value, unit="万元", year="2025", column="2025 年", **kwargs):
    fields = dict(occurrence_id=f"SYN-{index}", document_id="SYN", pdf_page=10, label=label, value=value, unit=unit,
                  year=year, year_status="attributed", column_header=column, quality="located",
                  quality_reason="年度、单位与行列头均已绑定", topic="environment",
                  row_header=f"{label} {value} {unit}", context=f"{QUOTE}\n{label} | {value} | {unit}")
    fields.update(kwargs)
    return DisclosureOccurrence(**fields)


def test_year_column_must_not_fall_back_to_report_period():
    page = {"page": 1, "lines": [], "tables": [{"bbox": [0, 0, 400, 40],
        "data": [["项目", "本期"], ["环保投入", "20"]],
        "cells": [[[0, 0, 100, 20], [100, 0, 200, 20]], [[0, 20, 100, 40], [100, 20, 200, 40]]],
        "headers": [{"text": "本期", "bbox": [100, 0, 200, 20], "table_bbox": [0, 0, 200, 20]}]}]}
    result = _extract_tables(page, document(period="2024"), ["environment"])
    assert result and result[0].year == ""
    assert result[0].year_status == "unattributed"
    assert result[0].quality == "uncertain"
    assert "年度" in result[0].quality_reason


def test_quality_defaults_to_uncertain_and_requires_year_unit_header():
    bare = DisclosureOccurrence(occurrence_id="X", document_id="SYN", pdf_page=1, label="环保投入",
        value="1", context=QUOTE)
    assert bare.quality == "uncertain"
    assert bare.year_status == "unattributed"
    assert _quality("2025", "万元", "2025 年")[0] == "located"
    assert _quality("", "万元", "2025 年")[0] == "uncertain"
    assert _quality("2025", "", "2025 年")[0] == "uncertain"
    assert _quality("2025", "万元", "")[0] == "uncertain"


def test_composition_candidate_has_deterministic_entrance():
    rows = [row(1, "环保投入费用化", "60"), row(2, "环保投入资本化", "40"),
            row(3, "环保投入合计", "100"), row(4, "环保投入合计", "100", pdf_page=20)]
    checks = candidate_checks(rows, "2025")
    composition = [c for c in checks if c.rule_id == "ENV-001"]
    assert composition, "同表合计与分项必须形成确定性组成候选"
    members = {m.role for m in composition[0].members}
    assert members == {"total", "component"}
    assert composition[0].criteria_status == "unknown", "结构成立不等于前提已获支持"
    assert composition[0].calculation["residual"] is None


def test_ratio_candidate_uses_formula_in_label():
    rows = [row(1, "研发投入", "20", topic="research"), row(2, "营业收入", "400", topic="research"),
            row(3, "研发投入占营业收入比例", "5", unit="%", topic="research")]
    checks = candidate_checks(rows, "2025")
    ratio = [c for c in checks if c.rule_id == "INT-001"]
    assert ratio, "指标名称写明公式时必须形成确定性比例候选"
    assert {m.role for m in ratio[0].members} == {"numerator", "denominator", "reported_ratio"}


def test_unattributed_rows_do_not_enter_candidates_but_stay_excluded():
    rows = [row(1, "环保投入费用化", "60", year="", year_status="unattributed", quality="uncertain",
                quality_reason="年度列无法归属，未回退为报告期间")]
    checks = candidate_checks(rows, "2025")
    assert not [c for c in checks if c.rule_id == "ENV-001"]


def adjustment(adjustment_id="ADJ-1", effect_id="EFF-1", amount="5", sign="-", path="amount_bridge", **kwargs):
    fields = dict(rounding="exact")
    fields.update(kwargs)
    return AdjustmentRecord(adjustment_id=adjustment_id, effect_id=effect_id, label="合成调节项", sign=sign,
        amount=amount, unit="万元", metric_period="2025", scope="合并范围", basis_id="BASIS-1", path=path,
        evidence=[EvidenceRef(occurrence_id="SYN-0", quote=QUOTE)], **fields)


def test_additive_adjustment_reduces_residual_but_is_not_a_free_pass():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    assert calculate(check, rows).calculation["residual"] == "-50000"
    check.adjustments = [adjustment()]
    result = calculate(check, rows)
    assert result.calculation_status == "adjustment_explained"
    assert result.calculation["adjustment"]["remaining_residual"] == "0"
    assert result.calculation["adjustment"]["closed"] is True
    assert "不证明解释真实" in result.calculation["adjustment"]["note"]
    # 调节额不足时保留剩余残差，不能靠改标签关闭差额。
    check.adjustments = [adjustment(amount="2")]
    partial = calculate(check, rows)
    assert partial.calculation_status == "unexplained_difference"
    assert partial.calculation["adjustment"]["remaining_residual"] == "-30000"


def test_duplicate_effect_is_rejected_but_declared_overlap_with_basis_is_allowed():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    check.adjustments = [adjustment("ADJ-1", "EFF-1", "2"), adjustment("ADJ-2", "EFF-1", "3")]
    result = calculate(check, rows)
    assert result.calculation_status == "unexplained_difference"
    # 重复项被拒，已采纳项保留记录但拒绝正式闭合。
    assert [item["effect_id"] for item in result.calculation["adjustment"]["applied"]] == ["EFF-1"]
    assert result.calculation["adjustment"]["closed"] is False
    assert any("再次扣除" in value for value in result.unresolved)
    # 声明与本次未采纳的效果重叠，且给出互斥依据：应接受并记录依据，不是"声明即拒绝"。
    check.adjustments = [adjustment(overlap_with=["EFF-9"], overlap_basis="原文分列不同表，互不重叠")]
    allowed = calculate(check, rows)
    assert len(allowed.calculation["adjustment"]["applied"]) == 1
    assert allowed.calculation["adjustment"]["applied"][0]["overlap_basis"].startswith("原文分列")
    assert allowed.calculation_status == "adjustment_explained"
    # 与本次已采纳的效果重叠：拒绝叠加。
    check.adjustments = [adjustment("ADJ-1", "EFF-1", "2"),
                        adjustment("ADJ-2", "EFF-2", "3", overlap_with=["EFF-1"], overlap_basis="同一对象")]
    overlapping = calculate(check, rows)
    assert [item["effect_id"] for item in overlapping.calculation["adjustment"]["applied"]] == ["EFF-1"]
    assert any("重叠" in value for value in overlapping.unresolved)
    # 声明重叠却无依据：拒绝。
    check.adjustments = [adjustment(overlap_with=["EFF-9"])]
    missing = calculate(check, rows)
    assert missing.calculation["adjustment"]["applied"] == []
    assert any("未给出互斥依据" in value for value in missing.unresolved)


def test_grouping_adjustment_registers_basis_without_deducting_amount():
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    assert calculate(check, rows).calculation_status == "consistent"
    check.adjustments = [adjustment(path="grouping", amount="5", sign="-")]
    result = calculate(check, rows)
    # 分组只登记新基准，不扣金额，也不能把本来衔接的关系判成未解释差异。
    assert result.calculation["adjustment"]["basis_partitions"]
    assert result.calculation["adjustment"]["applied"] == []
    assert result.calculation["adjustment"]["total"] == "0"
    assert result.calculation["adjustment"]["remaining_residual"] == "0"
    assert result.calculation_status == "consistent"


def test_adjustment_amount_without_rounding_method_cannot_close():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    item = adjustment()
    item.rounding = "unknown"
    check.adjustments = [item]
    result = calculate(check, rows)
    assert result.calculation["adjustment"]["interval_status"] == "unknown"
    assert result.calculation["adjustment"]["closed"] is False
    assert result.calculation_status == "unexplained_difference"
    assert any("精度方法未声明" in value for value in result.unresolved)


def test_multi_position_residual_interval_is_envelope_not_point():
    rows, check = relationship("OCC-001", ["100", "100", "105"], ["occurrence"] * 3)
    check.conditions[-1].status = "unknown"
    result = calculate(check, rows)
    # 门禁下不给正式区间；试算里的各位置区间必须来自成员舍入区间，而不是点值。
    assert result.calculation["residual_interval"] is None
    positions = result.hypothetical["positions"]
    assert all("residual_interval" in item for item in positions)


def test_ratio_derives_denominator_interval():
    rows, check = relationship("INT-001", ["20", "100", "20"], ["numerator", "denominator", "reported_ratio"],
                               ["万元", "万元", "%"])
    result = calculate(check, rows)
    assert result.calculation["denominator_check"]["compatible"] is True
    implied = result.calculation["denominator_check"]["implied"]
    assert Decimal(implied["low"]) == Decimal(implied["high"]) == Decimal("1000000")


def test_ratio_and_occurrence_adjustments_are_not_supported():
    rows, check = relationship("INT-001", ["20", "100", "20"], ["numerator", "denominator", "reported_ratio"],
                               ["万元", "万元", "%"])
    check.adjustments = [adjustment()]
    result = calculate(check, rows)
    assert result.calculation_status == "consistent", "未采纳调节不改变原正式结论"
    assert any("受控变换" in value for value in result.unresolved)


def test_adjustment_without_source_is_rejected():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    item = adjustment()
    item.evidence = [EvidenceRef(occurrence_id="SYN-0", quote="原文并不存在的调节依据")]
    check.adjustments = [item]
    result = calculate(check, rows)
    assert result.calculation["adjustment"]["applied"] == []
    assert any("出处" in value for value in result.unresolved)


def test_notice_is_dispatched_by_task_kind():
    assert notice_for("connectivity").startswith("AI生成内容，用于年度报告与可持续发展报告关联核对")
    assert notice_for("legacy_audit").startswith("AI生成内容，仅供审计计划阶段进一步核查")
    with pytest.raises(ValueError):
        notice_for("unknown_task")


def test_export_carries_notice_and_matches_page_fingerprint():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    run = ConnectivityRun(run_id="SYN-RUN", company="合成企业", period="2025", documents=[document()],
                          occurrences=rows, checks=[calculate(check, rows)], dataset_role="synthetic")
    payload, _ = export_run(run, "json")
    assert notice_for("connectivity")[:10] in payload.decode("utf-8")
    assert verify_export_same_source(run, payload) == []
    csv_payload, _ = export_run(run, "csv")
    assert "差分" not in csv_payload.decode("utf-8-sig")
    assert export_fingerprint(run)[0]["residual"] == "-50000"


def test_overview_counts_carry_denominators_and_allow_overlap():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    run = ConnectivityRun(run_id="SYN-RUN", company="合成企业", period="2025", documents=[document()],
                          occurrences=rows, checks=[calculate(check, rows)], dataset_role="synthetic")
    overview = build_overview(run)
    for key in ("confirmable", "unconfirmable", "unexplained"):
        assert overview[key]["denominator"] == 1
    assert overview["not_found"]["value"] == 0
    assert "可能同时计入多个状态" in overview["note"]


def test_public_view_hides_personal_observation_body(tmp_path, monkeypatch):
    rows, check = relationship("EQ-001", ["1", "10000"], ["left", "right"], ["亿元", "万元"])
    run = ConnectivityRun(run_id="SYN-RUN", company="合成企业", period="2025", documents=[document()],
                          occurrences=rows, checks=[calculate(check, rows)], dataset_role="synthetic")
    overall = build_overview(run)
    run.overview = overall
    run.professional_notes = [{"check_id": "SYN-CHECK", "observation": "个人对统计范围的疑问",
                               "reason": "合成理由", "actor": "合成使用者", "created_at": "2026-10-17T00:00:00+00:00"}]
    monkeypatch.setattr(connectivity_api, "load_registry", lambda root: [document()])
    monkeypatch.setattr(connectivity_api, "demo_task_supabase_enabled", lambda: False)
    monkeypatch.setattr(connectivity_api, "run_pipeline", lambda *args, **kwargs: run.model_copy(deep=True))
    monkeypatch.setenv("AUDITTRACE_DEMO_EXECUTOR_MODE", "web")
    app = FastAPI()
    app.include_router(connectivity_api.build_router(tmp_path, lambda request: None, lambda: None))
    with TestClient(app) as owner:
        owner.get("/api/connectivity/bootstrap")
        task_id = owner.post("/api/connectivity/runs", json={"pair_id": "SYN-PAIR", "mode": "calculation_only"}).json()["task_id"]
        for _ in range(100):
            body = owner.get(f"/api/connectivity/runs/{task_id}").json()
            if body["status"] not in {"queued", "running"}:
                break
        assert body["result"]["professional_notes"][0]["observation"] == "个人对统计范围的疑问"
        assert body["result"]["personal_observation_count"] == 1
        assert body["can_modify"] is True
    with TestClient(app) as stranger:
        stranger.get("/api/connectivity/bootstrap")
        view = stranger.get(f"/api/connectivity/runs/{task_id}").json()
        assert view["result"]["professional_notes"] == []
        assert view["result"]["personal_observation_count"] == 1
        assert view["can_modify"] is False
        public_csv = stranger.get(f"/api/connectivity/runs/{task_id}/export/csv").content.decode("utf-8-sig")
        assert "个人对统计范围的疑问" not in public_csv
        own_csv = owner.get(f"/api/connectivity/runs/{task_id}/export/csv?private=1").content.decode("utf-8-sig")
        assert "个人对统计范围的疑问" in own_csv
