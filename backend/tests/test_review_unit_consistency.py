"""复审发现的增速差单位错误：正确数字不因格式错误重跑模型。"""
import pytest

from backend.app.agents import format_growth_gap_text, validate_agent_output
from backend.app.schemas import RuleResult


@pytest.mark.parametrize("gap", ["-13.20", "-0.58", "15.00"])
def test_growth_gap_unit_is_corrected_without_changing_rates(gap):
    payload = {
        "schema_version": "agent_output_v2", "run_id": "RUN-UNIT", "role": "review", "rule_id": "R1", "status": "defer",
        "analysis_conclusion": "additional_procedure_required", "ai_recommendation": "defer",
        "claims": [{"text": f"增速差为{gap}%，尚需补充资料。", "evidence_ids": ["E1"], "support_status": "supported"}],
        "normal_explanations": [], "data_gaps": ["账龄"], "requested_materials": ["账龄表"],
        "reason_for_status": "资料不足", "draft_title": "待核查草稿", "draft_observation": f"收入增速9.44%，增速差{gap}%。",
    }
    output = validate_agent_output(payload, run_id="RUN-UNIT", role="review", rule_id="R1", allowed_evidence_ids={"E1"}, analysis_route="evidence_gap_review")
    assert output.draft_observation == f"收入增速9.44%，增速差{gap}个百分点。"
    assert output.claims[0].text == f"增速差为{gap}个百分点，尚需补充资料。"
    assert payload["draft_observation"].endswith(f"{gap}%。")  # 原输入不覆盖。


def test_unit_format_is_idempotent_and_does_not_change_other_percentages():
    text = "收入下降24.45%，增速差-13.20个百分点，应收占收入52.304%。"
    assert format_growth_gap_text(text) == text
