"""自适应智能体编排：A0规划 → 受控工具 → Challenger反证 → 条件门禁。

设计边界（决赛与专业用途都必须成立）：
- 行动只来自共享动作池（evidence_plan 的 best_path/by_edge），编排器不另造行动；
- 工具只走 connectivity_tool_registry 白名单，每步记录回执、参数与输出指纹；
- Challenger 模型只能提出竞争解释；假设状态只能由条件门禁改变，
  模型文字不能宣告"已推翻/已证实"；
- 无模型密钥或调用失败时走确定性降级闭环，outcome=degraded_no_model，
  不伪称模型参与；未调用到的角色必须留下 skipped 记录。
状态机固定为：planned → running → evidence_received → evaluated → {replan | completed | blocked}
"""
from __future__ import annotations

import hashlib
import json
import re
import time

from pydantic import Field
from typing import Literal

from .connectivity_schemas import Contract
from .connectivity_tool_registry import ToolRequest, execute_tool

VERSION = "agent_orchestrator_v1"
STATE_MACHINE = ["planned", "running", "evidence_received", "evaluated",
                 "replan", "completed", "blocked"]
ROLES = ("A0_planner", "evidence", "challenger", "gate")
REVERSE_TERMS = ("未达到", "未实施", "口径变化", "剔除", "更正", "重述", "调整")
MAX_CHALLENGER_CALLS = 2


class ChallengerNote(Contract):
    """Challenger 提出的竞争解释：只是候选，状态仍由门禁决定。"""
    claim_id: str = Field(default="", max_length=60)
    edge_id: str = Field(default="", max_length=60)
    explanation: str = Field(min_length=5, max_length=600)
    testable_condition: str = Field(default="", max_length=400)
    discriminating_evidence: str = Field(default="", max_length=400)
    next_tool: Literal["search_registered_reports", "open_source_page", "lookup_ontology_rule", "recompute_decimal", "lookup_annual_comparison", "lookup_peer_sample"] | None = None
    tool_arguments: dict = Field(default_factory=dict)


class ChallengerProposals(Contract):
    hypotheses: list[ChallengerNote] = Field(default_factory=list, max_length=3)


def _digest(text: str) -> str:
    return hashlib.sha256(str(text or "").encode()).hexdigest()[:16]


def _event(run, round_id: str, role: str, *, tool_name: str = "", args_hash: str = "",
           source_hash: str = "", output_digest: str = "", evidence_ids=None,
           old_hypotheses=None, new_hypotheses=None, decision_reason: str = "",
           provider_call_id: str = "", token_cost=None, elapsed_ms: int = 0,
           outcome: str = "completed", stop_reason: str = "") -> dict:
    return {
        "run_id": getattr(run, "run_id", ""), "round_id": round_id, "role": role,
        "state_machine": STATE_MACHINE, "tool_name": tool_name,
        "validated_args_hash": args_hash, "source_hash": source_hash,
        "output_digest": output_digest, "evidence_ids": list(evidence_ids or []),
        "old_hypotheses": list(old_hypotheses or []), "new_hypotheses": list(new_hypotheses or []),
        "decision_reason": decision_reason,
        "actual_provider_call_id": provider_call_id, "token_cost": token_cost,
        "elapsed_ms": elapsed_ms, "outcome": outcome, "stop_reason": stop_reason,
    }


def _next_action(plan: dict, done_condition_ids: set[str], done_action_ids: set[str], remaining_cost: int = 8) -> dict | None:
    """从共享动作池取下一个未执行动作：先组合最优路径，再逐关系行动单。"""
    candidates = []
    for action in plan.get("best_path", []) + plan.get("second_path", []):
        candidates.append(action)
    for edge_actions in plan.get("by_edge", {}).values():
        candidates.extend(edge_actions)
    for action in candidates:
        if action["action_id"] in done_action_ids or action["condition_id"] in done_condition_ids:
            continue
        if action.get("requires_entity"):
            continue
        if not action.get("executable", True) or int(action.get("estimated_cost_tier", 1)) > remaining_cost:
            continue
        if action.get("dependency") and not action.get("dependency_satisfied"):
            continue
        return action
    return None


def _tool_request_for(run, action: dict) -> ToolRequest:
    """把行动映射到白名单工具；只使用行动自带的文档、页码与检索词。

    行动没有绑定具体文档时，回退到本次已登记文档做登记内检索，不越出登记范围。
    """
    if action.get("tool_name"):
        return ToolRequest(action["tool_name"], action.get("tool_arguments", {}))
    source = str(action.get("proposed_source") or "")
    document_id = source.split(" p", 1)[0].strip() if " p" in source else source.strip()
    registered = [doc.document_id for doc in getattr(run, "documents", [])]
    if document_id not in registered:
        document_id = next(iter(registered), "")
    page_match = re.search(r"p\s*(\d+)", source)
    terms = [str(term) for term in action.get("query_terms", [])][:5]
    if page_match and document_id:
        return ToolRequest("open_source_page",
                           {"document_id": document_id, "page": int(page_match.group(1)),
                            "terms": action.get("context_terms") or terms})
    if document_id and terms:
        return ToolRequest("search_registered_reports",
                           {"document_id": document_id, "terms": terms})
    return ToolRequest("lookup_annual_comparison", {"company": ""})


def _hypotheses_for_edge(revision: dict, edge_id: str) -> list[dict]:
    return [h for h in revision.get("hypotheses", []) if h.get("edge_id") == edge_id]


def _gate_transitions(revision: dict, action: dict, receipt: dict, notes: list[dict],
                      round_id: str) -> list[dict]:
    """按当前项目语境核对工具回执，再决定假设是否改变。

    否定词必须与项目或指标锚点处于同一段原文。
    回执中的目录、请求参数和说明文字不作为披露原文。
    明确出现其他年度的段落不能支持当前年度的改判。
    普通命中最多表示存在可调查的候选，不证明关联成立。
    新竞争解释写入同一账本，后续轮次可继续选取并检验。
    模型返回的其他关系编号不能越权改变当前关系。
    重复解释使用稳定编号去重，避免靠重复文字增加状态变化数。
    工具原页、文件身份和证据摘要随账本条目一起保存。
    模型意见和确定性门禁使用不同来源标签，不能互相冒充。
    """
    result = receipt.get("result") or {}
    text = str(result.get("quote") or "\n".join(hit.get("snippet", "") for hit in result.get("hits", [])))
    transitions = []
    edge_id = action.get("edge_id", "")
    live = [h for h in _hypotheses_for_edge(revision, edge_id) if h.get("status") in {"open", "plausible"}]
    # 否定词必须与当前项目/指标在同一段，而非扫描整页JSON。
    anchors = [term for term in action.get("context_terms", []) if len(term) >= 2]
    if not anchors:
        anchors = [term for term in action.get("query_terms", []) if len(term) >= 2]
    segments = [part for part in re.split(r"[。；;\n]", text) if any(term in part for term in anchors)]
    related = bool(segments)
    if action.get("period"):
        segments = [part for part in segments if not re.findall(r"20\d{2}年", part)
                    or str(action["period"]) + "年" in part]
        related = bool(segments)
    hit_reverse = receipt.get("status") == "hit" and related and any(term in part for part in segments for term in REVERSE_TERMS)
    hit_positive = receipt.get("status") == "hit" and related and not hit_reverse
    for hypothesis in live:
        old = hypothesis["status"]
        if hit_reverse:
            after, reason = "weakened", f"回执原文出现反向表述；解释强度下调（{round_id}）。"
        elif hit_positive and old == "open":
            after, reason = "plausible", f"行动命中相关原文；只记为候选成立，须逐条件核对后才能升级（{round_id}）。"
        else:
            continue
        transitions.append({
            "hypothesis_id": hypothesis["hypothesis_id"], "edge_id": edge_id,
            "before": old, "after": after, "reason": reason,
            "evidence_ids": [receipt.get("output_digest", "")],
            "round_id": round_id,
            "semantic_status": "program_gate_not_model_self_claim",
        })
        hypothesis["status"] = after
    for note in notes:
        if note.get("edge_id") and note["edge_id"] != edge_id:
            continue
        hypothesis_id = "MODEL-" + _digest(edge_id + note.get("explanation", ""))[:8].upper()
        if any(item["hypothesis_id"] == hypothesis_id for item in revision.get("hypotheses", [])):
            continue
        revision.setdefault("hypotheses", []).append({
            **note, "hypothesis_id": hypothesis_id, "edge_id": edge_id, "status": "open",
            "initial_status": "open", "source": "model", "evidence_ids": [receipt.get("output_digest", "")],
            "evidence_refs": result.get("evidence_refs", [])})
        transitions.append({
            "hypothesis_id": hypothesis_id,
            "edge_id": edge_id, "before": "", "after": "open",
            "reason": "Challenger 提出竞争解释；进入同一门禁账本，状态保持 open。",
            "evidence_ids": [receipt.get("output_digest", "")], "round_id": round_id,
            "semantic_status": "ai_assessed_not_independently_verified",
        })
    return transitions


def _challenger_payload(run, edge: dict, action: dict, receipt: dict) -> dict:
    quote = str((receipt.get("result") or {}).get("quote", ""))[:300]
    return {
        "run_id": getattr(run, "run_id", ""),
        "edge_id": edge.get("edge_id", ""),
        "claim_id": edge.get("claim_id", ""),
        "claim_statement": str(edge.get("claim_text") or edge.get("why") or "")[:300],
        "missing_conditions": edge.get("missing_conditions", []),
        "action_condition": action.get("condition", ""),
        "registered_documents": [{"document_id": doc.document_id, "pages": doc.pages} for doc in getattr(run, "documents", [])],
        "tool_receipt": {"tool_name": receipt.get("tool_name", ""),
                         "status": receipt.get("status", ""),
                         "quote": quote,
                         "evidence_refs": (receipt.get("result") or {}).get("evidence_refs", []),
                         "matched_terms": (receipt.get("result") or {}).get("matched_terms", [])},
    }


def run_investigation(root, run, *, bridge: dict, revision: dict, plan: dict,
                      challenger=None, max_rounds: int = 3,
                      enable_tools: bool = True, enable_challenger: bool = True,
                      before_model=None) -> dict:
    """主循环：每轮 A0取行动 → 工具取证 → Challenger反证 → 门禁评估 → 重排。

    challenger 为 None 或调用失败时走确定性降级；不会抛出模型异常中断整个运行。
    enable_tools/enable_challenger 供消融实验显式关闭部件；关闭时记 skipped 并注明
    "消融"，与无密钥的 degraded_no_model 降级路径区分。
    """
    events: list[dict] = []
    transitions: list[dict] = []
    model_notes: list[dict] = []
    tool_receipts: list[dict] = []
    original_plan = plan
    from copy import deepcopy
    plan = deepcopy(plan)
    called_roles: set[str] = set()
    seen_digests: set[str] = set()
    done_condition_ids: set[str] = set()
    done_action_ids: set[str] = set()
    challenger_calls = 0
    degraded = False
    tool_blocked = False
    stop_reason = ""
    edges_by_id = {edge.get("edge_id"): edge for edge in bridge.get("edges", [])}
    started = time.perf_counter()
    budget = plan.get("budget", {})
    remaining_cost = max(0, int(budget.get("call_budget", 3)))
    max_actions = max(0, int(budget.get("max_actions", max_rounds)))

    for round_no in range(1, max_rounds + 1):
        if len(tool_receipts) >= max_actions or remaining_cost <= 0:
            stop_reason = "tool_budget_exhausted"
            break
        round_id = f"INV-R{round_no:02d}"
        # A0：从共享动作池选择行动（planned）。
        action = _next_action(plan, done_condition_ids, done_action_ids, remaining_cost)
        if action is None:
            stop_reason = "no_actions"
            events.append(_event(run, round_id, "A0_planner", outcome="skipped",
                                 decision_reason="共享动作池没有剩余可执行行动。",
                                 stop_reason=stop_reason))
            called_roles.add("A0_planner")
            break
        called_roles.add("A0_planner")
        events.append(_event(run, round_id, "A0_planner", outcome="completed",
                             decision_reason=f"选择行动 {action['action_id']}（条件：{action.get('condition')}）。",
                             evidence_ids=action.get("target_hypotheses", [])))
        # running：受控工具执行；消融关闭时留下 skipped 记录，不伪称取证。
        if not enable_tools:
            called_roles.add("evidence")
            receipt = {"tool_name": "", "args_hash": "", "status": "ablated",
                       "output_digest": "", "source_hash": "", "elapsed_ms": 0,
                       "result": None, "reason": "消融运行：定向检索已关闭。"}
            events.append(_event(run, round_id, "evidence", outcome="skipped",
                                 decision_reason=receipt["reason"]))
        else:
            called_roles.add("evidence")
            request = _tool_request_for(run, action)
            receipt = execute_tool(root, run, request)
            remaining_cost -= int(action.get("estimated_cost_tier", 1))
            tool_receipts.append({**receipt, "round_id": round_id, "action_id": action["action_id"]})
            events.append(_event(run, round_id, "evidence", tool_name=receipt["tool_name"],
                                 args_hash=receipt["args_hash"], source_hash=receipt["source_hash"],
                                 output_digest=receipt["output_digest"],
                                 decision_reason=receipt.get("reason", "") or "工具回执已生成。",
                                 elapsed_ms=receipt["elapsed_ms"],
                                 outcome="completed" if receipt["status"] == "hit" else "blocked"))
        # evidence_received：增量判定。
        if receipt["output_digest"] and receipt["output_digest"] in seen_digests:
            stop_reason = "no_increment"
            events.append(_event(run, round_id, "gate", outcome="skipped",
                                 decision_reason="本轮工具输出与此前完全相同；无增量即停，不重复计费。",
                                 stop_reason=stop_reason))
            break
        if receipt["output_digest"]:
            seen_digests.add(receipt["output_digest"])
        if receipt["status"] == "ablated":
            edge = edges_by_id.get(action.get("edge_id"), {})
        elif receipt["status"] not in {"hit", "no_match"}:
            tool_blocked = True
            stop_reason = f"tool_{receipt['status']}"
            events.append(_event(run, round_id, "gate", outcome="blocked",
                                 decision_reason=receipt.get("reason", ""),
                                 stop_reason=stop_reason))
            done_action_ids.add(action["action_id"])
            break
        else:
            edge = edges_by_id.get(action.get("edge_id"), {})
        # evaluated：Challenger（可用才调用；消融关闭与降级分列）。
        notes: list[dict] = []
        if not enable_challenger:
            called_roles.add("challenger")
            events.append(_event(run, round_id, "challenger", outcome="skipped",
                                 decision_reason="消融运行：Challenger已关闭；反证仅由确定性门禁执行。"))
        elif challenger is not None and challenger_calls < MAX_CHALLENGER_CALLS:
            called_roles.add("challenger")
            try:
                if before_model:
                    before_model()
                challenger_calls += 1
                result, record = challenger(_challenger_payload(run, edge, action, receipt))
                # 每次实际调用记录进入统一预算账；主管线回调不再单独追加。
                if record and not any(existing.get("provider_call_id") and existing.get("provider_call_id") == record.get("provider_call_id") for existing in run.provider_calls):
                    run.provider_calls.append(record)
                # call_role 返回的已是 dict；兼容直接返回模型对象的桩/回调。
                notes = [note if isinstance(note, dict) else note.model_dump()
                         for note in result.get("hypotheses", [])]
                model_notes.extend(notes)
                usage = (record.get("input_tokens") or 0) + (record.get("output_tokens") or 0)
                events.append(_event(run, round_id, "challenger",
                                     decision_reason="Challenger 返回竞争解释；状态仍由门禁决定。",
                                     provider_call_id=record.get("provider_call_id", ""),
                                     token_cost=usage or None, elapsed_ms=record.get("elapsed_ms", 0)))
            except Exception as error:
                if isinstance(error, InterruptedError):
                    raise
                degraded = True
                failure = getattr(error, "record", None)
                if failure and failure not in run.provider_calls:
                    run.provider_calls.append(failure)
                detail = str(error)[:120] or type(error).__name__
                events.append(_event(run, round_id, "challenger", outcome="degraded",
                                     decision_reason=f"模型调用失败：{detail}；"
                                                     f"本轮仅用确定性门禁继续，不伪称模型参与。"))
        elif challenger is None:
            degraded = True
            events.append(_event(run, round_id, "challenger", outcome="skipped",
                                 decision_reason="未提供模型通道；确定性降级闭环继续执行。"))
        # 门禁评估（状态只由门禁改变）。
        called_roles.add("gate")
        old_statuses = {h["hypothesis_id"]: h.get("status", "") for h in revision.get("hypotheses", [])}
        round_transitions = _gate_transitions(revision, action, receipt, notes, round_id)
        transitions.extend(round_transitions)
        revision.setdefault("transitions", []).extend(round_transitions)
        new_statuses = {h["hypothesis_id"]: h.get("status", "") for h in revision.get("hypotheses", [])}
        events.append(_event(
            run, round_id, "gate",
            evidence_ids=[receipt["output_digest"]] if receipt["output_digest"] else [],
            old_hypotheses=[f"{key}:{value}" for key, value in old_statuses.items()],
            new_hypotheses=[f"{key}:{value}" for key, value in new_statuses.items()],
            decision_reason="状态只由回执原文与条件门禁改变；命中只到 plausible，反向证据才下调。",
            outcome="completed" if round_transitions else "no_change"))
        # replan：已完成条件退出候选，按新证据重排共享动作池。
        done_action_ids.add(action["action_id"])
        # 模型提出的下一工具也进入同一动作池，仍由注册表验证文档/参数。
        for hypothesis in revision.get("hypotheses", []):
            if hypothesis.get("edge_id") != action.get("edge_id") or not hypothesis.get("next_tool"):
                continue
            follow_id = "ACT-" + hypothesis["hypothesis_id"]
            if follow_id in done_action_ids:
                continue
            follow = {**action, "action_id": follow_id, "condition_id": follow_id,
                "condition": "竞争解释检验", "exact_target": hypothesis.get("testable_condition") or hypothesis["explanation"],
                "target_hypotheses": [hypothesis["hypothesis_id"]], "tool_name": hypothesis["next_tool"],
                "tool_arguments": hypothesis.get("tool_arguments", {})}
            pool = plan.setdefault("by_edge", {}).setdefault(action.get("edge_id", ""), [])
            if not any(item["action_id"] == follow_id for item in pool):
                pool.append(follow)
        from .connectivity_evidence_planner import rerank
        plan = rerank(plan, completed_conditions=[],
                      new_evidence_ids=[receipt["output_digest"]] if receipt["output_digest"] else [],
                      reviewed_actions=[action["action_id"]])
        events.append(_event(run, round_id, "A0_planner", outcome="completed",
                             decision_reason=f"行动已退出候选；重排后第一优先："
                                             f"{(plan.get('best_path') or [{}])[0].get('action_id', '无')}。"))
    else:
        stop_reason = stop_reason or "rounds_exhausted"

    for role in ROLES:
        if role not in called_roles:
            events.append(_event(run, "INV-END", role, outcome="skipped",
                                 decision_reason="该角色在本次调查中未被调用；按合同留下 skipped 记录。"))
    if not stop_reason:
        stop_reason = "all_actions_done"
    outcome = "blocked" if tool_blocked else ("degraded_no_model" if degraded else "completed")
    changed = sum(1 for item in transitions if item.get("before") != item.get("after"))
    original_plan.clear()
    original_plan.update(plan)
    summary = revision.setdefault("summary", {})
    summary["changed"] = sum(1 for item in revision.get("transitions", []) if item.get("before") != item.get("after"))
    for status in ("refuted", "weakened", "supported", "open", "plausible"):
        summary[status] = sum(item.get("status") == status for item in revision.get("hypotheses", []))
    return {
        "version": VERSION, "state_machine": STATE_MACHINE,
        "events": events, "transitions": transitions, "model_notes": model_notes,
        "final_plan": plan, "tool_receipts": tool_receipts,
        "summary": {
            "rounds": len({event["round_id"] for event in events if event["round_id"].startswith("INV-R")}),
            "tool_calls": len(tool_receipts),
            "challenger_calls": challenger_calls,
            "hypothesis_changes": changed,
            "model_notes": len(model_notes),
        },
        "outcome": outcome, "stop_reason": stop_reason,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "notice": "调查循环只消费共享动作池与受控工具；模型解释进入账本但状态由条件门禁决定。",
    }
