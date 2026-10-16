"""真实公开报告写入用户已授权的Supabase项目，验证独立实例和并发修订。"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
os.environ["AUDITTRACE_DEMO_TASK_PERSISTENCE"] = "supabase"
os.environ["AUDITTRACE_DEMO_EXECUTOR_MODE"] = "web"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.connectivity_api import build_router, COOKIE


def application():
    app = FastAPI()
    app.include_router(build_router(ROOT, lambda request: None, lambda: None))
    return app


def completed(client, task_id):
    deadline = time.monotonic()+180
    while time.monotonic() < deadline:
        response = client.get(f"/api/connectivity/runs/{task_id}")
        response.raise_for_status()
        task = response.json()
        if task["status"] not in {"queued", "running"}:
            assert task["status"] == "completed", {"status": task["status"], "failure": task.get("failure_code")}
            return task
        time.sleep(1)
    raise TimeoutError("观察超时；不取消和重复创建原任务")


def main():
    with TestClient(application()) as first, TestClient(application()) as second:
        first.get("/api/connectivity/bootstrap").raise_for_status()
        created = first.post("/api/connectivity/runs", headers={"Idempotency-Key":str(uuid.uuid4())},
            json={"pair_id":"600019-2024", "mode":"calculation_only"})
        created.raise_for_status()
        task_id = created.json()["task_id"]
        print(json.dumps({"task_id": task_id, "state":"created_in_supabase"}), flush=True)
        original = completed(first, task_id)
        independent = completed(second, task_id)
        assert independent["result"] == original["result"]
        run = original["result"]
        body = {"expected_revision":run["result_revision"], "action":"personal_observation",
            "check_ids":[run["checks"][0]["check_id"]], "reason":"工程验证：观察与系统事实分别存储",
            "observation":"本条为公开报告原型的存储与恢复验证记录，不是专业评价或审计意见。",
            "actor":"自动化工程验证", "action_id":str(uuid.uuid4())}
        endpoint=f"/api/connectivity/runs/{task_id}/reviews"
        second.cookies.set(COOKIE, first.cookies.get(COOKIE))
        competing = deepcopy(body)
        competing["action_id"] = str(uuid.uuid4())
        competing["reason"] = "工程验证：并发修订应明确冲突"
        with ThreadPoolExecutor(max_workers=2) as executor:
            a = executor.submit(first.post, endpoint, json=body)
            b = executor.submit(second.post, endpoint, json=competing)
            outcomes = [a.result(), b.result()]
        assert sorted(r.status_code for r in outcomes) == [200,409], [r.status_code for r in outcomes]
        winner_index = next(i for i,r in enumerate(outcomes) if r.status_code == 200)
        winner_body = [body,competing][winner_index]
        child_id = outcomes[winner_index].json()["task_id"]
        child = completed(first, child_id)
        assert child["result"]["checks"] == run["checks"]
        assert child["result"]["parent_run_id"] == run["run_id"]
        assert len(child["result"]["professional_notes"]) == 1
        retry = first.post(endpoint, json=winner_body)
        assert retry.status_code == 200 and retry.json()["task_id"] == child_id
        assert completed(second, child_id)["result"] == child["result"]
        assert completed(first, task_id)["result"] == run
        export = second.get(f"/api/connectivity/runs/{child_id}/export/json")
        export.raise_for_status()
        assert export.json() == child["result"]
        report = {"checked_at":datetime.now(timezone.utc).isoformat(), "status":"passed",
            "report_pair":"600019-2024", "discovery":"real_raw_pdf", "model_called":False,
            "task_id":task_id, "run_id":run["run_id"], "child_task_id":child_id,
            "independent_application_read":True, "concurrent_revision_statuses":[r.status_code for r in outcomes],
            "idempotent_retry":True, "original_unchanged":True, "observation_keeps_facts":True,
            "saved_json_export_matches":True, "private_data_transferred":False,
            "boundary":"两个独立应用及存储实例访问真实Supabase；不冒充真人专业评价，也不冒充独立主机重启。"}
        (ROOT/"outputs/connectivity-v1-acceptance/supabase-workflow.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__ == "__main__":
    main()
