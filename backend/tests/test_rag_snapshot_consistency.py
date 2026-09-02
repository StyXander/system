"""fresh-web RAG 必须使用 Supabase active snapshot，不能被旧本机索引遮蔽。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module


class _RemoteRagClient:
    def __init__(self) -> None:
        self.persisted: list[dict[str, Any]] = []

    def get_remote_rag_status(self, *, case_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        return {
            "status": "ready",
            "case_id": case_id,
            "rag_snapshot_id": "RAG-SNAPSHOT-REMOTE-B",
            "index_version": "rag-v1.2-case-isolated-hash-ngram-faiss-20260728",
            "chunk_count": 1,
        }

    def get_active_rag_chunks(self, *, case_id: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "rag_snapshot_id": "RAG-SNAPSHOT-REMOTE-B",
                "chunk_id": "REMOTE-B-001",
                "document_id": "DOC-1",
                "pdf_page": 1,
                "content": "资产负债表显示资产总额。",
                "metadata": {"company_name": "测试公司", "disclosure_date": "2026-03-01", "source_sha256": "abc"},
            }
        ]

    def persist_rag_retrieval(self, **payload: Any) -> None:
        self.persisted.append(payload)


def _case() -> dict[str, Any]:
    return {
        "case_id": "REMOTE_CASE",
        "tenant_id": None,
        "sample_type": "public",
        "company_name": "测试公司",
        "documents": [{"document_id": "DOC-1", "source_file": "report.pdf", "report_year": 2025}],
        "financial_fields": [],
    }


def test_supabase_rag_status_ignores_ready_local_index(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _RemoteRagClient()
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(main_module, "_case_record", lambda *_args, **_kwargs: _case())
    monkeypatch.setattr(main_module, "authorize_case_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "rag_status", lambda *_args, **_kwargs: pytest.fail("不应读取本机旧状态"))
    response = TestClient(main_module.app).get("/api/rag/status?case_id=REMOTE_CASE")
    assert response.status_code == 200, response.text
    assert response.json()["rag_snapshot_id"] == "RAG-SNAPSHOT-REMOTE-B"
    assert response.json()["persistence"]["cross_instance"] is True


def test_supabase_rag_retrieve_binds_actual_remote_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _RemoteRagClient()
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(main_module, "_case_record", lambda *_args, **_kwargs: _case())
    monkeypatch.setattr(main_module, "authorize_case_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "retrieve", lambda *_args, **_kwargs: pytest.fail("不应读取本机旧索引"))
    response = TestClient(main_module.app).post(
        "/api/rag/retrieve",
        json={"case_id": "REMOTE_CASE", "query": "资产", "top_k": 2},
    )
    assert response.status_code == 200, response.text
    assert fake.persisted
    assert fake.persisted[0]["rag_snapshot_id"] == "RAG-SNAPSHOT-REMOTE-B"
    assert response.json()["results"][0]["chunk_id"] == "REMOTE-B-001"
