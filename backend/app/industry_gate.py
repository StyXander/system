"""行业适配闸门。

闸门只做确定性的适配分流，不替代行业研究或专业判断：
普通非金融企业允许当前工程规则，金融企业默认跳过 R1/R2，
条件适用行业保留限制并继续由字段和人工复核决定是否采用。
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Iterable


INDUSTRY_GATE_VERSION = "industry_gate_v1"
FINANCIAL_KEYWORDS = (
    "银行",
    "保险",
    "人寿",
    "财险",
    "证券",
    "券商",
    "信托",
    "基金",
    "金融",
    "融资租赁",
    "中国人保",
    "中国太保",
    "中国太平",
    "申万宏源",
    "中国平安",
    "平安银行",
    "招商银行",
)
CONDITIONAL_KEYWORDS = (
    "房地产",
    "建筑",
    "工程",
    "租赁",
    "物业",
    "平台",
    "互联网金融",
)
ENERGY_KEYWORDS = (
    "能源",
    "石油",
    "石化",
    "海油",
    "煤炭",
    "电力",
    "燃气",
    "矿业",
)
RULE_FIELDS = {
    "R1": ["revenue", "accounts_receivable"],
    "R2": ["revenue", "operating_cash_flow"],
}


def _text(*values: Any) -> str:
    return " ".join(str(value or "").strip() for value in values if str(value or "").strip())


def _normalized(value: Any) -> str:
    return re.sub(r"[\s（）()【】\[\]·,，。\-—_]", "", str(value or "").lower())


def evaluate_industry_gate(
    *,
    company: dict[str, Any] | None,
    case: dict[str, Any] | None,
    rule_ids: Iterable[str],
) -> dict[str, Any]:
    """根据可回查的公司元数据返回四级适配结果。

    当前巨潮股票清单不稳定地提供行业字段，因此第一版明确把名称关键词
    标为 metadata_heuristic，并把证据和理由码写入运行记录，不能伪装成
    交易所正式行业分类。
    """

    company = company or {}
    case = case or {}
    selected_rules = list(dict.fromkeys(str(rule) for rule in rule_ids))
    name = _text(
        company.get("company_name"),
        company.get("company_alias"),
        case.get("company_name"),
        case.get("company_alias"),
    )
    metadata_text = _text(
        company.get("industry"),
        company.get("industry_name"),
        company.get("industry_category"),
        company.get("business_scope"),
        case.get("industry"),
        case.get("industry_name"),
        case.get("reporting_profile"),
    )
    normalized_name = _normalized(name)
    normalized_metadata = _normalized(metadata_text)
    ticker = str(company.get("ticker") or case.get("ticker") or "")
    evidence = [
        {
            "evidence_type": "company_metadata",
            "case_id": case.get("case_id"),
            "ticker": ticker,
            "field": "company_name",
            "value": name,
            "source_mode": company.get("source_mode") or case.get("registry_mode") or "registered_case",
        }
    ]
    for field, value in (
        ("industry", company.get("industry") or case.get("industry")),
        ("industry_name", company.get("industry_name") or case.get("industry_name")),
        ("reporting_profile", company.get("reporting_profile") or case.get("reporting_profile")),
    ):
        if value:
            evidence.append(
                {
                    "evidence_type": "industry_metadata",
                    "case_id": case.get("case_id"),
                    "ticker": ticker,
                    "field": field,
                    "value": value,
                    "source_mode": company.get("source_mode") or case.get("registry_mode") or "registered_case",
                }
            )

    matched_financial = next((term for term in FINANCIAL_KEYWORDS if term in normalized_name or term in normalized_metadata), None)
    matched_conditional = next((term for term in CONDITIONAL_KEYWORDS if term in normalized_name or term in normalized_metadata), None)
    matched_energy = next((term for term in ENERGY_KEYWORDS if term in normalized_name or term in normalized_metadata), None)

    if matched_financial:
        fit_level = "not_applicable"
        family = "financial"
        reporting_profile = "FINANCIAL_INSTITUTION"
        allowed_rules: list[str] = []
        blocked_rules = selected_rules
        reason_codes = ["FINANCIAL_INDUSTRY_RULE_SCOPE"]
        rationale = f"公司名称命中金融行业关键词“{matched_financial}”；当前 R1/R2 不是金融专用规则。"
    elif matched_conditional:
        fit_level = "conditional"
        family = "conditional_business"
        reporting_profile = "PRC_GAAP_NON_FINANCIAL_CONDITIONAL"
        allowed_rules = selected_rules
        blocked_rules = []
        reason_codes = ["CONDITIONAL_INDUSTRY_REVIEW"]
        rationale = f"公司名称命中条件适用行业关键词“{matched_conditional}”；规则可以预筛，但字段映射和口径限制必须保留。"
    elif matched_energy:
        fit_level = "direct"
        family = "energy"
        reporting_profile = "PRC_GAAP_NON_FINANCIAL"
        allowed_rules = selected_rules
        blocked_rules = []
        reason_codes = ["NON_FINANCIAL_STATEMENTS", "ENERGY_COMPANY_METADATA_HINT"]
        rationale = f"公司名称命中非金融企业关键词“{matched_energy}”；当前规则可进入字段校验。"
    elif name and (ticker or case.get("sample_type") == "synthetic"):
        fit_level = "direct"
        family = "general_business"
        reporting_profile = "PRC_GAAP_NON_FINANCIAL"
        allowed_rules = selected_rules
        blocked_rules = []
        reason_codes = ["NON_FINANCIAL_DEFAULT_SCOPE", "INDUSTRY_METADATA_NOT_EXPLICIT"]
        if case.get("sample_type") == "synthetic":
            reason_codes.append("SYNTHETIC_TEST_SCOPE")
        rationale = "未命中金融或条件适用关键词；先按普通非金融企业进入字段闸门，行业结论仍不是专业判断。"
    else:
        fit_level = "unknown"
        family = "unknown"
        reporting_profile = "UNKNOWN"
        allowed_rules = []
        blocked_rules = selected_rules
        reason_codes = ["INSUFFICIENT_COMPANY_METADATA"]
        rationale = "公司名称或证券代码不足，系统不猜测行业，也不放行当前数值规则。"

    return {
        "gate_version": INDUSTRY_GATE_VERSION,
        "industry_family": family,
        "reporting_profile": reporting_profile,
        "fit_level": fit_level,
        "allowed_rules": allowed_rules,
        "blocked_rules": blocked_rules,
        "required_fields": {rule_id: RULE_FIELDS.get(rule_id, []) for rule_id in selected_rules},
        "reason_codes": reason_codes,
        "rationale": rationale,
        "confidence": "metadata_heuristic" if fit_level != "unknown" else "insufficient_metadata",
        "evidence": evidence,
    }


def build_not_applicable_context(
    *,
    case: dict[str, Any],
    current_year: int,
    rule_ids: Iterable[str],
    gate: dict[str, Any],
) -> dict[str, Any]:
    """为不适用行业构造不依赖 R1 财务字段的公开预筛上下文。"""

    selected_rules = list(rule_ids)
    report_years = sorted(case.get("available_report_years") or case.get("available_years") or [], reverse=True)
    previous_year = current_year - 1
    return {
        "case_id": case["case_id"],
        "company_name": case.get("company_name") or case.get("company_alias") or "",
        "company_alias": case.get("company_alias") or case.get("company_name") or "",
        "ticker": case.get("ticker"),
        "current_year": current_year,
        "previous_year": previous_year,
        "prior_year": current_year - 2 if current_year - 2 in report_years else None,
        "t0": case.get("t0"),
        "currency": case.get("currency", "CNY"),
        "amount_unit": case.get("amount_unit", "元"),
        "statement_scope": case.get("statement_scope", "合并"),
        "sample_type": case.get("sample_type", "public"),
        "model_transfer_allowed": bool(case.get("model_transfer_allowed")),
        "source_snapshot_id": case.get("source_snapshot_id"),
        "three_year_r1_ready": False,
        "public_prescreen": True,
        "industry_gate": deepcopy(gate),
        "prescreen_plan": {
            "mode": "public_prescreen",
            "requested_current_year": current_year,
            "analysis_current_year": current_year,
            "analysis_previous_year": previous_year,
            "analysis_years": [year for year in (current_year, previous_year) if year in report_years] or [current_year],
            "rule_plans": {},
            "skipped_rules": [
                {
                    "rule_id": rule_id,
                    "reason": gate["rationale"],
                    "required_fields": gate["required_fields"].get(rule_id, []),
                }
                for rule_id in selected_rules
            ],
            "missing_fields": [],
            "has_calculable_rule": False,
            "source_candidate_count": 0,
            "human_confirmation": "industry_specialized_rule_required",
            "confidence": gate["confidence"],
        },
    }
