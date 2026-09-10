"""文档身份、报告年度、年报类型是三个独立必要条件，不能互相补分。

覆盖 2026-09-09 审查反例 C03：旧实现把四项命中相加，名称、代码和报告类型
齐了就能放行错误年度，却仍返回 validation_status=passed。
"""
from __future__ import annotations

import httpx
import pymupdf as fitz
import pytest

from backend.app.cninfo import CNInfoClient, CNInfoError

COMPANY = {"company_name": "Fixture Corporation", "company_alias": "", "ticker": "600302"}
# 真实年报的财务报表在中后部，补页只能用不含企业名、代码和报告年度的中性正文。
BODY_LINE = "测试文档正文段落，用于填满页数，不含企业名、证券代码或报告年度标识。" * 3


def _validate(pages: dict[int, str], announcement: dict) -> dict:
    document = fitz.open()
    for index in range(12):
        document.new_page().insert_text((40, 60), pages.get(index, BODY_LINE))
    content = document.tobytes()
    document.close()
    client = CNInfoClient(client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))
    return client.validate_pdf(content, announcement, COMPANY)


def test_wrong_report_year_is_rejected_even_with_name_code_and_type() -> None:
    """封面只写 2022 时，公告标题写 2024 也不能放行。"""

    with pytest.raises(CNInfoError) as error:
        _validate(
            {0: "Fixture Corporation 600302 2022 annualreport"},
            {"report_year": 2024, "announcement_title": "2024 annualreport", "company_name": "Fixture Corporation"},
        )
    assert error.value.code == "PDF_REPORT_YEAR_UNCONFIRMED"
    assert error.value.detail["year_source"] == "absent"


def test_year_only_in_comparison_column_is_not_auto_confirmed() -> None:
    """目标年度只在比较列出现时只能进入待核验，不能记成 passed。"""

    result = _validate(
        {
            0: "Fixture Corporation 600302 2023年年度报告",
            6: "合并资产负债表 单位：元 项目 2023年12月31日 2024年12月31日 应收账款 80 120",
        },
        {"report_year": 2024, "announcement_title": "2024 年度报告", "company_name": "Fixture Corporation"},
    )
    assert result["validation_status"] == "identity_unresolved"
    assert result["content_checks"]["year_source"] == "comparison_column_only"
    assert result["content_checks"]["year_hit"] is False


def test_cover_year_passes_and_records_evidence() -> None:
    result = _validate(
        {0: "Fixture Corporation 600302 2024年年度报告"},
        {"report_year": 2024, "announcement_title": "2024 年度报告", "company_name": "Fixture Corporation"},
    )
    assert result["validation_status"] == "passed"
    assert result["content_checks"]["year_source"] == "cover_text"


def test_missing_company_identity_is_rejected() -> None:
    """公告元数据总带着目标企业名，所以身份必须看 PDF 正文是否复述了它。"""

    with pytest.raises(CNInfoError) as error:
        _validate(
            {0: "2024年年度报告 第二节 会计数据和财务指标摘要"},
            {"report_year": 2024, "announcement_title": "2024 年度报告", "company_name": "Fixture Corporation"},
        )
    assert error.value.code == "PDF_IDENTITY_MISMATCH"
    assert error.value.detail["name_hit"] is False
    assert error.value.detail["code_hit"] is False


def test_non_annual_document_is_rejected() -> None:
    with pytest.raises(CNInfoError) as error:
        _validate(
            {0: "Fixture Corporation 600302 2024年第一季度报告"},
            {"report_year": 2024, "announcement_title": "2024年第一季度报告", "company_name": "Fixture Corporation"},
        )
    assert error.value.code == "PDF_NOT_ANNUAL_REPORT"


def test_error_message_no_longer_claims_the_year_was_confirmed() -> None:
    """错误文案不得再声称已同时确认企业、年度与报告类型三项。"""

    with pytest.raises(CNInfoError) as error:
        _validate(
            {0: "Fixture Corporation 600302 2022 annualreport"},
            {"report_year": 2024, "announcement_title": "2024 annualreport", "company_name": "Fixture Corporation"},
        )
    assert "同时确认" not in str(error.value)
