"""统计每个登记报告的金额行币种证据状态；只做抽取，不跑关系。"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectivity_extraction import extract_document, load_registry  # noqa: E402
from app.connectivity_engine import numeric_unit  # noqa: E402


def main() -> int:
    rows = []
    for doc in load_registry(ROOT):
        occurrences, coverage, exclusions = extract_document(ROOT, doc, ["research", "environment", "intensity"])
        money = [row for row in occurrences if "money" in numeric_unit(row.unit)[0]]
        status = Counter(row.currency_status for row in money)
        rows.append({"document_id": doc.document_id, "money_rows": len(money),
                     "unknown": status.get("unknown", 0),
                     "explicit": status.get("explicit", 0), "table": status.get("table", 0),
                     "report_declaration": status.get("report_declaration", 0),
                     "exclusions": len(exclusions),
                     "injection_exclusions": sum(1 for item in exclusions if "INJ" in item.occurrence_id)})
    total_money = sum(row["money_rows"] for row in rows)
    total_unknown = sum(row["unknown"] for row in rows)
    payload = {"documents": rows, "money_rows": total_money, "unknown": total_unknown,
               "unknown_ratio": round(total_unknown / total_money, 4) if total_money else None}
    Path(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"money_rows": total_money, "unknown": total_unknown,
                      "unknown_ratio": payload["unknown_ratio"]}, ensure_ascii=False))
    for row in rows:
        print(f'{row["document_id"]}: money={row["money_rows"]} unknown={row["unknown"]} '
              f'explicit={row["explicit"]} table={row["table"]} report={row["report_declaration"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
