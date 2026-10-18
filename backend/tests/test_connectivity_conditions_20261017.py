"""前提可追溯升级、规则卡归属、指标期间与候选兜底的合成测试。

不引入企业研究数值，只用合成原文验证判定规则本身。
"""
from decimal import Decimal

import pytest

from app.connectivity_conditions import upgrade_conditions
from app.connectivity_engine import calculate
from app.connectivity_pipeline import candidate_checks
from app.connectivity_schemas import (ComparisonCondition, ConnectivityRun, DisclosureOccurrence, EvidenceRef,
    RelationshipCheck, RelationshipMember, ReportDocument)

ENTITY = "合成股份有限公司"
BASIS = f"{ENTITY} 2025年年度报告。报告主体为{ENTITY}，合并报表范围包括全部子公司。"
DEFINITION = "环保投入指企业为环境保护发生的资本化与费用化支出，金额单位为万元。环保投入统计范围为合并范围，资本化与费用化互不重叠。"


def doc(document_id="SYN-AR", report_type="AR", metric_period=""):
    return ReportDocument(document_id=document_id, case_id="SYN-PAIR", company_id="SYN", company=ENTITY,
        report_type=report_type, period="2025", metric_period=metric_period,
        source_url="https://example.invalid/synthetic")


def row(index, label, value, unit="万元", year="2025", scope="合并范围", context=None, topic="environment", page=10):
    text = context or f"{BASIS}\n{DEFINITION}\n单位：万元\n2025年 2025年\n{label} | {value} | {unit}"
    return DisclosureOccurrence(occurrence_id=f"SYN-{index}", document_id="SYN-AR", pdf_page=page,
        bbox=[100, 100 + index * 20, 300, 115 + index * 20], label=label,
        value=value, unit=unit, unit_source="本表单位列", currency="CNY", year=year, year_status="attributed" if year else "unattributed",
        scope=scope, column_header="2025 年", row_header=f"{label} | {value} | {unit}", context=text,
        quality="located", quality_reason="年度、单位与行列头均已绑定", topic=topic)


def run_with(rows, documents=None):
    return ConnectivityRun(run_id="SYN-RUN", company=ENTITY, period="2025", report_period="2025",
        documents=documents or [doc()], occurrences=rows, dataset_role="synthetic")


def test_conditions_can_be_upgraded_from_original_structure():
    rows = [row(1, "环保投入费用化", "60"), row(2, "环保投入资本化", "40"), row(3, "环保投入合计", "100")]
    run = run_with(rows)
    check = RelationshipCheck(check_id="SYN-CHECK", rule_id="ENV-001", title="环保投入合计 · 表内合计与分项",
        topic="environment", operator="sum",
        members=[RelationshipMember(occurrence_id="SYN-3", role="total"),
                 RelationshipMember(occurrence_id="SYN-1", role="component"),
                 RelationshipMember(occurrence_id="SYN-2", role="component")],
        conditions=[ComparisonCondition(name=name) for name in ("主体", "期间", "定义", "范围", "单位", "组成完整", "互不重叠")],
        relationship_evidence=[EvidenceRef(occurrence_id="SYN-3", quote="环保投入合计 | 100 | 万元")])
    upgraded, names = upgrade_conditions(check, run, "2025")
    assert set(names) == {"主体", "期间", "定义", "范围", "单位", "组成完整", "互不重叠"}, names
    result = calculate(upgraded, rows)
    assert result.criteria_status == "supported"
    assert result.calculation["residual"] == "0"
    assert result.calculation_status == "consistent"


def test_upgrade_never_downgrades_or_overrides_existing_basis():
    rows = [row(1, "环保投入费用化", "60"), row(2, "环保投入资本化", "40"), row(3, "环保投入合计", "100")]
    check = RelationshipCheck(check_id="SYN-CHECK", rule_id="ENV-001", title="合成", operator="sum",
        members=[RelationshipMember(occurrence_id="SYN-3", role="total"),
                 RelationshipMember(occurrence_id="SYN-1", role="component"),
                 RelationshipMember(occurrence_id="SYN-2", role="component")],
        conditions=[ComparisonCondition(name="主体", status="conflicting", reason="合成冲突"),
                    ComparisonCondition(name="定义", status="unknown")])
    upgraded, names = upgrade_conditions(check, run_with(rows), "2025")
    statuses = {item.name: item.status for item in upgraded.conditions}
    assert statuses["主体"] == "conflicting", "已有冲突不能被自动升级覆盖"
    assert "主体" not in names and "定义" in names


def test_upgrade_requires_verbatim_evidence():
    rows = [row(1, "环保投入费用化", "60", context="只有数字，没有主体、定义、范围说明。"),
            row(2, "环保投入资本化", "40", context="只有数字，没有主体、定义、范围说明。"),
            row(3, "环保投入合计", "100", context="只有数字，没有主体、定义、范围说明。")]
    check = RelationshipCheck(check_id="SYN-CHECK", rule_id="ENV-001", title="合成", operator="sum",
        members=[RelationshipMember(occurrence_id="SYN-3", role="total"),
                 RelationshipMember(occurrence_id="SYN-1", role="component"),
                 RelationshipMember(occurrence_id="SYN-2", role="component")],
        conditions=[ComparisonCondition(name=name) for name in ("主体", "期间", "定义", "范围", "单位")])
    upgraded, names = upgrade_conditions(check, run_with(rows), "2025")
    assert "主体" not in names and "定义" not in names and "范围" not in names
    assert calculate(upgraded, rows).criteria_status == "unknown"


def test_intensity_topic_never_gets_research_rule_card():
    rows = [row(1, "综合能源消耗分项A", "60", topic="intensity"), row(2, "综合能源消耗分项B", "40", topic="intensity"),
            row(3, "综合能源消耗合计", "100", topic="intensity")]
    checks = candidate_checks(rows, "2025")
    composition = [c for c in checks if "合计与分项" in c.title]
    assert composition == [], "强度事项不得被贴成 RD-001 或 ENV-001"


def test_candidate_error_is_recorded_not_fatal():
    rows = [row(1, "环保投入", "60"), row(2, "环保投入", "60"), row(3, "环保投入", "60")]
    # 三处同标签 → OCC-001；把三处成员指向同一物理单元格会触发成员重复检查。
    for item in rows:
        item.bbox = [10, 20, 40, 50]
    rejections = []
    checks = candidate_checks(rows, "2025", run=run_with(rows), rejections=rejections)
    assert isinstance(checks, list)
    assert all(c.check_id for c in checks)


def test_metric_period_uses_unique_known_value():
    from app.connectivity_pipeline import run_pipeline
    from pathlib import Path
    import app.connectivity_pipeline as pipeline

    docs = [doc("SYN-AR"), doc("SYN-ESG", "ESG", metric_period="2024")]
    monkeypatch_registry = [*docs]
    original = pipeline.load_registry
    pipeline.load_registry = lambda root: monkeypatch_registry
    try:
        captured = {}

        def fake_extract(root, document, topics, cancelled=lambda: False):
            from app.connectivity_schemas import SearchCoverage
            return [], SearchCoverage(document_id=document.document_id, total_pages=1, parsed_pages=1), []

        pipeline.extract_document = fake_extract
        run = run_pipeline(Path("."), _request())
        captured["metric"] = run.metric_period
        assert run.metric_period == "2024", "只有第二份登记指标期间时也必须采用该值"
        assert run.period == "2024"
        assert "2024" in run.versions["period_basis"]
    finally:
        pipeline.load_registry = original


def _request():
    from app.connectivity_schemas import RunRequest
    return RunRequest(pair_id="SYN-PAIR", mode="calculation_only")
