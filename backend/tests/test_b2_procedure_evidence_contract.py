from __future__ import annotations

import pytest

from backend.app.agents import validate_agent_output
from backend.app.schemas import RuleResult
from scripts.run_controlled_b1_b3_prescore import _b2_prompt, _validation_failure


def _rule_result() -> RuleResult:
    return RuleResult(
        rule_id="R1",
        status="candidate",
        source_validation={"issues": []},
        metrics={"growth_gap": 0.42, "three_year_trend_available": True},
        risk_card={"observation": "程序筛查形成待核查候选。"},
    )


def test_b2_prompt_distinguishes_field_and_procedure_evidence() -> None:
    prompt = _b2_prompt()
    assert "field_evidence" in prompt
    assert "procedure_evidence" in prompt
    assert "PROC-*" in prompt
    assert "待验证假设" in prompt


def test_b2_procedure_evidence_can_support_computed_claim() -> None:
    payload = {
        "schema_version": "agent_output_v2",
        "run_id": "EVAL-B2-TEST",
        "role": "review",
        "rule_id": "R1",
        "status": "retain",
        "claims": [
            {
                "text": "程序结果卡支持形成待核查候选。",
                "evidence_ids": ["PROC-R1-2025"],
                "support_status": "supported",
            }
        ],
        "normal_explanations": [
            {
                "text": "业务原因仍是待验证假设。",
                "evidence_ids": [],
                "support_status": "unverified_hypothesis",
            }
        ],
        "data_gaps": ["账龄结构"],
        "requested_materials": ["账龄明细表"],
        "reason_for_status": "仅依据程序结果卡形成待核查草稿。",
        "draft_title": "R1 待核查候选",
        "draft_observation": "程序计算结果需要人工回查。",
        "ai_recommendation": "retain",
    }
    output = validate_agent_output(
        payload,
        run_id="EVAL-B2-TEST",
        role="review",
        rule_id="R1",
        allowed_evidence_ids={"PROC-R1-2025", "FIELD-1"},
        rule_result=_rule_result(),
    )
    assert output.claims[0].evidence_ids == ["PROC-R1-2025"]
    assert output.normal_explanations[0].support_status == "unverified_hypothesis"


def test_b2_unknown_procedure_evidence_remains_hard_failure() -> None:
    payload = {
        "schema_version": "agent_output_v2",
        "run_id": "EVAL-B2-TEST",
        "role": "review",
        "rule_id": "R1",
        "status": "retain",
        "claims": [
            {
                "text": "程序结果支持待核查候选。",
                "evidence_ids": ["PROC-R1-OTHER"],
                "support_status": "supported",
            }
        ],
        "normal_explanations": [],
        "data_gaps": [],
        "requested_materials": [],
        "reason_for_status": "仅依据程序结果。",
        "draft_title": "待核查候选",
        "draft_observation": "需要人工回查。",
        "ai_recommendation": "retain",
    }
    with pytest.raises(ValueError, match="证据包以外"):
        validate_agent_output(
            payload,
            run_id="EVAL-B2-TEST",
            role="review",
            rule_id="R1",
            allowed_evidence_ids={"PROC-R1-2025"},
            rule_result=_rule_result(),
        )


@pytest.mark.parametrize(
    ("message", "code", "stage"),
    [
        ("模型主张必须由本次evidence_id支持", "MODEL_EVIDENCE_VALIDATION_ERROR", "evidence"),
        ("模型输出包含禁止定性用语", "MODEL_POLICY_VIOLATION", "policy"),
        ("确定性事实语言与阈值不一致", "MODEL_FACT_LANGUAGE_VALIDATION_ERROR", "fact_language"),
        ("未获支持的解释必须明确标为待验证假设", "MODEL_FACT_LANGUAGE_VALIDATION_ERROR", "fact_language"),
    ],
)
def test_b2_validation_failure_has_detailed_code(message: str, code: str, stage: str) -> None:
    assert _validation_failure(ValueError(message)) == (code, stage)
