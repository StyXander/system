"""字段候选必须按表头列身份取本期值，禁止用金额大小代替本期/上期判定。

覆盖 2026-09-09 审查反例 C01：本期 80、上期 120 时旧实现会为了排除附注号
把 120 提到首位并直接采用，且下游质量闸门使用同一套大小启发式而无法拦截。
"""
from __future__ import annotations

from backend.app.cases import (
    annotate_financial_field_quality,
    calculation_ready_financial_rows,
)
from backend.app.field_extraction import (
    FIELD_CONFIG,
    _find_page_candidate,
    _reorder_for_visibility,
    _scan_number_cells,
)

CONFIG = FIELD_CONFIG["accounts_receivable"]


def _row(candidate: dict, *, year: int = 2024) -> dict:
    """构造一条与 extract_cninfo_fields 输出同形的自动候选行。"""

    return {
        "evidence_id": f"FIX_AR_{year}",
        "field_kind": "accounts_receivable",
        "year": year,
        "value": candidate["value"],
        "unit": candidate["unit"] or "元",
        "source_unit": candidate.get("source_unit") or candidate.get("unit") or "元",
        "field_basis": CONFIG["basis"],
        "document_id": "FIX-DOC",
        "pdf_page": candidate["page"],
        "locator": candidate["locator"],
        "raw_excerpt": candidate["raw_excerpt"],
        "column_identity": candidate["column_identity"],
        "extraction_method": "pdf_text_heuristic_candidate",
        "source_review_status": "auto_extracted_pending_human_page_confirmation",
    }


def test_small_current_period_is_not_demoted_by_magnitude() -> None:
    """本期 80、上期 120 时必须取 80；旧缺陷会返回 120。"""

    candidate = _find_page_candidate(
        ["合并资产负债表\n单位：元\n项目 2024年末 2023年末\n应收账款\n80\n120\n"],
        CONFIG,
    )
    assert candidate["raw_value"] == 80.0
    assert candidate["column_identity"] == "resolved_by_header_position"


def test_note_column_is_dropped_by_header_position_not_by_size() -> None:
    """中国海油式“附注列 + 两期”仍取本期，依据是列位置而不是数值大小。"""

    candidate = _find_page_candidate(
        [
            "2025年12月31日\n合并资产负债表\n人民币百万元\n项目\n附注\n"
            "2025年12月31日\n2024年12月31日\n应收账款\n（六）4\n32,415\n32,918\n"
        ],
        CONFIG,
    )
    assert candidate["raw_value"] == 32_415.0
    assert candidate["column_identity"] == "resolved_by_header_position"


def test_reversed_compare_columns_follow_the_target_report_year() -> None:
    """比较列倒序排列时，必须取目标报告年度所在的列，而不是第一个数字。"""

    pages = ["单位：元\n项目 2023年12月31日 2024年12月31日\n应收账款 120 80\n"]
    assert _find_page_candidate(pages, CONFIG, report_year=2024)["raw_value"] == 80.0
    assert _find_page_candidate(pages, CONFIG, report_year=2023)["raw_value"] == 120.0


def test_header_without_target_year_is_ambiguous() -> None:
    """表头只含其他年度时不能拿最新一列充数，必须标为歧义候选。"""

    candidate = _find_page_candidate(
        ["单位：元\n项目 2023年12月31日 2022年12月31日\n应收账款 120 90\n"],
        CONFIG,
        report_year=2024,
    )
    assert candidate["column_identity"] == "unresolved_report_year_not_in_header"


def test_bare_note_number_without_header_is_ambiguous_and_blocked() -> None:
    """表头没有期间列时不得自动采用；可见性排序保留，但行必须被闸门阻断。"""

    pages = ["合并资产负债表\n单位：元\n应收账款\n4\n8,110,758,258.05\n7,293,628,386.69\n"]
    assert _reorder_for_visibility(_scan_number_cells(pages[0].splitlines(), 2, term="应收账款"))[0][0] == 8_110_758_258.05
    candidate = _find_page_candidate(pages, CONFIG, report_year=2024)
    assert candidate["column_identity"].startswith("unresolved_")
    annotated = annotate_financial_field_quality(_row(candidate))
    assert annotated["candidate_quality_status"] == "blocked_pending_human_confirmation"
    assert any("列身份" in issue for issue in annotated["candidate_quality_issues"])
    assert calculation_ready_financial_rows([_row(candidate)]) == []


def test_legit_small_amount_in_wan_unit_is_not_flagged_as_note() -> None:
    """单位万元下的合法小金额，列身份已确认时不能被“≤100 疑似附注号”误杀。"""

    candidate = _find_page_candidate(
        ["合并资产负债表\n单位：万元\n项目 2024年12月31日 2023年12月31日\n应收账款 80 120\n"],
        CONFIG,
        report_year=2024,
    )
    assert candidate["raw_value"] == 80.0
    annotated = annotate_financial_field_quality(_row(candidate))
    assert annotated["candidate_quality_issues"] == []


def test_scan_number_cells_keeps_document_order() -> None:
    """位置解析依赖文档顺序，扫描函数不得重排。"""

    lines = ["应收账款", "80", "120"]
    assert [value for value, _ in _scan_number_cells(lines, 0, term="应收账款")] == [80.0, 120.0]
