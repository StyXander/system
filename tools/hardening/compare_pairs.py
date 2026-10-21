"""比较修改前后的 5 个真实报告对结果，输出可复核的对照表。"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    before = {row["pair_id"] or key: row for key, row in enumerate(load(sys.argv[1])["pairs"])}
    after_rows = load(sys.argv[2])["pairs"]
    order = ["000858-2025", "000333-2025", "300750-2025", "600019-2025", "600019-2024"]
    before_list = load(sys.argv[1])["pairs"]
    out = []
    for index, pair in enumerate(order):
        b = before_list[index]
        a = after_rows[index]
        out.append({
            "pair": pair,
            "checks_before": b["checks"], "checks_after": a["checks"],
            "formal_before": b["formal"], "formal_after": a["formal"],
            "assumption_before": b["assumption_compatible"], "assumption_after": a["assumption_compatible"],
            "unexplained_before": b["unexplained_difference"], "unexplained_after": a["unexplained_difference"],
            "rejections_before": b["rejections"], "rejections_after": a["rejections"],
            "reject_top_before": list(b["rejection_reasons"].items())[:2],
            "reject_top_after": list(a["rejection_reasons"].items())[:2],
            "currency_unknown_before": b["currency_unknown"], "currency_unknown_after": a["currency_unknown"],
            "money_rows": b["money_rows"],
            "conditions_before": b["conditions"], "conditions_after": a["conditions"],
            "titles_after": [c["title"] for c in a["checks_brief"]],
            "titles_before": [c["title"] for c in b["checks_brief"]],
        })
    total = lambda key, rows: sum(row[key] for row in rows)  # noqa: E731
    summary = {
        "checks_before": sum(r["checks_before"] for r in out), "checks_after": sum(r["checks_after"] for r in out),
        "formal_before": sum(r["formal_before"] for r in out), "formal_after": sum(r["formal_after"] for r in out),
        "assumption_before": sum(r["assumption_before"] for r in out),
        "assumption_after": sum(r["assumption_after"] for r in out),
        "unexplained_before": sum(r["unexplained_before"] for r in out),
        "unexplained_after": sum(r["unexplained_after"] for r in out),
        "rejections_before": sum(r["rejections_before"] for r in out),
        "rejections_after": sum(r["rejections_after"] for r in out),
        "currency_unknown_before": sum(r["currency_unknown_before"] for r in out),
        "currency_unknown_after": sum(r["currency_unknown_after"] for r in out),
        "money_rows": sum(r["money_rows"] for r in out),
    }
    payload = {"summary": summary, "pairs": out}
    Path(sys.argv[3]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for row in out:
        print(f'{row["pair"]}: checks {row["checks_before"]}->{row["checks_after"]} '
              f'reject {row["rejections_before"]}->{row["rejections_after"]} '
              f'currency? {row["currency_unknown_before"]}->{row["currency_unknown_after"]}/{row["money_rows"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
