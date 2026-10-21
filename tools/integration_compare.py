"""三模式公平对照：纯规则 / 单模型 / 三角色，同一输入、同一判据。

只记录可复算的过程指标，不把模型自述当准确率：
- 关系召回：checks 数与其证据覆盖分布；
- 结论分级：formal / assumption / limited / insufficient / conflict / not_applicable；
- AI 主张：claim 账本里 supported / contradicted / insufficient_basis 与 material 矛盾数；
- 成本：provider_calls 次数、耗时、token（若回执提供）。

用法：
    python tools/integration_compare.py --pair 000858-2025 --modes calculation_only,single_model,three_agents --out result.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
    if os.getenv(key):
        os.environ[key] = os.environ[key]

from app.connectivity_pipeline import run_pipeline  # noqa: E402
from app.connectivity_schemas import RunRequest  # noqa: E402


def summarize(run, elapsed: float, mode: str) -> dict:
    claims = run.claim_ledger
    support = Counter(item.get("support_status", "unknown") for item in claims)
    materials = [claim for item in claims for claim in item.get("material_contradictions", [])]
    levels = Counter(check.calculation.get("conclusion_level", "none") for check in run.checks)
    tokens = 0
    for call in run.provider_calls:
        usage = call.get("usage") or {}
        tokens += int(usage.get("total_tokens") or
                      (int(call.get("input_tokens") or 0) + int(call.get("output_tokens") or 0)))
    return {
        "mode": mode,
        "pair_id": run.versions.get("pair_id") or (run.documents[0].case_id if run.documents else ""),
        "elapsed_seconds": round(elapsed, 1),
        "occurrences": len(run.occurrences),
        "checks": len(run.checks),
        "levels": dict(levels),
        "formal": levels.get("formal_consistent", 0),
        "assumption_compatible": levels.get("assumption_compatible", 0),
        "limited_support": levels.get("limited_support", 0),
        "insufficient_basis": levels.get("insufficient_basis", 0),
        "unexplained_difference": levels.get("unexplained_difference", 0),
        "rejections": len(run.candidate_rejections),
        "ai_analyses": len(run.ai_analyses),
        "ai_verdicts": dict(Counter(item.verdict for item in run.ai_analyses)),
        "claim_total": len(claims),
        "claim_support": dict(support),
        "claim_material_contradictions": len(materials),
        "provider_calls": len(run.provider_calls),
        "provider_details": [
            {key: call.get(key) for key in ("role", "status", "failure_code", "duration_ms",
                                            "input_tokens", "output_tokens", "batch")}
            for call in run.provider_calls
        ],
        "tokens": tokens,
        "model_status": run.model_status,
        "checks_brief": [
            {"rule_id": check.rule_id, "title": check.title[:60],
             "level": check.calculation.get("conclusion_level", "none"),
             "criteria": check.criteria_status, "calc": check.calculation_status}
            for check in run.checks
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", required=True)
    parser.add_argument("--modes", default="calculation_only,single_model,three_agents")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = []
    for mode in [item for item in args.modes.split(",") if item]:
        started = time.monotonic()
        try:
            run = run_pipeline(ROOT, RunRequest(pair_id=args.pair, mode=mode))
            rows.append(summarize(run, time.monotonic() - started, mode))
        except Exception as error:  # 单模式失败不应吞掉整轮对照
            rows.append({"mode": mode, "pair_id": args.pair, "error": f"{type(error).__name__}: {error}",
                         "elapsed_seconds": round(time.monotonic() - started, 1)})
        print(mode, "->", rows[-1].get("checks"), "checks", rows[-1].get("formal"), "formal",
              rows[-1].get("elapsed_seconds"), "s", flush=True)
    Path(args.out).write_text(json.dumps({"pair": args.pair, "runs": rows}, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    return 1 if any("error" in row for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
