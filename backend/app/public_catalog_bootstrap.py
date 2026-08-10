"""Idempotently publish the tracked public catalog seed to Supabase.

The Render build has the verified metadata/field seed but not the ignored PDF
runtime.  Publishing only public cases, report metadata and field evidence lets
fresh web instances show the 50 companies immediately; PDF/RAG work remains
on-demand through the normal CNINFO pipeline.  A transient Supabase failure is
reported but does not make an otherwise healthy static demo fail its build;
the next deploy retries the same idempotent writes.
"""

from __future__ import annotations

import json
from pathlib import Path

from .seed_catalog import load_seed_cases
from .supabase_adapter import SupabaseError, get_supabase_client, supabase_enabled


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    cases = load_seed_cases(WORKSPACE_ROOT)
    if not cases:
        print(json.dumps({"status": "skipped", "reason": "seed_missing"}, ensure_ascii=False))
        return
    if not supabase_enabled():
        print(json.dumps({"status": "skipped", "reason": "persistence_not_supabase", "case_count": len(cases)}, ensure_ascii=False))
        return
    try:
        client = get_supabase_client()
    except SupabaseError as error:
        print(json.dumps({"status": "deferred", "reason": getattr(error, "code", "SUPABASE_ERROR"), "case_count": len(cases)}, ensure_ascii=False))
        return

    succeeded = 0
    failures: list[dict[str, str]] = []
    for case in cases:
        try:
            client.persist_case_metadata(
                workspace_root=WORKSPACE_ROOT,
                case=case,
                rows=case.get("financial_fields") or [],
                upload_private_documents=False,
            )
            succeeded += 1
        except SupabaseError as error:
            failures.append({"case_id": str(case.get("case_id") or ""), "code": getattr(error, "code", "SUPABASE_ERROR")})
    print(
        json.dumps(
            {
                "status": "ready" if succeeded == len(cases) else "partial",
                "case_count": len(cases),
                "succeeded": succeeded,
                "failed": len(failures),
                "failures": failures[:5],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
