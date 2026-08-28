"""B1/B2/B3 受控内部预评估执行器（AI 辅助预评分，非正式人工评分）。

行为约束：
- 同一冻结案例的 B1、B2、B3 各执行一次正式尝试，不挑选成功记录；
- B1 不调用外部模型；B2 仅一次单模型直接复核（无 RAG、无多 Agent）；
  B3 走确定性规则 + 案例 RAG + 知识检索 + 三 Agent + 事实语言闸门完整链；
- 除合同允许的一次受控修正（工具协议正确、事实语言校验失败）外不做通用重试；
- 每次运行立即落盘并追加统一 Markdown 台账；--resume 只跳过已完成组合；
- provider 失败按真实失败计入，保留脱敏失败码与摘要，不保存密钥；
- 默认拒绝未冻结合同。

用法示例：
  python scripts/run_controlled_b1_b3_prescore.py --freeze-only
  python scripts/run_controlled_b1_b3_prescore.py --groups B1,B2,B3
  python scripts/run_controlled_b1_b3_prescore.py --resume
  python scripts/run_controlled_b1_b3_prescore.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agents import (
    AGENT_OUTPUT_TOOL_NAME,
    THINKING_CONFIG,
    _agent_output_tool_for,
    _parse_json_content,
    _strict_tool_base_url,
    validate_agent_output,
)
from backend.app.main import app
from backend.app.prescore import prescore_group
from backend.app.schemas import AI_GENERATED_CONTENT_NOTICE, RuleResult

DEFAULT_EVALUATION_ID = "EVAL-20260825-B1B3-AI-PRESCORE-V1"
EVAL_ROOT = ROOT / "outputs" / "evaluation_v5"

# 冻结案例：分层标签只进入密封映射，不进入评分盲包。
# negative_confirmation 路线在当前 R1 下不可达（risk_card 恒带四项资料缺口），
# 因此在评估限制中如实记录缺失路线，不伪造第四案。
FROZEN_CASES = [
    {
        "case_id": "CNINFO_000858_T0_20260430",
        "company_name": "五粮液",
        "current_year": 2025,
        "t0": "2026-04-30",
        "rule_ids": ["R1"],
        "stratum": "risk_candidate",
        "selection_reason": "B1 确定性筛查为 candidate，属 risk_candidate 路线；来源、字段与案例 RAG 均可回查。",
    },
    {
        "case_id": "CNINFO_600938_T0_20260326",
        "company_name": "中国海油",
        "current_year": 2025,
        "t0": "2026-03-26",
        "rule_ids": ["R1"],
        "stratum": "industry_review",
        "selection_reason": "能源/矿业行业专用规则命中（specialized_rule=energy_mining_ar_revenue），属 industry_review 路线。",
    },
    {
        "case_id": "STD_DEV_T0",
        "company_name": "标准股份",
        "current_year": 2025,
        "t0": "2026-04-30",
        "rule_ids": ["R1"],
        "stratum": "evidence_gap_review",
        "selection_reason": "B1 为 RULE_NOT_TRIGGERED 且 risk_card 恒带四项资料缺口，属 evidence_gap_review 路线；主演示案例来源可回查。",
    },
]
GROUPS = ("B1", "B2", "B3")
SCORING_RULE_VERSION = "ai_prescore_v1"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _provider_failure_code(error: BaseException) -> str | None:
    """把 B2 直连异常归一为与三 Agent 链一致的脱敏失败码。"""
    explicit = getattr(error, "failure_code", None)
    if explicit:
        return str(explicit)
    if isinstance(error, TimeoutError):
        return "MODEL_PROVIDER_TIMEOUT"
    if isinstance(error, HTTPError):
        if error.code == 402:
            return "MODEL_PROVIDER_BALANCE_EXHAUSTED"
        if error.code in {401, 403}:
            return "MODEL_PROVIDER_AUTH_FAILED"
        if error.code == 429:
            return "MODEL_PROVIDER_RATE_LIMITED"
        return "MODEL_PROVIDER_REJECTED"
    if isinstance(error, (URLError, OSError)):
        return "MODEL_PROVIDER_UNREACHABLE"
    return None


def _validation_failure(error: BaseException) -> tuple[str, str]:
    """把 B2 硬校验异常拆成可行动的阶段码，保留总失败事实。"""
    message = str(error)
    if "evidence_id" in message or "证据包以外" in message:
        return "MODEL_EVIDENCE_VALIDATION_ERROR", "evidence"
    if "禁止定性" in message:
        return "MODEL_POLICY_VIOLATION", "policy"
    if (
        "事实语言" in message
        or "强阈值" in message
        or "趋势" in message
        or "未获支持的解释" in message
        or "待验证假设" in message
    ):
        return "MODEL_FACT_LANGUAGE_VALIDATION_ERROR", "fact_language"
    if "Schema" in message or "字段" in message or "类型" in message:
        return "MODEL_SCHEMA_VALIDATION_ERROR", "schema"
    return "MODEL_OUTPUT_VALIDATION_FAILED", "validation"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _run_git(*args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
        return proc.stdout.strip() or proc.stderr.strip()
    except Exception:
        return "unknown"


def _eval_dir(evaluation_id: str) -> Path:
    return EVAL_ROOT / evaluation_id


def _contract_path(evaluation_id: str) -> Path:
    return _eval_dir(evaluation_id) / "00_contract.json"


def _record_path(evaluation_id: str, case_id: str, group: str, attempt_id: str) -> Path:
    return _eval_dir(evaluation_id) / "runs" / f"{case_id}_{group}_{attempt_id}.json"


def _ledger_path(evaluation_id: str) -> Path:
    return _eval_dir(evaluation_id) / "B1_B2_B3_RUN_LEDGER.md"


def _case_input(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "current_year": case["current_year"],
        "rule_ids": case["rule_ids"],
        "r1_gap_threshold": 0.15,
        "r1_strong_gap_threshold": 0.30,
        "r1_absolute_threshold": 0.0,
        "planned_materiality": None,
    }


def _freeze_contract(evaluation_id: str, model_id: str, base_url: str) -> dict[str, Any]:
    """冻结评估合同：逐案例对输入、来源、规则、知识、提示词、模型配置做逐字节哈希。"""
    from backend.app.agents import PROMPT_VERSION
    from backend.app.rag import question_set
    from backend.app.signoff import current_r1_config_canonical

    manifest_bytes = (ROOT / "backend" / "competition_demo_cases.json").read_bytes()
    agents_bytes = (ROOT / "backend" / "app" / "agents.py").read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    cases = manifest.get("cases") or []
    if isinstance(cases, dict):
        cases = list(cases.values())
    by_id = {c["case_id"]: c for c in cases}

    contract = {
        "schema_version": "b1_b3_evaluation_contract_v2",
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
        "evaluation_id": evaluation_id,
        "frozen_at": _now(),
        "code_head": _run_git("rev-parse", "HEAD"),
        "groups": list(GROUPS),
        "scoring_rule_version": SCORING_RULE_VERSION,
        "model": {
            "model_id": model_id,
            "temperature": 0.1,
            "role_max_output_tokens": {"challenge": 1400, "counter": 1400, "review": 1600},
            "controlled_correction_allowed": 1,
            "retry_policy": "each group one formal attempt; one controlled correction only on tool-protocol-correct fact-language failure",
        },
        "b2_evidence_contract": {
            "schema_version": "b2_single_model_input_v1",
            "procedure_evidence_id_pattern": "PROC-{rule_id}-{current_year}",
            "field_claims": "原始金额、年报事实和原文摘录只能引用 field_evidence 中已存在的 evidence_id。",
            "computed_claims": "增速差、阈值判断、规则状态等程序计算只能引用 procedure_evidence 中的 PROC-* evidence_id。",
            "hypothesis_boundary": "没有证据的正常解释必须标记为 unverified_hypothesis，且文本明确包含‘待验证假设’。",
            "rag_enabled": False,
            "validator_policy": "不放宽 validate_agent_output；未知 evidence_id、越界主张和禁止表述均失败。",
        },
        "stop_conditions": [
            "任一组合完成或真实失败后不再重复执行",
            "provider 永久失败（鉴权/余额/配额）保留原始失败记录并停止该组合",
            "模型真实成功率低于 80% 时向项目队长告警，不自行更换模型",
        ],
        "r1_signoff": {
            "status": "captain_approved_for_competition_demo",
            "config_canonical_sha256": _sha256_bytes(current_r1_config_canonical().encode("utf-8")),
        },
        "knowledge_snapshot": json.loads(
            (ROOT / "backend" / "knowledge_sources.manifest.json").read_text(encoding="utf-8")
        ).get("frozen_at"),
        "agent_prompt_version": PROMPT_VERSION,
        "agents_py_sha256": _sha256_bytes(agents_bytes),
        "question_set_sha256": _sha256_json(question_set()),
        "case_set_selection_note": (
            "negative_confirmation 路线不可达：R1 的 risk_card 在 RULE_NOT_TRIGGERED 时仍无条件携带"
            "四项资料缺口，导致该状态在无专用行业规则时被归入 evidence_gap_review。"
        ),
        "cases": [],
    }
    for case in FROZEN_CASES:
        manifest_case = by_id.get(case["case_id"]) or {}
        docs = manifest_case.get("documents") or []
        file_hashes = [
            {"report_year": d.get("report_year"), "sha256": d.get("sha256")}
            for d in docs
            if isinstance(d, dict)
        ]
        contract["cases"].append(
            {
                "case_id": case["case_id"],
                "company_name": case["company_name"],
                "current_year": case["current_year"],
                "t0": case["t0"],
                "stratum": case["stratum"],
                "selection_reason": case["selection_reason"],
                "input_sha256": _sha256_json(_case_input(case)),
                "manifest_entry_sha256": _sha256_json(manifest_case),
                "source_file_hashes": file_hashes,
                "source_fingerprint": manifest_case.get("source_fingerprint"),
                "rag_index_version": manifest_case.get("rag_index_version"),
            }
        )
    # 对不含 sha256 字段本身的副本求哈希，避免自引用导致复算不一致。
    contract_payload = {key: value for key, value in contract.items() if key != "contract_sha256"}
    contract["contract_sha256"] = _sha256_json(contract_payload)
    return contract


def _b1_run(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    payload = dict(_case_input(case))
    payload["run_mode"] = "calculation_only"
    response = client.post("/api/runs", json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"B1 HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    if int(data.get("provider_call_count") or 0) != 0:
        raise RuntimeError("B1 确定性组不应调用外部模型。")
    data["execution_mode"] = "b1_calculation_only"
    return data


def _b2_prompt() -> str:
    return (
        "你是 B2 单模型基线，只能使用用户消息中的确定性计算、字段证据和程序结果卡。\n"
        "本组没有 RAG、反证 Agent 或人工结论。请调用 submit_agent_output 返回 review 结构。\n"
        "原始金额和年报事实必须引用 field_evidence 中已有 evidence_id；增速差、阈值和规则状态等程序计算必须引用 procedure_evidence 中的 PROC-* evidence_id。\n"
        "外部业务解释只能写“待验证假设”并留空 evidence_ids。\n"
        "不得声称未达到的强阈值已达到；趋势不可评价时不得声称周转显著变化。\n"
        "必须说明资料缺口和待索取资料。不得作专业认定或批准导出。\n"
        "只提交工具参数，不输出 Markdown、解释或代码围栏。"
    )


def _call_provider(
    api_key: str,
    base_url: str,
    model_id: str,
    payload: dict[str, Any],
    tool: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {
        "model": model_id,
        "temperature": 0.1,
        "max_tokens": 1600,
        "stream": False,
        "thinking": THINKING_CONFIG,
        "tools": [tool],
        "tool_choice": {"type": "function", "function": {"name": AGENT_OUTPUT_TOOL_NAME}},
        "messages": [
            {"role": "system", "content": _b2_prompt()},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    request = Request(
        f"{_strict_tool_base_url(base_url)}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        # OpenCode Go 的边缘防护会拒绝 urllib 默认 User-Agent（返回 403/1010），
        # 必须与 agents._call_model 一样显式携带应用 User-Agent。
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AuditTrace-Demo/1.0",
        },
        method="POST",
    )
    started = time.perf_counter()
    with urlopen(request, timeout=120) as response:
        raw = response.read()
    duration_ms = round((time.perf_counter() - started) * 1000)
    response_data = json.loads(raw.decode("utf-8"))
    choice = response_data["choices"][0]
    calls = choice["message"].get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise ValueError("B2 单模型未返回唯一工具参数")
    function = calls[0].get("function") or {}
    if function.get("name") != AGENT_OUTPUT_TOOL_NAME:
        raise ValueError("B2 单模型调用了未声明工具")
    parsed = _parse_json_content(function.get("arguments") or "")
    usage = response_data.get("usage") or {}
    metadata = {
        "request_sha256": _sha256_json(payload),
        "response_sha256": _sha256_bytes(raw),
        "duration_ms": duration_ms,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "finish_reason": choice.get("finish_reason"),
    }
    return parsed, metadata


def _b2_run(
    api_key: str,
    base_url: str,
    model_id: str,
    case: dict[str, Any],
    b1: dict[str, Any],
    evaluation_id: str,
) -> dict[str, Any]:
    """一次单模型直接复核（B2）。允许一次受控修正，不做通用重试。"""
    rule_result = b1["rule_results"][0]
    run_id = f"EVAL-B2-{uuid.uuid4().hex[:12].upper()}"
    sources = [
        row for row in b1.get("sources") or []
        if row.get("evidence_id") in set(rule_result.get("evidence_ids") or [])
    ]
    procedure_id = f"PROC-{rule_result['rule_id']}-{case['current_year']}"
    procedure_evidence = {
        "evidence_id": procedure_id,
        "evidence_type": "deterministic_rule_result",
        "field_label": f"{rule_result['rule_id']}程序筛查结果",
        "value": rule_result.get("status"),
        "unit": "status",
        "document_id": None,
        "source_file": None,
        "pdf_page": None,
        "locator": "程序计算结果卡；只支持程序计算事实，不代表原文事实或人工确认",
        "excerpt": str((rule_result.get("risk_card") or {}).get("observation") or f"{rule_result['rule_id']} 返回状态 {rule_result.get('status')}")[:500],
        "review_status": "program_calculated",
        "claim_scope": "procedure_result",
    }
    allowed_evidence_ids = set(rule_result.get("evidence_ids") or []) | {procedure_id}
    payload = {
        "schema_version": "b2_single_model_input_v1",
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
        "evaluation_id": evaluation_id,
        "run_id": run_id,
        "role": "review",
        "rule_result": {
            "rule_id": rule_result["rule_id"],
            "status": rule_result["status"],
            "metrics": rule_result["metrics"],
            "risk_card": rule_result["risk_card"],
        },
        "field_evidence": sources,
        "procedure_evidence": [procedure_evidence],
        "allowed_evidence_ids": sorted(allowed_evidence_ids),
        "group_boundary": "B2=确定性计算+一次模型草稿；无RAG、无三Agent、无人工评分。",
    }
    tool = _agent_output_tool_for("review", "R1", run_id)
    validated = None
    validation_status = "failed"
    validation_error = None
    validation_failure_stage = None
    correction_count = 0
    meta: dict[str, Any] = {}
    corrected_meta: dict[str, Any] | None = None
    raw_args: Any = None
    original_raw_args: Any = None
    failure_code: str | None = None

    try:
        raw_args, meta = _call_provider(api_key, base_url, model_id, payload, tool)
        original_raw_args = raw_args
        validated = validate_agent_output(
            raw_args,
            run_id=run_id,
            role="review",
            rule_id="R1",
            allowed_evidence_ids=allowed_evidence_ids,
            rule_result=RuleResult.model_validate(rule_result),
        ).model_dump(mode="json")
        validation_status = "passed"
    except Exception as error:
        failure_text = f"{type(error).__name__}: {error}"
        failure_code = _provider_failure_code(error)
        if failure_code is None:
            failure_code, validation_failure_stage = _validation_failure(error)
        # 受控修正：仅当工具协议已正确、且硬校验明确归类为事实语言失败时执行一次。
        # 证据绑定、Schema、政策和 provider 失败不得借“修正”变成第二次通用重试。
        if correction_count == 0 and failure_code == "MODEL_FACT_LANGUAGE_VALIDATION_ERROR":
            correction_count = 1
            correction_payload = dict(payload)
            correction_payload["semantic_correction"] = {
                "attempt": 1,
                "hint": "上一次草稿未通过确定性事实语言校验；请逐条核对阈值、趋势与证据支持后重新提交。",
            }
            try:
                raw_args, corrected_meta = _call_provider(api_key, base_url, model_id, correction_payload, tool)
                validated = validate_agent_output(
                    raw_args,
                    run_id=run_id,
                    role="review",
                    rule_id="R1",
                    allowed_evidence_ids=allowed_evidence_ids,
                    rule_result=RuleResult.model_validate(rule_result),
                ).model_dump(mode="json")
                validation_status = "passed_after_controlled_correction"
            except Exception as second_error:
                second_code = _provider_failure_code(second_error)
                if second_code is None:
                    second_code, validation_failure_stage = _validation_failure(second_error)
                failure_code = second_code or failure_code
                validation_error = (
                    f"{failure_text}；受控修正后仍失败：{type(second_error).__name__}: {second_error}"
                )
        else:
            validation_error = failure_text
            if failure_code is None:
                failure_code = "MODEL_OUTPUT_VALIDATION_FAILED"

    prompt_tokens = (meta.get("prompt_tokens") or 0) + (corrected_meta.get("prompt_tokens") or 0 if corrected_meta else 0)
    completion_tokens = (meta.get("completion_tokens") or 0) + (corrected_meta.get("completion_tokens") or 0 if corrected_meta else 0)
    total_duration = (meta.get("duration_ms") or 0) + (corrected_meta.get("duration_ms") or 0 if corrected_meta else 0)

    # 统一成评分可消费的标准 run 结构。
    scoring_rule = dict(rule_result)  # 保留完整 B1 rule_result（含 source_validation、evidence_ids）
    scoring_rule["ai_draft"] = validated
    scoring_run: dict[str, Any] = {
        "schema_version": "run_output_v2",
        "run_id": run_id,
        "status": "completed" if validation_status.startswith("passed") else "failed",
        "run_completeness": "complete_b2_single_model" if validation_status.startswith("passed") else "failed_b2_single_model",
        "screening_status": rule_result.get("screening_status") or rule_result["status"],
        "rule_results": [scoring_rule],
        "evidence_bundle": {
            "field_evidence": sources,
            "procedure_evidence": [procedure_evidence],
        },
        "sources": sources,
        "final_ai_draft": validated,
        "provider_call_count": 1 + correction_count,
        "controlled_correction_count": correction_count,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "duration_ms": total_duration,
        "execution_mode": "b2_single_model",
        "validation_status": validation_status,
        "failure_code": failure_code,
        "validation_failure_stage": validation_failure_stage,
        "validation_error": validation_error,
        "raw_tool_arguments": raw_args,
        "original_tool_arguments": original_raw_args,
        "original_response_sha256": (meta or {}).get("response_sha256"),
        "corrected_response_sha256": (corrected_meta or {}).get("response_sha256") if corrected_meta else None,
        "provider_metadata": meta,
        "corrected_metadata": corrected_meta,
        "model_id": model_id,
    }
    return scoring_run


def _b3_run(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    payload = dict(_case_input(case))
    payload["run_mode"] = "full_analysis"
    response = client.post("/api/runs", json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"B3 HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    data["execution_mode"] = "b3_full_chain"
    return data


def _record(
    evaluation_id: str,
    case: dict[str, Any],
    group: str,
    run: dict[str, Any],
    *,
    started_at: str,
    attempt_id: str,
) -> dict[str, Any]:
    status = run.get("status") or ("completed" if run.get("run_id") else "failed")
    record = {
        "schema_version": "b1_b3_prescore_record_v1",
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
        "evaluation_id": evaluation_id,
        "case_id": case["case_id"],
        "case_name": case["company_name"],
        "t0": case["t0"],
        "current_year": case["current_year"],
        "stratum": case["stratum"],
        "group": group,
        "attempt_id": attempt_id,
        "run_id": run.get("run_id"),
        "started_at": started_at,
        "ended_at": _now(),
        "duration_ms": run.get("duration_ms") or 0,
        "code_head": _run_git("rev-parse", "HEAD"),
        "model_id": run.get("model_id"),
        "provider_call_count": int(run.get("provider_call_count") or 0),
        "controlled_correction_count": int(run.get("controlled_correction_count") or 0),
        "status": status,
        "failure_code": run.get("failure_code"),
        "validation_failure_stage": run.get("validation_failure_stage"),
        "failure_summary": run.get("validation_error") or run.get("failure_summary"),
        "result": run,
        "prescore": prescore_group(group, run),
        "project_captain_score": None,
        "project_captain_comment": None,
        "formal_human_score_status": "pending",
    }
    record["record_sha256"] = _sha256_json(record)
    return record


def _append_ledger(evaluation_id: str, case: dict[str, Any], group: str, record: dict[str, Any]) -> None:
    ledger = _ledger_path(evaluation_id)
    prescore = record["prescore"]
    lines = [
        "",
        f"## {group} ｜ {case['company_name']}（{case['case_id']}）",
        "",
        f"- 分层盲编号：`{case['stratum']}`（密封映射，不进入评分盲包）",
        f"- 组别定义：{group}",
        f"- run ID：`{record['run_id'] or '无'}`；attempt ID：`{record['attempt_id']}`",
        f"- 时间：{record['started_at']} → {record['ended_at']}（{record['duration_ms']} ms）",
        f"- 代码 HEAD：`{record['code_head']}`",
        f"- 模型 ID：{record['model_id'] or '未调用'}；真实调用次数：{record['provider_call_count']}；受控修正次数：{record['controlled_correction_count']}",
        f"- 最终状态：`{record['status']}`",
        f"- 失败码：{record['failure_code'] or '无'}；失败摘要：{record['failure_summary'] or '无'}",
        f"- 校验阶段：`{record['validation_failure_stage'] or '不适用/未失败'}`",
        "",
        "### AI 辅助预评分（非正式人工评分）",
        "",
        f"总分：**{prescore['total']} / 100**（封顶原因：{prescore['cap_reason'] or '无'}；违约：{prescore['contract_violation']}）",
        "",
        "| 维度 | 得分 | 依据 |",
        "|---|---:|---|",
    ]
    for name, dim in prescore["dimensions"].items():
        lines.append(f"| {dim['label']} | {dim['score']}/{dim['max']} | {'；'.join(dim['evidence'])} |")
    lines.extend(
        [
            "",
            f"- 项目队长最终评分：____ / 100",
            f"- 项目队长意见：________________",
            f"- 正式人工评分状态：`{record['formal_human_score_status']}`",
            "",
            "---",
        ]
    )
    with open(ledger, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation-id", default=DEFAULT_EVALUATION_ID)
    parser.add_argument("--groups", default="B1,B2,B3")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()

    evaluation_id = str(args.evaluation_id).strip()
    groups = [g for g in str(args.groups).split(",") if g in GROUPS]
    if not groups:
        raise SystemExit("--groups 至少选择 B1/B2/B3 之一")
    out_dir = _eval_dir(evaluation_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs").mkdir(parents=True, exist_ok=True)

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model_id = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

    contract_path = _contract_path(evaluation_id)
    if not contract_path.is_file():
        if args.freeze_only or args.dry_run:
            contract = _freeze_contract(evaluation_id, model_id, base_url)
            with open(contract_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(contract, ensure_ascii=False, indent=2))
            print("frozen contract:", contract_path)
            print("contract_sha256:", contract["contract_sha256"])
            if args.freeze_only:
                return
        else:
            raise SystemExit("未找到冻结合同，请先执行 --freeze-only")
    else:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract_payload = {key: value for key, value in contract.items() if key != "contract_sha256"}
        if contract.get("contract_sha256") != _sha256_json(contract_payload):
            raise SystemExit("冻结合同哈希不一致，拒绝执行")

    ledger = _ledger_path(evaluation_id)
    if not ledger.is_file():
        with open(ledger, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(
                f"# B1/B2/B3 运行台账｜{evaluation_id}\n\n"
                f"> 追加式台账；每完成一个组合立即追加，不统一补写。\n"
                f"> 统一 AI 声明：{AI_GENERATED_CONTENT_NOTICE}\n"
            )

    if not api_key and ("B2" in groups or "B3" in groups):
        print("WARNING: DEEPSEEK_API_KEY 未配置；B2/B3 将按真实 provider 缺失记录失败。")
    if args.dry_run:
        print("DRY-RUN：不调用模型。将执行的组合：")
        for case in FROZEN_CASES:
            for group in groups:
                print("  ", case["case_id"], group)
        return

    client = TestClient(app)
    for case in FROZEN_CASES:
        for group in groups:
            attempt_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
            record_path = _record_path(evaluation_id, case["case_id"], group, attempt_id)
            if args.resume and record_path.is_file():
                print("resume skip:", case["case_id"], group)
                continue
            started_at = _now()
            print(f"== {case['case_id']} {group} ==", flush=True)
            try:
                if group == "B1":
                    run = _b1_run(client, case)
                elif group == "B2":
                    if not api_key:
                        run = {
                            "run_id": None,
                            "status": "failed",
                            "failure_code": "MODEL_API_KEY_MISSING",
                            "failure_summary": "DEEPSEEK_API_KEY 未配置，B2 未调用模型。",
                            "provider_call_count": 0,
                            "rule_results": [],
                            "evidence_bundle": {},
                            "sources": [],
                            "schema_version": "run_output_v2",
                        }
                    else:
                        b1 = _b1_run(client, case)
                        run = _b2_run(api_key, base_url, model_id, case, b1, evaluation_id)
                else:  # B3
                    run = _b3_run(client, case)
            except Exception as error:  # 真实失败如实落盘
                run = {
                    "run_id": None,
                    "status": "failed",
                    "failure_code": _provider_failure_code(error) or "EXECUTOR_EXCEPTION",
                    "failure_summary": f"{type(error).__name__}: {error}"[:800],
                    "provider_call_count": int(getattr(error, "provider_call_count", 0) or 0),
                    "rule_results": [],
                    "evidence_bundle": {},
                    "sources": [],
                    "schema_version": "run_output_v2",
                }
            record = _record(evaluation_id, case, group, run, started_at=started_at, attempt_id=attempt_id)
            with open(record_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, indent=2))
            _append_ledger(evaluation_id, case, group, record)
            print("  status:", record["status"], "prescore:", record["prescore"]["total"], "run:", record["run_id"], flush=True)

    print("done:", evaluation_id)


if __name__ == "__main__":
    main()
