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

COOKIE = "audittrace_connectivity_session"
CONNECTIVITY_RETENTION_SECONDS = 30 * 86400


def build_router(root: Path, reserve_model, quota_ledger) -> APIRouter:
    """延迟绑定现有应用配额，避免循环导入和第二套模型预算。"""
    router = APIRouter(prefix="/api/connectivity", tags=["connectivity"])
    lock = threading.RLock()
    stores = {}
    directory = root / "backend/runtime/connectivity"
    directory.mkdir(parents=True, exist_ok=True)

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
        if not request.cookies.get(COOKIE) or not hmac.compare_digest(owner(request), item["run_body"].get("owner", "")):
            raise HTTPException(403, "只能更正或取消当前浏览器创建的任务")
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "更正请求必须来自当前网站")

    def public(item: dict, request: Request | None = None) -> dict:
        view = store(item["task_id"]).snapshot(item["task_id"])
        if not view:
            raise HTTPException(404, "任务不存在")
        result = {k: v for k, v in view.items() if k not in {"run_body", "request_payload", "request_sha256", "idempotency_key_sha256"}}
        result["parent_task_id"] = item.get("run_body", {}).get("parent_task_id")
        is_owner = bool(request and request.cookies.get(COOKIE)
                        and hmac.compare_digest(owner(request), item.get("run_body", {}).get("owner", "")))
        result["can_modify"] = is_owner
        # 公共视图默认不含个人观察正文，只列条数；本人视图才展开。
        body = result.get("result")
        if isinstance(body, dict):
            body = dict(body)
            normalized = ConnectivityRun.model_validate({k:v for k,v in body.items() if k in ConnectivityRun.model_fields})
            body['overview'] = build_overview(normalized)
            body['ai_generated_content_notice'] = NOTICE
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

    @router.get("/bootstrap")
    def bootstrap(response: Response, request: Request):
        if not request.cookies.get(COOKIE):
            response.set_cookie(COOKIE, secrets.token_urlsafe(32), httponly=True, samesite="strict", secure=request.url.scheme == "https", max_age=30*86400)
        grouped = {}
        for doc in load_registry(root):
            pair = grouped.setdefault(doc.case_id, {"pair_id": doc.case_id, "company": doc.company, "period": doc.period, "documents": []})
            pair["documents"].append(doc.model_dump())
        rule_cards = {key: {**rule, "conditions": list(required_conditions(rule["operator"]))} for key, rule in RULES.items()}
        return {"pairs": list(grouped.values()), "topics": TOPICS, "rules": rule_cards, "notice": NOTICE,
                "task_persistence": "supabase" if demo_task_supabase_enabled() else "local", "schema_version": SCHEMA_VERSION,
                "intelligence_version": INTELLIGENCE_VERSION, "prompt_version": PROMPT_VERSION,
                "project_facts": project_facts(root)}

    @router.get("/readiness")
    def readiness(pair_id: str | None = None):
        return source_readiness(root, pair_id=pair_id)

    @router.get("/runs")
    def history(request: Request, limit: int = Query(5, ge=1, le=20), offset: int = Query(0, ge=0, le=10000)):
        # 无会话不能用空串哈希探测历史；已知链接读取沿用原有公开策略。
        if not request.cookies.get(COOKIE):
            raise HTTPException(409, "请先加载工作台以建立当前浏览器会话")
        rows = store().list_owned(owner(request), limit=limit + 1, offset=offset)
        items = [{k: row.get(k) for k in ("task_id", "case_id", "status", "created_at", "updated_at", "result_expires_at", "run_id", "failure_code")}
                 for row in rows[:limit]]
        return {"items": items, "limit": limit, "offset": offset,
                "next_offset": offset + limit if len(rows) > limit else None,
                "notice": NOTICE, "read_policy": "known_link_public; history_session_owned"}

    @router.post("/runs")
    def create(body: RunRequest, request: Request):
        if os.getenv("AUDITTRACE_DEMO_EXECUTOR_MODE","web").strip().lower() != "web":
            raise HTTPException(503,"关联核对执行器未就绪：当前版本须配置Web执行模式")
        if not request.cookies.get(COOKIE):
            raise HTTPException(409, "请先加载工作台以建立当前浏览器会话")
        if body.pair_id not in {d.case_id for d in load_registry(root)}:
            raise HTTPException(404, "报告对未登记")
        runtime = store()
        run_body = {**body.model_dump(), "kind": "connectivity", "owner": owner(request)}
        resume = None
        if body.retry_of_task_id:
            original = task(body.retry_of_task_id)
            authorize(request, original)
            snapshot = store(body.retry_of_task_id).snapshot(body.retry_of_task_id) or {}
            if original.get("case_id") != body.pair_id:
                raise HTTPException(422, "重试报告对必须与原任务一致")
            if set(original.get('run_body', {}).get('topics', body.topics)) != set(body.topics):
                raise HTTPException(422, '增量重试须沿用原事项选择；改变事项请发起新运行')
            if snapshot.get("result"):
                resume = ConnectivityRun.model_validate(snapshot["result"])
                if resume.execution_mode != body.mode:
                    raise HTTPException(422, "增量重试须沿用原执行模式；切换模式请发起新运行")
            run_body["parent_task_id"] = body.retry_of_task_id

        def execute(item):
            reservation = None
            result = None
            cancellation = {"checked_at": 0.0, "value": False}
            def cancelled():
                # 解析器逐页询问取消；远程存储不能每页都发一次数据库请求。
                now = time.monotonic()
                if not cancellation["checked_at"] or now-cancellation["checked_at"] >= 1:
                    cancellation["value"] = runtime.is_cancelled(item["task_id"])
                    cancellation["checked_at"] = time.monotonic()
                return cancellation["value"]
            def before_model():
                nonlocal reservation
                if runtime.is_cancelled(item["task_id"]):
                    raise InterruptedError("原任务已取消，未发送模型请求")
                reservation = reserve_model(request)
            try:
                resume_options = {"resume": resume} if resume is not None else {}
                result = run_pipeline(root, body,
                    progress=lambda *args: runtime.update_stage(item["task_id"], *args),
                    agent_progress=lambda *args: runtime.update_agent_step(item["task_id"], *args),
                    cancelled=cancelled, before_model=before_model, **resume_options)
            finally:
                if reservation:
                    calls = result.provider_calls if result else []
                    try:
                        quota_ledger().settle(reservation, input_tokens=sum(c.get("input_tokens") or 0 for c in calls), output_tokens=sum(c.get("output_tokens") or 0 for c in calls))
                    except PublicModelQuotaError as error:
                        if result is None:
                            raise
                        # 模型响应和预算结算是两种事实；保留已取得意见，明确结算未通过。
                        result.versions['quota_settlement'] = {'status': 'failed', 'code': error.code, 'message': str(error)[:240]}
                        runtime.update_stage(item['task_id'], 'structured_output', 'degraded', str(error)[:240])
            degraded = result.model_status not in {"not_requested", "three_agents_completed", "single_completed", "reused_completed"} or result.versions.get('quota_settlement', {}).get('status') == 'failed'
            runtime.update_task(item["task_id"], status="degraded" if degraded else "completed", run_id=result.run_id,
                result=result.model_dump(mode="json"), result_expires_at=result_expiry_iso(minimum_seconds=CONNECTIVITY_RETENTION_SECONDS))
        execute.__audittrace_request__ = request
        try:
            item = runtime.create(body.pair_id, run_body, execute, idempotency_key=request.headers.get("idempotency-key"))
        except IdempotencyConflict as error:
            raise HTTPException(409, str(error)) from error
        return public(item, request)

    @router.get("/runs/{task_id}")
    def read(task_id: str, request: Request):
        return public(task(task_id), request)

    @router.post("/runs/{task_id}/cancel")
    def cancel(task_id: str, request: Request):
        item = task(task_id)
        authorize(request, item)
        result = store(task_id).cancel(task_id)
        if result and result.get("cancel_rejected"):
            raise HTTPException(409, "模型调用已经开始，当前阶段不可中断；请等待实际结果")
        return public(task(task_id), request)

    def readable(task_id):
        """修订与导出读取完整结果；公共视图的裁剪只在响应层做，不能反过来丢数据。"""
        item = task(task_id)
        snapshot = store(task_id).snapshot(task_id) or {}
        if snapshot.get("status") not in {"completed", "degraded"} or not snapshot.get("result"):
            raise HTTPException(409, "任务尚无可读取的完成结果")
        return item, ConnectivityRun.model_validate(snapshot["result"])

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
            raise HTTPException(422, str(error)) from error
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
                refresh_analysis_status(child)
                child.versions['result_origin'] = 'user_revision'
                child.program_hints = build_program_hints(child)
                child.overview = build_overview(child)
                runtime.update_task(row["task_id"], status="completed", run_id=child.run_id, result=child.model_dump(mode="json"), result_expires_at=result_expiry_iso(minimum_seconds=CONNECTIVITY_RETENTION_SECONDS))
            correction_body = {"kind": "connectivity", "owner": owner(request), "parent_run_id": run.run_id, "parent_task_id": item["task_id"], "action_id": body.action_id, "mutation_digest": mutation_digest}
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
    def export(task_id: str, format_name: str, request: Request, private: bool = False):
        item, run = readable(task_id)
        if format_name not in {"json", "csv", "docx"}:
            raise HTTPException(404, "不支持的导出格式")
        is_owner = bool(request.cookies.get(COOKIE)) and hmac.compare_digest(owner(request), item["run_body"].get("owner", ""))
        # 公共导出默认剔除个人观察正文，只有本人且显式 private=1 才展开。
        include_personal = bool(private and is_owner)
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
