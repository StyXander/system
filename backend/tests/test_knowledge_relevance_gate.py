"""知识检索相关性先于权威等级：无关条目不得当证据，零命中必须显式拒答。

覆盖 2026-09-09 审查反例 C02：旧实现从不读取自然语言问题文本，排序把权威
等级放在词命中之前且不剔除零命中，真实清单上返回的 8 条命中全部零相关词。
"""
from __future__ import annotations

from pathlib import Path

from backend.app.knowledge_rag import (
    build_retrieval_request,
    controlled_question_terms,
    retrieve_knowledge,
)
from backend.app.knowledge_sources import load_source_manifest

MANIFEST = Path(__file__).parents[1] / "knowledge_sources.manifest.json"

ALL_CATEGORIES = [
    "annual_report",
    "csrc_penalty",
    "exchange_inquiry",
    "accounting_standard",
    "auditing_standard",
    "tax_regulation",
    "industry_report",
    "news",
    "macro_indicator",
]

ENTRY = {
    "source_id": "FIXTURE-KB",
    "source_category": "auditing_standard",
    "publisher": "中国注册会计师协会",
    "title": "审计抽样程序",
    "official_url": "https://www.cicpa.org.cn/sample",
    "published_at": "2024-01-01",
    "document_id": "DOC-SAMPLE",
    "sha256": "a" * 64,
    "validation_status": "passed",
    "retrieval_excerpt": "抽样程序须记录总体和样本。",
    "retrieval_locator": "第 5 页",
    "excerpt_sha256": "b" * 64,
    "query_terms": ["审计抽样"],
}


def _request(**overrides):
    payload = {
        "case_id": "FIXTURE",
        "question_id": "KB-R1",
        "source_categories": ["auditing_standard"],
        "as_of_date": "2026-08-24",
        "cutoff_date": "2026-08-24",
        "snapshot_id": "SNAP-1",
    }
    payload.update(overrides)
    return build_retrieval_request(**payload)


def test_irrelevant_question_returns_nothing_instead_of_one_authoritative_entry() -> None:
    """问火星土壤时不得因为某条准则权威等级高就送进上下文。"""

    assert retrieve_knowledge([ENTRY], _request(query_text="火星土壤的化学组成是什么")) == []


def test_relevant_question_text_gates_in_the_registered_entry() -> None:
    hits = retrieve_knowledge([ENTRY], _request(query_text="应收账款的审计抽样程序"))
    assert [hit["source_id"] for hit in hits] == ["FIXTURE-KB"]
    assert hits[0]["relevance_matches"] >= 1
    assert hits[0]["retrieval_version"]


def test_rule_question_id_maps_to_registered_controlled_terms() -> None:
    """KB-R1 必须展开成登记的中文问题词，而不是把 kb、r1 当语义信号。"""

    terms = controlled_question_terms("KB-R1")
    assert "应收账款" in terms or "营业收入" in terms
    assert "kb" not in terms


def test_zero_limit_returns_no_hits() -> None:
    """limit=0 表示不要结果，旧实现用 max(1, limit) 强行返回一条。"""

    assert retrieve_knowledge([ENTRY], _request(query_text="审计抽样"), limit=0) == []


def test_live_manifest_returns_only_relevant_hits() -> None:
    """真实清单上 R1 固定问题必须能检索到相关条目，且每条都有词命中。"""

    entries, error = load_source_manifest(MANIFEST)
    assert error is None
    hits = retrieve_knowledge(
        entries,
        _request(
            query_text="营业收入与应收账款增长背离的审计程序",
            source_categories=ALL_CATEGORIES,
            ticker="600302",
            industry="制造业",
        ),
        limit=8,
    )
    assert hits, "R1 固定问题必须能在真实清单上检索到相关条目"
    assert all(hit["relevance_matches"] >= 1 for hit in hits)


def test_more_relevant_low_authority_beats_less_relevant_high_authority() -> None:
    """权威等级只能在同等相关度之间定序，不能替代相关性本身。"""

    sharp_news = dict(
        ENTRY,
        source_id="FIXTURE-NEWS",
        source_category="news",
        title="应收账款与营业收入异常增长问询",
        retrieval_excerpt="应收账款 营业收入 增长 问询函",
        query_terms=["应收账款", "营业收入", "增长"],
    )
    weak_rule = dict(
        ENTRY,
        source_id="FIXTURE-RULE",
        source_category="auditing_standard",
        title="审计抽样程序",
        retrieval_excerpt="抽样程序须记录总体和样本。",
        query_terms=["应收账款"],
    )
    hits = retrieve_knowledge(
        [weak_rule, sharp_news],
        _request(query_text="应收账款 营业收入 增长", source_categories=["auditing_standard", "news"]),
        limit=2,
    )
    assert [hit["source_id"] for hit in hits] == ["FIXTURE-NEWS", "FIXTURE-RULE"]


def test_other_company_annual_report_is_excluded_not_just_marked_prohibited() -> None:
    """他企业年报即使词面高度相关，也不能进入当前案例的证据与上下文预算。"""

    standard_report = {
        "source_id": "FIXTURE-600302-AR",
        "source_category": "annual_report",
        "publisher": "巨潮资讯",
        "title": "标准股份 2024 年年度报告",
        "official_url": "https://static.cninfo.com.cn/finalpage/2025-04-29/a.pdf",
        "published_at": "2025-04-29",
        "document_id": "DOC-600302-2024",
        "sha256": "c" * 64,
        "validation_status": "passed",
        "retrieval_excerpt": "合并资产负债表披露应收账款与营业收入。",
        "retrieval_locator": "第 120 页",
        "ticker": "600302",
        "company_name": "标准股份",
        "query_terms": ["应收账款", "营业收入"],
    }
    query = "应收账款 营业收入 规模关系"
    other_request = _request(query_text=query, source_categories=["annual_report"], ticker="600938")
    other_request["company_name"] = "中国海油"
    assert retrieve_knowledge([standard_report], other_request, limit=5) == []
    same_request = _request(query_text=query, source_categories=["annual_report"], ticker="600302")
    same_request["company_name"] = "标准股份"
    hits = retrieve_knowledge([standard_report], same_request, limit=5)
    assert [hit["source_id"] for hit in hits] == ["FIXTURE-600302-AR"]


def test_authority_breaks_ties_at_equal_relevance() -> None:
    """相关度相同时，权威准则条目仍优先于新闻条目。"""

    low = dict(ENTRY, source_id="FIXTURE-NEWS", source_category="news")
    high = dict(ENTRY, source_id="FIXTURE-RULE", source_category="auditing_standard")
    hits = retrieve_knowledge(
        [low, high],
        _request(query_text="审计抽样 总体 样本", source_categories=["auditing_standard", "news"]),
        limit=2,
    )
    assert [hit["source_id"] for hit in hits] == ["FIXTURE-RULE", "FIXTURE-NEWS"]
