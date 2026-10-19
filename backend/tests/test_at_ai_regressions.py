"""AI2 智能推理专项回归：错绑、列义、派生算式、叙述幅度、反证与检索。

测试只使用合成原文和本地规则，不调用真实模型；真实缓存评估另见交接文档命令。
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import re

import pytest

from app.connectivity_claims import (apply_hypothesis_updates, build_claim_ledger, build_next_evidence,
    classify_column_semantics, hypothesis_ledger, parse_claimed_magnitude, semantic_problem,
    should_reject_analysis, verify_narrative_magnitude)
from app.connectivity_engine import calculate
from app.connectivity_intelligence import integrate_analyses
from app.connectivity_pipeline import (_proposal_problem, candidate_checks, integrate_proposals,
    make_findings)
from app.connectivity_retrieval import (build_query_plan, knowledge_ablation, load_rule_basis,
    retrieve_targeted_pages, retrieval_effect, rule_basis_for)
from app.connectivity_rules import BASE_CONDITIONS, RULES
from app.connectivity_schemas import (AIAnalysis, ComparisonCondition, ConnectivityRun, DisclosureOccurrence,
    EvidenceRef, ExplanationHypothesis, NarrativeClaim, RelationshipCheck, RelationshipMember,
    RelationshipProposal, ReportDocument)

ENTITY = "合成股份有限公司"


def occ(occurrence_id, label, value, unit="万元", document_id="SYN-AR", year="2025",
        header="2025 年", scope="", topic="research", page=1, context=None):
    """构造一行可定位披露；文字包含数值，便于逐字引用测试。"""
    return DisclosureOccurrence(
        occurrence_id=occurrence_id, document_id=document_id, pdf_page=page, label=label,
        value=value, unit=unit, unit_source="表头单位", currency="CNY",
        year=year, year_status="attributed" if year else "unattributed", scope=scope,
        column_header=header, row_header=f"{label} {value} {unit}",
        context=context or f"{ENTITY} 2025年。{label} {value}{unit}，同一统计范围。",
        quality="located", quality_reason="合成测试行", topic=topic)


def doc(document_id, report_type):
    return ReportDocument(document_id=document_id, case_id="SYN-PAIR", company_id="SYN",
        company=ENTITY, report_type=report_type, period="2025",
        source_url="https://example.invalid/synthetic")


def run_with(rows, documents=None, period="2025"):
    return ConnectivityRun(run_id="SYN-RUN", company=ENTITY, period=period, report_period=period,
        documents=documents or [doc("SYN-AR", "AR"), doc("SYN-ESG", "ESG")],
        occurrences=rows, dataset_role="synthetic")


def eq_check(rows, members, check_id="CHECK-T", title="合成同值关系"):
    refs = [EvidenceRef(occurrence_id=row.occurrence_id,
                        quote=next((line for line in row.context.split("\n") if row.value in line), row.context[:40]))
            for row in rows]
    return RelationshipCheck(check_id=check_id, rule_id="EQ-001", title=title, topic="research",
        operator="equal", members=[RelationshipMember(occurrence_id=oid, role=role) for oid, role in members],
        conditions=[ComparisonCondition(name=name) for name in BASE_CONDITIONS],
        relationship_basis="auto_label_match", relationship_evidence=refs)


def test_wrong_metric_binding_is_rejected_before_result():
    money = occ("MONEY", "研发投入金额", "100", "万元", "SYN-AR")
    people = occ("PEOPLE", "研发人员数量", "100", "人", "SYN-ESG", topic="research")
    run = run_with([money, people])
    proposal = RelationshipProposal(rule_id="EQ-001", title="研发投入与人数", topic="research",
        members=[RelationshipMember(occurrence_id="MONEY", role="left"),
                 RelationshipMember(occurrence_id="PEOPLE", role="right")],
        conditions=[], relationship_evidence=[])
    result = integrate_proposals(run, {"checks": [proposal.model_dump()]},
                                 {"MONEY", "PEOPLE"}, "A1")
    assert not result["accepted_check_ids"]
    assert any("量纲" in item["reason"] for item in result["rejected"])
    assert not run.checks


def test_incomplete_composition_roles_are_rejected():
    total = occ("TOTAL", "研发投入合计", "100")
    component = occ("C1", "研发投入费用化", "60")
    run = run_with([total, component])
    proposal = RelationshipProposal(rule_id="RD-001", title="研发投入组成", topic="research",
        members=[RelationshipMember(occurrence_id="TOTAL", role="total"),
                 RelationshipMember(occurrence_id="C1", role="component")],
        conditions=[], relationship_evidence=[])
    result = integrate_proposals(run, {"checks": [proposal.model_dump()]},
                                 {"TOTAL", "C1"}, "A1")
    assert any("至少两个component" in item["reason"] for item in result["rejected"])


def test_wrong_period_is_rejected():
    current = occ("CUR", "研发投入金额", "100", "万元", "SYN-AR", year="2025")
    previous = occ("PRE", "研发投入金额", "90", "万元", "SYN-ESG", year="2024")
    run = run_with([current, previous])
    proposal = RelationshipProposal(rule_id="EQ-001", title="跨年比较", topic="research",
        members=[RelationshipMember(occurrence_id="CUR", role="left"),
                 RelationshipMember(occurrence_id="PRE", role="right")],
        conditions=[], relationship_evidence=[])
    result = integrate_proposals(run, {"checks": [proposal.model_dump()]},
                                 {"CUR", "PRE"}, "A1")
    assert any("期间" in item["reason"] for item in result["rejected"])


def test_change_ratio_column_cannot_be_used_as_annual_value():
    change = occ("CHG", "研发投入占营业收入比例", "0.66", "%", "SYN-AR",
                 year="", header="2025 年 2024 年 变动比例",
                 context="研发投入占营业收入比例 1.11% 0.45% 0.66%")
    change.year_status = "unattributed"
    current = occ("CUR", "研发投入金额", "449183817.50", "元", "SYN-AR")
    previous = occ("PRE", "研发投入金额", "405053632.27", "元", "SYN-ESG", year="2024")
    check = eq_check([current, previous], [("CUR", "left"), ("PRE", "right")])
    run = run_with([change, current, previous], documents=[doc("SYN-AR", "AR"), doc("SYN-ESG", "ESG")])
    run.checks = [calculate(check, run.occurrences)]
    analysis = AIAnalysis(check_id=check.check_id, verdict="potential_conflict",
        summary="2024年研发投入占比为0.66%，与本期不一致。",
        reasons=["该值来自变动比例列但被当作年度值。"],
        supporting_evidence=[EvidenceRef(occurrence_id="CHG", quote="研发投入占营业收入比例 1.11% 0.45% 0.66%"),
                             EvidenceRef(occurrence_id="CUR", quote="研发投入金额 449183817.50 元")])
    result = integrate_analyses(run, [analysis], {"CHG", "CUR", "PRE"}, "A3", "test")
    assert not result["accepted_analysis_ids"]
    assert any("变动" in item["reason"] or "年度" in item["reason"] for item in result["analysis_rejections"])
    assert run.intelligence_trace[-1]["kind"] == "claim_ledger"
    assert run.intelligence_trace[-1]["support_status"] == "contradicted"


def test_quoted_change_ratio_header_does_not_rescue_annual_misuse():
    change = occ("CHG", "研发投入占营业收入比例", "0.66", "%", "SYN-AR",
                 year="", header="2025 年 2024 年 变动比例",
                 context="研发投入占营业收入比例 1.11% 0.45% 0.66%")
    change.year_status = "unattributed"
    current = occ("CUR", "研发投入金额", "449183817.50", "元", "SYN-AR")
    previous = occ("PRE", "研发投入金额", "405053632.27", "元", "SYN-ESG", year="2024")
    check = eq_check([current, previous], [("CUR", "left"), ("PRE", "right")])
    run = run_with([change, current, previous])
    run.checks = [calculate(check, run.occurrences)]
    analysis = AIAnalysis(check_id=check.check_id, verdict="potential_conflict",
        summary="2025 年 2024 年 变动比例 的0.66%被当作年度值。",
        reasons=["引用列头并不能改变该值不是年度值的事实。"],
        supporting_evidence=[EvidenceRef(occurrence_id="CHG", quote="研发投入占营业收入比例 1.11% 0.45% 0.66%"),
                             EvidenceRef(occurrence_id="CUR", quote="研发投入金额 449183817.50 元")])
    result = integrate_analyses(run, [analysis], {"CHG", "CUR", "PRE"}, "A3", "test")
    assert not result["accepted_analysis_ids"]
    assert any("变动" in item["reason"] or "年度" in item["reason"] for item in result["analysis_rejections"])


def test_change_ratio_can_be_described_as_change_ratio():
    change = occ("CHG", "研发投入占营业收入比例", "0.66", "%", "SYN-AR",
                 year="", header="2025 年 2024 年 变动比例",
                 context="研发投入占营业收入比例 1.11% 0.45% 0.66%")
    change.year_status = "unattributed"
    current = occ("CUR", "研发投入金额", "449183817.50", "元", "SYN-AR")
    previous = occ("PRE", "研发投入金额", "405053632.27", "元", "SYN-ESG", year="2024")
    check = eq_check([current, previous], [("CUR", "left"), ("PRE", "right")])
    run = run_with([change, current, previous])
    run.checks = [calculate(check, run.occurrences)]
    analysis = AIAnalysis(check_id=check.check_id, verdict="plausible_explanation",
        summary="变动比例为0.66%，不能当作年度值。",
        reasons=["该数值来自变动比例列，需结合本期与上期另行核对。"],
        supporting_evidence=[EvidenceRef(occurrence_id="CHG", quote="研发投入占营业收入比例 1.11% 0.45% 0.66%"),
                             EvidenceRef(occurrence_id="CUR", quote="研发投入金额 449183817.50 元")],
        next_actions=["核对表头年度列与变动比例列"])
    result = integrate_analyses(run, [analysis], {"CHG", "CUR", "PRE"}, "A3", "test")
    assert result["accepted_analysis_ids"], result["analysis_rejections"]
    assert run.ai_analyses[0].analysis_quality in {"medium", "high"}


def test_derived_formula_is_recomputed_and_wrong_input_is_rejected():
    energy = occ("ENERGY", "综合能源消耗", "26.12", "吨标准煤", "SYN-ESG")
    revenue = occ("REV", "营业收入", "405.29", "万元", "SYN-ESG", topic="intensity")
    check = eq_check([energy, revenue], [("ENERGY", "left"), ("REV", "right")])
    run = run_with([energy, revenue])
    run.checks = [calculate(check, run.occurrences)]
    good = AIAnalysis(check_id=check.check_id, verdict="plausible_explanation",
        summary="强度0.0644由26.12÷405.29得出。",
        reasons=["按综合能耗26.12除以营业收入405.29复算，结果为0.0644。"],
        supporting_evidence=[EvidenceRef(occurrence_id="ENERGY", quote="综合能源消耗 26.12吨标准煤"),
                             EvidenceRef(occurrence_id="REV", quote="营业收入 405.29万元")])
    assert integrate_analyses(run, [good], {"ENERGY", "REV"}, "A3", "test")["accepted_analysis_ids"]
    bad = AIAnalysis(check_id=check.check_id, verdict="plausible_explanation",
        summary="强度0.0644由22.86÷405.29得出。",
        reasons=["按直接能耗22.86除以营业收入405.29复算，结果为0.0644。"],
        supporting_evidence=[EvidenceRef(occurrence_id="ENERGY", quote="综合能源消耗 26.12吨标准煤"),
                             EvidenceRef(occurrence_id="REV", quote="营业收入 405.29万元")])
    result = integrate_analyses(run, [bad], {"ENERGY", "REV"}, "A3", "test")
    assert not result["accepted_analysis_ids"]
    assert any("复算" in item["reason"] for item in result["analysis_rejections"])


def test_narrative_magnitude_108949_and_reverse_direction():
    current = occ("CUR", "研发投入金额", "449183817.50", "元", "SYN-AR")
    previous = occ("PRE", "研发投入金额", "405053632.27", "元", "SYN-AR", year="2024")
    check = eq_check([current, previous], [("CUR", "left"), ("PRE", "right")])
    check.narrative_claim = NarrativeClaim(indicator="研发投入金额", direction="increase",
        current_id="CUR", previous_id="PRE",
        evidence=[EvidenceRef(occurrence_id="CUR", quote="研发投入金额 449183817.50 元")],
        basis_description="同比增长10.89%")
    result = verify_narrative_magnitude(check, check.narrative_claim, [current, previous])
    assert result["status"] == "supported"
    assert result["recomputed_value"] == "10.89"
    assert result["magnitude_matches"]
    check.narrative_claim.direction = "decrease"
    reversed_result = verify_narrative_magnitude(check, check.narrative_claim, [current, previous])
    assert reversed_result["status"] == "contradicted"
    check.narrative_claim.previous_id = "CUR"
    same = verify_narrative_magnitude(check, check.narrative_claim, [current, previous])
    assert same["status"] == "not_executable"


def test_target_is_not_treated_as_achieved_result():
    current = occ("CUR", "单位产量排放强度", "8", "吨二氧化碳当量/吨产品", "SYN-ESG")
    previous = occ("PRE", "单位产量排放强度", "10", "吨二氧化碳当量/吨产品", "SYN-ESG", year="2024")
    check = eq_check([current, previous], [("CUR", "left"), ("PRE", "right")])
    check.explanation = "公司已实现减排目标。"
    check.narrative_claim = NarrativeClaim(indicator="单位产量排放强度", direction="decrease",
        current_id="CUR", previous_id="PRE",
        evidence=[EvidenceRef(occurrence_id="CUR", quote="单位产量排放强度 8吨二氧化碳当量/吨产品")],
        basis_description="目标到2025年下降20%")
    result = verify_narrative_magnitude(check, check.narrative_claim, [current, previous])
    assert result["target_as_result"] is True
    assert result["status"] == "contradicted"


def test_ai_text_treating_target_as_achieved_is_rejected():
    current = occ("CUR", "单位产量排放强度", "8", "吨二氧化碳当量/吨产品", "SYN-ESG")
    previous = occ("PRE", "单位产量排放强度", "10", "吨二氧化碳当量/吨产品", "SYN-ESG", year="2024")
    check = eq_check([current, previous], [("CUR", "left"), ("PRE", "right")])
    check.narrative_claim = NarrativeClaim(indicator="单位产量排放强度", direction="decrease",
        current_id="CUR", previous_id="PRE",
        evidence=[EvidenceRef(occurrence_id="CUR", quote="单位产量排放强度 8吨二氧化碳当量/吨产品")],
        basis_description="目标到2025年下降20%")
    run = run_with([current, previous])
    run.checks = [calculate(check, run.occurrences)]
    analysis = AIAnalysis(check_id=check.check_id, verdict="lean_consistent",
        summary="公司已实现减排目标。",
        reasons=["强度下降20%，可以作为目标完成的证明。"],
        supporting_evidence=[EvidenceRef(occurrence_id="CUR", quote="单位产量排放强度 8吨二氧化碳当量/吨产品")])
    result = integrate_analyses(run, [analysis], {"CUR", "PRE"}, "A3", "test")
    assert not result["accepted_analysis_ids"]
    assert any("目标" in item["reason"] for item in result["analysis_rejections"])


def test_total_up_and_intensity_down_are_not_contradictory():
    current = occ("CUR", "单位产量排放强度", "8", "吨二氧化碳当量/吨产品", "SYN-ESG")
    previous = occ("PRE", "单位产量排放强度", "10", "吨二氧化碳当量/吨产品", "SYN-ESG", year="2024")
    check = eq_check([current, previous], [("CUR", "left"), ("PRE", "right")])
    check.explanation = "排放总量同比增长5%，但单位产量强度下降。"
    check.narrative_claim = NarrativeClaim(indicator="单位产量排放强度", direction="decrease",
        current_id="CUR", previous_id="PRE",
        evidence=[EvidenceRef(occurrence_id="CUR", quote="单位产量排放强度 8吨二氧化碳当量/吨产品")],
        basis_description="强度同比下降20%")
    result = verify_narrative_magnitude(check, check.narrative_claim, [current, previous])
    assert result["status"] == "supported"
    assert result.get("total_and_intensity_coexist") is True


def test_counter_evidence_refutes_explanation_and_absence_is_not_verification():
    current = occ("CUR", "环保投入", "100")
    previous = occ("PRE", "环保投入", "90")
    check = eq_check([current, previous], [("CUR", "left"), ("PRE", "right")])
    check.hypotheses = [ExplanationHypothesis(hypothesis_id="H1", explanation="范围差异导致差额",
        status="supported", assumptions=["可检验条件：若为范围差异，应找到未纳入子公司的说明"],
        supporting_evidence=[EvidenceRef(occurrence_id="CUR", quote="环保投入 100万元")],
        counter_evidence=[EvidenceRef(occurrence_id="PRE", quote="环保投入 90万元")])]
    updates = apply_hypothesis_updates(check, [current, previous])
    assert any(item["after"] == "refuted" for item in updates)
    assert check.hypotheses[0].status == "refuted"
    check.hypotheses[0].counter_evidence = []
    check.hypotheses[0].status = "plausible"
    records = hypothesis_ledger(check)
    assert records[0]["status"] == "plausible"
    assert "不等于解释成立" in records[0]["unverified_note"]


def test_queries_are_metric_specific_and_deduplicated():
    rows, checks = [], []
    for index in range(13):
        row = occ(f"R{index:02d}", f"指标{index}", str(100 + index), "万元", f"DOC-{index % 2}")
        rows.append(row)
        checks.append(RelationshipCheck(check_id=f"CHECK-{index:04d}", rule_id="EQ-001",
            title=f"指标{index}核对", topic="research", operator="equal",
            members=[RelationshipMember(occurrence_id=row.occurrence_id, role="left")],
            conditions=[ComparisonCondition(name="范围")], relationship_basis="auto_label_match"))
    # 同一指标出现两次时，query 应共享而不是复制一份宽泛词。
    checks.append(checks[0].model_copy(update={"check_id": "CHECK-DUP"}))
    run = run_with(rows, documents=[doc("DOC-0", "AR"), doc("DOC-1", "ESG")])
    plan = build_query_plan(run, checks)
    assert plan["query_count"] >= 13
    assert plan["shared_query_count"] >= 1
    for check in checks:
        item = plan["check_plans"][check.check_id]
        assert item["queries"]
        for query in item["queries"]:
            assert item["metrics"][0] in query["terms"][0] or any(metric in query["text"] for metric in item["metrics"])
    texts = [query["text"] for query in plan["queries"]]
    assert len(texts) == len(set(texts)), "全局查询必须去重"


def test_rule_basis_never_fabricates_unverified_clause():
    rules = load_rule_basis()["rules"]
    assert len(rules) >= 10
    for rule in rules:
        if rule["verification_status"] == "unverified":
            clause = str((rule.get("source") or {}).get("clause", ""))
            assert clause in {"", "待核验具体条款", "待逐条核验具体条款"}
            assert "第" not in clause or "待" in clause
    check = RelationshipCheck(check_id="CHECK-R", rule_id="EQ-001", title="研发投入与范围核对",
        topic="research", operator="equal", members=[], conditions=[ComparisonCondition(name="范围")])
    hits = rule_basis_for(check)
    assert hits and all(hit["basis_id"] for hit in hits)
    assert knowledge_ablation(check)["disabled_hit_count"] == 0


def test_topic_filter_suppresses_revenue_only_relations():
    revenue = occ("REV", "营业收入", "405.29", "亿元", "SYN-AR", topic="intensity")
    revenue2 = occ("REV2", "营业收入", "405.29", "亿元", "SYN-ESG", topic="intensity")
    run = run_with([revenue, revenue2])
    checks = candidate_checks(run.occurrences, "2025", run=run, topics=["intensity"])
    assert not [check for check in checks if "营业收入" in check.title and check.rule_id in {"EQ-001", "OCC-001"}]
    coverage = [item for item in run.intelligence_trace if item.get("kind") == "topic_coverage"]
    assert any(item["status"] in {"insufficient_coverage", "only_multi_location"} for item in coverage)


def test_macro_and_generic_rows_cannot_form_pairs():
    macro = occ("MACRO", "我国粗钢产量", "100", "万吨", "SYN-AR", topic="intensity",
                context="国家统计局公布我国粗钢产量100万吨。")
    macro2 = occ("MACRO2", "我国粗钢产量", "100", "万吨", "SYN-ESG", topic="intensity",
                 context="国家统计局公布我国粗钢产量100万吨。")
    generic = occ("GEN", "一", "3221.2", "亿元", "SYN-AR", topic="research")
    generic2 = occ("GEN2", "一", "93.4", "亿元", "SYN-ESG", topic="research")
    run = run_with([macro, macro2, generic, generic2])
    checks = candidate_checks(run.occurrences, "2025", run=run, topics=["research", "intensity"])
    assert not [check for check in checks if "粗钢" in check.title or check.title.startswith("一")]
    reasons = " ".join(item.get("reason", "") for item in run.candidate_rejections)
    assert "宏观" in reasons or "行名" in reasons


def test_merged_and_parent_scope_are_not_subtracted_as_anomaly():
    left = occ("LEFT", "研发投入金额", "100", "万元", "SYN-AR", scope="合并")
    right = occ("RIGHT", "研发投入金额", "80", "万元", "SYN-ESG", scope="母公司")
    run = run_with([left, right])
    checks = candidate_checks(run.occurrences, "2025", run=run, topics=["research"])
    assert checks
    assert all(check.rule_id != "EQ-001" for check in checks)
    scoped = next(check for check in checks if check.rule_id == "NAR-001")
    assert scoped.mapping_type == "different_metric"
    assert "不同口径" in scoped.mapping_reason
    assert scoped.calculation_status == "not_applicable"


def test_same_document_large_spread_is_not_an_eq_or_anomaly():
    left = occ("L", "研发费用", "37.79", "亿元", "SYN-AR", page=77)
    right = occ("R", "研发费用", "12.50", "亿元", "SYN-AR", page=120)
    run = run_with([left, right], documents=[doc("SYN-AR", "AR")])
    proposal = RelationshipProposal(rule_id="EQ-001", title="研发费用跨表", topic="research",
        members=[RelationshipMember(occurrence_id="L", role="left"),
                 RelationshipMember(occurrence_id="R", role="right")],
        conditions=[], relationship_evidence=[])
    problem = _proposal_problem(proposal, run, {row.occurrence_id: row for row in run.occurrences})
    assert "合并/母公司" in problem
    checks = candidate_checks(run.occurrences, "2025", run=run, topics=["research"])
    occ_check = next(check for check in checks if check.rule_id == "OCC-001")
    assert occ_check.mapping_type == "different_metric"
    assert occ_check.calculation_status != "unexplained_difference"


def test_column_composition_balances_and_stays_a_candidate():
    total = occ("SYN-ESG-79-T2-R0-C6", "环保资本化项目投入", "4.835", "亿元", "SYN-ESG", header="2024 年 / 合计", topic="environment")
    steel = occ("SYN-ESG-79-T2-R0-C4", "环保资本化项目投入", "4.34", "亿元", "SYN-ESG", header="2024 年 / 钢铁", topic="environment")
    other = occ("SYN-ESG-79-T2-R0-C5", "环保资本化项目投入", "0.495", "亿元", "SYN-ESG", header="2024 年 / 其他", topic="environment")
    for row in (total, steel, other):
        row.header_path = ["2024 年", row.column_header.split("/")[-1].strip()]
    run = run_with([total, steel, other], documents=[doc("SYN-ESG", "ESG")])
    checks = candidate_checks(run.occurrences, "2025", run=run, topics=["environment"])
    composition = next(check for check in checks if check.rule_id == "ENV-001" and "合计列" in check.title)
    assert {member.role for member in composition.members} == {"total", "component"}
    assert composition.calculation_status == "not_comparable"
    assert composition.hypothetical["residual"] == "0"


def test_non_identical_alias_mapping_recalls_but_expense_is_not_investment():
    left = occ("L", "研发投入金额", "4.49", "亿元", "SYN-AR", topic="research")
    right = occ("R", "研发支出", "4.49", "亿元", "SYN-ESG", topic="research")
    run = run_with([left, right])
    checks = candidate_checks(run.occurrences, "2025", run=run, topics=["research"])
    mapped = next(check for check in checks if check.rule_id == "EQ-001" and "非同名" in check.title)
    assert mapped.mapping_type == "same_metric"
    assert "别名" in mapped.mapping_reason
    expense = occ("EXP", "研发费用", "4.49", "亿元", "SYN-ESG", topic="research")
    run2 = run_with([left, expense])
    checks2 = candidate_checks(run2.occurrences, "2025", run=run2, topics=["research"])
    assert not [check for check in checks2 if check.rule_id == "EQ-001" and "非同名" in check.title]


def test_next_evidence_has_material_and_upgrade_path():
    check = RelationshipCheck(check_id="CHECK-N", rule_id="EQ-001", title="研发投入核对",
        topic="research", operator="equal", members=[],
        conditions=[ComparisonCondition(name=name) for name in BASE_CONDITIONS])
    actions = build_next_evidence(check)
    assert actions
    assert all(action["material"] and action["action"] for action in actions)
    assert all("L1" in action["upgrade_effect"] or "L0" in action["upgrade_effect"] or "L2" in action["upgrade_effect"]
               for action in actions)
    finding = make_findings([check])[0]
    assert "材料位置" in finding.requested_material


def test_model_candidates_are_deduplicated_and_deterministic():
    left = occ("L", "环保投入", "100", "万元", "SYN-AR", topic="environment")
    right = occ("R", "环保投入", "100", "万元", "SYN-ESG", topic="environment")
    run = run_with([left, right])
    checks_a = candidate_checks(run.occurrences, "2025", run=run, topics=["environment"])
    run_b = run_with([left.model_copy(deep=True), right.model_copy(deep=True)])
    checks_b = candidate_checks(run_b.occurrences, "2025", run=run_b, topics=["environment"])
    assert [(c.check_id, c.title, c.rule_id) for c in checks_a] == [(c.check_id, c.title, c.rule_id) for c in checks_b]
    fields = {"rule_id", "title", "topic", "members", "conditions", "relationship_evidence"}
    first = checks_a[0].model_dump(include=fields)
    duplicate = deepcopy(first)
    duplicate["members"] = list(reversed(duplicate["members"]))
    result = integrate_proposals(run, {"checks": [first, duplicate]},
                                 {row.occurrence_id for row in run.occurrences}, "A1")
    assert len(result["accepted_check_ids"]) <= 1
    assert any("重复" in item["reason"] for item in result["rejected"])


def test_ai1_composition_hook_is_optional_and_used_when_present(monkeypatch):
    from app import connectivity_extraction
    left = occ("L", "合成指标", "10", "万元", "SYN-AR")
    right = occ("R", "合成指标", "10", "万元", "SYN-ESG")
    run = run_with([left, right])
    baseline = candidate_checks(run.occurrences, "2025", run=run, topics=["research"])
    assert baseline
    hook_check = RelationshipCheck(check_id="PENDING", rule_id="NAR-001", title="AI1结构候选",
        topic="research", operator="narrative",
        members=[RelationshipMember(occurrence_id="L", role="occurrence")],
        conditions=[ComparisonCondition(name="范围")],
        relationship_evidence=[EvidenceRef(occurrence_id="L", quote="合成指标 10 万元")])
    monkeypatch.setattr(connectivity_extraction, "build_table_composition_candidates",
                        lambda current, period: [hook_check], raising=False)
    hooked = candidate_checks(run.occurrences, "2025", run=run, topics=["research"])
    assert any(check.title == "AI1结构候选" for check in hooked)
    assert any(item.get("hook") == "build_table_composition_candidates" and item.get("status") == "used"
               for item in run.intelligence_trace)


def test_retrieval_effect_counts_real_upgrades_and_invalid_citations():
    row = occ("R", "环保投入", "100", "万元", "SYN-AR", topic="environment")
    before = RelationshipCheck(check_id="CHECK-R", rule_id="EQ-001", title="环保投入核对",
        topic="environment", operator="equal",
        members=[RelationshipMember(occurrence_id="R", role="left")],
        conditions=[ComparisonCondition(name="范围"), ComparisonCondition(name="单位")],
        relationship_basis="auto_label_match")
    after = before.model_copy(deep=True)
    after.conditions[0].status = "supported"
    after.conditions[0].evidence = [EvidenceRef(occurrence_id="R", quote="环保投入 100万元")]
    after.conditions[1].status = "supported"
    after.conditions[1].evidence = [EvidenceRef(occurrence_id="R", quote="不存在的引文")]
    metrics = retrieval_effect([before], [after], [row], {"R"})
    assert metrics["checks_with_upgraded_conditions"] == 1
    assert metrics["invalid_citations"] == 1
    assert metrics["erroneous_citation_rate"] == 0.5
    assert metrics["new_evidence_used_in_upgrades"] == 2
