"""任务11-B：财务穿透三种技术路线的可复现实验脚本。

三条实验臂：
1. rule_only：规则抽取 + 附注结构化 + BM25/精确匹配 + 九项条件裁决（本脚本实际执行）。
2. single_model：单模型完成事项与会计映射（需 --allow-models 且配置密钥，本次未执行）。
3. multi_agent：A1/A2/A3 + 会计知识库 + 混合检索 + 独立反证（需 --allow-models，本次未执行）。

诚实性约束：
- 没有会计专业人工标注时，不输出 Precision/Recall/F1，只记录可复核的结构化计数与运行时长。
- 未执行的臂记为 not_run 并写明原因，不以规则结果冒充模型结果。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.connectivity_extraction import load_registry  # noqa: E402
from backend.app.financial_impact import build  # noqa: E402

ARMS = {
    "rule_only": "规则抽取 + 附注结构化 + BM25/精确匹配 + 九项条件裁决",
    "single_model": "单模型完成事项抽取与会计映射（实验基线）",
    "multi_agent": "A1/A2/A3 + 会计规则库 + 混合检索 + 独立反证",
}


def pairs() -> list[tuple[str, str]]:
    seen = []
    for document in load_registry(ROOT):
        key = (document.company, str(document.period))
        if key not in seen:
            seen.append(key)
    return seen


def run_rule_arm(max_events: int) -> dict:
    results = []
    for company, period in pairs():
        documents = [doc for doc in load_registry(ROOT) if doc.company == company and str(doc.period) == period]
        if len(documents) < 2:
            results.append({"company": company, "period": period, "status": "skipped_no_pair"})
            continue
        started = time.perf_counter()
        try:
            payload = build(ROOT, documents=documents, max_events=max_events)
        except Exception as error:  # 单对失败不掩盖其他对
            results.append({"company": company, "period": period, "status": "failed",
                            "error": f"{type(error).__name__}: {error}"[:200]})
            continue
        stats = payload.get("stats", {})
        results.append({
            "company": company, "period": period, "status": "completed",
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "events": stats.get("events", 0), "items": stats.get("items", 0),
            "treatments": stats.get("treatments", 0), "relations": stats.get("relations", 0),
            "project_level": stats.get("project_level", 0), "grades": stats.get("grades", {}),
            "verified_items": stats.get("verified_items", 0),
        })
    return {"arm": "rule_only", "status": "completed", "results": results}


def model_arm(name: str, allow_models: bool) -> dict:
    if not allow_models:
        return {"arm": name, "status": "not_run",
                "reason": "未使用 --allow-models；模型调用会产生外部费用，需预算授权"}
    if not os.getenv("DEEPSEEK_API_KEY") and not (ROOT / ".env").exists():
        return {"arm": name, "status": "not_run", "reason": "未配置模型密钥"}
    return {"arm": name, "status": "not_run",
            "reason": "本脚本只负责规则臂与记账；模型臂需在既有配额管线内单独运行并登记 token 成本"}


def summarize(rule: dict) -> dict:
    completed = [item for item in rule["results"] if item["status"] == "completed"]
    if not completed:
        return {"pairs_completed": 0}
    durations = [item["duration_ms"] for item in completed]
    return {
        "pairs_completed": len(completed),
        "events_total": sum(item["events"] for item in completed),
        "items_total": sum(item["items"] for item in completed),
        "relations_total": sum(item["relations"] for item in completed),
        "project_level_total": sum(item["project_level"] for item in completed),
        "duration_ms_median": int(statistics.median(durations)),
        "pairs_with_project_level": sum(1 for item in completed if item["project_level"] > 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="财务穿透三路线对照实验")
    parser.add_argument("--allow-models", action="store_true", help="允许调用付费模型（默认关闭）")
    parser.add_argument("--max-events", type=int, default=16)
    parser.add_argument("--out", default=str(ROOT / "outputs/financial_impact_experiment.json"))
    args = parser.parse_args()

    rule = run_rule_arm(args.max_events)
    report = {
        "schema": "financial_impact_experiment_v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "arms": {name: description for name, description in ARMS.items()},
        "rule_only": rule,
        "single_model": model_arm("single_model", args.allow_models),
        "multi_agent": model_arm("multi_agent", args.allow_models),
        "labels": {"status": "not_completed",
                   "reason": "未取得会计专业人工标注，不计算 Precision/Recall/F1，避免编造指标"},
        "summary": summarize(rule),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"written: {out}")
    for name in ("single_model", "multi_agent"):
        print(f"{name}: {report[name]['status']} — {report[name].get('reason', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
