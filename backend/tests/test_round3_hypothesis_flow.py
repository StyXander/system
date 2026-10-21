"""第三轮假设、反证与下游意见流测试；合成替身不作为真实模型效果证据。"""
from copy import deepcopy
from decimal import Decimal

from app.connectivity_claims import apply_hypothesis_updates, build_claim_ledger, hypothesis_ledger
from app.connectivity_intelligence import integrate_analyses, merge_hypotheses, pack_role_context
from app.connectivity_schemas import AIAnalysis, DisclosureOccurrence, EvidenceRef, ExplanationHypothesis
from test_connectivity_hybrid import bridge_run, opinion


def original_hypothesis(item):
    return ExplanationHypothesis(hypothesis_id="coverage", explanation="未纳入的设备投资可能解释范围差异",
        status="plausible", supporting_evidence=item.supporting_evidence,
        assumptions=["设备投资没有被重复计入"])


def test_a2_refutation_changes_downstream_a3_and_cannot_be_overwritten():
    run = bridge_run()
    facts = deepcopy(run.checks[0].calculation)
    first = opinion(run)
    first.hypotheses = [original_hypothesis(first)]
    ids = {row.occurrence_id for row in run.occurrences}
    assert integrate_analyses(run, [first], ids, "A1", "synthetic")["accepted_analysis_ids"]
    counter = DisclosureOccurrence(occurrence_id="COUNTER", document_id=run.occurrences[0].document_id,
        pdf_page=3, label="设备组成说明", context="设备投资已经包含于所列环保治理投入，不应重复扣减。", quality="text_only")
    run.occurrences.append(counter)
    ids.add(counter.occurrence_id)
    a2 = opinion(run)
    a2.verdict = "potential_conflict"
    a2.summary = "新组成说明否定了未纳入假设，设备投资不能再作为差额解释。"
    a2.reasons = ["原文明确设备投资已包含，重复扣减不能用于解释候选差额。"]
    a2.counter_evidence = [EvidenceRef(occurrence_id=counter.occurrence_id, quote=counter.context)]
    a2.hypotheses = [first.hypotheses[0].model_copy(update={"status": "refuted", "counter_evidence": a2.counter_evidence})]
    assert integrate_analyses(run, [a2], ids, "A2", "synthetic")["accepted_analysis_ids"]
    assert run.checks[0].hypotheses[0].status == "refuted"
    assert any(update["after"] == "refuted" for trace in run.intelligence_trace
               if trace["kind"] == "hypothesis_update" for update in trace["updates"])

    stale_a3 = opinion(run)
    stale_a3.hypotheses = [first.hypotheses[0].model_copy(update={"status": "supported", "counter_evidence": []})]
    rejected = integrate_analyses(run, [stale_a3], ids, "A3", "synthetic")
    assert not rejected["accepted_analysis_ids"]
    assert any("反证" in record["reason"] for record in rejected["analysis_rejections"])
    assert run.ai_analyses[0].producer_role == "A2"
    assert run.checks[0].hypotheses[0].counter_evidence[0].occurrence_id == "COUNTER"

    revised_a3 = a2.model_copy(deep=True)
    revised_a3.summary = "撤回原设备投资桥接解释；现有范围与组成材料不足以闭合差额。"
    revised_a3.next_actions = ["核对附注中的完整组成与设备投资是否重复包含"]
    assert integrate_analyses(run, [revised_a3], ids, "A3", "synthetic")["accepted_analysis_ids"]
    assert run.ai_analyses[0].producer_role == "A3"
    assert run.ai_analyses[0].verdict == "potential_conflict"
    assert "撤回" in run.ai_analyses[0].summary
    assert run.analysis_history[0]["previous"]["verdict"] == "plausible_explanation"
    assert run.checks[0].calculation == facts
    assert run.checks[0].calculation_status == "not_comparable"
    assert hypothesis_ledger(run.checks[0])[0]["semantic_status"] == "ai_assessed_not_independently_verified"


def test_neutral_quote_does_not_automatically_refute_a_hypothesis():
    run = bridge_run()
    item = opinion(run)
    h = original_hypothesis(item)
    h.status = "supported"
    h.counter_evidence = [item.supporting_evidence[0]]
    run.checks[0].hypotheses = [h]
    updates = apply_hypothesis_updates(run.checks[0], run.occurrences)
    assert updates[0]["after"] == "plausible"
    assert h.status == "plausible"
    assert hypothesis_ledger(run.checks[0])[0]["status"] == "plausible"


def test_refuted_requires_valid_counter_quote_and_an_explicit_reason():
    run = bridge_run()
    item = opinion(run)
    h = original_hypothesis(item)
    h.status = "refuted"
    h.counter_evidence = [EvidenceRef(occurrence_id="ADJ", quote="原文没有这一句")]
    h.reasons = ["已找到原文说明，不再沿用原解释"]
    run.checks[0].hypotheses = [h]
    apply_hypothesis_updates(run.checks[0], run.occurrences)
    assert h.status == "plausible"


def test_same_id_cannot_change_the_explanation_identity_or_drop_counter():
    item = opinion(bridge_run())
    old = original_hypothesis(item)
    old.counter_evidence = [item.supporting_evidence[0]]
    incoming = old.model_copy(update={"explanation": "改成一个完全不同的解释", "counter_evidence": []})
    merged, notices = merge_hypotheses([old], [incoming], "CHECK")
    assert merged[0].explanation == old.explanation
    assert merged[0].counter_evidence == old.counter_evidence
    assert notices and "新ID" in notices[0]["reason"]
    assert old.explanation != incoming.explanation


def test_self_consistent_but_unbound_formula_is_not_grounded():
    run = bridge_run()
    item = opinion(run)
    item.summary = "按虚构投入99991+7=99998复算得出新金额。"
    item.reasons = [item.summary]
    ledger = build_claim_ledger(run.checks[0], item, run.occurrences)
    assert ledger["derived_checks"]
    assert ledger["derived_checks"][0]["matches"] is False
    assert ledger["derived_checks"][0]["inputs_grounded"] is False
    delta = integrate_analyses(run, [item], {row.occurrence_id for row in run.occurrences}, "A3", "synthetic")
    assert not delta["accepted_analysis_ids"]


def test_derived_zero_and_a_legitimate_unit_conversion_keep_proof():
    run = bridge_run()
    item = opinion(run)
    item.summary = "候选差额可复算为1200-1050=150。"
    item.reasons = ["1200-1050=150，若设备投资未重复计入，150-150=0。", "设备投入150万元=0.015亿元，换算不证明统计范围一致。"]
    ledger = build_claim_ledger(run.checks[0], item, run.occurrences)
    assert any(record.get("computed") == "0" and record["matches"] for record in ledger["derived_checks"])
    conversion = next(record for record in ledger["derived_checks"] if record.get("output_unit") == "亿元")
    assert conversion["inputs_grounded"] and conversion["source_occurrence_ids"] == ["ADJ"]
    assert Decimal(conversion["computed"]) == Decimal("0.015")
    assert integrate_analyses(run, [item], {row.occurrence_id for row in run.occurrences}, "A3", "synthetic")["accepted_analysis_ids"]
    assert any("150-150=0" in reason for reason in run.ai_analyses[0].reasons)


def test_wrong_unit_conversion_is_rejected_even_if_both_numbers_appear_elsewhere():
    run = bridge_run()
    item = opinion(run)
    item.summary = "环保设备投入150万元=1200亿元。"
    item.reasons = [item.summary]
    delta = integrate_analyses(run, [item], {row.occurrence_id for row in run.occurrences}, "A3", "synthetic")
    assert not delta["accepted_analysis_ids"]
    assert any("换算" in record["reason"] for record in delta["analysis_rejections"])


def test_context_keeps_structure_qualifiers_provenance_and_has_no_dangling_pool_ids():
    rows = [{"occurrence_id": f"O{index}", "document_id": "AR", "pdf_page": 1,
             "label": "环保投入（资本性）", "value": "100", "unit": "万元", "year": "2025",
             "context": "环保投入（资本性）100万元。", "table_id": "T1", "row_index": index,
             "column_index": 2, "column_header": "2025年", "full_table_header": "项目 2025年 2024年",
             "header_path": ["合并", "2025年"], "bbox": [10, 20, 30, 40],
             "metric_identity": {"qualifiers": {"accounting": "capital"}},
             "currency_status": "report_declaration", "currency_source_id": "REPORT-SOURCE",
             "scope_source_quote": "合并范围包括子公司"} for index in range(100)]
    pool = [{"members": [{"occurrence_id": f"O{index}", "role": "left"},
                         {"occurrence_id": f"O{index+1}", "role": "right"}]} for index in range(0, 100, 2)]
    packed = pack_role_context({"occurrences": rows, "candidate_checks": [], "structured_candidate_pool": pool}, char_budget=18000)
    sent = {row["occurrence_id"] for row in packed["occurrences"]}
    first = packed["occurrences"][0]
    assert first["table_id"] == "T1" and first["column_index"] == 2
    assert first["metric_identity"]["qualifiers"]["accounting"] == "capital"
    assert first["full_table_header"] == "项目 2025年 2024年"
    assert first["currency_source_id"] == "REPORT-SOURCE" and first["scope_source_quote"]
    assert all(member["occurrence_id"] in sent for item in packed["structured_candidate_pool"] for member in item["members"])
    assert packed["context_packing"]["candidate_pool_omitted_count"] > 0
