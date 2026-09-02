from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz
import pytest

from backend.app import cases as cases_module
from backend.app import pipeline as pipeline_module
from backend.app.cases import build_case_template_zip, get_case, import_case_zip, register_cninfo_case
from backend.app.catalog import catalog_path, connect_catalog, lookup_cached_case, sync_case_to_catalog
from backend.app.cninfo import _date_from_value
from backend.app.industry_gate import evaluate_industry_gate
from backend.app.rag import INDEX_VERSION, get_retrieval, prepare_index, retrieve


def _single_page_pdf(label: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), label)
    content = document.tobytes()
    document.close()
    return content


def _catalog_case() -> dict:
    return {
        "case_id": "CNINFO_600302_T0_20250430",
        "ticker": "600302",
        "company_name": "测试科技股份有限公司",
        "company_alias": "测试科技",
        "market": "sse",
        "registry_mode": "cninfo_official_auto",
        "source_snapshot_id": "snapshot-valid",
        "documents": [
            {
                "document_id": "DOC-2024",
                "report_year": 2024,
                "disclosure_date": "2025-04-30",
                "announcement_title": "测试科技2024年年度报告",
                "source_url": "https://static.cninfo.com.cn/finalpage/2025-04-30/2024.PDF",
                "sha256": "A" * 64,
                "validation_status": "passed",
            },
            {
                "document_id": "DOC-2023",
                "report_year": 2023,
                "disclosure_date": "2024-04-30",
                "announcement_title": "测试科技2023年年度报告",
                "source_url": "https://static.cninfo.com.cn/finalpage/2024-04-30/2023.PDF",
                "sha256": "B" * 64,
                "validation_status": "passed",
            },
        ],
    }


def test_cninfo_timestamp_uses_seconds_or_milliseconds_and_shanghai_date() -> None:
    shanghai = timezone(timedelta(hours=8))
    instant = datetime(2024, 1, 1, 0, 30, tzinfo=shanghai)
    seconds = int(instant.timestamp())

    assert _date_from_value(seconds) == "2024-01-01"
    assert _date_from_value(str(seconds)) == "2024-01-01"
    assert _date_from_value(seconds * 1000) == "2024-01-01"
    assert _date_from_value(str(seconds * 1000)) == "2024-01-01"


def test_financial_leasing_is_not_misclassified_as_construction_leasing() -> None:
    gate = evaluate_industry_gate(
        company={"company_name": "江苏金融租赁股份有限公司", "ticker": "600901"},
        case={},
        rule_ids=["R1"],
    )

    assert gate["fit_level"] == "not_applicable"
    assert gate["industry_family"] == "financial"
    assert gate["specialized_rule"] is None
    assert "R1" in gate["blocked_rules"]


def test_catalog_skips_corrupt_snapshot_and_finds_older_valid_snapshot(tmp_path: Path) -> None:
    case = _catalog_case()
    sync_case_to_catalog(
        tmp_path,
        case,
        rag_manifest={
            "status": "ready",
            "index_version": INDEX_VERSION,
            "source_fingerprint": "fingerprint-valid",
            "chunk_count": 2,
        },
        industry_gate=evaluate_industry_gate(company=case, case=case, rule_ids=["R1"]),
    )
    connection = connect_catalog(tmp_path)
    try:
        connection.execute(
            """
            INSERT INTO source_snapshots(
              snapshot_id, case_id, ticker, source_fingerprint, report_years_json,
              cache_status, rag_index_version, extractor_version, cache_key_json,
              verified_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "snapshot-corrupt",
                "CNINFO_600302_CORRUPT",
                "600302",
                "fingerprint-corrupt",
                "{broken-json",
                "ready",
                INDEX_VERSION,
                "field_extraction_v1",
                "{}",
                "2026-08-09T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    match = lookup_cached_case(tmp_path, "600302", [2024, 2023])
    assert match is not None
    assert match["case_id"] == case["case_id"]


def test_catalog_bootstrap_reads_atomically_published_rag_manifest(tmp_path: Path) -> None:
    from backend.app.catalog import bootstrap_runtime_catalog

    case = {
        **_catalog_case(),
        "schema_version": "case_manifest_v1",
        "company_alias": "测试科技",
        "industry": "制造业",
        "available_years": [],
        "sample_type": "public",
    }
    runtime_root = tmp_path / "backend" / "runtime"
    namespace = os.getenv("AUDITTRACE_RUNTIME_NAMESPACE", "")
    if namespace:
        runtime_root = runtime_root / namespace
    case_dir = runtime_root / "cases" / case["case_id"]
    case_dir.mkdir(parents=True)
    (case_dir / "case.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    (case_dir / "financial_fields.json").write_text("[]", encoding="utf-8")

    rag_root = runtime_root / "rag" / case["case_id"]
    version = "0123456789abcdef-ABCDEF12"
    version_dir = rag_root / "versions" / version
    version_dir.mkdir(parents=True)
    (version_dir / "rag.faiss").write_bytes(b"published-index-placeholder")
    (version_dir / "manifest.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "case_id": case["case_id"],
                "index_version": INDEX_VERSION,
                "source_fingerprint": "fingerprint-active",
                "chunk_count": 2,
            }
        ),
        encoding="utf-8",
    )
    (rag_root / "active.json").write_text(json.dumps({"version": version}), encoding="utf-8")

    assert bootstrap_runtime_catalog(tmp_path, force=True) == 1
    match = lookup_cached_case(tmp_path, "600302", [2024, 2023])
    assert match is not None
    assert match["source_fingerprint"] == "fingerprint-active"


def test_rag_retrieval_log_survives_atomic_index_rebuild(tmp_path: Path) -> None:
    imported = import_case_zip(
        tmp_path,
        build_case_template_zip(),
        authorized=True,
        desensitized=True,
    )
    case_id = imported["case_id"]
    prepare_index(tmp_path, case_id=case_id)
    first = retrieve(
        tmp_path,
        query="synthetic annual report",
        t0=imported["t0"],
        rule_id="R1",
        top_k=1,
        case_id=case_id,
    )

    prepare_index(tmp_path, case_id=case_id, force=True)
    restored = get_retrieval(tmp_path, first["retrieval_id"])

    assert restored is not None
    assert restored["case_id"] == case_id


def test_task_state_replace_retries_transient_windows_reader_contention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_replace = Path.replace
    attempts = 0

    def flaky_replace(path: Path, target: Path) -> Path:
        nonlocal attempts
        if path.name.endswith(".tmp") and attempts < 2:
            attempts += 1
            raise PermissionError("simulated Windows reader contention")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    task = pipeline_module.create_task(tmp_path, {"company_query": "600302", "years": 2})

    assert attempts == 2
    assert pipeline_module.load_task(tmp_path, task["task_id"])["status"] == "queued"


def test_pipeline_runtime_namespace_isolates_task_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDITTRACE_RUNTIME_NAMESPACE", "acceptance-run")

    task = pipeline_module.create_task(tmp_path, {"company_query": "600302", "years": 2})

    namespaced = tmp_path / "backend" / "runtime" / "acceptance-run" / "pipelines" / f"{task['task_id']}.json"
    formal = tmp_path / "backend" / "runtime" / "pipelines" / f"{task['task_id']}.json"
    assert namespaced.is_file()
    assert not formal.exists()


def test_pipeline_and_catalog_share_the_same_sanitized_runtime_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDITTRACE_RUNTIME_NAMESPACE", "acceptance.v1")

    task = pipeline_module.create_task(tmp_path, {"company_query": "600302", "years": 2})

    assert pipeline_module._task_path(tmp_path, task["task_id"]).parent.parent == catalog_path(tmp_path).parent


def test_pipeline_preflight_failure_is_persisted_instead_of_leaving_task_queued(tmp_path: Path) -> None:
    task = pipeline_module.create_task(tmp_path, {"company_query": "600302", "years": "invalid"})

    result = pipeline_module.run_ingestion(tmp_path, task["task_id"])
    persisted = pipeline_module.load_task(tmp_path, task["task_id"])

    assert result["status"] == "failed"
    assert persisted is not None
    assert persisted["status"] == "failed"
    assert persisted["attempt"] == 1
    assert persisted["errors"][-1]["code"] == "PIPELINE_INTERNAL_ERROR"


def test_snapshot_fingerprint_is_stable_when_document_order_changes() -> None:
    documents = [
        {"document_id": "D-2024", "report_year": 2024, "source_url": "u-2024", "sha256": "A"},
        {"document_id": "D-2023", "report_year": 2023, "source_url": "u-2023", "sha256": "B"},
    ]

    assert pipeline_module._source_snapshot_id(documents) == pipeline_module._source_snapshot_id(list(reversed(documents)))


def test_cached_field_years_keep_latest_complete_pair_when_older_year_has_gaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {"field_kind": kind, "year": year, "value": 1.0}
        for year in (2024, 2023)
        for kind in ("revenue", "accounts_receivable")
    ]
    monkeypatch.setattr(pipeline_module, "get_financial_rows", lambda _root, _case_id: rows)

    extraction = pipeline_module._cached_field_extraction(
        tmp_path,
        "CACHE_CASE",
        rule_ids=["R1"],
        requested_years=[2024, 2023, 2022],
    )

    assert extraction["status"] == "cached_with_gaps"
    assert extraction["available_years"] == [2024]


@pytest.mark.parametrize("worker_count", [5, 10, 20])
def test_concurrent_same_snapshot_registration_reuses_completed_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, worker_count: int
) -> None:
    content = _single_page_pdf("Concurrent annual report")
    documents = [
        {
            "document_id": "CNINFO-600302-2024-CONCURRENT",
            "report_year": 2024,
            "announcement_date": "2025-04-30",
            "announcement_title": "测试科技2024年年度报告",
            "source_url": "https://static.cninfo.com.cn/finalpage/2025-04-30/concurrent.PDF",
            "sha256": cases_module._sha256_bytes(content),
            "byte_count": len(content),
            "page_count": 1,
            "validation_status": "passed",
            "content": content,
        }
    ]
    company = {
        "ticker": "600302",
        "company_name": "测试科技股份有限公司",
        "company_alias": "测试科技",
        "org_id": "gssz0000302",
        "market": "sse",
    }
    original_store = cases_module._ensure_content_addressed_pdf

    def delayed_store(workspace_root: Path, sha256: str, payload: bytes) -> Path:
        time.sleep(0.08)
        return original_store(workspace_root, sha256, payload)

    monkeypatch.setattr(cases_module, "_ensure_content_addressed_pdf", delayed_store)

    def register() -> dict:
        return register_cninfo_case(
            tmp_path,
            case_id="CNINFO_600302_T0_20250430",
            company=company,
            documents=documents,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(lambda _index: register(), range(worker_count)))

    assert {item["source_snapshot_id"] for item in results} == {results[0]["source_snapshot_id"]}
    assert get_case(tmp_path, "CNINFO_600302_T0_20250430") is not None
