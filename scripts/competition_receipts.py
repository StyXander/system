"""Execution eligibility for experiments; a saved result is not a completed task."""
import json
from pathlib import Path
from backend.app.connectivity_matter_completion import effective_role_status, known_usage


def resolve_case(manifest, case_id, *, report_set_id, matter_id, as_of):
    cases = json.loads(Path(manifest).read_text(encoding="utf-8")).get("scenarios", [])
    matches = [c for c in cases if c.get("case_id") == case_id]
    if len(matches) != 1:
        raise ValueError("CASE_ID_UNKNOWN_OR_DUPLICATE: 案例须唯一对应人工任务清单")
    case = matches[0]
    for field, value in (("report_set_id", report_set_id), ("matter_id", matter_id), ("as_of_date", str(as_of))):
        if case.get(field) != value:
            raise ValueError("CASE_INPUT_MISMATCH: " + field)
    if not str(case.get("question") or "").strip() or not case.get("question_id"):
        raise ValueError("CASE_QUESTION_MISSING")
    return {"research_question": case["question"], "question_id": case["question_id"],
            "benchmark_case_id": case_id, "research_task_type": case.get("research_task_type", "relation_tracing")}


def execution_eligibility(run, task_status=None):
    if task_status is not None and task_status not in {"completed", "degraded"}:
        return False, "task_" + str(task_status)
    if not run.get("matter_assessments"):
        return False, "missing_assessment"
    mode = run.get("execution_mode")
    status = run.get("model_status", "")
    if mode == "calculation_only" and status == "not_requested":
        return True, "rule_only"
    if status.endswith("_completed") and task_status != "degraded":
        tasks = run.get("matter_tasks", [])
        current = [t for t in tasks if not t.get("run_id") or t.get("run_id") == run.get("run_id")]
        latest = {(t.get("role"), t.get("matter_id")): t for t in current}
        if any(effective_role_status(t) in {"failed", "partial", "interrupted", "running"} for t in latest.values()):
            return False, "incomplete_role"
        return True, "completed"
    # Removing a role deliberately keeps the product's partial-workflow label.
    # This is usable only as its declared ablation, with every remaining role done.
    ablation = run.get("versions", {}).get("ablation")
    if mode == "five_agents" and ablation in {"no_temporal", "no_counterevidence"}:
        omitted = "A3" if ablation == "no_temporal" else "A4"
        required = {"A1", "A2", "A3", "A4", "A5"} - {omitted}
        tasks = run.get("matter_tasks", [])
        latest = {t.get("role"): t for t in tasks}
        if all(r in latest and effective_role_status(latest[r]) in {"completed", "reused"} for r in required):
            return True, "completed_declared_ablation"
    return False, "incomplete_or_unverifiable_model_status"


def usage_receipt(calls):
    values = known_usage(calls)
    attempted = [c for c in calls if c.get("request_attempted")]
    return {**values,
            "known_input_tokens": sum(c.get("input_tokens") or 0 for c in attempted),
            "known_output_tokens": sum(c.get("output_tokens") or 0 for c in attempted),
            "unknown_usage_calls": sum(c.get("input_tokens") is None or c.get("output_tokens") is None for c in attempted)}
