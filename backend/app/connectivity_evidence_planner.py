"""预算约束下的补证行动规划：行动级区分度、成本、依赖与可复算排序。

“最优”只指当前候选集合、既定权重和预算内的最优解；候选很多时用束搜索，
并在结果中明确算法与权重，不把启发式排序说成全局最优。
"""
from __future__ import annotations

import hashlib
import itertools
import re
from decimal import Decimal

VERSION = "evidence_planner_v1"
WEIGHTS = {"discrimination": 12, "gap_coverage": 8, "availability": 6,
           "novelty": 4, "cost": -3, "dependency": -2, "redundancy": -5,
           "specificity": 1}
CONDITION_WEIGHT = {"定义": 10, "期间": 8, "单位": 8, "主体": 7, "范围": 6,
                    "金额归属": 5, "反向检索": 4, "修订说明": 4, "项目台账": 3}
DEFAULT_BUDGET = {"call_budget": 3, "max_actions": 2}


def _stable_id(text: str) -> str:
    return "ACT-" + hashlib.sha256(text.encode()).hexdigest()[:10].upper()


def _condition_name(text: str) -> str:
    return str(text or "").split("：", 1)[0].strip() or "未命名条件"


def _hypotheses_for(edge: dict, revision: dict | None) -> list[str]:
    if not revision:
        return []
    return [hypothesis["hypothesis_id"] for hypothesis in revision.get("hypotheses", [])
            if hypothesis.get("edge_id") == edge.get("edge_id")]


def _template(condition: str, edge: dict) -> dict:
    page = edge.get("financial_page")
    claim_page = edge.get("claim_page")
    line = edge.get("financial_statement_line") or "年报财务项目"
    templates = {
        "定义": (f"核对年报 p{page} 表头与附注：{line}", "确认“预算数/本期增加/期末余额”与ESG“总投入”是否为同一计量口径"),
        "范围": (f"核对ESG p{claim_page} 主张原句与年报 p{page} 项目行", "确认主张覆盖多基地/多项目，还是单一项目"),
        "期间": (f"核对年报 p{page} 项目表列名与期间", "确认金额是累计预算、本期增加还是期末余额"),
        "主体": (f"核对年报 p{page} 项目所属主体/基地", "确认项目与ESG披露主体是否为同一合并范围"),
        "金额归属": (f"查找年报 p{page} 项目行金额与ESG p{claim_page} 项目清单", "确认是否存在逐项金额对应，而非主题相近"),
        "单位": (f"核对年报 p{page} 金额单位与ESG p{claim_page} 单位", "排除元/万元/亿元及实物量口径错配"),
    }
    return {"target": templates.get(condition, (f"核对年报 p{page} 与ESG p{claim_page} 的原文", "补齐该条件")), "condition": condition}


def actions_for_edge(edge: dict, revision: dict | None = None) -> list[dict]:
    """为一个关系生成 5-8 条候选行动；不足时补入反向检索与人工索取。"""
    conditions = [_condition_name(item) for item in edge.get("missing_conditions", [])]
    conditions = list(dict.fromkeys(conditions)) or ["金额归属"]
    hypotheses = _hypotheses_for(edge, revision)
    actions = []
    for index, condition in enumerate(conditions[:5]):
        target, purpose = _template(condition, edge)["target"]
        page = edge.get("financial_page")
        executable = bool(page) or condition in {"范围", "金额归属"}
        tier = 1 if page else 2
        dependency = ""
        if condition in {"金额归属", "期间"} and "定义" in conditions:
            dependency = _stable_id(f"{edge['edge_id']}|定义")
        action = {
            "action_id": _stable_id(f"{edge['edge_id']}|{condition}"),
            "edge_id": edge["edge_id"],
            "claim_id": edge["claim_id"],
            "condition_id": f"{edge['edge_id']}:{condition}",
            "condition": condition,
            "target_hypotheses": hypotheses,
            "proposed_source": f"{edge.get('financial_document_id') or edge.get('claim_document_id')} p{page or edge.get('claim_page')}",
            "exact_target": target,
            "purpose": purpose,
            "expected_discrimination": len(hypotheses) or 1,
            "gap_coverage": len(conditions),
            "estimated_cost_tier": tier,
            "dependency": dependency,
            "evidence_already_available": bool(edge.get("evidence_ids")),
            "predicted_outcomes": {
                "if_support": "该条件可升级为 supported；关系最多升到有限支持，仍需其他条件",
                "if_refute": "该条件记为 conflicting；关系降级或保留为反例",
                "if_no_result": "保持 unknown，不推定企业未披露",
            },
            "stop_condition": "找到原文明确表述，或确认本次报告对内没有该项目级信息",
            "provenance": "deterministic_template_v1",
            "executable": executable,
            "requires_entity": condition == "金额归属" and not page,
            "query_terms": _query_terms(edge, condition),
            "context_terms": [edge.get("financial_label", "")] if edge.get("financial_label") else [],
            "company": edge.get("company", ""), "period": edge.get("period", ""),
        }
        actions.append(action)
    # 不足 5 条时补入反向检索与人工动作，保证可比较。
    extras = [
        ("反向检索", "检索与主张相反或例外的披露", "寻找“未达到/未实施/口径变化”等反向材料", 1, True),
        ("修订说明", "核对报告修订/更正说明", "确认金额是否因重述而变化", 2, True),
        ("项目台账", "向企业索取项目级投入台账", "取得报告未公开的项目明细与会计归属", 3, False),
    ]
    for condition, target, purpose, tier, executable in extras:
        if len(actions) >= 6:
            break
        if any(action["condition"] == condition for action in actions):
            continue
        actions.append({
            "action_id": _stable_id(f"{edge['edge_id']}|{condition}"),
            "edge_id": edge["edge_id"], "claim_id": edge["claim_id"],
            "condition_id": f"{edge['edge_id']}:{condition}",
            "condition": condition, "target_hypotheses": hypotheses,
            "proposed_source": "已登记报告" if executable else "企业未公开资料",
            "exact_target": target, "purpose": purpose,
            "expected_discrimination": len(hypotheses) or 1,
            "gap_coverage": len(conditions), "estimated_cost_tier": tier, "dependency": "",
            "evidence_already_available": False,
            "predicted_outcomes": {"if_support": "补充一条独立证据", "if_refute": "可能改变关系方向",
                                   "if_no_result": "保持未决"},
            "stop_condition": "取得原文或确认无法从公开报告取得",
            "provenance": "deterministic_template_v1", "executable": executable,
            "requires_entity": not executable, "query_terms": _query_terms(edge, condition),
        })
    return actions[:8]


def _query_terms(edge: dict, condition: str) -> list[str]:
    terms = []
    if condition in {"定义", "期间", "单位"}:
        terms = ["预算数", "本期增加", "期末余额"]
    elif condition == "范围":
        terms = ["各基地", "四基地", "合计", "项目"]
    elif condition == "主体":
        terms = ["母公司", "合并", "子公司", "基地"]
    elif condition == "金额归属":
        terms = ["环保", "节能", "项目", "投入"]
    elif condition == "反向检索":
        terms = ["未达到", "未实施", "口径变化", "剔除"]
    elif condition == "修订说明":
        terms = ["更正", "修订", "重述"]
    else:
        terms = ["项目", "预算", "投入"]
    return terms[:5]


def score_action(action: dict) -> dict:
    breakdown = {
        "discrimination": WEIGHTS["discrimination"] * max(1, action.get("expected_discrimination", 1)),
        "gap_coverage": WEIGHTS["gap_coverage"] * max(1, min(3, action.get("gap_coverage", 1))),
        "availability": WEIGHTS["availability"] if action.get("evidence_already_available") else 0,
        "novelty": WEIGHTS["novelty"] if not action.get("evidence_already_available") else 0,
        "cost": WEIGHTS["cost"] * int(action.get("estimated_cost_tier", 1)),
        "dependency": WEIGHTS["dependency"] if action.get("dependency") else 0,
        "specificity": WEIGHTS["specificity"] * CONDITION_WEIGHT.get(action.get("condition", ""), 2),
    }
    breakdown["total"] = sum(breakdown.values())
    return breakdown


def _set_score(action: dict) -> dict:
    action["score_breakdown"] = score_action(action)
    action["score"] = action["score_breakdown"]["total"]
    return action


def _portfolio_value(actions: list[dict]) -> int:
    """组合分数：覆盖的条件累加，重复区分同一假设要扣冗余。"""
    total = sum(action["score"] for action in actions)
    seen = {}
    for action in actions:
        for hypothesis in action.get("target_hypotheses", []):
            seen[hypothesis] = seen.get(hypothesis, 0) + 1
    return total + sum(WEIGHTS["redundancy"] * (count - 1) for count in seen.values() if count > 1)


def optimize(actions: list[dict], budget: dict | None = None) -> dict:
    """预算内穷举（候选≤12）或束搜索；返回第一/第二路径与差异。"""
    budget = {**DEFAULT_BUDGET, **(budget or {})}
    max_actions = max(1, min(4, int(budget.get("max_actions", 2))))
    call_budget = max(1, min(8, int(budget.get("call_budget", 3))))
    eligible = [action for action in actions if action.get("executable", True)]
    eligible = [_set_score(action) for action in eligible]
    # 同一条件只保留得分最高的动作，避免组合里重复查同一页。
    by_condition = {}
    for action in eligible:
        key = (action.get("condition"), action.get("proposed_source")) or action["condition_id"]
        if key not in by_condition or action["score"] > by_condition[key]["score"]:
            by_condition[key] = action
    pool = sorted(by_condition.values(), key=lambda item: (-item["score"], item["action_id"]))[:12]
    combinations = []
    for size in range(1, max_actions + 1):
        for combo in itertools.combinations(pool, size):
            cost = sum(int(action.get("estimated_cost_tier", 1)) for action in combo)
            if cost > call_budget:
                continue
            covered = {identifier for action in combo for identifier in
                       [action["action_id"], *action.get("covered_action_ids", [])]}
            if any(action.get("dependency") and action["dependency"] not in covered
                   and not action.get("dependency_satisfied") for action in combo):
                continue
            combinations.append(list(combo))
    combinations.sort(key=lambda combo: (-_portfolio_value(combo), sum(a["estimated_cost_tier"] for a in combo)))
    best = combinations[0] if combinations else []
    second = next((combo for combo in combinations[1:]
                   if not best or combo[0]["action_id"] != best[0]["action_id"]), [])
    primary = best[0] if best else None
    alternative = next((action for action in pool if primary and action["action_id"] != primary["action_id"]
                        and action.get("condition") != primary.get("condition")
                        and int(action.get("estimated_cost_tier", 1)) <= call_budget
                        and (not action.get("dependency") or action.get("dependency_satisfied"))), None)
    return {
        "budget": budget,
        "algorithm": "候选≤12时穷举全部组合；超过12时按单项得分束搜索（本实现截断为12）",
        "pool_size": len(pool),
        "best_path": [_public_action(action) for action in best],
        "second_path": [_public_action(action) for action in second],
        "primary_action": _public_action(primary) if primary else None,
        "alternative_action": _public_action(alternative) if alternative else None,
        "best_value": _portfolio_value(best) if best else 0,
        "second_value": _portfolio_value(second) if second else 0,
        "primary_delta": (primary["score"] - alternative["score"]) if primary and alternative else 0,
        "comparison": _comparison(best, second, primary, alternative),
        "weights": WEIGHTS,
        "note": "分数是确定性优先级，不是正确率或信息增益概率；最优仅指当前候选与权重下。",
    }


def _public_action(action: dict) -> dict:
    return {key: value for key, value in action.items() if key not in {"score"}}


def _comparison(best: list[dict], second: list[dict], primary: dict | None = None,
                alternative: dict | None = None) -> str:
    if not best:
        return "没有可执行行动。"
    if primary and alternative:
        delta = primary["score"] - alternative["score"]
        return (f"第一优先“{primary['condition']}”：{primary['exact_target']}，"
                f"比第二优先“{alternative['condition']}”高 {delta} 分；"
                f"理由是它能同时覆盖 {primary['gap_coverage']} 项缺口、区分 "
                f"{primary['expected_discrimination']} 个解释，且成本为 {primary['estimated_cost_tier']} 级。")
    first = best[0]
    if not second:
        return f"第一优先：{first['exact_target']}；没有可比较的第二路径。"
    delta = _portfolio_value(best) - _portfolio_value(second)
    return (f"组合路径比第二路径高 {delta} 分；第一优先“{first['condition']}”（{first['exact_target']}）。")


def _consolidate(actions: list[dict]) -> list[dict]:
    """同一页同一条件的行动可同时服务多个关系；合并后只查一次，避免重复计分。"""
    groups = {}
    for action in actions:
        key = (action.get("condition"), action.get("proposed_source"))
        if key not in groups:
            groups[key] = dict(action)
            groups[key]["target_hypotheses"] = list(action.get("target_hypotheses", []))
            groups[key]["covered_edges"] = [action.get("edge_id")]
            groups[key]["covered_action_ids"] = [action["action_id"]]
            groups[key]["gap_coverage"] = max(1, action.get("gap_coverage", 1))
            continue
        current = groups[key]
        current["target_hypotheses"] = list(dict.fromkeys(
            [*current.get("target_hypotheses", []), *action.get("target_hypotheses", [])]))
        current["covered_edges"] = list(dict.fromkeys([*current.get("covered_edges", []), action.get("edge_id")]))
        current["covered_action_ids"] = list(dict.fromkeys([*current.get("covered_action_ids", []), action["action_id"]]))
        current["gap_coverage"] = max(current.get("gap_coverage", 1), action.get("gap_coverage", 1))
        current["expected_discrimination"] = len(current["target_hypotheses"]) or 1
    return sorted(groups.values(), key=lambda item: -_set_score(item)["score"])


def build_plan(bridge: dict, revision: dict | None = None, budget: dict | None = None) -> dict:
    """为每个未决关系生成行动，并给出全局前三条与逐关系行动单。"""
    actions = []
    for edge in bridge.get("edges", []):
        if edge.get("status") in {"insufficient"} and not edge.get("missing_conditions"):
            continue
        actions.extend(actions_for_edge(edge, revision))
    # 全局池：每条关系最多保留 2 个高分动作，避免一个大关系淹没其他关系。
    grouped = {}
    for action in actions:
        grouped.setdefault(action["edge_id"], []).append(action)
    global_pool = []
    for edge_actions in grouped.values():
        ranked = sorted((_set_score(action) for action in edge_actions), key=lambda item: -item["score"])
        global_pool.extend(ranked[:2])
    global_pool = _consolidate(global_pool)
    plan = optimize(global_pool, budget)
    by_edge = {}
    for edge_id, edge_actions in grouped.items():
        ranked = sorted((_set_score(action) for action in edge_actions), key=lambda item: -item["score"])
        by_edge[edge_id] = [_public_action(action) for action in ranked]
    plan.update(version=VERSION, by_edge=by_edge, total_actions=len(actions), edges=len(grouped))
    return plan


def rerank(previous: dict, *, completed_conditions: list[str], new_evidence_ids: list[str],
           reviewed_actions: list[str] | None = None) -> dict:
    """执行行动后，使用同一候选池重新计算优先级。

    已尝试行动与已解决条件分别传入，打开原页不代表条件成立。
    完成的行动退出候选，同一关系的其他未决条件继续保留。
    逐关系候选池与全局路径同步返回，不能只留下两个优先动作。
    新证据仅提高明确绑定动作的可获得性，不为整池统一加分。
    保留实际执行回执，让界面解释本次为何重排。
    第一和第二路径使用相同预算、评分权重和动作身份。
    依赖项未解决时继续在动作上显示，不能把执行过当作已支持。
    排序分数用于解释优先顺序，不代表成功概率或专业正确率。
    """
    completed = set(completed_conditions) | set(reviewed_actions or [])
    actions = []
    for action in previous.get("best_path", []) + previous.get("second_path", []):
        if action["condition_id"] in completed or action["action_id"] in completed:
            continue
        actions.append(action)
    for edge_actions in previous.get("by_edge", {}).values():
        for action in edge_actions:
            if action["condition_id"] in completed or action["action_id"] in completed:
                continue
            action = dict(action)
            # 新证据只影响明确绑定到该动作的可获得性，不全池一律加分。
            action["evidence_already_available"] = bool(action.get("evidence_already_available") or
                set(new_evidence_ids) & set(action.get("target_hypotheses", [])))
            actions.append(action)
    unique = {action["action_id"]: action for action in actions}
    new_plan = optimize(list(unique.values()), previous.get("budget"))
    old_first = (previous.get("best_path") or [{}])[0].get("action_id")
    new_first = (new_plan.get("best_path") or [{}])[0].get("action_id")
    remaining_by_edge = {edge: [a for a in edge_actions if a["condition_id"] not in completed
                               and a["action_id"] not in completed]
                         for edge, edge_actions in previous.get("by_edge", {}).items()}
    return {
        **new_plan,
        "version": previous.get("version", VERSION), "by_edge": remaining_by_edge,
        "total_actions": len(unique), "edges": len(remaining_by_edge),
        "execution": previous.get("execution", {}),
        "rerank": {
            "completed_conditions": sorted(completed),
            "new_evidence_ids": new_evidence_ids,
            "old_first": old_first,
            "new_first": new_first,
            "changed": old_first != new_first,
            "reason": "已完成条件退出候选；新证据使相关动作的可获得性上升，重新计算预算内最优组合。",
        },
    }


def execute_action(root, action: dict, documents: list) -> dict:
    """在已登记报告内执行“打开指定页并检索关键词”；不访问网络、不接受外部路径。"""
    if action.get("requires_entity"):
        return {"status": "requires_entity", "action_id": action["action_id"],
                "reason": "需要企业未公开的项目台账或凭证，系统不假装已读取。"}
    document_id = None
    page = None
    matched = re.search(r"(?:p|页)\s*(\d+)", action.get("exact_target", ""))
    if matched:
        page = int(matched.group(1))
    for doc in documents:
        if doc.document_id and doc.document_id in action.get("proposed_source", ""):
            document_id = doc.document_id
            break
    if not document_id:
        return {"status": "not_executable", "action_id": action["action_id"],
                "reason": "行动没有绑定到已登记文档。"}
    if not page:
        return {"status": "not_executable", "action_id": action["action_id"], "reason": "行动没有具体页码。"}
    try:
        from .connectivity_extraction import source_path
        from .source_viewer import PDF_ACCESS_LOCK
        import pymupdf
        doc = next(item for item in documents if item.document_id == document_id)
        with PDF_ACCESS_LOCK, pymupdf.open(source_path(root, doc)) as pdf:
            if page > len(pdf):
                return {"status": "no_match", "action_id": action["action_id"], "reason": "页码超出原件范围"}
            text = pdf[page - 1].get_text("text")
    except Exception as error:
        return {"status": "error", "action_id": action["action_id"], "reason": type(error).__name__}
    hits = [term for term in action.get("query_terms", []) if term in text]
    return {"status": "hit" if hits else "no_match", "action_id": action["action_id"],
            "document_id": document_id, "page": page, "matched_terms": hits,
            "quote": text[:400].replace("\n", " "), "tool": "open_registered_page"}
