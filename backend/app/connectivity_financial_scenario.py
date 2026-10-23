"""财务风险传导情景模拟：企业披露原值与用户假设分列，结果可复算、可导出。

专业边界（必须随输出一起展示）：
- 已披露基础值必须带证据ID与报告页码；用户假设变量默认只是演示参数。
- 至少支持两个参数（价格、用量）与“基础/情景A/情景B”的可复算比较。
- 情景结果不是企业实际损失预测、不是审计调整、也不是业绩预测。
- 原文无法提供可分离基数时，只保留影响路径，不编造企业金额。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

VERSION = "financial_scenario_v3"

DEFAULT_PRICE_PROFILE = {"price_base": "850", "price_low": "700", "price_high": "1000"}
# 第二参数：用量（节能量实现比例）变动；默认情景A为价格上浮、情景B为用量增加。
USAGE_PROFILE = {"usage_base": "100", "usage_low": "80", "usage_high": "110"}


def _decimal(value) -> Decimal | None:
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _impact(tons: Decimal, price: Decimal, usage_pct: Decimal) -> Decimal:
    """情景影响 = 节能量 × 用量比例 × 价格假设；全程 Decimal，单位亿元。"""
    return tons * usage_pct / Decimal(100) * price / Decimal("100000000")


def build_scenario(bridge: dict) -> dict:
    """由 bridge 的绩效主张与财务节点构造受控情景；缺基数时诚实降级。"""
    profile = (bridge.get("profile") or {}).get("scenario") or {}
    if profile.get("kind") not in {"energy_cost", "water_cost"}:
        return {"version": VERSION, "available": False,
                "reason": "本行业配置暂无可复算的成本参数，保留证据路径而不伪造金额。"}
    price_unit = profile.get("price_unit", "元/吨")
    resource_label = "节水量" if profile.get("kind") == "water_cost" else "节能量"
    claims = bridge.get("claims", [])
    nodes = bridge.get("nodes", [])

    # 同时校验语态、物理量和计价单位；保留实际被选中的金额项。
    from .connectivity_claim_taxonomy import classify_claim
    resources = []
    for claim in claims:
        phase = claim.get("planned_or_realized") or classify_claim(claim.get("text", ""), claim.get("amounts"))["planned_or_realized"]
        if phase != "realized":
            continue
        for amount in claim.get("amounts", []):
            # 相同的立方米可表示沼气或水；必须核对数值附近的资源名与节约语义。
            import re
            text = str(claim.get("text", ""))
            offset = text.find(str(amount.get("text") or ""))
            prefix = text[max(0, offset - 32):offset] if offset >= 0 else ""
            resource_names = re.findall(r"沼气|天然气|废气|用水|水|标准煤|标煤", prefix)
            nearby = resource_names[-1] if resource_names else ""
            if amount.get("qualifier", "exact") != "exact":
                continue
            unit = amount.get("unit", "")
            valid_energy = (profile["kind"] == "energy_cost" and unit in {"吨标准煤", "吨标煤", "万吨标准煤", "万吨标煤"}
                            and "标准煤" in price_unit and bool(re.search(r"节能|节约|减少能耗", prefix)))
            valid_water = (profile["kind"] == "water_cost" and unit in {"立方米", "万立方米"} and "立方米" in price_unit
                           and nearby in {"水", "用水"} and bool(re.search(r"节水|节约用水|节约水量|减少用水", prefix)))
            quantity = _decimal(amount.get("normalized"))
            if (valid_energy or valid_water) and quantity is not None and quantity > 0:
                resources.append((quantity, claim, amount))
    selected = max(resources, key=lambda item: item[0], default=None)
    performance = selected[1] if selected else None
    cost_node = next((node for node in nodes if node.get("industry_role") == "operating_cost"), None)
    if not performance or not cost_node:
        return {"version": VERSION, "available": False,
                "reason": "缺少同资源口径、可定位的实绩节能量/节水量或营业成本基数，未生成金额情景。"}
    resource = selected[2]
    tons = _decimal(resource.get("normalized"))
    # 财务节点amounts中的normalized为元，显示单位不能再重复放大。
    cost_amount = next((item for item in cost_node.get("amounts", []) if item.get("dimension") == "money"), {})
    cost = _decimal(cost_amount.get("normalized", cost_node.get("value")))
    if tons is None or cost is None or cost <= 0:
        return {"version": VERSION, "available": False, "reason": "绩效值或营业成本无法转为数值。"}
    price_base = _decimal(profile.get("price_base", DEFAULT_PRICE_PROFILE["price_base"]))
    price_low = _decimal(profile.get("price_low", DEFAULT_PRICE_PROFILE["price_low"]))
    price_high = _decimal(profile.get("price_high", DEFAULT_PRICE_PROFILE["price_high"]))
    usage_base = _decimal(USAGE_PROFILE["usage_base"])
    usage_low = _decimal(USAGE_PROFILE["usage_low"])
    usage_high = _decimal(USAGE_PROFILE["usage_high"])
    if None in (price_base, price_low, price_high, usage_base, usage_low, usage_high):
        return {"version": VERSION, "available": False, "reason": "情景参数无效。"}

    def money(price: Decimal, usage_pct: Decimal) -> dict:
        value = _impact(tons, price, usage_pct)
        return {"value": f"{value:.2f}", "unit": "亿元",
                "share_of_cost": f"{(value * Decimal('100000000') / cost * 100):.4f}%"}

    base_price_value = _impact(tons, price_base, usage_base)
    # 情景A：仅价格变动（用量不变）；情景B：仅用量变动（价格不变）——单变量可归因。
    scenario_a = {"name": "情景A：价格上浮", **money(price_high, usage_base)}
    scenario_b = {"name": f"情景B：{resource_label}按低实现比例", **money(price_base, usage_low)}
    sensitivity = []
    for delta in ("-20", "-10", "0", "10", "20"):
        price = price_base * (Decimal(1) + Decimal(delta) / Decimal(100))
        usage = usage_base * (Decimal(1) + Decimal(delta) / Decimal(100))
        row = {"price_change": delta + "%", "usage_change": delta + "%",
               **money(price, usage_base), "two_param": money(price, usage)}
        sensitivity.append(row)
    return {
        "version": VERSION,
        "available": True,
        "mechanism": profile["kind"],
        "resource_label": resource_label,
        "industry": bridge.get("industry", ""),
        # 已披露企业基础值：证据身份必须保留，禁止与用户假设混写。
        "base": {"claim_id": performance["claim_id"], "document_id": performance["document_id"],
                 "pdf_page": performance["pdf_page"], "label": performance["text"][:160],
                 "value": resource.get("raw"), "unit": resource.get("unit"),
                 "normalized": str(tons), "provenance": "disclosed"},
        "target": {"node_id": cost_node["node_id"], "document_id": cost_node["document_id"],
                   "pdf_page": cost_node["pdf_page"], "label": cost_node["label"],
                   "value": cost_node["value"], "unit": cost_node["unit"],
                   "provenance": "disclosed"},
        # 用户假设变量：默认演示值，不是企业数据。
        "assumptions": [
            {"name": f"{profile.get('label', '价格')}（低/基准/高）", "kind": "user_assumption",
             "value": f"{profile.get('price_low')} / {profile.get('price_base')} / {profile.get('price_high')}",
             "unit": profile.get("price_unit", price_unit),
             "source": profile.get("source", "用户输入假设")},
            {"name": f"{resource_label}实现比例（低/基准/高）", "kind": "user_assumption",
             "value": f"{usage_low}% / {usage_base}% / {usage_high}%",
             "unit": "%", "source": f"用户输入假设：报告未逐项证明{resource_label}当期全部实现"},
        ],
        "formula": (f"情景影响 = {resource_label} {resource.get('raw')}{resource.get('unit')} × 用量比例 × "
                    f"价格假设（{price_unit}） ÷ 1亿元"),
        "baseline": {"name": "基础", **money(price_base, usage_base)},
        "parameters": {"price": {"value": str(price_base), "min": str(price_low), "max": str(price_high), "unit": price_unit},
                       "usage": {"value": str(usage_base), "min": "0", "max": "110", "unit": "%"}},
        "cost_normalized": str(cost),
        "scenarios": [scenario_a, scenario_b],
        "sensitivity": sensitivity,
        "sensitivity_range": {
            "price_low_value": f"{_impact(tons, price_low, usage_base):.2f}",
            "price_high_value": f"{_impact(tons, price_high, usage_base):.2f}",
            "usage_low_value": f"{_impact(tons, price_base, usage_low):.2f}",
            "usage_high_value": f"{_impact(tons, price_base, usage_high):.2f}",
            "unit": "亿元"},
        "affected_financial_statement_items": ["营业成本", "水费" if profile["kind"] == "water_cost" else "燃料及动力费"],
        "limitations": [
            f"{resource_label}取自ESG原文；是否已全部实现、是否对应本年度成本，报告未逐项证明",
            "未考虑能源结构变化、价格传导、产量波动与会计确认期间",
            "价格与实现比例为用户假设，不是企业实际采购价或执行率",
        ],
        "note": "情景模拟用于说明影响方向与量级，不是企业实际损失预测，不进入正式结论，也不是审计调整。",
    }


def recalculate_scenario(scenario: dict, price, usage) -> dict:
    """只在同源可量化基数上调整两个用户假设。

    单价与实现比例由界面传入，不能替换企业披露基数。
    原文数值、单位、文件编号和页码在计算副本中原样保留。
    非有限数值与越界输入直接拒绝，避免生成假成功结果。
    单价的计量单位由已验证的场景机制决定，用户不能任意改写。
    计算使用十进制，最终金额和比例分别按既定精度显示。
    单位换算只发生在受控计算函数内，不交给前端重新推导。
    结果仅表示假设条件下的敏感性，不进入正式核验结论。
    页面与所有导出调用同一函数，确保用户参数与结果一致。
    历史运行对象不变，更换参数不会篡改原始保存结果。
    """
    import copy
    if not scenario.get("available"):
        raise ValueError("本次情景缺少可量化基数")
    price_value, usage_value = _decimal(price), _decimal(usage)
    parameters = scenario.get("parameters", {})
    if price_value is None or usage_value is None:
        raise ValueError("价格和实现比例必须为有限十进制数")
    for key, value in (("price", price_value), ("usage", usage_value)):
        config = parameters.get(key, {})
        if value < Decimal(config.get("min", "0")) or value > Decimal(config.get("max", "110")):
            raise ValueError("情景参数超出允许范围")
    result = copy.deepcopy(scenario)
    quantity = Decimal(result["base"]["normalized"])
    money_value = _impact(quantity, price_value, usage_value)
    cost = Decimal(result["cost_normalized"])
    result["scenario_result"] = {"name": "用户情景", "value": f"{money_value:.2f}", "unit": "亿元",
                                 "share_of_cost": f"{money_value * Decimal('100000000') / cost * 100:.4f}%"}
    result["parameters"]["price"]["value"] = str(price_value)
    result["parameters"]["usage"]["value"] = str(usage_value)
    result["assumptions"] = [*result.get("assumptions", []),
        {"name": "本次用户情景", "kind": "user_assumption", "value": f"单价{price_value}，实现比例{usage_value}%", "source": "本次参数调整"}]
    return result
