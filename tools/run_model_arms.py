"""真实模型对照运行：按模式逐对执行，落盘完整结果与调用记录。

用法：
  python tools/run_model_arms.py --pairs 000858-2025,600019-2025 --modes single_model,three_agents

诚实性：
- 只用真实供应商调用；失败记录 failure_code 与原因，不重试到成功为止。
- token、成本、模型名全部来自 provider_calls 实际回执。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def load_env(path: Path) -> None:
    """不依赖 python-dotenv：逐行读取 KEY=VALUE，已有环境变量优先。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env(ROOT / ".env")
os.environ.setdefault("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "true")

from backend.app.connectivity_pipeline import run_pipeline  # noqa: E402
from backend.app.connectivity_schemas import RunRequest  # noqa: E402


def summarize(run, pair: str) -> dict:
    calls = run.provider_calls or []
    input_tokens = sum(int(call.get("input_tokens") or 0) for call in calls)
    output_tokens = sum(int(call.get("output_tokens") or 0) for call in calls)
    cost = sum(float(call.get("cost") or 0) for call in calls)
    return {
        "run_id": run.run_id, "pair_id": pair, "mode": run.execution_mode,
        "model_status": run.model_status, "schema_version": run.schema_version,
        "duration_ms": run.duration_ms,
        "checks": len(run.checks), "ai_analyses": len(run.ai_analyses),
        "provider_calls": len(calls),
        "failed_calls": [call.get("failure_code") for call in calls if call.get("status") != "completed"],
        "input_tokens": input_tokens, "output_tokens": output_tokens, "cost": round(cost, 6),
        "agent_steps": [{key: step.get(key) for key in ("role", "status", "reason")} for step in run.agent_steps],
        "tool_requests": [entry for entry in run.intelligence_trace
                          if entry.get("kind") in {"agent_tool_request", "agent_tool_result"}][:20],
        "financial_stats": (run.financial_impact or {}).get("stats", {}),
        "financial_receipts": len(((run.financial_impact or {}).get("investigation") or {}).get("receipts") or []),
        "financial_candidates_seen": any(entry.get("kind") == "financial_impact_ready" for entry in run.intelligence_trace),
        "financial_assessments": [{"role": entry.get("role"), "relation_id": entry.get("relation_id"),
                                   "project_name": entry.get("project_name"), "verdict": entry.get("verdict"),
                                   "reason": str(entry.get("reason") or "")[:120]}
                                  for entry in run.intelligence_trace if entry.get("kind") == "financial_assessment"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", default="000858-2025")
    parser.add_argument("--modes", default="single_model,three_agents")
    parser.add_argument("--out", default=str(ROOT / "outputs/model_arms"))
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for pair in [item.strip() for item in args.pairs.split(",") if item.strip()]:
        for mode in [item.strip() for item in args.modes.split(",") if item.strip()]:
            started = time.time()
            record = {"pair_id": pair, "mode": mode}
            try:
                run = run_pipeline(ROOT, RunRequest(pair_id=pair, mode=mode))
                summary = summarize(run, pair)
                record.update({"status": "completed", **summary})
                (out_dir / f"{pair}_{mode}.json").write_text(
                    json.dumps(run.model_dump(mode="json"), ensure_ascii=False), encoding="utf-8")
            except Exception as error:
                record.update({"status": "failed", "error": f"{type(error).__name__}: {error}"[:240]})
            record["wall_seconds"] = round(time.time() - started, 1)
            results.append(record)
            print(json.dumps(record, ensure_ascii=False)[:600], flush=True)
    index = out_dir / "index.json"
    previous = []
    if index.exists():
        try:
            previous = json.loads(index.read_text(encoding="utf-8")).get("results", [])
        except Exception:
            previous = []
    merged = previous + results
    index.write_text(json.dumps({"schema": "model_arms_v1", "results": merged}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"written: {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
