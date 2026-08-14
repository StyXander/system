"""Build the small, public metadata seed used by the Render demo.

The verified CNINFO cache contains large PDFs and FAISS indexes under
``backend/runtime``; that directory is intentionally ignored by Git.  The
public deployment still needs the validated case cards and extracted field
candidates, so this script copies only JSON metadata, field evidence and
official source URLs into a tracked seed file.  No PDF bytes or local paths
are included.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.rag import RAG_QUESTIONS, _anchor_score, _keyword_score, _matched_excerpt, _tokens, export_chunks  # noqa: E402
from backend.app.cases import annotate_financial_field_rows_quality  # noqa: E402


LOCK_PATH = ROOT / "backend" / "cache_seed.lock.json"
CASES_ROOT = ROOT / "backend" / "runtime" / "cases"
OUTPUT_PATH = ROOT / "backend" / "cache_seed.materialized.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _public_document(document: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: document.get(key)
        for key in (
            "document_id",
            "document_type",
            "report_year",
            "disclosure_date",
            "announcement_date",
            "announcement_title",
            "source_url",
            "sha256",
            "file_sha256",
            "byte_count",
            "page_count",
            "validation_status",
            "source_mode",
        )
        if document.get(key) is not None
    }
    # Only official CNINFO final-page URLs are allowed into the seed.  The
    # runtime path and PDF filename are deployment-local and must never leak.
    if not str(result.get("source_url") or "").startswith("https://static.cninfo.com.cn/finalpage/"):
        raise ValueError(f"非官方来源 URL：{result.get('source_url')!r}")
    return result


def _public_field(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in (
        "source_file",
        "storage_relpath",
        "storage_object_path",
        "original_source_file",
        "candidate_urls",
    ):
        result.pop(key, None)
    # Evidence excerpts are useful for the public pre-screen but are bounded
    # to prevent an accidental full-document copy into the tracked seed.
    excerpt = result.get("raw_excerpt")
    if isinstance(excerpt, str) and len(excerpt) > 1200:
        result["raw_excerpt"] = excerpt[:1200]
    return result


def _demo_rag_evidence(case: dict[str, Any]) -> list[dict[str, Any]]:
    """为竞赛站点保留少量可回页原文，不把整本年报或完整索引打进仓库。"""

    case_id = str(case.get("case_id") or "")
    chunks = export_chunks(ROOT, case_id)
    evidence: list[dict[str, Any]] = []
    for question in RAG_QUESTIONS:
        query_tokens = set(_tokens(str(question["retrieval_query"])))
        ranked: list[tuple[float, dict[str, Any]]] = []
        for chunk in chunks:
            metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
            disclosure_date = str(metadata.get("disclosure_date") or "")
            if case.get("t0") and disclosure_date > str(case["t0"]):
                continue
            searchable = f"{metadata.get('title', '')} {chunk.get('content', '')}"
            anchor_score = _anchor_score(list(question["anchor_terms"]), searchable)
            if anchor_score <= 0:
                continue
            keyword_score = _keyword_score(query_tokens, searchable)
            excerpt, excerpt_start, excerpt_end = _matched_excerpt(
                str(chunk.get("content") or ""),
                list(question["anchor_terms"]),
            )
            score = round(anchor_score * 0.65 + keyword_score * 0.35, 6)
            ranked.append(
                (
                    score,
                    {
                        "question_id": question["question_id"],
                        "evidence_id": f"RAG-{chunk['chunk_id']}",
                        "chunk_id": chunk["chunk_id"],
                        "document_id": chunk["document_id"],
                        "score": score,
                        "vector_score": None,
                        "keyword_score": round(keyword_score, 6),
                        "anchor_score": round(anchor_score, 6),
                        # 部署种子不保留本机文件名或路径，来源阅读器按文档编号回到巨潮原件。
                        "source_file": chunk["document_id"],
                        "source_sha256": metadata.get("source_sha256"),
                        "disclosure_date": disclosure_date,
                        "report_year": metadata.get("report_year"),
                        "pdf_page": chunk.get("pdf_page"),
                        "print_page": None,
                        "linked_field_evidence_ids": [],
                        "source_locator": f"PDF 第 {chunk.get('pdf_page')} 页 / {chunk['chunk_id']}",
                        "title": metadata.get("title") or "年报原文",
                        "excerpt": excerpt,
                        "excerpt_char_start": excerpt_start,
                        "excerpt_char_end": excerpt_end,
                        "chunk_char_length": len(str(chunk.get("content") or "")),
                        "excerpt_is_verbatim": True,
                        "review_status": "demo_candidate_fragment_pending_human_page_review",
                    },
                )
            )
        ranked.sort(key=lambda item: (item[0], item[1]["chunk_id"]), reverse=True)
        evidence.extend(item for _, item in ranked[:2])
    return evidence


def build() -> dict[str, Any]:
    lock = _read_json(LOCK_PATH)
    entries = lock.get("entries") if isinstance(lock, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("cache_seed.lock.json 没有可用 entries")

    local_cases: dict[str, dict[str, Any]] = {}
    local_fields: dict[str, list[dict[str, Any]]] = {}
    for case_path in CASES_ROOT.glob("*/case.json"):
        case = _read_json(case_path)
        case_id = str(case.get("case_id") or "")
        if case_id:
            local_cases[case_id] = case
            fields_path = case_path.with_name("financial_fields.json")
            if fields_path.is_file():
                fields = _read_json(fields_path)
                local_fields[case_id] = fields if isinstance(fields, list) else []

    cases: list[dict[str, Any]] = []
    for entry in entries:
        case_id = str(entry.get("case_id") or "")
        case = local_cases.get(case_id)
        if not case:
            raise ValueError(f"锁定清单案例未找到本地 JSON：{case_id}")
        if (
            case.get("registry_mode") != "cninfo_official_auto"
            or case.get("sample_type") != "public"
            or not case_id.startswith("CNINFO_")
        ):
            raise ValueError(f"案例不是可信公开巨潮案例：{case_id}")
        documents = [_public_document(item) for item in case.get("documents", [])]
        if not documents:
            raise ValueError(f"案例没有年报文档：{case_id}")
        fields = [
            _public_field(item)
            for item in annotate_financial_field_rows_quality(
                row for row in local_fields.get(case_id, []) if isinstance(row, dict)
            )
        ]
        public_case = {
            key: case.get(key)
            for key in (
                "schema_version",
                "case_id",
                "company_name",
                "company_alias",
                "ticker",
                "org_id",
                "market",
                "t0",
                "currency",
                "amount_unit",
                "statement_scope",
                "sample_type",
                "model_transfer_allowed",
                "retention_expires_at",
                "legal_sample_confirmation_status",
                "source_snapshot_id",
                "source_review_status",
                "available_report_years",
                "available_years",
                "three_year_r1_ready",
                "registry_mode",
                "financial_fields_status",
                "human_confirmed_available_years",
                "human_confirmed_three_year_r1_ready",
                "industry",
                "industry_name",
            )
            if case.get(key) is not None
        }
        public_case["tenant_id"] = None
        public_case["owner_org_id"] = None
        public_case["owner_user_id"] = None
        public_case["documents"] = documents
        public_case["financial_fields"] = fields
        public_case["structured_evidence"] = fields
        public_case["seed_materialization"] = "verified_metadata_with_unconfirmed_field_candidates_no_pdf"
        public_case["seed_snapshot_id"] = entry.get("snapshot_id")
        public_case["seed_source_fingerprint"] = entry.get("source_fingerprint")
        public_case["seed_rag"] = entry.get("rag") or {}
        public_case["demo_rag_evidence"] = _demo_rag_evidence(case)
        cases.append(public_case)

    cases.sort(key=lambda item: (str(item.get("company_name") or ""), str(item.get("ticker") or "")))
    return {
        "schema_version": "cninfo_public_catalog_seed_v1",
        "description": "已校验巨潮公开年报的可部署元数据、待人工回页字段候选与少量原文片段；不包含 PDF、FAISS 或本机路径。",
        "source": "backend/cache_seed.lock.json + backend/runtime/cases",
        "company_count": len(cases),
        "ready_count": sum(1 for item in cases if item.get("documents") and item.get("financial_fields")),
        "cases": cases,
    }


def main() -> None:
    payload = build()
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_PATH), "company_count": payload["company_count"], "ready_count": payload["ready_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
