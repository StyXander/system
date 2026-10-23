"""财务穿透的受控调查：把未决条件转成可执行证据动作，并用真实回执更新状态。

边界：
- 动作只来自未满足条件，不按固定权重凑数；每步写明“能区分什么解释”。
- 工具由 connectivity_tool_registry 执行，返回真实页码与命中数；未命中记 no_hit。
- 状态只由程序按 impact_verifier 重新计算，模型与工具回执都不能直接写等级。
"""
from __future__ import annotations

from .models import AmountNature, FinancialItem, RelationGrade
from .textutil import compact

INVESTIGATION_VERSION = "financial_investigation_v1.0"
MAX_ACTIONS = 6


def brief(impact: dict, *, limit: int = 6) -> list[dict]:
    """给模型看的紧凑候选：只给身份、等级、未满足条件与可用动作，不给结论。"""
    events = {event["event_id"]: event for event in impact.get("events", [])}
    items = {item["item_id"]: item for item in impact.get("items", [])}
    treatments = {treatment["treatment_id"]: treatment for treatment in impact.get("treatments", [])}
    order = {"A": 0, "B": 1, "contradicted": 2, "C": 3, "incompatible": 4, "D": 5}
    relations = sorted(impact.get("relations", []), key=lambda rel: order.get(rel.get("grade"), 9))[:limit]
    result = []
    for relation in relations:
        event = events.get(relation.get("event_id"), {})
        item = items.get(relation.get("financial_item_id") or "", {})
        treatment = treatments.get(relation.get("treatment_id") or "", {})
        unmet = [check for check in relation.get("conditions", [])
                 if check.get("status") != "true" and check.get("key") != "no_counter_evidence"]
        result.append({
            "relation_id": relation.get("relation_id"),
            "grade": relation.get("grade"),
            "project_name": event.get("project_name") or "",
            "event_page": event.get("pdf_page"),
            "event_quote": str(event.get("quote") or "")[:100],
            "stage": event.get("stage"), "amount_nature": event.get("amount_nature"),
            "accounting_scene": treatment.get("scene") or "",
            "financial_item": item.get("row_header") or "",
            "column_semantics": item.get("value_semantics") or "",
            "financial_page": item.get("pdf_page"),
            "unmet": [{"key": check.get("key"), "label": check.get("label")} for check in unmet][:5],
            "reconciliation": (relation.get("numeric_reconciliation") or {}).get("status"),
        })
    return result


def actions_for(relation: dict, impact: dict, annual_document_id: str | None = None) -> list[dict]:
    """只针对“缺项目级证据”和“引文未核验”两类可行动缺口生成动作。"""
    events = {event["event_id"]: event for event in impact.get("events", [])}
    items = {item["item_id"]: item for item in impact.get("items", [])}
    event = events.get(relation.get("event_id"), {})
    item = items.get(relation.get("financial_item_id") or "")
    actions = []
    if item is None and event.get("project_name"):
        actions.append({
            "relation_id": relation["relation_id"], "action": "search_financial_notes",
            "query": event["project_name"][:40], "purpose": "确认年报附注是否存在同名项目级明细",
            "discriminates": "项目级归属成立 vs 只有主题词相近",
        })
        if annual_document_id:
            actions.append({
                "relation_id": relation["relation_id"], "action": "search_registered_reports",
                "document_id": annual_document_id, "terms": [event["project_name"][:30]],
                "purpose": "在年报全文中检索该项目名，确认是否真的没有对应披露",
                "discriminates": "确有项目但未解析 vs 年报确实未写该项目名",
            })
    if item is not None and item.get("quote"):
        actions.append({
            "relation_id": relation["relation_id"], "action": "verify_evidence",
            "document_id": item.get("document_id"), "page": item.get("pdf_page"),
            "quote": str(item.get("quote"))[:60], "purpose": "逐字核验附注行是否真实存在于该页",
            "discriminates": "证据有效 vs 引文不可回溯",
        })
    if item is not None and (relation.get("numeric_reconciliation") or {}).get("status") == "not_comparable":
        actions.append({
            "relation_id": relation["relation_id"], "action": "get_accounting_rules",
            "keyword": (item.get("row_header") or "")[:20] or "在建工程",
            "purpose": "确认该金额性质是否需要资本化/费用化前提",
            "discriminates": "金额性质可由规则解释 vs 属于口径冲突",
        })
    return actions


def _item_from_hit(hit: dict, impact: dict) -> FinancialItem | None:
    """把工具命中的附注行还原成项目；语义缺失时不升级。"""
    semantics = hit.get("value_semantics") or "none"
    if semantics == "none":
        return None
    try:
        nature = AmountNature(semantics)
    except ValueError:
        return None
    return FinancialItem(
        item_id=hit.get("item_id") or "FI-TOOL", company=impact.get("company", ""),
        table_title=hit.get("table_title") or "", row_header=hit.get("row_header") or "",
        column_header=hit.get("column_header") or "", value_semantics=nature,
        raw_value=str(hit.get("raw_value") or ""), value=str(hit.get("raw_value") or "").replace(",", ""),
        unit=hit.get("unit") or "", normalized=str(hit.get("raw_value") or "").replace(",", ""),
        period=impact.get("period", ""), document_id=hit.get("document_id") or "",
        pdf_page=int(hit.get("pdf_page") or 0), quote=hit.get("quote") or "", page_verified=True,
    )


def apply_receipts(impact: dict, receipts: list[dict]) -> dict:
    """用真实工具回执重算受影响关系，并保留等级变化历史。"""
    from . import impact_verifier
    events = {event["event_id"]: event for event in impact.get("events", [])}
    items = {item["item_id"]: item for item in impact.get("items", [])}
    treatments = {treatment["treatment_id"]: treatment for treatment in impact.get("treatments", [])}
    by_relation = {relation["relation_id"]: relation for relation in impact.get("relations", [])}
    changes = []
    for receipt in receipts:
        relation = by_relation.get(str(receipt.get("relation_id") or ""))
        if relation is None:
            continue
        event_payload = events.get(relation.get("event_id"))
        if event_payload is None:
            continue
        item_payload = items.get(relation.get("financial_item_id") or "")
        support = [{"filter_ok": True, "quote": entry.get("quote", ""),
                    "pdf_page": entry.get("pdf_page", 0)} for entry in relation.get("supporting", [])]
        if receipt.get("tool_name") == "search_financial_notes" and item_payload is None:
            hits = (receipt.get("result") or {}).get("items") or []
            name = compact(event_payload.get("project_name") or "")
            same_name = [hit for hit in hits if name and name in compact(
                f"{hit.get('table_title', '')}{hit.get('row_header', '')}")]
            if same_name:
                candidate = _item_from_hit(same_name[0], impact)
                if candidate is not None:
                    item_payload = candidate.model_dump(mode="json")
                    impact.setdefault("items", []).append(item_payload)
                    items[candidate.item_id] = item_payload
                    relation["financial_item_id"] = candidate.item_id
                    support.append({"filter_ok": True, "quote": candidate.quote,
                                    "pdf_page": candidate.pdf_page})
        if receipt.get("tool_name") == "verify_evidence" and receipt.get("verified") and item_payload:
            item_payload["page_verified"] = True
        rebuilt = impact_verifier.build_relation(
            _as_event(event_payload), _as_item(item_payload),
            _as_treatment(treatments.get(relation.get("treatment_id") or "")),
            support=support, counter=[entry for entry in relation.get("counter", [])],
            previous=_as_relation(relation))
        rebuilt.numeric_reconciliation.setdefault(
            "item_selection", (relation.get("numeric_reconciliation") or {}).get("item_selection", {}))
        before = relation.get("grade")
        relation.update(rebuilt.model_dump(mode="json"))
        if before != relation.get("grade"):
            changes.append({"relation_id": relation["relation_id"], "from": before, "to": relation["grade"]})
    impact["investigation"] = {
        "version": INVESTIGATION_VERSION, "receipts": receipts, "changes": changes,
        "note": "工具只提供证据与规则；等级由九项条件重新计算，未命中不改状态。",
    }
    return impact


def _as_event(payload: dict):
    from .models import SustainabilityEvent
    return SustainabilityEvent.model_validate(payload)


def _as_item(payload: dict | None):
    if payload is None:
        return None
    return FinancialItem.model_validate(payload)


def _as_treatment(payload: dict | None):
    from .models import AccountingTreatment
    return AccountingTreatment.model_validate(payload) if payload else None


def _as_relation(payload: dict):
    from .models import ImpactRelation
    return ImpactRelation.model_validate(payload)
