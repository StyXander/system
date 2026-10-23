"""任务9：当期与预期财务影响分析。

三类输出必须分开，不得混为一谈：
1. 企业已量化披露的金额（原文数字，不是模型预测）。
2. 基于现有资料的情景试算（须明示假设，缺参数就不算）。
3. 只有定性影响路径、无法可靠量化的事项。

不预测净利润、未来现金流改善额或投资回报率。
"""
from __future__ import annotations

from .models import (AccountingTreatment, AmountNature, FinancialItem, ImpactRelation,
                     RelationGrade, Stage, SustainabilityEvent)

ANALYSIS_VERSION = "impact_analysis_v1.0"

ACCOUNT_EFFECT = {
    "在建工程": ("资产", "增加", "项目投入先归集，转固后转入固定资产"),
    "固定资产": ("资产", "增加", "达到预定可使用状态后计提折旧"),
    "无形资产": ("资产", "增加", "按成本初始计量并摊销"),
    "开发支出": ("资产", "可能增加", "仅资本化部分，研究阶段不形成资产"),
    "预计负债": ("负债", "增加", "环境修复义务满足确认条件时计提"),
    "管理费用": ("费用", "增加", "日常治理与维护支出"),
    "研发费用": ("费用", "增加", "研究阶段及不满足资本化条件的支出"),
    "营业外支出": ("费用", "可能增加", "修复支出或履约支出"),
    "递延收益": ("负债", "增加", "与资产相关的政府补助分期确认"),
}

TIME_STATES = ("planned", "contracted", "executing", "recognized", "settled")
TRANSITION_REQUIREMENTS = {
    ("planned", "contracted"): "合同或中标通知",
    ("contracted", "executing"): "开工或设备到场记录",
    ("executing", "recognized"): "达到预定可使用状态并转固",
    ("recognized", "settled"): "结算单或现金支付记录",
}
STAGE_TO_STATE = {
    Stage.STRATEGY: "planned", Stage.PLANNED: "planned", Stage.CONTRACTED: "contracted",
    Stage.EXECUTING: "executing", Stage.COMPLETED: "recognized", Stage.SETTLED: "settled",
    Stage.UNKNOWN: "planned",
}


def state_of(event: SustainabilityEvent) -> dict:
    state = STAGE_TO_STATE.get(event.stage, "planned")
    index = TIME_STATES.index(state)
    return {"state": state, "index": index,
            "next_state": TIME_STATES[index + 1] if index + 1 < len(TIME_STATES) else None,
            "next_requirement": TRANSITION_REQUIREMENTS.get((state, TIME_STATES[index + 1])) if index + 1 < len(TIME_STATES) else None}


def current_impact(events: list[SustainabilityEvent], relations: list[ImpactRelation],
                   treatments: dict[str, AccountingTreatment], items: dict[str, FinancialItem]) -> list[dict]:
    """已发生且有证据支持的影响；只收 A/B 级且阶段在实施及以后的事项。"""
    results = []
    event_by_id = {event.event_id: event for event in events}
    for relation in relations:
        if relation.grade not in {RelationGrade.A, RelationGrade.B}:
            continue
        event = event_by_id.get(relation.event_id)
        if event is None or event.stage in {Stage.STRATEGY, Stage.PLANNED, Stage.UNKNOWN}:
            continue
        treatment = treatments.get(relation.treatment_id or "")
        item = items.get(relation.financial_item_id or "")
        accounts = []
        for account in (treatment.accounts if treatment else []):
            effect = ACCOUNT_EFFECT.get(account)
            if effect:
                accounts.append({"account": account, "statement": effect[0], "direction": effect[1], "why": effect[2]})
        results.append({
            "event_id": event.event_id, "project_name": event.project_name or event.quote[:24],
            "grade": relation.grade.value, "accounts": accounts,
            "financial_item": (f"{item.table_title}·{item.row_header}" if item else ""),
            "value": (item.normalized or item.value) if item else "",
            "unit": item.unit if item else "",
            "period": event.period, "basis": (treatment.basis[:1] if treatment else []),
            "state": state_of(event),
            "note": "只说明已找到的会计路径与项目级证据，不表示金额已被逐项勾稽。",
        })
    return results


def expected_impact(events: list[SustainabilityEvent], treatments: list[AccountingTreatment]) -> list[dict]:
    results = []
    treatment_by_event: dict[str, list[AccountingTreatment]] = {}
    for treatment in treatments:
        treatment_by_event.setdefault(treatment.treatment_id.split(":")[0], []).append(treatment)
    for event in events:
        if event.stage in {Stage.EXECUTING, Stage.COMPLETED, Stage.SETTLED}:
            continue
        money = [amount for amount in event.amounts if amount.dimension == "money"]
        if money and event.amount_nature in {AmountNature.BUDGET, AmountNature.PLANNED_INVESTMENT}:
            kind = "disclosed_quantified"
            amount = {"value": money[0].normalized or money[0].value, "unit": money[0].unit,
                      "raw": money[0].raw, "nature": event.amount_nature.value}
            note = "企业自己披露的预算/计划金额，按原文引用，不作为已发生支出"
        elif event.performance:
            kind = "scenario_trial"
            amount = {"value": "", "unit": "", "raw": event.performance[0].raw,
                      "nature": event.performance[0].dimension}
            note = "只有实物绩效，缺少价格与实现比例，不代算金额；需用户输入假设后才生成情景区间"
        else:
            kind = "qualitative_only"
            amount = {"value": "", "unit": "", "raw": "", "nature": ""}
            note = "只有定性影响路径，无可量化依据"
        results.append({
            "event_id": event.event_id, "project_name": event.project_name or event.quote[:24],
            "kind": kind, "amount": amount, "stage": event.stage.value,
            "treatments": [treatment.scene for treatment in treatment_by_event.get(event.event_id, [])],
            "note": note,
        })
    return results


def build(events, relations, treatments, items) -> dict:
    treatment_map = {treatment.treatment_id: treatment for treatment in treatments}
    item_map = {item.item_id: item for item in items}
    current = current_impact(events, relations, treatment_map, item_map)
    expected = expected_impact(events, treatments)
    buckets = {"disclosed_quantified": 0, "scenario_trial": 0, "qualitative_only": 0}
    for item in expected:
        buckets[item["kind"]] = buckets.get(item["kind"], 0) + 1
    return {
        "version": ANALYSIS_VERSION,
        "current": current,
        "expected": expected,
        "buckets": buckets,
        "time_states": [{"event_id": event.event_id, "state": state_of(event)} for event in events],
        "note": ("当期影响只列已找到证据的会计路径；预期影响分三类，企业披露金额、情景试算与定性路径不混用；"
                 "不预测净利润、未来现金流改善额或投资回报率。"),
    }
