"""巨潮年报自动导入任务状态机。

任务日志独立于现有 /api/runs 保存，便于回看搜索、下载、校验和建库过程。
每一步都以 JSON 持久化，服务重启后仍能区分已通过、失败和待人工状态。
本模块完成到 RAG 和字段候选，不直接调用外部模型，模型调用由主流程统一控制。
"""

from __future__ import annotations

import json
import hashlib
import re
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from .cases import get_case, get_financial_rows, register_cninfo_case
from .catalog import bootstrap_runtime_catalog, lookup_cached_document, resolve_analysis_source, sync_case_to_catalog
from .cninfo import CNInfoClient, CNInfoError, prepare_report_years
from .field_extraction import extract_cninfo_fields
from .industry_gate import evaluate_industry_gate
from .rag import prepare_index, retrieve, status as rag_status


PIPELINE_SCHEMA_VERSION = "cninfo_pipeline_v1"
# 步骤名称是前端进度条和失败定位的稳定协议，新增步骤需要同步文档和测试。
PIPELINE_STEP_NAMES = (
    "company_resolve",
    "announcement_search",
    "document_select",
    "download",
    "document_validate",
    "case_register",
    "rag_prepare",
    "rag_smoke_test",
    "field_extract",
    "field_validate",
    "analysis_run",
)
TASK_ID_PATTERN = re.compile(r"^CNINFO-[A-Z0-9]{8,32}$")


def _pipeline_dir(workspace_root: Path) -> Path:
    """创建任务目录；测试命名空间由现有环境变量统一隔离。"""

    # 运行目录跟随项目运行时命名空间，测试和演示可以互不污染。
    path = workspace_root / "backend" / "runtime" / "pipelines"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _task_path(workspace_root: Path, task_id: str) -> Path:
    """任务编号不能携带路径语义，读取时也再次执行白名单校验。"""

    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("非法巨潮任务编号。")
    return _pipeline_dir(workspace_root) / f"{task_id}.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _new_steps() -> dict[str, dict[str, Any]]:
    """所有步骤从 pending 开始，避免缺失键被误读成通过。"""

    return {name: {"status": "pending", "detail": "尚未执行。"} for name in PIPELINE_STEP_NAMES}


def _save_task(workspace_root: Path, task: dict[str, Any]) -> dict[str, Any]:
    """以临时文件替换任务 JSON，避免服务中断留下半个 JSON。"""

    # 原子替换确保接口读取到的始终是完整 JSON，而不是写入中间态。
    path = _task_path(workspace_root, task["task_id"])
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return task


def create_task(workspace_root: Path, request: dict[str, Any]) -> dict[str, Any]:
    """创建一个追加式巨潮导入任务。"""

    # 任务编号不复用案例编号，便于同一企业重复刷新时保留每次尝试。
    task_id = f"CNINFO-{uuid.uuid4().hex[:12].upper()}"
    task = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "task_id": task_id,
        "status": "queued",
        "request": deepcopy(request),
        "steps": _new_steps(),
        "attempt": 0,
        "created_at": _now(),
        "updated_at": _now(),
        "result": None,
        "errors": [],
    }
    return _save_task(workspace_root, task)


def load_task(workspace_root: Path, task_id: str) -> dict[str, Any] | None:
    """读取任务状态；坏日志按不存在处理，由接口返回稳定 404。"""

    path = _task_path(workspace_root, task_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def queue_retry(
    workspace_root: Path,
    task_id: str,
    *,
    request_update: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """保留上一轮结果后重置步骤，供人工确认企业或技术失败后重试。"""

    task = load_task(workspace_root, task_id)
    if task is None:
        raise ValueError("巨潮任务不存在。")
    active_statuses = {"searching", "downloading", "validating", "indexing", "extracting_fields", "analyzing"}
    if task.get("status") in active_statuses:
        # 正常执行时至少有一个步骤处于 running。若服务重启发生在两个步骤之间，
        # JSON 会遗留活动总状态但没有运行步骤；这类中断任务应允许人工重试。
        has_running_step = any(
            isinstance(step, dict) and step.get("status") == "running"
            for step in (task.get("steps") or {}).values()
        )
        if has_running_step:
            raise ValueError("任务仍在执行，不能重复提交。")
        task["errors"] = list(task.get("errors") or []) + [
            {
                "at": _now(),
                "code": "PIPELINE_INTERRUPTED",
                "message": "服务重启或进程退出导致任务中断，已允许保留历史后重试。",
                "detail": {"previous_status": task.get("status")},
            }
        ]
    # 重试前把上一轮摘要放入 history，失败原因和人工判断不会被覆盖。
    task.setdefault("history", []).append(
        {
            "attempt": task.get("attempt", 0),
            "status": task.get("status"),
            "result": task.get("result"),
            "error": task.get("error"),
            "errors": task.get("errors", []),
            "saved_at": _now(),
        }
    )
    if request_update:
        task["request"].update(request_update)
    task["status"] = "queued"
    task["steps"] = _new_steps()
    task["result"] = None
    task.pop("error", None)
    task["updated_at"] = _now()
    return _save_task(workspace_root, task)


def mark_analysis_failure(workspace_root: Path, task_id: str, error: Exception) -> dict[str, Any]:
    """记录完整分析编排失败，不把前面的 RAG 成功覆盖成完整成功。"""

    task = load_task(workspace_root, task_id)
    if task is None:
        raise ValueError("巨潮任务不存在。")
    payload = _error_payload(error)
    result = dict(task.get("result") or {})
    result["status"] = "needs_human"
    result["analysis"] = {"status": "failed", "error": payload, "run_completeness": "incomplete_analysis_orchestration"}
    task["result"] = result
    task["errors"] = list(task.get("errors") or []) + [{"at": _now(), **payload}]
    _set_step(workspace_root, task, "analysis_run", "failed", "完整分析 API 编排失败，未生成完成报告。", error=payload)
    _set_status(workspace_root, task, "needs_human", result=result, error=payload)
    return task


def _set_step(
    workspace_root: Path,
    task: dict[str, Any],
    name: str,
    status: str,
    detail: str,
    **extra: Any,
) -> None:
    """更新单步状态并同步总任务的更新时间。"""

    # 单步状态只允许写入预定义名称，防止前端出现无法解释的自由字段。
    if name not in task["steps"]:
        raise ValueError(f"未知流程步骤：{name}")
    task["steps"][name] = {"status": status, "detail": detail, **extra}
    task["updated_at"] = _now()
    _save_task(workspace_root, task)


def _set_status(workspace_root: Path, task: dict[str, Any], status: str, **extra: Any) -> None:
    """写入总状态和可追溯的结果摘要。"""

    # 总状态只描述当前阶段，详细原因仍保存在 steps 和 errors 中。
    task["status"] = status
    task["updated_at"] = _now()
    task.update(extra)
    _save_task(workspace_root, task)


def _error_payload(error: Exception) -> dict[str, Any]:
    """只输出稳定错误信息，不把异常对象或响应头原样暴露给前端。"""

    # 巨潮可预期错误使用业务编码，内部异常则隐藏具体堆栈和网络响应。
    if isinstance(error, CNInfoError):
        return {"code": error.code, "message": error.message, "detail": error.detail}
    return {"code": "PIPELINE_INTERNAL_ERROR", "message": f"流程执行失败：{type(error).__name__}。", "detail": {}}


def _needs_human(error: Exception) -> bool:
    """企业多候选、缺报、内容不符和字段不确定都由人工接管。"""

    # 这些状态不是程序崩溃，而是需要人工确认来源或目标企业的业务分支。
    if not isinstance(error, CNInfoError):
        return False
    return error.code in {
        "COMPANY_AMBIGUOUS",
        "COMPANY_NOT_FOUND",
        "ANNUAL_REPORT_NOT_FOUND",
        "PDF_CONTENT_MISMATCH",
        "PDF_PAGE_COUNT_INVALID",
        "PDF_PARSE_FAILED",
    }


def _cached_field_extraction(
    workspace_root: Path,
    case_id: str,
    *,
    rule_ids: list[str],
    requested_years: list[int],
) -> dict[str, Any]:
    """从已经验证过的案例字段读取热缓存，不重新扫描 PDF。"""

    rows = [
        row for row in get_financial_rows(workspace_root, case_id)
        if int(row.get("year", 0)) in set(requested_years)
    ]
    required = set()
    if "R1" in rule_ids:
        required.update({"revenue", "accounts_receivable"})
    if "R2" in rule_ids:
        required.update({"revenue", "operating_cash_flow"})
    found = {(row.get("field_kind"), int(row.get("year", 0))) for row in rows}
    issues = [
        f"{year}年缺少{kind}字段候选。"
        for year in requested_years
        for kind in sorted(required)
        if (kind, year) not in found
    ]
    status = "cached_ready" if rows and not issues else "cached_with_gaps" if rows else "failed"
    return {
        "status": status,
        "case_id": case_id,
        "rows": rows,
        "row_count": len(rows),
        "required_kinds": sorted(required),
        "optional_kinds": [],
        "issues": issues,
        "optional_missing": [],
        "available_years": sorted({int(row["year"]) for row in rows if not issues}, reverse=True),
        "human_review_required": False,
        "human_review_recommended": bool(rows),
        "formal_adoption_requires_human_review": True,
        "cache_reused": True,
    }


def _cached_result(
    workspace_root: Path,
    task: dict[str, Any],
    cached: dict[str, Any],
) -> dict[str, Any]:
    """把热缓存命中转换成与实时流程一致的任务摘要。"""

    request = task["request"]
    case_id = cached["case_id"]
    case = get_case(workspace_root, case_id)
    if case is None:
        raise ValueError("缓存命中的案例已不存在，已关闭本次缓存复用。")
    task["case_id"] = case_id
    task["company"] = {
        key: case.get(key)
        for key in ("ticker", "company_name", "company_alias", "org_id", "market", "column", "plate", "source_mode")
        if case.get(key) is not None
    }
    years = prepare_report_years(request.get("latest_year"), int(request.get("years", 3)))
    gate = evaluate_industry_gate(company=task["company"], case=case, rule_ids=request.get("rule_ids") or ["R1"])
    task["industry_gate"] = gate
    manifest = rag_status(workspace_root, case_id)
    if manifest.get("status") != "ready":
        raise ValueError("缓存案例的 RAG 索引已过期，已关闭缓存复用。")
    for step, detail in {
        "company_resolve": "已命中预热缓存并确认企业。",
        "announcement_search": "已读取缓存中的官方年报年度清单。",
        "document_select": "已复用已校验的当前全文版本。",
        "download": "已复用本地已校验 PDF；本次未重复下载。",
        "document_validate": "已复用来源哈希、页数和 PDF 校验结果。",
        "case_register": "已复用企业独立案例和来源快照。",
        "rag_prepare": "已复用来源指纹一致的 RAG 索引。",
        "rag_smoke_test": "已复用缓存 RAG；检索烟测仍保留运行记录。",
    }.items():
        _set_step(workspace_root, task, step, "passed", detail, cache_hit=True, snapshot_id=cached["snapshot_id"])
    smoke = retrieve(
        workspace_root,
        query="",
        question_id="RAG-Q1",
        t0=case["t0"],
        rule_id="R1",
        top_k=3,
        case_id=case_id,
        company_name=case["company_name"],
    )
    _set_step(
        workspace_root,
        task,
        "rag_smoke_test",
        "passed",
        "已复用缓存 RAG 并完成固定问题检索烟测。",
        cache_hit=True,
        snapshot_id=cached["snapshot_id"],
        retrieval_id=smoke["retrieval_id"],
        retrieval_status=smoke["status"],
        result_count=len(smoke["results"]),
    )
    if str(request.get("analysis_mode") or "full_analysis") == "rag_only":
        result = {
            "task_id": task["task_id"],
            "status": "rag_ready",
            "case_id": case_id,
            "company": task["company"],
            "report_years": years,
            "rag": {
                "status": manifest["status"],
                "chunk_count": manifest.get("chunk_count"),
                "index_version": manifest.get("index_version"),
                "smoke_retrieval_id": smoke["retrieval_id"],
                "smoke_status": smoke["status"],
                "smoke_result_count": len(smoke["results"]),
                "cache_hit": True,
                "snapshot_id": cached["snapshot_id"],
            },
            "industry_gate": gate,
            "cache": {
                "hit": True,
                "snapshot_id": cached["snapshot_id"],
                "source_fingerprint": cached["source_fingerprint"],
                "report_years": cached.get("report_years", years),
                "rag_index_version": cached.get("rag_index_version"),
                "cache_state": cached.get("cache_state", "ready"),
                "verified_at": cached.get("verified_at"),
                "cache_age_days": cached.get("cache_age_days"),
                "cache_max_age_days": cached.get("cache_max_age_days"),
            },
            "analysis": None,
            "human_review_required": True,
        }
        _set_status(workspace_root, task, "completed", result=result)
        return result

    if gate["fit_level"] in {"not_applicable", "unknown"}:
        extraction = {
            "status": "not_applicable" if gate["fit_level"] == "not_applicable" else "industry_unknown",
            "case_id": case_id,
            "rows": [],
            "row_count": 0,
            "required_kinds": [],
            "optional_kinds": [],
            "issues": [gate["rationale"]],
            "optional_missing": [],
            "available_years": [],
            "human_review_required": False,
            "human_review_recommended": True,
            "formal_adoption_requires_human_review": True,
            "skipped_by_industry_gate": True,
        }
    else:
        extraction = _cached_field_extraction(
            workspace_root,
            case_id,
            rule_ids=list(request.get("rule_ids") or ["R1"]),
            requested_years=years,
        )
    _set_step(
        workspace_root,
        task,
        "field_extract",
        "passed_with_gaps" if extraction["status"] == "cached_with_gaps" else "passed",
        "已复用缓存字段；未重新扫描 PDF。" if extraction["status"] not in {"not_applicable", "industry_unknown"} else "行业适配闸门已跳过当前规则字段提取。",
        extraction_summary={key: extraction.get(key) for key in ("row_count", "status", "available_years")},
        cache_hit=True,
    )
    _set_step(
        workspace_root,
        task,
        "field_validate",
        "passed_with_gaps" if extraction.get("issues") else "passed",
        "缓存字段版本可用；正式采用和导出前仍需人工复核。",
        available_years=extraction.get("available_years", []),
        issues=extraction.get("issues", []),
        cache_hit=True,
    )
    result = {
        "task_id": task["task_id"],
        "status": "ready_for_analysis",
        "case_id": case_id,
        "company": task["company"],
        "report_years": years,
        "rag": {"status": manifest["status"], "chunk_count": manifest.get("chunk_count"), "smoke_retrieval_id": smoke["retrieval_id"], "cache_hit": True, "snapshot_id": cached["snapshot_id"]},
        "industry_gate": gate,
        "field_extraction": extraction,
        "analysis": None,
        "human_review_required": False,
        "human_review_recommended": True,
        "formal_adoption_requires_human_review": True,
        "cache": {
            "hit": True,
            "snapshot_id": cached["snapshot_id"],
            "source_fingerprint": cached["source_fingerprint"],
            "report_years": cached.get("report_years", years),
            "rag_index_version": cached.get("rag_index_version"),
            "cache_state": cached.get("cache_state", "ready"),
            "verified_at": cached.get("verified_at"),
            "cache_age_days": cached.get("cache_age_days"),
            "cache_max_age_days": cached.get("cache_max_age_days"),
        },
    }
    _set_status(workspace_root, task, "ready_for_analysis", result=result)
    return result


def _close_running_step_after_error(
    workspace_root: Path,
    task: dict[str, Any],
    payload: dict[str, Any],
    *,
    needs_human: bool,
) -> None:
    """异常发生后关闭唯一的进行中步骤，避免总任务失败但步骤仍显示运行。"""

    active = next(
        (name for name, step in task.get("steps", {}).items() if step.get("status") == "running"),
        None,
    )
    if active is None:
        return
    # 任务只允许一个步骤处于运行态，异常时必须同步关闭该步骤。
    task["steps"][active] = {
        "status": "needs_human" if needs_human else "failed",
        "detail": str(payload.get("message") or "该步骤未完成。"),
        "error": payload,
    }
    task["updated_at"] = _now()
    _save_task(workspace_root, task)


def _document_id(ticker: str, year: int, sha256: str) -> str:
    """来源编号包含企业、年度和哈希前缀，便于页面和证据回查。"""

    return f"CNINFO-{ticker}-{year}-{sha256[:12]}".upper()


def run_ingestion(
    workspace_root: Path,
    task_id: str,
    *,
    client: CNInfoClient | None = None,
) -> dict[str, Any]:
    """执行搜索、下载、校验、登记、RAG 和字段候选提取。"""

    task = load_task(workspace_root, task_id)
    if task is None:
        raise ValueError("巨潮任务不存在。")
    task["attempt"] = int(task.get("attempt", 0)) + 1
    _set_status(workspace_root, task, "searching")
    request = task["request"]
    requested_years = prepare_report_years(request.get("latest_year"), int(request.get("years", 3)))
    cache_policy = str(request.get("cache_policy") or ("force_refresh" if request.get("force_refresh") else "prefer_cache"))
    if cache_policy != "force_refresh":
        # 目录只作为加速索引；任何读取异常都降级到既有巨潮实时流程。
        try:
            bootstrap_runtime_catalog(workspace_root)
            resolution = resolve_analysis_source(
                workspace_root,
                str(request.get("company_query") or ""),
                requested_years,
                cache_policy=cache_policy,
            )
            if resolution["hit"] and resolution.get("match"):
                result = _cached_result(workspace_root, task, resolution["match"])
                result.setdefault("cache", {}).update({"policy": cache_policy, "reason": resolution["reason"]})
                task["cache"] = result["cache"]
                _save_task(workspace_root, task)
                return result
        except (OSError, ValueError, TypeError):
            task["cache"] = {"hit": False, "fallback": "catalog_unavailable"}
    owns_client = client is None
    cninfo = client or CNInfoClient()
    # selected_reports 只保存最终版本，候选数量会另写入搜索步骤日志。
    selected_reports: list[dict[str, Any]] = []
    try:
        _set_step(workspace_root, task, "company_resolve", "running", "正在从巨潮公开股票清单确认企业。")
        company = cninfo.resolve_company(str(request["company_query"]))
        task["company"] = company
        _set_step(workspace_root, task, "company_resolve", "passed", "已确认唯一巨潮企业。", company=company)

        years = requested_years
        task["report_years"] = years
        _set_step(workspace_root, task, "announcement_search", "running", "正在查询目标年度报告公告。", years=years)
        candidates_by_year: dict[str, list[dict[str, Any]]] = {}
        for year in years:
            # 每个年度独立查询，缺一年度就停止，避免生成看似完整的断档案例。
            candidates = cninfo.search_annual_reports(company, year)
            candidates_by_year[str(year)] = candidates
            if not candidates:
                raise CNInfoError("ANNUAL_REPORT_NOT_FOUND", f"未找到 {year} 年年度报告全文。")
        _set_step(
            workspace_root,
            task,
            "announcement_search",
            "passed",
            f"已查询 {len(candidates_by_year)} 个年度。",
            # 候选数量用于解释为什么选择了当前全文版本。
            candidate_counts={year: len(rows) for year, rows in candidates_by_year.items()},
        )

        _set_step(workspace_root, task, "document_select", "running", "正在按全文、年度和修订版规则选择公告。")
        selected_reports = [
            cninfo.select_annual_report(candidates_by_year[str(year)], year) for year in years
        ]
        _set_step(
            workspace_root,
            task,
            "document_select",
            "passed",
            "已排除摘要和非全文公告。",
            selected=[
                {
                    "report_year": item["report_year"],
                    "announcement_title": item["announcement_title"],
                    "source_url": item["source_url"],
                    "candidate_count": item["candidate_count"],
                }
                for item in selected_reports
            ],
        )

        _set_status(workspace_root, task, "downloading")
        _set_step(workspace_root, task, "download", "running", "正在从巨潮静态原件下载 PDF。")
        downloaded: list[dict[str, Any]] = []
        reused_cached_count = 0
        for announcement in selected_reports:
            # 新年度到来时只下载 URL 发生变化的报告；历史年度沿用已校验的本地 PDF，
            # 仍会重新计算哈希并走同一份 PDF 身份校验，避免把“增量”变成信任旁路。
            cached_document = lookup_cached_document(
                workspace_root,
                str(company["ticker"]),
                int(announcement["report_year"]),
                str(announcement["source_url"]),
            )
            cached_path = None
            if cached_document and cached_document.get("storage_relpath"):
                candidate = (workspace_root / str(cached_document["storage_relpath"])).resolve()
                try:
                    candidate.relative_to(workspace_root.resolve())
                except ValueError:
                    candidate = None
                if candidate and candidate.is_file():
                    content = candidate.read_bytes()
                    digest = hashlib.sha256(content).hexdigest().upper()
                    if digest == str(cached_document.get("sha256") or "").upper():
                        cached_path = candidate
                        download_meta = {
                            "final_url": str(announcement["source_url"]),
                            "byte_count": len(content),
                            "sha256": digest,
                            "cache_reused": True,
                        }
                        reused_cached_count += 1
            if cached_path is None:
                # 下载后的内容先留在内存中，全部通过硬校验后才进入案例目录。
                content, download_meta = cninfo.download_pdf(announcement["source_url"])
            downloaded.append({"announcement": announcement, "content": content, **download_meta})
        _set_step(
            workspace_root,
            task,
            "download",
            "passed",
            f"已取得 {len(downloaded)} 份 PDF，其中 {reused_cached_count} 份复用已校验历史文件。",
            files=[
                {"report_year": item["announcement"]["report_year"], "bytes": item["byte_count"], "sha256": item["sha256"]}
                for item in downloaded
            ],
            cache_reused_count=reused_cached_count,
        )

        _set_step(workspace_root, task, "document_validate", "running", "正在校验 PDF 文件头、页数、企业和报告年度。")
        validated: list[dict[str, Any]] = []
        for item in downloaded:
            # 企业、年度、PDF 文件头和哈希校验全部通过才允许进入 RAG。
            validation = cninfo.validate_pdf(item["content"], item["announcement"], company)
            validated.append(
                {
                    **item["announcement"],
                    "document_id": _document_id(company["ticker"], item["announcement"]["report_year"], item["sha256"]),
                    "content": item["content"],
                    "final_url": item["final_url"],
                    **validation,
                }
            )
        _set_step(
            workspace_root,
            task,
            "document_validate",
            "passed",
            "所有 PDF 通过来源和内容硬校验。",
            # 每份校验摘要都保留哈希和页数，便于外部评审复核。
            documents=[
                {
                    key: item[key]
                    for key in ("document_id", "report_year", "announcement_title", "announcement_date", "source_url", "sha256", "byte_count", "page_count", "content_checks")
                }
                for item in validated
            ],
        )

        _set_step(workspace_root, task, "case_register", "running", "正在创建企业独立案例目录。")
        latest_t0 = max(item["announcement_date"] for item in validated)
        case_id = f"CNINFO_{company['ticker']}_T0_{latest_t0.replace('-', '')}"
        case = register_cninfo_case(
            workspace_root,
            case_id=case_id,
            company=company,
            documents=validated,
        )
        task["case_id"] = case_id
        industry_gate = evaluate_industry_gate(company=company, case=case, rule_ids=request.get("rule_ids") or ["R1"])
        task["industry_gate"] = industry_gate
        _set_step(
            workspace_root,
            task,
            "case_register",
            "passed",
            "已登记企业独立案例；财务字段仍待候选提取和人工确认。",
            # 案例登记完成后才允许建立 RAG，保证索引一定绑定明确 case_id。
            case_id=case_id,
            source_snapshot_id=case["source_snapshot_id"],
        )

        _set_status(workspace_root, task, "indexing")
        _set_step(workspace_root, task, "rag_prepare", "running", "正在建立案例隔离 RAG 索引。")
        index_manifest = prepare_index(workspace_root, case_id=case_id, force=bool(request.get("force_refresh", False)))
        cache_info = sync_case_to_catalog(
            workspace_root,
            case,
            rows=[],
            rag_manifest=index_manifest,
            industry_gate=industry_gate,
        )
        cache_info.update(
            {
                "policy": cache_policy,
                "reason": "force_refresh_completed" if cache_policy == "force_refresh" else "live_snapshot_created",
            }
        )
        _set_step(
            workspace_root,
            task,
            "rag_prepare",
            "passed",
            "RAG 索引已完成。",
            # 索引摘要只记录可复核元数据，不把整本年报复制到任务日志。
            index={key: index_manifest.get(key) for key in ("index_version", "source_count", "chunk_count", "source_fingerprint", "built_at", "rebuilt")},
        )

        _set_step(workspace_root, task, "rag_smoke_test", "running", "正在执行固定问题检索烟测。")
        smoke = retrieve(
            workspace_root,
            query="",
            question_id="RAG-Q1",
            t0=case["t0"],
            rule_id="R1",
            top_k=3,
            case_id=case_id,
            company_name=case["company_name"],
        )
        _set_step(
            workspace_root,
            task,
            "rag_smoke_test",
            "passed",
            "检索接口完成；命中或无命中均保留为可复核结果。",
            # 烟测只证明索引和检索链路可用，不代替财务字段的专业判断。
            retrieval_id=smoke["retrieval_id"],
            retrieval_status=smoke["status"],
            result_count=len(smoke["results"]),
        )

        analysis_mode = str(request.get("analysis_mode") or "full_analysis")
        if analysis_mode == "rag_only":
            # rag_only 是公开数据演示的安全默认路径，不涉及模型传输和财务字段猜测。
            result = {
                "task_id": task_id,
                "status": "rag_ready",
                "case_id": case_id,
                "company": company,
                "report_years": years,
                "documents": [
                    {
                        key: item.get(key)
                        for key in ("document_id", "report_year", "announcement_title", "announcement_date", "source_url", "sha256", "byte_count", "page_count", "validation_status", "candidate_count")
                    }
                    for item in validated
                ],
                "rag": {
                    "status": index_manifest["status"],
                    "chunk_count": index_manifest["chunk_count"],
                    "index_version": index_manifest["index_version"],
                    "smoke_retrieval_id": smoke["retrieval_id"],
                    "smoke_status": smoke["status"],
                    "smoke_result_count": len(smoke["results"]),
                    "cache_hit": False,
                },
                "industry_gate": industry_gate,
                "cache": cache_info,
                "analysis": None,
                "human_review_required": True,
            }
            _set_status(workspace_root, task, "completed", result=result)
            return result

        _set_status(workspace_root, task, "extracting_fields")
        if industry_gate["fit_level"] in {"not_applicable", "unknown"}:
            extraction = {
                "status": "not_applicable" if industry_gate["fit_level"] == "not_applicable" else "industry_unknown",
                "case_id": case_id,
                "rows": [],
                "row_count": 0,
                "required_kinds": [],
                "optional_kinds": [],
                "issues": [industry_gate["rationale"]],
                "optional_missing": [],
                "available_years": [],
                "human_review_required": False,
                "human_review_recommended": True,
                "formal_adoption_requires_human_review": True,
                "skipped_by_industry_gate": True,
            }
            _set_step(workspace_root, task, "field_extract", "passed", "行业适配闸门已跳过当前规则字段提取。", extraction_summary={"status": extraction["status"], "row_count": 0})
            _set_step(workspace_root, task, "field_validate", "passed", "行业适配闸门通过；当前规则不适用，等待行业专用规则。", available_years=[], issues=[])
            _set_status(
                workspace_root,
                task,
                "ready_for_analysis",
                result={
                    "task_id": task_id,
                    "status": "ready_for_analysis",
                    "case_id": case_id,
                    "company": company,
                    "report_years": years,
                    "rag": {"status": index_manifest["status"], "chunk_count": index_manifest["chunk_count"], "smoke_retrieval_id": smoke["retrieval_id"], "cache_hit": False},
                    "industry_gate": industry_gate,
                    "cache": cache_info,
                    "field_extraction": extraction,
                    "analysis": None,
                    "human_review_required": False,
                    "human_review_recommended": True,
                    "formal_adoption_requires_human_review": True,
                },
            )
            return task["result"]
        # 完整分析前先形成字段候选；公开预筛允许带着明确缺口继续运行。
        _set_step(workspace_root, task, "field_extract", "running", "正在从年报表格附近提取结构化字段候选。")
        extraction = extract_cninfo_fields(
            workspace_root,
            case_id,
            rule_ids=list(request.get("rule_ids") or ["R1"]),
            requested_years=years,
        )
        if extraction["status"] == "failed":
            _set_step(workspace_root, task, "field_extract", "failed", "未形成任何字段候选。", extraction=extraction)
            raise CNInfoError("FIELD_EXTRACTION_FAILED", "未形成可用财务字段候选。", detail=extraction)
        _set_step(workspace_root, task, "field_extract", "passed", "已形成财务字段候选。", extraction_summary={key: extraction.get(key) for key in ("row_count", "status", "available_years")})
        _set_step(workspace_root, task, "field_validate", "running", "正在检查年度连续性、来源页码和计算口径。")
        validation_status = "passed_with_gaps" if extraction["status"] == "passed_technical_with_gaps" else "passed"
        validation_detail = (
            "字段技术校验通过；部分年度或规则字段缺失，系统将按可比期间降级预筛。"
            if validation_status == "passed_with_gaps"
            else "字段技术校验通过；人工复核保留为正式采用和导出前的推荐步骤。"
        )
        _set_step(
            workspace_root,
            task,
            "field_validate",
            validation_status,
            validation_detail,
            available_years=extraction["available_years"],
            issues=extraction["issues"],
        )
        refreshed_case = get_case(workspace_root, case_id) or case
        cache_info = sync_case_to_catalog(
            workspace_root,
            refreshed_case,
            rows=extraction["rows"],
            rag_manifest=index_manifest,
            industry_gate=industry_gate,
        )
        cache_info.update(
            {
                "policy": cache_policy,
                "reason": "force_refresh_completed" if cache_policy == "force_refresh" else "live_snapshot_created",
            }
        )
        _set_status(
            workspace_root,
            task,
            "ready_for_analysis",
            result={
                "task_id": task_id,
                "status": "ready_for_analysis",
                "case_id": case_id,
                "company": company,
                "report_years": years,
                "rag": {"status": index_manifest["status"], "chunk_count": index_manifest["chunk_count"], "smoke_retrieval_id": smoke["retrieval_id"]},
                "industry_gate": industry_gate,
                "cache": cache_info,
                "field_extraction": extraction,
                "analysis": None,
                "human_review_required": False,
                "human_review_recommended": extraction.get("human_review_recommended", True),
                "formal_adoption_requires_human_review": True,
            },
        )
        return task["result"]
    except Exception as error:
        payload = _error_payload(error)
        task["errors"] = list(task.get("errors") or []) + [{"at": _now(), **payload}]
        status = "needs_human" if _needs_human(error) else "failed"
        if isinstance(error, CNInfoError) and error.code.startswith("FIELD_"):
            status = "needs_human"
        _close_running_step_after_error(
            workspace_root,
            task,
            payload,
            needs_human=status == "needs_human",
        )
        _set_status(workspace_root, task, status, error=payload)
        return {"task_id": task_id, "status": status, "error": payload, "case_id": task.get("case_id")}
    finally:
        if owns_client:
            cninfo.close()


def update_analysis_result(workspace_root: Path, task_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
    """把现有 /api/runs 的真实结果挂回任务，不重新解释模型状态。"""

    # 分析结果只挂回对应任务，不改变年报文件、RAG 索引或历史任务。
    task = load_task(workspace_root, task_id)
    if task is None:
        raise ValueError("巨潮任务不存在。")
    result = dict(task.get("result") or {})
    result["analysis"] = analysis
    run_completeness = str(analysis.get("run_completeness") or "")
    if run_completeness.startswith("complete_"):
        status = "completed"
        detail = "完整分析 API 已返回真实运行记录；人工复核仍未替代。"
    else:
        status = "needs_human"
        detail = "分析 API 已返回，但完整性未通过或模型传输仍关闭。"
    result["status"] = status
    task["result"] = result
    _set_step(workspace_root, task, "analysis_run", "passed" if run_completeness.startswith("complete_") else "needs_human", detail, run_id=analysis.get("run_id"), run_completeness=run_completeness)
    _set_status(workspace_root, task, status, result=result)
    return task
