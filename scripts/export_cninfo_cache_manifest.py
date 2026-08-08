"""Export a reproducible lock manifest for the verified CNINFO cache.

The manifest contains public-source metadata only. It intentionally excludes
PDFs, FAISS files, and the writable SQLite runtime directory.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_manifest(root: Path) -> dict[str, Any]:
    seed = _read_json(root / "backend" / "cache_seed.example.json")
    requested_years = [int(year) for year in range(2025, 2022, -1)]
    tickers = [str(item["ticker"]).zfill(6) for item in seed["companies"]]
    if len(tickers) != len(set(tickers)):
        raise ValueError("cache seed contains duplicate tickers")

    db_path = root / "backend" / "runtime" / "catalog.sqlite3"
    if not db_path.is_file():
        raise FileNotFoundError(f"verified runtime catalog not found: {db_path}")

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    entries: list[dict[str, Any]] = []
    try:
        for ticker in tickers:
            company = connection.execute(
                "SELECT ticker, company_name, company_alias, market, industry_family "
                "FROM companies WHERE ticker=?",
                (ticker,),
            ).fetchone()
            if company is None:
                raise ValueError(f"catalog company missing: {ticker}")

            snapshots = connection.execute(
                "SELECT snapshot_id, case_id, source_fingerprint, report_years_json, "
                "cache_status, rag_index_version, extractor_version, verified_at, updated_at "
                "FROM source_snapshots WHERE ticker=? AND cache_status='ready' "
                "ORDER BY verified_at DESC, updated_at DESC",
                (ticker,),
            ).fetchall()
            snapshot = next(
                (
                    row
                    for row in snapshots
                    if set(requested_years).issubset(set(_read_json_value(row["report_years_json"])))
                ),
                None,
            )
            if snapshot is None:
                raise ValueError(f"ready three-year snapshot missing: {ticker}")

            documents = connection.execute(
                "SELECT report_year, announcement_title, disclosure_date, source_url, sha256, "
                "byte_count, page_count, validation_status FROM report_documents "
                "WHERE case_id=? AND report_year IN (2025, 2024, 2023) "
                "ORDER BY report_year DESC",
                (snapshot["case_id"],),
            ).fetchall()
            if {int(row["report_year"]) for row in documents} != set(requested_years):
                raise ValueError(f"three-year document set missing: {ticker}")

            rag = connection.execute(
                "SELECT index_version, source_fingerprint, chunk_count, status, built_at "
                "FROM rag_manifests WHERE case_id=?",
                (snapshot["case_id"],),
            ).fetchone()
            gate = connection.execute(
                "SELECT gate_version, fit_level, industry_family, reporting_profile, "
                "allowed_rules_json, blocked_rules_json, reason_codes_json "
                "FROM industry_gate_results WHERE case_id=? AND snapshot_id=? "
                "ORDER BY evaluated_at DESC LIMIT 1",
                (snapshot["case_id"], snapshot["snapshot_id"]),
            ).fetchone()
            entry = {
                "ticker": company["ticker"],
                "company_name": company["company_name"],
                "company_alias": company["company_alias"],
                "market": company["market"],
                "industry_family": company["industry_family"],
                "case_id": snapshot["case_id"],
                "snapshot_id": snapshot["snapshot_id"],
                "source_fingerprint": snapshot["source_fingerprint"],
                "report_years": _read_json_value(snapshot["report_years_json"]),
                "cache_status": snapshot["cache_status"],
                "verified_at": snapshot["verified_at"],
                "rag_index_version": snapshot["rag_index_version"],
                "extractor_version": snapshot["extractor_version"],
                "documents": [dict(row) for row in documents],
                "rag": dict(rag) if rag else None,
                "industry_gate": _decode_gate(gate),
            }
            entries.append(entry)
    finally:
        connection.close()

    distribution = dict(sorted(Counter(entry["industry_family"] for entry in entries).items()))
    return {
        "schema_version": "cninfo_cache_seed_lock_v1",
        "description": "已校验巨潮公开年报热缓存的可复现元数据锁定清单；不包含 PDF、FAISS 或可写 runtime。",
        "source": "CNINFO official public reports",
        "requested_years": requested_years,
        "company_count": len(entries),
        "ready_count": sum(entry["cache_status"] == "ready" for entry in entries),
        "industry_distribution": distribution,
        "entries": entries,
    }


def _read_json_value(value: str | None) -> list[Any]:
    return json.loads(value or "[]")


def _decode_gate(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "gate_version": row["gate_version"],
        "fit_level": row["fit_level"],
        "industry_family": row["industry_family"],
        "reporting_profile": row["reporting_profile"],
        "allowed_rules": _read_json_value(row["allowed_rules_json"]),
        "blocked_rules": _read_json_value(row["blocked_rules_json"]),
        "reason_codes": _read_json_value(row["reason_codes_json"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write JSON to this path; stdout by default")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    payload = build_manifest(root)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
