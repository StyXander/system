"""登记报告的零模型核验；不能用于声称AI能力或专业准确率提升。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pair", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / "backend"))
    from app.connectivity_pipeline import run_pipeline
    from app.connectivity_schemas import RunRequest
    summary = {"verification": "registered_reports_calculation_only", "model_calls": 0, "results": []}
    args.output.mkdir(parents=True, exist_ok=True)
    for pair in args.pair or ["000858-2025", "600019-2025"]:
        print(f"Checking {pair}", flush=True)
        run = run_pipeline(root, RunRequest(pair_id=pair, mode="calculation_only"),
                           progress=lambda stage, status, detail: print(stage, status, flush=True))
        assert not run.provider_calls and run.model_status == "not_requested"
        (args.output / f"{pair}.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
        info = {"pair_id": pair, "company": run.company, "documents": [
            {"document_id": d.document_id, "sha256": d.file_sha256} for d in run.documents],
            "occurrences": len(run.occurrences), "checks": len(run.checks),
            "formal_supported": sum(c.criteria_status == "supported" for c in run.checks),
            "formal_consistent": sum(c.calculation_status == "consistent" for c in run.checks),
            "conditional_trials": sum(bool(c.hypothetical) for c in run.checks),
            "ai_analyses": len(getattr(run, "ai_analyses", [])), "model_calls": len(run.provider_calls),
            "duration_ms": run.duration_ms}
        summary["results"].append(info)
        print(json.dumps(info, ensure_ascii=False), flush=True)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
