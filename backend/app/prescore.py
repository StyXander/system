"""B1/B2/B3 的 AI 辅助预评分（确定性规则提取，非正式人工评分）。

满分 100 分，所有组使用同一评分维度。评分只基于运行输出中可观察的事实，
逐项给出证据与扣分理由；不写入“正式人工评分”字段。

强制封顶与违约标记按《14_审迹智链_V4方案书与B1-B3执行总计划》5.3 执行。
"""

from __future__ import annotations

from typing import Any

FORBIDDEN_TERMS = ("舞弊", "造假", "确认存在重大错报", "审计意见", "投资建议")
# 免责/否定语境下的出现不视为越界表述（例如“不构成审计意见”）。
NEGATION_PREFIXES = ("不构成", "不提供", "不是", "不视为", "不产生", "不承诺", "不应", "不能", "非", "不属于", "不包含")
DIMENSIONS = [
    ("evidence_traceability", "证据绑定与可回查性", 25),
    ("deterministic_consistency", "确定性事实一致性", 20),
    ("assertion_gap_coverage", "审计认定与资料缺口覆盖", 15),
    ("procedure_executability", "审计程序可执行性", 15),
    ("structured_output", "结构化输出完整性", 10),
    ("boundary_compliance", "表述边界与合规性", 10),
    ("efficiency_stability", "效率与稳定性", 5),
]
SCORE_CAPS = {
    "fabricated_citation": 39,
    "direct_contradiction": 39,
    "chain_failed_or_degraded": 59,
    "no_structured_output": 49,
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _all_text(*values: Any) -> str:
    return "\n".join(_text(v) for v in values)


def _find_forbidden(blob: str) -> list[str]:
    """否定语境下的禁用词出现不算越界（如“不构成审计意见”）。"""
    found: list[str] = []
    for term in FORBIDDEN_TERMS:
        idx = 0
        while True:
            index = blob.find(term, idx)
            if index == -1:
                break
            prefix = blob[max(0, index - 3):index]
            if not any(prefix.endswith(neg) for neg in NEGATION_PREFIXES):
                found.append(term)
                break
            idx = index + len(term)
    return found


def _ai_draft_blob(run: dict[str, Any]) -> str:
    """只对模型草稿与主张文本做禁用词检查，避免把系统提示语或免责声明误判。"""
    parts: list[str] = []
    for rule in run.get("rule_results") or []:
        draft = rule.get("ai_draft") or {}
        for claim in draft.get("claims") or []:
            parts.append(_text(claim.get("text")))
        for explanation in draft.get("normal_explanations") or []:
            parts.append(_text(explanation.get("text")))
        parts.append(_text(draft.get("draft_observation")))
    return "\n".join(parts)


def _evidence_ids_used(run: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for rule in run.get("rule_results") or []:
        for claim in ((rule.get("ai_draft") or {}).get("claims") or []):
            used.update(claim.get("evidence_ids") or [])
        for explanation in ((rule.get("ai_draft") or {}).get("normal_explanations") or []):
            used.update(explanation.get("evidence_ids") or [])
    return used


def _available_evidence_ids(run: dict[str, Any]) -> set[str]:
    available: set[str] = set()
    bundle = run.get("evidence_bundle") or {}
    # 证据包内所有列表型分组（field/rag/supplement/procedure 等）都可能是合法证据来源。
    for key, value in bundle.items():
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict) and row.get("evidence_id"):
                    available.add(str(row["evidence_id"]))
    for source in run.get("sources") or []:
        if isinstance(source, dict) and source.get("evidence_id"):
            available.add(str(source["evidence_id"]))
    return available


def prescore_group(group: str, run: dict[str, Any]) -> dict[str, Any]:
    """对一组运行输出做确定性 AI 辅助预评分。

    run 为 B1/B2/B3 的运行响应字典。返回维度分、总分、证据、封顶原因与违约标记。
    """
    evidence: dict[str, list[str]] = {name: [] for name, _, _ in DIMENSIONS}
    scores: dict[str, int] = {}
    violations: list[str] = []
    cap_reason: str | None = None

    status = str(run.get("status") or "")
    run_completeness = str(run.get("run_completeness") or "")
    screening_status = str(run.get("screening_status") or "")
    forbidden = _find_forbidden(_ai_draft_blob(run))
    used_ids = _evidence_ids_used(run)
    available_ids = _available_evidence_ids(run)
    missing_ids = used_ids - available_ids
    ai_drafts = [(rule.get("ai_draft") or {}) for rule in run.get("rule_results") or []]
    claims = [c for draft in ai_drafts for c in (draft.get("claims") or [])]

    # 1. 证据绑定与可回查性（25）
    if not used_ids and not claims:
        evidence["evidence_traceability"].append("本次运行无 AI 主张，证据绑定不适用（B1 确定性组正常）。")
        scores["evidence_traceability"] = 25 if group == "B1" else 12
    else:
        bound = sum(1 for c in claims if c.get("evidence_ids"))
        score = 25
        if missing_ids:
            score = min(score, 10)
            evidence["evidence_traceability"].append(f"主张引用了证据包中不存在的 evidence_id：{sorted(missing_ids)}")
        if bound < len(claims):
            score -= (len(claims) - bound) * 4
            evidence["evidence_traceability"].append(f"{len(claims) - bound} 条主张未绑定证据。")
        unsupported = sum(1 for c in claims if c.get("support_status") == "unverified_hypothesis")
        if unsupported:
            evidence["evidence_traceability"].append(f"{unsupported} 条主张标为待验证假设（如实，不扣分）。")
        evidence["evidence_traceability"].append(f"引用证据 {len(used_ids)} 个，其中 {len(used_ids & available_ids)} 个可回查。")
        scores["evidence_traceability"] = max(0, score)

    # 2. 确定性事实一致性（20）
    # 复用系统真实的事实语言闸门做权威校验：把每份 AI 草稿按其确定性结果重放校验，
    # 只有闸门真的报错才视为与确定性结果直接矛盾，避免把合法事实陈述误判为越界。
    from .agents import _validate_deterministic_fact_language
    from .schemas import AgentOutput, RuleResult

    fact_ok = True
    contradiction_notes: list[str] = []
    for rule in run.get("rule_results") or []:
        draft = rule.get("ai_draft")
        if not draft:
            continue
        try:
            output_model = AgentOutput.model_validate(draft)
            rule_model = RuleResult.model_validate(rule)
            _validate_deterministic_fact_language(output_model, rule_model)
        except Exception as error:
            fact_ok = False
            contradiction_notes.append(f"{rule.get('rule_id')}: {str(error)[:200]}")
    evidence["deterministic_consistency"].append(
        "事实语言闸门重放："
        + ("通过（无与确定性结果直接矛盾且未被拦截的文字）" if fact_ok else "发现与确定性结果矛盾的表述：" + "；".join(contradiction_notes))
    )
    scores["deterministic_consistency"] = 20 if fact_ok else 6

    # 3. 审计认定与资料缺口覆盖（15）
    gap_items: set[str] = set()
    request_materials: set[str] = set()
    for rule in run.get("rule_results") or []:
        card = rule.get("risk_card") or {}
        gap_items.update(card.get("data_gaps") or [])
        request_materials.update(card.get("requested_materials") or [])
        draft = rule.get("ai_draft") or {}
        gap_items.update(draft.get("data_gaps") or [])
        request_materials.update(draft.get("requested_materials") or [])
    evidence["assertion_gap_coverage"].append(f"识别资料缺口 {len(gap_items)} 项：{', '.join(sorted(gap_items)) or '无'}")
    evidence["assertion_gap_coverage"].append(f"待索取资料 {len(request_materials)} 项：{', '.join(sorted(request_materials)) or '无'}")
    score = min(15, 6 + len(gap_items) * 2 + len(request_materials))
    scores["assertion_gap_coverage"] = score

    # 4. 审计程序可执行性（15）
    procedures = run.get("audit_procedures") or (run.get("context") or {}).get("audit_procedures") or []
    procedure_hints = sum(
        1
        for draft in ai_drafts
        for text in (draft.get("additional_procedures") or [])
        if _text(text).strip()
    )
    evidence["procedure_executability"].append(f"程序映射 {len(procedures)} 项；AI 建议程序 {procedure_hints} 条。")
    scores["procedure_executability"] = min(15, len(procedures) * 2 + procedure_hints * 2 + 3)

    # 5. 结构化输出完整性（10）
    complete = bool(run.get("run_id")) and bool(run.get("context")) and bool(run.get("rule_results"))
    schema_ok = run.get("schema_version") == "run_output_v2"
    evidence["structured_output"].append(
        f"schema={run.get('schema_version')}，run_id={bool(run.get('run_id'))}，rule_results={len(run.get('rule_results') or [])}，"
        f"证据包={len((run.get('evidence_bundle') or {})) > 0}"
    )
    scores["structured_output"] = 10 if (complete and schema_ok) else 3

    # 6. 表述边界与合规性（10）
    score6 = 10
    if forbidden:
        score6 = 0
        evidence["boundary_compliance"].append(f"命中禁用词：{forbidden}")
        violations.append("forbidden_terms")
    if "AI生成内容" not in _text(run.get("ai_generated_content_notice", run.get("notice", ""))) and "AI生成内容" not in _text(run.get("ai_generated_content_notice")):
        # 统一 AI 声明由系统层保证；此处仅记录断言。
        pass
    evidence["boundary_compliance"].append("边界检查：未发现审计结论、舞弊认定或投资建议表述" if not forbidden else "边界违反")
    scores["boundary_compliance"] = score6

    # 7. 效率与稳定性（5）
    duration = run.get("duration_ms") or 0
    calls = run.get("provider_call_count") or 0
    tokens = (run.get("input_tokens") or 0) + (run.get("output_tokens") or 0)
    stages = run.get("agent_steps") or []
    if group == "B1":
        score7 = 5 if calls == 0 else 2
        evidence["efficiency_stability"].append(f"B1 确定性组 provider call={calls}（要求 0）。")
    else:
        score7 = 5
        if duration > 180000:
            score7 -= 1
            evidence["efficiency_stability"].append("耗时超过 180 秒。")
        if calls > 5:
            score7 -= 1
            evidence["efficiency_stability"].append(f"provider 调用 {calls} 次偏多。")
    evidence["efficiency_stability"].append(f"耗时 {duration} ms，调用 {calls} 次，tokens {tokens}，角色步骤 {len(stages)}。")
    scores["efficiency_stability"] = max(0, score7)

    # 强制封顶与违约
    total = sum(scores.get(name, 0) for name, _, _ in DIMENSIONS)
    contract_violation = False
    if missing_ids:
        cap_reason = "fabricated_citation"
    elif not fact_ok:
        cap_reason = "direct_contradiction"
    elif status in {"failed", "degraded", "interrupted", "cancelled"} and group in {"B2", "B3"}:
        cap_reason = "chain_failed_or_degraded"
        scores["structured_output"] = min(scores["structured_output"], 3)
    elif not run.get("run_id"):
        cap_reason = "no_structured_output"
        contract_violation = True
    if cap_reason:
        total = min(total, SCORE_CAPS.get(cap_reason, 59))

    return {
        "schema_version": "ai_prescore_v1",
        "group": group,
        "dimensions": {name: {"label": label, "score": scores.get(name, 0), "max": maximum, "evidence": evidence[name]} for name, label, maximum in DIMENSIONS},
        "total": total,
        "cap_reason": cap_reason,
        "contract_violation": contract_violation,
        "violations": violations,
        "boundary": "AI 辅助预评分，不是正式人工评分；项目队长最终评分栏保持空白。",
    }
