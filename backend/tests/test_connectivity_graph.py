"""唯一图谱后端：三轴边状态、原文溯源与版本失效。

合成样本只验证装配与门禁，不冒充任何企业事实。
"""
from __future__ import annotations

from backend.app.connectivity_financial_bridge import build
from backend.app.connectivity_graph import build_impact_graph, invalidate_graph
from backend.tests.test_financial_bridge import _docs, _pages


def _bridge():
    return build(None, documents=_docs(), pages=_pages(), industry="steel")


def test_graph_has_four_node_layers_and_typed_edges():
    graph = build_impact_graph(_bridge())
    types = {node["type"] for node in graph["nodes"]}
    assert {"claim", "performance", "financial"} <= types
    kinds = {edge["kind"] for edge in graph["edges"]}
    assert "challenged" in kinds
    assert all(node.get("document_id") or node["type"] == "gap" for node in graph["nodes"])
    assert graph["stats"]["claims"] >= 1 and graph["stats"]["financial"] >= 1


def test_edges_carry_three_independent_axes():
    """关系种类、断言来源、证据状态三轴并存；相关不等于已证实。"""
    graph = build_impact_graph(_bridge())
    typed = [edge for edge in graph["edges"] if edge.get("relation_kind")]
    assert typed
    for edge in typed:
        assert edge["assertion_origin"] in {"report", "program", "model", "assumption"}
        assert edge["evidence_status"] in {"supported", "indirect_supported", "refuted",
                                           "pending", "not_comparable"}
    # 语义关联不得被标为已支持。
    for edge in typed:
        if edge["relation_kind"] == "SEMANTIC_ASSOCIATION":
            assert edge["evidence_status"] != "supported"


def test_key_path_is_bounded_for_judges():
    """默认关键路径只保留评委需看的核心节点（≤12），全景点开才展开。"""
    graph = build_impact_graph(_bridge())
    assert 0 < len(graph["key_path"]) <= 12


def test_source_change_invalidates_dependent_edges_not_history():
    graph = build_impact_graph(_bridge())
    target = next(node for node in graph["nodes"] if node["type"] == "claim")
    changed = {target["document_id"]: "f" * 64}
    invalidate_graph(graph, changed)
    assert graph["invalidations"], "来源SHA变化后必须有边失效"
    assert all(edge["invalid_reason"] for edge in graph["edges"] if edge["invalid"])
    # 节点保留，不删除历史。
    assert any(node["id"] == target["id"] for node in graph["nodes"])
