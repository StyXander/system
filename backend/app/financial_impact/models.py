"""财务穿透层的公共数据模型。

设计约束（对应任务书第二、三、八、九条）：
1. 事项阶段与金额性质必须分开记录：计划投资不是当期支出，期末余额不是投入。
2. 每个财务数值必须带 document_id / file_sha256 / pdf_page / bbox / 行列标题 / 原始文本 / 语义。
3. 关联等级只由可核验的九项条件决定，模型文本不能写入等级。
4. 缺失证据只能记 unresolved，不得反推为企业未披露或披露不实。
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class Stage(str, Enum):
    """经济活动实施阶段。状态是分析框架，不代表所有事项都会依次经历。"""

    STRATEGY = "strategy"                 # 战略目标/原则性承诺
    PLANNED = "planned"                   # 计划投资、拟建
    CONTRACTED = "contracted"             # 已签约
    EXECUTING = "executing"               # 在建/实施中
    COMPLETED = "completed"               # 已建成/投产
    SETTLED = "settled"                   # 已结算/已支付
    UNKNOWN = "unknown"
    RECOGNIZED = "recognized"


class AmountNature(str, Enum):
    """金额性质。与阶段独立，避免把预算数或余额当成当期投入。"""

    BUDGET = "budget"                     # 预算数
    PLANNED_INVESTMENT = "planned_investment"
    ACTUAL_PAYMENT = "actual_payment"     # 实际现金支付
    INVESTMENT_INCURRED = "investment_incurred"  # 已发生投入，但不必然是现金支付
    PERIOD_INCREASE = "period_increase"   # 本期增加
    PERIOD_DECREASE = "period_decrease"
    TRANSFER_OUT = "transfer_out"         # 转固/转出
    CLOSING_BALANCE = "closing_balance"   # 期末余额
    OPENING_BALANCE = "opening_balance"
    EXPENSE = "expense"                   # 当期费用
    REVENUE = "revenue"
    PERFORMANCE = "performance"           # 实物绩效（节能量等）
    NONE = "none"


class EvidenceRef(BaseModel):
    document_id: str
    file_sha256: str = ""
    report_type: str = ""
    pdf_page: int = 0
    bbox: list[float] = Field(default_factory=list)
    quote: str = ""
    row_header: str = ""
    column_header: str = ""
    verified: bool = False
    kind: Literal['source_quote', 'table_structure'] = 'source_quote'


class Amount(BaseModel):
    raw: str = ""
    value: str = ""
    unit: str = ""
    dimension: str = ""
    normalized: str = ""
    nature: AmountNature = AmountNature.NONE
    qualifier: str = "exact"
    period: str = ""

    @property
    def as_decimal(self) -> Decimal | None:
        try:
            return Decimal(self.normalized or self.value)
        except Exception:
            return None


class SustainabilityEvent(BaseModel):
    """一项可识别的可持续经济活动。"""

    event_id: str
    company: str
    company_id: str = ""
    subject: str = ""                                  # 企业内具体主体/基地
    project_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    activity_type: str = ""
    period: str = ""
    stage: Stage = Stage.UNKNOWN
    amounts: list[Amount] = Field(default_factory=list)
    amount_nature: AmountNature = AmountNature.NONE
    performance: list[Amount] = Field(default_factory=list)
    scope: str = "未明示"
    currency: str = "未明示"
    document_id: str
    file_sha256: str = ""
    report_type: str = ""
    pdf_page: int = 0
    bbox: list[float] = Field(default_factory=list)
    quote: str = ""
    missing_fields: list[str] = Field(default_factory=list)
    extraction_method: Literal["rule", "model", "rule+model"] = "rule"
    page_verified: bool = False


class FinancialItem(BaseModel):
    """年报附注/报表中的结构化财务项目。"""

    item_id: str
    company: str
    company_id: str = ""
    table_title: str = ""                 # 上级标题，如“在建工程”
    row_header: str = ""
    column_header: str = ""
    value_semantics: AmountNature = AmountNature.NONE
    raw_value: str = ""
    value: str = ""
    unit: str = ""
    normalized: str = ""
    period: str = ""
    scope: str = "未明示"                  # 合并/母公司
    currency: str = "未明示"
    document_id: str
    file_sha256: str = ""
    pdf_page: int = 0
    bbox: list[float] = Field(default_factory=list)
    quote: str = ""
    page_verified: bool = False


class AccountingRule(BaseModel):
    rule_id: str
    scene: str                            # 业务场景
    applies_when: list[str] = Field(default_factory=list)
    accounts: list[str] = Field(default_factory=list)
    recognition: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    counter_examples: list[str] = Field(default_factory=list)
    basis: list[dict] = Field(default_factory=list)   # {title, issuer, version, locator}
    verification: Literal["verified", "pending_human_review"] = "pending_human_review"
    activity_types: list[str] = Field(default_factory=list)
    cash_flow_class: str = ''


class AccountingTreatment(BaseModel):
    treatment_id: str
    rule_id: str
    scene: str
    accounts: list[str] = Field(default_factory=list)
    conditions: list[dict] = Field(default_factory=list)   # 待验证前提
    required_evidence: list[str] = Field(default_factory=list)
    basis: list[dict] = Field(default_factory=list)
    cash_flow_class: str = ""
    status: Literal["hypothesis", "supported", "refuted", "not_applicable"] = "hypothesis"


class RelationGrade(str, Enum):
    A = "A"          # 明确财务关联
    B = "B"          # 有证据的间接关联
    C = "C"          # 合理关联假设
    D = "D"          # 公开证据不足
    INCOMPATIBLE = "incompatible"
    CONTRADICTED = "contradicted"
    NOT_APPLICABLE = "not_applicable"


class ConditionCheck(BaseModel):
    """九项独立条件之一；true/false/unknown 三态，unknown 不得当作 true。"""

    key: str
    label: str
    status: Literal["true", "false", "unknown"] = "unknown"
    reason: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ImpactRelation(BaseModel):
    relation_id: str
    event_id: str
    financial_item_id: str | None = None
    treatment_id: str | None = None
    relation_type: str = "unresolved"
    grade: RelationGrade = RelationGrade.D
    conditions: list[ConditionCheck] = Field(default_factory=list)
    supporting: list[EvidenceRef] = Field(default_factory=list)
    counter: list[EvidenceRef] = Field(default_factory=list)
    numeric_reconciliation: dict = Field(default_factory=dict)
    explanation: str = ""
    history: list[dict] = Field(default_factory=list)


class ImpactAnalysis(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str = ''
    buckets: dict[str,int] = Field(default_factory=dict)
    time_states: list[dict] = Field(default_factory=list)
    current: list[dict] = Field(default_factory=list)
    expected: list[dict] = Field(default_factory=list)
    note: str = ""


class FinancialImpactResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str = "financial_impact_v1"
    company: str = ""
    period: str = ""
    events: list[SustainabilityEvent] = Field(default_factory=list)
    items: list[FinancialItem] = Field(default_factory=list)
    treatments: list[AccountingTreatment] = Field(default_factory=list)
    relations: list[ImpactRelation] = Field(default_factory=list)
    graph: dict = Field(default_factory=dict)
    analysis: ImpactAnalysis = Field(default_factory=ImpactAnalysis)
    stats: dict = Field(default_factory=dict)
    retrieval: dict = Field(default_factory=dict)
    agents: dict = Field(default_factory=dict)
    note: str = (
        "可持续事项与财务项目的关系等级只描述证据支持程度，不是模型正确概率；"
        "找不到对应项目不等于企业披露不实。"
    )
