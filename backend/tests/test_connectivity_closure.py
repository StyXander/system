"""反事实闭合推演的边界测试：预测不得反写结论，冲突不得预测闭合。

全部用合成输入，不引入任何企业数值。测试点对应四个真实风险：
把假设当结论、把冲突洗成缺口、把关系级缺口混进前提清单、以及默认路径被悄悄改动。
"""
from decimal import Decimal

import pytest

from app.connectivity_closure import (attach, attribution, build_closure, closure_probe,
                                      evidence_demands, structural_gaps, summarize)
from app.connectivity_engine import calculate
from app.connectivity_rules import RULES, required_conditions
from app.connectivity_schemas import (ComparisonCondition, DisclosureOccurrence, EvidenceRef,
                                      RelationshipCheck, RelationshipMember)

QUOTE = "原文明示完整且互不重叠的组成关系、单位和公式"


def relationship(rule="EQ-001", values=("100", "100"), roles=("left", "right"), units=None):
    operator = RULES[rule]["operator"]
    units = units or ["万元"] * len(values)
    documents = ["SYNTHETIC-AR" if role == "left" else "SYNTHETIC-ESG" if role == "right" else "SYNTHETIC"
                 for role in roles]
    rows = [DisclosureOccurrence(occurrence_id=f"SYN-{i}", document_id=documents[i], pdf_page=1,
            label=f"合成成员{i}", value=value, unit=unit, currency="CNY", year="2025",
            context=f"合成企业2025年，同一统计范围。{QUOTE}", row_header="合成企业2025年")
            for i, (value, unit) in enumerate(zip(values, units))]
    refs = [EvidenceRef(occurrence_id=rows[0].occurrence_id, quote=QUOTE)]
    check = RelationshipCheck(check_id="SYN-CHECK", rule_id=rule, title="独立合成关系", operator=operator,
        members=[RelationshipMember(occurrence_id=row.occurrence_id, role=role) for row, role in zip(rows, roles)],
        conditions=[ComparisonCondition(name=name, status="supported", reason="合成条件明确", evidence=refs)
                    for name in required_conditions(operator)],
        relationship_evidence=refs)
    return rows, check


def open_condition(check, name):
    for condition in check.conditions:
        if condition.name == name:
            condition.status = "unknown"
            condition.reason = "合成：该前提未获原文支持"
            condition.evidence = []
    return check


def test_default_calculate_is_unchanged_by_new_switches():
    """两个反事实开关默认关闭时，结果必须与显式传入空集合逐字段一致。"""
    rows, check = relationship()
    open_condition(check, "范围")
    baseline = calculate(check, rows)
    explicit = calculate(check, rows, assume_supported=set(), disregard_gaps=False)
    assert baseline.model_dump() == explicit.model_dump()
    # 门禁仍然生效：正式差额字段为空，试算单独存放。
    assert baseline.criteria_status == "unknown"
    assert baseline.calculation["residual"] is None
    assert baseline.hypothetical["hypothetical"] is True


def test_ceiling_reports_substantive_risk_when_numbers_differ():
    """数值本身矛盾时，补齐纸面前提也只能得到"仍然差钱"，必须判为实质风险。"""
    rows, check = relationship(values=("100", "105"))
    open_condition(check, "范围")
    block = build_closure(check, rows)
    assert block["ceiling"]["status"] == "would_still_differ"
    assert block["ceiling"]["is_assumption"] is True
    # 残差按归一量纲记录：5 万元 = 50000 元，不按显示单位冒充。
    assert Decimal(block["ceiling"]["residual"]) == Decimal("-50000")
    assert block["ceiling"]["normalized_unit"] == "元"
    assert block["tier"] == "substantive_risk"
    assert block["demands"] and block["demands"][0]["condition"] == "范围"


def test_ceiling_reports_formal_gap_when_numbers_match():
    """数值一致、只缺范围原文时，缺口是形式证据，不是实质差异。"""
    rows, check = relationship(values=("100", "100"))
    open_condition(check, "范围")
    block = build_closure(check, rows)
    assert block["ceiling"]["status"] == "would_confirm"
    assert block["tier"] == "formal_gap"


def test_ceiling_follows_engine_verdict_ladder_not_its_own(monkeypatch):
    """引擎判定为"仅显示精度相容"时，上限预测不得升级为"仍差钱"。

    这是一条契约测试：推演若用自己的映射重推结论，会把显示精度量级的差异
    报成实质差异，直接制造假警报。此处直接钉住映射关系，不依赖具体数值构造。
    """
    from app import connectivity_closure as closure_module

    rows, check = relationship(values=("100", "105"))
    open_condition(check, "范围")
    for level, expected in (
        ("assumption_compatible", "would_confirm_conditionally"),
        ("formal_consistent", "would_confirm"),
        ("unexplained_difference", "would_still_differ"),
        ("insufficient_basis", "not_executable"),
    ):
        probe = calculate(check, rows)
        probe.conclusion_level = level
        probe.calculation = {"residual": "0"}
        monkeypatch.setattr(closure_module, "calculate_with_gaps_ignored", lambda *a, **k: probe)
        assert closure_module.closure_probe(check, rows)["status"] == expected, level
    # 引擎结论阶梯的每个取值都必须有映射，新增级别不得静默落到不可执行。
    from app.connectivity_closure import CONCLUSION_TO_CEILING
    assert {"formal_consistent", "assumption_compatible", "unexplained_difference",
            "insufficient_basis", "limited_support", "not_applicable"} <= set(CONCLUSION_TO_CEILING)


def test_tier_uses_conclusion_level_after_for_supported_relations():
    rows, check = relationship(values=("100", "100"))
    block = build_closure(calculate(check, rows), rows)
    assert block["tier"] == "closed"
    assert block["ceiling"]["status"] == "would_confirm"


def test_relation_scope_separates_same_document_from_cross_document():
    """同报告多位置与跨报告差额性质不同，必须分开登记，否则风险来源被误读。"""
    rows, check = relationship(values=("100", "105"))
    open_condition(check, "范围")
    cross = build_closure(calculate(check, rows), rows)
    assert cross["relation_scope"] == "cross_document"
    # 把两个成员挪到同一文档：引擎会拒绝同文档同值关系，因此直接检查同文档分支的标记来源。
    same = check.model_copy(deep=True)
    same.cross_document = False
    block = build_closure(same, rows)
    assert block["relation_scope"] == "same_document"
    assert "同报告" in block["relation_scope_note"]


def test_precision_covered_difference_is_not_reported_as_substantive():
    """差额落在显示精度区间内时，不得报成实质差异。

    引擎在"未声明舍入方法"时把点值差额一律记为未解释，这是严格口径；
    推演层若照搬就会把 0.01 亿元精度的舍入差报成实质差异，制造假警报。
    """
    rows, check = relationship(values=("449183817.50", "4.49"), units=["元", "亿元"])
    open_condition(check, "范围")
    block = build_closure(check, rows)
    assert block["ceiling"]["status"] == "would_still_differ"
    assert block["ceiling"]["precision_assumption"] == "contains_zero"
    assert block["tier"] == "formal_gap"
    assert "显示精度" in block["tier_reason"]


def test_conflict_cannot_be_forecast_as_closure():
    """前提明确冲突时不得给出任何闭合预测，档位固定为不可执行。"""
    rows, check = relationship(values=("100", "100"))
    for condition in check.conditions:
        if condition.name == "单位":
            condition.status = "conflicting"
            condition.reason = "合成：单位声明互相矛盾"
    blocked = calculate(check, rows)
    assert blocked.criteria_status == "conflicting"
    ceiling = closure_probe(blocked, rows)
    assert ceiling["status"] == "conflicting"
    assert build_closure(blocked, rows)["tier"] == "blocked"


def test_single_point_is_sufficient_only_when_it_is_the_last_gap():
    """只缺一项时，单独补这一项即可打开闸门；缺两项时任何单项都不足够。"""
    rows, check = relationship(values=("100", "100"))
    open_condition(check, "范围")
    one_gap = build_closure(check, rows)
    assert [item["condition"] for item in one_gap["single_point"]] == ["范围"]
    assert one_gap["single_point"][0]["sufficient_alone"] is True
    assert one_gap["single_point_only"] == 1

    open_condition(check, "定义")
    two_gaps = build_closure(check, rows)
    assert two_gaps["demand_count"] == 2
    assert two_gaps["single_point_only"] == 0
    assert all(item["sufficient_alone"] is False for item in two_gaps["single_point"])
    # 缺两项时单项补证的结论等级只能是有限支持，不能是正式一致。
    assert all(item["conclusion_after"] != "formal_consistent" for item in two_gaps["single_point"])


def test_demands_are_typed_and_follow_rule_order():
    rows, check = relationship(rule="RD-001", values=("100", "60", "40"),
                               roles=("total", "component", "component"))
    for condition in check.conditions:
        condition.status = "unknown"
        condition.reason = "合成：全部前提待证"
    demands = evidence_demands(check, rows)
    assert [item["condition"] for item in demands] == list(required_conditions("sum"))
    assert all(item["kind"] and item["procedure"] and item["search_terms"] for item in demands)
    assert all(item["blocks_formal"] is True for item in demands)
    # 需求身份必须稳定且唯一，便于页面与导出按同一 ID 追溯。
    assert len({item["demand_id"] for item in demands}) == len(demands)


def test_relationship_gap_is_structural_not_a_demand():
    """关系本身缺原文依据，不是"补一份定义"能解决的，必须单列。"""
    rows, check = relationship()
    check.relationship_basis = "auto_label_match"
    gaps = structural_gaps(calculate(check, rows))
    assert any("自动配对" in item for item in gaps)
    block = build_closure(calculate(check, rows), rows)
    assert all("自动配对" not in (demand["current_reason"] or "") for demand in block["demands"])


def test_attach_never_rewrites_formal_conclusion_fields():
    """核心红线：closure 只能新增派生字段，五个正式结论字段必须逐字不变。"""
    rows, check = relationship(values=("100", "105"))
    open_condition(check, "范围")
    plain = calculate(check, rows)
    with_closure = attach(plain, rows)
    for field in ("conclusion_level", "criteria_status", "calculation_status", "basis_level", "calculation"):
        assert getattr(with_closure, field) == getattr(plain, field), field
    assert with_closure.closure["version"]
    # 再次计算会重置 calculation，但不得重置 closure 之外的任何东西。
    assert with_closure.closure["ceiling"]["status"] == "would_still_differ"


def test_fabricated_condition_claim_still_produces_a_demand():
    """条件自称 supported 但引文无法回溯时，引擎降级回 unknown，需求清单必须保留。"""
    rows, check = relationship()
    for condition in check.conditions:
        if condition.name == "定义":
            condition.status = "supported"
            condition.evidence = [EvidenceRef(occurrence_id=rows[0].occurrence_id, quote="原文根本没有这句话")]
    recalculated = calculate(check, rows)
    assert recalculated.criteria_status == "unknown"
    demands = evidence_demands(recalculated, rows)
    assert "定义" in {item["condition"] for item in demands}
    assert build_closure(recalculated, rows)["tier"] in {"substantive_risk", "formal_gap"}


def test_attribution_marks_quantification_honestly():
    rows, check = relationship(values=("100", "105"))
    items = {item["mechanism"]: item for item in attribution(calculate(check, rows), rows)}
    assert items["unit"]["status"] == "excluded"
    # 整数成员不构造显示精度区间，因此舍入原因只能是"未量化"，不得给出伪区间。
    assert items["rounding"]["status"] == "pending"
    assert items["rounding"]["quantified"] is False
    # 定义与范围没有可量化边界，必须显式标注未量化，不得伪造区间。
    assert items["definition"]["quantified"] is False
    assert items["scope"]["quantified"] is False


def test_attribution_quantifies_rounding_only_when_decimals_exist():
    rows, check = relationship(values=("100.5", "100.6"))
    items = {item["mechanism"]: item for item in attribution(calculate(check, rows), rows)}
    assert items["rounding"]["quantified"] is True
    assert items["rounding"]["status"] in {"supported", "excluded"}


def test_summarize_uses_explicit_denominators():
    rows, check = relationship(values=("100", "105"))
    open_condition(check, "范围")
    risky = attach(calculate(check, rows), rows)
    rows2, check2 = relationship(values=("100", "100"))
    open_condition(check2, "范围")
    formal = attach(calculate(check2, rows2), rows2)
    summary = summarize([risky, formal])
    assert summary["relation_total"] == 2
    assert summary["substantive_risk_count"] == 1
    assert summary["formal_gap_count"] == 1
    assert summary["tiers"]["substantive_risk"]["check_ids"] == ["SYN-CHECK"]
    assert summary["open_demand_by_condition"]["范围"] == 2
    assert "2 条关系" in summary["statement"]
