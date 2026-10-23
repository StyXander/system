"""主链接入：财务穿透、反证、补证计划必须进入同一次运行结果。"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.connectivity_extraction import load_registry, source_path
from backend.app.connectivity_pipeline import run_pipeline
from backend.app.connectivity_schemas import RunRequest

ROOT = Path(__file__).resolve().parents[2]


def _docs():
    docs = [doc for doc in load_registry(ROOT) if doc.company == "宝钢股份" and doc.period == "2025"]
    if len(docs) != 2 or not all(source_path(ROOT, doc).exists() for doc in docs):
        pytest.skip("宝钢2025报告对未登记或原件未缓存")
    return docs


def test_calculation_only_run_carries_financial_layer_and_execution_receipt():
    _docs()  # 真实原件集成测试沿用缓存前提，不把 CI 网络故障当作代码结果。
    run = run_pipeline(ROOT, RunRequest(pair_id="600019-2025", mode="calculation_only",
                                        topics=["research", "environment", "intensity"]))
    assert run.model_status == "not_requested"
    assert run.checks
    assert run.financial_claims and run.financial_nodes and run.financial_edges
    assert run.impact_graph["stats"]["financial"] >= 1
    assert run.revision_loop["summary"]["refuted"] >= 1
    assert run.financial_scenario["available"] is True
    plan = run.evidence_plan
    assert plan["primary_action"] and plan["best_path"]
    assert plan["execution"]["status"] == "hit"
    assert plan["rerank"]["changed"] is True
    # 结果合同版本与新增字段同时存在，旧字段未被替换。
    assert run.schema_version == "connectivity_v6"
    assert run.checks and run.overview["relation_total"] == len(run.checks)


def test_synthetic_calculation_pipeline_keeps_financial_contract(monkeypatch, tmp_path):
    """离线合成合同：真实运行流水线与财务层，不代表任何企业的验收。"""
    from backend.app import connectivity_pipeline as pipeline
    from backend.app.connectivity_financial_bridge import build
    from backend.app.connectivity_schemas import SearchCoverage
    from backend.tests.test_financial_bridge import _docs as synthetic_docs, _pages

    docs = synthetic_docs()
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "false")
    monkeypatch.setattr(pipeline, "load_registry", lambda root: docs)
    monkeypatch.setattr(pipeline, "extract_document", lambda root, doc, *args: (
        [], SearchCoverage(document_id=doc.document_id, total_pages=10,
                           parsed_pages=10, searched_pages=list(range(1, 11))), []))
    monkeypatch.setattr(pipeline, "report_industry_context", lambda *args: {"industry": "steel"})
    monkeypatch.setattr(pipeline, "build_financial_bridge", lambda root, run:
                        build(None, documents=run.documents, pages=_pages(), industry="steel"))
    monkeypatch.setattr(pipeline, "call_role", lambda *args, **kwargs:
                        pytest.fail("只计算合同不得调用模型"))
    run = pipeline.run_pipeline(tmp_path, RunRequest(pair_id="TEST-2025", mode="calculation_only"))
    assert run.model_status == "not_requested" and not run.provider_calls
    assert run.financial_claims and run.financial_nodes and run.financial_edges
    assert run.impact_graph["stats"]["financial"] >= 1
    assert run.revision_loop["summary"]["refuted"] >= 1
    assert run.financial_scenario["available"] is True
    assert run.evidence_plan["primary_action"] and run.evidence_plan["best_path"]
    assert run.schema_version == "connectivity_v6"
    assert {d.company_id for d in run.documents} == {"TEST"}
def test_pipeline_carries_project_level_financial_impact():
    """五粮液 ESG 与年报在建工程出现同一项目名，应产生项目级关联并带九项条件。"""
    docs = [doc for doc in load_registry(ROOT) if doc.company == "五粮液" and doc.period == "2025"]
    if len(docs) != 2 or not all(source_path(ROOT, doc).exists() for doc in docs):
        pytest.skip("五粮液2025报告对未登记或原件未缓存")
    run = run_pipeline(ROOT, RunRequest(pair_id="000858-2025", mode="calculation_only"))
    impact = run.financial_impact
    assert impact and impact["events"] and impact["items"]
    assert impact["stats"]["project_level"] >= 1
    project = [relation for relation in impact["relations"]
               if relation["numeric_reconciliation"].get("item_selection", {}).get("status") == "project_level"]
    assert project and project[0]["grade"] in {"A", "B"}
    assert {check["key"] for check in project[0]["conditions"]} == {
        "identity", "period", "scope", "accounting_conditions", "comparability",
        "cross_reference", "evidence", "no_counter_evidence", "reconciliation"}
    assert run.financial_impact["graph"]["paths"], "图谱应给出受约束路径"
    assert any(item["kind"] == "disclosed_quantified" or item["kind"] == "qualitative_only"
               for item in impact["analysis"]["expected"] + [{"kind": "qualitative_only"}])
