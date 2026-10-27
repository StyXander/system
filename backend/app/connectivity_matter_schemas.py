"""事项调查合同；来源、执行、专业判断与人工采用使用独立状态。

事项合同独立版本与旧数值合同并存，历史读取不改写原状态。
证据原件身份、模型建议、程序复算与人工采用分别登记。
报告年度用于披露定位，事件发生期间未知时保持空值。
所有角色建议先经过结构与引用检查，不能直接写入共享结果。
金额使用原文定位和十进制复算，文字意见不能自行放行。
预算限制由服务端执行，不接受模型自行增加调用权限。
"""
from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

MATTER_VERSION = "matter_connectivity_v1"
MatterType = Literal["climate_risk", "transition_project", "commitment", "resource_efficiency", "other"]
Support = Literal["pending", "limited", "supported", "conflicting", "not_comparable", "invalid"]
ROLE_NAMES = {"A1": "事项识别与建档", "A2": "财务影响调查", "A3": "跨期承诺与后果追踪",
              "A4": "边界解释与反证调查", "A5": "综合复核与补证决策"}


class MatterContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvestigationBudget(MatterContract):
    """服务端共享调查预算。
    角色重试、工具反馈和定向补查均受同一调用上限约束。
    并行上限约束同时在途请求，不代表五个角色全部同时运行。
    深查数量以外的事项仍显示在待调查队列中。
    """
    max_provider_calls: int = Field(default=20, ge=1, le=40)
    max_parallel_calls: int = Field(default=2, ge=1, le=2)
    max_matters: int = Field(default=1, ge=1, le=10)
    max_role_rounds: int = Field(default=2, ge=1, le=6)


class ReportSetRequest(MatterContract):
    document_ids: list[str] = Field(min_length=1, max_length=30)
    as_of_date: date = Field(default_factory=date.today)


class ReportSet(MatterContract):
    """不可变的多年资料选择。
    文件指纹与观察时点共同构成集合身份。
    覆盖缺口只描述当前取得的资料，不评价企业披露完整性。
    同一原件可跨集合复用，报告年度与指标年度不混用。
    """
    report_set_id: str
    company_id: str
    company: str
    document_ids: list[str]
    document_fingerprints: dict[str, str]
    periods: list[str]
    as_of_date: date
    coverage_gaps: list[str] = Field(default_factory=list)
    schema_version: str = MATTER_VERSION


class MatterEvidence(MatterContract):
    """原件中的可定位叙述片段。
    核验状态只确认字节与摘录来源，不确认语义推理正确。
    扫描识别方式单列，不能将识别结果冒充原生文字层。
    来源变更后标记失效，保留旧片段用于历史复查。
    """
    evidence_id: str
    document_id: str
    source_sha256: str
    company_id: str
    report_type: Literal["AR", "ESG"]
    report_period: str
    disclosure_date: str = ""
    pdf_page: int = Field(ge=1)
    printed_page: str = ""
    quote: str = Field(min_length=1, max_length=1800)
    context: str = Field(default="", max_length=3500)
    adjacent_evidence_ids: list[str] = Field(default_factory=list)
    section: str = ""
    bbox: list[float] = Field(default_factory=list)
    extraction_method: Literal["text", "ocr"] = "text"
    source_verified: bool = False
    invalid_reason: str = ""


class MatterEvent(MatterContract):
    """披露支持的事件候选。
    报告期间、披露日期和事件发生期间使用独立字段。
    程序推定和模型解释保留来源类型，不自动等同事实认定。
    事件标签可辅助时序阅读，不能代替原文引用。
    """
    event_id: str
    matter_id: str
    kind: Literal["risk", "promise", "revision", "action", "investment", "commissioning", "performance", "financial", "termination"]
    label: str
    report_period: str
    occurred_period: str = ""
    disclosure_date: str = ""
    evidence_ids: list[str]
    origin: Literal["program_candidate", "model_interpretation", "human_review"] = "program_candidate"
    evidence_status: Support = "pending"


class MatterCommitment(MatterContract):
    """目标及其后续修订的登记记录。
    原目标不被新目标覆盖，修订关系通过被替代编号保留。
    目标期限未到不生成失败判断，绩效口径仍须核对。
    承诺进展与财务阶段分别评价，投资不能证明目标已达成。
    """
    commitment_id: str
    matter_id: str
    label: str
    evidence_ids: list[str]
    proposed_period: str
    baseline_year: str = ""
    target_year: str = ""
    metric_definition: str = ""
    scope: str = ""
    supersedes: str = ""
    evidence_status: Support = "pending"
    status: Literal["not_due", "progress_unknown", "revised", "supported_as_reported", "needs_review"] = "needs_review"


class SustainabilityMatter(MatterContract):
    """以项目、风险或承诺为核心的统一档案。
    单处披露首先进入身份待确认候选，不强制跨年归并。
    人工确认身份不代表对应财务金额或专业结论已经成立。
    关注变化只影响调查顺序，不等于财务重要性或违规认定。
    """
    matter_id: str
    company_id: str
    name: str
    matter_type: MatterType
    subject: str = ""
    location: str = ""
    aliases: list[str] = Field(default_factory=list)
    identity_status: Literal["candidate", "evidence_linked", "human_confirmed"] = "candidate"
    identity_basis: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    investigation_status: Literal["pending", "running", "completed", "partial", "skipped"] = "pending"
    lineage: list[str] = Field(default_factory=list)
    attention_signals: list[str] = Field(default_factory=list)
    attention_evidence_ids: list[str] = Field(default_factory=list)


class PathStep(MatterContract):
    """财务传导路径中的一段主张。
    原文陈述和机制假设必须分别标注，支持状态不能跨段传递。
    没有引用的步骤保持待证，即使前后步骤已有充分信息。
    模型不能把自身建议声明为程序复算或人工复核。
    """
    label: str = Field(min_length=1, max_length=200)
    explanation: str = Field(default="", max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)
    support: Support = "pending"
    origin: Literal["report_statement", "model_hypothesis", "program_calculation", "human_review"] = "model_hypothesis"


class FinancialImpactPath(MatterContract):
    """事项到具体财务项目的候选路径。
    支持程度由各段及反证约束，不用主题相近替代缺失环节。
    与路径相连的财务项目可能只是调查方向，不代表已确认金额。
    未决条件跟随路径保存并进入后续补证。
    """
    path_id: str
    matter_id: str
    financial_item: str
    steps: list[PathStep] = Field(min_length=1, max_length=8)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    support: Support = "pending"
    unresolved: list[str] = Field(default_factory=list)


class MatterRelation(MatterContract):
    """多对多的信息关联边。
    端点必须是当前账本中的事项、证据、事件或数值对象。
    关联类型、主张来源和证据支持分别记录，不合成单一可信度。
    同一证据或财务项目可以参与多条关系，金额不自动汇总。
    """
    edge_id: str
    matter_id: str
    source_id: str
    target_id: str
    relation_kind: Literal["same_matter", "component_of", "allocated_to", "affects_estimate", "potential_mechanism", "progress_of", "supersedes"]
    assertion_origin: Literal["report_statement", "model_hypothesis", "program_calculation", "human_review"] = "model_hypothesis"
    evidence_status: Support = "pending"
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str = ""


class CompetingExplanation(MatterContract):
    hypothesis_id: str
    matter_id: str
    explanation: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    discriminating_evidence: str
    status: Literal["hypothesis", "supported_as_reported", "challenged", "unresolved"] = "hypothesis"


class NextAction(MatterContract):
    question: str = Field(min_length=3, max_length=500)
    requested_material: str = Field(min_length=3, max_length=500)
    purpose: str = Field(min_length=3, max_length=500)
    target_role: Literal["A1", "A2", "A3", "A4", "A5"] = "A2"
    priority: Literal["high", "medium", "low"] = "medium"


class MatterAssessment(MatterContract):
    """综合复核意见，保留假设、分歧与下一步。
    关联支持、金额可比、承诺进展和财务阶段使用独立状态。
    模型意见不能自行设置人工采用结果或正式放行计算。
    意见绑定结果版本，来源变化后仍保留历史记录。
    """
    matter_id: str
    summary: str
    relation_support: Support = "pending"
    amount_comparability: Literal["not_assessed", "comparable", "not_comparable", "needs_evidence"] = "not_assessed"
    commitment_progress: str = "未取得足以评价承诺进展的证据"
    financial_stage: str = "待调查"
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    review_status: Literal["unreviewed", "accepted", "rejected"] = "unreviewed"
    result_revision: int = 1


class MatterToolCall(MatterContract):
    tool_name: Literal["search_matter_reports", "open_source_page", "lookup_ontology_rule", "locate_matter_numbers", "recompute_decimal"]
    arguments: dict = Field(default_factory=dict)
    reason: str = Field(min_length=3, max_length=500)


class MatterProposal(MatterContract):
    name: str = Field(min_length=2, max_length=160)
    matter_type: MatterType
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    identity_basis: str = Field(min_length=3, max_length=1000)
    subject: str = ""
    location: str = ""
    aliases: list[str] = Field(default_factory=list, max_length=15)


class AgentMatterResult(MatterContract):
    """角色建议不能直接覆盖共享结果，由主管线检查身份、引用和版本后合并。"""
    matter_id: str = ""
    input_revision: int = Field(default=1, ge=1)
    summary: str = Field(default="", max_length=2500)
    matters: list[MatterProposal] = Field(default_factory=list, max_length=12)
    paths: list[FinancialImpactPath] = Field(default_factory=list, max_length=6)
    events: list[MatterEvent] = Field(default_factory=list, max_length=20)
    commitments: list[MatterCommitment] = Field(default_factory=list, max_length=10)
    relations: list[MatterRelation] = Field(default_factory=list, max_length=20)
    explanations: list[CompetingExplanation] = Field(default_factory=list, max_length=6)
    assessment: MatterAssessment | None = None
    tool_requests: list[MatterToolCall] = Field(default_factory=list, max_length=4)
    stop_reason: str = Field(default="", max_length=300)


class RoleResult(MatterContract):
    """供应商只接触本角色合同，统一档案由程序侧组装。"""
    matter_id: str
    input_revision: int = Field(ge=1, strict=True)
    summary: str = Field(max_length=2500)
    tool_requests: list[MatterToolCall] = Field(default_factory=list, max_length=4)
    stop_reason: str = Field(default="", max_length=300)


class IdentificationResult(RoleResult):
    matters: list[MatterProposal] = Field(max_length=1)


class FinancialResult(RoleResult):
    paths: list[FinancialImpactPath] = Field(max_length=6)
    relations: list[MatterRelation] = Field(default_factory=list, max_length=20)


class TemporalResult(RoleResult):
    events: list[MatterEvent] = Field(max_length=20)
    commitments: list[MatterCommitment] = Field(max_length=10)
    relations: list[MatterRelation] = Field(default_factory=list, max_length=20)


class CounterResult(RoleResult):
    explanations: list[CompetingExplanation] = Field(max_length=6)
    relations: list[MatterRelation] = Field(default_factory=list, max_length=20)


class ReviewResult(RoleResult):
    assessment: MatterAssessment | None


ROLE_RESULT_SCHEMAS = {"A1": IdentificationResult, "A2": FinancialResult, "A3": TemporalResult,
                       "A4": CounterResult, "A5": ReviewResult}


def validate_role_result(role, value, *, combined=False):
    schema = AgentMatterResult if combined else ROLE_RESULT_SCHEMAS[role]
    if isinstance(value, AgentMatterResult):
        # 供应商适配器已经转成统一对象；不能将别的角色的非空内容带入。
        value = {k: v for k, v in value.model_dump().items() if k in schema.model_fields or v not in (None, [], "")}
    result = schema.model_validate(value)
    if not combined and not result.tool_requests:
        if role == "A1" and not result.matters:
            raise ValueError("matters: 最终建档必须明确所选事项身份，无法确认应保留候选并写依据")
        if role == "A5" and result.assessment is None:
            raise ValueError("assessment: 综合判断缺失；证据不足也必须保留缺口判断")
    return AgentMatterResult.model_validate(result.model_dump())


class MatterRevisionRequest(MatterContract):
    expected_revision: int = Field(ge=1)
    action_id: str = Field(min_length=8, max_length=100)
    action: Literal["merge", "split", "accept", "reject", "planning_adopt", "planning_defer", "planning_exclude"]
    planning_entry_ids: list[str] = Field(default_factory=list, max_length=50)
    actor: str = Field(default="个人演示用户", min_length=1, max_length=100)
    matter_ids: list[str] = Field(min_length=1, max_length=20)
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=3, max_length=2000)


class ReconciliationOperand(MatterContract):
    occurrence_id: str
    sign: Literal[1, -1] = 1


class MatterReconciliation(MatterContract):
    """受证据约束的条件调节申请。
    每个操作数使用本运行原文定位编号，不能直接提交任意数值。
    主体、期间、计量基础、项目归属和去重依据均需可回查引用。
    本版只产生条件试算，语义资格未经专业复核时不输出正式差额。
    """
    matter_id: str
    operands: list[ReconciliationOperand] = Field(min_length=2, max_length=30)
    identity_evidence_ids: list[str] = Field(min_length=1)
    measurement_basis: str
    deduplication_basis: str
    # 所有前提均需证据，不接受客户端声明 true。
    condition_evidence: dict[str, list[str]] = Field(default_factory=dict)


def matter_enabled():
    """关闭新事项运行入口，历史结果仍按原版本读取。
    回退开关只改变新建默认，不把五Agent请求暗换成三Agent。
    """
    import os
    return os.getenv("CONNECTIVITY_MATTER_ENABLED","true").lower() in {"true","1","yes","on"}
