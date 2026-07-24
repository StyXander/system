"""审迹智链 W2/W3 本地后端。

当前只处理标准股份 DEV_T0 开发资料。R1/R2由程序确定性计算；模型仅在规则触发后
按固定顺序输出受校验的语义草稿，不能改变数字、来源、规则触发或人工结论。
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agents import PROMPT_VERSION, run_agent_chain
from .data import CASE_ID, RULE_FIELD_SPECS, SOURCE_SNAPSHOT_ID, get_period_sources
from .run_store import load_run, save_human_review, save_run
from .schemas import (
    HealthResponse,
    HumanReviewRequest,
    ModelCheck,
    RuleResult,
    RunRequest,
    RunResponse,
    StoredRunResponse,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(WORKSPACE_ROOT / ".env")

# 仅在公开演示部署时启用的轻量保护：避免匿名访问反复触发付费模型调用。
# 这是进程内限额，不替代生产环境的网关、账户体系或专业审计留痕方案。
_PUBLIC_MODEL_REQUESTS_BY_IP: dict[str, deque[float]] = {}
_PUBLIC_MODEL_REQUESTS_GLOBAL: deque[float] = deque()
_PUBLIC_MODEL_REQUEST_LOCK = threading.Lock()

app = FastAPI(title="审迹智链 AuditTrace W3 API", version="0.3.0")
# 本地 file:// 预览只会得到真实的“后端不可用”提示；正式部署前再收紧来源。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

assets_dir = WORKSPACE_ROOT / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


def _model_settings() -> tuple[str | None, str, str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip() or None
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model_id = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
    return api_key, base_url, model_id


def _positive_int_env(name: str, default: int) -> int:
    """读取公开演示保护参数；非法环境变量回退到安全默认值。"""
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _public_demo_enabled() -> bool:
    return os.getenv("AUDITTRACE_PUBLIC_DEMO", "false").strip().lower() in {"1", "true", "yes"}


def _client_identity(request: Request) -> str:
    """Render 等反向代理会传递首个 X-Forwarded-For；本地运行时退回连接地址。"""
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    return request.client.host if request.client else "unknown"


def _enforce_public_model_quota(request: Request) -> None:
    """公开演示只有匿名访问时限流；本地开发与团队内测不受此限制。"""
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
                detail="公开演示的AI调用次数已达到临时上限，请稍后再试；确定性计算和页面浏览不受影响。",
            )
        recent_for_ip.append(now)
        _PUBLIC_MODEL_REQUESTS_GLOBAL.append(now)


def _validate_sources(rows: list[dict[str, Any]], t0: str) -> list[str]:
    """来源缺失或超过分析时点时，必须阻断对应规则，不能让模型补齐。"""
    issues: list[str] = []
    for row in rows:
        required = ("evidence_id", "source_file", "disclosure_date", "pdf_page", "print_page", "locator")
        missing = [field for field in required if not row.get(field)]
        if missing:
            issues.append(f"{row['field_id']}缺少：{'、'.join(missing)}")
        if row.get("disclosure_date", "9999-12-31") > t0:
            issues.append(f"{row['evidence_id']}披露日晚于T0")
        if not isinstance(row.get("value"), (int, float)):
            issues.append(f"{row['evidence_id']}金额不是数值")
    return issues


def _growth(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return (current - previous) / abs(previous)


def _rule_rows(all_rows: list[dict[str, Any]], rule_id: str) -> list[dict[str, Any]]:
    required_ids = {spec[0] for spec in RULE_FIELD_SPECS[rule_id]}
    return [row for row in all_rows if row["field_id"] in required_ids]


def _base_source_validation(issues: list[str]) -> dict[str, Any]:
    return {
        "status": "failed" if issues else "passed",
        "issues": issues,
        "review_boundary": "来源已完成技术交叉复核，仍待团队人工专业确认。",
    }


def _r1_result(rows: list[dict[str, Any]], source_issues: list[str]) -> RuleResult:
    if source_issues:
        return RuleResult(
            rule_id="R1",
            status="SOURCE_INCOMPLETE",
            source_validation=_base_source_validation(source_issues),
            metrics={"revenue_growth": None, "ar_growth": None, "growth_gap": None},
        )

    by_field = {row["field_id"]: row["value"] for row in rows}
    revenue_growth = _growth(by_field["revenue_current"], by_field["revenue_previous"])
    ar_growth = _growth(by_field["ar_current"], by_field["ar_previous"])
    if revenue_growth is None or ar_growth is None:
        return RuleResult(
            rule_id="R1",
            status="DATA_GAP",
            source_validation=_base_source_validation([]),
            metrics={"revenue_growth": revenue_growth, "ar_growth": ar_growth, "growth_gap": None},
            risk_card={
                "rule_id": "R1",
                "title": "R1无法计算：上年营业收入或应收账款为零",
                "data_gaps": ["需确认上年基数与可比口径"],
                "requested_materials": ["相关年度报表项目明细及口径说明"],
            },
        )

    growth_gap = ar_growth - revenue_growth
    candidate = growth_gap > 0
    return RuleResult(
        rule_id="R1",
        status="candidate" if candidate else "RULE_NOT_TRIGGERED",
        source_validation=_base_source_validation([]),
        metrics={"revenue_growth": revenue_growth, "ar_growth": ar_growth, "growth_gap": growth_gap},
        risk_card={
            "rule_id": "R1",
            "engineering_version": "四字段增速方向比较",
            "status": "candidate_pending_human_review" if candidate else "rule_not_triggered",
            "title": "应收账款增速高于收入增速，建议进一步了解" if candidate else "本次未出现应收增速高于收入增速的方向",
            "observation": (
                f"应收账款增速为{ar_growth:.2%}，营业收入增速为{revenue_growth:.2%}，前者高出{growth_gap:.2%}。"
                "按R1当前工程版形成待进一步了解候选；是否保留须人工复核。"
                if candidate
                else f"应收账款增速为{ar_growth:.2%}，营业收入增速为{revenue_growth:.2%}。"
                "按R1当前工程版未形成方向候选；这不代表不存在其他收入确认相关风险。"
            ),
            "normal_explanations": ["信用政策或结算周期改变", "季节性回款节奏", "新增客户或行业账期变化"],
            "data_gaps": ["账龄明细", "期后回款记录", "主要客户合同关键结算条款摘要"],
            "requested_materials": ["账龄明细表", "期后回款记录", "主要合同摘要", "信用政策变更说明（如有）"],
        },
    )


def _r2_result(rows: list[dict[str, Any]], source_issues: list[str], min_gap: float) -> RuleResult:
    """R2 过渡工程版：方向比较前先阻断现金流基数过小或跨期变号的伪同比。"""
    if source_issues:
        return RuleResult(
            rule_id="R2",
            status="SOURCE_INCOMPLETE",
            source_validation=_base_source_validation(source_issues),
            metrics={
                "revenue_growth": None,
                "operating_cash_flow_growth": None,
                "growth_gap": None,
                "cashflow_to_revenue_current": None,
                "cashflow_to_revenue_previous": None,
                "net_profit_cashflow_gap": None,
            },
        )

    by_field = {row["field_id"]: row["value"] for row in rows}
    revenue_growth = _growth(by_field["revenue_current"], by_field["revenue_previous"])
    current_ocf = by_field["operating_cash_flow_current"]
    previous_ocf = by_field["operating_cash_flow_previous"]
    previous_revenue = by_field["revenue_previous"]
    cashflow_growth = _growth(current_ocf, previous_ocf)
    cashflow_to_revenue_current = current_ocf / by_field["revenue_current"] if by_field["revenue_current"] else None
    cashflow_to_revenue_previous = previous_ocf / previous_revenue if previous_revenue else None
    net_profit = by_field.get("net_profit_current")
    net_profit_cashflow_gap = (
        (current_ocf - net_profit) / abs(net_profit)
        if isinstance(net_profit, (int, float)) and net_profit > 0
        else None
    )

    if revenue_growth is None:
        return RuleResult(
            rule_id="R2",
            status="DATA_GAP",
            source_validation=_base_source_validation([]),
            metrics={
                "revenue_growth": revenue_growth,
                "operating_cash_flow_growth": cashflow_growth,
                "growth_gap": None,
                "cashflow_to_revenue_current": cashflow_to_revenue_current,
                "cashflow_to_revenue_previous": cashflow_to_revenue_previous,
                "net_profit_cashflow_gap": net_profit_cashflow_gap,
            },
            risk_card={
                "rule_id": "R2",
                "title": "R2无法计算：上年收入或经营活动现金流量净额为零",
                "data_gaps": ["需确认上年基数与可比口径"],
                "requested_materials": ["相关年度合并现金流量表及口径说明"],
            },
        )

    # 上年 OCF 很小或跨期变号时，百分比同比会出现数千个百分点而没有比较意义。
    # 此处只阻断错误展示，不等同于完成 R2 v0.2 的销售收现率、OCF 构成等完整规则。
    comparable = (
        previous_ocf != 0
        and abs(previous_ocf) >= abs(previous_revenue) * 0.03
        and current_ocf * previous_ocf > 0
    )
    if not comparable:
        if previous_ocf == 0:
            reason = "上年经营现金流为零"
        elif current_ocf == 0:
            reason = "本年经营现金流为零"
        elif current_ocf * previous_ocf < 0:
            reason = "经营现金流跨期变号"
        else:
            reason = "上年经营现金流基数过小"
        return RuleResult(
            rule_id="R2",
            status="DATA_NOT_COMPARABLE",
            source_validation=_base_source_validation([]),
            metrics={
                "revenue_growth": revenue_growth,
                "operating_cash_flow_growth": None,
                "growth_gap": None,
                "cashflow_to_revenue_current": cashflow_to_revenue_current,
                "cashflow_to_revenue_previous": cashflow_to_revenue_previous,
                "net_profit_cashflow_gap": net_profit_cashflow_gap,
            },
            risk_card={
                "rule_id": "R2",
                "engineering_version": "方向比较版（含可比性保护）",
                "status": "not_comparable_pending_human_review",
                "title": f"R2同比不宜比较：{reason}",
                "observation": (
                    f"营业收入增速为{revenue_growth:.2%}；本年经营活动现金流量净额为{current_ocf:,.2f}元，"
                    f"上年为{previous_ocf:,.2f}元。由于{reason}，系统不展示经营现金流同比或增速差，也不按方向规则形成候选。"
                ),
                "normal_explanations": ["经营现金流受采购、税费、存货及经营性往来变化等多因素共同影响"],
                "data_gaps": ["销售收现明细", "经营性应收应付变动明细", "经营现金流量表补充资料"],
                "requested_materials": ["季度现金流量表明细", "收入与销售收现调节表", "主要经营性项目变动说明"],
            },
        )

    growth_gap = revenue_growth - cashflow_growth
    candidate = revenue_growth > 0 and growth_gap > min_gap
    strengthened = bool(
        candidate
        and cashflow_to_revenue_current is not None
        and cashflow_to_revenue_previous is not None
        and cashflow_to_revenue_current < cashflow_to_revenue_previous
    )
    return RuleResult(
        rule_id="R2",
        status="candidate" if candidate else "RULE_NOT_TRIGGERED",
        source_validation=_base_source_validation([]),
        metrics={
            "revenue_growth": revenue_growth,
            "operating_cash_flow_growth": cashflow_growth,
            "growth_gap": growth_gap,
            "cashflow_to_revenue_current": cashflow_to_revenue_current,
            "cashflow_to_revenue_previous": cashflow_to_revenue_previous,
            "net_profit_cashflow_gap": net_profit_cashflow_gap,
        },
        risk_card={
            "rule_id": "R2",
            "engineering_version": "收入正增长下的经营现金流增速方向比较",
            "configured_min_gap": min_gap,
            "status": "candidate_pending_human_review" if candidate else "rule_not_triggered",
            "title": (
                "收入增长与经营现金流增速背离，且现金流占收入比下降，建议重点关注"
                if strengthened
                else "收入增长与经营现金流增速背离，建议进一步了解"
                if candidate
                else "按R2当前工程版未形成收入正增长下的现金流背离候选"
            ),
            "observation": (
                f"营业收入增速为{revenue_growth:.2%}，经营活动现金流量净额增速为{cashflow_growth:.2%}，"
                f"现金流增速落后{growth_gap:.2%}。按R2当前工程版形成待进一步了解候选；是否保留须人工复核。"
                if candidate
                else f"营业收入增速为{revenue_growth:.2%}，经营活动现金流量净额增速为{cashflow_growth:.2%}。"
                "R2只在收入正增长且现金流增速明显落后时触发；本次未形成方向候选，不代表现金流不存在其他需要关注的事项。"
            ),
            "normal_explanations": [
                "扩张期赊销或新业务账期拉长",
                "经营性应付项目集中支付",
                "存货备货增加占用资金",
                "行业回款周期整体拉长",
                "收入确认与现金回收存在结算时点差异",
            ],
            "data_gaps": ["季度或月度经营现金流明细", "经营性应收应付变动明细", "存货备货计划与订单支持", "主要客户信用期政策"],
            "requested_materials": ["季度现金流量表明细", "主要经营性应收应付项目变动明细", "存货备货订单或合同支持文件", "主要客户信用期政策说明"],
        },
    )


def _model_check_from_results(results: list[RuleResult], *, enabled: bool, model_id: str) -> ModelCheck:
    if not enabled:
        return ModelCheck(status="not_requested", model_id=model_id, detail="本次未请求三Agent调用。")
    steps = [step for result in results for step in result.agent_steps]
    statuses = [step.status for step in steps]
    if not statuses or all(status == "not_applicable" for status in statuses):
        return ModelCheck(status="not_applicable", model_id=model_id, detail="本次没有已触发规则，未调用模型。")
    if "config_missing" in statuses:
        return ModelCheck(status="config_missing", model_id=model_id, detail="未配置DEEPSEEK_API_KEY；未调用模型。")
    if "provider_unreachable" in statuses:
        return ModelCheck(status="provider_unreachable", model_id=model_id, detail="模型调用失败，已停止后续AI草稿链。")
    if "MODEL_OUTPUT_INVALID" in statuses:
        return ModelCheck(status="MODEL_OUTPUT_INVALID", model_id=model_id, detail="模型输出未通过JSON、证据ID或禁用词校验，已停止AI草稿链。")
    completed = [step for step in steps if step.status == "completed"]
    if len(completed) == 3:
        duration_ms = sum(step.duration_ms or 0 for step in completed)
        response_material = "".join(step.response_sha256 or "" for step in completed)
        return ModelCheck(
            status="model_success",
            model_id=model_id,
            duration_ms=duration_ms,
            response_sha256=hashlib.sha256(response_material.encode("utf-8")).hexdigest(),
            detail="三Agent已完成结构化输出；模型没有参与数字计算、来源定位或人工结论。",
        )
    return ModelCheck(status="MODEL_OUTPUT_INVALID", model_id=model_id, detail="AI草稿链未形成完整可验证结果。")


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
        detail="服务可用；模型状态仅表示配置是否存在，不表示已经完成真实三Agent调用。",
    )


@app.post("/api/runs", response_model=RunResponse)
def run_rules(request: RunRequest, http_request: Request) -> RunResponse:
    if request.case_id != CASE_ID:
        raise HTTPException(status_code=404, detail="当前后端只支持STD_DEV_T0开发样例。")
    try:
        context, sources = get_period_sources(request.current_year, tuple(request.rule_ids))
    except KeyError as error:
        raise HTTPException(status_code=422, detail="当前年度或规则没有已登记的连续开发样例。") from error

    context["scene"] = request.scene
    context["selected_rule_ids"] = request.rule_ids
    context["r2_min_gap"] = request.r2_min_gap
    context["agent_prompt_version"] = PROMPT_VERSION
    run_id = f"RUN-W3-{uuid.uuid4().hex[:12].upper()}"
    rule_results: list[RuleResult] = []
    sources_by_rule: dict[str, list[dict[str, Any]]] = {}
    for rule_id in request.rule_ids:
        rows = _rule_rows(sources, rule_id)
        sources_by_rule[rule_id] = rows
        issues = _validate_sources(rows, context["t0"])
        if rule_id == "R1":
            rule_results.append(_r1_result(rows, issues))
        else:
            rule_results.append(_r2_result(rows, issues, request.r2_min_gap))

    api_key, base_url, model_id = _model_settings()
    if request.check_model:
        _enforce_public_model_quota(http_request)
    for result in rule_results:
        result.agent_steps = run_agent_chain(
            run_id=run_id,
            rule_result=result,
            sources=sources_by_rule[result.rule_id],
            enabled=request.check_model,
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
        )

    all_issues = [issue for result in rule_results for issue in result.source_validation["issues"]]
    overall_status = "SOURCE_INCOMPLETE" if all_issues else "candidate" if any(result.status == "candidate" for result in rule_results) else "RULE_NOT_TRIGGERED"
    response = RunResponse(
        run_id=run_id,
        status=overall_status,
        context=context,
        source_validation=_base_source_validation(all_issues),
        sources=sources,
        rule_results=rule_results,
        model_check=_model_check_from_results(rule_results, enabled=request.check_model, model_id=model_id),
    )
    save_run(WORKSPACE_ROOT, response)
    return response


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
