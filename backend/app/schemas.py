"""审迹智链 0.7.1 的结构化输入输出契约。

程序筛查、AI 建议、人工处理和运行完整性始终是四个独立字段。兼容字段
``check_model`` 只负责把旧请求映射到新运行模式，不能把失败运行包装成完整分析。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


RuleId = Literal["R1", "R2"]
AgentRole = Literal["challenge", "counter", "review"]
RunMode = Literal["full_analysis", "calculation_only"]
PipelineAnalysisMode = Literal["rag_only", "full_analysis"]
SupportStatus = Literal["supported", "unverified_hypothesis"]


# 所有对外机器可读结果与人可读草稿共用同一句声明，避免不同出口弱化边界。
AI_GENERATED_CONTENT_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"


class AiGeneratedContentNotice(BaseModel):
    """为公开 JSON 输出提供稳定、可测试的 AI 生成内容声明。"""

    ai_generated_content_notice: Literal[
        "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
    ] = AI_GENERATED_CONTENT_NOTICE


class RunRequest(BaseModel):
    """发起一次案例运行；完整分析是主路径，计算预检明确属于不完整运行。"""

    case_id: str = Field(default="STD_DEV_T0", min_length=3, max_length=40)
    current_year: int = Field(description="本年年度；必须在所选案例的连续期间登记表中存在。")
    scene: Literal["审计计划"] = "审计计划"
    rule_ids: list[RuleId] = Field(default_factory=lambda: ["R1"])
    run_mode: RunMode = "full_analysis"
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


class ModelCheck(BaseModel):
    status: str
    model_id: str | None = None
    duration_ms: int | None = None
    response_sha256: str | None = None
    detail: str


class HealthResponse(AiGeneratedContentNotice):
    service_status: str
    model_status: str
    model_id: str | None = None
    source_snapshot_id: str
    detail: str
    engine_version: str = "0.7.1"


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
    status: Literal["candidate", "retain", "downgrade", "defer"]
    claims: list[AgentClaim] = Field(min_length=1, max_length=4)
    normal_explanations: list[AgentClaim] = Field(default_factory=list, max_length=5)
    data_gaps: list[str] = Field(default_factory=list, max_length=8)
    requested_materials: list[str] = Field(default_factory=list, max_length=8)
    reason_for_status: str = Field(min_length=1, max_length=500)
    draft_title: str = Field(default="", max_length=200)
    draft_observation: str = Field(default="", max_length=1000)
    ai_recommendation: Literal["retain", "downgrade", "defer", "not_applicable"] | None = None


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


class HumanReviewRequest(BaseModel):
    status: Literal["未复核", "保留为待核查候选", "降级", "暂缓"]
    note: str = Field(default="", max_length=1000)
    reviewer: str = Field(default="", max_length=100)
    reviewed_at: str | None = None
    export_approved: bool = False
    reviewer_type: Literal["human", "automation"] = "human"


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
    """从巨潮资讯网创建新企业导入任务；默认只做本地 RAG，不自动开放模型传输。"""

    # 企业字段支持股票代码或名称，最终必须回到官方股票清单确认。
    company_query: str = Field(min_length=1, max_length=120)
    years: int = Field(default=3, ge=2, le=5)
    latest_year: int | None = Field(default=None, ge=2000, le=2100)
    # 默认路径只下载、校验和建库，不自动把公开年报发送给外部模型。
    analysis_mode: PipelineAnalysisMode = "rag_only"
    # R1 是当前项目最稳定的演示规则，其他规则仍沿用已有字段校验。
    rule_ids: list[RuleId] = Field(default_factory=lambda: ["R1"])
    force_refresh: bool = False
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


class CNInfoCompanyConfirmation(BaseModel):
    """同名企业候选确认只允许选择巨潮返回的股票代码。"""

    # 这里只校验代码格式，候选归属还会在接口中与上一轮结果比对。
    ticker: str = Field(pattern=r"^\d{6}$")


class CNInfoFieldConfirmation(BaseModel):
    """巨潮自动字段候选的真人确认、修正或拒绝记录。"""

    # 字段编号由案例内的字段种类和报告年度组成，不能由前端拼接任意路径。
    field_id: str = Field(pattern=r"^(revenue|accounts_receivable|accounts_receivable_allowance|accounts_receivable_net|operating_cash_flow|net_profit)_\d{4}$")
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

    @model_validator(mode="after")
    def map_legacy(self) -> "SupplementRerunRequest":
        if self.check_model is not None:
            self.run_mode = "full_analysis" if self.check_model else "calculation_only"
        return self


class StoredRunResponse(AiGeneratedContentNotice):
    """读取运行日志时使用；human_review 是真实人工保存状态。"""

    run: RunResponse
    human_review: HumanReviewRequest | None = None
