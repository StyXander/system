"""AI1 核心计算与表格引擎回归：合成输入覆盖口径、精度、闸门与表内自证。

所有用例不调用模型，不写入运行目录；真实报告复测由独立脚本执行。
"""
from __future__ import annotations

from app.connectivity_conditions import upgrade_conditions
from app.connectivity_engine import calculate, member_boundary
from app.connectivity_extraction import (_boundary_from_text, _column_role, _display_precision,
    _exclusions, _extract_tables, _label_from_row, _resolve_row_identity, _row_role)
from app.connectivity_metrics import content_classification, metric_identity
from app.connectivity_rules import RULES, required_conditions
from app.connectivity_schemas import (ComparisonCondition, ConnectivityRun, DisclosureOccurrence,
    EvidenceRef, RelationshipCheck, RelationshipMember, ReportDocument)
from app.connectivity_tables import build_table_composition_candidates

NOTICE_TEXT = "合成企业2025年年度报告合并范围说明，单位：人民币万元。"


def document(document_id="SYN-AR", report_type="AR", period="2025"):
    return ReportDocument(document_id=document_id, case_id="SYN-PAIR", company_id="SYN",
        company="合成企业", report_type=report_type, period=period, metric_period=period,
        source_url="https://example.invalid/synthetic")


def row(index, label, value, unit="万元", *, document_id="SYN-AR", currency="CNY", year="2025",
        context=None, topic="research", scope="", scope_level="unknown", boundary="unknown",
        table_scope="", table_id="", row_index=None, column_index=None, row_role="unknown", column_role="unknown",
        column_header="2025 年", header_path=None, display_precision=None, rounding_method="unknown",
        content_class="company", quality="located", bbox=None):
    text = context or f"{NOTICE_TEXT}\n{label} | {value} | {unit}"
    return DisclosureOccurrence(
        occurrence_id=f"{document_id}-{index}", document_id=document_id, pdf_page=1,
        bbox=bbox or [10, 10 + index * 20, 200, 25 + index * 20], label=label,
        value=value, unit=unit, unit_source="本表单位列", unit_status="table",
        currency=currency, currency_status="explicit" if currency else "unknown",
        year=year, year_status="attributed" if year else "unattributed",
        report_boundary=boundary, scope=scope, table_scope=table_scope, scope_level=scope_level,
        display_precision=display_precision, rounding_method=rounding_method,
        content_class=content_class, table_id=table_id, row_index=row_index, column_index=column_index,
        row_role=row_role, column_role=column_role, row_header=text, column_header=column_header,
        header_path=header_path or [column_header], context=text, quality=quality,
        quality_reason="合成已绑定", topic=topic)


def run_of(rows, documents=None):
    return ConnectivityRun(run_id="SYN-RUN", company="合成企业", period="2025", report_period="2025",
        documents=documents or [document(), document("SYN-ESG", "ESG")],
        occurrences=list(rows), dataset_role="synthetic")


def refs_for(rows, quote=None):
    return [EvidenceRef(occurrence_id=rows[0].occurrence_id, quote=quote or rows[0].context[:80])]


def check_for(rows, rule="EQ-001", roles=None, supported=True, unknown=(), basis="text_statement",
              explanation="", explanation_evidence=None):
    operator = RULES[rule]["operator"]
    roles = roles or ["left", "right"]
    refs = refs_for(rows)
    conditions = []
    for name in required_conditions(operator):
        if not supported or name in unknown:
            conditions.append(ComparisonCondition(name=name, status="unknown"))
        else:
            conditions.append(ComparisonCondition(name=name, status="supported", reason="合成条件", evidence=refs))
    return RelationshipCheck(check_id="SYN-CHECK", rule_id=rule, title="合成关系", operator=operator,
        members=[RelationshipMember(occurrence_id=row.occurrence_id, role=role) for row, role in zip(rows, roles)],
        conditions=conditions,
        relationship_evidence=refs if basis == "text_statement" else [],
        relationship_basis=basis, explanation=explanation,
        explanation_evidence=explanation_evidence or [])


def page_with_table(heading, rows, *, header_year="2025 年", unit_line=None):
    """构造与 PyMuPDF 缓存同形的表页，验证标题/单位/币种继承。"""
    lines, y = [], 0
    for text in heading:
        lines.append({"text": text, "bbox": [0, y, 300, y + 12], "spans": [([0, y, 300, y + 12], text)], "side": 0})
        y += 16
    table_top = y + 10
    table = {"bbox": [0, table_top, 320, table_top + len(rows) * 18], "data": rows,
             "cells": [], "headers": [{"text": header_year,
                                      "bbox": [120 + (len(rows[0]) - 2) * 60, table_top,
                                               180 + (len(rows[0]) - 2) * 60, table_top + 14],
                                      "table_bbox": [0, table_top, 320, table_top + len(rows) * 18]}]}
    for row_index, values in enumerate(rows):
        cells = []
        for column_index, _ in enumerate(values):
            if column_index == 0:
                cells.append([0, table_top + row_index * 18, 120, table_top + (row_index + 1) * 18])
            else:
                cells.append([120 + (column_index - 1) * 60, table_top + row_index * 18,
                              180 + (column_index - 1) * 60, table_top + (row_index + 1) * 18])
        table["cells"].append(cells)
    return {"page": 1, "width": 595, "height": 842, "lines": lines, "tables": [table], "headers": []}


def test_scope_report_level_is_not_metric_level_and_does_not_formalise():
    rows = [row(1, "研发投入金额", "100", scope="合并范围", scope_level="report",
                boundary="consolidated", context=NOTICE_TEXT + "\n本报告范围包括全部子公司。"),
            row(2, "研发投入金额", "100", document_id="SYN-ESG", scope="合并范围",
                scope_level="report", boundary="consolidated", context=NOTICE_TEXT + "\n本报告范围包括全部子公司。")]
    check = check_for(rows, unknown=("范围",))
    upgraded, names = upgrade_conditions(check, run_of(rows), "2025")
    scope = next(item for item in upgraded.conditions if item.name == "范围")
    assert scope.status == "unknown"
    assert scope.evidence_kind == "report_level"
    assert "报告级边界" in scope.reason or "总体范围" in scope.reason
    result = calculate(upgraded, rows)
    assert result.criteria_status == "unknown"
    assert result.calculation_status == "not_comparable"
    assert result.calculation["residual"] is None
    assert result.conclusion_level != "formal_consistent"


def test_table_heading_inherits_boundary_currency_and_unit():
    page = page_with_table(["2025年度合并利润表", "单位：人民币万元"],
                           [["指标", "2024 年", "2025 年"], ["研发投入金额", "100", "120"]])
    extracted = _extract_tables(page, document(), ["research"])
    target = next(item for item in extracted if item.value == "120")
    assert target.report_boundary == "consolidated"
    assert target.currency == "CNY" and target.currency_status == "table"
    assert target.unit == "万元" and target.unit_status == "table"
    assert target.display_precision == 0
    assert target.rounding_method == "unknown"
    assert target.content_class == "company"
    assert target.table_id and target.row_index is not None and target.column_index is not None
    assert target.report_boundary_source_quote and "合并" in target.report_boundary_source_quote


def test_table_heading_metric_scope_is_recorded_without_guessing():
    heading = ["2025年度合并利润表", "研发投入统计范围为合并范围", "单位：万元"]
    page = page_with_table(heading, [["指标", "2025 年"], ["研发投入金额", "120"]])
    target = next(item for item in _extract_tables(page, document(), ["research"]) if item.value == "120")
    assert target.scope_level == "metric"
    assert "研发投入统计范围" in target.scope
    assert target.scope_source_quote and target.scope_source_id == target.occurrence_id
    assert target.report_boundary == "consolidated"


def test_currency_is_not_inferred_from_yuan_word_only():
    page = page_with_table(["2025年度合并利润表", "单位：万元"],
                           [["指标", "2025 年"], ["研发投入金额", "120"]])
    target = next(item for item in _extract_tables(page, document(), ["research"]) if item.value == "120")
    assert target.currency == ""
    assert target.currency_status == "unknown"


def test_parent_and_consolidated_boundaries_are_blocked_not_called_errors():
    rows = [row(1, "研发投入金额", "120", boundary="parent"),
            row(2, "研发投入金额", "100", document_id="SYN-ESG", boundary="consolidated")]
    check = check_for(rows)
    result = calculate(check, rows)
    assert result.criteria_status == "unknown"
    assert result.calculation_status == "not_comparable"
    assert any("不同口径" in value or "合并报表与母公司" in value for value in result.unresolved)
    assert result.calculation["residual"] is None
    assert result.conclusion_level != "unexplained_difference"
    assert result.comparability["boundary"]["status"] == "different"


def test_parent_boundary_against_unverified_boundary_is_not_comparable():
    rows = [row(1, "研发费用", "1249616010.99", unit="元", boundary="parent"),
            row(2, "研发费用", "37.79", unit="亿元", document_id="SYN-ESG", boundary="unknown")]
    result = calculate(check_for(rows), rows)
    assert result.calculation_status == "not_comparable"
    assert result.comparability["boundary"]["status"] == "undetermined"
    assert any("报告边界未证实" in value for value in result.unresolved)
    assert result.calculation["residual"] is None


def test_table_group_scope_difference_blocks_equal_relation():
    rows = [row(1, "环保投入", "100", table_scope="钢铁", scope="钢铁", scope_level="table", boundary="consolidated"),
            row(2, "环保投入", "100", document_id="SYN-ESG", table_scope="其他", scope="其他",
                scope_level="table", boundary="consolidated")]
    result = calculate(check_for(rows), rows)
    assert result.calculation_status == "not_comparable"
    assert "表内分组" in "；".join(result.unresolved)
    assert result.conclusion_level != "formal_consistent"


def test_missing_currency_blocks_formal_and_keeps_input_provenance():
    rows = [row(1, "研发投入金额", "1", unit="亿元"),
            row(2, "研发投入金额", "10000", unit="万元", document_id="SYN-ESG")]
    rows[0].currency = ""
    result = calculate(check_for(rows), rows)
    assert result.calculation_status == "not_comparable"
    assert any("币种尚未证实" in value for value in result.unresolved)
    assert result.comparability["currency"]["status"] == "missing"


def test_unit_multiplier_is_kept_with_raw_value_and_factor():
    rows = [row(1, "研发投入金额", "1", unit="亿元"),
            row(2, "研发投入金额", "10000", unit="万元", document_id="SYN-ESG")]
    result = calculate(check_for(rows), rows)
    assert result.calculation_status == "consistent"
    inputs = {item["occurrence_id"]: item for item in result.calculation["inputs"]}
    assert inputs[rows[0].occurrence_id]["raw"] == "1"
    assert inputs[rows[0].occurrence_id]["unit_factor"] == "100000000"
    assert inputs[rows[0].occurrence_id]["normalized"] == "100000000"
    assert inputs[rows[1].occurrence_id]["normalized"] == "100000000"
    assert result.conclusion_level == "formal_consistent"


def test_display_precision_interval_is_conditional_and_explains_five_liangye_gap():
    rows = [row(1, "研发投入金额", "449183817.50", unit="元", display_precision=2),
            row(2, "研发投入金额", "4.49", unit="亿元", document_id="SYN-ESG", display_precision=2)]
    result = calculate(check_for(rows, unknown=("范围",)), rows)
    assumption = result.calculation["assumption_check"]
    assert assumption["status"] == "contains_zero"
    assert assumption["assumption"] == "display_half_up"
    assert assumption["residual_interval"]["low"] == "-316182.505"
    assert assumption["residual_interval"]["high"] == "683817.505"
    assert result.hypothetical["residual"] == "183817.50"
    assert result.calculation["residual"] is None
    assert result.calculation_status == "not_comparable"
    assert result.conclusion_level == "assumption_compatible"
    assert result.basis_level == "L0"


def test_display_precision_does_not_hide_real_gap():
    rows = [row(1, "研发投入金额", "449183817.50", unit="元", display_precision=2),
            row(2, "研发投入金额", "4.00", unit="亿元", document_id="SYN-ESG", display_precision=2)]
    result = calculate(check_for(rows, unknown=("范围",)), rows)
    assumption = result.calculation["assumption_check"]
    assert assumption["status"] == "not_contains_zero"
    assert result.conclusion_level == "insufficient_basis"
    assert result.basis_level == "L0"


def test_integer_values_do_not_get_display_rounding_interval():
    rows = [row(1, "研发人员数量", "2581", unit="人"),
            row(2, "研发人员数量", "2581", unit="人", document_id="SYN-ESG")]
    result = calculate(check_for(rows, unknown=("范围",)), rows)
    assert result.calculation["assumption_check"]["status"] == "not_run"
    assert result.conclusion_level == "insufficient_basis"


def test_unknown_rounding_never_becomes_formal_even_when_interval_contains_zero():
    rows = [row(1, "研发投入金额", "2.00", unit="元"),
            row(2, "研发投入金额", "2.004", unit="元", document_id="SYN-ESG")]
    result = calculate(check_for(rows), rows)
    assert result.calculation_status == "unexplained_difference"
    assert result.conclusion_level != "formal_consistent"
    assert result.calculation["assumption_check"]["status"] == "contains_zero"
    assert result.calculation["residual"] == "-0.004"


def test_explanation_text_never_changes_numeric_result():
    rows = [row(1, "研发投入金额", "100"),
            row(2, "研发投入金额", "105", document_id="SYN-ESG")]
    empty = calculate(check_for(rows), rows)
    explained = calculate(check_for(rows, explanation="统计范围调整但没有依据"), rows)
    assert empty.calculation["residual"] == explained.calculation["residual"] == "-50000"
    assert empty.criteria_status == explained.criteria_status == "supported"
    assert empty.comparability["explanation"]["status"] == "not_provided"
    assert explained.comparability["explanation"]["status"] == "unsupported"
    assert not any("解释尚缺" in value for value in explained.unresolved)


def test_narrative_unsupported_explanation_still_blocks_narrative_only():
    rows = [row(1, "研发投入说明", None, topic="research")]
    check = check_for(rows, rule="NAR-001", roles=["occurrence"], explanation="没有引文的解释")
    result = calculate(check, rows)
    assert result.calculation_status == "not_applicable"
    assert result.criteria_status == "unknown"
    assert any("解释尚缺" in value for value in result.unresolved)


def test_macro_and_industry_rows_are_excluded_with_reason_but_company_row_kept():
    page = page_with_table(["2025年全国粗钢产量与钢材价格指数", "单位：万吨"],
        [["指标", "2025 年"], ["我国粗钢产量", "100"], ["钢材价格指数", "9.23"], ["公司粗钢产量", "80"]])
    extracted = _extract_tables(page, document(), ["intensity"])
    by_label = {item.label: item for item in extracted}
    assert by_label["我国粗钢产量"].content_class == "macro"
    assert by_label["我国粗钢产量"].quality == "uncertain"
    assert by_label["钢材价格指数"].content_class == "macro"
    assert by_label["钢材价格指数"].quality == "uncertain"
    assert by_label["公司粗钢产量"].content_class == "company"
    assert by_label["公司粗钢产量"].quality == "located"
    excluded = {item.label for item in _exclusions(extracted)}
    assert {"我国粗钢产量", "钢材价格指数"} <= excluded
    assert "公司粗钢产量" not in excluded


def test_row_label_identity_restores_parent_and_rejects_bare_ordinal():
    assert _label_from_row(["一", "营业收入", "100"])[0] == "营业收入"
    assert _resolve_row_identity([["一", "120"]], 0, ["一", "120"])[2] is False
    composed, parent, valid = _resolve_row_identity([["研发投入合计", "100"], ["其中", "20"]], 1, ["其中", "20"])
    assert valid and parent == "研发投入合计"
    assert composed == "研发投入合计·其中"
    assert _row_role("研发投入合计") == "total"
    assert _row_role("费用化研发投入") == "component"
    assert _column_role(["2025 年", "钢铁"], "2025 年 / 钢铁") == "component"
    assert _column_role(["2025 年", "合计"], "2025 年 / 合计") == "total"


def test_boundary_parser_keeps_ambiguous_merged_and_parent_unknown():
    assert _boundary_from_text("2025年度合并及母公司利润表") == "unknown"
    assert _boundary_from_text("母公司利润表") == "parent"
    assert _boundary_from_text("合并利润表") == "consolidated"
    assert _boundary_from_text("分部报告") == "segment"


def test_display_precision_parser_contains_trailing_zero_information():
    assert _display_precision("449,183,817.50") == 2
    assert _display_precision("4.49") == 2
    assert _display_precision("2581") == 0
    assert _display_precision("(1,234.00)") == 2
    assert _display_precision("2.00") == 2


def test_metric_identity_dictionary_covers_new_topics_and_rejects_false_equivalence():
    assert metric_identity("研发投入金额（亿元）")["metric_id"] == "研发投入金额"
    assert metric_identity("研发费用")["metric_id"] == "研发费用"
    assert metric_identity("研发费用")["metric_id"] != "研发投入金额"
    emissions = metric_identity("温室气体排放总量")
    assert emissions["metric_id"] == "温室气体排放量" and emissions["dimension"] == "co2e"
    assert metric_identity("综合能源消耗量")["metric_id"] == "综合能源消耗量"
    assert metric_identity("总取水量")["metric_id"] == "年度总用水量"
    assert metric_identity("排放强度")["metric_id"] == ""
    assert content_classification("我国粗钢产量", "")[0] == "macro"
    assert content_classification("公司粗钢产量", "2025年全国粗钢产量统计")[0] == "company"


def _table_row(table_id, index, label, value, row_index, column_index, *, row_role, column_role,
               column_header="2025 年", header_path=None, topic="research", unit="万元"):
    return row(index, label, value, unit=unit, table_id=table_id, row_index=row_index,
               column_index=column_index, row_role=row_role, column_role=column_role,
               column_header=column_header, header_path=header_path or [column_header], topic=topic)


def test_row_composition_candidate_has_structure_but_is_only_L1_until_text_supported():
    rows = [
        _table_row("SYN-T0", 1, "费用化研发投入", "60", 0, 2, row_role="component", column_role="period"),
        _table_row("SYN-T0", 2, "资本化研发投入", "40", 1, 2, row_role="component", column_role="period"),
        _table_row("SYN-T0", 3, "研发投入合计", "100", 2, 2, row_role="total", column_role="period"),
    ]
    candidates = build_table_composition_candidates(rows, "2025")
    assert len(candidates) == 1
    candidate = candidates[0]
    structure = candidate.table_structure
    assert structure["layout"] == "row_sum"
    assert structure["coverage"]["total_equals_sum"] is True
    assert structure["coverage"]["component_count"] == 2
    assert {item["row_index"] for item in structure["components"]} == {0, 1}
    result = calculate(candidate, rows)
    assert result.calculation_status == "not_comparable"
    assert result.calculation["residual"] is None
    assert result.hypothetical["residual"] == "0"
    assert result.conclusion_level == "limited_support"
    assert result.basis_level == "L1"
    supported = candidate.model_copy(deep=True)
    supported.relationship_basis = "text_statement"
    supported.relationship_evidence = refs_for(rows)
    supported.conditions = [ComparisonCondition(name=name, status="supported", reason="合成",
                                                evidence=refs_for(rows))
                            for name in required_conditions(supported.operator)]
    formal = calculate(supported, rows)
    assert formal.criteria_status == "supported"
    assert formal.calculation_status == "consistent"
    assert formal.conclusion_level == "formal_consistent"
    assert formal.basis_level == "L2"


def test_column_composition_candidate_detects_steel_plus_other_equals_total():
    rows = [
        _table_row("SYN-T1", 1, "环保投入", "60", 0, 1, row_role="detail", column_role="component",
                   column_header="2025 年 / 钢铁", header_path=["2025 年", "钢铁"], topic="environment"),
        _table_row("SYN-T1", 2, "环保投入", "40", 0, 2, row_role="detail", column_role="component",
                   column_header="2025 年 / 其他", header_path=["2025 年", "其他"], topic="environment"),
        _table_row("SYN-T1", 3, "环保投入", "100", 0, 3, row_role="detail", column_role="total",
                   column_header="2025 年 / 合计", header_path=["2025 年", "合计"], topic="environment"),
    ]
    candidates = build_table_composition_candidates(rows, "2025")
    assert len(candidates) == 1
    structure = candidates[0].table_structure
    assert structure["layout"] == "column_sum"
    assert structure["coverage"]["total_equals_sum"] is True
    assert len(structure["components"]) == 2


def test_composition_missing_component_is_not_forced_closed():
    row_missing = [
        _table_row("SYN-T2", 1, "费用化研发投入", "60", 0, 2, row_role="component", column_role="period"),
        _table_row("SYN-T2", 2, "研发投入合计", "100", 1, 2, row_role="total", column_role="period"),
    ]
    assert build_table_composition_candidates(row_missing, "2025") == []
    column_missing = [
        _table_row("SYN-T3", 1, "环保投入", "60", 0, 1, row_role="detail", column_role="component",
                   column_header="2025 年 / 钢铁", header_path=["2025 年", "钢铁"], topic="environment"),
        _table_row("SYN-T3", 2, "环保投入", "100", 0, 2, row_role="detail", column_role="total",
                   column_header="2025 年 / 合计", header_path=["2025 年", "合计"], topic="environment"),
    ]
    assert build_table_composition_candidates(column_missing, "2025") == []


def test_cross_table_bridge_is_optional_and_marked_as_limited():
    rows = [
        _table_row("SYN-T4", 1, "环保投入合计", "100", 5, 2, row_role="total", column_role="period", topic="environment"),
        _table_row("SYN-T5", 2, "环保投入-钢铁", "60", 0, 2, row_role="component", column_role="period", topic="environment"),
        _table_row("SYN-T5", 3, "环保投入-其他", "40", 1, 2, row_role="component", column_role="period", topic="environment"),
    ]
    assert not [item for item in build_table_composition_candidates(rows, "2025") if item.table_structure["layout"] == "cross_table"]
    crossing = build_table_composition_candidates(rows, "2025", include_cross_table=True)
    assert any(item.table_structure["layout"] == "cross_table" for item in crossing)
    bridge = next(item for item in crossing if item.table_structure["layout"] == "cross_table")
    assert bridge.table_structure["non_overlap"]["status"] == "unknown"
    assert bridge.relationship_basis == "table_structure"


def test_table_structure_condition_evidence_is_not_upgraded_to_supported():
    rows = [
        _table_row("SYN-T6", 1, "费用化研发投入", "60", 0, 2, row_role="component", column_role="period"),
        _table_row("SYN-T6", 2, "资本化研发投入", "40", 1, 2, row_role="component", column_role="period"),
        _table_row("SYN-T6", 3, "研发投入合计", "100", 2, 2, row_role="total", column_role="period"),
    ]
    candidate = build_table_composition_candidates(rows, "2025")[0]
    upgraded, names = upgrade_conditions(candidate, run_of(rows), "2025")
    composition = next(item for item in upgraded.conditions if item.name == "组成完整")
    assert composition.status == "unknown"
    assert composition.evidence_kind == "table_structure"
    assert "L1" in composition.reason
    assert "组成完整" not in names


def test_legacy_scope_without_level_still_infers_boundary_for_compatibility():
    legacy = row(1, "研发投入金额", "100", scope="合并范围", scope_level="unknown")
    assert member_boundary(legacy) == "consolidated"
    parent = row(2, "研发投入金额", "100", scope="母公司", scope_level="unknown")
    assert member_boundary(parent) == "parent"
