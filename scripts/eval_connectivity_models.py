"""经实际任务接口跑单模型与三角色，保留配额、失败和真实用量。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]


def evaluate(pair_id: str, base_url: str, modes=None, retry_of_task_id=None):
    target = ROOT / "outputs/connectivity-v1-acceptance/model-comparisons" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target.mkdir(parents=True, exist_ok=True)
    summaries = []
    with httpx.Client(base_url=base_url, timeout=30, trust_env=False) as client:
        client.get("/api/connectivity/bootstrap").raise_for_status()
        for mode in modes or ("single_model", "three_agents"):
            action_id = str(uuid.uuid4())
            created = client.post("/api/connectivity/runs", headers={"Idempotency-Key": action_id},
                json={"pair_id": pair_id, "topics": ["research", "environment", "intensity"], "mode": mode,
                    "retry_of_task_id":retry_of_task_id})
            if created.is_error:
                failure = {"pair_id":pair_id,"mode":mode,"idempotency_key":action_id,
                    "http_status":created.status_code,"response":created.json()}
                (target / "creation-failure.json").write_text(json.dumps(failure,ensure_ascii=False,indent=2),encoding="utf-8")
                print(json.dumps(failure,ensure_ascii=True),flush=True)
            created.raise_for_status()
            task_id = created.json()["task_id"]
            print(json.dumps({"mode": mode, "task_id": task_id, "state": "created"}), flush=True)
            (target / f"{mode}-task.json").write_text(created.text, encoding="utf-8")
            deadline = time.monotonic() + 600
            while True:
                response = client.get(f"/api/connectivity/runs/{task_id}")
                response.raise_for_status()
                task = response.json()
                if task["status"] not in {"queued", "running"}:
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError(f"{task_id}仍未完成；观察超时不取消或重跑实际任务")
                time.sleep(2)
            (target / f"{mode}-task.json").write_text(response.text, encoding="utf-8")
            run = task.get("result") or {}
            calls = run.get("provider_calls", [])
            checks = run.get("checks", [])
            summary = {"mode": mode, "task_id": task_id, "run_id": run.get("run_id"), "task_status": task["status"],
                "failure_code":task.get("failure_code"),"retry_of_task_id":task.get("retry_of_task_id"),
                "model_status": run.get("model_status"), "versions": run.get("versions"),
                "models": sorted({c["model"] for c in calls if c.get("model")}),
                "calls": sum(bool(c.get("performed")) for c in calls),
                "input_tokens": sum(c.get("input_tokens") or 0 for c in calls) if all(c.get("input_tokens") is not None for c in calls) and calls else None,
                "output_tokens": sum(c.get("output_tokens") or 0 for c in calls) if all(c.get("output_tokens") is not None for c in calls) and calls else None,
                "duration_ms": run.get("duration_ms"), "cost": None, "cost_note": "未配置计价，不推算费用",
                "relations": len(checks), "relations_by_rule": {rule: sum(c["rule_id"] == rule for c in checks) for rule in ["EQ-001", "RD-001", "ENV-001", "INT-001", "OCC-001", "NAR-001"]},
                "supported_criteria": sum(c["criteria_status"] == "supported" for c in checks),
                "unresolved": sum(bool(c["unresolved"]) for c in checks),
                "context_counts": [{"role": step["role"], "count": step.get("context_count")} for step in run.get("agent_steps", [])],
                "accepted": sum(len(s.get("accepted_check_ids", [])) for s in run.get("agent_steps", []) if s["role"] != "A3"),
                "rejected": sum(len(s.get("rejected", [])) for s in run.get("agent_steps", []))}
            summaries.append(summary)
            (target / "comparison.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(summary, ensure_ascii=True), flush=True)
    title = "单模型与三角色实际运行对照" if len(summaries)>1 else "单次模型实际运行记录（不构成对照实验）"
    lines = [f"# {title}", "", f"报告对：{pair_id}。通过应用任务接口执行，保留原有配额；单模型获得首轮与补查原文的并集，最多8项关系；A1、A2各最多4项，A3只整理已有问题。", "",
        "| 运行方式 | 实际模型状态 | 调用 | 输入tokens | 输出tokens | 毫秒 | 关系 | 条件充分 | 仍未决 |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in summaries:
        lines.append(f"| {s['mode']} | {s['model_status']} | {s['calls']} | {s['input_tokens']} | {s['output_tokens']} | {s['duration_ms']} | {s['relations']} | {s['supported_criteria']} | {s['unresolved']} |")
    lines += ["", "关系数量包含共同的确定性候选，不能直接当命中数或准确率。角色采纳数不代表人工确认；不同关系的事实正确性须逐项核对。单模型与三角色调用预算及任务分工不同，表中明确记录实际耗时和用量，不据此宣称后者全面优越。", "",
        "该记录是工程运行对照；人工PDF与Excel基线、盲评及专业反馈均未由脚本执行。未配置单价，因此费用保持未计价。"]
    (target / "实际模型对照.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps({"saved": str(target)}, ensure_ascii=True), flush=True)
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", default="600019-2024")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--mode", choices=["single_model", "three_agents"], action="append")
    parser.add_argument("--retry-of-task-id")
    args = parser.parse_args()
    summaries=evaluate(args.pair,args.base_url,args.mode,args.retry_of_task_id)
    raise SystemExit(0 if all(s["task_status"]=="completed" for s in summaries) else 1)
