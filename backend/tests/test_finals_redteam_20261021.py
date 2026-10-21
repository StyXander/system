"""Finals red-team synthetic tests: no model calls, no real-enterprise claims."""
from decimal import Decimal
import pytest

from backend.app.connectivity_engine import calculate, numeric_unit, validate_refs
from backend.app.connectivity_rules import required_conditions
from backend.app.connectivity_schemas import (
    DisclosureOccurrence, EvidenceRef, ComparisonCondition,
    RelationshipCheck, RelationshipMember,
)


def pair(left="1", right="1", left_unit="吨", right_unit="吨"):
    rows = [
        DisclosureOccurrence(occurrence_id="AR-1", document_id="SYN-AR",
            pdf_page=1, label="温室气体排放", value=left, unit=left_unit, year="2025",
            context=f"合成材料 年度2025 温室气体排放 {left} {left_unit}", currency=""),
        DisclosureOccurrence(occurrence_id="ESG-1", document_id="SYN-ESG",
            pdf_page=2, label="温室气体排放", value=right, unit=right_unit, year="2025",
            context=f"合成材料 年度2025 温室气体排放 {right} {right_unit}", currency=""),
    ]
    refs = [EvidenceRef(occurrence_id="AR-1", quote="合成材料")]
    check = RelationshipCheck(check_id="SYN-FINAL", rule_id="EQ-001", title="合成数值关系",
        operator="equal", relationship_basis="text_statement", relationship_evidence=refs,
        members=[RelationshipMember(occurrence_id="AR-1", role="left"),
                 RelationshipMember(occurrence_id="ESG-1", role="right")],
        conditions=[ComparisonCondition(name=name, status="supported",
            reason="合成样本约定口径一致", evidence=refs)
            for name in required_conditions("equal")])
    return rows, check


@pytest.mark.parametrize("scenario,left,right,lu,ru,expected", [
    ("identical", "5", "5", "吨", "吨", "consistent"),
    ("unexplained_gap", "5", "6", "吨", "吨", "unexplained_difference"),
    ("tonne_to_kg", "1", "1000", "吨", "千克", "consistent"),
    ("kg_to_tonne", "2500", "2.5", "公斤", "吨", "consistent"),
    ("ten_thousand_tonnes", "1", "10000", "万吨", "吨", "consistent"),
    ("co2e_kg", "1000", "1", "千克二氧化碳当量", "吨二氧化碳当量", "consistent"),
    ("co2e_gap", "1000", "2", "千克二氧化碳当量", "吨二氧化碳当量", "unexplained_difference"),
    ("negative_same", "-10", "-10", "吨", "吨", "consistent"),
    ("negative_gap", "-10", "-8", "吨", "吨", "unexplained_difference"),
    ("decimal_equal", "0.001", "0.001", "吨", "吨", "consistent"),
    ("very_large", "1000000000000", "1000000000000", "吨", "吨", "consistent"),
    ("small_delta", "0.00001", "0.00002", "吨", "吨", "unexplained_difference"),
    ("zero_same", "0", "0", "吨", "吨", "consistent"),
    ("zero_gap", "0", "1", "吨", "吨", "unexplained_difference"),
])
def test_final_redteam_numeric_cases(scenario, left, right, lu, ru, expected):
    rows, check = pair(left, right, lu, ru)
    assert calculate(check, rows).calculation_status == expected, scenario


@pytest.mark.parametrize("scenario,change", [
    ("missing_scope", "scope_unknown"),
    ("conflicting_scope", "scope_conflict"),
    ("missing_period", "period_unknown"),
    ("year_mismatch", "year_mismatch"),
    ("currency_conflict", "currency_conflict"),
    ("missing_currency", "currency_missing"),
    ("dimension_mismatch", "dimension_mismatch"),
    ("quote_fabrication", "fake_quote"),
])
def test_final_redteam_blocked_cases(scenario, change):
    rows, check = pair("100", "100")
    if change == "scope_unknown":
        check.conditions[3].status = "unknown"
    elif change == "scope_conflict":
        check.conditions[3].status = "conflicting"
    elif change == "period_unknown":
        check.conditions[1].status = "unknown"
    elif change == "year_mismatch":
        rows[1].year = "2024"
    elif change == "currency_conflict":
        rows[0].unit = rows[1].unit = "元"
        rows[0].currency, rows[1].currency = "CNY", "USD"
    elif change == "currency_missing":
        rows[0].unit = rows[1].unit = "元"
    elif change == "dimension_mismatch":
        rows[1].unit = "立方米"
    elif change == "fake_quote":
        check.conditions[3].evidence = [EvidenceRef(occurrence_id="AR-1", quote="根本不存在的内容")]
    result = calculate(check, rows)
    assert result.calculation_status not in {"consistent", "precision_explained"}, scenario


@pytest.mark.parametrize("quote,ok", [
    ("合成材料", True),
    ("合 成 材 料", True),
    ("不存在的引用", False),
    ("  ", False),
    ("\n\t", False),
])
def test_final_redteam_evidence_integrity(quote, ok):
    rows, _ = pair()
    refs = [EvidenceRef(occurrence_id="AR-1", quote=quote)]
    assert validate_refs(refs, {row.occurrence_id: row for row in rows}) is ok


@pytest.mark.parametrize("unit,expected", [
    ("千克", ("mass", Decimal("0.001"))),
    ("公斤", ("mass", Decimal("0.001"))),
    ("千克二氧化碳当量", ("co2e", Decimal("0.001"))),
    ("吨", ("mass", Decimal("1"))),
])
def test_final_redteam_unit_registry(unit, expected):
    assert numeric_unit(unit) == expected
