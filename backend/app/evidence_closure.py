"""证据闭合状态判定（口径 D2）。

本模块把已经存在的四个证据控制项——数字闸门、证据适配度、认定—证据—程序覆盖矩阵、
主张的绑定与支持状态——以及未解决的资料缺口与待取得资料，组合成三档「证据闭合状态」。
判定条件逐字取自 `2026-09-19_口径签字与开工基线.md` §二 D2（队长 2026-09-19 已签字）。

三档的充分条件（不引入任何新阈值，也不读取上述控制项之外的信息）：
- E1 已闭合：闸门 passed=true ∧ 所有 claim 的 support_status=supported ∧ 无未解决 data_gaps；
- E2 部分闭合：闸门 passed=true ∧ 有直接证据，但存在 unverified_hypothesis 或待取得资料；
- E3 未闭合：闸门 passed=false ∨ 关键 claim 无 evidence 绑定 ∨ evidence_fitness 违规。

求值顺序取 E3 → E2 → E1，三档都不满足充分条件时落到 E3。理由与 D1 相反方向但同源：
E1/E2 都是对「闭合性」的正面断言，任何确认不了的残差都必须取不夸大的一侧，
这与 numeric_gate.py 既有的 fail-closed 原则一致。

设计约束：
1. 纯函数，无 I/O、无网络、无模型调用；禁止由模型直接产出 E1/E2/E3。
2. 控制项缺失或形态读不出时如实记为「未提供/未识别」，并压制正面结论，不当成「已检查且无违规」。
3. 本状态与「审计关注优先级」彼此独立，不合并为任何复合分数，也不读取优先级结果。
"""

from __future__ import annotations

from typing import Any

from .schemas import AI_GENERATED_CONTENT_NOTICE

# 保守求值顺序：先判破坏性条件，再判两个正面断言。
EVIDENCE_STATE_ORDER: tuple[str, ...] = ("E3", "E2", "E1")

# 三档中文标签，逐字对应签字口径。
EVIDENCE_STATE_LABELS: dict[str, str] = {
    "E1": "已闭合",
    "E2": "部分闭合",
    "E3": "未闭合",
}

# D2 未随签字给出边界句，这里按 D1 同族表述撰写，并作为待确认事项上报队长。
EVIDENCE_STATE_BOUNDARY = (
    "证据闭合状态只描述本次运行的数字闸门、证据适配度、认定覆盖与主张绑定等控制项是否齐备，"
    "不是审计认定，不构成审计结论或审计意见。"
)

# 主张支持状态的两种取值，来自 schemas.SupportStatus。
SUPPORTED = "supported"
UNVERIFIED_HYPOTHESIS = "unverified_hypothesis"


def _as_plain_dict(item: Any) -> dict[str, Any]:
    """把 AgentClaim 模型或普通字典统一成字典视图，便于挂载方按任一方式传入。"""

    if isinstance(item, dict):
        return item
    dumper = getattr(item, "model_dump", None)
    if callable(dumper):
        return dict(dumper(mode="json"))
    return {}


def _string_list(value: Any) -> list[str]:
    """把可选的字符串列表归一为去空白的列表；未提供时返回空列表。"""

    if not isinstance(value, (list, tuple)):
        return []
    return [text for text in (str(item).strip() for item in value if item is not None) if text]


def _read_gate(numeric_gate: Any) -> tuple[str, list[str], int]:
    """读取数字闸门控制项，返回 passed/failed/not_provided 三态与未通过数字清单。"""

    if not isinstance(numeric_gate, dict) or not numeric_gate:
        return "not_provided", [], 0
    passed = numeric_gate.get("passed")
    # 只有显式布尔才算数；缺失或非布尔意味着闸门没有返回可判定状态，不能当作通过。
    state = "passed" if passed is True else "failed" if passed is False else "not_provided"
    return state, _string_list(numeric_gate.get("key_unverified")), int(numeric_gate.get("unverified_count") or 0)


def _read_fitness(evidence_fitness: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    """读取证据适配度违规清单。

    返回 ``(violations, note)``：violations 为 ``None`` 表示控制项未提供或形态不可读，
    note 携带需要向上如实登记的说明。
    """

    if evidence_fitness is None:
        return None, "evidence_fitness 控制项未提供，本次未纳入其违规信号。"
    if isinstance(evidence_fitness, list):
        return [row for row in evidence_fitness if row], None
    if isinstance(evidence_fitness, dict):
        for key in ("violations", "evidence_fitness_violations"):
            rows = evidence_fitness.get(key)
            if isinstance(rows, list):
                return [row for row in rows if row], None
        return None, "evidence_fitness 形态未识别：既不是违规清单，也不含 violations 键，按未提供处理。"
    return None, "evidence_fitness 形态未识别（非列表亦非字典），按未提供处理。"


def _summarise_claims(claims: Any) -> dict[str, Any]:
    """统计主张的绑定与支持状态，找出「自称已支持却无证据」的关键主张。"""

    rows = [row for row in (_as_plain_dict(item) for item in (claims or [])) if row]
    supported = 0
    hypotheses = 0
    unbound: list[str] = []
    bound = 0
    for row in rows:
        status = str(row.get("support_status") or "")
        evidence_ids = [text for text in _string_list(row.get("evidence_ids")) if text]
        text = str(row.get("text") or "")[:60]
        if status == SUPPORTED:
            supported += 1
            if not evidence_ids:
                # 自称已被证据支持的陈述没有绑定任何 evidence_id，正是最需要拦住的越界主张。
                unbound.append(text or "（空文本主张）")
            else:
                bound += 1
        elif status == UNVERIFIED_HYPOTHESIS:
            hypotheses += 1
    return {
        "total": len(rows),
        "supported": supported,
        "supported_with_evidence_binding": bound,
        "unverified_hypothesis": hypotheses,
        "supported_without_evidence": unbound,
    }


def _summarise_coverage(coverage_matrix: Any) -> dict[str, Any]:
    """从认定—证据—程序矩阵判断是否存在当前企业直接证据。"""

    rows = [row for row in (_as_plain_dict(item) for item in (coverage_matrix or [])) if row]
    with_direct = 0
    for row in rows:
        if _string_list(row.get("current_entity_direct_evidence")):
            with_direct += 1
    return {
        "provided": bool(rows),
        "rows": len(rows),
        "rows_with_current_entity_direct_evidence": with_direct,
    }


def _factor(name: str, value: Any, contribution: str, source: str) -> dict[str, Any]:
    """登记一个控制项：返回了什么、贡献什么、从哪读来。"""

    return {"factor": name, "value": value, "contribution": contribution, "source": source}


def compute_evidence_state(
    *,
    numeric_gate: Any,
    evidence_fitness: Any,
    coverage_matrix: Any,
    claims: Any,
    data_gaps: Any,
    requested_materials: Any,
) -> dict[str, Any]:
    """按已签字口径 D2 计算证据闭合状态，并返回逐条可复核的理由。

    返回字段：
    - ``evidence_state``：E1/E2/E3；
    - ``label``：与状态逐字对应的中文标签；
    - ``factors``：每个控制项「返回了什么、贡献什么、从哪读来」；
    - ``evidence_state_reasons``：逐条记录哪个控制项返回了什么、因此判为此档；
    - ``evidence_state_boundary``：随状态一起显示的边界句。
    """

    gate_state, key_unverified, unverified_count = _read_gate(numeric_gate)
    fitness_violations, fitness_note = _read_fitness(evidence_fitness)
    claim_summary = _summarise_claims(claims)
    coverage_summary = _summarise_coverage(coverage_matrix)
    gaps = _string_list(data_gaps)
    materials = _string_list(requested_materials)

    has_direct_evidence = coverage_summary["rows_with_current_entity_direct_evidence"] > 0
    unbound_supported = claim_summary["supported_without_evidence"]
    violation_count = len(fitness_violations or [])

    factors = [
        _factor(
            "numeric_gate",
            {
                "state": gate_state,
                "key_unverified": key_unverified,
                "unverified_count": unverified_count,
            },
            "passed=false 或未返回可判定状态即判 E3；passed=true 是 E1 与 E2 的共同前提",
            "context.numeric_claim_trace（numeric_gate.validate_numeric_claims 返回体）",
        ),
        _factor(
            "evidence_fitness",
            {
                "provided": fitness_violations is not None,
                "violation_count": violation_count,
                "note": fitness_note,
            },
            "存在越界违规即判 E3；未提供时不升格为任何正面结论",
            "context.evidence_fitness_violations（evidence_fitness.enforce_claim_boundaries 产出）",
        ),
        _factor(
            "coverage_matrix",
            coverage_summary,
            "至少一行含 current_entity_direct_evidence 才算「有直接证据」，是 E1 与 E2 的必要条件",
            "context.assertion_evidence_procedure_matrix（coverage_matrix 产出）",
        ),
        _factor(
            "claims",
            claim_summary,
            "全部 supported 才可能 E1；存在 unverified_hypothesis 只能 E2；supported 却无 evidence 绑定判 E3",
            "AgentClaim.support_status 与 AgentClaim.evidence_ids",
        ),
        _factor(
            "data_gaps",
            gaps,
            "有未解决资料缺口即不得称已闭合；资料受限只压制闭合性，不参与也不影响审计关注优先级",
            "ai_draft.data_gaps 与 risk_card.data_gaps",
        ),
        _factor(
            "requested_materials",
            materials,
            "有待取得资料即不得称已闭合",
            "ai_draft.requested_materials 与 risk_card.requested_materials",
        ),
    ]

    reasons: list[str] = []
    if fitness_note:
        # 控制项本身的缺失先记一笔，保证无论最终落哪一档都能读到它是缺的。
        reasons.append(fitness_note)

    # E3：三个破坏性条件取并集，任一成立即未闭合，不再比较后续正面档位。
    blocking: list[str] = []
    if gate_state == "failed":
        blocking.append(
            "numeric_gate 返回 passed=false，key_unverified="
            + ("、".join(key_unverified) if key_unverified else "（清单为空）")
            + "，关键财务数字未通过可追溯校验，因此判为未闭合（E3）。"
        )
    elif gate_state == "not_provided":
        blocking.append("numeric_gate 未返回可判定的 passed 状态，无法确认数字可追溯，因此判为未闭合（E3）。")
    if unbound_supported:
        blocking.append(
            "claims 控制项返回 "
            + str(len(unbound_supported))
            + " 条 support_status=supported 却无 evidence_ids 绑定的主张（"
            + "；".join(unbound_supported)
            + "），关键主张无证据绑定，因此判为未闭合（E3）。"
        )
    if violation_count:
        blocking.append(
            "evidence_fitness 控制项返回 "
            + str(violation_count)
            + " 条证据适配度越界违规，因此判为未闭合（E3）。"
        )

    if blocking:
        state = "E3"
        reasons.extend(blocking)
    elif has_direct_evidence and (
        claim_summary["unverified_hypothesis"] > 0 or bool(gaps) or bool(materials)
    ):
        state = "E2"
        reasons.append(
            "numeric_gate 返回 passed=true，coverage_matrix 有 "
            + str(coverage_summary["rows_with_current_entity_direct_evidence"])
            + " 行含当前企业直接证据；但 claims 返回 "
            + str(claim_summary["unverified_hypothesis"])
            + " 条 unverified_hypothesis、data_gaps 返回 "
            + str(len(gaps))
            + " 项、requested_materials 返回 "
            + str(len(materials))
            + " 项待取得资料，存在未闭合因素，因此判为部分闭合（E2）。"
        )
    elif (
        gate_state == "passed"
        and fitness_violations is not None
        and has_direct_evidence
        and claim_summary["total"] > 0
        and claim_summary["supported"] == claim_summary["total"]
        and not gaps
        and not materials
    ):
        state = "E1"
        reasons.append(
            "numeric_gate 返回 passed=true，claims 的全部 "
            + str(claim_summary["total"])
            + " 条主张均为 supported 且已绑定证据，evidence_fitness 已执行且无违规，"
            "data_gaps 与 requested_materials 均为空，因此判为已闭合（E1）。"
        )
    else:
        state = "E3"
        reasons.append(
            "未命中：E1 与 E2 的充分条件均不成立（闸门状态="
            + gate_state
            + "，直接证据行数="
            + str(coverage_summary["rows_with_current_entity_direct_evidence"])
            + "，主张总数="
            + str(claim_summary["total"])
            + "，supported 数="
            + str(claim_summary["supported"])
            + "，缺口数="
            + str(len(gaps))
            + "，待取得资料数="
            + str(len(materials))
            + "）。三档中任何正面断言都无法由现有控制项证实，按未闭合（E3）处理。"
        )

    return {
        "evidence_state": state,
        "label": EVIDENCE_STATE_LABELS[state],
        "evaluation_order": list(EVIDENCE_STATE_ORDER),
        "factors": factors,
        "evidence_state_reasons": reasons,
        "evidence_state_boundary": EVIDENCE_STATE_BOUNDARY,
        # 统一 AI 声明随片段一起出口，避免脱离 RunResponse 后边界被弱化。
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
    }
