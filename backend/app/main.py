"""审迹智链 0.7.1 主流程、运行状态机与公开接口。

正式产品只服务审计计划阶段的销售与收款循环风险讨论准备。
业务承接与续聘不进入当前运行接口，只在未来路线图中保留。
一次运行从案例字段开始，不接受前端直接提交计算结果。
案例注册表决定可用年度、资料时点和是否允许模型传输。
确定性规则负责计算，模型负责受约束的语义质疑与反证。
程序筛查、模型建议、人工处理和运行完整性是四个独立状态。
四层状态任何时候都不能合并成一个模糊的成功或失败标签。
程序候选只表示命中工程筛查条件，不表示存在重大错报。
规则未触发只表示当前条件未命中，不允许在页面写成无风险。
模型建议只能针对待核查草稿，不能覆盖程序筛查原始状态。
人工处理由真人提交，自动化账户不能伪装成人工批准。
运行完整性反映技术链是否走完，不评价专业结论是否正确。
仅计算模式是明确的不完整预检，不能生成模型成功记录。
完整分析模式才允许依次执行检索、三角色和最终草稿生成。
案例禁止模型传输时保留本地计算，同时关闭模型调用主链。
模型密钥缺失时显示未配置，不使用前端假数据补成完整结果。
RAG 失败时不调用模型，防止没有原文证据的旁路推理。
三角色任一步失败时最终草稿为空，完整性保持模型链失败。
三个角色全部完成后才允许标记完整分析并保存最终草稿。
没有程序候选时完整分析可完整结束，但三个角色均不适用。
模型配额只限制公开演示中的候选调用，不影响本地测试计算。
配额按来源地址和全局窗口双重控制，避免意外消耗付费额度。
运行编号在创建时生成，贯穿证据包、角色输出和人工复核。
运行上下文保存规则版本、提示词版本、模式版本和参数快照。
参数快照明确标记待专业签字，不能假装成正式审计标准。
计划重要性由使用者输入，缺失时不得评价金额重要性。
R1 增速差阈值属于工程草案，真人签字前始终保留草案标识。
R1 比较使用来源行中的明确口径，不自动把净额改成账面余额。
两项同时下降时仍会计算方向，但风险卡必须提示正常解释空间。
周转天数使用平均应收账款，缺少前两年时不伪造趋势数值。
持续期间只按已登记连续数据计算，不把缺年视为持续异常。
金额变化与重要性的比较独立于相对增速，避免小金额噪声。
R2 只是辅助规则，不能抢占 R1 主链或扩张正式产品范围。
来源验证先检查字段完整、披露时点、文件哈希和报表口径。
来源验证失败时规则返回来源不完整，不继续形成候选风险卡。
计算字段证据进入公开证据包时去除本机绝对存储路径。
案例包公开账龄作为增强证据进入模型上下文和网页详情。
增强证据可以关闭同名资料缺口，但不能自动降低风险状态。
期后回款和合同条款仍缺失时继续出现在待索取资料清单中。
RAG 固定问题只针对已经形成的候选事项，减少无目的检索。
检索结果保留问题编号、检索编号、页码、片段和来源哈希。
没有检索命中时生成证据缺口记录，不用相似文本替代原文。
Agent 证据包按规则筛选字段和检索结果，避免跨规则串用。
模型只能引用当前规则证据包中的编号，硬校验在模型之后执行。
最终草稿标记为 AI 辅助生成，并声明正式判断由人工完成。
AI 建议聚合保持保留、降级、暂缓的明确优先逻辑。
人工复核接口保存处理、备注、复核人、时间和导出批准状态。
人工姓名为空或自动化身份时不能获得正式导出权限。
缓存只保存已批准运行的可回放结果，不重新调用模型。
缓存回放必须标记执行方式，不能冒充新的真实模型运行。
报告导出要求真人批准，未批准请求返回冲突而不是空白文档。
报告内容读取最终草稿、证据包和人工处理，不再旁路忽略模型。
报告同时展示程序计算与 AI 建议，避免读者误把二者合并。
状态接口读取唯一项目状态文件，网页不能硬编码验收结论。
健康接口只说明服务与模型配置状态，不说明完整链已经成功。
案例模板接口必须在无密钥环境下也能正常下载。
案例导入接口必须同时确认合法来源和个人信息处理状态。
来源文件接口只能打开登记文档，任意文件名读取必须被拒绝。
补充资料接口将新证据绑定父运行和资料日期，保留原始时点。
补充资料续分析默认重新执行完整主链，不固定关闭模型检查。
旧字段更正属于兼容路径，必须醒目标记并保留原始字段来源。
网页根入口由同一后端提供，避免静态双击产生假成功体验。
旧版网页只读保留为历史对照，不参与正式根入口验收。
异常响应应使用稳定状态码和可理解边界，不泄露内部密钥。
模型异常只公开失败阶段与稳定代码，不保存敏感原始输出。
运行存储、RAG 索引和案例文件按测试命名空间隔离。
自动化测试不得污染真人运行，也不得产生虚假人工签名。
版本升级必须同步结构模式、状态文件、网页、报告和文档。
新增接口不得绕过案例注册、来源验证或人工导出闸门。
本模块的目标是让每个成功与失败都能被复现和解释。
"""

from __future__ import annotations

import hashlib
import json
import math
import mimetypes
import os
import re
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .agents import PROMPT_VERSION, run_agent_chain
from .auth import (
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    authorize_case_access,
    authorize_case_write,
    authorize_model_transfer,
    authorize_pipeline_task,
    configured_persistence,
    identity_from_access_token,
    identity_for_task,
    is_public_case,
    model_consent_contract,
    optional_authenticated,
    require_authenticated,
    request_identity,
)
from .cases import (
    _recompute_cninfo_human_status,
    build_case_template_zip,
    confirm_cninfo_field,
    get_case,
    get_cninfo_field_readiness,
    get_financial_rows,
    get_period_sources,
    import_case_zip,
    list_cases,
    resolve_case_document,
)
from .industry_gate import build_not_applicable_context, evaluate_industry_gate
from .industry_rules import build_industry_prescreen
from .privacy import model_transmission_scope, scan_sensitive_payload
from .catalog import (
    bootstrap_runtime_catalog,
    create_refresh_job,
    list_cache_entries,
    recover_orphaned_refresh_jobs,
    refresh_report,
    resolve_analysis_source,
    update_refresh_job,
)
from .data import CASE_ID, EVIDENCE, SOURCE_SNAPSHOT_ID
from .delivery import build_report, cache_run, replay_cache
from .rag import get_retrieval, prepare_index, question_set, retrieve, status as rag_status
from .run_store import load_run, save_human_review, save_run
from .seed_catalog import get_seed_case, load_seed_cases, seed_catalog_summary
from .schemas import (
    AI_GENERATED_CONTENT_NOTICE,
    AgentStep,
    AuthLoginRequest,
    CachePrewarmRequest,
    CacheResolveRequest,
    CNInfoCompanyConfirmation,
    CNInfoFieldConfirmation,
    CNInfoPipelineRequest,
    HealthResponse,
    HumanReviewRequest,
    ModelCheck,
    ModelTransferConsentRequest,
    RagRetrieveRequest,
    RuleResult,
    RunRequest,
    RunResponse,
    StoredRunResponse,
    SupplementRerunRequest,
)
from .source_cache import ensure_standard_sources
from .supplements import create_supplement, load_supplement, mark_supplement_storage
from .supabase_adapter import (
    SupabaseAuthError,
    SupabaseConflict,
    SupabaseError,
    SupabaseLeaseLost,
    get_supabase_client,
    supabase_enabled,
)
from .pipeline import (
    create_task,
    load_task,
    mark_analysis_failure,
    materialize_task,
    prepare_report_years,
    queue_retry,
    run_ingestion,
    _save_task,
    update_analysis_result,
)


ENGINE_VERSION = "0.7.1"
RUN_SCHEMA_VERSION = "run_output_v2"
R1_VERSION = "r1_v0.4-draft"
R2_VERSION = "r2_v0.2-auxiliary-draft"
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(WORKSPACE_ROOT / ".env")

# 公开演示时仅用进程内窗口保护付费模型；本地与自动化测试不受影响。
_PUBLIC_MODEL_REQUESTS_BY_IP: dict[str, deque[float]] = {}
_PUBLIC_MODEL_REQUESTS_GLOBAL: deque[float] = deque()
_PUBLIC_MODEL_REQUEST_LOCK = threading.Lock()

@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    """Make interrupted prewarm work explicit instead of leaving stale progress forever."""

    try:
        recover_orphaned_refresh_jobs(WORKSPACE_ROOT)
        bootstrap_runtime_catalog(WORKSPACE_ROOT)
    except (OSError, ValueError, TypeError):
        # A catalog problem must not prevent the HTTP service from exposing its
        # health endpoint; individual cache calls still return a clear 503.
        pass
    yield


app = FastAPI(title="审迹智链 AuditTrace API", version=ENGINE_VERSION, lifespan=app_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


def _with_ai_notice(payload: dict[str, Any]) -> dict[str, Any]:
    """所有公开 JSON 对象统一携带同一句 AI 生成内容声明。"""
    return {**payload, "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE}


def _cookie_max_age(value: Any, default: int, upper: int) -> int:
    """把身份服务的过期秒数限制在安全范围，异常值不会形成永久 Cookie。"""

    try:
        return max(60, min(upper, int(value)))
    except (TypeError, ValueError):
        return default


def _session_cookie_secure() -> bool:
    """公网演示强制 Secure；本机 Supabase 开发仅能用显式环境变量关闭。"""

    configured = os.getenv("AUDITTRACE_COOKIE_SECURE", "").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"} and not _public_demo_enabled():
        return False
    # 未配置、非法值或公网演示一律失败关闭为 Secure，绝不根据可伪造 Host 自动降级。
    return True


def _set_session_cookies(response: Response, session: dict[str, Any]) -> None:
    """令牌只写同源 HttpOnly Cookie；公网始终启用 Secure 与 SameSite=Lax。"""

    common = {"httponly": True, "secure": _session_cookie_secure(), "samesite": "lax", "path": "/"}
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        str(session["access_token"]),
        max_age=_cookie_max_age(session.get("expires_in"), 3600, 86_400),
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        str(session["refresh_token"]),
        max_age=_cookie_max_age(session.get("refresh_expires_in"), 2_592_000, 7_776_000),
        **common,
    )


def _clear_session_cookies(response: Response) -> None:
    """退出只清理本域会话，并保持与创建时完全一致的安全属性。"""

    for name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME):
        response.delete_cookie(name, path="/", secure=_session_cookie_secure(), httponly=True, samesite="lax")


def _authenticated_session_payload(session: dict[str, Any]) -> dict[str, Any]:
    """验证新会话并仅返回身份摘要，access/refresh token 永不进入 JSON。"""

    identity = identity_from_access_token(str(session.get("access_token") or ""))
    return _with_ai_notice(
        {
            "authenticated": True,
            "user": identity.as_public_dict(),
            "persistence": configured_persistence(),
            "session": {
                "http_only": True,
                "same_site": "lax",
                "cookie_secure": _session_cookie_secure(),
                "transport_boundary": (
                    "仅供明确配置 AUDITTRACE_COOKIE_SECURE=false 的非公网本机 HTTP 开发。"
                    if not _session_cookie_secure()
                    else "Cookie 仅通过 HTTPS 发送。"
                ),
            },
            "boundary": "会话令牌仅保存在同源 HttpOnly Cookie；JSON 不返回 access token 或 refresh token。",
        }
    )


@app.exception_handler(StarletteHTTPException)
async def json_http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
    """错误 JSON 也保留声明，防止失败分支成为未标识的机器生成出口。"""
    return JSONResponse(
        status_code=error.status_code,
        headers=error.headers,
        content=_with_ai_notice({"detail": jsonable_encoder(error.detail)}),
    )


@app.exception_handler(RequestValidationError)
async def json_validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_with_ai_notice({"detail": jsonable_encoder(error.errors())}),
    )


def _openapi_with_ai_notice() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schema["x-ai-generated-content-notice"] = AI_GENERATED_CONTENT_NOTICE
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_ai_notice

assets_dir = WORKSPACE_ROOT / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# 保留旧 V3 页面作为只读对照路径；根入口始终由正式 index.html 提供。
forensic_editorial_dir = WORKSPACE_ROOT / "08_官网V3_ForensicEditorial"
if forensic_editorial_dir.exists():
    app.mount(
        "/forensic-editorial",
        StaticFiles(directory=forensic_editorial_dir, html=True),
        name="forensic_editorial",
    )


def _model_settings() -> tuple[str | None, str, str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip() or None
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model_id = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
    return api_key, base_url, model_id


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _public_demo_enabled() -> bool:
    return os.getenv("AUDITTRACE_PUBLIC_DEMO", "false").strip().lower() in {"1", "true", "yes"}


def _client_identity(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    return request.client.host if request.client else "unknown"


def _enforce_public_model_quota(request: Request) -> None:
    if not _public_demo_enabled():
        return
    now = time.monotonic()
    window_seconds = _positive_int_env("AUDITTRACE_MODEL_RUN_WINDOW_SECONDS", 900)
    per_ip_limit = _positive_int_env("AUDITTRACE_MODEL_RUN_LIMIT", 2)
    global_limit = _positive_int_env("AUDITTRACE_MODEL_RUN_GLOBAL_LIMIT", 40)
    cutoff = now - window_seconds
    client_id = _client_identity(request)
    with _PUBLIC_MODEL_REQUEST_LOCK:
        while _PUBLIC_MODEL_REQUESTS_GLOBAL and _PUBLIC_MODEL_REQUESTS_GLOBAL[0] <= cutoff:
            _PUBLIC_MODEL_REQUESTS_GLOBAL.popleft()
        recent_for_ip = _PUBLIC_MODEL_REQUESTS_BY_IP.setdefault(client_id, deque())
        while recent_for_ip and recent_for_ip[0] <= cutoff:
            recent_for_ip.popleft()
        if len(recent_for_ip) >= per_ip_limit or len(_PUBLIC_MODEL_REQUESTS_GLOBAL) >= global_limit:
            raise HTTPException(
                status_code=429,
                detail="公开演示的AI调用次数已达到临时上限，请稍后再试；仅计算预检不受影响。",
            )
        recent_for_ip.append(now)
        _PUBLIC_MODEL_REQUESTS_GLOBAL.append(now)


def _public_case(case: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(case)
    private_case = not is_public_case(case)
    public.pop("package_sha256", None)
    public.pop("tenant_id", None)
    public.pop("owner_org_id", None)
    public.pop("owner_user_id", None)
    for document in public.get("documents", []):
        document.pop("storage_relpath", None)
        document.pop("storage_object_path", None)
        if private_case:
            # 内部来源只能通过 /sources/{document_id} 生成短时签名 URL，
            # 不把清单中的原始 URL带到前端或公开 JSON。
            document.pop("source_url", None)
    return public


def _normalize_official_public_case(case: dict[str, Any]) -> dict[str, Any]:
    """服务端巨潮注册器形成的公开年报证据属于全局只读 scope，不继承排队用户租户。"""

    normalized = deepcopy(case)
    if (
        str(normalized.get("registry_mode") or "") == "cninfo_official_auto"
        and str(normalized.get("sample_type") or "") == "public"
        and str(normalized.get("case_id") or "").upper().startswith("CNINFO_")
    ):
        normalized["tenant_id"] = None
        normalized.pop("owner_org_id", None)
        normalized.pop("owner_user_id", None)
    return normalized


def _merge_public_seed_material(case: dict[str, Any]) -> dict[str, Any]:
    """补齐远端公开目录缺失的已校验字段，不覆盖远端真人复核结果。"""

    if not is_public_case(case):
        return case
    seed = get_seed_case(WORKSPACE_ROOT, str(case.get("case_id") or ""))
    if seed is None:
        return case
    merged = deepcopy(case)
    for key in ("documents", "financial_fields", "structured_evidence"):
        if not merged.get(key) and seed.get(key):
            merged[key] = deepcopy(seed[key])
    for key in (
        "company_alias",
        "ticker",
        "market",
        "t0",
        "available_years",
        "available_report_years",
        "source_snapshot_id",
        "currency",
        "amount_unit",
        "statement_scope",
        "registry_mode",
        "financial_fields_status",
    ):
        if merged.get(key) in (None, "", []):
            merged[key] = deepcopy(seed.get(key))
    merged["seed_materialization"] = "verified_metadata_and_fields_no_pdf"
    return merged


def _identity_tenant(http_request: Request, *, required: bool = False) -> str | None:
    """先验证请求身份再把租户传给 service-role 查询，禁止按 case_id 整表回退。"""

    identity = require_authenticated(http_request) if required else optional_authenticated(http_request)
    return str(identity.tenant_id or "").strip() or None if identity and not identity.is_local else None


def _public_source(row: dict[str, Any], *, private: bool = False) -> dict[str, Any]:
    excluded = {"storage_relpath", "storage_object_path"}
    if private:
        excluded.add("source_url")
    return {
        key: deepcopy(value)
        for key, value in row.items()
        if key not in excluded
    }


def _persist_case_remote(case: dict[str, Any], *, rows: list[dict[str, Any]] | None = None, upload_private_documents: bool = False) -> dict[str, Any] | None:
    """公网模式把案例元数据交给 Postgres；本地模式不发起网络请求。"""

    if not supabase_enabled():
        return None
    try:
        return get_supabase_client().persist_case_metadata(
            workspace_root=WORKSPACE_ROOT,
            case=case,
            rows=rows,
            upload_private_documents=upload_private_documents,
        )
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="公网持久化服务暂时不可用，案例未完成提交。") from error


def _worker_lease_is_current(http_request: Request) -> bool:
    """worker 请求存在探针时实时确认租约；普通 HTTP 请求不受内部 fencing 影响。"""

    probe = getattr(http_request.state, "audittrace_worker_lease_probe", None)
    if not callable(probe):
        return True
    try:
        return bool(probe())
    except Exception:
        # 无法证明仍持有 token 与明确 CAS 失败具有相同副作用风险，统一失败关闭。
        return False


def _require_worker_lease(http_request: Request) -> None:
    """在下载后分析、模型和结果持久化等阶段边界阻止旧 worker 继续副作用。"""

    if not _worker_lease_is_current(http_request):
        raise SupabaseLeaseLost("worker 租约已经失效，已停止后续高成本步骤。")


def _queue_pipeline_task(
    background_tasks: BackgroundTasks,
    task: dict[str, Any],
    payload: dict[str, Any],
    http_request: Request,
    *,
    requeue: bool = False,
    expected_status: str | None = None,
    expected_attempt: int | None = None,
) -> None:
    """本地使用后台任务，公网模式只写数据库队列，由独立 worker 领取。"""

    if not supabase_enabled():
        background_tasks.add_task(_execute_cninfo_task, task["task_id"], payload, http_request)
        return
    identity = request_identity(http_request)
    payload = deepcopy(payload)
    payload["requested_by_identity"] = identity_for_task(http_request)
    # worker 领取的是数据库任务，但现有状态机仍从本地任务 JSON 读取请求；
    # 把已验证的服务端身份摘要同步进去，不写入 Bearer token。
    task["request"]["requested_by_identity"] = payload["requested_by_identity"]
    _save_task(WORKSPACE_ROOT, task)
    try:
        client = get_supabase_client()
        if requeue:
            if expected_status is None or expected_attempt is None:
                raise SupabaseConflict("重排任务缺少状态和 attempt 前置条件。")
            client.requeue_pipeline_task(
                task_id=task["task_id"],
                request_payload=payload,
                expected_status=expected_status,
                expected_attempt=expected_attempt,
            )
        else:
            client.enqueue_pipeline_task(
                task_id=task["task_id"],
                request_payload=payload,
                tenant_id=identity.tenant_id if identity and not identity.is_local else None,
                requested_by=identity.user_id if identity and not identity.is_local else None,
            )
    except SupabaseConflict as error:
        raise HTTPException(status_code=409, detail="任务状态已经变化，请刷新后重试。") from error
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="公网任务队列暂时不可用，请稍后重试。") from error


def _read_pipeline_task(task_id: str) -> dict[str, Any] | None:
    """公网 web 实例从 Postgres 读取 worker 结果；本地模式仍读 JSON。"""

    local = load_task(WORKSPACE_ROOT, task_id)
    if not supabase_enabled():
        return local
    try:
        remote = get_supabase_client().get_pipeline_task(task_id)
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="公网任务状态暂时不可用。") from error
    if not remote:
        return local
    result = remote.get("result")
    remote_error = remote.get("error")
    if isinstance(result, dict) and result.get("task_id"):
        task = deepcopy(result)
    elif isinstance(remote_error, dict) and remote_error.get("task_id"):
        # needs_human/failed 由 worker 写入 error 任务快照；fresh web 必须能恢复
        # 企业候选和完整步骤，而不能依赖另一个实例的本地 JSON。
        task = deepcopy(remote_error)
    else:
        task = deepcopy(local) if local else {"task_id": task_id, "steps": {}, "errors": []}
    task["task_id"] = task_id
    has_task_snapshot = bool(
        (isinstance(result, dict) and result.get("task_id"))
        or (isinstance(remote_error, dict) and remote_error.get("task_id"))
    )
    task["status"] = task.get("status") if has_task_snapshot else remote.get("status") or task.get("status", "queued")
    task["attempt"] = remote.get("attempt", task.get("attempt", 0))
    task["updated_at"] = remote.get("updated_at", task.get("updated_at"))
    task["tenant_id"] = remote.get("tenant_id")
    task["requested_by"] = remote.get("requested_by")
    if not isinstance(task.get("request"), dict) and isinstance(remote.get("request_payload"), dict):
        task["request"] = deepcopy(remote["request_payload"])
    if not isinstance(task.get("error"), dict) and isinstance(remote_error, dict):
        # worker 撤权或自身异常只上报稳定错误摘要，不一定附整份任务快照；
        # fresh web 仍应向任务所有者展示受控错误码，而不是空白 failed。
        task["error"] = deepcopy(remote_error)
    task["persistence"] = {"backend": "supabase", "queue_status": remote.get("status")}
    return task


def _public_pipeline_task(task: dict[str, Any]) -> dict[str, Any]:
    """任务归属只用于服务端授权，响应不暴露用户 UUID、租户 UUID 或身份摘要。"""

    public = deepcopy(task)
    public.pop("tenant_id", None)
    public.pop("requested_by", None)
    if isinstance(public.get("request"), dict):
        public["request"].pop("requested_by_identity", None)
    return public


def _remote_case_for_run(case_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
    if not supabase_enabled():
        local = get_case(WORKSPACE_ROOT, case_id)
        return _normalize_official_public_case(local) if local is not None else None
    scoped_local = _exact_tenant_local_case(case_id, tenant_id=tenant_id)
    if scoped_local is not None:
        return scoped_local
    try:
        remote = get_supabase_client().get_case_metadata(case_id, tenant_id=tenant_id)
    except SupabaseError as error:
        # Render 的 web 实例不携带可写 runtime；公开演示仍可使用已校验的
        # 元数据种子完成确定性预筛，不能因为远端目录短暂不可达而把运行
        # 入口伪装成“案例不存在”。私有案例绝不走这个公开回退。
        if not tenant_id:
            local_fallback = get_case(WORKSPACE_ROOT, case_id)
            if local_fallback is not None and is_public_case(local_fallback):
                return _normalize_official_public_case(local_fallback)
            fallback = get_seed_case(WORKSPACE_ROOT, case_id)
            if fallback is not None:
                return fallback
        raise HTTPException(status_code=503, detail="公网案例元数据暂时不可用。") from error
    if remote is None:
        return get_seed_case(WORKSPACE_ROOT, case_id) if not tenant_id else None
    # 全局本机副本没有 owner，必须先由 Postgres 确认同编号记录确实是 PUBLIC；
    # 否则租户私有案例会被同名公开缓存遮蔽，标准案例编号也会误命中内置样例。
    return _merge_public_seed_material(_confirmed_public_local_case(case_id, remote) or remote)


def _case_record(case_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
    if not supabase_enabled():
        local = get_case(WORKSPACE_ROOT, case_id)
        return _normalize_official_public_case(local) if local is not None else None
    scoped_local = _exact_tenant_local_case(case_id, tenant_id=tenant_id)
    if scoped_local is not None:
        return scoped_local
    try:
        case = get_supabase_client().get_case_bundle(case_id, tenant_id=tenant_id)
        if case and case.get("registry_mode") == "cninfo_official_auto":
            _recompute_cninfo_human_status(case, case.get("financial_fields") or [])
        if case is None:
            return get_seed_case(WORKSPACE_ROOT, case_id) if not tenant_id else None
        # 远端私有 bundle 始终原样返回；只有远端明确解析到无租户公开 scope，
        # 才允许复用同快照的全局本机材料，避免 case_id 成为跨租户选择器。
        # 登录租户读取公开案例时，adapter 已把该租户 field_review_overlays 合入
        # bundle；若此处换回本机 base，会悄悄丢掉真人修正。匿名公开读取才可整包回退。
        case = _merge_public_seed_material(case)
        return (_confirmed_public_local_case(case_id, case) if not tenant_id else None) or case
    except SupabaseError as error:
        # 同上：仅公开、已锁定的 CNINFO seed 可以降级；租户私有数据必须
        # 继续失败关闭，防止把跨租户数据当作公开案例返回。
        if not tenant_id:
            local_fallback = get_case(WORKSPACE_ROOT, case_id)
            if local_fallback is not None and is_public_case(local_fallback):
                return _normalize_official_public_case(local_fallback)
            fallback = get_seed_case(WORKSPACE_ROOT, case_id)
            if fallback is not None:
                return fallback
        raise HTTPException(status_code=503, detail="公网案例数据暂时不可用。") from error


def _exact_tenant_local_case(case_id: str, *, tenant_id: str | None) -> dict[str, Any] | None:
    """只接受租户隔离目录中的精确归属副本，不接受内置/全局同名回退。"""

    normalized_tenant = str(tenant_id or "").strip()
    if not normalized_tenant:
        return None
    local = get_case(WORKSPACE_ROOT, case_id, tenant_id=normalized_tenant)
    if local is None or str(local.get("tenant_id") or "").strip() != normalized_tenant:
        # 这层归属复核刻意重复 cases.py 的目录校验：即使旧版本仍对标准编号
        # 返回内置案例，也不能让无 owner 的样例冒充当前租户临时副本。
        return None
    return _normalize_official_public_case(local)


def _confirmed_public_local_case(case_id: str, remote: dict[str, Any]) -> dict[str, Any] | None:
    """远端确认 PUBLIC 后，才返回同一来源快照的无租户本机缓存。"""

    if not is_public_case(remote):
        return None
    local = get_case(WORKSPACE_ROOT, case_id)
    if local is None or not is_public_case(local):
        return None
    remote_snapshot = str(remote.get("source_snapshot_id") or "").strip()
    local_snapshot = str(local.get("source_snapshot_id") or "").strip()
    if remote_snapshot and local_snapshot and remote_snapshot != local_snapshot:
        # 远端记录是发布权威；快照不同说明本机副本可能陈旧，宁可走远端字段，
        # 也不把旧材料与当前 metadata 拼接成不可复现的混合证据链。
        return None
    return _normalize_official_public_case(local)


def _materialized_case_for_resolved(
    case: dict[str, Any],
    *,
    tenant_id: str | None,
) -> dict[str, Any] | None:
    """为已授权案例选择可用本机材料，同时保持解析出的 tenant/public scope。"""

    case_id = str(case.get("case_id") or "")
    if not case_id:
        return None
    if not supabase_enabled():
        return get_case(WORKSPACE_ROOT, case_id)
    resolved_tenant = str(case.get("tenant_id") or "").strip()
    if resolved_tenant:
        if resolved_tenant != str(tenant_id or "").strip():
            return None
        return _exact_tenant_local_case(case_id, tenant_id=resolved_tenant)
    # 调用者传入的 case 已由远端解析；这里只对公开 scope 开放全局缓存。
    return _confirmed_public_local_case(case_id, case)


def _materialized_financial_rows(
    case: dict[str, Any],
    *,
    tenant_id: str | None,
) -> list[dict[str, Any]] | None:
    """从与已解析案例同 scope 的目录读取字段；缺失时由调用者使用远端 bundle。"""

    if supabase_enabled() and is_public_case(case) and str(tenant_id or "").strip():
        # 认证租户的公开字段可能包含私有 overlay；其权威结果只存在于远端 bundle。
        return None
    local = _materialized_case_for_resolved(case, tenant_id=tenant_id)
    if local is None:
        return None
    local_tenant = str(local.get("tenant_id") or "").strip() or None
    try:
        return get_financial_rows(WORKSPACE_ROOT, str(case.get("case_id") or ""), tenant_id=local_tenant)
    except (KeyError, OSError, ValueError):
        # 临时副本可能在另一 worker 清理或尚未写完；远端 bundle 才是公网恢复路径。
        return None


def _local_rag_matches_remote(
    *,
    case: dict[str, Any],
    local_status: dict[str, Any],
    remote_status: dict[str, Any],
) -> bool:
    """仅在完整快照描述一致时允许本机索引作为 Supabase 加速层。"""

    if not is_public_case(case) or local_status.get("status") != "ready" or remote_status.get("status") != "ready":
        return False
    expected_scope = f"PUBLIC:{str(case.get('case_id') or '').upper()}"
    remote_scope = str(remote_status.get("case_scope") or "").strip()
    if remote_scope and remote_scope != expected_scope:
        return False
    comparable = ("rag_snapshot_id", "index_version", "chunk_count")
    return all(
        str(local_status.get(key) or "") == str(remote_status.get(key) or "")
        for key in comparable
    ) and bool(local_status.get("rag_snapshot_id"))


def _run_context_tenant(stored: StoredRunResponse) -> str | None:
    identity = stored.run.context.get("request_identity")
    return str(identity.get("tenant_id") or "").strip() or None if isinstance(identity, dict) else None


def _load_stored_run_record(
    run_id: str,
    *,
    owner_tenant_id: str | None = None,
) -> tuple[StoredRunResponse, str | None] | None:
    """返回运行及其所有者租户；公网优先读权威行，避免本地旧副本绕过对象授权。"""

    if not supabase_enabled():
        stored = load_run(WORKSPACE_ROOT, run_id)
        return (stored, _run_context_tenant(stored)) if stored is not None else None
    try:
        remote_row = get_supabase_client().get_analysis_run(run_id, tenant_id=owner_tenant_id)
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="公网运行记录暂时不可用。") from error
    payload = remote_row.get("payload") if remote_row else None
    if isinstance(payload, dict):
        try:
            stored = (
                StoredRunResponse.model_validate(payload)
                if isinstance(payload.get("run"), dict)
                else StoredRunResponse(run=RunResponse.model_validate(payload))
            )
            return stored, str(remote_row.get("tenant_id") or "").strip() or None
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=503, detail="公网运行记录格式无法恢复。") from error
    local = load_run(WORKSPACE_ROOT, run_id)
    if local is None:
        return None
    local_owner = _run_context_tenant(local)
    if local_owner != owner_tenant_id:
        return None
    return local, local_owner


def _load_stored_run(run_id: str, *, owner_tenant_id: str | None = None) -> StoredRunResponse | None:
    """兼容内部调用的简写；路由需要所有者信息时应使用 `_load_stored_run_record`。"""

    record = _load_stored_run_record(run_id, owner_tenant_id=owner_tenant_id)
    return record[0] if record else None


def _persist_stored_run_remote(
    stored: StoredRunResponse,
    case: dict[str, Any],
    *,
    owner_tenant_id: str | None,
) -> None:
    """人工复核后覆盖同一远程运行行，使下一台 web 实例能恢复复核与导出闸门。"""

    if not supabase_enabled():
        return
    try:
        get_supabase_client().persist_run(
            run=stored.model_dump(mode="json"),
            tenant_id=owner_tenant_id,
            case_id=str(stored.run.context.get("case_id") or ""),
            case_tenant_id=str(case.get("tenant_id") or "").strip() or None,
            pipeline_task_id=str(stored.run.context.get("pipeline_task_id") or "").strip() or None,
        )
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="人工复核未完成公网持久化，请稍后重试。") from error


def _supplement_record_path(tenant_id: str, supplement_id: str) -> str:
    """补充记录使用可验证固定路径，不能由文件名或请求参数拼接任意 Storage 对象。"""

    if not re.fullmatch(r"SUP-[A-Z0-9]+", supplement_id):
        raise HTTPException(status_code=404, detail="未找到该补充资料记录。")
    return f"{tenant_id}/supplements/{supplement_id}/record.json"


def _persist_supplement_record_remote(record: dict[str, Any], tenant_id: str) -> None:
    """把结构化补充记录单独写入私有 Storage，跨实例续分析不依赖本机磁盘。"""

    try:
        get_supabase_client().upload_private_object(
            bucket=os.getenv("SUPABASE_PRIVATE_BUCKET", "audittrace-private"),
            object_path=_supplement_record_path(tenant_id, str(record.get("supplement_id") or "")),
            content=json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            content_type="application/json",
        )
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="补充资料记录未完成公网持久化。") from error


def _load_supplement_record(supplement_id: str, identity: Any | None) -> dict[str, Any] | None:
    """本地记录不存在时按已验证租户从私有 Storage 回源，并校验记录归属。"""

    record = load_supplement(WORKSPACE_ROOT, supplement_id)
    if record is not None or not supabase_enabled():
        return record
    if identity is None or identity.is_local or not identity.tenant_id:
        return None
    try:
        content = get_supabase_client().download_private_object(
            bucket=os.getenv("SUPABASE_PRIVATE_BUCKET", "audittrace-private"),
            object_path=_supplement_record_path(identity.tenant_id, supplement_id),
        )
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="公网补充资料记录暂时不可用。") from error
    try:
        remote = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=503, detail="公网补充资料记录格式无法恢复。") from error
    if not isinstance(remote, dict):
        raise HTTPException(status_code=503, detail="公网补充资料记录格式无法恢复。")
    if str(remote.get("supplement_id") or "") != supplement_id or str(remote.get("tenant_id") or "") != identity.tenant_id:
        # 固定路径内的对象仍要二次校验租户和编号，避免错误对象被当成授权记录。
        raise HTTPException(status_code=404, detail="未找到该补充资料记录。")
    return remote


def _validated_rerun_parameters(raw: Any) -> dict[str, float | None]:
    """旧运行参数必须是有限且在现行边界内的数值，坏记录稳定返回 409 而不是 500。"""

    if not isinstance(raw, dict):
        raise HTTPException(status_code=409, detail="父运行参数快照格式无效，不能续分析。")

    def finite_value(name: str, default: float, *, upper: float | None = None) -> float:
        value = raw.get(name, default)
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=f"父运行参数 {name} 无效，不能续分析。") from error
        if not math.isfinite(number) or number < 0 or (upper is not None and number > upper):
            raise HTTPException(status_code=409, detail=f"父运行参数 {name} 超出现行边界，不能续分析。")
        return number

    materiality_value = raw.get("planned_materiality")
    if materiality_value is None:
        planned_materiality = None
    else:
        try:
            planned_materiality = float(materiality_value)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=409, detail="父运行计划重要性无效，不能续分析。") from error
        if not math.isfinite(planned_materiality) or planned_materiality < 0:
            raise HTTPException(status_code=409, detail="父运行计划重要性超出现行边界，不能续分析。")

    values: dict[str, float | None] = {
        "r2_min_gap": finite_value("r2_min_gap", 0.0, upper=1.0),
        "planned_materiality": planned_materiality,
        "r1_gap_threshold": finite_value("r1_gap_threshold", 0.15, upper=2.0),
        "r1_strong_gap_threshold": finite_value("r1_strong_gap_threshold", 0.30, upper=3.0),
        "r1_absolute_threshold": finite_value("r1_absolute_threshold", 0.0),
    }
    if float(values["r1_strong_gap_threshold"] or 0) < float(values["r1_gap_threshold"] or 0):
        raise HTTPException(status_code=409, detail="父运行强提示阈值低于基本阈值，不能续分析。")
    return values


def _remote_cninfo_field_readiness(
    rows: list[dict[str, Any]],
    rule_ids: list[str],
    current_year: int,
) -> list[str]:
    """在无本地案例文件时复用同一字段闸门语义，拒绝把技术候选误作真人确认。"""

    row_map = {(row.get("field_kind"), int(row.get("year"))): row for row in rows if row.get("year") is not None}
    required: set[tuple[str, int]] = set()
    if "R1" in rule_ids:
        required.update(
            {
                ("revenue", current_year),
                ("revenue", current_year - 1),
                ("accounts_receivable", current_year),
                ("accounts_receivable", current_year - 1),
            }
        )
        if all((kind, current_year - 2) in row_map for kind in ("revenue", "accounts_receivable")):
            required.update({("revenue", current_year - 2), ("accounts_receivable", current_year - 2)})
    if "R2" in rule_ids:
        required.update(
            {
                ("revenue", current_year),
                ("revenue", current_year - 1),
                ("operating_cash_flow", current_year),
                ("operating_cash_flow", current_year - 1),
            }
        )
        if ("net_profit", current_year) in row_map:
            required.add(("net_profit", current_year))
    issues: list[str] = []
    for kind, year in sorted(required, key=lambda item: (item[1], item[0])):
        row = row_map.get((kind, year))
        if row is None:
            issues.append(f"{year}年{kind}字段缺失")
        elif (row.get("human_review") or {}).get("decision") not in {"confirm", "correct"}:
            issues.append(f"{year}年{kind}字段尚未真人确认")
    return issues


def _remote_period_sources(
    case: dict[str, Any],
    current_year: int,
    rule_ids: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """从已发布 Postgres 字段构造与本地案例一致的计算上下文，不物化伪造 PDF。"""

    raw_rows = [deepcopy(row) for row in (case.get("financial_fields") or [])]
    documents = {str(item.get("document_id") or ""): item for item in case.get("documents", [])}

    def select(kind: str, year: int) -> dict[str, Any] | None:
        return next(
            (deepcopy(row) for row in raw_rows if row.get("field_kind") == kind and int(row.get("year") or 0) == year),
            None,
        )

    requested_current_year = int(current_year)
    prescreen_plan: dict[str, Any] | None = None
    if case.get("registry_mode") == "cninfo_official_auto":
        required_by_rule = {
            "R1": ("revenue", "accounts_receivable"),
            "R2": ("revenue", "operating_cash_flow"),
        }
        plans: dict[str, dict[str, Any]] = {}
        skipped: list[dict[str, Any]] = []
        missing_fields: list[str] = []
        report_years = sorted(
            {int(item.get("report_year")) for item in case.get("documents", []) if item.get("report_year")},
            reverse=True,
        )
        for rule_id in rule_ids:
            kinds = required_by_rule.get(rule_id, ())
            complete = sorted(
                {
                    int(row.get("year"))
                    for row in raw_rows
                    if row.get("year") is not None
                    and all(select(kind, int(row.get("year"))) is not None for kind in kinds)
                },
                reverse=True,
            )
            eligible = [year for year in complete if year - 1 in complete and year <= requested_current_year]
            selected = max(eligible, default=None)
            if selected is None:
                skipped.append({"rule_id": rule_id, "reason": "没有连续两年完整字段，无法进行同比计算。", "required_fields": list(kinds)})
            else:
                plans[rule_id] = {
                    "status": "ready",
                    "current_year": selected,
                    "previous_year": selected - 1,
                    "prior_year": selected - 2 if selected - 2 in complete else None,
                    "complete_years": complete,
                    "three_year_available": selected - 2 in complete,
                }
            for year in report_years:
                if year <= requested_current_year:
                    missing_fields.extend(f"{year}年{kind}" for kind in kinds if select(kind, year) is None)
        primary = "R1" if "R1" in plans else next(iter(plans), None)
        current_year = int(plans[primary]["current_year"]) if primary else requested_current_year
        prescreen_plan = {
            "mode": "public_prescreen",
            "requested_current_year": requested_current_year,
            "analysis_current_year": current_year if primary else None,
            "analysis_previous_year": current_year - 1 if primary else None,
            "analysis_years": [current_year, current_year - 1] if primary else [],
            "rule_plans": plans,
            "skipped_rules": skipped,
            "missing_fields": list(dict.fromkeys(missing_fields)),
            "has_calculable_rule": bool(plans),
            "source_candidate_count": len(raw_rows),
            "human_confirmation": "recommended_before_formal_adoption_or_export",
            "confidence": "technical_candidate_pending_optional_human_confirmation" if raw_rows else "insufficient_data",
        }
    elif current_year not in {int(year) for year in (case.get("available_years") or [])}:
        raise KeyError(current_year)

    previous_year, prior_year = current_year - 1, current_year - 2
    requested: list[tuple[str, str, str, int]] = []
    if "R1" in rule_ids and (not prescreen_plan or prescreen_plan.get("rule_plans", {}).get("R1")):
        requested.extend([
            ("revenue_current", "本年营业收入", "revenue", current_year),
            ("revenue_previous", "上年营业收入", "revenue", previous_year),
            ("ar_current", "本年应收账款", "accounts_receivable", current_year),
            ("ar_previous", "上年应收账款", "accounts_receivable", previous_year),
        ])
        if select("revenue", prior_year) and select("accounts_receivable", prior_year):
            requested.extend([
                ("revenue_prior", "前两年营业收入", "revenue", prior_year),
                ("ar_prior", "前两年应收账款", "accounts_receivable", prior_year),
            ])
    if "R2" in rule_ids and (not prescreen_plan or prescreen_plan.get("rule_plans", {}).get("R2")):
        requested.extend([
            ("revenue_current", "本年营业收入", "revenue", current_year),
            ("revenue_previous", "上年营业收入", "revenue", previous_year),
            ("operating_cash_flow_current", "本年经营活动现金流量净额", "operating_cash_flow", current_year),
            ("operating_cash_flow_previous", "上年经营活动现金流量净额", "operating_cash_flow", previous_year),
        ])
        if select("net_profit", current_year):
            requested.append(("net_profit_current", "本年净利润（R2增强项）", "net_profit", current_year))

    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field_id, label, kind, year in requested:
        if field_id in seen:
            continue
        source = select(kind, year)
        if source is None:
            if prescreen_plan:
                continue
            raise KeyError(f"{kind}/{year}")
        document = documents.get(str(source.get("document_id") or "")) or {}
        source.update({
            "field_id": field_id,
            "field_label": label,
            "source_file": source.get("source_file") or document.get("source_file") or source.get("document_id"),
            "file_sha256": source.get("file_sha256") or document.get("sha256"),
            "disclosure_date": source.get("disclosure_date") or document.get("disclosure_date") or document.get("announcement_date") or case.get("t0"),
            "locator": source.get("locator") or f"PDF 第 {source.get('pdf_page')} 页",
            "unit": source.get("unit") or case.get("amount_unit", "元"),
            "currency": source.get("currency") or case.get("currency", "CNY"),
            "statement_scope": source.get("statement_scope") or case.get("statement_scope", "合并"),
            "source_mode": "supabase_persisted_verified",
        })
        sources.append(source)
        seen.add(field_id)
    context = {
        "case_id": case.get("case_id"),
        "company_name": case.get("company_name") or "",
        "company_alias": case.get("company_alias") or case.get("company_name") or "",
        "ticker": case.get("ticker") or "",
        "current_year": current_year,
        "previous_year": previous_year,
        "prior_year": prior_year if any(row.get("field_id", "").endswith("_prior") for row in sources) else None,
        "t0": case.get("t0"),
        "currency": case.get("currency", "CNY"),
        "amount_unit": case.get("amount_unit", "元"),
        "statement_scope": case.get("statement_scope", "合并"),
        "sample_type": case.get("sample_type", "public"),
        "registry_mode": case.get("registry_mode"),
        "model_transfer_allowed": bool(case.get("model_transfer_allowed")),
        "source_snapshot_id": case.get("source_snapshot_id"),
        "source_review_status": case.get("source_review_status"),
        "three_year_r1_ready": bool(case.get("three_year_r1_ready")),
        "requested_current_year": requested_current_year,
        "analysis_cutoff_year": current_year if sources else None,
        "public_prescreen": prescreen_plan is not None,
        "prescreen_plan": prescreen_plan,
        "case_evidence_count": len(case.get("structured_evidence", [])),
        "case_material_gaps": deepcopy(case.get("material_gaps", [])),
    }
    return context, sources


def _remote_rag_retrieve(
    *,
    case: dict[str, Any],
    query: str,
    t0: str,
    rule_id: str,
    top_k: int,
    question_id: str | None,
    owner_tenant_id: str | None,
    requested_by: str | None,
) -> dict[str, Any]:
    """对活动 Postgres 快照做确定性词项召回，保持证据定位与无命中合同。"""

    questions_payload = question_set()
    question = next(
        (item for item in questions_payload.get("questions", []) if item.get("question_id") == question_id),
        None,
    ) if question_id else None
    if question_id and question is None:
        raise ValueError("未知的 RAG 固定问题编号")
    if question and rule_id not in question.get("rule_ids", []):
        raise ValueError(f"{question_id} 不属于规则 {rule_id}")
    effective_query = str(question.get("retrieval_query") if question else query).strip()
    if not effective_query:
        raise ValueError("检索词不能为空")
    client = get_supabase_client()
    rows = client.get_active_rag_chunks(
        case_id=str(case.get("case_id") or ""),
        tenant_id=str(case.get("tenant_id") or "").strip() or None,
    )
    if not rows:
        raise RuntimeError("RAG 索引尚未构建")
    documents = {str(item.get("document_id") or ""): item for item in case.get("documents", [])}
    fields = case.get("financial_fields") or []
    anchors = [str(item).lower() for item in (question.get("anchor_terms", []) if question else [])]
    query_terms = [term.lower() for term in re.split(r"\s+", effective_query) if term]
    candidates: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        disclosure_date = str(metadata.get("disclosure_date") or "")
        company_name = str(metadata.get("company_name") or case.get("company_name") or "")
        if disclosure_date and disclosure_date > t0:
            continue
        if company_name and company_name != str(case.get("company_name") or company_name):
            continue
        content = str(row.get("content") or "")
        normalized = re.sub(r"\s+", "", content.lower())
        anchor_hits = sum(1 for term in anchors if re.sub(r"\s+", "", term) in normalized)
        if question and anchor_hits == 0:
            continue
        keyword_hits = sum(1 for term in query_terms if re.sub(r"\s+", "", term) in normalized)
        score = min(1.0, keyword_hits / max(2, len(query_terms))) * 0.55 + min(1.0, anchor_hits / max(1, min(3, len(anchors)))) * 0.45
        if score <= 0:
            continue
        document_id = str(row.get("document_id") or "")
        page = int(row.get("pdf_page") or 0)
        matched = [item for item in fields if str(item.get("document_id") or "") == document_id and int(item.get("pdf_page") or 0) == page]
        terms = anchors or query_terms
        positions = [content.lower().find(term) for term in terms if term and content.lower().find(term) >= 0]
        start = max(0, (min(positions) if positions else 0) - 140)
        end = min(len(content), start + 500)
        document = documents.get(document_id) or {}
        candidates.append(
            {
                "evidence_id": f"RAG-{row.get('chunk_id')}",
                "chunk_id": row.get("chunk_id"),
                "document_id": document_id,
                "score": round(score, 6),
                "vector_score": 0.0,
                "keyword_score": round(min(1.0, keyword_hits / max(2, len(query_terms))), 6),
                "anchor_score": round(min(1.0, anchor_hits / max(1, min(3, len(anchors)))) if anchors else 0.0, 6),
                "source_file": document.get("source_file") or document_id,
                "source_sha256": metadata.get("source_sha256") or document.get("sha256"),
                "disclosure_date": disclosure_date,
                "report_year": metadata.get("report_year") or document.get("report_year"),
                "pdf_page": page,
                "print_page": next((item.get("print_page") for item in matched if item.get("print_page")), None),
                "linked_field_evidence_ids": [item.get("evidence_id") for item in matched if item.get("evidence_id")],
                "source_locator": f"PDF 第 {page} 页 / {row.get('chunk_id')}",
                "title": metadata.get("title") or document.get("announcement_title") or "年报原文",
                "excerpt": content[start:end],
                "excerpt_char_start": start,
                "excerpt_char_end": end,
                "chunk_char_length": len(content),
                "excerpt_is_verbatim": True,
                "review_status": "candidate_fragment_pending_human_page_review",
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    candidates = candidates[:top_k]
    retrieval_id = f"RET-{uuid.uuid4().hex[:12].upper()}"
    record = {
        "retrieval_id": retrieval_id,
        "status": "hit" if candidates else "no_hit",
        "question_set_version": questions_payload.get("version") if question else None,
        "retrieval_version": "rag-retrieval-v1.2-case-isolated-20260728",
        "question": deepcopy(question) if question else None,
        "effective_query": effective_query,
        "boundary": "检索结果是候选原文，不构成审计结论；须回到原 PDF 页复核。",
        "filter": {"case_id": case.get("case_id"), "company_name": case.get("company_name"), "t0_lte": t0, "rule_id": rule_id},
        "evidence_gap": {
            "status": "retrieval_no_hit" if not candidates else "candidate_fragments_found",
            "label": "资料缺口候选 - 未检索到可回查片段" if not candidates else "已返回候选原文片段",
            "message": question.get("no_hit_prompt") if question and not candidates else "命中只表示候选片段；是否披露充分须人工回页确认。",
            "requires_human_confirmation": True,
            "auto_sync_to_risk_card": False,
        },
        "results": candidates,
    }
    client.persist_rag_retrieval(
        retrieval_id=retrieval_id,
        case_id=str(case.get("case_id") or ""),
        case_tenant_id=str(case.get("tenant_id") or "").strip() or None,
        owner_tenant_id=owner_tenant_id,
        requested_by=requested_by,
        rag_snapshot_id=str(rows[0].get("rag_snapshot_id") or ""),
        payload=record,
    )
    return record


def _replay_remote_cache_payload(payload: Any, cache_id: str) -> RunResponse:
    """从 Postgres 缓存恢复回放，强制保留“非新分析”、来源缓存和 AI 声明标记。"""

    if not isinstance(payload, dict) or payload.get("cache_id") != cache_id:
        raise HTTPException(status_code=503, detail="公网运行缓存格式无法恢复。")
    if payload.get("ai_generated_content_notice") != AI_GENERATED_CONTENT_NOTICE:
        raise HTTPException(status_code=503, detail="公网运行缓存缺少统一 AI 声明。")
    try:
        stored = StoredRunResponse.model_validate(payload.get("stored"))
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=503, detail="公网运行缓存格式无法恢复。") from error
    review = stored.human_review
    if review is None or review.reviewer_type != "human" or not review.export_approved:
        raise HTTPException(status_code=503, detail="公网运行缓存不满足人工批准闸门。")
    run_data = stored.run.model_dump(mode="json")
    source_run_id = str(run_data.get("run_id") or "")
    replay_id = f"RUN-REPLAY-{uuid.uuid4().hex[:12].upper()}"
    run_data["run_id"] = replay_id
    context = run_data.get("context") if isinstance(run_data.get("context"), dict) else {}
    context.update(
        {
            "execution_mode": "cache_replay",
            "replayed_from_cache_id": cache_id,
            "replayed_from_run_id": source_run_id,
            "replayed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
    )
    run_data["context"] = context
    run_data["run_completeness"] = "cache_replay_not_fresh_analysis"
    original_model = run_data.get("model_check") if isinstance(run_data.get("model_check"), dict) else {}
    run_data["model_check"] = {
        "status": "cache_replay",
        "model_id": original_model.get("model_id"),
        "detail": "本次回放保留原Agent轨迹，但没有重新运行RAG或模型。",
    }
    try:
        return RunResponse.model_validate(run_data)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=503, detail="公网运行缓存无法形成有效回放。") from error


def _remote_prewarm_report(batch: dict[str, Any]) -> dict[str, Any]:
    """跨实例汇总批次任务，只展示受控状态码，不回显 worker 或外部站点原始错误。"""

    payload = batch.get("payload") if isinstance(batch.get("payload"), dict) else {}
    specs = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    counts = {key: 0 for key in ("queued", "running", "success", "not_found", "not_applicable", "field_gaps", "needs_human", "failed")}
    items: list[dict[str, Any]] = []
    client = get_supabase_client()
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        task_id = str(spec.get("task_id") or "")
        remote = client.get_pipeline_task(task_id) if task_id else None
        authorized_task = bool(
            remote
            and str(remote.get("tenant_id") or "") == str(batch.get("tenant_id") or "")
            and str(remote.get("requested_by") or "") == str(batch.get("requested_by") or "")
        )
        task_record = remote.get("result") if authorized_task and isinstance(remote.get("result"), dict) else {}
        if (
            not task_record
            and authorized_task
            and isinstance(remote.get("error"), dict)
            and remote["error"].get("task_id")
        ):
            task_record = remote["error"]
        result = task_record.get("result") if isinstance(task_record.get("result"), dict) else {}
        error = (
            task_record.get("error")
            if isinstance(task_record.get("error"), dict)
            else remote.get("error") if authorized_task and isinstance(remote.get("error"), dict) else {}
        )
        pipeline_status = str(task_record.get("status") or (remote or {}).get("status") or "missing")
        extraction = result.get("field_extraction") if isinstance(result.get("field_extraction"), dict) else {}
        gate = result.get("industry_gate") if isinstance(result.get("industry_gate"), dict) else {}
        error_code = str(error.get("code") or "") or None
        if not authorized_task:
            status, category, error_code = "failed", "failed", "REMOTE_TASK_UNAVAILABLE"
        elif str(remote.get("status")) in {"queued", "running"}:
            status = str(remote["status"])
            category = status
        elif str(remote.get("status")) == "failed" and pipeline_status == "needs_human":
            status, category = "needs_human", "needs_human"
        elif str(remote.get("status")) == "failed":
            status = "failed"
            category = "not_found" if error_code == "ANNUAL_REPORT_NOT_FOUND" else "failed"
        elif pipeline_status == "needs_human":
            status, category = "needs_human", "needs_human"
        else:
            status = "completed"
            extraction_status = str(extraction.get("status") or "")
            if gate.get("fit_level") == "not_applicable":
                category = "not_applicable"
            elif extraction_status in {"cached_with_gaps", "passed_technical_with_gaps", "industry_unknown"} or extraction.get("field_gap_count"):
                category = "field_gaps"
            else:
                category = "success"
        counts[category] += 1
        items.append(
            {
                "job_id": spec.get("job_id"),
                "task_id": task_id,
                "ticker": spec.get("ticker"),
                "requested_years": spec.get("requested_years") or payload.get("requested_years") or [],
                "status": status,
                "category": category,
                "result_status": result.get("status"),
                "industry_fit_level": gate.get("fit_level"),
                "field_extraction_status": extraction.get("status"),
                "field_gap_count": extraction.get("field_gap_count", 0),
                "duration_seconds": None,
                "error_code": error_code,
                "reason": "任务未完成；原始外部响应不会通过批次报告回显。" if category in {"failed", "not_found"} else None,
                "last_activity_at": (remote or {}).get("updated_at"),
                "activity_age_seconds": None,
                "stalled": False,
                "created_at": (remote or {}).get("created_at") or batch.get("created_at"),
                "updated_at": (remote or {}).get("updated_at") or batch.get("updated_at"),
            }
        )
    return {
        "schema_version": "catalog_refresh_report_v1",
        "batch_id": batch.get("batch_id"),
        "total": len(items),
        "counts": counts,
        "complete": bool(items) and all(item["category"] not in {"queued", "running"} for item in items),
        "stall_threshold_seconds": None,
        "items": items,
        "persistence": {"backend": "supabase", "cross_instance": True},
    }


def _visible_case_records(http_request: Request) -> tuple[Any, list[dict[str, Any]], dict[str, Any]]:
    identity = optional_authenticated(http_request)
    local_cases = [_normalize_official_public_case(case) for case in list_cases(WORKSPACE_ROOT)]
    cases = [
        case
        for case in local_cases
        if not supabase_enabled()
        or is_public_case(case)
        or (identity and identity.tenant_id and str(case.get("tenant_id") or "") == identity.tenant_id)
    ]
    catalog_state: dict[str, Any] = {
        "status": "local_only" if not supabase_enabled() else "ready",
        "source": "runtime",
    }
    if supabase_enabled():
        try:
            remote_rows = get_supabase_client().list_case_metadata(
                tenant_id=identity.tenant_id if identity and not identity.is_local else None,
            )
        except SupabaseError as error:
            # 公开演示的 50 家企业元数据和字段候选随代码部署；远端目录
            # 恢复时再自动合并。这样 Supabase 短暂 503 不会让整个页面永远
            # 停留在“正在读取”，也不会把任何私有租户记录降级成公开数据。
            remote_rows = []
            catalog_state = {
                "status": "degraded",
                "source": "tracked_verified_cninfo_seed",
                "detail": "Supabase 案例目录暂时不可用，当前展示已校验的公开企业种子；新任务仍需远端队列恢复。",
                "error_code": getattr(error, "code", "SUPABASE_ERROR"),
            }
        known = {str(case.get("case_id")) for case in cases}
        for row in remote_rows:
            case_id = str(row.get("case_id") or "")
            if not case_id or case_id in known:
                continue
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            cases.append(
                {
                    **metadata,
                    "case_id": case_id,
                    "tenant_id": row.get("tenant_id"),
                    "sample_type": row.get("sample_type"),
                    "company_name": row.get("company_name"),
                    "company_alias": metadata.get("company_alias") or row.get("company_name"),
                    "ticker": row.get("ticker") or "",
                    "t0": row.get("t0"),
                    "source_snapshot_id": row.get("source_snapshot_id"),
                    "documents": [],
                    "available_years": metadata.get("available_years") or [],
                }
            )
        # 即使远端查询成功，仍合并公开 seed 中尚未同步到 Postgres 的企业。
        # seed 只包含可信的 CNINFO public scope，不包含任何租户私有记录。
        if _public_demo_enabled():
            for seed_case in load_seed_cases(WORKSPACE_ROOT):
                case_id = str(seed_case.get("case_id") or "")
                if case_id and case_id not in known:
                    cases.append(seed_case)
                    known.add(case_id)
            if catalog_state.get("status") == "ready":
                catalog_state["source"] = "supabase_plus_verified_seed"
    return identity, cases, catalog_state


def _registered_standard_source_url(document_id: str) -> str | None:
    """公开演示不再分发年报全文，仅允许回到内置登记的巨潮官方原件。"""
    document = next(
        (
            row
            for row in get_case(WORKSPACE_ROOT, CASE_ID).get("documents", [])
            if row.get("document_id") == document_id
        ),
        None,
    )
    if document is None:
        return None
    source_url = str(document.get("source_url") or "")
    if not source_url.startswith("https://static.cninfo.com.cn/finalpage/"):
        return None
    return source_url


def _ensure_public_standard_sources(case_id: str) -> None:
    """Render 公开演示缺少年报缓存时受控补取；其他案例不允许联网补文件。"""
    if not _public_demo_enabled() or case_id.upper() != CASE_ID:
        return
    try:
        ensure_standard_sources(WORKSPACE_ROOT)
    except (httpx.HTTPError, OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail=f"官方来源缓存准备失败，已关闭本次运行：{type(error).__name__}: {error}",
        ) from error


def _validate_sources(rows: list[dict[str, Any]], t0: str) -> list[str]:
    """字段证据必须可定位、可哈希、口径明确；模型不能替代这个闸门。"""
    issues: list[str] = []
    verified_hashes: dict[Path, str] = {}
    for row in rows:
        required = (
            "evidence_id",
            "field_id",
            "source_file",
            "disclosure_date",
            "locator",
            "unit",
            "file_sha256",
            "document_id",
        )
        if row.get("source_mode") != "supplement_structured":
            required += ("pdf_page",)
        missing = [field for field in required if row.get(field) in (None, "")]
        if missing:
            issues.append(f"{row.get('field_id', 'UNKNOWN')}缺少：{'、'.join(missing)}")
        if row.get("source_mode") != "supplement_structured" and row.get("disclosure_date", "9999-12-31") > t0:
            issues.append(f"{row.get('evidence_id', 'UNKNOWN')}披露日晚于T0")
        if (
            not isinstance(row.get("value"), (int, float))
            or isinstance(row.get("value"), bool)
            or not math.isfinite(float(row.get("value")))
        ):
            issues.append(f"{row.get('evidence_id', 'UNKNOWN')}金额不是数值")
        if row.get("source_mode") in {"supplement_structured", "supabase_persisted_verified"}:
            # Postgres 字段已绑定已发布案例、文档哈希和页码；fresh web 没有本机 PDF，
            # 这里验证持久化元数据而不伪造一个本地文件存在性检查。
            continue
        source_path = (WORKSPACE_ROOT / str(row.get("storage_relpath", row.get("source_file", "")))).resolve()
        try:
            source_path.relative_to(WORKSPACE_ROOT.resolve())
        except ValueError:
            issues.append(f"{row.get('evidence_id', 'UNKNOWN')}来源文件超出工作区边界")
            continue
        if not source_path.is_file():
            issues.append(f"{row.get('evidence_id', 'UNKNOWN')}来源文件不存在")
        else:
            if source_path not in verified_hashes:
                verified_hashes[source_path] = hashlib.sha256(source_path.read_bytes()).hexdigest().upper()
            actual_sha256 = verified_hashes[source_path]
            if actual_sha256 != str(row.get("file_sha256", "")).upper():
                issues.append(f"{row.get('evidence_id', 'UNKNOWN')}来源文件SHA-256不一致")
    return issues


def _growth(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return (current - previous) / abs(previous)


RULE_FIELDS = {
    "R1": {
        "revenue_current",
        "revenue_previous",
        "revenue_prior",
        "ar_current",
        "ar_previous",
        "ar_prior",
        "ar_allowance_current",
        "ar_allowance_previous",
        "ar_net_current",
        "ar_net_previous",
    },
    "R2": {
        "revenue_current",
        "revenue_previous",
        "operating_cash_flow_current",
        "operating_cash_flow_previous",
        "net_profit_current",
    },
}


def _rule_rows(all_rows: list[dict[str, Any]], rule_id: str) -> list[dict[str, Any]]:
    return [row for row in all_rows if row.get("field_id") in RULE_FIELDS[rule_id]]


def _base_source_validation(issues: list[str]) -> dict[str, Any]:
    return {
        "status": "failed" if issues else "passed",
        "issues": issues,
        "review_boundary": "程序只完成来源存在性、哈希、日期与结构检查；专业口径仍待人工确认。",
    }


def _r1_result(
    rows: list[dict[str, Any]],
    source_issues: list[str],
    *,
    planned_materiality: float | None = None,
    gap_threshold: float = 0.15,
    strong_gap_threshold: float = 0.30,
    absolute_threshold: float = 0.0,
) -> RuleResult:
    """R1 工程草案：八类指标由程序计算，阈值未签字前不是专业标准。"""
    evidence_ids = [row["evidence_id"] for row in rows if row.get("evidence_id")]
    empty_metrics: dict[str, float | int | str | bool | None] = {
        "revenue_growth": None,
        "ar_growth": None,
        "growth_gap": None,
        "absolute_ar_change": None,
        "ar_to_revenue_current": None,
        "ar_to_revenue_previous": None,
        "turnover_days_current": None,
        "turnover_days_previous": None,
        "turnover_trend_days": None,
        "sustained_periods": None,
        "materiality_multiple": None,
        "materiality_assessment": "未评价金额重要性",
    }
    if source_issues:
        return RuleResult(
            rule_id="R1",
            status="SOURCE_INCOMPLETE",
            screening_status="SOURCE_INCOMPLETE",
            source_validation=_base_source_validation(source_issues),
            metrics=empty_metrics,
            evidence_ids=evidence_ids,
        )
    by_field = {row["field_id"]: float(row["value"]) for row in rows}
    required = {"revenue_current", "revenue_previous", "ar_current", "ar_previous"}
    missing = sorted(required - set(by_field))
    if missing:
        return RuleResult(
            rule_id="R1",
            status="DATA_GAP",
            screening_status="DATA_GAP",
            # 字段缺失是数据缺口，不是来源文件、哈希或披露时点校验失败。
            source_validation=_base_source_validation([]),
            metrics=empty_metrics,
            risk_card={
                "card_type": "data_gap",
                "rule_id": "R1",
                "title": "R1本次未计算：公开数据缺口",
                "observation": "来源技术校验通过，但缺少R1同比所需字段，系统未对缺失金额作任何猜测。",
                "data_gaps": ["缺少R1基本字段：" + "、".join(missing)],
                "requested_materials": ["缺失年度营业收入和应收账款字段、原文页码及口径说明"],
                "basis_limitation": "应收账款口径未在登记表中说明，待补充。",
                "boundary": "资料缺口不等于来源失败，也不等于无风险；正式采用前须补充并人工复核。",
            },
            evidence_ids=evidence_ids,
        )

    revenue_growth = _growth(by_field["revenue_current"], by_field["revenue_previous"])
    ar_growth = _growth(by_field["ar_current"], by_field["ar_previous"])
    if revenue_growth is None or ar_growth is None:
        metrics = {**empty_metrics, "revenue_growth": revenue_growth, "ar_growth": ar_growth}
        return RuleResult(
            rule_id="R1",
            status="DATA_GAP",
            screening_status="DATA_GAP",
            source_validation=_base_source_validation([]),
            metrics=metrics,
            risk_card={
                "card_type": "screening_only",
                "rule_id": "R1",
                "title": "R1无法计算：上年营业收入或应收账款为零",
                "data_gaps": ["需确认上年基数与可比口径"],
                "requested_materials": ["相关年度报表项目明细及口径说明"],
            },
            evidence_ids=evidence_ids,
        )

    growth_gap = ar_growth - revenue_growth
    absolute_change = by_field["ar_current"] - by_field["ar_previous"]
    current_ratio = by_field["ar_current"] / by_field["revenue_current"] if by_field["revenue_current"] else None
    previous_ratio = by_field["ar_previous"] / by_field["revenue_previous"] if by_field["revenue_previous"] else None
    turnover_current = (
        ((by_field["ar_current"] + by_field["ar_previous"]) / 2) / by_field["revenue_current"] * 365
        if by_field["revenue_current"]
        else None
    )
    prior_available = "ar_prior" in by_field and "revenue_prior" in by_field
    turnover_previous: float | None = None
    previous_gap: float | None = None
    if prior_available and by_field["revenue_previous"]:
        turnover_previous = (
            (by_field["ar_previous"] + by_field["ar_prior"]) / 2 / by_field["revenue_previous"] * 365
        )
        prior_rev_growth = _growth(by_field["revenue_previous"], by_field["revenue_prior"])
        prior_ar_growth = _growth(by_field["ar_previous"], by_field["ar_prior"])
        if prior_rev_growth is not None and prior_ar_growth is not None:
            previous_gap = prior_ar_growth - prior_rev_growth
    turnover_trend = turnover_current - turnover_previous if turnover_current is not None and turnover_previous is not None else None
    sustained_periods = 1 if growth_gap >= gap_threshold else 0
    if sustained_periods and previous_gap is not None and previous_gap >= gap_threshold:
        sustained_periods = 2
    materiality_multiple = (
        abs(absolute_change) / planned_materiality
        if planned_materiality is not None and planned_materiality > 0
        else None
    )
    materiality_assessment = (
        "未评价金额重要性"
        if planned_materiality is None
        else "达到或超过计划重要性"
        if abs(absolute_change) >= planned_materiality
        else "低于计划重要性"
    )
    basis_values = {
        str(row.get("field_basis"))
        for row in rows
        if row.get("field_id") in {"ar_current", "ar_previous", "ar_prior"}
        and row.get("field_basis")
    }
    if not basis_values:
        basis_limitation = "应收账款口径未在登记表中说明，待补充。"
    elif "net" in basis_values:
        basis_limitation = "应收账款仅有净额/报表列示额，未达到专业目标的账面余额口径。"
    elif "gross" in basis_values:
        basis_limitation = "应收账款采用账面余额口径。"
    else:
        basis_limitation = "应收账款口径未在登记表中说明，待补充。"
    candidate = growth_gap >= gap_threshold and abs(absolute_change) >= absolute_threshold
    strength = "strong" if candidate and growth_gap >= strong_gap_threshold else "standard" if candidate else "none"
    status = "candidate" if candidate else "RULE_NOT_TRIGGERED"
    metrics = {
        "revenue_growth": revenue_growth,
        "ar_growth": ar_growth,
        "growth_gap": growth_gap,
        "absolute_ar_change": absolute_change,
        "ar_to_revenue_current": current_ratio,
        "ar_to_revenue_previous": previous_ratio,
        "turnover_days_current": turnover_current,
        "turnover_days_previous": turnover_previous,
        "turnover_trend_days": turnover_trend,
        "sustained_periods": sustained_periods,
        "materiality_multiple": materiality_multiple,
        "materiality_assessment": materiality_assessment,
        "three_year_trend_available": prior_available,
    }
    return RuleResult(
        rule_id="R1",
        status=status,
        screening_status=status,
        source_validation=_base_source_validation([]),
        metrics=metrics,
        evidence_ids=evidence_ids,
        risk_card={
            "card_type": "screening_only",
            "rule_id": "R1",
            "engineering_version": R1_VERSION,
            "screening_strength": strength,
            "configured_thresholds": {
                "gap_threshold": gap_threshold,
                "strong_gap_threshold": strong_gap_threshold,
                "absolute_threshold": absolute_threshold,
                "planned_materiality": planned_materiality,
                "review_status": "draft_pending_professional_signoff",
            },
            "status": "candidate_pending_ai_and_human_review" if candidate else "rule_not_triggered",
            "title": "程序筛查形成R1待核查候选" if candidate else "程序筛查未形成R1方向候选",
            "observation": (
                f"应收账款增速为{ar_growth:.2%}，营业收入增速为{revenue_growth:.2%}，增速差为{growth_gap:.2%}；"
                f"应收账款绝对变动为{absolute_change:,.2f}{rows[0].get('unit', '')}。{materiality_assessment}。"
            ),
            "basis_limitation": basis_limitation,
            "trend_limitation": None if prior_available else "缺少第三年，持续期间和周转趋势不可评价。",
            "data_gaps": ["账龄结构", "期后回款", "信用政策变动", "主要客户合同结算条款"],
            "requested_materials": ["账龄明细表", "期后回款记录", "信用政策说明", "主要合同关键条款摘要"],
            "boundary": "这是工程草案筛查状态，不是审计认定；需经RAG、三Agent和人工复核。",
        },
    )


def _r2_result(rows: list[dict[str, Any]], source_issues: list[str], min_gap: float) -> RuleResult:
    """R2 仅为辅助工程规则；跨期变号或基数过小时禁止展示伪同比。"""
    evidence_ids = [row["evidence_id"] for row in rows if row.get("evidence_id")]
    metric_defaults: dict[str, float | int | str | bool | None] = {
        "revenue_growth": None,
        "operating_cash_flow_growth": None,
        "growth_gap": None,
        "cashflow_to_revenue_current": None,
        "cashflow_to_revenue_previous": None,
        "net_profit_cashflow_gap": None,
    }
    if source_issues:
        return RuleResult(
            rule_id="R2",
            status="SOURCE_INCOMPLETE",
            screening_status="SOURCE_INCOMPLETE",
            source_validation=_base_source_validation(source_issues),
            metrics=metric_defaults,
            evidence_ids=evidence_ids,
        )
    by_field = {row["field_id"]: float(row["value"]) for row in rows}
    required = {"revenue_current", "revenue_previous", "operating_cash_flow_current", "operating_cash_flow_previous"}
    missing = sorted(required - set(by_field))
    if missing:
        return RuleResult(
            rule_id="R2",
            status="DATA_GAP",
            screening_status="DATA_GAP",
            source_validation=_base_source_validation(["缺少R2字段：" + "、".join(missing)]),
            metrics=metric_defaults,
            risk_card={
                "card_type": "screening_only",
                "rule_id": "R2",
                "title": "R2辅助规则缺少可比字段",
                "boundary": "R2不抢占R1主演示，也不伪装成完整能力。",
            },
            evidence_ids=evidence_ids,
        )
    revenue_growth = _growth(by_field["revenue_current"], by_field["revenue_previous"])
    current_ocf = by_field["operating_cash_flow_current"]
    previous_ocf = by_field["operating_cash_flow_previous"]
    previous_revenue = by_field["revenue_previous"]
    cashflow_growth = _growth(current_ocf, previous_ocf)
    current_ratio = current_ocf / by_field["revenue_current"] if by_field["revenue_current"] else None
    previous_ratio = previous_ocf / previous_revenue if previous_revenue else None
    net_profit = by_field.get("net_profit_current")
    profit_gap = (current_ocf - net_profit) / abs(net_profit) if isinstance(net_profit, float) and net_profit > 0 else None
    metrics = {
        "revenue_growth": revenue_growth,
        "operating_cash_flow_growth": cashflow_growth,
        "growth_gap": None,
        "cashflow_to_revenue_current": current_ratio,
        "cashflow_to_revenue_previous": previous_ratio,
        "net_profit_cashflow_gap": profit_gap,
    }
    if revenue_growth is None:
        return RuleResult(
            rule_id="R2",
            status="DATA_GAP",
            screening_status="DATA_GAP",
            source_validation=_base_source_validation([]),
            metrics=metrics,
            evidence_ids=evidence_ids,
        )
    comparable = previous_ocf != 0 and abs(previous_ocf) >= abs(previous_revenue) * 0.03 and current_ocf * previous_ocf > 0
    if not comparable:
        reason = (
            "上年经营现金流为零"
            if previous_ocf == 0
            else "本年经营现金流为零"
            if current_ocf == 0
            else "经营现金流跨期变号"
            if current_ocf * previous_ocf < 0
            else "上年经营现金流基数过小"
        )
        metrics["operating_cash_flow_growth"] = None
        return RuleResult(
            rule_id="R2",
            status="DATA_NOT_COMPARABLE",
            screening_status="DATA_NOT_COMPARABLE",
            source_validation=_base_source_validation([]),
            metrics=metrics,
            evidence_ids=evidence_ids,
            risk_card={
                "card_type": "screening_only",
                "rule_id": "R2",
                "engineering_version": R2_VERSION,
                "title": f"R2同比不宜比较：{reason}",
                "observation": f"本年经营现金流为{current_ocf:,.2f}元，上年为{previous_ocf:,.2f}元；程序不展示失真的同比。",
                "boundary": "R2为辅助工程规则，不是正式专业标准。",
            },
        )
    growth_gap = revenue_growth - float(cashflow_growth)
    metrics["growth_gap"] = growth_gap
    candidate = revenue_growth > 0 and growth_gap > min_gap
    status = "candidate" if candidate else "RULE_NOT_TRIGGERED"
    return RuleResult(
        rule_id="R2",
        status=status,
        screening_status=status,
        source_validation=_base_source_validation([]),
        metrics=metrics,
        evidence_ids=evidence_ids,
        risk_card={
            "card_type": "screening_only",
            "rule_id": "R2",
            "engineering_version": R2_VERSION,
            "configured_min_gap": min_gap,
            "title": "R2辅助筛查形成待核查候选" if candidate else "R2辅助筛查未形成方向候选",
            "observation": f"营业收入增速为{revenue_growth:.2%}，经营现金流增速为{cashflow_growth:.2%}，差额为{growth_gap:.2%}。",
            "boundary": "R2不抢占R1主演示，结果须人工复核。",
        },
    )


def _screening_overall(results: list[RuleResult]) -> str:
    if results and all(result.status == "INDUSTRY_UNKNOWN" for result in results):
        return "INDUSTRY_UNKNOWN"
    if results and all(result.status == "NOT_APPLICABLE" for result in results):
        return "NOT_APPLICABLE"
    if any(result.status == "SOURCE_INCOMPLETE" for result in results):
        return "SOURCE_INCOMPLETE"
    if any(result.status == "candidate" for result in results):
        return "candidate"
    if any(result.status == "DATA_NOT_COMPARABLE" for result in results):
        return "DATA_NOT_COMPARABLE"
    if any(result.status == "DATA_GAP" for result in results):
        return "DATA_GAP"
    return "RULE_NOT_TRIGGERED"


def _industry_period_sources(
    case: dict[str, Any],
    *,
    current_year: int,
    gate: dict[str, Any],
    tenant_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """组装行业专用字段，不把通用 R1/R2 的字段名硬套到金融报表。"""

    local_rows = _materialized_financial_rows(case, tenant_id=tenant_id)
    rows = local_rows if local_rows is not None else deepcopy(case.get("financial_fields") or [])
    documents = {str(item.get("document_id")): item for item in case.get("documents", [])}
    requested_year = int(current_year)
    eligible: list[dict[str, Any]] = []
    for row in rows:
        try:
            year = int(row.get("year"))
        except (TypeError, ValueError):
            continue
        document = documents.get(str(row.get("document_id")))
        disclosure_date = str(row.get("disclosure_date") or (document or {}).get("disclosure_date") or "")
        # 年度和披露日期都受 T0 与请求年度约束；后续年报不能回退替代请求时点。
        if year > requested_year or (case.get("t0") and disclosure_date > str(case["t0"])):
            continue
        source = deepcopy(row)
        source["field_id"] = f"industry_{row.get('field_kind')}_{year}"
        source["field_label"] = f"{year}年{row.get('field_kind')}（行业专用字段）"
        if document:
            source.setdefault("source_file", document.get("source_file"))
            source.setdefault("storage_relpath", document.get("storage_relpath"))
            source.setdefault("file_sha256", document.get("sha256") or document.get("file_sha256"))
            source.setdefault("source_url", document.get("source_url"))
            source.setdefault("pdf_page", row.get("pdf_page"))
            source.setdefault("disclosure_date", document.get("disclosure_date"))
        if local_rows is None:
            source["source_mode"] = "supabase_persisted_verified"
            source.setdefault("source_file", source.get("document_id"))
            source.setdefault("file_sha256", (document or {}).get("sha256") or source.get("file_sha256"))
            source.setdefault("locator", f"PDF 第 {source.get('pdf_page')} 页")
            source.setdefault("unit", case.get("amount_unit", "元"))
        eligible.append(source)
    years = sorted({int(row["year"]) for row in eligible}, reverse=True)
    effective_year = max(years, default=None)
    previous_year = effective_year - 1 if effective_year is not None else None
    prior_year = effective_year - 2 if effective_year is not None and effective_year - 2 in years else None
    selected_years = {year for year in (effective_year, previous_year, prior_year) if year is not None}
    sources = [row for row in eligible if int(row["year"]) in selected_years]
    sources.sort(key=lambda row: (int(row.get("year") or 0), str(row.get("field_kind") or "")), reverse=True)
    plan = {
        "mode": "public_prescreen",
        "specialized_rule": gate.get("specialized_rule"),
        "industry_rule_version": gate.get("industry_rule_version"),
        "requested_current_year": requested_year,
        "analysis_current_year": effective_year,
        "analysis_previous_year": previous_year,
        "analysis_years": [year for year in (effective_year, previous_year, prior_year) if year is not None],
        "rule_plans": {},
        "skipped_rules": [],
        "missing_fields": [],
        "has_calculable_rule": bool(effective_year and previous_year),
        "source_candidate_count": len(sources),
        "human_confirmation": "recommended_before_formal_adoption_or_export",
        "confidence": "technical_candidate_pending_optional_human_confirmation" if sources else "insufficient_data",
    }
    context = {
        "case_id": case["case_id"],
        "company_name": case.get("company_name") or case.get("company_alias") or "",
        "company_alias": case.get("company_alias") or case.get("company_name") or "",
        "ticker": case.get("ticker") or "",
        "current_year": effective_year if effective_year is not None else requested_year,
        "previous_year": previous_year,
        "prior_year": prior_year,
        "t0": case.get("t0"),
        "currency": case.get("currency", "CNY"),
        "amount_unit": case.get("amount_unit", "元"),
        "statement_scope": case.get("statement_scope", "合并"),
        "sample_type": case.get("sample_type", "public"),
        "model_transfer_allowed": case.get("model_transfer_allowed", False),
        "source_snapshot_id": case.get("source_snapshot_id"),
        "source_review_status": case.get("source_review_status"),
        "three_year_r1_ready": False,
        "requested_current_year": requested_year,
        "analysis_cutoff_year": effective_year,
        "public_prescreen": True,
        "prescreen_plan": plan,
        "industry_gate": deepcopy(gate),
        "case_evidence_count": len(case.get("structured_evidence", [])),
        "case_material_gaps": deepcopy(case.get("material_gaps", [])),
    }
    return context, sources


def _industry_not_applicable_result(rule_id: str, gate: dict[str, Any]) -> RuleResult:
    """行业不适用时返回明确卡片，不把它伪装成资料缺失或无风险。"""

    unknown = gate.get("fit_level") == "unknown"
    status = "INDUSTRY_UNKNOWN" if unknown else "NOT_APPLICABLE"
    title = f"{rule_id}待确认行业适配" if unknown else f"{rule_id}当前行业不适用"
    observation = (
        "公司行业或报表体系元数据不足，系统没有猜测行业，也没有执行当前数值规则。"
        if unknown
        else gate.get("rationale") or "当前工程规则不适合该行业。"
    )
    return RuleResult(
        rule_id=rule_id,
        status=status,
        screening_status=status,
        source_validation={
            "status": "not_applicable",
            "issues": [],
            "review_boundary": "当前行业需要专用规则；本次没有对不适用的 R1/R2 指标作数值判断。",
        },
        metrics={},
        risk_card={
            "card_type": "industry_gate",
            "rule_id": rule_id,
            "title": title,
            "observation": observation,
            "data_gaps": [],
            "requested_materials": ["对应行业专用财务指标、会计政策和风险资料"],
            "boundary": "规则不适用或行业待确认不等于企业无风险；仍可继续使用公开年报 RAG，并选择行业专用规则。",
            "industry_gate": gate,
        },
        evidence_ids=[],
    )


def _industry_specialized_result(
    *,
    gate: dict[str, Any],
    sources: list[dict[str, Any]],
    current_year: int,
    t0: str,
    outer_rule_id: str = "R1",
) -> tuple[RuleResult, dict[str, Any]]:
    """把行业专用结果装进兼容的 RuleResult 外壳，保留原有 API 协议。"""

    source_issues = _validate_sources(sources, t0)
    prescreen = build_industry_prescreen(
        gate=gate,
        rows=sources,
        current_year=current_year,
        t0=t0,
        source_issues=source_issues,
    )
    risk_card = {
        "card_type": "industry_specialized_screening",
        "rule_id": prescreen["industry_rule_id"],
        "title": prescreen["industry_rule_name"],
        "status": prescreen["status"],
        "engineering_version": prescreen["industry_rule_version"],
        "configured_thresholds": prescreen["configured_thresholds"],
        "observation": prescreen["rationale"],
        "field_evidence": prescreen["field_evidence"],
        "data_gaps": prescreen["data_gaps"],
        "requested_materials": prescreen["requested_materials"],
        "human_review_status": prescreen["human_review_status"],
        "professional_signoff_status": prescreen["professional_signoff_status"],
        "boundary": prescreen["boundary"],
        "rule_not_triggered_boundary": prescreen["rule_not_triggered_boundary"],
        "industry_gate": gate,
    }
    result = RuleResult(
        rule_id=outer_rule_id,
        status=prescreen["status"],
        screening_status=prescreen["screening_status"],
        source_validation=prescreen["source_validation"],
        metrics=prescreen["metrics"],
        risk_card=risk_card,
        evidence_ids=prescreen["evidence_ids"],
    )
    return result, prescreen


def _model_check_from_results(results: list[RuleResult], *, enabled: bool, model_id: str) -> ModelCheck:
    if not enabled:
        return ModelCheck(status="not_requested", model_id=model_id, detail="本次为仅计算预检，未运行RAG和三Agent。")
    steps = [step for result in results for step in result.agent_steps]
    statuses = [step.status for step in steps]
    if not statuses or all(status == "not_applicable" for status in statuses):
        return ModelCheck(status="not_applicable", model_id=model_id, detail="程序未形成规则候选，三Agent不适用。")
    if "config_missing" in statuses:
        return ModelCheck(status="config_missing", model_id=model_id, detail="未配置DEEPSEEK_API_KEY，完整分析未完成。")
    if "provider_unreachable" in statuses:
        return ModelCheck(status="provider_unreachable", model_id=model_id, detail="模型调用失败，已关闭后续AI草稿链。")
    if "model_transfer_revoked" in statuses:
        return ModelCheck(status="model_transfer_revoked", model_id=model_id, detail="逐案模型传输同意已撤销或无法确认，已关闭后续AI调用。")
    if "MODEL_OUTPUT_INVALID" in statuses or "EVIDENCE_BUNDLE_EMPTY" in statuses:
        return ModelCheck(status="MODEL_OUTPUT_INVALID", model_id=model_id, detail="模型输出或证据包未通过硬校验，完整分析未完成。")
    completed = [step for step in steps if step.status == "completed"]
    candidate_count = sum(1 for result in results if result.status == "candidate")
    if candidate_count and len(completed) == candidate_count * 3:
        response_material = "".join(step.response_sha256 or "" for step in completed)
        return ModelCheck(
            status="model_success",
            model_id=model_id,
            duration_ms=sum(step.duration_ms or 0 for step in completed),
            response_sha256=hashlib.sha256(response_material.encode("utf-8")).hexdigest(),
            detail="三Agent完成结构化输出；数字、来源和人工处理未交给模型决定。",
        )
    return ModelCheck(status="MODEL_OUTPUT_INVALID", model_id=model_id, detail="AI草稿链没有形成完整可验证结果。")


RAG_QUESTIONS_BY_RULE = {
    "R1": ("RAG-Q1", "RAG-Q2", "RAG-Q5", "RAG-Q6"),
    "R2": ("RAG-Q3", "RAG-Q4", "RAG-Q6"),
}


def _run_rag_for_candidates(
    *,
    context: dict[str, Any],
    rule_results: list[RuleResult],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """固定问题集自动检索；无命中是证据缺口，索引/结构失败才关闭完整链。"""
    candidate_rules = [result.rule_id for result in rule_results if result.status == "candidate"]
    if not candidate_rules:
        return [], [], [], None
    try:
        identity_payload = context.get("request_identity") if isinstance(context.get("request_identity"), dict) else {}
        owner_tenant_id = str(identity_payload.get("tenant_id") or "").strip() or None
        remote_case = _case_record(context["case_id"], tenant_id=owner_tenant_id)
        if remote_case is None:
            raise RuntimeError("RAG 对应案例不存在")
        # Supabase 模式下 active RAG snapshot 是跨实例唯一权威；本机 SQLite
        # 可能仍停留在旧版本，不能把旧片段混进当前运行或把远端 snapshot ID
        # 写到本机结果上。只有完全离线的 local 模式才读取本机索引。
        local_case = (
            _materialized_case_for_resolved(remote_case, tenant_id=owner_tenant_id)
            if not supabase_enabled()
            else None
        )
        if local_case is not None:
            prepare_index(WORKSPACE_ROOT, case_id=context["case_id"], force=False)
        retrievals: list[dict[str, Any]] = []
        rag_evidence: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        seen_evidence: set[str] = set()
        for rule_id in candidate_rules:
            for question_id in RAG_QUESTIONS_BY_RULE[rule_id]:
                record = (
                    retrieve(
                        WORKSPACE_ROOT,
                        query="",
                        question_id=question_id,
                        t0=context["t0"],
                        rule_id=rule_id,
                        top_k=2,
                        case_id=context["case_id"],
                        company_name=context["company_name"],
                    )
                    if local_case is not None
                    else _remote_rag_retrieve(
                        case=remote_case or {},
                        query="",
                        question_id=question_id,
                        t0=context["t0"],
                        rule_id=rule_id,
                        top_k=2,
                        owner_tenant_id=owner_tenant_id,
                        requested_by=str(identity_payload.get("user_id") or "").strip() or None,
                    )
                )
                retrievals.append(record)
                if record["status"] == "no_hit":
                    gaps.append(
                        {
                            "question_id": question_id,
                            "retrieval_id": record["retrieval_id"],
                            **record["evidence_gap"],
                        }
                    )
                for item in record["results"]:
                    if item["evidence_id"] in seen_evidence:
                        continue
                    seen_evidence.add(item["evidence_id"])
                    rag_evidence.append(
                        {
                            **item,
                            "rule_id": rule_id,
                            "question_id": question_id,
                            "retrieval_id": record["retrieval_id"],
                        }
                    )
        return retrievals, rag_evidence, gaps, None
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        return [], [], [], f"{type(error).__name__}: {error}"


def _aggregate_ai_recommendation(results: list[RuleResult]) -> str:
    recommendations = [result.ai_recommendation for result in results if result.ai_recommendation in {"retain", "downgrade", "defer"}]
    if "retain" in recommendations:
        return "retain"
    if "downgrade" in recommendations:
        return "downgrade"
    if "defer" in recommendations:
        return "defer"
    return "not_generated"


def _reconcile_registered_context(
    results: list[RuleResult], supplemental_evidence: list[dict[str, Any]]
) -> None:
    """已登记账龄只能关闭同名资料缺口，不能据此把待核查事项自动降级。"""
    if not any(item.get("evidence_kind") == "public_aging" for item in supplemental_evidence):
        return
    for result in results:
        if result.rule_id != "R1" or not result.risk_card:
            continue
        card = result.risk_card
        card["data_gaps"] = [item for item in card.get("data_gaps", []) if "账龄" not in item]
        card["requested_materials"] = [item for item in card.get("requested_materials", []) if "账龄" not in item]
        card["available_context"] = ["公开年报汇总账龄已登记；客户级明细与真实性仍待人工复核。"]


def _execute_run(
    *,
    context: dict[str, Any],
    sources: list[dict[str, Any]],
    rule_ids: list[str],
    run_mode: str,
    r2_min_gap: float,
    planned_materiality: float | None,
    r1_gap_threshold: float,
    r1_strong_gap_threshold: float,
    r1_absolute_threshold: float,
    http_request: Request,
    run_prefix: str,
    supplement_evidence: list[dict[str, Any]] | None = None,
    model_recheck: Callable[[str], bool] | None = None,
) -> RunResponse:
    pipeline_task_id = str(getattr(http_request.state, "audittrace_pipeline_task_id", None) or "").strip()
    # worker 重试必须命中同一运行编号；随机 run_id 会让“已落库但未 complete”
    # 的恢复再次执行模型，并绕过 analysis_runs 的 task_id 唯一约束。
    run_suffix = (
        hashlib.sha256(f"{run_prefix}:{pipeline_task_id}".encode("utf-8")).hexdigest()[:12].upper()
        if pipeline_task_id
        else uuid.uuid4().hex[:12].upper()
    )
    run_id = f"{run_prefix}-{run_suffix}"
    context = deepcopy(context)
    if pipeline_task_id:
        context["pipeline_task_id"] = pipeline_task_id
        _require_worker_lease(http_request)
    context.update(
        {
            "scene": "审计计划",
            "selected_rule_ids": rule_ids,
            "run_mode": run_mode,
            "engine_version": ENGINE_VERSION,
            "run_schema_version": RUN_SCHEMA_VERSION,
            "r1_version": R1_VERSION,
            "r2_version": R2_VERSION,
            "agent_prompt_version": PROMPT_VERSION,
            "configured_parameters": {
                "planned_materiality": planned_materiality,
                "r1_gap_threshold": r1_gap_threshold,
                "r1_strong_gap_threshold": r1_strong_gap_threshold,
                "r1_absolute_threshold": r1_absolute_threshold,
                "r2_min_gap": r2_min_gap,
                "professional_review_status": "draft_pending_professional_signoff",
            },
        }
    )
    rule_results: list[RuleResult] = []
    sources_by_rule: dict[str, list[dict[str, Any]]] = {}
    industry_gate = context.get("industry_gate") or {}
    industry_gate_blocked = industry_gate.get("fit_level") in {"not_applicable", "unknown"}
    specialized_rule = industry_gate.get("specialized_rule")
    specialized_prescreen: dict[str, Any] | None = None
    specialized_result: RuleResult | None = None
    for rule_id in rule_ids:
        rows = _rule_rows(sources, rule_id)
        sources_by_rule[rule_id] = rows
        if specialized_rule and specialized_prescreen is None:
            result, specialized_prescreen = _industry_specialized_result(
                gate=industry_gate,
                sources=sources,
                current_year=int(context.get("current_year") or 0),
                t0=str(context.get("t0") or "9999-12-31"),
                outer_rule_id=rule_id,
            )
            specialized_result = result
            context["industry_prescreen"] = specialized_prescreen
            if context.get("prescreen_plan"):
                context["prescreen_plan"]["missing_fields"] = specialized_prescreen.get("data_gaps", [])
                context["prescreen_plan"]["confidence"] = (
                    "technical_candidate_pending_optional_human_confirmation"
                    if specialized_prescreen.get("status") not in {"DATA_GAP", "SOURCE_INCOMPLETE"}
                    else "technical_candidate_with_gaps"
                )
        elif specialized_rule:
            # 一个请求可以同时带 R1/R2，但行业专用规则只计算一次；
            # 兼容外层 rule_results 时明确标出其余通用规则不适用。
            result = _industry_not_applicable_result(rule_id, industry_gate)
            result.risk_card["title"] = "通用 R1/R2 已由行业专用预筛替代"
            result.risk_card["observation"] = "本次不重复套用普通工商企业规则，详细结果见行业专用规则卡。"
        elif industry_gate_blocked:
            result = _industry_not_applicable_result(rule_id, industry_gate)
        else:
            issues = _validate_sources(rows, context["t0"])
            if rule_id == "R1":
                result = _r1_result(
                    rows,
                    issues,
                    planned_materiality=planned_materiality,
                    gap_threshold=r1_gap_threshold,
                    strong_gap_threshold=r1_strong_gap_threshold,
                    absolute_threshold=r1_absolute_threshold,
                )
            else:
                result = _r2_result(rows, issues, r2_min_gap)
            if industry_gate.get("fit_level") == "conditional" and result.risk_card is not None:
                result.risk_card["industry_gate"] = industry_gate
                result.risk_card["boundary"] = (
                    f"条件适用行业：{industry_gate.get('rationale', '')} 当前结果只能作为公开预筛，不能替代专用口径复核。"
                )
        rule_results.append(result)

    prescreen_plan = context.get("prescreen_plan") if context.get("public_prescreen") else None
    if prescreen_plan:
        # 把降级范围写入每次运行，使用者能看见“分析了什么、跳过了什么、为什么”。
        # 分析截止年度和请求年度分开保存，避免使用者把旧年度结果误认为最新年报。
        # 风险卡只描述待核查事项，不把缺口转换成舞弊或审计意见。
        prescreen_summary = {
            "mode": "公开财报快速预筛",
            "requested_current_year": prescreen_plan.get("requested_current_year"),
            "analysis_cutoff_year": prescreen_plan.get("analysis_current_year"),
            "analysis_years": prescreen_plan.get("analysis_years", []),
            "missing_fields": prescreen_plan.get("missing_fields", []),
            "skipped_rules": prescreen_plan.get("skipped_rules", []),
            "rule_plans": prescreen_plan.get("rule_plans", {}),
            "industry_prescreen": context.get("industry_prescreen"),
            "confidence": prescreen_plan.get("confidence"),
            "human_review": "正式采用、缓存或导出前复核；不阻断本次公开预筛。",
        }
        context["prescreen_summary"] = prescreen_summary
        for result in rule_results:
            plan = prescreen_plan.get("rule_plans", {}).get(result.rule_id)
            if result.risk_card is None and not plan:
                result.risk_card = {
                    "card_type": "screening_only",
                    "rule_id": result.rule_id,
                    "title": f"{result.rule_id}本次未计算：公开数据不足",
                    "observation": "系统保留 RAG 和其他可运行规则，未对缺失金额作任何猜测。",
                    "data_gaps": [item.get("reason", "缺少连续可比字段") for item in prescreen_plan.get("skipped_rules", []) if item.get("rule_id") == result.rule_id],
                    "requested_materials": ["缺失年度的官方年报字段或可回查的补充资料"],
                    "boundary": "公开预筛允许降级；正式采用前仍需人工回查证据。",
                }
            if result.risk_card is not None and plan and not plan.get("three_year_available"):
                result.risk_card["trend_limitation"] = "缺少第三个连续年度，未评价三年持续趋势。"
            if result.risk_card is not None and prescreen_plan.get("missing_fields"):
                result.risk_card["prescreen_missing_fields"] = prescreen_plan["missing_fields"]

        if specialized_prescreen is not None and specialized_result is not None:
            # 行业专用卡片是公开预筛摘要的唯一来源，避免后续通用补丁改写其缺口语义。
            if specialized_result.risk_card is not None:
                specialized_result.risk_card["prescreen_missing_fields"] = specialized_prescreen.get("data_gaps", [])

    screening_status = _screening_overall(rule_results)
    public_sources = [_public_source(row, private=bool(context.get("private_case"))) for row in sources]
    supplementary = deepcopy(supplement_evidence or [])
    _reconcile_registered_context(rule_results, supplementary)
    retrievals: list[dict[str, Any]] = []
    rag_evidence: list[dict[str, Any]] = []
    evidence_gaps: list[dict[str, Any]] = []
    rag_error: str | None = None
    candidate_exists = any(result.status == "candidate" for result in rule_results)
    if run_mode == "full_analysis" and context.get("model_transfer_allowed", False):
        retrievals, rag_evidence, evidence_gaps, rag_error = _run_rag_for_candidates(
            context=context,
            rule_results=rule_results,
        )

    sensitive_findings = scan_sensitive_payload(
        {
            "field_evidence": public_sources,
            "rag_evidence": rag_evidence,
            "supplement_evidence": supplementary,
        }
    )
    context["privacy_scan"] = {
        "status": "blocked" if sensitive_findings else "passed",
        "finding_count": len(sensitive_findings),
        "findings": sensitive_findings,
        "external_model_scope": model_transmission_scope(),
    }
    sensitive_data_blocked = bool(context.get("model_transfer_allowed") and sensitive_findings)

    api_key, base_url, model_id = _model_settings()
    if run_mode == "calculation_only":
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="not_requested" if result.status == "candidate" else "not_applicable",
                    detail="本次为仅计算预检，未运行RAG和三Agent。" if result.status == "candidate" else "规则未触发，三Agent不适用。",
                )
            ]
        model_check = _model_check_from_results(rule_results, enabled=False, model_id=model_id)
        run_completeness = "incomplete_calculation_only"
    elif specialized_rule:
        # 行业专用阈值仍是工程草案，本批只完成本地确定性预筛，不把普通
        # 三Agent提示词误用于银行、保险、券商或合同循环口径。
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="not_applicable",
                    detail="行业专用工程预筛已完成；当前批次不调用通用三Agent，等待专业人员确认规则口径和阈值。",
                )
            ]
        model_check = ModelCheck(
            status="not_applicable",
            model_id=model_id,
            detail="行业专用工程规则不复用普通 R1/R2 三Agent链；本次未调用外部模型。",
        )
        has_gaps = bool(
            specialized_prescreen
            and specialized_prescreen.get("status") in {"DATA_GAP", "SOURCE_INCOMPLETE"}
        )
        run_completeness = (
            "complete_public_prescreen_industry_rule_with_gaps"
            if prescreen_plan and has_gaps
            else "complete_public_prescreen_industry_rule"
            if prescreen_plan
            else "complete_industry_rule_with_gaps"
            if has_gaps
            else "complete_industry_rule"
        )
    elif all(result.status in {"NOT_APPLICABLE", "INDUSTRY_UNKNOWN"} for result in rule_results):
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="not_applicable",
                    detail="行业适配闸门已关闭当前规则，未调用模型；请使用行业专用规则或 RAG。",
                )
            ]
        model_check = ModelCheck(status="not_applicable", model_id=model_id, detail="当前规则不适用于该行业或行业信息不足，三Agent未调用。")
        if industry_gate.get("fit_level") == "unknown":
            run_completeness = "complete_public_prescreen_industry_unknown" if prescreen_plan else "complete_rule_industry_unknown"
        else:
            run_completeness = "complete_public_prescreen_not_applicable" if prescreen_plan else "complete_rule_not_applicable"
    elif not context.get("model_transfer_allowed", False):
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="model_transfer_not_allowed" if result.status == "candidate" else "not_applicable",
                    detail="案例未授权模型传输，只能完成本地计算预检。" if result.status == "candidate" else "规则未触发，三Agent不适用。",
                )
            ]
        model_check = ModelCheck(
            status="model_transfer_not_allowed",
            model_id=model_id,
            detail=str(context.get("model_transfer_block_reason") or "本次模型传输未获有效许可，完整分析主链已如实关闭。"),
        )
        run_completeness = "incomplete_model_transfer_not_allowed"
    elif rag_error:
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="rag_failed" if result.status == "candidate" else "not_applicable",
                    detail="RAG准备或检索失败，未调用模型。" if result.status == "candidate" else "规则未触发，三Agent不适用。",
                )
            ]
        model_check = ModelCheck(status="not_attempted_rag_failure", model_id=model_id, detail="RAG失败，完整分析未完成。")
        run_completeness = "incomplete_rag_failure"
    elif sensitive_data_blocked:
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="sensitive_data_blocked" if result.status == "candidate" else "not_applicable",
                    detail="模型传输前隐私扫描命中高风险信息，已阻断外部模型调用；本地确定性结果仍保留。",
                    failure_stage="policy" if result.status == "candidate" else None,
                    failure_code="SENSITIVE_DATA_BLOCKED" if result.status == "candidate" else None,
                )
            ]
        model_check = ModelCheck(status="sensitive_data_blocked", model_id=model_id, detail="外部模型调用因高风险个人信息扫描命中而阻断。")
        run_completeness = "incomplete_sensitive_data_blocked"
        if supabase_enabled():
            identity_payload = context.get("request_identity") if isinstance(context.get("request_identity"), dict) else {}
            try:
                get_supabase_client().record_audit_event(
                    tenant_id=str(identity_payload.get("tenant_id") or "") or None,
                    user_id=str(identity_payload.get("user_id") or "") or None,
                    event_type="model_transfer_blocked_sensitive_data",
                    case_id=str(context.get("case_id") or ""),
                    run_id=run_id,
                    metadata={"finding_count": len(sensitive_findings), "finding_kinds": sorted({item["kind"] for item in sensitive_findings})},
                )
            except SupabaseError:
                context["privacy_scan"]["audit_status"] = "unavailable"
    else:
        if candidate_exists:
            _enforce_public_model_quota(http_request)
        for result in rule_results:
            allowed_field_ids = set(result.evidence_ids)
            rule_bundle = {
                "field_evidence": [row for row in public_sources if row.get("evidence_id") in allowed_field_ids],
                "rag_evidence": [row for row in rag_evidence if row.get("rule_id") == result.rule_id],
                "supplement_evidence": supplementary,
                "evidence_gaps": evidence_gaps,
            }
            # RAG 片段在主链中显式进入 Agent；硬校验仍只允许引用该 bundle 的 evidence_id。
            result.agent_steps = run_agent_chain(
                run_id=run_id,
                rule_result=result,
                evidence_bundle=rule_bundle,
                enabled=True,
                api_key=api_key,
                base_url=base_url,
                model_id=model_id,
                before_role=model_recheck,
            )
            review_step = next(
                (step for step in result.agent_steps if step.role == "review" and step.status == "completed" and step.output),
                None,
            )
            if review_step and review_step.output:
                result.ai_recommendation = review_step.output.ai_recommendation or review_step.output.status
                result.ai_draft = review_step.output.model_dump(mode="json")
        model_check = _model_check_from_results(rule_results, enabled=True, model_id=model_id)
        partial_prescreen = bool(
            prescreen_plan
            and (
                prescreen_plan.get("missing_fields")
                or prescreen_plan.get("skipped_rules")
                or any(result.status == "DATA_GAP" for result in rule_results)
            )
        )
        if all(result.status in {"NOT_APPLICABLE", "INDUSTRY_UNKNOWN"} for result in rule_results):
            if industry_gate.get("fit_level") == "unknown":
                run_completeness = "complete_public_prescreen_industry_unknown" if prescreen_plan else "complete_rule_industry_unknown"
            else:
                run_completeness = "complete_public_prescreen_not_applicable" if prescreen_plan else "complete_rule_not_applicable"
        elif not candidate_exists:
            run_completeness = (
                "complete_public_prescreen_with_gaps"
                if prescreen_plan and partial_prescreen
                else "complete_public_prescreen_no_candidate"
                if prescreen_plan
                else "complete_full_analysis_no_candidate"
            )
        elif model_check.status == "model_success":
            run_completeness = "complete_public_prescreen_with_gaps" if partial_prescreen else "complete_full_analysis"
        else:
            run_completeness = (
                "incomplete_model_transfer_revoked"
                if model_check.status == "model_transfer_revoked"
                else "incomplete_model_chain_failed"
            )

    ai_recommendation = _aggregate_ai_recommendation(rule_results)
    final_items = [result.ai_draft for result in rule_results if result.ai_draft]
    final_ai_draft = (
        {
            "schema_version": "final_ai_draft_v2",
            "ai_assisted": True,
            "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
            "items": final_items,
            "boundary": "AI草稿只形成待核查建议；正式认定与发布由人工决定。",
        }
        if final_items
        else None
    )
    all_issues = [issue for result in rule_results for issue in result.source_validation.get("issues", [])]
    evidence_bundle = {
        "schema_version": "evidence_bundle_v2",
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
        "case_id": context["case_id"],
        "field_evidence": public_sources,
        "rag_evidence": rag_evidence,
        "supplement_evidence": supplementary,
        "evidence_gaps": evidence_gaps,
        "rag_error": rag_error,
        "prescreen_summary": context.get("prescreen_summary"),
    }
    response = RunResponse(
        run_id=run_id,
        status=screening_status,
        screening_status=screening_status,
        ai_recommendation=ai_recommendation,
        human_disposition="未复核",
        run_completeness=run_completeness,
        context=context,
        source_validation=_base_source_validation(all_issues),
        sources=public_sources,
        rule_results=rule_results,
        model_check=model_check,
        evidence_bundle=evidence_bundle,
        retrievals=retrievals,
        final_ai_draft=final_ai_draft,
    )
    # 最终本地/远程落盘前再确认一次；即使租约恰在最后一个模型角色后丢失，
    # 旧 worker 也不能发布运行或覆盖新持有者的 checkpoint。
    _require_worker_lease(http_request)
    save_run(WORKSPACE_ROOT, response)
    # 公网模式的 Postgres 记录用于跨实例恢复；本地 JSON 仍作为竞赛模式和失败回放兜底。
    if supabase_enabled():
        identity = context.get("request_identity") if isinstance(context.get("request_identity"), dict) else {}
        owner_tenant_id = str(identity.get("tenant_id") or "").strip() or None
        case_record = _case_record(
            str(context.get("case_id") or ""),
            tenant_id=owner_tenant_id,
        ) or {}
        try:
            get_supabase_client().persist_run(
                run=response.model_dump(mode="json"),
                tenant_id=owner_tenant_id,
                case_id=str(context.get("case_id") or ""),
                case_tenant_id=str(case_record.get("tenant_id") or "").strip() or None,
                pipeline_task_id=str(context.get("pipeline_task_id") or "").strip() or None,
            )
            response.context["persistence"] = {"backend": "supabase", "status": "persisted"}
        except SupabaseError:
            # 已落地的本地运行记录仍保留，但结果明确标成公网持久化不完整，不能冒充可恢复成功。
            response.context["persistence"] = {
                "backend": "supabase",
                "status": "unavailable",
                "boundary": "本次本地结果已保留；公网 Postgres 未确认写入，禁止作为跨实例完成记录。",
            }
            response.run_completeness = "incomplete_persistence_unavailable"
            save_run(WORKSPACE_ROOT, response)
    return response


@app.get("/", include_in_schema=False)
def serve_main_page() -> FileResponse:
    return FileResponse(WORKSPACE_ROOT / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    api_key, _, model_id = _model_settings()
    return HealthResponse(
        service_status="ready",
        model_status="configured" if api_key else "config_missing",
        model_id=model_id,
        source_snapshot_id=SOURCE_SNAPSHOT_ID,
        detail="服务可用；模型配置状态不等于已经完成真实三Agent运行。",
    )


@app.get("/api/status")
def project_status(http_request: Request) -> dict[str, Any]:
    status_path = WORKSPACE_ROOT / "PROJECT_STATUS.json"
    if status_path.is_file():
        try:
            registered = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            registered = {"status_file": "invalid"}
    else:
        registered = {"status_file": "missing"}
    identity, cases, catalog_state = _visible_case_records(http_request)
    rag_cases = [rag_status(WORKSPACE_ROOT, case["case_id"]) for case in cases]
    api_key, _, model_id = _model_settings()
    return _with_ai_notice({
        **registered,
        "engine_version": ENGINE_VERSION,
        "run_schema_version": RUN_SCHEMA_VERSION,
        "case_count": len(cases),
        "cases": [
                {
                    "case_id": case["case_id"],
                    "company_name": case.get("company_name", ""),
                    "available_years": case.get("available_years", []),
                    "source_count": len(case.get("documents", [])),
                    "model_transfer_allowed": bool(case.get("model_transfer_allowed")),
            }
            for case in cases
        ],
        "rag": {
            "ready_cases": sum(1 for item in rag_cases if item.get("status") == "ready"),
            "chunk_count": sum(int(item.get("chunk_count", 0)) for item in rag_cases),
            "cases": rag_cases,
        },
        "model": {
            "status": "configured" if api_key else "config_missing",
            "model_id": model_id,
            "boundary": "配置存在不代表真实完整运行已经验收。",
        },
        "persistence": configured_persistence(),
        "catalog": {**catalog_state, "seed": seed_catalog_summary(WORKSPACE_ROOT)},
        "auth": {
            "authenticated": bool(identity and not identity.is_local),
            "tenant_id": identity.tenant_id if identity and not identity.is_local else None,
        },
    })


@app.get("/api/cases")
def get_cases(http_request: Request) -> dict[str, Any]:
    identity, visible_cases, catalog_state = _visible_case_records(http_request)
    return _with_ai_notice({
        "schema_version": "case_list_v1",
        "cases": [_public_case(case) for case in visible_cases],
        "catalog": {**catalog_state, "seed": seed_catalog_summary(WORKSPACE_ROOT)},
        "auth": {
            "authenticated": identity is not None and not identity.is_local,
            "tenant_id": identity.tenant_id if identity and not identity.is_local else None,
        },
        "boundary": "公开案例可匿名读取；内部案例只展示给所属租户成员。来源快照变化后仍须重新核验。",
    })


@app.get("/api/auth/me")
def auth_me(http_request: Request) -> dict[str, Any]:
    """前端读取登录状态；匿名公开模式不把未登录误报为系统故障。"""

    identity = optional_authenticated(http_request)
    return _with_ai_notice(
        {
            "authenticated": bool(identity and not identity.is_local),
            "persistence": configured_persistence(),
            "user": identity.as_public_dict() if identity and not identity.is_local else None,
            "boundary": "登录状态只决定内部租户资料和模型调用权限，不改变公开年报的来源证据。",
        }
    )


@app.post("/api/auth/login")
def auth_login(credentials: AuthLoginRequest, http_response: Response) -> dict[str, Any]:
    """建立同源 Supabase 会话；密码和令牌均不写日志、不进入响应正文。"""

    if not supabase_enabled():
        raise HTTPException(status_code=409, detail="本地竞赛模式不使用公网登录会话。")
    try:
        session = get_supabase_client().sign_in_with_password(
            email=credentials.email,
            password=credentials.password.get_secret_value(),
        )
        payload = _authenticated_session_payload(session)
    except SupabaseAuthError as error:
        raise HTTPException(status_code=401, detail="邮箱或密码无效。") from error
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="身份服务暂时不可用，请稍后重试。") from error
    _set_session_cookies(http_response, session)
    return payload


@app.post("/api/auth/refresh")
def auth_refresh(http_request: Request, http_response: Response) -> Any:
    """轮换 HttpOnly 会话；刷新令牌只从 Cookie 读取，不能由 JSON 参数注入。"""

    if not supabase_enabled():
        raise HTTPException(status_code=409, detail="本地竞赛模式不使用公网登录会话。")
    refresh_token = str(http_request.cookies.get(REFRESH_COOKIE_NAME) or "").strip()
    if not refresh_token:
        raise HTTPException(status_code=401, detail="刷新会话不存在，请重新登录。")
    try:
        session = get_supabase_client().refresh_session(refresh_token=refresh_token)
        payload = _authenticated_session_payload(session)
    except SupabaseAuthError:
        # 直接返回同一个 JSONResponse，确保两个删除 Cookie 的 Set-Cookie 头不会被异常处理器丢弃。
        rejected = JSONResponse(
            status_code=401,
            content=_with_ai_notice({"detail": "刷新会话无效或已过期，请重新登录。"}),
        )
        _clear_session_cookies(rejected)
        return rejected
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="身份服务暂时不可用，请稍后重试。") from error
    _set_session_cookies(http_response, session)
    return payload


@app.post("/api/auth/logout")
def auth_logout(http_response: Response) -> dict[str, Any]:
    """清理同源 Cookie；服务端响应不回显被清除的任何令牌。"""

    if not supabase_enabled():
        raise HTTPException(status_code=409, detail="本地竞赛模式没有公网登录会话。")
    _clear_session_cookies(http_response)
    return _with_ai_notice({"authenticated": False, "user": None, "status": "logged_out"})


@app.get("/api/cases/template")
def download_case_template() -> Response:
    content = build_case_template_zip()
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="audittrace_case_template_v1.zip"'},
    )


@app.post("/api/cases/import", status_code=201)
async def import_case(
    http_request: Request,
    file: UploadFile = File(...),
    authorized: bool = Form(...),
    desensitized: bool = Form(...),
) -> dict[str, Any]:
    # 内部文件上传在两种模式都保留明确身份：本地是离线竞赛操作员，公网是 Supabase 成员。
    identity = require_authenticated(http_request)
    content = await file.read()
    try:
        case = import_case_zip(
            WORKSPACE_ROOT,
            content,
            authorized=authorized,
            desensitized=desensitized,
            tenant_id=identity.tenant_id if identity and not identity.is_local else None,
            owner_user_id=identity.user_id if identity and not identity.is_local else None,
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    _persist_case_remote(case, rows=case.get("structured_evidence", []), upload_private_documents=bool(identity and not identity.is_local))
    return _with_ai_notice({
        "status": "imported_pending_human_confirmation",
        "case": _public_case(case),
        "boundary": "系统未从PDF自动取数，也未把该案例认定为正式竞赛样例。",
    })


@app.get("/api/cases/{case_id}")
def get_case_detail(case_id: str, http_request: Request) -> dict[str, Any]:
    normalized = case_id.upper()
    tenant_id = _identity_tenant(http_request)
    case = _case_record(normalized, tenant_id=tenant_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    authorize_case_access(http_request, case)
    local_rows = _materialized_financial_rows(case, tenant_id=tenant_id)
    rows = [
        _public_source(row, private=not is_public_case(case))
        for row in (local_rows if local_rows is not None else case.get("financial_fields", []))
    ]
    evidence_confirmed = case.get("evidence_owner_review_status") == "owner_confirmed"
    return _with_ai_notice({
        **_public_case(case),
        "financial_fields": rows,
        "field_validation": {
            "status": case.get("financial_fields_status", "passed_import_or_registry_validation"),
            "field_count": len(rows),
            "years": sorted({row["year"] for row in rows}, reverse=True),
            "human_confirmed_available_years": case.get("human_confirmed_available_years", []),
            "boundary": (
                "当前来源快照的字段、页码、披露日期与哈希已由项目所有者核验。"
                if evidence_confirmed
                else "字段已通过结构和来源登记校验；金额口径与专业含义仍待人工复核。"
            ),
        },
    })


@app.post("/api/cases/{case_id}/fields/confirm")
def confirm_case_field(case_id: str, confirmation: CNInfoFieldConfirmation, http_request: Request) -> dict[str, Any]:
    """保存巨潮字段候选的真人确认、修正或拒绝，并返回最新闸门状态。"""

    normalized = case_id.upper()
    identity = require_authenticated(http_request) if supabase_enabled() else optional_authenticated(http_request)
    case_before = _case_record(
        normalized,
        tenant_id=str(identity.tenant_id or "") or None if identity and not identity.is_local else None,
    )
    if case_before is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    identity = authorize_case_write(http_request, case_before)
    # 公网字段复核必须写带 tenant/case_scope 的 Postgres 行；无 scope 的本机
    # 同名案例既不能作为授权依据，也不能接收租户私有复核。
    local_case = get_case(WORKSPACE_ROOT, normalized) if not supabase_enabled() else None
    public_overlay = bool(
        supabase_enabled()
        and is_public_case(case_before)
        and case_before.get("registry_mode") == "cninfo_official_auto"
    )
    if public_overlay:
        try:
            remote_case = get_supabase_client().get_case_bundle(
                normalized,
                tenant_id=str(identity.tenant_id or "") or None,
            )
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网字段复核服务暂时不可用。") from error
        if remote_case is None:
            raise HTTPException(status_code=409, detail="公开字段尚未完成公网发布，不能保存租户复核。")
        case_before = remote_case
    if local_case is not None and not public_overlay:
        try:
            result = confirm_cninfo_field(
                WORKSPACE_ROOT,
                normalized,
                confirmation.model_dump(mode="json"),
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        case = result["case"]
        raw_rows = get_financial_rows(WORKSPACE_ROOT, normalized)
    else:
        # 新 web 实例没有 worker 的案例目录时，直接更新 Postgres field_evidence 元数据与历史。
        try:
            remote_result = get_supabase_client().update_case_field_review(
                case=case_before,
                confirmation=confirmation.model_dump(mode="json"),
                tenant_id=str(identity.tenant_id or ""),
                reviewer_user_id=identity.user_id,
            )
        except SupabaseConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网字段复核服务暂时不可用。") from error
        case = deepcopy(case_before)
        raw_rows = remote_result["rows"]
        _recompute_cninfo_human_status(case, raw_rows)
        case["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        current_year = max(case.get("available_years") or [int(row.get("year") or 0) for row in raw_rows] or [0])
        result = {
            "case": case,
            "field": remote_result["field"],
            "readiness": _remote_cninfo_field_readiness(raw_rows, ["R1", "R2"], current_year),
        }
    if supabase_enabled() and str(case.get("tenant_id") or "").strip():
        # 案例闸门和字段历史同步回 Postgres；不重写已登记文档的 Storage 路径。
        remote_case = deepcopy(case)
        remote_case["documents"] = []
        _persist_case_remote(remote_case, rows=raw_rows)
    rows = [_public_source(row, private=not is_public_case(case_before)) for row in raw_rows]
    return _with_ai_notice(
        {
            "status": "field_review_saved",
            "case": _public_case(case),
            "field": _public_source(result["field"], private=not is_public_case(case)),
            "financial_fields": rows,
            "field_validation": {
                "status": case.get("financial_fields_status"),
                "field_count": len(rows),
                "human_confirmed_available_years": case.get("human_confirmed_available_years", []),
                "boundary": "真人确认记录已追加保存；仍不等于专业签字或审计结论。",
            },
            "readiness": result["readiness"],
        }
    )


@app.get("/api/cases/{case_id}/sources/{document_id}")
def open_case_source(case_id: str, document_id: str, http_request: Request) -> Response:
    normalized_case_id = case_id.upper()
    normalized_document_id = document_id.upper()
    tenant_id = _identity_tenant(http_request)
    case = _case_record(normalized_case_id, tenant_id=tenant_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    authorize_case_access(http_request, case)
    if supabase_enabled() and not is_public_case(case):
        registered_document = next(
            (
                item
                for item in case.get("documents", [])
                if str(item.get("document_id") or "").upper() == normalized_document_id
            ),
            None,
        )
        if registered_document is None:
            raise HTTPException(status_code=404, detail="来源文档未登记。")
        try:
            # 只接受数据库登记的内容寻址路径，并再次验证租户/案例固定前缀。
            signed_path = str(registered_document.get("storage_object_path") or "")
            expected_prefix = f"{case['tenant_id']}/{normalized_case_id}/{normalized_document_id}-"
            if not signed_path.startswith(expected_prefix) or not signed_path.endswith(".pdf"):
                raise HTTPException(status_code=404, detail="私有来源对象登记无效。")
            signed_url = get_supabase_client().create_signed_url(
                bucket=os.getenv("SUPABASE_PRIVATE_BUCKET", "audittrace-private"),
                object_path=signed_path,
            )
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="私有年报暂时无法生成短时访问链接。") from error
        return RedirectResponse(signed_url, status_code=307)
    if normalized_case_id == CASE_ID and _public_demo_enabled():
        source_url = _registered_standard_source_url(normalized_document_id)
        if source_url:
            return RedirectResponse(source_url, status_code=307)
    local_case = _materialized_case_for_resolved(case, tenant_id=tenant_id)
    local_tenant = (
        str(local_case.get("tenant_id") or "").strip() or None
        if local_case is not None and supabase_enabled()
        else None
    )
    resolved = (
        resolve_case_document(
            WORKSPACE_ROOT,
            normalized_case_id,
            normalized_document_id,
            tenant_id=local_tenant,
        )
        if local_case is not None
        else None
    )
    if resolved is None:
        remote_document = next(
            (item for item in case.get("documents", []) if str(item.get("document_id") or "").upper() == normalized_document_id),
            None,
        )
        remote_url = str((remote_document or {}).get("source_url") or "")
        if is_public_case(case) and remote_url.startswith("https://static.cninfo.com.cn/finalpage/"):
            return RedirectResponse(remote_url, status_code=307)
        if normalized_case_id == CASE_ID:
            source_url = _registered_standard_source_url(normalized_document_id)
            if source_url:
                return RedirectResponse(source_url, status_code=307)
        raise HTTPException(status_code=404, detail="来源文档未登记或文件不存在。")
    path, document = resolved
    return FileResponse(path, media_type="application/pdf", filename=document["source_file"])


def _consent_public_payload(consent: dict[str, Any] | None, *, required: bool, status: str) -> dict[str, Any]:
    contract = model_consent_contract()
    return {
        "required": required,
        "active": bool(consent and not consent.get("revoked_at")),
        "status": status,
        "consent": {
            key: consent.get(key)
            for key in ("id", "provider", "model_id", "transmission_scope", "purpose", "valid_until", "revoked_at", "created_at")
            if consent and consent.get(key) is not None
        },
        # 前端展示和提交都从这一服务端合同取值，避免中文文案或环境模型变化
        # 造成按钮点击后 422；真正授权仍只按数据库中的规范化合同判断。
        "contract": contract,
        "minimum_scope": contract["transmission_scope"],
        "boundary": "同意只针对当前案例和有效期；不上传整本 PDF，不改变人工复核与正式结论闸门。",
    }


@app.get("/api/cases/{case_id}/model-consent")
def get_model_consent(case_id: str, http_request: Request) -> dict[str, Any]:
    case = _case_record(case_id.upper(), tenant_id=_identity_tenant(http_request))
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    identity = authorize_case_access(http_request, case)
    if not supabase_enabled():
        return _with_ai_notice(
            _consent_public_payload(
                None,
                required=False,
                status="local_manifest_permission" if case.get("model_transfer_allowed") else "local_model_transfer_disabled",
            )
        )
    if identity is None or identity.is_local:
        return _with_ai_notice(_consent_public_payload(None, required=True, status="login_required"))
    contract = model_consent_contract()
    try:
        consent = get_supabase_client().get_active_model_transfer_consent(
            tenant_id=str(identity.tenant_id),
            case_id=case["case_id"],
            case_tenant_id=str(case.get("tenant_id") or "").strip() or None,
            user_id=identity.user_id,
            provider=contract["provider"],
            model_id=contract["model_id"],
            transmission_scope=contract["transmission_scope"],
        )
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="模型传输同意状态暂时不可用。") from error
    return _with_ai_notice(_consent_public_payload(consent, required=True, status="active" if consent else "not_granted"))


@app.post("/api/cases/{case_id}/model-consent")
def create_model_consent(
    case_id: str,
    consent_request: ModelTransferConsentRequest,
    http_request: Request,
) -> dict[str, Any]:
    identity = require_authenticated(http_request)
    case = _case_record(case_id.upper(), tenant_id=str(identity.tenant_id or "") or None)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    authorize_case_access(http_request, case)
    if not supabase_enabled() or identity.is_local or not identity.tenant_id:
        raise HTTPException(status_code=409, detail="本地竞赛模式沿用案例 manifest 许可；逐案 Supabase 同意仅在公网模式启用。")
    if not consent_request.confirmed:
        raise HTTPException(status_code=422, detail="必须明确 confirmed=true 才能保存模型传输同意。")
    contract = model_consent_contract()
    # 兼容已经发布的前端占位文案，但这些客户端字段从不进入授权行；服务端始终
    # 绑定当前 hostname/model/canonical scope。非占位的矛盾具体值则失败关闭。
    legacy_values = {
        "provider": {"当前服务端已配置供应商"},
        "model_id": {"configured-model"},
        "transmission_scope": {"仅传输字段证据、来源元数据与 RAG 命中原文片段。"},
    }
    submitted = {
        "provider": consent_request.provider.strip(),
        "model_id": consent_request.model_id.strip(),
        "transmission_scope": consent_request.transmission_scope.strip(),
    }
    matches_contract = all(
        value == contract[key] or value in legacy_values[key]
        for key, value in submitted.items()
    )
    if not matches_contract:
        raise HTTPException(status_code=422, detail="模型同意必须精确匹配服务端当前供应商、模型与最小传输范围。")
    client = get_supabase_client()
    created: dict[str, Any] | None = None
    try:
        created = client.create_model_transfer_consent(
            tenant_id=identity.tenant_id,
            case_id=case["case_id"],
            case_tenant_id=str(case.get("tenant_id") or "").strip() or None,
            user_id=identity.user_id,
            provider=contract["provider"],
            model_id=contract["model_id"],
            transmission_scope=contract["transmission_scope"],
            purpose=consent_request.purpose.strip(),
            valid_until=consent_request.valid_until,
        )
        client.record_audit_event(
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            event_type="model_transfer_consent_created",
            case_id=case["case_id"],
            metadata={"consent_id": created.get("id"), "provider": created.get("provider"), "model_id": created.get("model_id")},
        )
    except SupabaseError as error:
        if created and created.get("id"):
            try:
                client.revoke_model_transfer_consent(consent_id=str(created["id"]), tenant_id=identity.tenant_id, user_id=identity.user_id)
            except SupabaseError:
                pass
        raise HTTPException(status_code=503, detail="模型传输同意或审计记录未完成保存。") from error
    return _with_ai_notice(_consent_public_payload(created, required=True, status="active"))


@app.post("/api/model-consents/{consent_id}/revoke")
def revoke_model_consent(consent_id: str, http_request: Request) -> dict[str, Any]:
    identity = require_authenticated(http_request)
    if not supabase_enabled() or identity.is_local or not identity.tenant_id:
        raise HTTPException(status_code=409, detail="本地竞赛模式没有独立的 Supabase 同意记录。")
    try:
        consent_uuid = uuid.UUID(consent_id)
    except (ValueError, AttributeError) as error:
        raise HTTPException(status_code=404, detail="未找到模型传输同意记录。") from error
    client = get_supabase_client()
    try:
        consent = client.get_model_transfer_consent(str(consent_uuid))
        if not consent or consent.get("tenant_id") != identity.tenant_id or consent.get("user_id") != identity.user_id:
            raise HTTPException(status_code=404, detail="未找到模型传输同意记录。")
        client.revoke_model_transfer_consent(
            consent_id=str(consent_uuid),
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
        )
        client.record_audit_event(
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            event_type="model_transfer_consent_revoked",
            case_id=str(consent.get("case_id") or ""),
            metadata={"consent_id": str(consent_uuid)},
        )
    except HTTPException:
        raise
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="模型传输同意撤销或审计记录未完成。") from error
    return _with_ai_notice({"status": "revoked", "consent_id": str(consent_uuid), "active": False, "boundary": "撤销后后续模型调用立即重新检查并被禁止。"})


@app.post("/api/runs", response_model=RunResponse)
def run_rules(request: RunRequest, http_request: Request) -> RunResponse:
    _ensure_public_standard_sources(request.case_id)
    tenant_id = _identity_tenant(http_request)
    case = _case_record(request.case_id, tenant_id=tenant_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    authorize_case_access(http_request, case)
    company = {
        key: case.get(key)
        for key in ("ticker", "company_name", "company_alias", "org_id", "market", "source_mode")
        if case.get(key) is not None
    }
    gate = evaluate_industry_gate(company=company, case=case, rule_ids=request.rule_ids)
    # 金融行业等不适用普通规则不要求先伪造一组 R1 字段；有专用规则时
    # 仍然加载其真实字段，普通 R1/R2 只作为兼容外壳保留。
    if gate.get("specialized_rule"):
        try:
            context, sources = _industry_period_sources(
                case,
                current_year=request.current_year,
                gate=gate,
                tenant_id=tenant_id,
            )
        except KeyError as error:
            raise HTTPException(status_code=422, detail="当前案例没有可读取的行业专用字段。") from error
    elif gate["fit_level"] in {"not_applicable", "unknown"}:
        context = build_not_applicable_context(
            case=case,
            current_year=request.current_year,
            rule_ids=request.rule_ids,
            gate=gate,
        )
        sources = []
    else:
        # 公开财报预筛不把逐字段人工确认作为前置门槛；正式缓存和报告导出仍由 delivery 层要求真人复核。
        try:
            local_rows = _materialized_financial_rows(case, tenant_id=tenant_id)
            if local_rows is not None and (not supabase_enabled() or is_public_case(case)):
                context, sources = get_period_sources(
                    WORKSPACE_ROOT,
                    request.case_id,
                    request.current_year,
                    tuple(request.rule_ids),
                )
            elif local_rows is not None:
                # 租户隔离临时副本不能通过无 scope 的 get_period_sources 读取；
                # 注入精确目录字段后复用纯内存构造器，杜绝同名全局案例串入。
                scoped_case = deepcopy(case)
                scoped_case["financial_fields"] = local_rows
                context, sources = _remote_period_sources(
                    scoped_case,
                    request.current_year,
                    list(request.rule_ids),
                )
            else:
                context, sources = _remote_period_sources(
                    case,
                    request.current_year,
                    list(request.rule_ids),
                )
        except KeyError as error:
            raise HTTPException(status_code=422, detail="当前案例没有该年度所需的连续字段。") from error
        context["industry_gate"] = gate
    context["private_case"] = not is_public_case(case)
    # 外部模型调用在公网模式必须有真实登录身份；匿名用户仍可完成公开确定性预筛，
    # 但不会把项目级许可误当作用户级模型授权。
    original_model_transfer_allowed = bool(context.get("model_transfer_allowed"))
    model_authorized = authorize_model_transfer(http_request, case) if supabase_enabled() else original_model_transfer_allowed
    model_recheck: Callable[[str], bool] | None = None
    if not model_authorized:
        context["model_transfer_allowed"] = False
        context["model_transfer_auth_required"] = True
        context["model_transfer_block_reason"] = (
            "公网模型调用需要当前案例有效同意；匿名公开预筛不上传证据片段。"
            if supabase_enabled()
            else "案例 manifest 未允许外部模型传输，只完成本地确定性预检。"
        )
    elif supabase_enabled():
        context["model_transfer_allowed"] = True
        context["model_transfer_scope"] = model_transmission_scope()

        def _recheck_model_consent(_role: str) -> bool:
            try:
                if not _worker_lease_is_current(http_request):
                    return False
                return authorize_model_transfer(http_request, case)
            except HTTPException:
                # 外部模型默认拒绝；同意状态服务暂不可用时也不能继续发出后续请求。
                return False

        model_recheck = _recheck_model_consent
    identity = request_identity(http_request)
    if identity:
        context["request_identity"] = identity.as_public_dict()
    return _execute_run(
        context=context,
        sources=sources,
        rule_ids=list(request.rule_ids),
        run_mode=request.run_mode,
        r2_min_gap=request.r2_min_gap,
        planned_materiality=request.planned_materiality,
        r1_gap_threshold=request.r1_gap_threshold,
        r1_strong_gap_threshold=request.r1_strong_gap_threshold,
        r1_absolute_threshold=request.r1_absolute_threshold,
        http_request=http_request,
        run_prefix="RUN-V7",
        supplement_evidence=case.get("structured_evidence", []),
        model_recheck=model_recheck,
    )


def _execute_cninfo_task(task_id: str, payload: dict[str, Any], http_request: Request) -> None:
    """后台执行巨潮导入；完整分析仍复用现有 /api/runs 主链和保存逻辑。"""

    job_id = payload.get("cache_job_id")
    if job_id:
        update_refresh_job(WORKSPACE_ROOT, str(job_id), status="running", reason={"message": "任务正在执行。"})
    # 后台任务先独立完成来源与 RAG，再决定是否进入已有规则分析入口。
    # 这样公开数据导入失败时不会生成一条内容不完整的分析运行记录。
    result = run_ingestion(WORKSPACE_ROOT, task_id)
    if result.get("status") != "ready_for_analysis":
        if job_id:
            error = result.get("error") or {}
            completed_rag = result.get("status") == "rag_ready"
            update_refresh_job(
                WORKSPACE_ROOT,
                str(job_id),
                status="completed" if completed_rag else str(result.get("status") or "failed"),
                reason={
                    "message": "RAG预热完成。" if completed_rag else error.get("message") or "公开年报任务未形成可分析结果。",
                    "error_code": error.get("code"),
                    "result_status": result.get("status"),
                    "industry_fit_level": (result.get("industry_gate") or {}).get("fit_level"),
                    "field_extraction_status": (result.get("field_extraction") or {}).get("status"),
                    "field_gap_count": len((result.get("field_extraction") or {}).get("issues") or []),
                },
            )
        return
    # 来源/RAG 阶段可能持续数十秒；进入分析与模型前必须使用当前 token
    # 再做一次同步 RPC，而不是只相信后台心跳线程稍早的结果。
    _require_worker_lease(http_request)
    task = load_task(WORKSPACE_ROOT, task_id)
    case_id = str((task or {}).get("case_id") or result.get("case_id") or "")
    case = get_case(WORKSPACE_ROOT, case_id)
    if case is None:
        mark_analysis_failure(
            WORKSPACE_ROOT,
            task_id,
            ValueError("巨潮案例登记后不存在可读取的案例记录。"),
        )
        return
    try:
        # 当前分析统一走 run_rules，保证规则、日志和模型开关只有一套实现。
        from .pipeline import _set_status, _set_step  # 局部导入避免把状态机 API 暴露到常规路由。

        current_year = max(case.get("available_years") or case.get("available_report_years") or [0])
        _set_status(WORKSPACE_ROOT, task or {}, "analyzing")
        if task is not None:
            _set_step(WORKSPACE_ROOT, task, "analysis_run", "running", "正在调用现有 /api/runs 分析主链。")
        run_request = RunRequest(
            case_id=case_id,
            current_year=current_year,
            rule_ids=list(payload.get("rule_ids") or ["R1"]),
            run_mode="full_analysis",
            planned_materiality=payload.get("planned_materiality"),
        )
        _require_worker_lease(http_request)
        run_response = run_rules(run_request, http_request)
        _require_worker_lease(http_request)
        update_analysis_result(WORKSPACE_ROOT, task_id, run_response.model_dump(mode="json"))
        if job_id:
            summary = {
                "message": "预热任务完成。",
                "result_status": run_response.status,
                "industry_fit_level": (run_response.context.get("industry_gate") or {}).get("fit_level"),
                "field_extraction_status": (result.get("field_extraction") or {}).get("status"),
                "field_gap_count": len((result.get("field_extraction") or {}).get("issues") or [])
                + len((run_response.context.get("prescreen_summary") or {}).get("missing_fields") or []),
                "run_id": run_response.run_id,
            }
            update_refresh_job(WORKSPACE_ROOT, str(job_id), status="completed", reason=summary)
    except SupabaseLeaseLost:
        # 失租由 worker 外层接管；这里不能把旧执行者标成普通业务失败或继续写刷新作业。
        raise
    except Exception as error:
        mark_analysis_failure(WORKSPACE_ROOT, task_id, error)
        if job_id:
            update_refresh_job(
                WORKSPACE_ROOT,
                str(job_id),
                status="failed",
                reason={"message": f"分析阶段失败：{type(error).__name__}。", "error_code": "ANALYSIS_FAILED"},
            )


def _execute_cninfo_batch(
    task_specs: list[tuple[str, dict[str, Any]]],
    http_request: Request,
) -> None:
    """Run a prewarm batch with bounded concurrency and per-company isolation."""

    if not task_specs:
        return
    # Two workers keep CNINFO traffic bounded while preventing one large PDF from
    # serially blocking every other company in the administrator's batch.
    max_workers = min(2, len(task_specs))
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cninfo-prewarm") as executor:
        futures = {
            executor.submit(_execute_cninfo_task, task_id, payload, http_request): (task_id, payload)
            for task_id, payload in task_specs
        }
        for future in as_completed(futures):
            task_id, payload = futures[future]
            try:
                future.result()
            except Exception as error:
                # A worker-level exception must close only its own job; other
                # companies continue and the batch report remains truthful.
                mark_analysis_failure(WORKSPACE_ROOT, task_id, error)
                if payload.get("cache_job_id"):
                    update_refresh_job(
                        WORKSPACE_ROOT,
                        str(payload["cache_job_id"]),
                        status="failed",
                        reason={"message": f"后台任务异常：{type(error).__name__}。", "error_code": "WORKER_FAILED"},
                    )


@app.post("/api/pipelines/cninfo", status_code=202)
def create_cninfo_pipeline(
    request: CNInfoPipelineRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> dict[str, Any]:
    """输入企业后创建巨潮年报、校验、RAG和可选完整分析任务。"""

    # 公网下载、解析和建库会消耗网络、CPU 与存储，必须绑定真实任务所有者；本地竞赛行为不变。
    require_authenticated(http_request) if supabase_enabled() else optional_authenticated(http_request)
    # 接口只负责排队并返回任务编号，进度通过 GET 接口读取，适合长 PDF 下载。
    task = create_task(WORKSPACE_ROOT, request.model_dump(mode="json"))
    _queue_pipeline_task(background_tasks, task, task["request"], http_request)
    return _with_ai_notice(
        {
            "task_id": task["task_id"],
            "status": task["status"],
            "steps": task["steps"],
            "boundary": "任务只访问巨潮公开来源；失败、待人工和模型传输关闭状态不会伪装成完成。",
        }
    )


@app.get("/api/pipelines/{task_id}")
def get_cninfo_pipeline(task_id: str, http_request: Request) -> dict[str, Any]:
    """读取巨潮任务进度和每一步证据。"""

    task = _read_pipeline_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到巨潮导入任务。")
    authorize_pipeline_task(http_request, task)
    return _with_ai_notice(_public_pipeline_task(task))


@app.get("/api/pipelines/{task_id}/result")
def get_cninfo_pipeline_result(task_id: str, http_request: Request) -> dict[str, Any]:
    """读取已形成的 RAG 或完整分析结果；未完成时明确返回冲突状态。"""

    task = _read_pipeline_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到巨潮导入任务。")
    authorize_pipeline_task(http_request, task)
    # 没有结果时用 409 区分“尚未完成”和“任务不存在”。
    if task.get("result") is None:
        raise HTTPException(status_code=409, detail="巨潮导入任务尚未形成结果。")
    return _with_ai_notice(task["result"])


@app.post("/api/pipelines/{task_id}/retry", status_code=202)
def retry_cninfo_pipeline(task_id: str, background_tasks: BackgroundTasks, http_request: Request) -> dict[str, Any]:
    """保留上一轮日志后重试失败或待人工任务。"""

    # 先从 Postgres 读取并完成对象级授权，不能在确认所有者前改写本地任务文件。
    current = _read_pipeline_task(task_id)
    if current is None:
        raise HTTPException(status_code=404, detail="未找到巨潮导入任务。")
    authorize_pipeline_task(http_request, current)
    expected_status = str((current.get("persistence") or {}).get("queue_status") or current.get("status") or "")
    expected_attempt = int(current.get("attempt") or 0)
    allowed_statuses = {"failed"} if supabase_enabled() else {"failed", "needs_human"}
    if expected_status not in allowed_statuses:
        # running/queued 由租约状态机管理，completed 是不可逆终态；旧标签页不能
        # 通过 retry 把任一状态清回 queued，也不能绕开 attempt CAS。
        raise HTTPException(status_code=409, detail="只有失败或待人工任务可以重试；运行中和已完成任务不可重排。")
    if load_task(WORKSPACE_ROOT, task_id) is None:
        _save_task(WORKSPACE_ROOT, current)
    # 重试会保留 history，便于评审时查看原始失败点和人工决定。
    try:
        task = queue_retry(WORKSPACE_ROOT, task_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    _queue_pipeline_task(
        background_tasks,
        task,
        task["request"],
        http_request,
        requeue=True,
        expected_status=expected_status,
        expected_attempt=expected_attempt,
    )
    return _with_ai_notice({"task_id": task_id, "status": "queued", "attempt": task["attempt"] + 1})


@app.post("/api/pipelines/{task_id}/confirm-company", status_code=202)
def confirm_cninfo_company(
    task_id: str,
    confirmation: CNInfoCompanyConfirmation,
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> dict[str, Any]:
    """只接受上一轮巨潮返回的同名候选股票代码。"""

    # 企业确认不是自由输入：只能选择本次搜索返回的候选代码。
    task = _read_pipeline_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到巨潮导入任务。")
    authorize_pipeline_task(http_request, task)
    expected_status = str((task.get("persistence") or {}).get("queue_status") or task.get("status") or "")
    expected_attempt = int(task.get("attempt") or 0)
    if (supabase_enabled() and expected_status != "failed") or (
        not supabase_enabled() and task.get("status") != "needs_human"
    ):
        raise HTTPException(status_code=409, detail="企业确认只接受待人工的失败任务；运行中和已完成任务不可重排。")
    error_code = str((task.get("error") or {}).get("code") or "")
    if error_code not in {"COMPANY_AMBIGUOUS", "CNINFO_COMPANY_AMBIGUOUS"}:
        raise HTTPException(status_code=409, detail="当前任务不是等待企业候选确认状态。")
    if load_task(WORKSPACE_ROOT, task_id) is None:
        _save_task(WORKSPACE_ROOT, task)
    candidates = ((task.get("error") or {}).get("detail") or {}).get("candidates") or []
    candidate_codes = {str(item.get("ticker")) for item in candidates if isinstance(item, dict)}
    if confirmation.ticker not in candidate_codes:
        raise HTTPException(status_code=422, detail="股票代码不在本次巨潮候选列表中。")
    try:
        queued = queue_retry(WORKSPACE_ROOT, task_id, request_update={"company_query": confirmation.ticker})
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    _queue_pipeline_task(
        background_tasks,
        queued,
        queued["request"],
        http_request,
        requeue=True,
        expected_status=expected_status,
        expected_attempt=expected_attempt,
    )
    return _with_ai_notice({"task_id": task_id, "status": "queued", "confirmed_ticker": confirmation.ticker})


@app.get("/api/runs/{run_id}", response_model=StoredRunResponse)
def get_run(run_id: str, http_request: Request) -> StoredRunResponse:
    owner_tenant_id = _identity_tenant(http_request)
    record = _load_stored_run_record(run_id, owner_tenant_id=owner_tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
    stored, run_owner_tenant = record
    case = _remote_case_for_run(
        str(stored.run.context.get("case_id") or ""),
        tenant_id=run_owner_tenant,
    )
    if case is None:
        raise HTTPException(status_code=404, detail="运行对应案例不存在。")
    authorize_case_access(http_request, case)
    return stored


@app.post("/api/runs/{run_id}/review", response_model=StoredRunResponse)
def review_run(run_id: str, review: HumanReviewRequest, http_request: Request) -> StoredRunResponse:
    owner_tenant_id = _identity_tenant(http_request, required=supabase_enabled())
    record = _load_stored_run_record(run_id, owner_tenant_id=owner_tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
    stored_before, run_owner_tenant = record
    case = _case_record(str(stored_before.run.context.get("case_id") or ""), tenant_id=run_owner_tenant)
    if case is None:
        raise HTTPException(status_code=404, detail="运行对应案例不存在。")
    authorize_case_write(http_request, case)
    if load_run(WORKSPACE_ROOT, run_id) is None:
        # 本地 materialize 仅为复用原子化人工复核写入；权威副本随后同步回 Postgres。
        save_run(WORKSPACE_ROOT, stored_before.run)
    stored = save_human_review(WORKSPACE_ROOT, run_id, review)
    if stored is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
    _persist_stored_run_remote(stored, case, owner_tenant_id=run_owner_tenant)
    return stored


@app.post("/api/runs/{run_id}/cache")
def create_run_cache(run_id: str, http_request: Request) -> dict[str, Any]:
    owner_tenant_id = _identity_tenant(http_request, required=supabase_enabled())
    record = _load_stored_run_record(run_id, owner_tenant_id=owner_tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
    stored, run_owner_tenant = record
    case = _case_record(str(stored.run.context.get("case_id") or ""), tenant_id=run_owner_tenant)
    if case is None:
        raise HTTPException(status_code=404, detail="运行对应案例不存在。")
    identity = authorize_case_write(http_request, case)
    try:
        cache_metadata = cache_run(WORKSPACE_ROOT, stored)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if supabase_enabled():
        if identity.is_local or not identity.tenant_id:
            raise HTTPException(status_code=403, detail="公网运行缓存缺少有效租户归属。")
        payload = {**cache_metadata, "stored": stored.model_dump(mode="json")}
        try:
            get_supabase_client().persist_run_cache(
                cache_id=str(cache_metadata["cache_id"]),
                source_run_id=stored.run.run_id,
                case_id=str(stored.run.context.get("case_id") or ""),
                case_tenant_id=str(case.get("tenant_id") or "").strip() or None,
                tenant_id=identity.tenant_id,
                created_by=identity.user_id,
                payload=payload,
            )
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="运行缓存未完成公网持久化。") from error
        cache_metadata["persistence"] = {"backend": "supabase", "cross_instance": True}
    return _with_ai_notice(cache_metadata)


@app.get("/api/cache/status")
def get_catalog_status(company_query: str | None = None) -> dict[str, Any]:
    """读取公开年报热缓存目录，不触发搜索、下载或模型调用。"""

    if supabase_enabled():
        try:
            entries = get_supabase_client().list_public_catalog_entries(company_query=company_query)
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网热缓存目录暂时不可用。") from error
        return _with_ai_notice(
            {
                "schema_version": "catalog_status_v1",
                "bootstrap_synced": 0,
                "count": len(entries),
                "entries": entries,
                "storage_boundary": "公网以 Supabase 全局公开案例和活动 RAG 快照为权威；本机 SQLite 只作开发缓存。",
                "cache_boundary": "缓存命中只代表复用已校验公开来源，不代表最新公告已自动确认；需要最新数据时使用force_refresh。",
            }
        )
    try:
        synced = bootstrap_runtime_catalog(WORKSPACE_ROOT)
        entries = list_cache_entries(WORKSPACE_ROOT, company_query=company_query)
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(status_code=503, detail="热缓存目录暂时不可用。") from error
    return _with_ai_notice(
        {
            "schema_version": "catalog_status_v1",
            "bootstrap_synced": synced,
            "count": len(entries),
            "entries": entries,
            "storage_boundary": "SQLite只保存元数据、结构化字段、证据定位和RAG指纹；PDF与索引仍按案例目录保存。",
            "cache_boundary": "缓存命中只代表复用已校验公开来源，不代表最新公告已自动确认；需要最新数据时使用force_refresh。",
        }
    )


@app.post("/api/cache/resolve")
def resolve_catalog_cache(request: CacheResolveRequest) -> dict[str, Any]:
    """按证券代码或名称查询可直接复用的公开年报快照。"""

    if supabase_enabled():
        years = prepare_report_years(request.latest_year, request.years)
        try:
            entries = get_supabase_client().list_public_catalog_entries(company_query=request.company_query)
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网热缓存目录暂时不可用。") from error
        match = next(
            (
                entry
                for entry in entries
                if entry.get("cache_state") == "ready"
                and set(years).issubset({int(year) for year in entry.get("report_years", [])})
            ),
            None,
        )
        if request.cache_policy == "force_refresh":
            match = None
        return _with_ai_notice(
            {
                "schema_version": "catalog_resolve_v1",
                "company_query": request.company_query,
                "requested_years": years,
                "cache_hit": bool(match),
                "match": match,
                "bootstrap_synced": 0,
                "cache_policy": request.cache_policy,
                "reason": "supabase_public_snapshot_ready" if match else "force_refresh_requested" if request.cache_policy == "force_refresh" else "snapshot_not_found_or_incomplete",
                "stale_match": None,
                "next_step": "直接读取案例字段与RAG并进入规则分析。" if match else "未命中；继续执行巨潮搜索、下载、校验和建库。",
            }
        )
    try:
        synced = bootstrap_runtime_catalog(WORKSPACE_ROOT)
        years = prepare_report_years(request.latest_year, request.years)
        resolution = resolve_analysis_source(
            WORKSPACE_ROOT,
            request.company_query,
            years,
            cache_policy=request.cache_policy,
        )
        match = resolution.get("match")
        resolution_reason = str(resolution.get("reason") or "snapshot_not_found_or_incomplete")
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(status_code=503, detail="热缓存目录暂时不可用。") from error
    return _with_ai_notice(
        {
            "schema_version": "catalog_resolve_v1",
            "company_query": request.company_query,
            "requested_years": years,
            "cache_hit": bool(match),
            "match": match,
            "bootstrap_synced": synced,
            "cache_policy": request.cache_policy,
            "reason": resolution_reason,
            "stale_match": resolution.get("stale_match"),
            "next_step": "直接读取案例字段与RAG并进入规则分析。" if match else "未命中；继续执行巨潮搜索、下载、校验和建库。",
        }
    )


@app.post("/api/cache/prewarm", status_code=202)
def prewarm_catalog(
    request: CachePrewarmRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> dict[str, Any]:
    """为最多 50 家常用企业排队建立公开年报热缓存。"""

    identity = require_authenticated(http_request) if supabase_enabled() else optional_authenticated(http_request)
    idempotency_key = str(http_request.headers.get("idempotency-key") or "").strip()
    if idempotency_key and not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(status_code=422, detail="Idempotency-Key 必须为 8 至 128 位字母、数字或 ._:-。")
    if idempotency_key and identity and not identity.is_local:
        # 批次编号只由服务端已验证 owner 与幂等键决定；同一键换请求时由
        # 数据库比较完整 payload 并冲突，不能静默生成第二批任务。
        batch_suffix = hashlib.sha256(
            f"{identity.tenant_id}:{identity.user_id}:{idempotency_key}".encode("utf-8")
        ).hexdigest()[:12].upper()
    else:
        batch_suffix = uuid.uuid4().hex[:12].upper()
    batch_id = f"CACHE-BATCH-{batch_suffix}"
    requested_years = prepare_report_years(request.latest_year, request.years)
    tasks: list[dict[str, Any]] = []
    cache_policy = "force_refresh" if request.force_refresh else "prefer_cache"
    task_specs: list[tuple[str, dict[str, Any]]] = []
    for index, company_query in enumerate(request.companies, start=1):
        job_id = f"CACHE-JOB-{batch_id[-12:]}-{index:02d}"
        payload = {
            "company_query": company_query,
            "years": request.years,
            "latest_year": request.latest_year,
            "analysis_mode": request.analysis_mode,
            "rule_ids": request.rule_ids,
            "force_refresh": request.force_refresh,
            "cache_policy": cache_policy,
            "planned_materiality": None,
            "cache_batch_id": batch_id,
            "cache_job_id": job_id,
        }
        # task_id 跟随 batch_id 稳定生成；数据库响应丢失后以同一幂等键重试，
        # 仍会命中原任务而不会重复下载或模型执行。
        task_id = "CNINFO-" + hashlib.sha256(
            f"{batch_id}:{index}:{company_query}".encode("utf-8")
        ).hexdigest()[:12].upper()
        task = materialize_task(WORKSPACE_ROOT, task_id, payload, attempt=0)
        create_refresh_job(
            WORKSPACE_ROOT,
            job_id=job_id,
            batch_id=batch_id,
            task_id=task["task_id"],
            ticker=company_query,
            requested_years=requested_years,
        )
        task_specs.append((task["task_id"], payload))
        tasks.append({"task_id": task["task_id"], "company_query": company_query, "status": task["status"]})
    if supabase_enabled():
        if identity is None or identity.is_local or not identity.tenant_id:
            raise HTTPException(status_code=403, detail="公网预热批次缺少有效租户归属。")
        persisted_tasks = [
            {
                "task_id": task_id,
                "job_id": payload["cache_job_id"],
                "ticker": payload["company_query"],
                "requested_years": requested_years,
            }
            for task_id, payload in task_specs
        ]
        try:
            identity_payload = identity_for_task(http_request)
            if isinstance(identity_payload, dict):
                # worker 会用 service-role 成员表重建当前角色；队列快照只保留
                # owner 主键，避免同一幂等请求因 owner/reviewer 角色变化而误冲突。
                identity_payload = {
                    "user_id": identity_payload.get("user_id"),
                    "tenant_id": identity_payload.get("tenant_id"),
                }
            queue_tasks: list[dict[str, Any]] = []
            for task_id, payload in task_specs:
                queue_payload = deepcopy(payload)
                queue_payload["requested_by_identity"] = identity_payload
                local_task = load_task(WORKSPACE_ROOT, task_id)
                if local_task is None:
                    raise SupabaseError("预热任务本地投影缺失。")
                local_task["request"] = deepcopy(queue_payload)
                _save_task(WORKSPACE_ROOT, local_task)
                queue_tasks.append({"task_id": task_id, "request_payload": queue_payload})
            get_supabase_client().enqueue_prewarm_batch(
                batch_id=batch_id,
                tenant_id=identity.tenant_id,
                requested_by=identity.user_id,
                payload={
                    "schema_version": "catalog_prewarm_batch_v1",
                    "batch_id": batch_id,
                    "requested_years": requested_years,
                    "analysis_mode": request.analysis_mode,
                    "tasks": persisted_tasks,
                    "boundary": "批次只保存任务清单与受控状态，不保存外部站点原始错误或文档正文。",
                },
                tasks=queue_tasks,
            )
        except SupabaseConflict as error:
            raise HTTPException(status_code=409, detail="该 Idempotency-Key 已绑定另一份预热请求。") from error
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="预热批次未完成公网持久化。") from error
    else:
        background_tasks.add_task(_execute_cninfo_batch, task_specs, http_request)
    response_payload = {
        "schema_version": "catalog_prewarm_v1",
        "batch_id": batch_id,
        "requested_years": requested_years,
        "queued_count": len(tasks),
        "tasks": tasks,
        "analysis_mode": request.analysis_mode,
        "boundary": "每家公司仍执行官方股票清单确认、全文选择、PDF校验和RAG建库；批量接口不会绕过来源闸门。",
    }
    if supabase_enabled():
        response_payload["persistence"] = {
            "backend": "supabase",
            "cross_instance": True,
            "atomic_batch_enqueue": True,
            "idempotency_key_accepted": bool(idempotency_key),
        }
    return _with_ai_notice(response_payload)


@app.get("/api/cache/prewarm/{batch_id}")
def get_prewarm_report(batch_id: str, http_request: Request) -> dict[str, Any]:
    """读取批量预热报告，不重新执行任务。"""

    normalized = batch_id.strip().upper()
    if supabase_enabled():
        identity = require_authenticated(http_request)
        if identity.is_local or not identity.tenant_id:
            raise HTTPException(status_code=404, detail="未找到该批量预热批次。")
        try:
            batch = get_supabase_client().get_prewarm_batch(
                batch_id=normalized,
                tenant_id=identity.tenant_id,
                requested_by=identity.user_id,
            )
            report = _remote_prewarm_report(batch) if batch is not None else {"items": []}
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网预热批次报告暂时不可用。") from error
    else:
        report = refresh_report(WORKSPACE_ROOT, normalized)
    if not report["items"]:
        raise HTTPException(status_code=404, detail="未找到该批量预热批次。")
    return _with_ai_notice(report)


@app.get("/api/cache/companies/{ticker}")
def get_cached_company(ticker: str) -> dict[str, Any]:
    """读取单家企业的热缓存状态和快照版本。"""

    if supabase_enabled():
        try:
            entries = get_supabase_client().list_public_catalog_entries(company_query=ticker.strip())
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网热缓存目录暂时不可用。") from error
        exact = next((entry for entry in entries if str(entry.get("ticker")) == ticker.strip()), None)
        if exact is None:
            raise HTTPException(status_code=404, detail="该证券代码尚未进入热缓存目录。")
        return _with_ai_notice({"schema_version": "catalog_company_v1", "cache_hit": True, "entry": exact})
    try:
        bootstrap_runtime_catalog(WORKSPACE_ROOT)
        entries = list_cache_entries(WORKSPACE_ROOT, company_query=ticker.strip())
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(status_code=503, detail="热缓存目录暂时不可用。") from error
    exact = next((entry for entry in entries if str(entry.get("ticker")) == ticker.strip()), None)
    if exact is None:
        raise HTTPException(status_code=404, detail="该证券代码尚未进入热缓存目录。")
    return _with_ai_notice({"schema_version": "catalog_company_v1", "cache_hit": True, "entry": exact})


@app.post("/api/cache/refresh/{ticker}", status_code=202)
def refresh_cached_company(
    ticker: str,
    background_tasks: BackgroundTasks,
    http_request: Request,
    years: int = 3,
    latest_year: int | None = None,
) -> dict[str, Any]:
    """按证券代码强制刷新一家企业的公开年报缓存。"""

    require_authenticated(http_request) if supabase_enabled() else optional_authenticated(http_request)
    if years < 2 or years > 5:
        raise HTTPException(status_code=422, detail="years 必须在 2 到 5 之间。")
    batch_id = f"CACHE-BATCH-{uuid.uuid4().hex[:12].upper()}"
    job_id = f"CACHE-JOB-{batch_id[-12:]}-01"
    requested_years = prepare_report_years(latest_year, years)
    payload = {
        "company_query": ticker.strip(),
        "years": years,
        "latest_year": latest_year,
        "analysis_mode": "rag_only",
        "rule_ids": ["R1"],
        "force_refresh": True,
        "cache_policy": "force_refresh",
        "planned_materiality": None,
        "cache_batch_id": batch_id,
        "cache_job_id": job_id,
    }
    task = create_task(WORKSPACE_ROOT, payload)
    create_refresh_job(
        WORKSPACE_ROOT,
        job_id=job_id,
        batch_id=batch_id,
        task_id=task["task_id"],
        ticker=ticker.strip(),
        requested_years=requested_years,
    )
    _queue_pipeline_task(background_tasks, task, payload, http_request)
    return _with_ai_notice(
        {
            "schema_version": "catalog_refresh_v1",
            "task_id": task["task_id"],
            "batch_id": batch_id,
            "ticker": ticker.strip(),
            "status": task["status"],
            "boundary": "刷新仍需重新确认巨潮官方股票清单、年报全文、哈希和RAG指纹。",
        }
    )


@app.get("/api/industry-gates/{case_id}")
def get_industry_gate(case_id: str, http_request: Request) -> dict[str, Any]:
    """读取当前案例在现行闸门版本下的确定性适配结果。"""

    case = _case_record(case_id.upper(), tenant_id=_identity_tenant(http_request))
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    authorize_case_access(http_request, case)
    company = {
        key: case.get(key)
        for key in (
            "ticker",
            "company_name",
            "company_alias",
            "org_id",
            "market",
            "source_mode",
            "industry",
            "industry_name",
            "reporting_profile",
        )
        if case.get(key) is not None
    }
    gate = evaluate_industry_gate(company=company, case=case, rule_ids=["R1", "R2"])
    return _with_ai_notice({"schema_version": "industry_gate_v2", "case_id": case["case_id"], "industry_gate": gate})


@app.post("/api/cache/{cache_id}/replay", response_model=RunResponse)
def replay_run_cache(cache_id: str, http_request: Request) -> RunResponse:
    response: RunResponse | None = None
    remote_cache: dict[str, Any] | None = None
    if supabase_enabled():
        identity = require_authenticated(http_request)
        if identity.is_local or not identity.tenant_id:
            raise HTTPException(status_code=404, detail="未找到该缓存。")
        try:
            remote_cache = get_supabase_client().get_run_cache(cache_id=cache_id, tenant_id=identity.tenant_id)
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网运行缓存暂时不可用。") from error
        if remote_cache is None:
            raise HTTPException(status_code=404, detail="未找到该缓存。")
        response = _replay_remote_cache_payload(remote_cache.get("payload"), cache_id)
        if str(remote_cache.get("case_id") or "") != str(response.context.get("case_id") or ""):
            raise HTTPException(status_code=503, detail="公网运行缓存案例归属不一致。")
    else:
        response = replay_cache(WORKSPACE_ROOT, cache_id)
        if response is None:
            raise HTTPException(status_code=404, detail="未找到该缓存。")
    owner_tenant_id = _identity_tenant(http_request, required=supabase_enabled())
    case = _case_record(str(response.context.get("case_id") or ""), tenant_id=owner_tenant_id)
    if case is None:
        raise HTTPException(status_code=404, detail="缓存对应案例不存在。")
    if supabase_enabled():
        authorize_case_write(http_request, case)
    else:
        authorize_case_access(http_request, case)
    save_run(WORKSPACE_ROOT, response)
    if supabase_enabled():
        _persist_stored_run_remote(
            StoredRunResponse(run=response),
            case,
            owner_tenant_id=owner_tenant_id,
        )
    return response


@app.get("/api/runs/{run_id}/report.docx")
def export_run_report(run_id: str, http_request: Request) -> FileResponse:
    owner_tenant_id = _identity_tenant(http_request, required=supabase_enabled())
    record = _load_stored_run_record(run_id, owner_tenant_id=owner_tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
    stored, run_owner_tenant = record
    case = _case_record(str(stored.run.context.get("case_id") or ""), tenant_id=run_owner_tenant)
    if case is None:
        raise HTTPException(status_code=404, detail="运行对应案例不存在。")
    authorize_case_write(http_request, case)
    try:
        path = build_report(WORKSPACE_ROOT, stored)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


@app.get("/api/rag/status")
def get_rag_status(http_request: Request, case_id: str = CASE_ID) -> dict[str, Any]:
    tenant_id = _identity_tenant(http_request)
    case = _case_record(case_id.upper(), tenant_id=tenant_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    authorize_case_access(http_request, case)
    if not supabase_enabled():
        local_case = _materialized_case_for_resolved(case, tenant_id=tenant_id)
        local_status = rag_status(WORKSPACE_ROOT, case_id.upper()) if local_case is not None else {"status": "not_built"}
        return _with_ai_notice(local_status)
    # 公网部署的 web 与 worker 不共享 SQLite；Supabase active snapshot 才是
    # 可恢复状态。即便本机有 ready 索引，也必须先读取远端，避免旧索引遮蔽新发布。
    try:
        remote_status = get_supabase_client().get_remote_rag_status(case_id=case_id.upper(), tenant_id=tenant_id)
        local_case = _materialized_case_for_resolved(case, tenant_id=tenant_id) if is_public_case(case) else None
        local_status = rag_status(WORKSPACE_ROOT, case_id.upper()) if local_case is not None else {"status": "not_built"}
        if _local_rag_matches_remote(case=case, local_status=local_status, remote_status=remote_status):
            return _with_ai_notice({
                **local_status,
                "persistence": {"backend": "supabase", "cross_instance": True, "snapshot_verified": True},
            })
        return _with_ai_notice({**remote_status, "persistence": {"backend": "supabase", "cross_instance": True}})
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="公网 RAG 状态暂时不可用。") from error


@app.get("/api/rag/questions")
def get_rag_questions() -> dict[str, Any]:
    return _with_ai_notice(question_set())


@app.get("/api/sources/{filename}")
def open_registered_source(filename: str) -> Response:
    """标准股份旧链接只读兼容；新前端统一使用 case_id/document_id。"""
    registered = next((row for row in EVIDENCE.values() if row["source_file"] == filename), None)
    if registered is None:
        raise HTTPException(status_code=404, detail="该文件不在标准案例旧来源白名单中。")
    document_id = f"STD-AR-{registered['year']}-{registered['file_sha256'][:12]}"
    if _public_demo_enabled():
        source_url = _registered_standard_source_url(document_id)
        if source_url:
            return RedirectResponse(source_url, status_code=307)
    path = WORKSPACE_ROOT / filename
    if not path.is_file():
        source_url = _registered_standard_source_url(document_id)
        if source_url:
            return RedirectResponse(source_url, status_code=307)
        raise HTTPException(status_code=404, detail="已登记来源文件不存在且没有安全的官方回退地址。")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.post("/api/rag/prepare")
def prepare_rag(http_request: Request, case_id: str = CASE_ID, force: bool = False) -> dict[str, Any]:
    normalized_case_id = case_id.upper()
    tenant_id = _identity_tenant(http_request, required=supabase_enabled())
    case = _case_record(normalized_case_id, tenant_id=tenant_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    if supabase_enabled():
        authorize_case_write(http_request, case)
    else:
        authorize_case_access(http_request, case)
    if supabase_enabled():
        try:
            remote_status = get_supabase_client().get_remote_rag_status(case_id=normalized_case_id, tenant_id=tenant_id)
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网 RAG 状态暂时不可用。") from error
        if remote_status.get("status") == "ready" and not force:
            return _with_ai_notice({**remote_status, "rebuilt": False, "persistence": {"backend": "supabase", "cross_instance": True}})
        raise HTTPException(status_code=409, detail="fresh web 没有已登记原件，不能本地重建；请通过受控 pipeline 刷新。")
    local_case = _materialized_case_for_resolved(case, tenant_id=tenant_id)
    _ensure_public_standard_sources(normalized_case_id)
    try:
        return _with_ai_notice(prepare_index(WORKSPACE_ROOT, case_id=normalized_case_id, force=force))
    except (FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rag/retrieve")
def rag_retrieve(request: RagRetrieveRequest, http_request: Request) -> dict[str, Any]:
    tenant_id = _identity_tenant(http_request)
    case = _case_record(request.case_id, tenant_id=tenant_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    authorize_case_access(http_request, case)
    try:
        if not supabase_enabled():
            local_case = _materialized_case_for_resolved(case, tenant_id=tenant_id)
            if local_case is None:
                raise RuntimeError("本地 RAG 索引尚未构建")
            record = retrieve(
                WORKSPACE_ROOT,
                query=request.query,
                t0=request.t0,
                rule_id=request.rule_id,
                top_k=request.top_k,
                case_id=request.case_id,
                company_name=request.company_name,
                question_id=request.question_id,
            )
        else:
            identity = request_identity(http_request)
            client = get_supabase_client()
            remote_status = client.get_remote_rag_status(
                case_id=request.case_id,
                tenant_id=str(case.get("tenant_id") or "").strip() or None,
            )
            local_case = _materialized_case_for_resolved(case, tenant_id=tenant_id) if is_public_case(case) else None
            local_status = rag_status(WORKSPACE_ROOT, request.case_id) if local_case is not None else {"status": "not_built"}
            if _local_rag_matches_remote(case=case, local_status=local_status, remote_status=remote_status):
                record = retrieve(
                    WORKSPACE_ROOT,
                    query=request.query,
                    t0=request.t0,
                    rule_id=request.rule_id,
                    top_k=request.top_k,
                    case_id=request.case_id,
                    company_name=request.company_name,
                    question_id=request.question_id,
                )
                record = {**record, "case_id": request.case_id}
                client.persist_rag_retrieval(
                    retrieval_id=str(record.get("retrieval_id") or ""),
                    case_id=request.case_id,
                    case_tenant_id=str(case.get("tenant_id") or "").strip() or None,
                    owner_tenant_id=tenant_id,
                    requested_by=identity.user_id if identity and not identity.is_local else None,
                    rag_snapshot_id=str(local_status["rag_snapshot_id"]),
                    payload=record,
                )
            else:
                # 远端 ready、本机旧版本或本机缺失时，实际计算和留痕都走
                # 同一 Supabase active generation，绝不以远端 ID 给旧结果贴标签。
                record = _remote_rag_retrieve(
                    case=case,
                    query=request.query,
                    t0=request.t0,
                    rule_id=request.rule_id,
                    top_k=request.top_k,
                    question_id=request.question_id,
                    owner_tenant_id=tenant_id,
                    requested_by=identity.user_id if identity and not identity.is_local else None,
                )
        return _with_ai_notice(record)
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="公网 RAG 检索暂时不可用。") from error
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/rag/retrievals/{retrieval_id}")
def read_retrieval_log(retrieval_id: str, http_request: Request) -> dict[str, Any]:
    tenant_id = _identity_tenant(http_request)
    if supabase_enabled():
        # 公网永远先查带 owner 的 Postgres 留痕；即使本机恰有同编号 SQLite
        # 记录，也不能让另一租户或匿名用户以“公开案例”为由绕过日志所有权。
        try:
            remote = get_supabase_client().get_rag_retrieval(retrieval_id, owner_tenant_id=tenant_id)
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="公网检索日志暂时不可用。") from error
        record = remote.get("payload") if remote and isinstance(remote.get("payload"), dict) else None
        if record is not None:
            record = {**record, "case_id": str(remote.get("case_id") or record.get("case_id") or "")}
    else:
        record = get_retrieval(WORKSPACE_ROOT, retrieval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该检索日志。")
    case_id = str(record.get("case_id") or "").upper()
    if case_id:
        case = _case_record(case_id, tenant_id=tenant_id)
        if case is None:
            raise HTTPException(status_code=404, detail="检索对应案例不存在。")
        authorize_case_access(http_request, case)
    return _with_ai_notice(record)


@app.post("/api/supplements")
async def register_supplement(
    http_request: Request,
    parent_run_id: str = Form(...),
    material_type: str = Form("其他补充资料"),
    authorized: bool = Form(False),
    desensitized: bool = Form(False),
    bound_rule_ids: str = Form("R1"),
    as_of_date: str = Form(...),
    note: str = Form(""),
    structured_json: str = Form(""),
    file: UploadFile | None = File(None),
) -> dict[str, Any]:
    identity = require_authenticated(http_request)
    parent = _load_stored_run(parent_run_id, owner_tenant_id=str(identity.tenant_id or "") or None)
    if parent is None:
        raise HTTPException(status_code=404, detail="父运行不存在，不能绑定补充资料。")
    parent_case = _case_record(
        str(parent.run.context.get("case_id") or ""),
        tenant_id=str(identity.tenant_id or "") or None,
    )
    if parent_case is None:
        raise HTTPException(status_code=404, detail="父运行对应案例不存在。")
    authorize_case_write(http_request, parent_case)
    try:
        parsed_rules = json.loads(bound_rule_ids)
        rules = parsed_rules if isinstance(parsed_rules, list) else [str(parsed_rules)]
    except json.JSONDecodeError:
        rules = [item.strip() for item in bound_rule_ids.split(",") if item.strip()]
    content = await file.read() if file is not None else b""
    filename = file.filename if file is not None and file.filename else "structured.json"
    record = create_supplement(
        WORKSPACE_ROOT,
        parent_run_id=parent_run_id,
        material_type=material_type,
        authorized=authorized,
        desensitized=desensitized,
        bound_rule_ids=rules,
        as_of_date=as_of_date,
        note=note,
        filename=filename,
        content=content,
        structured_json=structured_json,
        tenant_id=identity.tenant_id if identity and not identity.is_local else None,
        owner_user_id=identity.user_id if identity and not identity.is_local else None,
    )
    if supabase_enabled() and identity and not identity.is_local and record.get("content_stored"):
        try:
            storage_path = f"{identity.tenant_id}/supplements/{record['supplement_id']}/{record['original_filename']}"
            get_supabase_client().upload_private_object(
                bucket=os.getenv("SUPABASE_PRIVATE_BUCKET", "audittrace-private"),
                object_path=storage_path,
                content=content,
                content_type=mimetypes.guess_type(record["original_filename"])[0] or "application/octet-stream",
            )
            record = mark_supplement_storage(
                WORKSPACE_ROOT,
                record["supplement_id"],
                storage_backend="supabase_private",
                storage_object_path=storage_path,
            ) or record
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="补充资料未完成私有 Storage 持久化。") from error
    if supabase_enabled() and identity and not identity.is_local and identity.tenant_id:
        # 即使资料因脱敏或授权问题被拒绝，也持久化不含原文件的拒绝元数据，保持审计轨迹完整。
        _persist_supplement_record_remote(record, identity.tenant_id)
    return _with_ai_notice(record)


@app.get("/api/supplements/{supplement_id}")
def get_supplement(supplement_id: str, http_request: Request) -> dict[str, Any]:
    identity = require_authenticated(http_request) if supabase_enabled() else optional_authenticated(http_request)
    record = _load_supplement_record(supplement_id, identity)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该补充资料记录。")
    parent = _load_stored_run(
        str(record.get("parent_run_id") or ""),
        owner_tenant_id=str(identity.tenant_id or "") or None if identity else None,
    )
    if parent is None:
        raise HTTPException(status_code=404, detail="补充资料对应父运行不存在。")
    case = _case_record(
        str(parent.run.context.get("case_id") or ""),
        tenant_id=str(identity.tenant_id or "") or None if identity else None,
    )
    if case is None:
        raise HTTPException(status_code=404, detail="补充资料对应案例不存在。")
    authorize_case_access(http_request, case)
    return _with_ai_notice(record)


@app.post("/api/supplements/{supplement_id}/rerun", response_model=RunResponse)
def rerun_with_supplement(
    supplement_id: str,
    request: SupplementRerunRequest,
    http_request: Request,
) -> RunResponse:
    identity = require_authenticated(http_request)
    supplement = _load_supplement_record(supplement_id, identity)
    if supplement is None:
        raise HTTPException(status_code=404, detail="未找到该补充资料记录。")
    if supplement["status"] != "ready_for_rerun":
        raise HTTPException(status_code=409, detail="补充资料没有可验证的结构化证据，不能续分析。")
    parent = _load_stored_run(
        supplement["parent_run_id"],
        owner_tenant_id=str(identity.tenant_id or "") or None,
    )
    if parent is None:
        raise HTTPException(status_code=404, detail="父运行记录已不存在。")
    parent_case = _case_record(
        str(parent.run.context.get("case_id") or ""),
        tenant_id=str(identity.tenant_id or "") or None,
    )
    if parent_case is None:
        raise HTTPException(status_code=404, detail="父运行对应案例不存在。")
    authorize_case_write(http_request, parent_case)
    rule_ids = list(supplement["bound_rule_ids"])
    try:
        if not supabase_enabled() and get_case(WORKSPACE_ROOT, str(parent.run.context.get("case_id") or "")) is not None:
            _, sources = get_period_sources(
                WORKSPACE_ROOT,
                str(parent.run.context["case_id"]),
                int(parent.run.context["current_year"]),
                tuple(rule_ids),
            )
        else:
            # 公网运行已固化当时租户 overlay 和字段证据；无 scope 本机副本可能是
            # 同名公开 base，续分析必须复用父运行不可变快照而不是重新选本机材料。
            sources = deepcopy(parent.run.sources)
            if not sources:
                raise ValueError("父运行没有可恢复的字段证据。")
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=409, detail="父运行对应的案例字段已经不可用。") from error
    # 旧版明确字段更正只作兼容，绝不把独立补充证据静默当作原报表数字。
    for source in sources:
        field_id = source.get("field_id")
        if field_id not in supplement.get("structured_fields", {}):
            continue
        source.update(
            {
                "value": supplement["structured_fields"][field_id],
                "evidence_id": f"{supplement_id}-{field_id}",
                "source_file": supplement["original_filename"] or "结构化粘贴",
                "document_id": f"{supplement_id}-LEGACY-CORRECTION",
                "disclosure_date": supplement["as_of_date"],
                "pdf_page": None,
                "print_page": None,
                "locator": f"补充资料明确字段更正 / {field_id}",
                "file_sha256": supplement["file_sha256"],
                "source_mode": "supplement_structured",
                "supplement_id": supplement_id,
                "source_review_status": "legacy_correction_pending_human_confirmation",
            }
        )
    context = dict(parent.run.context)
    context.update(
        {
            "parent_run_id": parent.run.run_id,
            "supplement_id": supplement_id,
            "continuation_mode": "supplement_evidence_rerun",
            "original_t0": parent.run.context.get("original_t0") or parent.run.context.get("t0"),
            "t0": parent.run.context.get("original_t0") or parent.run.context.get("t0"),
            "supplement_as_of_date": supplement["as_of_date"],
            "selected_rule_ids": rule_ids,
            "source_snapshot_id": f"{parent.run.context.get('source_snapshot_id')}+{supplement_id}",
            "private_case": not is_public_case(parent_case),
        }
    )
    if identity and not identity.is_local:
        context["request_identity"] = identity.as_public_dict()
    model_recheck: Callable[[str], bool] | None = None
    if supabase_enabled():
        model_authorized = authorize_model_transfer(http_request, parent_case)
        if not model_authorized:
            context["model_transfer_allowed"] = False
            context["model_transfer_auth_required"] = True
            context["model_transfer_block_reason"] = "公网模型调用需要当前案例有效同意；本次续分析仅保留本地确定性预检。"
        else:
            context["model_transfer_allowed"] = True
            context["model_transfer_scope"] = model_transmission_scope()

            def _recheck_model_consent(_role: str) -> bool:
                try:
                    if not _worker_lease_is_current(http_request):
                        return False
                    return authorize_model_transfer(http_request, parent_case)
                except HTTPException:
                    return False

            model_recheck = _recheck_model_consent
    parameters = _validated_rerun_parameters(parent.run.context.get("configured_parameters", {}))
    response = _execute_run(
        context=context,
        sources=sources,
        rule_ids=rule_ids,
        run_mode=request.run_mode,
        r2_min_gap=float(parameters["r2_min_gap"]),
        planned_materiality=parameters.get("planned_materiality"),
        r1_gap_threshold=float(parameters["r1_gap_threshold"]),
        r1_strong_gap_threshold=float(parameters["r1_strong_gap_threshold"]),
        r1_absolute_threshold=float(parameters["r1_absolute_threshold"]),
        http_request=http_request,
        run_prefix="RUN-SUP",
        supplement_evidence=supplement.get("structured_evidence", []),
        model_recheck=model_recheck,
    )
    response.context["recommendation_change"] = {
        "before": parent.run.ai_recommendation,
        "after": response.ai_recommendation,
        "label": (
            "保留"
            if parent.run.ai_recommendation == response.ai_recommendation
            else "建议发生变化"
        ),
        "boundary": "变化由新增证据参与本次链路后产生，仍须真人复核。",
    }
    save_run(WORKSPACE_ROOT, response)
    return response
