"""审迹智链的受约束三Agent调用与校验。

这里不模拟模型成功：无Key、网络失败、JSON无效或引用越界时，都返回可回看的失败状态。
"""

from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from .schemas import AgentOutput, AgentRole, AgentStep, RuleResult


FORBIDDEN_TERMS = ("舞弊", "造假", "确认存在重大错报", "违法", "审计意见", "投资建议")
ROLE_ORDER: tuple[AgentRole, ...] = ("challenge", "counter", "review")
ROLE_ALLOWED_STATUSES: dict[AgentRole, list[str]] = {
    "challenge": ["candidate"],
    "counter": ["candidate", "defer"],
    "review": ["retain", "downgrade", "defer"],
}
PROMPT_VERSION = "agent_prompt_v1"
ROLE_MAX_OUTPUT_TOKENS: dict[AgentRole, int] = {"challenge": 1000, "counter": 1000, "review": 1000}
# 这里要求模型直接返回受约束 JSON；关闭深度思考，避免只产生 reasoning_content 而没有可校验的 content。
THINKING_CONFIG = {"type": "disabled"}
AGENT_OUTPUT_TOOL_NAME = "submit_agent_output"

# DeepSeek strict Tool Call 的参数模式。它不是让模型执行外部动作，而是把模型的语义草稿
# 放进一份由服务端约束的 JSON 参数中；程序仍会再次校验角色、规则、证据编号和禁用词。
AGENT_OUTPUT_TOOL = {
    "type": "function",
    "function": {
        "name": AGENT_OUTPUT_TOOL_NAME,
        "strict": True,
        "description": "提交一份仅基于本次证据包的审计前置语义草稿。",
        "parameters": {
            "type": "object",
            "properties": {
                "schema_version": {"type": "string", "enum": ["agent_output_v1"]},
                "run_id": {"type": "string"},
                "role": {"type": "string", "enum": ["challenge", "counter", "review"]},
                "rule_id": {"type": "string", "enum": ["R1", "R2"]},
                "status": {"type": "string", "enum": ["candidate", "retain", "downgrade", "defer"]},
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["text", "evidence_ids"],
                        "additionalProperties": False,
                    },
                },
                "normal_explanations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["text", "evidence_ids"],
                        "additionalProperties": False,
                    },
                },
                "data_gaps": {"type": "array", "items": {"type": "string"}},
                "requested_materials": {"type": "array", "items": {"type": "string"}},
                "reason_for_status": {"type": "string"},
            },
            "required": [
                "schema_version",
                "run_id",
                "role",
                "rule_id",
                "status",
                "claims",
                "normal_explanations",
                "data_gaps",
                "requested_materials",
                "reason_for_status",
            ],
            "additionalProperties": False,
        },
    },
}


def _agent_output_tool_for(role: AgentRole, rule_id: str, run_id: str) -> dict[str, Any]:
    """把角色、规则和本次运行号一并缩进严格Schema，避免跨角色状态或串单。"""
    tool = deepcopy(AGENT_OUTPUT_TOOL)
    properties = tool["function"]["parameters"]["properties"]
    properties["run_id"]["enum"] = [run_id]
    properties["role"]["enum"] = [role]
    properties["rule_id"]["enum"] = [rule_id]
    properties["status"]["enum"] = ROLE_ALLOWED_STATUSES[role]
    return tool

ROLE_INSTRUCTIONS: dict[AgentRole, str] = {
    "challenge": "提出需要进一步了解的风险假设；不得作事实认定。",
    "counter": "只在同一证据包中寻找正常解释、相反材料或资料缺口；找不到必须如实说明。",
    "review": "检查前两步是否超出证据；只建议保留、降级或暂缓，不能新增事实。",
}


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _compact_evidence_bundle(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只把本次已登记的字段来源交给模型，避免模型借外部知识补写页码或事实。"""
    return [
        {
            "evidence_id": row["evidence_id"],
            "field_label": row["field_label"],
            "value": row["value"],
            "unit": row["unit"],
            "source_file": row["source_file"],
            "disclosure_date": row["disclosure_date"],
            "pdf_page": row["pdf_page"],
            "print_page": row["print_page"],
            "locator": row["locator"],
        }
        for row in sources
    ]


def _system_prompt(role: AgentRole) -> str:
    return f"""你是“审迹智链”的{role} Agent，服务于会计师事务所审计前置阶段。

任务：{ROLE_INSTRUCTIONS[role]}
只使用用户消息中的规则计算结果和 evidence_bundle，不得搜索网页、使用公司记忆或补全未提供事实。
不得认定舞弊、重大错报、违法，不得出具审计意见或投资建议。
每条 claim 必须绑定至少一个已有 evidence_id；没有可核验证据时写入 data_gaps 或 requested_materials。
不得改写程序计算的数字、公式、页码、原文定位或规则触发结论。
为保证可复核和展示简洁：claims 只写1条；normal_explanations最多2条；data_gaps和requested_materials各最多3条；
每条文字尽量不超过40个汉字，reason_for_status不超过80个汉字；不要重复数字或整段复述证据。
必须调用 submit_agent_output 提交结果，不要输出可见文字、Markdown或代码围栏。"""


def _user_payload(
    run_id: str,
    role: AgentRole,
    rule_result: RuleResult,
    evidence_bundle: list[dict[str, Any]],
    previous_outputs: dict[str, AgentOutput],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "agent_output_v1",
        "run_id": run_id,
        "role": role,
        "rule_result": {
            "rule_id": rule_result.rule_id,
            "status": rule_result.status,
            "metrics": rule_result.metrics,
            "risk_card": rule_result.risk_card,
        },
        "evidence_bundle": evidence_bundle,
        "output_contract": {
            "schema_version": "agent_output_v1",
            "role": role,
            "rule_id": rule_result.rule_id,
            "status": "challenge返回candidate；counter返回candidate或defer；review返回retain、downgrade或defer",
            "claims": [{"text": "待进一步了解的简短表述", "evidence_ids": ["本次证据ID"]}],
            "normal_explanations": [],
            "data_gaps": [],
            "requested_materials": [],
            "reason_for_status": "仅基于本次证据包的简短说明",
        },
    }
    if role in {"counter", "review"}:
        payload["challenge"] = previous_outputs["challenge"].model_dump(mode="json")
    if role == "review":
        payload["counter"] = previous_outputs["counter"].model_dump(mode="json")
    return payload


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    parsed = json.loads(text.strip())
    if not isinstance(parsed, dict):
        raise ValueError("模型输出不是JSON对象")
    return parsed


def _strict_tool_base_url(base_url: str) -> str:
    """DeepSeek strict Tool Call 需要 beta 路径；保留用户填写的自定义 beta 地址。"""
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/beta") else f"{normalized}/beta"


def validate_agent_output(
    payload: dict[str, Any],
    *,
    run_id: str,
    role: AgentRole,
    rule_id: str,
    allowed_evidence_ids: set[str],
) -> AgentOutput:
    """模型JSON必须与本次运行完全绑定；任何越界引用都属于硬失败。"""
    output = AgentOutput.model_validate(payload)
    if output.run_id != run_id or output.role != role or output.rule_id != rule_id:
        raise ValueError("模型输出的run_id、role或rule_id与本次运行不一致")

    if role == "challenge" and output.status != "candidate":
        raise ValueError("质疑角色只能返回candidate")
    if role == "counter" and output.status not in {"candidate", "defer"}:
        raise ValueError("反证角色状态不允许")
    if role == "review" and output.status not in {"retain", "downgrade", "defer"}:
        raise ValueError("语义复核角色状态不允许")

    for claim in output.claims:
        if not claim.evidence_ids:
            raise ValueError("模型主张缺少evidence_id")
    for claim in [*output.claims, *output.normal_explanations]:
        if not set(claim.evidence_ids).issubset(allowed_evidence_ids):
            raise ValueError("模型引用了本次证据包以外的evidence_id")
        if any(term in claim.text for term in FORBIDDEN_TERMS):
            raise ValueError("模型输出包含禁止定性用语")
    if any(term in output.reason_for_status for term in FORBIDDEN_TERMS):
        raise ValueError("模型输出包含禁止定性用语")
    return output


def _call_model(
    *, api_key: str, base_url: str, model_id: str, role: AgentRole, payload: dict[str, Any]
) -> tuple[dict[str, Any], int, str, str, int | None, int | None]:
    output_tool = _agent_output_tool_for(
        role,
        str(payload["rule_result"]["rule_id"]),
        str(payload["run_id"]),
    )
    request_body = {
        "model": model_id,
        "temperature": 0.1,
        "max_tokens": ROLE_MAX_OUTPUT_TOKENS[role],
        "stream": False,
        "thinking": THINKING_CONFIG,
        "tools": [output_tool],
        "tool_choice": {"type": "function", "function": {"name": AGENT_OUTPUT_TOOL_NAME}},
        "messages": [
            {"role": "system", "content": _system_prompt(role)},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    request = Request(
        f"{_strict_tool_base_url(base_url)}/chat/completions",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urlopen(request, timeout=35) as response:
        raw = response.read()
    duration_ms = round((time.perf_counter() - started) * 1000)
    response_data = json.loads(raw.decode("utf-8"))
    choice = response_data["choices"][0]
    finish_reason = choice.get("finish_reason") or "unknown"
    if finish_reason == "length":
        raise ValueError("模型工具参数超过本角色输出上限")
    tool_calls = choice["message"].get("tool_calls")
    if not isinstance(tool_calls, list) or len(tool_calls) != 1:
        raise ValueError(f"模型未返回受约束的工具参数（finish_reason={finish_reason}）")
    function = tool_calls[0].get("function") if isinstance(tool_calls[0], dict) else None
    if not isinstance(function, dict) or function.get("name") != AGENT_OUTPUT_TOOL_NAME:
        raise ValueError("模型调用了未声明的输出工具")
    arguments = function.get("arguments")
    if not isinstance(arguments, str) or not arguments.strip():
        raise ValueError("模型未返回可解析的工具参数")
    usage = response_data.get("usage") or {}
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    return (
        _parse_json_content(arguments),
        duration_ms,
        hashlib.sha256(raw).hexdigest(),
        _json_hash(payload),
        input_tokens if isinstance(input_tokens, int) else None,
        output_tokens if isinstance(output_tokens, int) else None,
    )


def run_agent_chain(
    *,
    run_id: str,
    rule_result: RuleResult,
    sources: list[dict[str, Any]],
    enabled: bool,
    api_key: str | None,
    base_url: str,
    model_id: str,
) -> list[AgentStep]:
    """串行执行三角色；任一步失败即关闭AI草稿链，不生成伪造的后续角色答案。"""
    if rule_result.status != "candidate":
        return [AgentStep(role="challenge", status="not_applicable", detail="规则未触发，未调用模型。")]
    if not enabled:
        return [AgentStep(role="challenge", status="not_requested", detail="本次未请求三Agent调用。")]
    if not api_key:
        return [AgentStep(role="challenge", status="config_missing", model_id=None, prompt_version=PROMPT_VERSION, detail="未配置DEEPSEEK_API_KEY；未调用模型。")]

    evidence_bundle = _compact_evidence_bundle(sources)
    allowed_evidence_ids = {item["evidence_id"] for item in evidence_bundle}
    previous_outputs: dict[str, AgentOutput] = {}
    steps: list[AgentStep] = []
    for role in ROLE_ORDER:
        payload = _user_payload(run_id, role, rule_result, evidence_bundle, previous_outputs)
        input_sha256 = _json_hash(payload)
        try:
            raw_output, duration_ms, response_sha256, _, input_tokens, output_tokens = _call_model(
                api_key=api_key,
                base_url=base_url,
                model_id=model_id,
                role=role,
                payload=payload,
            )
            output = validate_agent_output(
                raw_output,
                run_id=run_id,
                role=role,
                rule_id=rule_result.rule_id,
                allowed_evidence_ids=allowed_evidence_ids,
            )
        except (HTTPError, URLError, TimeoutError) as error:
            steps.append(AgentStep(role=role, status="provider_unreachable", model_id=model_id, prompt_version=PROMPT_VERSION, detail=f"模型调用失败：{type(error).__name__}", input_sha256=input_sha256))
            break
        except (json.JSONDecodeError, KeyError, IndexError, UnicodeDecodeError, ValidationError, ValueError) as error:
            steps.append(AgentStep(role=role, status="MODEL_OUTPUT_INVALID", model_id=model_id, prompt_version=PROMPT_VERSION, detail=f"模型输出未通过结构化校验：{type(error).__name__}", input_sha256=input_sha256))
            break
        else:
            previous_outputs[role] = output
            steps.append(
                AgentStep(
                    role=role,
                    status="completed",
                    detail="已完成结构化输出并通过evidence_id与禁用词校验。",
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    input_sha256=input_sha256,
                    response_sha256=response_sha256,
                    duration_ms=duration_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    output=output,
                )
            )
    return steps
