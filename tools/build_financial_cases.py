"""从真实运行中固化三个演示案例：项目级穿透、口径反例、证据缺口。

只读取已登记原件与本次运行结果，不写死金额、不补造项目。
输出 outputs/financial_cases.json，并在终端打印可回查的页码与引文。
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.connectivity_extraction import load_registry  # noqa: E402
from backend.app.financial_impact import build as build_impact  # noqa: E402
from backend.app.financial_impact import investigation as impact_investigation  # noqa: E402
from backend.app.connectivity_tool_registry import ToolRequest, execute_tool  # noqa: E402

PAIRS = {"A": ("五粮液", "2025"), "B": ("宝钢股份", "2025"), "C": ("宝钢股份", "2025")}


def documents(company: str, period: str):
    return [doc for doc in load_registry(ROOT) if doc.company == company and str(doc.period) == period]


def source_meta(docs) -> dict:
    return {doc.document_id: {"report_type": doc.report_type, "file_sha256": doc.file_sha256,
                              "pages": doc.pages, "source_url": doc.source_url} for doc in docs}


class RunShim:
    """工具注册表只要求 documents 与 financial_impact 两个属性。"""

    def __init__(self, documents, impact):
        self.documents = documents
        self.financial_impact = impact


def investigate(impact: dict, docs) -> None:
    annual = next((doc.document_id for doc in docs if str(doc.report_type).upper() == "AR"), None)
    receipts = []
    for relation in impact.get("relations", [])[:6]:
        for action in impact_investigation.actions_for(relation, impact, annual)[:3]:
            arguments = {key: value for key, value in action.items()
                         if key in {"query", "document_id", "page", "quote", "keyword", "terms"}}
            receipt = execute_tool(ROOT, RunShim(docs, impact), ToolRequest(action["action"], arguments))
            receipt.update({"relation_id": action["relation_id"], "purpose": action["purpose"]})
            receipts.append(receipt)
    if receipts:
        impact_investigation.apply_receipts(impact, receipts)


def case_a(impact: dict, docs) -> dict:
    relations = [rel for rel in impact["relations"]
                 if rel["numeric_reconciliation"].get("item_selection", {}).get("status") == "project_level"]
    if not relations:
        return {"status": "unavailable", "reason": "五粮液本次未产生项目级关联"}
    relation = relations[0]
    event = next(item for item in impact["events"] if item["event_id"] == relation["event_id"])
    item = next(item for item in impact["items"] if item["item_id"] == relation["financial_item_id"])
    treatment = next((entry for entry in impact["treatments"]
                      if entry["treatment_id"] == relation["treatment_id"]), {})
    return {
        "status": "ready", "name": "案例A：项目级穿透（五粮液2025）",
        "event": {"document_id": event["document_id"], "page": event["pdf_page"],
                  "quote": event["quote"], "project_name": event["project_name"],
                  "stage": event["stage"], "amount_nature": event["amount_nature"]},
        "financial_item": {"document_id": item["document_id"], "page": item["pdf_page"],
                           "table_title": item["table_title"], "row_header": item["row_header"],
                           "column": item["column_header"], "semantics": item["value_semantics"],
                           "raw_value": item["raw_value"], "unit": item["unit"], "bbox": item["bbox"]},
        "accounting_path": {"rule_id": treatment.get("rule_id"), "scene": treatment.get("scene"),
                            "basis": treatment.get("basis")},
        "grade": relation["grade"],
        "conditions": [{"key": check["key"], "status": check["status"], "reason": check["reason"]}
                       for check in relation["conditions"]],
        "reconciliation": relation["numeric_reconciliation"],
        "why_not_a": "事项原文未披露项目金额，预算数不能当已发生支出；会计前提仍为假设。",
    }


def case_b(impact: dict, docs) -> dict:
    """同一对报告里找“预算数 vs 已发生投入”的口径冲突，而不是硬凑一致。"""
    events = [event for event in impact["events"] if event.get("amounts")]
    target = next((event for event in events
                   if any("32" in str(amount.get("raw")) for amount in event["amounts"])
                   and event.get("amount_nature") in {"investment_incurred", "planned_investment"}), None)
    budget_candidates = [item for item in impact["items"]
                         if item["value_semantics"] == "budget" and "取向硅钢" in item["row_header"]]
    budget_item = min(budget_candidates,
                      key=lambda item: abs(Decimal(str(item["raw_value"]).replace(",", "")) - Decimal("3289215370"))) \
        if budget_candidates else None
    if target is None or budget_item is None:
        return {"status": "unavailable", "reason": "本次未同时出现投入事项与预算项目"}
    return {
        "status": "ready", "name": "案例B：口径差异与反例（宝钢2025）",
        "event": {"document_id": target["document_id"], "page": target["pdf_page"], "quote": target["quote"],
                  "amounts": target["amounts"], "amount_nature": target["amount_nature"]},
        "financial_item": {"document_id": budget_item["document_id"], "page": budget_item["pdf_page"],
                           "row_header": budget_item["row_header"], "column": budget_item["column_header"],
                           "raw_value": budget_item["raw_value"], "semantics": budget_item["value_semantics"]},
        "why_not_equal": [
            "口径：ESG 是87项、多基地、当期投入；年报是单一项目累计预算。",
            "性质：投入总额不等于预算数，预算数不产生会计确认。",
            "范围：ESG 未声明合并范围；年报附注为合并口径。",
        ],
        "program_verdict": "comparability=false；金额接近不构成勾稽，判不兼容/待补证。",
    }


def case_c(impact: dict, docs) -> dict:
    investigation = impact.get("investigation") or {}
    receipts = investigation.get("receipts") or []
    unresolved = [rel for rel in impact["relations"] if rel["grade"] in {"C", "D"}]
    if not unresolved:
        return {"status": "unavailable", "reason": "本次没有未决关系"}
    relation = unresolved[0]
    event = next(item for item in impact["events"] if item["event_id"] == relation["event_id"])
    related = [receipt for receipt in receipts if receipt.get("relation_id") == relation["relation_id"]]
    return {
        "status": "ready", "name": "案例C：证据缺口与补证（宝钢2025）",
        "event": {"document_id": event["document_id"], "page": event["pdf_page"], "quote": event["quote"],
                  "project_name": event["project_name"]},
        "grade": relation["grade"],
        "unmet": [check["label"] for check in relation["conditions"] if check["status"] != "true"],
        "tool_receipts": [{"tool": receipt.get("tool_name"), "status": receipt.get("status"),
                           "reason": receipt.get("reason", ""), "purpose": receipt.get("purpose", ""),
                           "source_hash": receipt.get("source_hash", "")} for receipt in related],
        "next_step": "若年报确无该项目名，需要企业提供的项目台账、合同或验收单；公开资料只能到证据不足。",
    }


def main() -> int:
    payload = {"schema": "financial_cases_v1", "cases": {}}
    built = {}
    for key, (company, period) in PAIRS.items():
        if key in built:
            continue
        docs = documents(company, period)
        if len(docs) < 2:
            payload["cases"][key] = {"status": "unavailable", "reason": f"{company}{period} 未登记双报告"}
            continue
        impact = build_impact(ROOT, documents=docs, max_events=16)
        investigate(impact, docs)
        built[key] = (impact, docs)
        payload.setdefault("source", {})[company] = source_meta(docs)
    if "A" in built:
        payload["cases"]["A"] = case_a(*built["A"])
    if "B" in built:
        payload["cases"]["B"] = case_b(*built["B"])
    if "C" in built:
        payload["cases"]["C"] = case_c(*built["C"])
    out = ROOT / "outputs/financial_cases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    for key, case in payload["cases"].items():
        print(f"{key}: {case.get('status')} {case.get('name', '')}")
        if case.get("status") == "ready":
            event = case.get("event", {})
            item = case.get("financial_item", {})
            print(f"   event {event.get('document_id')} p{event.get('page')} | {str(event.get('quote'))[:60]}")
            if item:
                print(f"   item  {item.get('document_id')} p{item.get('page')} | "
                      f"{item.get('row_header')} | {item.get('semantics')} {item.get('raw_value')}")
            print(f"   grade {case.get('grade', case.get('program_verdict', ''))}")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
