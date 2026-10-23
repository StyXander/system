"""任务11：真实报告验收与对抗场景。

真实报告只读登记原件；对抗场景用受控样本，不把合成样本冒充真实案例。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.connectivity_extraction import load_registry
from backend.app.financial_impact import build
from backend.app.financial_impact.financial_notes import parse_notes
from backend.app.financial_impact.models import Amount, AmountNature, Stage
from backend.app.financial_impact.sustainability_events import apply_model_fields, extract_events
from backend.tests.test_financial_impact import Doc, SUPPORT, event, item, page, treatment

ROOT = Path(__file__).resolve().parents[2]


def _pair(company: str):
    documents = [doc for doc in load_registry(ROOT) if doc.company == company and doc.period == "2025"]
    if len(documents) < 2:
        pytest.skip(f"缺少 {company} 2025 双报告原件")
    return build(ROOT, documents=documents, max_events=16)


@pytest.fixture(scope="module")
def wuliangye():
    return _pair("五粮液")


@pytest.fixture(scope="module")
def baosteel():
    return _pair("宝钢股份")


def test_五粮液存在真实项目级关联(wuliangye):
    assert wuliangye["stats"]["events"] >= 8
    assert wuliangye["stats"]["items"] >= 50
    assert wuliangye["stats"]["project_level"] >= 1
    project = [relation for relation in wuliangye["relations"]
               if relation["numeric_reconciliation"].get("item_selection", {}).get("status") == "project_level"]
    assert project, "应至少有一条项目级关联"
    relation = project[0]
    events = {entry["event_id"]: entry for entry in wuliangye["events"]}
    items = {entry["item_id"]: entry for entry in wuliangye["items"]}
    source = events[relation["event_id"]]
    target = items[relation["financial_item_id"]]
    assert "包装" in source["project_name"]
    assert source["report_type"] == "ESG"
    assert target["document_id"] != source["document_id"]
    assert "在建工程" in target["table_title"] or "包装" in target["row_header"]
    assert relation["grade"] in {"A", "B"}


def test_五粮液项目级关联保留预算与发生额语义(wuliangye):
    project = [relation for relation in wuliangye["relations"]
               if relation["numeric_reconciliation"].get("item_selection", {}).get("status") == "project_level"][0]
    item_value = next(entry for entry in wuliangye["items"] if entry["item_id"] == project["financial_item_id"])
    assert item_value["value_semantics"] in {"budget", "period_increase", "closing_balance", "transfer_out"}
    assert item_value["bbox"], "附注项目必须保留坐标"
    assert item_value["page_verified"] is True


def test_宝钢不得凭空出现A级或项目级关联(baosteel):
    assert baosteel["stats"]["events"] >= 8
    grades = baosteel["stats"]["grades"]
    assert "A" not in grades, "宝钢 ESG 未写年报项目名，不能出现明确关联"
    assert baosteel["stats"]["project_level"] == 0


def test_没有项目名时不借用其他项目(baosteel):
    for relation in baosteel["relations"]:
        selection = relation["numeric_reconciliation"].get("item_selection", {})
        assert selection.get("status") != "project_level"
        if selection.get("status") in {"no_name_match", "same_page_only"}:
            assert relation["financial_item_id"] is None


# ---------- 对抗场景 ----------

def test_金额相同但项目不同():
    relation = __import__("backend.app.financial_impact.impact_verifier", fromlist=["build_relation"]).build_relation(
        event(project_name="污水零排放改造项目"),
        item(table_title="在建工程·污水处理厂", row_header="污水处理厂项目",
             quote="污水处理厂项目 | 100,000,000.00"), treatment(), support=SUPPORT)
    assert relation.grade.value == "incompatible"


def test_ESG未来预算与年报当期发生额不得互相替代():
    planned = event(amount_nature=AmountNature.BUDGET, stage=Stage.PLANNED,
                    amounts=[Amount(raw="5", value="5", unit="亿元", dimension="money",
                                    normalized="500000000", nature=AmountNature.BUDGET)])
    relation = __import__("backend.app.financial_impact.impact_verifier", fromlist=["build_relation"]).build_relation(
        planned, item(value_semantics=AmountNature.PERIOD_INCREASE), treatment(), support=SUPPORT)
    assert relation.grade.value != "A"
    comparability = next(check for check in relation.conditions if check.key == "comparability")
    assert comparability.status == "false"


def test_本期增加不得与期末余额互换():
    relation = __import__("backend.app.financial_impact.impact_verifier", fromlist=["build_relation"]).build_relation(
        event(), item(value_semantics=AmountNature.CLOSING_BALANCE), treatment(), support=SUPPORT)
    assert relation.numeric_reconciliation["status"] == "not_comparable"


def test_研发投入与研发费用不得混同():
    relation = __import__("backend.app.financial_impact.impact_verifier", fromlist=["build_relation"]).build_relation(
        event(amount_nature=AmountNature.INVESTMENT_INCURRED), item(value_semantics=AmountNature.EXPENSE),
        treatment(), support=SUPPORT)
    comparability = next(check for check in relation.conditions if check.key == "comparability")
    assert comparability.status == "false"


def test_附注没有项目级明细时如实降级():
    relation = __import__("backend.app.financial_impact.impact_verifier", fromlist=["build_relation"]).build_relation(
        event(), None, treatment(), support=SUPPORT)
    assert relation.grade.value in {"C", "D"}
    assert relation.financial_item_id is None


def test_支持证据与反向证据并存判为冲突():
    relation = __import__("backend.app.financial_impact.impact_verifier", fromlist=["build_relation"]).build_relation(
        event(), item(), treatment(), support=SUPPORT,
        counter=[{"quote": "羧甲基纤维素改造项目已终止", "pdf_page": 30}])
    assert relation.grade.value == "contradicted"


def test_模型补全的引文不能凭空出现():
    candidates, _ = extract_events([page(10, "本期投入1亿元实施节能改造项目。")], Doc())
    assert candidates

    def runner(_prompt):
        return '[{"event_id": "%s", "project_name": "虚构零碳项目", "subject": "虚构基地"}]' % candidates[0].event_id

    events, receipt = apply_model_fields(candidates, runner, {10: "本期投入1亿元实施节能改造项目。"})
    assert receipt["rejected_count"] >= 1
    assert events[0].project_name == "节能改造项目"


def test_跨页续表继承表头():
    pages = [
        {"page": 154, "text": "单位：元 在建工程",
         "blocks_detail": [{"text": "在建工程", "bbox": [70, 60, 120, 80]}],
         "tables": [{"bbox": [60, 90, 500, 200],
                     "data": [["项目名称", "预算数", "本期增加金额", "期末余额"],
                              ["绿色改造项目", "1,000,000.00", "200,000.00", "800,000.00"]],
                     "cells": [[None] * 4] * 2}]},
        {"page": 155, "text": "单位：元 在建工程",
         "blocks_detail": [{"text": "在建工程", "bbox": [70, 60, 120, 80]}],
         "tables": [{"bbox": [60, 63.9, 500, 160], "data": [["续建项目", "2,000,000.00", "300,000.00", "1,700,000.00"]],
                     "cells": [[[1, 2, 3, 4]] * 4]}]},
    ]
    items, receipt = parse_notes(pages, Doc())
    assert receipt["items"] >= 3
    assert any(entry.row_header == "续建项目" for entry in items)
    continuation = next(entry for entry in items if entry.row_header == "续建项目")
    assert continuation.table_title in {"在建工程", "跨页续表"}


def test_模型未配置时明确标记rule_only():
    events, receipt = extract_events([page(10, "本期投入1亿元实施节能改造项目。")], Doc())
    assert receipt["status"] == "rule_only"
    assert "不伪装" in receipt["note"]
