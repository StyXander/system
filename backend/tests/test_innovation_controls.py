"""四项审计专属增强的确定性合同测试。"""

from __future__ import annotations

from backend.app.anti_confirmation import build_anti_confirmation_record
from backend.app.coverage_matrix import build_assertion_evidence_procedure_matrix, load_audit_procedure_map
from backend.app.evidence_fitness import (
    ANALOGOUS_BACKGROUND,
    CURRENT_ENTITY,
    NORMATIVE_BASIS,
    annotate_evidence_bundle,
    enforce_claim_boundaries,
    fitness_map_for_evidence,
)
from backend.app.numeric_gate import validate_numeric_claims


def test_coverage_matrix_uses_registered_procedure_ids_only() -> None:
    rule_results = [
        {
            "rule_id": "R1",
            "risk_card": {"data_gaps": ["账龄结构"], "requested_materials": ["账龄明细表"]},
            "metrics": {"revenue_growth": -0.2, "ar_growth": 0.1},
        }
    ]
    evidence_bundle = {
        "field_evidence": [
            {"evidence_id": "REV-2025", "field_label": "营业收入", "value": 100},
            {"evidence_id": "AR-2025", "field_label": "应收账款", "value": 50},
        ]
    }
    matrix = build_assertion_evidence_procedure_matrix(
        case_id="CASE-1",
        current_year=2025,
        t0="2026-04-30",
        rule_ids=["R1"],
        rule_results=rule_results,
        evidence_bundle=evidence_bundle,
    )
    registered = {
        item.get("procedure_id")
        for item in (load_audit_procedure_map().get("procedures") or [])
        if isinstance(item, dict)
    }
    assert matrix
    assert all(set(row["procedure_ids"]) <= registered for row in matrix)
    assert all(row["source_of_row"] == "programmatic" for row in matrix)
    assert any(row["status"] in {"covered", "partially_covered", "gap"} for row in matrix)


def test_evidence_fitness_downgrades_background_supported_claim() -> None:
    bundle = annotate_evidence_bundle(
        {
            "field_evidence": [{"evidence_id": "FIELD-1", "field_label": "营业收入"}],
            "knowledge_evidence": [
                {"evidence_id": "KB-1", "source_category": "csrc_penalty"},
                {"evidence_id": "KB-2", "source_category": "auditing_standard"},
            ],
        }
    )
    mapping = fitness_map_for_evidence(bundle)
    assert mapping["FIELD-1"] == CURRENT_ENTITY
    assert mapping["KB-1"] == ANALOGOUS_BACKGROUND
    assert mapping["KB-2"] == NORMATIVE_BASIS
    claims = [{"text": "当前企业已存在同类问题", "evidence_ids": ["KB-1"], "support_status": "supported"}]
    violations = enforce_claim_boundaries(claims, mapping)
    assert violations
    assert claims[0]["support_status"] == "unverified_hypothesis"


def test_numeric_gate_traces_negative_percent_and_context_year() -> None:
    result = validate_numeric_claims(
        "营收下降54.55%，应收增速1.07%，增速差55.62%，报告年度2025。",
        rule_results=[
            {
                "rule_id": "R1",
                "metrics": {"revenue_growth": -0.5455, "ar_growth": 0.0107, "growth_gap": 0.5562},
            }
        ],
        evidence_bundle={},
        allowed_years=[2025],
        additional_sources=[
            {"source_type": "configured_parameter", "source_ref": "R1.r1_gap_threshold", "value": 0.15}
        ],
    )
    assert result["passed"] is True
    assert result["unverified_count"] == 0
    assert {item["source"] for item in result["trace"] if item["verification_status"] == "traced"} == {
        "R1.revenue_growth",
        "R1.ar_growth",
        "R1.growth_gap",
    }


def test_numeric_gate_marks_unmapped_financial_number() -> None:
    result = validate_numeric_claims(
        "应收账款金额为123456789元。",
        rule_results=[{"rule_id": "R1", "metrics": {}}],
        evidence_bundle={},
    )
    assert result["passed"] is False
    assert result["key_unverified_count"] == 1


def test_anti_confirmation_record_allows_no_supported_explanation() -> None:
    record = build_anti_confirmation_record(
        route="risk_candidate",
        rag_evidence=[{"retrieval_id": "RAG-1", "evidence_id": "E-1", "locator": "p.10"}],
        counter_explanations=[
            {"text": "待验证的正常解释", "evidence_ids": [], "support_status": "unverified_hypothesis"}
        ],
        review_recommendation="retain",
    )
    assert record["reverse_evidence_search_performed"] is True
    assert record["hit_count"] == 1
    assert record["none_supported_by_current_evidence"] is True
    assert record["final_recommendation"] == "retain"


def test_calculation_run_exposes_innovation_context_without_model_call() -> None:
    """确定性运行也要输出矩阵、适配度、数字和反确认字段，不能只在模型成功时出现。"""
    from fastapi.testclient import TestClient

    from backend.app.main import app

    response = TestClient(app).post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2025, "rule_ids": ["R1"], "run_mode": "calculation_only"},
    )
    assert response.status_code == 200
    payload = response.json()
    context = payload["context"]
    bundle = payload["evidence_bundle"]
    assert context["assertion_evidence_procedure_matrix"]
    assert context["evidence_fitness_boundary"]
    assert "numeric_claim_trace" in context
    assert "anti_confirmation" in context
    assert [row["matrix_row_id"] for row in bundle["assertion_evidence_procedure_matrix"]] == [
        row["matrix_row_id"] for row in context["assertion_evidence_procedure_matrix"]
    ]
    assert payload["provider_call_count"] == 0
