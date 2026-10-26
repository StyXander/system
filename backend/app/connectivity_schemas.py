"""跨报告关联核对合同：原文、关系、计算与人工处理分别记录。

公开报告只能支持其实际披露内容，关系成立不表示企业整体真实可靠。
金额使用十进制字符串，避免网页与后端浮点结果不一致。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .connectivity_matter_schemas import (InvestigationBudget, MatterType, ReportSet, MatterEvidence,
    SustainabilityMatter, MatterEvent, MatterCommitment, FinancialImpactPath, MatterRelation,
    CompetingExplanation, MatterAssessment)

NOTICE = "AI生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，不构成审计结论、鉴证结论或鉴证意见。"
# 历史业务声明保持原文不变；导出与接口按 task_kind 分派，不互相冒充。
LEGACY_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
NOTICE_BY_TASK_KIND = {"connectivity": NOTICE, "legacy_audit": LEGACY_NOTICE}
SCHEMA_VERSION = "connectivity_v5"
INTELLIGENCE_VERSION = "hybrid_v4_counterevidence_grounded"
# 财务穿透与反证层的合同版本；旧结果缺少这些字段时按空值读取，不改变既有结论。
FINANCIAL_VERSION = "financial_bridge_v1"

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
    # 约数和上下界保留原文性质，不能伪装为精确点值进入差额计算。
    value_qualifier: Literal["unspecified", "exact", "approximate", "lower_bound", "upper_bound"] = "unspecified"
    unit: str = ""
    unit_source: str = ""
    currency: str = ""
    currency_source_id: str = ""
    currency_source_quote: str = ""
    # 币种、单位、范围都要能说明“从哪一层继承”，不能把报告声明冒充指标级证据。
    currency_status: Literal["explicit", "table", "report_declaration", "assumed", "unknown"] = "unknown"
    unit_status: Literal["explicit", "table", "report_declaration", "unknown"] = "unknown"
    unit_source_quote: str = ""
    year: str = ""
    # 年度列解析失败时保持空值并标 unattributed，不得回退成报告期间。
    year_status: Literal["attributed", "unattributed"] = "unattributed"
    # 报告边界（合并/母公司/分部）与表内分组、指标统计范围分开登记。
    report_boundary: Literal["consolidated", "parent", "segment", "unknown"] = "unknown"
    report_boundary_source_id: str = ""
    report_boundary_source_quote: str = ""
    scope: str = ""
    table_scope: str = ""
    scope_source_id: str = ""
    scope_source_quote: str = ""
    scope_level: Literal["report", "table", "metric", "unknown"] = "unknown"
    # 显示小数位只是原文写法；舍入方法必须有原文声明，不能从位数推定。
    display_precision: int | None = None
    rounding_method: Literal["unknown", "exact", "half_up", "truncate"] = "unknown"
    # 公司自身披露、宏观/行业背景、同业信息分开；宏观数字不得进入企业异常候选。
    content_class: Literal["company", "macro", "industry", "peer", "background", "unknown"] = "unknown"
    metric_id: str = ""
    metric_identity: dict = Field(default_factory=dict)
    # 表格结构身份用于表内合计/分项自证及跨表桥接。
    table_id: str = ""
    row_index: int | None = None
    column_index: int | None = None
    row_role: Literal["total", "component", "detail", "header", "unknown"] = "unknown"
    column_role: Literal["total", "component", "period", "unit", "label", "unknown"] = "unknown"
    row_parent_label: str = ""
    definition: str = ""
    row_header: str = ""
    # 所选列与整表头分存，避免把其他年度误当作本值所属列。
    full_table_header: str = ""
    year_binding: Literal["cell_header", "coordinate", "inline", "unattributed"] = "unattributed"
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
    evidence_kind: Literal["unspecified", "explicit", "table_structure", "derived", "ai_semantic", "report_level"] = "unspecified"


class RelationshipMember(Contract):
    occurrence_id: str
    role: Literal["left", "right", "total", "component", "numerator", "denominator", "reported_ratio", "occurrence"]


class CalculationPlan(Contract):
    """模型选择既有模板；变量数值始终由程序从原始披露取回。"""
    plan_id: str
    operator: Literal["equal", "sum", "ratio", "occurrences", "narrative"]
    members: list[RelationshipMember]
    reason: str = ""
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    status: Literal["proposed", "trial", "formal", "rejected"] = "proposed"
    producer_role: str = ""


class AdjustmentProposal(Contract):
    """只提交原始数值的ID，不允许模型填造调节金额。"""
    occurrence_id: str
    label: str = Field(min_length=2, max_length=160)
    sign: Literal["+", "-"]
    reason: str = Field(min_length=2, max_length=600)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=6)
    assumptions: list[str] = Field(default_factory=list, max_length=8)


class ExplanationHypothesis(Contract):
    """竞争解释保存支持、反证和下一步检索，不用未知条件代替业务分析。"""
    hypothesis_id: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=6, max_length=700)
    status: Literal["supported", "plausible", "open", "refuted"] = "open"
    reasons: list[str] = Field(default_factory=list, max_length=4)
    supporting_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=6)
    counter_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=6)
    assumptions: list[str] = Field(default_factory=list, max_length=5)
    retrieval_queries: list[str] = Field(default_factory=list, max_length=3)


class AIAnalysis(Contract):
    """AI意见与正式计算、人工处理分开保存，历史运行默认没有该内容。"""
    check_id: str
    verdict: Literal["lean_consistent", "potential_conflict", "plausible_explanation", "insufficient_basis", "not_comparable"]
    summary: str = Field(min_length=6, max_length=1000)
    reasons: list[str] = Field(min_length=1, max_length=8)
    supporting_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=12)
    counter_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    alternative_explanations: list[str] = Field(default_factory=list, max_length=6)
    next_actions: list[str] = Field(default_factory=list, max_length=8)
    analysis_quality: Literal["high", "medium", "low"] = "low"
    quality_reasons: list[str] = Field(default_factory=list, max_length=6)
    calculation_plan_ids: list[str] = Field(default_factory=list, max_length=8)
    producer_role: str = ""
    prompt_version: str = ""
    input_fingerprint: str = ""
    status: Literal["current", "needs_refresh"] = "current"
    review_status: Literal["unreviewed", "accepted", "rejected"] = "unreviewed"
    hypotheses: list[ExplanationHypothesis] = Field(default_factory=list, max_length=3)
    priority: Literal["high", "medium", "low"] | None = None
    priority_reason: str = Field(default="", max_length=500)
    producer_model: str = ""
    revision_note: str = Field(default="", max_length=500)
    inherited_from_run_id: str = ""


class NarrativeClaim(Contract):
    """模型解析文字主张；程序核对绑定数据的变化方向。"""
    indicator: str = Field(min_length=2, max_length=120)
    direction: Literal["increase", "decrease", "stable"]
    current_id: str
    previous_id: str
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=4)
    basis_description: str = Field(min_length=2, max_length=400)


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
    # 关系是怎么被认定的：原文明示 / 标签与量纲自动配对 / 同报告多位置 / 表内结构 /
    # 受控指标身份字典映射。自动配对、多位置与表内结构只产生候选，成员行不能
    # 充当"关系本身有原文依据"；字典映射属于可复核的受控依据。
    relationship_basis: Literal["text_statement", "auto_label_match", "multi_location", "table_structure", "metric_identity"] = "text_statement"
    ratio_scale: str = "1"
    explanation: str = ""
    explanation_evidence: list[EvidenceRef] = Field(default_factory=list)
    criteria_status: str = "unknown"
    calculation_status: str = "not_executable"
    # 结论级别：L0 数值试算、L1 有限可比、L2 指标级有依据可比；均不等于鉴证意见。
    basis_level: Literal["not_assessed", "L0", "L1", "L2"] = "not_assessed"
    conclusion_level: Literal["not_assessed", "formal_consistent", "assumption_compatible",
                             "limited_support", "unexplained_difference", "insufficient_basis",
                             "not_applicable"] = "not_assessed"
    # 数值、口径、解释分别记录，解释文案不得改写数学差额。
    comparability: dict = Field(default_factory=dict)
    # 表内合计/分项与跨表桥接的结构证据；字段结构见 AI1 交接文档。
    table_structure: dict = Field(default_factory=dict)
    # 成员是否来自不同报告：同一文档内的多位置一致不构成跨报告衔接。
    cross_document: bool = False
    review_status: str = "unreviewed"
    calculation: dict = Field(default_factory=dict)
    # 假设试算独立存放，不占用正式差额字段，也不进入已衔接统计。
    hypothetical: dict | None = None
    adjustments: list[AdjustmentRecord] = Field(default_factory=list, max_length=20)
    unresolved: list[str] = Field(default_factory=list)
    related_checks: list[str] = Field(default_factory=list)
    mapping_type: Literal["same_metric", "component_of", "ratio_of", "overlap", "related_only", "different_metric", "uncertain"] = "uncertain"
    mapping_reason: str = ""
    calculation_plan: CalculationPlan | None = None
    # 模型调节建议先进入场景试算，不自动写入正式adjustments。
    adjustment_proposals: list[AdjustmentProposal] = Field(default_factory=list, max_length=10)
    scenario_adjustment: dict | None = None
    narrative_claim: NarrativeClaim | None = None
    narrative_test: dict | None = None
    hypotheses: list[ExplanationHypothesis] = Field(default_factory=list, max_length=3)
    # 反事实闭合推演：证据需求、上限预测、单项补证效果与归因候选。
    # 只读派生数据，不参与任何正式结论；结构见 connectivity_closure.py。
    closure: dict = Field(default_factory=dict)


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
    mapping_type: Literal["same_metric", "component_of", "ratio_of", "overlap", "related_only", "different_metric", "uncertain"] = "uncertain"
    mapping_reason: str = Field(default="", max_length=600)
    calculation_reason: str = Field(default="", max_length=600)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    adjustment_proposals: list[AdjustmentProposal] = Field(default_factory=list, max_length=10)
    narrative_claim: NarrativeClaim | None = None
    hypotheses: list[ExplanationHypothesis] = Field(default_factory=list, max_length=3)


class SearchDirective(Contract):
    """模型申请的本报告内检索；不接受网址、路径或可执行代码。"""
    check_id: str = Field(min_length=1, max_length=100)
    metric: str = Field(min_length=2, max_length=50)
    terms: list[str] = Field(min_length=1, max_length=5)
    kind: Literal["support", "counter"] = "counter"
    reason: str = Field(min_length=4, max_length=200)


class AgentProposals(Contract):
    search_requests: list[SearchDirective] = Field(default_factory=list, max_length=4)
    checks: list[RelationshipProposal] = Field(max_length=8)
    notes: list[str] = Field(default_factory=list, max_length=6)


class SingleAgentProposals(Contract):
    search_requests: list[SearchDirective] = Field(default_factory=list, max_length=4)
    """单模型可一次提出两轮角色合计的八项关系，不人为压低输出容量。"""
    checks: list[RelationshipProposal] = Field(max_length=8)
    notes: list[str] = Field(default_factory=list, max_length=6)
    analyses: list[AIAnalysis] = Field(default_factory=list, max_length=30)


class FinalFinding(Contract):
    check_id: str
    question: str
    requested_material: str
    purpose: str
    evidence: list[EvidenceRef] = Field(max_length=12)


class FinalSummaries(Contract):
    search_requests: list[SearchDirective] = Field(default_factory=list, max_length=4)
    findings: list[FinalFinding] = Field(default_factory=list, max_length=30)
    analyses: list[AIAnalysis] = Field(default_factory=list, max_length=30)


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
    # AI 意见与正式计算分开存放：意见不改变 criteria/calculation 状态，也不进入已衔接统计。
    ai_opinions: list[dict] = Field(default_factory=list)
    findings: list[FindingAndRequest] = Field(default_factory=list)
    professional_notes: list[ProfessionalRiskNote] = Field(default_factory=list)
    source_lineage: list[SourceLineage] = Field(default_factory=list)
    reviews: list[ReviewEvent] = Field(default_factory=list)
    agent_steps: list[dict] = Field(default_factory=list)
    provider_calls: list[dict] = Field(default_factory=list)
    duration_ms: int = 0
    versions: dict = Field(default_factory=dict)
    ai_analyses: list[AIAnalysis] = Field(default_factory=list)
    # 新运行的程序提示不计入模型意见；旧ai_opinions仅供历史兼容读取。
    program_hints: list[dict] = Field(default_factory=list)
    analysis_history: list[dict] = Field(default_factory=list)
    prior_provider_calls: list[dict] = Field(default_factory=list)
    industry_context: dict = Field(default_factory=dict)
    intelligence_trace: list[dict] = Field(default_factory=list)
    # 显式证据账本字段与原始trace并存，旧记录缺失时保持空列表。
    claim_ledger: list[dict] = Field(default_factory=list)
    rule_basis: list[dict] = Field(default_factory=list)
    next_evidence: list[dict] = Field(default_factory=list)
    # 创新一：可持续主张→财务项目的受控关系与图谱；创新二：证据驱动状态机；
    # 创新三：预算约束补证计划与情景模拟。全部为只读派生数据，不改变正式结论。
    financial_claims: list[dict] = Field(default_factory=list)
    financial_nodes: list[dict] = Field(default_factory=list)
    financial_edges: list[dict] = Field(default_factory=list)
    impact_graph: dict = Field(default_factory=dict)
    revision_loop: dict = Field(default_factory=dict)
    evidence_plan: dict = Field(default_factory=dict)
    financial_scenario: dict = Field(default_factory=dict)
    investigation: dict = Field(default_factory=dict)
    comparison_summary: dict = Field(default_factory=dict)
    matter_schema_version: str = ""
    report_set: ReportSet | None = None
    matter_evidence: list[MatterEvidence] = Field(default_factory=list)
    matters: list[SustainabilityMatter] = Field(default_factory=list)
    matter_events: list[MatterEvent] = Field(default_factory=list)
    matter_commitments: list[MatterCommitment] = Field(default_factory=list)
    matter_paths: list[FinancialImpactPath] = Field(default_factory=list)
    matter_relations: list[MatterRelation] = Field(default_factory=list)
    matter_explanations: list[CompetingExplanation] = Field(default_factory=list)
    matter_assessments: list[MatterAssessment] = Field(default_factory=list)
    matter_tasks: list[dict] = Field(default_factory=list)
    matter_tool_receipts: list[dict] = Field(default_factory=list)
    matter_coverage: list[dict] = Field(default_factory=list)
    matter_rejections: list[dict] = Field(default_factory=list)
    matter_revisions: list[dict] = Field(default_factory=list)
    matter_graph: dict = Field(default_factory=dict)
    matter_overview: dict = Field(default_factory=dict)
    ai_generated_content_notice: str = NOTICE


class RunRequest(Contract):
    pair_id: str | None = Field(default=None, min_length=2, max_length=100)
    report_set_id: str | None = Field(default=None, min_length=2, max_length=100)
    topics: list[Literal["research", "environment", "intensity"]] = Field(default_factory=lambda: ["research", "environment", "intensity"], min_length=1, max_length=3)
    mode: Literal["calculation_only", "three_agents", "single_model", "adaptive_agents", "five_agents"] = "three_agents"
    analysis_scope: Literal["legacy_checks", "matter_connectivity"] = "legacy_checks"
    as_of_date: date | None = None
    matter_types: list[MatterType] = Field(default_factory=lambda: ["climate_risk", "transition_project", "commitment", "resource_efficiency", "other"], min_length=1, max_length=5)
    selected_matter_ids: list[str] = Field(default_factory=list, max_length=30)
    ablation: Literal["none","no_temporal","no_counterevidence"] = "none"
    budget: InvestigationBudget = Field(default_factory=InvestigationBudget)
    retry_of_task_id: str | None = None

    @model_validator(mode="after")
    def source_selection(self):
        if bool(self.pair_id) == bool(self.report_set_id):
            raise ValueError("请选择一个报告对或一个多年资料集合")
        if self.report_set_id or self.mode == "five_agents":
            self.analysis_scope = "matter_connectivity"
        if self.ablation!="none" and self.mode!="five_agents":raise ValueError("角色消融仅适用于五Agent实验")
        if self.analysis_scope == "matter_connectivity" and self.mode == "adaptive_agents":
            raise ValueError("事项调查请选择五Agent、三Agent对照或单模型对照")
        return self


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
    action: Literal["reading_confirmation", "personal_observation", "ai_accept", "ai_reject"]
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
