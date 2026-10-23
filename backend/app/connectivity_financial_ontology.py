"""财务—可持续语义本体：候选许可、可否定规则与解释卡。

本体负责两件事，且只负责这两件事：
1. 许可/排除：判断一个“ESG主张 → 年报财务项目”的候选映射是否被领域规则允许，
   被禁止的等价（如环保投入=在建工程）必须给出可解释理由。
2. 解释卡：同一映射同时输出支持性因素与排除因素，前端原样展示，不自行裁决。

确定性金额复算仍由 connectivity_engine.py 完成；本体不得越过既有计算闸门，
也不得把语义相关升格为已证实因果。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

VERSION = "financial_ontology_v1"

_RULES_PATH = Path(__file__).with_name("connectivity_impact_rules.json")


@lru_cache(maxsize=1)
def load_rules() -> dict:
    """读取领域规则库；文件损坏时直接抛错，不静默降级为无规则。"""
    with _RULES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def forbidden_equivalences() -> list[dict]:
    return load_rules().get("forbidden_equivalences", [])


def relation_templates() -> list[dict]:
    return load_rules().get("relation_templates", [])


def template_for(relation_kind: str) -> dict | None:
    for template in relation_templates():
        if template["relation_kind"] == relation_kind:
            return template
    return None


def lookup_rule(keyword: str) -> list[dict]:
    """受控工具入口：按概念或规则编号检索本体；不接受任意查询语句。"""
    body = str(keyword or "").strip()
    if not body:
        return []
    hits = []
    for item in forbidden_equivalences():
        if body in item["id"] or body in item["left"] or body in item["right"]:
            hits.append({"kind": "forbidden_equivalence", **item})
    for item in relation_templates():
        if body in item["rule_id"] or body in item["name"] or body in item["source_concept"] \
                or body in item["target_concept"]:
            hits.append({"kind": "relation_template", **item})
    domain = load_rules().get("concept_domain", {})
    for concept, aliases in domain.items():
        if body == concept or body in aliases:
            hits.append({"kind": "concept", "concept": concept, "aliases": aliases})
    return hits


def candidate_financial_statements(topic: str, industry: str) -> list[str]:
    """给定主题与行业，返回许可的财务科目候选；不得为凑确认数放宽。"""
    domain = load_rules().get("concept_domain", {})
    statements: list[str] = []
    for template in relation_templates():
        if industry in template["applicable_industries"] or "*" in template["applicable_industries"]:
            if topic and (topic in template["source_concept"] or topic in template["name"]):
                statements.extend(template["financial_statement_candidates"])
    for concept, aliases in domain.items():
        if topic and (topic in concept or any(alias in str(topic) for alias in aliases)):
            for template in relation_templates():
                statements.extend(template["financial_statement_candidates"])
    return sorted(set(statements))


def evaluate_mapping(claim: dict, node: dict, *, relation_kind: str,
                     same_entity: bool, same_period: bool | None,
                     definition_compatible: bool | None,
                     boundary_compatible: bool | None) -> dict:
    """对一条候选关系执行本体许可检查，输出裁决与解释卡双因素。

    裁决只有三种：
    - "forbidden"：命中禁止等价，必须降级或拒绝，理由写入排除因素；
    - "conditional"：未命中禁止项，但仍有未满足前提，维持待补证语义；
    - "allowed"：前提未被否定，可保持原关系强度（仍不是已证实因果）。
    """
    supporting: list[str] = []
    excluding: list[dict] = []
    if same_entity:
        supporting.append("主张与财务项目属于同一报告主体。")
    if same_period is True:
        supporting.append("主张期间与财务项目期间一致。")
    if definition_compatible is True:
        supporting.append("计量口径在原文层面一致。")
    if boundary_compatible is True:
        supporting.append("统计范围（合并/项目级）一致。")

    # 规则1：计划/预算口径与实绩金额不得直接对等（FE-003、FE-004）。
    phase = str(claim.get("planned_or_realized") or "")
    value_kind = str(node.get("value_kind") or "")
    if phase in {"plan", "budget"} and relation_kind in {"DIRECT_RECONCILIATION", "DISCLOSED_ALLOCATION"}:
        excluding.append({
            "rule_id": "FE-003",
            "factor": f"主张为{'计划' if phase == 'plan' else '预算'}口径（{phase}），财务项目为已发生金额（{value_kind or '实绩'}）。",
            "consequence": "禁止按同源披露对等处理；只能建立跨期或机制关联。"})
    # 规则2：目标语态主张与实绩财务节点（FE-004）。
    if claim.get("claim_kind") in {"target", "policy", "plan"} and relation_kind == "DIRECT_RECONCILIATION":
        excluding.append({
            "rule_id": "FE-004",
            "factor": "主张为目标/承诺语态，财务项目为已发生披露。",
            "consequence": "承诺不等于达成结果；关系降级为跨期关联。"})
    # 规则3：会计属性错配——费用化主张对应资本化项目（或反之）。
    nature = str(claim.get("accounting_nature") or "")
    node_line = str(node.get("financial_statement_line") or "")
    if nature == "opex" and any(term in node_line for term in ("在建工程", "固定资产", "购建")):
        excluding.append({
            "rule_id": "FE-002",
            "factor": "主张为费用性支出，财务项目为资本性项目。",
            "consequence": "资本化与费用化不得等价；须核对构成与调整。"})
    if nature == "capex" and "费用" in node_line and "研发" not in node_line:
        excluding.append({
            "rule_id": "FE-002",
            "factor": "主张为资本性投入，财务项目为费用性科目。",
            "consequence": "方向相反的口径错配，禁止等价。"})
    # 规则4：合并范围与母公司口径混算（FE-007）。
    scope = str(claim.get("accounting_scope") or "") + " " + str(node.get("scope") or "")
    if ("母公司" in scope and "合并" in scope) and same_entity:
        excluding.append({
            "rule_id": "FE-007",
            "factor": "主张与财务项目分属合并与母公司口径。",
            "consequence": "同主体条件不足以支持混算；须分别核对范围声明。"})
    # 规则5：仅凭同名/同金额/同年度不构成直接证实——即使结论层无冲突也必须保留待补证语义。
    if relation_kind == "DIRECT_RECONCILIATION":
        has_text_basis = bool(claim.get("metric_definition")) and definition_compatible is True
        if not has_text_basis:
            excluding.append({
                "rule_id": "OT-DIRECT-01",
                "factor": "仅有金额接近且主体/期间未发现冲突，缺少原文明示的同一口径。",
                "consequence": "同名、同金额、同年度均不能单独触发 directly_supported；保持待补证。"})

    if excluding:
        # FE-003/FE-004 命中时关系必须降级：不得把计划当实绩。
        hard = [item for item in excluding if item["rule_id"] in {"FE-003", "FE-004"}]
        if hard and relation_kind in {"DIRECT_RECONCILIATION", "DISCLOSED_ALLOCATION"}:
            return {"verdict": "forbidden", "relation_kind": relation_kind,
                    "suggested_relation_kind": "TEMPORAL_ASSOCIATION",
                    "supporting_factors": supporting,
                    "exclusion_factors": excluding,
                    "explanation": "；".join(item["factor"] for item in hard)}
        return {"verdict": "conditional", "relation_kind": relation_kind,
                "suggested_relation_kind": relation_kind,
                "supporting_factors": supporting,
                "exclusion_factors": excluding,
                "explanation": "存在排除因素；保持待补证语义，不升级关系强度。"}
    return {"verdict": "allowed", "relation_kind": relation_kind,
            "suggested_relation_kind": relation_kind,
            "supporting_factors": supporting or ["未发现支持性原文；保留候选。"],
            "exclusion_factors": [],
            "explanation": "未命中禁止等价与排除条件。"}
