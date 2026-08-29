"""Read-only public catalog fallback for deployments without local runtime files.

Render intentionally does not receive ``backend/runtime`` because that folder
contains large PDFs and writable indexes.  The tracked materialized seed keeps
the verified company cards, official document URLs and field candidates, so a
temporary Supabase outage does not leave the whole UI in an endless loading
state.  It is public CNINFO data only; tenant-owned rows are never read here.
"""

from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from .rag import QUESTION_SET_VERSION, RETRIEVAL_VERSION, _get_question, _keyword_score, _tokens


SEED_FILENAME = "cache_seed.materialized.json"
_DEMO_RETRIEVALS: dict[str, dict[str, Any]] = {}
_DEMO_RETRIEVALS_LOCK = threading.Lock()


def _seed_path(workspace_root: Path) -> Path:
    return workspace_root / "backend" / SEED_FILENAME


def load_seed_cases(workspace_root: Path) -> list[dict[str, Any]]:
    path = _seed_path(workspace_root)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        return []
    result: list[dict[str, Any]] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "").strip().upper()
        if not case_id.startswith("CNINFO_") or item.get("sample_type") != "public":
            continue
        if str(item.get("registry_mode") or "") != "cninfo_official_auto":
            continue
        case = deepcopy(item)
        # The seed is a global public scope.  Never let a copied JSON value turn
        # it into a tenant-owned record or expose an old local owner.
        case["case_id"] = case_id
        case["tenant_id"] = None
        case.pop("owner_org_id", None)
        case.pop("owner_user_id", None)
        case.setdefault("case_scope", f"PUBLIC:{case_id}")
        case.setdefault("source_review_status", "cninfo_fields_candidate_pending_human_professional_confirmation")
        case.setdefault("financial_fields", [])
        case.setdefault("documents", [])
        case["seed_materialization"] = "verified_metadata_and_fields_no_pdf"
        result.append(case)
    return result


def get_seed_case(workspace_root: Path, case_id: str) -> dict[str, Any] | None:
    normalized = str(case_id or "").strip().upper()
    return next((case for case in load_seed_cases(workspace_root) if case.get("case_id") == normalized), None)


def seed_catalog_summary(workspace_root: Path) -> dict[str, Any]:
    cases = load_seed_cases(workspace_root)
    return {
        "status": "ready" if cases else "missing",
        "source": "tracked_verified_cninfo_seed",
        "case_count": len(cases),
        "field_case_count": sum(1 for case in cases if case.get("financial_fields")),
        "rag_case_count": sum(1 for case in cases if case.get("demo_rag_evidence")),
        "pdf_policy": "official_source_url_on_demand",
    }


def seed_rag_status(case: dict[str, Any]) -> dict[str, Any]:
    """返回随部署种子携带的轻量 RAG 状态，明确区别于完整 FAISS 索引。"""

    evidence = case.get("demo_rag_evidence") if isinstance(case.get("demo_rag_evidence"), list) else []
    seed = case.get("seed_rag") if isinstance(case.get("seed_rag"), dict) else {}
    return {
        "status": "ready" if evidence else "not_built",
        "source_status": "source_available" if evidence else "source_missing",
        "index_status": "seed_snapshot" if evidence else "not_built",
        "runtime_ready": bool(evidence),
        "case_id": case.get("case_id"),
        "company_name": case.get("company_name"),
        "index_version": seed.get("index_version"),
        "source_fingerprint": seed.get("source_fingerprint"),
        "chunk_count": int(seed.get("chunk_count") or 0),
        "demo_excerpt_count": len(evidence),
        "built_at": seed.get("built_at"),
        "retrieval_mode": "tracked_demo_excerpts",
        "boundary": "竞赛演示使用冻结索引中预先筛选的少量可回页片段；不是整本年报全文检索服务。",
    }


def retrieve_seed_rag(
    case: dict[str, Any],
    *,
    query: str,
    t0: str,
    rule_id: str,
    top_k: int,
    question_id: str | None,
) -> dict[str, Any]:
    """在只读演示片段中检索，并保留与正式 RAG 相同的证据返回合同。"""

    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
        raise ValueError("top_k 必须是 1 至 10 的整数")
    question = _get_question(question_id)
    if question and rule_id not in question["rule_ids"]:
        raise ValueError(f"{question_id} 不属于规则 {rule_id}")
    effective_query = str(question.get("retrieval_query") if question else query).strip()
    if not effective_query:
        raise ValueError("检索词不能为空")
    rows = [
        deepcopy(item)
        for item in (case.get("demo_rag_evidence") or [])
        if isinstance(item, dict)
        and str(item.get("disclosure_date") or "") <= t0
        and (not question_id or item.get("question_id") == question_id)
    ]
    if not question_id:
        query_tokens = set(_tokens(effective_query))
        for item in rows:
            item["score"] = round(_keyword_score(query_tokens, f"{item.get('title', '')} {item.get('excerpt', '')}"), 6)
        rows = [item for item in rows if float(item.get("score") or 0) > 0]
    for item in rows:
        score = float(item.get("score") or 0)
        item["low_confidence"] = score < 0.50
        item["confidence_note"] = "低置信候选，必须回原页复核。" if score < 0.50 else "候选片段仍须回原页复核。"
    rows.sort(key=lambda item: (float(item.get("score") or 0), str(item.get("chunk_id") or "")), reverse=True)
    results = rows[:top_k]
    retrieval_id = f"RET-DEMO-{uuid.uuid4().hex[:12].upper()}"
    record = {
        "retrieval_id": retrieval_id,
        "case_id": case.get("case_id"),
        "status": "hit" if results else "no_hit",
        "question_set_version": QUESTION_SET_VERSION if question else None,
        "retrieval_version": RETRIEVAL_VERSION,
        "question": dict(question) if question else None,
        "effective_query": effective_query,
        "boundary": "竞赛演示返回已锁定的候选原文片段；仍须按文档编号和 PDF 页码回看巨潮原件。",
        "filter": {
            "case_id": case.get("case_id"),
            "company_name": case.get("company_name"),
            "t0_lte": t0,
            "rule_id": rule_id,
            "retrieval_mode": "tracked_demo_excerpts",
        },
        "evidence_gap": {
            "status": "retrieval_no_hit" if not results else "candidate_fragments_found",
            "label": "资料缺口候选 - 演示片段未命中" if not results else "已返回候选原文片段",
            "message": (
                question["no_hit_prompt"]
                if question and not results
                else "当前演示片段没有命中；不能据此认定年报未披露。"
                if not results
                else "命中只表示候选片段；是否形成资料缺口仍须人工回页确认。"
            ),
            "requires_human_confirmation": True,
            "auto_sync_to_risk_card": False,
        },
        "results": results,
    }
    with _DEMO_RETRIEVALS_LOCK:
        _DEMO_RETRIEVALS[retrieval_id] = deepcopy(record)
    return record


def get_seed_retrieval(retrieval_id: str) -> dict[str, Any] | None:
    with _DEMO_RETRIEVALS_LOCK:
        record = _DEMO_RETRIEVALS.get(retrieval_id)
    return deepcopy(record) if record else None
