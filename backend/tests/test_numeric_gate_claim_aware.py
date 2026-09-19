"""D4 签字口径下的数字闸门验收：claim-aware 溯源四类硬门。

对应 2026-09-19 口径签字记录 §二 D4 的验收表：
T1 数字存在于本主张已绑定的 RAG 片段 → traced（source_type=rag_chunk）
T2 数字存在于其他 RAG 片段但本主张未绑定 → 仍然 unverified
T3 数字在任何 evidence 中都不存在 → unverified 且关键数字计数>0、passed=false
T4 数字来自结构化 field/metric value → 旧路径仍然 traced（回归保护）
"""

from __future__ import annotations

from backend.app.numeric_gate import build_numeric_claim_trace, validate_numeric_claims

BOUND_CHUNK = "RAG-CNINFO_000858_T0_20260430-2025-P0089-C00"
UNBOUND_CHUNK = "RAG-CNINFO_000858_T0_20260430-2025-P0010-C01"

# 真实案例里 rag_evidence 行的 value 恒为 None，数字只在 excerpt 中。
EVIDENCE_BUNDLE = {
    "field_evidence": [
        {"evidence_id": "FIELD-AR-2025", "field_label": "应收账款", "value": 1234567.89},
        {"evidence_id": "RAG-PLACEHOLDER", "field_label": "占位", "value": None},
    ],
    "rag_evidence": [
        {
            "evidence_id": BOUND_CHUNK,
            "pdf_page": 89,
            "value": None,
            "excerpt": "截至报告期末，应收账款账面余额为41,813,685.32元。",
        },
        {
            "evidence_id": UNBOUND_CHUNK,
            "pdf_page": 10,
            "value": None,
            "excerpt": "前五名客户销售额合计98,765,432.10元，占年度销售总额14.55%。",
        },
    ],
}

RULE_RESULTS = [
    {"rule_id": "R1", "metrics": {"revenue_growth": -0.5455, "ar_growth": 0.0107, "growth_gap": 0.5562}}
]


def _find(trace: list[dict], raw: str) -> dict:
    matched = [item for item in trace if item["raw"] == raw]
    assert matched, f"轨迹中缺少数字 {raw}"
    return matched[0]


def test_t1_number_in_claim_bound_rag_chunk_is_traced() -> None:
    """T1：主张确实绑定了该片段，其中的年报原文数字必须判为可追溯。"""
    result = validate_numeric_claims(
        "",
        rule_results=RULE_RESULTS,
        evidence_bundle=EVIDENCE_BUNDLE,
        claim_evidence_bindings=[
            {"text": "应收账款账面余额为41,813,685.32元。", "evidence_ids": [BOUND_CHUNK]}
        ],
    )
    row = _find(result["trace"], "41,813,685.32")
    assert row["verification_status"] == "traced"
    assert row["source_type"] == "rag_chunk"
    assert row["source"] == BOUND_CHUNK
    assert row["bound_by_claim"] is True
    assert result["validation_mode"] == "claim_scoped"
    assert result["key_unverified_count"] == 0
    assert result["passed"] is True


def test_t2_number_in_unbound_chunk_stays_unverified() -> None:
    """T2：数字真实存在于另一个片段，但本主张没有绑定它，仍然算无来源。"""
    result = validate_numeric_claims(
        "",
        rule_results=RULE_RESULTS,
        evidence_bundle=EVIDENCE_BUNDLE,
        claim_evidence_bindings=[
            {"text": "前五名客户销售额合计98,765,432.10元。", "evidence_ids": [BOUND_CHUNK]}
        ],
    )
    row = _find(result["trace"], "98,765,432.10")
    assert row["verification_status"] == "unverified_numeric_claim"
    assert row["source"] is None
    assert row["bound_by_claim"] is False
    assert result["key_unverified"] == ["98,765,432.10"]
    assert result["passed"] is False


def test_t2b_percentage_in_unbound_chunk_stays_unverified() -> None:
    """T2 补充：比例同样受绑定关系约束，不按整包文本白名单放行。"""
    result = validate_numeric_claims(
        "",
        rule_results=RULE_RESULTS,
        evidence_bundle=EVIDENCE_BUNDLE,
        claim_evidence_bindings=[
            {"text": "前五名客户销售额占比14.55%。", "evidence_ids": [BOUND_CHUNK]}
        ],
    )
    row = _find(result["trace"], "14.55%")
    assert row["verification_status"] == "unverified_numeric_claim"
    assert result["passed"] is False


def test_t3_invented_number_is_rejected_and_fail_closed() -> None:
    """T3：模型凭空写出的金额，即便绑定了片段也必须拒绝并判不完整。"""
    result = validate_numeric_claims(
        "",
        rule_results=RULE_RESULTS,
        evidence_bundle=EVIDENCE_BUNDLE,
        claim_evidence_bindings=[
            {"text": "其他应收款期末余额为55,555,555.55元。", "evidence_ids": [BOUND_CHUNK]}
        ],
    )
    row = _find(result["trace"], "55,555,555.55")
    assert row["verification_status"] == "unverified_numeric_claim"
    assert row["source"] is None
    assert result["key_unverified_count"] == 1
    assert result["passed"] is False


def test_t4_structured_field_and_metric_sources_still_trace() -> None:
    """T4：结构化 field/metric 旧路径不得被破坏，且不依赖任何片段绑定。"""
    result = validate_numeric_claims(
        "",
        rule_results=RULE_RESULTS,
        evidence_bundle=EVIDENCE_BUNDLE,
        claim_evidence_bindings=[
            # 该段刻意不绑定任何 evidence_id，只允许使用结构化来源。
            {"text": "应收账款为1,234,567.89元，增速差为55.62%。", "evidence_ids": []}
        ],
    )
    amount = _find(result["trace"], "1,234,567.89")
    assert amount["verification_status"] == "traced"
    assert amount["source_type"] == "evidence"
    assert amount["source"] == "FIELD-AR-2025"
    assert amount["bound_by_claim"] is False
    gap = _find(result["trace"], "55.62%")
    assert gap["verification_status"] == "traced"
    assert gap["source_type"] == "metric"
    assert gap["source"] == "R1.growth_gap"


def test_legacy_call_without_bindings_does_not_whitelist_rag_numbers() -> None:
    """收紧条件 4：不传绑定时沿用旧口径，RAG 原文数字一律不进全局白名单。"""
    trace = build_numeric_claim_trace(
        "应收账款账面余额为41,813,685.32元。",
        rule_results=RULE_RESULTS,
        evidence_bundle=EVIDENCE_BUNDLE,
    )
    row = _find(trace, "41,813,685.32")
    assert row["verification_status"] == "unverified_numeric_claim"
    assert row["source"] is None


def test_one_unverified_key_number_keeps_run_fail_closed() -> None:
    """收紧条件 5：同一次校验中只要有一个关键数字无来源，整体仍判不通过。"""
    result = validate_numeric_claims(
        "",
        rule_results=RULE_RESULTS,
        evidence_bundle=EVIDENCE_BUNDLE,
        claim_evidence_bindings=[
            {"text": "应收账款账面余额为41,813,685.32元。", "evidence_ids": [BOUND_CHUNK]},
            {"text": "合同负债余额为77,777,777.77元。", "evidence_ids": [BOUND_CHUNK]},
        ],
    )
    assert _find(result["trace"], "41,813,685.32")["verification_status"] == "traced"
    assert _find(result["trace"], "77,777,777.77")["verification_status"] == "unverified_numeric_claim"
    assert result["validated_segment_count"] == 2
    assert result["key_unverified"] == ["77,777,777.77"]
    assert result["passed"] is False


def test_binding_without_matching_row_is_not_a_source() -> None:
    """绑定了一个 evidence_id，但证据包里不存在对应片段行时不得凭空放行。"""
    result = validate_numeric_claims(
        "",
        rule_results=RULE_RESULTS,
        evidence_bundle=EVIDENCE_BUNDLE,
        claim_evidence_bindings=[
            {"text": "应收账款账面余额为41,813,685.32元。", "evidence_ids": ["RAG-NOT-IN-BUNDLE"]}
        ],
    )
    assert result["passed"] is False
    assert result["key_unverified_count"] == 1
