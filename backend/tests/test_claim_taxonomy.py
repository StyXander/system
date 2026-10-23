"""主张分类合同：九类主张、计划/实绩对抗样例、会计属性与唯一状态映射。"""
from __future__ import annotations

import pytest

from backend.app.connectivity_claim_taxonomy import (
    CLAIM_KINDS, LINK_STATES, canonical_to_view, classify_claim,
    completion_rate_allowed, map_link_to_overview, observed_from_phase)


def test_nine_kinds_and_five_link_states_are_the_contract():
    assert len(CLAIM_KINDS) == 9
    assert len(LINK_STATES) == 5


def test_target_language_stays_plan_even_with_year_number():
    claim = classify_claim("公司承诺到2030年将吨钢综合能耗降低10%。")
    assert claim["claim_kind"] == "target"
    assert claim["planned_or_realized"] == "plan"
    assert "target" in claim["status_language"]


def test_plan_with_money_is_budget_phase_not_realized():
    claim = classify_claim("公司计划投入12亿元用于污水处理设施建设。",
                           amounts=[{"dimension": "money", "text": "12亿元"}])
    assert claim["claim_kind"] == "plan"
    assert claim["planned_or_realized"] == "plan"


def test_budget_word_upgrades_to_input_with_budget_phase():
    claim = classify_claim("全年环保领域总投入32亿元。",
                           amounts=[{"dimension": "money", "text": "32亿元"}])
    assert claim["claim_kind"] == "input"
    assert claim["planned_or_realized"] == "realized"
    planned = classify_claim("公司拟安排预算12亿元开展污水治理。",
                             amounts=[{"dimension": "money", "text": "12亿元"}])
    assert planned["planned_or_realized"] == "budget"


def test_realized_outcome_keeps_non_monetary_without_amounts():
    claim = classify_claim("报告期内实现节能量25.85万吨标准煤。")
    assert claim["claim_kind"] == "outcome"
    assert claim["planned_or_realized"] == "realized"
    assert claim["accounting_nature"] == "non_monetary"


def test_risk_language_without_performance_is_risk():
    claim = classify_claim("极端天气可能对公司经营带来风险。")
    assert claim["claim_kind"] == "risk"


def test_financial_implication_requires_money():
    without = classify_claim("折旧增加将影响当期费用。")
    assert without["claim_kind"] == "risk"
    with_money = classify_claim("折旧增加将影响当期费用1.2亿元。",
                                amounts=[{"dimension": "money", "text": "1.2亿元"}])
    assert with_money["claim_kind"] == "financial_implication"


def test_accounting_nature_distinguishes_cash_capex_opex():
    cash = classify_claim("购建固定资产、无形资产支付的现金18.5亿元。",
                          amounts=[{"dimension": "money", "text": "18.5亿元"}])
    assert cash["accounting_nature"] == "cash_out"
    capex = classify_claim("在建工程资本化投入3.29亿元。",
                           amounts=[{"dimension": "money", "text": "3.29亿元"}])
    assert capex["accounting_nature"] == "capex"


def test_view_mapping_and_overview_translation_are_unique():
    assert canonical_to_view("outcome") == "performance"
    assert canonical_to_view("policy") == "commitment"
    assert canonical_to_view("unregistered_kind") == "commitment"
    assert map_link_to_overview("supported_link") == "limited_support"
    assert map_link_to_overview("refuted_link") == "challenged"
    with pytest.raises(ValueError):
        map_link_to_overview("made_up_state")
    assert observed_from_phase("budget") == "plan"
    assert observed_from_phase("realized") == "observed"
    assert observed_from_phase("unknown") == "commitment"


def test_completion_gate_requires_every_prerequisite():
    ok, reason = completion_rate_allowed(
        baseline_year="2020", target_year="2030", realized_period="2025",
        subject_scope="集团合并", metric_definition="吨钢综合能耗", formula_compatible=True)
    assert ok is True
    bad, reason = completion_rate_allowed(
        baseline_year="2020", target_year="", realized_period="2025",
        subject_scope="集团合并", metric_definition="吨钢综合能耗", formula_compatible=True)
    assert bad is False and "目标年" in reason
    bad, reason = completion_rate_allowed(
        baseline_year="2020", target_year="2030", realized_period="2025",
        subject_scope="集团合并", metric_definition="吨钢综合能耗", formula_compatible=False)
    assert bad is False and "不可比" in reason
