"""公开身份发现与年报元数据：不下载 PDF、不建库、不调用模型。

目录缓存采用官方快照，过期且来源失败时明确返回降级状态。
检索结果只表示身份候选，不表示年报字段完整或专业复核通过。
匿名发现与付费分析保持不同入口，沿用分析任务原有权限闸门。
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import OrderedDict, deque
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .cninfo import CNInfoClient, CNInfoError, STOCK_LIST_URLS, _market_for_code, _column_and_plate, match_companies, normalize_company_query
from .seed_catalog import load_seed_cases

DIRECTORY_TTL = 86400
EXPANDED_TICKERS = ("600276", "000333", "600588", "300015", "601668", "000002", "601398", "688111")
_directory_lock = threading.Lock()
_directory_failures: OrderedDict[str, tuple[float, str, str]] = OrderedDict()
_rate_lock = threading.Lock()
_request_windows: OrderedDict[str, deque[float]] = OrderedDict()
_network_slots = threading.BoundedSemaphore(2)
_report_lock = threading.Lock()
_report_cache: OrderedDict[tuple[str, int, str], tuple[float, dict[str, Any]]] = OrderedDict()
_report_failures: OrderedDict[tuple[str, int, str], tuple[float, str, str]] = OrderedDict()
_report_inflight: set[tuple[str, int, str]] = set()


def enforce_discovery_quota(identity: str) -> None:
    """单进程限流与有界身份台账，避免匿名检索占用无限网络与内存。"""

    now = time.monotonic()
    with _rate_lock:
        for key, limit in (("__global__", 180), ("ip:" + identity, 30)):
            window = _request_windows.setdefault(key, deque())
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= limit:
                raise CNInfoError("DISCOVERY_RATE_LIMITED", "企业查询过于频繁，请一分钟后再试。")
        for key in ("__global__", "ip:" + identity):
            _request_windows[key].append(now)
            _request_windows.move_to_end(key)
        while len(_request_windows) > 2048:
            _request_windows.popitem(last=False)


def _client() -> CNInfoClient:
    """发现入口采用短超时和零重试，重型解析由独立任务处理。"""

    session = httpx.Client(timeout=httpx.Timeout(8, connect=4), trust_env=False, follow_redirects=True, headers={"User-Agent": "AuditTrace/0.8", "Accept": "application/json,text/plain,*/*", "X-Requested-With": "XMLHttpRequest", "Origin": "https://www.cninfo.com.cn", "Referer": "https://www.cninfo.com.cn/new/index"})
    return CNInfoClient(client=session, min_delay_seconds=0, max_retries=0)


def _fetch_directory() -> list[dict[str, Any]]:
    client = _client()
    try:
        client.set_operation_deadline(12)
        return client.stock_directory()
    finally:
        client.client.close()


def _snapshot_path(root: Path) -> Path:
    namespace = re.sub(r"[^a-zA-Z0-9_-]", "_", os.getenv("AUDITTRACE_RUNTIME_NAMESPACE", "default"))[:80]
    return root / "backend" / "runtime" / namespace / "company_discovery" / "directory.json"


@contextmanager
def _directory_refresh_guard():
    """官方来源慢或失败时不让全部请求无限排队占满服务线程。"""
    if not _directory_lock.acquire(timeout=1):
        raise CNInfoError("DISCOVERY_BUSY", "官方企业目录正在更新，请稍后再试。")
    try:
        yield
    finally:
        _directory_lock.release()


def directory(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """串行刷新目录，原子保存官方清单；过期快照最多降级使用七天。"""

    path = _snapshot_path(root)
    with _directory_refresh_guard():
        snapshot: dict[str, Any] = {}
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        # 损坏或旧格式缓存不能把公开入口变成500，重新从官方目录恢复。
        try:
            if not isinstance(snapshot, dict):
                raise ValueError("invalid snapshot")
            epoch = float(snapshot.get("fetched_at_epoch") or 0)
            rows = snapshot.get("companies") or []
            if not isinstance(rows, list) or any(not isinstance(row, dict) or not re.fullmatch(r"\d{6}", str(row.get("ticker") or "")) for row in rows):
                raise ValueError("invalid companies")
            if not 0 < epoch <= time.time() + 60:
                raise ValueError("invalid timestamp")
            age = max(0, time.time() - epoch)
        except (ValueError, TypeError):
            snapshot, rows, age = {}, [], 7 * DIRECTORY_TTL
        # 市场标签是代码派生字段，升级后修正旧缓存中的920北交所标签。
        for company in rows:
            company["market"] = _market_for_code(company["ticker"])
            company["column"], company["plate"] = _column_and_plate(company["market"])
        if rows and age < DIRECTORY_TTL:
            return rows, {"status": "official_cache", "fetched_at": snapshot.get("fetched_at"), "age_seconds": round(age), "source_url": STOCK_LIST_URLS["szse"]}
        try:
            recent_failure = _directory_failures.get(str(path))
            if recent_failure and time.monotonic() < recent_failure[0]:
                raise CNInfoError(recent_failure[1], recent_failure[2])
            companies = _fetch_directory()
        except CNInfoError as error:
            # 失败退避固定六十秒，不因后续失败请求滑动延长；台账有界。
            if not recent_failure or time.monotonic() >= recent_failure[0]:
                _directory_failures[str(path)] = (time.monotonic() + 60, error.code, error.message)
                _directory_failures.move_to_end(str(path))
                while len(_directory_failures) > 32:
                    _directory_failures.popitem(last=False)
            if rows and age < 7 * DIRECTORY_TTL:
                return rows, {"status": "stale_official_cache", "fetched_at": snapshot.get("fetched_at"), "age_seconds": round(age), "source_url": STOCK_LIST_URLS["szse"], "failure_code": error.code, "boundary": "官方来源当前不可用，正在使用过期身份清单；年报可用性需重新核验。"}
            raise
        _directory_failures.pop(str(path), None)
        snapshot = {"fetched_at_epoch": time.time(), "fetched_at": datetime.now(timezone.utc).isoformat(), "companies": companies}
        persistence = "saved"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            persistence = "unavailable"
        return companies, {"status": "official_live", "cache_persistence": persistence, "fetched_at": snapshot["fetched_at"], "age_seconds": 0, "source_url": STOCK_LIST_URLS["szse"]}


def search(root: Path, query: str) -> dict[str, Any]:
    """每次最多展示二十个候选，模糊结果必须由用户点击确认。"""

    normalized = normalize_company_query(query)
    # 无效短输入在网络请求之前拒绝，不浪费官方目录请求。
    match_companies([], normalized)
    rows, provenance = directory(root)
    matches = match_companies(rows, normalized)
    seed_ids = {case["ticker"]: case["case_id"] for case in load_seed_cases(root)}
    candidates = [{**company, "seed_case_id": seed_ids.get(company["ticker"])} for company in matches[:20]]
    return {"query": query, "normalized_query": normalized, "status": "candidates" if candidates else "not_found", "match_count": len(matches), "truncated": len(matches) > 20, "requires_confirmation": bool(candidates), "candidates": candidates, "directory": provenance, "boundary": "查询范围为巨潮沪深北股票目录；非上市、境外企业和历史名称可能不在目录内。身份命中不代表资料或分析已就绪。"}


def annual_reports(root: Path, ticker: str, year: int, cutoff: date) -> dict[str, Any]:
    """查询一个年度的官方全文候选，截止日之外的修订件不得入选。"""

    normalized = normalize_company_query(ticker)
    if not re.fullmatch(r"\d{6}", normalized):
        raise CNInfoError("COMPANY_CODE_INVALID", "请先确认六位股票代码。")
    rows, provenance = directory(root)
    matches = match_companies(rows, normalized)
    if len(matches) != 1:
        raise CNInfoError("COMPANY_NOT_FOUND", "官方目录中未找到该股票代码。")
    key = (normalized, year, cutoff.isoformat())
    with _report_lock:
        cached = _report_cache.get(key)
        if cached and time.monotonic() - cached[0] < 600:
            return {**cached[1], "metadata_cache": "hit"}
        failure = _report_failures.get(key)
        if failure and time.monotonic() < failure[0]:
            raise CNInfoError(failure[1], failure[2] + " 同条件失败查询短暂冷却，请20秒后再试。")
        if key in _report_inflight:
            raise CNInfoError("DISCOVERY_BUSY", "相同企业、年度和截止日的公告正在查询，请稍后重试。")
        # 同条件并发不重复访问官方来源；失败也必须在finally释放标记。
        _report_inflight.add(key)
    client = None
    acquired = False
    try:
        acquired = _network_slots.acquire(blocking=False)
        if not acquired:
            raise CNInfoError("DISCOVERY_BUSY", "官方公告查询繁忙，请稍后重试。")
        client = _client()
        client.set_operation_deadline(18)
        candidates, query_status = client.search_annual_reports_detailed(matches[0], year)
        eligible = [item for item in candidates if item.get("announcement_date") and item["announcement_date"] <= cutoff.isoformat()]
        selected = None
        if eligible:
            selected = client.select_annual_report(eligible, year, query_status=query_status, source_cutoff_date=cutoff.isoformat())
        # 原始公告体无需出现在公开接口；PDF 仅提供官方链接，不在此下载。
        public = lambda item: {key: value for key, value in item.items() if key != "raw"}
        result = {"company": matches[0], "report_year": year, "source_cutoff_date": cutoff.isoformat(), "status": "available_partial" if selected and query_status.get("truncated") else "available" if selected else "query_incomplete" if query_status.get("truncated") else "not_found_before_cutoff", "candidates": [public(item) for item in eligible], "selected": public(selected) if selected else None, "excluded_after_cutoff_or_undated": len(candidates) - len(eligible), "query_status": query_status, "directory": provenance, "fetched_at": datetime.now(timezone.utc).isoformat(), "metadata_cache": "miss", "boundary": "仅完成官方公告元数据查询；尚未下载或校验 PDF 正文，也未执行模型分析。"}
        with _report_lock:
            _report_cache[key] = (time.monotonic(), result)
            _report_cache.move_to_end(key)
            while len(_report_cache) > 128:
                _report_cache.popitem(last=False)
        return result
    except CNInfoError as error:
        if error.code != "DISCOVERY_BUSY":
            with _report_lock:
                _report_failures[key] = (time.monotonic() + 20, error.code, error.message)
                _report_failures.move_to_end(key)
                while len(_report_failures) > 128:
                    _report_failures.popitem(last=False)
        raise
    finally:
        if client is not None:
            client.client.close()
        if acquired:
            _network_slots.release()
        with _report_lock:
            _report_inflight.discard(key)


def expanded_cases(root: Path) -> list[dict[str, Any]]:
    """扩展工程样例来自已有公开快照，不能冒充新的冻结或真人签字案例。"""

    seeds = {case["ticker"]: case for case in load_seed_cases(root)}
    result = []
    for ticker in EXPANDED_TICKERS:
        case = seeds.get(ticker)
        if case:
            years = sorted({int(document["report_year"]) for document in case.get("documents", []) if str(document.get("report_year") or "").isdigit()}, reverse=True)
            result.append({"ticker": ticker, "case_id": case["case_id"], "company_name": case.get("company_alias") or case.get("company_name"), "report_years": years, "document_count": len(case.get("documents") or []), "field_count": len(case.get("financial_fields") or []), "professional_review": "pending", "source_mode": "registered_public_snapshot", "boundary": "扩展体验案例，未计入原15案专业冻结清单。"})
    return result
