"""自适应智能体编排：受控闭环、无增量即停、模型降级与角色 skipped 记录。

测试不调用真实模型；Challenger 用桩替代，验证状态只由门禁改变。
"""
from __future__ import annotations

import pymupdf

from backend.app import connectivity_extraction
from backend.app.connectivity_agent_orchestrator import (
    ChallengerNote, ChallengerProposals, run_investigation)
from backend.app.connectivity_schemas import ConnectivityRun, ReportDocument, RunRequest


def _docs():
    return [
        ReportDocument(document_id="DOC-A", case_id="CASE-2025", company_id="CO", company="测试钢铁",
                       report_type="ESG", period="2025", source_url="https://example.invalid/esg.pdf",
                       file_sha256="a" * 64, pages=1),
        ReportDocument(document_id="DOC-B", case_id="CASE-2025", company_id="CO", company="测试钢铁",
                       report_type="AR", period="2025", source_url="https://example.invalid/ar.pdf",
                       file_sha256="b" * 64, pages=1),
    ]


def _run(tmp_path, monkeypatch, page_text: str):
    pdf = pymupdf.open()
    pdf_page = pdf.new_page()
    pdf_page.insert_text((72, 72), page_text, fontname="china-s")
    path = tmp_path / "src.pdf"
    pdf.save(str(path))
    pdf.close()
    monkeypatch.setattr(connectivity_extraction, "source_path", lambda root, doc: str(path))
    return ConnectivityRun(run_id="RUN-INV", company="测试钢铁", period="2025", documents=_docs())


def _plan(page: int = 1, edge_id: str = "EDGE-1", count: int = 2):
    """两个动作都打开同一页：第二轮输出指纹相同，必须触发无增量即停。"""
    return {
        "best_path": [
            {"action_id": f"ACT-{index}", "condition_id": f"{edge_id}:条件{index}",
             "edge_id": edge_id, "condition": f"条件{index}",
             "proposed_source": f"DOC-B p{page}", "query_terms": ["预算数"],
             "requires_entity": False, "executable": True, "exact_target": f"核对 DOC-B p{page}",
             "purpose": "补齐条件",
             "estimated_cost_tier": 1, "gap_coverage": 1, "expected_discrimination": 1}
            for index in range(1, count + 1)
        ],
        "second_path": [], "by_edge": {},
    }


def _revision(edge_id: str = "EDGE-1"):
    return {"hypotheses": [
        {"hypothesis_id": "H-01A", "edge_id": edge_id, "status": "open"},
        {"hypothesis_id": "H-01B", "edge_id": edge_id, "status": "open"},
    ], "transitions": [], "rounds": []}


CONTRACT_FIELDS = {"run_id", "round_id", "role", "state_machine", "tool_name",
                   "validated_args_hash", "source_hash", "output_digest", "evidence_ids",
                   "old_hypotheses", "new_hypotheses", "decision_reason",
                   "actual_provider_call_id", "token_cost", "elapsed_ms",
                   "outcome", "stop_reason"}


def test_deterministic_loop_without_model_degrades_honestly(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, "预算数 本期增加 期末余额")
    investigation = run_investigation(None, run, bridge={"edges": []},
                                      revision=_revision(), plan=_plan(), challenger=None)
    assert investigation["outcome"] == "degraded_no_model"
    assert investigation["stop_reason"] == "no_increment"
    roles = [event["role"] for event in investigation["events"]]
    assert {"A0_planner", "evidence", "challenger", "gate"} <= set(roles)
    challenger_events = [event for event in investigation["events"] if event["role"] == "challenger"]
    assert all(event["outcome"] in {"skipped", "degraded"} for event in challenger_events)
    assert all(set(event) == CONTRACT_FIELDS for event in investigation["events"])
    # 门禁只允许命中到 plausible，不得升级为 supported/refuted。
    statuses = {h["hypothesis_id"]: h["status"] for h in _revision()["hypotheses"]}
    assert set(statuses.values()) <= {"open", "plausible", "weakened"}
    assert investigation["summary"]["challenger_calls"] == 0


def test_hit_only_goes_plausible_and_reverse_evidence_weakens(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, "预算数 本期增加 期末余额")
    revision = _revision()
    run_investigation(None, run, bridge={"edges": []}, revision=revision,
                      plan=_plan(count=1), challenger=None)
    assert all(h["status"] == "plausible" for h in revision["hypotheses"])

    run2 = _run(tmp_path, monkeypatch, "预算数 未达到 口径变化")
    revision2 = _revision()
    second = run_investigation(None, run2, bridge={"edges": []}, revision=revision2,
                               plan=_plan(count=1), challenger=None)
    assert all(h["status"] == "weakened" for h in revision2["hypotheses"])
    weakened = [item for item in second["transitions"] if item["after"] == "weakened"]
    assert weakened and all(item["semantic_status"] == "program_gate_not_model_self_claim"
                            for item in weakened)


def test_challenger_notes_enter_ledger_without_status_power(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, "预算数 本期增加")
    bridge = {"edges": [{"edge_id": "EDGE-1", "claim_id": "CLAIM-1"}]}
    calls = []

    def fake_challenger(payload):
        calls.append(payload)
        result = ChallengerProposals(hypotheses=[ChallengerNote(
            edge_id=payload["edge_id"], explanation="金额接近可能是同一笔投入。",
            testable_condition="原文明确同一项目", discriminating_evidence="项目表列名")])
        record = {"provider_call_id": "CALL-1", "input_tokens": 10, "output_tokens": 5,
                  "elapsed_ms": 3, "role": "challenger", "performed": True, "status": "completed"}
        return result.model_dump(), record

    investigation = run_investigation(None, run, bridge=bridge,
                                      revision=_revision(), plan=_plan(count=1),
                                      challenger=fake_challenger)
    assert len(calls) == 1 and calls[0]["edge_id"] == "EDGE-1"
    assert investigation["summary"]["challenger_calls"] == 1
    assert investigation["model_notes"] and investigation["model_notes"][0]["explanation"]
    challenger_events = [event for event in investigation["events"] if event["role"] == "challenger"]
    assert challenger_events[0]["actual_provider_call_id"] == "CALL-1"
    assert challenger_events[0]["token_cost"] == 15
    # 竞争解释进入账本，但状态保持 open，且标记为模型来源。
    ledger = investigation["transitions"]
    model_rows = [item for item in ledger if item["semantic_status"] == "ai_assessed_not_independently_verified"]
    assert model_rows and all(item["after"] == "open" for item in model_rows)


def test_challenger_failure_keeps_deterministic_loop(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, "预算数 本期增加")

    def broken_challenger(payload):
        raise ValueError("MODEL_CONFIG_MISSING")

    investigation = run_investigation(None, run, bridge={"edges": []},
                                      revision=_revision(), plan=_plan(count=1),
                                      challenger=broken_challenger)
    assert investigation["outcome"] == "degraded_no_model"
    degraded = [event for event in investigation["events"]
                if event["role"] == "challenger" and event["outcome"] == "degraded"]
    assert degraded and "MODEL_CONFIG_MISSING" in degraded[0]["decision_reason"]
    assert investigation["summary"]["tool_calls"] >= 1


def test_no_actions_logs_skipped_roles(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, "预算数")
    plan = {"best_path": [], "second_path": [], "by_edge": {}}
    investigation = run_investigation(None, run, bridge={"edges": []},
                                      revision=_revision(), plan=plan, challenger=None)
    assert investigation["stop_reason"] == "no_actions"
    skipped = {event["role"] for event in investigation["events"] if event["outcome"] == "skipped"}
    assert {"A0_planner", "evidence", "challenger", "gate"} <= skipped


def test_unregistered_document_source_falls_back_to_registered(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, "预算数 未达到")
    revision = _revision()
    plan = {"best_path": [{"action_id": "ACT-X", "condition_id": "E:反向检索", "edge_id": "EDGE-1",
                           "condition": "反向检索", "proposed_source": "已登记报告",
                           "query_terms": ["未达到"], "requires_entity": False, "executable": True,
                           "exact_target": "检索反向披露", "purpose": "寻找反向材料",
                           "estimated_cost_tier": 1, "gap_coverage": 1, "expected_discrimination": 1}],
            "second_path": [], "by_edge": {}}
    investigation = run_investigation(None, run, bridge={"edges": []},
                                      revision=revision, plan=plan, challenger=None)
    evidence = [event for event in investigation["events"] if event["role"] == "evidence"]
    assert evidence and evidence[0]["tool_name"] == "search_registered_reports"
    assert evidence[0]["outcome"] == "completed"
    assert all(h["status"] == "weakened" for h in revision["hypotheses"])


def test_run_request_accepts_adaptive_mode_and_run_has_investigation_field():
    request = RunRequest(pair_id="PAIR-2025", mode="adaptive_agents")
    assert request.mode == "adaptive_agents"
    for mode in ("calculation_only", "three_agents", "single_model"):
        assert RunRequest(pair_id="PAIR-2025", mode=mode).mode == mode
    run = ConnectivityRun(run_id="RUN-X", company="测试钢铁", period="2025", documents=_docs())
    assert run.investigation == {}
