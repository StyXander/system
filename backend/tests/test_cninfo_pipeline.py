"""巨潮年报适配器和自动导入闭环的离线回归。"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import fitz
import httpx
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.catalog import (
    connect_catalog,
    create_refresh_job,
    list_cache_entries,
    lookup_cached_case,
    refresh_report,
    resolve_analysis_source,
    sync_case_to_catalog,
    update_refresh_job,
)
from backend.app.cninfo import CNInfoClient, CNInfoError, _network_error_detail
from backend.app.field_extraction import FIELD_CONFIG, _find_page_candidate, _unit
from backend.app.industry_gate import evaluate_industry_gate
from backend.app.cases import (
    _runtime_base,
    confirm_cninfo_field,
    get_case,
    get_cninfo_field_readiness,
    get_cninfo_prescreen_plan,
    get_financial_rows,
    get_period_sources,
)
from backend.app.pipeline import _task_path, create_task, load_task, queue_retry, run_ingestion, update_analysis_result
from backend.app.schemas import AgentStep


def _pdf_bytes(year: int, *, include_fields: bool = False) -> bytes:
    """生成不含真实企业资料的多页 PDF 夹具。"""

    document = fitz.open()
    for page_number in range(12):
        page = document.new_page(width=595, height=842)
        if page_number == 0:
            text = f"测试科技股份有限公司 600302 {year}年年度报告"
        elif include_fields and page_number == 1:
            text = "主要会计数据\n单位：元\n营业收入\n1000\n900\n"
            if year == 2023:
                text = "主要会计数据\n单位：元\n营业收入\n900\n800\n"
        elif include_fields and page_number == 2:
            text = "资产及负债状况\n单位：元\n应收账款\n七、5\n500\n450\n"
            if year == 2023:
                text = "资产及负债状况\n单位：元\n应收账款\n七、5\n450\n400\n"
        elif page_number == 3:
            text = "销售模式与回款政策\n信用政策 客户账期 结算方式 回款政策"
        else:
            text = (f"测试科技 {year} 年度报告正文第 {page_number + 1} 页，用于离线 RAG 回归。" * 8)
        page.insert_text((48, 90), text, fontsize=11, fontname="china-s")
    content = document.tobytes(garbage=4, deflate=True)
    document.close()
    return content


def test_pipeline_next_action_separates_incomplete_analysis_from_human_review(tmp_path: Path) -> None:
    """技术未完整不应继续冒充需要人工专业判断。"""

    task = create_task(tmp_path, {"company_query": "测试科技", "analysis_mode": "full_analysis"})
    task_id = task["task_id"]
    incomplete = update_analysis_result(
        tmp_path,
        task_id,
        {
            "run_id": "RUN-INCOMPLETE",
            "run_completeness": "incomplete_model_transfer_not_allowed",
        },
    )
    assert incomplete["status"] == "needs_human"
    assert incomplete["result"]["next_action"] == {
        "type": "inspect_incomplete_analysis",
        "label": "查看分析未完整原因",
        "target": "analysis",
        "requires_human_decision": False,
    }
    assert incomplete["steps"]["analysis_run"]["status"] == "needs_human"
    assert "不要求填写人工专业结论" in incomplete["steps"]["analysis_run"]["detail"]

    completed = update_analysis_result(
        tmp_path,
        task_id,
        {
            "run_id": "RUN-COMPLETE",
            "run_completeness": "complete_public_prescreen",
        },
    )
    assert completed["status"] == "completed"
    assert completed["result"]["next_action"] == {
        "type": "review_analysis_result",
        "label": "去做结果人工复核",
        "target": "delivery_review",
        "requires_human_decision": True,
    }


def test_cninfo_client_filters_summary_and_validates_pdf() -> None:
    pdf = _pdf_bytes(2024)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/new/data/szse_stock.json"):
            return httpx.Response(
                200,
                json={"stockList": [{"code": "600302", "zwjc": "测试科技", "zwjcFull": "测试科技股份有限公司", "orgId": "gssh0600302"}]},
            )
        if request.url.path.endswith("/new/hisAnnouncement/query"):
            payload = parse_qs(request.content.decode("utf-8"))
            assert payload["stock"] == ["600302,gssh0600302"]
            assert payload["column"] == ["sse"]
            assert payload["plate"] == ["sh"]
            return httpx.Response(
                200,
                json={
                    "hasMore": False,
                    "announcements": [
                        {
                            "announcementId": "summary",
                            "announcementTitle": "测试科技：测试科技2024年年度报告摘要",
                            "announcementTime": "2025-04-30",
                            "adjunctUrl": "/finalpage/2025-04-30/summary.PDF",
                            "secCode": "600302",
                            "secName": "测试科技",
                        },
                        {
                            "announcementId": "full",
                            "announcementTitle": "测试科技：测试科技2024年年度报告全文（修订版）",
                            "announcementTime": "2025-05-01",
                            "adjunctUrl": "/finalpage/2025-05-01/full.PDF",
                            "secCode": "600302",
                            "secName": "测试科技",
                        },
                    ],
                },
            )
        if request.url.host == "static.cninfo.com.cn":
            return httpx.Response(200, content=pdf)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with CNInfoClient(httpx.Client(transport=transport, follow_redirects=True), min_delay_seconds=0, max_retries=0) as client:
        # 名称查询会遍历统一股票清单；沪市归属必须由 6 开头代码判定。
        company = client.resolve_company("测试科技")
        candidates = client.search_annual_reports(company, 2024)
        selected = client.select_annual_report(candidates, 2024)
        content, meta = client.download_pdf(selected["source_url"])
        validation = client.validate_pdf(content, selected, company)

    assert company["org_id"] == "gssh0600302"
    assert company["market"] == "sse"
    assert company["column"] == "sse"
    assert company["plate"] == "sh"
    assert len(candidates) == 1
    assert "修订版" in selected["announcement_title"]
    assert meta["sha256"] == validation["sha256"]
    assert validation["page_count"] == 12
    assert validation["content_checks"]["code_hit"] is True


def test_field_extraction_accepts_rmb_unit_header_and_skips_parenthesized_note() -> None:
    """中国海油式“人民币百万元/（六）4”表头应提取报表列示净额，而不是附注号。"""

    assert _unit("合并资产负债表\n人民币百万元\n") == ("百万元", 1_000_000.0)
    assert _unit("合并资产负债表\n单位：人民币百万元\n") == ("百万元", 1_000_000.0)
    assert _unit("主要会计数据\n营业收入（元）\n") == ("元", 1.0)
    assert _unit("主营业务收入（人民币万元）\n") == ("万元", 10_000.0)

    candidate = _find_page_candidate(
        [
            "2025年12月31日\n"
            "合并资产负债表\n"
            "人民币百万元\n"
            "项目\n附注\n2025年12月31日\n2024年12月31日\n"
            "应收账款\n（六）4\n32,415\n32,918\n"
        ],
        FIELD_CONFIG["accounts_receivable"],
    )

    assert candidate is not None
    assert candidate["unit"] == "百万元"
    assert candidate["raw_value"] == 32_415.0
    assert candidate["value"] == 32_415_000_000.0
    assert FIELD_CONFIG["accounts_receivable"]["basis"] == "net"


def test_industry_gate_separates_financial_company_from_energy_company() -> None:
    financial = evaluate_industry_gate(
        company={"ticker": "601628", "company_name": "中国人寿", "source_mode": "cninfo_official"},
        case={"case_id": "CNINFO_601628_T0_20260325", "ticker": "601628", "company_name": "中国人寿"},
        rule_ids=["R1", "R2"],
    )
    energy = evaluate_industry_gate(
        company={"ticker": "600938", "company_name": "中国海油", "source_mode": "cninfo_official"},
        case={"case_id": "CNINFO_600938_T0_20260326", "ticker": "600938", "company_name": "中国海油"},
        rule_ids=["R1", "R2"],
    )

    assert financial["fit_level"] == "not_applicable"
    assert financial["blocked_rules"] == ["R1", "R2"]
    assert energy["fit_level"] == "direct"
    assert energy["allowed_rules"] == ["R1", "R2"]


def test_industry_gate_uses_verified_ticker_mapping_for_china_ping_an() -> None:
    """简称不含“保险”时，已验证证券代码仍应进入保险专用字段闸门。"""

    gate = evaluate_industry_gate(
        company={"ticker": "601318", "company_name": "中国平安", "source_mode": "cninfo_official"},
        case={"case_id": "CNINFO_601318_T0_20260326", "ticker": "601318", "company_name": "中国平安"},
        rule_ids=["R1"],
    )

    assert gate["fit_level"] == "not_applicable"
    assert gate["specialized_rule"] == "insurance_service_result"
    assert gate["blocked_rules"] == ["R1"]


def test_catalog_round_trip_keeps_source_metadata_and_matches_requested_years(tmp_path: Path) -> None:
    case = {
        "case_id": "CNINFO_600302_T0_20250430",
        "company_name": "测试科技股份有限公司",
        "company_alias": "测试科技",
        "ticker": "600302",
        "market": "sse",
        "registry_mode": "cninfo_official_auto",
        "source_snapshot_id": "SNAPSHOT-600302",
        "documents": [
            {
                "document_id": "DOC-600302-2024",
                "report_year": 2024,
                "source_url": "https://static.cninfo.com.cn/2024.pdf",
                "sha256": "A" * 64,
                "page_count": 12,
                "storage_relpath": "backend/runtime/cases/CNINFO_600302_T0_20250430/documents/2024.pdf",
                "validation_status": "passed",
            },
            {
                "document_id": "DOC-600302-2023",
                "report_year": 2023,
                "source_url": "https://static.cninfo.com.cn/2023.pdf",
                "sha256": "B" * 64,
                "page_count": 12,
                "storage_relpath": "backend/runtime/cases/CNINFO_600302_T0_20250430/documents/2023.pdf",
                "validation_status": "passed",
            },
        ],
    }
    gate = evaluate_industry_gate(company=case, case=case, rule_ids=["R1"])
    synced = sync_case_to_catalog(
        tmp_path,
        case,
        rows=[
            {
                "field_id": "revenue_2024",
                "field_kind": "revenue",
                "year": 2024,
                "value": 1000,
                "unit": "元",
                "document_id": "DOC-600302-2024",
                "pdf_page": 2,
                "locator": "PDF 第 2 页：营业收入",
                "evidence_id": "EVIDENCE-REV-2024",
                "raw_excerpt": "营业收入 1000",
            }
        ],
        rag_manifest={"status": "ready", "index_version": "rag-v1", "chunk_count": 10, "source_fingerprint": "FP-1"},
        industry_gate=gate,
    )

    hit = lookup_cached_case(tmp_path, "测试科技", [2024, 2023])
    entries = list_cache_entries(tmp_path, company_query="600302")

    assert synced["cache_status"] == "ready"
    assert hit is not None
    assert hit["ticker"] == "600302"
    assert hit["report_years"] == [2024, 2023]
    assert entries[0]["cache_status"] == "ready"


def test_cache_policy_exposes_stale_snapshot_without_calling_it_fresh(tmp_path: Path) -> None:
    case = {
        "case_id": "CNINFO_600303_T0_20250430",
        "company_name": "过期测试科技",
        "company_alias": "过期测试科技",
        "ticker": "600303",
        "market": "sse",
        "registry_mode": "cninfo_official_auto",
        "source_snapshot_id": "SNAPSHOT-600303",
        "documents": [
            {
                "document_id": "DOC-600303-2024",
                "report_year": 2024,
                "source_url": "https://static.cninfo.com.cn/2024.pdf",
                "sha256": "C" * 64,
                "page_count": 12,
                "storage_relpath": "backend/runtime/cases/CNINFO_600303_T0_20250430/documents/2024.pdf",
                "validation_status": "passed",
            },
            {
                "document_id": "DOC-600303-2023",
                "report_year": 2023,
                "source_url": "https://static.cninfo.com.cn/2023.pdf",
                "sha256": "D" * 64,
                "page_count": 12,
                "storage_relpath": "backend/runtime/cases/CNINFO_600303_T0_20250430/documents/2023.pdf",
                "validation_status": "passed",
            },
        ],
    }
    sync_case_to_catalog(
        tmp_path,
        case,
        rag_manifest={"status": "ready", "index_version": "rag-v1", "chunk_count": 2, "source_fingerprint": "FP-STALE"},
    )
    with connect_catalog(tmp_path) as connection:
        connection.execute("UPDATE source_snapshots SET verified_at=?", ("2020-01-01T00:00:00+0000",))
        connection.commit()

    assert lookup_cached_case(tmp_path, "600303", [2024, 2023]) is None
    stale = lookup_cached_case(tmp_path, "600303", [2024, 2023], include_stale=True)
    assert stale is not None and stale["cache_state"] == "stale"
    prefer = resolve_analysis_source(tmp_path, "600303", [2024, 2023], cache_policy="prefer_cache")
    refresh = resolve_analysis_source(tmp_path, "600303", [2024, 2023], cache_policy="refresh_if_stale")
    assert prefer["hit"] is True and prefer["reason"] == "stale_snapshot_fallback"
    assert refresh["hit"] is False and refresh["stale_match"]["cache_state"] == "stale"


def test_refresh_report_separates_success_not_applicable_and_missing_report(tmp_path: Path) -> None:
    batch_id = "CACHE-BATCH-TEST001"
    cases = [
        ("JOB-01", "TASK-01", "600938", "completed", {"result_status": "rag_ready", "industry_fit_level": "direct"}),
        ("JOB-02", "TASK-02", "601628", "completed", {"result_status": "rag_ready", "industry_fit_level": "not_applicable"}),
        ("JOB-03", "TASK-03", "000000", "needs_human", {"error_code": "ANNUAL_REPORT_NOT_FOUND", "message": "未找到年度报告全文。"}),
    ]
    for job_id, task_id, ticker, status, reason in cases:
        create_refresh_job(
            tmp_path,
            job_id=job_id,
            batch_id=batch_id,
            task_id=task_id,
            ticker=ticker,
            requested_years=[2025, 2024, 2023],
        )
        update_refresh_job(tmp_path, job_id, status=status, reason=reason)

    report = refresh_report(tmp_path, batch_id)

    assert report["total"] == 3
    assert report["counts"]["success"] == 1
    assert report["counts"]["not_applicable"] == 1
    assert report["counts"]["needs_human"] == 1


def test_queue_retry_recovers_interrupted_active_task(tmp_path: Path) -> None:
    """服务重启遗留活动状态但没有运行步骤时，任务应能保留历史后重试。"""

    task = create_task(
        tmp_path,
        {"company_query": "测试科技", "years": 3, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    task["status"] = "indexing"
    task["steps"]["rag_prepare"] = {"status": "passed", "detail": "RAG 索引已完成。"}
    task["steps"]["rag_smoke_test"] = {"status": "passed", "detail": "检索接口完成。"}
    # 与生产读取器使用同一路径解析，确保 pytest 命名空间不会写入正式目录。
    task_path = _task_path(tmp_path, task["task_id"])
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")

    queued = queue_retry(tmp_path, task["task_id"])

    assert queued["status"] == "queued"
    assert queued["history"][-1]["status"] == "indexing"
    assert queued["history"][-1]["errors"][-1]["code"] == "PIPELINE_INTERRUPTED"


class _FakeCNInfoClient:
    """不联网的流程夹具，模拟巨潮适配器已经返回的官方元数据。"""

    def __init__(self, pdfs: dict[int, bytes]) -> None:
        self.pdfs = pdfs
        self.downloaded_urls: list[str] = []

    def resolve_company(self, _query: str) -> dict[str, str]:
        return {
            "ticker": "600302",
            "company_name": "测试科技股份有限公司",
            "company_alias": "测试科技",
            "org_id": "gssh0600302",
            "market": "sse",
            "column": "sse",
            "plate": "sh",
            "source_mode": "cninfo_official",
        }

    def search_annual_reports(self, company: dict[str, str], year: int) -> list[dict[str, object]]:
        return [
            {
                "announcement_id": f"A{year}",
                "announcement_title": f"测试科技：测试科技{year}年年度报告全文",
                "announcement_date": f"{year + 1}-04-30",
                "report_year": year,
                "ticker": company["ticker"],
                "company_name": company["company_alias"],
                "org_id": company["org_id"],
                "source_url": f"https://static.cninfo.com.cn/finalpage/{year + 1}-04-30/{year}.PDF",
                "adjunct_type": "PDF",
                "adjunct_size": 1,
                "is_revised": False,
                "raw": {},
            }
        ]

    def select_annual_report(self, candidates: list[dict[str, object]], _year: int) -> dict[str, object]:
        selected = dict(candidates[0])
        selected.update({"selection_reason": "offline fixture", "candidate_count": 1, "candidate_urls": [selected["source_url"]]})
        return selected

    def download_pdf(self, source_url: str) -> tuple[bytes, dict[str, object]]:
        self.downloaded_urls.append(source_url)
        year = int(Path(source_url).stem)
        content = self.pdfs[year]
        import hashlib

        return content, {"final_url": source_url, "byte_count": len(content), "sha256": hashlib.sha256(content).hexdigest().upper()}

    def validate_pdf(self, content: bytes, _announcement: dict[str, object], _company: dict[str, str]) -> dict[str, object]:
        document = fitz.open(stream=content, filetype="pdf")
        pages = len(document)
        document.close()
        import hashlib

        return {
            "validation_status": "passed",
            "page_count": pages,
            "byte_count": len(content),
            "sha256": hashlib.sha256(content).hexdigest().upper(),
            "content_checks": {"name_hit": True, "code_hit": True, "year_hit": True, "annual_report_hit": True, "text_sample_chars": 100},
            "ocr_required": False,
        }


def test_new_year_reuses_validated_historical_pdfs_incrementally(tmp_path: Path) -> None:
    pdfs = {
        2023: _pdf_bytes(2023, include_fields=True),
        2024: _pdf_bytes(2024, include_fields=True),
        2025: _pdf_bytes(2025, include_fields=True),
    }
    first_client = _FakeCNInfoClient(pdfs)
    first = create_task(
        tmp_path,
        {"company_query": "600302", "years": 2, "latest_year": 2024, "analysis_mode": "rag_only", "rule_ids": ["R1"]},
    )
    first_result = run_ingestion(tmp_path, first["task_id"], client=first_client)

    second_client = _FakeCNInfoClient(pdfs)
    second = create_task(
        tmp_path,
        {"company_query": "600302", "years": 3, "latest_year": 2025, "analysis_mode": "rag_only", "rule_ids": ["R1"]},
    )
    second_result = run_ingestion(tmp_path, second["task_id"], client=second_client)

    assert first_result["status"] == "rag_ready"
    assert second_result["status"] == "rag_ready"
    assert len(second_client.downloaded_urls) == 1
    assert second_client.downloaded_urls[0].endswith("/2025.PDF")
    assert load_task(tmp_path, second["task_id"])["steps"]["download"]["cache_reused_count"] == 2


class _FailingCNInfoClient:
    """模拟服务进程没有外网权限时的巨潮股票清单失败。"""

    def resolve_company(self, _query: str) -> dict[str, str]:
        raise CNInfoError(
            "CNINFO_NETWORK_ERROR",
            "巨潮股票清单请求失败，已停止重试。当前服务进程没有外网访问权限。",
            detail={
                "reason": "network_permission_denied",
                "error_type": "PermissionError",
                "attempts": 3,
                "suggestion": "请用项目启动脚本重新启动服务。",
            },
        )


def test_network_permission_error_has_actionable_detail() -> None:
    detail = _network_error_detail(PermissionError(10013, "socket access forbidden"), 3)

    assert detail["reason"] == "network_permission_denied"
    assert detail["attempts"] == 3
    assert "启动审迹智链.bat" in detail["suggestion"]


def test_pipeline_failure_closes_running_company_step(tmp_path: Path) -> None:
    task = create_task(
        tmp_path,
        {"company_query": "宁德时代", "years": 3, "latest_year": 2024, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )

    result = run_ingestion(tmp_path, task["task_id"], client=_FailingCNInfoClient())
    saved = load_task(tmp_path, task["task_id"])

    assert result["status"] == "failed"
    assert saved is not None and saved["status"] == "failed"
    assert saved["steps"]["company_resolve"]["status"] == "failed"
    assert saved["steps"]["company_resolve"]["error"]["detail"]["reason"] == "network_permission_denied"
    assert not any(step["status"] == "running" for step in saved["steps"].values())


def test_rag_only_pipeline_registers_isolated_case(tmp_path: Path) -> None:
    pdfs = {2024: _pdf_bytes(2024), 2023: _pdf_bytes(2023)}
    task = create_task(
        tmp_path,
        {"company_query": "600302", "years": 2, "latest_year": 2024, "analysis_mode": "rag_only", "rule_ids": ["R1"]},
    )
    result = run_ingestion(tmp_path, task["task_id"], client=_FakeCNInfoClient(pdfs))
    saved = load_task(tmp_path, task["task_id"])

    assert result["status"] == "rag_ready"
    assert saved is not None and saved["status"] == "completed"
    assert saved["case_id"] == "CNINFO_600302_T0_20250430"
    assert result["rag"]["chunk_count"] > 0
    assert result["rag"]["smoke_status"] == "hit"
    case = get_case(tmp_path, saved["case_id"])
    assert case is not None
    assert case["registry_mode"] == "cninfo_official_auto"
    assert len(case["documents"]) == 2
    assert get_financial_rows(tmp_path, saved["case_id"]) == []


def test_full_pipeline_stops_before_model_when_field_candidate_is_incomplete(tmp_path: Path) -> None:
    pdfs = {2024: _pdf_bytes(2024, include_fields=True), 2023: _pdf_bytes(2023, include_fields=True)}
    task = create_task(
        tmp_path,
        {"company_query": "600302", "years": 2, "latest_year": 2024, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    result = run_ingestion(tmp_path, task["task_id"], client=_FakeCNInfoClient(pdfs))
    saved = load_task(tmp_path, task["task_id"])

    assert result["status"] == "ready_for_analysis"
    assert saved is not None and saved["status"] == "ready_for_analysis"
    case = get_case(tmp_path, saved["case_id"])
    assert case is not None
    assert case["available_years"] == [2024]
    rows = get_financial_rows(tmp_path, saved["case_id"])
    assert {(row["field_kind"], row["year"]) for row in rows} == {
        ("revenue", 2024),
        ("revenue", 2023),
        ("accounts_receivable", 2024),
        ("accounts_receivable", 2023),
    }
    assert {
        row["year"]: row["value"]
        for row in rows
        if row["field_kind"] == "accounts_receivable"
    } == {2024: 500.0, 2023: 450.0}


def test_pipeline_reuses_catalog_before_live_company_lookup(tmp_path: Path) -> None:
    """同一企业第二次分析应先命中已校验快照，不再依赖巨潮股票清单请求。"""

    pdfs = {2024: _pdf_bytes(2024, include_fields=True), 2023: _pdf_bytes(2023, include_fields=True)}
    first = create_task(
        tmp_path,
        {"company_query": "600302", "years": 2, "latest_year": 2024, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    first_result = run_ingestion(tmp_path, first["task_id"], client=_FakeCNInfoClient(pdfs))

    second = create_task(
        tmp_path,
        {"company_query": "测试科技", "years": 2, "latest_year": 2024, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    second_result = run_ingestion(tmp_path, second["task_id"], client=_FailingCNInfoClient())

    assert first_result["status"] == "ready_for_analysis"
    assert second_result["status"] == "ready_for_analysis"
    assert second_result["cache"]["hit"] is True
    assert second_result["case_id"] == first_result["case_id"]


def test_full_analysis_rescans_rag_only_cache_for_fields(tmp_path: Path) -> None:
    """RAG-only 预热后首次完整分析必须复用 PDF 并补做字段提取。"""

    pdfs = {2024: _pdf_bytes(2024, include_fields=True), 2023: _pdf_bytes(2023, include_fields=True)}
    warmup = create_task(
        tmp_path,
        {"company_query": "600302", "years": 2, "latest_year": 2024, "analysis_mode": "rag_only", "rule_ids": ["R1"]},
    )
    warmup_result = run_ingestion(tmp_path, warmup["task_id"], client=_FakeCNInfoClient(pdfs))
    assert warmup_result["status"] == "rag_ready"
    assert get_financial_rows(tmp_path, warmup_result["case_id"]) == []

    full = create_task(
        tmp_path,
        {"company_query": "600302", "years": 2, "latest_year": 2024, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    # 命中本地缓存后不应再调用巨潮；PDF 已在 warmup 中通过硬校验并留在案例目录。
    full_result = run_ingestion(tmp_path, full["task_id"], client=_FailingCNInfoClient())

    assert full_result["status"] == "ready_for_analysis"
    assert full_result["field_extraction"]["row_count"] == 4
    assert full_result["field_extraction"]["status"] == "passed_technical_pending_human"
    rows = get_financial_rows(tmp_path, full_result["case_id"])
    assert {(row["field_kind"], row["year"]) for row in rows} == {
        ("revenue", 2024),
        ("revenue", 2023),
        ("accounts_receivable", 2024),
        ("accounts_receivable", 2023),
    }
    saved = load_task(tmp_path, full["task_id"])
    assert saved is not None
    assert saved["steps"]["field_extract"]["source"] == "validated_pdf_rescan"


def test_public_prescreen_uses_latest_complete_pair_and_reports_third_year_gap(tmp_path: Path) -> None:
    """缺少第三年字段时仍使用最近两年，并把缺口和趋势限制写入计划。"""

    pdfs = {
        2024: _pdf_bytes(2024, include_fields=True),
        2023: _pdf_bytes(2023, include_fields=True),
        2022: _pdf_bytes(2022),
    }
    task = create_task(
        tmp_path,
        {"company_query": "600302", "years": 3, "latest_year": 2024, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    result = run_ingestion(tmp_path, task["task_id"], client=_FakeCNInfoClient(pdfs))
    saved = load_task(tmp_path, task["task_id"])
    assert result["status"] == "ready_for_analysis"
    assert saved is not None and saved["status"] == "ready_for_analysis"
    assert result["field_extraction"]["status"] == "passed_technical_with_gaps"
    assert result["field_extraction"]["human_review_required"] is False

    case_id = result["case_id"]
    plan = get_cninfo_prescreen_plan(tmp_path, case_id, 2024, ["R1"])
    assert plan["analysis_current_year"] == 2024
    assert plan["analysis_years"] == [2024, 2023]
    assert plan["rule_plans"]["R1"]["three_year_available"] is False
    assert any("2022" in item for item in plan["missing_fields"])

    context, sources = get_period_sources(tmp_path, case_id, 2024, ("R1",))
    assert context["public_prescreen"] is True
    assert context["analysis_cutoff_year"] == 2024
    assert {item["field_id"] for item in sources} == {
        "revenue_current",
        "revenue_previous",
        "ar_current",
        "ar_previous",
    }


def test_public_prescreen_api_completes_with_gap_and_keeps_rag_evidence(tmp_path: Path, monkeypatch) -> None:
    """公开预筛的实际 runs API 不因第三年缺口阻断候选和 RAG。"""

    pdfs = {
        2024: _pdf_bytes(2024, include_fields=True),
        2023: _pdf_bytes(2023, include_fields=True),
        2022: _pdf_bytes(2022),
    }
    task = create_task(
        tmp_path,
        {"company_query": "600302", "years": 3, "latest_year": 2024, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    result = run_ingestion(tmp_path, task["task_id"], client=_FakeCNInfoClient(pdfs))
    case_id = result["case_id"]
    case_dir = _runtime_base(tmp_path) / "cases" / case_id
    case_path = case_dir / "case.json"
    fields_path = case_dir / "financial_fields.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["model_transfer_allowed"] = True
    case_path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = json.loads(fields_path.read_text(encoding="utf-8"))
    for row in fields:
        if row["field_kind"] == "accounts_receivable" and row["year"] == 2024:
            row["value"] = 700.0
        if row["field_kind"] == "accounts_receivable" and row["year"] == 2023:
            row["value"] = 450.0
    fields_path.write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(main_module, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(main_module, "_model_settings", lambda: ("test-key", "https://model.invalid", "test-model"))
    monkeypatch.setattr(
        main_module,
        "_run_knowledge_retrieval",
        lambda **_kwargs: (
            [{
                "retrieval_id": "KB-TEST",
                "source_id": "SRC-TEST",
                "document_id": "DOC-TEST",
                "source_category": "auditing_standard",
                "publisher": "test",
                "published_at": "2024-01-01",
                "official_url": "https://www.cicpa.org.cn/test",
                "locator": "第 1 页",
                "content_sha256": "a" * 64,
                "claim_scope": "procedure_guidance",
                "boundary": "仅支持程序依据",
                "snapshot_id": "SNAP-TEST",
            }],
            {"cutoff_date": "2026-08-24", "categories": {}},
            None,
        ),
    )

    def fake_agent_chain(**_kwargs):
        return [
            AgentStep(role=role, status="completed", detail="离线合成模型链通过", response_sha256=role)
            for role in ("challenge", "counter", "review")
        ]

    monkeypatch.setattr(main_module, "run_agent_chain", fake_agent_chain)
    response = TestClient(main_module.app).post(
        "/api/runs",
        json={"case_id": case_id, "current_year": 2024, "run_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_completeness"] == "complete_public_prescreen_with_gaps"
    assert body["context"]["analysis_cutoff_year"] == 2024
    assert body["context"]["prescreen_summary"]["missing_fields"]
    assert body["rule_results"][0]["status"] == "candidate"
    assert body["rule_results"][0]["risk_card"]["trend_limitation"]
    assert body["evidence_bundle"]["rag_evidence"]


def test_cninfo_field_confirmation_preserves_candidate_and_unlocks_r1(tmp_path: Path) -> None:
    """字段未逐项确认时阻断 R1；修正值另存且保留自动候选原值。"""

    pdfs = {2024: _pdf_bytes(2024, include_fields=True), 2023: _pdf_bytes(2023, include_fields=True)}
    task = create_task(
        tmp_path,
        {"company_query": "600302", "years": 2, "latest_year": 2024, "analysis_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    result = run_ingestion(tmp_path, task["task_id"], client=_FakeCNInfoClient(pdfs))
    case_id = result["case_id"]
    assert get_cninfo_field_readiness(tmp_path, case_id, ["R1"], 2024)

    for field_id in ("revenue_2024", "revenue_2023", "accounts_receivable_2023"):
        saved = confirm_cninfo_field(
            tmp_path,
            case_id,
            {"field_id": field_id, "decision": "confirm", "reviewer": "TEST-HUMAN-ROLE"},
        )
        assert saved["field"]["human_review"]["decision"] == "confirm"

    corrected = confirm_cninfo_field(
        tmp_path,
        case_id,
        {
            "field_id": "accounts_receivable_2024",
            "decision": "correct",
            "reviewer": "TEST-HUMAN-ROLE",
            "reason": "回查原件后按 PDF 第 3 页修正录入。",
            "corrected_value": 510.0,
            "corrected_pdf_page": 3,
        },
    )
    assert corrected["field"]["value"] == 510.0
    assert corrected["field"]["candidate"]["value"] == 500.0
    assert corrected["field"]["human_review"]["decision"] == "correct"
    assert get_cninfo_field_readiness(tmp_path, case_id, ["R1"], 2024) == []
