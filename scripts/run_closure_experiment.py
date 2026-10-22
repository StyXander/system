"""反事实闭合推演的真实报告实测：五对已登记报告，计算链路，无模型调用。

对照设计（同一批报告、同一评价口径）：
- B0 关闭推演层：把 attach_closure 临时替换为恒等函数，其余完全不变。
- B1 开启推演层：正式结论字段必须与 B0 逐项相同，只新增 closure 派生块。

因此本脚本同时产出两件事：推演层的效果分布，以及"它没有改写任何正式结论"的
可复跑证据。真实公开报告、无合成样本；未跑到的指标一律不写入结果。
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / "backend")]

import app.connectivity_pipeline as pipeline  # noqa: E402
from app.connectivity_overview import build_overview  # noqa: E402
from app.connectivity_schemas import RunRequest  # noqa: E402

PAIRS = ["000858-2025", "000333-2025", "300750-2025", "600019-2025", "600019-2024"]
OUT = Path(__file__).resolve().parents[1] / "outputs" / "closure-20261022"


def formal_signature(run) -> dict:
    """只取正式结论字段，用于证明推演层没有改写结论。"""
    return {
        check.check_id: {
            "criteria_status": check.criteria_status,
            "conclusion_level": check.conclusion_level,
            "calculation_status": check.calculation_status,
            "basis_level": check.basis_level,
            "residual": (check.calculation or {}).get("residual"),
            "unresolved": list(check.unresolved),
        }
        for check in run.checks
    }


def run_pair(root: Path, pair_id: str, with_closure: bool) -> dict:
    original = pipeline.attach_closure
    if not with_closure:
        pipeline.attach_closure = lambda check, occurrences, **kwargs: check
    try:
        started = time.perf_counter()
        run = pipeline.run_pipeline(root, RunRequest(pair_id=pair_id, mode="calculation_only"))
        elapsed = time.perf_counter() - started
    finally:
        pipeline.attach_closure = original
    overview = build_overview(run)
    return {
        "pair_id": pair_id,
        "elapsed_seconds": round(elapsed, 2),
        "relation_total": len(run.checks),
        "occurrences": len(run.occurrences),
        "levels": {key: value["value"] for key, value in overview["program_levels"].items()},
        "closure": overview["closure"],
        "keyword_causes": {item["code"]: item["count"] for item in overview["unresolved_causes"]},
        "signature": formal_signature(run),
        "checks": [
            {
                "check_id": check.check_id,
                "rule_id": check.rule_id,
                "title": check.title,
                "conclusion_level": check.conclusion_level,
                "criteria_status": check.criteria_status,
                "calculation_status": check.calculation_status,
                "unresolved": check.unresolved,
                "closure": check.closure,
            }
            for check in run.checks
        ],
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for pair_id in PAIRS:
        baseline = run_pair(root, pair_id, with_closure=False)
        treated = run_pair(root, pair_id, with_closure=True)
        same = baseline["signature"] == treated["signature"]
        results.append({"baseline": {k: v for k, v in baseline.items() if k != "signature"},
                        "treated": treated,
                        "formal_signature_identical": same})
        print(f"{pair_id}: checks={treated['relation_total']} identical={same} "
              f"t={treated['elapsed_seconds']}s base_t={baseline['elapsed_seconds']}s | "
              f"{treated['closure']['statement']}")
    (OUT / "closure_experiment.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    totals = Counter()
    ceiling = Counter()
    demands = Counter()
    keyword = Counter()
    for item in results:
        tiers = item["treated"]["closure"]["tiers"]
        for key, value in tiers.items():
            totals[key] += value["count"]
        ceiling.update(item["treated"]["closure"]["ceiling_status"])
        demands.update(item["treated"]["closure"]["open_demand_by_condition"])
        keyword.update(item["treated"]["keyword_causes"])

    substantive = []
    hypotheses = Counter()
    for item in results:
        for check in item["treated"]["checks"]:
            block = check["closure"] or {}
            leading = block.get("leading_hypothesis") or {}
            if leading.get("mechanism"):
                hypotheses[f"{leading['mechanism']}:{leading['status']}"] += 1
            if block.get("tier") == "substantive_risk":
                substantive.append({
                    "pair_id": item["treated"]["pair_id"],
                    "check_id": check["check_id"],
                    "title": check["title"],
                    "relation_scope": block.get("relation_scope"),
                    "tier_label": block.get("tier_label"),
                    "tier_reason": block.get("tier_reason"),
                    "residual": (block.get("ceiling") or {}).get("residual"),
                    "unit": (block.get("ceiling") or {}).get("normalized_unit"),
                    "open_demands": [d["condition"] for d in block.get("demands") or []],
                    "single_point_only": block.get("single_point_only"),
                    "leading_hypothesis": leading or None,
                })

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pairs": PAIRS,
        "relation_total": sum(item["treated"]["relation_total"] for item in results),
        "tiers": dict(totals),
        "ceiling_status": dict(ceiling),
        "open_demand_by_condition": dict(demands),
        "keyword_cause_counts": dict(keyword),
        "formal_signature_identical_all": all(item["formal_signature_identical"] for item in results),
        "leading_hypothesis": dict(hypotheses),
        "substantive_risk": substantive,
        "note": "真实公开报告；仅计算链路，未调用任何模型；上限预测不是结论",
    }
    (OUT / "closure_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(json.dumps({k: v for k, v in summary.items() if k != "substantive_risk"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
