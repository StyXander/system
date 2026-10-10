"""复核自动边界必须能通过自身校验，真实的肯定式趋势矛盾仍拒绝。"""
import pytest

from backend.app.agents import _with_review_boundaries, _validate_deterministic_fact_language
from backend.app.schemas import AgentOutput, RuleResult


def output(text="采用净额口径，仍需补充资料。"):
    return AgentOutput(schema_version="agent_output_v2", run_id="RUN-BOUNDARY", role="review",
                       rule_id="R1", status="defer", ai_recommendation="defer",
                       reason_for_status="资料不足。", draft_title="待核查", draft_observation=text)


def rule():
    return RuleResult(rule_id="R1", status="RULE_NOT_TRIGGERED",
                      source_validation={"status": "passed", "issues": []},
                      metrics={"three_year_trend_available": False},
                      risk_card={"basis_limitation": "应收仅有净额。",
                                 "trend_limitation": "缺少第三个连续年度，未评价三年持续趋势。"})


def test_automatic_boundary_is_valid_and_idempotent():
    original = output()
    normalized = _with_review_boundaries(original, rule())
    assert "趋势不可评价" in normalized.draft_observation
    assert "缺少第三个连续年度" in normalized.draft_observation
    _validate_deterministic_fact_language(normalized, rule())
    assert _with_review_boundaries(normalized, rule()) == normalized
    assert original.draft_observation == "采用净额口径，仍需补充资料。"


def test_explicit_valid_limitation_remains_unchanged():
    original = output("采用净额口径，趋势不可评价。")
    assert _with_review_boundaries(original, rule()) == original
    _validate_deterministic_fact_language(original, rule())


def test_adding_limitation_does_not_hide_positive_trend_contradiction():
    normalized = _with_review_boundaries(output("采用净额口径，周转天数较上年延长。"), rule())
    with pytest.raises(ValueError, match="跨期趋势判断"):
        _validate_deterministic_fact_language(normalized, rule())
