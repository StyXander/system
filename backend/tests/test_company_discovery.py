"""身份发现、匿名权限、来源时点及扩展案例的可复验回归。"""

from datetime import date, timedelta
import json
import time
from collections import OrderedDict

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import company_discovery as discovery
from backend.app import main
from backend.app.cninfo import CNInfoClient, CNInfoError, match_companies, normalize_company_query
from backend.app.schemas import CNInfoPipelineRequest


def companies():
    return [
        {"ticker": "000333", "company_name": "美的集团股份有限公司", "company_alias": "美的集团", "org_id": "gssz0000333", "market": "szse"},
        {"ticker": "600276", "company_name": "江苏恒瑞医药股份有限公司", "company_alias": "恒瑞医药", "org_id": "gssh0600276", "market": "sse"},
        {"ticker": "600000", "company_name": "上海浦东发展银行股份有限公司", "company_alias": "浦发银行", "org_id": "gssh0600000", "market": "sse"},
        {"ticker": "601398", "company_name": "中国工商银行股份有限公司", "company_alias": "工商银行", "org_id": "gssh0601398", "market": "sse"},
    ]


@pytest.mark.parametrize("query,expected", [("ＳＨ６００２７６", "600276"), ("600276.sh", "600276"), ("SZ 000333", "000333"), ("  美的集团  ", "美的集团"), ("00033", "00033"), ("920002.BJ", "920002")])
def test_normalization(query, expected):
    assert normalize_company_query(query) == expected


def test_wrong_market_rejected_before_discovery():
    with pytest.raises(CNInfoError, match="市场"):
        normalize_company_query("SZ600276")


def test_exact_name_precedes_fuzzy_and_ambiguity_is_preserved():
    assert match_companies(companies(), "美的集团")[0]["ticker"] == "000333"
    assert len(match_companies(companies(), "银行")) == 2
    assert match_companies(companies(), "不存在的企业") == []
    assert match_companies([{**companies()[0], "pinyin": "apl"}], "AAPL") == []
    with pytest.raises(CNInfoError):
        match_companies(companies(), "美")


def test_directory_one_request_for_all_markets():
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"stockList": [{"code": "600276", "zwjc": "恒瑞医药", "orgId": "gssh0600276"}, {"code": "000333", "zwjc": "美的集团", "orgId": "gssz0000333"}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as session:
        client = CNInfoClient(session, min_delay_seconds=0)
        assert client.resolve_company("恒瑞医药")["market"] == "sse"
    assert len(calls) == 1


def test_directory_cache_and_explicit_stale_failure(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(discovery, "_fetch_directory", lambda: calls.append(1) or companies())
    assert discovery.search(tmp_path, "美的集团")["directory"]["status"] == "official_live"
    assert discovery.search(tmp_path, "银行")["match_count"] == 2
    assert len(calls) == 1
    path = discovery._snapshot_path(tmp_path)
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["fetched_at_epoch"] = time.time() - 2 * discovery.DIRECTORY_TTL
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    def failure():
        raise CNInfoError("CNINFO_NETWORK_ERROR", "来源不可用")
    monkeypatch.setattr(discovery, "_fetch_directory", failure)
    response = discovery.search(tmp_path, "000333")
    assert response["directory"]["status"] == "stale_official_cache"
    assert response["requires_confirmation"]
    snapshot["fetched_at_epoch"] = time.time() - 8 * discovery.DIRECTORY_TTL
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(CNInfoError):
        discovery.search(tmp_path, "000333")


@pytest.mark.parametrize("snapshot", [[], {"fetched_at_epoch": "bad", "companies": []}, {"fetched_at_epoch": time.time(), "companies": [{"name": "bad"}]}])
def test_corrupt_directory_recovers_from_official_source(tmp_path, monkeypatch, snapshot):
    path = discovery._snapshot_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(discovery, "_fetch_directory", companies)
    assert discovery.search(tmp_path, "000333")["directory"]["status"] == "official_live"


def test_seed_subset_never_resolves_fuzzy_identity():
    assert main._find_demo_seed_case("美的集团")["ticker"] == "000333"
    assert main._find_demo_seed_case("SZ000333")["ticker"] == "000333"
    assert main._find_demo_seed_case("美的") is None


def test_directory_failure_backoff_does_not_repeat_network(tmp_path, monkeypatch):
    calls = []
    def failure():
        calls.append(1)
        raise CNInfoError("CNINFO_NETWORK_ERROR", "来源不可用")
    monkeypatch.setattr(discovery, "_fetch_directory", failure)
    monkeypatch.setattr(discovery, "_directory_failures", OrderedDict())
    clock = [100.0]
    monkeypatch.setattr(discovery.time, "monotonic", lambda: clock[0])
    for _ in range(2):
        with pytest.raises(CNInfoError):
            discovery.directory(tmp_path)
    assert len(calls) == 1
    clock[0] += 60
    with pytest.raises(CNInfoError):
        discovery.directory(tmp_path)
    assert len(calls) == 2


def test_directory_busy_is_bounded_instead_of_waiting_forever(tmp_path):
    discovery._directory_lock.acquire()
    try:
        with pytest.raises(CNInfoError) as error:
            discovery.directory(tmp_path)
        assert error.value.code == "DISCOVERY_BUSY"
    finally:
        discovery._directory_lock.release()


def test_production_expanded_preview_cannot_start_import_or_model(monkeypatch):
    """生产持久化模式也开放快照预检，不能借参数扩大为付费链或新企业导入。"""
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setattr(main, "supabase_enabled", lambda: True)
    monkeypatch.setattr(discovery, "enforce_discovery_quota", lambda _: None)
    observed = []
    class Result:
        run_id = "RUN-TEST-PREVIEW"
        def model_dump(self, **kwargs):
            return {"run_id": self.run_id, "model_check": {"provider_call_count": 0}}
    monkeypatch.setattr(main, "run_rules", lambda request, _: observed.append(request) or Result())
    def forbidden(*args, **kwargs):
        raise AssertionError("预检不得创建接入任务或要求登录")
    monkeypatch.setattr(main, "create_task", forbidden)
    monkeypatch.setattr(main, "require_authenticated", forbidden)
    with TestClient(main.app) as client:
        result = client.post("/api/demo/expanded-cases/000333/preview", json={"run_mode": "full_analysis", "latest_year": 2099})
        assert result.status_code == 200
        assert result.json()["persistence"]["resume_supported"] is False
        assert client.post("/api/demo/expanded-cases/920106/preview").status_code == 404
    assert len(observed) == 1 and observed[0].run_mode == "calculation_only"
    assert observed[0].current_year == 2025


def test_cutoff_uses_china_day_instead_of_server_day(monkeypatch):
    from backend.app import cninfo
    monkeypatch.setattr(cninfo, "china_today", lambda: date(2026, 10, 9))
    assert CNInfoPipelineRequest(company_query="000333", source_cutoff_date="2026-10-09")
    with pytest.raises(ValueError):
        CNInfoPipelineRequest(company_query="000333", source_cutoff_date="2026-10-10")


def test_report_selection_respects_cutoff():
    rows = [{"report_year": 2024, "announcement_date": day, "source_url": f"https://static.cninfo.com.cn/{index}.PDF", "announcement_id": str(index)} for index, day in enumerate(("2025-04-30", "2025-07-01"))]
    with CNInfoClient(min_delay_seconds=0) as client:
        selected = client.select_annual_report(rows, 2024, source_cutoff_date="2025-05-01")
        assert selected["announcement_date"] == "2025-04-30"
        with pytest.raises(CNInfoError) as captured:
            client.select_annual_report(rows, 2024, source_cutoff_date="2025-01-01")
        assert captured.value.code == "ANNUAL_REPORT_AFTER_CUTOFF"


def test_announcement_search_highlight_and_meeting_are_not_full_reports():
    company = {**companies()[1]}
    base = {"secCode": "600276", "announcementTime": "2026-04-30", "adjunctUrl": "finalpage/2026-04-30/test.PDF"}
    with CNInfoClient(min_delay_seconds=0) as client:
        assert client._normalize_announcement({**base, "announcementTitle": "<em>2025年</em><em>年度报告</em>"}, company, 2025)["announcement_title"] == "2025年年度报告"
        assert client._normalize_announcement({**base, "announcementTitle": "2025年年度报告业绩说明会预告公告"}, company, 2025) is None
        assert client._normalize_announcement({**base, "announcementTitle": "2025年年度报告", "secCode": "000333"}, company, 2025) is None


def test_future_cutoff_rejected_and_code_normalized():
    assert CNInfoPipelineRequest(company_query="600276.SH").company_query == "600276"
    with pytest.raises(ValueError):
        CNInfoPipelineRequest(company_query="600276", source_cutoff_date=date.today() + timedelta(days=1))
    with pytest.raises(ValueError):
        CNInfoPipelineRequest(company_query="SZ600276")
    with pytest.raises(ValueError):
        CNInfoPipelineRequest(company_query="  ")


def test_anonymous_search_does_not_require_auth_or_create_task(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setattr(main, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(discovery, "_fetch_directory", companies)
    monkeypatch.setattr(discovery, "enforce_discovery_quota", lambda _: None)
    def forbidden(*args, **kwargs):
        raise AssertionError("搜索不得下载、建库或执行鉴权任务")
    monkeypatch.setattr(main, "require_authenticated", forbidden)
    monkeypatch.setattr(main, "create_task", forbidden)
    with TestClient(main.app) as client:
        response = client.get("/api/companies/search", params={"q": "银行"})
        assert response.status_code == 200
        assert response.json()["match_count"] == 2
        assert response.json()["ai_generated_content_notice"] == "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"


def test_unavailable_source_not_reported_as_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(discovery, "enforce_discovery_quota", lambda _: None)
    def failure():
        raise CNInfoError("CNINFO_NETWORK_ERROR", "官方来源当前不可用")
    monkeypatch.setattr(discovery, "_fetch_directory", failure)
    with TestClient(main.app) as client:
        response = client.get("/api/companies/search?q=600276")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "CNINFO_NETWORK_ERROR"


def test_anonymous_quota_expires_and_releases_window(monkeypatch):
    """限流应阻断超量请求，但窗口到期后可恢复，不能永久锁住访客。"""
    monkeypatch.setattr(discovery, "_request_windows", OrderedDict())
    clock = [100.0]
    monkeypatch.setattr(discovery.time, "monotonic", lambda: clock[0])
    for _ in range(30):
        discovery.enforce_discovery_quota("192.0.2.1")
    with pytest.raises(CNInfoError) as captured:
        discovery.enforce_discovery_quota("192.0.2.1")
    assert captured.value.code == "DISCOVERY_RATE_LIMITED"
    clock[0] += 60
    discovery.enforce_discovery_quota("192.0.2.1")


def test_anonymous_new_company_import_still_blocked(monkeypatch):
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setattr(main, "supabase_enabled", lambda: False)
    monkeypatch.setattr(main, "_find_demo_seed_case", lambda _: None)
    with TestClient(main.app) as client:
        response = client.post("/api/pipelines/cninfo", json={"company_query": "600999"})
    assert response.status_code == 403


def test_extended_cases_have_real_documents_and_no_fabricated_signoff():
    cases = discovery.expanded_cases(main.WORKSPACE_ROOT)
    assert len(cases) == 8
    assert len({case["ticker"] for case in cases}) == 8
    assert all(case["document_count"] >= 3 and case["field_count"] > 0 for case in cases)
    assert all(case["professional_review"] == "pending" for case in cases)


def test_random_retrieval_identifier_cannot_be_misread_as_phone_but_excerpt_still_blocks():
    """复现基线失败：服务端检索编号含手机号形状时不误报，原文联系方式仍拦截。"""
    row = {"evidence_id": "E1", "retrieval_id": "RET-DEMO-13800138000A", "excerpt": "必要公开原文"}
    def scan(item):
        return main.scan_sensitive_payload(main._model_privacy_scan_payload({"rag_evidence": [item]}, context={}, rule_results=[]))
    assert scan(row) == []
    assert scan({**row, "excerpt": "联系人13800138000"})[0]["kind"] == "中国大陆手机号"
    assert scan({**row, "retrieval_id": "联系人13800138000"})[0]["kind"] == "中国大陆手机号"
