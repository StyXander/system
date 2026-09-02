"""多源知识库（G3）单元测试：Schema、分层、截止日、检索合同与隔离语义。"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.knowledge_rag import build_retrieval_request, normalize_retrieval_hit, rank_candidates, retrieve_knowledge
from backend.app.knowledge_sources import (
    SOURCE_CATEGORIES,
    cutoff_window_years,
    active_source_entries,
    coverage_group_summary,
    filter_by_cutoff,
    knowledge_cutoff_date,
    load_source_manifest,
    normalize_source_entry,
    source_layer,
)


def test_source_entry_normalization_adds_layer_and_defaults():
    entry = normalize_source_entry(
        {
            "source_id": "SRC-MOF-CAS14",
            "source_category": "accounting_standard",
            "publisher": "中华人民共和国财政部",
            "title": "企业会计准则第14号——收入",
            "official_url": "https://www.mof.gov.cn/example",
            "published_at": "2017-07-19",
        }
    )
    assert entry["layer"] == "authoritative_rules"
    assert entry["coverage_status"] == "representative"
    assert entry["validation_status"] == "failed"
    assert "missing_document_id" in entry["validation_errors"]
    assert entry["sha256"] is None
    assert entry["retrieved_at"]


def test_unknown_category_fails_validation():
    entry = normalize_source_entry(
        {
            "source_id": "SRC-BAD",
            "source_category": "random_blog",
            "publisher": "x",
            "title": "y",
            "official_url": "https://example.com",
            "published_at": "2024-01-01",
            "document_id": "D1",
            "sha256": "deadbeef",
            "coverage_status": "representative",
            "validation_status": "passed",
        }
    )
    assert entry["validation_status"] == "failed"
    assert source_layer("random_blog") == "case_evidence"


def test_cutoff_window_and_filtering():
    assert cutoff_window_years(None) is None
    window = cutoff_window_years("2026-08-15", 5)
    assert window == ("2021-08-15", "2026-08-15")
    sources = [
        {"source_category": "annual_report", "published_at": "2025-04-30"},
        {"source_category": "csrc_penalty", "published_at": "2026-09-01"},
        {"source_category": "news", "published_at": ""},
    ]
    assert len(filter_by_cutoff(sources, "2026-08-15")) == 1
    assert len(filter_by_cutoff(sources, None)) == 0


def test_default_cutoff_is_frozen_and_window_is_exact_anniversary():
    assert knowledge_cutoff_date() == "2026-08-24"
    assert cutoff_window_years("2026-08-24", 5) == ("2021-08-24", "2026-08-24")
    entries = [
        {"source_id": "OLD", "source_category": "csrc_penalty", "published_at": "2021-08-23", "validation_status": "passed"},
        {"source_id": "BOUNDARY", "source_category": "csrc_penalty", "published_at": "2021-08-24", "validation_status": "passed"},
        {"source_id": "FUTURE", "source_category": "csrc_penalty", "published_at": "2026-08-25", "validation_status": "passed"},
    ]
    assert [row["source_id"] for row in active_source_entries(entries, "2026-08-24")] == ["BOUNDARY"]


def test_manifest_load_and_validation(tmp_path: Path):
    manifest = tmp_path / "knowledge_sources.manifest.json"
    manifest.write_text(
        '{"schema_version": "knowledge_sources_manifest_v1", "sources": []}',
        encoding="utf-8",
    )
    entries, failure = load_source_manifest(manifest)
    assert failure is None and entries == []
    manifest.write_text('{"not": "a manifest"}', encoding="utf-8")
    _entries, failure = load_source_manifest(manifest)
    assert failure == "knowledge_manifest_schema_mismatch"
    _entries, failure = load_source_manifest(tmp_path / "missing.json")
    assert failure == "knowledge_manifest_missing"


def test_retrieval_request_requires_categories_and_date():
    request = build_retrieval_request(
        case_id="STD_DEV_T0",
        question_id="RAG-Q1",
        source_categories=["annual_report", "accounting_standard"],
        as_of_date="2026-08-15",
        cutoff_date="2026-08-15",
        snapshot_id="KNOWLEDGE-20260815-V1",
        ticker="300689",
    )
    assert request["source_categories"] == ["annual_report", "accounting_standard"]
    with pytest.raises(ValueError):
        build_retrieval_request(case_id="STD_DEV_T0", question_id="RAG-Q1", source_categories=[], as_of_date="2026-08-15", cutoff_date=None, snapshot_id="S")
    with pytest.raises(ValueError):
        build_retrieval_request(case_id="STD_DEV_T0", question_id="RAG-Q1", source_categories=["news"], as_of_date="not-a-date", cutoff_date=None, snapshot_id="S")


def test_rank_candidates_puts_authoritative_rules_first_and_honors_cutoff():
    candidates = [
        {"source_id": "S1", "source_category": "news", "published_at": "2026-07-01"},
        {"source_id": "S2", "source_category": "accounting_standard", "published_at": "2017-07-01"},
        {"source_id": "S3", "source_category": "annual_report", "published_at": "2026-08-20"},
    ]
    request = build_retrieval_request(
        case_id="C1",
        question_id="Q1",
        source_categories=["news", "accounting_standard", "annual_report"],
        as_of_date="2026-08-15",
        cutoff_date="2026-08-15",
        snapshot_id="S",
    )
    ranked = rank_candidates(candidates, request)
    assert [item["source_id"] for item in ranked] == ["S2", "S1"]
    # 未请求的类别不进入结果；请求的类别即使超出截止日也按规则保留（此处无截止日）
    request_without_news = build_retrieval_request(
        case_id="C1", question_id="Q1", source_categories=["annual_report"], as_of_date="2026-08-15",
        cutoff_date=None, snapshot_id="S",
    )
    only_annual = rank_candidates(candidates, request_without_news)
    assert [item["source_id"] for item in only_annual] == ["S3"]


def test_retrieval_hit_schema_and_support_status():
    hit = normalize_retrieval_hit(
        {
            "retrieval_id": "RET-1",
            "source_id": "SRC-1",
            "document_id": "D1",
            "locator": "第 12 页",
            "content_sha256": "abc",
            "publisher": "财政部",
            "published_at": "2017-07-01",
            "support_status": "supported",
            "source_category": "accounting_standard",
        }
    )
    assert hit["support_status"] == "supported"
    uncertain = normalize_retrieval_hit({"source_id": "SRC-2"})
    assert uncertain["support_status"] == "candidate"
    assert uncertain["retrieval_id"].startswith("RET-")
    assert uncertain["document_id"] is None


def test_retrieval_returns_locator_snapshot_and_claim_boundary():
    entries = [
        {
            "source_id": "SRC-RULE",
            "source_category": "auditing_standard",
            "publisher": "中国注册会计师协会",
            "title": "审计准则示例",
            "official_url": "https://www.cicpa.org.cn/example",
            "published_at": "2024-01-01",
            "document_id": "DOC-RULE",
            "sha256": "f" * 64,
            "validation_status": "passed",
            "retrieval_excerpt": "收入确认风险应设计实质性程序。",
            "retrieval_locator": "第 3 页，审计程序",
            "excerpt_sha256": "e" * 64,
            "query_terms": ["R1"],
        }
    ]
    request = build_retrieval_request(
        case_id="C1", question_id="R1", source_categories=["auditing_standard"],
        as_of_date="2026-08-24", cutoff_date="2026-08-24", snapshot_id="SNAP-1",
    )
    hits = retrieve_knowledge(entries, request, limit=1)
    assert len(hits) == 1
    assert hits[0]["locator"] == "第 3 页，审计程序"
    assert hits[0]["snapshot_id"] == "SNAP-1"
    assert hits[0]["claim_scope"] == "procedure_guidance"
    assert "不支持当前企业事实" in hits[0]["boundary"]


def test_manifest_has_active_representative_coverage_for_all_categories():
    entries, failure = load_source_manifest(Path(__file__).parents[1] / "knowledge_sources.manifest.json")
    assert failure is None
    summary = coverage_group_summary(entries, "2026-08-24")
    assert summary["active_source_count"] > 0
    assert summary["archived_source_count"] >= 1
    assert all(item["document_count"] >= 1 for item in summary["categories"].values())
    assert summary["categories"]["csrc_penalty"]["validation_status"] == "passed"
    assert summary["categories"]["exchange_inquiry"]["validation_status"] == "passed"


def test_all_categories_are_registered_in_layers():
    for category in SOURCE_CATEGORIES:
        assert source_layer(category) in {"case_evidence", "authoritative_rules", "industry_context"}


def test_coverage_summary_counts_verified_sources(monkeypatch):
    from backend.app import knowledge_sources as ks

    monkeypatch.delenv("COMPETITION_DATA_CUTOFF_DATE", raising=False)
    entries = [
        {"source_category": "annual_report", "validation_status": "passed", "retrieved_at": "2026-08-24T00:00:00Z"},
        {"source_category": "annual_report", "validation_status": "pending", "retrieved_at": "2026-08-23T00:00:00Z"},
        {"source_category": "tax_regulation", "validation_status": "passed", "retrieved_at": "2026-08-24T00:00:00Z"},
    ]
    summary = ks.coverage_group_summary(entries, None)
    assert summary["total_sources"] == 3
    assert summary["verified_sources"] == 2
    assert summary["draft_mode"] is True
    assert summary["categories"]["annual_report"]["document_count"] == 2
    assert summary["categories"]["annual_report"]["verified_count"] == 1
    assert summary["last_checked_at"] == "2026-08-24T00:00:00Z"
    assert "草案" in summary["boundary"]
