"""行业适配闸门。

闸门只做确定性的适配分流，不替代行业研究或专业判断：
普通非金融企业允许当前工程规则，金融企业默认跳过 R1/R2，
条件适用行业保留限制并继续由字段和人工复核决定是否采用。
行业判断优先使用登记元数据，名称关键词只是信息不足时的启发式信号。
启发式命中会随结果保存证据字段，不能包装成交易所正式行业分类。
公司名称和简称共同参与匹配，但空名称不会被猜测成普通非金融企业。
证券代码只帮助确认登记身份，本模块不维护代码到行业的外部映射。
文本归一化只移除排版符号，不执行可能改变企业含义的模糊分词。
关键词命中顺序属于受控规则协议，调整顺序必须补充歧义企业回归。
金融关键词优先阻断普通工商企业规则，防止把金融资产当作应收账款。
银行、保险和券商已有各自专用草案时，仍保持普通 R1/R2 为阻断状态。
金融专用规则可以继续形成行业预筛，但不能借此宣称普通规则适用。
融资租赁含有宽泛的租赁词，金融信号必须优先于建设地产匹配。
互联网金融同时含有平台或互联网词，也不能落入普通条件适用分支。
建设、房地产和物业只形成条件适用提示，不代表企业全部业务属于该行业。
能源采矿名称信号允许进入专用预筛，字段口径仍由后续规则单独校验。
普通非金融默认分支要求存在企业名称及代码或明确的合成样例标记。
信息不足时返回未知并阻断所选规则，不能为了流程完整而默认放行。
行业族、报表画像和适配级别必须相互一致，页面不能只读取其中一个字段。
允许规则与阻断规则由同一请求规则集合生成，避免遗漏用户选择的规则。
规则编号先去重再处理，重复请求不能产生重复的阻断或允许记录。
所需字段列表随规则返回，行业闸门本身不检查 PDF 中是否已经取得字段。
专用规则键只在实际采用该专用分支时返回，原始模糊候选不得泄漏给下游。
专用字段清单来自版本化规则配置，不能在闸门内另写一套不一致口径。
行业规则版本只在存在专用规则时返回，普通默认分支不伪造版本号。
理由码供程序稳定判断，中文说明只用于人工理解而不是控制流程。
解释文字必须说明关键词命中来源，避免展示无法复验的笼统行业判断。
置信度固定标明元数据启发式或信息不足，不使用虚构的小数概率。
闸门证据只复制登记元数据，不读取年报正文推断主营业务比例。
同一企业后续补充正式行业元数据时应重新计算闸门，不能永久沿用旧结果。
案例缓存中的旧闸门结果不能覆盖当前版本重新评估的确定性结果。
不适用上下文仍保留请求年度和公开来源计划，便于解释为什么跳过数值规则。
不适用不等于无需审计程序，只表示当前工程规则不能直接套用。
未知行业与明确金融不适用是不同状态，资料索取和页面提示必须区分。
条件适用允许继续提取候选字段，但正式采用必须复核行业特有结算口径。
合成样例只能用于测试默认分支，不能作为真实企业行业识别的先例。
新增关键词要评估包含关系，尤其避免短词先于更具体的金融词命中。
任何闸门放行都只是进入字段校验的许可，不是风险结论或审计意见。
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Iterable

from .industry_rules import INDUSTRY_RULES_VERSION, get_specialized_spec

INDUSTRY_GATE_VERSION = "industry_gate_v2"
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

SPECIALIZED_KEYWORDS = {
    "banking_credit_quality": ("银行",),
    "insurance_service_result": ("保险", "人寿", "财险", "中国人保", "中国太保", "中国太平"),
    "securities_margin_commission": ("证券", "券商", "申万宏源"),
    "construction_real_estate_contract_cycle": ("房地产", "建筑", "工程", "租赁", "物业"),
    "energy_mining_ar_revenue": ("能源", "石油", "石化", "海油", "煤炭", "电力", "燃气", "矿业"),
}

# 部分大型金融机构的简称不含“保险/银行/证券”（例如“中国平安”），
# 仅靠名称关键词会把已登记年报错误地降级为 not_applicable。证券代码是
# 巨潮公司身份的一部分，在名称缺少行业词时可作为受控补充证据；这里只放
# 已在官方案例清单中验证过的稳定映射，不允许客户端自行提交行业结论。
SPECIALIZED_TICKER_RULES = {
    "601318": "insurance_service_result",  # 中国平安
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

    matched_specialized: tuple[str, str] | None = None
    for rule_key, terms in SPECIALIZED_KEYWORDS.items():
        term = next((item for item in terms if item in normalized_name or item in normalized_metadata), None)
        if term:
            matched_specialized = (rule_key, term)
            break
    if matched_specialized is None:
        mapped_rule = SPECIALIZED_TICKER_RULES.get(ticker)
        if mapped_rule:
            matched_specialized = (mapped_rule, f"证券代码 {ticker} 的已验证行业映射")
    matched_financial = next((term for term in FINANCIAL_KEYWORDS if term in normalized_name or term in normalized_metadata), None)
    matched_conditional = next((term for term in CONDITIONAL_KEYWORDS if term in normalized_name or term in normalized_metadata), None)
    matched_energy = next((term for term in ENERGY_KEYWORDS if term in normalized_name or term in normalized_metadata), None)

    specialized_rule = matched_specialized[0] if matched_specialized else None
    specialized_spec = get_specialized_spec(specialized_rule)
    specialized_family = str((specialized_spec or {}).get("industry_family") or "")
    # “租赁”“工程”等词在普通企业名称里很宽，但“金融”“融资租赁”直接
    # 关系到是否允许套用工商企业 R1/R2。除银行/保险/券商已有明确专用规则外，
    # 金融信号优先失败关闭，不能先被较宽的非金融专用关键词截走。
    prefer_specialized = bool(
        matched_specialized
        and specialized_spec
        and (specialized_family in {"banking", "insurance", "securities"} or not matched_financial)
    )
    if prefer_specialized:
        rule_key, matched_term = matched_specialized
        family = specialized_family
        is_financial_specialized = family in {"banking", "insurance", "securities"}
        fit_level = "not_applicable" if is_financial_specialized else "conditional" if family == "construction_real_estate" else "direct"
        reporting_profile = "FINANCIAL_INSTITUTION" if is_financial_specialized else "PRC_GAAP_NON_FINANCIAL"
        allowed_rules = [] if is_financial_specialized else selected_rules
        blocked_rules = selected_rules if is_financial_specialized else []
        reason_codes = ["SPECIALIZED_INDUSTRY_RULE_REQUIRED", f"SPECIALIZED_{family.upper()}_METADATA_HINT"]
        rationale = f"公司元数据命中行业专用关键词“{matched_term}”；本次使用{specialized_spec['rule_name']}，不把 R1/R2 解释为该行业正式标准。"
    elif matched_financial:
        fit_level = "not_applicable"
        family = "financial"
        # 宽泛“租赁”虽命中建设地产词表，但金融优先分支没有可用专用规则；
        # 清空原始候选，避免下游看到 not_applicable 却仍误跑建设行业字段。
        specialized_rule = None
        specialized_spec = None
        reporting_profile = "FINANCIAL_INSTITUTION"
        allowed_rules = []
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
        "specialized_rule": specialized_rule,
        "specialized_required_fields": list((specialized_spec or {}).get("required_fields") or []),
        "specialized_optional_fields": list((specialized_spec or {}).get("optional_fields") or []),
        "industry_rule_version": INDUSTRY_RULES_VERSION if specialized_spec else None,
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
