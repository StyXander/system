"""第 2 次验收指出问题的回归：跨报告约束、定义句式锚定、比例零值、版本类型隔离。

全部合成输入，不调用外部模型，也不写运行目录。
"""
from decimal import Decimal

import pytest

from app.connectivity_conditions import _definition_quote, upgrade_conditions
from app.connectivity_engine import calculate
from app.connectivity_pipeline import candidate_checks
from app.connectivity_schemas import (ComparisonCondition, ConnectivityRun, DisclosureOccurrence, EvidenceRef,
    RelationshipCheck, RelationshipMember, ReportDocument)
from app.connectivity_versions import build_version_chain

BASE = "某股份有限公司 2024年年度报告。合并报表范围包括全部子公司。"


def document(document_id, report_type, role="original", date="", metric_period=""):
    return ReportDocument(document_id=document_id, case_id="P", company_id="C", company="某股份有限公司",
        report_type=report_type, period="2024", disclosure_date=date, version_role=role,
        metric_period=metric_period, source_url="https://example.invalid/x")


def row(index, document_id, label, value, unit="万元", context=None, topic="research", page=10):
    text = context or f"{BASE}\n单位：万元\n2024年\n{label} | {value} | {unit}"
    return DisclosureOccurrence(occurrence_id=f"{document_id}-{index}", document_id=document_id, pdf_page=page,
        bbox=[10, 10 + index * 40, 200, 25 + index * 40], label=label, value=value, unit=unit, unit_source="本表单位列",
        currency="CNY", year="2024", year_status="attributed", scope="", column_header="2024 年",
        row_header=f"{label} | {value} | {unit}", context=text, quality="located",
        quality_reason="年度、单位与行列头均已绑定", topic=topic)


def run_of(rows, documents):
    return ConnectivityRun(run_id="SYN-RUN", company="某股份有限公司", period="2024", report_period="2024",
        documents=documents, occurrences=rows, dataset_role="synthetic")


def supported(check, names=("主体", "期间", "定义", "范围", "单位")):
    refs = [EvidenceRef(occurrence_id=check.members[0].occurrence_id, quote=BASE)]
    return check.model_copy(update={"conditions": [ComparisonCondition(name=name, status="supported", reason="合成",
                                                                       evidence=refs) for name in names],
                                    "relationship_evidence": refs})


def test_equal_relation_requires_two_reports():
    rows = [row(1, "AR", "研发投入", "100"), row(2, "AR", "研发投入", "100")]
    check = RelationshipCheck(check_id="X", rule_id="EQ-001", title="合成", operator="equal",
        members=[RelationshipMember(occurrence_id=rows[0].occurrence_id, role="left"),
                 RelationshipMember(occurrence_id=rows[1].occurrence_id, role="right")],
        conditions=[ComparisonCondition(name=n) for n in ("主体", "期间", "定义", "范围", "单位")])
    result = calculate(supported(check), rows)
    assert result.cross_document is False
    assert result.criteria_status == "unknown"
    assert any("不同报告" in value for value in result.unresolved)


def test_same_document_duplicates_become_multi_position_not_equal():
    documents = [document("AR", "AR"), document("ESG", "ESG")]
    rows = [row(1, "AR", "年度总用水量", "100"), row(2, "AR", "年度总用水量", "100"),
            row(3, "ESG", "年度总用水量", "100")]
    checks = candidate_checks(rows, "2024", run=run_of(rows, documents))
    equal = [c for c in checks if c.rule_id == "EQ-001"]
    multi = [c for c in checks if c.rule_id == "OCC-001"]
    assert len(equal) == 1, equal
    assert {m.occurrence_id.split("-")[0] for m in equal[0].members} == {"AR", "ESG"}
    assert len({ref.occurrence_id.split("-")[0] for ref in equal[0].relationship_evidence}) == 2
    assert multi, "同一报告内的重复位置仍应保留为多位置核对"
    assert all({m.occurrence_id.split("-")[0] for m in c.members} == {"AR"} for c in multi)
    assert multi[0].cross_document is False


def test_same_document_single_report_never_becomes_equal():
    documents = [document("ESG", "ESG")]
    rows = [row(1, "ESG", "环保投入", "50"), row(2, "ESG", "环保投入", "50")]
    checks = candidate_checks(rows, "2024", run=run_of(rows, documents))
    assert not [c for c in checks if c.rule_id == "EQ-001"]


def test_definition_requires_indicator_anchored_sentence():
    # "价格指数""数据指标"里的"指"不能当作定义。
    assert _definition_quote("国内钢材价格指数 9.23 主要数据指标", "年度总用水量") == ""
    assert _definition_quote("年度总用水量是指企业取用的全部水量。", "年度总用水量").startswith("年度总用水量是指")
    rows = [row(1, "AR", "环保投入", "100", context=f"{BASE}\n环保投入指企业为环境保护发生的资本化与费用化支出。"),
            row(2, "ESG", "环保投入", "100", context=f"{BASE}\n国内钢材价格指数 9.23 主要数据指标。")]
    check = RelationshipCheck(check_id="X", rule_id="EQ-001", title="合成", operator="equal",
        members=[RelationshipMember(occurrence_id=rows[0].occurrence_id, role="left"),
                 RelationshipMember(occurrence_id=rows[1].occurrence_id, role="right")],
        conditions=[ComparisonCondition(name=n) for n in ("主体", "期间", "定义", "范围", "单位")])
    upgraded, names = upgrade_conditions(check, run_of(rows, [document("AR", "AR"), document("ESG", "ESG")]), "2024")
    condition = next(item for item in upgraded.conditions if item.name == "定义")
    if "定义" in names:
        assert condition.evidence and "指" in condition.evidence[0].quote
        assert condition.evidence[0].quote.startswith("环保投入指")


def test_zero_percent_ratio_is_handled_not_crashed():
    rows = [row(1, "AR", "研发投入", "0"), row(2, "AR", "营业收入", "1000", unit="万元"),
            row(3, "AR", "研发投入占营业收入比例", "0", unit="%")]
    checks = candidate_checks(rows, "2024", run=run_of(rows, [document("AR", "AR")]), rejections=[])
    ratio = [c for c in checks if c.rule_id == "INT-001"]
    assert ratio, "0% 比例仍应形成候选，而不是让整次核验失败"
    check = ratio[0].calculation.get("denominator_check") or ratio[0].hypothetical.get("denominator_check") or {}
    assert "implied" in check
    if check.get("implied") is None:
        assert "比例区间跨零" in check.get("note", "")


def test_version_chain_does_not_pair_ar_with_esg():
    chain = build_version_chain([
        {"document": document("AR", "AR", "original", "2024-04-01"), "occurrences": [row(1, "AR", "环保投入", "100")]},
        {"document": document("ESG", "ESG", "correction", "2024-05-01"), "occurrences": [row(2, "ESG", "环保投入", "90")]},
    ])
    assert chain["changes"] == [], "AR 与 ESG 不是彼此的版本"
    roles = {record.report_type: record.version_role for record in chain["records"]}
    assert roles == {"AR": "original", "ESG": "correction"}


def test_version_chain_pairs_same_type_correction():
    chain = build_version_chain([
        {"document": document("AR1", "AR", "original", "2024-04-01"), "occurrences": [row(1, "AR1", "环保投入", "100")]},
        {"document": document("AR2", "AR", "correction", "2024-09-01"), "occurrences": [row(2, "AR2", "环保投入", "90")]},
    ])
    assert len(chain["changes"]) == 1
    assert chain["changes"][0].display_change == "-10"

def test_auto_pair_is_candidate_not_conclusion():
    """自动配对即便成员行都能对上原文，也不构成"关系有原文依据"。"""
    documents = [document("AR", "AR"), document("ESG", "ESG")]
    rows = [row(1, "AR", "环保投入", "100"), row(2, "ESG", "环保投入", "100")]
    checks = candidate_checks(rows, "2024", run=run_of(rows, documents))
    equal = [check for check in checks if check.rule_id == "EQ-001"]
    assert equal, "跨 AR/ESG 同名应召回同值候选"
    check = equal[0]
    assert check.relationship_basis == "auto_label_match"
    result = calculate(supported(check), rows)
    # 五项前提全支持，但关系本身仍是自动配对，因此不得判为已确认。
    assert result.criteria_status == "unknown"
    assert result.cross_document is True
    assert any("对两者关系本身" in value for value in result.unresolved)


def test_multi_location_basis_never_confirmed():
    documents = [document("AR", "AR")]
    rows = [row(1, "AR", "年度总用水量", "100", page=9), row(2, "AR", "年度总用水量", "100", page=12)]
    checks = candidate_checks(rows, "2024", run=run_of(rows, documents))
    multi = [check for check in checks if check.rule_id == "OCC-001"]
    assert multi and multi[0].relationship_basis == "multi_location"
    result = calculate(supported(multi[0]), rows)
    assert result.criteria_status == "unknown"
    assert any("多处同名披露" in value for value in result.unresolved)


def test_relationship_basis_reason_classified_as_c3():
    """关系依据不足必须落在 C3，不能被兜底错记成"前提缺原文"。"""
    from app.connectivity_overview import unresolved_causes
    documents = [document("AR", "AR")]
    rows = [row(1, "AR", "年度总用水量", "100", page=9), row(2, "AR", "年度总用水量", "100", page=12)]
    check = candidate_checks(rows, "2024", run=run_of(rows, documents))[0]
    result = calculate(supported(check), rows)
    run = run_of(rows, documents).model_copy(update={"checks": [result], "overview": {}})
    bucket = {item["code"]: item["count"] for item in unresolved_causes(run)}
    assert bucket["C3"] >= 1


def test_text_statement_relation_keeps_original_behaviour():
    """人工/提案给出的关系有独立引文时，不受自动配对限制。"""
    documents = [document("AR", "AR"), document("ESG", "ESG")]
    rows = [row(1, "AR", "环保投入", "100"), row(2, "ESG", "环保投入", "100")]
    refs = [EvidenceRef(occurrence_id="AR-1", quote=BASE), EvidenceRef(occurrence_id="ESG-2", quote=BASE)]
    check = RelationshipCheck(check_id="T", rule_id="EQ-001", title="合成", operator="equal",
        members=[RelationshipMember(occurrence_id="AR-1", role="left"),
                 RelationshipMember(occurrence_id="ESG-2", role="right")],
        relationship_basis="text_statement", relationship_evidence=refs,
        conditions=[ComparisonCondition(name=n, status="supported", reason="合成", evidence=refs)
                    for n in ("主体", "期间", "定义", "范围", "单位")])
    result = calculate(check, rows)
    assert not any("对两者关系本身" in value for value in result.unresolved)
