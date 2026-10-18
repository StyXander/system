"""当前程序事实与核查排序；不生成AI倾向、风险分或自报置信度。
旧固定结论实现移入legacy_ai_opinion，仅保留历史兼容回归。
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from .connectivity_schemas import RelationshipCheck

def _decimal(value) -> Decimal | None:
    """只接受明确十进制数；空值、破折号与模型自由文本一律不回退成 0。"""
    if value in (None, "", "—", "-"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _numeric_pair(check: RelationshipCheck) -> tuple[Decimal | None, Decimal | None, dict]:
    """优先取正式算式，正式门禁拦截时退回假设试算；两者都不伪装成正式差额。"""
    calculation = check.calculation or {}
    if calculation.get("left") is not None and calculation.get("right") is not None:
        return _decimal(calculation.get("left")), _decimal(calculation.get("right")), calculation
    hypothetical = check.hypothetical or {}
    return _decimal(hypothetical.get("left")), _decimal(hypothetical.get("right")), hypothetical


def program_hint(check: RelationshipCheck, analysis=None) -> dict:
    """显示差异、证据覆盖和核查优先级；不把缺材料折成企业风险或正确概率。"""
    left, right, calculation = _numeric_pair(check)
    difference = {"absolute": None, "relative_percent": None, "percentage_points": None,
                  "unit": calculation.get("normalized_unit", ""),
                  "conditional": check.calculation.get("residual") is None and bool(check.hypothetical)}
    if left is not None and right is not None:
        delta = left - right
        scale = abs(left)
        difference.update(signed=str(delta), absolute=str(abs(delta)),
                          relative_percent=str(abs(delta) / scale * 100) if scale else None,
                          relative_basis="left", relative_base=str(left), relative_note="以左侧或报告所列比率为固定基准；基准为零时不计算相对差异")
        if any(i.get("unit") in {"%", "％"} and (check.operator != "ratio" or i.get("role") == "reported_ratio") for i in calculation.get("inputs", [])):
            difference["percentage_points"] = str(delta * 100)
    supported = [c.name for c in check.conditions if c.status == "supported"]
    unknown = [c.name for c in check.conditions if c.status == "unknown"]
    conflicting = [c.name for c in check.conditions if c.status == "conflicting"]
    priority, reason = "low", "当前没有已证实的数值矛盾，保留原文与语义检查"
    if check.calculation_status == "unexplained_difference":
        priority, reason = "high", "当前可比基准下仍有未解释差异"
    elif check.narrative_test and check.narrative_test.get("direction_matches") is False:
        priority, reason = "high", "绑定数值方向与文字主张不同，需要结合主张口径解释"
    elif difference["absolute"] is not None and Decimal(difference["absolute"]) != 0:
        priority, reason = "medium", "条件试算存在差额，优先寻找可比口径与正常解释"
    if check.operator != "narrative" and check.calculation_status == "not_executable":
        priority, reason = "medium", "当前成员或量纲不能执行数值核对，先检查绑定与原文口径"
    program_priority = priority
    source = "program"
    if analysis is not None and analysis.status == "current" and analysis.priority and analysis.priority_reason:
        priority, reason, source = analysis.priority, analysis.priority_reason, "model"
    return {"check_id": check.check_id, "generated_by": "program", "difference": difference,
            "coverage": {"supported": supported, "unknown": unknown, "conflicting": conflicting,
                         "note": "未知仅表示本次证据覆盖缺口，不等于企业未披露或表现较差"},
            "priority": priority, "priority_reason": reason, "priority_source": source,
            "program_priority": program_priority, "calculation_status": check.calculation_status,
            "note": "核查排序提示，不是企业评级、错报概率或审计重要性结论"}


def build_program_hints(run) -> list[dict]:
    """页面、导出和角色排序共享同源程序事实，不增加模型意见数量。"""
    analyses = {a.check_id: a for a in run.ai_analyses}
    return [program_hint(c, analyses.get(c.check_id)) for c in run.checks]
