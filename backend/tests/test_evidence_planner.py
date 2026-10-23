"""补证规划：行动级字段、预算内排序、执行回执触发重排。"""
from __future__ import annotations

from backend.app.connectivity_evidence_planner import actions_for_edge, build_plan, optimize, rerank
from backend.app.connectivity_financial_bridge import build
from backend.app.connectivity_revision import build_revision_loop
from backend.tests.test_financial_bridge import _docs, _pages


def _bridge():
    return build(None, documents=_docs(), pages=_pages(), industry="steel")


def test_actions_have_discrimination_dependency_and_stop_condition():
    bridge = _bridge()
    edge = next(item for item in bridge["edges"] if item["relation_type"] == "CONTRADICTED")
    actions = actions_for_edge(edge, build_revision_loop(bridge))
    assert 5 <= len(actions) <= 8
    assert all(action["action_id"] and action["condition_id"] for action in actions)
    assert all(action["stop_condition"] and action["predicted_outcomes"] for action in actions)
    assert any(action["target_hypotheses"] for action in actions)
    assert any(action["dependency"] for action in actions)


def test_plan_ranks_first_and_second_with_recomputable_scores():
    bridge = _bridge()
    plan = build_plan(bridge, build_revision_loop(bridge))
    assert plan["primary_action"] and plan["alternative_action"]
    assert plan["primary_delta"] >= 0
    assert plan["best_path"] and plan["best_value"] >= 0
    assert set(plan["weights"]) >= {"discrimination", "gap_coverage", "cost", "dependency"}
    assert "不是正确率" in plan["note"]


def test_rerank_drops_reviewed_action_and_changes_first():
    bridge = _bridge()
    plan = build_plan(bridge, build_revision_loop(bridge))
    old_first = plan["primary_action"]["action_id"]
    reranked = rerank(plan, completed_conditions=[], new_evidence_ids=["TERM"],
                      reviewed_actions=[old_first])
    assert reranked["rerank"]["old_first"] == old_first
    assert reranked["rerank"]["changed"] is True
    assert reranked["primary_action"]["action_id"] != old_first


def test_budget_limits_portfolio_cost():
    actions = [{"action_id": "A", "condition_id": "A:1", "condition": "定义", "proposed_source": "X p1",
                "exact_target": "p1", "expected_discrimination": 2, "gap_coverage": 2,
                "estimated_cost_tier": 2, "executable": True, "target_hypotheses": ["H1"]},
               {"action_id": "B", "condition_id": "B:2", "condition": "范围", "proposed_source": "X p2",
                "exact_target": "p2", "expected_discrimination": 2, "gap_coverage": 2,
                "estimated_cost_tier": 2, "executable": True, "target_hypotheses": ["H2"]}]
    plan = optimize(actions, {"call_budget": 2, "max_actions": 2})
    assert len(plan["best_path"]) == 1
