"""第三轮真实缺陷的最小合成复现；不写入企业案例结果或降低正式结论门槛。"""
from decimal import Decimal

import pytest

from app.connectivity_engine import Interval, _divide_interval, calculate
from app.connectivity_metrics import compact_label, currency_in_text, metric_comparison, metric_identity
from test_connectivity_engine import relationship


@pytest.mark.parametrize("label,dimension,value", [
    ("环保投入（资本性）", "accounting", "capital"),
    ("环保投入（费用性）", "accounting", "expense"),
    ("环保投入（现金）", "payment", "cash"),
    ("环保投入（非现金）", "payment", "noncash"),
    ("环保投入（累计）", "period", "cumulative"),
    ("本期环保投入", "period", "current"),
    ("母公司环保投入", "boundary", "parent"),
    ("环保投入（其中部分）", "extent", "component"),
])
def test_business_qualifiers_survive_brackets(label, dimension, value):
    identity = metric_identity(label)
    assert identity["metric_id"] == "环保投入"
    assert identity["qualifiers"][dimension] == value
    assert identity["source_label"] == label


def test_unit_brackets_are_removed_without_removing_business_qualifiers():
    assert compact_label("研发投入金额（亿元）") == "研发投入金额"
    identity = metric_identity("环保投入（资本性、现金）（万元）")
    assert identity["qualifiers"] == {"accounting": "capital", "payment": "cash"}
    combined = "环保投入（资本性与费用性合计）"
    assert metric_identity(combined)["qualifiers"]["accounting"] == "capital+expense"
    assert metric_comparison(combined, combined)["status"] == "compatible"


@pytest.mark.parametrize("left,right,expected", [
    ("研发投入金额", "研发费用", "conflicting"),
    ("环保投入（现金）", "环保投入", "unknown"),
    ("环保投入（资本性）", "环保投入（费用性）", "conflicting"),
    ("环保投入（累计）", "环保投入（本期）", "conflicting"),
    ("合并环保投入", "母公司环保投入", "conflicting"),
    ("环保投入（其中部分）", "环保投入合计", "conflicting"),
    ("环保投入（资本性、现金）", "环保投入（资本性）", "unknown"),
    ("环保投入（现金）", "环保投入（非现金）", "conflicting"),
    ("研发支出合计（不含资本化部分）", "研发支出合计（含资本化部分）", "conflicting"),
    ("环保投入（不含费用性支出）", "环保投入（含费用性支出）", "conflicting"),
])
def test_same_number_with_different_business_meaning_is_never_formal(left, right, expected):
    assert metric_comparison(left, right)["status"] == expected
    rows, check = relationship("EQ-001", ["100.00", "100.00"], ["left", "right"])
    rows[0].label, rows[1].label = left, right
    result = calculate(check, rows)
    assert result.calculation_status == "not_comparable"
    assert result.conclusion_level != "formal_consistent"
    if expected == "conflicting":
        assert result.conclusion_level != "assumption_compatible"
    assert result.calculation["residual"] is None
    assert Decimal(result.hypothetical["residual"]) == 0
    assert result.criteria_status == ("conflicting" if expected == "conflicting" else "unknown")


def test_compatible_identity_still_allows_a_fully_evidenced_positive_case():
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    rows[0].label, rows[1].label = "环保投入合计", "环保投入"
    assert metric_comparison(rows[0].label, rows[1].label)["status"] == "compatible"
    assert calculate(check, rows).conclusion_level == "formal_consistent"
    check.conditions[2].status = "unknown"
    assert calculate(check, rows).conclusion_level != "formal_consistent"


def test_occurrence_path_cannot_bypass_qualifier_guard():
    rows, check = relationship("OCC-001", ["100", "100"], ["occurrence", "occurrence"])
    rows[0].label, rows[1].label = "环保投入（累计）", "环保投入（本期）"
    assert calculate(check, rows).criteria_status == "conflicting"


def test_excluded_capital_is_not_classified_as_a_capital_only_component():
    identity = metric_identity("研发支出合计（不含资本化部分）")
    qualifiers = identity["qualifiers"]
    assert qualifiers["inclusion_capital"] == "excluded"
    assert "accounting" not in qualifiers
    assert qualifiers["extent"] == "total"
    assert identity["modifier"] != "capitalized"


def ratio_result(values, *, rounding="unknown", units=None):
    rows, check = relationship("INT-001", values, ["numerator", "denominator", "reported_ratio"],
                               units or ["万元", "万元", "%"])
    for row in rows:
        row.rounding_method = rounding
    return rows, check, calculate(check, rows)


def test_rounded_ratio_has_conditional_denominator_explanation_without_formal_upgrade():
    _, _, result = ratio_result(["20.00", "300.00", "6.67"])
    assert result.calculation_status == "unexplained_difference"
    assert result.conclusion_level == "assumption_compatible"
    assert result.basis_level == "L0"
    assert Decimal(result.calculation["residual"]) != 0
    denominator = result.calculation["denominator_check"]
    assert denominator["compatible"] is False
    assert denominator["conditional_compatible"] is True
    assert denominator["precision_basis"] == "display_assumption"
    assert result.calculation["assumption_check"]["status"] == "contains_zero"


def test_explicit_rounding_uses_all_three_member_intervals():
    _, _, result = ratio_result(["20.00", "300.00", "6.67"], rounding="half_up")
    assert result.calculation_status == "precision_explained"
    assert result.conclusion_level == "assumption_compatible"
    assert result.calculation["denominator_check"]["compatible"] is True


def test_real_ratio_gap_is_not_hidden_by_display_precision():
    _, _, result = ratio_result(["20.00", "300.00", "8.00"])
    assert result.conclusion_level == "unexplained_difference"
    assert result.calculation["denominator_check"]["conditional_compatible"] is False
    assert result.calculation["assumption_check"]["status"] == "not_contains_zero"


def test_exact_rounding_is_not_replaced_with_display_assumption():
    _, _, result = ratio_result(["20.00", "300.00", "6.67"], rounding="exact")
    assert result.conclusion_level == "unexplained_difference"
    assert result.calculation["assumption_check"]["status"] == "not_run"
    assert "conditional_compatible" not in result.calculation["denominator_check"]


def test_ratio_unit_conversion_is_deterministic():
    _, _, result = ratio_result(["0.20", "30000.00", "6.67"], units=["亿元", "万元", "%"])
    assert result.conclusion_level == "assumption_compatible"
    assert result.calculation["denominator_check"]["conditional_compatible"] is True


def test_zero_ratio_is_not_inverted_and_zero_denominator_is_not_calculated():
    _, _, result = ratio_result(["0.00", "100.00", "0.00"])
    assert result.calculation["denominator_check"]["implied"] is None
    assert result.calculation["denominator_check"]["conditional_check"]["implied"] is None
    _, _, invalid = ratio_result(["20.00", "0.00", "6.67"])
    assert invalid.calculation_status == "not_executable"
    assert invalid.conclusion_level != "formal_consistent"


def test_interval_division_keeps_attainable_endpoints_and_negative_signs():
    assert _divide_interval(Interval(Decimal("1"), Decimal("2"), True, False),
                            Interval(Decimal("1"), Decimal("1"))) == Interval(Decimal("1"), Decimal("2"), True, False)
    assert _divide_interval(Interval(Decimal("-2"), Decimal("-1"), False, True),
                            Interval(Decimal("1"), Decimal("1"))) == Interval(Decimal("-2"), Decimal("-1"), False, True)


def test_assumed_currency_never_supports_a_formal_amount_comparison():
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    rows[0].currency_status = "assumed"
    result = calculate(check, rows)
    assert result.calculation_status == "not_comparable"
    assert result.conclusion_level != "formal_consistent"


@pytest.mark.parametrize("foreign", ["美元", "港元", "欧元", "日元"])
def test_multiple_currencies_are_not_silently_reduced_to_cny(foreign):
    assert currency_in_text("本报告列示人民币及" + foreign) == ""
    assert currency_in_text("金额单位：元") == ""
    assert currency_in_text("金额单位：人民币万元") == "CNY"


@pytest.mark.parametrize('label', ['耗水强度（以单位营收计算）', '取水强度（以单位营收计算）', '单位营业收入能源强度', '研发投入占营业收入比例'])
def test_denominator_name_never_becomes_metric_identity(label):
    identity = metric_identity(label)
    assert identity['metric_id'] == ''
    assert identity['qualifiers']['quantity_kind'] in {'intensity','ratio'}


@pytest.mark.parametrize('left,right', [('耗水强度（以单位营收计算）','取水强度（以单位营收计算）'), ('总耗水量','总取水量'), ('总取水量','总用水量')])
def test_water_business_definitions_cannot_be_formally_equal(left,right):
    assert metric_comparison(left,right)['status'] == 'conflicting'
    rows,check=relationship('EQ-001',['100','100'],['left','right'])
    rows[0].label,rows[1].label=left,right
    result=calculate(check,rows)
    assert result.criteria_status=='conflicting'
    assert result.calculation.get('residual') is None


@pytest.mark.parametrize('left,right', [('温室气体排放总量（范围一）','温室气体排放总量（范围二）'),('温室气体排放总量（范围一+范围二）','温室气体排放总量（范围一+范围二+范围三）'),('年度总用水量','年度总用水量-地表水')])
def test_scope_and_component_are_not_lost_inside_total_metric(left,right):
    assert metric_comparison(left,right)['status']!='compatible'
    rows,check=relationship('EQ-001',['100','100'],['left','right'])
    rows[0].label,rows[1].label=left,right
    result=calculate(check,rows)
    assert result.conclusion_level!='formal_consistent'
    assert result.calculation.get('residual') is None


def test_same_emission_scope_combination_preserves_compatible_identity():
    assert metric_comparison('温室气体排放总量（范围二+范围一）','温室气体排放总量（范围一+范围二）')['status']=='compatible'


@pytest.mark.parametrize('label,unit',[('研发人员数量','%'),('研发投入金额','人')])
def test_metric_unit_conflict_cannot_be_formally_equal_even_when_values_match(label,unit):
    rows,check=relationship('EQ-001',['100','100'],['left','right'],[unit,unit])
    for row in rows: row.label=label
    result=calculate(check,rows)
    assert result.criteria_status=='conflicting'
    assert result.calculation.get('residual') is None
    assert any('量纲冲突' in reason for reason in result.unresolved)
