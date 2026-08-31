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
正式模式的 RAG 失败时不调用模型；竞赛完整分析会把 RAG 缺口显式交给证据缺口路线。
三角色任一步失败时最终草稿为空，完整性保持模型链失败。
三个角色全部完成后才允许标记完整分析并保存最终草稿。
没有程序候选时完整分析仍进入三角色；AI复核路线改为未触发、行业或缺口任务。
模型配额限制公开访客调用；服务端批量预热只绕过访客窗口，仍受每日预算和并发约束。
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
RAG 固定问题按 AI 复核路线覆盖候选、未触发、行业和数据缺口事项。
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
import hmac
import ipaddress
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
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .agents import PROMPT_VERSION, compact_evidence_bundle, minimize_model_context, run_agent_chain
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
    annotate_financial_field_rows_quality,
    build_case_template_zip,
    calculation_ready_financial_rows,
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
from .provider_readiness import (
    classify_provider_channel,
    get_provider_snapshot,
    is_provider_probe_enabled,
    record_provider_failure,
    record_provider_success,
)
from .public_model import PublicModelLedger, PublicModelQuotaError, SupabasePublicModelLedger, build_cache_key
from .evaluation import load_evaluation_dashboard
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
from .demo_bootstrap import blocked_bootstrap_payload, build_bootstrap_payload, load_demo_manifest
from .demo_run_tasks import AGENT_ROLE_ORDER, STAGE_ORDER, DemoRunTaskStore, IdempotencyConflict, SupabaseDemoRunTaskStore, result_expiry_iso
from .manifest_hash import CANONICAL_MANIFEST_HASH_ALGORITHM, manifest_sha256
from .knowledge_rag import build_retrieval_request, retrieve_knowledge
from .knowledge_sources import active_source_entries, coverage_group_summary, knowledge_cutoff_date, knowledge_snapshot_id
from .knowledge_sources import load_source_manifest as load_knowledge_manifest
from .model_quality import quality_snapshot, record_external_run
from .anti_confirmation import build_anti_confirmation_record
from .coverage_matrix import build_assertion_evidence_procedure_matrix
from .evidence_fitness import annotate_evidence_bundle, enforce_claim_boundaries, fitness_map_for_evidence
from .numeric_gate import validate_numeric_claims
from .rag import get_retrieval, prepare_index, question_set, retrieve, status as rag_status
from .run_store import load_run, save_human_review, save_run
from .seed_catalog import (
    get_seed_case,
    get_seed_retrieval,
    load_seed_cases,
    retrieve_seed_rag,
    seed_catalog_summary,
    seed_rag_status,
)
from .signoff import SIGNOFF_BOUNDARY, load_signoff_status
from .schemas import (
    AI_GENERATED_CONTENT_NOTICE,
    AgentClaim,
    AgentOutput,
    AgentStep,
    AuthLoginRequest,
    CachePrewarmRequest,
    CacheResolveRequest,
    CNInfoCompanyConfirmation,
    CNInfoFieldConfirmation,
    CNInfoPipelineRequest,
    DemoRunCreateRequest,
    HealthResponse,
    HumanReviewRequest,
    ModelCheck,
    ModelTransferConsentRequest,
    RagRetrieveRequest,
    RuleResult,
    RunRequest,
    RunResponse,
    StoredRunResponse,
    SupplementSampleRequest,
    SupplementRerunRequest,
)
from .source_cache import ensure_standard_sources
from .supplements import create_supplement, load_supplement, mark_supplement_storage
from .supabase_adapter import (
    SupabaseAuthError,
    SupabaseConflict,
    SupabaseError,
    SupabaseLeaseLost,
    SupabaseNotConfigured,
    SupabaseConfig,
    demo_task_supabase_enabled,
    get_demo_task_client,
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
_PUBLIC_MODEL_LEDGER: PublicModelLedger | SupabasePublicModelLedger | None = None
_PUBLIC_MODEL_LEDGER_MODE: str | None = None


def _public_model_ledger() -> PublicModelLedger | SupabasePublicModelLedger:
    """按公开演示台账配置选择本地或跨实例 Supabase 实现。"""

    global _PUBLIC_MODEL_LEDGER, _PUBLIC_MODEL_LEDGER_MODE
    requested_mode = "supabase" if demo_task_supabase_enabled() else "local"
    if _PUBLIC_MODEL_LEDGER is not None and _PUBLIC_MODEL_LEDGER_MODE != requested_mode:
        _PUBLIC_MODEL_LEDGER = None
    if _PUBLIC_MODEL_LEDGER is None:
        if requested_mode == "supabase":
            # 缺失 URL/service-role key 时让调用方映射为 503，严禁静默退回
            # 本地额度，避免 Render 重启后清空公共预算并产生匿名超发。
            _PUBLIC_MODEL_LEDGER = SupabasePublicModelLedger(get_demo_task_client())
        else:
            _PUBLIC_MODEL_LEDGER = PublicModelLedger(WORKSPACE_ROOT)
        _PUBLIC_MODEL_LEDGER_MODE = requested_mode
    return _PUBLIC_MODEL_LEDGER

@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    """启动时校验代理信任边界，并恢复中断的预热任务。

    代理配置错误属于部署安全错误，必须阻止启动，不能静默忽略。
    目录恢复失败则保留健康接口，具体缓存请求仍会返回可理解的 503。
    恢复仅处理本地已有记录，不会在启动期间调用外部模型。
    """

    _validate_trusted_proxy_configuration()
    # 启动时打印模型通道、模型 ID 与调用开关，用于人工核对配置；绝不打印 API Key。
    try:
        _startup_key, startup_base_url, startup_model = _model_settings()
        startup_channel = classify_provider_channel(startup_base_url)
        print(
            f"[AuditTrace startup] provider={startup_channel['provider_kind']} "
            f"({startup_channel['provider_host']}) model={startup_model} "
            f"probe_enabled={str(is_provider_probe_enabled()).lower()} "
            f"external_model_enabled={str(_demo_external_model_enabled()).lower()} "
            f"demo_mode={str(_competition_demo_enabled()).lower()} "
            f"api_key_present={bool(_startup_key)}"
        )
    except Exception:  # noqa: BLE001 - 启动打印失败不能阻止服务启动
        pass
    try:
        recover_orphaned_refresh_jobs(WORKSPACE_ROOT)
        bootstrap_runtime_catalog(WORKSPACE_ROOT)
    except (OSError, ValueError, TypeError):
        # A catalog problem must not prevent the HTTP service from exposing its
        # health endpoint; individual cache calls still return a clear 503.
        pass
    yield


def _configured_cors_origins() -> list[str]:
    """
    默认同源；只有显式登记的 HTTP(S) 源可以跨域调用 API。

    Origin 只允许 scheme、host 和可选端口，拒绝用户信息、路径、查询、片段和通配符。
    先用结构化 URL 解析器取得组件，再与规范化 Origin 比对，避免简单正则放过欺骗值。
    去除唯一可选的末尾斜杠后去重，保证中间件收到稳定列表。
    """

    raw = os.getenv("AUDITTRACE_CORS_ORIGINS", "")
    origins: list[str] = []
    for item in (part.strip() for part in raw.split(",")):
        if not item:
            continue
        parsed = urlsplit(item)
        try:
            parsed_port = parsed.port
        except ValueError as error:
            raise RuntimeError("AUDITTRACE_CORS_ORIGINS 包含无效端口。") from error
        normalized_host = f"[{parsed.hostname}]" if parsed.hostname and ":" in parsed.hostname else parsed.hostname
        expected_netloc = (
            f"{normalized_host}:{parsed_port}"
            if normalized_host and parsed_port is not None
            else normalized_host
        )
        canonical_origin = f"{parsed.scheme}://{expected_netloc}"
        supplied_origin = item[:-1] if item.endswith("/") else item
        valid = (
            item != "*"
            and parsed.scheme in {"http", "https"}
            and parsed.hostname is not None
            and "*" not in parsed.netloc
            and not any(character.isspace() or ord(character) < 32 for character in item)
            and parsed.username is None
            and parsed.password is None
            and parsed.netloc.lower() == str(expected_netloc or "").lower()
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and supplied_origin.lower() == canonical_origin.lower()
        )
        if not valid:
            raise RuntimeError("AUDITTRACE_CORS_ORIGINS 只能填写逗号分隔的明确 HTTP(S) Origin，不能使用通配符。")
        normalized = supplied_origin
        if normalized not in origins:
            origins.append(normalized)
    return origins


app = FastAPI(title="审迹智链 AuditTrace API", version=ENGINE_VERSION, lifespan=app_lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
)


@app.middleware("http")
async def security_headers(http_request: Request, call_next: Callable[..., Any]) -> Any:
    """给 HTML、API 和下载响应统一增加最小安全头，错误分支也不能例外。"""

    response = await call_next(http_request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src "
        "'self'; style-src-attr 'none'; img-src 'self' data:; "
        "font-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    # 运行状态、任务和下载不能被浏览器/代理复用旧快照；带版本号的静态
    # 资源可以长期缓存，案例选择器等公开只读路由可由路由自身覆盖策略。
    path = http_request.url.path
    if path.startswith("/assets/"):
        cache_policy = "public, max-age=31536000, immutable"
    elif path == "/openapi.json":
        cache_policy = "public, max-age=300"
    elif path == "/" or path.startswith("/api/"):
        cache_policy = "private, no-store"
    else:
        cache_policy = "no-store"
    response.headers.setdefault("Cache-Control", cache_policy)
    if http_request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


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


@app.exception_handler(SupabaseError)
async def supabase_error_handler(_request: Request, error: SupabaseError) -> JSONResponse:
    """远程任务台账异常统一映射为脱敏、可操作的稳定响应。"""

    # Supabase 原始响应、URL 和 service-role key 不进入公开响应；具体错误只留在
    # 服务端日志（由部署平台收集），浏览器只依赖稳定 code/status 重试或停用入口。
    return JSONResponse(
        status_code=int(getattr(error, "status_code", 503) or 503),
        content=_with_ai_notice(
            {
                "detail": str(getattr(error, "code", "SUPABASE_ERROR")),
                "failure_code": str(getattr(error, "code", "SUPABASE_ERROR")),
            }
        ),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, error: Exception) -> JSONResponse:
    """全局兜底异常处理器：未捕获异常返回脱敏 500 错误，并强制附加 AI 免责声明。"""
    # 记录原始异常类型便于定位问题，同时保证所有未预期 500 响应均包含合规 AI 声明
    return JSONResponse(
        status_code=500,
        content=_with_ai_notice({
            "detail": f"服务器内部处理异常（{type(error).__name__}），请稍后重试或查看系统状态日志。"
        }),
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


def _model_readiness(request: Request | None = None) -> dict[str, Any]:
    """结合配置、额度账本与供应商可用性快照，给出真实模型可用性结论。"""

    # 就绪判断读取服务端状态与受控探测快照，不产生用户 Token 消耗。
    # Key 存在只能证明配置完成，不能证明供应商鉴权、余额与公开账本可用。
    # 公开页面必须同时看到后端可用、模型已配置和真实模型可运行三种状态。
    # 缺少任一公开条件或供应商处于熔断时，页面仍保留确定性备用入口。
    # 原因码保持稳定，前端可以据此给出中文的下一步操作。
    # 额度快照只在需要时读取，不把秘密值返回给浏览器。
    # 真实运行的鉴权与余额失败会立即反馈给熔断状态机。
    # 账本异常按失败关闭处理，避免把未知状态误报为可运行。
    # 并发额度为零时禁止继续排队，避免用户反复点击消耗资源。
    # 私有模式仍允许已授权案例使用配置好的模型链。
    # 公开模式只有所有条件同时满足才返回 external_live 所需的 ready。
    # 这些判断与确定性备用完全分离，备用分析永远不调用外部模型。
    api_key, base_url, model_id = _model_settings()
    channel_info = classify_provider_channel(base_url)
    p_kind = channel_info["provider_kind"]
    p_label = channel_info["provider_label"]
    p_host = channel_info["provider_host"]
    public_live = _public_demo_enabled() and _demo_external_model_enabled()

    if not api_key:
        return {
            "full_analysis_ready": False,
            "full_analysis_reason_code": "api_key_missing",
            "full_analysis_message": f"服务端尚未配置 {p_label} API Key；可运行仅计算或确定性备用分析。",
            "deterministic_backup_available": True,
            "model_id": model_id,
            "provider_kind": p_kind,
            "provider_label": p_label,
            "provider_host": p_host,
            "paid_probe_performed": False,
            "last_runtime_failure_code": None,
            "next_action_code": "configure_api_key",
            "quota": None,
            "provider": None,
        }
    if not public_live:
        provider_snapshot = get_provider_snapshot()
        return {
            "full_analysis_ready": provider_snapshot.status == "ready",
            "full_analysis_reason_code": provider_snapshot.reason_code,
            "full_analysis_message": provider_snapshot.message,
            "deterministic_backup_available": True,
            "model_id": model_id,
            "provider_kind": p_kind,
            "provider_label": p_label,
            "provider_host": p_host,
            "paid_probe_performed": bool(provider_snapshot.paid_probe_performed),
            "last_runtime_failure_code": provider_snapshot.last_runtime_failure_code,
            "next_action_code": provider_snapshot.next_action_code,
            "quota": None,
            "provider": provider_snapshot.to_dict(),
        }
    quota_secret = os.getenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "").strip()
    if not quota_secret:
        return {
            "full_analysis_ready": False,
            "full_analysis_reason_code": "public_quota_secret_missing",
            "full_analysis_message": "公开模型额度密钥未配置；请在服务端生成密钥后再运行真实完整分析。",
            "deterministic_backup_available": True,
            "model_id": model_id,
            "provider_kind": p_kind,
            "provider_label": p_label,
            "provider_host": p_host,
            "paid_probe_performed": False,
            "last_runtime_failure_code": None,
            "next_action_code": "configure_quota_secret",
            "quota": None,
            "provider": None,
        }
    if len(quota_secret) < 32:
        return {
            "full_analysis_ready": False,
            "full_analysis_reason_code": "public_quota_secret_invalid",
            "full_analysis_message": "公开模型额度密钥长度不足 32 位；请在服务端重新生成安全密钥。",
            "deterministic_backup_available": True,
            "model_id": model_id,
            "provider_kind": p_kind,
            "provider_label": p_label,
            "provider_host": p_host,
            "paid_probe_performed": False,
            "last_runtime_failure_code": None,
            "next_action_code": "configure_quota_secret",
            "quota": None,
            "provider": None,
        }
    try:
        quota = _public_model_ledger().quota_snapshot(_client_identity(request) if request else None)
    except (OSError, RuntimeError, ValueError, TypeError, SupabaseError) as error:
        return {
            "full_analysis_ready": False,
            "full_analysis_reason_code": "quota_ledger_unavailable",
            "full_analysis_message": f"公开额度账本暂不可用（{type(error).__name__}）；请稍后重试或使用备用分析。",
            "deterministic_backup_available": True,
            "model_id": model_id,
            "provider_kind": p_kind,
            "provider_label": p_label,
            "provider_host": p_host,
            "paid_probe_performed": False,
            "last_runtime_failure_code": None,
            "next_action_code": "retry_later",
            "quota": None,
            "provider": None,
        }
    quota_exhausted = any(
        int(quota.get(key) or 0) <= 0
        for key in ("global_remaining_15m", "daily_runs_remaining")
    ) or int(quota.get("active") or 0) >= int(quota.get("max_concurrent") or 1)
    if quota_exhausted:
        return {
            "full_analysis_ready": False,
            "full_analysis_reason_code": "quota_exhausted",
            "full_analysis_message": "当前公开模型额度或并发已用尽；请稍后重试，或选择确定性备用分析。",
            "deterministic_backup_available": True,
            "model_id": model_id,
            "provider_kind": p_kind,
            "provider_label": p_label,
            "provider_host": p_host,
            "paid_probe_performed": False,
            "last_runtime_failure_code": None,
            "next_action_code": "use_deterministic_backup",
            "quota": quota,
            "provider": None,
        }
    provider_snapshot = get_provider_snapshot()
    if provider_snapshot.status != "ready":
        return {
            "full_analysis_ready": False,
            "full_analysis_reason_code": provider_snapshot.reason_code,
            "full_analysis_message": provider_snapshot.message,
            "deterministic_backup_available": True,
            "model_id": model_id,
            "provider_kind": p_kind,
            "provider_label": p_label,
            "provider_host": p_host,
            "paid_probe_performed": bool(provider_snapshot.paid_probe_performed),
            "last_runtime_failure_code": provider_snapshot.last_runtime_failure_code,
            "next_action_code": provider_snapshot.next_action_code,
            "quota": quota,
            "provider": provider_snapshot.to_dict(),
        }
    return {
        "full_analysis_ready": True,
        "full_analysis_reason_code": "ready",
        "full_analysis_message": f"真实模型（{p_label}）、公开额度密钥、额度账本和当前额度均可用。",
        "deterministic_backup_available": True,
        "model_id": model_id,
        "provider_kind": p_kind,
        "provider_label": p_label,
        "provider_host": p_host,
        "paid_probe_performed": bool(provider_snapshot.paid_probe_performed),
        "last_runtime_failure_code": provider_snapshot.last_runtime_failure_code,
        "next_action_code": "ready",
        "quota": quota,
        "provider": provider_snapshot.to_dict(),
    }


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _nonnegative_int_env(name: str, default: int = 0, upper: int = 10) -> int:
    """读取受信代理跳数等允许为零的安全整数配置。"""

    try:
        return max(0, min(upper, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def _configured_trusted_proxy_networks() -> tuple[Any, ...]:
    """解析可直连本服务的受信反向代理网段；空值表示不信任转发头。"""

    raw = os.getenv("AUDITTRACE_TRUSTED_PROXY_CIDRS", "")
    networks: list[Any] = []
    for item in (part.strip() for part in raw.split(",")):
        if not item:
            continue
        try:
            network = ipaddress.ip_network(item, strict=False)
        except ValueError as error:
            raise RuntimeError("AUDITTRACE_TRUSTED_PROXY_CIDRS 包含无效的 IP 网段。") from error
        if network.prefixlen == 0:
            raise RuntimeError("AUDITTRACE_TRUSTED_PROXY_CIDRS 不能信任整个互联网地址空间。")
        if network not in networks:
            networks.append(network)
    return tuple(networks)


def _validate_trusted_proxy_configuration() -> None:
    """转发跳数与受信网段必须成对配置，避免部署时静默退化。"""

    trusted_hops = _nonnegative_int_env("AUDITTRACE_TRUSTED_PROXY_HOPS")
    trusted_networks = _configured_trusted_proxy_networks()
    if bool(trusted_hops) != bool(trusted_networks):
        raise RuntimeError(
            "AUDITTRACE_TRUSTED_PROXY_HOPS 与 AUDITTRACE_TRUSTED_PROXY_CIDRS 必须同时配置或同时留空。"
        )


def _public_demo_enabled() -> bool:
    return os.getenv("AUDITTRACE_PUBLIC_DEMO", "false").strip().lower() in {"1", "true", "yes"}


def _competition_demo_enabled() -> bool:
    """竞赛演示关闭账号与租户依赖，但不放宽来源、文件和模型输出校验。"""

    return os.getenv("AUDITTRACE_DEMO_MODE", "false").strip().lower() in {"1", "true", "yes"}


def _onsite_live_sample_enabled() -> bool:
    """团队本机现场模式可接入新公开样例；共享部署默认关闭高成本写入。"""

    return os.getenv("AUDITTRACE_ONSITE_LIVE_SAMPLE", "false").strip().lower() in {"1", "true", "yes"}


def _reject_shared_demo_mutation(action: str = "自定义案例或资料") -> None:
    """匿名本地公网实例只允许可丢弃的内置样例操作，禁止权威或高成本写入。"""

    if _public_demo_enabled() and _competition_demo_enabled() and not supabase_enabled():
        raise HTTPException(
            status_code=403,
            detail=f"公开演示实例不允许{action}；请在私有本地模式或已启用租户隔离的部署中操作。",
        )


def _reject_shared_demo_uploads() -> None:
    """兼容旧调用名；上传属于共享 Demo 禁止的权威写入。"""

    _reject_shared_demo_mutation("接收自定义案例或资料")


def _client_identity(request: Request) -> str:
    """只从明确网段内的反向代理解析转发链；其他请求使用直连地址。"""

    direct = str(request.client.host if request.client else "unknown").strip()
    try:
        direct_ip = ipaddress.ip_address(direct)
    except ValueError:
        direct_ip = None
    trusted_hops = _nonnegative_int_env("AUDITTRACE_TRUSTED_PROXY_HOPS")
    trusted_networks = _configured_trusted_proxy_networks()
    direct_is_trusted = bool(
        direct_ip is not None and any(direct_ip in network for network in trusted_networks)
    )
    if trusted_hops and direct_is_trusted:
        chain = [item.strip() for item in request.headers.get("x-forwarded-for", "").split(",") if item.strip()]
        candidate_index = len(chain) - trusted_hops
        if candidate_index >= 0:
            try:
                parsed_chain = [ipaddress.ip_address(item) for item in chain]
            except ValueError:
                parsed_chain = []
            trusted_relays = parsed_chain[candidate_index + 1 :]
            if parsed_chain and all(
                any(relay in network for network in trusted_networks)
                for relay in trusted_relays
            ):
                return str(parsed_chain[candidate_index])
    return str(direct_ip) if direct_ip is not None else direct or "unknown"


def _authorize_model_prewarm(request: Request) -> None:
    """Allow full-model prewarm only from a server/operator secret.

    Public visitors keep the normal per-IP and fifteen-minute limits.  The
    secret is read only by the service and is never returned to the browser;
    the batch still consumes the daily model budget and concurrency lease.
    """

    configured = os.getenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "").strip()
    provided = str(request.headers.get("x-audittrace-prewarm-secret") or "").strip()
    if len(configured) < 32:
        raise HTTPException(status_code=503, detail="服务端模型预热密钥未安全配置。")
    if not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(status_code=403, detail="模型预热仅允许服务端批处理调用。")


def _enforce_public_model_quota(request: Request) -> str | None:
    if not _public_demo_enabled():
        return None
    # 只有具备供应商密钥、确实可能发生外部调用时才占用真实模型额度账本。
    # 开关开启但密钥缺失仍要让请求进入运行链并返回 config_missing；此类匿名
    # 尝试继续使用下方内存窗口限流，不能被额度摘要密钥的 503 提前遮蔽。
    if _demo_external_model_enabled() and os.getenv("DEEPSEEK_API_KEY", "").strip():
        quota_secret = os.getenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "").strip()
        if len(quota_secret) < 32:
            raise HTTPException(
                status_code=503,
                detail="公开真实模型额度摘要秘密未安全配置；请设置至少32位的 AUDITTRACE_PUBLIC_QUOTA_SECRET。",
            )
        try:
            if bool(getattr(request.state, "model_batch_authorized", False)):
                return _public_model_ledger().reserve_batch(str(getattr(request.state, "model_batch_id", "service")))
            return _public_model_ledger().reserve(_client_identity(request))
        except PublicModelQuotaError as error:
            raise HTTPException(status_code=429, detail=str(error)) from error
        except SupabaseError as error:
            # 生产使用 Supabase 时不可静默降级到进程内 SQLite；静态浏览与
            # 确定性备用仍可用，但新的真实模型任务必须明确返回 503。
            raise HTTPException(status_code=503, detail="公开模型额度台账暂不可用。") from error
    now = time.monotonic()
    window_seconds = _positive_int_env("AUDITTRACE_MODEL_RUN_WINDOW_SECONDS", 900)
    per_ip_limit = _positive_int_env("AUDITTRACE_MODEL_RUN_LIMIT", 2)
    global_limit = _positive_int_env("AUDITTRACE_MODEL_RUN_GLOBAL_LIMIT", 10)
    cutoff = now - window_seconds
    client_id = _client_identity(request)
    with _PUBLIC_MODEL_REQUEST_LOCK:
        while _PUBLIC_MODEL_REQUESTS_GLOBAL and _PUBLIC_MODEL_REQUESTS_GLOBAL[0] <= cutoff:
            _PUBLIC_MODEL_REQUESTS_GLOBAL.popleft()
        for existing_client_id, existing_requests in list(_PUBLIC_MODEL_REQUESTS_BY_IP.items()):
            while existing_requests and existing_requests[0] <= cutoff:
                existing_requests.popleft()
            if not existing_requests:
                _PUBLIC_MODEL_REQUESTS_BY_IP.pop(existing_client_id, None)
        recent_for_ip = _PUBLIC_MODEL_REQUESTS_BY_IP.get(client_id)
        if (recent_for_ip is not None and len(recent_for_ip) >= per_ip_limit) or len(_PUBLIC_MODEL_REQUESTS_GLOBAL) >= global_limit:
            raise HTTPException(
                status_code=429,
                detail="公开演示的AI调用次数已达到临时上限，请稍后再试；仅计算预检不受影响。",
            )
        if recent_for_ip is None:
            recent_for_ip = deque()
            _PUBLIC_MODEL_REQUESTS_BY_IP[client_id] = recent_for_ip
        recent_for_ip.append(now)
        _PUBLIC_MODEL_REQUESTS_GLOBAL.append(now)
    return None


def _public_case(case: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(case)
    # 演示检索片段只由服务端检索接口按需返回，案例目录不整包下发。
    public.pop("demo_rag_evidence", None)
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
    documents = {str(item.get("document_id") or ""): item for item in public.get("documents", [])}
    for field in public.get("financial_fields", []):
        document = documents.get(str(field.get("document_id") or "")) or {}
        # 种子不携带部署本机文件名；页面以稳定文档编号展示来源，不再显示空白或 undefined。
        field["source_file"] = field.get("source_file") or field.get("document_id")
        field["file_sha256"] = field.get("file_sha256") or document.get("sha256")
        field["source_mode"] = field.get("source_mode") or "supabase_persisted_verified"
    return public


def _public_case_summary(case: dict[str, Any]) -> dict[str, Any]:
    """案例目录只下发选择器所需元数据，完整字段仍由详情接口按案例读取。"""

    years = case.get("available_years") or case.get("available_report_years") or []
    if not years:
        years = sorted(
            {
                int(row["year"])
                for row in case.get("financial_fields", [])
                if isinstance(row, dict) and str(row.get("year") or "").isdigit()
            },
            reverse=True,
        )
    case_id = str(case.get("case_id") or "")
    registry_mode = str(case.get("registry_mode") or "")
    sample_type = str(case.get("sample_type") or "")
    # 案例来源分类标签：用于前端选择器直观展示案例类型与审计证据来源
    # 区分开发基准案例、手工登记案例、巨潮官方自动抓取案例与合成样例
    if case_id.startswith("STD_DEV"):
        source_label = "标准股份开发案例"
        registry_mode = registry_mode or "built_in"
        source_type = str(case.get("source_type") or "development_standard")
    elif case_id.startswith("JACK_"):
        source_label = "手工登记案例"
        registry_mode = registry_mode or "imported_template"
        source_type = str(case.get("source_type") or "manual_registered")
    elif registry_mode == "cninfo_official_auto" or case_id.startswith("CNINFO_"):
        source_label = "巨潮年报抓取"
        registry_mode = registry_mode or "cninfo_official_auto"
        source_type = str(case.get("source_type") or "official_annual_report")
    elif sample_type == "synthetic":
        source_label = "合成样例"
        registry_mode = registry_mode or "synthetic"
        source_type = str(case.get("source_type") or "synthetic")
    else:
        source_label = "公开案例快照"
        registry_mode = registry_mode or "registered_case"
        source_type = str(case.get("source_type") or "public_snapshot")
    summary = {
        "case_id": case.get("case_id"),
        "company_name": case.get("company_name"),
        "available_years": sorted({str(year) for year in years}, reverse=True),
        "source_label": source_label,
        "registry_mode": registry_mode,
        "source_type": source_type,
    }
    # 目录摘要允许省略空可选字段；这对历史临时案例很多的本地开发目录
    # 尤其重要，同时保留公开演示案例的完整代码、日期和来源元数据。
    for key in ("company_alias", "ticker", "t0"):
        value = case.get(key)
        if value not in (None, "", []):
            summary[key] = value
    # sample_type 仍只在详情返回；registry_mode / source_type 留在轻量摘要中，
    # 供前端区分同公司、同代码的历史案例来源，不需要再请求完整案例。
    return summary


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
        if _competition_demo_enabled():
            # 公开演示的 CNINFO 案例以跟踪的元数据/RAG 种子为准；本机目录
            # 可能还有旧的 SQLite 副本，但不能让它遮蔽发布清单中的快照。
            seed = get_seed_case(WORKSPACE_ROOT, case_id)
            if seed is not None:
                return seed
        local = get_case(WORKSPACE_ROOT, case_id)
        if local is not None:
            return _normalize_official_public_case(local)
        return get_seed_case(WORKSPACE_ROOT, case_id) if _competition_demo_enabled() else None
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
        if _competition_demo_enabled():
            # 与 RAG 和 demo run 共用冻结 seed，避免本机旧案例记录缺少
            # demo_rag_evidence 时把公开 15 案误判为未登记或未就绪。
            seed = get_seed_case(WORKSPACE_ROOT, case_id)
            if seed is not None:
                return seed
        local = get_case(WORKSPACE_ROOT, case_id)
        if local is not None:
            return _normalize_official_public_case(local)
        return get_seed_case(WORKSPACE_ROOT, case_id) if _competition_demo_enabled() else None
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

    candidate_rows = [deepcopy(row) for row in (case.get("financial_fields") or [])]
    raw_rows = calculation_ready_financial_rows(candidate_rows)
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
            "source_candidate_count": len(candidate_rows),
            "usable_source_candidate_count": len(raw_rows),
            "blocked_candidate_count": len(candidate_rows) - len(raw_rows),
            "candidate_quality_issues": list(
                dict.fromkeys(
                    issue
                    for row in annotate_financial_field_rows_quality(candidate_rows)
                    for issue in row.get("candidate_quality_issues", [])
                )
            ),
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
        "case_material_gaps": list(
            dict.fromkeys(
                list(deepcopy(case.get("material_gaps", [])))
                + list((prescreen_plan or {}).get("candidate_quality_issues") or [])
            )
        ),
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
                "low_confidence": score < 0.50,
                "confidence_note": "低置信候选，必须回原页复核。" if score < 0.50 else "候选片段仍须回原页复核。",
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
    source_usage = {
        "input_tokens": int(run_data.get("input_tokens") or 0),
        "output_tokens": int(run_data.get("output_tokens") or 0),
        "duration_ms": int(run_data.get("duration_ms") or 0),
        "provider_call_count": int(run_data.get("provider_call_count") or 0),
    }
    context = run_data.get("context") if isinstance(run_data.get("context"), dict) else {}
    context.update(
        {
            "execution_mode": "cache_replay",
            "replayed_from_cache_id": cache_id,
            "replayed_from_run_id": source_run_id,
            "replayed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "cache_source_model_usage": source_usage,
            "external_model_call_performed": False,
        }
    )
    run_data["context"] = context
    run_data["run_completeness"] = "cache_replay_not_fresh_analysis"
    run_data["execution_mode"] = "cache_replay"
    run_data["cache_hit"] = True
    run_data["input_tokens"] = 0
    run_data["output_tokens"] = 0
    run_data["duration_ms"] = 0
    run_data["provider_call_count"] = 0
    original_model = run_data.get("model_check") if isinstance(run_data.get("model_check"), dict) else {}
    run_data["model_check"] = {
        "status": "cache_replay",
        "model_id": original_model.get("model_id"),
        "execution_mode": "cache_replay",
        "cache_hit": True,
        "input_tokens": 0,
        "output_tokens": 0,
        "duration_ms": 0,
        "provider_call_count": 0,
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
    if _competition_demo_enabled():
        # 比赛目录固定为一个标准案例加 50 家公开 CNINFO 样例；历史运行目录
        # 里的临时案例不混入选择器，避免重复公司和评委看到不相关状态。
        standard = next((case for case in local_cases if str(case.get("case_id") or "") == CASE_ID), None)
        cases = [standard] if standard is not None else []
        cases.extend(load_seed_cases(WORKSPACE_ROOT))
    else:
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
    if _competition_demo_enabled():
        if not supabase_enabled():
            catalog_state = {
                "status": "demo_ready",
                "source": "standard_case_plus_tracked_verified_cninfo_seed",
                "detail": "竞赛演示目录固定展示标准案例和 50 家已校验的公开年报样例，不需要登录服务。",
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
        gap_message = "缺少R2字段：" + "、".join(missing)
        return RuleResult(
            rule_id="R2",
            status="DATA_GAP",
            screening_status="DATA_GAP",
            # 字段缺失属于资料缺口，不是来源文件、哈希或披露日期失败。
            source_validation=_base_source_validation([]),
            metrics=metric_defaults,
            risk_card={
                "card_type": "data_gap",
                "rule_id": "R2",
                "title": "R2辅助规则缺少可比字段",
                "data_gaps": [gap_message],
                "requested_materials": ["缺失年度的经营现金流或收入字段"],
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
    candidate_rows = local_rows if local_rows is not None else deepcopy(case.get("financial_fields") or [])
    rows = calculation_ready_financial_rows(candidate_rows)
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
            # 部署种子刻意不携带本机文件名；setdefault 会把首次写入的 None
            # 永久保留，导致后续文档编号兜底失效。这里按有效值逐级回退。
            source["source_file"] = source.get("source_file") or document.get("source_file") or source.get("document_id")
            source.setdefault("storage_relpath", document.get("storage_relpath"))
            source.setdefault("file_sha256", document.get("sha256") or document.get("file_sha256"))
            source.setdefault("source_url", document.get("source_url"))
            source.setdefault("pdf_page", row.get("pdf_page"))
            source.setdefault("disclosure_date", document.get("disclosure_date"))
        if local_rows is None:
            source["source_mode"] = "supabase_persisted_verified"
            source["source_file"] = source.get("source_file") or source.get("document_id")
            source["file_sha256"] = source.get("file_sha256") or (document or {}).get("sha256")
            source["locator"] = source.get("locator") or f"PDF 第 {source.get('pdf_page')} 页"
            source["unit"] = source.get("unit") or case.get("amount_unit", "元")
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
        "source_candidate_count": len(candidate_rows),
        "usable_source_candidate_count": len(rows),
        "blocked_candidate_count": len(candidate_rows) - len(rows),
            "candidate_quality_issues": list(
                dict.fromkeys(
                    issue
                    for row in annotate_financial_field_rows_quality(candidate_rows)
                    for issue in row.get("candidate_quality_issues", [])
                )
            ),
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
        "case_material_gaps": list(
            dict.fromkeys(
                list(deepcopy(case.get("material_gaps", [])))
                + list(plan.get("candidate_quality_issues") or [])
            )
        ),
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
    if not statuses or all(status in {"not_applicable", "not_requested"} for status in statuses):
        return ModelCheck(status="not_applicable", model_id=model_id, detail="本次未请求完整分析，或模型链未被启用。")
    if "config_missing" in statuses:
        return ModelCheck(status="config_missing", model_id=model_id, detail="未配置DEEPSEEK_API_KEY，完整分析未完成。")
    if "provider_quota_exhausted" in statuses:
        return ModelCheck(status="provider_quota_exhausted", model_id=model_id, detail="模型供应商余额不足，本次完整分析未完成。")
    if "provider_region_opt_in_required" in statuses:
        return ModelCheck(status="provider_region_opt_in_required", model_id=model_id, detail="OpenCode Go 当前 DeepSeek 版本需要在工作区开启中国托管模型，本次完整分析未完成。")
    if "provider_unavailable" in statuses:
        return ModelCheck(status="provider_unavailable", model_id=model_id, detail="模型供应商拒绝或暂时不可用，本次完整分析未完成。")
    if "provider_unreachable" in statuses:
        return ModelCheck(status="provider_unreachable", model_id=model_id, detail="模型调用失败，已关闭后续AI草稿链。")
    if "model_transfer_revoked" in statuses:
        return ModelCheck(status="model_transfer_revoked", model_id=model_id, detail="逐案模型传输同意已撤销或无法确认，已关闭后续AI调用。")
    if "MODEL_OUTPUT_INVALID" in statuses or "EVIDENCE_BUNDLE_EMPTY" in statuses:
        return ModelCheck(status="MODEL_OUTPUT_INVALID", model_id=model_id, detail="模型输出或证据包未通过硬校验，完整分析未完成。")
    if any(step.failure_code == "DEMO_FALLBACK" for step in steps):
        return ModelCheck(
            status="demo_fallback",
            model_id="demo-deterministic-v1",
            detail="外部模型未作为比赛演示前置条件；本次使用绑定证据的确定性演示草稿。",
        )
    completed = [step for step in steps if step.status == "completed"]
    completed_roles = {step.role for step in completed}
    if completed_roles == {"challenge", "counter", "review"} and len(completed) >= 3:
        response_material = "".join(step.response_sha256 or "" for step in completed)
        return ModelCheck(
            status="model_success",
            model_id=model_id,
            duration_ms=sum(step.duration_ms or 0 for step in completed),
            response_sha256=hashlib.sha256(response_material.encode("utf-8")).hexdigest(),
            detail="三Agent完成结构化输出；数字、来源和人工处理未交给模型决定。",
        )
    return ModelCheck(status="MODEL_OUTPUT_INVALID", model_id=model_id, detail="AI草稿链没有形成完整可验证结果。")


_PROVIDER_RUNTIME_FAILURE_STATUSES = frozenset({
    "provider_quota_exhausted",
    "provider_region_opt_in_required",
    "provider_unavailable",
    "provider_unreachable",
})
_PROVIDER_RUNTIME_FAILURE_CODES = frozenset({
    "MODEL_PROVIDER_AUTH_FAILED",
    "MODEL_PROVIDER_BALANCE_EXHAUSTED",
    "MODEL_PROVIDER_REGION_OPT_IN_REQUIRED",
    "MODEL_PROVIDER_RATE_LIMITED",
    "MODEL_PROVIDER_REJECTED",
    "MODEL_PROVIDER_TIMEOUT",
    "MODEL_PROVIDER_UNREACHABLE",
})


def _record_provider_run_feedback(steps: list[AgentStep], *, model_id: str, base_url: str) -> None:
    """将本次链路的真实 provider 结果反馈给就绪熔断，保留 schema 的 failure_code。"""
    # AgentStep 没有 error_code 字段，且实际失败状态不是笼统的 failed；先记录
    # 失败再考虑成功，避免 challenge 成功但 counter/review 失败时误报当前可用。
    failed_step = next(
        (
            step
            for step in steps
            if step.failure_stage == "provider"
            and step.status in _PROVIDER_RUNTIME_FAILURE_STATUSES
            and step.failure_code in _PROVIDER_RUNTIME_FAILURE_CODES
        ),
        None,
    )
    if failed_step is not None:
        record_provider_failure(failed_step.failure_code or "MODEL_PROVIDER_REJECTED", failed_step.detail or "", base_url=base_url)
        return
    if any(step.status == "completed" and step.provider_call_performed for step in steps):
        record_provider_success(model_id=model_id, base_url=base_url)


def _enrich_model_check(model_check: ModelCheck, results: list[RuleResult]) -> ModelCheck:
    """把三 Agent 的实际 token、耗时和执行方式汇总到运行级状态。"""
    steps = [step for result in results for step in result.agent_steps]
    provider_steps = [step for step in steps if step.provider_call_performed]
    calls = sum(max(1, step.provider_call_count) for step in provider_steps)
    execution_mode = model_check.execution_mode
    if any(step.failure_code == "DEMO_FALLBACK" for step in steps):
        execution_mode = "deterministic_backup"
    elif calls and model_check.status == "model_success":
        execution_mode = "external_live"
    elif calls and model_check.status not in {"model_success", "demo_fallback"}:
        # A provider/network/semantic failure is an attempted external run, but
        # never a completed model result.  Keep the UI from presenting it as
        # "not applicable" while preserving the exact failure code per role.
        execution_mode = "unavailable"
    return model_check.model_copy(update={
        "input_tokens": sum(step.input_tokens or 0 for step in provider_steps),
        "output_tokens": sum(step.output_tokens or 0 for step in provider_steps),
        "duration_ms": sum(step.duration_ms or 0 for step in provider_steps),
        "provider_call_count": calls,
        "execution_mode": execution_mode,
    })


def _cached_run_for_new_request(
    cached: RunResponse,
    *,
    run_id: str,
    context: dict[str, Any],
    sources: list[dict[str, Any]],
    source_validation: dict[str, Any],
    evidence_bundle: dict[str, Any],
    retrievals: list[dict[str, Any]],
    cache_key_hash: str,
) -> RunResponse:
    """复用已验证的模型结果，但为本次请求生成新的可追溯运行编号。"""

    def rebind_run_ids(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: run_id if key == "run_id" else rebind_run_ids(child)
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [rebind_run_ids(child) for child in value]
        return deepcopy(value)

    results: list[RuleResult] = []
    for result in cached.rule_results:
        steps: list[AgentStep] = []
        for step in result.agent_steps:
            output = step.output
            if output is not None:
                output = output.model_copy(update={"run_id": run_id})
            steps.append(
                step.model_copy(
                    update={
                        "output": output,
                        "provider_call_performed": False,
                        "provider_call_count": 0,
                    }
                )
            )
        results.append(
            result.model_copy(
                update={
                    "agent_steps": steps,
                    "ai_draft": rebind_run_ids(result.ai_draft) if result.ai_draft else None,
                }
            )
        )
    cached_context = deepcopy(context)
    cached_context["cache_source_run_id"] = cached.run_id
    cached_context["cache_source_model_usage"] = {
        "input_tokens": cached.input_tokens,
        "output_tokens": cached.output_tokens,
        "duration_ms": cached.duration_ms,
        "provider_call_count": cached.provider_call_count,
    }
    cached_context["external_model_call_performed"] = False
    model_check = cached.model_check.model_copy(
        update={
            "execution_mode": "external_cached",
            "cache_hit": True,
            "cache_key_hash": cache_key_hash,
            "input_tokens": 0,
            "output_tokens": 0,
            "duration_ms": 0,
            "provider_call_count": 0,
        }
    )
    flattened_steps = [step for result in results for step in result.agent_steps]
    completed_roles = {step.role for step in flattened_steps if step.status == "completed"}
    return cached.model_copy(
        update={
            "run_id": run_id,
            "context": cached_context,
            "source_validation": deepcopy(source_validation),
            "sources": deepcopy(sources),
            "rule_results": results,
            "evidence_bundle": deepcopy(evidence_bundle),
            "retrievals": deepcopy(retrievals),
            "final_ai_draft": rebind_run_ids(cached.final_ai_draft) if cached.final_ai_draft else None,
            "model_check": model_check,
            "execution_mode": "external_cached",
            "cache_hit": True,
            "cache_key_hash": cache_key_hash,
            "model_id": model_check.model_id,
            "prompt_version": PROMPT_VERSION,
            "input_tokens": 0,
            "output_tokens": 0,
            "duration_ms": 0,
            "provider_call_count": 0,
            "parent_run_id": context.get("parent_run_id"),
            "ai_analysis_route": cached.ai_analysis_route or cached_context.get("ai_analysis_route") or "risk_candidate",
            "ai_analysis_conclusion": cached.ai_analysis_conclusion or cached.model_check.analysis_conclusion,
            "ai_execution_requested": True,
            "ai_execution_completed": completed_roles == {"challenge", "counter", "review"},
            "agent_steps": flattened_steps,
        }
    )


def _model_privacy_scan_payload(
    evidence_bundle: dict[str, Any],
    *,
    context: dict[str, Any],
    rule_results: list[RuleResult],
) -> list[dict[str, Any]]:
    """扫描模型会收到的证据与分析上下文，排除纯服务端技术标识。"""

    payload = [
        {key: value for key, value in row.items() if key != "evidence_id"}
        for row in compact_evidence_bundle(evidence_bundle)
    ]
    # 补充资料的结构化详情和说明可能参与本地重算或后续提示词扩展，
    # 同样执行失败关闭扫描；文件名、哈希和证据编号不进入该扫描载荷。
    payload.extend(
        {
            "field_label": row.get("field_label"),
            "details": row.get("details"),
            "excerpt": row.get("excerpt"),
            "note": row.get("note"),
        }
        for row in evidence_bundle.get("supplement_evidence", [])
        if isinstance(row, dict)
    )
    payload.append(
        minimize_model_context({
            "company_name": context.get("company_name"),
            "ticker": context.get("ticker"),
            "current_year": context.get("current_year"),
            "selected_rule_ids": context.get("selected_rule_ids", []),
            "industry_gate": context.get("industry_gate"),
            "rule_results": [
                {
                    "rule_id": result.rule_id,
                    "status": result.status,
                    "metrics": result.metrics,
                    "risk_card": result.risk_card,
                }
                for result in rule_results
            ],
        })
    )
    return payload


def _analysis_input_fingerprint(
    *,
    context: dict[str, Any],
    rule_results: list[RuleResult],
    evidence_bundle: dict[str, Any],
) -> str:
    """把规则参数、确定性结果与实际模型证据共同纳入缓存身份。"""

    payload = {
        "engine_version": context.get("engine_version"),
        "r1_version": context.get("r1_version"),
        "r2_version": context.get("r2_version"),
        "configured_parameters": context.get("configured_parameters"),
        "analysis_route": context.get("ai_analysis_route"),
        "rule_results": [
            result.model_dump(
                mode="json",
                exclude={"agent_steps", "ai_draft", "ai_recommendation", "ai_analysis_conclusion"},
            )
            for result in rule_results
        ],
        "model_evidence": compact_evidence_bundle(evidence_bundle),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _current_evidence_bundle(
    *,
    context: dict[str, Any],
    rule_bundle: dict[str, Any],
    rag_error: str | None,
) -> dict[str, Any]:
    """把当前请求的完整证据元数据写入响应；缓存只复用模型结论。"""

    return {
        "schema_version": "evidence_bundle_v2",
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
        "case_id": context["case_id"],
        "field_evidence": deepcopy(rule_bundle.get("field_evidence") or []),
        "rag_evidence": deepcopy(rule_bundle.get("rag_evidence") or []),
        "supplement_evidence": deepcopy(rule_bundle.get("supplement_evidence") or []),
        "procedure_evidence": deepcopy(rule_bundle.get("procedure_evidence") or []),
        "knowledge_evidence": deepcopy(rule_bundle.get("knowledge_evidence") or []),
        "evidence_gaps": deepcopy(rule_bundle.get("evidence_gaps") or []),
        "assertion_evidence_procedure_matrix": deepcopy(context.get("assertion_evidence_procedure_matrix") or []),
        "evidence_fitness_boundary": context.get("evidence_fitness_boundary"),
        "evidence_fitness_violations": deepcopy(context.get("evidence_fitness_violations") or []),
        "numeric_claim_trace": deepcopy(context.get("numeric_claim_trace") or {}),
        "anti_confirmation": deepcopy(context.get("anti_confirmation") or {}),
        "rag_error": rag_error,
        "prescreen_summary": deepcopy(context.get("prescreen_summary")),
    }


def _format_evidence_gap(item: Any) -> str:
    """把资料缺口统一成可读短句，禁止 Python dict repr 泄漏到页面或报告。"""

    if isinstance(item, dict):
        question_id = str(item.get("question_id") or item.get("problem_id") or "").strip()
        gap_type = str(item.get("type") or item.get("status") or item.get("label") or "资料缺口").strip()
        message = str(item.get("message") or item.get("detail") or item.get("reason") or "待回查").strip()
        prefix = f"{question_id} · " if question_id else ""
        return f"{prefix}{gap_type}：{message}"
    return str(item).strip()


def _dedupe_gap_messages(items: list[Any], limit: int = 8) -> list[str]:
    """按问题编号、类型和消息去重，保持第一次出现的证据顺序。"""

    seen: set[tuple[str, str, str]] = set()
    output: list[str] = []
    for item in items:
        text = _format_evidence_gap(item)
        if not text:
            continue
        if isinstance(item, dict):
            key = (
                str(item.get("question_id") or item.get("problem_id") or ""),
                str(item.get("type") or item.get("status") or item.get("label") or ""),
                str(item.get("message") or item.get("detail") or item.get("reason") or text),
            )
        else:
            key = ("", "", text)
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
        if len(output) >= limit:
            break
    return output


def _demo_agent_steps(
    *,
    run_id: str,
    rule_result: RuleResult,
    evidence_bundle: dict[str, Any],
    model_id: str,
    analysis_route: str = "risk_candidate",
) -> list[AgentStep]:
    """在比赛模式提供可重复的证据绑定草稿，避免外部模型服务阻塞现场演示。"""

    evidence_rows = [
        item
        for key in ("field_evidence", "rag_evidence", "supplement_evidence", "procedure_evidence")
        for item in evidence_bundle.get(key, [])
        if isinstance(item, dict) and item.get("evidence_id")
    ]
    evidence_ids = list(dict.fromkeys(str(item["evidence_id"]) for item in evidence_rows))[:5]
    fallback_ids = evidence_ids
    support_status = "supported" if fallback_ids else "unverified_hypothesis"
    gaps = _dedupe_gap_messages(
        list((rule_result.risk_card or {}).get("data_gaps") or [])
        + list(rule_result.source_validation.get("issues") or [])
        + list(evidence_bundle.get("evidence_gaps") or [])
    )
    requested = list(dict.fromkeys(
        str(item) for item in ((rule_result.risk_card or {}).get("requested_materials") or []) if str(item).strip()
    ))[:8]
    observation = str((rule_result.risk_card or {}).get("observation") or "规则已完成确定性预筛，结果仍需人工回看证据。")
    status = "defer" if gaps else "retain"
    recommendation = "defer" if status == "defer" else "retain"
    route_conclusion = {
        "risk_candidate": "risk_candidate",
        "negative_confirmation": "no_trigger_confirmed",
        "industry_review": "industry_boundary",
        "evidence_gap_review": "data_gap",
    }.get(analysis_route, "additional_procedure_required")
    outputs: list[AgentStep] = []
    role_text = {
        "challenge": "挑战：检查候选是否有证据支持；演示模式不把缺失资料解释成负面结论。",
        "counter": "反向：列出正常解释和仍需补充的公开资料，避免单一指标直接定性。",
        "review": "复核：汇总当前证据、数据缺口和下一步人工回页动作。",
    }
    for role in ("challenge", "counter", "review"):
        output = AgentOutput(
            schema_version="agent_output_v2",
            run_id=run_id,
            role=role,
            rule_id=rule_result.rule_id,
            analysis_conclusion=route_conclusion,
            status=(
                "defer" if analysis_route == "negative_confirmation" and role in {"challenge", "counter"}
                else "candidate" if role == "challenge" and analysis_route == "risk_candidate"
                else "defer" if role == "counter" and gaps
                else status
            ),
            claims=[AgentClaim(text=observation[:500], evidence_ids=fallback_ids, support_status=support_status)],
            normal_explanations=[
                AgentClaim(
                    text="公开年报候选和演示检索片段只能形成待核查提示，不替代专业判断。",
                    evidence_ids=fallback_ids,
                    support_status=support_status,
                )
            ],
            data_gaps=gaps,
            requested_materials=requested,
            reason_for_status=f"竞赛演示使用确定性模板；AI路线为 {analysis_route}；正式采用前仍需真人回查文档、口径、金额单位和页码。",
            draft_title="竞赛演示：证据绑定的待核查建议" if role == "review" else "",
            draft_observation=observation[:1000] if role == "review" else "",
            ai_recommendation=recommendation,
        )
        outputs.append(
            AgentStep(
                role=role,
                status="completed",
                detail=role_text[role] + f" 未调用外部模型；当前路线：{analysis_route}。",
                model_id=model_id,
                prompt_version="demo-deterministic-v1",
                response_sha256=hashlib.sha256(output.model_dump_json().encode("utf-8")).hexdigest(),
                failure_code="DEMO_FALLBACK",
                output=output,
            )
        )
    return outputs


def _demo_external_model_enabled() -> bool:
    """竞赛演示默认尝试真实外部模型；显式关闭时才使用确定性备用。"""

    return os.getenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL", "true").strip().lower() in {"1", "true", "yes", "on"}


RAG_QUESTIONS_BY_RULE = {
    "R1": ("RAG-Q1", "RAG-Q2", "RAG-Q5", "RAG-Q6"),
    "R2": ("RAG-Q3", "RAG-Q4", "RAG-Q6"),
}

AI_ROUTE_LABELS = {
    "risk_candidate": "候选风险核查",
    "negative_confirmation": "未触发结果复核",
    "industry_review": "行业口径复核",
    "evidence_gap_review": "数据缺口复核",
}


def _select_ai_analysis_route(
    rule_results: list[RuleResult],
    *,
    specialized_rule: str | None = None,
    industry_gate: dict[str, Any] | None = None,
) -> str:
    """把程序筛查结果映射为 AI 的工作任务，不改变程序筛查结论。"""
    if any(result.status == "candidate" for result in rule_results):
        return "risk_candidate"
    if specialized_rule or (industry_gate or {}).get("fit_level") in {"conditional", "not_applicable", "unknown"}:
        return "industry_review"
    if any(
        result.status == "DATA_GAP"
        or result.source_validation.get("issues")
        or (result.risk_card or {}).get("data_gaps")
        for result in rule_results
    ):
        return "evidence_gap_review"
    return "negative_confirmation"


def _procedure_evidence_for_ai(rule_results: list[RuleResult], context: dict[str, Any]) -> list[dict[str, Any]]:
    """为没有字段或检索命中的案例提供可引用的程序结果卡，不猜测财务金额。"""
    rows: list[dict[str, Any]] = []
    for result in rule_results:
        card = result.risk_card or {}
        evidence_id = f"PROC-{result.rule_id}-{context.get('current_year') or 'NA'}"
        rows.append(
            {
                "evidence_id": evidence_id,
                "evidence_type": "deterministic_rule_result",
                "field_label": f"{result.rule_id}程序筛查结果",
                "value": result.status,
                "unit": "status",
                "document_id": None,
                "source_file": None,
                "pdf_page": None,
                "locator": "程序计算结果卡；不代表原文事实或人工确认",
                "excerpt": str(card.get("observation") or f"{result.rule_id} 返回状态 {result.status}")[:500],
                "review_status": "program_calculated",
            }
        )
    return rows


def _run_rag_for_analysis(
    *,
    context: dict[str, Any],
    rule_results: list[RuleResult],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """按四条 AI 路线检索全部选定规则；无命中是证据缺口，不是跳过模型理由。"""
    active_rules = list(dict.fromkeys(result.rule_id for result in rule_results))
    if not active_rules:
        return [], [], [], None
    route = str(context.get("ai_analysis_route") or "risk_candidate")
    route_questions = {
        "risk_candidate": ("RAG-Q1", "RAG-Q2", "RAG-Q5", "RAG-Q6"),
        "negative_confirmation": ("RAG-Q1", "RAG-Q2", "RAG-Q5", "RAG-Q6"),
        "industry_review": ("RAG-Q3", "RAG-Q4", "RAG-Q6", "RAG-Q1"),
        "evidence_gap_review": ("RAG-Q5", "RAG-Q6", "RAG-Q1"),
    }
    try:
        identity_payload = context.get("request_identity") if isinstance(context.get("request_identity"), dict) else {}
        owner_tenant_id = str(identity_payload.get("tenant_id") or "").strip() or None
        remote_case = _case_record(context["case_id"], tenant_id=owner_tenant_id)
        if remote_case is None:
            raise RuntimeError("RAG 对应案例不存在")
        # Supabase 模式下 active RAG snapshot 是跨实例唯一权威；本机 SQLite
        # 可能仍停留在旧版本，不能把旧片段混进当前运行或把远端 snapshot ID
        # 写到本机结果上。只有完全离线的 local 模式才读取本机索引。
        # 15 案竞赛发布优先使用随清单冻结的 seed snapshot；本机若残留旧
        # FAISS 目录也不能改变公开运行的证据版本。完整本地/内部案例仍走
        # 本机索引和 singleflight prepare_index。
        use_seed_snapshot = bool(_competition_demo_enabled() and remote_case.get("demo_rag_evidence"))
        local_case = (
            _materialized_case_for_resolved(remote_case, tenant_id=owner_tenant_id)
            if not supabase_enabled() and not use_seed_snapshot
            else None
        )
        if local_case is not None:
            prepare_index(WORKSPACE_ROOT, case_id=context["case_id"], force=False)
        retrievals: list[dict[str, Any]] = []
        rag_evidence: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        seen_evidence: set[str] = set()
        for rule_id in active_rules:
            allowed_questions = RAG_QUESTIONS_BY_RULE.get(rule_id, RAG_QUESTIONS_BY_RULE["R1"])
            questions = tuple(
                question_id
                for question_id in route_questions.get(route, allowed_questions)
                if question_id in allowed_questions
            ) or allowed_questions
            for question_id in questions:
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
                    else retrieve_seed_rag(
                        remote_case,
                        query="",
                        question_id=question_id,
                        t0=context["t0"],
                        rule_id=rule_id,
                        top_k=2,
                    )
                    if _competition_demo_enabled() and remote_case.get("demo_rag_evidence")
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


def _run_rag_for_candidates(**kwargs: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """Backward-compatible test/extension alias; full analysis now covers every route."""

    return _run_rag_for_analysis(**kwargs)


def _run_knowledge_retrieval(
    *,
    context: dict[str, Any],
    rule_results: list[RuleResult],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    """检索登记的规范、监管和行业最小语料，并把可用边界写入运行上下文。

    与案例年报 RAG 不同，本函数返回的是来源台账的可复验命中；其资料用途由
    claim_scope 限定，不能借由监管处罚或新闻片段生成当前企业的已证实事实。
    """
    try:
        entries, failure = load_knowledge_manifest(
            WORKSPACE_ROOT / "backend" / "knowledge_sources.manifest.json"
        )
        if failure is not None:
            return [], None, failure
        cutoff = knowledge_cutoff_date()
        summary = coverage_group_summary(entries, cutoff)
        if cutoff is None:
            return [], summary, "knowledge_cutoff_unconfirmed"
        active_rules = list(dict.fromkeys(result.rule_id for result in rule_results)) or ["R1"]
        categories = [
            "annual_report", "csrc_penalty", "exchange_inquiry",
            "accounting_standard", "auditing_standard", "tax_regulation",
            "industry_report", "news", "macro_indicator",
        ]
        request = build_retrieval_request(
            case_id=str(context.get("case_id") or ""),
            question_id=f"KB-{'-'.join(active_rules)}",
            source_categories=categories,
            as_of_date=str(context.get("t0") or cutoff),
            cutoff_date=cutoff,
            snapshot_id=knowledge_snapshot_id(),
            ticker=str(context.get("ticker") or "") or None,
            industry=str((context.get("industry_gate") or {}).get("industry") or "") or None,
        )
        request["company_name"] = str(context.get("company_name") or "")
        trace = retrieve_knowledge(entries, request, limit=8)
        if not trace:
            return [], summary, "knowledge_retrieval_empty"
        return trace, summary, None
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        return [], None, f"knowledge_retrieval_error:{type(error).__name__}"


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
    progress_callback: Callable[[str, str, str], None] | None = None,
    agent_step_callback: Callable[[str, str, str], None] | None = None,
) -> RunResponse:
    def _progress(stage: str, status: str, detail: str) -> None:
        if progress_callback is not None:
            try:
                progress_callback(stage, status, detail)
            except Exception:
                # 进度回调是旁路观察；它的异常不得阻断真实运行。
                pass

    def _forward_agent_steps(steps: list[AgentStep], live: bool) -> None:
        # live=True 时 run_agent_chain 已在每步结算时回调过，这里只补演示确定性
        # 草稿与未请求/未授权路径的状态，避免重复写阶段。
        if agent_step_callback is None:
            return
        for step in steps:
            if live:
                return
            suffix = f"（{step.failure_code}）" if step.failure_code else ""
            try:
                agent_step_callback(step.role, step.status, f"{step.detail}{suffix}")
            except Exception:
                pass

    def _notify_live_agent_step(role: str, step: AgentStep) -> bool:
        if agent_step_callback is None:
            return True
        suffix = f"（{step.failure_code}）" if step.failure_code else ""
        try:
            agent_step_callback(role, step.status, f"{step.detail}{suffix}")
        except Exception:
            pass
        return True

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
    cache_fill_owner = False
    cache_fill_event: threading.Event | None = None
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
                "r1_signoff_status": _r1_signoff_snapshot()["signoff_status"],
            },
        }
    )
    rule_results: list[RuleResult] = []
    sources_by_rule: dict[str, list[dict[str, Any]]] = {}
    industry_gate = context.get("industry_gate") or {}
    _progress("evidence_load", "running", "正在读取案例、字段证据与来源信息，并执行来源校验。")
    # context 与 sources 已由受控案例接口建立；此处完成的是可用于规则计算的
    # 已登记证据包载入，而不是把后续 RAG 检索提前标成已完成。
    _progress("evidence_load", "completed", f"案例证据载入完成：{len(sources)} 条已登记字段来源。")
    _progress("rule_calculation", "running", "行业闸门与 R1/R2 确定性计算执行中。")
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
    _progress("rule_calculation", "completed", f"行业闸门与确定性计算完成，共 {len(rule_results)} 条规则结果。")

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
            "blocked_candidate_count": prescreen_plan.get("blocked_candidate_count", 0),
            "candidate_quality_issues": prescreen_plan.get("candidate_quality_issues", []),
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
    field_evidence_ids = {
        str(row.get("evidence_id"))
        for row in public_sources
        if isinstance(row, dict) and row.get("evidence_id")
    }
    supplementary = [
        deepcopy(row)
        for row in (supplement_evidence or [])
        if not isinstance(row, dict)
        or not row.get("evidence_id")
        or str(row.get("evidence_id")) not in field_evidence_ids
    ]
    _reconcile_registered_context(rule_results, supplementary)
    ai_analysis_route = _select_ai_analysis_route(
        rule_results,
        specialized_rule=specialized_rule,
        industry_gate=industry_gate,
    )
    context["ai_analysis_route"] = ai_analysis_route
    context["ai_analysis_route_label"] = AI_ROUTE_LABELS.get(ai_analysis_route, ai_analysis_route)
    for result in rule_results:
        result.ai_analysis_route = ai_analysis_route
    procedure_evidence = _procedure_evidence_for_ai(rule_results, context)
    retrievals: list[dict[str, Any]] = []
    rag_evidence: list[dict[str, Any]] = []
    evidence_gaps: list[dict[str, Any]] = []
    knowledge_trace: list[dict[str, Any]] = []
    knowledge_summary: dict[str, Any] | None = None
    rag_error: str | None = None
    has_candidate_result = any(result.status == "candidate" for result in rule_results)
    if run_mode == "full_analysis" and context.get("model_transfer_allowed", False):
        _progress("knowledge_retrieval", "running", "正在检索案例原文与已登记知识来源。")
        retrievals, rag_evidence, evidence_gaps, rag_error = _run_rag_for_analysis(
            context=context,
            rule_results=rule_results,
        )
        if rag_error is None:
            _progress("knowledge_retrieval", "running", "正在检索已登记的准则、监管与行业知识来源。")
            knowledge_trace, knowledge_summary, knowledge_error = _run_knowledge_retrieval(
                context=context,
                rule_results=rule_results,
            )
            context["knowledge_retrieval_trace"] = knowledge_trace
            context["knowledge_source_ledger"] = [
                {
                    key: hit.get(key)
                    for key in (
                        "retrieval_id", "source_id", "document_id", "source_category",
                        "publisher", "published_at", "official_url", "locator",
                        "content_sha256", "claim_scope", "boundary", "snapshot_id",
                    )
                }
                for hit in knowledge_trace
            ]
            context["source_coverage_summary"] = knowledge_summary
            context["knowledge_snapshot_id"] = knowledge_snapshot_id()
            if knowledge_error is not None:
                rag_error = knowledge_error
                evidence_gaps.append(
                    {
                        "type": "knowledge_retrieval_unavailable",
                        "message": "知识库检索未完成；完整分析失败关闭，本次不调用外部模型。",
                        "detail": knowledge_error,
                    }
                )
                _progress("knowledge_retrieval", "failed", f"知识检索失败（{knowledge_error}）。")
            else:
                _progress("knowledge_retrieval", "completed", f"知识检索完成：{len(knowledge_trace)} 条可回查命中。")
        else:
            _progress("knowledge_retrieval", "failed", f"案例原文 RAG 检索失败（{rag_error}）。")
    else:
        context["knowledge_retrieval_trace"] = []
        context["knowledge_source_ledger"] = []
        try:
            _entries, _failure = load_knowledge_manifest(WORKSPACE_ROOT / "backend" / "knowledge_sources.manifest.json")
            context["source_coverage_summary"] = coverage_group_summary(_entries, knowledge_cutoff_date())
        except (OSError, TypeError, ValueError):
            context["source_coverage_summary"] = None
        context["knowledge_snapshot_id"] = knowledge_snapshot_id()
        _progress("knowledge_retrieval", "skipped", "本次未请求完整分析或未获模型传输许可，未运行知识检索。")
    if rag_error:
        evidence_gaps.append(
            {
                "type": "rag_unavailable",
                "message": "RAG检索未完成；完整分析失败关闭，本次不调用外部模型。",
                "detail": rag_error,
            }
        )

    rule_bundle = {
        "field_evidence": public_sources,
        "rag_evidence": rag_evidence,
        "supplement_evidence": supplementary,
        "procedure_evidence": procedure_evidence,
        "knowledge_evidence": knowledge_trace,
        "evidence_gaps": _dedupe_gap_messages(evidence_gaps, limit=16),
    }
    # 创新二：先把证据适配度和允许主张边界编译进 Agent 输入，
    # 后续 Agent 只能在这份带 fitness_class 的证据包上生成草稿。
    rule_bundle = annotate_evidence_bundle(rule_bundle)
    rule_result_dicts = [result.model_dump(mode="json") for result in rule_results]
    context["evidence_fitness_map"] = fitness_map_for_evidence(rule_bundle)
    context["evidence_fitness_boundary"] = (
        "current_entity_primary_evidence 可支持受边界限制的当前企业事实；"
        "authoritative_normative_basis 仅支持规范/程序依据；"
        "analogous_regulatory_or_industry_background 仅支持类比或待验证背景；"
        "unverified_background 不得进入最终事实主张。"
    )
    context["assertion_evidence_procedure_matrix"] = build_assertion_evidence_procedure_matrix(
        case_id=str(context.get("case_id") or ""),
        current_year=int(context.get("current_year") or 0),
        t0=str(context.get("t0") or "") or None,
        rule_ids=list(rule_ids),
        rule_results=rule_result_dicts,
        evidence_bundle=rule_bundle,
        knowledge_trace=knowledge_trace,
    )
    api_key, base_url, model_id = _model_settings()
    sensitive_findings = scan_sensitive_payload(
        _model_privacy_scan_payload(
            rule_bundle,
            context=context,
            rule_results=rule_results,
        )
    )
    context["privacy_scan"] = {
        "status": "blocked" if sensitive_findings else "passed",
        "finding_count": len(sensitive_findings),
        "findings": sensitive_findings,
        "external_model_scope": model_transmission_scope(),
    }
    # 只有本次确实准备调用外部模型时，隐私扫描命中才会阻断运行。
    # 非比赛模式默认走真实供应商；比赛模式则必须显式启用外呼开关。
    # 公开预筛与私有案例使用同一失败关闭判断，不能因路线类型绕过扫描。
    external_model_call_planned = bool(
        run_mode == "full_analysis"
        and context.get("model_transfer_allowed")
        and not context.get("force_deterministic_backup")
        and api_key
        and (not _competition_demo_enabled() or _demo_external_model_enabled())
    )
    context["external_model_call_planned"] = external_model_call_planned
    sensitive_data_blocked = bool(sensitive_findings and external_model_call_planned)
    model_input_fingerprint = _analysis_input_fingerprint(
        context=context,
        rule_results=rule_results,
        evidence_bundle=rule_bundle,
    )
    context["model_input_fingerprint"] = model_input_fingerprint
    reservation_id: str | None = None
    cache_key_hash: str | None = None
    ai_requested = (
        run_mode == "full_analysis"
        and bool(context.get("model_transfer_allowed"))
        and not bool(context.get("force_deterministic_backup"))
    )
    if run_mode == "calculation_only":
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="not_requested" if result.status == "candidate" else "not_applicable",
                    detail="本次为仅计算预检，未运行RAG和三Agent。",
                )
            ]
        model_check = _model_check_from_results(rule_results, enabled=False, model_id=model_id)
        run_completeness = "incomplete_calculation_only"
    elif specialized_rule and (
        not context.get("ai_model_all_cases")
        or not context.get("model_transfer_allowed")
    ):
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
    elif all(result.status in {"NOT_APPLICABLE", "INDUSTRY_UNKNOWN"} for result in rule_results) and (
        not context.get("ai_model_all_cases")
        or not context.get("model_transfer_allowed")
    ):
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
                    status="model_transfer_not_allowed",
                    detail="本次模型传输未获许可，只能完成本地计算预检。",
                )
            ]
        model_check = ModelCheck(
            status="model_transfer_not_allowed",
            model_id=model_id,
            detail=str(context.get("model_transfer_block_reason") or "本次模型传输未获有效许可，完整分析主链已如实关闭。"),
        )
        run_completeness = "incomplete_model_transfer_not_allowed"
    elif sensitive_data_blocked:
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="sensitive_data_blocked",
                    detail="模型传输前隐私扫描命中高风险信息，已阻断外部模型调用；本地确定性结果仍保留。",
                    failure_stage="policy",
                    failure_code="SENSITIVE_DATA_BLOCKED",
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
    elif rag_error:
        for result in rule_results:
            result.agent_steps = [
                AgentStep(
                    role="challenge",
                    status="rag_failed",
                    detail="RAG准备或检索失败，本次未调用模型。",
                )
            ]
        model_check = ModelCheck(status="not_attempted_rag_failure", model_id=model_id, detail="RAG失败，完整分析未完成。")
        run_completeness = "incomplete_rag_failure"
    else:
        if ai_requested and _demo_external_model_enabled() and api_key:
            supplement_hash = hashlib.sha256(
                json.dumps(supplementary, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest() if supplementary else None
            cache_key_hash = build_cache_key(
                case_id=str(context.get("case_id") or ""),
                year=int(context.get("current_year") or 0),
                rule_ids=list(rule_ids),
                source_snapshot_id=str(context.get("source_snapshot_id") or SOURCE_SNAPSHOT_ID),
                prompt_version=PROMPT_VERSION,
                model_id=model_id,
                supplement_hash=supplement_hash,
                input_fingerprint=model_input_fingerprint,
            )
            cached_payload = _public_model_ledger().get_cache(cache_key_hash)
            if cached_payload:
                try:
                    cached_response = _cached_run_for_new_request(
                        RunResponse.model_validate(cached_payload),
                        run_id=run_id,
                        context=context,
                        sources=public_sources,
                        source_validation=_base_source_validation(
                            [issue for result in rule_results for issue in result.source_validation.get("issues", [])]
                        ),
                        evidence_bundle=_current_evidence_bundle(
                            context=context,
                            rule_bundle=rule_bundle,
                            rag_error=rag_error,
                        ),
                        retrievals=retrievals,
                        cache_key_hash=cache_key_hash,
                    )
                except Exception:
                    cached_response = None
                if cached_response is not None:
                    _require_worker_lease(http_request)
                    save_run(WORKSPACE_ROOT, cached_response)
                    return cached_response
            cache_fill_owner, cache_fill_event = _public_model_ledger().acquire_cache_fill(cache_key_hash)
            if not cache_fill_owner:
                # 同一输入已经有访客在执行真实模型；等待其写入 24 小时缓存，
                # 避免重复消耗 token。超时后才允许后续请求重新尝试。
                cache_fill_event.wait(timeout=125)
                cached_payload = _public_model_ledger().get_cache(cache_key_hash)
                if cached_payload:
                    try:
                        cached_response = _cached_run_for_new_request(
                            RunResponse.model_validate(cached_payload),
                            run_id=run_id,
                            context=context,
                            sources=public_sources,
                            source_validation=_base_source_validation(
                                [issue for result in rule_results for issue in result.source_validation.get("issues", [])]
                            ),
                            evidence_bundle=_current_evidence_bundle(
                                context=context,
                                rule_bundle=rule_bundle,
                                rag_error=rag_error,
                            ),
                            retrievals=retrievals,
                            cache_key_hash=cache_key_hash,
                        )
                    except Exception:
                        cached_response = None
                    if cached_response is not None:
                        _require_worker_lease(http_request)
                        save_run(WORKSPACE_ROOT, cached_response)
                        return cached_response
                cache_fill_owner, cache_fill_event = _public_model_ledger().acquire_cache_fill(cache_key_hash)
                if not cache_fill_owner:
                    raise HTTPException(status_code=409, detail="相同输入的真实模型分析正在执行，请稍后重试。")
        # A full-analysis request is quota-controlled even when the provider is
        # currently unconfigured.  This preserves the public-demo safety
        # boundary for repeated attempts that would otherwise bypass the
        # limiter and also keeps the legacy ``check_model=true`` contract
        # deterministic in local validation.  Explicit deterministic backups
        # never consume a live-model reservation.
        if (
            ai_requested
            and run_mode == "full_analysis"
            and not context.get("force_deterministic_backup")
            and _public_demo_enabled()
            and _demo_external_model_enabled()
        ):
            try:
                reservation_id = _enforce_public_model_quota(http_request)
            except Exception:
                if cache_fill_owner and cache_key_hash:
                    _public_model_ledger().complete_cache_fill(cache_key_hash, cache_fill_event)
                    cache_fill_owner = False
                raise
        route_priority = {
            "risk_candidate": lambda item: item.status == "candidate",
            "negative_confirmation": lambda item: item.status not in {"candidate", "DATA_GAP"},
            "industry_review": lambda item: item is specialized_result or item.status in {"INDUSTRY_UNKNOWN", "NOT_APPLICABLE"},
            "evidence_gap_review": lambda item: item.status == "DATA_GAP" or bool(item.source_validation.get("issues")) or bool((item.risk_card or {}).get("data_gaps")),
        }
        primary_selector = route_priority.get(ai_analysis_route, lambda _item: False)
        primary_result = next((item for item in rule_results if primary_selector(item)), rule_results[0] if rule_results else None)
        analysis_context = {
            "case_id": context.get("case_id"),
            "company_name": context.get("company_name"),
            "ticker": context.get("ticker"),
            "current_year": context.get("current_year"),
            "selected_rule_ids": context.get("selected_rule_ids", []),
            "screening_status": screening_status,
            "rule_results": [
                {
                    "rule_id": item.rule_id,
                    "status": item.status,
                    "screening_status": item.screening_status,
                    "risk_card": item.risk_card,
                    "metrics": item.metrics,
                }
                for item in rule_results
            ],
            "industry_gate": industry_gate,
            "evidence_gap_count": len(evidence_gaps),
            # 命中仅为程序/背景指引；Agent 仍不能把 KB-* 作为当前企业事实证据。
            "knowledge_retrieval_trace": [
                {
                    key: hit.get(key)
                    for key in (
                        "retrieval_id", "source_id", "source_category", "publisher",
                        "published_at", "locator", "excerpt", "claim_scope", "boundary",
                    )
                }
                for hit in context.get("knowledge_retrieval_trace", [])
            ],
            "assertion_evidence_procedure_matrix": context.get("assertion_evidence_procedure_matrix", []),
            "evidence_fitness_boundary": context.get("evidence_fitness_boundary"),
        }
        for result in rule_results:
            result.ai_analysis_route = ai_analysis_route
            result.agent_steps = []
        if primary_result is not None:
            # RAG 片段在主链中显式进入 Agent；比赛模式默认尝试真实模型，
            # 但可由 AUDITTRACE_DEMO_USE_EXTERNAL_MODEL=false 明确切回确定性备用。
            demo_fallback_chain = bool(
                context.get("force_deterministic_backup")
                or (_competition_demo_enabled() and not _demo_external_model_enabled())
            )
            _progress("agent_collaboration", "running", f"三角色协作链执行中（{'演示确定性草稿' if demo_fallback_chain else '真实外部模型'}）。")
            primary_result.agent_steps = (
                _demo_agent_steps(
                    run_id=run_id,
                    rule_result=primary_result,
                    evidence_bundle=rule_bundle,
                    model_id="demo-deterministic-v1",
                    analysis_route=ai_analysis_route,
                )
                if demo_fallback_chain
                else run_agent_chain(
                    run_id=run_id,
                    rule_result=primary_result,
                    evidence_bundle=rule_bundle,
                    enabled=True,
                    api_key=api_key,
                    base_url=base_url,
                    model_id=model_id,
                    before_role=model_recheck,
                    analysis_route=ai_analysis_route,
                    analysis_context=analysis_context,
                    on_step=_notify_live_agent_step,
                )
            )
            _forward_agent_steps(primary_result.agent_steps, live=not demo_fallback_chain)
            # 真实运行反向反馈：记录供应商成功或失败熔断
            if not context.get("force_deterministic_backup") and not (_competition_demo_enabled() and not _demo_external_model_enabled()):
                _record_provider_run_feedback(
                    primary_result.agent_steps,
                    model_id=model_id,
                    base_url=base_url,
                )
            review_step = next(
                (step for step in primary_result.agent_steps if step.role == "review" and step.status == "completed" and step.output),
                None,
            )
            if review_step and review_step.output:
                primary_result.ai_recommendation = review_step.output.ai_recommendation or review_step.output.status
                primary_result.ai_draft = review_step.output.model_dump(mode="json")
        model_check = _model_check_from_results(rule_results, enabled=True, model_id=model_id).model_copy(
            update={"analysis_route": ai_analysis_route}
        )
        partial_prescreen = bool(
            prescreen_plan
            and (
                prescreen_plan.get("missing_fields")
                or prescreen_plan.get("skipped_rules")
                or any(result.status == "DATA_GAP" for result in rule_results)
            )
        )
        if context.get("force_deterministic_backup"):
            run_completeness = (
                "complete_demo_fallback_with_gaps" if partial_prescreen
                else "complete_demo_fallback"
            )
        elif context.get("ai_model_all_cases") and model_check.status == "demo_fallback":
            run_completeness = (
                "complete_public_prescreen_with_gaps" if prescreen_plan and partial_prescreen
                else "complete_public_prescreen" if prescreen_plan
                else "complete_demo_fallback_with_gaps" if partial_prescreen
                else "complete_demo_fallback"
            )
        elif context.get("ai_model_all_cases") and model_check.status == "model_success":
            run_completeness = (
                "complete_public_prescreen_with_gaps" if prescreen_plan and partial_prescreen
                else "complete_public_prescreen" if prescreen_plan
                else "complete_full_analysis_with_gaps" if partial_prescreen
                else "complete_full_analysis"
            )
        elif context.get("ai_model_all_cases"):
            run_completeness = (
                "incomplete_model_quota"
                if model_check.status == "provider_quota_exhausted"
                else "incomplete_model_chain_failed"
            )
        elif all(result.status in {"NOT_APPLICABLE", "INDUSTRY_UNKNOWN"} for result in rule_results):
            if industry_gate.get("fit_level") == "unknown":
                run_completeness = "complete_public_prescreen_industry_unknown" if prescreen_plan else "complete_rule_industry_unknown"
            else:
                run_completeness = "complete_public_prescreen_not_applicable" if prescreen_plan else "complete_rule_not_applicable"
        elif not has_candidate_result:
            run_completeness = (
                "complete_public_prescreen_with_gaps"
                if prescreen_plan and partial_prescreen
                else "complete_public_prescreen_no_candidate"
                if prescreen_plan
                else "complete_full_analysis_no_candidate"
            )
        elif model_check.status == "demo_fallback":
            run_completeness = (
                "complete_demo_fallback_with_gaps"
                if partial_prescreen
                else "complete_demo_fallback"
            )
        elif model_check.status == "model_success":
            run_completeness = "complete_public_prescreen_with_gaps" if partial_prescreen else "complete_full_analysis"
        else:
            run_completeness = (
                "incomplete_model_transfer_revoked"
                if model_check.status == "model_transfer_revoked"
                else "incomplete_model_quota"
                if model_check.status == "provider_quota_exhausted"
                else "incomplete_model_chain_failed"
            )

    model_check = _enrich_model_check(model_check, rule_results)
    context["external_model_call_performed"] = bool(model_check.provider_call_count)
    if ai_requested and model_check.execution_mode in {"external_live", "deterministic_backup"}:
        supplement_hash = hashlib.sha256(
            json.dumps(supplementary, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest() if supplementary else None
        cache_key_hash = build_cache_key(
            case_id=str(context.get("case_id") or ""),
            year=int(context.get("current_year") or 0),
            rule_ids=list(rule_ids),
            source_snapshot_id=str(context.get("source_snapshot_id") or SOURCE_SNAPSHOT_ID),
            prompt_version=PROMPT_VERSION,
            model_id=model_id,
            supplement_hash=supplement_hash,
            input_fingerprint=model_input_fingerprint,
        )
        model_check = model_check.model_copy(update={"cache_key_hash": cache_key_hash})
    if reservation_id:
        try:
            _public_model_ledger().settle(
                reservation_id,
                input_tokens=model_check.input_tokens or 0,
                output_tokens=model_check.output_tokens or 0,
            )
        except PublicModelQuotaError as error:
            model_check = model_check.model_copy(update={"status": "quota_exhausted", "execution_mode": "unavailable", "detail": str(error)})
            run_completeness = "incomplete_model_quota"
    route_default_conclusion = {
        "risk_candidate": "risk_candidate",
        "negative_confirmation": "no_trigger_confirmed",
        "industry_review": "industry_boundary",
        "evidence_gap_review": "data_gap",
    }.get(ai_analysis_route, "additional_procedure_required")
    review_conclusion = next(
        (
            step.output.analysis_conclusion
            for result in rule_results
            for step in result.agent_steps
            if step.role == "review" and step.status == "completed" and step.output and step.output.analysis_conclusion
        ),
        route_default_conclusion if ai_requested else None,
    )
    for result in rule_results:
        result.ai_analysis_conclusion = review_conclusion
    model_check = model_check.model_copy(update={"analysis_conclusion": review_conclusion})
    ai_recommendation = _aggregate_ai_recommendation(rule_results)
    final_items = [result.ai_draft for result in rule_results if result.ai_draft]
    context["model_attempt_history"] = [
        {
            "rule_id": result.rule_id,
            "role": step.role,
            "status": step.status,
            "failure_code": step.failure_code,
            "attempts": step.model_attempt_history,
        }
        for result in rule_results
        for step in result.agent_steps
        if step.model_attempt_history
    ]
    pending_evidence_review = any(
        "pending" in str(row.get("review_status") or row.get("source_review_status") or "").lower()
        for key in ("field_evidence", "rag_evidence", "supplement_evidence")
        for row in rule_bundle.get(key, [])
        if isinstance(row, dict)
    )
    context["pending_evidence_review"] = pending_evidence_review
    # G7：运行上下文扩充结构化成因说明（向后兼容，新字段只增不改）。
    # 这里重载台账仅用于最终导出展示；真实检索已在 Agent 之前完成。
    knowledge_entries: list[dict[str, Any]] = []
    try:
        knowledge_entries, _knowledge_failure = load_knowledge_manifest(
            WORKSPACE_ROOT / "backend" / "knowledge_sources.manifest.json"
        )
        if context.get("source_coverage_summary") is None:
            context["source_coverage_summary"] = coverage_group_summary(knowledge_entries, knowledge_cutoff_date())
    except (OSError, ValueError, TypeError):
        context["source_coverage_summary"] = None
    context["knowledge_snapshot_id"] = knowledge_snapshot_id()
    try:
        _procedure_map = json.loads(
            (WORKSPACE_ROOT / "backend" / "audit_procedure_map.json").read_text(encoding="utf-8")
        )
        context["audit_procedure_map_version"] = _procedure_map.get("schema_version")
        context["audit_procedures"] = _procedure_map.get("procedures") or []
    except (OSError, json.JSONDecodeError, ValueError):
        context["audit_procedure_map_version"] = None
        context["audit_procedures"] = []
    try:
        context["provider_readiness_snapshot"] = get_provider_snapshot().to_dict()
    except Exception:  # noqa: BLE001 - 冗余快照失败不影响运行
        context["provider_readiness_snapshot"] = None
    # 监管/准则证据：展示来源台账中的官方登记条目（登记级，不代表本案例已逐条回查）。
    active_knowledge_entries = active_source_entries(knowledge_entries, knowledge_cutoff_date())
    if active_knowledge_entries:
        context["regulatory_evidence"] = [
            {
                key: entry.get(key)
                for key in (
                    "source_id", "source_category", "publisher", "title",
                    "document_id", "sha256", "official_url", "published_at",
                )
            }
            for entry in active_knowledge_entries
            if entry.get("source_category")
            in {"accounting_standard", "auditing_standard", "tax_regulation", "csrc_penalty", "exchange_inquiry"}
        ]
        context["regulatory_evidence_boundary"] = (
            "活跃来源台账登记级条目；本次知识检索的用途边界见 knowledge_retrieval_trace，仍须人工回查官方原文与页码。"
        )
    else:
        context["regulatory_evidence"] = []
        context["regulatory_evidence_boundary"] = "知识库台账尚未接入监管与准则来源。"
    # 补充证据差异：只有在补充/续分析路径才非空；不覆盖原年报字段。
    context["supplement_delta"] = (
        {
            "supplement_evidence_count": len(supplementary),
            "parent_run_id": context.get("parent_run_id"),
            "recommendation_change": context.get("recommendation_change"),
            "boundary": "补充资料仅进入当前案例证据空间，不覆盖原年报字段；变化仍须真人复核。",
        }
        if supplementary
        else None
    )
    # 创新二：对每个 Agent 输出再次执行证据适配度边界校验。
    # 违规主张降级为待验证假设，并保留违规清单；不删除原始模型响应或哈希。
    fitness_map = fitness_map_for_evidence(rule_bundle)
    fitness_violations: list[dict[str, Any]] = []
    for result in rule_results:
        for step in result.agent_steps:
            if step.output is None:
                continue
            output_payload = step.output.model_dump(mode="json")
            violations = enforce_claim_boundaries(output_payload.get("claims") or [], fitness_map)
            output_payload["evidence_fitness_violations"] = violations
            if violations:
                fitness_violations.extend(
                    [{"rule_id": result.rule_id, "role": step.role, **item} for item in violations]
                )
            step.output = AgentOutput.model_validate(output_payload)
        if result.ai_draft:
            violations = enforce_claim_boundaries(result.ai_draft.get("claims") or [], fitness_map)
            result.ai_draft["evidence_fitness_violations"] = violations
            if violations:
                fitness_violations.extend(
                    [{"rule_id": result.rule_id, "role": "final_draft", **item} for item in violations]
                )
    context["evidence_fitness_violations"] = fitness_violations

    # 创新四：记录是否执行了反确认偏差搜索；不强迫模型凑出正常解释。
    counter_explanations: list[dict[str, Any]] = []
    for result in rule_results:
        for step in result.agent_steps:
            if step.role == "counter" and step.output is not None:
                counter_explanations.extend(
                    [item.model_dump(mode="json") for item in step.output.normal_explanations]
                )
    context["anti_confirmation"] = build_anti_confirmation_record(
        route=ai_analysis_route if ai_requested else None,
        rag_evidence=rag_evidence,
        counter_explanations=counter_explanations,
        review_recommendation=ai_recommendation,
    )

    # 创新三：仅对 Agent 的自然语言字段做数字主张回查，不把 run_id、哈希和元数据
    # 误当成财务数字。年份使用当前案例已知报告年度作为上下文来源。
    numeric_text_parts: list[str] = []
    for result in rule_results:
        draft = result.ai_draft or {}
        numeric_text_parts.extend(
            [
                str(draft.get("draft_title") or ""),
                str(draft.get("draft_observation") or ""),
                str(draft.get("reason_for_status") or ""),
            ]
        )
        numeric_text_parts.extend(
            str(item.get("text") or "")
            for key in ("claims", "normal_explanations")
            for item in (draft.get(key) or [])
            if isinstance(item, dict)
        )
    configured = context.get("configured_parameters") or {}
    numeric_additional_sources = [
        {
            "source_type": "configured_parameter",
            "source_ref": f"R1.{key}",
            "value": configured.get(key),
            "label": key,
        }
        for key in ("r1_gap_threshold", "r1_strong_gap_threshold", "r1_absolute_threshold")
        if isinstance(configured.get(key), (int, float))
    ]
    numeric_gate = validate_numeric_claims(
        "\n".join(text for text in numeric_text_parts if text),
        rule_results=rule_result_dicts,
        evidence_bundle=rule_bundle,
        knowledge_trace=knowledge_trace,
        allowed_years={
            int(context.get("current_year") or 0) - offset
            for offset in range(0, 4)
            if int(context.get("current_year") or 0) - offset > 0
        },
        additional_sources=numeric_additional_sources,
    )
    context["numeric_claim_trace"] = numeric_gate
    if numeric_gate.get("key_unverified_count") and model_check.status == "model_success":
        # 生成模型成功不等于数字主张可发布；保持真实模型状态，但禁止完整性伪装。
        run_completeness = "incomplete_numeric_claims"
    final_ai_draft = (
        {
            "schema_version": "final_ai_draft_v2",
            "ai_assisted": True,
            "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
            "items": final_items,
            "boundary": (
                "AI草稿只形成待核查建议；本次字段或原文片段仍含待人工回页候选，正式认定与发布由人工决定。"
                if pending_evidence_review
                else "AI草稿只形成待核查建议；正式认定与发布由人工决定。"
            ),
        }
        if final_items
        else None
    )
    all_issues = [issue for result in rule_results for issue in result.source_validation.get("issues", [])]
    evidence_bundle = annotate_evidence_bundle(_current_evidence_bundle(
        context=context,
        rule_bundle=rule_bundle,
        rag_error=rag_error,
    ))
    all_agent_steps = [step for result in rule_results for step in result.agent_steps]
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
        execution_mode=model_check.execution_mode,
        model_id=model_check.model_id,
        prompt_version=PROMPT_VERSION if model_check.execution_mode == "external_live" else None,
        input_tokens=model_check.input_tokens or 0,
        output_tokens=model_check.output_tokens or 0,
        duration_ms=model_check.duration_ms or 0,
        provider_call_count=model_check.provider_call_count,
        cache_hit=model_check.cache_hit,
        cache_key_hash=model_check.cache_key_hash,
        parent_run_id=context.get("parent_run_id"),
        ai_analysis_route=ai_analysis_route if run_mode == "full_analysis" else "not_requested",
        ai_analysis_conclusion=review_conclusion if run_mode == "full_analysis" else None,
        ai_execution_requested=ai_requested,
        ai_execution_completed=bool(
            {step.role for step in all_agent_steps if step.status == "completed"}
            == {"challenge", "counter", "review"}
        ),
        agent_steps=all_agent_steps,
    )
    try:
        # 公开演示的运行详情必须引用 Supabase 当前窗口；不能把本地历史
        # 台账（尤其是 fallback/cache/test）嵌入本次结果，造成质量口径漂移。
        if _public_demo_enabled() or demo_task_supabase_enabled():
            runtime_snapshot = _runtime_quality_snapshot(_model_settings()[2])
            response.context["model_quality_snapshot"] = runtime_snapshot or {
                "status": "unmeasured",
                "window_id": "RUNTIME-UNAVAILABLE-LOCAL",
                "model_id": _model_settings()[2],
                "sample_count": 0,
                "success_count": 0,
                "success_rate": None,
                "threshold": 0.8,
                "alert": False,
                "alert_kind": None,
                "source": "no_runtime_supabase_ledger",
                "boundary": "公开演示尚无 Supabase 运行时质量窗口；本地历史台账不作为当前生产成功率。",
            }
        else:
            response.context["model_quality_snapshot"] = record_external_run(WORKSPACE_ROOT, response) or quality_snapshot(WORKSPACE_ROOT, model_id=_model_settings()[2])
    except (OSError, TypeError, ValueError):
        response.context["model_quality_snapshot"] = {
            "status": "unavailable",
            "alert": False,
            "alert_kind": "ledger_unavailable",
            "boundary": "真实模型成功率台账暂不可读取；未改变本次运行结论。",
        }
    # 最终本地/远程落盘前再确认一次；即使租约恰在最后一个模型角色后丢失，
    # 旧 worker 也不能发布运行或覆盖新持有者的 checkpoint。
    _require_worker_lease(http_request)
    save_run(WORKSPACE_ROOT, response)
    if cache_key_hash and model_check.status == "model_success" and _demo_external_model_enabled():
        _public_model_ledger().put_cache(cache_key_hash, response.model_dump(mode="json"))
        if cache_fill_owner:
            _public_model_ledger().complete_cache_fill(cache_key_hash, cache_fill_event)
    elif cache_fill_owner and cache_key_hash:
        _public_model_ledger().complete_cache_fill(cache_key_hash, cache_fill_event)
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
def health(http_request: Request) -> HealthResponse:
    api_key, _, model_id = _model_settings()
    readiness = _model_readiness(http_request)
    provider_info = readiness.get("provider") or {}
    release = _release_fact_snapshot(readiness=readiness)
    return HealthResponse(
        service_status="ready",
        model_status="configured" if api_key else "config_missing",
        model_id=model_id,
        full_analysis_ready=bool(readiness["full_analysis_ready"]),
        full_analysis_reason_code=str(readiness["full_analysis_reason_code"]),
        full_analysis_message=str(readiness["full_analysis_message"]),
        deterministic_backup_available=bool(readiness["deterministic_backup_available"]),
        source_snapshot_id=SOURCE_SNAPSHOT_ID,
        detail="服务可用；模型配置状态不等于已经完成真实三Agent运行。"
        f" 当前就绪判断：{readiness['full_analysis_message']}",
        provider_status=provider_info.get("status"),
        provider_reason_code=provider_info.get("reason_code"),
        provider_checked_at=provider_info.get("checked_at"),
        provider_source=provider_info.get("source"),
        provider_ready=bool(
            provider_info.get("status") == "ready"
            and str(provider_info.get("source") or "") in {"probe", "live_run"}
        ),
        model_execution_ready=bool(readiness.get("full_analysis_ready")),
        competition_release_ready=bool(release.get("competition_release_ready")),
    )


def _r1_signoff_snapshot() -> dict[str, Any]:
    """返回 R1 专业口径签字的统一只读快照，供状态、导出与页面共用。"""
    return load_signoff_status()


def _release_fact_snapshot(
    *, readiness: dict[str, Any] | None = None, runtime_quality: dict[str, Any] | None = None
) -> dict[str, Any]:
    """从受跟踪发布记录形成可公开核验的事实快照。"""

    path = WORKSPACE_ROOT / "backend" / "release_records" / "current_release.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        state = {}
    state = state if isinstance(state, dict) else {}
    manifest_path = WORKSPACE_ROOT / "backend" / "competition_demo_cases.json"
    manifest_hash = None
    manifest_count = None
    manifest_source_head = None
    manifest_hash_algorithm = str(((state.get("demo") or {}).get("manifest_hash_algorithm") or "raw_bytes_v1")).strip().lower()
    try:
        raw_manifest = manifest_path.read_bytes()
        if manifest_hash_algorithm == CANONICAL_MANIFEST_HASH_ALGORITHM:
            manifest_hash = manifest_sha256(manifest_path)
        elif manifest_hash_algorithm == "raw_bytes_v1":
            manifest_hash = hashlib.sha256(raw_manifest).hexdigest()
        parsed_manifest = json.loads(raw_manifest.decode("utf-8"))
        if isinstance(parsed_manifest, dict):
            manifest_count = parsed_manifest.get("case_count")
            manifest_source_head = parsed_manifest.get("source_head")
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    expected_manifest_hash = str(((state.get("demo") or {}).get("manifest_sha256") or "")).lower() or None
    manifest_status = (
        "verified"
        if manifest_hash and expected_manifest_hash and manifest_hash == expected_manifest_hash
        else "blocked"
    )
    eval_dashboard = load_evaluation_dashboard(WORKSPACE_ROOT)
    signoff = load_signoff_status()
    readiness = readiness or {}
    configured_model_id = _model_settings()[2]
    deployment_commit = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or None
    release_evidence_head = os.getenv("AUDITTRACE_RELEASE_EVIDENCE_HEAD") or None
    materialized_source_head = ((state.get("demo") or {}).get("materialized_source_head") or manifest_source_head)
    eval_pointer_status = str(eval_dashboard.get("current_pointer_status") or "legacy")
    human_scoring_status = str(eval_dashboard.get("human_scoring_status") or "pending")
    ready_checks = {
        "manifest_hash": manifest_status == "verified" and manifest_count == 15,
        "model_id": str(readiness.get("model_id") or ((state.get("model") or {}).get("model_id") or "")) == configured_model_id,
        # provider probe 是无 Token 的 /models 或 /user/balance 检查，不能与
        # paid_probe_performed（真实三 Agent 业务调用）混为一谈；新的生产 B3
        # 另由 fresh_production_b3 门禁单独确认。
        "provider_probe": bool((readiness.get("provider") or {}).get("status") == "ready")
        and str((readiness.get("provider") or {}).get("source") or "") == "probe",
        "evaluation_pointer": eval_pointer_status == "valid",
        "signoff": signoff.get("signoff_status") == "captain_approved_for_competition_demo",
        "human_scoring": human_scoring_status not in {"pending", "pending_human_scoring", "pending_human_scoring_and_fresh_model_runs"},
        "fresh_production_b3": bool((state.get("release_readiness") or {}).get("fresh_production_b3_completed")),
    }
    return {
        "schema_version": str(state.get("schema_version") or "audittrace_release_record_v1"),
        "release_id": state.get("release_id"),
        "release_status": state.get("release_status") or "blocked",
        "model": {
            "model_id": str(readiness.get("model_id") or ((state.get("model") or {}).get("model_id") or configured_model_id)),
            "provider_label": readiness.get("provider_label") or (state.get("model") or {}).get("provider_label"),
        },
        "heads": {
            "deployment_commit": deployment_commit,
            "release_evidence_head": release_evidence_head,
            "materialized_source_head": materialized_source_head,
            "demo_manifest_sha256": manifest_hash,
        },
        "manifest": {
            "path": "backend/competition_demo_cases.json",
            "case_count": manifest_count,
            "source_head": manifest_source_head,
            "hash_algorithm": manifest_hash_algorithm,
            "sha256_expected": expected_manifest_hash,
            "sha256_status": manifest_status,
        },
        "evaluation": {
            "evaluation_id": eval_dashboard.get("evaluation_id"),
            "pointer_status": eval_pointer_status,
            "pointer_reason": eval_dashboard.get("current_pointer_reason"),
            "human_scoring_status": human_scoring_status,
            "quality_window": eval_dashboard.get("quality_window"),
            "runtime_quality_window": runtime_quality,
        },
        "signoff": {
            "status": signoff.get("signoff_status"),
            "signoff_id": signoff.get("signoff_id"),
            "record": "backend/release_records/r1_signoff_20260825_r2.json",
        },
        "task_continuity": _demo_task_continuity(),
        "competition_release_ready": all(ready_checks.values()),
        "ready_checks": ready_checks,
        "boundary": "配置存在、探测通过和历史评估均不等于新的竞赛发布批准；人工评分和最终批准为空时保持 pending。",
    }


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
    rag_cases = [
        seed_rag_status(case)
        if _competition_demo_enabled() and case.get("demo_rag_evidence") and _materialized_case_for_resolved(case, tenant_id=None) is None
        else rag_status(WORKSPACE_ROOT, case["case_id"])
        for case in cases
    ]
    api_key, _, model_id = _model_settings()
    live_acceptance = registered.get("live_model_acceptance") if isinstance(registered, dict) else None
    readiness = _model_readiness(http_request)
    demo_backup_mode = _competition_demo_enabled() and bool(readiness["deterministic_backup_available"])
    model_execution_mode = (
        "external_live"
        if readiness["full_analysis_ready"]
        else "deterministic_backup"
        if demo_backup_mode
        else "unavailable"
    )
    quota_snapshot = readiness.get("quota")
    runtime_quality = _runtime_quality_snapshot(model_id)
    release_snapshot = _release_fact_snapshot(readiness=readiness, runtime_quality=runtime_quality)
    return _with_ai_notice({
        **registered,
        # PROJECT_STATUS.json 是历史登记和团队状态的兼容输入；公开接口的
        # 当前发布事实必须以受跟踪 release snapshot 为准，避免旧的模型、HEAD
        # 或评估数字在顶层覆盖本轮整改后的实时判断。
        "current_release": release_snapshot,
        "readiness_contract_version": "model_readiness_v1",
        "full_analysis_ready": bool(readiness["full_analysis_ready"]),
        "full_analysis_reason_code": str(readiness["full_analysis_reason_code"]),
        "full_analysis_message": str(readiness["full_analysis_message"]),
        "deterministic_backup_available": bool(readiness["deterministic_backup_available"]),
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
            "provider_kind": readiness.get("provider_kind") or "deepseek_direct",
            "provider_label": readiness.get("provider_label") or "DeepSeek 官方直连",
            "provider_host": readiness.get("provider_host") or "api.deepseek.com",
            "execution_mode": model_execution_mode,
            "full_analysis_ready": bool(readiness["full_analysis_ready"]),
            "full_analysis_reason_code": str(readiness["full_analysis_reason_code"]),
            "full_analysis_message": str(readiness["full_analysis_message"]),
            "next_action_code": str(readiness.get("next_action_code") or "ready"),
            "paid_probe_performed": bool(readiness.get("paid_probe_performed", False)),
            "last_runtime_failure_code": readiness.get("last_runtime_failure_code"),
            "deterministic_backup_available": bool(readiness["deterministic_backup_available"]),
            "public_access": bool(_competition_demo_enabled()),
            "quota": quota_snapshot,
            "last_verified_live_run": {
                "run_id": live_acceptance.get("run_id"),
                "model_id": live_acceptance.get("model_id") or model_id,
                "completed_at": live_acceptance.get("completed_at"),
                "completed_roles": live_acceptance.get("completed_roles", 0),
            } if isinstance(live_acceptance, dict) and live_acceptance.get("result") == "model_success" else None,
            "frozen_release_quality_window": registered.get("model_quality_alert") if isinstance(registered, dict) else None,
            "runtime_quality_window": runtime_quality,
            "boundary": "配置存在不代表真实完整运行已经验收。",
        },
        "demo_mode": {
            "enabled": _competition_demo_enabled(),
            "shared_public": _public_demo_enabled(),
            "login_required": False if _competition_demo_enabled() else supabase_enabled(),
            "supplement_policy": "public_sample_material" if _competition_demo_enabled() else "authorized_private_material",
            "boundary": "竞赛演示仅展示产品思路；账号、多租户和生产保密流程未启用。" if _competition_demo_enabled() else "正式工程边界。",
        },
        "persistence": configured_persistence(),
        "release": release_snapshot,
        "deployment": {
            "commit": os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or None,
            "deployment_commit": os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or None,
            "release_evidence_head": os.getenv("AUDITTRACE_RELEASE_EVIDENCE_HEAD") or None,
            "materialized_source_head": release_snapshot.get("heads", {}).get("materialized_source_head"),
            "demo_manifest_sha256": release_snapshot.get("heads", {}).get("demo_manifest_sha256"),
            "branch": os.getenv("RENDER_GIT_BRANCH") or os.getenv("GIT_BRANCH") or None,
            "service": os.getenv("RENDER_SERVICE_NAME") or os.getenv("RENDER_SERVICE_ID") or None,
            "source": "render_runtime_environment" if os.getenv("RENDER_GIT_COMMIT") else "local_runtime_environment",
        },
        "catalog": {**catalog_state, "seed": seed_catalog_summary(WORKSPACE_ROOT)},
        "auth": {
            "authenticated": bool(identity and not identity.is_local),
            "tenant_id": identity.tenant_id if identity and not identity.is_local else None,
        },
        "signoff": _r1_signoff_snapshot(),
    })


def _local_rag_status_for(case: dict[str, Any], *, tenant_id: str | None) -> dict[str, Any]:
    """本地持久化下的 RAG 状态统一解析：竞赛种子优先于本机旧索引。"""

    # 15 案公开演示的冻结片段是发布事实源；即使工作区恰好留有旧 FAISS
    # 目录，也不能让命名空间或历史缓存改变 bootstrap 的发布状态。
    if _competition_demo_enabled() and case.get("demo_rag_evidence"):
        return seed_rag_status(case)
    local_case = _materialized_case_for_resolved(case, tenant_id=tenant_id)
    if local_case is not None:
        return rag_status(WORKSPACE_ROOT, str(case["case_id"]).upper())
    return {"status": "not_built"}


def _demo_bootstrap_rag_status(case_id: str) -> dict[str, Any]:
    """演示启动快照的逐案 RAG 就绪解析；复用正式状态逻辑且不抛出异常。

    Supabase 持久化部署不逐案访问远端，避免一次启动快照放大成
    15 次跨实例读取；该场景返回 unknown 由前端按“需团队处理”显示。
    """

    case = _case_record(str(case_id).upper(), tenant_id=None)
    if case is None:
        return {"status": "unavailable", "reason_code": "case_not_registered"}
    if supabase_enabled():
        return {"status": "unknown", "reason_code": "supabase_persistence_active"}
    try:
        return _local_rag_status_for(case, tenant_id=None)
    except Exception:  # noqa: BLE001 - 启动快照不允许因单案异常整体失败
        return {"status": "unknown", "reason_code": "rag_status_read_failed"}


@app.get("/api/demo/bootstrap")
def get_demo_bootstrap(http_request: Request) -> dict[str, Any]:
    """竞赛演示启动快照：15 案白名单、精选顺序、就绪状态一次返回。

    只读聚合既有登记事实；manifest 缺失或不一致时返回发布阻断
    原因码，前端据此停留在“演示资源未就绪”，不进入 ready。
    """

    manifest, failure = load_demo_manifest()
    if manifest is None:
        return _with_ai_notice(blocked_bootstrap_payload(failure))
    status_path = WORKSPACE_ROOT / "PROJECT_STATUS.json"
    try:
        registered = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        registered = {}
    versions = registered.get("versions") if isinstance(registered.get("versions"), dict) else {}
    model_readiness = _model_readiness(http_request)
    payload = build_bootstrap_payload(
        manifest,
        model_readiness=model_readiness,
        versions=versions,
        rag_status_resolver=_demo_bootstrap_rag_status,
    )
    payload["capabilities"]["onsite_live_sample"] = bool(
        _onsite_live_sample_enabled() and not _public_demo_enabled() and not supabase_enabled()
    )
    payload["capabilities"]["structured_exports"] = ["json", "table", "print_pdf"]
    # 多源审计知识底座：只汇总来源台账的登记事实，不返回正文。
    knowledge_entries, _knowledge_failure = load_knowledge_manifest(
        WORKSPACE_ROOT / "backend" / "knowledge_sources.manifest.json"
    )
    payload["knowledge_base"] = coverage_group_summary(knowledge_entries, knowledge_cutoff_date())
    # 公开演示只展示当前发布定义的运行时窗口。不能把本地历史
    # model-quality.json 的最后十条记录误当成生产 Supabase 窗口。
    model_id = _model_settings()[2]
    runtime_quality = _runtime_quality_snapshot(model_id)
    if runtime_quality is not None:
        payload["model_quality"] = runtime_quality
    else:
        payload["model_quality"] = {
            "status": "unmeasured",
            "window_id": "RUNTIME-UNAVAILABLE-LOCAL",
            "model_id": model_id,
            "sample_count": 0,
            "success_count": 0,
            "success_rate": None,
            "threshold": 0.8,
            "alert": False,
            "alert_kind": None,
            "source": "no_runtime_supabase_ledger",
            "boundary": "公开演示尚无 Supabase 运行时质量窗口；本地历史台账不作为当前生产成功率。",
        }
    # 审计程序映射：静态合同，版本与边界随快照返回。
    try:
        procedure_map = json.loads(
            (WORKSPACE_ROOT / "backend" / "audit_procedure_map.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        procedure_map = {"schema_version": None, "procedures": []}
    payload["audit_procedure_map"] = procedure_map
    # 发布事实与演示资源状态分开返回：bootstrap 可 ready 不代表 provider、评估或
    # 人工签字已经达到发布门禁，前端必须按 release.competition_release_ready 展示。
    runtime_quality = _runtime_quality_snapshot(_model_settings()[2])
    payload["runtime_quality_window"] = runtime_quality
    payload["release"] = _release_fact_snapshot(readiness=model_readiness, runtime_quality=runtime_quality)
    payload["task_continuity"] = _demo_task_continuity()
    return _with_ai_notice(payload)


@app.get("/api/cases")
def get_cases(http_request: Request, summary: bool = False, http_response: Response = None) -> dict[str, Any]:
    identity, visible_cases, catalog_state = _visible_case_records(http_request)
    if http_response is not None:
        http_response.headers["Cache-Control"] = (
            "public, max-age=300, stale-while-revalidate=86400"
            if _competition_demo_enabled()
            else "private, no-store"
        )
    cases = (
        [_public_case_summary(case) for case in visible_cases]
        if summary
        else [_public_case(case) for case in visible_cases]
    )
    if summary:
        # 摘要接口只服务案例选择器；避免把每个请求都重复发送鉴权、边界
        # 和 AI 声明长文本，保证即使开发机残留历史临时案例也保持轻量。
        return {
            "schema_version": "case_list_summary_v1",
            "cases": cases,
        }
    return _with_ai_notice({
        "schema_version": "case_list_v1",
        "cases": cases,
        "catalog": {**catalog_state, "seed": seed_catalog_summary(WORKSPACE_ROOT)},
        "auth": {
            "authenticated": identity is not None and not identity.is_local,
            "tenant_id": identity.tenant_id if identity and not identity.is_local else None,
        },
        "boundary": (
            "竞赛演示案例与补充资料均按公开样例处理；来源快照变化后仍须重新核验。"
            if _competition_demo_enabled()
            else "公开案例可匿名读取；内部案例只展示给所属租户成员。来源快照变化后仍须重新核验。"
        ),
    })


@app.get("/api/evaluations/current")
def current_evaluation() -> dict[str, Any]:
    """公开只读评估页只返回已冻结的真实进度和结果。"""
    return _with_ai_notice(load_evaluation_dashboard(WORKSPACE_ROOT))


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
    _reject_shared_demo_uploads()
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
def get_case_detail(case_id: str, http_request: Request, http_response: Response = None) -> dict[str, Any]:
    normalized = case_id.upper()
    tenant_id = _identity_tenant(http_request)
    case = _case_record(normalized, tenant_id=tenant_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    authorize_case_access(http_request, case)
    if http_response is not None:
        http_response.headers["Cache-Control"] = (
            "public, max-age=300, stale-while-revalidate=86400"
            if _competition_demo_enabled() and is_public_case(case)
            else "private, no-store"
        )
    local_rows = _materialized_financial_rows(case, tenant_id=tenant_id)
    rows = [
        _public_source(row, private=not is_public_case(case))
        for row in annotate_financial_field_rows_quality(
            local_rows if local_rows is not None else case.get("financial_fields", [])
        )
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

    _reject_shared_demo_mutation("保存字段真人确认或修正")
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
    """正式运行入口：固定案例与现场任务统一走这里，保持单套主链。"""
    return _run_rules_impl(request, http_request)


def _run_rules_impl(request: RunRequest, http_request: Request, *, progress_callback: Callable[[str, str, str], None] | None = None, agent_step_callback: Callable[[str, str, str], None] | None = None) -> RunResponse:
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
    context["force_deterministic_backup"] = bool(request.force_deterministic_backup)
    if request.force_deterministic_backup:
        context["continuation_mode"] = "explicit_deterministic_backup"
    context["ai_model_all_cases"] = request.run_mode == "full_analysis"
    # 外部模型调用在公网模式必须有真实登录身份；匿名用户仍可完成公开确定性预筛，
    # 但不会把项目级许可误当作用户级模型授权。
    original_model_transfer_allowed = bool(context.get("model_transfer_allowed"))
    model_authorized = (
        True
        if request.force_deterministic_backup
        else authorize_model_transfer(http_request, case)
        if supabase_enabled()
        else original_model_transfer_allowed
    )
    model_recheck: Callable[[str], bool] | None = None
    if not model_authorized:
        context["model_transfer_allowed"] = False
        context["model_transfer_auth_required"] = True
        context["model_transfer_block_reason"] = (
            "公网模型调用需要当前案例有效同意；匿名公开预筛不上传证据片段。"
            if supabase_enabled()
            else "案例 manifest 未允许外部模型传输，只完成本地确定性预检。"
        )
    elif request.force_deterministic_backup:
        context["model_transfer_allowed"] = True
        context["model_transfer_scope"] = "仅在本地生成确定性备用草稿；不发生外部模型传输。"
    elif _competition_demo_enabled() and original_model_transfer_allowed:
        # 演示模式只使用案例已有的公开来源许可，不替案例清单补造授权。
        context["model_transfer_scope"] = "公开样例字段、来源元数据和 RAG 片段；不上传整本 PDF。"
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
        supplement_evidence=[],
        model_recheck=model_recheck,
        progress_callback=progress_callback,
        agent_step_callback=agent_step_callback,
    )


@app.post("/api/runs/{run_id}/deterministic-backup", response_model=RunResponse)
def deterministic_backup_run(run_id: str, http_request: Request) -> RunResponse:
    """对失败的真实模型运行创建独立、明确标注的确定性备用子运行。"""
    stored = _load_stored_run(run_id, owner_tenant_id=_identity_tenant(http_request))
    if stored is None:
        raise HTTPException(status_code=404, detail="未找到原始运行记录。")
    if not str(stored.run.run_completeness or "").startswith("incomplete_"):
        raise HTTPException(status_code=409, detail="只有未完成的真实模型运行可以生成备用分析。")
    context = stored.run.context
    try:
        request = RunRequest(
            case_id=str(context.get("case_id") or ""),
            current_year=int(context.get("current_year") or context.get("t0", "0")[:4]),
            rule_ids=list(context.get("selected_rule_ids") or ["R1"]),
            run_mode="full_analysis",
            planned_materiality=(context.get("configured_parameters") or {}).get("planned_materiality"),
            force_deterministic_backup=True,
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=409, detail="原始运行缺少可恢复的案例或年度参数。") from error
    response = run_rules(request, http_request)
    response.context["parent_run_id"] = stored.run.run_id
    response.context["continuation_mode"] = "explicit_deterministic_backup"
    response.parent_run_id = stored.run.run_id
    response.execution_mode = "deterministic_backup"
    response.model_check = response.model_check.model_copy(update={"execution_mode": "deterministic_backup"})
    save_run(WORKSPACE_ROOT, response)
    return response


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


def _find_demo_seed_case(company_query: str) -> dict[str, Any] | None:
    """按股票代码或公司名定位比赛目录中的公开样例。"""

    query = str(company_query or "").strip().lower()
    if not query:
        return None
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for case in load_seed_cases(WORKSPACE_ROOT):
        values = {
            str(case.get("ticker") or "").strip().lower(),
            str(case.get("company_name") or "").strip().lower(),
            str(case.get("company_alias") or "").strip().lower(),
        }
        values.discard("")
        if query in values:
            exact.append(case)
        elif any(query in value or value in query for value in values):
            partial.append(case)
    if len(exact) == 1:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return None


def _execute_demo_seed_pipeline(task_id: str, payload: dict[str, Any], http_request: Request) -> None:
    """直接使用已校验公开种子完成 Demo 任务，不重复下载同一份年报。"""

    from .pipeline import _set_step

    task = load_task(WORKSPACE_ROOT, task_id)
    case = _find_demo_seed_case(str(payload.get("company_query") or ""))
    if task is None or case is None:
        if task is not None:
            mark_analysis_failure(WORKSPACE_ROOT, task_id, ValueError("演示目录中没有匹配的公开企业样例。"))
        return
    task["case_id"] = case["case_id"]
    task["company"] = {
        "company_name": case.get("company_name"),
        "ticker": case.get("ticker"),
        "org_id": case.get("org_id"),
    }
    _save_task(WORKSPACE_ROOT, task)
    try:
        for step_name, detail in (
            ("company_resolve", "已从比赛公开样例目录确认公司与股票代码。"),
            ("announcement_search", "已读取预校验的巨潮年报公告元数据。"),
            ("document_select", "已选定每年度登记的正式年报文档。"),
            ("download", "Demo 复用已登记公开快照，不重复下载整本 PDF。"),
            ("document_validate", "来源快照、文档编号和哈希已随种子构建时校验。"),
            ("case_register", "已绑定公开案例和可回查字段证据。"),
            ("rag_prepare", "已准备固定问题对应的公开 RAG 演示片段。"),
            ("rag_smoke_test", "已完成固定问题 RAG 演示烟测。"),
            ("field_extract", "已读取登记字段候选；缺口保持为数据缺口。"),
            ("field_validate", "来源字段回填和技术校验通过，专业复核仍保留。"),
        ):
            _set_step(WORKSPACE_ROOT, task, step_name, "passed", detail)
        report_years = [
            int(year)
            for year in (case.get("available_years") or case.get("available_report_years") or [])
            if str(year).isdigit()
        ]
        if not report_years:
            report_years = [
                int(document["report_year"])
                for document in case.get("documents", [])
                if str(document.get("report_year") or "").isdigit()
            ]
        current_year = max(report_years)
        analysis_mode = str(payload.get("analysis_mode") or "rag_only")
        run = run_rules(
            RunRequest(
                case_id=str(case["case_id"]),
                current_year=current_year,
                scene="审计计划",
                rule_ids=list(payload.get("rule_ids") or ["R1"]),
                run_mode="full_analysis" if analysis_mode == "full_analysis" else "calculation_only",
            ),
            http_request,
        )
        result = {
            "status": "ready_for_analysis",
            "case_id": case["case_id"],
            "company": {
                "company_name": case.get("company_name"),
                "ticker": case.get("ticker"),
                "org_id": case.get("org_id"),
            },
            "report_years": sorted(report_years, reverse=True),
            "documents": deepcopy(case.get("documents") or []),
            "rag": seed_rag_status(case),
            "field_extraction": {
                "status": case.get("financial_fields_status") or "passed_technical_with_gaps",
                "row_count": len(case.get("financial_fields") or []),
                "issues": deepcopy(case.get("material_gaps") or []),
                "rows": deepcopy(case.get("financial_fields") or []),
            },
            "industry_gate": deepcopy(case.get("industry_gate") or {}),
            "human_review_recommended": True,
        }
        task["result"] = result
        _save_task(WORKSPACE_ROOT, task)
        update_analysis_result(WORKSPACE_ROOT, task_id, run.model_dump(mode="json"))
        task = load_task(WORKSPACE_ROOT, task_id) or task
        _set_step(WORKSPACE_ROOT, task, "analysis_run", "passed", "公开样例已完成规则、RAG 和演示分析。", run_id=run.run_id, run_completeness=run.run_completeness)
    except Exception as error:
        mark_analysis_failure(WORKSPACE_ROOT, task_id, error)


@app.post("/api/pipelines/cninfo", status_code=202)
def create_cninfo_pipeline(
    request: CNInfoPipelineRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> dict[str, Any]:
    """输入企业后创建巨潮年报、校验、RAG和可选完整分析任务。"""

    if _competition_demo_enabled() and _public_demo_enabled() and not supabase_enabled():
        # 共享站只允许命中已冻结的公开种子；任意新企业会触发外网、PDF 解析和共享磁盘写入。
        if _find_demo_seed_case(request.company_query) is None:
            _reject_shared_demo_mutation("抓取或导入非内置企业")
    # 公网下载、解析和建库会消耗网络、CPU 与存储，必须绑定真实任务所有者；私有本地行为不变。
    require_authenticated(http_request) if supabase_enabled() else optional_authenticated(http_request)
    # 比赛模式优先命中 50 家公开种子，现场不因网络、下载或 PDF 解析波动失去
    # 主链；不在种子中的新企业仍保留原有巨潮实时搜索路径。
    task = create_task(WORKSPACE_ROOT, request.model_dump(mode="json"))
    if _competition_demo_enabled() and _find_demo_seed_case(request.company_query) is not None:
        background_tasks.add_task(_execute_demo_seed_pipeline, task["task_id"], task["request"], http_request)
        return _with_ai_notice(
            {
                "task_id": task["task_id"],
                "status": task["status"],
                "steps": task["steps"],
                "boundary": "已命中公开样例快照；流程不需要登录，不重复下载整本年报。",
            }
        )
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
    _reject_shared_demo_mutation("保存真人复核或导出批准")
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
    _reject_shared_demo_mutation("创建正式运行缓存")
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

    if _competition_demo_enabled():
        years = prepare_report_years(request.latest_year, request.years)
        seed = _find_demo_seed_case(request.company_query)
        seed_years = {
            int(year)
            for year in (seed or {}).get("available_report_years", [])
            if str(year).isdigit()
        }
        if not seed_years:
            seed_years = {
                int(document["report_year"])
                for document in (seed or {}).get("documents", [])
                if str(document.get("report_year") or "").isdigit()
            }
        match = (
            {
                "cache_state": "ready",
                "case_id": seed.get("case_id"),
                "ticker": seed.get("ticker"),
                "company_name": seed.get("company_name"),
                "report_years": sorted(seed_years, reverse=True),
                "rag_index_version": ((seed.get("seed_rag") or {}).get("index_version")),
                "source_fingerprint": seed.get("source_snapshot_id"),
                "storage_backend": "tracked_demo_seed",
            }
            if seed and set(years).issubset(seed_years) and request.cache_policy != "force_refresh"
            else None
        )
        return _with_ai_notice(
            {
                "schema_version": "catalog_resolve_v1",
                "company_query": request.company_query,
                "requested_years": years,
                "cache_hit": bool(match),
                "match": match,
                "bootstrap_synced": 0,
                "cache_policy": request.cache_policy,
                "reason": "tracked_demo_seed_ready" if match else "force_refresh_requested" if request.cache_policy == "force_refresh" else "snapshot_not_found_or_incomplete",
                "stale_match": None,
                "next_step": "直接读取公开样例字段与 RAG 并进入规则分析。" if match else "未命中；继续执行巨潮搜索、下载、校验和建库。",
            }
        )

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
    """为最多 51 家常用企业排队建立公开年报热缓存。"""

    _reject_shared_demo_mutation("创建批量预热任务")
    if str(request.analysis_mode) == "full_analysis":
        # 完整模型预热会触发真实供应商调用，不能作为公开访客按钮。
        # RAG-only 预热仍可走原有案例/租户边界，不消耗模型额度。
        _authorize_model_prewarm(http_request)
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
    if str(request.analysis_mode) == "full_analysis":
        http_request.state.model_batch_authorized = True
        http_request.state.model_batch_id = batch_id
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
        "model_prewarm": str(request.analysis_mode) == "full_analysis",
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

    _reject_shared_demo_mutation("强制刷新公开年报缓存")
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
        path = build_report(WORKSPACE_ROOT, stored, demo_preview=_competition_demo_enabled())
    except (ValueError, OSError, IOError) as error:
        raise HTTPException(status_code=409, detail=f"报告文档生成或读取异常：{error}") from error
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
        # 本地持久化下的状态解析与演示启动快照共用同一逻辑，避免两处口径漂移。
        return _with_ai_notice(_local_rag_status_for(case, tenant_id=tenant_id))
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
    if local_case is None and _competition_demo_enabled() and case.get("demo_rag_evidence"):
        return _with_ai_notice({**seed_rag_status(case), "rebuilt": False})
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
            # 公开 15 案始终以冻结 seed snapshot 为准；不能因为本机恰好有旧
            # 索引，就把 fresh namespace 的检索误判为“索引尚未构建”。
            if _competition_demo_enabled() and case.get("demo_rag_evidence"):
                record = retrieve_seed_rag(
                    case,
                    query=request.query,
                    t0=request.t0,
                    rule_id=request.rule_id,
                    top_k=request.top_k,
                    question_id=request.question_id,
                )
            else:
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
        record = get_retrieval(WORKSPACE_ROOT, retrieval_id) or (
            get_seed_retrieval(retrieval_id) if _competition_demo_enabled() else None
        )
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该检索日志。")
    case_id = str(record.get("case_id") or "").upper()
    if case_id:
        case = _case_record(case_id, tenant_id=tenant_id)
        if case is None:
            raise HTTPException(status_code=404, detail="检索对应案例不存在。")
        authorize_case_access(http_request, case)
    return _with_ai_notice(record)


_PUBLIC_SUPPLEMENT_SAMPLES: dict[str, dict[str, Any]] = {
    "aging": {
        "sample_id": "aging",
        "material_type": "应收账款账龄明细",
        "title": "应收账款账龄及逾期情况",
        "description": "公开演示样例：按账龄区间提供余额、逾期比例和客户集中度，供 R1 续分析回查。",
        "structured_json": {
            "aging_summary": {
                "under_90_days_ratio": 0.46,
                "90_to_180_days_ratio": 0.33,
                "over_180_days_ratio": 0.21,
                "overdue_ratio": 0.18,
                "customer_concentration_top5_ratio": 0.54,
            }
        },
    },
    "receipts": {
        "sample_id": "receipts",
        "material_type": "期后回款及银行流水摘要",
        "title": "期后回款及银行流水摘要",
        "description": "公开演示样例：提供 T0 后回款比例、已核对流水笔数及异常回款说明。",
        "structured_json": {
            "subsequent_receipts_summary": {
                "receipt_ratio": 0.63,
                "verified_receipt_ratio": 0.58,
                "bank_statement_checked_count": 12,
                "exception_count": 1,
            }
        },
    },
}


@app.get("/api/supplement-samples")
def supplement_samples() -> dict[str, Any]:
    """返回不含运行或访客数据的公开补充资料样例目录。"""

    return _with_ai_notice(
        {
            "schema_version": "supplement_samples_v1",
            "samples": [
                {
                    "sample_id": value["sample_id"],
                    "material_type": value["material_type"],
                    "title": value["title"],
                    "description": value["description"],
                    "field_keys": sorted(value["structured_json"]),
                }
                for value in _PUBLIC_SUPPLEMENT_SAMPLES.values()
            ],
            "boundary": "公开样例只用于竞赛演示，不代表真实公司资料或专业结论。",
        }
    )


@app.post("/api/supplements/from-sample")
def supplement_from_sample(payload: SupplementSampleRequest, http_request: Request) -> dict[str, Any]:
    """将公开样例绑定到已有父运行，生成可追溯的独立补充资料记录。"""

    sample = _PUBLIC_SUPPLEMENT_SAMPLES.get(str(payload.sample_id or "").strip().lower())
    if sample is None:
        raise HTTPException(status_code=404, detail="未找到该公开补充资料样例。")
    identity = require_authenticated(http_request)
    owner_tenant_id = str(identity.tenant_id or "").strip() or None if identity and not identity.is_local else None
    parent = _load_stored_run(payload.parent_run_id, owner_tenant_id=owner_tenant_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="父运行不存在，不能绑定补充资料。")
    parent_case = _case_record(str(parent.run.context.get("case_id") or ""), tenant_id=owner_tenant_id)
    if parent_case is None:
        raise HTTPException(status_code=404, detail="父运行对应案例不存在。")
    authorize_case_write(http_request, parent_case)
    context_t0 = str(parent.run.context.get("t0") or "")
    default_date = context_t0[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", context_t0[:10]) else f"{int(parent.run.context.get('current_year') or 2026)}-12-31"
    as_of_date = payload.as_of_date or default_date
    try:
        parsed_rules = list(dict.fromkeys(payload.bound_rule_ids or ["R1"]))
        structured = json.dumps(sample["structured_json"], ensure_ascii=False, sort_keys=True)
        record = create_supplement(
            WORKSPACE_ROOT,
            parent_run_id=payload.parent_run_id,
            material_type=sample["material_type"],
            authorized=True,
            desensitized=True,
            bound_rule_ids=parsed_rules,
            as_of_date=as_of_date,
            note=payload.note or sample["description"],
            filename=f"{sample['sample_id']}_public_demo.json",
            content=b"",
            structured_json=structured,
            tenant_id=owner_tenant_id,
            owner_user_id=identity.user_id if identity and not identity.is_local else None,
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if supabase_enabled() and owner_tenant_id:
        _persist_supplement_record_remote(record, owner_tenant_id)
    return _with_ai_notice({**record, "sample_id": sample["sample_id"], "sample_title": sample["title"], "sample_payload": sample["structured_json"]})


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
    _reject_shared_demo_uploads()
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


def _rerun_with_supplement_impl(
    supplement_id: str,
    request: SupplementRerunRequest,
    http_request: Request,
    *,
    progress_callback: Callable[[str, str, str], None] | None = None,
    agent_step_callback: Callable[[str, str, str], None] | None = None,
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
            "force_deterministic_backup": bool(request.force_deterministic_backup),
            "ai_model_all_cases": request.run_mode == "full_analysis",
        }
    )
    if identity and not identity.is_local:
        context["request_identity"] = identity.as_public_dict()
    model_recheck: Callable[[str], bool] | None = None
    if request.force_deterministic_backup:
        context["model_transfer_allowed"] = True
        context["model_transfer_scope"] = "仅在本地生成确定性备用草稿；不发生外部模型传输。"
    elif _competition_demo_enabled():
        context["model_transfer_allowed"] = True
        context["model_transfer_scope"] = "公开样例字段、来源元数据和 RAG 片段；不上传整本 PDF。"
    elif supabase_enabled():
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
        progress_callback=progress_callback,
        agent_step_callback=agent_step_callback,
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
    if isinstance(response.context.get("supplement_delta"), dict):
        response.context["supplement_delta"]["recommendation_change"] = response.context["recommendation_change"]
    save_run(WORKSPACE_ROOT, response)
    return response


@app.post("/api/supplements/{supplement_id}/rerun", response_model=RunResponse)
def rerun_with_supplement(
    supplement_id: str,
    request: SupplementRerunRequest,
    http_request: Request,
) -> RunResponse:
    """兼容旧同步接口；演示前端使用下方 rerun-task 异步接口。"""
    return _rerun_with_supplement_impl(supplement_id, request, http_request)


# —— 固定案例分阶段演示运行（G2）——
# 诊断：固定案例页面原先只在 POST /api/runs 完整返回后一次性渲染阶段，
# 现场无法看到真实过程。这里复用现场新企业的任务轮询模式：POST 返回 202，
# 后台执行仍走同一套 run_rules 主链（规则、RAG、模型开关只有一份实现），
# 六阶段与三角色状态全部由后端业务节点写入，前端定时器只读取状态。


_demo_run_store: DemoRunTaskStore | SupabaseDemoRunTaskStore | None = None
_demo_run_store_lock = threading.Lock()
_demo_run_store_mode: str | None = None
_demo_backup_store: DemoRunTaskStore | None = None
_demo_backup_store_mode: str | None = None
_demo_backup_store_lock = threading.Lock()
_demo_task_probe_lock = threading.Lock()
_demo_task_probe_snapshot: dict[str, Any] | None = None
_demo_task_probe_signature: tuple[str, str] | None = None
_demo_task_probe_expires_at = 0.0
_DEMO_TASK_PROBE_TTL_SECONDS = 30.0


def _demo_task_config_signature() -> tuple[str, str]:
    """Return a cache key without retaining a service key in the snapshot."""

    config = SupabaseConfig.from_env(mode_override="supabase")
    key_digest = hashlib.sha256((config.service_role_key or "").encode("utf-8")).hexdigest()
    return (config.url or "", key_digest)


def _probe_demo_task_store() -> dict[str, Any]:
    """Read-only, short-lived availability probe for the public task ledger."""

    global _demo_task_probe_snapshot, _demo_task_probe_signature, _demo_task_probe_expires_at
    checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not demo_task_supabase_enabled():
        return {
            "availability": "ready",
            "configured": True,
            "reason_code": "local_task_store",
            "checked_at": checked_at,
        }
    signature = _demo_task_config_signature()
    now = time.monotonic()
    with _demo_task_probe_lock:
        if (
            _demo_task_probe_snapshot is not None
            and _demo_task_probe_signature == signature
            and _demo_task_probe_expires_at > now
        ):
            return dict(_demo_task_probe_snapshot)
        try:
            config = SupabaseConfig.from_env(mode_override="supabase")
            if not config.url or not config.service_role_key:
                raise SupabaseNotConfigured(
                    "演示任务台账需要 SUPABASE_URL 与 SUPABASE_SERVICE_ROLE_KEY。"
                )
            client = get_demo_task_client()
            client.probe_demo_task_store()
            result = {
                "availability": "ready",
                "configured": True,
                "reason_code": "supabase_ready",
                "checked_at": checked_at,
            }
        except SupabaseNotConfigured as error:
            result = {
                "availability": "not_configured",
                "configured": False,
                "reason_code": getattr(error, "code", "SUPABASE_NOT_CONFIGURED"),
                "checked_at": checked_at,
            }
        except SupabaseError as error:
            result = {
                "availability": "unavailable",
                "configured": True,
                "reason_code": getattr(error, "code", "SUPABASE_ERROR"),
                "checked_at": checked_at,
            }
        except Exception:
            # Never expose a driver traceback or URL in a public readiness payload.
            result = {
                "availability": "unavailable",
                "configured": True,
                "reason_code": "SUPABASE_PROBE_FAILED",
                "checked_at": checked_at,
            }
        _demo_task_probe_snapshot = dict(result)
        _demo_task_probe_signature = signature
        _demo_task_probe_expires_at = time.monotonic() + _DEMO_TASK_PROBE_TTL_SECONDS
        return result


def _get_demo_run_store() -> DemoRunTaskStore | SupabaseDemoRunTaskStore:
    global _demo_run_store, _demo_run_store_mode
    requested_mode = "supabase" if demo_task_supabase_enabled() else "local"
    runtime_namespace = re.sub(
        r"[^A-Za-z0-9_-]", "", os.getenv("AUDITTRACE_RUNTIME_NAMESPACE", "")
    )[:80]
    store_mode_key = f"{requested_mode}:{runtime_namespace}"
    executor_mode = os.getenv("AUDITTRACE_DEMO_EXECUTOR_MODE", "web").strip().lower()
    if executor_mode not in {"web", "worker"}:
        raise HTTPException(status_code=503, detail="演示任务执行模式配置不受支持。")
    if executor_mode == "worker" and requested_mode != "supabase":
        raise HTTPException(status_code=503, detail="Worker 执行模式必须同时启用 Supabase 演示任务台账。")
    with _demo_run_store_lock:
        if _demo_run_store is not None and _demo_run_store_mode != store_mode_key:
            _demo_run_store.shutdown()
            _demo_run_store = None
        if _demo_run_store is None:
            if requested_mode == "supabase":
                try:
                    from .demo_run_tasks import SupabaseDemoRunTaskStore

                    _demo_run_store = SupabaseDemoRunTaskStore(get_demo_task_client())
                except SupabaseError as error:
                    code = str(getattr(error, "code", "SUPABASE_ERROR"))
                    raise HTTPException(
                        status_code=503,
                        detail=f"演示任务持久化服务暂不可用（{code}）。",
                        headers={"X-AuditTrace-Failure-Code": code},
                    ) from error
            else:
                from .demo_run_tasks import DemoRunTaskStore

                # 本地开发/自动化台账同样按受控 namespace 隔离，避免一次
                # 回归测试复用正式演示 task、额度或旧结果。空 namespace 才
                # 使用历史兼容目录；任何环境变量内容都先做稳定字符过滤。
                task_root = WORKSPACE_ROOT / "runtime"
                if runtime_namespace:
                    task_root = task_root / runtime_namespace
                _demo_run_store = DemoRunTaskStore(task_root / "demo-run-tasks")
            _demo_run_store_mode = store_mode_key
        return _demo_run_store


def _get_demo_backup_store() -> DemoRunTaskStore:
    """Create the explicitly selected, process-local deterministic backup store."""

    global _demo_backup_store, _demo_backup_store_mode
    runtime_namespace = re.sub(
        r"[^A-Za-z0-9_-]", "", os.getenv("AUDITTRACE_RUNTIME_NAMESPACE", "")
    )[:80]
    task_root = WORKSPACE_ROOT / "runtime"
    if runtime_namespace:
        task_root = task_root / runtime_namespace
    store_mode_key = str(task_root)
    with _demo_backup_store_lock:
        if _demo_backup_store is not None and _demo_backup_store_mode != store_mode_key:
            _demo_backup_store.shutdown()
            _demo_backup_store = None
        if _demo_backup_store is None:
            _demo_backup_store = DemoRunTaskStore(
                task_root / "demo-backup-tasks",
                task_id_prefix="DEMO-BACKUP",
            )
            _demo_backup_store_mode = store_mode_key
        return _demo_backup_store


def _store_for_demo_task(task_id: str) -> DemoRunTaskStore | SupabaseDemoRunTaskStore:
    """Route explicit backup IDs separately from durable public task IDs."""

    return _get_demo_backup_store() if str(task_id).startswith("DEMO-BACKUP-") else _get_demo_run_store()


def _demo_task_continuity() -> dict[str, Any]:
    executor_mode = os.getenv("AUDITTRACE_DEMO_EXECUTOR_MODE", "web").strip().lower() or "web"
    if demo_task_supabase_enabled():
        probe = _probe_demo_task_store()
        configured = bool(probe.get("configured"))
        available = probe.get("availability") == "ready"
        return {
            "task_backend": "supabase",
            "executor_mode": executor_mode,
            "configured": configured,
            "availability": probe.get("availability"),
            "reason_code": probe.get("reason_code"),
            "checked_at": probe.get("checked_at"),
            "completed_result_durable": available,
            "running_task_resume": False,
            "boundary": (
                "完成或降级结果可跨刷新与 Web 重启读取；运行中实例中断后需显式创建新任务。"
                if available
                else "Supabase 演示任务台账当前不可用；正式新任务会被阻止，可显式选择确定性备用演示。"
            ),
        }
    return {
        "task_backend": "local_json",
        "executor_mode": executor_mode,
        "configured": True,
        "availability": "ready",
        "reason_code": "local_task_store",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "completed_result_durable": False,
        "running_task_resume": False,
        "boundary": "当前进程的本地演示台账仅用于开发；生产需启用 Supabase 演示任务台账。",
    }


def _demo_task_outcome_from_run(response: RunResponse) -> str:
    """把运行结果映射为任务终态：completed / degraded / failed。"""
    if not response.rule_results or response.run_completeness.startswith("incomplete_rag_failure"):
        return "failed"
    if response.model_check.status == "model_success":
        return "completed"
    return "degraded"


def _record_demo_quality_event(store: DemoRunTaskStore | SupabaseDemoRunTaskStore, task: dict[str, Any], response: RunResponse) -> None:
    """把真实外部运行的脱敏质量事件写入共享台账；fallback/缓存不计入。"""

    client = getattr(store, "client", None)
    if client is None or not response.provider_call_count:
        return
    try:
        model_id = str(response.context.get("model_id") or _model_settings()[2])
        failures = [str(step.failure_code) for step in (response.agent_steps or []) if step.failure_code]
        client.record_model_quality_event(
            {
                "run_id": response.run_id,
                "task_id": str(task.get("task_id") or ""),
                "case_id": str(response.context.get("case_id") or task.get("case_id") or ""),
                "model_id": model_id,
                "route": str(response.context.get("ai_analysis_route") or ""),
                "outcome": str(response.model_check.status or "unknown"),
                "provider_call_count": int(response.provider_call_count or 0),
                "completed_roles": sum(1 for step in (response.agent_steps or []) if step.status == "completed"),
                "input_tokens": int(response.input_tokens or 0),
                "output_tokens": int(response.output_tokens or 0),
                "failure_codes": failures,
            }
        )
    except Exception:  # noqa: BLE001 - 质量台账失败不能覆写已完成分析
        return


def _runtime_quality_snapshot(model_id: str) -> dict[str, Any] | None:
    """读取 Supabase 最近真实当前模型三角色窗口；不可用时明确标记，而非套用旧本地数字。"""

    if not demo_task_supabase_enabled():
        return None
    try:
        client = get_demo_task_client()
        rows = client.list_model_quality_events(model_id=model_id, limit=10)
    except SupabaseError:
        return {
            "status": "unavailable",
            "window_id": f"RUNTIME-{model_id.upper()}-UNAVAILABLE",
            "model_id": model_id,
            "sample_count": 0,
            "success_count": 0,
            "success_rate": None,
            "threshold": 0.8,
            "alert": False,
            "alert_kind": "ledger_unavailable",
            "source": "supabase_model_quality_events",
            "boundary": "运行时质量台账暂不可读取；不得用本地历史质量窗口替代。",
        }
    sample_count = len(rows)
    success_count = sum(
        1
        for row in rows
        if str(row.get("outcome") or "") == "model_success"
        and int(row.get("provider_call_count") or 0) > 0
        and int(row.get("completed_roles") or 0) == 3
    )
    rate = success_count / sample_count if sample_count else None
    return {
        "status": "below_threshold" if sample_count and rate is not None and rate < 0.8 else "meets_threshold" if sample_count else "unmeasured",
        "window_id": f"RUNTIME-{model_id.upper()}-LAST10",
        "model_id": model_id,
        "sample_count": sample_count,
        "success_count": success_count,
        "success_rate": rate,
        "threshold": 0.8,
        "alert": bool(sample_count and rate is not None and rate < 0.8),
        "alert_kind": "threshold_breach" if sample_count and rate is not None and rate < 0.8 else None,
        "source": "supabase_model_quality_events",
        "includes_retries": True,
        "boundary": f"仅统计最近10次真实 {model_id} 三 Agent 完整尝试；不含 B1、B2、缓存回放、确定性备用或 provider probe。",
    }


def _finalize_demo_run_stages(store: DemoRunTaskStore, task_id: str, response: RunResponse) -> None:
    """运行结束后按真实结果补齐阶段 3—5；阶段 1—2 已由业务节点写入。"""
    steps = list(response.agent_steps or [])
    completed = [step for step in steps if step.status == "completed"]
    attempted = [step for step in steps if step.status not in {
        "not_requested", "not_applicable", "skipped", "not_attempted_rag_failure",
        "model_transfer_not_allowed", "config_missing", "sensitive_data_blocked",
    }]
    chain_ran = bool(attempted) or bool(completed)
    if response.run_completeness.startswith("incomplete_rag_failure"):
        store.update_stage(task_id, "agent_collaboration", "skipped", "证据加载失败，协作链未执行。")
        store.update_stage(task_id, "evidence_validation", "skipped", "未执行验证。")
        for role in AGENT_ROLE_ORDER:
            store.update_agent_step(task_id, role, "skipped", "证据链未完成，三角色协作未执行。")
    elif not chain_ran:
        store.update_stage(task_id, "agent_collaboration", "skipped", "本次未执行模型协作链（未请求或未授权）。")
        store.update_stage(task_id, "evidence_validation", "skipped", "未执行验证。")
        for role in AGENT_ROLE_ORDER:
            store.update_agent_step(task_id, role, "skipped", "本次未请求三角色协作。")
    elif len(completed) == 3:
        model_note = ""
        if any(str(step.model_id or "") == "demo-deterministic-v1" for step in completed):
            model_note = "（演示确定性草稿，未调用外部模型）"
        store.update_stage(task_id, "agent_collaboration", "completed", f"三角色协作完成{model_note}。")
        store.update_stage(task_id, "evidence_validation", "completed", "证据白名单、Schema、事实语言与禁用词校验结束。")
    else:
        store.update_stage(task_id, "agent_collaboration", "degraded", f"{len(completed)}/3 角色完成，协作链未全部通过。")
        store.update_stage(
            task_id,
            "evidence_validation",
            "degraded" if attempted else "skipped",
            "硬校验未全部通过，失败码已保留，未放宽任何校验。",
        )
    if _demo_task_outcome_from_run(response) == "failed":
        store.update_stage(
            task_id,
            "structured_output",
            "failed",
            "前置证据或规则链未完成，未生成可导出的结构化结果。",
        )
    else:
        store.update_stage(
            task_id,
            "structured_output",
            "completed",
            f"运行 {response.run_id} 已保存，可导出 JSON / 表格 / CSV / PDF。",
        )


def _execute_demo_run(task: dict[str, Any], store: DemoRunTaskStore, http_request: Request) -> None:
    """后台执行固定案例分阶段运行；所有状态写入走 store，不让前端模拟。"""
    task_id = str(task["task_id"])
    body = task.get("run_body") or {}
    try:
        request = RunRequest(
            case_id=str(body.get("case_id") or task.get("case_id") or ""),
            current_year=int(body.get("current_year") or 0),
            scene="审计计划",
            rule_ids=list(body.get("rule_ids") or ["R1"]),
            run_mode=str(body.get("run_mode") or "full_analysis"),
            planned_materiality=body.get("planned_materiality"),
            force_deterministic_backup=bool(body.get("force_deterministic_backup", False)),
        )
    except (TypeError, ValueError) as error:
        store.update_task(task_id, status="failed", failure_code="TASK_INVALID_REQUEST", error=f"{type(error).__name__}: {str(error)[:400]}")
        return

    def _progress(stage: str, status: str, detail: str) -> None:
        store.update_stage(task_id, stage, status, detail)

    def _role_step(role: str, status: str, detail: str) -> None:
        store.update_agent_step(task_id, role, status, detail)

    try:
        response = _run_rules_impl(request, http_request, progress_callback=_progress, agent_step_callback=_role_step)
    except HTTPException as error:
        detail = str(getattr(error, "detail", "") or "")
        store.update_stage(task_id, "evidence_load", "failed", f"运行被拒绝：{detail[:200]}")
        for stage in STAGE_ORDER[1:]:
            store.update_stage(task_id, stage, "skipped", "前置阶段未完成，后续阶段未执行。")
        for role in AGENT_ROLE_ORDER:
            store.update_agent_step(task_id, role, "skipped", "前置阶段未完成。")
        # 终态写入放在阶段收口之后，避免 CAS store 拒绝修改 failed 任务。
        store.update_task(task_id, status="failed", failure_code=f"HTTP_{error.status_code}", error=detail[:400])
        return
    except Exception as error:  # noqa: BLE001 - worker 边界负责失败关闭
        store.update_stage(task_id, "evidence_load", "failed", f"运行异常：{type(error).__name__}。")
        for stage in STAGE_ORDER[1:]:
            store.update_stage(task_id, stage, "skipped", "异常关闭后未执行。")
        for role in AGENT_ROLE_ORDER:
            store.update_agent_step(task_id, role, "skipped", "异常关闭后未执行。")
        store.update_task(task_id, status="failed", failure_code="TASK_EXECUTION_ERROR", error=f"{type(error).__name__}: {str(error)[:400]}")
        return
    store.update_task(
        task_id,
        run_id=response.run_id,
        result=response.model_dump(mode="json"),
        result_expires_at=result_expiry_iso(),
    )
    _record_demo_quality_event(store, task, response)
    if store.is_cancelled(task_id):
        return
    _finalize_demo_run_stages(store, task_id, response)
    store.update_task(task_id, status=_demo_task_outcome_from_run(response))


def _execute_demo_supplement_run(task: dict[str, Any], store: DemoRunTaskStore, http_request: Request) -> None:
    """补充材料续分析复用同一六阶段任务台账；父运行只读，子运行单独落盘。"""
    task_id = str(task["task_id"])
    body = task.get("run_body") or {}

    def _progress(stage: str, status: str, detail: str) -> None:
        store.update_stage(task_id, stage, status, detail)

    def _role_step(role: str, status: str, detail: str) -> None:
        store.update_agent_step(task_id, role, status, detail)

    try:
        supplement_id = str(body.get("supplement_id") or "")
        request = SupplementRerunRequest(
            run_mode=str(body.get("run_mode") or "full_analysis"),
            force_deterministic_backup=bool(body.get("force_deterministic_backup", False)),
        )
        response = _rerun_with_supplement_impl(
            supplement_id,
            request,
            http_request,
            progress_callback=_progress,
            agent_step_callback=_role_step,
        )
    except HTTPException as error:
        detail = str(getattr(error, "detail", "") or "")
        store.update_stage(task_id, "evidence_load", "failed", f"补充运行被拒绝：{detail[:200]}")
        for stage in STAGE_ORDER[1:]:
            store.update_stage(task_id, stage, "skipped", "前置阶段未完成，后续阶段未执行。")
        for role in AGENT_ROLE_ORDER:
            store.update_agent_step(task_id, role, "skipped", "前置阶段未完成。")
        store.update_task(task_id, status="failed", failure_code=f"HTTP_{error.status_code}", error=detail[:400])
        return
    except Exception as error:  # noqa: BLE001 - worker boundary fail-closed
        store.update_stage(task_id, "evidence_load", "failed", f"补充运行异常：{type(error).__name__}。")
        for stage in STAGE_ORDER[1:]:
            store.update_stage(task_id, stage, "skipped", "异常关闭后未执行。")
        for role in AGENT_ROLE_ORDER:
            store.update_agent_step(task_id, role, "skipped", "异常关闭后未执行。")
        store.update_task(task_id, status="failed", failure_code="SUPPLEMENT_TASK_EXECUTION_ERROR", error=f"{type(error).__name__}: {str(error)[:400]}")
        return
    store.update_task(
        task_id,
        run_id=response.run_id,
        result=response.model_dump(mode="json"),
        result_expires_at=result_expiry_iso(),
    )
    _record_demo_quality_event(store, task, response)
    if store.is_cancelled(task_id):
        return
    _finalize_demo_run_stages(store, task_id, response)
    store.update_task(task_id, status=_demo_task_outcome_from_run(response))


@app.post("/api/supplements/{supplement_id}/rerun-task", status_code=202)
def create_supplement_rerun_task(
    supplement_id: str,
    request: SupplementRerunRequest,
    http_request: Request,
) -> dict[str, Any]:
    """创建补充材料异步续分析；前端沿用固定案例六阶段轮询协议。"""
    identity = require_authenticated(http_request)
    supplement = _load_supplement_record(supplement_id, identity)
    if supplement is None:
        raise HTTPException(status_code=404, detail="未找到该补充资料记录。")
    if supplement.get("status") != "ready_for_rerun":
        raise HTTPException(status_code=409, detail="补充资料没有可验证的结构化证据，不能续分析。")
    parent = _load_stored_run(
        str(supplement.get("parent_run_id") or ""),
        owner_tenant_id=str(identity.tenant_id or "") or None if identity else None,
    )
    if parent is None:
        raise HTTPException(status_code=404, detail="父运行记录已不存在。")
    case_id = str(parent.run.context.get("case_id") or "")
    store = _get_demo_run_store()
    task = store.create(
        f"SUPPLEMENT:{supplement_id}",
        {
            "kind": "supplement_rerun",
            "supplement_id": supplement_id,
            "run_mode": request.run_mode,
            "force_deterministic_backup": request.force_deterministic_backup,
        },
        lambda current: _execute_demo_supplement_run(current, store, http_request),
    )
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "case_id": case_id,
        "parent_run_id": str(supplement.get("parent_run_id") or ""),
        "supplement_id": supplement_id,
        "stage_schema_version": task.get("stage_schema_version", "demo_task_v2"),
        "retry_of_task_id": task.get("retry_of_task_id"),
        "steps": task.get("steps", {}),
        "agent_steps": task.get("agent_steps", {}),
    }


def _demo_backup_continuity() -> dict[str, Any]:
    return {
        "task_backend": "local_ephemeral",
        "executor_mode": "web",
        "configured": True,
        "availability": "ready",
        "reason_code": "explicit_deterministic_backup",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "completed_result_durable": False,
        "running_task_resume": False,
        "boundary": "确定性备用不调用外部模型；结果只保留在当前 Web 实例，刷新或重启后需重新创建。",
    }


def _create_demo_run_task(
    request: DemoRunCreateRequest,
    http_request: Request,
    *,
    idempotency_key: str | None,
    backup: bool = False,
) -> dict[str, Any]:
    """Validate one frozen case and create either a durable or explicit backup task."""

    idempotency_key = str(idempotency_key or "").strip() or None
    if idempotency_key and not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(status_code=422, detail="Idempotency-Key 必须为 8 至 128 位字母、数字或 ._:-。")
    if not _competition_demo_enabled():
        raise HTTPException(status_code=403, detail="演示运行接口只在竞赛演示模式启用。")
    if request.run_mode not in {"full_analysis", "calculation_only"}:
        raise HTTPException(status_code=422, detail="run_mode 只能是 full_analysis 或 calculation_only。")
    if request.force_deterministic_backup and not backup:
        raise HTTPException(status_code=422, detail="确定性备用必须通过显式备用演示入口启动。")
    if backup:
        request = request.model_copy(update={
            "run_mode": "full_analysis",
            "force_deterministic_backup": True,
            "retry_of_task_id": None,
        })
    # 公开模式的允许集合只来自受跟踪的 15 案发布 manifest，不因核心
    # 案例切换到 Supabase 或远端目录而扩大。清单损坏/缺失是发布材料问题，
    # 用 503 与“非清单案例”403 分开，避免页面已展示但运行入口偷偷放行别的案例。
    manifest, manifest_failure = load_demo_manifest()
    manifest_case = None
    if _public_demo_enabled():
        if manifest_failure or not isinstance(manifest, dict):
            raise HTTPException(status_code=503, detail=f"当前公开演示发布清单不可用：{manifest_failure or 'demo_manifest_invalid'}")
        manifest_case = next(
            (item for item in (manifest.get("cases") or [])
             if isinstance(item, dict) and str(item.get("case_id") or "").upper() == request.case_id.upper()),
            None,
        )
        if manifest_case is None:
            raise HTTPException(status_code=403, detail="该案例不在当前公开演示的 15 案发布清单中。")
    store = _get_demo_backup_store() if backup else _get_demo_run_store()
    if request.retry_of_task_id:
        previous = store.snapshot(request.retry_of_task_id)
        if previous is None:
            raise HTTPException(status_code=404, detail="待重跑的旧任务不存在。")
        if str(previous.get("case_id") or "").upper() != request.case_id.upper():
            raise HTTPException(status_code=422, detail="重跑任务必须使用同一公开案例。")
        if previous.get("status") not in {"failed", "cancelled", "interrupted", "expired", "degraded"}:
            raise HTTPException(status_code=409, detail="旧任务尚未进入可安全重跑的终态。")
    # 演示入口必须与 bootstrap/cases 使用同一套公开案例解析；直接调用
    # get_case 只认识本地标准案，会让页面展示的 14 个 seed 案在主按钮处 404。
    case = _case_record(request.case_id, tenant_id=None)
    if case is None:
        if _public_demo_enabled():
            raise HTTPException(status_code=503, detail="当前发布包缺少该公开演示案例。")
        raise HTTPException(status_code=404, detail="案例未登记。")
    if manifest_case is None:
        # 非公开开发模式仍保留旧的 seed 年度/规则合同；它不扩大公开接口的
        # 15 案白名单，只用于本地调试和兼容既有请求。
        manifest_case = next(
            (item for item in load_seed_cases(WORKSPACE_ROOT)
             if str(item.get("case_id") or "").upper() == request.case_id.upper()),
            None,
        )
    if _competition_demo_enabled() and manifest_case is not None:
        allowed_years = {int(year) for year in (manifest_case.get("report_years") or []) if str(year).isdigit()}
        if allowed_years and int(request.current_year) not in allowed_years:
            raise HTTPException(status_code=422, detail="报告年度不在该公开案例的冻结年度范围内。")
        allowed_rules = {str(rule).upper() for rule in (manifest_case.get("rule_ids") or [])}
        if allowed_rules and not set(request.rule_ids).issubset(allowed_rules):
            raise HTTPException(status_code=422, detail="请求规则不在该公开案例的冻结规则范围内。")
    try:
        task = store.create(
            request.case_id,
            request.model_dump(mode="json"),
            lambda current: _execute_demo_run(current, store, http_request),
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflict as error:
        raise HTTPException(status_code=409, detail="该 Idempotency-Key 已绑定另一份请求。") from error
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "case_id": request.case_id,
        "retry_of_task_id": task.get("retry_of_task_id") or request.retry_of_task_id,
        "stage_schema_version": task.get("stage_schema_version", "demo_task_v2"),
        "steps": task.get("steps", {}),
        "agent_steps": task.get("agent_steps", {}),
        "result_expires_at": task.get("result_expires_at"),
        "continuity": _demo_backup_continuity() if backup else _demo_task_continuity(),
    }


@app.post("/api/demo/runs", status_code=202)
def create_demo_run(
    request: DemoRunCreateRequest,
    http_request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """创建固定案例分阶段演示运行；返回 202 与 task_id，立即可以轮询。"""

    return _create_demo_run_task(request, http_request, idempotency_key=idempotency_key)


@app.post("/api/demo/backup-runs", status_code=202)
def create_demo_backup_run(
    request: DemoRunCreateRequest,
    http_request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """创建用户明确选择的确定性备用演示任务；不调用外部模型或 Supabase。"""

    return _create_demo_run_task(request, http_request, idempotency_key=idempotency_key, backup=True)


@app.get("/api/demo/runs/{task_id}")
def get_demo_run_task(task_id: str) -> dict[str, Any]:
    """读取真实任务进度；不存在时返回 404。"""
    task = _store_for_demo_task(task_id).snapshot(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="演示运行任务不存在。")
    task["continuity"] = _demo_backup_continuity() if str(task_id).startswith("DEMO-BACKUP-") else _demo_task_continuity()
    return task


@app.get("/api/demo/runs/{task_id}/result")
def get_demo_run_result(task_id: str) -> dict[str, Any]:
    """任务结束后读取现有 RunResponse；未结束返回 409。"""
    task = _store_for_demo_task(task_id).snapshot(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="演示运行任务不存在。")
    if task["status"] == "expired":
        raise HTTPException(status_code=410, detail="TASK_RESULT_EXPIRED")
    if task["status"] in {"cancelled", "interrupted", "failed"}:
        raise HTTPException(status_code=409, detail="任务未生成可读取的结构化结果。")
    if task["status"] in {"queued", "running"} or task.get("result") is None:
        raise HTTPException(status_code=409, detail="演示运行尚未结束。")
    return task["result"]


@app.post("/api/demo/runs/{task_id}/cancel")
def cancel_demo_run_task(task_id: str) -> dict[str, Any]:
    """取消尚未进入不可中断外部调用的任务；已终态返回 409。"""
    cancelled = _store_for_demo_task(task_id).cancel(task_id)
    if cancelled is None:
        raise HTTPException(status_code=409, detail="任务不存在或已结束，无法取消。")
    if cancelled.get("cancel_rejected"):
        raise HTTPException(status_code=409, detail="任务已进入不可中断的协作阶段；将如实等待当前调用结算。")
    return {"task_id": cancelled["task_id"], "status": cancelled["status"], "failure_code": cancelled["failure_code"]}
