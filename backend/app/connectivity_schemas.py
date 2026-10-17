"""跨报告关联核对合同：原文、关系、计算与人工处理分别记录。

公开报告只能支持其实际披露内容，关系成立不表示企业整体真实可靠。
金额使用十进制字符串，避免网页与后端浮点结果不一致。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NOTICE = "AI生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，不构成审计结论、鉴证结论或鉴证意见。"
# 历史业务声明保持原文不变；导出与接口按 task_kind 分派，不互相冒充。
LEGACY_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
NOTICE_BY_TASK_KIND = {"connectivity": NOTICE, "legacy_audit": LEGACY_NOTICE}
SCHEMA_VERSION = "connectivity_v2"

# 本轮事项类型裁决：取方案(b)。海菲曼利润总额只走版本子流程并使用独立事项标识，
# 不扩 topics 枚举，以免把双报告引擎改造成通用多文档平台。
TOPIC_DOMAIN = {"research": "研发投入", "environment": "环保投入", "intensity": "强度与分母", "version_track": "公告版本追踪"}


def notice_for(task_kind: str) -> str:
    """按业务类型返回对外声明；未登记的业务类型一律拒绝，不默认套用新声明。"""
    if task_kind not in NOTICE_BY_TASK_KIND:
        raise ValueError(f"未登记的对外声明类型：{task_kind}")
    return NOTICE_BY_TASK_KIND[task_kind]


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
    # 报告所属期间与指标所属期间分开登记；旧 period 只作读取兼容。
    report_period: str = ""
    metric_period: str = ""
    version: str = "登记公开版本"
    source_url: str
    source_kind: str = "official"
    disclosure_date: str = ""
    retrieved_at: str = ""
    compilation_basis: str = "待从本次报告核对"
    pages: int = 0
    file_sha256: str = ""
    available: bool = False
    version_role: Literal["original", "correction", "unknown"] = "unknown"

    @model_validator(mode="after")
    def _report_period_from_legacy(self):
        """报告所属期间可由文档自身 period 补齐；指标期间一律不自动推定。"""
        if not self.report_period.strip():
            self.report_period = self.period
        return self

    @property
    def effective_period(self) -> str:
        return self.report_period or self.period


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
    unit_source: str = ""
    currency: str = ""
    currency_source_id: str = ""
    currency_source_quote: str = ""
    year: str = ""
    # 年度列解析失败时保持空值并标 unattributed，不得回退成报告期间。
    year_status: Literal["attributed", "unattributed"] = "unattributed"
    scope: str = ""
    definition: str = ""
    row_header: str = ""
    column_header: str = ""
    header_path: list[str] = Field(default_factory=list)
    context: str
    footnotes: list[str] = Field(default_factory=list)
    footnote_scope: str = ""
    # 质量默认失败关闭：缺省不等于可信，由提取器显式升级为 located。
    quality: Literal["located", "uncertain", "text_only"] = "uncertain"
    quality_reason: str = "提取器未显式确认年度、单位与行列绑定"
    rounding: Literal["unknown", "exact", "half_up"] = "unknown"
    version_role: Literal["original", "correction", "unknown"] = "unknown"
    topic: str = ""


class ExtractionExclusion(Contract):
    """已提取但未进入候选的行或位置，必须显式列示，不能静默丢弃。"""
    occurrence_id: str
    document_id: str
    pdf_page: int = Field(ge=1)
    label: str = ""
    value: str = ""
    reason: str
    year: str = ""
    unit: str = ""


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


class AdjustmentRecord(Contract):
    """差异解释的量化调节：只收同基准、有原文依据、符号明确、互不重叠的加性项。

    乘性变换、共享变量依赖与多级基准转换不在首版范围，遇到即登记为未支持。
    `sign` 表示该解释对差额的贡献方向，剩余残差＝原始差额 − Σ有符号调节额；
    因此与原始差额同向的抵扣项应登记为负号，而不是一律写正号。
    """
    adjustment_id: str
    effect_id: str
    label: str
    sign: Literal["+", "-"]
    amount: str = Field(pattern=r"^\d+(?:\.\d+)?$")
    unit: str
    metric_period: str = ""
    scope: str = ""
    basis_id: str = ""
    path: Literal["amount_bridge", "grouping"] = "amount_bridge"
    overlap_with: list[str] = Field(default_factory=list)
    overlap_basis: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=6)
    note: str = ""
    # 调节额自身的精度方法必须声明；未声明时不据此判定闭合。
    rounding: Literal["unknown", "exact", "half_up"] = "unknown"


class VersionRecord(Contract):
    """企业披露版本链独立登记；版本变化只生成版本证据链，不生成正式跨报告差额。"""
    version_id: str
    document_id: str
    # 版本链只在同一报告类型内成立；AR 与 ESG 不是彼此的版本。
    report_type: str = ""
    version_role: Literal["original", "correction", "unknown"] = "unknown"
    disclosure_date: str = ""
    metric_period: str = ""
    report_period: str = ""
    label: str = ""
    value: str = ""
    unit: str = ""
    effective_relation: str = "登记公开版本"
    source_kind: Literal["official", "mirror", "media_quote"] = "official"
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=6)


class VersionChange(Contract):
    """受控版本对比结果；字段命名与正式差额隔离，禁止相加成跨报告结论。"""
    from_version_id: str
    to_version_id: str
    label: str
    display_change: str
    absolute_change: str
    unit: str
    only_version_evidence: bool = True
    note: str = "版本金额变化只说明财务披露版本发生变化，不能计为已解释的跨报告差异"


class RelationshipCheck(Contract):
    check_id: str
    rule_id: Literal["EQ-001", "RD-001", "ENV-001", "INT-001", "OCC-001", "NAR-001"]
    rule_version: str = "2026-10-17.1"
    title: str
    topic: str = ""
    operator: Literal["equal", "sum", "ratio", "occurrences", "narrative"]
    members: list[RelationshipMember] = Field(default_factory=list, max_length=100)
    conditions: list[ComparisonCondition] = Field(default_factory=list, max_length=12)
    relationship_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=12)
    # 关系是怎么被认定的：原文明示 / 标签与量纲自动配对 / 同报告多位置。
    # 自动配对只产生候选，成员行不能充当"关系本身有原文依据"。
    relationship_basis: Literal["text_statement", "auto_label_match", "multi_location"] = "text_statement"
    ratio_scale: str = "1"
    explanation: str = ""
    explanation_evidence: list[EvidenceRef] = Field(default_factory=list)
    criteria_status: str = "unknown"
    calculation_status: str = "not_executable"
    # 成员是否来自不同报告：同一文档内的多位置一致不构成跨报告衔接。
    cross_document: bool = False
    review_status: str = "unreviewed"
    calculation: dict = Field(default_factory=dict)
    # 假设试算独立存放，不占用正式差额字段，也不进入已衔接统计。
    hypothetical: dict | None = None
    adjustments: list[AdjustmentRecord] = Field(default_factory=list, max_length=20)
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
    # 报告所属期间与指标所属期间分别记录；比较期间取 period，口径来源写入 versions。
    report_period: str = ""
    metric_period: str = ""
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
    extraction_exclusions: list[ExtractionExclusion] = Field(default_factory=list)
    candidate_rejections: list[dict] = Field(default_factory=list)
    version_records: list[VersionRecord] = Field(default_factory=list)
    version_changes: list[VersionChange] = Field(default_factory=list)
    overview: dict = Field(default_factory=dict)
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
