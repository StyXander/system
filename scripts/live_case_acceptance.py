"""Temporary live acceptance for registered public-report pairs; no confidential content is logged."""
import http.cookiejar
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = os.environ.get("ACCEPTANCE_BASE", "https://audittrace-demo.onrender.com").rstrip("/")
CASES = [
    ("五粮液 2025", "000858-2025"),
    ("美的集团 2025", "000333-2025"),
    ("宁德时代 2025", "300750-2025"),
    ("宝钢股份 2025", "600019-2025"),
]
out = {"base": BASE, "source": os.environ.get("GITHUB_SHA"), "cases": [],
       "observations": {}, "test_scope": "live official registered documents, provider calls only when enabled"}
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def api(method, path, body=None, timeout=45, max_read=30_000_000):
    url = BASE + path
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method,
        headers={"User-Agent": "AuditTrace-acceptance/20261027",
                 "Accept": "application/json",
                 "Origin": BASE,
                 "Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with client.open(req, timeout=timeout) as response:
            blob = response.read(max_read)
            try:
                obj = json.loads(blob)
            except (ValueError, UnicodeError):
                obj = {"preview": blob[:200].decode("utf-8", "replace")}
            return {"http": response.status, "seconds": round(time.monotonic()-started,2), "data": obj}
    except urllib.error.HTTPError as e:
        blob = e.read(2500)
        return {"http": e.code, "seconds": round(time.monotonic()-started,2),
                "error": blob.decode("utf-8", "replace")[:1500]}
    except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as e:
        return {"http": 0, "seconds": round(time.monotonic()-started,2),
                "error": repr(e)[:350]}


def poll(task_id, *, seconds=165):
    deadline = time.monotonic()+seconds
    history = []
    consecutive_failures = 0
    while time.monotonic()<deadline:
        response = api("GET", "/api/connectivity/runs/" + urllib.parse.quote(task_id) + "/status", timeout=25)
        if response["http"] != 200:
            consecutive_failures += 1
            history.append({"http": response["http"], "error": response.get("error", "")[:130]})
            if consecutive_failures >= 4: break
        else:
            consecutive_failures = 0
            state = response["data"]
            status = state.get("status")
            history.append({"status": status, "stage": state.get("current_stage")})
            if status in ("completed", "failed", "degraded", "cancelled"):
                break
        time.sleep(6)
    detail = api("GET", "/api/connectivity/runs/"+urllib.parse.quote(task_id), timeout=50)
    result = detail.get("data", {}).get("result") or {}
    tasks = result.get("matter_tasks") or []
    calls = result.get("provider_calls") or []
    return {"last_status": history[-1] if history else {},
            "poll_count": len(history),
            "detail_http": detail["http"],
            "status": detail.get("data",{}).get("status"),
            "failure_code": detail.get("data",{}).get("failure_code"),
            "error": detail.get("error","")[:300],
            "model_status": result.get("model_status"),
            "matter_count": len(result.get("matters") or []),
            "matters": [{"id":m.get("matter_id"), "type":m.get("matter_type"),
                        "status":m.get("investigation_status")} for m in (result.get("matters") or [])[:5]],
            "provider_calls": len(calls),
            "provider_attempts": sum(bool(c.get("request_attempted")) for c in calls),
            "provider_failures": [{"role":c.get("role"), "code":c.get("failure_code"),
                                   "status":c.get("status")} for c in calls if c.get("status")=="failed"][:15],
            "roles": [{"role":t.get("role"),"status":t.get("status"),
                       "code":t.get("failure_code"), "stop":(t.get("stop_reason") or "")[:150]} for t in tasks[:15]],
            "coverage": [{"document_id":d.get("document_id"),"error":d.get("error"),"pages":d.get("total_pages")} for d in (result.get("matter_coverage") or [])[:10]],
            "full_result": result}


def slim(p):
    value=dict(p)
    value.pop("full_result",None)
    return value


try:
    health=api("GET","/api/health")
    out["observations"]["health"]={"http": health["http"],"status":health.get("data",{}).get("service_status"),
        "commit":health.get("data",{}).get("deployment",{}).get("commit"),
        "mode":health.get("data",{}).get("default_mode"),
        "model":health.get("data",{}).get("model_status"),
        "single_user":health.get("data",{}).get("single_user"),
        "error":health.get("error","")[:250]}
    print("HEALTH",json.dumps(out["observations"]["health"],ensure_ascii=False),flush=True)
    bootstrap=api("GET","/api/connectivity/bootstrap",timeout=65)
    pairs=bootstrap.get("data",{}).get("pairs") or []
    out["observations"]["bootstrap"]={"http":bootstrap["http"],"pairs":[{"pair_id":p.get("pair_id"),"company":p.get("company"),
           "documents":len(p.get("documents") or [])} for p in pairs],
           "default_mode":bootstrap.get("data",{}).get("default_mode"),
           "task_persistence":bootstrap.get("data",{}).get("task_persistence")}
    print("BOOTSTRAP",json.dumps(out["observations"]["bootstrap"],ensure_ascii=False),flush=True)
    reg=api("GET","/api/connectivity/report-sets",timeout=50,max_read=10_000_000)
    out["observations"]["report_sets"]={"http":reg["http"],
         "documents":len(reg.get("data",{}).get("documents") or []),
         "sets":len(reg.get("data",{}).get("items") or []),
         "persistence":reg.get("data",{}).get("persistence")}
    print("REGISTERED_SETS",json.dumps(out["observations"]["report_sets"],ensure_ascii=False),flush=True)
    if health["http"]!=200 or bootstrap["http"]!=200:
        raise RuntimeError("Live backend/bootstrap unreachable: no tasks started")
    for name, pair_id in CASES:
        record={"name":name,"pair_id":pair_id}
        out["cases"].append(record)
        try:
            start=api("POST","/api/connectivity/runs",
                      {"pair_id":pair_id,"analysis_scope":"matter_connectivity",
                       "mode":"calculation_only"},timeout=40,max_read=5_000_000)
            record["initial_http"]=start["http"]
            record["initial_error"]=start.get("error","")[:500]
            task_id=(start.get("data") or {}).get("task_id")
            if not task_id:
                print("CASE",name,"INIT_FAILED",record["initial_http"],record["initial_error"],flush=True)
                continue
            record["initial_task_id"]=task_id
            initial=poll(task_id,seconds=135)
            record["initial"]=slim(initial)
            print("CASE",name,"INITIAL",json.dumps(record["initial"],ensure_ascii=False)[:1900],flush=True)
            if initial["status"] not in ("completed",) or not initial["full_result"].get("matters"):
                continue
            matter=next((m for m in initial["full_result"]["matters"] if m.get("matter_type")=="transition_project"),
                        initial["full_result"]["matters"][0])
            selected=matter.get("matter_id")
            record["selected_matter_id"]=selected
            if not selected or health["data"].get("model_status")!="configured":
                record["five_agents_skipped"]="No matter ID or hosted API key unavailable"
                continue
            req={"pair_id":pair_id,"analysis_scope":"matter_connectivity","mode":"five_agents",
                 "selected_matter_ids":[selected],
                 "budget":{"max_provider_calls":15,"max_parallel_calls":1,
                           "max_matters":1,"max_role_rounds":2}}
            created=api("POST","/api/connectivity/runs",req,timeout=45,max_read=5_000_000)
            record["model_create_http"]=created["http"]
            record["model_create_error"]=created.get("error","")[:450]
            five_task=(created.get("data") or {}).get("task_id")
            if not five_task:
                print("CASE",name,"MODEL_CREATE_FAILED",record["model_create_http"],record["model_create_error"],flush=True)
                continue
            record["five_agent_task_id"]=five_task
            outcome=poll(five_task,seconds=180)
            record["five_agents"]=slim(outcome)
            print("CASE",name,"FIVE_AGENTS",json.dumps(record["five_agents"],ensure_ascii=False)[:3000],flush=True)
        except Exception as e:
            record["exception"]=repr(e)[:400]
            print("CASE_EXCEPTION",name,repr(e)[:400],flush=True)
finally:
    destination=Path("outputs/live-case-acceptance.json")
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RESULT_JSON",str(destination),flush=True)
