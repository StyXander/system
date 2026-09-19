"""W07/W08：证据闭合状态判定（口径 D2）的合同测试。

口径来源：`2026-09-19_口径签字与开工基线.md` §二 D2（队长 2026-09-19 已签字，逐字实现）。
输入只允许来自现有证据控制项：数字闸门、evidence_fitness、覆盖矩阵、claim 支持状态、
未解决的资料缺口与待取得资料。禁止由模型直接打 E1/E2/E3。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.app.evidence_closure import (
    EVIDENCE_STATE_BOUNDARY,
    EVIDENCE_STATE_LABELS,
    compute_evidence_state,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = WORKSPACE_ROOT / "backend" / "runtime" / "runs"


def _gate(*, passed: bool | None = True, key_unverified: list[str] | None = None) -> dict[str, Any]:
    """按 numeric_gate.validate_numeric_claims 的返回形状拼装闸门结果。"""

    return {
        "schema_version": "numeric_claim_trace_v2",
        "trace": [],
        "unverified_count": len(key_unverified or []),
        "key_unverified_count": len(key_unverified or []),
        "key_unverified": key_unverified or [],
        "passed": passed,
        "boundary": "关键财务数字无来源时禁止完整成功。",
    }


def _claim(text: str, evidence_ids: list[str], support_status: str = "supported") -> dict[str, Any]:
    """一条主张的最小形状，与 schemas.AgentClaim 的 JSON 视图一致。"""

    return {"text": text, "evidence_ids": evidence_ids, "support_status": support_status}


def _matrix(*direct_evidence: str) -> list[dict[str, Any]]:
    """覆盖矩阵最小行；只有 current_entity_direct_evidence 参与本判定。"""

    return [
        {
            "matrix_row_id": "CASE-R1-应收账款-存在",
            "assertion": "存在",
            "rule_id": "R1",
            "status": "partially_covered" if direct_evidence else "gap",
            "current_entity_direct_evidence": list(direct_evidence),
        }
    ]


_FITNESS_CLEAN: list[dict[str, Any]] = []
_FITNESS_VIOLATION: list[dict[str, Any]] = [
    {
        "rule_id": "R1",
        "role": "counter",
        "claim_index": 0,
        "reason": "仅引用规范/类比背景证据，不能支持当前企业事实，主张降级为待验证假设。",
        "evidence_ids": ["KB-QM-001"],
    }
]


def _state(**overrides: Any) -> str:
    """用一套默认已闭合输入跑一次，只返回状态，便于逐条断言。"""

    payload: dict[str, Any] = {
        "numeric_gate": _gate(),
        "evidence_fitness": _FITNESS_CLEAN,
        "coverage_matrix": _matrix("CNINFO_AR_2025"),
        "claims": [_claim("应收账款增速与收入增速背离。", ["CNINFO_AR_2025"])],
        "data_gaps": [],
        "requested_materials": [],
    }
    payload.update(overrides)
    return compute_evidence_state(**payload)["evidence_state"]


def test_e1_when_gate_passed_all_claims_supported_and_no_gaps() -> None:
    assert _state() == "E1"


def test_e2_when_gate_passed_but_a_key_hypothesis_stays_unverified() -> None:
    assert _state(
        claims=[
            _claim("应收账款增速与收入增速背离。", ["CNINFO_AR_2025"]),
            _claim("待验证假设：先款后货的结算安排或可解释背离。", ["RAG-P0010-C01"], "unverified_hypothesis"),
        ]
    ) == "E2"


def test_e2_when_gate_passed_but_materials_are_still_pending() -> None:
    assert _state(requested_materials=["账龄明细表"]) == "E2"


def test_e2_when_gate_passed_but_data_gaps_remain_unresolved() -> None:
    """data_gaps 与 requested_materials 是两个独立控制项，任一非空都不能称已闭合。"""

    assert _state(data_gaps=["缺少账龄结构"]) == "E2"


def test_e3_when_gate_failed_even_if_every_claim_is_supported() -> None:
    assert _state(numeric_gate=_gate(passed=False, key_unverified=["41,813,685.32"])) == "E3"


def test_e3_when_a_supported_claim_has_no_evidence_binding() -> None:
    assert _state(
        claims=[
            _claim("应收账款增速与收入增速背离。", ["CNINFO_AR_2025"]),
            _claim("客户集中度已显著上升。", []),
        ]
    ) == "E3"


def test_e3_when_evidence_fitness_reports_a_violation() -> None:
    assert _state(evidence_fitness=_FITNESS_VIOLATION) == "E3"


def test_unverified_hypothesis_without_evidence_is_not_treated_as_unbound_key_claim() -> None:
    """待验证假设本就允许暂无证据，不能因此判未闭合，否则与 E2 的定义自相矛盾。"""

    assert _state(
        claims=[_claim("待验证假设：结算节奏变化。", [], "unverified_hypothesis")],
        data_gaps=["缺少期后回款"],
    ) == "E2"


def test_missing_gate_is_not_silently_treated_as_passed() -> None:
    """闸门未返回可判定状态时不得宣称闭合，按未闭合处理。"""

    assert _state(numeric_gate=None) == "E3"
    assert _state(numeric_gate={}) == "E3"


def test_fitness_control_item_not_provided_caps_the_result_at_not_closed() -> None:
    """适配度控制项缺失时既不能升格为已闭合，也不能谎称部分闭合：残余一律取不夸大的一侧。

    原则：三档都不满足充分条件时落 E3，因为 E1/E2 都是对闭合性的正面断言。
    """

    assert _state(evidence_fitness=None, claims=[_claim("结论", ["EV-1"])]) == "E3"
    reasons = compute_evidence_state(
        numeric_gate=_gate(),
        evidence_fitness=None,
        coverage_matrix=_matrix("EV-1"),
        claims=[_claim("结论", ["EV-1"])],
        data_gaps=[],
        requested_materials=[],
    )["evidence_state_reasons"]
    assert any("evidence_fitness" in text or "适配度" in text for text in reasons)


def test_no_claims_cannot_be_declared_closed() -> None:
    """空主张列表会让「所有 claim 均 supported」空真成立，必须显式排除。"""

    assert _state(claims=[], data_gaps=["缺少字段"]) == "E2"
    assert _state(claims=[]) == "E3"


def test_no_direct_evidence_caps_result_as_not_closed() -> None:
    """E2 的充分条件要求「有直接证据」；覆盖矩阵全空时按未闭合处理。"""

    assert _state(coverage_matrix=_matrix(), data_gaps=["缺少账龄结构"]) == "E3"


def test_fitness_violations_also_accept_a_dict_shape() -> None:
    """轨 A 可能传 context 里的字典形态，两种形态都要能读出违规，不得静默当作无违规。"""

    assert _state(evidence_fitness={"violations": _FITNESS_VIOLATION}) == "E3"
    assert _state(evidence_fitness={"evidence_fitness_violations": _FITNESS_CLEAN}) == "E1"


def test_unrecognised_fitness_shape_is_recorded_and_caps_result() -> None:
    """读不出违规清单的形态必须留下痕迹，不能被当成「已检查且无违规」。"""

    result = compute_evidence_state(
        numeric_gate=_gate(),
        evidence_fitness="unexpected-shape",
        coverage_matrix=_matrix("EV-1"),
        claims=[_claim("结论", ["EV-1"])],
        data_gaps=[],
        requested_materials=[],
    )
    assert result["evidence_state"] == "E3"
    assert any("形态未识别" in text for text in result["evidence_state_reasons"])


def test_labels_and_boundary_are_verbatim() -> None:
    assert EVIDENCE_STATE_LABELS == {"E1": "已闭合", "E2": "部分闭合", "E3": "未闭合"}
    assert isinstance(EVIDENCE_STATE_BOUNDARY, str) and EVIDENCE_STATE_BOUNDARY
    for state in ("E1", "E2", "E3"):
        payload = _payload_for(state)
        assert payload["evidence_state_boundary"] == EVIDENCE_STATE_BOUNDARY
        assert payload["label"] == EVIDENCE_STATE_LABELS[state]


def _payload_for(state: str) -> dict[str, Any]:
    """为三档各构造一条能命中的输入，供逐档断言标签与边界句。"""

    base: dict[str, Any] = {
        "numeric_gate": _gate(),
        "evidence_fitness": _FITNESS_CLEAN,
        "coverage_matrix": _matrix("EV-1"),
        "claims": [_claim("结论", ["EV-1"])],
        "data_gaps": [],
        "requested_materials": [],
    }
    if state == "E1":
        return compute_evidence_state(**base)
    if state == "E2":
        return compute_evidence_state(**{**base, "data_gaps": ["缺少账龄结构"]})
    return compute_evidence_state(**{**base, "numeric_gate": _gate(passed=False, key_unverified=["1,234.00"])})


def test_reasons_name_the_control_item_and_its_returned_value() -> None:
    """D2 铁律 3：reasons 要逐条写明哪个控制项返回了什么、因此判为此档。"""

    payload = compute_evidence_state(
        numeric_gate=_gate(passed=False, key_unverified=["41,813,685.32"]),
        evidence_fitness=_FITNESS_CLEAN,
        coverage_matrix=_matrix("EV-1"),
        claims=[_claim("结论", ["EV-1"])],
        data_gaps=["缺少期后回款"],
        requested_materials=["期后回款记录"],
    )
    joined = "\n".join(payload["evidence_state_reasons"])
    assert "numeric_gate" in joined
    assert "41,813,685.32" in joined
    assert payload["evidence_state"] == "E3"
    for row in payload["factors"]:
        assert {"factor", "value", "contribution", "source"} <= set(row)
    named = {row["factor"] for row in payload["factors"]}
    assert {"numeric_gate", "evidence_fitness", "coverage_matrix", "claims", "data_gaps", "requested_materials"} <= named


def test_output_has_no_severity_score_and_stays_independent_of_priority() -> None:
    """证据状态与审计关注优先级是两条独立轴，本模块不得产出级别或分值。"""

    payload = _payload_for("E2")
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "grade" not in dumped
    for key in payload:
        assert "score" not in key.lower()
    assert payload["evidence_state"] in {"E1", "E2", "E3"}


def test_unified_ai_notice_travels_with_the_state() -> None:
    """AGENTS.md §3：新增对外 JSON 片段必须逐字带统一 AI 声明，不得弱化成另一套措辞。"""

    from backend.app.schemas import AI_GENERATED_CONTENT_NOTICE

    payload = _payload_for("E2")
    assert payload["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE
    assert payload["ai_generated_content_notice"] == (
        "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
    )


def test_none_inputs_do_not_raise() -> None:
    """整条证据链都没跑时仍要给出可复核的未闭合结论，而不是异常。"""

    payload = compute_evidence_state(
        numeric_gate=None,
        evidence_fitness=None,
        coverage_matrix=None,
        claims=None,
        data_gaps=None,
        requested_materials=None,
    )
    assert payload["evidence_state"] == "E3"
    assert payload["evidence_state_reasons"]


def test_purity_same_input_same_output_and_no_mutation() -> None:
    """纯函数：同输入同输出，且不回写调用方传入的列表。"""

    claims = [_claim("结论", ["EV-1"])]
    before = json.dumps(claims, ensure_ascii=False, sort_keys=True)
    kwargs: dict[str, Any] = {
        "numeric_gate": _gate(),
        "evidence_fitness": _FITNESS_CLEAN,
        "coverage_matrix": _matrix("EV-1"),
        "claims": claims,
        "data_gaps": [],
        "requested_materials": [],
    }
    assert compute_evidence_state(**kwargs) == compute_evidence_state(**kwargs)
    assert json.dumps(claims, ensure_ascii=False, sort_keys=True) == before


def _load_sealed_run(run_id: str) -> dict[str, Any]:
    """读取已封存的历史运行原件；本机没有 runtime 时跳过，不改写任何文件。"""

    path = RUNS_DIR / f"{run_id}.json"
    if not path.is_file():
        pytest.skip(f"未找到封存运行 {path.name}（runtime 目录不随仓库分发）")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("run") or payload


def _state_from_run(run: dict[str, Any]) -> dict[str, Any]:
    """从封存运行原件按轨 A 将要挂载的口径组装入参。"""

    context = run.get("context") or {}
    claims: list[dict[str, Any]] = []
    gaps: list[str] = []
    materials: list[str] = []
    for rule in run.get("rule_results") or []:
        draft = rule.get("ai_draft") or {}
        for key in ("claims", "normal_explanations"):
            claims.extend(item for item in (draft.get(key) or []) if isinstance(item, dict))
        gaps.extend(str(item) for item in (draft.get("data_gaps") or []))
        materials.extend(str(item) for item in (draft.get("requested_materials") or []))
    return compute_evidence_state(
        numeric_gate=context.get("numeric_claim_trace"),
        evidence_fitness=context.get("evidence_fitness_violations"),
        coverage_matrix=context.get("assertion_evidence_procedure_matrix"),
        claims=claims,
        data_gaps=gaps,
        requested_materials=materials,
    )


def test_sealed_wuliangye_run_with_passed_gate_is_partially_closed() -> None:
    """RUN-V7-45BFA3297C39：闸门 passed、两条正常解释均为待验证假设、4 项缺口未解决 → E2。"""

    run = _load_sealed_run("RUN-V7-45BFA3297C39")
    payload = _state_from_run(run)
    assert payload["evidence_state"] == "E2"
    assert (run.get("context") or {}).get("numeric_claim_trace", {}).get("passed") is True


def test_sealed_wuliangye_run_with_failed_gate_is_not_closed() -> None:
    """RUN-V7-D8933A6BBDDB 在 W01 之前仍被闸门拦下：passed=false 直接落 E3，不得粉饰。"""

    run = _load_sealed_run("RUN-V7-D8933A6BBDDB")
    assert (run.get("context") or {}).get("numeric_claim_trace", {}).get("passed") is False
    assert _state_from_run(run)["evidence_state"] == "E3"


def test_sealed_biaozhun_run_state_and_documented_divergence() -> None:
    """标准股份 RUN-V7-BF8D84368D35 逐字套用签字口径 D2 得 E2，而方案文档的实测参照写 E3。

    该分歧已列入本轮报告的未确认事项，等待队长裁决；本测试锁定的是签字口径
    在这条真实封存运行上的实际输出，不擅自放宽或收紧 D2 的任何一档条件去凑 E3。
    """

    run = _load_sealed_run("RUN-V7-BF8D84368D35")
    context = run.get("context") or {}
    assert context.get("numeric_claim_trace", {}).get("passed") is True
    payload = _state_from_run(run)
    assert payload["evidence_state"] == "E2"
    assert payload["factors"]
    assert any("unverified_hypothesis" in text for text in payload["evidence_state_reasons"])
