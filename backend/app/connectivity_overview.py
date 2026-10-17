"""结果概览四问：每个数字都带分母，状态允许重叠，不合成综合分数。

页面、导出与接口读同一份 overview，避免"页面有数字、导出没有"或两边不一致。
同时给出未决原因六类分类，回答"为什么全未决"，不靠读者自己推断。
"""
from __future__ import annotations

from collections import Counter

from .connectivity_rules import BASE_CONDITIONS
from .connectivity_schemas import ConnectivityRun

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


def build_overview(run: ConnectivityRun) -> dict:
    """由同一次运行的关系、覆盖与未计入清单确定性推导，不调用模型。"""
    checks = run.checks
    total = len(checks)
    confirmed = [c for c in checks if c.criteria_status == "supported" and c.calculation_status in CONFIRMED_STATUSES]
    blocked = [c for c in checks if c.criteria_status in {"unknown", "conflicting"}]
    conflicting = [c for c in blocked if c.criteria_status == "conflicting"]
    unexplained = [c for c in checks if c.calculation_status == "unexplained_difference"]
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
    opinions = [a for a in run.ai_analyses if a.status == "current"]
    return {
        "relation_total": total,
        "ai_analysis": {"value": len(opinions), "denominator": total,
                        "items": [a.check_id for a in opinions],
                        "by_verdict": dict(Counter(a.verdict for a in opinions)),
                        "stale": sum(a.status != "current" for a in run.ai_analyses)},
        "trial_calculations": {"value": sum(bool(c.hypothetical) for c in checks),
                               "items": [c.check_id for c in checks if c.hypothetical]},
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
        "not_found": {"value": excluded + failed_pages, "label": "未计入位置与失败页合计",
                      "unattributed": {"value": excluded, "denominator": extracted,
                                       "label": "已提取但未归属或未达候选门槛的位置",
                                       "items": [item.occurrence_id for item in run.extraction_exclusions[:10]]},
                      "failed_pages": {"value": failed_pages, "denominator": total_pages,
                                       "label": "解析失败的页", "items": [c.failed_pages for c in run.coverage if c.failed_pages]},
                      "searched_pages": searched, "parsed_pages": sum(c.parsed_pages for c in run.coverage),
                      "total_pages": total_pages,
                      "denominator_label": f"已提取{extracted}处 / 已检索{searched}页 / 共{total_pages}页"},
        "unresolved_causes": unresolved_causes(run),
        "next_questions": [{"check_id": f.check_id, "question": f.question} for f in run.findings[:3]],
        "note": "同一关系可能同时计入多个状态；四问不合成综合分数，也不做排行。",
    }
