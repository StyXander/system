"""审计关注优先级判定（口径 D1）。

本模块只做一件事：把已经由确定性计算与复核角色产出的冻结字段，按队长 2026-09-19
签字的六档排定顺序组合成一个「程序筛查信号分级」。级别代号与判定条件均逐字取自
`2026-09-19_口径签字与开工基线.md` §二 D1，本文件不新增任何阈值。

排定顺序固定为 G → P1 → P2 → P3 → S → P4，G 最先，因为「无法分级」比「暂缓」更根本。
数据缺口在这里只会导致不出级或维持不出级，绝不参与任何升级；升级只能来自
`screening_status`、`screening_strength`、`sustained_periods` 与 `ai_recommendation`
四个已冻结字段的组合。`blocked_candidate_count` 是 §7.7 追加的可选入参，只在 P4 上
起「排除」作用，方向与数据缺口一致：只会取消出级资格，不会抬高级别。

设计约束：
1. 纯函数，无 I/O、无网络、无模型调用、不读运行时全局状态；同输入必得同输出。
2. 只接受已存在的冻结字段，不重新计算增速差，也不重新解释规则状态。
3. 每一个取值都写进 `factors`，每一次命中与否都写进 `reasons`，使级别可逐条复核。
4. 金额重要性与复核处置是并排的独立轴，不折入级别，也不被级别覆盖。
5. 六档不穷尽时返回 `grade=None`，并如实记录未命中原因；不自创第七档。
"""

from __future__ import annotations

from typing import Any

from .schemas import AI_GENERATED_CONTENT_NOTICE

# 已签字的排定顺序；任何实现都必须按此顺序短路求值。
PRIORITY_ORDER: tuple[str, ...] = ("G", "P1", "P2", "P3", "S", "P4")

# 六个级别的中文标签，逐字对应签字口径，不得改写或近义替换。
PRIORITY_LABELS: dict[str, str] = {
    "G": "暂不分级（资料/口径受限）",
    "P1": "立即扩大核查",
    "P2": "优先核查",
    "P3": "常规跟进",
    "S": "暂缓判断",
    "P4": "维持常规程序",
}

# 必须随级别一起显示的边界句，逐字使用签字记录中的原文。
PRIORITY_BOUNDARY = (
    "本级别为审计计划阶段的程序筛查信号分级，不是审计认定，不构成审计结论或审计意见。"
)

# 六档均未命中时的说明文字。它不是第七个级别，只是「本次不出级」的如实登记。
UNGRADED_LABEL = "未分级（已签字排定条件均未命中）"

# G 档的两个触发状态；SOURCE_INCOMPLETE 不在签字口径内，故不并入此处。
DATA_LIMITED_STATUSES = frozenset({"DATA_GAP", "DATA_NOT_COMPARABLE"})

# 「无 blocked 行」在本函数可见输入中的近似代理：被选用规则未落到任一受阻状态。
ROW_BLOCKING_STATUSES = frozenset({"DATA_GAP", "DATA_NOT_COMPARABLE", "SOURCE_INCOMPLETE"})

# 处置建议轴独立于级别轴，标签沿用 W00 契约的中文表述。
DISPOSITION_LABELS: dict[str, str] = {
    "retain": "建议保留",
    "downgrade": "建议降级",
    "defer": "建议暂缓",
    "not_applicable": "本角色不作建议",
    "not_generated": "复核角色尚未给出建议",
}

# 未提供处置建议时的兜底标签，避免把「没有值」写成任何一种处置结论。
DISPOSITION_UNKNOWN_LABEL = "处置建议未提供"


def _as_plain_dict(rule: Any) -> dict[str, Any]:
    """把 RuleResult 模型或普通字典统一成字典视图，便于轨 A 两种方式挂载。"""

    if isinstance(rule, dict):
        return rule
    dumper = getattr(rule, "model_dump", None)
    if callable(dumper):
        # 运行响应里挂的是 Pydantic 模型，model_dump 的 json 模式与封存 JSON 同构。
        return dict(dumper(mode="json"))
    return {}


def _rule_status(rule: dict[str, Any]) -> str:
    """读取规则的冻结状态；缺失按空串处理，不猜测。"""

    return str(rule.get("status") or "")


def _screening_strength(rule: dict[str, Any]) -> str | None:
    """读取 risk_card 里的筛查强度；R2 与缺口卡片本就不产出该字段。"""

    card = rule.get("risk_card")
    if not isinstance(card, dict):
        return None
    value = card.get("screening_strength")
    return str(value) if value is not None else None


def _sustained_periods(rule: dict[str, Any]) -> int | None:
    """读取持续期间数；只接受真实整数，字符串与空值一律按未提供处理。"""

    metrics = rule.get("metrics")
    if not isinstance(metrics, dict):
        return None
    value = metrics.get("sustained_periods")
    # 布尔是 int 的子类，但「True 期」没有业务含义，显式排除以免误判。
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _metric_value(rule: dict[str, Any], key: str) -> Any:
    """读取一个未被本函数用于分级的展示型指标，仅并排透传。"""

    metrics = rule.get("metrics")
    if not isinstance(metrics, dict):
        return None
    return metrics.get(key)


def _first_candidate_rule(rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    """按 rule_id 升序取第一条 candidate 规则，作为强度与持续性字段的来源。"""

    candidates = [rule for rule in rules if _rule_status(rule) == "candidate"]
    if not candidates:
        return None
    # 固定排序，避免依赖上游列表顺序；R1 恒优先于 R2 提供分级字段。
    candidates.sort(key=lambda rule: str(rule.get("rule_id") or ""))
    for rule in candidates:
        if _screening_strength(rule) is not None:
            return rule
    return candidates[0]


def _collect_reason_for_status(rules: list[dict[str, Any]]) -> str | None:
    """取第一条非空的复核理由原文，供处置轴并排显示；不改写、不概括。"""

    for rule in rules:
        draft = rule.get("ai_draft")
        if isinstance(draft, dict):
            text = str(draft.get("reason_for_status") or "").strip()
            if text:
                return text
    return None


def _factor(name: str, value: Any, contribution: str, source: str) -> dict[str, Any]:
    """登记一个判定输入字段：取了什么值、贡献什么、从哪读来。"""

    return {"factor": name, "value": value, "contribution": contribution, "source": source}


def _data_complete(run_completeness: Any) -> bool:
    """数据完整性只认运行完整性前缀，不接受任何推断。"""

    return str(run_completeness or "").startswith("complete_")


def _as_count(value: Any) -> int | None:
    """把外部传入的 blocked 计数归一为非负整数；布尔与不可解析值按未提供处理。"""

    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def compute_planning_priority(
    *,
    rule_results: Any,
    ai_recommendation: Any,
    analysis_conclusion: Any,
    run_completeness: Any,
    screening_status: Any,
    blocked_candidate_count: int | None = None,
) -> dict[str, Any]:
    """按已签字口径 D1 计算审计关注优先级，并返回可逐条复核的结构化结果。

    ``blocked_candidate_count`` 是 §7.7 追加的可选入参：传入 ``context.prescreen_plan``
    的实际计数时，P4 的「无 blocked 行」直接按该计数判定；为 ``None`` 时退回原有的
    规则状态代理判据，并在 ``factors`` 里标成 ``blocked_row_proxy`` 以便区分。
    该入参只影响 P4 一档，其余五档判定不变。

    返回字段：
    - ``grade``：G/P1/P2/P3/S/P4 之一；六档均未命中时为 ``None``，不自创第七档；
    - ``label``：与级别逐字对应的中文标签；
    - ``factors``：每个输入字段「取了什么值、贡献什么、从哪读来」；
    - ``reasons``：按固定顺序逐档记录的命中与未命中理由；
    - ``disposition``：独立的处置建议轴，与级别并排且互不覆盖；
    - ``materiality_assessment`` / ``materiality_multiple``：金额重要性并排透传，不折入级别；
    - ``boundary``：随级别一起显示的边界句。
    """

    rules = [rule for rule in (_as_plain_dict(item) for item in (rule_results or [])) if rule]
    status = str(screening_status or "")
    recommendation = str(ai_recommendation or "")
    rule_statuses = [_rule_status(rule) or "UNKNOWN" for rule in rules]

    # G 档只看被选用规则是否返回资料或口径受限状态，与其余档位互不借用证据。
    limited_rules = [
        {"rule_id": rule.get("rule_id"), "status": _rule_status(rule)}
        for rule in rules
        if _rule_status(rule) in DATA_LIMITED_STATUSES
    ]
    source_rule = _first_candidate_rule(rules)
    strength = _screening_strength(source_rule) if source_rule else None
    sustained = _sustained_periods(source_rule) if source_rule else None
    strength_source = str((source_rule or {}).get("rule_id") or "") or "未选用候选规则"
    # 重要性透传与候选规则不强绑：无候选时回退到首条被选用规则，但必须与 factors 同源。
    materiality_rule = source_rule or (rules[0] if rules else None)
    materiality_source = str((materiality_rule or {}).get("rule_id") or "") or "无被选用规则"

    # 「无 blocked 行」的两条判据路径：显式计数优先，缺计数才退回规则状态代理。
    proxy_blocked = sorted(ROW_BLOCKING_STATUSES.intersection(rule_statuses)) or None
    blocked_count = _as_count(blocked_candidate_count)
    blocked_count_given = blocked_count is not None
    no_blocked_rows = blocked_count == 0 if blocked_count_given else not proxy_blocked

    factors = [
        _factor(
            "screening_status",
            status or None,
            "运行级筛查状态；candidate 才可能进入 P1/P2/P3，RULE_NOT_TRIGGERED 才可能进入 P4",
            "RunResponse.screening_status",
        ),
        _factor(
            "rule_statuses",
            rule_statuses,
            "任一被选用规则返回 DATA_GAP 或 DATA_NOT_COMPARABLE 即触发 G；缺口只导致不出级，不参与升级",
            "RuleResult.status",
        ),
        _factor(
            "screening_strength",
            strength,
            "strong 进入 P1/P2 判定，standard 进入 P3 判定；缺失按未提供处理，不视为任一档命中",
            f"risk_card.screening_strength（来源 {strength_source}；由 main.py 的 >= 阈值产出）",
        ),
        _factor(
            "sustained_periods",
            sustained,
            ">=2 是 P1 的必要条件之一；本函数不重新计算期间数",
            f"metrics.sustained_periods（来源 {strength_source}）",
        ),
        _factor(
            "ai_recommendation",
            recommendation or None,
            "retain 是 P1 的必要条件之一；非 candidate 且 defer 命中 S；本字段同时作为处置轴并排输出",
            "RunResponse.ai_recommendation",
        ),
        _factor(
            "run_completeness",
            run_completeness or None,
            "数据完整（complete_ 前缀）是 P4 的必要条件之一",
            "RunResponse.run_completeness",
        ),
        _factor(
            "blocked_candidate_count" if blocked_count_given else "blocked_row_proxy",
            blocked_count if blocked_count_given else proxy_blocked,
            "P4 要求无 blocked 行：本次按 context.prescreen_plan.blocked_candidate_count 显式计数判定"
            if blocked_count_given
            else "P4 要求无 blocked 行：本次未收到 blocked_candidate_count，"
            "只能以「被选用规则未落到 DATA_GAP/DATA_NOT_COMPARABLE/SOURCE_INCOMPLETE」作代理判据",
            "context.prescreen_plan.blocked_candidate_count"
            if blocked_count_given
            else "RuleResult.status 代理判定",
        ),
        _factor(
            "analysis_conclusion",
            str(analysis_conclusion) if analysis_conclusion is not None else None,
            "已签字六档条件均不含本字段，仅登记为上下文，不参与级别计算",
            "RunResponse.ai_analysis_conclusion",
        ),
        _factor(
            "materiality_assessment",
            _metric_value(materiality_rule, "materiality_assessment") if materiality_rule else None,
            "金额重要性不折入级别，只作为独立字段并排输出",
            f"metrics.materiality_assessment（来源 {materiality_source}）",
        ),
    ]

    reasons: list[str] = []
    grade: str | None = None

    # 以下严格按 G → P1 → P2 → P3 → S → P4 求值，一旦命中立即停止，不回头比较。
    if limited_rules:
        grade = "G"
        reasons.append(
            "G 命中：被选用规则 "
            + "、".join(f"{item['rule_id']}={item['status']}" for item in limited_rules)
            + " 返回资料或口径受限状态，按签字口径优先不出级。"
        )
    elif status == "candidate" and strength == "strong" and sustained is not None and sustained >= 2 and recommendation == "retain":
        grade = "P1"
        reasons.append(
            "P1 命中：screening_status=candidate、screening_strength=strong、"
            f"sustained_periods={sustained}（>=2）、ai_recommendation=retain 四条件同时成立。"
        )
    elif status == "candidate" and strength == "strong":
        grade = "P2"
        reasons.append(
            "P2 命中：candidate 且 strong，但 P1 的必要条件未全部成立"
            + (f"（sustained_periods={sustained}）。" if sustained != 2 else f"（ai_recommendation={recommendation or '未提供'}）。")
        )
    elif status == "candidate" and strength == "standard":
        grade = "P3"
        reasons.append("P3 命中：candidate 且 screening_strength=standard，未达 strong。")
    elif status != "candidate" and recommendation == "defer":
        grade = "S"
        reasons.append(
            f"S 命中：screening_status={status or '未提供'} 不是 candidate，且复核建议为 defer，判为暂缓判断。"
        )
    elif status == "RULE_NOT_TRIGGERED" and _data_complete(run_completeness) and no_blocked_rows:
        grade = "P4"
        reasons.append(
            "P4 命中：规则未触发、run_completeness 表明数据完整，且无 blocked 行"
            + (
                f"（blocked_candidate_count={blocked_count}，按显式计数判定）。"
                if blocked_count_given
                else "（按被选用规则状态代理判据，本次未收到 blocked_candidate_count）。"
            )
        )
    else:
        reasons.append(
            "未命中：G→P1→P2→P3→S→P4 六档的充分条件均不成立，按签字口径不出级（grade=null），"
            "不自创第七档，也不把资料受限之外的状态塞进 G。"
        )

    if grade is None:
        # 逐级补记为什么落空，让评委和轨 A 都能看到是哪一根字段缺失。
        reasons.append(
            f"字段核对：screening_status={status or '未提供'}、screening_strength={strength or '未提供'}、"
            f"sustained_periods={sustained if sustained is not None else '未提供'}、"
            f"ai_recommendation={recommendation or '未提供'}、run_completeness={run_completeness or '未提供'}。"
        )

    if source_rule is None and grade != "G":
        reasons.append("字段核对：本次没有 status=candidate 的规则，强度与持续期间字段按未提供处理。")

    disposition_value = recommendation or None
    return {
        "grade": grade,
        "label": PRIORITY_LABELS[grade] if grade else UNGRADED_LABEL,
        "evaluation_order": list(PRIORITY_ORDER),
        "factors": factors,
        "reasons": reasons,
        "disposition": {
            "ai_recommendation": disposition_value,
            "label": DISPOSITION_LABELS.get(recommendation, DISPOSITION_UNKNOWN_LABEL)
            if disposition_value
            else DISPOSITION_UNKNOWN_LABEL,
            "reason_for_status": _collect_reason_for_status(rules),
        },
        "materiality_assessment": _metric_value(materiality_rule, "materiality_assessment") if materiality_rule else None,
        "materiality_multiple": _metric_value(materiality_rule, "materiality_multiple") if materiality_rule else None,
        "boundary": PRIORITY_BOUNDARY,
        # 统一 AI 声明随片段一起出口，避免脱离 RunResponse 后边界被弱化。
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
    }
