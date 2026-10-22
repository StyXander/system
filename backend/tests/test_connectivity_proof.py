"""主动补证和证据图专项：全部合成样例，仅验证程序合同。"""
from types import SimpleNamespace as N

from backend.app.connectivity_proof import build_proof_graph, plan_procedures, procedure_effect


def sample(status="unknown", quote="定义为"):
    ar = N(document_id="AR", report_type="AR")
    esg = N(document_id="ESG", report_type="ESG")
    a = N(occurrence_id="A", document_id="AR", pdf_page=12, label="研发投入",
          value="120", unit="万元", context="研发投入定义为当期投入金额")
    b = N(occurrence_id="B", document_id="ESG", pdf_page=8, label="研究开发投入",
          value="120", unit="万元", context="研究开发投入定义为当期投入金额")
    cond = N(name="定义", status=status, evidence=[N(occurrence_id="A", quote=quote)])
    check = N(check_id="C1", title="跨报告研发投入", cross_document=True,
              conditions=[cond], members=[N(occurrence_id="A", role="left"),
                                          N(occurrence_id="B", role="right")],
              hypotheses=[], relationship_evidence=[N(occurrence_id="B", quote="研究开发投入")],
              basis_level="L1", conclusion_level="limited_support")
    return N(documents=[ar, esg], occurrences=[a, b], checks=[check])


def test_procedure_plan_bounded_and_deterministic():
    run = sample()
    one = plan_procedures(run.checks, round_number=1, budget=1)
    assert one == plan_procedures(run.checks, round_number=1, budget=1)
    assert one["selected_check_ids"] == ["C1"]
    assert "定义" in one["procedures"][0]["unresolved_conditions"]


def test_no_evidence_gap_stops_first_round():
    run = sample(status="supported")
    assert plan_procedures(run.checks, round_number=1)["stop_reason"] == "no_evidence_gap"
    assert plan_procedures(run.checks, round_number=2)["selected_check_ids"] == ["C1"]


def test_state_change_not_hit_count_measures_effect():
    before = sample()
    after = sample(status="supported")
    plan = plan_procedures(before.checks, round_number=1)
    effect = procedure_effect(plan, before.checks, after.checks,
        [{"check_id": "C1", "new_evidence_ids": ["A"]}])
    assert effect["executed"] == 1 and effect["upgraded"] == 1
    unchanged = procedure_effect(plan, before.checks, before.checks,
        [{"check_id": "C1", "new_evidence_ids": ["A", "B"]}])
    assert unchanged["upgraded"] == 0


def test_graph_rejects_nonverbatim_quote():
    graph = build_proof_graph(sample(status="supported", quote="原文中不存在的引用"))
    assert graph["paths"][0]["trace"] == "incomplete"
    assert "定义:quote_unverified" in graph["paths"][0]["gaps"]


def test_graph_tracks_two_reports_and_valid_quote():
    graph = build_proof_graph(sample(status="supported"))
    assert graph["paths"][0]["trace"] == "complete"
    assert len([n for n in graph["nodes"] if n["type"] == "document"]) == 2
    assert any(e["kind"] == "supported_by" for e in graph["edges"])


def test_graph_does_not_change_check_conclusions():
    run = sample(status="supported")
    original = run.checks[0].conclusion_level
    build_proof_graph(run)
    assert run.checks[0].conclusion_level == original


def test_multiple_tool_results_for_one_check_are_not_overwritten():
    run = sample()
    plan = plan_procedures(run.checks, round_number=1)
    result = procedure_effect(plan, run.checks, run.checks,
        [{'check_id': 'C1', 'new_evidence_ids': ['FIRST'], 'query_ids': ['Q1']},
         {'check_id': 'C1', 'new_evidence_ids': [], 'query_ids': ['Q2']}])
    assert result['events'][0]['new_evidence_ids'] == ['FIRST']
    assert result['events'][0]['query_ids'] == ['Q1', 'Q2']

