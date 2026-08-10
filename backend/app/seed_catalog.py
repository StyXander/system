"""Read-only public catalog fallback for deployments without local runtime files.

Render intentionally does not receive ``backend/runtime`` because that folder
contains large PDFs and writable indexes.  The tracked materialized seed keeps
the verified company cards, official document URLs and field candidates, so a
temporary Supabase outage does not leave the whole UI in an endless loading
state.  It is public CNINFO data only; tenant-owned rows are never read here.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SEED_FILENAME = "cache_seed.materialized.json"


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
        "pdf_policy": "official_source_url_on_demand",
    }
