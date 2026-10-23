"""语义本体：禁止等价、关系模板与裁决三态（forbidden/conditional/allowed）。"""
from __future__ import annotations

from backend.app.connectivity_financial_ontology import (
    candidate_financial_statements, evaluate_mapping, forbidden_equivalences,
    lookup_rule, relation_templates, template_for)


def _claim(**overrides):
    base = {"claim_id": "C1", "text": "报告期内环保投入12亿元", "planned_or_realized": "realized",
            "accounting_nature": "opex", "metric_definition": "环保投入"}
    base.update(overrides)
    return base


def _node(**overrides):
    base = {"node_id": "N1", "label": "管理费用", "value_kind": "实绩",
            "financial_statement_line": "管理费用"}
    base.update(overrides)
    return base


def test_rules_registry_has_seven_forbidden_equivalences_and_templates():
    rules = forbidden_equivalences()
    assert len(rules) >= 7
    assert all(item["reason"] and item["allowed_inference"] for item in rules)
    templates = relation_templates()
    kinds = {item["relation_kind"] for item in templates}
    assert {"DIRECT_RECONCILIATION", "DISCLOSED_ALLOCATION", "TEMPORAL_ASSOCIATION",
            "SEMANTIC_ASSOCIATION", "HYPOTHESIZED_MECHANISM"} <= kinds
    temporal = template_for("TEMPORAL_ASSOCIATION")
    assert temporal["time_lag_policy"]


def test_lookup_rule_by_keyword_and_concept():
    hits = lookup_rule("环保投入")
    assert hits and any(item["kind"] == "forbidden_equivalence" for item in hits)
    assert lookup_rule("") == []
    assert any(item["kind"] == "concept" for item in lookup_rule("节能"))


def test_candidate_financial_statements_scoped_by_industry():
    statements = candidate_financial_statements("节能", "steel")
    assert statements and all(isinstance(item, str) for item in statements)


def test_allowed_verdict_with_full_text_basis():
    result = evaluate_mapping(_claim(), _node(), relation_kind="DIRECT_RECONCILIATION",
                              same_entity=True, same_period=True,
                              definition_compatible=True, boundary_compatible=True)
    assert result["verdict"] == "allowed"
    assert result["suggested_relation_kind"] == "DIRECT_RECONCILIATION"
    assert result["exclusion_factors"] == []
    assert any("同一报告主体" in item for item in result["supporting_factors"])


def test_conditional_verdict_keeps_pending_semantics():
    result = evaluate_mapping(_claim(), _node(financial_statement_line="在建工程"),
                              relation_kind="DIRECT_RECONCILIATION",
                              same_entity=True, same_period=True,
                              definition_compatible=True, boundary_compatible=True)
    assert result["verdict"] == "conditional"
    assert any(item["rule_id"] == "FE-002" for item in result["exclusion_factors"])
    assert "待补证" in result["explanation"]


def test_forbidden_verdict_downgrades_budget_to_temporal():
    result = evaluate_mapping(_claim(planned_or_realized="budget", text="预算32亿元"), _node(),
                              relation_kind="DISCLOSED_ALLOCATION",
                              same_entity=True, same_period=True,
                              definition_compatible=True, boundary_compatible=True)
    assert result["verdict"] == "forbidden"
    assert result["suggested_relation_kind"] == "TEMPORAL_ASSOCIATION"
    assert any(item["rule_id"] == "FE-003" for item in result["exclusion_factors"])
