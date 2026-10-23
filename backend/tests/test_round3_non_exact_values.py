"""约数、上下界不得被点值算式制造精确差额。"""
import pytest
from app.connectivity_engine import calculate
from test_connectivity_direct_metrics import pair
from app.connectivity_pipeline import candidate_checks

@pytest.mark.parametrize("qualifier", ["approximate", "lower_bound", "upper_bound"])
def test_non_exact_value_never_has_point_difference_even_with_supported_conditions(qualifier):
    run = pair()
    check = candidate_checks(run.occurrences, "2025", run)[0]
    run.occurrences[0].value_qualifier = qualifier
    result = calculate(check, run.occurrences)
    assert result.hypothetical is None
    assert "residual" not in result.calculation
    assert result.calculation_status == "not_executable"
    assert result.criteria_status != "supported"

def test_legacy_bound_label_also_blocks_point_difference():
    run = pair()
    check = candidate_checks(run.occurrences, "2025", run)[0]
    run.occurrences[0].label = "研发人员超过"
    result = calculate(check, run.occurrences)
    assert result.hypothetical is None
    assert "residual" not in result.calculation
