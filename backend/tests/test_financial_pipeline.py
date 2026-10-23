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
    assert run.schema_version == "connectivity_v5"
    assert run.checks and run.overview["relation_total"] == len(run.checks)
