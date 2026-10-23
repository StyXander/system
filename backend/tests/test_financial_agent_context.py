"""P0 架构验收：财务穿透候选必须进入 A1/A2/A3 的实际输入。

用离线替身替换 call_role，不发起任何网络请求；只验证 payload 与运行轨迹。
"""
from __future__ import annotations

from pathlib import Path

import pytest

import backend.app.connectivity_pipeline as pipeline
from backend.app.connectivity_extraction import load_registry, source_path
from backend.app.connectivity_schemas import RunRequest

ROOT = Path(__file__).resolve().parents[2]


def test_three_agents_receive_financial_candidates(monkeypatch):
    docs = [doc for doc in load_registry(ROOT) if doc.company == "五粮液" and doc.period == "2025"]
    if len(docs) != 2 or not all(source_path(ROOT, doc).exists() for doc in docs):
        pytest.skip("五粮液2025双报告未登记")
    # 只为通过配置闸门；call_role 已被替身替换，不会发出请求。
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-offline-double")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "true")
    seen = []

    def offline(role, payload):
        candidates = payload.get("financial_candidates") or []
        seen.append({"role": role, "count": len(candidates),
                     "names": [entry.get("project_name") for entry in candidates]})
        result = {"checks": []} if role in {"A1", "A2"} else {"analyses": [], "findings": []}
        return result, {"role": role, "model": "OFFLINE_TEST_DOUBLE", "status": "completed", "performed": True}

    monkeypatch.setattr(pipeline, "call_role", offline)
    run = pipeline.run_pipeline(ROOT, RunRequest(pair_id="000858-2025", mode="three_agents"))

    assert [entry["role"] for entry in seen[:3]] == ["A1", "A2", "A3"]
    assert all(entry["count"] >= 1 for entry in seen), "三角色都必须收到财务候选"
    assert any("包装" in (name or "") for name in seen[0]["names"]), "A1 应看到项目级候选"
    assert [step.get("status") for step in run.agent_steps[:3]] == ["completed", "completed", "completed"]
    # 穿透层在智能体之前就绪，且调查回执留在同一运行。
    kinds = [entry.get("kind") for entry in run.intelligence_trace]
    assert "financial_impact_ready" in kinds
    receipts = (run.financial_impact.get("investigation") or {}).get("receipts") or []
    assert receipts and any(receipt.get("status") == "ok" for receipt in receipts)
