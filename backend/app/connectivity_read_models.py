"""分层读取投影；不把模型调用记录或证据全文放进轮询。"""
from copy import deepcopy

META_FIELDS = ("task_id", "case_id", "status", "created_at", "updated_at", "version",
               "result_expires_at", "run_id", "failure_code", "error", "steps", "agent_steps")
BASE_FIELDS = ("run_id", "company", "period", "documents", "report_set", "matter_schema_version",
               "execution_mode", "model_status", "result_revision", "parent_run_id", "matter_overview", "duration_ms")
DETAIL_FIELDS = ("matter_events", "matter_commitments", "matter_paths", "matter_relations",
                 "matter_explanations", "matter_assessments", "matter_tasks")


def metadata(item):
    value = {key: deepcopy(item.get(key)) for key in META_FIELDS}
    value["version"] = item.get("version", item.get("updated_at"))
    body = item.get("run_body") or item.get("request_payload") or {}
    value["run_body"] = {key: body.get(key) for key in ("kind", "owner", "analysis_scope", "parent_task_id")}
    return value


def visible_result(item):
    if item.get("status") == "expired":
        return None
    result = item.get("result")
    if item.get("status") in {"failed", "cancelled", "interrupted"} and not (result or {}).get("matter_schema_version"):
        return None
    return result


def project_result(result, kind, matter_id=None):
    if not result:
        return None
    base = {key: deepcopy(result[key]) for key in BASE_FIELDS if key in result}
    if not result.get("matter_schema_version"):
        return {**base, "projection_supported": False}
    versions = result.get("versions") or {}
    base["versions"] = {key: deepcopy(versions[key]) for key in
        ("matter_rule_fingerprints", "source_validity", "rule_validity", "budget", "seed_coverage", "investigation_scope", "matter_types", "result_origin") if key in versions}
    matters = result.get("matters") or []
    if kind in {"summary", "matters"}:
        base["matters"] = [{k: deepcopy(m.get(k)) for k in ("matter_id", "company_id", "name", "matter_type", "identity_status", "investigation_status", "identity_basis", "evidence_ids", "lineage")} for m in matters]
        if kind == "summary":
            investigated = {m["matter_id"] for m in matters if m.get("investigation_status") != "pending"}
            base["matter_assessments"] = [deepcopy(a) for a in result.get("matter_assessments", []) if a.get("matter_id") in investigated]
            planning = deepcopy(result.get("assurance_planning") or {})
            for field in ('risk_findings', 'evidence_requests'):
                planning[field] = [r for r in planning.get(field, []) if investigated.intersection(r.get('matter_ids', []))]
                for row in planning[field]:
                    for evidence_field in ('evidence', 'counter_evidence'):
                        if evidence_field in row:
                            row[evidence_field] = [{k: e[k] for k in ('evidence_id','document_id','pdf_page','report_period','report_type') if k in e} for e in row[evidence_field]]
            base["assurance_planning"] = planning
        return base
    matter = next((m for m in matters if m["matter_id"] == matter_id), None)
    if matter is None:
        return None
    base["matters"] = [deepcopy(matter)]
    base["current_task_ids"] = [c.get('task_id') for c in result.get('provider_calls', []) if c.get('task_id')]
    for key in DETAIL_FIELDS:
        base[key] = [deepcopy(row) for row in result.get(key, []) if row.get("matter_id") == matter_id or (key == "matter_tasks" and row.get("role") == "A1")]
    from .connectivity_matters import _all_refs
    ids = set(matter.get("evidence_ids", [])) | set(_all_refs(base))
    base["matter_evidence"] = [deepcopy(e) for e in result.get("matter_evidence", []) if e["evidence_id"] in ids]
    base["matter_tool_receipts"] = [deepcopy(r) for r in result.get("matter_tool_receipts", []) if r.get("matter_id") == matter_id]
    base["matter_rejections"] = [deepcopy(r) for r in result.get("matter_rejections", []) if r.get("matter_id") == matter_id]
    endpoints = {value for edge in base.get('matter_relations', []) for value in (edge.get('source_id'),edge.get('target_id'))}
    base["matter_graph"] = {"nodes": [deepcopy(n) for n in (result.get("matter_graph") or {}).get("nodes", []) if n.get("matter_id") == matter_id or n.get('id') in ids or n.get('id') in endpoints]}
    return base
