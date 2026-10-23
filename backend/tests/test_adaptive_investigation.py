"""受控调查闭环：无模型时也必须留下真实工具回执、门禁与重排记录。"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.connectivity_agent_orchestrator import run_investigation
from backend.app.connectivity_evidence_planner import build_plan
from backend.app.connectivity_extraction import load_registry, source_path
from backend.app.connectivity_financial_bridge import build
from backend.app.connectivity_revision import build_revision_loop

ROOT = Path(__file__).resolve().parents[2]


def _case():
    docs = [doc for doc in load_registry(ROOT) if doc.company == "宝钢股份" and doc.period == "2025"]
    if len(docs) != 2 or not all(source_path(ROOT, doc).exists() for doc in docs):
        pytest.skip("宝钢2025报告对未登记或原件未缓存")
    bridge = build(ROOT, documents=docs, industry="steel")
    revision = build_revision_loop(bridge)
    plan = build_plan(bridge, revision)
    return docs, bridge, revision, plan


def test_investigation_without_model_is_degraded_but_real():
    docs, bridge, revision, plan = _case()

    class Run:
        intelligence_trace = []
        provider_calls = []
        run_id = "TEST-INVESTIGATION"
        documents = docs

    run = Run()
    result = run_investigation(ROOT, run, bridge=bridge, revision=revision, plan=plan,
                               challenger=None, max_rounds=2)
    assert result["outcome"] in {"degraded_no_model", "completed"}
    assert result["events"]
    assert any(event.get("tool_name") for event in result["events"])
    assert result["summary"]
    # 事件中的工具回执必须来自真实登记页，而不是伪造文本。
    receipt_events = [event for event in result["events"] if event.get("tool_name")]
    assert receipt_events
    assert all(event.get("output_digest") for event in receipt_events)
