"""审迹智链 0.7.1 的结构化输入输出契约。

程序筛查、AI 建议、人工处理和运行完整性始终是四个独立字段。兼容字段
``check_model`` 只负责把旧请求映射到新运行模式，不能把失败运行包装成完整分析。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


RuleId = Literal["R1", "R2"]
AgentRole = Literal["challenge", "counter", "review"]
RunMode = Literal["full_analysis", "calculation_only"]
PipelineAnalysisMode = Literal["rag_only", "full_analysis"]
CachePolicy = Literal["prefer_cache", "refresh_if_stale", "force_refresh"]
SupportStatus = Literal["supported", "unverified_hypothesis"]
# 2026-09-19 签字口径 D1/D2：以下两组代号是展示层分级，不是审计认定。
PlanningPriorityGrade = Literal["P1", "P2", "P3", "P4", "S", "G"]
EvidenceStateCode = Literal["E1", "E2", "E3"]
# 运行来源徽标只允许三态，live 与回放、备用链不得互相冒充。
ExecutionBadgeMode = Literal["external_live", "cache_replay", "deterministic_backup"]
DispositionCode = Literal["retain", "downgrade", "defer", "not_applicable"]


# 所有对外机器可读结果与人可读草稿共用同一句声明，避免不同出口弱化边界。
AI_GENERATED_CONTENT_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"


class AiGeneratedContentNotice(BaseModel):
    """为公开 JSON 输出提供稳定、可测试的 AI 生成内容声明。"""

    ai_generated_content_notice: Literal[
        "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
    ] = AI_GENERATED_CONTENT_NOTICE


class AuthLoginRequest(BaseModel):
    """同源登录只接收账号凭据，令牌始终由服务端写入 HttpOnly Cookie。"""

    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        """做最小且不依赖额外包的邮箱校验，避免把空白或控制字符交给身份服务。"""

        normalized = value.strip().lower()
        if any(character.isspace() for character in normalized) or normalized.count("@") != 1:
            raise ValueError("请输入有效的邮箱地址。")
        local, domain = normalized.split("@", 1)
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("请输入有效的邮箱地址。")
        return normalized


class RunRequest(BaseModel):
    """发起一次案例运行；完整分析是主路径，计算预检明确属于不完整运行。"""

    case_id: str = Field(default="STD_DEV_T0", min_length=3, max_length=40)
    current_year: int = Field(description="本年年度；必须在所选案例的连续期间登记表中存在。")
    scene: Literal["审计计划"] = "审计计划"
    rule_ids: list[RuleId] = Field(default_factory=lambda: ["R1"])
    run_mode: RunMode = "full_analysis"
    force_deterministic_backup: bool = Field(default=False, description="仅在真实模型失败后由用户显式请求的确定性备用链")
    check_model: bool | None = Field(
        default=None,
        description="旧接口兼容：true 映射完整分析，false 映射仅计算预检；新前端不再发送。",
    )
    planned_materiality: float | None = Field(
        default=None,
        ge=0,
        description="计划重要性金额（与案例金额单位一致）；缺失时不得评价金额重要性。",
    )
    r1_gap_threshold: float = Field(
        default=0.15,
        ge=0,
        le=2,
        description="R1 工程草案增速差阈值；未获专业签字，不是正式审计标准。",
    )
    r1_strong_gap_threshold: float = Field(default=0.30, ge=0, le=3)
    r1_absolute_threshold: float = Field(default=0.0, ge=0)
    r2_min_gap: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("case_id")
    @classmethod
    def normalize_case_id(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("rule_ids")
    @classmethod
    def rule_ids_must_be_unique_and_nonempty(cls, value: list[RuleId]) -> list[RuleId]:
        ordered = list(dict.fromkeys(value))
        if not ordered:
            raise ValueError("至少选择一条已接入规则。")
        return ordered

    @model_validator(mode="after")
    def map_legacy_check_model(self) -> "RunRequest":
        if self.check_model is not None:
            self.run_mode = "full_analysis" if self.check_model else "calculation_only"
        if self.r1_strong_gap_threshold < self.r1_gap_threshold:
            raise ValueError("R1 强提示阈值不得低于基本提示阈值。")
        return self


class DemoRunCreateRequest(BaseModel):
    """创建固定案例分阶段演示运行；后端返回 202 与 task_id，避免等待整次分析。"""

    case_id: str = Field(min_length=3, max_length=40)
    current_year: int = Field(description="本年年度；必须在所选案例的连续期间登记表中存在。")
    scene: Literal["审计计划"] = "审计计划"
    rule_ids: list[RuleId] = Field(default_factory=lambda: ["R1"])
    run_mode: RunMode = "full_analysis"
    planned_materiality: float | None = Field(default=None, ge=0)
    retry_of_task_id: str | None = Field(default=None, max_length=80)
    # 仅由显式确定性备用入口设置；正式主按钮保持真实模型/降级状态原样。
    force_deterministic_backup: bool = False

    @field_validator("case_id")
    @classmethod
    def normalize_case_id(cls, value: str) -> str:
        return value.strip().upper()


class ModelCheck(BaseModel):
    status: str
    model_id: str | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_call_count: int = 0
    execution_mode: str = "not_applicable"
    cache_hit: bool = False
    cache_key_hash: str | None = None
    response_sha256: str | None = None
    analysis_route: str = "not_requested"
    analysis_conclusion: str | None = None
    detail: str


class HealthResponse(AiGeneratedContentNotice):
    service_status: str
    model_status: str
    model_id: str | None = None
    full_analysis_ready: bool = False
    full_analysis_reason_code: str = "unknown"
    full_analysis_message: str = "尚未读取真实模型运行条件。"
    deterministic_backup_available: bool = True
    source_snapshot_id: str
    detail: str
    engine_version: str = "0.7.1"
    provider_status: str | None = None
    provider_reason_code: str | None = None
    provider_checked_at: str | None = None
    provider_source: str | None = None
    provider_ready: bool = False
    model_execution_ready: bool = False
    competition_release_ready: bool = False


class AgentClaim(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    support_status: SupportStatus = "supported"


class AgentOutput(AiGeneratedContentNotice):
    """v2 增加最终草稿与支持状态；v1 只用于读取历史运行。"""

    schema_version: Literal["agent_output_v1", "agent_output_v2"]
    run_id: str
    role: AgentRole
    rule_id: RuleId
    analysis_conclusion: Literal[
        "risk_candidate",
        "no_trigger_confirmed",
        "additional_procedure_required",
        "data_gap",
        "industry_boundary",
    ] | None = None
    status: Literal["candidate", "retain", "downgrade", "defer"]
    # 证据包为空时允许空 claims；服务端语义校验会限制该例外只能用于
    # 数据缺口/行业边界路线，正常有证据的路线最多形成 Top 5 条核心待核查事项。
    claims: list[AgentClaim] = Field(default_factory=list, max_length=5)
    normal_explanations: list[AgentClaim] = Field(default_factory=list, max_length=5)
    data_gaps: list[str] = Field(default_factory=list, max_length=8)
    requested_materials: list[str] = Field(default_factory=list, max_length=8)
    reason_for_status: str = Field(min_length=1, max_length=500)
    draft_title: str = Field(default="", max_length=200)
    draft_observation: str = Field(default="", max_length=1000)
    ai_recommendation: Literal["retain", "downgrade", "defer", "not_applicable"] | None = None
    evidence_fitness_violations: list[dict[str, Any]] = Field(default_factory=list, max_length=8)


class AgentStep(BaseModel):
    role: AgentRole
    status: str
    detail: str
    failure_stage: Literal["provider", "tool_arguments", "schema", "evidence", "policy"] | None = None
    failure_code: str | None = Field(default=None, max_length=80)
    model_id: str | None = None
    prompt_version: str | None = None
    input_sha256: str | None = None
    response_sha256: str | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_call_performed: bool = False
    provider_call_count: int = Field(default=0, ge=0)
    # 每次真实调用只记录脱敏哈希、校验结果和用量；不保存模型原文。
    model_attempt_history: list[dict[str, Any]] = Field(default_factory=list, max_length=4)
    output: AgentOutput | None = None


class RuleResult(BaseModel):
    rule_id: RuleId
    status: str
    source_validation: dict[str, Any]
    metrics: dict[str, float | int | str | bool | None]
    risk_card: dict[str, Any] | None = None
    agent_steps: list[AgentStep] = Field(default_factory=list)
    screening_status: str | None = None
    ai_recommendation: str = "not_generated"
    ai_draft: dict[str, Any] | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    ai_analysis_route: str | None = None
    ai_analysis_conclusion: str | None = None


class PlanningPriority(BaseModel):
    """D1 审计关注优先级：只由确定性纯函数产出，模型不得直接给级。"""

    grade: PlanningPriorityGrade | None = None
    label: str | None = None
    factors: list[dict[str, Any]] | None = None
    boundary: str | None = None


class EvidenceState(BaseModel):
    """D2 证据闭合状态：输入只能是既有控制项，不得由模型打分。"""

    state: EvidenceStateCode | None = None
    label: str | None = None
    reasons: list[str] | None = None
    boundary: str | None = None


class Disposition(BaseModel):
    """复核处置轴：与优先级并排独立显示，二者互不覆盖。"""

    ai_recommendation: DispositionCode | None = None
    label: str | None = None
    reason_for_status: str | None = None


class MaterialityDisplay(BaseModel):
    """金额重要性独立展示，不折入审计关注优先级。"""

    assessment: str | None = None
    multiple: float | None = None


class ExecutionBadge(BaseModel):
    """运行来源徽标：本次真实调用、已验证回放与确定性备用链不得混淆。"""

    mode: ExecutionBadgeMode | None = None
    label: str | None = None
    provider_call_count: int | None = None


# 徽标中文标签与判定表由契约 §六 冻结，前后端只允许这一处实现。
EXECUTION_BADGE_LABELS: dict[str, str] = {
    "external_live": "本次真实模型运行",
    "cache_replay": "已验证历史结果回放",
    "deterministic_backup": "确定性备用链",
}
# 后端内部 execution_mode 到对外三态的归一映射；未列出的模式一律视为来源不可判定。
_EXECUTION_MODE_TO_BADGE: dict[str, str] = {
    "deterministic_backup": "deterministic_backup",
    "cache_replay": "cache_replay",
    "external_cached": "cache_replay",
    "external_live": "external_live",
}


def execution_badge_for(
    *,
    execution_mode: str | None,
    cache_hit: bool,
    provider_call_count: int | None,
) -> ExecutionBadge:
    """按契约判定表产出运行来源徽标；不推断任何成功或失败。"""

    calls = int(provider_call_count or 0)
    mode = _EXECUTION_MODE_TO_BADGE.get(str(execution_mode or ""))
    if mode is None and cache_hit:
        mode = "cache_replay"
    if mode is None:
        return ExecutionBadge(provider_call_count=calls)
    if mode == "external_live" and calls <= 0:
        # 声称 live 却没有调用留痕时不产出徽标，避免把无法判定的来源写成真实运行。
        return ExecutionBadge(provider_call_count=0)
    return ExecutionBadge(mode=mode, label=EXECUTION_BADGE_LABELS[mode], provider_call_count=calls)


class NumericGateSummary(BaseModel):
    """数字可追溯闸门的对外摘要；完整轨迹仍保留在 context.numeric_claim_trace。"""

    passed: bool | None = None
    key_unverified: list[str] | None = None
    unverified_count: int | None = None
    trace_count: int | None = None


class RunResponse(AiGeneratedContentNotice):
    run_id: str
    status: str
    context: dict[str, Any]
    source_validation: dict[str, Any]
    sources: list[dict[str, Any]]
    rule_results: list[RuleResult]
    model_check: ModelCheck
    schema_version: Literal["run_output_v2"] = "run_output_v2"
    engine_version: str = "0.7.1"
    screening_status: str = "not_run"
    ai_recommendation: str = "not_generated"
    human_disposition: str = "未复核"
    run_completeness: str = "incomplete"
    evidence_bundle: dict[str, Any] = Field(default_factory=dict)
    retrievals: list[dict[str, Any]] = Field(default_factory=list)
    final_ai_draft: dict[str, Any] | None = None
    execution_mode: str = "not_applicable"
    model_id: str | None = None
    prompt_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    provider_call_count: int = 0
    # 每次真实供应商尝试的内部追踪 ID；由输入/响应哈希派生，不保存供应商原文或密钥。
    provider_call_ids: list[str] = Field(default_factory=list, max_length=32)
    cache_hit: bool = False
    cache_key_hash: str | None = None
    parent_run_id: str | None = None
    ai_analysis_route: str = "not_requested"
    ai_analysis_conclusion: str | None = None
    ai_execution_requested: bool = False
    ai_execution_completed: bool = False
    agent_steps: list[AgentStep] = Field(default_factory=list)
    # 2026-09-19 契约字段：全部可选，历史 run JSON 缺失时保持 None 而不是报错。
    planning_priority: PlanningPriority | None = None
    evidence_state: EvidenceState | None = None
    disposition: Disposition | None = None
    materiality_display: MaterialityDisplay | None = None
    execution_badge: ExecutionBadge | None = None
    numeric_gate_summary: NumericGateSummary | None = None


def sanitize_cached_trace(run: RunResponse, *, current_run_id: str) -> RunResponse:
    """清理缓存结果中的本次调用字段，并把草稿编号绑定到回放运行。"""

    def rebind_run_ids(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: current_run_id if key == "run_id" else rebind_run_ids(child)
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [rebind_run_ids(child) for child in value]
        return value

    def sanitize_step(step: AgentStep) -> AgentStep:
        output = step.output
        if output is not None:
            output = output.model_copy(update={"run_id": current_run_id})
        return step.model_copy(
            update={
                "output": output,
                "input_sha256": None,
                "response_sha256": None,
                "duration_ms": None,
                "input_tokens": None,
                "output_tokens": None,
                "provider_call_performed": False,
                "provider_call_count": 0,
                "model_attempt_history": [],
            }
        )

    results = [
        result.model_copy(
            update={
                "agent_steps": [sanitize_step(step) for step in result.agent_steps],
                "ai_draft": rebind_run_ids(result.ai_draft) if result.ai_draft else None,
            }
        )
        for result in run.rule_results
    ]
    flattened_steps = [step for result in results for step in result.agent_steps]
    return run.model_copy(
        update={
            "rule_results": results,
            "final_ai_draft": rebind_run_ids(run.final_ai_draft) if run.final_ai_draft else None,
            "agent_steps": flattened_steps,
        }
    )


class HumanReviewRequest(BaseModel):
    status: Literal["未复核", "保留为待核查候选", "降级", "暂缓"]
    note: str = Field(default="", max_length=1000)
    reviewer: str = Field(default="", max_length=100)
    reviewed_at: str | None = None
    export_approved: bool = False
    # 默认必须是 automation：自称真人要显式声明，再由服务端校验并盖章归属。
    reviewer_type: Literal["human", "automation"] = "automation"
    reviewer_user_id: str | None = Field(default=None, max_length=120)
    reviewer_source: str | None = Field(default=None, max_length=40)


class ModelTransferConsentRequest(BaseModel):
    """逐案例、限时、最小范围的外部模型传输同意。"""

    provider: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=160)
    transmission_scope: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=300)
    valid_until: str = Field(min_length=10, max_length=40)
    confirmed: bool = False

    @field_validator("valid_until")
    @classmethod
    def valid_until_must_be_future_iso(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("有效期必须是 ISO-8601 日期时间。") from error
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed <= datetime.now(timezone.utc):
            raise ValueError("模型传输同意有效期必须晚于当前时间。")
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


class RagRetrieveRequest(BaseModel):
    query: str = Field(default="", max_length=500)
    question_id: str | None = Field(default=None, max_length=20)
    t0: str = Field(default="2026-04-30", pattern=r"^\d{4}-\d{2}-\d{2}$")
    rule_id: RuleId = "R1"
    top_k: int = Field(default=5, ge=1, le=10)
    case_id: str = "STD_DEV_T0"
    company_name: str | None = Field(default=None, max_length=200)

    @field_validator("case_id")
    @classmethod
    def normalize_case_id(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def query_or_question_is_required(self) -> "RagRetrieveRequest":
        if not self.query.strip() and not self.question_id:
            raise ValueError("检索词和固定问题编号至少填写一项。")
        return self


class CNInfoPipelineRequest(BaseModel):
    """从巨潮资讯网创建新企业任务；默认只下载并建立 RAG，避免意外消耗模型额度。"""

    # 企业字段支持股票代码或名称，最终必须回到官方股票清单确认。
    company_query: str = Field(min_length=1, max_length=120)
    years: int = Field(default=3, ge=2, le=5)
    latest_year: int | None = Field(default=None, ge=2000, le=2100)
    # 新企业默认只下载、校验和建库；调用者必须显式选择 full_analysis。
    analysis_mode: PipelineAnalysisMode = "rag_only"
    # R1 是当前项目最稳定的演示规则，其他规则仍沿用已有字段校验。
    rule_ids: list[RuleId] = Field(default_factory=lambda: ["R1"])
    force_refresh: bool = False
    cache_policy: CachePolicy = "prefer_cache"
    planned_materiality: float | None = Field(default=None, ge=0)

    @field_validator("company_query")
    @classmethod
    def normalize_company_query(cls, value: str) -> str:
        return value.strip()

    @field_validator("rule_ids")
    @classmethod
    def pipeline_rule_ids_must_be_unique(cls, value: list[RuleId]) -> list[RuleId]:
        ordered = list(dict.fromkeys(value))
        if not ordered:
            raise ValueError("至少选择一条规则。")
        return ordered

    @model_validator(mode="after")
    def force_refresh_sets_cache_policy(self) -> "CNInfoPipelineRequest":
        if self.force_refresh:
            self.cache_policy = "force_refresh"
        return self


class CacheResolveRequest(BaseModel):
    """查询本地公开年报热缓存；命中后不触发巨潮网络请求。"""

    company_query: str = Field(min_length=1, max_length=120)
    years: int = Field(default=3, ge=2, le=5)
    latest_year: int | None = Field(default=None, ge=2000, le=2100)
    cache_policy: CachePolicy = "prefer_cache"

    @field_validator("company_query")
    @classmethod
    def normalize_cache_company_query(cls, value: str) -> str:
        return value.strip()


class CachePrewarmRequest(BaseModel):
    """批量建立常用企业热缓存；每个企业仍走同一条来源校验流程。"""

    companies: list[str] = Field(min_length=1, max_length=51)
    years: int = Field(default=3, ge=2, le=5)
    latest_year: int | None = Field(default=None, ge=2000, le=2100)
    analysis_mode: PipelineAnalysisMode = "rag_only"
    rule_ids: list[RuleId] = Field(default_factory=lambda: ["R1"])
    force_refresh: bool = False

    @field_validator("companies")
    @classmethod
    def normalize_prewarm_companies(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not normalized:
            raise ValueError("至少提供一家企业。")
        return normalized

    @field_validator("rule_ids")
    @classmethod
    def prewarm_rule_ids_must_be_unique(cls, value: list[RuleId]) -> list[RuleId]:
        ordered = list(dict.fromkeys(value))
        if not ordered:
            raise ValueError("至少选择一条规则。")
        return ordered


class CNInfoCompanyConfirmation(BaseModel):
    """同名企业候选确认只允许选择巨潮返回的股票代码。"""

    # 这里只校验代码格式，候选归属还会在接口中与上一轮结果比对。
    ticker: str = Field(pattern=r"^\d{6}$")


class CNInfoFieldConfirmation(BaseModel):
    """巨潮自动字段候选的真人确认、修正或拒绝记录。"""

    # 字段编号先限制为安全的小写协议键与年度；服务层随后必须精确匹配案例内
    # 已登记候选。这样行业专用字段可复核，同时未知字段和路径字符仍会被拒绝。
    field_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}_\d{4}$")
    decision: Literal["confirm", "correct", "reject"]
    reviewer: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=500)
    corrected_value: float | None = None
    corrected_pdf_page: int | None = Field(default=None, ge=1, le=10000)
    corrected_locator: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def corrected_value_is_complete(self) -> "CNInfoFieldConfirmation":
        if self.decision == "correct" and self.corrected_value is None:
            raise ValueError("修正字段必须提供 corrected_value。")
        if self.decision == "correct" and self.corrected_pdf_page is None:
            raise ValueError("修正字段必须提供 corrected_pdf_page。")
        return self


class SupplementRerunRequest(BaseModel):
    run_mode: RunMode = "full_analysis"
    check_model: bool | None = None
    force_deterministic_backup: bool = Field(
        default=False,
        description="仅在用户明确选择时沿用确定性备用链；普通续分析会清除父运行遗留标志。",
    )

    @model_validator(mode="after")
    def map_legacy(self) -> "SupplementRerunRequest":
        if self.check_model is not None:
            self.run_mode = "full_analysis" if self.check_model else "calculation_only"
        return self


class SupplementSampleRequest(BaseModel):
    """公开竞赛样例补充资料的最小请求合同。"""

    parent_run_id: str
    sample_id: str
    bound_rule_ids: list[str] = Field(default_factory=lambda: ["R1"])
    as_of_date: str | None = None
    note: str = ""


class StoredRunResponse(AiGeneratedContentNotice):
    """读取运行日志时使用；human_review 是真实人工保存状态。"""

    run: RunResponse
    human_review: HumanReviewRequest | None = None
