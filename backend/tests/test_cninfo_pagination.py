"""公告翻页必须显式区分"完整"与"截至分页上限"，不得把截断当成已核验最新。

覆盖 2026-09-09 审查结构风险 4.2：旧实现撞满 MAX_ANNOUNCEMENT_PAGES 且
hasMore 仍为真时，静默返回已取得的候选。
"""
from __future__ import annotations

import httpx

from backend.app.cninfo import MAX_ANNOUNCEMENT_PAGES, CNInfoClient

COMPANY = {
    "ticker": "600302",
    "org_id": "gssh0600302",
    "market": "sse",
    "company_name": "测试科技",
    "company_alias": "测试科技",
}


def _rows(count: int) -> list[dict[str, object]]:
    return [
        {
            "announcementId": f"DOC-{index}",
            "announcementTitle": f"测试科技2024年年度报告{index}",
            "announcementTime": 1745856000000 + index,
            "adjunctUrl": f"static/DISC_{index}.PDF",
            "adjunctType": "PDF",
        }
        for index in range(count)
    ]


def _client(handler) -> CNInfoClient:
    return CNInfoClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_delay_seconds=0,
        max_retries=0,
    )


def test_truncated_page_run_is_reported_as_partial() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"announcements": _rows(30), "hasMore": True})

    with _client(handler) as client:
        candidates, status = client.search_annual_reports_detailed(COMPANY, 2024)

    assert len(calls) == MAX_ANNOUNCEMENT_PAGES
    assert status["fetched_pages"] == MAX_ANNOUNCEMENT_PAGES
    assert status["has_more"] is True and status["truncated"] is True
    assert status["completeness"] == "partial_page_limit_reached"


def test_complete_page_run_is_reported_as_complete() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"announcements": _rows(2), "hasMore": False})

    with _client(handler) as client:
        candidates, status = client.search_annual_reports_detailed(COMPANY, 2024)

    assert status["fetched_pages"] == 1
    assert status["truncated"] is False
    assert status["completeness"] == "complete"
    assert len(candidates) == 2


def test_selection_records_truncation_so_latest_is_not_claimed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"announcements": _rows(2), "hasMore": False})

    with _client(handler) as client:
        candidates, status = client.search_annual_reports_detailed(COMPANY, 2024)
        truncated = dict(status, truncated=True)
        partial = client.select_annual_report(candidates, 2024, query_status=truncated)
        clean = client.select_annual_report(candidates, 2024, query_status=status)
        unknown = client.select_annual_report(candidates, 2024)

    assert "分页上限截断" in partial["selection_reason"]
    assert partial["candidate_completeness"] == "partial_page_limit_reached"
    assert "分页上限截断" not in clean["selection_reason"]
    assert clean["candidate_completeness"] == "complete"
    assert unknown["candidate_completeness"] == "unknown"
