from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.supabase_adapter import SupabaseUnavailable


class _UnavailableCatalogClient:
    def list_case_metadata(self, **_kwargs):
        raise SupabaseUnavailable("test outage")

    def get_case_bundle(self, *_args, **_kwargs):
        raise SupabaseUnavailable("test outage")

    def get_case_metadata(self, *_args, **_kwargs):
        raise SupabaseUnavailable("test outage")


def test_public_catalog_uses_verified_seed_when_supabase_is_temporarily_unavailable(monkeypatch):
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: _UnavailableCatalogClient())

    client = TestClient(main_module.app)
    listing = client.get("/api/cases")

    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["catalog"]["status"] == "degraded"
    assert body["catalog"]["seed"]["case_count"] == 50
    by_id = {item["case_id"]: item for item in body["cases"]}
    assert "CNINFO_002594_T0_20260327" in by_id
    assert by_id["CNINFO_002594_T0_20260327"]["ticker"] == "002594"

    detail = client.get("/api/cases/CNINFO_002594_T0_20260327")
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert detail_body["company_name"]
    assert len(detail_body["financial_fields"]) >= 6


def test_seed_file_contains_only_public_official_cases():
    from backend.app.seed_catalog import load_seed_cases

    cases = load_seed_cases(main_module.WORKSPACE_ROOT)
    assert len(cases) == 50
    assert all(case["sample_type"] == "public" for case in cases)
    assert all(case["registry_mode"] == "cninfo_official_auto" for case in cases)
    assert all(case["tenant_id"] is None for case in cases)
    assert all("storage_relpath" not in row for case in cases for row in case["financial_fields"])


def test_compact_case_catalog_keeps_details_out_of_initial_payload(monkeypatch):
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")

    response = TestClient(main_module.app).get("/api/cases?summary=true")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "case_list_summary_v1"
    assert len(json.dumps(body, ensure_ascii=False)) < 100_000
    assert "public" in response.headers.get("cache-control", "")
    assert all("financial_fields" not in item for item in body["cases"])
    assert all("documents" not in item for item in body["cases"])
    assert all({"case_id", "company_name", "ticker", "available_years"}.issubset(item) for item in body["cases"])

    detail = TestClient(main_module.app).get("/api/cases/CNINFO_002594_T0_20260327")
    assert detail.status_code == 200, detail.text
    assert "public" in detail.headers.get("cache-control", "")
    assert detail.json()["financial_fields"]
