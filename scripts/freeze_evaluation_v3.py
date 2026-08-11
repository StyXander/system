"""冻结竞赛演示评估清单；不生成或填充任何人工分数。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.evaluation import B0_B3_DEFINITIONS, EVALUATION_ID, FIXED_CASES, write_evaluation_dashboard
from backend.app.seed_catalog import load_seed_cases


def main() -> None:
    seeds = {str(item.get("case_id")): item for item in load_seed_cases(ROOT)}
    cases = []
    for item in FIXED_CASES:
        source = seeds.get(item["case_id"], {})
        snapshot = {
            "case_id": item["case_id"],
            "company_name": item["company_name"],
            "stratum": item["stratum"],
            "t0": source.get("t0"),
            "available_years": source.get("available_years") or source.get("available_report_years") or [],
            "source_snapshot_id": source.get("source_snapshot_id"),
            "source_fingerprint": hashlib.sha256(json.dumps(source.get("documents") or [], sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        }
        groups = {group: {"status": "not_started", "definition": definition} for group, definition in B0_B3_DEFINITIONS.items()}
        if item["stratum"] in {"rule_not_triggered", "conditional_industry", "industry_not_applicable"}:
            groups["B2"]["status"] = "not_applicable_no_call"
            groups["B3"]["status"] = "not_applicable_no_call"
        cases.append({**snapshot, "groups": groups})
    aggregate_groups = {
        group: {
            "status": "not_started",
            "definition": definition,
            "completed": 0,
            "total": len(cases),
        }
        for group, definition in B0_B3_DEFINITIONS.items()
    }
    for item in cases:
        for group in ("B2", "B3"):
            if item["groups"][group].get("status") == "not_applicable_no_call":
                aggregate_groups[group]["not_applicable_count"] = aggregate_groups[group].get("not_applicable_count", 0) + 1
    payload = {
        "schema_version": "evaluation_dashboard_v1",
        "evaluation_id": EVALUATION_ID,
        "status": "frozen",
        "frozen_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "model_id": None,
        "reviewers_required": 2,
        "cases_required": len(cases),
        "review_forms_required": len(cases) * 2,
        "review_forms_completed": 0,
        "metrics": None,
        "groups": aggregate_groups,
        "cases": cases,
        "disputes": 0,
        "boundary": "评分仅用于竞赛效果展示，不用于训练模型或修改规则。",
    }
    target = write_evaluation_dashboard(ROOT, payload)
    print(json.dumps({"evaluation_id": EVALUATION_ID, "path": str(target), "cases": len(cases)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
