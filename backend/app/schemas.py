"""审迹智链运行接口的结构化输入输出。

模型只能提交受约束的语义草稿；数字、来源定位、规则触发和人工结论不由模型决定。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


RuleId = Literal["R1", "R2"]
AgentRole = Literal["challenge", "counter", "review"]


class RunRequest(BaseModel):
    """网页发起一次确定性规则运行时的最小输入。"""

    case_id: str = Field(default="STD_DEV_T0")
    current_year: int = Field(description="本年年度；当前DEV资料仅支持2025、2024、2023")
    scene: str = Field(default="审计计划")
    rule_ids: list[RuleId] = Field(default_factory=lambda: ["R1"])
    check_model: bool = Field(
        default=True,
        description="允许对已触发规则执行真实三Agent调用；无Key或失败时只返回真实状态。",
    )
    r2_min_gap: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="R2方向比较工程版的最小背离阈值；现金流跨期变号、基数过小时先返回“同比不宜比较”。",
    )

    @field_validator("rule_ids")
    @classmethod
    def rule_ids_must_be_unique_and_nonempty(cls, value: list[RuleId]) -> list[RuleId]:
        ordered = list(dict.fromkeys(value))
        if not ordered:
            raise ValueError("至少选择一条已接入规则。")
        return ordered


class ModelCheck(BaseModel):
    status: str
    model_id: str | None = None
    duration_ms: int | None = None
    response_sha256: str | None = None
    detail: str


class HealthResponse(BaseModel):
    service_status: str
    model_status: str
    model_id: str | None = None
    source_snapshot_id: str
    detail: str


class AgentClaim(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=6)


class AgentOutput(BaseModel):
    """三个角色共用的最小JSON Schema。"""

    schema_version: Literal["agent_output_v1"]
    run_id: str
    role: AgentRole
    rule_id: RuleId
    status: Literal["candidate", "retain", "downgrade", "defer"]
    claims: list[AgentClaim] = Field(min_length=1, max_length=3)
    normal_explanations: list[AgentClaim] = Field(default_factory=list, max_length=5)
    data_gaps: list[str] = Field(default_factory=list, max_length=8)
    requested_materials: list[str] = Field(default_factory=list, max_length=8)
    reason_for_status: str = Field(min_length=1, max_length=500)


class AgentStep(BaseModel):
    role: AgentRole
    status: str
    detail: str
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
    metrics: dict[str, float | None]
    risk_card: dict[str, Any] | None = None
    agent_steps: list[AgentStep] = Field(default_factory=list)


class RunResponse(BaseModel):
    run_id: str
    status: str
    context: dict[str, Any]
    source_validation: dict[str, Any]
    sources: list[dict[str, Any]]
    rule_results: list[RuleResult]
    model_check: ModelCheck


class HumanReviewRequest(BaseModel):
    status: Literal["未复核", "保留为待核查候选", "降级", "暂缓"]
    note: str = Field(default="", max_length=1000)


class StoredRunResponse(BaseModel):
    """读取运行日志时使用；review字段只表示人工保存状态。"""

    run: RunResponse
    human_review: HumanReviewRequest | None = None
