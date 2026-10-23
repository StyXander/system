"""诊断：多年度表头导致的候选拒绝到底来自哪种年份绑定。只读不改库。"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectivity_extraction import extract_document, load_registry  # noqa: E402
from app.connectivity_pipeline import _ambiguous_column_header, _located  # noqa: E402


def main() -> int:
    pair = sys.argv[1] if len(sys.argv) > 1 else "000333-2025"
    docs = [doc for doc in load_registry(ROOT) if doc.case_id == pair]
    topics = ["research", "environment", "intensity"]
    for doc in docs:
        rows, coverage, exclusions = extract_document(ROOT, doc, topics)
        flagged = [row for row in rows if _ambiguous_column_header(row)]
        print(f"\n== {doc.document_id} rows={len(rows)} ambiguous={len(flagged)} located={len(list(_located(rows, doc.period)))}")
        print("year_status:", Counter((row.year, row.year_status) for row in flagged).most_common(6))
        for row in flagged[:8]:
            print("-", row.occurrence_id, "| year=", row.year, row.year_status,
                  "| value=", row.value, row.unit, "| label=", row.label[:28],
                  "| header=", (row.column_header or "")[:60], "| quality=", row.quality)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
