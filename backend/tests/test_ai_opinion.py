"""历史兼容回归：AI意见层的确定性测试：容差、证据缺口、标签与模型合并边界。"""
from decimal import Decimal

from app.legacy_ai_opinion import build_opinions, merge_model_items, opinion_for_check, summarize_opinions
from app.judgment_layer import Materiality, compare
from app.connectivity_schemas import ComparisonCondition, EvidenceRef, RelationshipCheck, RelationshipMember


def _check(*, left, right, conditions, topic="environment", criteria="supported", calc_status="unexplained_difference"):
    return RelationshipCheck(
        check_id="C-1", rule_id="EQ-001", title="环保投入 2024（年报 vs ESG）", topic=topic,
        operator="equal",
        members=[RelationshipMember(occurrence_id="o1", role="left"), RelationshipMember(occurrence_id="o2", role="right")],
        conditions=conditions, criteria_status=criteria, calculation_status=calc_status,
        relationship_basis="text_statement",
        relationship_evidence=[EvidenceRef(occurrence_id="o1", quote="环保投入与上年同期可比")],
        calculation={"left": str(left), "right": str(right), "residual": str(left-right),
                     "normalized_unit": "元", "inputs": [{"dimension": "money"}]},
    )


def _conditions(scope="supported", subject="supported"):
    return [
        ComparisonCondition(name="主体", status=subject, reason="同一公司"),
        ComparisonCondition(name="期间", status="supported", reason="均为2024年"),
        ComparisonCondition(name="单位", status="supported", reason="均为元"),
        ComparisonCondition(name="范围", status=scope, reason="合并范围与母公司范围不一致"),
        ComparisonCondition(name="定义", status="supported", reason="均含环保设施运行费"),
    ]


def test_ratio_uses_percentage_point_materiality():
    """比例值已规范化为小数时，整体重要性应是 1 个百分点而不是 100%。"""
    materiality = Materiality.from_base(Decimal("1"))
    band = compare(Decimal("0.0486"), Decimal("0.0512"), materiality)
    assert band.grade == "MINOR"
    assert band.materiality.overall == Decimal("0.01")


def test_exact_match_is_consistent_and_high_confidence():
    opinion = opinion_for_check(_check(left=Decimal("100000"), right=Decimal("100000"),
                                      conditions=_conditions(), calc_status="consistent"))
    assert opinion["verdict"] == "CONSISTENT"
    assert opinion["score"] == 5.0
    assert opinion["needs_human"] is False


def test_scope_conflict_explains_but_still_needs_human():
    """口径冲突可以作为解释，但不能因此变成“同口径一致”。"""
    opinion = opinion_for_check(_check(left=Decimal("42180000"), right=Decimal("38980000"),
                                      conditions=_conditions(scope="conflicting"), criteria="conflicting",
                                      calc_status="not_comparable"))
    assert opinion["verdict"] == "EXPLAINABLE_DIFFERENCE"
    assert opinion["score"] == 61.88
    assert opinion["confidence"] == 0.539
    assert opinion["needs_human"] is True
    assert any(tag["code"] == "SCOPE_DRIFT" for tag in opinion["tags"])


def test_missing_prerequisites_never_return_none():
    """旧逻辑会整条卡死；新逻辑必须给出中等风险、证据不足与补查建议。"""
    opinion = opinion_for_check(_check(
        left=Decimal("58200"), right=Decimal("58600"),
        conditions=[ComparisonCondition(name=name, status="unknown", reason="原文未说明")
                    for name in ("主体", "期间", "单位", "范围")],
        criteria="unknown", calc_status="not_comparable"))
    assert opinion is not None
    assert opinion["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert opinion["score"] >= 40
    assert opinion["confidence"] <= 0.50
    assert opinion["needs_human"] is True
    assert opinion["recommended_actions"]


def test_model_cannot_overwrite_score_band_or_verdict():
    opinion = opinion_for_check(_check(left=Decimal("42180000"), right=Decimal("38980000"),
                                      conditions=_conditions(scope="conflicting"), criteria="conflicting",
                                      calc_status="not_comparable"))
    merged = merge_model_items([opinion], [{
        "check_id": "C-1", "verdict": "CONSISTENT", "headline": "模型认为没有问题",
        "rationale": ["口径不同"], "alternatives": ["另一可能"], "recommended_actions": ["补查"],
        "confidence": 0.99,
    }], "deepseek-v4-flash")
    assert merged[0]["score"] == 61.88
    assert merged[0]["band"]["label"] == "高"
    assert merged[0]["verdict"] == "EXPLAINABLE_DIFFERENCE"
    assert merged[0]["confidence"] <= 0.70
    assert merged[0]["generated_by"] == "llm"
    assert merged[0]["needs_human"] is True


def test_summary_counts_bands_and_human_reviews():
    opinion = opinion_for_check(_check(left=Decimal("100000"), right=Decimal("100000"),
                                      conditions=_conditions(), calc_status="consistent"))
    summary = summarize_opinions([opinion])
    assert summary["total"] == 1
    assert summary["bands"]["可忽略"] == 1