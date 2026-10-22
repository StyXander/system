"""审迹智链：有预算约束的主动补证规划与可追溯证据图。

本模块不调用模型，不更改事实计算或正式结论。分数只是确定性检索优先级，
不能当作正确率、风险评分或行业审计意见。
"""
from __future__ import annotations

import re

VERSION = "adaptive_proof_v1"
WEIGHTS = {"定义": 8, "范围": 8, "公式": 7, "组成完整": 7, "互不重叠": 7,
           "单位": 6, "期间": 6, "主体": 6}
ACTIONS = {"定义": "查找指标定义及排除项", "范围": "核对统计口径和合并边界",
           "公式": "补查分子、分母及公式脚注", "组成完整": "核实完整分类及其他项",
           "互不重叠": "寻找分项包含与重叠证据", "单位": "查看单位和换算说明",
           "期间": "查验期间与重述披露", "主体": "核对公司主体与合并范围"}


def _get(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _list(obj, name):
    return _get(obj, name, []) or []


def plan_procedures(checks, *, round_number: int, budget: int = 8) -> dict:
    """因证据缺口选择后续程序，稳定排序、限两轮、不得无限循环。"""
    if round_number not in (1, 2) or not 1 <= budget <= 32:
        raise ValueError("round_number must be 1..2 and budget 1..32")
    candidates = []
    for check in checks:
        pending = [c for c in _list(check, "conditions") if _get(c, "status") != "supported"]
        unexplained = [h for h in _list(check, "hypotheses") if _get(h, "status") in {"open", "plausible"}]
        cross = bool(_get(check, "cross_document", False))
        if not pending and not unexplained and round_number != 2:
            continue
        if not pending and not unexplained and not cross:
            continue
        names = sorted({str(_get(c, "name", "unknown")) for c in pending})
        top = max(names, key=lambda n: WEIGHTS.get(n, 1)) if names else ""
        conflicts = sum(_get(c, "status") == "conflicting" for c in pending)
        points = sum(WEIGHTS.get(_get(c, "name"), 2) for c in pending)
        points += conflicts * 5 + len(unexplained) * 3 + (4 if cross else 0)
        candidates.append({"check_id": str(_get(check, "check_id")),
                           "priority": points,
                           "unresolved_conditions": names,
                           "action": ACTIONS.get(top, "主动检索相反披露与附注"),
                           "counter_search": round_number == 2 or bool(conflicts),
                           "rationale": "缺失条件/冲突/跨报告价值综合排序，不代表准确率"})
    candidates.sort(key=lambda x: (-x["priority"], x["check_id"]))
    chosen = candidates[:budget]
    return {"version": VERSION, "round": round_number, "budget": budget,
            "eligible": len(candidates), "selected_check_ids": [c["check_id"] for c in chosen],
            "deferred_check_ids": [c["check_id"] for c in candidates[budget:]],
            "procedures": chosen, "stop_reason": "no_evidence_gap" if not candidates else "bounded_budget"}


def procedure_effect(plan: dict, before_checks, after_checks, tasks: list[dict]) -> dict:
    """只有条件状态真实变化才计入有效升级，不能把检索命中冒充专业结论。"""
    def state(items):
        return {str(_get(x, "check_id")): {str(_get(c, "name")): _get(c, "status")
                for c in _list(x, "conditions")} for x in items}
    first, second = state(before_checks), state(after_checks)
    by_id = {str(t.get("check_id")): t for t in tasks}
    events = []
    for check_id in plan["selected_check_ids"]:
        changed = [{"condition": name, "before": status, "after": second.get(check_id, {}).get(name)}
                   for name, status in first.get(check_id, {}).items()
                   if second.get(check_id, {}).get(name) != status]
        task = by_id.get(check_id)
        events.append({"check_id": check_id, "executed": task is not None,
                       "new_evidence_ids": list((task or {}).get("new_evidence_ids", [])),
                       "condition_changes": changed,
                       "upgraded_conditions": [c["condition"] for c in changed if c["after"] == "supported"]})
    return {"version": VERSION, "round": plan["round"], "events": events,
            "executed": sum(x["executed"] for x in events),
            "upgraded": sum(bool(x["upgraded_conditions"]) for x in events),
            "note": "条件升级来自已有确定性核验；检索次数和命中数不等于正确率"}


def build_proof_graph(run, max_checks: int = 60) -> dict:
    """关系-条件-原文-报告构成局部图；逐字引文未验证时显式保留缺口。"""
    if not 1 <= max_checks <= 200:
        raise ValueError("max_checks out of bounds")
    occurrences = {str(_get(x, "occurrence_id")): x for x in _list(run, "occurrences")}
    documents = {str(_get(x, "document_id")): x for x in _list(run, "documents")}
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str]] = set()
    paths = []
    def node(kind, key, **fields):
        ident = kind + ":" + key
        nodes[ident] = {"id": ident, "type": kind, **fields}
        return ident
    def edge(a, b, kind):
        edges.add((a, b, kind))
    def cite(ref, anchor, relation):
        oid, quote = str(_get(ref, "occurrence_id", "")), str(_get(ref, "quote", ""))
        occurrence = occurrences.get(oid)
        if occurrence is None or len(quote.strip()) < 2:
            return False
        compact = lambda value: re.sub(r"\s+", "", str(value or ""))
        if compact(quote) not in compact(_get(occurrence, "context", "")):
            return False
        did = str(_get(occurrence, "document_id", ""))
        if did not in documents:
            return False
        row = node("occurrence", oid, label=str(_get(occurrence, "label", ""))[:150],
                   document_id=did, pdf_page=_get(occurrence, "pdf_page"), quote=quote[:240])
        document = node("document", did, report_type=_get(documents[did], "report_type", ""))
        edge(anchor, row, relation)
        edge(row, document, "page_source")
        return True
    all_checks = _list(run, "checks")
    for check in all_checks[:max_checks]:
        cid = str(_get(check, "check_id"))
        root = node("check", cid, title=_get(check, "title", ""),
                    basis_level=_get(check, "basis_level", ""),
                    conclusion_level=_get(check, "conclusion_level", ""))
        gaps, supported, members = [], [], []
        for member in _list(check, "members"):
            oid = str(_get(member, "occurrence_id"))
            occurrence = occurrences.get(oid)
            if occurrence is None or str(_get(occurrence, "document_id", "")) not in documents:
                gaps.append("unbound_member:" + oid)
                continue
            did = str(_get(occurrence, "document_id"))
            m = node("occurrence", oid, label=_get(occurrence, "label", ""),
                     document_id=did, pdf_page=_get(occurrence, "pdf_page"),
                     value=_get(occurrence, "value"), unit=_get(occurrence, "unit"))
            d = node("document", did, report_type=_get(documents[did], "report_type", ""))
            edge(root, m, "member_" + str(_get(member, "role", "")))
            edge(m, d, "page_source")
            members.append(oid)
        if _get(check, "cross_document", False):
            kinds = {_get(documents[str(_get(occurrences[oid], "document_id"))], "report_type", "")
                     for oid in members}
            if len(kinds) < 2:
                gaps.append("cross_report_requires_two_report_types")
        for condition in _list(check, "conditions"):
            name = str(_get(condition, "name"))
            status = str(_get(condition, "status"))
            n = node("condition", cid + ":" + name, name=name, status=status)
            edge(root, n, "requires")
            count = sum(cite(ref, n, "supported_by") for ref in _list(condition, "evidence"))
            if status == "supported" and count:
                supported.append(name)
            else:
                gaps.append(name + ":" + (status if status != "supported" else "quote_unverified"))
        relation_quotes = sum(cite(ref, root, "relationship_quoted_by") for ref in _list(check, "relationship_evidence"))
        paths.append({"check_id": cid, "members": members, "supported_conditions": supported,
                      "gaps": gaps, "relationship_quote_count": relation_quotes,
                      "trace": "complete" if members and not gaps and relation_quotes else "incomplete"})
    return {"version": VERSION, "nodes": [nodes[k] for k in sorted(nodes)],
            "edges": [{"from": a, "to": b, "kind": k} for a, b, k in sorted(edges)],
            "paths": paths, "truncated_checks": max(0, len(all_checks) - max_checks),
            "note": "证据来源可追溯不代表企业披露真实、审计证据充分或已出具审计意见"}
