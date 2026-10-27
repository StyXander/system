"""关联核对接口：复用原有任务台账，公开读取与演示更正分别授权。

登记来源是唯一文件入口，不允许网页提交路径或金额代替原件。
完成任务可刷新恢复，关系修正生成子运行并保留原自动结果。
"""
from __future__ import annotations

import hashlib
import hmac
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from copy import deepcopy
import logging

from fastapi import APIRouter, HTTPException, Request, Response, Query
from fastapi.responses import JSONResponse, RedirectResponse
import pymupdf

from .connectivity_schemas import ConnectivityRun, CorrectionRequest, UserReviewRequest, ProfessionalRiskNote, ReviewEvent, RunRequest, NOTICE, SCHEMA_VERSION, INTELLIGENCE_VERSION
from .connectivity_engine import calculate
from .connectivity_extraction import load_registry, ensure_source, extract_document
from .connectivity_pipeline import run_pipeline, make_findings, PROMPT_VERSION
from .connectivity_intelligence import enrich_calculation, refresh_analysis_status
from .ai_opinion import build_program_hints
from .connectivity_overview import build_overview
from .connectivity_rules import RULES, TOPICS, required_conditions
from .demo_run_tasks import DemoRunTaskStore, SupabaseDemoRunTaskStore, IdempotencyConflict, result_expiry_iso
from .supabase_adapter import demo_task_supabase_enabled, get_demo_task_client, SupabaseConflict
from .source_viewer import preview_path, source_page_response, PDF_ACCESS_LOCK
from .public_model import PublicModelQuotaError

from .connectivity_facts import project_facts, execution_provenance
from .connectivity_bootstrap import source_readiness
from .connectivity_graph import refresh_run_sources
from .connectivity_financial_scenario import recalculate_scenario
from .connectivity_matter_schemas import ReportSetRequest, MatterRevisionRequest, MatterReconciliation
from .connectivity_report_sets import create_report_set, report_set_records, resolve_documents
from .connectivity_access import single_user_enabled

COOKIE = "audittrace_connectivity_session"
CONNECTIVITY_RETENTION_SECONDS = 30 * 86400


def build_router(root: Path, reserve_model, quota_ledger) -> APIRouter:
    """延迟绑定现有应用配额，避免循环导入和第二套模型预算。"""
    router = APIRouter(prefix="/api/connectivity", tags=["connectivity"])
    lock = threading.RLock()
    stores = {}
    directory = root / "backend/runtime/connectivity"
    directory.mkdir(parents=True, exist_ok=True)
    result_cache = OrderedDict()
    log = logging.getLogger(__name__)

    def normalized_result(item, *, layer="full"):
        body = item.get("result")
        if not body or body.get("projection_supported") is False:
            return body
        from .connectivity_extraction import source_path
        from .connectivity_source_cache import source_signature
        registry = {d.document_id: d for d in load_registry(root)}
        signatures = []
        for original in body.get("documents", []):
            doc = registry.get(original["document_id"])
            try:
                signatures.append((original["document_id"], doc.file_sha256, source_signature(source_path(root, doc))))
            except (OSError, AttributeError, ValueError):
                signatures.append((original["document_id"], "missing"))
        rules = root / "backend/app/connectivity_matter_rules.json"
        try:
            rule_signature = source_signature(rules)
        except OSError:
            rule_signature = None
        version = item.get("version", item.get("updated_at"))
        key = (item["task_id"], version, layer, tuple(signatures), rule_signature)
        with lock:
            if key in result_cache:
                result_cache.move_to_end(key)
                log.info("connectivity_result cache=hit task=%s layer=%s version=%s", item["task_id"], layer, version)
                return deepcopy(result_cache[key])
        normalized = ConnectivityRun.model_validate({k: v for k, v in body.items() if k in ConnectivityRun.model_fields})
        normalized = refresh_run_sources(root, normalized)
        if layer == "full":
            if normalized.matter_schema_version:
                from .connectivity_assurance_planning import build_assurance_planning
                normalized.assurance_planning = build_assurance_planning(normalized)
            value = normalized.model_dump(mode="json")
            value["overview"] = build_overview(normalized)
        else:
            all_fields = normalized.model_dump(mode="json")
            value = {k: all_fields.get(k, v) for k, v in body.items()}
            value["versions"] = all_fields["versions"]
            if layer in {"summary", "matters"} and normalized.versions.get("source_validity", {}).get("status") == "invalid":
                # 摘要没有证据全文，不能继续展示来源有效的旧判断。
                value["assurance_planning"] = {}
                for assessment in value.get("matter_assessments", []):
                    assessment["relation_support"] = "invalid"
                    assessment["unresolved"] = [*assessment.get("unresolved", []), "依赖来源变化，打开事项查看失效证据"]
        value["ai_generated_content_notice"] = NOTICE
        with lock:
            # 版本变化即淘汰旧版本；来源变化也不积累大结果。
            for old in list(result_cache):
                if old[0] == item["task_id"] and (old[1] != version or old[2] == layer):
                    del result_cache[old]
            result_cache[key] = deepcopy(value)
            while len(result_cache) > 16:
                result_cache.popitem(last=False)
        log.info("connectivity_result cache=miss task=%s layer=%s version=%s", item["task_id"], layer, version)
        return value

    def store(task_id=None):
        mode = "local" if task_id and task_id.startswith("CONNJOB-") else ("supabase" if task_id or demo_task_supabase_enabled() else "local")
        with lock:
            if mode not in stores:
                stores[mode] = SupabaseDemoRunTaskStore(get_demo_task_client()) if mode == "supabase" else DemoRunTaskStore(directory / "tasks", task_id_prefix="CONNJOB")
        return stores[mode]

    def owner(request: Request) -> str:
        return hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()

    def task(task_id: str):
        result = store(task_id).get(task_id)
        if not result or result.get("run_body", {}).get("kind") != "connectivity":
            raise HTTPException(404, "关联核对任务不存在")
        return result

    def authorize(request: Request, item: dict):
        if not single_user_enabled() and (not request.cookies.get(COOKIE) or not hmac.compare_digest(owner(request), item["run_body"].get("owner", ""))):
            raise HTTPException(403, "只能更正或取消当前浏览器创建的任务")
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "更正请求必须来自当前网站")

    def public(item: dict, request: Request | None = None) -> dict:
        view = store(item["task_id"]).snapshot(item["task_id"], item=item)
        if not view:
            raise HTTPException(404, "任务不存在")
        result = {k: v for k, v in view.items() if k not in {"run_body", "request_payload", "request_sha256", "idempotency_key_sha256"}}
        result["parent_task_id"] = item.get("run_body", {}).get("parent_task_id")
        is_owner = single_user_enabled() or bool(request and request.cookies.get(COOKIE)
                        and hmac.compare_digest(owner(request), item.get("run_body", {}).get("owner", "")))
        if item.get("run_body", {}).get("analysis_scope") == "matter_connectivity" and not is_owner:
            raise HTTPException(403, "事项调查任务仅当前创建会话可读取")
        result["can_modify"] = is_owner
        # 公共视图默认不含个人观察正文，只列条数；本人视图才展开。
        body = result.get("result")
        if isinstance(body, dict):
            body = normalized_result({**item, "result": body})
            result['result'] = body
        if isinstance(body, dict) and not is_owner:
            body = dict(body)
            notes = body.get("professional_notes") or []
            body["personal_observation_count"] = len(notes)
            body["professional_notes"] = []
            result["result"] = body
        elif isinstance(body, dict):
            body = dict(body)
            body["personal_observation_count"] = len(body.get("professional_notes") or [])
            result["result"] = body
        return result

    from .connectivity_matter_schemas import matter_enabled
    from .connectivity_access import access_policy

    @router.get("/bootstrap")
    def bootstrap(response: Response, request: Request):
        if not request.cookies.get(COOKIE):
            response.set_cookie(COOKIE, secrets.token_urlsafe(32), httponly=True, samesite="strict", secure=request.url.scheme == "https", max_age=30*86400)
        grouped = {}
        for doc in load_registry(root):
            pair = grouped.setdefault(doc.case_id, {"pair_id": doc.case_id, "company": doc.company, "period": doc.period, "documents": []})
            pair["documents"].append(doc.model_dump())
        rule_cards = {key: {**rule, "conditions": list(required_conditions(rule["operator"]))} for key, rule in RULES.items()}
        return {"pairs": list(grouped.values()), "topics": TOPICS, "rules": rule_cards, "notice": NOTICE, **access_policy(),
                "matter_enabled":matter_enabled(),"default_mode": "five_agents" if matter_enabled() else "three_agents", "matter_schema_version": "matter_connectivity_v1",
                "task_persistence": "supabase" if demo_task_supabase_enabled() else "local", "schema_version": SCHEMA_VERSION,
                "intelligence_version": INTELLIGENCE_VERSION, "prompt_version": PROMPT_VERSION,
                "project_facts": project_facts(root)}

    @router.get("/report-sets")
    def report_sets(company_id: str | None = None):
        records, persistence = report_set_records(root)
        return {"items": [r["report_set"] for r in records if not company_id or r["report_set"]["company_id"] == company_id],
            "documents": [d.model_dump(mode="json") for d in load_registry(root) if not company_id or d.company_id == company_id],
            "persistence": persistence}

    @router.post("/report-sets")
    def new_report_set(body: ReportSetRequest, request: Request):
        from .connectivity_catalog_api import can_import
        can_import(request)
        if request.headers.get("origin") and request.headers["origin"].rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "资料集合请求必须来自当前工作台")
        try:
            return create_report_set(root, body).model_dump(mode="json")
        except ValueError as error:
            raise HTTPException(422, getattr(error, "detail", str(error))) from error

    @router.get("/demo/baosteel")
    def baosteel_dossier():
        """Read-only case-specific evidence audit; never invokes the model or edits a task."""
        from .connectivity_project_demo import build_baosteel_dossier
        try:
            return build_baosteel_dossier(root)
        except (ValueError, OSError, RuntimeError) as error:
            log.warning("baosteel_dossier unavailable code=%s",type(error).__name__)
            raise HTTPException(503, "官方资料核验或专项证据索引尚未完成，请检查原件可用性及服务日志。") from error

    @router.get("/demo/baosteel/featured-runs")
    def baosteel_featured_real_agent_history():
        """Explicitly curated public-report-only, non-sensitive real supplier receipts.

        Unlike session-owned history this endpoint allows presentation on another
        browser, but NEVER exposes prompts, raw texts, private notes, secrets or
        unapproved run ids. Its source of truth is persisted production task data.
        """
        from .connectivity_project_demo import load_demo_config
        config=load_demo_config(root)
        safe=[]
        for task_id in config.get("featured_real_agent_task_ids",[])[:5]:
            if not isinstance(task_id,str) or not task_id.startswith("DEMO-RUN-"):
                continue
            try:
                item=task(task_id)
                body=item.get("run_body") or {}
                snapshot=store(task_id).snapshot(task_id,item=item) or {}
                result=snapshot.get("result") or {}
                documents=result.get("documents") or []
                if (body.get("mode")!="five_agents"
                    or body.get("analysis_scope")!="matter_connectivity"
                    or (body.get("pair_id")!="600019-2025" and
                        {d.get("document_id") for d in documents} != {"BAOSTEEL_AR_2025","BAOSTEEL_ESG_2025"})):
                    continue
                if result.get("dataset_role")=="synthetic" or (result.get("versions") or {}).get("provider_origin")=="injected_test_caller":
                    continue
                calls=result.get("provider_calls") or []
                if not any(c.get("request_attempted") and c.get("performed") and c.get("model") for c in calls):
                    continue
                role_rows=[]
                for role in ("A1","A2","A3","A4","A5"):
                    tasks=[t for t in (result.get("matter_tasks") or []) if t.get("role")==role]
                    last=tasks[-1] if tasks else {}
                    role_rows.append({"role":role,"status":last.get("status","not_run"),
                        "failure_code":last.get("failure_code"),"count":len(tasks),
                        "stop_reason":str(last.get("stop_reason") or "")[:190],
                        "identity_outcome":last.get("identity_outcome")})
                assessments=result.get("matter_assessments") or []
                a=assessments[0] if assessments else {}
                table=(result.get("versions") or {}).get("verified_project_table") or {}
                safe_table={"status":table.get("status"),"source_page":table.get("source_page"),
                    "document_id":table.get("document_id"),"source_sha256":table.get("source_sha256"),
                    "values_yuan":{key:table.get("values_yuan",{}).get(key) for key in
                        ("opening","increase","to_fixed","to_long_term","closing")},
                    "known_component_subtotal_yuan":table.get("known_component_subtotal_yuan"),
                    "note":str(table.get("note") or "")[:300]} if table.get("source_row_matched") else None
                safe.append({"task_id":task_id,"status":snapshot.get("status"),
                    "model_status":result.get("model_status"),"created_at":item.get("created_at"),
                    "models":sorted(set(c["model"] for c in calls if c.get("performed") and c.get("model"))),
                    "actual_model_requests":sum(bool(c.get("request_attempted")) for c in calls),
                    "role_results":role_rows,
                    "verified_financial_table":bool((result.get("versions") or {}).get("verified_project_table")),
                    "verified_table_detail":safe_table,
                    "financial_paths":len(result.get("matter_paths") or []),
                    "financial_occurrences":len(result.get("occurrences") or []),
                    "assessment_summary":str(a.get("summary") or "")[:520],
                    "financial_stage":str(a.get("financial_stage") or "")[:350],
                    "next_actions":[{"question":str(n.get("question") or "")[:220],
                        "requested_material":str(n.get("requested_material") or "")[:220]}
                        for n in (a.get("next_actions") or [])[:5]]})
            except Exception as exc:
                # A disappeared production snapshot or disconnected local CI database
                # must not take down the independent verified-PDF investigation screen.
                log.warning("featured_baosteel_run unavailable id=%s kind=%s",task_id,type(exc).__name__)
        return {"items":safe,"source":"live_saved_provider_receipts",
                "notice":"真实已保存任务，仅展示白名单内公开报告的脱敏模型回执；失败和降级原样保留。"}

    @router.get("/demo/baosteel/runs")
    def baosteel_saved_runs(request: Request):
        """Only list the current user's own real persisted tasks; no synthetic snapshots."""
        if not single_user_enabled() and not request.cookies.get(COOKIE):
            raise HTTPException(409, "请先加载工作台，建立本浏览器会话")
        owner_id = None if single_user_enabled() else owner(request)
        rows = store().list_owned(owner_id, limit=20, offset=0)
        items = []
        for row in rows:
            body = row.get("run_body") or row.get("request_payload") or {}
            company = str(row.get("company") or body.get("company") or "")
            if row.get("case_id") != "600019-2025" and "宝钢" not in company:
                continue
            items.append({"task_id":row["task_id"],"status":row.get("status"),
                "created_at":row.get("created_at"),"model_mode":body.get("mode"),
                "analysis_scope":body.get("analysis_scope"),
                "parent_task_id":body.get("parent_task_id"),
                "result_expires_at":row.get("result_expires_at")})
        return {"items":items[:8],"notice":"真实台账，只列当前会话有权查看的任务；部分完成和失败状态照实保留。"}

    @router.get("/readiness")
    def readiness(pair_id: str | None = None):
        return source_readiness(root, pair_id=pair_id)

    @router.get("/runs")
    def history(request: Request, limit: int = Query(5, ge=1, le=20), offset: int = Query(0, ge=0, le=10000)):
        # 无会话不能用空串哈希探测历史；已知链接读取沿用原有公开策略。
        if not single_user_enabled() and not request.cookies.get(COOKIE):
            raise HTTPException(409, "请先加载工作台以建立当前浏览器会话")
        rows = store().list_owned(None if single_user_enabled() else owner(request), limit=limit + 1, offset=offset)
        items = [{k: row.get(k) for k in ("task_id", "case_id", "status", "created_at", "updated_at", "result_expires_at", "run_id", "failure_code")}
                 for row in rows[:limit]]
        for value, row in zip(items, rows):
            value["company"] = row.get("company") or (row.get("result") or {}).get("company") or row.get("run_body", {}).get("company")
            value["parent_task_id"] = (row.get("run_body") or {}).get("parent_task_id")
            value["execution_mode"] = (row.get("run_body") or {}).get("mode")
        return {"items": items, "limit": limit, "offset": offset,
                "next_offset": offset + limit if len(rows) > limit else None,
                "notice": NOTICE, "read_policy": "single_user_workspace" if single_user_enabled() else "known_link_public; history_session_owned"}

    @router.post("/runs")
    def create(body: RunRequest, request: Request):
        if body.analysis_scope=="matter_connectivity" and not matter_enabled():raise HTTPException(503,"事项调查入口已关闭；历史结果仍可读取")
        if body.analysis_scope=="matter_connectivity" and body.mode!='calculation_only' and len(body.selected_matter_ids)!=1:
            raise HTTPException(422, {"code":"MATTER_SELECTION_REQUIRED","message":"请先无模型建立候选档案，再选择一个具体事项启动五Agent深查。单次仅调查一个事项。"})
        if body.mode != 'calculation_only':
            from .connectivity_catalog_api import authorize_model
            authorize_model(request)
        if os.getenv("AUDITTRACE_DEMO_EXECUTOR_MODE","web").strip().lower() != "web":
            raise HTTPException(503,"关联核对执行器未就绪：当前版本须配置Web执行模式")
        if not request.cookies.get(COOKIE):
            raise HTTPException(409, "请先加载工作台以建立当前浏览器会话")
        case_identity = body.report_set_id or body.pair_id
        if body.analysis_scope == "matter_connectivity":
            try:
                selected_set, _ = resolve_documents(root, body)
            except ValueError as error:
                raise HTTPException(422, getattr(error, "detail", str(error))) from error
        elif body.pair_id not in {d.case_id for d in load_registry(root)}:
            raise HTTPException(404, "报告对未登记")
        runtime = store()
        run_body = {**body.model_dump(mode="json"), "kind": "connectivity", "owner": owner(request)}
        if body.analysis_scope == "matter_connectivity":run_body['company']=selected_set.company
        if body.parent_task_id and not body.retry_of_task_id:
            predecessor = task(body.parent_task_id)
            authorize(request, predecessor)
            predecessor_set = ((predecessor.get("result") or {}).get("report_set") or {}).get("report_set_id")
            if not body.report_set_id or predecessor_set != body.report_set_id:
                raise HTTPException(422, "所选前序任务必须属于同一不可变资料集合；不能仅按企业名称关联历史")
            run_body["parent_task_id"] = body.parent_task_id
        resume = None
        if body.retry_of_task_id:
            original = task(body.retry_of_task_id)
            authorize(request, original)
            snapshot = store(body.retry_of_task_id).snapshot(body.retry_of_task_id, item=original) or {}
            if original.get("case_id") != case_identity:
                raise HTTPException(422, "重试报告对必须与原任务一致")
            if set(original.get('run_body', {}).get('topics', body.topics)) != set(body.topics):
                raise HTTPException(422, '增量重试须沿用原事项选择；改变事项请发起新运行')
            if original.get("run_body",{}).get("ablation","none")!=body.ablation:raise HTTPException(422,"重试不能改变消融条件")
            if body.analysis_scope=="matter_connectivity" and set(original.get("run_body",{}).get("matter_types",body.matter_types))!=set(body.matter_types):
                raise HTTPException(422,"增量重试须沿用事项类型；改变范围请创建新运行")
            if snapshot.get("result"):
                resume = ConnectivityRun.model_validate(snapshot["result"])
                if resume.execution_mode != body.mode:
                    raise HTTPException(422, "增量重试须沿用原执行模式；切换模式请发起新运行")
            run_body["parent_task_id"] = body.retry_of_task_id

        def execute(item):
            reservation = None
            result = None
            latest_run = None
            def checkpoint(run):
                nonlocal latest_run
                latest_run = run.model_copy(deep=True)
                runtime.update_task(item["task_id"], run_id=run.run_id, result=run.model_dump(mode="json"))
            cancellation = {"checked_at": 0.0, "value": False}
            def cancelled():
                # 解析器逐页询问取消；远程存储不能每页都发一次数据库请求。
                now = time.monotonic()
                if not cancellation["checked_at"] or now-cancellation["checked_at"] >= 1:
                    current_task = runtime.get(item["task_id"]) or {}
                    cancellation["value"] = runtime.is_cancelled(item["task_id"]) or current_task.get("failure_code") == "CANCEL_REQUESTED"
                    cancellation["checked_at"] = time.monotonic()
                return cancellation["value"]
            def before_model():
                nonlocal reservation
                if runtime.is_cancelled(item["task_id"]):
                    raise InterruptedError("原任务已取消，未发送模型请求")
                reservation = reserve_model(request)
            def provider_budget(run):
                if not reservation:return
                def amount(call,name):
                    if call.get(name) is not None:return call[name]
                    return call.get(name.replace("_tokens","_token_upper_bound"),0) if call.get("request_attempted") else 0
                quota_ledger().checkpoint_usage(reservation,input_tokens=sum(amount(c,"input_tokens") for c in run.provider_calls),
                    output_tokens=sum(amount(c,"output_tokens") for c in run.provider_calls))
            try:
                resume_options = {"resume": resume} if resume is not None else {}
                if body.analysis_scope=="matter_connectivity":resume_options["provider_budget"]=provider_budget
                result = run_pipeline(root, body,
                    progress=lambda *args: runtime.update_stage(item["task_id"], *args),
                    agent_progress=lambda *args: runtime.update_agent_step(item["task_id"], *args),
                    cancelled=cancelled, before_model=before_model, checkpoint=checkpoint, **resume_options)
            finally:
                if reservation:
                    calls = (result or latest_run).provider_calls if (result or latest_run) else []
                    unknown_usage = any(c.get("request_attempted") and (c.get("input_tokens") is None or c.get("output_tokens") is None) for c in calls)
                    if unknown_usage and (result or latest_run):
                        (result or latest_run).versions["usage_completeness"] = "provider_usage_unknown"
                    try:
                        # 未知usage不冒充零消耗；用量上界只用于额度占用，实际回执仍保留None。
                        def accounted(c, name):
                            if c.get(name) is not None:
                                return c[name]
                            return c.get(name.replace("_tokens", "_token_upper_bound"), 0) if c.get("request_attempted") else 0
                        quota_ledger().settle(reservation, input_tokens=sum(accounted(c, "input_tokens") for c in calls), output_tokens=sum(accounted(c, "output_tokens") for c in calls))
                    except PublicModelQuotaError as error:
                        if result is None:
                            raise
                        # 模型响应和预算结算是两种事实；保留已取得意见，明确结算未通过。
                        result.versions['quota_settlement'] = {'status': 'failed', 'code': error.code, 'message': str(error)[:240]}
                        runtime.update_stage(item['task_id'], 'structured_output', 'degraded', str(error)[:240])
            degraded = result.model_status not in {"not_requested", "three_agents_completed", "single_completed", "adaptive_completed", "reused_completed", "five_agents_completed", "matter_three_completed", "matter_single_completed"} or result.versions.get('quota_settlement', {}).get('status') == 'failed'
            from .connectivity_catalog import record_execution
            from .supabase_adapter import SupabaseError
            import sqlite3
            try:
                result.versions['catalog_execution'] = record_execution(root, result, item['task_id'])
            except (SupabaseError, sqlite3.Error) as error:
                # 分析历史保留；目录状态写入失败须显式出现在结果中，不能伪称已同步。
                result.versions['catalog_execution'] = {'status': 'failed', 'code': type(error).__name__}
            runtime.update_task(item["task_id"], status="cancelled" if result.versions.get("cancellation_requested") else "degraded" if degraded else "completed", run_id=result.run_id,
                result=result.model_dump(mode="json"), result_expires_at=result_expiry_iso(minimum_seconds=CONNECTIVITY_RETENTION_SECONDS))
        execute.__audittrace_request__ = request
        try:
            item = runtime.create(case_identity, run_body, execute, idempotency_key=request.headers.get("idempotency-key"))
        except IdempotencyConflict as error:
            raise HTTPException(409, str(error)) from error
        return public(item, request)

    @router.get("/runs/{task_id}")
    def read(task_id: str, request: Request):
        return public(task(task_id), request)

    def projected(task_id, request, kind="status", matter_id=None):
        from .supabase_adapter import SupabaseError
        try:
            item = store(task_id).get_projection(task_id, kind, matter_id)
        except SupabaseError as error:
            log.warning('connectivity_projection unavailable layer=%s code=%s',kind,error.code)
            raise HTTPException(503, "分层读取暂不可用；请检查数据库连接、权限及connectivity_read_projection迁移。未退回全量读取。") from error
        if not item or item.get("run_body", {}).get("kind") != "connectivity":
            raise HTTPException(404, "关联核对任务不存在")
        # 与完整读取保持相同可见性；分层端点不能绕开会话权限。
        if kind != "status" or item.get("run_body", {}).get("analysis_scope") == "matter_connectivity":
            authorize(request, item)
        is_owner = single_user_enabled() or bool(request.cookies.get(COOKIE) and hmac.compare_digest(owner(request), item["run_body"].get("owner") or ""))
        view = {k: v for k, v in item.items() if k != "run_body"}
        view["can_modify"] = is_owner
        if kind != "status":
            view["result"] = normalized_result(item, layer=f"detail:{matter_id}" if kind == "detail" else kind)
            if view["result"]:
                view["result"]["projection_layer"] = kind
        return view

    @router.get("/runs/{task_id}/status")
    def read_status(task_id: str, request: Request):
        view = projected(task_id, request)
        # 进度由真实阶段与角色状态投影，不复制结果或模型调用正文。
        steps = view.get("steps") or {}
        current_stage = next((k for k, v in steps.items() if v.get("status") == "running"), None)
        return {"task_id": view["task_id"], "status": view["status"], "current_stage": current_stage,
            "steps": {k: {"status": v.get("status"), "updated_at": v.get("updated_at")} for k, v in steps.items()},
            "agent_steps": {k: {"status": v.get("status"), "updated_at": v.get("updated_at")} for k, v in (view.get("agent_steps") or {}).items()},
            "updated_at": view["updated_at"], "version": view["version"]}

    @router.get("/runs/{task_id}/summary")
    def summary(task_id: str, request: Request):
        return projected(task_id, request, "summary")

    @router.get("/runs/{task_id}/matters")
    def matters(task_id: str, request: Request):
        item = projected(task_id, request, "matters")
        view = item.get("result") or {}
        return {"items": view.get("matters", []), "overview": view.get("matter_overview", {}), "result_revision": view.get("result_revision")}

    @router.get("/runs/{task_id}/matters/{matter_id}")
    def matter_detail(task_id: str, matter_id: str, request: Request):
        item = projected(task_id, request, "detail", matter_id)
        view = item.get("result") or {}
        matter = next((m for m in view.get("matters", []) if m["matter_id"] == matter_id), None)
        if matter is None:
            raise HTTPException(404, "事项不存在")
        result = {"matter": matter, "result_revision": view["result_revision"], "task_id": task_id,
                  "version": item.get("version"), "result": view}
        for field in ("matter_events", "matter_commitments", "matter_paths", "matter_relations", "matter_explanations", "matter_assessments", "matter_tasks"):
            result[field] = [r for r in view.get(field, []) if r.get("matter_id") == matter_id]
        ids = set(matter["evidence_ids"])
        from .connectivity_matters import _all_refs
        ids.update(_all_refs(result))
        result["evidence"] = [e for e in view.get("matter_evidence", []) if e["evidence_id"] in ids]
        return result

    @router.post("/runs/{task_id}/cancel")
    def cancel(task_id: str, request: Request):
        item = task(task_id)
        authorize(request, item)
        if item.get("run_body", {}).get("analysis_scope") == "matter_connectivity":
            if item.get("status") not in {"queued","running"}:return public(item,request)
            if not item.get("non_interruptible"):
                store(task_id).cancel(task_id)
                return public(task(task_id),request)
            # 已发出的请求等待回执并结算，拒绝继续发送；保留可恢复检查点。
            store(task_id).update_task(task_id, failure_code="CANCEL_REQUESTED")
            return public(task(task_id), request)
        result = store(task_id).cancel(task_id)
        if result and result.get("cancel_rejected"):
            raise HTTPException(409, "模型调用已经开始，当前阶段不可中断；请等待实际结果")
        return public(task(task_id), request)

    def readable(task_id, *, force_sources=False):
        """修订与导出读取完整结果；公共视图的裁剪只在响应层做，不能反过来丢数据。"""
        item = task(task_id)
        snapshot = store(task_id).snapshot(task_id, item=item) or {}
        if snapshot.get("status") not in {"completed", "degraded", "cancelled", "interrupted", "failed"} or not snapshot.get("result"):
            raise HTTPException(409, "任务尚无可读取的完成结果")
        return item, refresh_run_sources(root, ConnectivityRun.model_validate(snapshot["result"]), force=force_sources)

    @router.post("/runs/{task_id}/revalidate-sources")
    def revalidate_sources(task_id: str, request: Request):
        item = task(task_id)
        authorize(request, item)
        if not item.get("result"):
            raise HTTPException(409, "任务尚无结果")
        run = refresh_run_sources(root, ConnectivityRun.model_validate(item["result"]), force=True)
        with lock:
            for key in list(result_cache):
                if key[0] == task_id:
                    del result_cache[key]
        return {"task_id": task_id, "source_validity": run.versions.get("source_validity", {"status": "valid"})}

    @router.post("/runs/{task_id}/matter-revisions")
    def matter_revision(task_id: str, body: MatterRevisionRequest, request: Request):
        item, run = readable(task_id)
        authorize(request, item)
        child = run.model_copy(deep=True)
        from .connectivity_matter_revision import revise_matters
        try:
            revise_matters(child, body)
        except ValueError as error:
            raise HTTPException(422, getattr(error, "detail", str(error))) from error
        child.parent_run_id = run.run_id
        child.run_id = "CONN-" + uuid.uuid4().hex[:16].upper()
        child.result_revision += 1
        child.prior_provider_calls = [*run.prior_provider_calls, *run.provider_calls]
        child.provider_calls = []
        return save_revision(item, run, body, request, child)

    @router.post("/runs/{task_id}/matter-reconciliations")
    def matter_reconciliation(task_id: str, body: MatterReconciliation, request: Request):
        item, run = readable(task_id)
        authorize(request, item)
        from .connectivity_matter_revision import reconcile_matter
        try:
            return reconcile_matter(run, body)
        except ValueError as error:
            raise HTTPException(422, getattr(error, "detail", str(error))) from error

    @router.get("/runs/{task_id}/scenario")
    def scenario(task_id: str, request: Request, price: str = Query(..., max_length=24), usage: str = Query(..., max_length=24)):
        """情景是只读计算投影；两参数不修改企业原值或历史运行。"""
        scenario_item, run = readable(task_id)
        if run.matter_schema_version:
            authorize(request, scenario_item)
        try:
            computed = recalculate_scenario(run.financial_scenario, price, usage)
        except ValueError as error:
            raise HTTPException(422, getattr(error, "detail", str(error))) from error
        return {"run_id": run.run_id, "result_revision": run.result_revision, "scenario": computed}

    @router.post("/runs/{task_id}/corrections")
    def correct(task_id: str, body: CorrectionRequest, request: Request):
        item, run = readable(task_id)
        authorize(request, item)
        if not any(c.check_id == body.check.check_id for c in run.checks):
            raise HTTPException(422, "更正项不属于该运行")
        if body.expected_revision != run.result_revision:
            raise HTTPException(409, "结果版本已变化，请重新读取")
        try:
            validated = calculate(body.check, run.occurrences)
        except ValueError as error:
            raise HTTPException(422, getattr(error, "detail", str(error))) from error
        # 引用校验不通过时不能把更正标成有依据的人工确认。
        if any("引用" in gap or "有效原文" in gap for gap in validated.unresolved):
            raise HTTPException(422, "更正所用依据未能在本次原文核实")
        child = run.model_copy(deep=True)
        child.parent_run_id = run.run_id
        child.run_id = f"CONN-{uuid.uuid4().hex[:16].upper()}"
        child.result_revision += 1
        validated.review_status = "demo_modified"
        old = next(c for c in run.checks if c.check_id == validated.check_id)
        child.checks = [enrich_calculation(calculate(validated if c.check_id == validated.check_id else c, child.occurrences), child.occurrences) for c in child.checks]
        refresh_analysis_status(child)
        child.findings = make_findings(child.checks)
        child.reviews.append(ReviewEvent(event_id=body.action_id, actor=body.actor, action="relationship_correction", reason=body.reason,
            check_id=validated.check_id, before=old.model_dump(), after=validated.model_dump()))
        return save_revision(item, run, body, request, child)

    @router.post("/runs/{task_id}/reviews")
    def review(task_id: str, body: UserReviewRequest, request: Request):
        item, run = readable(task_id)
        authorize(request, item)
        if body.expected_revision != run.result_revision:
            raise HTTPException(409, "结果版本已变化，请重新读取")
        ids = set(body.check_ids)
        if len(ids) != len(body.check_ids) or not ids.issubset({c.check_id for c in run.checks}):
            raise HTTPException(422, "所选关系必须属于本次结果且不可重复")
        if body.action == "personal_observation" and (len(ids) != 1 or len(body.observation.strip()) < 3):
            raise HTTPException(422, "个人观察须对应一项关系并填写具体内容")
        if body.action in {"ai_accept", "ai_reject"}:
            if len(ids) != 1 or not any(a.check_id in ids and a.status == "current" for a in run.ai_analyses):
                raise HTTPException(422, "请选一项与当前结果绑定的AI意见；旧意见需先重新分析")
        child = run.model_copy(deep=True)
        child.parent_run_id = run.run_id
        child.run_id = f"CONN-{uuid.uuid4().hex[:16].upper()}"
        child.result_revision += 1
        for check in child.checks:
            if check.check_id not in ids:
                continue
            before = check.model_dump()
            if body.action in {"ai_accept", "ai_reject"}:
                opinion = next(a for a in child.ai_analyses if a.check_id == check.check_id)
                before = opinion.model_dump()
                opinion.review_status = "accepted" if body.action == "ai_accept" else "rejected"
                child.reviews.append(ReviewEvent(event_id=body.action_id, actor=body.actor, action=body.action,
                    reason=body.reason, check_id=check.check_id, before=before, after=opinion.model_dump()))
                continue
            elif body.action == "reading_confirmation":
                check.review_status = "read_confirmed"
            else:
                child.professional_notes.append(ProfessionalRiskNote(check_id=check.check_id,
                    observation=body.observation.strip(), reason=body.reason, actor=body.actor))
            child.reviews.append(ReviewEvent(event_id=body.action_id, actor=body.actor, action=body.action,
                reason=body.reason, check_id=check.check_id, before=before, after=check.model_dump()))
        return save_revision(item, run, body, request, child)

    def save_revision(item, run, body, request, child):
        if os.getenv("AUDITTRACE_DEMO_EXECUTOR_MODE","web").strip().lower() != "web":
            raise HTTPException(503,"关联核对修订执行器未就绪：当前版本须配置Web执行模式")
        runtime = store(item["task_id"])
        mutation_digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        with lock:
            head_file = directory / "revisions" / f"{run.run_id}.json"
            head_file.parent.mkdir(parents=True, exist_ok=True)
            remote = not item["task_id"].startswith("CONNJOB-")
            if remote:
                # 子修订本身也在共享任务表内，刷新或实例更换不依赖本机侧文件。
                rows = get_demo_task_client()._request("GET", "rest/v1/demo_run_tasks", service=True,
                    params={"request_payload->>parent_run_id": f"eq.{run.run_id}", "task_kind": "eq.connectivity", "select": "task_id,request_payload", "limit": "1"})
                if rows:
                    previous = rows[0]
                    if previous["request_payload"].get("action_id") == body.action_id:
                        if previous["request_payload"].get("mutation_digest") != mutation_digest:
                            raise HTTPException(409, "同一操作编号不能提交不同内容")
                        return public(task(previous["task_id"]), request)
                    raise HTTPException(409, "该结果已有新修订，请读取子运行后再更正")
            elif head_file.exists():
                head = json.loads(head_file.read_text(encoding="utf-8"))
                if head["action_id"] == body.action_id:
                    if head.get("mutation_digest") != mutation_digest:
                        raise HTTPException(409, "同一操作编号不能提交不同内容")
                    return public(task(head["task_id"]), request)
                raise HTTPException(409, "该结果已有新修订，请读取子运行后再更正")
            def save_child(row):
                if child.matter_schema_version:
                    from .connectivity_matters import finish_projection
                    finish_projection(child)
                refresh_analysis_status(child)
                child.versions['result_origin'] = 'user_revision'
                child.program_hints = build_program_hints(child)
                child.overview = build_overview(child)
                runtime.update_task(row["task_id"], status="completed", run_id=child.run_id, result=child.model_dump(mode="json"), result_expires_at=result_expiry_iso(minimum_seconds=CONNECTIVITY_RETENTION_SECONDS))
            correction_body = {"kind": "connectivity", "owner": owner(request), "analysis_scope": run.versions.get("analysis_scope", "legacy_checks"), "parent_run_id": run.run_id, "parent_task_id": item["task_id"], "action_id": body.action_id, "mutation_digest": mutation_digest}
            try:
                # 每个父版本使用一个稳定修订键，复用共享任务表既有唯一约束。
                result = runtime.create(item["case_id"], correction_body, save_child, idempotency_key=f"connectivity-revision-{run.run_id}")
            except (SupabaseConflict, IdempotencyConflict) as error:
                raise HTTPException(409, "修订发生并发冲突，请重新读取当前结果") from error
            if not remote:
                temporary = head_file.with_suffix(".tmp")
                temporary.write_text(json.dumps({"task_id": result["task_id"], "action_id": body.action_id, "mutation_digest": mutation_digest}), encoding="utf-8")
                temporary.replace(head_file)
        return public(result, request)

    @router.get("/runs/{task_id}/export/{format_name}")
    def export(task_id: str, format_name: str, request: Request, private: bool = False,
               scenario_price: str | None = Query(None, max_length=24), scenario_usage: str | None = Query(None, max_length=24)):
        item, run = readable(task_id, force_sources=True)
        if run.matter_schema_version:
            authorize(request, item)
        if format_name not in {"json", "csv", "docx"}:
            raise HTTPException(404, "不支持的导出格式")
        is_owner = bool(request.cookies.get(COOKIE)) and hmac.compare_digest(owner(request), item["run_body"].get("owner", ""))
        # 公共导出默认剔除个人观察正文，只有本人且显式 private=1 才展开。
        include_personal = bool(private and is_owner)
        if scenario_price is not None or scenario_usage is not None:
            if scenario_price is None or scenario_usage is None:
                raise HTTPException(422, "情景导出须同时提供价格与实现比例")
            try:
                run.financial_scenario = recalculate_scenario(run.financial_scenario, scenario_price, scenario_usage)
            except ValueError as error:
                raise HTTPException(422, getattr(error, "detail", str(error))) from error
        from .connectivity_delivery import export_run, verify_export_same_source
        payload, mime = export_run(run, format_name, include_personal=include_personal)
        if format_name == "json":
            # 同源校验进入导出链路：导出与页面结果不一致时拒绝下发，而不是只写在单测里。
            problems = verify_export_same_source(run, payload)
            if problems:
                raise HTTPException(500, "导出与页面结果不同源，已拒绝下载：" + "；".join(problems[:3]))
        return Response(payload, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{run.run_id}.{format_name}"'})

    def document(document_id):
        doc = next((d for d in load_registry(root) if d.document_id == document_id), None)
        if not doc:
            raise HTTPException(404, "来源未登记")
        path = ensure_source(root, doc)
        return doc, path

    @router.get("/version-chains/{company_id}")
    def version_chain(company_id: str):
        """企业披露版本链独立入口：不受双报告配对限制，也不产出跨报告差额。"""
        from .connectivity_versions import build_version_chain
        documents = [doc for doc in load_registry(root) if doc.company_id == company_id]
        if not documents:
            raise HTTPException(404, "该公司未登记公开版本")
        entries = []
        for doc in sorted(documents, key=lambda item: (item.disclosure_date or "9999", item.document_id)):
            try:
                rows, _, _ = extract_document(root, doc, ["research", "environment", "intensity"])
            except (OSError, ValueError) as error:
                raise HTTPException(503, f"{doc.document_id} 原件暂不可读取：{type(error).__name__}") from error
            entries.append({"document": doc, "occurrences": rows})
        chain = build_version_chain(entries)
        return {"company_id": company_id, "notice": NOTICE, **chain}

    @router.get("/sources/{document_id}")
    def source(document_id: str, page: int = 1, view: bool = True):
        doc, path = document(document_id)
        if page < 1:
            raise HTTPException(422, "PDF顺序页必须大于零")
        if not view:
            return RedirectResponse(doc.source_url)
        return source_page_response(path, {"document_id": doc.document_id, "source_file": f"{doc.company} {doc.period} {doc.report_type}"}, page,
                                    f"/api/connectivity/sources/{document_id}", notice=NOTICE, original_url=doc.source_url)

    @router.get("/sources/{document_id}/pages/{page}.png")
    def page_image(document_id: str, page: int):
        doc, path = document(document_id)
        with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
            if page < 1 or page > len(pdf):
                raise HTTPException(404, "PDF页码超出范围")
            source = pdf[page-1]
            scale = min(1.5, 2200/max(source.rect.width, source.rect.height))
            image = source.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
        return Response(image, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

    return router
