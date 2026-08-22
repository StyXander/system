"""审迹智链的受约束三 Agent 调用、证据闸门与失败分类。

本模块处理模型语义推理，但不负责确定财务字段是否正确。
程序筛查先于模型调用，模型不能改变确定性计算的原始结果。
质疑角色只能提出受证据支持的候选主张或未触发复核问题，不形成最终草稿。
反证角色必须寻找正常解释、口径限制和相反证据，不负责下结论。
复核角色综合前两步，才允许提交非空的待核查草稿。
三个角色依次执行，前一步失败时后续角色不会假装独立成功。
角色顺序是状态机约束，不是给界面展示的装饰流程。
质疑与反证的草稿字段固定为空字符串，避免旁路生成最终文字。
质疑与反证的建议字段固定为不适用，避免越权给出处理意见；路线结论单独记录。
复核角色的建议只能是保留、降级或暂缓，并与角色状态一致。
提示词不允许空值占位，因为工具参数模式不接受空值语义。
每个角色使用专用工具模式，不能共用宽松的万能输出结构。
工具模式只约束返回参数，不授权模型执行任何外部操作。
模型返回后仍由服务端再次完成结构、角色和证据硬校验。
模型声称已经核对原文，不能替代程序中的证据编号验证。
每条主张必须引用当前证据包内已经登记的证据编号。
模型不能引用其他案例、其他运行或提示词中未提供的编号。
字段证据、检索证据与补充证据在同一白名单中分别保留来源。
检索片段只是候选原文，不因为进入模型上下文而变成审计证据。
补充资料的支持状态保持待人工确认，模型不得自动提升可信级别。
没有证据编号的正常解释只能标为未验证假设，不能标为已支持。
支持状态与证据编号必须相互一致，防止文字与结构化状态冲突。
禁用词检查覆盖主张、理由、草稿标题和草稿观察文字。
禁用词用于阻止模型越权认定舞弊、违法或出具审计意见。
禁用词命中属于政策失败，不会静默删词后继续接受模型结果。
服务端不自动修补残缺 JSON，以免制造不存在的模型成功记录。
供应商连接失败单独记录，不与结构化解析失败混为一谈。
工具参数无法解析时记录参数阶段，不保存原始敏感响应正文。
字段类型或枚举不符时记录结构阶段，便于定位模式兼容问题。
证据编号越界时记录证据阶段，说明输出未通过来源约束。
禁用词或角色越权时记录政策阶段，说明输出违反表达边界。
稳定失败码供网页、状态文件和验收记录使用，不携带模型原文。
失败详情只描述阶段与约束，不回显密钥、请求头或供应商响应。
响应哈希用于运行留痕，但哈希本身不能证明内容专业正确。
输入哈希用于判断同一证据包是否被重复调用，不泄露证据正文。
模型标识和提示词版本随角色步骤保存，支持版本链回查。
调用时长和令牌数只作工程指标，不被解释为专业效果指标。
离线测试可替换供应商调用，但必须明确属于模拟提供方。
模拟成功只验证状态机和硬校验，不能写成真实模型已经验收。
真实验收最多按既定预算调用三个角色，不自动无限重试。
自动重试会混淆首次失败证据，因此本模块默认不执行角色重试。
供应商超时直接结束当前角色，后续状态如实显示未执行。
没有密钥时返回未配置状态，不回退为预设的成功示例。
案例禁止模型传输时不进入本模块，主流程应提前关闭模型链。
完整分析模式下四条 AI 路线都执行三个角色；规则未触发只改变任务，不关闭模型链。
calculation_only 才是明确不调用模型的模式；模型不改变确定性规则结论。
复核成功后产生的是 AI 辅助草稿，不是人工处理决定。
最终草稿仍需人工选择保留、降级或暂缓，并明确是否允许导出。
模型建议与人工处理分别存储，任何一方都不能覆盖另一方字段。
旧运行缺少失败阶段时仍可读取，新字段保持向后兼容。
错误分类应保持稳定，避免网页根据易变的异常文本判断状态。
新增角色字段时必须同步模式、提示词、校验器和回归测试。
修改禁用词时必须评估误伤正常解释和漏拦越权结论的风险。
修改证据白名单时必须保留案例隔离和运行隔离两个边界。
修改提示词不能放宽“只引用已给证据”的核心限制。
任何角色都不得把收入真实性作为规范认定名称写入正式草稿。
认定表达应落在收入发生、截止、准确性及应收存在、计价分摊。
模型可以建议索取资料，但不能声称资料已经取得或已经复核。
模型可以提出正常解释，但必须说明仍需何种材料加以验证。
模型不能根据单一增速差直接推断业务异常或管理层动机。
角色输出是待核查事项生成链的一部分，而不是旁路说明文字。
只有三角色全部完成并形成最终草稿，主运行才可标记完整分析。
任一角色失败都会保留程序结果，但完整性状态必须保持失败。
模型输入在调用前压缩为最小证据卡，不能把整个案例对象直接发送。
证据卡哈希随步骤记录，复验时可以确认三角色看到的输入是否一致。
每个角色工具模式绑定本次运行和规则编号，供应商输出不能跨单复用。
工具调用名称必须与受控名称完全一致，普通文本 JSON 不能冒充严格调用。
输出令牌上限按角色设置，过长回答不能无限挤占服务资源和日志空间。
网络超时只重试受控次数，重复失败后保留供应商错误阶段并停止链条。
模型返回多个工具调用时只接受协议允许的结构，不能任意挑选有利结果。
解析后的对象还要经过 Pydantic 和业务双重校验，模式通过不等于政策通过。
质疑角色至少提出一条候选主张，但每条仍需当前证据或明确未验证标记。
反证角色的正常解释不能引用不存在的资料，也不能把假设写成已支持事实。
复核角色必须解释保留、降级或暂缓原因，空草稿不能获得完成状态。
确定性规则未触发时，模型不得用修辞把它改写为已触发的程序事实。
模型调用计时只反映供应商响应，不应被解释为推理质量或证据充分性。
调用失败日志不保存原始提示词全文，减少证据和个人信息在日志中复制。
三角色机制增加对立检查机会，但不能替代审计人员的职业怀疑和复核程序。
本模块的设计目标是可证伪、可回查和诚实失败，而不是提高成功率表象。
"""

from __future__ import annotations

import hashlib
from http.client import HTTPException as HTTPClientException
import json
import re
import time
from copy import deepcopy
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from .privacy import scan_sensitive_payload
from .provider_readiness import get_provider_error_guidance
from .schemas import AgentOutput, AgentRole, AgentStep, RuleResult


FORBIDDEN_TERMS = ("舞弊", "造假", "确认存在重大错报", "违法", "审计意见", "投资建议")
ROLE_ORDER: tuple[AgentRole, ...] = ("challenge", "counter", "review")
ROLE_ALLOWED_STATUSES: dict[AgentRole, list[str]] = {
    "challenge": ["candidate"],
    "counter": ["candidate", "defer"],
    "review": ["retain", "downgrade", "defer"],
}
ROUTE_ROLE_ALLOWED_STATUSES: dict[str, dict[AgentRole, list[str]]] = {
    "risk_candidate": ROLE_ALLOWED_STATUSES,
    "negative_confirmation": {
        "challenge": ["defer"],
        "counter": ["defer"],
        "review": ["retain", "defer"],
    },
    "industry_review": {
        "challenge": ["candidate", "defer"],
        "counter": ["candidate", "defer"],
        "review": ["retain", "downgrade", "defer"],
    },
    "evidence_gap_review": {
        "challenge": ["candidate", "defer"],
        "counter": ["candidate", "defer"],
        "review": ["retain", "downgrade", "defer"],
    },
}
ROUTE_CONCLUSIONS = {
    "risk_candidate": "risk_candidate",
    "negative_confirmation": "no_trigger_confirmed",
    "industry_review": "industry_boundary",
    "evidence_gap_review": "data_gap",
}
ROUTE_ALLOWED_CONCLUSIONS = {
    "risk_candidate": ["risk_candidate", "additional_procedure_required"],
    "negative_confirmation": ["no_trigger_confirmed", "additional_procedure_required"],
    "industry_review": ["industry_boundary", "additional_procedure_required", "data_gap"],
    "evidence_gap_review": ["data_gap", "additional_procedure_required"],
}
PROMPT_VERSION = "agent_prompt_v3"
ROLE_MAX_OUTPUT_TOKENS: dict[AgentRole, int] = {"challenge": 1400, "counter": 1400, "review": 1600}


class ProviderCallError(RuntimeError):
    """A provider rejected a request; keep its stable public failure code."""

    def __init__(self, failure_code: str, detail: str, *, provider_call_count: int = 1) -> None:
        super().__init__(detail)
        self.failure_code = failure_code
        self.detail = detail
        self.provider_call_count = max(1, int(provider_call_count))


class ToolArgumentsError(ValueError):
    """工具调用协议失败的稳定诊断，不回显供应商原始响应。"""

    def __init__(self, failure_code: str, detail: str) -> None:
        super().__init__(detail)
        self.failure_code = failure_code
        self.detail = detail


def _tool_arguments_failure(error: ValueError) -> tuple[str, str]:
    """把工具参数协议失败归类为稳定码，避免所有 ValueError 被压成同一错误。"""
    if isinstance(error, ToolArgumentsError):
        return error.failure_code, error.detail
    message = str(error)
    if "输出上限" in message or "finish_reason=length" in message:
        return "MODEL_TOOL_OUTPUT_TRUNCATED", "模型在完成工具参数前达到本角色输出上限。"
    if "未声明的输出工具" in message or "受约束的工具参数" in message:
        return "MODEL_TOOL_CALL_CONTRACT_ERROR", "模型未按声明的输出工具合同返回调用。"
    if "可解析的工具参数" in message:
        return "MODEL_TOOL_ARGUMENTS_MISSING", "模型未返回可读取的工具参数。"
    if "JSON对象后" in message or "不是JSON对象" in message:
        return "MODEL_TOOL_ARGUMENTS_SHAPE_INVALID", "模型工具参数不是单个可校验的 JSON 对象。"
    return "MODEL_TOOL_ARGUMENTS_INVALID", "模型工具参数未通过服务端协议检查。"


def _provider_error_message(error: HTTPError) -> str:
    """Read a short, non-sensitive provider error message for stable mapping."""

    try:
        raw = error.read(4096)
    except Exception:
        return ""
    if not raw:
        return ""
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except (TypeError, ValueError, UnicodeDecodeError):
        return raw.decode("utf-8", "replace")[:500]
    if isinstance(payload, dict):
        nested = payload.get("error")
        if isinstance(nested, dict):
            return str(nested.get("message") or nested.get("type") or "")[:500]
        return str(payload.get("message") or payload.get("type") or "")[:500]
    return ""


def _region_opt_in_detail(message: str) -> str:
    """Turn OpenCode's China-hosting gate into an actionable demo message."""

    match = re.search(r"https://opencode\.ai/workspace/[A-Za-z0-9_-]+/go", message)
    if match:
        return f"OpenCode Go 当前 DeepSeek 版本需要先在工作区开启中国托管模型：{match.group(0)}"
    return "OpenCode Go 当前 DeepSeek 版本需要先在工作区开启中国托管模型，再重新运行。"


AI_ANALYSIS_ROUTES = {
    "risk_candidate": "核查程序筛出的候选事项是否由证据支持，并提出下一步复核动作。",
    "negative_confirmation": "复核规则未触发结果，主动检查阈值边缘、异常趋势、漏判可能和原文中的反向迹象；不得把未触发改写成已触发。",
    "industry_review": "结合行业闸门和行业专用口径，检查当前程序选择是否合理、是否需要行业资料或替代程序；不得套用不适用的通用口径。",
    "evidence_gap_review": "围绕数据缺口检查年报原文中的替代披露、缺口影响和可执行的补充程序；不得猜测缺失金额。",
}
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
                "schema_version": {"type": "string", "enum": ["agent_output_v2"]},
                "run_id": {"type": "string"},
                "role": {"type": "string", "enum": ["challenge", "counter", "review"]},
                "rule_id": {"type": "string", "enum": ["R1", "R2"]},
                "analysis_conclusion": {"type": "string", "enum": ["risk_candidate", "no_trigger_confirmed", "additional_procedure_required", "data_gap", "industry_boundary"]},
                "status": {"type": "string", "enum": ["candidate", "retain", "downgrade", "defer"]},
                "claims": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "evidence_ids": {"type": "array", "items": {"type": "string"}},
                            "support_status": {"type": "string", "enum": ["supported", "unverified_hypothesis"]},
                        },
                        "required": ["text", "evidence_ids", "support_status"],
                        "additionalProperties": False,
                    },
                },
                "normal_explanations": {
                    "type": "array",
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "evidence_ids": {"type": "array", "items": {"type": "string"}},
                            "support_status": {"type": "string", "enum": ["supported", "unverified_hypothesis"]},
                        },
                        "required": ["text", "evidence_ids", "support_status"],
                        "additionalProperties": False,
                    },
                },
                "data_gaps": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
                "requested_materials": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
                "reason_for_status": {"type": "string"},
                "draft_title": {"type": "string"},
                "draft_observation": {"type": "string"},
                "ai_recommendation": {"type": "string", "enum": ["retain", "downgrade", "defer", "not_applicable"]},
            },
            "required": [
                "schema_version",
                "run_id",
                "role",
                "rule_id",
                "analysis_conclusion",
                "status",
                "claims",
                "normal_explanations",
                "data_gaps",
                "requested_materials",
                "reason_for_status",
                "draft_title",
                "draft_observation",
                "ai_recommendation",
            ],
            "additionalProperties": False,
        },
    },
}


def _agent_output_tool_for(
    role: AgentRole,
    rule_id: str,
    run_id: str,
    analysis_route: str = "risk_candidate",
    allow_empty_claims: bool = False,
) -> dict[str, Any]:
    """把角色、规则和本次运行号一并缩进严格Schema，避免跨角色状态或串单。"""
    tool = deepcopy(AGENT_OUTPUT_TOOL)
    properties = tool["function"]["parameters"]["properties"]
    properties["run_id"]["enum"] = [run_id]
    properties["role"]["enum"] = [role]
    properties["rule_id"]["enum"] = [rule_id]
    route_statuses = ROUTE_ROLE_ALLOWED_STATUSES.get(analysis_route, ROLE_ALLOWED_STATUSES)
    properties["status"]["enum"] = route_statuses[role]
    properties["analysis_conclusion"]["enum"] = ROUTE_ALLOWED_CONCLUSIONS.get(
        analysis_route,
        ROUTE_ALLOWED_CONCLUSIONS["risk_candidate"],
    )
    # 空证据路线仍需真实调用模型，但必须退化为缺口/边界草稿；
    # 普通证据路线保持至少一条引用主张。
    if allow_empty_claims and analysis_route in {"evidence_gap_review", "industry_review"}:
        properties["claims"].pop("minItems", None)
    if role == "review":
        # 复核角色必须形成最终草稿；建议集合与其允许的处理状态保持一致。
        properties["draft_title"]["minLength"] = 1
        properties["draft_observation"]["minLength"] = 1
        properties["ai_recommendation"]["enum"] = ROLE_ALLOWED_STATUSES[role]
    else:
        # 前两角色不负责最终草稿。用空字符串而不是 null，避免严格Schema与提示词冲突。
        properties["draft_title"]["enum"] = [""]
        properties["draft_observation"]["enum"] = [""]
        properties["ai_recommendation"]["enum"] = ["not_applicable"]
    return tool

ROLE_INSTRUCTIONS: dict[AgentRole, str] = {
    "challenge": "把程序筛查结果转成一个可验证的待核查问题；不得把候选风险写成事实结论。",
    "counter": "审阅质疑角色的主张，在同一证据包中寻找正常解释、相反材料和资料缺口；不得替程序改数。",
    "review": "综合程序结果、质疑和反证，检查证据边界后形成待核查草稿，只能建议保留、降级或暂缓。",
}

# 三个角色各自承担不同的审计前置职责。这里刻意把“输入—动作—交接—禁止事项”写进
# 提示词，而不是只依赖网页文案；这样真实模型、缓存回放和离线模拟都使用同一份合同。
ROLE_PROMPTS: dict[AgentRole, str] = {
    "challenge": """你是审迹智链 Challenge Agent，负责把确定性筛查结果变成一个可验证的待核查问题。

你会收到：rule_result（程序计算真值）、deterministic_constraints（不可改写的约束）和 evidence_bundle（本次案例允许使用的证据白名单）。
你必须：
1. 只提出一条最重要的候选主张，说明需要核查的会计事项和原因；
2. 每条 claims 主张至少引用一个 evidence_id 且必须是 supported；只能作为推测的内容放入 normal_explanations，并标记为 unverified_hypothesis；
3. 把缺失的期后回款、账龄、合同或其他材料列入 data_gaps/requested_materials；
4. 除非路线合同另有规定，status 返回 candidate；draft_title、draft_observation 为空字符串，ai_recommendation 返回 not_applicable；
5. 把输出交给 Counter Agent，不能提前给出最终处理建议。

严禁：把程序候选写成舞弊、违法、重大错报或审计意见；重算、改写或猜测金额、比例、页码、趋势和阈值；使用证据包以外的信息。""",
    "counter": """你是审迹智链 Counter Agent，负责对 Challenge Agent 的主张做反证和正常解释检查。

你会收到：同一 rule_result、deterministic_constraints、evidence_bundle，以及 Challenge Agent 的结构化输出。你必须：
1. 先判断 Challenge 的主张是否真的被当前证据支持，指出越界或不确定之处；
2. 优先寻找同一证据包中的正常业务解释、口径差异、季节性、合并范围和反向证据；
3. 找不到反证时要明确写“当前证据未发现相反材料”，不能编造反证；
4. 如果解释没有 RAG-/SUP- evidence_id 直接支持，support_status 必须为 unverified_hypothesis，并在 text 中明确写“待验证假设”；字段数值本身不能证明季节性、口径差异或管理层原因；
5. 列出仍需取得的资料和下一步核查动作；
6. 除非路线合同另有规定，status 只能返回 candidate 或 defer；draft_title、draft_observation 为空字符串，ai_recommendation 返回 not_applicable；
7. 不要声称达到强阈值，也不要写跨年度周转/回款趋势或变化；如果程序没有提供可比年度，只能列为资料缺口或待验证假设；
8. 将结构化结果交给 Review Agent，不替 Review 作最终建议。

严禁：删除或弱化程序事实；根据增速差推断管理层动机；把待验证假设写成已确认事实；引用 Challenge 输出中不存在的 evidence_id。""",
    "review": """你是审迹智链 Review Agent，负责把程序筛查、Challenge 和 Counter 收敛成可交给人工复核的审计计划草稿。

你会收到：同一 rule_result、deterministic_constraints、evidence_bundle、Challenge 输出和 Counter 输出。你必须：
1. 检查三者是否引用同一案例、同一规则和当前证据白名单；
2. 区分“程序已计算事实”“有证据支持的解释”“仍待验证的假设”和“资料缺口”；
3. 形成非空 draft_title 与 draft_observation，简洁说明核查重点、证据边界和建议取得的材料；
4. 如果 rule_result.risk_card 提供 basis_limitation 或 trend_limitation，必须把这些限制原样或等义写进 draft_observation；不能省略“净额/账面口径限制”或“趋势不可评价/缺少第三年”等程序边界；
5. 只有 deterministic_constraints 明确允许时才能描述强阈值、持续趋势或周转变化；未达到强阈值、缺少第三年时必须明确写“未达到/不可评价”，不得用相反措辞；
6. status 与 ai_recommendation 必须一致，只能是 retain、downgrade 或 defer；
7. claims 仍需引用 evidence_id，不能因为前两角色写过就省略引用；
8. 输出的是 AI 辅助草稿，最终处理必须留给人工复核。

严禁：新增证据包没有的事实；把“保留”写成专业结论；认定舞弊、违法、重大错报或出具审计意见；把缺失数据补成金额或趋势。""",
}


def _route_role_contract(analysis_route: str, role: AgentRole) -> str:
    """Return the route-specific task and status contract appended to prompts."""

    conclusion = ROUTE_CONCLUSIONS.get(analysis_route, "risk_candidate")
    if analysis_route == "negative_confirmation":
        if role == "challenge":
            return "本路线不是候选风险确认：status 必须为 defer，专门检查未触发结果是否存在阈值边缘、漏判或反向迹象；不得把程序状态改成 candidate。analysis_conclusion 填 no_trigger_confirmed。"
        if role == "counter":
            return "本路线 status 必须为 defer，验证正常解释和反向证据；不得制造风险候选。analysis_conclusion 填 no_trigger_confirmed。"
        return "本路线优先给出 no_trigger_confirmed；只有资料不足以确认时才给 additional_procedure_required，并保持 status=defer。"
    if analysis_route == "industry_review":
        return f"本路线围绕行业适配和专用口径工作；不得把通用规则套到不适用行业。analysis_conclusion 填 {conclusion} 或 additional_procedure_required。"
    if analysis_route == "evidence_gap_review":
        return f"本路线围绕字段缺口、替代披露和补充程序工作；不得猜测缺失金额。analysis_conclusion 填 {conclusion} 或 additional_procedure_required。"
    return "本路线核查程序候选是否有证据支持；analysis_conclusion 填 risk_candidate。"


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


_MODEL_CONTEXT_EXCLUDED_KEYS = {
    "cache_key_hash",
    "case_id",
    "content_sha256",
    "document_id",
    "field_id",
    "file_sha256",
    "filename",
    "human_review",
    "human_review_history",
    "input_sha256",
    "locator",
    "original_filename",
    "owner_user_id",
    "package_sha256",
    "request_identity",
    "response_sha256",
    "retrieval_id",
    "reviewed_by",
    "reviewer",
    "source_file",
    "source_locator",
    "source_snapshot_id",
    "source_url",
    "storage_path",
    "storage_relpath",
    "tenant_id",
    "user_id",
}


def minimize_model_context(value: Any) -> Any:
    """递归删除模型推理不需要的技术标识、路径、哈希和人工身份字段。

    该函数位于模型请求的最后组装入口，作为上游最小化之外的第二道防线。
    风险卡会嵌套字段证据，因此不能只清理顶层 evidence bundle。
    哈希、缓存键、租户与用户编号用于服务端追踪，不帮助模型形成审计建议。
    文件名、对象路径和来源 URL 由服务端回查接口保存，不进入供应商载荷。
    文档号与检索号可留在本地完整运行中，但模型引用统一使用 evidence_id。
    页码、披露日期、金额、单位和必要摘录仍会保留，避免破坏证据语义。
    人工复核身份与历史不进入模型，防止模型把审批动作误当作事实支持。
    未知的新字典层级也会递归处理，降低未来新增风险卡字段时的泄露风险。
    该过程只改变发送给模型的副本，不改写本地原始证据或其哈希记录。
    隐私扫描必须使用同一最小化视图，保证“已扫描内容”与“实际发送内容”一致。
    最小化不等于脱敏批准；命中高风险个人信息时仍由调用链失败关闭。
    """

    if isinstance(value, dict):
        return {
            str(key): minimize_model_context(child)
            for key, child in value.items()
            if str(key) not in _MODEL_CONTEXT_EXCLUDED_KEYS
        }
    if isinstance(value, list):
        return [minimize_model_context(child) for child in value]
    if isinstance(value, tuple):
        return [minimize_model_context(child) for child in value]
    return value


def compact_evidence_bundle(evidence_bundle: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把字段、RAG 与补充资料压成同一证据列表，模型不能引用列表外事实。"""
    if isinstance(evidence_bundle, list):
        categories = [("field", evidence_bundle)]
    else:
        categories = [
            ("field", evidence_bundle.get("field_evidence", [])),
            ("rag", evidence_bundle.get("rag_evidence", [])),
            ("supplement", evidence_bundle.get("supplement_evidence", [])),
            ("procedure", evidence_bundle.get("procedure_evidence", [])),
        ]
    compact: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for evidence_type, items in categories:
        for row in items:
            if not isinstance(row, dict) or not row.get("evidence_id"):
                continue
            evidence_id = str(row["evidence_id"])
            # 同一 evidence ID 可能同时出现在字段、RAG 和补充列表中；
            # 顺序决定优先级：字段 > RAG > 补充 > 程序证据。
            if evidence_id in seen_ids:
                continue
            seen_ids.add(evidence_id)
            compact.append(
                {
                    "evidence_id": evidence_id,
                    "evidence_type": evidence_type,
                    "field_label": row.get("field_label"),
                    "value": row.get("value"),
                    "unit": row.get("unit"),
                    "disclosure_date": row.get("disclosure_date"),
                    "pdf_page": row.get("pdf_page"),
                    "print_page": row.get("print_page"),
                    "excerpt": str(row.get("excerpt") or "")[:500],
                    "review_status": row.get("review_status") or row.get("source_review_status"),
                }
            )
    return compact


# 读取历史扩展和验收脚本时保留旧函数名；新代码统一使用公开名称。
_compact_evidence_bundle = compact_evidence_bundle


def _system_prompt(role: AgentRole, analysis_route: str = "risk_candidate") -> str:
    route_instruction = AI_ANALYSIS_ROUTES.get(analysis_route, AI_ANALYSIS_ROUTES["risk_candidate"])
    return f"""{ROLE_PROMPTS[role]}

本次 AI 分析路线：{analysis_route}。路线目标：{route_instruction}
路线角色合同：{_route_role_contract(analysis_route, role)}

共同合同（所有角色必须遵守）：
只使用用户消息中的规则计算结果和 evidence_bundle，不得搜索网页、使用公司记忆或补全未提供事实。
deterministic_constraints 是程序真值：strong_threshold_met=false 时不得写已达到强阈值；
turnover_trend_available=false 时不得写周转或回款周期较上年延长/缩短；review 必须保留给出的口径与趋势局限。
当 strong_threshold_met=false 时，任何角色的 claims、normal_explanations、reason_for_status、draft_observation
都不得出现“达到/超过/触发强阈值”等肯定表述，只能写“未达到、未证实或待核查”；行业闸门为 not_applicable/unknown 时也不得把通用规则写成适用结论。
不得认定舞弊、重大错报、违法，不得出具审计意见或投资建议。
每条 claim 必须绑定至少一个已有 evidence_id 且 support_status=supported。
正常解释只有在证据支持时才能标 supported；否则必须标 unverified_hypothesis，并明确是“待验证假设”。
如果 evidence_bundle 为空，仍必须调用 submit_agent_output 完成三角色链；此时 claims 和 normal_explanations 必须为空，
只能填写 data_gaps/requested_materials、路线允许的 analysis_conclusion 以及 review 的缺口草稿，绝不编造事实或 evidence_id。
不得改写程序计算的数字、公式、页码、原文定位或规则触发结论。
为保证可复核和展示简洁：claims 只写1条；normal_explanations最多2条；data_gaps和requested_materials各最多3条；
每条文字尽量不超过60个汉字，reason_for_status不超过100个汉字；不要整段复述证据。
review 角色必须形成非空 draft_title、draft_observation 与 ai_recommendation；前两角色将两个草稿字段设为空字符串，ai_recommendation设为not_applicable，禁止使用null。
必须调用 submit_agent_output 提交结果，不要输出可见文字、Markdown或代码围栏。"""


def _user_payload(
    run_id: str,
    role: AgentRole,
    rule_result: RuleResult,
    evidence_bundle: list[dict[str, Any]],
    previous_outputs: dict[str, AgentOutput],
    analysis_route: str = "risk_candidate",
    analysis_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route_statuses = ROUTE_ROLE_ALLOWED_STATUSES.get(analysis_route, ROLE_ALLOWED_STATUSES)
    allowed_conclusions = ROUTE_ALLOWED_CONCLUSIONS.get(
        analysis_route,
        ROUTE_ALLOWED_CONCLUSIONS["risk_candidate"],
    )
    allowed_evidence_ids = [
        str(item.get("evidence_id"))
        for item in evidence_bundle
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    ]
    payload: dict[str, Any] = {
        "schema_version": "agent_output_v2",
        "run_id": run_id,
        "role": role,
        "analysis_route": analysis_route,
        "analysis_route_instruction": AI_ANALYSIS_ROUTES.get(analysis_route, AI_ANALYSIS_ROUTES["risk_candidate"]),
        "allowed_analysis_conclusions": ROUTE_ALLOWED_CONCLUSIONS.get(
            analysis_route,
            ROUTE_ALLOWED_CONCLUSIONS["risk_candidate"],
        ),
        "analysis_context": minimize_model_context(analysis_context or {}),
        "rule_result": {
            "rule_id": rule_result.rule_id,
            "status": rule_result.status,
            "metrics": rule_result.metrics,
            "risk_card": minimize_model_context(rule_result.risk_card),
        },
        # 把程序已经确定的真假条件单列出来，避免模型把 26.84% 写成超过
        # 30% 强阈值，或在缺少可比期间时擅自声称周转天数“显著延长”。
        "deterministic_constraints": {
            "strong_threshold_met": (
                bool(rule_result.risk_card)
                and rule_result.risk_card.get("screening_strength") == "strong"
            ),
            "turnover_trend_available": bool(
                rule_result.metrics.get("three_year_trend_available")
            ),
            "basis_limitation": (
                (rule_result.risk_card or {}).get("basis_limitation") or ""
            ),
            "trend_limitation": (
                (rule_result.risk_card or {}).get("trend_limitation") or ""
            ),
        },
        "evidence_bundle": evidence_bundle,
        "evidence_mode": "empty_gap_only" if not allowed_evidence_ids else "evidence_bound",
        "output_contract": {
            "schema_version": "agent_output_v2",
            "role": role,
            "rule_id": rule_result.rule_id,
            "analysis_conclusion": allowed_conclusions,
            "status_values_for_this_role": route_statuses[role],
            "allowed_evidence_ids": allowed_evidence_ids,
            "status_values": route_statuses[role],
            "claims": [{"text": "待进一步了解的简短表述", "evidence_ids": ["本次证据ID"], "support_status": "supported"}],
            "normal_explanations": [],
            "data_gaps": [],
            "requested_materials": [],
            "reason_for_status": "仅基于本次证据包的简短说明",
            "draft_title": "review角色填写非空文本；其他角色必须为空字符串",
            "draft_observation": "review角色填写非空文本；其他角色必须为空字符串",
            "ai_recommendation": "review角色等于其status；其他角色为not_applicable",
        },
        "hard_rules_for_this_call": [
            "当 strong_threshold_met=false 时只能写未达到、未证实或待核查，不得写达到、超过、触发强阈值。",
            "当 turnover_trend_available=false 时不得写跨年度周转或回款周期变化，只能写资料缺口或待验证假设。",
            "claims 只能使用 allowed_evidence_ids 中的 evidence_id，并且每条 claim 至少绑定一个 evidence_id。",
            "不得输出舞弊、违法、重大错报、审计意见或投资建议；不确定时使用 defer 和 additional_procedure_required。",
        ],
    }
    if role in {"counter", "review"}:
        payload["challenge"] = previous_outputs["challenge"].model_dump(mode="json")
    if role == "review":
        payload["counter"] = previous_outputs["counter"].model_dump(mode="json")
    return payload


def _parse_json_content(content: str) -> dict[str, Any]:
    """剥离兼容层包装，但绝不猜测或修补残缺的模型 JSON。

    个别兼容 OpenAI 协议的供应商会把工具参数再次编码成 JSON 字符串，或在
    对象前后附少量说明。这里最多剥两层并只接收一个完整对象；截断、尾逗号
    和引号缺失仍是硬失败，防止“自动修复”改变模型原意。
    """
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    text = text.strip()
    parsed: Any
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        object_start = text.find("{")
        if object_start < 0:
            raise
        parsed, end = json.JSONDecoder().raw_decode(text[object_start:])
        tail = text[object_start + end :].strip()
        if tail and tail != "```":
            raise ValueError("模型JSON对象后仍有不可校验内容")
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    if not isinstance(parsed, dict):
        raise ValueError("模型输出不是JSON对象")
    return parsed


def _with_review_boundaries(output: AgentOutput, rule_result: RuleResult | None) -> AgentOutput:
    """将程序已知的口径/趋势边界显式补入复核草稿，不替模型新增事实。"""
    if output.role != "review" or rule_result is None:
        return output
    risk_card = rule_result.risk_card or {}
    observation = output.draft_observation.strip()
    joined = "\n".join(
        [
            *(claim.text for claim in output.claims),
            *(claim.text for claim in output.normal_explanations),
            output.reason_for_status,
            output.draft_title,
            observation,
        ]
    )
    additions: list[str] = []
    basis_limitation = str(risk_card.get("basis_limitation") or "").strip()
    if basis_limitation:
        basis_tokens = (
            ("净额", "口径局限", "口径限制")
            if "净额" in basis_limitation
            else ("账面余额", "口径", "未在登记表")
        )
        if not any(token in joined for token in basis_tokens):
            additions.append(f"程序边界（口径）：{basis_limitation}")
    trend_limitation = str(risk_card.get("trend_limitation") or "").strip()
    if trend_limitation and not any(token in joined for token in ("趋势不可评价", "无法评价趋势", "缺少第三年")):
        additions.append(f"程序边界（趋势）：{trend_limitation}")
    if not additions:
        return output
    suffix = "\n".join(additions)
    return output.model_copy(update={"draft_observation": f"{observation}\n{suffix}".strip()})


def _normalize_unverified_explanations(output: AgentOutput) -> AgentOutput:
    """把缺少原文/补充证据的因果解释降级为待验证假设，避免误标为已证实。"""
    causal_terms = ("主要原因", "由于", "行业需求", "信用政策", "客户结构", "季节性", "结算方式", "催收措施")
    explanations = []
    changed = False
    for explanation in output.normal_explanations:
        if (
            explanation.support_status == "supported"
            and any(term in explanation.text for term in causal_terms)
            and not any(str(evidence_id).startswith(("RAG-", "SUP-")) for evidence_id in explanation.evidence_ids)
        ):
            text = explanation.text.strip()
            if "待验证假设" not in text:
                text = f"待验证假设：{text}"
            explanation = explanation.model_copy(update={"text": text, "support_status": "unverified_hypothesis"})
            changed = True
        explanations.append(explanation)
    return output.model_copy(update={"normal_explanations": explanations}) if changed else output


def _semantic_failure_code(message: str) -> str:
    """将语义硬校验失败归类为稳定码，不把模型原文写入运行记录。"""
    if "强阈值" in message:
        return "MODEL_STRONG_THRESHOLD_CONTRADICTION"
    if "周转趋势" in message or "跨期趋势" in message:
        return "MODEL_TREND_CONTRADICTION"
    if "应收口径" in message:
        return "MODEL_BASIS_LIMITATION_MISSING"
    if "外部因果" in message:
        return "MODEL_CAUSAL_EVIDENCE_ERROR"
    return "MODEL_SEMANTIC_VALIDATION_ERROR"


def _strict_tool_base_url(base_url: str) -> str:
    """Return the provider's tool-call base without inventing an endpoint suffix.

    The native DeepSeek endpoint keeps strict tool calls under ``/beta``.  OpenCode
    Zen and other OpenAI-compatible gateways already expose their contract under a
    versioned ``/v1`` path, so appending ``/beta`` would turn a valid URL into a
    404.  This helper intentionally uses only the public URL shape; credentials
    never participate in endpoint selection.
    """
    normalized = base_url.rstrip("/")
    lowered = normalized.lower()
    if normalized.endswith("/beta") or normalized.endswith("/v1") or "/v1/" in normalized:
        return normalized
    if "opencode.ai/" in lowered:
        return normalized
    return f"{normalized}/beta"


def validate_agent_output(
    payload: dict[str, Any],
    *,
    run_id: str,
    role: AgentRole,
    rule_id: str,
    allowed_evidence_ids: set[str],
    rule_result: RuleResult | None = None,
    analysis_route: str = "risk_candidate",
) -> AgentOutput:
    """模型JSON必须与本次运行完全绑定；任何越界引用都属于硬失败。"""
    output = AgentOutput.model_validate(payload)
    if output.run_id != run_id or output.role != role or output.rule_id != rule_id:
        raise ValueError("模型输出的run_id、role或rule_id与本次运行不一致")

    route_statuses = ROUTE_ROLE_ALLOWED_STATUSES.get(analysis_route, ROLE_ALLOWED_STATUSES)
    if output.status not in route_statuses[role]:
        raise ValueError(f"{analysis_route} 路线的 {role} 角色状态不允许")
    allowed_conclusions = ROUTE_ALLOWED_CONCLUSIONS.get(
        analysis_route,
        ROUTE_ALLOWED_CONCLUSIONS["risk_candidate"],
    )
    expected_conclusion = ROUTE_CONCLUSIONS.get(analysis_route, "risk_candidate")
    if output.analysis_conclusion is None:
        output = output.model_copy(update={"analysis_conclusion": expected_conclusion})
    elif output.analysis_conclusion not in set(allowed_conclusions):
        raise ValueError(f"{analysis_route} 路线的模型分析结论不允许")

    if role == "challenge" and analysis_route == "risk_candidate" and output.status != "candidate":
        raise ValueError("候选风险路线的质疑角色只能返回candidate")
    if role == "counter" and analysis_route == "risk_candidate" and output.status not in {"candidate", "defer"}:
        raise ValueError("反证角色状态不允许")
    if role == "review" and output.status not in {"retain", "downgrade", "defer"}:
        raise ValueError("语义复核角色状态不允许")
    if not output.claims:
        if allowed_evidence_ids or analysis_route not in {"evidence_gap_review", "industry_review"}:
            raise ValueError("有证据或非缺口路线必须至少保留一条模型主张")

    if output.schema_version == "agent_output_v2" and role == "review":
        if not output.draft_title.strip() or not output.draft_observation.strip():
            raise ValueError("复核Agent未形成最终待核查草稿")
        if output.ai_recommendation != output.status:
            raise ValueError("复核Agent的ai_recommendation必须与status一致")
        output = _with_review_boundaries(output, rule_result)
    output = _normalize_unverified_explanations(output)

    for claim in output.claims:
        if not claim.evidence_ids or claim.support_status != "supported":
            raise ValueError("模型主张必须由本次evidence_id支持")
    for claim in [*output.claims, *output.normal_explanations]:
        if not set(claim.evidence_ids).issubset(allowed_evidence_ids):
            raise ValueError("模型引用了本次证据包以外的evidence_id")
        if claim.support_status == "supported" and not claim.evidence_ids:
            raise ValueError("supported 表述缺少evidence_id")
        if claim.support_status == "unverified_hypothesis" and "待验证" not in claim.text:
            raise ValueError("未获支持的解释必须明确标为待验证假设")
    # 禁用定性必须覆盖整个结构，不能只扫 claims 而漏掉资料缺口等自由文本字段。
    # 统一免责声明本身包含“审计意见”四字；禁用词只扫描模型生成的业务字段，
    # 不能把系统固定声明误判为模型越权表述。
    generated_fields = output.model_dump(mode="json")
    generated_fields.pop("ai_generated_content_notice", None)
    serialized = json.dumps(generated_fields, ensure_ascii=False)
    if any(term in serialized for term in FORBIDDEN_TERMS):
        raise ValueError("模型输出包含禁止定性用语")
    if rule_result is not None:
        _validate_deterministic_fact_language(output, rule_result)
    return output


def _validate_deterministic_fact_language(output: AgentOutput, rule_result: RuleResult) -> None:
    """拒绝与程序计算直接冲突的数值语义，不尝试替模型改写答案。

    evidence ID 只能证明模型引用了本次材料，不能证明它正确解释了阈值和
    趋势。因此这里额外检查最容易形成致命误导的强阈值、跨期周转和因果
    解释；命中后整步失败，保留原始响应哈希，不把错误草稿包装成成功。
    """

    texts = [
        *(claim.text for claim in output.claims),
        *(claim.text for claim in output.normal_explanations),
        output.reason_for_status,
        output.draft_title,
        output.draft_observation,
    ]
    joined = "\n".join(texts)
    risk_card = rule_result.risk_card or {}

    if rule_result.rule_id == "R1":
        strong_met = risk_card.get("screening_strength") == "strong"
        # Match positive assertions only.  A plain substring check would also
        # reject the safe phrase “未达到强阈值”, because it contains “达到强阈值”.
        strong_assertion = re.search(r"(?<!未)(?<!不)(?<!尚)(?:已)?(?:超|达到|超过|高于|突破|触发)\s*强阈值", joined)
        if not strong_met and strong_assertion:
            raise ValueError("模型把未达到的R1强阈值写成已达到")

        trend_available = bool(rule_result.metrics.get("three_year_trend_available"))
        trend_claim_phrases = (
            "周转天数显著延长",
            "周转天数延长",
            "周转天数显著缩短",
            "周转天数缩短",
            "周转天数上升",
            "周转天数下降",
            "回款周期显著延长",
            "回款周期延长",
            "回款周期显著缩短",
            "回款周期缩短",
            "远超上年",
            "较上年延长",
            "较上年缩短",
        )
        if not trend_available and any(phrase in joined for phrase in trend_claim_phrases):
            raise ValueError("模型在周转趋势不可评价时作了跨期趋势判断")

        if output.role == "review":
            basis_limitation = str(risk_card.get("basis_limitation") or "")
            if basis_limitation and not any(
                token in joined
                for token in (
                    ("净额", "口径局限", "口径限制")
                    if "净额" in basis_limitation
                    else ("账面余额", "口径", "未在登记表")
                )
            ):
                raise ValueError("复核Agent遗漏了R1应收口径局限")
            trend_limitation = str(risk_card.get("trend_limitation") or "")
            if trend_limitation and not any(token in joined for token in ("趋势不可评价", "无法评价趋势", "缺少第三年")):
                raise ValueError("复核Agent遗漏了R1周转趋势局限")

    # 数字字段只能支持数字关系，不能单独支持行业、客户、政策等外部因果解释。
    causal_terms = ("主要因", "由于", "行业需求", "信用政策", "客户结构", "季节性", "结算方式", "催收措施")
    for explanation in output.normal_explanations:
        if explanation.support_status != "supported" or not any(term in explanation.text for term in causal_terms):
            continue
        if not any(evidence_id.startswith(("RAG-", "SUP-")) for evidence_id in explanation.evidence_ids):
            raise ValueError("模型用财务字段证据支持了外部因果解释")


def _call_model(
    *, api_key: str, base_url: str, model_id: str, role: AgentRole, payload: dict[str, Any], analysis_route: str = "risk_candidate"
) -> tuple[dict[str, Any], int, str, str, int | None, int | None]:
    output_tool = _agent_output_tool_for(
        role,
        str(payload["rule_result"]["rule_id"]),
        str(payload["run_id"]),
        str(payload.get("analysis_route") or analysis_route),
        allow_empty_claims=payload.get("evidence_mode") == "empty_gap_only",
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
            {"role": "system", "content": _system_prompt(role, analysis_route)},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    request = Request(
        f"{_strict_tool_base_url(base_url)}/chat/completions",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        # OpenCode Go's edge protection rejects urllib's default
        # ``Python-urllib`` user agent with a generic 403/1010 response.  Send
        # an explicit application user agent while keeping the key server-side.
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AuditTrace-Demo/1.0",
        },
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
        raise ToolArgumentsError("MODEL_TOOL_OUTPUT_TRUNCATED", "模型在完成工具参数前达到本角色输出上限。")
    tool_calls = choice["message"].get("tool_calls")
    if not isinstance(tool_calls, list) or len(tool_calls) != 1:
        raise ToolArgumentsError("MODEL_TOOL_CALL_CONTRACT_ERROR", "模型未按声明的输出工具合同返回调用。")
    function = tool_calls[0].get("function") if isinstance(tool_calls[0], dict) else None
    if not isinstance(function, dict) or function.get("name") != AGENT_OUTPUT_TOOL_NAME:
        raise ToolArgumentsError("MODEL_TOOL_CALL_CONTRACT_ERROR", "模型未按声明的输出工具合同返回调用。")
    arguments = function.get("arguments")
    if not isinstance(arguments, str) or not arguments.strip():
        raise ToolArgumentsError("MODEL_TOOL_ARGUMENTS_MISSING", "模型未返回可读取的工具参数。")
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


def _call_model_with_transient_retry(
    *, api_key: str, base_url: str, model_id: str, role: AgentRole, payload: dict[str, Any], analysis_route: str
) -> tuple[dict[str, Any], int, str, str, int | None, int | None, int]:
    """Retry one transient provider failure; classify permanent HTTP failures."""

    for attempt in range(2):
        try:
            result = _call_model(
                api_key=api_key,
                base_url=base_url,
                model_id=model_id,
                role=role,
                payload=payload,
                analysis_route=analysis_route,
            )
            return (*result, attempt + 1)
        except HTTPError as error:
            code = int(getattr(error, "code", 0) or 0)
            provider_message = _provider_error_message(error)
            provider_message_lower = provider_message.lower()
            if code == 403 and (
                "regionerror" in provider_message_lower
                or "requires explicit opt in" in provider_message_lower
                or "hosted in china" in provider_message_lower
            ):
                raise ProviderCallError(
                    "MODEL_PROVIDER_REGION_OPT_IN_REQUIRED",
                    _region_opt_in_detail(provider_message),
                    provider_call_count=attempt + 1,
                ) from error
            if code == 402:
                guidance = get_provider_error_guidance("MODEL_PROVIDER_BALANCE_EXHAUSTED", base_url=base_url, http_code=402)
                raise ProviderCallError(
                    "MODEL_PROVIDER_BALANCE_EXHAUSTED",
                    guidance["message"],
                    provider_call_count=attempt + 1,
                ) from error
            if code in {401, 403}:
                guidance = get_provider_error_guidance("MODEL_PROVIDER_AUTH_FAILED", base_url=base_url, http_code=code, detail=provider_message)
                raise ProviderCallError(
                    "MODEL_PROVIDER_AUTH_FAILED",
                    guidance["message"],
                    provider_call_count=attempt + 1,
                ) from error
            if code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                guidance = get_provider_error_guidance("MODEL_PROVIDER_REJECTED", base_url=base_url, http_code=code)
                raise ProviderCallError(
                    "MODEL_PROVIDER_REJECTED",
                    guidance["message"],
                    provider_call_count=attempt + 1,
                ) from error
            if attempt == 1:
                guidance = get_provider_error_guidance("MODEL_PROVIDER_RATE_LIMITED", base_url=base_url, http_code=code)
                raise ProviderCallError(
                    "MODEL_PROVIDER_RATE_LIMITED",
                    guidance["message"],
                    provider_call_count=attempt + 1,
                ) from error
            time.sleep(1.5)
        except (URLError, HTTPClientException, TimeoutError, OSError) as error:
            if attempt == 1:
                setattr(error, "provider_call_count", attempt + 1)
                raise
            time.sleep(1.5)
        except (json.JSONDecodeError, KeyError, IndexError, UnicodeDecodeError, TypeError, ValueError) as error:
            setattr(error, "provider_call_count", attempt + 1)
            raise
    raise RuntimeError("unreachable model retry state")


def run_agent_chain(
    *,
    run_id: str,
    rule_result: RuleResult,
    evidence_bundle: dict[str, Any] | list[dict[str, Any]],
    enabled: bool,
    api_key: str | None,
    base_url: str,
    model_id: str,
    before_role: Callable[[AgentRole], bool] | None = None,
    analysis_route: str = "risk_candidate",
    analysis_context: dict[str, Any] | None = None,
) -> list[AgentStep]:
    """串行执行三角色；任一步失败即关闭AI草稿链，不生成伪造的后续角色答案。"""
    if not enabled:
        return [AgentStep(role="challenge", status="not_requested", detail="本次未请求三Agent调用。")]
    if not api_key:
        return [AgentStep(role="challenge", status="config_missing", model_id=None, prompt_version=PROMPT_VERSION, detail="未配置DEEPSEEK_API_KEY；未调用模型。")]

    compact_bundle = compact_evidence_bundle(evidence_bundle)
    allowed_evidence_ids = {item["evidence_id"] for item in compact_bundle}
    previous_outputs: dict[str, AgentOutput] = {}
    steps: list[AgentStep] = []

    def append_skipped(role_index: int, reason: str) -> None:
        for skipped_role in ROLE_ORDER[role_index + 1 :]:
            steps.append(
                AgentStep(
                    role=skipped_role,
                    status="skipped",
                    detail=reason,
                    failure_code="PREVIOUS_ROLE_FAILED",
                    model_id=None,
                    prompt_version=PROMPT_VERSION,
                )
            )

    for role_index, role in enumerate(ROLE_ORDER):
        if before_role is not None:
            try:
                authorized = before_role(role)
            except Exception:
                authorized = False
            if not authorized:
                steps.append(
                    AgentStep(
                        role=role,
                        status="model_transfer_revoked",
                        model_id=model_id,
                        prompt_version=PROMPT_VERSION,
                        detail="逐案模型传输同意已撤销或暂时无法确认，已停止后续模型调用。",
                        failure_stage="policy",
                        failure_code="MODEL_TRANSFER_REVOKED",
                    )
                )
                append_skipped(role_index, "前置模型传输授权未通过，后续角色未调用。")
                break
        payload = _user_payload(
            run_id,
            role,
            rule_result,
            compact_bundle,
            previous_outputs,
            analysis_route=analysis_route,
            analysis_context=analysis_context,
        )
        input_sha256 = _json_hash(payload)
        try:
            raw_output, duration_ms, response_sha256, _, input_tokens, output_tokens, provider_call_count = _call_model_with_transient_retry(
                api_key=api_key,
                base_url=base_url,
                model_id=model_id,
                role=role,
                payload=payload,
                analysis_route=analysis_route,
            )
        except ProviderCallError as error:
            status = (
                "provider_quota_exhausted"
                if error.failure_code == "MODEL_PROVIDER_BALANCE_EXHAUSTED"
                else "provider_region_opt_in_required"
                if error.failure_code == "MODEL_PROVIDER_REGION_OPT_IN_REQUIRED"
                else "provider_unavailable"
            )
            steps.append(
                AgentStep(
                    role=role,
                    status=status,
                    failure_stage="provider",
                    failure_code=error.failure_code,
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    detail=error.detail,
                    input_sha256=input_sha256,
                    provider_call_performed=True,
                    provider_call_count=error.provider_call_count,
                )
            )
            append_skipped(role_index, "前一角色的供应商调用未完成，后续角色未调用。")
            break
        except (HTTPError, URLError, HTTPClientException, TimeoutError, OSError) as error:
            steps.append(
                AgentStep(
                    role=role,
                    status="provider_unreachable",
                    failure_stage="provider",
                    failure_code="MODEL_PROVIDER_UNREACHABLE",
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    detail=f"模型调用失败：{type(error).__name__}",
                    input_sha256=input_sha256,
                    provider_call_performed=True,
                    provider_call_count=max(1, int(getattr(error, "provider_call_count", 1))),
                )
            )
            append_skipped(role_index, "前一角色的模型请求失败，后续角色未调用。")
            break
        except json.JSONDecodeError as error:
            steps.append(
                AgentStep(
                    role=role,
                    status="MODEL_OUTPUT_INVALID",
                    failure_stage="tool_arguments",
                    failure_code="MODEL_JSON_PARSE_ERROR",
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    detail="模型工具参数不是完整JSON对象。",
                    input_sha256=input_sha256,
                    provider_call_performed=True,
                    provider_call_count=max(1, int(getattr(error, "provider_call_count", 1))),
                )
            )
            append_skipped(role_index, "前一角色返回的工具参数无法解析，后续角色未调用。")
            break
        except (KeyError, IndexError, UnicodeDecodeError, TypeError, ValueError) as error:
            failure_code, detail = _tool_arguments_failure(error) if isinstance(error, ValueError) else (
                "MODEL_TOOL_RESPONSE_STRUCTURE_INVALID",
                "模型工具调用响应缺少服务端所需的结构字段。",
            )
            steps.append(
                AgentStep(
                    role=role,
                    status="MODEL_OUTPUT_INVALID",
                    failure_stage="tool_arguments",
                    failure_code=failure_code,
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    detail=detail,
                    input_sha256=input_sha256,
                    provider_call_performed=True,
                    provider_call_count=max(1, int(getattr(error, "provider_call_count", 1))),
                )
            )
            append_skipped(role_index, "前一角色输出未通过结构校验，后续角色未调用。")
            break
        try:
            output = validate_agent_output(
                raw_output,
                run_id=run_id,
                role=role,
                rule_id=rule_result.rule_id,
                allowed_evidence_ids=allowed_evidence_ids,
                rule_result=rule_result,
                analysis_route=analysis_route,
            )
        except ValidationError:
            steps.append(
                AgentStep(
                    role=role,
                    status="MODEL_OUTPUT_INVALID",
                    failure_stage="schema",
                    failure_code="MODEL_SCHEMA_VALIDATION_ERROR",
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    detail="模型输出字段、类型或长度未通过Schema校验。",
                    input_sha256=input_sha256,
                    response_sha256=response_sha256,
                    duration_ms=duration_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    provider_call_performed=True,
                    provider_call_count=provider_call_count,
                )
            )
            append_skipped(role_index, "前一角色输出未通过服务端硬校验，后续角色未调用。")
            break
        except ValueError as error:
            message = str(error)
            if "evidence_id" in message or "证据包以外" in message:
                failure_stage = "evidence"
                failure_code = "MODEL_EVIDENCE_VALIDATION_ERROR"
            elif "禁止定性" in message:
                failure_stage = "policy"
                failure_code = "MODEL_POLICY_VIOLATION"
            else:
                failure_stage = "schema"
                failure_code = _semantic_failure_code(message)
            steps.append(
                AgentStep(
                    role=role,
                    status="MODEL_OUTPUT_INVALID",
                    failure_stage=failure_stage,
                    failure_code=failure_code,
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    detail=f"模型输出未通过服务端硬校验：{failure_code}",
                    input_sha256=input_sha256,
                    response_sha256=response_sha256,
                    duration_ms=duration_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    provider_call_performed=True,
                    provider_call_count=provider_call_count,
                )
            )
            append_skipped(role_index, "前一角色输出未通过服务端硬校验，后续角色未调用。")
            break
        sensitive_output_findings = scan_sensitive_payload(output.model_dump(mode="json"))
        if sensitive_output_findings:
            finding_summary = "、".join(
                f"{item['kind']}@{item['path']}" for item in sensitive_output_findings[:5]
            )
            steps.append(
                AgentStep(
                    role=role,
                    status="MODEL_OUTPUT_INVALID",
                    failure_stage="policy",
                    failure_code="MODEL_OUTPUT_SENSITIVE_DATA",
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    detail=f"模型输出命中高风险个人信息格式（{finding_summary}）；原文未保存，后续角色已停止。",
                    input_sha256=input_sha256,
                    response_sha256=response_sha256,
                    duration_ms=duration_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    provider_call_performed=True,
                    provider_call_count=provider_call_count,
                )
            )
            append_skipped(role_index, "前一角色输出命中高风险个人信息格式，后续角色未调用。")
            break
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
                provider_call_performed=True,
                provider_call_count=provider_call_count,
                output=output,
            )
        )
    return steps
