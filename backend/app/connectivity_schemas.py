"""跨报告关联核对合同：原文、关系、计算与人工处理分别记录。

公开报告只能支持其实际披露内容，关系成立不表示企业整体真实可靠。
金额使用十进制字符串，避免网页与后端浮点结果不一致。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

NOTICE = "AI生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，不构成审计结论、鉴证结论或鉴证意见。"
SCHEMA_VERSION = "connectivity_v1"


def now_iso() -> str:
    """统一记录带时区的运行时间，不由模型生成日期。"""
    return datetime.now(timezone.utc).isoformat()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportDocument(Contract):
    document_id: str
    case_id: str
    company_id: str
    company: str
    report_type: Literal["AR", "ESG"]
    period: str
    version: str = "登记公开版本"
    source_url: str
    source_kind: str = "official"
    disclosure_date: str = ""
    retrieved_at: str = ""
    compilation_basis: str = "待从本次报告核对"
    pages: int = 0
    file_sha256: str = ""
    available: bool = False


class DisclosureOccurrence(Contract):
    occurrence_id: str
    document_id: str
    pdf_page: int = Field(ge=1)
    printed_page: str = ""
    bbox: list[float] = Field(default_factory=list)
    page_width: float = 0
    page_height: float = 0
    label: str
    value: str | None = None
    unit: str = ""
    currency: str = ""
    currency_source_id: str = ""
    currency_source_quote: str = ""
    year: str = ""
    scope: str = ""
    definition: str = ""
    row_header: str = ""
    column_header: str = ""
    context: str
    footnotes: list[str] = Field(default_factory=list)
    quality: Literal["located", "uncertain", "text_only"] = "located"
    rounding: Literal["unknown", "exact", "half_up"] = "unknown"
    topic: str = ""


class EvidenceRef(Contract):
    """出处必须落到当前报告的真实片段，禁止拿规范当企业事实。"""
    occurrence_id: str
    quote: str = Field(min_length=2, max_length=1600)


class ComparisonCondition(Contract):
    name: str
    status: Literal["supported", "conflicting", "unknown"] = "unknown"
    reason: str = "本次原文尚未充分说明"
    evidence: list[EvidenceRef] = Field(default_factory=list)


class RelationshipMember(Contract):
    occurrence_id: str
    role: Literal["left", "right", "total", "component", "numerator", "denominator", "reported_ratio", "occurrence"]


class RelationshipCheck(Contract):
    check_id: str
    rule_id: Literal["EQ-001", "RD-001", "ENV-001", "INT-001", "OCC-001", "NAR-001"]
    rule_version: str = "2026-10-16.1"
    title: str
    topic: str = ""
    operator: Literal["equal", "sum", "ratio", "occurrences", "narrative"]
    members: list[RelationshipMember] = Field(default_factory=list, max_length=100)
    conditions: list[ComparisonCondition] = Field(default_factory=list, max_length=12)
    relationship_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=12)
    ratio_scale: str = "1"
    explanation: str = ""
    explanation_evidence: list[EvidenceRef] = Field(default_factory=list)
    criteria_status: str = "unknown"
    calculation_status: str = "not_executable"
    review_status: str = "unreviewed"
    calculation: dict = Field(default_factory=dict)
    unresolved: list[str] = Field(default_factory=list)
    related_checks: list[str] = Field(default_factory=list)


class RelationshipProposal(Contract):
    """模型只能提关系和引用，计算状态由程序生成。"""
    rule_id: Literal["EQ-001", "RD-001", "ENV-001", "INT-001", "OCC-001", "NAR-001"]
    title: str
    topic: str
    members: list[RelationshipMember] = Field(max_length=50)
    conditions: list[ComparisonCondition] = Field(max_length=12)
    relationship_evidence: list[EvidenceRef] = Field(max_length=12)
    explanation: str = ""
    explanation_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=12)


class AgentProposals(Contract):
    checks: list[RelationshipProposal] = Field(max_length=4)
    notes: list[str] = Field(default_factory=list, max_length=6)


class SingleAgentProposals(Contract):
    """单模型可一次提出两轮角色合计的八项关系，不人为压低输出容量。"""
    checks: list[RelationshipProposal] = Field(max_length=8)
    notes: list[str] = Field(default_factory=list, max_length=6)


class FinalFinding(Contract):
    check_id: str
    question: str
    requested_material: str
    purpose: str
    evidence: list[EvidenceRef] = Field(max_length=12)


class FinalSummaries(Contract):
    findings: list[FinalFinding] = Field(max_length=30)


class SearchCoverage(Contract):
    document_id: str
    total_pages: int
    parsed_pages: int
    searched_pages: list[int] = Field(default_factory=list)
    failed_pages: list[dict] = Field(default_factory=list)
    method: str = "PyMuPDF坐标文本、表格与上下文召回"
    discovered_count: int = 0


class FindingAndRequest(Contract):
    finding_id: str
    check_id: str
    known_facts: str
    question: str
    requested_material: str
    purpose: str
    provider_role: str = "公开报告使用者可进一步向披露方了解"
    status: str = "unresolved"


class ProfessionalRiskNote(Contract):
    check_id: str
    observation: str = Field(min_length=3, max_length=3000)
    reason: str = Field(min_length=3, max_length=2000)
    actor: str = "公开报告使用者"
    created_at: str = Field(default_factory=now_iso)


class SourceLineage(Contract):
    document_id: str
    producer: str
    category: str
    upstream: str = "unknown"
    independence: str = "同企业披露，不作为独立证实"


class ReviewEvent(Contract):
    event_id: str
    actor: str = "演示使用者"
    created_at: str = Field(default_factory=now_iso)
    action: str
    reason: str
    check_id: str
    before: dict
    after: dict


class ConnectivityRun(Contract):
    run_id: str
    task_kind: str = "connectivity"
    schema_version: str = SCHEMA_VERSION
    company: str
    period: str
    created_at: str = Field(default_factory=now_iso)
    discovery_mode: Literal["auto_discovery", "manual_located"] = "auto_discovery"
    dataset_role: Literal["development", "held_out", "synthetic"] = "development"
    execution_mode: str = "calculation_only"
    model_status: str = "not_requested"
    parent_run_id: str | None = None
    result_revision: int = 1
    documents: list[ReportDocument]
    occurrences: list[DisclosureOccurrence] = Field(default_factory=list)
    checks: list[RelationshipCheck] = Field(default_factory=list)
    coverage: list[SearchCoverage] = Field(default_factory=list)
    findings: list[FindingAndRequest] = Field(default_factory=list)
    professional_notes: list[ProfessionalRiskNote] = Field(default_factory=list)
    source_lineage: list[SourceLineage] = Field(default_factory=list)
    reviews: list[ReviewEvent] = Field(default_factory=list)
    agent_steps: list[dict] = Field(default_factory=list)
    provider_calls: list[dict] = Field(default_factory=list)
    duration_ms: int = 0
    versions: dict = Field(default_factory=dict)
    ai_generated_content_notice: str = NOTICE


class RunRequest(Contract):
    pair_id: str = Field(min_length=2, max_length=100)
    topics: list[Literal["research", "environment", "intensity"]] = Field(default_factory=lambda: ["research", "environment", "intensity"], min_length=1, max_length=3)
    mode: Literal["calculation_only", "three_agents", "single_model"] = "three_agents"
    retry_of_task_id: str | None = None


class CorrectionRequest(Contract):
    """更正保留父结果；身份说明不等于正式专业签批。"""
    expected_revision: int = Field(ge=1)
    check: RelationshipCheck
    reason: str = Field(min_length=3, max_length=2000)
    actor: str = Field(default="演示使用者", min_length=1, max_length=80)
    action_id: str = Field(min_length=8, max_length=100)

    @field_validator("reason", "actor")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("更正理由和演示身份不能为空")
        return value.strip()


class UserReviewRequest(Contract):
    """阅读确认与个人观察只改变使用者记录，不升级计算或专业结论。"""
    expected_revision: int = Field(ge=1)
    action: Literal["reading_confirmation", "personal_observation"]
    check_ids: list[str] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=3, max_length=2000)
    observation: str = Field(default="", max_length=3000)
    actor: str = Field(default="公开报告使用者", min_length=1, max_length=80)
    action_id: str = Field(min_length=8, max_length=100)

    @field_validator("reason", "actor")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("记录理由和使用者身份不能为空")
        return value.strip()
