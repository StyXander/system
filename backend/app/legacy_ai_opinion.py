"""已弃用的历史固定结论模块，仅供兼容回归与读取旧方案。
新运行只使用ai_opinion中的程序事实和connectivity_intelligence中的真实模型研判。
本文件保全原实现，不得重新接入当前运行管线。
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Iterable

from .connectivity_schemas import RelationshipCheck
from .judgment_layer import (
    DISCLAIMER,
    PREREQUISITE,
    ConditionView,
    Materiality,
    apply_tags,
    build_profile,
    compare,
    disclosure_risk,
    judge,
    offline_reasoner,
    risk_band,
)

OPINION_VERSION = "2026-10-18.1"

#: 不同事项的披露风险敞口。环境与强度指标更容易因边界、分母产生口径差异，
#: 因此敞口高于研发投入；这是可调参数，不是监管阈值。
TOPIC_EXPOSURE = {"research": 55.0, "environment": 70.0, "intensity": 75.0, "version_track": 65.0}
DEFAULT_EXPOSURE = 60.0
DEFAULT_MANAGEABLE = 85.0

#: 风险分地板：前提未知或冲突时，数值再接近也不许判成"可忽略"。
UNSUPPORTED_FLOOR = 35.0
PREREQUISITE_UNKNOWN_FLOOR = 40.0
CONFLICT_FLOOR = 55.0


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


def _is_ratio(check: RelationshipCheck, trial: dict) -> bool:
    """比例关系按百分点尺度取重要性；金额关系按金额尺度。"""
    if check.operator == "ratio":
        return True
    if "无量纲" in str(trial.get("normalized_unit", "")):
        return True
    return any(row.get("dimension") == "ratio" for row in trial.get("inputs", []))


def _conditions(check: RelationshipCheck) -> list[ConditionView]:
    return [ConditionView(name=row.name, status=row.status, reason=row.reason) for row in check.conditions]


def _infer_tags(check: RelationshipCheck) -> list[str]:
    """标签只从已登记的条件状态推导，不靠模型自由发挥。"""
    status = {row.name: row.status for row in check.conditions}
    tags: list[str] = []
    if check.relationship_basis != "text_statement" or not check.relationship_evidence:
        tags.append("RELATION_UNCONFIRMED")
    if status.get("范围") == "conflicting":
        tags.append("SCOPE_DRIFT")
    elif status.get("范围") == "unknown":
        tags.append("BOUNDARY_OPAQUE")
    if status.get("定义") == "unknown":
        tags.append("DEFINITION_OPAQUE")
    if status.get("公式") in {"unknown", "conflicting"}:
        tags.append("DENOMINATOR_SWITCH")
    if status.get("期间") == "conflicting":
        tags.append("PERIOD_MISMATCH")
    if status.get("单位") == "conflicting":
        tags.append("UNIT_JUMP")
    if check.operator == "occurrences" and check.calculation_status == "unexplained_difference":
        tags.append("MULTI_LOCATION_DRIFT")
    return list(dict.fromkeys(tags))


def _missing(check: RelationshipCheck) -> list[str]:
    return [row.name for row in check.conditions if row.status != "supported"] or ["关键前提"]


def _verdict_for(check: RelationshipCheck, managed: float, band_grade: str, tags: list[str]) -> str:
    """先把"能不能下结论"和"差额多大"分开，再决定意见类型。"""
    if check.relationship_basis != "text_statement" or not check.relationship_evidence:
        # 关系本身只是自动配对候选时，先确认“这两处该不该比”，再谈差额大小。
        return "INSUFFICIENT_EVIDENCE"
    if check.criteria_status != "supported":
        # 范围/分母已在原文中明确冲突时，冲突本身可以解释差额；但仍不是同口径一致。
        if ({"SCOPE_DRIFT", "DENOMINATOR_SWITCH"} & set(tags)) and band_grade in {"MINOR", "MATERIAL", "SIGNIFICANT"}:
            return "EXPLAINABLE_DIFFERENCE" if band_grade in {"MATERIAL", "SIGNIFICANT"} else "PROBABLE_EXPLAINABLE"
        # 前提不齐时，数值一致也不能升级成"一致"；冲突或证据太少直接转人工。
        if any(row.status == "conflicting" for row in check.conditions) or managed < 55:
            return "INSUFFICIENT_EVIDENCE"
        return "PROBABLE_EXPLAINABLE"
    if check.calculation_status in {"consistent", "precision_explained"}:
        return "CONSISTENT"
    if check.calculation_status == "adjustment_explained":
        return "EXPLAINABLE_DIFFERENCE"
    if check.calculation_status == "unexplained_difference":
        return "UNEXPLAINED"
    if check.calculation_status == "not_comparable":
        return "INSUFFICIENT_EVIDENCE"
    if band_grade in {"EXACT", "ROUNDING", "TRIVIAL"}:
        return "CONSISTENT"
    if band_grade == "MINOR":
        return "PROBABLE_EXPLAINABLE"
    return "UNEXPLAINED"


def _headline(check: RelationshipCheck, verdict: str, diff: Decimal, band, managed: float) -> str:
    missing = "、".join(_missing(check)[:3])
    if verdict == "INSUFFICIENT_EVIDENCE":
        if diff == 0:
            return f"{check.title}：两处数值相同，但{missing}未获原文支持，暂不能认定同口径一致"
        return f"{check.title}：数值层面相差 {diff}，但{missing}未获原文支持，暂不把差额认定为披露差异"
    if verdict == "CONSISTENT":
        if check.calculation_status == "precision_explained":
            return f"{check.title}：差额 {diff} 可由原文声明的精度区间解释"
        return f"{check.title}：两侧数值在容差内一致（差额 {diff}）"
    if verdict == "EXPLAINABLE_DIFFERENCE":
        return f"{check.title}：差额 {diff}，已有原文依据的口径解释，剩余残差可接受"
    if verdict == "PROBABLE_EXPLAINABLE":
        return f"{check.title}：差额 {diff}，最可能是口径或分母差异，尚缺直接原文"
    return f"{check.title}：差额 {diff}，同口径下仍有未解释差异"


def _rationale(check: RelationshipCheck, band, profile, verdict: str) -> list[str]:
    rows = [band.narrative, f"证据完整度 {profile.managed}/100；未支持前提：{'、'.join(profile.unknown_names[:3]) or '无'}"]
    if verdict == "INSUFFICIENT_EVIDENCE":
        rows.append("按当前规则，前提不齐时不出正式差额；该差额只作假设试算进入风险刻度")
    if check.calculation_status == "adjustment_explained":
        rows.append("调节项均有本次原文出处，且剩余残差区间含 0")
    if check.calculation_status == "unexplained_difference":
        rows.append("已尝试同口径重算，差额仍未被精度或已登记调节吸收")
    return rows


def _actions(check: RelationshipCheck, verdict: str) -> list[str]:
    actions: list[str] = []
    missing = _missing(check)
    if "范围" in missing:
        actions.append("核对合并范围/组织边界在原报告中的表述，必要时索取口径调整表")
    if "定义" in missing:
        actions.append("定位指标定义句，确认分子分母与统计口径")
    if "期间" in missing:
        actions.append("核对指标所属年度与报告期间，排除比较期间混用")
    if "单位" in missing:
        actions.append("核对单位与量纲，确认是否需要统一换算")
    if verdict == "CONSISTENT":
        actions.append("归档本次比对，无需追加程序")
    elif verdict in {"EXPLAINABLE_DIFFERENCE", "PROBABLE_EXPLAINABLE"}:
        actions.append("把口径差异写入核对底稿，不强行调整为同一数")
    else:
        actions.append("向编制人索取差异说明，并检查是否存在版本回撤或旧版数据")
    return list(dict.fromkeys(actions))[:4]


def opinion_for_check(
    check: RelationshipCheck,
    *,
    reasoner=offline_reasoner,
    model: str = "offline-reasoner",
) -> dict | None:
    """单条关系 → 一条 AI 意见；叙述关系与不可执行关系暂不生成。"""
    if check.operator == "narrative" or check.calculation_status in {"not_applicable", "not_executable"}:
        return None
    left, right, trial = _numeric_pair(check)
    if left is None or right is None:
        return None
    conditions = _conditions(check)
    ratio = _is_ratio(check, trial)
    base = Decimal("1") if ratio and max(abs(left), abs(right)) <= 1 else (
        Decimal("100") if ratio else max(abs(left), abs(right), Decimal("1"))
    )
    materiality = Materiality.from_base(base)
    band = compare(left, right, materiality)
    exposure = TOPIC_EXPOSURE.get(check.topic, DEFAULT_EXPOSURE)
    profile = build_profile(conditions, exposure=exposure, manageable=DEFAULT_MANAGEABLE)
    tags = _infer_tags(check)
    verdict = _verdict_for(check, profile.managed, band.grade, tags)

    opinion = judge(
        target=check.title,
        left=left,
        right=right,
        conditions=conditions,
        base_amount=base,
        exposure=exposure,
        manageable=DEFAULT_MANAGEABLE,
        tags=tags,
        reasoner=reasoner,
        model=model,
        is_ratio=ratio,
    )

    # 覆盖成引擎语义：差额、风险分与标签仍由程序决定，模型/推理器只改叙述。
    opinion.verdict = verdict
    opinion.headline = _headline(check, verdict, band.diff, band, profile.managed)
    opinion.rationale = _rationale(check, band, profile, verdict)
    opinion.alternatives = list(opinion.alternatives)[:3]
    opinion.recommended_actions = _actions(check, verdict)
    opinion.source = "direct" if check.criteria_status == "supported" and verdict in {
        "CONSISTENT", "EXPLAINABLE_DIFFERENCE", "UNEXPLAINED"
    } else ("insufficient" if verdict == "INSUFFICIENT_EVIDENCE" else "inference")

    raw_score = disclosure_risk(band, profile, verdict)
    score, tags_hit, floor = apply_tags(raw_score, tags)
    if check.criteria_status != "supported":
        score = max(score, UNSUPPORTED_FLOOR)
    if any(row.name in {"主体", "期间", "范围", "公式"} and row.status == "unknown" for row in check.conditions):
        score = max(score, PREREQUISITE_UNKNOWN_FLOOR)
    if any(row.status == "conflicting" for row in check.conditions):
        score = max(score, CONFLICT_FLOOR)
    score = round(min(100.0, max(score, floor)), 2)
    if check.relationship_basis != "text_statement" or not check.relationship_evidence:
        # 关系未确认时，差额再大也只能说明“可疑”，不能直接推到严重；封顶放在标签地板之后。
        score = round(min(max(score, 38.0), 60.0), 2)
    opinion.score = score
    opinion.band = risk_band(score)
    opinion.tags = tags_hit

    if verdict == "INSUFFICIENT_EVIDENCE":
        opinion.confidence = min(opinion.confidence, 0.50)
    critical_open = any(row.name in PREREQUISITE and row.status != "supported" for row in check.conditions)
    opinion.needs_human = bool(opinion.confidence < 0.60 or critical_open
                               or verdict in {"INSUFFICIENT_EVIDENCE", "UNEXPLAINED"})

    record = {
        "check_id": check.check_id,
        "ai_opinion_version": OPINION_VERSION,
        "generated_by": "offline",
        "numbers": {"left": str(left), "right": str(right), "diff": str(band.diff)},
    }
    record.update(opinion.to_dict())
    return record


def build_opinions(checks: Iterable[RelationshipCheck]) -> list[dict]:
    """一次运行的全部意见；顺序与关系列表一致，便于前端按 check_id 回填。"""
    result = []
    for check in checks:
        record = opinion_for_check(check)
        if record:
            result.append(record)
    return result


def summarize_opinions(opinions: list[dict]) -> dict:
    """给概览区一行摘要，不把五档风险压成一个"准确率"。"""
    bands = {"可忽略": 0, "低": 0, "中": 0, "高": 0, "严重": 0}
    for item in opinions:
        label = (item.get("band") or {}).get("label")
        if label in bands:
            bands[label] += 1
    top = sorted(opinions, key=lambda item: item.get("score", 0), reverse=True)[:3]
    return {
        "total": len(opinions),
        "bands": bands,
        "needs_human": sum(1 for item in opinions if item.get("needs_human")),
        "insufficient": sum(1 for item in opinions if item.get("verdict") == "INSUFFICIENT_EVIDENCE"),
        "top": [{"check_id": item["check_id"], "target": item.get("target"), "score": item.get("score"),
                 "band": (item.get("band") or {}).get("label"), "verdict": item.get("verdict")} for item in top],
        "note": "AI意见由程序刻度与模型/规则推理共同生成，仅供进一步核查参考。",
    }


def model_payload(opinions: list[dict]) -> dict:
    """只把已算好的事实交给模型；不传整份报告，降低越界与注入面。"""
    return {
        "task": "对披露一致性核对结果给出解释性意见，不重新计算、不改写数字。",
        "opinions": [
            {
                "check_id": item["check_id"],
                "target": item.get("target"),
                "verdict": item.get("verdict"),
                "risk_score": item.get("score"),
                "risk_band": (item.get("band") or {}).get("label"),
                "confidence": item.get("confidence"),
                "numbers": item.get("numbers"),
                "conditions": item.get("rationale"),
                "tags": [tag.get("name") for tag in item.get("tags", [])],
            }
            for item in opinions
        ],
    }


def merge_model_items(opinions: list[dict], items: list[dict], model: str) -> list[dict]:
    """模型只改叙述与建议；分数、等级、verdict 与标签保持程序结果。"""
    by_id = {item.get("check_id"): item for item in opinions}
    for item in items:
        record = by_id.get(item.get("check_id"))
        if not record:
            continue
        record["headline"] = str(item.get("headline") or record["headline"])[:180]
        for key in ("rationale", "alternatives", "recommended_actions"):
            values = [str(value)[:160] for value in (item.get(key) or []) if str(value).strip()]
            if values:
                record[key] = values[:4]
        try:
            model_confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            model_confidence = None
        if model_confidence is not None:
            # 模型置信度不能把低于人工复核线的意见抬过线，也不能超过推理上限 0.70。
            record["confidence"] = round(min(0.70, max(record.get("confidence", 0), min(0.70, model_confidence))), 3)
        record["generated_by"] = "llm"
        record["model"] = model
        record["source"] = "inference"
        # 模型可以提高置信度，但不能把原本需要人工的意见直接改成"可归档"。
        record["needs_human"] = bool(record.get("needs_human") or record["confidence"] < 0.60
                                     or record.get("verdict") in {"INSUFFICIENT_EVIDENCE", "UNEXPLAINED"})
    return list(by_id.values())


def program_hint(check: RelationshipCheck, analysis=None) -> dict:
    """显示差异、证据覆盖和核查优先级；不把缺材料折成企业风险或正确概率。"""
    left, right, _ = _numeric_pair(check)
    difference = {"absolute": None, "relative_percent": None, "percentage_points": None,
                  "unit": check.calculation.get("normalized_unit", ""),
                  "conditional": bool(check.hypothetical)}
    if left is not None and right is not None:
        delta = left - right
        scale = max(abs(left), abs(right))
        difference.update(signed=str(delta), absolute=str(abs(delta)),
                          relative_percent=str(abs(delta) / scale * 100) if scale else None)
        if difference["unit"] == "%" or any(i.get("dimension") == "ratio" for i in check.calculation.get("inputs", [])):
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


def dumps(opinions: list[dict]) -> str:
    """调试与留档用；网页与导出使用结构化对象，不解析这段文本。"""
    return json.dumps(opinions, ensure_ascii=False, indent=2)
