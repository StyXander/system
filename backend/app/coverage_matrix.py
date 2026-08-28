"""认定—证据—程序覆盖矩阵（创新一）。

矩阵把审计计划阶段的“认定 × 证据 × 程序”组织为可回查的结构化行：
- 认定只能来自已登记映射（R1 认定候选），不由模型自由编造；
- procedure ID 只能来自 backend/audit_procedure_map.json；
- 支持等级根据证据与缺口状态确定性判定。

矩阵用于 API 结构化结果、证据抽屉、JSON/CSV/PDF/DOCX 导出与评估台账，
保证同一案例四类导出内容一致。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .signoff import R1_ASSERTION_MAPPING

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PROCEDURE_MAP_PATH = WORKSPACE_ROOT / "backend" / "audit_procedure_map.json"

# 支持等级取值
COVERED = "covered"
PARTIALLY_COVERED = "partially_covered"
GAP = "gap"
NOT_APPLICABLE = "not_applicable"


def load_audit_procedure_map() -> dict[str, Any]:
    """读取审计程序映射；只读，不缓存改写。"""
    if not PROCEDURE_MAP_PATH.is_file():
        return {"procedures": []}
    try:
        return json.loads(PROCEDURE_MAP_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"procedures": []}


def procedures_by_assertion(assertion: str) -> list[dict[str, Any]]:
    """返回覆盖某认定的程序；只使用映射中已登记的程序 ID。"""
    payload = load_audit_procedure_map()
    procedures = payload.get("procedures") or []
    if isinstance(procedures, dict):
        procedures = list(procedures.values())
    result = []
    for item in procedures:
        if not isinstance(item, dict):
            continue
        assertions = item.get("assertions") or []
        if any(assertion in text for text in assertions):
            result.append(
                {
                    "procedure_id": item.get("procedure_id"),
                    "procedure": item.get("procedure"),
                    "automation_level": item.get("automation_level"),
                }
            )
    return result


def _assertion_rows(case_id: str, rule_ids: list[str]) -> list[dict[str, Any]]:
    """按签字认定映射展开矩阵行；只覆盖当前规则相关的认定。"""
    rows: list[dict[str, Any]] = []
    for rule_id in rule_ids or ["R1"]:
        if rule_id == "R1":
            for account, assertions in R1_ASSERTION_MAPPING.items():
                for assertion in assertions:
                    rows.append(
                        {
                            "assertion": assertion,
                            "account": account,
                            "rule_id": rule_id,
                            "matrix_row_id": f"{case_id}-{rule_id}-{account}-{assertion}",
                        }
                    )
    return rows


def _field_evidence_for_assertion(evidence_bundle: dict[str, Any], assertion: str) -> list[str]:
    """返回当前企业直接证据中与该认定相关的 evidence ID。

    当前实现按账户粗粒度关联（应收/收入字段证据对应认定），
    不做证据文本级的认定匹配，避免过度声称。
    """
    ids: list[str] = []
    for row in (evidence_bundle or {}).get("field_evidence") or []:
        field_label = str(row.get("field_label") or "")
        evidence_id = str(row.get("evidence_id") or "")
        if not evidence_id:
            continue
        if assertion in ("存在", "计价和分摊") and ("应收" in field_label or "坏账" in field_label):
            ids.append(evidence_id)
        elif assertion in ("发生", "截止", "准确性") and ("收入" in field_label or "营业收入" in field_label):
            ids.append(evidence_id)
    return ids


def build_assertion_evidence_procedure_matrix(
    *,
    case_id: str,
    current_year: int,
    t0: str | None,
    rule_ids: list[str],
    rule_results: list[dict[str, Any]],
    evidence_bundle: dict[str, Any],
    knowledge_trace: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """构建覆盖矩阵。knowledge_trace 是知识检索轨迹（source_category 等）。"""
    knowledge_trace = knowledge_trace or []
    rows: list[dict[str, Any]] = []
    rule_map = {r.get("rule_id"): r for r in rule_results if isinstance(r, dict)}
    gaps: set[str] = set()
    requested: set[str] = set()
    for rule in rule_results if isinstance(rule_results, list) else []:
        card = rule.get("risk_card") or {}
        gaps.update(card.get("data_gaps") or [])
        requested.update(card.get("requested_materials") or [])

    normative_basis = [
        {
            "source_id": item.get("source_id"),
            "locator": item.get("locator"),
            "category": item.get("source_category"),
        }
        for item in knowledge_trace
        if item.get("source_category") in {"accounting_standard", "auditing_standard", "tax_regulation"}
    ]
    analogous_background = [
        {
            "source_id": item.get("source_id"),
            "locator": item.get("locator"),
            "category": item.get("source_category"),
        }
        for item in knowledge_trace
        if item.get("source_category") in {"csrc_penalty", "exchange_inquiry", "industry_report", "news", "macro_indicator"}
    ]

    for base in _assertion_rows(case_id, rule_ids):
        rule = rule_map.get(base["rule_id"]) or {}
        direct_evidence = _field_evidence_for_assertion(evidence_bundle, base["assertion"])
        procedures = procedures_by_assertion(base["assertion"])
        if not procedures:
            status = NOT_APPLICABLE
            support_level = "无程序映射，本认定不在当前范围"
        elif not direct_evidence and gaps:
            status = GAP
            support_level = "缺少当前企业直接证据且存在资料缺口"
        elif direct_evidence and gaps:
            status = PARTIALLY_COVERED
            support_level = "有当前企业直接证据，但资料缺口未完全覆盖"
        elif direct_evidence:
            status = COVERED
            support_level = "有当前企业直接证据"
        else:
            status = GAP
            support_level = "缺少当前企业直接证据"
        rows.append(
            {
                "matrix_row_id": base["matrix_row_id"],
                "assertion": base["assertion"],
                "account": base["account"],
                "rule_id": base["rule_id"],
                "current_entity_direct_evidence": direct_evidence,
                "normative_basis": normative_basis,
                "analogous_background": analogous_background,
                "support_level": support_level,
                "status": status,
                "uncovered_gaps": sorted(gaps),
                "requested_materials": sorted(requested),
                "suggested_procedures": procedures,
                "procedure_ids": [p["procedure_id"] for p in procedures],
                "source_of_row": "programmatic",
            }
        )
    return rows
