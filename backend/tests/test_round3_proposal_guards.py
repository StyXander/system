"""独立审查复现：候选数值门禁、无向关系去重和续分析修复。离线替身不证明模型能力。"""
from copy import deepcopy

import pytest

from app.connectivity_pipeline import integrate_proposals
from app.connectivity_schemas import AIAnalysis, RunRequest
from test_connectivity_hybrid import bridge_run
from test_connectivity_hybrid_upgrade import offline_pipeline


def proposal(run):
    return run.checks[0].model_dump(include={"rule_id", "title", "topic", "members", "conditions",
        "relationship_evidence", "explanation", "explanation_evidence"})


@pytest.mark.parametrize("role", ["A1", "A2"])
@pytest.mark.parametrize("field", ["explanation", "reasons", "assumptions"])
def test_proposal_hypothesis_rejects_invented_number_without_losing_relationship(role, field):
    run = bridge_run()
    p = proposal(run)
    h = {"hypothesis_id": "invented", "explanation": "设备投资可能解释范围差异", "status": "supported",
        "supporting_evidence": [{"occurrence_id": "SYN-0", "quote": "环保投入1200万元"}]}
    h[field] = "另有999999999万元投入能够解释差异" if field == "explanation" else ["另有999999999万元投入能够解释差异"]
    p["hypotheses"] = [h]
    delta = integrate_proposals(run, {"checks": [p]}, {r.occurrence_id for r in run.occurrences}, role)
    assert delta["accepted_check_ids"] == ["SYN-CHECK"]
    assert any(item["field"] == "hypotheses" and "无来源数字" in item["reason"] for item in delta["rejected"])
    assert not run.checks[0].hypotheses


@pytest.mark.parametrize("quote,oid", [("原文没有这一句", "SYN-0"), ("环保投入1200万元", "UNSENT")])
def test_bad_hypothesis_reference_does_not_discard_valid_relationship(quote, oid):
    run = bridge_run()
    p = proposal(run)
    p["hypotheses"] = [{"hypothesis_id": "bad-ref", "explanation": "设备投资可能解释范围差异",
        "supporting_evidence": [{"occurrence_id": oid, "quote": quote}]}]
    delta = integrate_proposals(run, {"checks": [p]}, {r.occurrence_id for r in run.occurrences}, "A2")
    assert delta["accepted_check_ids"] == ["SYN-CHECK"]
    assert "引用" in delta["rejected"][0]["reason"]
    assert not run.checks[0].hypotheses


def test_proposal_hypothesis_accepts_grounded_formula_and_conversion():
    run = bridge_run()
    p = proposal(run)
    p["hypotheses"] = [{"hypothesis_id": "derived", "explanation": "候选金额差为1200-1050=150。",
        "reasons": ["环保设备投入150万元=0.015亿元，范围仍待核实。"],
        "supporting_evidence": [{"occurrence_id": "ADJ", "quote": "环保设备投入150万元"}]}]
    delta = integrate_proposals(run, {"checks": [p]}, {r.occurrence_id for r in run.occurrences}, "A2")
    assert not delta["rejected"]
    assert run.checks[0].hypotheses[0].hypothesis_id == "derived"


def test_reversed_equality_updates_existing_identity_and_keeps_evidence():
    run = bridge_run()
    p = proposal(run)
    before = deepcopy(run.checks[0].relationship_evidence)
    p["members"][0]["role"], p["members"][1]["role"] = "right", "left"
    p["relationship_evidence"] = [{"occurrence_id": "SYN-0", "quote": "环保投入1200万元"}]
    delta = integrate_proposals(run, {"checks": [p]}, {r.occurrence_id for r in run.occurrences}, "A2")
    assert delta["accepted_check_ids"] == ["SYN-CHECK"]
    assert not delta["new_check_ids"]
    assert len(run.checks) == 1
    assert run.checks[0].members[0].role == "left"
    assert all(ref in run.checks[0].relationship_evidence for ref in before)


def test_a1_rejection_is_handed_to_a2_without_duplicate_a1_call(monkeypatch, tmp_path):
    run = bridge_run()
    pipeline = offline_pipeline(monkeypatch, run)
    monkeypatch.setattr(pipeline, 'retrieve_targeted_pages', lambda *args: [])
    bad = proposal(run)
    bad['members'][0]['role'] = 'component'
    calls, handoffs = [], []
    def offline(role, payload):
        calls.append(role)
        if role == 'A2':
            handoffs.extend(e for e in payload['collaboration_history']
                            if e.get('kind') == 'role_contribution' and e.get('role') == 'A1')
        response = {'checks': [bad]} if role == 'A1' else {'checks': []} if role == 'A2' else {'analyses': [], 'findings': []}
        return response, {'role': role, 'model': 'OFFLINE_TEST_DOUBLE', 'status': 'completed', 'performed': True}
    monkeypatch.setattr(pipeline, 'call_role', offline)
    pipeline.run_pipeline(tmp_path, RunRequest(pair_id='SYN-PAIR'))
    assert calls.count('A1') == 1
    assert handoffs and handoffs[0]['rejected']


def test_resume_candidate_repair_new_relationship_reaches_a3(monkeypatch, tmp_path):
    run = bridge_run()
    pipeline = offline_pipeline(monkeypatch, run)
    run.execution_mode = "three_agents"
    run.agent_steps = [{"role": "A1", "status": "completed"}]
    monkeypatch.setattr(pipeline, "retrieve_targeted_pages", lambda *args: [])
    calls = []
    seen_new = []
    bad = proposal(run)
    bad["members"][0]["role"] = "component"
    repaired = {"rule_id": "NAR-001", "title": "设备投资的范围说明", "topic": "environment",
        "members": [{"occurrence_id": "ADJ", "role": "occurrence"}], "conditions": [],
        "relationship_evidence": [{"occurrence_id": "ADJ", "quote": "环保设备投入150万元"}]}

    def offline(role, payload):
        calls.append(role)
        if role == "A2":
            response = {"checks": [repaired if payload["validation_feedback"] else bad]}
        else:
            new = next(c for c in payload["candidate_checks"] if c["rule_id"] == "NAR-001")
            seen_new.append(new["check_id"])
            analysis = AIAnalysis(check_id=new["check_id"], verdict="insufficient_basis",
                summary="设备投资与治理投入之间的包含关系尚未说明。",
                reasons=["原文没有说明设备投入是否已包含于治理投入。"],
                supporting_evidence=repaired["relationship_evidence"], next_actions=["核对设备投资在治理投入附注中的组成范围"])
            response = {"analyses": [analysis.model_dump()], "findings": []}
        return response, {"role": role, "model": "OFFLINE_TEST_DOUBLE", "status": "completed", "performed": True}

    monkeypatch.setattr(pipeline, "call_role", offline)
    result = pipeline.run_pipeline(tmp_path, RunRequest(pair_id="SYN-PAIR"), resume=run)
    assert calls[:3] == ["A2", "A2", "A3"]
    assert seen_new
    assert any(a.check_id == seen_new[0] and a.producer_role == "A3" for a in result.ai_analyses)


def test_relationship_evidence_quote_must_belong_to_its_own_occurrence():
    """实跑复现：模型把研发投入的引文挂到研发人员行上，导出时无法逐字回溯。"""
    run = bridge_run()
    p = proposal(run)
    p["relationship_evidence"] = [
        {"occurrence_id": "SYN-0", "quote": "环保投入1200万元"},
        {"occurrence_id": "SYN-0", "quote": "研发投入金额（元） |  | 449,183,817.50"},
    ]
    delta = integrate_proposals(run, {"checks": [p]}, {r.occurrence_id for r in run.occurrences}, "A2")
    refs = run.checks[0].relationship_evidence
    assert all("研发投入金额" not in ref.quote for ref in refs)
    assert any(item.get("field") == "relationship_evidence" for item in delta["rejected"])
    assert delta["accepted_check_ids"] == ["SYN-CHECK"]


def test_new_relationship_with_only_unverifiable_quotes_is_not_adopted():
    run = bridge_run()
    extra = run.occurrences[0].model_copy(update={"occurrence_id": "SYN-2"})
    run.occurrences.append(extra)
    p = proposal(run)
    p["rule_id"], p["title"] = "EQ-001", "合成新关系"
    p["members"] = [{"occurrence_id": "SYN-0", "role": "left"}, {"occurrence_id": "SYN-2", "role": "right"}]
    p["relationship_evidence"] = [
        {"occurrence_id": "SYN-0", "quote": "研发投入金额（元） |  | 449,183,817.50"},
        {"occurrence_id": "SYN-2", "quote": "研发投入金额（元） |  | 449,183,817.50"},
    ]
    p["explanation_evidence"] = []
    before = len(run.checks)
    delta = integrate_proposals(run, {"checks": [p]}, {r.occurrence_id for r in run.occurrences}, "A2")
    assert len(run.checks) == before
    assert any("没有可逐字回溯" in item["reason"] for item in delta["rejected"])
