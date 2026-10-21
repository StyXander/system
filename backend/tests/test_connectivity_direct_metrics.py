"""直接披露量回归：同名人数可核对，口径冲突与不同指标仍阻断。"""
from app.connectivity_pipeline import candidate_checks
from app.connectivity_rules import direct_metric
from test_connectivity_conditions_20261017 import doc, row, run_with


def pair(left_label="研发人员数量（人）", right_label="研发人员数量", right_value="2581", unit="人"):
    left = row(1, left_label, "2581", unit=unit, topic="research")
    right = row(2, right_label, right_value, unit=unit, topic="research")
    right.document_id = "SYN-ESG"
    run = run_with([left, right], [doc(), doc("SYN-ESG", "ESG")])
    return run


def test_direct_headcount_comparison_needs_no_dictionary_sentence():
    run = pair()
    check = candidate_checks(run.occurrences, "2025", run)[0]
    assert check.criteria_status == "supported"
    assert check.calculation_status == "consistent"
    assert len(next(c for c in check.conditions if c.name == "定义").evidence) == 2


def test_numeric_difference_is_not_hidden_by_direct_metric_rule():
    run = pair(right_value="2580")
    check = candidate_checks(run.occurrences, "2025", run)[0]
    assert check.calculation_status == "unexplained_difference"


def test_explicit_ratio_label_compares_disclosure_without_claiming_recalculation():
    run = pair("研发投入占营业收入比例", "研发投入占营业收入比例", "2581", unit="%")
    # 比例的指标范围必须有自己的原文，环保投入范围不能移作研发比例依据。
    for occurrence in run.occurrences:
        occurrence.context += "\n研发投入占营业收入比例统计范围为合并范围。"
    check = candidate_checks(run.occurrences, "2025", run)[0]
    assert check.operator == "equal"
    assert check.calculation_status == "consistent"


def test_scope_gap_still_blocks_direct_comparison():
    run = pair()
    run.occurrences[1].scope = "母公司"
    check = candidate_checks(run.occurrences, "2025", run)[0]
    assert check.criteria_status == "unknown"
    assert "范围依据尚未充分说明" in check.unresolved


def test_expenses_and_person_times_are_not_input_or_headcount():
    for label in ("研发费用", "研发人员数量（人次）", "研发人员数量占比", "母公司研发人员数量"):
        assert not direct_metric(label)
    assert direct_metric("研发投入金额（亿元）") == "研发投入金额"


def test_unrelated_environment_scope_cannot_support_research_ratio():
    run = pair("研发投入占营业收入比例", "研发投入占营业收入比例", "2581", unit="%")
    check = candidate_checks(run.occurrences, "2025", run)[0]
    assert check.criteria_status == "unknown"
    assert check.calculation_status == "not_comparable"
