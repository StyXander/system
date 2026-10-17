"""合成输入验证实际误判边界，不将企业研究数值注入运行规则。"""
from copy import deepcopy
import pytest

from app.connectivity_engine import calculate, Interval, numeric_unit
from app.connectivity_rules import RULES, required_conditions
from app.connectivity_schemas import (DisclosureOccurrence, EvidenceRef, ComparisonCondition, RelationshipCheck, RelationshipMember)
from decimal import Decimal


def relationship(rule, values, roles, units=None):
    operator = RULES[rule]["operator"]
    units = units or ["万元"] * len(values)
    # 同值关系必须来自不同报告：左右成员分别放在 AR 与 ESG 文档。
    documents = ["SYNTHETIC-AR" if role == "left" else "SYNTHETIC-ESG" if role == "right" else "SYNTHETIC"
                 for role in roles]
    rows = [DisclosureOccurrence(occurrence_id=f"SYN-{i}", document_id=documents[i], pdf_page=1,
        label=f"合成成员{i}", value=value, unit=unit, currency="CNY", year="2025",
        context="合成企业2025年，同一统计范围。原文明示完整且互不重叠的组成关系、单位和公式。", row_header="合成企业2025年")
        for i, (value, unit) in enumerate(zip(values, units))]
    refs = [EvidenceRef(occurrence_id=rows[0].occurrence_id, quote="原文明示完整且互不重叠的组成关系、单位和公式")]
    check = RelationshipCheck(check_id="SYN-CHECK", rule_id=rule, title="独立合成关系", operator=operator,
        members=[RelationshipMember(occurrence_id=row.occurrence_id, role=role) for row, role in zip(rows, roles)],
        conditions=[ComparisonCondition(name=name, status="supported", reason="合成条件明确", evidence=refs) for name in required_conditions(operator)],
        relationship_evidence=refs)
    return rows, check


@pytest.mark.parametrize("rule,values,roles,units", [
    ("EQ-001", ["1", "10000"], ["left", "right"], ["亿元", "万元"]),
    ("RD-001", ["100", "80", "20"], ["total", "component", "component"], None),
    ("ENV-001", ["100", "60", "40"], ["total", "component", "component"], None),
    ("INT-001", ["20", "100", "20"], ["numerator", "denominator", "reported_ratio"], ["万元", "万元", "%"]),
    ("OCC-001", ["100", "100", "100"], ["occurrence"]*3, None),
])
def test_supported_relation_match_difference_and_missing_basis(rule, values, roles, units):
    rows, check = relationship(rule, values, roles, units)
    assert calculate(check, rows).calculation_status == "consistent"
    rows[-1].value = str(Decimal(rows[-1].value) + 5)
    difference = calculate(check, rows)
    assert difference.calculation_status == "unexplained_difference"
    check.conditions[3].status = "unknown"
    unresolved = calculate(check, rows)
    assert unresolved.criteria_status == "unknown"
    assert unresolved.calculation_status == "not_comparable"
    # 硬门禁：正式差额与正式残差字段为空，试算进入独立诊断对象。
    assert unresolved.calculation["residual"] is None
    assert unresolved.calculation["residual_interval"] is None
    assert unresolved.calculation["formal_blocked"] is True
    assert unresolved.calculation["gate"]["conclusion"] == "暂不能直接比较"
    assert unresolved.hypothetical["hypothetical"] is True
    assert unresolved.hypothetical["residual"] not in (None, "")


def test_same_number_does_not_prove_comparability():
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    check.conditions[3].status = "unknown"
    result = calculate(check, rows)
    # 数值相同也不能把正式差额写进结果，只能在假设试算中看到0。
    assert result.calculation["residual"] is None
    assert result.hypothetical["residual"] == "0"
    assert result.calculation_status == "not_comparable"


def test_third_difference_survives_two_matching_values():
    rows, check = relationship("OCC-001", ["100", "100", "105"], ["occurrence"]*3)
    result = calculate(check, rows)
    assert result.calculation_status == "unexplained_difference"
    assert [item["residual"] for item in result.calculation["positions"]] == ["0", "-50000"]


def test_missing_scope_third_position_cannot_be_removed_by_engine():
    rows, check = relationship("OCC-001", ["100", "100", "105"], ["occurrence"]*3)
    check.conditions[3].status = "unknown"
    result = calculate(check, rows)
    assert len(result.members) == 3
    assert result.calculation_status == "not_comparable"


def test_forged_quote_is_not_accepted():
    rows, check = relationship("ENV-001", ["100", "60", "40"], ["total", "component", "component"])
    check.conditions[3].evidence = [EvidenceRef(occurrence_id="SYN-0", quote="原文中不存在的范围证明")]
    assert calculate(check, rows).criteria_status == "unknown"


def test_duplicate_member_and_different_currency_are_not_summed():
    rows, check = relationship("ENV-001", ["100", "60", "40"], ["total", "component", "component"])
    check.members[-1].occurrence_id = check.members[1].occurrence_id
    with pytest.raises(ValueError, match="重复"):
        calculate(check, rows)
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    rows[1].currency = "USD"
    result = calculate(check, rows)
    assert result.calculation_status == "not_executable"
    assert any("币种不同" in value for value in result.unresolved)


def test_rounding_must_be_declared_and_boundary_inclusion_matters():
    rows, check = relationship("EQ-001", ["2.00", "2.004"], ["left", "right"])
    assert calculate(check, rows).calculation_status == "unexplained_difference"
    rows[0].rounding = "half_up"
    assert calculate(check, rows).calculation_status == "precision_explained"
    rows[1].value = "2.005"
    assert calculate(check, rows).calculation_status == "unexplained_difference"
    assert not Interval(Decimal("0"), Decimal("1"), True, False).overlaps(Interval(Decimal("1"), Decimal("2")))


def test_zero_denominator_and_unknown_currency_are_not_passes():
    rows, check = relationship("INT-001", ["20", "0", "20"], ["numerator", "denominator", "reported_ratio"], ["万元", "万元", "%"])
    assert calculate(check, rows).calculation_status == "not_executable"
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    rows[1].currency = ""
    assert calculate(check, rows).calculation_status == "not_comparable"


@pytest.mark.parametrize("support,explanation,expected", [
    (True,"合成原文明示组成关系", "supported"),
    (False,"统计口径调整但未说明对象", "unknown"),
    (False,"", "unknown"),
])
def test_narrative_support_is_not_a_numeric_pass(support, explanation, expected):
    rows, check = relationship("NAR-001", [None], ["occurrence"])
    check.explanation = explanation
    if support:
        check.explanation_evidence = [EvidenceRef(occurrence_id="SYN-0", quote="原文明示完整且互不重叠的组成关系")]
    else:
        check.conditions[3].status = "unknown"
    result = calculate(check, rows)
    assert result.criteria_status == expected
    assert result.calculation_status == "not_applicable"


def test_submitted_calculation_is_always_recomputed():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    check.calculation = {"residual": "0"}
    check.calculation_status = "consistent"
    assert calculate(check, rows).calculation["residual"] == "-50000"


def test_unit_prefix_is_not_partially_matched_and_equal_dimensions_reduce():
    assert numeric_unit("百万立方米") == ("volume", Decimal("1000000"))
    assert numeric_unit("万元/亿元") == ("ratio", Decimal("0.0001"))


def test_two_ids_cannot_double_count_one_pdf_cell():
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    # 同一单元格只可能出现在同一份报告内，这里显式放回同一文档再测重复占格。
    rows[1].document_id = rows[0].document_id
    rows[0].bbox = [10, 20, 40, 50]
    rows[1].bbox = [11, 21, 39, 49]
    with pytest.raises(ValueError, match="同一个原文单元格"):
        calculate(check, rows)
