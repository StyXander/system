"""原文阅读回归：真实页图、哈希验证、页码、旧文件与访问权限。"""

import hashlib
import pymupdf
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.app import main, cases
from backend.app.source_viewer import preview_path, source_page_response


@pytest.fixture
def registered_pdf(tmp_path):
    path = tmp_path / "report.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((30, 40), "Original page one")
        pdf.new_page().insert_text((30, 40), "Original page two")
        pdf.save(path)
    return path, {"document_id": "DOC", "source_file": "report.pdf", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_actual_page_is_rendered_with_correct_text_and_navigation(registered_pdf):
    path, document = registered_pdf
    response = source_page_response(path, document, 2, "/api/cases/PRIVATE/sources/DOC")
    text = response.body.decode()
    assert response.media_type == "text/html"
    assert "data:image/png;base64," in text
    assert "Original page two" in text and "Original page one" not in text
    assert "PDF 第 2 页 / 共 2 页" in text
    assert "page=1" in text and "下一页" not in text
    assert response.headers["cache-control"] == "no-store"
    assert "style-src 'nonce-" in response.headers["content-security-policy"]


def test_page_outside_original_is_rejected(registered_pdf):
    path, document = registered_pdf
    with pytest.raises(HTTPException) as error:
        source_page_response(path, document, 3, "/source")
    assert error.value.status_code == 404


def test_hash_mismatch_is_not_repaired_or_shown(registered_pdf, tmp_path):
    path, document = registered_pdf
    assert preview_path(tmp_path, document, path, public=False) == path
    original = path.read_bytes()
    with pytest.raises(HTTPException) as error:
        preview_path(tmp_path, {**document, "sha256": "0" * 64}, path, public=True)
    assert error.value.status_code == 409
    assert path.read_bytes() == original


def test_unregistered_remote_host_is_rejected(tmp_path):
    with pytest.raises(HTTPException) as error:
        preview_path(tmp_path, {"sha256": "0" * 64, "source_url": "https://internal.example/report.pdf"}, None, public=True)
    assert error.value.status_code == 404


def test_private_missing_original_does_not_download(tmp_path):
    with pytest.raises(HTTPException) as error:
        preview_path(tmp_path, {"sha256": "0" * 64}, None, public=False)
    assert error.value.status_code == 404


def test_reading_and_raw_routes_keep_authorization(monkeypatch, registered_pdf):
    path, document = registered_pdf
    case = {"case_id": "PRIVATE", "sample_type": "authorized_deidentified", "documents": [document]}
    calls = []
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    monkeypatch.setattr(main, "_case_record", lambda *a, **kw: case)
    monkeypatch.setattr(main, "authorize_case_access", lambda request, record: calls.append(record["case_id"]))
    monkeypatch.setattr(main, "_materialized_case_for_resolved", lambda *a, **kw: case)
    monkeypatch.setattr(main, "resolve_case_document", lambda root, cid, did, **kw: (path, document) if did == "DOC" else None)
    client = TestClient(main.app)
    response = client.get("/api/cases/PRIVATE/sources/DOC?view=true&page=2")
    assert response.status_code == 200 and "Original page two" in response.text
    raw = client.get("/api/cases/PRIVATE/sources/DOC")
    assert raw.headers["content-disposition"].startswith("inline;")
    assert raw.content == path.read_bytes()
    assert calls == ["PRIVATE", "PRIVATE"]
    assert client.get("/api/cases/PRIVATE/sources/UNKNOWN?view=true").status_code == 404
    assert client.get("/api/cases/PRIVATE/sources/DOC?view=true&page=0").status_code == 422
