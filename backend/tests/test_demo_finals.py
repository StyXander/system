"""决赛主案例：真实登记报告上的财务穿透、反证与补证路径。

该测试直接读取 backend/runtime/connectivity/sources 的登记原件；
原件缺失时跳过，不下载替代版本。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.connectivity_evidence_planner import build_plan
from backend.app.connectivity_extraction import load_registry
from backend.app.connectivity_financial_bridge import build
from backend.app.connectivity_graph import build_impact_graph
from backend.app.connectivity_financial_scenario import build_scenario
from backend.app.connectivity_revision import build_revision_loop

ROOT = Path(__file__).resolve().parents[2]


def _baosteel_docs():
    docs = [doc for doc in load_registry(ROOT) if doc.company == "宝钢股份" and doc.period == "2025"]
    if len(docs) != 2:
        pytest.skip("宝钢2025报告对未登记")
    from backend.app.connectivity_extraction import source_path
    if not all(source_path(ROOT, doc).exists() for doc in docs):
        pytest.skip("宝钢2025原件未缓存")
    return docs


@pytest.fixture(scope="module")
def baosteel_pages():
    """同一模块内复用一次全量解析结果；重复解析两份300页原件会放大本机内存压力。"""
    from backend.app.connectivity_financial_bridge import _load_pages
    docs = _baosteel_docs()
    return {doc.document_id: _load_pages(ROOT, doc) for doc in docs}


def test_real_baosteel_chain_has_financial_nodes_pages_and_a_counterexample(baosteel_pages):
    bridge = build(ROOT, documents=_baosteel_docs(), pages=baosteel_pages, industry="steel")
    assert bridge["stats"]["claims"] >= 5
    assert bridge["stats"]["financial_nodes"] >= 5
    assert bridge["stats"]["page_verified_claims"] == bridge["stats"]["claims"]
    assert bridge["stats"]["page_verified_nodes"] == bridge["stats"]["financial_nodes"]
    contradictions = [edge for edge in bridge["edges"] if edge["relation_type"] == "CONTRADICTED"]
    assert contradictions, bridge["stats"]
    # 32亿元ESG合计与32.89亿元单一项目预算：数值接近但口径冲突。
    assert any(edge["claim_page"] in {31, 34} and edge["financial_page"] in {154, 155}
               for edge in contradictions)
    assert all(edge["missing_conditions"] for edge in contradictions)


def test_real_baosteel_revision_and_scenario(baosteel_pages):
    bridge = build(ROOT, documents=_baosteel_docs(), pages=baosteel_pages, industry="steel")
    revision = build_revision_loop(bridge)
    assert revision["summary"]["refuted"] >= 1
    assert any(item["after"] == "refuted" for item in revision["transitions"])
    scenario = build_scenario(bridge)
    assert scenario["available"] is True
    assert scenario["base"]["value"] == "25.85"
    assert scenario["baseline"]["value"] == "2.20"
    graph = build_impact_graph(bridge)
    assert graph["stats"]["challenged"] >= 1
    assert graph["stats"]["financial"] >= 1
    plan = build_plan(bridge, revision)
    assert plan["primary_action"] and plan["best_path"]
    assert "不是正确率" in plan["note"]
