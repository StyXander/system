"""行业专用工程预筛规则。

本模块只做可回查字段上的确定性计算，不把行业草案包装成审计结论。
每条规则都返回字段证据、资料缺口、阈值版本和人工复核边界，便于前端
直接展示，也便于后续由专业人员逐项签字或替换阈值。
行业专用规则只在行业闸门明确给出规则键后运行，不能根据字段名称自行猜测。
规则配置返回深拷贝，单次请求调整不得污染全局工程阈值。
规则版本明确标记为草案，代码可运行不等于阈值已经专业签署。
字段协议区分金额与比例，比例字段不能套用金额单位倍率。
比例数值保存为百分比点，规则差额同样以百分点解释。
金额字段必须保留案例声明单位，规则层不做隐含币种或数量级换算。
行业字段词表只帮助定位候选，不能证明找到的数字就是正确报表项目。
每个必需字段都要同时具备本期和连续上期，缺一项就进入资料缺口。
可选字段只增强趋势信息，缺失时不能把基础规则改写为技术失败。
字段映射以字段类别和年度为键，不依赖 PDF 扫描返回的偶然顺序。
重复字段采用第一条已登记记录，前置校验应阻止含糊的多候选进入规则。
非有限数值统一视为缺失，避免 NaN 或无穷值污染比较结果。
增长率只有前后期均为有限数值且上期非零时才允许计算。
增长分母使用上期绝对值，使负基数场景保留方向但仍需人工解释。
上期为零时不返回无穷增长率，资料报告必须明确不可计算。
证据卡只复制回查所需字段，避免把整页原文扩散到规则摘要。
证据编号、文档编号、页码和文件哈希共同构成回查链条。
来源复核状态随证据卡保留，规则命中不得自动把状态提升为已核实。
披露日晚于请求时点的字段会被排除，未来信息不能进入当期预筛。
字段年度晚于请求年度同样被排除，不能用新期间填补旧期间缺口。
实际分析年度取时点内最新可用年度，并显式返回与请求年度的差异。
上期固定为分析年度减一，不能为了凑齐数据跳过断档年度。
三年趋势只在更早连续年度存在时标记可用，不以任意三个年份代替。
来源技术问题与字段资料缺口使用不同状态，页面不得合并解释。
来源问题存在时停止指标计算，避免在坏原件上生成看似精确的结果。
来源通过但字段不全时返回资料缺口，不能错误标成规则未触发。
资料齐全后才比较工程阈值，命中结果仍只是待核查候选。
未命中只表示当前指标没有越过草案阈值，不表示企业不存在风险。
工程阈值随结果返回，复核人能够看到触发判断使用的具体版本。
专业签署状态固定保留为待确认，程序运行不能替专业人员签字。
能源采矿规则比较应收账款与营业收入增速，仍沿用登记字段口径。
能源行业关键词不会改变 R1 数学含义，只决定是否展示行业专用说明。
建设地产规则同时观察合同资产、长期应收款和合同负债的趋势偏离。
合同负债下降信号还要求收入未下降，避免孤立负债变化触发误解。
建设项目结算周期复杂，任何趋势候选都必须回查具体项目和合同条款。
银行规则比较贷款与利息收入增长，并观察不良率和拨备覆盖率变化。
不良率上升和拨备覆盖率下降使用百分点阈值，不使用同比百分比。
贷款质量指标来自金融报表专用口径，不能由普通应收账款字段替代。
保险规则比较赔付和负债相对保险收入的趋势，并观察服务结果符号。
保险服务结果为负只形成工程信号，不能直接解释为偿付能力结论。
保险合同负债与普通合同负债含义不同，两类字段不能交叉复用。
券商规则比较两融资产、减值准备和佣金收入趋势，不扩展到客户适当性判断。
两融资产与佣金偏离需要业务结构明细解释，程序不能推断客户信用质量。
减值增长信号必须结合计提与转回明细，不能单凭增速作定性表述。
资料索取清单来自规则配置，并在字段缺失时增加官方原文定位要求。
索取建议只描述需要取得的材料，不声称材料一定存在或已经取得。
资料清单去重保持原有顺序，便于前端稳定展示和回归比较。
指标理由使用受控表述，避免出现舞弊、违法或审计意见等越权措辞。
返回结果同时包含请求时点和请求年度，便于发现自动降级的实际期间。
规则结果不修改案例字段，也不把候选写回人工确认记录。
新增行业规则必须定义字段类型、必需字段、阈值和资料索取边界。
修改字段口径或阈值必须提升规则版本，并补齐命中与缺口回归测试。
任何行业规则成功都只证明确定性计算完成，不证明专业判断正确。
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Iterable


INDUSTRY_RULES_VERSION = "industry_rules_v1-draft"


# ``field_kind`` 是案例字段协议的一部分；amount 表示需要明确金额单位，
# ratio 表示以百分比点保存，不在提取时乘金额倍率。
SPECIALIZED_FIELD_CONFIG: dict[str, dict[str, Any]] = {
    "contract_assets": {
        "terms": ["合同资产"],
        "hints": ["资产负债表", "合同资产", "建筑业"],
        "basis": "reported",
        "value_type": "amount",
    },
    "long_term_receivables": {
        "terms": ["长期应收款"],
        "hints": ["资产负债表", "长期应收款", "分期收款"],
        "basis": "reported",
        "value_type": "amount",
    },
    "contract_liabilities": {
        "terms": ["合同负债"],
        "hints": ["资产负债表", "合同负债", "预收"],
        "basis": "reported",
        "value_type": "amount",
    },
    "loan_balance": {
        "terms": ["贷款总额", "发放贷款和垫款", "贷款余额", "客户贷款"],
        "hints": ["贷款", "发放贷款和垫款", "资产负债表"],
        "basis": "reported",
        "value_type": "amount",
    },
    "interest_income": {
        "terms": ["利息收入"],
        "hints": ["利润表", "利息收入", "净利息收入"],
        "basis": "reported",
        "value_type": "amount",
    },
    "nonperforming_loan_ratio": {
        "terms": ["不良贷款率", "不良率"],
        "hints": ["不良贷款", "监管指标", "主要监管指标"],
        "basis": "reported",
        "value_type": "ratio",
    },
    "provision_coverage_ratio": {
        "terms": ["拨备覆盖率"],
        "hints": ["拨备", "监管指标", "主要监管指标"],
        "basis": "reported",
        "value_type": "ratio",
    },
    "insurance_revenue": {
        "terms": ["保险服务收入", "保险业务收入", "保险收入"],
        "hints": ["保险服务收入", "保险业务", "利润表"],
        "basis": "reported",
        "value_type": "amount",
    },
    "insurance_service_result": {
        "terms": ["保险服务业绩", "保险服务结果", "保险服务费用"],
        "hints": ["保险服务结果", "保险服务业绩", "利润表"],
        "basis": "reported",
        "value_type": "amount",
    },
    "claims_expense": {
        "terms": ["赔付支出", "赔款支出", "保险服务费用"],
        "hints": ["赔付", "保险服务费用", "利润表"],
        "basis": "reported",
        "value_type": "amount",
    },
    "insurance_liabilities": {
        "terms": ["保险合同负债", "保险负债", "未到期责任准备金"],
        "hints": ["保险合同负债", "保险负债", "负债"],
        "basis": "reported",
        "value_type": "amount",
    },
    "commission_income": {
        "terms": ["手续费及佣金收入", "手续费佣金收入"],
        "hints": ["手续费及佣金", "利润表", "证券经纪"],
        "basis": "reported",
        "value_type": "amount",
    },
    "margin_financing_assets": {
        "terms": ["融出资金", "融资融券", "两融余额"],
        "hints": ["融出资金", "融资融券", "信用业务"],
        "basis": "reported",
        "value_type": "amount",
    },
    "impairment_provision": {
        "terms": ["资产减值损失", "信用减值损失", "减值准备"],
        "hints": ["减值", "信用减值", "利润表"],
        "basis": "reported",
        "value_type": "amount",
    },
    # 能源/矿业规则把坏账准备和应收账款净额列为可选增强字段。
    # 它们不是每家公司的统一报表项目，因此缺失只能形成 optional_missing，
    # 不能因为规则词表漏项而让整条字段提取流程抛出 KeyError。
    "accounts_receivable_allowance": {
        "terms": ["应收账款坏账准备", "应收账款减值准备", "坏账准备"],
        "hints": ["应收账款", "坏账准备", "减值准备"],
        "basis": "reported",
        "value_type": "amount",
    },
    "accounts_receivable_net": {
        "terms": ["应收账款净额", "应收账款账面价值"],
        "hints": ["应收账款", "资产负债表", "账面价值"],
        "basis": "net",
        "value_type": "amount",
    },
}


SPECIALIZED_RULE_SPECS: dict[str, dict[str, Any]] = {
    "energy_mining_ar_revenue": {
        "industry_family": "energy_mining",
        "rule_id": "IND-ENERGY-AR-REV",
        "rule_name": "能源/矿业应收—收入口径增强预筛",
        "required_fields": ("revenue", "accounts_receivable"),
        "optional_fields": ("accounts_receivable_allowance", "accounts_receivable_net"),
        "thresholds": {"growth_gap": 0.15, "basis_required": True},
        "requested_materials": ["应收账款附注明细及坏账准备变动", "收入确认政策与重大客户结算资料"],
    },
    "construction_real_estate_contract_cycle": {
        "industry_family": "construction_real_estate",
        "rule_id": "IND-CONSTRUCTION-CONTRACT-CYCLE",
        "rule_name": "建筑/地产合同结算循环联合预筛",
        "required_fields": (
            "revenue",
            "accounts_receivable",
            "contract_assets",
            "long_term_receivables",
            "contract_liabilities",
        ),
        "optional_fields": (),
        "thresholds": {"growth_deviation": 0.15, "contract_liability_decline": -0.15},
        "requested_materials": ["合同资产和长期应收款明细", "合同负债结转及收入确认资料", "主要项目结算与回款资料"],
    },
    "banking_credit_quality": {
        "industry_family": "banking",
        "rule_id": "IND-BANK-CREDIT-QUALITY",
        "rule_name": "银行信贷质量趋势预筛",
        "required_fields": ("loan_balance", "interest_income", "nonperforming_loan_ratio", "provision_coverage_ratio"),
        "optional_fields": (),
        "thresholds": {"loan_interest_growth_gap": 0.15, "npl_rise_pp": 1.0, "coverage_decline_pp": -10.0},
        "requested_materials": ["贷款五级分类及迁徙表", "不良贷款和拨备计提明细", "利息收入与贷款结构明细"],
    },
    "insurance_service_result": {
        "industry_family": "insurance",
        "rule_id": "IND-INSURANCE-SERVICE",
        "rule_name": "保险服务结果与负债趋势预筛",
        "required_fields": ("insurance_revenue", "insurance_service_result", "claims_expense", "insurance_liabilities"),
        "optional_fields": (),
        "thresholds": {"claims_revenue_growth_gap": 0.15, "liability_revenue_growth_gap": 0.15, "negative_service_result": True},
        "requested_materials": ["保险合同负债和准备金滚动表", "赔付/费用明细及再保险资料", "保险服务结果勾稽表"],
    },
    "securities_margin_commission": {
        "industry_family": "securities",
        "rule_id": "IND-SECURITIES-MARGIN-COMMISSION",
        "rule_name": "券商佣金与两融资产趋势预筛",
        "required_fields": ("commission_income", "margin_financing_assets", "impairment_provision"),
        "optional_fields": (),
        "thresholds": {"margin_commission_growth_gap": 0.15, "impairment_growth_gap": 0.15},
        "requested_materials": ["经纪及两融业务收入明细", "融出资金和客户信用风险明细", "减值/拨备计提及转回明细"],
    },
}


def get_specialized_spec(rule_key: str | None) -> dict[str, Any] | None:
    """返回副本，避免请求处理过程修改全局规则配置。"""

    if not rule_key or rule_key not in SPECIALIZED_RULE_SPECS:
        return None
    return deepcopy(SPECIALIZED_RULE_SPECS[rule_key])


def _finite(value: Any) -> float | None:
    """把候选值收敛为有限浮点数，拒绝 NaN、无穷值和坏类型。"""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _growth(current: Any, previous: Any) -> float | None:
    """仅在前后期均可用且基数非零时计算安全增长率。"""

    current_value = _finite(current)
    previous_value = _finite(previous)
    if current_value is None or previous_value in (None, 0.0):
        return None
    return (current_value - previous_value) / abs(previous_value)


def _evidence_card(row: dict[str, Any]) -> dict[str, Any]:
    """只复制可回查元数据，不把整页原文塞进专用规则摘要。"""

    return {
        key: row.get(key)
        for key in (
            "evidence_id",
            "field_id",
            "field_kind",
            "year",
            "value",
            "unit",
            "source_unit",
            "field_basis",
            "statement_scope",
            "document_id",
            "pdf_page",
            "print_page",
            "file_sha256",
            "source_sha256",
            "disclosure_date",
            "locator",
            "source_review_status",
        )
        if row.get(key) is not None
    }


def _available_row_map(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    """按字段和年度建立唯一映射，后续规则不再依赖输入顺序。"""

    mapped: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        kind = str(row.get("field_kind") or "")
        year = _finite(row.get("year"))
        if not kind or year is None:
            continue
        mapped.setdefault((kind, int(year)), row)
    return mapped


def _missing_materials(spec: dict[str, Any], gaps: list[str]) -> list[str]:
    """把规则资料缺口与预设索取清单合并为可操作建议。"""

    result = list(spec.get("requested_materials") or [])
    if gaps:
        result.insert(0, "缺失字段的官方年报原文、PDF页码、单位和报表口径说明")
    return list(dict.fromkeys(result))


def _evaluate_metrics(spec: dict[str, Any], values: dict[tuple[str, str], float | None]) -> tuple[bool, str, dict[str, float | int | str | bool | None]]:
    """按行业规则计算确定性指标，不把阈值命中提升为审计结论。"""

    family = spec["industry_family"]
    thresholds = spec["thresholds"]
    metrics: dict[str, float | int | str | bool | None] = {}

    def growth(kind: str) -> float | None:
        """读取同一字段的本期与上期数值并统一计算同比。"""

        value = _growth(values.get((kind, "current")), values.get((kind, "previous")))
        metrics[f"{kind}_growth"] = value
        return value

    if family == "energy_mining":
        revenue_growth = growth("revenue")
        ar_growth = growth("accounts_receivable")
        gap = ar_growth - revenue_growth if ar_growth is not None and revenue_growth is not None else None
        metrics["growth_gap"] = gap
        candidate = gap is not None and gap >= float(thresholds["growth_gap"])
        return candidate, "应收账款增速超过营业收入增速达到工程阈值。" if candidate else "当前应收—收入增速差未达到工程阈值。", metrics

    if family == "construction_real_estate":
        revenue_growth = growth("revenue")
        deviations: dict[str, float] = {}
        for kind in ("accounts_receivable", "contract_assets", "long_term_receivables", "contract_liabilities"):
            value = growth(kind)
            if value is not None and revenue_growth is not None:
                deviations[kind] = value - revenue_growth
            metrics[f"{kind}_growth_deviation"] = deviations.get(kind)
        max_deviation = max(deviations.values(), default=None)
        liabilities_growth = metrics.get("contract_liabilities_growth")
        metrics["max_receivable_growth_deviation"] = max_deviation
        candidate = bool(
            max_deviation is not None and max_deviation >= float(thresholds["growth_deviation"])
        ) or bool(
            isinstance(liabilities_growth, (int, float))
            and liabilities_growth <= float(thresholds["contract_liability_decline"])
            and isinstance(revenue_growth, (int, float))
            and revenue_growth >= 0
        )
        return candidate, "合同循环相关资产/负债与收入趋势出现工程偏离。" if candidate else "合同循环相关趋势未达到工程阈值。", metrics

    if family == "banking":
        loan_growth = growth("loan_balance")
        interest_growth = growth("interest_income")
        gap = loan_growth - interest_growth if loan_growth is not None and interest_growth is not None else None
        npl_delta = None
        coverage_delta = None
        if values.get(("nonperforming_loan_ratio", "current")) is not None and values.get(("nonperforming_loan_ratio", "previous")) is not None:
            npl_delta = values[("nonperforming_loan_ratio", "current")] - values[("nonperforming_loan_ratio", "previous")]
        if values.get(("provision_coverage_ratio", "current")) is not None and values.get(("provision_coverage_ratio", "previous")) is not None:
            coverage_delta = values[("provision_coverage_ratio", "current")] - values[("provision_coverage_ratio", "previous")]
        metrics.update({"loan_interest_growth_gap": gap, "npl_ratio_delta_pp": npl_delta, "coverage_ratio_delta_pp": coverage_delta})
        candidate = bool(gap is not None and gap >= float(thresholds["loan_interest_growth_gap"]))
        candidate = candidate or bool(npl_delta is not None and npl_delta >= float(thresholds["npl_rise_pp"]))
        candidate = candidate or bool(coverage_delta is not None and coverage_delta <= float(thresholds["coverage_decline_pp"]))
        return candidate, "贷款、资产质量或拨备覆盖趋势出现工程预筛信号。" if candidate else "贷款、资产质量和拨备覆盖趋势未达到工程阈值。", metrics

    if family == "insurance":
        revenue_growth = growth("insurance_revenue")
        claims_growth = growth("claims_expense")
        liabilities_growth = growth("insurance_liabilities")
        claims_gap = claims_growth - revenue_growth if claims_growth is not None and revenue_growth is not None else None
        liabilities_gap = liabilities_growth - revenue_growth if liabilities_growth is not None and revenue_growth is not None else None
        service_result = _finite(values.get(("insurance_service_result", "current")))
        metrics.update({"claims_revenue_growth_gap": claims_gap, "liability_revenue_growth_gap": liabilities_gap, "insurance_service_result_current": service_result})
        candidate = bool(claims_gap is not None and claims_gap >= float(thresholds["claims_revenue_growth_gap"]))
        candidate = candidate or bool(liabilities_gap is not None and liabilities_gap >= float(thresholds["liability_revenue_growth_gap"]))
        candidate = candidate or bool(service_result is not None and service_result < 0)
        return candidate, "赔付、保险负债或保险服务结果出现工程预筛信号。" if candidate else "保险服务结果与负债趋势未达到工程阈值。", metrics

    # securities
    commission_growth = growth("commission_income")
    margin_growth = growth("margin_financing_assets")
    impairment_growth = growth("impairment_provision")
    margin_gap = margin_growth - commission_growth if margin_growth is not None and commission_growth is not None else None
    impairment_gap = impairment_growth - commission_growth if impairment_growth is not None and commission_growth is not None else None
    metrics.update({"margin_commission_growth_gap": margin_gap, "impairment_commission_growth_gap": impairment_gap})
    candidate = bool(margin_gap is not None and margin_gap >= float(thresholds["margin_commission_growth_gap"]))
    candidate = candidate or bool(impairment_gap is not None and impairment_gap >= float(thresholds["impairment_growth_gap"]))
    return candidate, "两融相关资产或减值趋势与佣金收入出现工程偏离。" if candidate else "佣金、两融资产和减值趋势未达到工程阈值。", metrics


def build_industry_prescreen(
    *,
    gate: dict[str, Any],
    rows: Iterable[dict[str, Any]],
    current_year: int,
    t0: str,
    source_issues: Iterable[str] | None = None,
) -> dict[str, Any]:
    """计算一条行业专用预筛，并保持 DATA_GAP 与来源失败严格分离。"""

    spec = get_specialized_spec(gate.get("specialized_rule"))
    if spec is None:
        raise ValueError("行业闸门未提供可识别的专用规则。")
    all_rows = [deepcopy(row) for row in rows]
    source_issues_list = list(dict.fromkeys(str(item) for item in (source_issues or []) if item))
    eligible_rows = [
        row
        for row in all_rows
        if _finite(row.get("year")) is not None
        and int(float(row["year"])) <= int(current_year)
        and str(row.get("disclosure_date") or "") <= str(t0)
    ]
    row_map = _available_row_map(eligible_rows)
    years = sorted({year for _, year in row_map}, reverse=True)
    analysis_current_year = max(years, default=None)
    analysis_previous_year = analysis_current_year - 1 if analysis_current_year is not None else None
    analysis_prior_year = analysis_current_year - 2 if analysis_current_year is not None and analysis_current_year - 2 in years else None
    values: dict[tuple[str, str], float | None] = {}
    gaps: list[str] = []
    required_fields = list(spec["required_fields"])
    for kind in required_fields:
        for label, year in (("本期", analysis_current_year), ("上期", analysis_previous_year)):
            row = row_map.get((kind, year)) if year is not None else None
            if row is None:
                gaps.append(f"{year or '请求年度'}年缺少{kind}（{label}）字段")
                continue
            value = _finite(row.get("value"))
            if value is None:
                gaps.append(f"{year}年{kind}不是有限数值")
                continue
            if not row.get("field_basis"):
                gaps.append(f"{year}年{kind}口径未登记")
            values[(kind, "current" if label == "本期" else "previous")] = value
    # 可选字段只进入证据卡和增强信息，不会把基础规则无声升级成失败。
    for kind in spec.get("optional_fields") or []:
        for label, year in (("current", analysis_current_year), ("previous", analysis_previous_year), ("prior", analysis_prior_year)):
            row = row_map.get((kind, year)) if year is not None else None
            if row is not None and _finite(row.get("value")) is not None:
                values[(kind, label)] = _finite(row.get("value"))
    evidence_rows = [row for row in eligible_rows if row.get("field_kind") in set(required_fields) | set(spec.get("optional_fields") or {})]
    evidence_rows.sort(key=lambda row: (int(row.get("year") or 0), str(row.get("field_kind") or "")), reverse=True)
    evidence = [_evidence_card(row) for row in evidence_rows]
    evidence_ids = [str(item["evidence_id"]) for item in evidence if item.get("evidence_id")]
    source_validation = {
        "status": "failed" if source_issues_list else "passed",
        "issues": source_issues_list,
        "review_boundary": "程序只完成来源存在性、哈希、日期与结构检查；专业口径仍待人工确认。",
    }
    if source_issues_list:
        status = "SOURCE_INCOMPLETE"
        rationale = "来源技术校验未通过，行业专用预筛未继续计算。"
        metrics: dict[str, float | int | str | bool | None] = {}
    elif gaps:
        status = "DATA_GAP"
        rationale = "来源技术校验通过，但行业专用规则所需字段或口径存在资料缺口。"
        metrics = {}
    else:
        candidate, rationale, metrics = _evaluate_metrics(spec, values)
        status = "candidate" if candidate else "RULE_NOT_TRIGGERED"
    if analysis_prior_year is not None:
        metrics["three_year_trend_available"] = True
    else:
        metrics["three_year_trend_available"] = False
    return {
        "status": status,
        "screening_status": status,
        "industry_family": spec["industry_family"],
        "industry_rule_id": spec["rule_id"],
        "industry_rule_name": spec["rule_name"],
        "industry_rule_version": INDUSTRY_RULES_VERSION,
        "analysis_current_year": analysis_current_year,
        "analysis_previous_year": analysis_previous_year,
        "analysis_prior_year": analysis_prior_year,
        "analysis_years": [year for year in (analysis_current_year, analysis_previous_year, analysis_prior_year) if year is not None],
        "configured_thresholds": {**deepcopy(spec["thresholds"]), "professional_review_status": "draft_pending_professional_signoff"},
        "metrics": metrics,
        "field_evidence": evidence,
        "evidence_ids": evidence_ids,
        "source_validation": source_validation,
        "data_gaps": list(dict.fromkeys(gaps)),
        "requested_materials": _missing_materials(spec, gaps),
        "human_review_status": "pending",
        "professional_signoff_status": "draft_pending_professional_signoff",
        "rationale": rationale,
        "boundary": "这是行业专用工程草案筛查，不是审计认定；正式采用前必须由专业人员确认行业口径、字段和阈值。",
        "rule_not_triggered_boundary": "未形成程序候选不等于企业无风险。",
        "t0": t0,
        "requested_current_year": current_year,
    }
