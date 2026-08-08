"""公开年报缓存目录。

SQLite 只保存可查询的元数据、结构化字段、证据定位和版本指纹；PDF 与
FAISS/RAG 文件仍保存在现有案例目录中，避免把大型二进制塞进数据库。
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


CATALOG_SCHEMA_VERSION = "catalog_v1"
CATALOG_DB_NAME = "catalog.sqlite3"
DEFAULT_CACHE_MAX_AGE_DAYS = 365
DEFAULT_REFRESH_STALL_SECONDS = 300


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _duration_seconds(started_at: str | None, finished_at: str | None) -> int | None:
    """Return a stable, human-readable job duration from catalog timestamps."""

    if not started_at or not finished_at:
        return None
    try:
        started = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%S%z")
        finished = datetime.strptime(finished_at, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    return max(0, int((finished - started).total_seconds()))


def _cache_max_age_days() -> int:
    try:
        configured = int(os.environ.get("AUDITTRACE_CACHE_MAX_AGE_DAYS", DEFAULT_CACHE_MAX_AGE_DAYS))
    except ValueError:
        configured = DEFAULT_CACHE_MAX_AGE_DAYS
    return max(1, min(configured, 3650))


def _cache_age_days(verified_at: str | None) -> int | None:
    if not verified_at:
        return None
    try:
        verified = datetime.strptime(verified_at, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    now = datetime.now(verified.tzinfo)
    return max(0, int((now - verified).total_seconds() // 86400))


def _cache_state(verified_at: str | None) -> str:
    age_days = _cache_age_days(verified_at)
    if age_days is None:
        return "stale"
    return "stale" if age_days > _cache_max_age_days() else "ready"


def _refresh_stall_seconds() -> int:
    try:
        configured = int(os.environ.get("AUDITTRACE_REFRESH_STALL_SECONDS", DEFAULT_REFRESH_STALL_SECONDS))
    except ValueError:
        configured = DEFAULT_REFRESH_STALL_SECONDS
    return max(30, min(configured, 86400))


def _runtime_dir(workspace_root: Path) -> Path:
    namespace = re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ.get("AUDITTRACE_RUNTIME_NAMESPACE", ""))
    base = workspace_root / "backend" / "runtime"
    return base / namespace if namespace else base


def catalog_path(workspace_root: Path) -> Path:
    path = _runtime_dir(workspace_root) / CATALOG_DB_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect_catalog(workspace_root: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(catalog_path(workspace_root), timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    initialize_catalog(connection)
    return connection


def initialize_catalog(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS companies (
            ticker TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            company_alias TEXT NOT NULL,
            market TEXT NOT NULL,
            registry_mode TEXT,
            industry_family TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS report_documents (
            document_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            report_year INTEGER NOT NULL,
            disclosure_date TEXT,
            announcement_title TEXT,
            source_url TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            byte_count INTEGER,
            page_count INTEGER,
            storage_relpath TEXT,
            content_store_relpath TEXT,
            validation_status TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(ticker, report_year, sha256)
        );
        CREATE TABLE IF NOT EXISTS source_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            source_fingerprint TEXT NOT NULL,
            report_years_json TEXT NOT NULL,
            cache_status TEXT NOT NULL,
            rag_index_version TEXT,
            extractor_version TEXT,
            verified_at TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(case_id, source_fingerprint)
        );
        CREATE TABLE IF NOT EXISTS financial_facts (
            fact_key TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            field_id TEXT,
            field_kind TEXT NOT NULL,
            year INTEGER NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            field_basis TEXT,
            document_id TEXT,
            pdf_page INTEGER,
            locator TEXT,
            evidence_id TEXT,
            extractor_version TEXT,
            review_status TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(snapshot_id, field_kind, year)
        );
        CREATE TABLE IF NOT EXISTS fact_evidence (
            evidence_id TEXT PRIMARY KEY,
            fact_key TEXT NOT NULL,
            raw_excerpt TEXT,
            file_sha256 TEXT,
            document_id TEXT,
            pdf_page INTEGER,
            locator TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rag_manifests (
            case_id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            index_version TEXT,
            source_fingerprint TEXT,
            chunk_count INTEGER,
            status TEXT,
            built_at TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS industry_gate_results (
            gate_key TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            snapshot_id TEXT,
            gate_version TEXT NOT NULL,
            fit_level TEXT NOT NULL,
            industry_family TEXT NOT NULL,
            reporting_profile TEXT NOT NULL,
            allowed_rules_json TEXT NOT NULL,
            blocked_rules_json TEXT NOT NULL,
            reason_codes_json TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            evaluated_at TEXT NOT NULL,
            UNIQUE(case_id, snapshot_id, gate_version)
        );
        CREATE TABLE IF NOT EXISTS cache_refresh_jobs (
            job_id TEXT PRIMARY KEY,
            batch_id TEXT,
            task_id TEXT,
            ticker TEXT NOT NULL,
            requested_years_json TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_documents_ticker_year ON report_documents(ticker, report_year);
        CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_status ON source_snapshots(ticker, cache_status);
        CREATE INDEX IF NOT EXISTS idx_facts_snapshot ON financial_facts(snapshot_id);
        """
    )
    # 目录已经可能由 V1 创建；只增加列，不重建或删除已有缓存。
    columns = {row[1] for row in connection.execute("PRAGMA table_info(cache_refresh_jobs)").fetchall()}
    if "batch_id" not in columns:
        connection.execute("ALTER TABLE cache_refresh_jobs ADD COLUMN batch_id TEXT")
    if "task_id" not in columns:
        connection.execute("ALTER TABLE cache_refresh_jobs ADD COLUMN task_id TEXT")
    snapshot_columns = {row[1] for row in connection.execute("PRAGMA table_info(source_snapshots)").fetchall()}
    if "verified_at" not in snapshot_columns:
        connection.execute("ALTER TABLE source_snapshots ADD COLUMN verified_at TEXT")
    connection.execute(
        "UPDATE source_snapshots SET verified_at=updated_at WHERE verified_at IS NULL OR verified_at=''"
    )
    document_columns = {row[1] for row in connection.execute("PRAGMA table_info(report_documents)").fetchall()}
    if "content_store_relpath" not in document_columns:
        connection.execute("ALTER TABLE report_documents ADD COLUMN content_store_relpath TEXT")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_refresh_jobs_batch ON cache_refresh_jobs(batch_id, created_at)")
    connection.execute(
        "INSERT INTO catalog_meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        ("schema_version", CATALOG_SCHEMA_VERSION),
    )
    connection.commit()


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False, sort_keys=True)


def sync_case_to_catalog(
    workspace_root: Path,
    case: dict[str, Any],
    *,
    rows: Iterable[dict[str, Any]] | None = None,
    rag_manifest: dict[str, Any] | None = None,
    industry_gate: dict[str, Any] | None = None,
    extractor_version: str = "field_extraction_v1",
    refresh_verified_at: bool = True,
) -> dict[str, Any]:
    """把一个已登记案例写入缓存目录，保留 PDF/RAG 文件的原有位置。"""

    case_id = str(case.get("case_id") or "")
    ticker = str(case.get("ticker") or "")
    snapshot_id = str(case.get("source_snapshot_id") or case_id)
    if not case_id or not ticker:
        raise ValueError("缓存目录同步需要案例编号和证券代码。")
    documents = list(case.get("documents") or [])
    rows = list(rows or [])
    rag_manifest = rag_manifest or {}
    updated_at = _now()
    report_years = sorted({int(item["report_year"]) for item in documents}, reverse=True)
    rag_status = str(rag_manifest.get("status") or "not_ready")
    cache_status = "ready" if documents and rag_status == "ready" else "registered"
    source_fingerprint = str(rag_manifest.get("source_fingerprint") or snapshot_id)
    with connect_catalog(workspace_root) as connection:
        connection.execute(
            """
            INSERT INTO companies(ticker, company_name, company_alias, market, registry_mode, industry_family, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET company_name=excluded.company_name,
              company_alias=excluded.company_alias, market=excluded.market,
              registry_mode=excluded.registry_mode,
              industry_family=COALESCE(excluded.industry_family, companies.industry_family),
              updated_at=excluded.updated_at
            """,
            (
                ticker,
                str(case.get("company_name") or ""),
                str(case.get("company_alias") or ""),
                str(case.get("market") or ""),
                str(case.get("registry_mode") or ""),
                (industry_gate or {}).get("industry_family"),
                updated_at,
            ),
        )
        for document in documents:
            connection.execute(
                """
                INSERT INTO report_documents(document_id, case_id, ticker, report_year, disclosure_date,
                  announcement_title, source_url, sha256, byte_count, page_count, storage_relpath,
                  content_store_relpath, validation_status, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET case_id=excluded.case_id,
                  report_year=excluded.report_year, disclosure_date=excluded.disclosure_date,
                  announcement_title=excluded.announcement_title, source_url=excluded.source_url,
                  sha256=excluded.sha256, byte_count=excluded.byte_count, page_count=excluded.page_count,
                  storage_relpath=excluded.storage_relpath, content_store_relpath=excluded.content_store_relpath,
                  validation_status=excluded.validation_status,
                  updated_at=excluded.updated_at
                """,
                (
                    document.get("document_id"), case_id, ticker, int(document["report_year"]),
                    document.get("disclosure_date"), document.get("announcement_title"),
                    document.get("source_url"), document.get("sha256") or document.get("file_sha256"),
                    document.get("byte_count"), document.get("page_count"), document.get("storage_relpath"),
                    document.get("content_store_relpath"), document.get("validation_status"), updated_at,
                ),
            )
        connection.execute(
            """
            INSERT INTO source_snapshots(snapshot_id, case_id, ticker, source_fingerprint, report_years_json,
              cache_status, rag_index_version, extractor_version, verified_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET case_id=excluded.case_id,
              source_fingerprint=excluded.source_fingerprint, report_years_json=excluded.report_years_json,
              cache_status=excluded.cache_status, rag_index_version=excluded.rag_index_version,
              extractor_version=excluded.extractor_version,
              verified_at=CASE WHEN ? THEN excluded.verified_at ELSE source_snapshots.verified_at END,
              updated_at=excluded.updated_at
            """,
            (snapshot_id, case_id, ticker, source_fingerprint, _json(report_years), cache_status,
             rag_manifest.get("index_version"), extractor_version,
             updated_at if refresh_verified_at else None, updated_at, refresh_verified_at),
        )
        for row in rows:
            field_id = str(row.get("field_id") or f"{row.get('field_kind')}_{row.get('year')}")
            fact_key = f"{snapshot_id}:{field_id}"
            connection.execute(
                """
                INSERT INTO financial_facts(fact_key, snapshot_id, case_id, field_id, field_kind, year, value,
                  unit, field_basis, document_id, pdf_page, locator, evidence_id, extractor_version,
                  review_status, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_key) DO UPDATE SET value=excluded.value, unit=excluded.unit,
                  field_basis=excluded.field_basis, document_id=excluded.document_id, pdf_page=excluded.pdf_page,
                  locator=excluded.locator, evidence_id=excluded.evidence_id, extractor_version=excluded.extractor_version,
                  review_status=excluded.review_status, updated_at=excluded.updated_at
                """,
                (fact_key, snapshot_id, case_id, field_id, row.get("field_kind"), int(row["year"]),
                 float(row["value"]), row.get("unit"), row.get("field_basis"), row.get("document_id"),
                 row.get("pdf_page"), row.get("locator"), row.get("evidence_id"), extractor_version,
                 row.get("source_review_status"), updated_at),
            )
            if row.get("evidence_id"):
                connection.execute(
                    """
                    INSERT INTO fact_evidence(evidence_id, fact_key, raw_excerpt, file_sha256, document_id,
                      pdf_page, locator, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(evidence_id) DO UPDATE SET fact_key=excluded.fact_key,
                      raw_excerpt=excluded.raw_excerpt, file_sha256=excluded.file_sha256,
                      document_id=excluded.document_id, pdf_page=excluded.pdf_page,
                      locator=excluded.locator, updated_at=excluded.updated_at
                    """,
                    (row["evidence_id"], fact_key, row.get("raw_excerpt"), row.get("file_sha256"),
                     row.get("document_id"), row.get("pdf_page"), row.get("locator"), updated_at),
                )
        if rag_manifest:
            connection.execute(
                """
                INSERT INTO rag_manifests(case_id, snapshot_id, index_version, source_fingerprint,
                  chunk_count, status, built_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET snapshot_id=excluded.snapshot_id,
                  index_version=excluded.index_version, source_fingerprint=excluded.source_fingerprint,
                  chunk_count=excluded.chunk_count, status=excluded.status, built_at=excluded.built_at,
                  updated_at=excluded.updated_at
                """,
                (case_id, snapshot_id, rag_manifest.get("index_version"), source_fingerprint,
                 rag_manifest.get("chunk_count"), rag_status, rag_manifest.get("built_at"), updated_at),
            )
        if industry_gate:
            gate_key = f"{case_id}:{snapshot_id}:{industry_gate.get('gate_version')}"
            connection.execute(
                """
                INSERT INTO industry_gate_results(gate_key, case_id, snapshot_id, gate_version, fit_level,
                  industry_family, reporting_profile, allowed_rules_json, blocked_rules_json,
                  reason_codes_json, evidence_json, evaluated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(gate_key) DO UPDATE SET fit_level=excluded.fit_level,
                  industry_family=excluded.industry_family, reporting_profile=excluded.reporting_profile,
                  allowed_rules_json=excluded.allowed_rules_json, blocked_rules_json=excluded.blocked_rules_json,
                  reason_codes_json=excluded.reason_codes_json, evidence_json=excluded.evidence_json,
                  evaluated_at=excluded.evaluated_at
                """,
                (gate_key, case_id, snapshot_id, industry_gate.get("gate_version"), industry_gate.get("fit_level"),
                 industry_gate.get("industry_family"), industry_gate.get("reporting_profile"),
                 _json(industry_gate.get("allowed_rules")), _json(industry_gate.get("blocked_rules")),
                 _json(industry_gate.get("reason_codes")), _json(industry_gate.get("evidence")), updated_at),
            )
        connection.commit()
    return {
        "hit": False,
        "cache_status": cache_status,
        "case_id": case_id,
        "ticker": ticker,
        "snapshot_id": snapshot_id,
        "source_fingerprint": source_fingerprint,
        "report_years": report_years,
        "rag_index_version": rag_manifest.get("index_version"),
    }


def lookup_cached_case(
    workspace_root: Path,
    company_query: str,
    requested_years: Iterable[int],
    *,
    include_stale: bool = False,
) -> dict[str, Any] | None:
    """按代码或企业名称查找可直接复用的完整来源快照。"""

    query = str(company_query or "").strip().lower()
    normalized_query = re.sub(r"[\s（）()【】\[\]·,，。\-—_]", "", query)
    required_years = {int(year) for year in requested_years}
    if not normalized_query or not required_years:
        return None
    with connect_catalog(workspace_root) as connection:
        rows = connection.execute(
            """
            SELECT c.*, s.snapshot_id, s.case_id, s.source_fingerprint, s.report_years_json,
              s.rag_index_version, s.extractor_version, s.verified_at, s.updated_at AS snapshot_updated_at
            FROM companies c JOIN source_snapshots s ON s.ticker=c.ticker
            WHERE s.cache_status='ready' ORDER BY s.updated_at DESC
            """
        ).fetchall()
        stale_match: dict[str, Any] | None = None
        for row in rows:
            names = {
                str(row["ticker"] or "").lower(),
                re.sub(r"[\s（）()【】\[\]·,，。\-—_]", "", str(row["company_name"] or "").lower()),
                re.sub(r"[\s（）()【】\[\]·,，。\-—_]", "", str(row["company_alias"] or "").lower()),
            }
            if not any(normalized_query == value or (value and normalized_query in value) for value in names):
                continue
            report_years = set(json.loads(row["report_years_json"] or "[]"))
            if not required_years.issubset(report_years):
                continue
            verified_at = row["verified_at"] or row["snapshot_updated_at"]
            match = {
                "case_id": row["case_id"],
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "company_alias": row["company_alias"],
                "market": row["market"],
                "snapshot_id": row["snapshot_id"],
                "source_fingerprint": row["source_fingerprint"],
                "report_years": sorted(report_years, reverse=True),
                "rag_index_version": row["rag_index_version"],
                "extractor_version": row["extractor_version"],
                "cache_state": _cache_state(verified_at),
                "verified_at": verified_at,
                "cache_age_days": _cache_age_days(verified_at),
                "cache_max_age_days": _cache_max_age_days(),
            }
            if match["cache_state"] == "ready":
                return match
            if include_stale and stale_match is None:
                stale_match = match
        return stale_match
    return None


def resolve_analysis_source(
    workspace_root: Path,
    company_query: str,
    requested_years: Iterable[int],
    *,
    cache_policy: str = "prefer_cache",
) -> dict[str, Any]:
    """统一返回热缓存解析结果，供实时流程和目录接口共用。"""

    normalized_policy = str(cache_policy or "prefer_cache")
    if normalized_policy == "force_refresh":
        return {
            "hit": False,
            "policy": normalized_policy,
            "reason": "force_refresh_requested",
            "match": None,
        }
    if normalized_policy == "prefer_cache":
        match = lookup_cached_case(workspace_root, company_query, requested_years, include_stale=True)
        reason = "stale_snapshot_fallback" if match and match.get("cache_state") == "stale" else "ready_snapshot_found"
        return {
            "hit": bool(match),
            "policy": normalized_policy,
            "reason": reason if match else "snapshot_not_found_or_incomplete",
            "match": match,
        }
    match = lookup_cached_case(workspace_root, company_query, requested_years, include_stale=False)
    stale_match = lookup_cached_case(workspace_root, company_query, requested_years, include_stale=True)
    return {
        "hit": bool(match),
        "policy": normalized_policy,
        "reason": "ready_snapshot_found" if match else "snapshot_not_found_or_incomplete",
        "match": match,
        "stale_match": stale_match if not match and stale_match and stale_match.get("cache_state") == "stale" else None,
    }


def create_refresh_job(
    workspace_root: Path,
    *,
    job_id: str,
    batch_id: str,
    task_id: str,
    ticker: str,
    requested_years: Iterable[int],
) -> dict[str, Any]:
    """登记一家公司预热作业，供批量报告读取。"""

    now = _now()
    years_json = _json([int(year) for year in requested_years])
    with connect_catalog(workspace_root) as connection:
        connection.execute(
            """
            INSERT INTO cache_refresh_jobs(job_id, batch_id, task_id, ticker, requested_years_json,
              status, reason, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET batch_id=excluded.batch_id, task_id=excluded.task_id,
              ticker=excluded.ticker, requested_years_json=excluded.requested_years_json,
              status=excluded.status, reason=excluded.reason, updated_at=excluded.updated_at
            """,
            (job_id, batch_id, task_id, ticker, years_json, "queued", None, now, now),
        )
        connection.commit()
    return {"job_id": job_id, "batch_id": batch_id, "task_id": task_id, "ticker": ticker, "status": "queued"}


def update_refresh_job(
    workspace_root: Path,
    job_id: str,
    *,
    status: str,
    reason: dict[str, Any] | str | None = None,
) -> None:
    """更新单家公司预热状态；reason 保留机器可读摘要而非整份任务。"""

    encoded_reason = reason if isinstance(reason, str) else json.dumps(reason or {}, ensure_ascii=False, sort_keys=True)
    with connect_catalog(workspace_root) as connection:
        connection.execute(
            "UPDATE cache_refresh_jobs SET status=?, reason=?, updated_at=? WHERE job_id=?",
            (status, encoded_reason, _now(), job_id),
        )
        connection.commit()


def recover_orphaned_refresh_jobs(workspace_root: Path) -> int:
    """Close jobs left running by a process restart instead of leaving them stuck forever."""

    now = _now()
    reason = json.dumps(
        {
            "message": "服务重启导致预热任务中断，请重新提交该企业。",
            "error_code": "SERVICE_RESTART_RECOVERY",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    with connect_catalog(workspace_root) as connection:
        cursor = connection.execute(
            """
            UPDATE cache_refresh_jobs
            SET status='needs_human', reason=?, updated_at=?
            WHERE status IN ('queued', 'running')
            """,
            (reason, now),
        )
        connection.commit()
        return int(cursor.rowcount or 0)


def refresh_report(workspace_root: Path, batch_id: str) -> dict[str, Any]:
    """汇总一批预热任务，区分成功、缺报、不适用、字段缺口和失败。"""

    with connect_catalog(workspace_root) as connection:
        rows = connection.execute(
            """
            SELECT job_id, batch_id, task_id, ticker, requested_years_json, status, reason, created_at, updated_at
            FROM cache_refresh_jobs WHERE batch_id=? ORDER BY created_at ASC
            """,
            (batch_id,),
        ).fetchall()
    items: list[dict[str, Any]] = []
    counts = {key: 0 for key in ("queued", "running", "success", "not_found", "not_applicable", "field_gaps", "needs_human", "failed")}
    for row in rows:
        try:
            summary = json.loads(row["reason"] or "{}")
        except json.JSONDecodeError:
            summary = {"message": row["reason"] or ""}
        status = str(row["status"] or "queued")
        result_status = summary.get("result_status")
        gate_level = summary.get("industry_fit_level")
        extraction_status = str(summary.get("field_extraction_status") or "")
        if status == "completed":
            if gate_level == "not_applicable":
                category = "not_applicable"
            elif extraction_status in {"cached_with_gaps", "passed_technical_with_gaps", "industry_unknown"} or summary.get("field_gap_count", 0):
                category = "field_gaps"
            else:
                category = "success"
        elif status == "needs_human":
            category = "needs_human"
        elif status == "failed":
            category = "not_found" if summary.get("error_code") == "ANNUAL_REPORT_NOT_FOUND" else "failed"
        else:
            category = status if status in {"queued", "running"} else "failed"
        counts[category] += 1
        activity_age_seconds = _duration_seconds(row["updated_at"], _now())
        items.append(
            {
                "job_id": row["job_id"],
                "task_id": row["task_id"],
                "ticker": row["ticker"],
                "requested_years": json.loads(row["requested_years_json"] or "[]"),
                "status": status,
                "category": category,
                "result_status": result_status,
                "industry_fit_level": gate_level,
                "field_extraction_status": extraction_status or None,
                "field_gap_count": summary.get("field_gap_count", 0),
                "duration_seconds": summary.get("duration_seconds")
                if summary.get("duration_seconds") is not None
                else _duration_seconds(row["created_at"], row["updated_at"]),
                "error_code": summary.get("error_code"),
                "reason": summary.get("message") or summary.get("reason"),
                "last_activity_at": row["updated_at"],
                "activity_age_seconds": activity_age_seconds,
                "stalled": status == "running" and (activity_age_seconds or 0) >= _refresh_stall_seconds(),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return {
        "schema_version": "catalog_refresh_report_v1",
        "batch_id": batch_id,
        "total": len(items),
        "counts": counts,
        "complete": bool(items) and all(item["category"] not in {"queued", "running"} for item in items),
        "stall_threshold_seconds": _refresh_stall_seconds(),
        "items": items,
    }


def list_cache_entries(workspace_root: Path, company_query: str | None = None) -> list[dict[str, Any]]:
    with connect_catalog(workspace_root) as connection:
        sql = """
            SELECT c.ticker, c.company_name, c.company_alias, c.market, c.industry_family,
              s.case_id, s.snapshot_id, s.source_fingerprint, s.report_years_json,
              s.cache_status, s.rag_index_version, s.extractor_version,
              s.verified_at, s.updated_at AS snapshot_updated_at
            FROM companies c JOIN source_snapshots s ON s.ticker=c.ticker
        """
        params: tuple[Any, ...] = ()
        if company_query:
            sql += " WHERE c.ticker=? OR c.company_name LIKE ? OR c.company_alias LIKE ?"
            like = f"%{company_query.strip()}%"
            params = (company_query.strip(), like, like)
        sql += " ORDER BY s.updated_at DESC"
        rows = connection.execute(sql, params).fetchall()
        entries: list[dict[str, Any]] = []
        for row in rows:
            verified_at = row["verified_at"] or row["snapshot_updated_at"]
            entries.append(
                {
                    **dict(row),
                    "report_years": json.loads(row["report_years_json"] or "[]"),
                    "report_years_json": None,
                    "cache_state": _cache_state(verified_at),
                    "cache_age_days": _cache_age_days(verified_at),
                    "cache_max_age_days": _cache_max_age_days(),
                }
            )
        return entries


def lookup_cached_document(
    workspace_root: Path,
    ticker: str,
    report_year: int,
    source_url: str,
) -> dict[str, Any] | None:
    """Find one already validated annual PDF that can be reused incrementally."""

    with connect_catalog(workspace_root) as connection:
        row = connection.execute(
            """
            SELECT document_id, case_id, ticker, report_year, source_url, sha256,
              byte_count, page_count, storage_relpath, content_store_relpath,
              validation_status
            FROM report_documents
            WHERE ticker=? AND report_year=? AND source_url=? AND validation_status='passed'
            ORDER BY updated_at DESC LIMIT 1
            """,
            (str(ticker), int(report_year), str(source_url)),
        ).fetchone()
    return dict(row) if row else None


def bootstrap_runtime_catalog(workspace_root: Path) -> int:
    """将已有巨潮案例的可验证元数据补入目录，供第一次热路径直接命中。"""

    cases_dir = _runtime_dir(workspace_root) / "cases"
    if not cases_dir.is_dir():
        return 0
    synced = 0
    for case_path in cases_dir.glob("*/case.json"):
        try:
            case = json.loads(case_path.read_text(encoding="utf-8"))
            if case.get("registry_mode") != "cninfo_official_auto":
                continue
            fields_path = case_path.with_name("financial_fields.json")
            rows = json.loads(fields_path.read_text(encoding="utf-8")) if fields_path.is_file() else []
            manifest_path = _runtime_dir(workspace_root) / "rag" / case["case_id"] / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
            # 不信任旧 gate JSON；按当前版本重新计算，但不刷新来源验证时间。
            from .industry_gate import evaluate_industry_gate

            gate = evaluate_industry_gate(company=case, case=case, rule_ids=["R1"])
            sync_case_to_catalog(
                workspace_root,
                case,
                rows=rows,
                rag_manifest=manifest,
                industry_gate=gate,
                refresh_verified_at=False,
            )
            synced += 1
        except (OSError, ValueError, TypeError, json.JSONDecodeError, sqlite3.Error):
            # 某一份历史缓存损坏不能阻断其他企业的实时流程。
            continue
    return synced
