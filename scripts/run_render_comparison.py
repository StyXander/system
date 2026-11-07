"""Run bounded comparisons through the deployed API; model credentials stay on Render.

The journal makes interrupted jobs resumable. Reusing an output directory reuses
the same task IDs and never silently starts another paid run. No API key is read.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_final_comparison import EXPERIMENT_GROUPS, FACTORIAL_2X2_GROUPS
from scripts.competition_receipts import execution_eligibility, usage_receipt, resolve_case

TERMINAL = {"completed", "degraded", "failed", "cancelled", "interrupted", "expired"}


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def receipt(row, task):
    result = task.get("result") or {}
    calls = result.get("provider_calls", [])
    selected=result.get('versions', {}).get('investigation_scope', {}).get('selected_matter_ids', [])
    if len(selected)==1:
        row.setdefault('requested_matter_id', row['matter_id'])
        row['matter_id']=selected[0]
    row.update(task_status=task["status"], run_id=result.get("run_id"),
               status="recorded" if result and task["status"] in {"completed", "degraded"} else "failed",
               model_status=result.get("model_status"), duration_ms=result.get("duration_ms"),
               fixed_evidence_sha256=result.get("versions", {}).get("fixed_evidence_sha256"),
               provider_calls=len(calls), successful_calls=sum(c.get("status") == "completed" for c in calls),
               attempted_calls=sum(bool(c.get("request_attempted")) for c in calls),
               **usage_receipt(calls),
               failure_code=task.get("failure_code"), cost=None,
               professional_quality="not_independently_evaluated")
    eligible, reason = execution_eligibility(result, task["status"])
    row.update(execution_eligible=eligible, execution_reason=reason,
               fixed_input_sha256=result.get("versions", {}).get("fixed_input_sha256"))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="https://audittrace-demo.onrender.com")
    p.add_argument("--report-set", required=True)
    p.add_argument("--matter-id", required=True)
    p.add_argument("--case-id", required=True)
    p.add_argument("--case-manifest", type=Path, default=ROOT / "docs/competition/development_cases.json")
    p.add_argument("--as-of", required=True)
    p.add_argument("--evidence-ids", type=Path)
    p.add_argument("--experiment-mode",choices=['fixed_evidence','end_to_end'],default='fixed_evidence')
    p.add_argument("--groups", default=",".join(FACTORIAL_2X2_GROUPS))
    p.add_argument("--allow-models", action="store_true")
    p.add_argument("--repeat", type=int, choices=range(1, 6), default=1)
    p.add_argument("--max-provider-calls", type=int, choices=range(1, 41), default=20)
    p.add_argument("--max-role-rounds", type=int, choices=range(1, 7), default=2)
    p.add_argument("--timeout", type=int, default=2400, help="Local polling deadline; does not cancel the remote task")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    groups = [g.strip() for g in args.groups.split(",")]
    if any(g not in EXPERIMENT_GROUPS for g in groups):
        p.error("Unknown group")
    if not args.allow_models and any(g != "G0" for g in groups):
        p.error("Real model tests require --allow-models")
    ids = json.loads(args.evidence_ids.read_text(encoding="utf-8")) if args.evidence_ids else []
    if args.experiment_mode=='fixed_evidence' and (not isinstance(ids, list) or not ids or len(ids) != len(set(ids))):
        p.error("Evidence IDs must be a nonempty unique list")
    if args.experiment_mode=='end_to_end':ids=[]
    try:
        question = resolve_case(args.case_manifest, args.case_id, report_set_id=args.report_set,
                                matter_id=args.matter_id, as_of=args.as_of)
    except ValueError as error:
        p.error(str(error))
    args.output.mkdir(parents=True, exist_ok=True)
    journal_path = args.output / "comparison.json"
    config = {"report_set_id": args.report_set, "matter_id": args.matter_id, "case_id": args.case_id,
              "as_of": args.as_of, "groups": groups, "repeat": args.repeat,
              "budget": {"max_matters": 1, "max_provider_calls": args.max_provider_calls,
                         "max_role_rounds": args.max_role_rounds, "max_parallel_calls": 2},
              "evidence_ids": sorted(ids), "experiment_mode":args.experiment_mode,"base_url": args.base_url.rstrip("/"), **question}
    fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else {
        "origin": "actual_render_api_execution", "experiment_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(), "config": config,
        "config_sha256": fingerprint, "runs": []}
    if journal["config_sha256"] != fingerprint:
        p.error("Output directory belongs to a different configuration")
    with httpx.Client(base_url=config["base_url"], timeout=120, follow_redirects=True) as client:
        def request(method, path, **kwargs):
            for attempt in range(3 if method=='GET' else 1):
                try:
                    r = client.request(method, path, **kwargs)
                    r.raise_for_status()
                    return r.json()
                except (httpx.TransportError,httpx.HTTPStatusError) as error:
                    transient=isinstance(error,httpx.TransportError) or error.response.status_code in {429,500,502,503,504}
                    if method!='GET' or not transient or attempt==2:raise
                    time.sleep(attempt+1)
        request("GET", "/api/connectivity/bootstrap")
        health = request("GET", "/api/health")
        if health.get("model_status") != "configured" and any(g != "G0" for g in groups):
            raise RuntimeError("Deployed model is not configured")
        # Preserve the deployment identity of every resumed batch as well.
        journal.setdefault("service_observations", []).append(health)
        save(journal_path, journal)
        for repeat in range(1, args.repeat + 1):
            order = groups[repeat % len(groups):] + groups[:repeat % len(groups)]
            for gid in order:
                row = next((x for x in journal["runs"] if x["group_id"] == gid and x["repeat"] == repeat), None)
                if row and row.get("status") in {"recorded", "failed"}:
                    continue
                if row is None:
                    group = EXPERIMENT_GROUPS[gid]
                    row = {"group_id": gid, "repeat": repeat, "case_id": args.case_id,
                           "matter_id": args.matter_id, "mode": group["mode"], "ablation": group["ablation"],
                           "experiment_mode": args.experiment_mode, "budget": config["budget"],
                           "result_file": f"{repeat}-{gid}.json", "status": "pending",
                           "idempotency_key": f"competition-{journal['experiment_id']}-{repeat}-{gid}"}
                    journal["runs"].append(row)
                    save(journal_path, journal)
                if not row.get("task_id"):
                    body = {"report_set_id": args.report_set, "as_of_date": args.as_of,
                            "analysis_scope": "matter_connectivity", "mode": row["mode"],
                            "ablation": row["ablation"], "selected_matter_ids": [args.matter_id],
                            "experiment_mode": args.experiment_mode, "fixed_evidence_ids": ids,
                            "comparison_run": True, "budget": config["budget"], **question}
                    row["deployment_before"] = request("GET", "/api/health").get("deployment", {})
                    task = request("POST", "/api/connectivity/runs", json=body,
                                   headers={"Idempotency-Key": row["idempotency_key"]})
                    row.update(task_id=task["task_id"], started_at=datetime.now(timezone.utc).isoformat())
                    save(journal_path, journal)
                print(f"{gid} repeat={repeat} task={row['task_id']}", flush=True)
                deadline = time.monotonic() + args.timeout
                last = None
                while True:
                    state = request("GET", f"/api/connectivity/runs/{row['task_id']}/status")
                    signature = (state["status"], state.get("current_stage"), str(state.get("agent_steps")))
                    if signature != last:
                        print(f"{gid}: {state['status']} stage={state.get('current_stage')} roles={state.get('agent_steps')}", flush=True)
                        last = signature
                    if state["status"] in TERMINAL:
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"Remote task remains active: {row['task_id']}; resume this exact command")
                    time.sleep(8)
                task = request("GET", f"/api/connectivity/runs/{row['task_id']}")
                result = receipt(row, task)
                row["deployment_after"] = request("GET", "/api/health").get("deployment", {})
                before_commit = row.get("deployment_before", {}).get("commit")
                after_commit = row["deployment_after"].get("commit")
                row["deployment_commit"] = before_commit if before_commit and before_commit == after_commit else None
                if not row["deployment_commit"]:
                    row.update(execution_eligible=False, execution_reason="deployment_identity_changed_or_unknown")
                save(args.output / f"{repeat}-{gid}.task.json", task)
                save(args.output / row["result_file"], result)
                save(journal_path, journal)
                for fmt in ("docx", "csv"):
                    if result:
                        r = client.get(f"/api/connectivity/runs/{row['task_id']}/export/{fmt}")
                        row[f"export_{fmt}_status"] = r.status_code
                        if r.is_success:
                            (args.output / f"{repeat}-{gid}.{fmt}").write_bytes(r.content)
                save(journal_path, journal)
                print(f"{gid}: {row['model_status']} calls={row['provider_calls']} successful={row['successful_calls']}", flush=True)
                if any(c.get("failure_code") in {"MODEL_HTTP_500", "MODEL_HTTP_502", "MODEL_HTTP_503", "MODEL_HTTP_504", "MODEL_HTTP_401", "MODEL_HTTP_403", "MODEL_HTTP_429"} for c in result.get("provider_calls", [])) and not row["execution_eligible"]:
                    journal["batch_stop_reason"] = "provider_unavailable; inspect receipts before starting more paid tasks"
                    save(journal_path, journal)
                    return 1
    hashes = {x.get("fixed_input_sha256") for x in journal["runs"] if x.get("status") == "recorded"}
    journal["fixed_evidence_check"] = ("matched" if len(hashes) == 1 and None not in hashes else "failed_or_incomplete") if args.experiment_mode=='fixed_evidence' else 'not_applicable'
    commits={r.get('deployment_commit') for r in journal['runs']}
    journal['deployment_check']='matched' if len(commits)==1 and None not in commits else 'failed_or_incomplete'
    journal["accuracy_status"] = "requires_independent_annotations"
    save(journal_path, journal)
    return int(len(journal["runs"]) != len(groups) * args.repeat or
               any(not r.get("execution_eligible") for r in journal["runs"]) or journal["fixed_evidence_check"] not in {"matched","not_applicable"} or journal['deployment_check']!='matched')


if __name__ == "__main__":
    raise SystemExit(main())
