#!/usr/bin/env python3
"""批次 7 的可复验准入运行器。

默认执行 15 案本地计算与 RAG 回归：精选案例各 10 次，其余案例各 5 次。
`--featured-model` 仅用于三个精选案例的真实模型连续运行；它不会把回放、
确定性备用或未完成运行计为成功，也不会删除或覆盖任何历史运行记录。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "backend" / "competition_demo_cases.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "competition-demo-batch7"


def post_run(base_url: str, payload: dict[str, Any], timeout: int = 420) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/runs",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_payload(case: dict[str, Any], run_mode: str) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "current_year": max(case.get("report_years") or [2025]),
        "scene": "审计计划",
        "rule_ids": case.get("rule_ids") or ["R1"],
        "run_mode": run_mode,
    }


def local_chain_passed(run: dict[str, Any]) -> bool:
    source_issues = (run.get("source_validation") or {}).get("issues") or []
    return bool(
        run.get("run_id")
        and run.get("run_completeness") == "incomplete_calculation_only"
        and run.get("rule_results")
        and run.get("evidence_bundle")
        and not source_issues
        and int(run.get("provider_call_count") or 0) == 0
    )


def fresh_model_passed(run: dict[str, Any]) -> bool:
    steps = run.get("agent_steps") or []
    model_check = run.get("model_check") or {}
    return bool(
        run.get("run_completeness") in {
            "complete_full_analysis",
            "complete_public_prescreen",
            "complete_public_prescreen_with_gaps",
        }
        and model_check.get("status") == "model_success"
        and len(steps) == 3
        and all(step.get("status") == "completed" for step in steps)
        and int(run.get("provider_call_count") or 0) > 0
        and int(run.get("input_tokens") or 0) > 0
        and int(run.get("output_tokens") or 0) > 0
        and not run.get("cache_hit")
    )


def execute_local(base_url: str, manifest: dict[str, Any]) -> dict[str, Any]:
    rows = []
    featured = set(manifest["featured_case_ids"])
    for case in manifest["cases"]:
        required = 10 if case["case_id"] in featured else 5
        attempts = []
        for number in range(1, required + 1):
            started = time.perf_counter()
            try:
                run = post_run(base_url, run_payload(case, "calculation_only"), timeout=90)
                passed = local_chain_passed(run)
                attempts.append(
                    {
                        "iteration": number,
                        "passed": passed,
                        "run_id": run.get("run_id"),
                        "run_completeness": run.get("run_completeness"),
                        "rule_count": len(run.get("rule_results") or []),
                        "evidence_count": len(run.get("evidence_bundle") or []),
                        "source_issues": (run.get("source_validation") or {}).get("issues") or [],
                        "provider_call_count": run.get("provider_call_count"),
                        "duration_seconds": round(time.perf_counter() - started, 3),
                    }
                )
            except Exception as exc:  # 失败保留原始类型，不补造成功。
                attempts.append({"iteration": number, "passed": False, "error": str(exc)[:500]})
            print(f"[local] {case['case_id']} {number}/{required} passed={attempts[-1]['passed']}", flush=True)
        rows.append(
            {
                "case_id": case["case_id"],
                "company_name": case.get("company_name"),
                "level": "A" if case["case_id"] in featured else "B",
                "required_runs": required,
                "passed_runs": sum(bool(item["passed"]) for item in attempts),
                "passed": all(bool(item["passed"]) for item in attempts),
                "attempts": attempts,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "local_deterministic_rag_regression",
        "case_count": len(rows),
        "total_required_runs": sum(row["required_runs"] for row in rows),
        "total_passed_runs": sum(row["passed_runs"] for row in rows),
        "passed": all(row["passed"] for row in rows),
        "cases": rows,
    }


def execute_featured_model(
    base_url: str,
    manifest: dict[str, Any],
    *,
    target_streak: int,
    max_attempts: int,
    cooldown: int,
    selected_case_ids: list[str] | None = None,
) -> dict[str, Any]:
    by_id = {case["case_id"]: case for case in manifest["cases"]}
    rows = []
    featured_case_ids = selected_case_ids or manifest["featured_case_ids"]
    for case_id in featured_case_ids:
        if case_id not in by_id:
            raise ValueError(f"unknown case: {case_id}")
        case = by_id[case_id]
        streak = 0
        attempts = []
        for number in range(1, max_attempts + 1):
            try:
                run = post_run(base_url, run_payload(case, "full_analysis"))
                passed = fresh_model_passed(run)
                streak = streak + 1 if passed else 0
                attempts.append(
                    {
                        "attempt": number,
                        "passed": passed,
                        "consecutive_successes": streak,
                        "run_id": run.get("run_id"),
                        "run_completeness": run.get("run_completeness"),
                        "model_status": (run.get("model_check") or {}).get("status"),
                        "provider_call_count": run.get("provider_call_count"),
                        "input_tokens": run.get("input_tokens"),
                        "output_tokens": run.get("output_tokens"),
                        "cache_hit": run.get("cache_hit"),
                        "agent_steps": [
                            {
                                "role": step.get("role"),
                                "status": step.get("status"),
                                "failure_code": step.get("failure_code"),
                            }
                            for step in (run.get("agent_steps") or [])
                        ],
                    }
                )
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                streak = 0
                attempts.append(
                    {"attempt": number, "passed": False, "consecutive_successes": 0, "error": str(exc)[:500]}
                )
            print(f"[model] {case_id} attempt={number} streak={streak}/{target_streak}", flush=True)
            if streak >= target_streak:
                break
            if cooldown:
                time.sleep(cooldown)
        rows.append(
            {
                "case_id": case_id,
                "company_name": case.get("company_name"),
                "target_streak": target_streak,
                "final_streak": streak,
                "passed": streak >= target_streak,
                "attempts": attempts,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "featured_fresh_model_streak",
        "target_streak": target_streak,
        "passed": all(row["passed"] for row in rows),
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--featured-model", action="store_true")
    parser.add_argument("--extension-model", action="store_true", help="12 个 B 级案例各取得一次 fresh 模型成功")
    parser.add_argument("--target-streak", type=int, default=3)
    parser.add_argument("--max-attempts", type=int, default=9)
    parser.add_argument("--cooldown", type=int, default=90)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.featured_model or args.extension_model:
        selected_case_ids = args.case_ids
        if args.extension_model and not selected_case_ids:
            featured = set(manifest["featured_case_ids"])
            selected_case_ids = [case["case_id"] for case in manifest["cases"] if case["case_id"] not in featured]
        report = execute_featured_model(
            args.base_url,
            manifest,
            target_streak=args.target_streak,
            max_attempts=args.max_attempts,
            cooldown=args.cooldown,
            selected_case_ids=selected_case_ids,
        )
        output = args.output_dir / ("extension-model-smoke.json" if args.extension_model else "featured-model-streak.json")
    else:
        report = execute_local(args.base_url, manifest)
        output = args.output_dir / "local-chain-regression.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={output} passed={report['passed']}", flush=True)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
