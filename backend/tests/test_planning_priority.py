"""W06/W08：审计关注优先级判定（口径 D1）的合同测试。

口径来源：`2026-09-19_口径签字与开工基线.md` §二 D1（队长 2026-09-19 已签字，逐字实现）。
判定顺序固定为 G → P1 → P2 → P3 → S → P4；数据缺口只能导致不出级，绝不能升级。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.app.planning_priority import (
    PRIORITY_BOUNDARY,
    PRIORITY_LABELS,
    compute_planning_priority,
)
from backend.app.schemas import RuleResult

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = WORKSPACE_ROOT / "backend" / "runtime" / "runs"

# 已签字的六个级别代号；不引入第七档，也不改用证券评级代码。
SIGNED_GRADES = {"G", "P1", "P2", "P3", "S", "P4"}


def _rule(
    *,
    rule_id: str = "R1",
    status: str = "candidate",
    screening_strength: str | None = None,
    sustained_periods: int | None = None,
    growth_gap: float | None = None,
    materiality_assessment: str | None = "未评价金额重要性",
    materiality_multiple: float | None = None,
    reason_for_status: str | None = None,
) -> dict[str, Any]:
    """按 main.py 的 R1 产出结构拼装最小规则结果字典。"""

    risk_card: dict[str, Any] = {"rule_id": rule_id}
    if screening_strength is not None:
        risk_card["screening_strength"] = screening_strength
    ai_draft = {"reason_for_status": reason_for_status} if reason_for_status else None
    return {
        "rule_id": rule_id,
        "status": status,
        "screening_status": status,
        "source_validation": {"issues": []},
        "metrics": {
            "growth_gap": growth_gap,
            "sustained_periods": sustained_periods,
            "materiality_assessment": materiality_assessment,
            "materiality_multiple": materiality_multiple,
        },
        "risk_card": risk_card,
        "ai_draft": ai_draft,
    }


def _grade(**overrides: Any) -> str | None:
    """用一套默认可分级输入跑一次，只返回级别，便于逐条断言。"""

    payload: dict[str, Any] = {
        "rule_results": [_rule(screening_strength="strong", sustained_periods=1)],
        "ai_recommendation": "retain",
        "analysis_conclusion": "risk_candidate",
        "run_completeness": "complete_public_prescreen",
        "screening_status": "candidate",
    }
    payload.update(overrides)
    return compute_planning_priority(**payload)["grade"]


def test_p1_requires_strong_two_periods_and_retain() -> None:
    assert _grade(
        rule_results=[_rule(screening_strength="strong", sustained_periods=2)],
        ai_recommendation="retain",
    ) == "P1"


def test_p2_when_strong_but_only_one_sustained_period() -> None:
    assert _grade(
        rule_results=[_rule(screening_strength="strong", sustained_periods=1)],
        ai_recommendation="retain",
    ) == "P2"


def test_p2_when_strong_but_disposition_is_downgrade() -> None:
    """P1 要求 retain；降级处置只能落 P2，但处置轴仍原样并排输出。"""

    result = compute_planning_priority(
        rule_results=[_rule(screening_strength="strong", sustained_periods=2)],
        ai_recommendation="downgrade",
        analysis_conclusion="risk_candidate",
        run_completeness="complete_public_prescreen",
        screening_status="candidate",
    )
    assert result["grade"] == "P2"
    assert result["disposition"]["ai_recommendation"] == "downgrade"
    assert result["disposition"]["label"] == "建议降级"


def test_p3_when_candidate_with_standard_strength() -> None:
    assert _grade(rule_results=[_rule(screening_strength="standard", sustained_periods=3)]) == "P3"


def test_p4_when_rule_not_triggered_with_complete_data() -> None:
    assert _grade(
        rule_results=[_rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0)],
        screening_status="RULE_NOT_TRIGGERED",
        ai_recommendation="retain",
        run_completeness="complete_public_prescreen",
    ) == "P4"


def test_s_when_not_candidate_and_review_defers() -> None:
    assert _grade(
        rule_results=[_rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0)],
        screening_status="RULE_NOT_TRIGGERED",
        ai_recommendation="defer",
        run_completeness="complete_public_prescreen",
    ) == "S"


def test_g_on_data_gap() -> None:
    assert _grade(
        rule_results=[_rule(status="DATA_GAP", screening_strength=None, sustained_periods=None)],
        screening_status="DATA_GAP",
        ai_recommendation="not_generated",
        run_completeness="incomplete_calculation_only",
    ) == "G"


def test_g_on_data_not_comparable() -> None:
    assert _grade(
        rule_results=[
            _rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0),
            _rule(rule_id="R2", status="DATA_NOT_COMPARABLE", screening_strength=None, sustained_periods=None),
        ],
        screening_status="DATA_NOT_COMPARABLE",
        ai_recommendation="defer",
    ) == "G"


def test_severe_data_gap_never_upgrades_to_p1() -> None:
    """D1 铁律 1 的关键反向用例：字段缺口与不可比同时存在时必须落 G，不得升到 P1。"""

    strong_payload = [_rule(screening_strength="strong", sustained_periods=2)]
    assert _grade(
        rule_results=[
            *strong_payload,
            _rule(rule_id="R2", status="DATA_GAP", screening_strength=None, sustained_periods=None),
            _rule(rule_id="R2", status="DATA_NOT_COMPARABLE", screening_strength=None, sustained_periods=None),
        ],
        ai_recommendation="retain",
        screening_status="candidate",
    ) == "G"
    # 同一候选载荷抽掉缺口规则即命中 P1，证明上一条里 G 真的压制了本可成立的 P1，
    # 而不是这条输入本来就够不上 P1。
    assert _grade(rule_results=strong_payload, ai_recommendation="retain") == "P1"


def test_data_gap_alone_does_not_upgrade_a_standard_candidate() -> None:
    """缺口只会压到 G，不会把 standard 候选抬成更强级别。"""

    assert _grade(
        rule_results=[
            _rule(screening_strength="standard", sustained_periods=1),
            _rule(rule_id="R2", status="DATA_GAP", screening_strength=None, sustained_periods=None),
        ],
        screening_status="DATA_NOT_COMPARABLE",
    ) == "G"


def test_growth_gap_exactly_015_is_candidate_and_lands_p3() -> None:
    """边界：增速差恰为 0.15 时按 main.py 的 >= 语义成为 candidate，但强度仍是 standard。"""

    from backend.app.main import _r1_result

    rows = [
        {"field_id": "revenue_current", "value": 100.0, "evidence_id": "E-REV-C", "field_basis": "reported", "unit": "元"},
        {"field_id": "revenue_previous", "value": 100.0, "evidence_id": "E-REV-P", "field_basis": "reported", "unit": "元"},
        {"field_id": "ar_current", "value": 115.0, "evidence_id": "E-AR-C", "field_basis": "gross", "unit": "元"},
        {"field_id": "ar_previous", "value": 100.0, "evidence_id": "E-AR-P", "field_basis": "gross", "unit": "元"},
    ]
    result = _r1_result(rows, [])
    assert result.status == "candidate"
    assert result.risk_card["screening_strength"] == "standard"
    assert result.metrics["sustained_periods"] == 1
    assert _grade(rule_results=[result.model_dump(mode="json")]) == "P3"


def test_growth_gap_exactly_030_is_strong_and_lands_p2() -> None:
    """边界：增速差恰为 0.30 时 >= 语义判为 strong；持续性只有 1 期，因此是 P2 而非 P1。"""

    from backend.app.main import _r1_result

    rows = [
        {"field_id": "revenue_current", "value": 100.0, "evidence_id": "E-REV-C", "field_basis": "reported", "unit": "元"},
        {"field_id": "revenue_previous", "value": 100.0, "evidence_id": "E-REV-P", "field_basis": "reported", "unit": "元"},
        {"field_id": "ar_current", "value": 130.0, "evidence_id": "E-AR-C", "field_basis": "gross", "unit": "元"},
        {"field_id": "ar_previous", "value": 100.0, "evidence_id": "E-AR-P", "field_basis": "gross", "unit": "元"},
    ]
    result = _r1_result(rows, [])
    assert result.risk_card["screening_strength"] == "strong"
    assert result.metrics["sustained_periods"] == 1
    assert _grade(rule_results=[result.model_dump(mode="json")]) == "P2"


def test_growth_gap_exactly_030_in_two_periods_with_retain_lands_p1() -> None:
    """两个 >= 阈值同时命中且处置为 retain 时才是 P1，仍然没有任何新阈值。"""

    from backend.app.main import _r1_result

    rows = [
        {"field_id": "revenue_current", "value": 100.0, "evidence_id": "E-REV-C", "field_basis": "reported", "unit": "元"},
        {"field_id": "revenue_previous", "value": 100.0, "evidence_id": "E-REV-P", "field_basis": "reported", "unit": "元"},
        {"field_id": "revenue_prior", "value": 100.0, "evidence_id": "E-REV-0", "field_basis": "reported", "unit": "元"},
        {"field_id": "ar_current", "value": 149.5, "evidence_id": "E-AR-C", "field_basis": "gross", "unit": "元"},
        {"field_id": "ar_previous", "value": 115.0, "evidence_id": "E-AR-P", "field_basis": "gross", "unit": "元"},
        {"field_id": "ar_prior", "value": 100.0, "evidence_id": "E-AR-0", "field_basis": "gross", "unit": "元"},
    ]
    result = _r1_result(rows, [])
    assert result.risk_card["screening_strength"] == "strong"
    assert result.metrics["sustained_periods"] == 2
    assert _grade(rule_results=[result.model_dump(mode="json")]) == "P1"


def test_factors_and_top_level_outputs_share_one_source() -> None:
    """factors 必须与出口字段同源，否则「可追溯」只是装饰。

    非候选路线（如 R1 未触发）没有 candidate 规则可取重要性，此时出口字段回退到
    首条被选用规则；因子行必须跟着回退，不能继续显示未选用候选而留空。
    """

    payload = _full_result_for("G")
    by_name = {row["factor"]: row for row in payload["factors"]}
    assert by_name["materiality_assessment"]["value"] == payload["materiality_assessment"]
    assert "来源" in by_name["materiality_assessment"]["source"]


def test_materiality_is_reported_side_by_side_and_never_changes_grade() -> None:
    """D1 铁律 2：金额重要性只并排输出，不折入级别。"""

    below = _grade(
        rule_results=[_rule(screening_strength="strong", sustained_periods=1, materiality_assessment="低于计划重要性", materiality_multiple=0.4)],
    )
    reached = _grade(
        rule_results=[_rule(screening_strength="strong", sustained_periods=1, materiality_assessment="达到或超过计划重要性", materiality_multiple=3.2)],
    )
    assert below == reached == "P2"
    result = compute_planning_priority(
        rule_results=[_rule(screening_strength="strong", sustained_periods=1, materiality_assessment="达到或超过计划重要性", materiality_multiple=3.2)],
        ai_recommendation="retain",
        analysis_conclusion="risk_candidate",
        run_completeness="complete_public_prescreen",
        screening_status="candidate",
    )
    assert result["materiality_assessment"] == "达到或超过计划重要性"
    assert result["materiality_multiple"] == 3.2


def test_analysis_conclusion_is_recorded_but_not_used_for_grading() -> None:
    """D1 表体不含 analysis_conclusion；它只能登记，不能改变级别。"""

    first = _grade(analysis_conclusion="risk_candidate")
    second = _grade(analysis_conclusion="additional_procedure_required")
    assert first == second == "P2"
    factors = compute_planning_priority(
        rule_results=[_rule(screening_strength="strong", sustained_periods=1)],
        ai_recommendation="retain",
        analysis_conclusion="additional_procedure_required",
        run_completeness="complete_public_prescreen",
        screening_status="candidate",
    )["factors"]
    recorded = {row["factor"] for row in factors}
    assert "analysis_conclusion" in recorded


def test_boundary_sentence_is_verbatim_and_label_set_is_closed() -> None:
    assert PRIORITY_BOUNDARY == "本级别为审计计划阶段的程序筛查信号分级，不是审计认定，不构成审计结论或审计意见。"
    assert PRIORITY_LABELS["G"] == "暂不分级（资料/口径受限）"
    assert PRIORITY_LABELS["P1"] == "立即扩大核查"
    assert PRIORITY_LABELS["P2"] == "优先核查"
    assert PRIORITY_LABELS["P3"] == "常规跟进"
    assert PRIORITY_LABELS["S"] == "暂缓判断"
    assert PRIORITY_LABELS["P4"] == "维持常规程序"
    for grade in SIGNED_GRADES:
        payload = _full_result_for(grade)
        assert payload["boundary"] == PRIORITY_BOUNDARY
        assert payload["label"] == PRIORITY_LABELS[grade]


def test_unified_ai_notice_travels_with_the_grade() -> None:
    """AGENTS.md §3：新增对外 JSON 片段必须逐字带统一 AI 声明，不得弱化成另一套措辞。"""

    from backend.app.schemas import AI_GENERATED_CONTENT_NOTICE

    payload = _full_result_for("P2")
    assert payload["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE
    assert payload["ai_generated_content_notice"] == (
        "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
    )


def _full_result_for(grade: str) -> dict[str, Any]:
    """为每个已签字级别造一条能命中它的输入，供逐级别断言使用。"""

    matrix: dict[str, dict[str, Any]] = {
        "P1": {"rule_results": [_rule(screening_strength="strong", sustained_periods=2)], "ai_recommendation": "retain"},
        "P2": {"rule_results": [_rule(screening_strength="strong", sustained_periods=1)], "ai_recommendation": "retain"},
        "P3": {"rule_results": [_rule(screening_strength="standard", sustained_periods=1)], "ai_recommendation": "retain"},
        "S": {
            "rule_results": [_rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0)],
            "screening_status": "RULE_NOT_TRIGGERED",
            "ai_recommendation": "defer",
        },
        "P4": {
            "rule_results": [_rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0)],
            "screening_status": "RULE_NOT_TRIGGERED",
            "ai_recommendation": "retain",
        },
        "G": {
            "rule_results": [_rule(status="DATA_GAP", screening_strength=None, sustained_periods=None)],
            "screening_status": "DATA_GAP",
            "ai_recommendation": "not_generated",
            "run_completeness": "incomplete_calculation_only",
        },
    }
    payload: dict[str, Any] = {
        "ai_recommendation": "not_applicable",
        "analysis_conclusion": None,
        "run_completeness": "complete_public_prescreen",
        "screening_status": "candidate",
    }
    payload.update(matrix[grade])
    return compute_planning_priority(**payload)


def test_output_carries_no_numeric_score_and_no_rating_vocabulary() -> None:
    """命名红线：级别是文字代号，不得出现分值，也不得出现证券评级代码。"""

    for grade in sorted(SIGNED_GRADES):
        payload = _full_result_for(grade)
        dumped = json.dumps(payload, ensure_ascii=False)
        assert payload["grade"] == grade
        assert isinstance(payload["grade"], str)
        for key in payload:
            assert "score" not in key.lower()
        for banned in ("风险评级", "信用等级", "无风险", "企业风险等级", "A1", "A2", "B1", "B2", "C1", "C2"):
            assert banned not in dumped


def test_every_grade_explains_which_field_contributed_what() -> None:
    """factors/reasons 必须逐条可追溯，评委能看出级别是怎么来的。"""

    payload = _full_result_for("P1")
    factors = payload["factors"]
    assert factors
    for row in factors:
        assert {"factor", "value", "contribution"} <= set(row)
    named = {row["factor"] for row in factors}
    assert {"screening_status", "screening_strength", "sustained_periods", "ai_recommendation"} <= named
    assert payload["reasons"]
    assert any("P1" in text for text in payload["reasons"])


def test_candidate_without_screening_strength_is_left_ungraded() -> None:
    """R2 的 risk_card 不产出 screening_strength（main.py:2485-2493），已签字六档均不命中。

    本函数不得为了给出级别而新增第七档，也不得把 unknown 强度当作 standard。
    """

    assert _grade(
        rule_results=[_rule(rule_id="R2", screening_strength=None, sustained_periods=None)],
        screening_status="candidate",
    ) is None


def test_residual_combinations_return_none_rather_than_a_invented_grade() -> None:
    """未触发但数据不完整、以及来源未完成，都不在已签字六档之内。"""

    assert _grade(
        rule_results=[_rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0)],
        screening_status="RULE_NOT_TRIGGERED",
        ai_recommendation="retain",
        run_completeness="incomplete_calculation_only",
    ) is None
    assert _grade(
        rule_results=[_rule(status="SOURCE_INCOMPLETE", screening_strength=None, sustained_periods=None)],
        screening_status="SOURCE_INCOMPLETE",
        ai_recommendation="not_applicable",
        run_completeness="incomplete_calculation_only",
    ) is None


def test_p4_requires_complete_data_and_records_blocked_row_proxy() -> None:
    """P4 的「数据完整 ∧ 无 blocked 行」在缺计数时只能近似，且必须留痕。"""

    payload = _full_result_for("P4")
    assert any(row["factor"] == "blocked_row_proxy" for row in payload["factors"])
    proxy = next(row for row in payload["factors"] if row["factor"] == "blocked_row_proxy")
    assert "代理" in proxy["contribution"]
    assert any("blocked" in text or "完整" in text for text in payload["reasons"])


def test_explicit_blocked_count_gates_p4() -> None:
    """§7.7：轨 A 传入 context.prescreen_plan.blocked_candidate_count 时以计数为准。"""

    not_triggered = [_rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0)]
    assert _grade(
        rule_results=not_triggered,
        screening_status="RULE_NOT_TRIGGERED",
        ai_recommendation="retain",
        blocked_candidate_count=0,
    ) == "P4"
    for count in (3, 5):
        assert _grade(
            rule_results=not_triggered,
            screening_status="RULE_NOT_TRIGGERED",
            ai_recommendation="retain",
            blocked_candidate_count=count,
        ) is None


def test_blocked_count_none_keeps_the_proxy_behaviour() -> None:
    """未传计数时行为与 §7.7 之前完全一致，避免挂载遗漏把 P4 全部抹掉。"""

    not_triggered = [_rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0)]
    assert _grade(
        rule_results=not_triggered,
        screening_status="RULE_NOT_TRIGGERED",
        ai_recommendation="retain",
        blocked_candidate_count=None,
    ) == "P4"
    payload = compute_planning_priority(
        rule_results=not_triggered,
        ai_recommendation="retain",
        analysis_conclusion="no_trigger_confirmed",
        run_completeness="complete_public_prescreen",
        screening_status="RULE_NOT_TRIGGERED",
        blocked_candidate_count=None,
    )
    assert any(row["factor"] == "blocked_row_proxy" for row in payload["factors"])


def test_blocked_count_source_is_recorded_per_judging_path() -> None:
    """两条判据路径必须在输出上可区分，评委要能看出这次到底是按什么判的。"""

    not_triggered = [_rule(status="RULE_NOT_TRIGGERED", screening_strength="none", sustained_periods=0)]
    with_count = compute_planning_priority(
        rule_results=not_triggered,
        ai_recommendation="retain",
        analysis_conclusion="no_trigger_confirmed",
        run_completeness="complete_public_prescreen",
        screening_status="RULE_NOT_TRIGGERED",
        blocked_candidate_count=0,
    )
    row = next(item for item in with_count["factors"] if "blocked" in item["factor"])
    assert row["factor"] == "blocked_candidate_count"
    assert row["value"] == 0
    assert "prescreen_plan" in row["source"]
    assert any("blocked_candidate_count" in text for text in with_count["reasons"])


def test_blocked_count_never_changes_any_grade_but_p4() -> None:
    """blocked 计数只压 P4，不得影响其余五档，更不得使优先级升级。"""

    strong = [_rule(screening_strength="strong", sustained_periods=2)]
    for count in (None, 0, 9):
        assert _grade(rule_results=strong, ai_recommendation="retain", blocked_candidate_count=count) == "P1"
        assert _grade(
            rule_results=[_rule(status="DATA_GAP", screening_strength=None, sustained_periods=None)],
            screening_status="DATA_GAP",
            ai_recommendation="not_generated",
            run_completeness="incomplete_calculation_only",
            blocked_candidate_count=count,
        ) == "G"


def test_disposition_axis_keeps_reason_for_status_and_never_overrides_grade() -> None:
    """D1 铁律 4：处置与级别并排、互不覆盖。"""

    payload = compute_planning_priority(
        rule_results=[
            _rule(screening_strength="strong", sustained_periods=2, reason_for_status="应收与收入增速差持续两期，建议扩大函证范围。")
        ],
        ai_recommendation="retain",
        analysis_conclusion="risk_candidate",
        run_completeness="complete_public_prescreen",
        screening_status="candidate",
    )
    assert payload["grade"] == "P1"
    assert payload["disposition"]["ai_recommendation"] == "retain"
    assert payload["disposition"]["label"] == "建议保留"
    assert payload["disposition"]["reason_for_status"] == "应收与收入增速差持续两期，建议扩大函证范围。"


def test_pydantic_rule_results_are_accepted_like_dicts() -> None:
    """轨 A 可能直接传 RunResponse 里的 RuleResult 模型，而不是 model_dump 后的字典。"""

    model_rows = [
        RuleResult(
            rule_id="R1",
            status="candidate",
            source_validation={"status": "passed", "issues": []},
            metrics={"growth_gap": 0.55, "sustained_periods": 2, "materiality_assessment": "未评价金额重要性"},
            risk_card={"rule_id": "R1", "screening_strength": "strong"},
        )
    ]
    as_models = _grade(rule_results=model_rows, screening_status="candidate")
    as_dicts = _grade(
        rule_results=[row.model_dump(mode="json") for row in model_rows],
        screening_status="candidate",
    )
    assert as_models == as_dicts == "P1"


def test_purity_same_input_same_output_and_no_mutation() -> None:
    """纯函数：同输入同输出，且不回写入参。"""

    rows = [_rule(screening_strength="strong", sustained_periods=2)]
    before = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    kwargs: dict[str, Any] = {
        "rule_results": rows,
        "ai_recommendation": "retain",
        "analysis_conclusion": "risk_candidate",
        "run_completeness": "complete_public_prescreen",
        "screening_status": "candidate",
    }
    first = compute_planning_priority(**kwargs)
    second = compute_planning_priority(**kwargs)
    assert first == second
    assert json.dumps(rows, ensure_ascii=False, sort_keys=True) == before


def _load_sealed_run(run_id: str) -> dict[str, Any]:
    """读取已封存的历史运行原件；本机没有 runtime 时跳过，不改写任何文件。"""

    path = RUNS_DIR / f"{run_id}.json"
    if not path.is_file():
        pytest.skip(f"未找到封存运行 {path.name}（runtime 目录不随仓库分发）")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("run") or payload


@pytest.mark.parametrize(
    ("run_id", "company", "expected_grade"),
    [
        ("RUN-V7-45BFA3297C39", "五粮液", "P2"),
        ("RUN-V7-BF8D84368D35", "西安标准工业股份有限公司（标准股份）", "G"),
    ],
)
def test_sealed_runs_map_to_signed_grades_without_reaching(run_id: str, company: str, expected_grade: str) -> None:
    """用真实封存运行验证归档，且只读不改写历史 JSON。"""

    run = _load_sealed_run(run_id)
    assert (run.get("context") or {}).get("company_name") == company
    payload = compute_planning_priority(
        rule_results=run.get("rule_results") or [],
        ai_recommendation=run.get("ai_recommendation"),
        analysis_conclusion=run.get("ai_analysis_conclusion"),
        run_completeness=run.get("run_completeness"),
        screening_status=run.get("screening_status"),
    )
    assert payload["grade"] == expected_grade
    assert payload["disposition"]["ai_recommendation"] == run.get("ai_recommendation")
