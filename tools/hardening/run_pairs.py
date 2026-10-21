"""批量跑已登记报告对的纯规则核验，输出可比较的能力基线。

用途：修改前后各跑一次，比较 checks 数、正式结论数、候选拒绝原因、
条件状态分布与币种未知比例。只调用确定性链，不触网、不调模型。
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectivity_pipeline import run_pipeline  # noqa: E402
from app.connectivity_schemas import RunRequest  # noqa: E402


PAIRS = ["000858-2025", "000333-2025", "300750-2025", "600019-2025", "600019-2024"]


def summarize(run) -> dict:
    checks = run.checks
    levels = Counter()
    statuses = Counter()
    unresolved = Counter()
    conditions = Counter()
    currency_unknown = 0
    money_rows = 0
    for check in checks:
        levels[check.calculation.get("conclusion_level", "none")] += 1
        statuses[check.calculation_status] += 1
        for item in check.unresolved:
            unresolved[item.split("：")[0][:40]] += 1
        for condition in check.conditions:
            conditions[f"{condition.name}:{condition.status}"] += 1
    for row in run.occurrences:
        if row.currency is None:
            continue
        if "money" in str(row.unit):
            money_rows += 1
            if not row.currency:
                currency_unknown += 1
    return {
        "pair_id": run.versions.get("pair_id", ""),
        "occurrences": len(run.occurrences),
        "checks": len(checks),
        "formal": levels.get("formal_consistent", 0),
        "assumption_compatible": levels.get("assumption_compatible", 0),
        "unexplained_difference": levels.get("unexplained_difference", 0),
        "insufficient_basis": levels.get("insufficient_basis", 0),
        "not_comparable": levels.get("not_comparable", 0),
        "not_applicable": levels.get("not_applicable", 0),
        "calculation_status": dict(statuses),
        "levels": dict(levels),
        "conditions": dict(conditions),
        "unresolved_top": dict(unresolved.most_common(8)),
        "rejections": len(run.candidate_rejections),
        "rejection_reasons": dict(Counter(item.get("reason", "")[:46] for item in run.candidate_rejections).most_common(8)),
        "money_rows": money_rows,
        "currency_unknown": currency_unknown,
        "ai_analyses": len(run.ai_analyses),
        "provider_calls": len(run.provider_calls),
        "checks_brief": [
            {"rule_id": check.rule_id, "title": check.title[:70],
             "level": check.calculation.get("conclusion_level", "none"),
             "status": check.calculation_status, "criteria": check.criteria_status}
            for check in checks
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--pairs", default=",".join(PAIRS))
    args = parser.parse_args()
    rows = []
    for pair in [item for item in args.pairs.split(",") if item]:
        run = run_pipeline(ROOT, RunRequest(pair_id=pair, mode="calculation_only"))
        rows.append(summarize(run))
        print(pair, "checks=", len(run.checks), "formal=", rows[-1]["formal"], flush=True)
    Path(args.out).write_text(json.dumps({"pairs": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
