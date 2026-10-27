"""Actual production five-Agent Baosteel acceptance. Uses hosted API and paid provider, no mocks.

Starts exactly ONE new screening and, if a concrete audited project was seeded,
ONE selected-matter five-Agent investigation. Artifacts contain summary only.
"""
from __future__ import annotations
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

BASE="https://audittrace-demo.onrender.com"
PAIR="600019-2025"
OUT=Path("outputs/finals-baosteel-a3-live-20261027.json")
OUT.parent.mkdir(parents=True,exist_ok=True)
jar=CookieJar()
http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
result={"started_at":datetime.now(timezone.utc).isoformat(),"target":BASE,"pair_id":PAIR,
        "run_policy":"one real seed run, one selected project real five-Agent run, no fake provider",
        "runs":[],"source_commit":os.environ.get("GITHUB_SHA","")}

def dump():
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")

def call(method,path,body=None,timeout=65):
    payload=None if body is None else json.dumps(body,ensure_ascii=False).encode()
    req=urllib.request.Request(BASE+path,data=payload,method=method,
      headers={"User-Agent":"AuditTrace-Live-5Agent-Acceptance/1.0","Content-Type":"application/json",
               "Accept":"application/json","Origin":BASE})
    start=time.monotonic()
    try:
        with http.open(req,timeout=timeout) as r:
            b=r.read(50_000_000)
            try: parsed=json.loads(b)
            except ValueError: parsed={"first_bytes":b[:150].decode(errors="replace")}
            return {"code":r.status,"seconds":round(time.monotonic()-start,2),"data":parsed}
    except urllib.error.HTTPError as e:
        return {"code":e.code,"seconds":round(time.monotonic()-start,2),"error":e.read(2500).decode(errors="replace")[:1200]}
    except (urllib.error.URLError,TimeoutError,socket.timeout,ConnectionError) as e:
        return {"code":0,"seconds":round(time.monotonic()-start,2),"error":repr(e)[:300]}

def run_and_poll(body, stage, max_seconds):
    response=call("POST","/api/connectivity/runs",body,timeout=85)
    info={"stage":stage,"request_code":response["code"],
          "start_duration":response["seconds"],"initial_error":response.get("error","")}
    result["runs"].append(info)
    task=(response.get("data") or {}).get("task_id")
    if not task:
        print("START_ERROR",stage,json.dumps(info,ensure_ascii=False),flush=True)
        dump()
        return info,None
    info["task_id"]=task
    print("STARTED",stage,task,flush=True)
    last=""
    deadline=time.monotonic()+max_seconds
    while time.monotonic()<deadline:
        p=call("GET",f"/api/connectivity/runs/{task}/status",timeout=40)
        d=p.get("data") or {}
        status=d.get("status")
        desc=f"{status} / {d.get('current_stage')}"
        if p["code"]!=200:desc=f"http_{p['code']}"
        if desc!=last:
            print("PROGRESS",stage,task,desc,flush=True)
            last=desc
        if status in ("completed","degraded","failed","cancelled","interrupted","expired"):
            break
        time.sleep(8)
    full=call("GET",f"/api/connectivity/runs/{task}",timeout=90)
    data=full.get("data") or {}
    info.update({"final_http":full["code"],"final_status":data.get("status"),
                 "failure_code":data.get("failure_code"),"error":full.get("error","")[:500],
                 "duration_to_read":full["seconds"],"timed_out":time.monotonic()>=deadline})
    r=data.get("result") or {}
    info.update({"model_status":r.get("model_status"),"run_id":r.get("run_id"),
                 "model_mode":r.get("execution_mode"),"candidate_count":len(r.get("matters") or []),
                 "selected_scope":(r.get("versions") or {}).get("investigation_scope"),
                 "report_set":(r.get("report_set") or {}).get("report_set_id"),
                 "provider_origin":(r.get("versions") or {}).get("provider_origin"),
                 "dataset_role":r.get("dataset_role")})
    info["role_results"]=[{"role":t.get("role"),"name":t.get("role_name"),
              "status":t.get("status"),"failure_code":t.get("failure_code"),
              "reason":str(t.get("stop_reason") or "")[:240],
              "rounds":t.get("rounds"),"duration_ms":t.get("duration_ms"),
              "matter_id":t.get("matter_id")} for t in (r.get("matter_tasks") or [])]
    calls=r.get("provider_calls") or []
    info["provider_calls"]=[{"role":t.get("role"),"model":t.get("model"),"requested_model":t.get("requested_model"),
             "status":t.get("status"),"failure_code":t.get("failure_code"),
             "parse_stage":t.get("parse_stage"),"http_status":t.get("http_status"),
             "request_attempted":t.get("request_attempted"),"performed":t.get("performed"),
             "input_tokens":t.get("input_tokens"),"output_tokens":t.get("output_tokens")} for t in calls]
    info["role_budgets"]=(r.get("versions") or {}).get("role_budgets")
    info["actual_provider_attempt_count"]=sum(bool(x.get("request_attempted")) for x in calls)
    info["actual_provider_performed_count"]=sum(bool(x.get("performed")) for x in calls)
    info["role_counts"]={role:{
         "complete":sum(x["status"]=="completed" for x in info["role_results"] if x["role"]==role),
         "failed":sum(x["status"]=="failed" for x in info["role_results"] if x["role"]==role),
         "skipped":sum(x["status"]=="skipped" for x in info["role_results"] if x["role"]==role)}
         for role in ("A1","A2","A3","A4","A5")}
    info["evidence_counts"]={"registered":len(r.get("matter_evidence") or []),
          "paths":len(r.get("matter_paths") or []),"events":len(r.get("matter_events") or []),
          "financial_occurrences":len(r.get("occurrences") or []),
          "relations":len(r.get("matter_relations") or []),
          "explanations":len(r.get("matter_explanations") or []),
          "assessments":len(r.get("matter_assessments") or []),
          "source_coverage":[{"document_id":c.get("document_id"),"pdf_pages":c.get("total_pages"),
               "fail_count":len(c.get("failed_pages") or [])} for c in (r.get("matter_coverage") or [])]}
    info["matters"]=[{"matter_id":m.get("matter_id"),"name":m.get("name"),
                 "type":m.get("matter_type"),"status":m.get("investigation_status"),
                 "identity":m.get("identity_status"),"evidence_ids":(m.get("evidence_ids") or [])[:4]}
                 for m in (r.get("matters") or [])]
    info["assessment_preview"]=[{"matter_id":a.get("matter_id"),
           "conclusion":str(a.get("conclusion") or a.get("assessment") or "")[:500],
           "next_actions":len(a.get("next_actions") or [])}
           for a in (r.get("matter_assessments") or [])[:4]]
    dump()
    print("RUN_SUMMARY",stage,json.dumps({k:info.get(k) for k in
           ("task_id","final_status","model_status","candidate_count","actual_provider_attempt_count",
            "role_results","role_counts","evidence_counts","failure_code")},
           ensure_ascii=False)[:7000],flush=True)
    return info,r

try:
    warm=call("GET","/",timeout=25)
    health=call("GET","/api/health",timeout=60)
    bootstrap=call("GET","/api/connectivity/bootstrap",timeout=65)
    result["environment"]={"homepage_http":warm["code"],"health_http":health["code"],
       "health_model":(health.get("data") or {}).get("model_status"),
       "health_commit":((health.get("data") or {}).get("deployment") or {}).get("commit"),
       "default_mode":(bootstrap.get("data") or {}).get("default_mode"),
       "bootstrap_http":bootstrap["code"],"cookie_names":[c.name for c in jar]}
    print("ENV",json.dumps(result["environment"],ensure_ascii=False),flush=True)
    dump()
    if health["code"]!=200 or bootstrap["code"]!=200 or not any(c.name=="audittrace_connectivity_session" for c in jar):
        raise RuntimeError("Bootstrap/service or session cookie is unavailable")
    # Require the strict-date-prompt fix to be live before spending provider calls.
    expected="7a22a5f0"
    check=(health.get("data") or {}).get("deployment",{}).get("commit") or ""
    if not check.startswith(expected):
        raise RuntimeError("New strict-A3 prompt deployment not live yet: "+str(check)[:12])
    first,seed=run_and_poll({"pair_id":PAIR,"analysis_scope":"matter_connectivity",
                            "mode":"calculation_only","matter_types":["transition_project","commitment","other","resource_efficiency","climate_risk"]},
                           "real_pdf_screening",210)
    if seed is None or first.get("final_status")!="completed":
        raise RuntimeError("Screening not completed; do not start model")
    matters=seed.get("matters") or []
    ev={x.get("evidence_id"):x for x in (seed.get("matter_evidence") or [])}
    ranked=[]
    for m in matters:
        proof=[ev.get(i) or {} for i in (m.get("evidence_ids") or [])]
        annual_154=any(x.get("document_id")=="BAOSTEEL_AR_2025" and x.get("pdf_page")==154 for x in proof)
        named="炼钢工程" in m.get("name","")
        factory="零碳高等级薄钢板" in m.get("name","")
        scores=120*annual_154+70*named+45*factory+15*(m.get("matter_type")=="transition_project")
        if any("宝钢湛江钢铁零碳高" in str(x.get("quote","")) for x in proof):scores+=50
        if scores>0:
            ranked.append((scores,m,proof))
    ranked.sort(key=lambda x:-x[0])
    first["ranked_concrete_candidates"]=[{"score":score,"id":m.get("matter_id"),
           "name":m.get("name"),"type":m.get("matter_type"),
           "pages":[{"doc":x.get("document_id"),"page":x.get("pdf_page")} for x in proofs]}
           for score,m,proofs in ranked[:12]]
    if not ranked:
        raise RuntimeError("No real Baosteel project matter found after screening; no fake selection")
    chosen=ranked[0][1]
    result["selection"]={"matter_id":chosen["matter_id"],"name":chosen["name"],
         "matter_type":chosen["matter_type"],"rationale":"Actual registered AR PDF p154 project/subproject and named annual evidence",
         "evidence_ids":chosen.get("evidence_ids") or [],
         "evidence_provenance":[{"doc":x.get("document_id"),"page":x.get("pdf_page"),"sha":x.get("source_sha256")} for x in ranked[0][2]]}
    print("CHOSEN",json.dumps(result["selection"],ensure_ascii=False),flush=True)
    dump()
    deep_body={"pair_id":PAIR,"analysis_scope":"matter_connectivity","mode":"five_agents",
       "matter_types":["transition_project","commitment","other","resource_efficiency","climate_risk"],
       "selected_matter_ids":[chosen["matter_id"]],
       "budget":{"max_provider_calls":14,"max_parallel_calls":1,
                 "max_matters":1,"max_role_rounds":1}}
    deep,full=run_and_poll(deep_body,"real_five_agent_selected_project",720)
    result["finished_at"]=datetime.now(timezone.utc).isoformat()
    result["final_assessment"]={"five_agent_model_status":deep.get("model_status"),
         "actual_provider_calls":deep.get("actual_provider_attempt_count"),
         "all_five_completed":all(deep["role_counts"].get(z,{}).get("complete",0)>0 for z in ("A1","A2","A3","A4","A5")),
         "task_id":deep.get("task_id")}
    dump()
    print("FINAL_ASSESSMENT",json.dumps(result["final_assessment"],ensure_ascii=False),flush=True)
except BaseException as exc:
    result["audit_error"]=repr(exc)[:500]
    result["finished_at"]=datetime.now(timezone.utc).isoformat()
    dump()
    print("AUDIT_ERROR",repr(exc),flush=True)
    raise
