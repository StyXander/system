"""验收报告指出问题的合成回归：四问分母与不可判断分类、版本链、脚注绑定、声明分派。

全部使用合成输入，不调用外部模型，也不写入运行目录。
"""
from decimal import Decimal

import pytest

from app.connectivity_conditions import upgrade_conditions
from app.connectivity_engine import calculate
from app.connectivity_extraction import _footnote_for
from app.connectivity_overview import build_overview
from app.connectivity_schemas import (ComparisonCondition, ConnectivityRun, DisclosureOccurrence, EvidenceRef, ReportDocument,
    RelationshipCheck, RelationshipMember, SearchCoverage)
from app.connectivity_versions import build_version_chain
from test_connectivity_engine import relationship


def document(document_id, role="unknown", date="", report_type="AR", company_id="SYN"):
    return ReportDocument(document_id=document_id, case_id="SYN-PAIR", company_id=company_id, company="合成企业",
        report_type=report_type, period="2025", disclosure_date=date, version_role=role,
        source_url="https://example.invalid/synthetic")


def occurrence(document_id, label, value, year="2025", unit="万元", index=0):
    return DisclosureOccurrence(occurrence_id=f"{document_id}-{index}", document_id=document_id, pdf_page=1,
        bbox=[10, 10 + index, 100, 20 + index], label=label, value=value, unit=unit, unit_source="本表单位列",
        currency="CNY", year=year, year_status="attributed", column_header="2025 年",
        row_header=f"{label} | {value}", context=f"合成企业2025年 单位：万元 {label} | {value} | {unit}",
        quality="located", quality_reason="已绑定", topic="research")


def base_run(checks, occurrences=(), exclusions=(), coverage=()):
    return ConnectivityRun(run_id="SYN-RUN", company="合成企业", period="2025", report_period="2025",
        documents=[document("SYN-AR")], occurrences=list(occurrences), checks=list(checks),
        extraction_exclusions=list(exclusions), coverage=list(coverage), dataset_role="synthetic")


def test_fourth_question_splits_rows_and_pages():
    overview = build_overview(base_run([], coverage=[SearchCoverage(document_id="SYN-AR", total_pages=362, parsed_pages=362,
                                                                    searched_pages=list(range(1, 363)))]))
    # 两件事分开：未计入位置按"处"计，失败页按"页"计，不合成一个比值。
    assert overview["not_found"]["unattributed"]["denominator"] == 0
    assert overview["not_found"]["failed_pages"]["denominator"] == 362
    assert overview["not_found"]["value"] == 0
    assert "已提取0处" in overview["not_found"]["denominator_label"]


def test_gated_relations_are_listed_as_undecidable_not_as_zero_unexplained():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    check.conditions[3].status = "unknown"
    gated = calculate(check, rows)
    overview = build_overview(base_run([gated], occurrences=rows))
    assert overview["unexplained"]["value"] == 0
    assert overview["unexplained"]["undecidable"]["value"] == 1
    assert overview["unexplained"]["undecidable"]["denominator"] == 1


def test_missing_conditions_show_evidence_gap_not_only_counts():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    # 五个条件均无依据：缺项与"有依据但未说明"必须分开统计。
    check.conditions = [ComparisonCondition(name=name) for name in ("主体", "期间", "定义", "范围", "单位")]
    overview = build_overview(base_run([calculate(check, rows)], occurrences=rows))
    breakdown = {item["name"]: item for item in overview["unconfirmable"]["missing_breakdown"]}
    assert breakdown["范围"]["unsupported"] == 1
    assert breakdown["范围"]["without_evidence"] == 1, "没有依据的缺项必须与有依据但冲突的缺项分开"
    assert {"主体", "期间", "定义", "范围", "单位"} <= set(breakdown)


def test_unresolved_causes_are_classified_into_six_buckets():
    rows, check = relationship("EQ-001", ["100", "105"], ["left", "right"])
    check.conditions[3].status = "unknown"
    overview = build_overview(base_run([calculate(check, rows)], occurrences=rows))
    causes = overview["unresolved_causes"]
    assert len(causes) == 6
    codes = {item["code"] for item in causes if item["count"]}
    assert "C1" in codes
    assert sum(item["count"] for item in causes) >= 1


def test_version_chain_links_original_and_two_corrections():
    original = document("SYN-ORIG", "original", "2025-04-20")
    first = document("SYN-C1", "correction", "2025-09-15")
    second = document("SYN-C2", "correction", "2025-10-10")
    chain = build_version_chain([
        {"document": original, "occurrences": [occurrence("SYN-ORIG", "研发投入", "7150.34")]},
        {"document": first, "occurrences": [occurrence("SYN-C1", "研发投入", "7132.61")]},
        {"document": second, "occurrences": [occurrence("SYN-C2", "研发投入", "7111.89")]},
    ])
    assert len(chain["records"]) == 3
    assert [record.version_role for record in chain["records"]] == ["original", "correction", "correction"]
    assert len(chain["changes"]) == 2
    assert {change.display_change for change in chain["changes"]} == {"-17.73", "-20.72"}
    assert all(change.only_version_evidence for change in chain["changes"])
    assert "不能计为已解释的跨报告差异" in chain["note"]


def test_version_chain_without_correction_is_explicit():
    chain = build_version_chain([{"document": document("SYN-ORIG", "original", "2025-04-20"),
                                  "occurrences": [occurrence("SYN-ORIG", "研发投入", "100")]}])
    assert chain["changes"] == []
    assert "只有原始版本" in chain["limitation"]


def test_footnote_does_not_cross_into_next_table():
    table = {"bbox": [0, 100, 200, 200]}
    later = {"bbox": [0, 400, 200, 500]}
    lines = [{"text": "注：本表口径为合并范围", "bbox": [0, 420, 200, 430]},
             {"text": "注1：本表单位为万元", "bbox": [0, 205, 200, 215]}]
    assert _footnote_for(table, lines, [table, later]) == "注1：本表单位为万元"
    far = [{"text": "注：属于下一张表的说明", "bbox": [0, 420, 200, 430]}]
    assert _footnote_for(table, far, [table, later]) == ""


def test_notice_is_dispatched_by_request_path():
    from app.main import _notice_for_request

    class Url:
        def __init__(self, path):
            self.path = path

    class Request:
        def __init__(self, path):
            self.url = Url(path)

    assert _notice_for_request(Request("/api/connectivity/runs/x")).startswith("AI生成内容，用于年度报告与可持续发展报告关联核对")
    assert _notice_for_request(Request("/api/run")).startswith("AI生成内容，仅供审计计划阶段进一步核查")
