"""结果概览四问：每个数字都带分母，状态允许重叠，不合成综合分数。

页面、导出与接口读同一份 overview，避免"页面有数字、导出没有"或两边不一致。
同时给出未决原因六类分类，回答"为什么全未决"，不靠读者自己推断。
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal

from .connectivity_rules import BASE_CONDITIONS
from .connectivity_closure import summarize as summarize_closure
from .connectivity_schemas import ConnectivityRun
from .ai_opinion import build_program_hints
from .connectivity_facts import execution_provenance

CONFIRMED_STATUSES = {"consistent", "precision_explained", "adjustment_explained"}

# 未决原因六类：判定只看已记录字段与未决文本，规则固定，可复核。
CAUSES = [
    ("C1", "前提缺原文依据", ("依据尚未充分说明",)),
    ("C2", "前提存在明确冲突", ("存在明确冲突",)),
    ("C3", "关系依据或成员不足", ("缺少有效原文依据", "成员", "只能有一个", "角色不完整",
                                  "对两者关系本身", "多处同名披露")),
    ("C4", "单位、量纲或币种未定", ("单位", "量纲", "币种", "精度", "受控变换")),
    ("C5", "期间或范围不可比", ("不同期间", "期间", "范围")),
    ("C6", "差额未解释或不可执行", ("未解释", "不可执行", "不支持的数值算子", "分母为零")),
]


def _cause_codes(check) -> list[str]:
    text = "；".join(check.unresolved)
    codes = []
    for code, _, keywords in CAUSES:
        if any(keyword in text for keyword in keywords):
            codes.append(code)
    if not codes and check.criteria_status != "supported":
        codes.append("C1")
    return codes


def unresolved_causes(run: ConnectivityRun) -> list[dict]:
    """按六类统计未决原因；同一关系可归入多类，故合计可大于关系数。"""
    buckets = {code: {"code": code, "name": name, "count": 0, "examples": []} for code, name, _ in CAUSES}
    for check in run.checks:
        for code in _cause_codes(check):
            bucket = buckets[code]
            bucket["count"] += 1
            if len(bucket["examples"]) < 3:
                bucket["examples"].append({"check_id": check.check_id, "title": check.title,
                                           "reason": (check.unresolved or ["关键前提未获支持"])[0]})
    return list(buckets.values())


def program_level(check) -> str:
    """与浏览器同样读取显式结论；有限支持与假设试算不升级正式结论。"""
    calc = check.calculation
    if check.criteria_status == "conflicting":
        return "conflict"
    declared = check.conclusion_level if check.conclusion_level != "not_assessed" else calc.get("conclusion_level")
    declared_map = {"formal_consistent": "formal", "unexplained_difference": "conflict",
                    "assumption_compatible": "conditional", "limited_support": "limited",
                    "insufficient_basis": "insufficient"}
    if declared == "formal_consistent" and (check.criteria_status != "supported" or calc.get("gate")):
        return "insufficient"
    if declared in declared_map:
        return declared_map[declared]
    if check.operator == "narrative" or check.calculation_status == "not_applicable":
        return "not_applicable"
    if check.criteria_status == "conflicting" or check.calculation_status == "unexplained_difference":
        return "conflict"
    assumption = calc.get("assumption_check") or {}
    if (assumption.get("status") and assumption["status"] != "not_run" and assumption.get("contains_zero")) or (not calc.get("gate") and (calc.get("scenario_adjustment") or {}).get("applied")):
        return "conditional"
    if check.criteria_status == "supported" and not calc.get("gate"):
        if check.calculation_status in CONFIRMED_STATUSES:
            return "formal"
        if check.calculation_status in {"not_comparable", "not_executable"}:
            return "limited"
    if calc.get("gate") or check.criteria_status == "unknown":
        return "insufficient"
    return "insufficient"


def build_overview(run: ConnectivityRun) -> dict:
    """由同一次运行的关系、覆盖与未计入清单确定性推导，不调用模型。"""
    checks = run.checks
    total = len(checks)
    levels = {c.check_id: program_level(c) for c in checks}
    confirmed = [c for c in checks if levels[c.check_id] == "formal"]
    blocked = [c for c in checks if c.criteria_status in {"unknown", "conflicting"}]
    conflicting = [c for c in blocked if c.criteria_status == "conflicting"]
    unexplained = [c for c in checks if levels[c.check_id] == "conflict" and c.criteria_status == "supported"]
    # 门禁拦住的关系无法判断差额是否未解释，单独列示，避免"0 项未解释"被读成没有未解释问题。
    undecidable = [c for c in checks if c.calculation_status == "not_comparable"]
    missing = Counter()
    conflicting_names = Counter()
    without_evidence = Counter()
    for check in blocked:
        for condition in check.conditions:
            if condition.status == "supported":
                continue
            missing[condition.name] += 1
            if condition.status == "conflicting":
                conflicting_names[condition.name] += 1
            if not condition.evidence:
                without_evidence[condition.name] += 1
        for name in BASE_CONDITIONS:
            if not any(condition.name == name for condition in check.conditions):
                missing[name] += 1
                without_evidence[name] += 1
    searched = sum(len(c.searched_pages) for c in run.coverage)
    total_pages = sum(c.total_pages for c in run.coverage)
    failed_pages = sum(len(c.failed_pages) for c in run.coverage)
    excluded = len(run.extraction_exclusions)
    extracted = len(run.occurrences)
    hints = run.program_hints or build_program_hints(run)
    priority = sorted([h for h in hints if h['priority'] != 'low'], key=lambda h: h['priority'] != 'high')
    formal = [c.check_id for c in checks if c.calculation.get('residual') is not None
              and levels[c.check_id] != 'conditional']
    arithmetic_trials = [c.check_id for c in checks if c.check_id not in formal and c.hypothetical and c.hypothetical.get('residual') is not None]
    trials = [c.check_id for c in checks if levels[c.check_id] == 'conditional']
    actionable = [h for h in hints if h.get('program_priority', h['priority']) != 'low'
                  or (h.get('difference', {}).get('absolute') is not None and Decimal(h['difference']['absolute']) != 0)]
    opinions = [a for a in run.ai_analyses if a.status == "current"]
    # 新计数明确区分披露位置和页；保留旧 not_found.value 供旧客户端过渡。
    counts = {"unattributed_occurrences": {"value": excluded, "unit": "处", "denominator": extracted},
              "failed_pages": {"value": failed_pages, "unit": "页", "denominator": total_pages}}
    # 旧五类字段仅是六级状态的投影，不能再独立用 hypothetical 或 L1 推断。
    aliases = {"formal": "confirmable", "limited": "limited_support", "conditional": "conditional_trial",
               "insufficient": "not_comparable", "conflict": "pending", "not_applicable": "pending"}
    bands = {key: [] for key in dict.fromkeys(aliases.values())}
    for check in checks:
        bands[aliases[levels[check.check_id]]].append(check.check_id)
    return {
        "delivery_contract_version": "2026-10-20.round3.1",
        "program_levels": {key: {"value": sum(levels[c.check_id] == key for c in checks),
                          "items": [c.check_id for c in checks if levels[c.check_id] == key], "denominator": total}
                           for key in ["formal", "conditional", "limited", "insufficient", "conflict", "not_applicable"]},
        "summary_bands_note": "由 program_levels 派生的历史五类投影；pending 合并明确冲突与非数值关系，准确分类以六级状态为准",
        "execution_provenance": execution_provenance(run),
        "coverage_counts": counts,
        "summary_bands": {key: {"value": len(ids), "items": ids, "denominator": total} for key, ids in bands.items()},
        "counting_version": "2026-10-18.2",
        "relation_total": total,
        "formal_calculations": {"value": len(formal), "items": formal},
        "program_calculations": {"value": len(formal), "items": formal, "label": "正式复算（历史字段别名）"},
        "numerical_records": {"value": len(formal)+len(arithmetic_trials), "items": formal+arithmetic_trials},
        "arithmetic_references": {"value": len(arithmetic_trials), "items": arithmetic_trials, "label": "受门禁限制的算术参考，不表示假设已支持"},
        "program_records": {"value": len(hints), "label": "程序事实记录，包含无差异记录"},
        "program_hints": {"value": len(actionable), "items": [h['check_id'] for h in actionable], "label": "程序差异或限制提示"},
        "priority_checks": {"value": len(priority), "items": [h['check_id'] for h in priority],
                            "details": priority, "label": "优先核查的关系，含模型排序建议"},
        "model_opinions": {"value": sum(a.status == 'current' for a in run.ai_analyses),
                           "items": [a.check_id for a in run.ai_analyses if a.status == 'current'],
                           "new": sum(a.status == 'current' and not a.inherited_from_run_id for a in run.ai_analyses),
                           "reused": sum(a.status == 'current' and bool(a.inherited_from_run_id) for a in run.ai_analyses)},
        "ai_analysis": {"value": len(opinions), "denominator": total,
                        "items": [a.check_id for a in opinions],
                        "by_verdict": dict(Counter(a.verdict for a in opinions)),
                        "stale": sum(a.status != "current" for a in run.ai_analyses)},
        "trial_calculations": {"value": len(trials), "items": trials, "label": "仅条件试算，不计入正式复算"},
        "scenario_bridges": {"value": sum(bool(c.scenario_adjustment and c.scenario_adjustment.get("applied")) for c in checks),
                             "items": [c.check_id for c in checks if c.scenario_adjustment and c.scenario_adjustment.get("applied")]},
        "confirmable": {"value": len(confirmed), "denominator": total,
                        "label": "条件支持且计算成立的关系", "items": [c.check_id for c in confirmed]},
        "unconfirmable": {"value": len(blocked), "denominator": total, "conflicting": len(conflicting),
                         "label": "缺前提或存在冲突的关系", "items": [c.check_id for c in blocked],
                         "missing_conditions": [{"name": name, "count": count} for name, count in missing.most_common()],
                         "missing_breakdown": [{"name": name, "unsupported": count,
                                                "conflicting": conflicting_names.get(name, 0),
                                                "without_evidence": without_evidence.get(name, 0)}
                                               for name, count in missing.most_common()]},
        "unexplained": {"value": len(unexplained), "denominator": total, "label": "仍有未解释残差的关系",
                        "items": [c.check_id for c in unexplained],
                        "undecidable": {"value": len(undecidable), "denominator": total,
                                        "label": "因前提未支持而无法判断差额的关系",
                                        "items": [c.check_id for c in undecidable]}},
        # 两件事分开计数，不合成"行数/页数"这种比值：
        # ① 已提取但未计入的位置（分母＝已提取位置数）；② 解析失败的页（分母＝总页数）。
        "not_found": {"deprecated_mixed_value": True, "replacement": "coverage_counts", "value": excluded + failed_pages, "label": "未计入位置与失败页合计",
                      "unattributed": {"value": excluded, "denominator": extracted,
                                       "label": "已提取但未归属或未达候选门槛的位置",
                                       "items": [item.occurrence_id for item in run.extraction_exclusions[:10]]},
                      "failed_pages": {"value": failed_pages, "denominator": total_pages,
                                       "label": "解析失败的页", "items": [c.failed_pages for c in run.coverage if c.failed_pages]},
                      "searched_pages": searched, "parsed_pages": sum(c.parsed_pages for c in run.coverage),
                      "total_pages": total_pages,
                      "denominator_label": f"已提取{extracted}处 / 已检索{searched}页 / 共{total_pages}页"},
        "unresolved_causes": unresolved_causes(run),
        # 反事实闭合推演汇总：把"依据不足"按"补纸面能否闭合"重新分档。
        # 与 unresolved_causes 并列而不替换：前者是程序字段的确定性读数，
        # 后者是对未决文本的关键词分类，两者分母不同，不得互相覆盖。
        "closure": summarize_closure(checks),
        "next_questions": [{"check_id": f.check_id, "question": f.question} for f in run.findings[:3]],
        "note": "同一关系可能同时计入多个状态；四问不合成综合分数，也不做排行。",
    }
