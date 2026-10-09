"""只读检查扩展年报的当前抽取结果，不写案例或触发模型。"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
import pymupdf as fitz
from backend.app.field_extraction import FIELD_CONFIG, find_financial_candidate
from backend.app.company_discovery import EXPANDED_TICKERS


def main():
    target = ROOT / "outputs" / "决赛整改_2026-10-09"
    target.mkdir(parents=True, exist_ok=True)
    seed = json.loads((ROOT / "backend/cache_seed.materialized.json").read_text(encoding="utf-8"))
    records = []
    for case in seed["cases"]:
        if case["ticker"] not in EXPANDED_TICKERS:
            continue
        for document in case["documents"]:
            path = ROOT / "backend/runtime/cases" / case["case_id"] / "documents" / (document["document_id"] + ".pdf")
            if not path.is_file():
                continue
            with fitz.open(path) as pdf:
                pages = [p.get_text("text") for p in pdf]
                for kind in ("revenue", "accounts_receivable"):
                    candidate = find_financial_candidate(pdf, pages, FIELD_CONFIG[kind], int(document["report_year"]))
                    record = {"case_id": case["case_id"], "ticker": case["ticker"], "document_id": document["document_id"], "document_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "year": document["report_year"], "field_kind": kind, "old": [r for r in case["financial_fields"] if r["year"] == document["report_year"] and r["field_kind"] == kind], "candidate": candidate}
                    records.append(record)
                    print(case["ticker"], document["report_year"], kind, {k: candidate.get(k) for k in ("page", "value", "unit", "column_identity")} if candidate else None)
    filename = sys.argv[1] if len(sys.argv) > 1 else "抽取修改前.json"
    (target / filename).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
