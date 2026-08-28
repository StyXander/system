"""证据适配度与允许主张等级（创新二）。

使用离散类别，不做未经专业确认的绝对“可靠性分数”：
1. current_entity_primary_evidence：当前企业年报及已验证补充资料，可支持受边界限制的案例事实；
2. authoritative_normative_basis：准则、法规及权威规范，只支持规范和程序依据；
3. analogous_regulatory_or_industry_background：处罚、问询、行业和宏观资料，只支持类比或待验证背景；
4. unverified_background：不得进入最终事实主张，只能登记待回查。

程序根据类别生成 allowed_claim_types，并在 Agent 输出校验时执行；
任何越界主张触发降级（force 为 unverified_hypothesis）并记录违规，供页面与导出展示。
"""

from __future__ import annotations

from typing import Any

CURRENT_ENTITY = "current_entity_primary_evidence"
NORMATIVE_BASIS = "authoritative_normative_basis"
ANALOGOUS_BACKGROUND = "analogous_regulatory_or_industry_background"
UNVERIFIED_BACKGROUND = "unverified_background"

NORMATIVE_SOURCE_CATEGORIES = {"accounting_standard", "auditing_standard", "tax_regulation"}
ANALOGOUS_SOURCE_CATEGORIES = {
    "csrc_penalty",
    "exchange_inquiry",
    "industry_report",
    "news",
    "macro_indicator",
    "annual_report",  # 知识库里的年报只作类比/背景，除非与当前案例一致由案例 RAG 提供
}

# 只有证据行需要 fitness_class；覆盖矩阵、数字轨迹和缺口列表是结构化结果，
# 不应被误标成“未核验背景”。
EVIDENCE_LIST_KEYS = {
    "field_evidence",
    "rag_evidence",
    "supplement_evidence",
    "procedure_evidence",
    "knowledge_evidence",
    "regulatory_evidence",
}

ALLOWED_CLAIM_TYPES = {
    CURRENT_ENTITY: ["current_entity_fact"],
    NORMATIVE_BASIS: ["normative_basis", "procedure_basis"],
    ANALOGOUS_BACKGROUND: ["analogous_background"],
    UNVERIFIED_BACKGROUND: [],
}


def classify_source_category(source_category: str | None) -> str:
    category = str(source_category or "").strip()
    if not category:
        return UNVERIFIED_BACKGROUND
    if category in NORMATIVE_SOURCE_CATEGORIES:
        return NORMATIVE_BASIS
    if category in ANALOGOUS_SOURCE_CATEGORIES:
        return ANALOGOUS_BACKGROUND
    return UNVERIFIED_BACKGROUND


def classify_evidence_row(row: dict[str, Any], *, bundle_key: str = "field_evidence") -> str:
    """按证据分组与来源类别确定适配度类别。"""
    if bundle_key in {"field_evidence", "rag_evidence", "supplement_evidence", "procedure_evidence"}:
        if bundle_key == "rag_evidence":
            # 案例隔离 RAG 片段来自当前案例年报原文，可支持当前企业事实。
            return CURRENT_ENTITY
        if bundle_key in {"field_evidence", "supplement_evidence"}:
            return CURRENT_ENTITY
        if bundle_key == "procedure_evidence":
            # 程序计算结果卡属于确定性程序输出，作为当前企业程序事实。
            return CURRENT_ENTITY
    source_category = row.get("source_category")
    if source_category:
        return classify_source_category(source_category)
    return UNVERIFIED_BACKGROUND


def annotate_evidence_bundle(evidence_bundle: dict[str, Any]) -> dict[str, Any]:
    """给证据包每行附加 fitness_class 与 allowed_claim_types（只读增强）。"""
    annotated: dict[str, Any] = {}
    for key, rows in evidence_bundle.items():
        if key not in EVIDENCE_LIST_KEYS or not isinstance(rows, list):
            annotated[key] = rows
            continue
        new_rows = []
        for row in rows:
            if not isinstance(row, dict):
                new_rows.append(row)
                continue
            fitness = classify_evidence_row(row, bundle_key=key)
            new_rows.append(
                {
                    **row,
                    "fitness_class": fitness,
                    "allowed_claim_types": ALLOWED_CLAIM_TYPES[fitness],
                }
            )
        annotated[key] = new_rows
    return annotated


def fitness_map_for_evidence(evidence_bundle: dict[str, Any]) -> dict[str, str]:
    """evidence_id -> fitness_class 映射，供主张边界校验使用。"""
    mapping: dict[str, str] = {}
    for key, rows in evidence_bundle.items():
        if key not in EVIDENCE_LIST_KEYS or not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("evidence_id"):
                mapping[str(row["evidence_id"])] = classify_evidence_row(row, bundle_key=key)
    return mapping


def enforce_claim_boundaries(
    claims: list[dict[str, Any]],
    fitness_map: dict[str, str],
) -> list[dict[str, Any]]:
    """检查主张的证据适配度边界；越界主张降级为 unverified_hypothesis 并记录违规。

    规则：
    - 引用 unverified_background 证据的主张不允许进入最终事实；
    - 仅引用规范/类比背景证据（无当前企业证据）且标为 supported 的主张必须降级，
      因为规范与类比不能支持当前企业事实；
    - 无证据主张保持原状（外部解释属于待验证假设，由语义校验处理）。
    """
    violations: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        evidence_ids = [str(e) for e in (claim.get("evidence_ids") or [])]
        if not evidence_ids:
            continue
        classes = {fitness_map.get(eid, UNVERIFIED_BACKGROUND) for eid in evidence_ids}
        if UNVERIFIED_BACKGROUND in classes:
            claim["support_status"] = "unverified_hypothesis"
            violations.append(
                {
                    "claim_index": index,
                    "reason": "引用未核验背景证据，主张降级为待验证假设。",
                    "evidence_ids": evidence_ids,
                }
            )
            continue
        if (
            claim.get("support_status") == "supported"
            and not classes & {CURRENT_ENTITY}
        ):
            claim["support_status"] = "unverified_hypothesis"
            violations.append(
                {
                    "claim_index": index,
                    "reason": "仅引用规范/类比背景证据，不能支持当前企业事实，主张降级为待验证假设。",
                    "evidence_ids": evidence_ids,
                    "fitness_classes": sorted(classes),
                }
            )
    return violations
