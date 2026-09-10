"""多源知识库检索合同：请求边界、结果结构与权威优先级。

G3-6 合同：
- 检索请求必须携带 case_id、as_of_date、source_categories、公司/股票代码、
  可选行业、固定问题 ID、截止日期与快照 ID；
- 返回结果携带 retrieval_id、source_id、document_id、页码/段落定位、内容哈希、
  发布机构与日期、证据支持状态与来源类别；
- 权威规则库不得被新闻片段覆盖：先做相关性门禁，再在同等相关条目中按
  authoritative_rules > industry_context 定序；零相关词条目一律剔除；
- 截止日期过滤：published_at 晚于截止日的条目直接剔除。
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .knowledge_sources import (
    LAYER_BY_CATEGORY,
    SOURCE_CATEGORIES,
    active_source_entries,
    filter_by_cutoff,
)

AUTHORITY_RANK = {
    "authoritative_rules": 3,
    "case_evidence": 2,
    "industry_context": 1,
}

REQUIRED_RETRIEVAL_FIELDS = (
    "retrieval_id",
    "source_id",
    "document_id",
    "locator",
    "content_sha256",
    "publisher",
    "published_at",
    "support_status",
    "source_category",
)

KNOWLEDGE_RETRIEVAL_SCHEMA_VERSION = "knowledge_retrieval_trace_v1"
# 相关性门禁版本：旧口径按权威等级返回零命中条目，必须与新口径可区分。
KNOWLEDGE_RETRIEVAL_VERSION = "knowledge_retrieval_relevance_gate_v2"

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]{2,}|[一-鿿]{2,}")
CJK_RUN_PATTERN = re.compile(r"[一-鿿]+")


def _tokens_from_text(text: str) -> set[str]:
    """生成确定性词符：整段加 2 至 4 字滑窗，弥补中文没有空格分词。

    滑窗只用于本仓库内的小词表匹配，不引入外部分词库，保证结果可复现。
    """

    tokens: set[str] = set()
    for run in TOKEN_PATTERN.findall(str(text or "")):
        lowered = run.lower()
        tokens.add(lowered)
        if not CJK_RUN_PATTERN.fullmatch(lowered):
            continue
        for size in (2, 3, 4):
            for index in range(0, max(0, len(lowered) - size + 1)):
                tokens.add(lowered[index : index + size])
    return tokens


def controlled_question_terms(question_id: str) -> set[str]:
    """把 KB-R1、RAG-Q1 等固定编号展开成已登记的中文问题词，不做外网搜索。

    问题词表复用案例检索的固定问题登记，避免同一竞赛出现两套问题定义。
    """

    # 延迟导入：rag 依赖 faiss，知识检索调用方不应被迫加载向量库。
    from .rag import RAG_QUESTIONS

    wanted = {token.upper() for token in str(question_id or "").replace("KB-", "").split("-") if token}
    terms: list[str] = []
    for item in RAG_QUESTIONS:
        rule_ids = {str(rule).upper() for rule in item.get("rule_ids") or []}
        if str(item.get("question_id") or "").upper() not in wanted and not wanted & rule_ids:
            continue
        terms.append(str(item.get("retrieval_query") or ""))
        terms.append(str(item.get("title") or ""))
        terms.extend(str(term) for term in item.get("anchor_terms") or [])
    return {token for text in terms for token in _tokens_from_text(text)}


def _searchable_text(entry: dict[str, Any]) -> str:
    """条目可匹配文本 = 标题 + 最小检索片段 + 登记的 query_terms。"""

    return " ".join(
        [
            str(entry.get("title") or ""),
            str(entry.get("retrieval_excerpt") or ""),
            " ".join(str(term) for term in (entry.get("query_terms") or [])),
        ]
    ).lower()


def _query_tokens(request: dict[str, Any]) -> set[str]:
    """相关词来自问题文本与受控词表；公司代码和行业只作缩小范围的辅助词。

    case_id 不再作为词来源：它匹配不到任何条目正文，只会污染排序。
    """

    raw = " ".join(
        [
            str(request.get("query_text") or ""),
            str(request.get("question_text") or ""),
            str(request.get("ticker") or ""),
            str(request.get("industry") or ""),
        ]
    )
    tokens = _tokens_from_text(raw)
    return tokens | controlled_question_terms(str(request.get("question_id") or ""))


def _claim_scope(entry: dict[str, Any], request: dict[str, Any]) -> tuple[str, str]:
    """给每个命中标明可支持的语义边界，禁止把类比材料变成当前企业事实。"""
    category = str(entry.get("source_category") or "")
    if category == "annual_report":
        ticker = str(entry.get("ticker") or "")
        company = str(entry.get("company_name") or "")
        if (ticker and ticker == str(request.get("ticker") or "")) or (
            company and company == str(request.get("company_name") or "")
        ):
            return "case_fact", "可作为当前案例事实的原文定位；仍须通过现有证据白名单校验。"
        return "case_fact_prohibited", "其他企业年报不能证明当前案例事实。"
    if category in {"accounting_standard", "auditing_standard", "tax_regulation"}:
        return "procedure_guidance", "仅支持审计程序、准则或法规依据，不支持当前企业事实。"
    return "contextual_hypothesis_only", "处罚、问询、行业、新闻与宏观材料仅作类比或待验证背景，不支持当前企业事实。"


def retrieve_knowledge(
    entries: list[dict[str, Any]],
    request: dict[str, Any],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """在本地来源清单的最小检索片段中做可复现检索，返回可导出的命中轨迹。

    该函数不下载网页、不把整篇文档交给模型。命中先由来源范围、截止日和
    相关性门禁决定，权威等级只用于同等相关度之间定序；零词命中条目不得成为
    证据候选。命中带回 URL、定位、摘要哈希与相关词数供人工复查。
    """
    allowed_categories = set(request.get("source_categories") or [])
    active = active_source_entries(entries, request.get("cutoff_date"))
    candidates = [entry for entry in active if entry.get("source_category") in allowed_categories]
    ranked = rank_candidates(candidates, request)
    tokens = {token for token in _query_tokens(request) if token}
    if limit <= 0 or not tokens:
        # limit=0 与无问题词都表示"不要结果"，不能强行凑出一条无关条目。
        return []

    scored: list[tuple[int, int, int, dict[str, Any]]] = []
    for ordinal, entry in enumerate(ranked):
        searchable = _searchable_text(entry)
        matches = sum(1 for token in tokens if token in searchable)
        if matches == 0:
            continue
        if _claim_scope(entry, request)[0] == "case_fact_prohibited":
            # 其他企业年报既不能证明当前案例事实，也不该占用本次上下文预算。
            continue
        layer = str(entry.get("layer") or LAYER_BY_CATEGORY.get(str(entry.get("source_category") or ""), "case_evidence"))
        scored.append((-matches, -AUTHORITY_RANK.get(layer, 0), ordinal, entry))
    scored.sort(key=lambda item: item[:3])

    hits: list[dict[str, Any]] = []
    for matches, _authority, ordinal, entry in scored[:limit]:
        excerpt = str(entry.get("retrieval_excerpt") or entry.get("title") or "").strip()
        locator = str(entry.get("retrieval_locator") or "官方来源登记条目；请回到原文核验。")
        content_sha256 = str(entry.get("excerpt_sha256") or "").strip() or hashlib.sha256(
            excerpt.encode("utf-8")
        ).hexdigest()
        scope, boundary = _claim_scope(entry, request)
        retrieval_seed = json.dumps(
            {
                "source_id": entry.get("source_id"),
                "case_id": request.get("case_id"),
                "question_id": request.get("question_id"),
                "snapshot_id": request.get("snapshot_id"),
                "ordinal": ordinal,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        hits.append(
            {
                "schema_version": KNOWLEDGE_RETRIEVAL_SCHEMA_VERSION,
                "retrieval_id": "KB-" + hashlib.sha256(retrieval_seed.encode("utf-8")).hexdigest()[:12].upper(),
                "evidence_id": "KB-" + str(entry.get("source_id") or "UNKNOWN"),
                "source_id": entry.get("source_id"),
                "document_id": entry.get("document_id"),
                "source_category": entry.get("source_category"),
                "publisher": entry.get("publisher"),
                "published_at": entry.get("published_at"),
                "official_url": entry.get("official_url"),
                "locator": locator,
                "excerpt": excerpt[:800],
                "content_sha256": content_sha256,
                "support_status": "candidate",
                "relevance_matches": -matches,
                "retrieval_version": KNOWLEDGE_RETRIEVAL_VERSION,
                "claim_scope": scope,
                "boundary": boundary,
                "snapshot_id": request.get("snapshot_id"),
            }
        )
    return hits


def build_retrieval_request(
    *,
    case_id: str,
    question_id: str,
    source_categories: list[str],
    as_of_date: str,
    cutoff_date: str | None,
    snapshot_id: str,
    ticker: str | None = None,
    industry: str | None = None,
    query_text: str = "",
) -> dict[str, Any]:
    """构造一次受约束检索请求；缺字段直接拒绝，不允许无边界检索。

    question_id 只是受控编号，query_text 才是相关性判定的问题文本。
    """
    categories = [category for category in source_categories if category in SOURCE_CATEGORIES]
    if not categories:
        raise ValueError("source_categories 必须至少包含一个已登记类别。")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of_date):
        raise ValueError("as_of_date 必须是 YYYY-MM-DD。")
    return {
        "case_id": case_id,
        "question_id": question_id,
        "query_text": str(query_text or ""),
        "source_categories": categories,
        "as_of_date": as_of_date,
        "cutoff_date": cutoff_date,
        "snapshot_id": snapshot_id,
        "ticker": ticker,
        "industry": industry,
    }


def rank_candidates(candidates: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    """按截止日过滤后：权威规则 > 案例证据 > 行业上下文，同层保持原顺序。"""
    allowed_layers = {cat for cat in (request.get("source_categories") or [])}
    allowed = set()
    from .knowledge_sources import LAYER_BY_CATEGORY

    for category in allowed_layers:
        allowed.add(LAYER_BY_CATEGORY.get(category, "case_evidence"))
    cutoff = request.get("cutoff_date")
    filtered = [item for item in candidates if item.get("source_category") in allowed_layers]
    if cutoff:
        filtered = filter_by_cutoff(filtered, cutoff)
    return sorted(
        filtered,
        key=lambda item: AUTHORITY_RANK.get(str(item.get("layer") or LAYER_BY_CATEGORY.get(str(item.get("source_category") or ""), "case_evidence")), 0),
        reverse=True,
    )


def normalize_retrieval_hit(raw: dict[str, Any]) -> dict[str, Any]:
    """把检索命中规范化为合同结构；缺失字段置 null，未登记类别置失败。"""
    hit = {field: raw.get(field) for field in REQUIRED_RETRIEVAL_FIELDS}
    if not hit["retrieval_id"]:
        hit["retrieval_id"] = "RET-" + hashlib.sha256(
            json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12].upper()
    schema_version = raw.get("schema_version")
    if schema_version not in (None, "knowledge_retrieval_v1"):
        hit["schema_version"] = schema_version
    else:
        hit["schema_version"] = "knowledge_retrieval_v1"
    if str(hit.get("support_status") or "") not in {"supported", "candidate", "unverified_hypothesis"}:
        hit["support_status"] = "candidate"
    return hit
