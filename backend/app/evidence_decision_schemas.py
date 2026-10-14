"""认定级证据检验合同；程序条件和专业语义状态分别保存。"""

from typing import Any, Literal
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegisteredEvidenceFields(BaseModel):
    """授权补充资料的显式字段；身份、原件哈希和编号由服务端盖章。"""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["customer_contract", "acceptance_record", "delivery_record", "ledger_entry", "invoice", "receivable_ledger", "receipt_record", "confirmation_response", "aging_schedule", "impairment_basis"]
    title: str = Field(min_length=1, max_length=160)
    granularity: Literal["transaction", "customer", "summary"]
    customer_id: str = Field(min_length=1, max_length=100)
    transaction_id: str | None = Field(default=None, max_length=100)
    balance_id: str | None = Field(default=None, max_length=100)
    available_at: date
    event_date: date | None = None
    posting_date: date | None = None
    recognition_event: str | None = Field(default=None, max_length=100)
    amount: str | None = Field(default=None, max_length=60)
    quantity: str | None = Field(default=None, max_length=60)
    unit_price: str | None = Field(default=None, max_length=60)
    discount: str | None = Field(default=None, max_length=60)
    aging_days: int | None = Field(default=None, ge=0)
    method: str | None = Field(default=None, max_length=400)
    currency: str | None = Field(default=None, max_length=20)
    unit: str | None = Field(default=None, max_length=20)
    basis: str | None = Field(default=None, max_length=80)


class EvidenceCheckRequest(BaseModel):
    """只接收已登记资料的引用，公开入口不接收任意文件或金额。"""

    model_config = ConfigDict(extra="forbid")
    base_kind: Literal["run", "validation_scenario"]
    base_id: str = Field(min_length=3, max_length=80)
    include_evidence_ids: list[str] = Field(default_factory=list, max_length=80)
    exclude_evidence_ids: list[str] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def distinct_operations(self):
        # 同一编号不能既加入又排除，避免操作顺序暗中影响结果。
        if set(self.include_evidence_ids) & set(self.exclude_evidence_ids):
            raise ValueError("同一证据不能同时加入与排除。")
        return self


class InvestigationHandoff(BaseModel):
    """角色必须把新增依据或任务绑定到服务端登记的核查事项。"""

    model_config = ConfigDict(extra="forbid")
    question_id: str = Field(min_length=1, max_length=60)
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    material_request_ids: list[str] = Field(default_factory=list, max_length=8)
    rationale: str = Field(min_length=1, max_length=350)

    @model_validator(mode="after")
    def has_traceable_reference(self):
        # 只有理由没有任何依据或任务的交接不具备可核查的贡献。
        if not self.evidence_ids and not self.material_request_ids:
            raise ValueError("交接必须引用证据或资料任务")
        if not self.rationale.strip():
            raise ValueError("交接目的不能为空")
        return self


class AuditInvestigation(BaseModel):
    """同一结构供页面、JSON及报告使用；旧运行缺少此项时不补造。"""

    schema_version: Literal["audit_investigation_v1"] = "audit_investigation_v1"
    rulebook_version: str
    rulebook_sha256: str
    source_snapshot_sha256: str
    case_id: str
    company_name: str
    source_mode: str
    questions: list[dict[str, Any]]
    material_requests: list[dict[str, Any]]
    evidence_decisions: list[dict[str, Any]]
    evidence_catalog: list[dict[str, Any]]
    default_evidence_ids: list[str]
    counter_contribution: dict[str, Any] = Field(default_factory=dict)
    professional_review_status: Literal["not_performed"] = "not_performed"
    semantic_support_status: Literal["not_verified"] = "not_verified"
    boundary: str


class EvidenceCheckResponse(BaseModel):
    """独立检验从不冒充本次完成了三角色模型调用。"""

    schema_version: Literal["evidence_check_v1"] = "evidence_check_v1"
    check_id: str
    base_kind: str
    base_id: str
    evaluation_mode: Literal["deterministic_evidence_check"] = "deterministic_evidence_check"
    provider_call_count: Literal[0] = 0
    investigation: AuditInvestigation
    changes: list[dict[str, Any]]
    ai_generated_content_notice: Literal["AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"] = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
