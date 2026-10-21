"""诊断：打印某文档某页的表头与目标行，检查年度列绑定是否可靠。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectivity_extraction import PARSER_CACHE_VERSION, load_registry  # noqa: E402


def main() -> int:
    pair, page_no, needle = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    for doc in load_registry(ROOT):
        if doc.case_id != pair:
            continue
        path = ROOT / "backend/runtime/connectivity/extraction" / f"{doc.file_sha256}-{PARSER_CACHE_VERSION}.json"
        if not path.is_file():
            print("no cache", path.name)
            continue
        pages = json.loads(path.read_text(encoding="utf-8"))
        page = next(p for p in pages if p["page"] == page_no)
        print("== headers")
        for head in page.get("headers", []):
            print("  ", [round(v, 1) for v in head["bbox"]], repr(head["text"][:40]))
        print("== tables", len(page.get("tables", [])))
        for ti, table in enumerate(page.get("tables", [])):
            print("  table", ti, "bbox", [round(v, 1) for v in table["bbox"]])
            for head in table.get("headers", []):
                print("    H", [round(v, 1) for v in head["bbox"]], repr(head["text"][:40]))
        print("== lines containing", needle)
        for line in page.get("lines", []):
            if needle in line["text"]:
                print("  ", [round(v, 1) for v in line["bbox"]], repr(line["text"][:80]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
