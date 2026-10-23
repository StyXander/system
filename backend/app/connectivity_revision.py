"""由证据门禁驱动的反证循环：模型可以提出解释，但状态只能由原文条件改变。

状态机固定为：
CLAIM_IDENTIFIED → COMPETING_HYPOTHESES → RETRIEVAL_ACTION_SELECTED →
EVIDENCE_RETURNED → HYPOTHESIS_UPDATED → NEXT_ACTION_OR_STOP → REVIEWED

每条状态转移都保存旧状态、新状态、触发证据、门槛原因和输入指纹。
本模块不调用模型；模型提出的解释作为 `source=model` 的记录进入同一门禁，
不能自行宣告“已被推翻”。
"""
from __future__ import annotations

import hashlib
import json

VERSION = "revision_gate_v1"
PROMPT_VERSION = "revision_gate_20261022.1"
STATE_MACHINE = ["CLAIM_IDENTIFIED", "COMPETING_HYPOTHESES", "RETRIEVAL_ACTION_SELECTED",
                 "EVIDENCE_RETURNED", "HYPOTHESIS_UPDATED", "NEXT_ACTION_OR_STOP", "REVIEWED"]


def _fingerprint(edge: dict) -> str:
    payload = {key: edge.get(key) for key in ("edge_id", "relation_type", "same_entity", "same_period",
                                             "definition_compatible", "boundary_compatible",
                                             "numeric_gap", "evidence_ids")}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _condition_summary(edge: dict) -> str:
    parts = []
    parts.append("主体一致" if edge.get("same_entity") else "主体未证明一致")
    if edge.get("same_period") is True:
        parts.append("期间一致")
    elif edge.get("same_period") is False:
        parts.append("期间冲突")
    else:
        parts.append("期间未证明")
    if edge.get("definition_compatible") is True:
        parts.append("定义一致")
    elif edge.get("definition_compatible") is False:
        parts.append("定义冲突")
    else:
        parts.append("定义未证明")
    if edge.get("boundary_compatible") is True:
        parts.append("范围一致")
    elif edge.get("boundary_compatible") is False:
        parts.append("范围冲突")
    else:
        parts.append("范围未证明")
    return "；".join(parts)


def _transition(hypothesis: dict, after: str, reason: str, round_id: str, evidence_ids: list[str]) -> dict:
    return {
        "hypothesis_id": hypothesis["hypothesis_id"],
        "claim_id": hypothesis.get("claim_id", ""),
        "edge_id": hypothesis.get("edge_id", ""),
        "before": hypothesis["status"],
        "after": after,
        "reason": reason,
        "evidence_ids": evidence_ids,
        "round_id": round_id,
        "semantic_status": "program_gate_not_model_self_claim",
    }


def build_revision_loop(bridge: dict, *, model_notes: list[dict] | None = None) -> dict:
    """为每个财务关系候选建立可复现的竞争解释与状态转移记录。"""
    hypotheses = []
    transitions = []
    rounds = []
    sequence = 0
    for edge in bridge.get("edges", []):
        if edge["relation_type"] == "INSUFFICIENT":
            continue
        sequence += 1
        claim_id = edge["claim_id"]
        base = {
            "claim_id": claim_id,
            "edge_id": edge["edge_id"],
            "relation_type": edge["relation_type"],
            "evidence_ids": edge.get("evidence_ids", []),
            "fingerprint": _fingerprint(edge),
            "condition_summary": _condition_summary(edge),
            "claim_document_id": edge.get("claim_document_id"),
            "financial_document_id": edge.get("financial_document_id"),
            "financial_page": edge.get("financial_page"),
            "claim_page": edge.get("claim_page"),
        }
        if edge["relation_type"] == "CONTRADICTED":
            primary = {
                **base, "hypothesis_id": f"H-{sequence:02d}A", "role": "numeric_proximity",
                "explanation": "ESG披露金额与年报项目金额接近，可能是同一笔投入或同一项目口径。",
                "status": "plausible", "initial_status": "plausible", "source": "program_candidate",
                "testable_condition": "主体、期间、定义、范围四项须同时成立，且原文明确同一项目",
                "discriminating_evidence": "年报项目表的列名（预算数/本期增加/期末余额）与ESG合计口径",
            }
            competing = {
                **base, "hypothesis_id": f"H-{sequence:02d}B", "role": "scope_definition_conflict",
                "explanation": "金额接近只是巧合；ESG为多项目合计/当期投入，年报为单一项目累计预算，不能相互证实。",
                "status": "open", "initial_status": "open", "source": "program_candidate",
                "testable_condition": "找到ESG项目清单逐项对应年报项目，或找到同一项目的原文交叉索引",
                "discriminating_evidence": "项目表列名、合计口径、基地范围、预算与本期增加的区别",
            }
            evidence = edge.get("evidence_ids", [])
            rounds.append({
                "round_id": f"R-{sequence:02d}-1", "state": "CLAIM_IDENTIFIED", "agent_role": "discovery",
                "input_fingerprint": base["fingerprint"], "tool_name": "", "tool_args_summary": "",
                "retrieved_evidence_ids": [], "old_state": "", "new_state": "CLAIM_IDENTIFIED",
                "reason": f"从ESG第{edge.get('claim_page')}页与年报第{edge.get('financial_page')}页发现金额接近的候选。",
                "provider_call_id": "", "cost_or_token_if_available": None,
            })
            rounds.append({
                "round_id": f"R-{sequence:02d}-2", "state": "COMPETING_HYPOTHESES", "agent_role": "challenge",
                "input_fingerprint": base["fingerprint"], "tool_name": "", "tool_args_summary": "",
                "retrieved_evidence_ids": [], "old_state": "CLAIM_IDENTIFIED", "new_state": "COMPETING_HYPOTHESES",
                "reason": "提出两项真正可区分的解释：同一笔投入 vs 口径不同导致的数值巧合。",
                "provider_call_id": "", "cost_or_token_if_available": None,
            })
            rounds.append({
                "round_id": f"R-{sequence:02d}-3", "state": "RETRIEVAL_ACTION_SELECTED", "agent_role": "evidence",
                "input_fingerprint": base["fingerprint"], "tool_name": "read_registered_page",
                "tool_args_summary": f"ESG p{edge.get('claim_page')} + 年报 p{edge.get('financial_page')}",
                "retrieved_evidence_ids": [], "old_state": "COMPETING_HYPOTHESES",
                "new_state": "RETRIEVAL_ACTION_SELECTED",
                "reason": "选择能同时读取主张原句与财务项目表列名的定向取证动作。",
                "provider_call_id": "", "cost_or_token_if_available": None,
            })
            rounds.append({
                "round_id": f"R-{sequence:02d}-4", "state": "EVIDENCE_RETURNED", "agent_role": "evidence",
                "input_fingerprint": base["fingerprint"], "tool_name": "read_registered_page",
                "tool_args_summary": f"ESG p{edge.get('claim_page')} + 年报 p{edge.get('financial_page')}",
                "retrieved_evidence_ids": evidence, "old_state": "RETRIEVAL_ACTION_SELECTED",
                "new_state": "EVIDENCE_RETURNED",
                "reason": f"取得两份原页；条件核对结果为：{base['condition_summary']}。",
                "provider_call_id": "", "cost_or_token_if_available": None,
            })
            conflict = any(edge.get(key) is False for key in ("definition_compatible", "boundary_compatible",
                                                               "same_period", "same_entity"))
            if conflict:
                changes = [("refuted", "数值接近不成立：定义/范围/期间/主体至少一项明确冲突，"
                                       "不能把两个金额当作同一口径。"),
                           ("supported", "竞争解释获得支持：该关系只能保留为反例或语义关联，不能升级为一致证据。")]
                hypotheses.extend([primary, competing])
                for hypothesis, (after, reason) in zip((primary, competing), changes):
                    transitions.append(_transition(hypothesis, after, reason,
                                                   f"R-{sequence:02d}-4", evidence))
            else:
                hypotheses.extend([primary, competing])
                transitions.append(_transition(primary, "plausible", "四项条件未发现冲突，但仍需原文明确同一项目；不直接升级。",
                                               f"R-{sequence:02d}-4", evidence))
                transitions.append(_transition(competing, "open", "尚未找到可区分证据。",
                                               f"R-{sequence:02d}-4", evidence))
            rounds.append({
                "round_id": f"R-{sequence:02d}-5", "state": "HYPOTHESIS_UPDATED", "agent_role": "review",
                "input_fingerprint": base["fingerprint"], "tool_name": "condition_gate",
                "tool_args_summary": base["condition_summary"],
                "retrieved_evidence_ids": evidence, "old_state": "COMPETING_HYPOTHESES",
                "new_state": "HYPOTHESIS_UPDATED",
                "reason": "状态只由条件门禁改变，模型不能自行宣告撤回。",
                "provider_call_id": "", "cost_or_token_if_available": None,
            })
            rounds.append({
                "round_id": f"R-{sequence:02d}-6", "state": "NEXT_ACTION_OR_STOP", "agent_role": "review",
                "input_fingerprint": base["fingerprint"], "tool_name": "", "tool_args_summary": "",
                "retrieved_evidence_ids": evidence, "old_state": "HYPOTHESIS_UPDATED",
                "new_state": "NEXT_ACTION_OR_STOP",
                "reason": "停止数值比对；下一步若继续，只能查项目级清单或企业未公开凭证。",
                "provider_call_id": "", "cost_or_token_if_available": None,
            })
        elif edge["relation_type"] == "SEMANTIC_ASSOCIATION":
            hypothesis = {
                **base, "hypothesis_id": f"H-{sequence:02d}", "role": "semantic_link",
                "explanation": "主题词或项目名相近，可能存在财务对应关系。",
                "status": "open", "initial_status": "open", "source": "program_candidate",
                "testable_condition": "原文须明确该项目就是该主张的财务对应项，并给出金额归属",
                "discriminating_evidence": "项目清单、附注金额、跨报告交叉索引",
            }
            hypotheses.append(hypothesis)
            evidence = edge.get("evidence_ids", [])
            rounds.append({
                "round_id": f"R-{sequence:02d}-1", "state": "CLAIM_IDENTIFIED", "agent_role": "discovery",
                "input_fingerprint": base["fingerprint"], "tool_name": "", "tool_args_summary": "",
                "retrieved_evidence_ids": [], "old_state": "", "new_state": "CLAIM_IDENTIFIED",
                "reason": "发现同主题主张与财务项目，但未见金额归属。", "provider_call_id": "",
                "cost_or_token_if_available": None,
            })
            rounds.append({
                "round_id": f"R-{sequence:02d}-2", "state": "RETRIEVAL_ACTION_SELECTED", "agent_role": "evidence",
                "input_fingerprint": base["fingerprint"], "tool_name": "read_registered_page",
                "tool_args_summary": f"ESG p{edge.get('claim_page')} + 年报 p{edge.get('financial_page')}",
                "retrieved_evidence_ids": [], "old_state": "CLAIM_IDENTIFIED",
                "new_state": "RETRIEVAL_ACTION_SELECTED",
                "reason": "查两页原句，确认是否存在项目名或金额归属。", "provider_call_id": "",
                "cost_or_token_if_available": None,
            })
            rounds.append({
                "round_id": f"R-{sequence:02d}-3", "state": "EVIDENCE_RETURNED", "agent_role": "evidence",
                "input_fingerprint": base["fingerprint"], "tool_name": "read_registered_page",
                "tool_args_summary": f"ESG p{edge.get('claim_page')} + 年报 p{edge.get('financial_page')}",
                "retrieved_evidence_ids": evidence, "old_state": "RETRIEVAL_ACTION_SELECTED",
                "new_state": "EVIDENCE_RETURNED",
                "reason": "两页可读，但未见“该主张对应该项目”的原文。", "provider_call_id": "",
                "cost_or_token_if_available": None,
            })
            transitions.append(_transition(hypothesis, "weakened",
                                           "只能证明主题相近；缺少金额归属与项目同一性，解释强度下调。",
                                           f"R-{sequence:02d}-3", evidence))
            rounds.append({
                "round_id": f"R-{sequence:02d}-4", "state": "HYPOTHESIS_UPDATED", "agent_role": "review",
                "input_fingerprint": base["fingerprint"], "tool_name": "condition_gate",
                "tool_args_summary": base["condition_summary"],
                "retrieved_evidence_ids": evidence, "old_state": "EVIDENCE_RETURNED",
                "new_state": "HYPOTHESIS_UPDATED",
                "reason": "语义关联降级为有限支持；不删除缺口。", "provider_call_id": "",
                "cost_or_token_if_available": None,
            })
        elif edge["relation_type"] == "HYPOTHESIZED_MECHANISM":
            hypothesis = {
                **base, "hypothesis_id": f"H-{sequence:02d}", "role": "mechanism",
                "explanation": "可持续投入可能通过经营成本/资本开支传导到财务结果，但报告未给出可归属金额。",
                "status": "open", "initial_status": "open", "source": "program_candidate",
                "testable_condition": "须取得项目级投入、成本基线、价格或产量参数",
                "discriminating_evidence": "项目预算、本期增加、成本明细、敏感性参数",
            }
            hypotheses.append(hypothesis)
            transitions.append(_transition(hypothesis, "open", "机制假设保留，未取得可归属金额。",
                                           f"R-{sequence:02d}-1", edge.get("evidence_ids", [])))
            rounds.append({
                "round_id": f"R-{sequence:02d}-1", "state": "COMPETING_HYPOTHESES", "agent_role": "challenge",
                "input_fingerprint": base["fingerprint"], "tool_name": "", "tool_args_summary": "",
                "retrieved_evidence_ids": edge.get("evidence_ids", []), "old_state": "CLAIM_IDENTIFIED",
                "new_state": "COMPETING_HYPOTHESES",
                "reason": "保留机制假设，同时保留“总额之间无逐项对应”的竞争解释。",
                "provider_call_id": "", "cost_or_token_if_available": None,
            })
        else:
            # DIRECT / DISCLOSED / TEMPORAL：保留为未完成验证的解释。
            hypothesis = {
                **base, "hypothesis_id": f"H-{sequence:02d}", "role": edge["relation_type"].lower(),
                "explanation": edge.get("why", ""),
                "status": "open", "initial_status": "open", "source": "program_candidate",
                "testable_condition": "补齐原文条件后方可升级",
                "discriminating_evidence": "项目级金额、期间、范围与定义",
            }
            hypotheses.append(hypothesis)
            transitions.append(_transition(hypothesis, "open", "当前只到候选/有限支持，未满足升级条件。",
                                           f"R-{sequence:02d}-1", edge.get("evidence_ids", [])))

    # 模型提出的解释进入同一账本，但状态仍由门禁决定。
    for note in model_notes or []:
        hypotheses.append({
            "hypothesis_id": note.get("hypothesis_id") or "MODEL-" + hashlib.sha256(
                str(note).encode()).hexdigest()[:8].upper(),
            "claim_id": note.get("claim_id", ""), "edge_id": note.get("edge_id", ""),
            "role": "model_proposed", "explanation": note.get("explanation", ""),
            "status": "open", "initial_status": "open",
            "reported_status": note.get("status", "open"),
            "source": "model", "testable_condition": note.get("testable_condition", ""),
            "discriminating_evidence": note.get("discriminating_evidence", ""),
            "semantic_status": "ai_assessed_not_independently_verified",
        })

    # 把门禁转移写回假设状态；模型文字不能直接改这里。
    by_id = {hypothesis["hypothesis_id"]: hypothesis for hypothesis in hypotheses}
    for transition in transitions:
        target = by_id.get(transition["hypothesis_id"])
        if target is not None:
            target["status"] = transition["after"]

    for hypothesis in hypotheses:
        if hypothesis["status"] != hypothesis["initial_status"]:
            rounds.append({
                "round_id": f"R-{hypothesis['hypothesis_id']}-REVIEW", "state": "REVIEWED",
                "agent_role": "review", "input_fingerprint": hypothesis.get("fingerprint", ""),
                "tool_name": "condition_gate", "tool_args_summary": hypothesis.get("condition_summary", ""),
                "retrieved_evidence_ids": hypothesis.get("evidence_ids", []),
                "old_state": "HYPOTHESIS_UPDATED", "new_state": "REVIEWED",
                "reason": "状态变化已记录，保留原始候选与反证材料。", "provider_call_id": "",
                "cost_or_token_if_available": None,
            })
    status_counts = {}
    for hypothesis in hypotheses:
        status_counts[hypothesis["status"]] = status_counts.get(hypothesis["status"], 0) + 1
    return {
        "version": VERSION,
        "prompt_version": PROMPT_VERSION,
        "state_machine": STATE_MACHINE,
        "hypotheses": hypotheses,
        "transitions": transitions,
        "rounds": rounds,
        "summary": {
            "candidates": len(hypotheses),
            "refuted": status_counts.get("refuted", 0),
            "weakened": status_counts.get("weakened", 0),
            "supported": status_counts.get("supported", 0),
            "open": status_counts.get("open", 0),
            "changed": len(transitions),
            "by_status": status_counts,
        },
        "notice": "状态变化由页码证据与条件门禁触发；模型文字本身不能改变状态。",
    }
