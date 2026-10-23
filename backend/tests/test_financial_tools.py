"""财务穿透工具注册表：白名单、只读、逐字核验。"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.connectivity_extraction import load_registry, source_path
from backend.app.connectivity_tool_registry import TOOL_NAMES, ToolRequest, execute_tool

ROOT = Path(__file__).resolve().parents[2]


class Run:
    def __init__(self, documents, impact):
        self.documents = documents
        self.financial_impact = impact


def _documents():
    docs = [doc for doc in load_registry(ROOT) if doc.company == "五粮液" and doc.period == "2025"]
    if len(docs) != 2 or not all(source_path(ROOT, doc).exists() for doc in docs):
        pytest.skip("五粮液2025双报告未登记")
    return docs


def _run():
    docs = _documents()
    impact = {
        "events": [{"event_id": "EV-1", "project_name": "成品酒包装及智能仓储配送一体化项目",
                    "quote": "配套建设成品酒包装及智能仓储配送一体化项目", "pdf_page": 19,
                    "stage": "executing", "amount_nature": "none"}],
        "items": [{"item_id": "FI-1", "table_title": "在建工程", "row_header": "成品酒包装及智能仓储配送一体化项目（注1）",
                   "column_header": "预算数", "value_semantics": "budget", "raw_value": "8,596,655,000.00",
                   "unit": "元", "pdf_page": 102, "quote": "成品酒包装及智能仓储配送一体化项目（注1）"}],
    }
    return Run(docs, impact)


def test_新工具在白名单内():
    for name in ("search_esg_events", "search_financial_notes", "get_accounting_rules", "verify_evidence"):
        assert name in TOOL_NAMES


def test_事项检索只读本次运行结果():
    receipt = execute_tool(ROOT, _run(), ToolRequest("search_esg_events", {"query": "包装"}))
    assert receipt["status"] == "ok"
    assert receipt["result"]["count"] == 1
    assert receipt["result"]["events"][0]["pdf_page"] == 19
    assert receipt["output_digest"]


def test_附注检索返回列语义():
    receipt = execute_tool(ROOT, _run(), ToolRequest("search_financial_notes", {"query": "包装"}))
    assert receipt["status"] == "ok"
    item = receipt["result"]["items"][0]
    assert item["value_semantics"] == "budget"
    assert item["column_header"] == "预算数"


def test_规则查询只返回待核验规则():
    receipt = execute_tool(ROOT, _run(), ToolRequest("get_accounting_rules", {"activity_type": "facility_retrofit"}))
    assert receipt["status"] == "ok"
    assert receipt["result"]["count"] >= 1
    assert all(rule["verification"] == "pending_human_review" for rule in receipt["result"]["rules"])


def test_引文核验逐字比对():
    docs = _documents()
    esg = next(doc for doc in docs if doc.report_type == "ESG")
    receipt = execute_tool(ROOT, Run(docs, {}), ToolRequest(
        "verify_evidence", {"document_id": esg.document_id, "page": 19,
                            "quote": "配套建设成品酒包装及智能仓储配送一体化项目"}))
    assert receipt["status"] == "ok"
    assert receipt["verified"] is True
    fake = execute_tool(ROOT, Run(docs, {}), ToolRequest(
        "verify_evidence", {"document_id": esg.document_id, "page": 19, "quote": "本项目投入一百亿元"}))
    assert fake["status"] == "ok" and fake["verified"] is False


def test_未登记文档被拒绝():
    receipt = execute_tool(ROOT, _run(), ToolRequest("verify_evidence", {
        "document_id": "NOT-REGISTERED", "page": 1, "quote": "任意文字"}))
    assert receipt["status"] == "rejected"
    assert "未登记" in receipt["reason"] or "不在本次" in receipt["reason"]


def test_未知工具被拒绝():
    receipt = execute_tool(ROOT, _run(), ToolRequest("run_shell", {"command": "dir"}))
    assert receipt["status"] == "rejected"
    assert "白名单" in receipt["reason"]
