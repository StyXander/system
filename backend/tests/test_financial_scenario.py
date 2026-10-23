"""情景模拟：原值与假设分列、双参数可复算、明确非预测边界。

合成样本只验证算式与门禁，不冒充任何企业事实。
"""
from __future__ import annotations

from decimal import Decimal

from backend.app.connectivity_financial_bridge import build
from backend.app.connectivity_financial_scenario import _impact, build_scenario
from backend.tests.test_financial_bridge import _docs, _pages


def _bridge():
    return build(None, documents=_docs(), pages=_pages(), industry="steel")


def test_scenario_disclosed_base_and_user_assumptions_are_separated():
    scenario = build_scenario(_bridge())
    assert scenario["available"] is True
    assert scenario["base"]["provenance"] == "disclosed"
    assert scenario["target"]["provenance"] == "disclosed"
    assert all(item["kind"] == "user_assumption" for item in scenario["assumptions"])
    assert scenario["base"]["value"] == "25.85"


def test_two_parameters_and_recomputable_scenarios():
    """两个参数、基础/情景A/情景B可复算；手动代入公式与输出一致。"""
    scenario = build_scenario(_bridge())
    tons = Decimal(scenario["base"]["normalized"])
    price_high = Decimal("1000")
    manual = _impact(tons, price_high, Decimal("100"))
    scenario_a = next(item for item in scenario["scenarios"] if "价格" in item["name"])
    # 输出按两位小数展示；比较前先以同一精度量化。
    assert Decimal(scenario_a["value"]) == manual.quantize(Decimal("0.01"))
    # 情景A与基础不同：参数拖动后结果确实变化。
    assert scenario_a["value"] != scenario["baseline"]["value"]
    assert len(scenario["sensitivity"]) == 5
    # 双参数行同时给出单参数与双参数结果。
    row = scenario["sensitivity"][0]
    assert "two_param" in row and "value" in row


def test_scenario_boundaries_are_explicit():
    scenario = build_scenario(_bridge())
    assert "不是企业实际损失预测" in scenario["note"]
    assert any("不是企业实际采购价" in item["source"] for item in scenario["assumptions"])
    assert scenario["affected_financial_statement_items"]


def test_scenario_unavailable_keeps_reason():
    bridge = _bridge()
    bridge["profile"]["scenario"]["kind"] = "none"
    scenario = build_scenario(bridge)
    assert scenario["available"] is False
    assert scenario["reason"]
