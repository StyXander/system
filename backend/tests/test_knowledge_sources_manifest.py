"""知识来源台账的截止日、定位和主张边界回归合同。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.app.knowledge_rag import _claim_scope, build_retrieval_request, retrieve_knowledge
from backend.app.knowledge_sources import (
    SOURCE_CATEGORIES,
    active_source_entries,
    coverage_group_summary,
    cutoff_window_years,
    load_source_manifest,
    normalize_source_entry,
    source_is_active,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "backend" / "knowledge_sources.manifest.json"


def test_manifest_has_deterministic_ids_and_retrieval_locator_for_active_sources() -> None:
    entries, error = load_source_manifest(MANIFEST)
    assert error is None
    assert len(entries) == 13
    assert len({entry["source_id"] for entry in entries}) == len(entries)
    active = active_source_entries(entries, "2026-08-24")
    assert len(active) == 12
    for entry in active:
        assert entry["official_url"].startswith("https://")
        assert entry["retrieval_excerpt"]
        assert entry["retrieval_locator"]
        assert entry["excerpt_sha256"] or hashlib.sha256(
            str(entry["retrieval_excerpt"]).encode("utf-8")
        ).hexdigest()


def test_exact_five_year_window_and_future_cutoff_are_enforced() -> None:
    assert cutoff_window_years("2026-08-24") == ("2021-08-24", "2026-08-24")
    old_penalty = {
        "source_category": "csrc_penalty",
        "published_at": "2021-08-23",
        "validation_status": "passed",
    }
    boundary_penalty = {**old_penalty, "published_at": "2021-08-24"}
    future_news = {
        "source_category": "news",
        "published_at": "2026-08-25",
        "validation_status": "passed",
    }
    assert not source_is_active(old_penalty, "2026-08-24")
    assert source_is_active(boundary_penalty, "2026-08-24")
    assert not source_is_active(future_news, "2026-08-24")


def test_coverage_summary_is_representative_and_covers_every_required_category() -> None:
    entries, error = load_source_manifest(MANIFEST)
    assert error is None
    summary = coverage_group_summary(entries, "2026-08-24")
    assert summary["cutoff_date"] == "2026-08-24"
    assert summary["snapshot_id"] == "KNOWLEDGE-20260824-REPRESENTATIVE-V1"
    assert summary["active_source_count"] == 12
    assert summary["archived_source_count"] == 1
    assert set(summary["categories"]) == set(SOURCE_CATEGORIES)
    assert all(item["coverage_status"] == "representative" for item in summary["categories"].values())
    assert all(item["document_count"] >= 1 for item in summary["categories"].values())


def test_claim_scope_keeps_normative_and_analogous_sources_out_of_case_facts() -> None:
    request = {"ticker": "600302", "company_name": "标准股份"}
    current = {"source_category": "annual_report", "ticker": "600302", "company_name": "标准股份"}
    other = {"source_category": "annual_report", "ticker": "000858", "company_name": "五粮液"}
    normative = {"source_category": "auditing_standard"}
    analogous = {"source_category": "csrc_penalty"}
    assert _claim_scope(current, request)[0] == "case_fact"
    assert _claim_scope(other, request)[0] == "case_fact_prohibited"
    assert _claim_scope(normative, request)[0] == "procedure_guidance"
    assert _claim_scope(analogous, request)[0] == "contextual_hypothesis_only"


def test_retrieval_filters_future_entries_and_returns_locator_hash_and_boundary() -> None:
    entries, error = load_source_manifest(MANIFEST)
    assert error is None
    entries.append(
        {
            "source_id": "SRC-FUTURE-TEST",
            "source_category": "news",
            "publisher": "测试",
            "title": "未来资料",
            "official_url": "https://www.csrc.gov.cn/future",
            "published_at": "2026-08-25",
            "retrieved_at": "2026-08-25T00:00:00Z",
            "document_id": "FUTURE-TEST",
            "sha256": "x",
            "coverage_status": "representative",
            "validation_status": "passed",
            "retrieval_excerpt": "未来资料不得进入当前快照",
            "retrieval_locator": "测试定位",
            "query_terms": ["销售与收款"],
        }
    )
    request = build_retrieval_request(
        case_id="STD_DEV_T0",
        question_id="sales_receivable",
        source_categories=["news"],
        as_of_date="2026-08-24",
        cutoff_date="2026-08-24",
        snapshot_id="KNOWLEDGE-20260824-REPRESENTATIVE-V1",
        ticker="600302",
        industry="制造业",
    )
    hits = retrieve_knowledge(entries, request, limit=10)
    assert hits
    assert all(hit["source_id"] != "SRC-FUTURE-TEST" for hit in hits)
    assert all(hit["locator"] and hit["content_sha256"] for hit in hits)
    assert all(hit["claim_scope"] == "contextual_hypothesis_only" for hit in hits)


def test_missing_source_id_is_generated_deterministically() -> None:
    raw = {
        "source_category": "news",
        "publisher": "测试发布者",
        "title": "测试来源",
        "official_url": "https://www.csrc.gov.cn/test",
        "published_at": "2026-08-01",
        "retrieved_at": "2026-08-24T00:00:00Z",
        "document_id": "TEST-1",
        "sha256": "abc",
        "coverage_status": "representative",
        "validation_status": "passed",
    }
    first = normalize_source_entry(raw)
    second = normalize_source_entry(raw)
    assert first["source_id"] == second["source_id"]
    assert first["source_id"].startswith("SRC-")
