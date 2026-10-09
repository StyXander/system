"""复审真实验收：有限两次模型任务，不把回放计作新成功。"""
from __future__ import annotations
import hashlib
import json
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "决赛整改_2026-10-09" / "当前版本真实运行"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8030"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def api(path: str, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(BASE + path, data=body, headers={"Content-Type":"application/json", "Idempotency-Key":str(uuid.uuid4())})
    with opener.open(request, timeout=120) as response:
        return json.load(response)

def completed(task):
    # 轮询只读取已有任务；期限到了即报告，绝不自动再提交一次付费任务。
    end = time.monotonic() + 240
    while task["status"] in {"queued", "running"} and time.monotonic() < end:
        time.sleep(1)
        task = api("/api/demo/runs/" + task["task_id"])
    run = task.get("result")
    if not run and task["status"] in {"completed", "degraded"}:
        run = api("/api/demo/runs/" + task["task_id"] + "/result")
    (OUT / (task["task_id"] + ".json")).write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"task_id":task["task_id"], "status":task["status"], "run_id":(run or {}).get("run_id"), "failure_code":task.get("failure_code"), "error":task.get("error")}
    if run:
        summary.update({"run_completeness":run.get("run_completeness"), "model_check":run.get("model_check"), "calls":run.get("provider_call_count"), "prompt":run.get("context",{}).get("agent_prompt_version"), "years":[run.get("context",{}).get(k) for k in ("current_year","previous_year","prior_year")], "rules":[{"rule":r["rule_id"],"status":r["status"],"gap":r.get("metrics",{}).get("growth_gap"),"observation":r.get("risk_card",{}).get("observation")} for r in run.get("rule_results",[])], "roles":[{"role":s["role"],"status":s["status"],"failure_code":s.get("failure_code"),"model_id":s.get("model_id")} for s in run.get("agent_steps",[])]})
        summary["payload_sha256"] = hashlib.sha256(json.dumps(run,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return summary,run

def main():
    results=[]
    for case,year in [("STD_DEV_T0",2025),("CNINFO_000858_T0_20260430",2025)]:
        task=api("/api/demo/runs",{"case_id":case,"current_year":year,"rule_ids":["R1","R2"],"scene":"审计计划","run_mode":"full_analysis"})
        summary,run=completed(task)
        results.append(summary)
        (OUT / "验收摘要.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    successful = all(item.get("run_completeness") in {"complete_full_analysis", "complete_public_prescreen_with_gaps"} and item.get("calls",0)>=3 and all(role["status"]=="completed" for role in item.get("roles",[])) for item in results)
    if not successful:
        raise SystemExit("真实运行存在不完整状态，保留原失败证据。")

if __name__=="__main__":
    main()
