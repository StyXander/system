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
import os
import threading
import time
import uuid
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .agents import PROMPT_VERSION, run_agent_chain
from .cases import (
    build_case_template_zip,
    get_case,
    get_financial_rows,
    get_period_sources,
    import_case_zip,
    list_cases,
    resolve_case_document,
)
from .data import CASE_ID, EVIDENCE, SOURCE_SNAPSHOT_ID
from .delivery import build_report, cache_run, replay_cache
from .rag import get_retrieval, prepare_index, question_set, retrieve, status as rag_status
from .run_store import load_run, save_human_review, save_run
from .schemas import (
    AI_GENERATED_CONTENT_NOTICE,
    AgentStep,
    HealthResponse,
    HumanReviewRequest,
    ModelCheck,
    RagRetrieveRequest,
    RuleResult,
    RunRequest,
    RunResponse,
    StoredRunResponse,
    SupplementRerunRequest,
)
from .source_cache import ensure_standard_sources
from .supplements import create_supplement, load_supplement


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

app = FastAPI(title="审迹智链 AuditTrace API", version=ENGINE_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _with_ai_notice(payload: dict[str, Any]) -> dict[str, Any]:
    """所有公开 JSON 对象统一携带同一句 AI 生成内容声明。"""
    return {**payload, "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE}


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
    public.pop("package_sha256", None)
    for document in public.get("documents", []):
        document.pop("storage_relpath", None)
    return public


def _public_source(row: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in row.items() if key != "storage_relpath"}


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
        if not isinstance(row.get("value"), (int, float)) or isinstance(row.get("value"), bool):
            issues.append(f"{row.get('evidence_id', 'UNKNOWN')}金额不是数值")
        if row.get("source_mode") == "supplement_structured":
            continue
        source_path = WORKSPACE_ROOT / row.get("storage_relpath", row.get("source_file", ""))
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
        issues = ["缺少R1基本字段：" + "、".join(missing)]
        return RuleResult(
            rule_id="R1",
            status="DATA_GAP",
            screening_status="DATA_GAP",
            source_validation=_base_source_validation(issues),
            metrics=empty_metrics,
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
    }
    basis_limitation = "应收账款仅有净额/报表列示额，未达到专业目标的账面余额口径。" if "net" in basis_values else "应收账款采用账面余额口径。"
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
    if any(result.status == "SOURCE_INCOMPLETE" for result in results):
        return "SOURCE_INCOMPLETE"
    if any(result.status == "candidate" for result in results):
        return "candidate"
    if any(result.status == "DATA_NOT_COMPARABLE" for result in results):
        return "DATA_NOT_COMPARABLE"
    if any(result.status == "DATA_GAP" for result in results):
        return "DATA_GAP"
    return "RULE_NOT_TRIGGERED"


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
        prepare_index(WORKSPACE_ROOT, case_id=context["case_id"], force=False)
        retrievals: list[dict[str, Any]] = []
        rag_evidence: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        seen_evidence: set[str] = set()
        for rule_id in candidate_rules:
            for question_id in RAG_QUESTIONS_BY_RULE[rule_id]:
                record = retrieve(
                    WORKSPACE_ROOT,
                    query="",
                    question_id=question_id,
                    t0=context["t0"],
                    rule_id=rule_id,
                    top_k=2,
                    case_id=context["case_id"],
                    company_name=context["company_name"],
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
) -> RunResponse:
    run_id = f"{run_prefix}-{uuid.uuid4().hex[:12].upper()}"
    context = deepcopy(context)
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
    for rule_id in rule_ids:
        rows = _rule_rows(sources, rule_id)
        sources_by_rule[rule_id] = rows
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
        rule_results.append(result)

    screening_status = _screening_overall(rule_results)
    public_sources = [_public_source(row) for row in sources]
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
            detail="案例 manifest 禁止模型传输，完整分析主链已如实关闭。",
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
            )
            review_step = next(
                (step for step in result.agent_steps if step.role == "review" and step.status == "completed" and step.output),
                None,
            )
            if review_step and review_step.output:
                result.ai_recommendation = review_step.output.ai_recommendation or review_step.output.status
                result.ai_draft = review_step.output.model_dump(mode="json")
        model_check = _model_check_from_results(rule_results, enabled=True, model_id=model_id)
        if not candidate_exists:
            run_completeness = "complete_full_analysis_no_candidate"
        elif model_check.status == "model_success":
            run_completeness = "complete_full_analysis"
        else:
            run_completeness = "incomplete_model_chain_failed"

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
def project_status() -> dict[str, Any]:
    status_path = WORKSPACE_ROOT / "PROJECT_STATUS.json"
    if status_path.is_file():
        try:
            registered = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            registered = {"status_file": "invalid"}
    else:
        registered = {"status_file": "missing"}
    cases = list_cases(WORKSPACE_ROOT)
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
                "company_name": case["company_name"],
                "available_years": case["available_years"],
                "source_count": len(case["documents"]),
                "model_transfer_allowed": case["model_transfer_allowed"],
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
    })


@app.get("/api/cases")
def get_cases() -> dict[str, Any]:
    return _with_ai_notice({
        "schema_version": "case_list_v1",
        "cases": [_public_case(case) for case in list_cases(WORKSPACE_ROOT)],
        "boundary": "导入通过只表示结构与安全预检通过；正式第二案例仍须人工冻结。",
    })


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
    file: UploadFile = File(...),
    authorized: bool = Form(...),
    desensitized: bool = Form(...),
) -> dict[str, Any]:
    content = await file.read()
    try:
        case = import_case_zip(
            WORKSPACE_ROOT,
            content,
            authorized=authorized,
            desensitized=desensitized,
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _with_ai_notice({
        "status": "imported_pending_human_confirmation",
        "case": _public_case(case),
        "boundary": "系统未从PDF自动取数，也未把该案例认定为正式竞赛样例。",
    })


@app.get("/api/cases/{case_id}")
def get_case_detail(case_id: str) -> dict[str, Any]:
    normalized = case_id.upper()
    case = get_case(WORKSPACE_ROOT, normalized)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    rows = [_public_source(row) for row in get_financial_rows(WORKSPACE_ROOT, normalized)]
    return _with_ai_notice({
        **_public_case(case),
        "financial_fields": rows,
        "field_validation": {
            "status": "passed_import_or_registry_validation",
            "field_count": len(rows),
            "years": sorted({row["year"] for row in rows}, reverse=True),
            "boundary": "字段已通过结构和来源登记校验；金额口径与专业含义仍待人工复核。",
        },
    })


@app.get("/api/cases/{case_id}/sources/{document_id}")
def open_case_source(case_id: str, document_id: str) -> Response:
    normalized_case_id = case_id.upper()
    normalized_document_id = document_id.upper()
    if normalized_case_id == CASE_ID and _public_demo_enabled():
        source_url = _registered_standard_source_url(normalized_document_id)
        if source_url:
            return RedirectResponse(source_url, status_code=307)
    resolved = resolve_case_document(WORKSPACE_ROOT, normalized_case_id, normalized_document_id)
    if resolved is None:
        if normalized_case_id == CASE_ID:
            source_url = _registered_standard_source_url(normalized_document_id)
            if source_url:
                return RedirectResponse(source_url, status_code=307)
        raise HTTPException(status_code=404, detail="来源文档未登记或文件不存在。")
    path, document = resolved
    return FileResponse(path, media_type="application/pdf", filename=document["source_file"])


@app.post("/api/runs", response_model=RunResponse)
def run_rules(request: RunRequest, http_request: Request) -> RunResponse:
    _ensure_public_standard_sources(request.case_id)
    case = get_case(WORKSPACE_ROOT, request.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    try:
        context, sources = get_period_sources(
            WORKSPACE_ROOT,
            request.case_id,
            request.current_year,
            tuple(request.rule_ids),
        )
    except KeyError as error:
        raise HTTPException(status_code=422, detail="当前案例没有该年度所需的连续字段。") from error
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
    )


@app.get("/api/runs/{run_id}", response_model=StoredRunResponse)
def get_run(run_id: str) -> StoredRunResponse:
    stored = load_run(WORKSPACE_ROOT, run_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
    return stored


@app.post("/api/runs/{run_id}/review", response_model=StoredRunResponse)
def review_run(run_id: str, review: HumanReviewRequest) -> StoredRunResponse:
    stored = save_human_review(WORKSPACE_ROOT, run_id, review)
    if stored is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
    return stored


@app.post("/api/runs/{run_id}/cache")
def create_run_cache(run_id: str) -> dict[str, Any]:
    stored = load_run(WORKSPACE_ROOT, run_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
    try:
        return _with_ai_notice(cache_run(WORKSPACE_ROOT, stored))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/cache/{cache_id}/replay", response_model=RunResponse)
def replay_run_cache(cache_id: str) -> RunResponse:
    response = replay_cache(WORKSPACE_ROOT, cache_id)
    if response is None:
        raise HTTPException(status_code=404, detail="未找到该缓存。")
    save_run(WORKSPACE_ROOT, response)
    return response


@app.get("/api/runs/{run_id}/report.docx")
def export_run_report(run_id: str) -> FileResponse:
    stored = load_run(WORKSPACE_ROOT, run_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="未找到该运行记录。")
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
def get_rag_status(case_id: str = CASE_ID) -> dict[str, Any]:
    if get_case(WORKSPACE_ROOT, case_id.upper()) is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    return _with_ai_notice(rag_status(WORKSPACE_ROOT, case_id.upper()))


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
def prepare_rag(case_id: str = CASE_ID, force: bool = False) -> dict[str, Any]:
    normalized_case_id = case_id.upper()
    _ensure_public_standard_sources(normalized_case_id)
    try:
        return _with_ai_notice(prepare_index(WORKSPACE_ROOT, case_id=normalized_case_id, force=force))
    except (FileNotFoundError, ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/rag/retrieve")
def rag_retrieve(request: RagRetrieveRequest) -> dict[str, Any]:
    case = get_case(WORKSPACE_ROOT, request.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案例未登记。")
    try:
        return _with_ai_notice(retrieve(
            WORKSPACE_ROOT,
            query=request.query,
            t0=request.t0,
            rule_id=request.rule_id,
            top_k=request.top_k,
            case_id=request.case_id,
            company_name=request.company_name,
            question_id=request.question_id,
        ))
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/rag/retrievals/{retrieval_id}")
def read_retrieval_log(retrieval_id: str) -> dict[str, Any]:
    record = get_retrieval(WORKSPACE_ROOT, retrieval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该检索日志。")
    return _with_ai_notice(record)


@app.post("/api/supplements")
async def register_supplement(
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
    if load_run(WORKSPACE_ROOT, parent_run_id) is None:
        raise HTTPException(status_code=404, detail="父运行不存在，不能绑定补充资料。")
    try:
        parsed_rules = json.loads(bound_rule_ids)
        rules = parsed_rules if isinstance(parsed_rules, list) else [str(parsed_rules)]
    except json.JSONDecodeError:
        rules = [item.strip() for item in bound_rule_ids.split(",") if item.strip()]
    content = await file.read() if file is not None else b""
    filename = file.filename if file is not None and file.filename else "structured.json"
    return _with_ai_notice(create_supplement(
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
    ))


@app.get("/api/supplements/{supplement_id}")
def get_supplement(supplement_id: str) -> dict[str, Any]:
    record = load_supplement(WORKSPACE_ROOT, supplement_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该补充资料记录。")
    return _with_ai_notice(record)


@app.post("/api/supplements/{supplement_id}/rerun", response_model=RunResponse)
def rerun_with_supplement(
    supplement_id: str,
    request: SupplementRerunRequest,
    http_request: Request,
) -> RunResponse:
    supplement = load_supplement(WORKSPACE_ROOT, supplement_id)
    if supplement is None:
        raise HTTPException(status_code=404, detail="未找到该补充资料记录。")
    if supplement["status"] != "ready_for_rerun":
        raise HTTPException(status_code=409, detail="补充资料没有可验证的结构化证据，不能续分析。")
    parent = load_run(WORKSPACE_ROOT, supplement["parent_run_id"])
    if parent is None:
        raise HTTPException(status_code=404, detail="父运行记录已不存在。")
    rule_ids = list(supplement["bound_rule_ids"])
    try:
        _, sources = get_period_sources(
            WORKSPACE_ROOT,
            str(parent.run.context["case_id"]),
            int(parent.run.context["current_year"]),
            tuple(rule_ids),
        )
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
        }
    )
    parameters = parent.run.context.get("configured_parameters", {})
    response = _execute_run(
        context=context,
        sources=sources,
        rule_ids=rule_ids,
        run_mode=request.run_mode,
        r2_min_gap=float(parameters.get("r2_min_gap", 0.0)),
        planned_materiality=parameters.get("planned_materiality"),
        r1_gap_threshold=float(parameters.get("r1_gap_threshold", 0.15)),
        r1_strong_gap_threshold=float(parameters.get("r1_strong_gap_threshold", 0.30)),
        r1_absolute_threshold=float(parameters.get("r1_absolute_threshold", 0.0)),
        http_request=http_request,
        run_prefix="RUN-SUP",
        supplement_evidence=supplement.get("structured_evidence", []),
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
