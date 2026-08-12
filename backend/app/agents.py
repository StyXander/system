"""审迹智链的受约束三 Agent 调用、证据闸门与失败分类。

本模块处理模型语义推理，但不负责确定财务字段是否正确。
程序筛查先于模型调用，模型不能改变确定性计算的原始结果。
质疑角色只能提出受证据支持的候选主张，不形成最终草稿。
反证角色必须寻找正常解释、口径限制和相反证据，不负责下结论。
复核角色综合前两步，才允许提交非空的待核查草稿。
三个角色依次执行，前一步失败时后续角色不会假装独立成功。
角色顺序是状态机约束，不是给界面展示的装饰流程。
质疑与反证的草稿字段固定为空字符串，避免旁路生成最终文字。
质疑与反证的建议字段固定为不适用，避免越权给出处理意见。
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
规则未触发时三个角色均不适用，不为展示效果强行调用模型。
只有候选事项需要语义质疑、反证和复核，减少无意义调用。
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
import json
import time
from copy import deepcopy
from typing import Any, Callable
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
PROMPT_VERSION = "agent_prompt_v3"
ROLE_MAX_OUTPUT_TOKENS: dict[AgentRole, int] = {"challenge": 1400, "counter": 1400, "review": 1600}
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
                "status": {"type": "string", "enum": ["candidate", "retain", "downgrade", "defer"]},
                "claims": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 4,
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


def _agent_output_tool_for(role: AgentRole, rule_id: str, run_id: str) -> dict[str, Any]:
    """把角色、规则和本次运行号一并缩进严格Schema，避免跨角色状态或串单。"""
    tool = deepcopy(AGENT_OUTPUT_TOOL)
    properties = tool["function"]["parameters"]["properties"]
    properties["run_id"]["enum"] = [run_id]
    properties["role"]["enum"] = [role]
    properties["rule_id"]["enum"] = [rule_id]
    properties["status"]["enum"] = ROLE_ALLOWED_STATUSES[role]
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
4. status 固定返回 candidate，draft_title、draft_observation 为空字符串，ai_recommendation 返回 not_applicable；
5. 把输出交给 Counter Agent，不能提前给出最终处理建议。

严禁：把程序候选写成舞弊、违法、重大错报或审计意见；重算、改写或猜测金额、比例、页码、趋势和阈值；使用证据包以外的信息。""",
    "counter": """你是审迹智链 Counter Agent，负责对 Challenge Agent 的主张做反证和正常解释检查。

你会收到：同一 rule_result、deterministic_constraints、evidence_bundle，以及 Challenge Agent 的结构化输出。你必须：
1. 先判断 Challenge 的主张是否真的被当前证据支持，指出越界或不确定之处；
2. 优先寻找同一证据包中的正常业务解释、口径差异、季节性、合并范围和反向证据；
3. 找不到反证时要明确写“当前证据未发现相反材料”，不能编造反证；
4. 列出仍需取得的资料和下一步核查动作；
5. status 只能返回 candidate 或 defer，draft_title、draft_observation 为空字符串，ai_recommendation 返回 not_applicable；
6. 将结构化结果交给 Review Agent，不替 Review 作最终建议。

严禁：删除或弱化程序事实；根据增速差推断管理层动机；把待验证假设写成已确认事实；引用 Challenge 输出中不存在的 evidence_id。""",
    "review": """你是审迹智链 Review Agent，负责把程序筛查、Challenge 和 Counter 收敛成可交给人工复核的审计计划草稿。

你会收到：同一 rule_result、deterministic_constraints、evidence_bundle、Challenge 输出和 Counter 输出。你必须：
1. 检查三者是否引用同一案例、同一规则和当前证据白名单；
2. 区分“程序已计算事实”“有证据支持的解释”“仍待验证的假设”和“资料缺口”；
3. 形成非空 draft_title 与 draft_observation，简洁说明核查重点、证据边界和建议取得的材料；
4. status 与 ai_recommendation 必须一致，只能是 retain、downgrade 或 defer；
5. claims 仍需引用 evidence_id，不能因为前两角色写过就省略引用；
6. 输出的是 AI 辅助草稿，最终处理必须留给人工复核。

严禁：新增证据包没有的事实；把“保留”写成专业结论；认定舞弊、违法、重大错报或出具审计意见；把缺失数据补成金额或趋势。""",
}


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _compact_evidence_bundle(evidence_bundle: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把字段、RAG 与补充资料压成同一证据列表，模型不能引用列表外事实。"""
    if isinstance(evidence_bundle, list):
        categories = [("field", evidence_bundle)]
    else:
        categories = [
            ("field", evidence_bundle.get("field_evidence", [])),
            ("rag", evidence_bundle.get("rag_evidence", [])),
            ("supplement", evidence_bundle.get("supplement_evidence", [])),
        ]
    compact: list[dict[str, Any]] = []
    for evidence_type, items in categories:
        for row in items:
            if not row.get("evidence_id"):
                continue
            compact.append(
                {
                    "evidence_id": row["evidence_id"],
                    "evidence_type": evidence_type,
                    "field_label": row.get("field_label"),
                    "value": row.get("value"),
                    "unit": row.get("unit"),
                    "source_file": row.get("source_file"),
                    "document_id": row.get("document_id"),
                    "disclosure_date": row.get("disclosure_date"),
                    "pdf_page": row.get("pdf_page"),
                    "print_page": row.get("print_page"),
                    "locator": row.get("locator") or row.get("source_locator"),
                    "excerpt": str(row.get("excerpt") or "")[:500],
                    "review_status": row.get("review_status") or row.get("source_review_status"),
                }
            )
    return compact


def _system_prompt(role: AgentRole) -> str:
    return f"""{ROLE_PROMPTS[role]}

共同合同（所有角色必须遵守）：
只使用用户消息中的规则计算结果和 evidence_bundle，不得搜索网页、使用公司记忆或补全未提供事实。
deterministic_constraints 是程序真值：strong_threshold_met=false 时不得写已达到强阈值；
turnover_trend_available=false 时不得写周转或回款周期较上年延长/缩短；review 必须保留给出的口径与趋势局限。
不得认定舞弊、重大错报、违法，不得出具审计意见或投资建议。
每条 claim 必须绑定至少一个已有 evidence_id 且 support_status=supported。
正常解释只有在证据支持时才能标 supported；否则必须标 unverified_hypothesis，并明确是“待验证假设”。
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
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "agent_output_v2",
        "run_id": run_id,
        "role": role,
        "rule_result": {
            "rule_id": rule_result.rule_id,
            "status": rule_result.status,
            "metrics": rule_result.metrics,
            "risk_card": rule_result.risk_card,
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
        "output_contract": {
            "schema_version": "agent_output_v2",
            "role": role,
            "rule_id": rule_result.rule_id,
            "status": "challenge返回candidate；counter返回candidate或defer；review返回retain、downgrade或defer",
            "claims": [{"text": "待进一步了解的简短表述", "evidence_ids": ["本次证据ID"], "support_status": "supported"}],
            "normal_explanations": [],
            "data_gaps": [],
            "requested_materials": [],
            "reason_for_status": "仅基于本次证据包的简短说明",
            "draft_title": "review角色填写非空文本；其他角色必须为空字符串",
            "draft_observation": "review角色填写非空文本；其他角色必须为空字符串",
            "ai_recommendation": "review角色等于其status；其他角色为not_applicable",
        },
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
    rule_result: RuleResult | None = None,
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
        if not claim.evidence_ids or claim.support_status != "supported":
            raise ValueError("模型主张必须由本次evidence_id支持")
    for claim in [*output.claims, *output.normal_explanations]:
        if not set(claim.evidence_ids).issubset(allowed_evidence_ids):
            raise ValueError("模型引用了本次证据包以外的evidence_id")
        if claim.support_status == "supported" and not claim.evidence_ids:
            raise ValueError("supported 表述缺少evidence_id")
        if claim.support_status == "unverified_hypothesis" and "待验证" not in claim.text:
            raise ValueError("未获支持的解释必须明确标为待验证假设")
    if output.schema_version == "agent_output_v2" and role == "review":
        if not output.draft_title.strip() or not output.draft_observation.strip():
            raise ValueError("复核Agent未形成最终待核查草稿")
        if output.ai_recommendation != output.status:
            raise ValueError("复核Agent的ai_recommendation必须与status一致")
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
        false_strong_phrases = (
            "超强阈值",
            "超过强阈值",
            "达到强阈值",
            "高于强阈值",
            "突破强阈值",
        )
        if not strong_met and any(phrase in joined for phrase in false_strong_phrases):
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
    evidence_bundle: dict[str, Any] | list[dict[str, Any]],
    enabled: bool,
    api_key: str | None,
    base_url: str,
    model_id: str,
    before_role: Callable[[AgentRole], bool] | None = None,
) -> list[AgentStep]:
    """串行执行三角色；任一步失败即关闭AI草稿链，不生成伪造的后续角色答案。"""
    if rule_result.status != "candidate":
        return [AgentStep(role="challenge", status="not_applicable", detail="规则未触发，未调用模型。")]
    if not enabled:
        return [AgentStep(role="challenge", status="not_requested", detail="本次未请求三Agent调用。")]
    if not api_key:
        return [AgentStep(role="challenge", status="config_missing", model_id=None, prompt_version=PROMPT_VERSION, detail="未配置DEEPSEEK_API_KEY；未调用模型。")]

    compact_bundle = _compact_evidence_bundle(evidence_bundle)
    allowed_evidence_ids = {item["evidence_id"] for item in compact_bundle}
    if not allowed_evidence_ids:
        return [AgentStep(role="challenge", status="EVIDENCE_BUNDLE_EMPTY", model_id=model_id, prompt_version=PROMPT_VERSION, detail="统一证据包为空，已关闭AI草稿链。")]
    previous_outputs: dict[str, AgentOutput] = {}
    steps: list[AgentStep] = []
    for role in ROLE_ORDER:
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
                break
        payload = _user_payload(run_id, role, rule_result, compact_bundle, previous_outputs)
        input_sha256 = _json_hash(payload)
        try:
            raw_output, duration_ms, response_sha256, _, input_tokens, output_tokens = _call_model(
                api_key=api_key,
                base_url=base_url,
                model_id=model_id,
                role=role,
                payload=payload,
            )
        except (HTTPError, URLError, TimeoutError, OSError) as error:
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
                )
            )
            break
        except json.JSONDecodeError:
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
                )
            )
            break
        except (KeyError, IndexError, UnicodeDecodeError, TypeError, ValueError) as error:
            steps.append(
                AgentStep(
                    role=role,
                    status="MODEL_OUTPUT_INVALID",
                    failure_stage="tool_arguments",
                    failure_code="MODEL_TOOL_ARGUMENTS_INVALID",
                    model_id=model_id,
                    prompt_version=PROMPT_VERSION,
                    detail=f"模型工具参数未通过协议检查：{type(error).__name__}",
                    input_sha256=input_sha256,
                )
            )
            break
        try:
            output = validate_agent_output(
                raw_output,
                run_id=run_id,
                role=role,
                rule_id=rule_result.rule_id,
                allowed_evidence_ids=allowed_evidence_ids,
                rule_result=rule_result,
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
                )
            )
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
                failure_code = "MODEL_SEMANTIC_VALIDATION_ERROR"
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
                )
            )
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
                output=output,
            )
        )
    return steps
