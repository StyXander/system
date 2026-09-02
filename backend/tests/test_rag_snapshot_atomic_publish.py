"""RAG generation/staging 与发布 RPC 的离线合同验收。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from backend.app import supabase_adapter


def _chunks(count: int = 205) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": f"CHUNK-{index:04d}",
            "document_id": "DOC-1",
            "pdf_page": index + 1,
            "content": f"第 {index} 页资产负债表原文。",
            "metadata": {
                "title": "资产负债表",
                "source_sha256": "A" * 64,
                "disclosure_date": "2026-03-01",
                "report_year": 2025,
                "company_name": "测试公司",
                "ticker": "000001",
            },
        }
        for index in range(count)
    ]


def _snapshot_id(chunks: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda item: item["chunk_id"]):
        digest.update(json.dumps(chunk, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\0")
    return f"RAG-SNAPSHOT-{digest.hexdigest()[:24].upper()}"


def _client(monkeypatch: pytest.MonkeyPatch) -> supabase_adapter.SupabaseClient:
    client = supabase_adapter.SupabaseClient.__new__(supabase_adapter.SupabaseClient)
    monkeypatch.setattr(client, "get_case_metadata", lambda case_id, tenant_id=None: {
        "case_id": case_id,
        "case_scope": f"PUBLIC:{case_id}",
        "tenant_id": None,
    })
    return client


def test_failed_second_staging_batch_does_not_touch_old_active(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    old = [{**chunk, "rag_snapshot_id": "RAG-SNAPSHOT-OLD", "active": True} for chunk in _chunks()]
    inserted: list[list[dict[str, Any]]] = []
    calls = {"count": 0}

    monkeypatch.setattr(client, "get_active_rag_chunks", lambda **kwargs: old)

    def insert(_table: str, rows: list[dict[str, Any]], **kwargs: Any) -> None:
        calls["count"] += 1
        inserted.append(rows)
        if calls["count"] == 2:
            raise supabase_adapter.SupabaseRequestError("模拟第二批失败")

    monkeypatch.setattr(client, "insert_table", insert)
    with pytest.raises(supabase_adapter.SupabaseRequestError):
        client.persist_rag_chunks(case_id="CASE-1", tenant_id=None, chunks=_chunks())
    assert len(inserted) == 2
    assert all(row["active"] is False for batch in inserted for row in batch)
    assert all(row["active"] for row in old)


def test_same_complete_snapshot_is_idempotent_without_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = _chunks()
    snapshot = _snapshot_id(chunks)
    client = _client(monkeypatch)
    monkeypatch.setattr(client, "get_active_rag_chunks", lambda **kwargs: [{**chunk, "rag_snapshot_id": snapshot} for chunk in chunks])
    monkeypatch.setattr(client, "insert_table", lambda *_args, **_kwargs: pytest.fail("完整同快照不应再次 staging"))
    result = client.persist_rag_chunks(case_id="CASE-1", tenant_id=None, chunks=chunks)
    assert result["idempotent"] is True
    assert result["rag_snapshot_id"] == snapshot


def test_schema_publish_rpc_is_locked_and_service_only() -> None:
    # 测试可以从项目根目录或 backend 目录启动，不能依赖当前工作目录。
    workspace_root = Path(__file__).resolve().parents[2]
    sql = (workspace_root / "supabase" / "schema.sql").read_text(encoding="utf-8")
    assert "generation_id text not null" in sql
    assert "pg_advisory_xact_lock(hashtextextended(p_case_scope, 0))" in sql
    assert "staged_count <> p_expected_count" in sql
    assert "revoke all on function public.publish_rag_snapshot(text, text, text, integer)" in sql
    assert "grant execute on function public.publish_rag_snapshot(text, text, text, integer) to service_role" in sql
    assert "grant execute on function public.publish_rag_snapshot(text, text, text, integer) to anon" not in sql
