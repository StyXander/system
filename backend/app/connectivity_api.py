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

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
import pymupdf

from .connectivity_schemas import ConnectivityRun, CorrectionRequest, UserReviewRequest, ProfessionalRiskNote, ReviewEvent, RunRequest, NOTICE
from .connectivity_engine import calculate
from .connectivity_extraction import load_registry, ensure_source
from .connectivity_pipeline import run_pipeline, make_findings
from .connectivity_rules import RULES, TOPICS, required_conditions
from .demo_run_tasks import DemoRunTaskStore, SupabaseDemoRunTaskStore, IdempotencyConflict, result_expiry_iso
from .supabase_adapter import demo_task_supabase_enabled, get_demo_task_client, SupabaseConflict
from .source_viewer import preview_path, source_page_response, PDF_ACCESS_LOCK

COOKIE = "audittrace_connectivity_session"


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

    def public(item: dict) -> dict:
        view = store(item["task_id"]).snapshot(item["task_id"])
        if not view:
            raise HTTPException(404, "任务不存在")
        result = {k: v for k, v in view.items() if k not in {"run_body", "request_payload", "request_sha256", "idempotency_key_sha256"}}
        result["parent_task_id"] = item.get("run_body", {}).get("parent_task_id")
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
                "task_persistence": "supabase" if demo_task_supabase_enabled() else "local", "schema_version": "connectivity_v1"}

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
                result = run_pipeline(root, body,
                    progress=lambda *args: runtime.update_stage(item["task_id"], *args),
                    agent_progress=lambda *args: runtime.update_agent_step(item["task_id"], *args),
                    cancelled=cancelled, before_model=before_model)
                degraded = result.model_status not in {"not_requested", "three_agents_completed", "single_completed"}
                runtime.update_task(item["task_id"], status="degraded" if degraded else "completed", run_id=result.run_id,
                    result=result.model_dump(mode="json"), result_expires_at=result_expiry_iso())
            finally:
                if reservation:
                    calls = result.provider_calls if result else []
                    quota_ledger().settle(reservation, input_tokens=sum(c.get("input_tokens") or 0 for c in calls), output_tokens=sum(c.get("output_tokens") or 0 for c in calls))
        execute.__audittrace_request__ = request
        try:
            item = runtime.create(body.pair_id, run_body, execute, idempotency_key=request.headers.get("idempotency-key"))
        except IdempotencyConflict as error:
            raise HTTPException(409, str(error)) from error
        return public(item)

    @router.get("/runs/{task_id}")
    def read(task_id: str, request: Request):
        item = task(task_id)
        view = public(item)
        view["can_modify"] = bool(request.cookies.get(COOKIE)) and hmac.compare_digest(owner(request), item["run_body"].get("owner", ""))
        return view

    @router.post("/runs/{task_id}/cancel")
    def cancel(task_id: str, request: Request):
        item = task(task_id)
        authorize(request, item)
        result = store(task_id).cancel(task_id)
        if result and result.get("cancel_rejected"):
            raise HTTPException(409, "模型调用已经开始，当前阶段不可中断；请等待实际结果")
        return public(task(task_id))

    def readable(task_id):
        item = task(task_id)
        snapshot = public(item)
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
        child.checks = [calculate(validated if c.check_id == validated.check_id else c, child.occurrences) for c in child.checks]
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
        child = run.model_copy(deep=True)
        child.parent_run_id = run.run_id
        child.run_id = f"CONN-{uuid.uuid4().hex[:16].upper()}"
        child.result_revision += 1
        for check in child.checks:
            if check.check_id not in ids:
                continue
            before = check.model_dump()
            if body.action == "reading_confirmation":
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
                        return public(task(previous["task_id"]))
                    raise HTTPException(409, "该结果已有新修订，请读取子运行后再更正")
            elif head_file.exists():
                head = json.loads(head_file.read_text(encoding="utf-8"))
                if head["action_id"] == body.action_id:
                    if head.get("mutation_digest") != mutation_digest:
                        raise HTTPException(409, "同一操作编号不能提交不同内容")
                    return public(task(head["task_id"]))
                raise HTTPException(409, "该结果已有新修订，请读取子运行后再更正")
            def save_child(row):
                runtime.update_task(row["task_id"], status="completed", run_id=child.run_id, result=child.model_dump(mode="json"), result_expires_at=result_expiry_iso())
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
        return public(result)

    @router.get("/runs/{task_id}/export/{format_name}")
    def export(task_id: str, format_name: str):
        _, run = readable(task_id)
        if format_name not in {"json", "csv", "docx"}:
            raise HTTPException(404, "不支持的导出格式")
        from .connectivity_delivery import export_run
        payload, mime = export_run(run, format_name)
        return Response(payload, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{run.run_id}.{format_name}"'})

    def document(document_id):
        doc = next((d for d in load_registry(root) if d.document_id == document_id), None)
        if not doc:
            raise HTTPException(404, "来源未登记")
        path = ensure_source(root, doc)
        return doc, path

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
