"""任务8：财务关联分级、反证与确定性校验。

九项条件独立判定，任何一项为 unknown 都不能当作 true。
等级只描述证据支持程度，不是模型正确概率；找不到财务项目只记 D，不推断企业未披露。
"""
from __future__ import annotations

import re
from decimal import Decimal

from .models import (AmountNature, ConditionCheck, EvidenceRef, FinancialItem, ImpactRelation,
                     RelationGrade, SustainabilityEvent)
from .textutil import compact, project_key

VERIFIER_VERSION = "impact_verifier_v1.0"
GRADE_LABELS = {
    RelationGrade.A: "明确财务关联",
    RelationGrade.B: "有证据的间接关联",
    RelationGrade.C: "合理关联假设",
    RelationGrade.D: "公开证据不足",
    RelationGrade.INCOMPATIBLE: "明确不兼容",
    RelationGrade.CONTRADICTED: "存在反证冲突",
    RelationGrade.NOT_APPLICABLE: "不适用",
}
GRADE_MEANING = "等级只表示证据支持程度，不代表模型正确概率，也不构成审计结论。"

COMPATIBLE_NATURES: dict[AmountNature, set[AmountNature]] = {
    # 期末余额是时点余额，不能与已发生投入直接勾稽；只接受发生额口径。
    # “投入”可能包含资本化部分，不能与当期费用直接对应（研发投入≠研发费用）。
    AmountNature.INVESTMENT_INCURRED: {AmountNature.PERIOD_INCREASE},
    AmountNature.PLANNED_INVESTMENT: {AmountNature.BUDGET, AmountNature.PLANNED_INVESTMENT},
    AmountNature.BUDGET: {AmountNature.BUDGET, AmountNature.PLANNED_INVESTMENT},
    AmountNature.ACTUAL_PAYMENT: {AmountNature.ACTUAL_PAYMENT},
    AmountNature.EXPENSE: {AmountNature.EXPENSE},
    AmountNature.PERFORMANCE: {AmountNature.PERFORMANCE},
    AmountNature.NONE: set(),
}


def _evidence(item: FinancialItem | None, event: SustainabilityEvent | None, quote: str = "", page: int = 0) -> EvidenceRef:
    if item is not None:
        return EvidenceRef(document_id=item.document_id, file_sha256=item.file_sha256, report_type="AR",
                           pdf_page=item.pdf_page, bbox=item.bbox, quote=item.quote or quote,
                           row_header=item.row_header, column_header=item.column_header,
                           verified=item.page_verified, kind='table_structure')
    return EvidenceRef(document_id=getattr(event, "document_id", ""),
                       file_sha256=getattr(event, "file_sha256", ""),
                       report_type=getattr(event, "report_type", ""),
                       pdf_page=page or getattr(event, "pdf_page", 0),
                       bbox=getattr(event, "bbox", []), quote=quote, verified=True)


GENERIC_PROJECT = {"在建工程项目", "工程项目", "建设项目", "研发项目", "募投项目", "技术改造项目",
                   "环保项目", "工程项目名称", "项目名称", "污水处理项目", "节能改造项目", "绿色研发项目", "环境治理项目"}


def _identity(event: SustainabilityEvent, item: FinancialItem) -> tuple[str, str]:
    """身份判定三态：同名=true；明确指向另一个项目=false；只是没出现=unknown。

    缺项目名不能判成不兼容——那是证据不足，不是反证。
    """
    if event.company_id and item.company_id and event.company_id != item.company_id:
        return "false", "企业身份不一致，不能跨企业归属项目"
    if event.subject and event.subject not in item.quote + item.row_header:
        return "unknown", "具体主体或基地未在财务项目原文中证实"
    name = compact(event.project_name)
    if not name:
        return "unknown", "事项未披露可识别项目名，无法核对业务身份"
    if name in GENERIC_PROJECT and not event.subject:
        return 'unknown', '通用项目名缺少基地或具体主体，不能仅凭同名建立项目身份'
    # 项目身份以行标题为准；表标题与整行引文只在行标题缺失时兜底，避免表内其他项目串味。
    haystack = compact(item.row_header) or compact(" ".join([item.table_title, item.quote]))
    if project_key(haystack) in {project_key(event.project_name), *map(project_key, event.aliases)}:
        return "true", "财务项目的表标题或行标题出现同一项目名"
    if compact(item.row_header) in {"合计", "总计", "小计"} or "合计" in compact(item.row_header):
        return "unknown", "财务项目为汇总行，无法核对单一项目身份"
    others = {compact(found) for found in re.findall(r"[\u4e00-\u9fffA-Za-z0-9（）()·\-]{4,30}?(?:项目|工程)", haystack)}
    others = {item_name for item_name in others if item_name not in GENERIC_PROJECT and name not in item_name}
    if others:
        return "false", f"财务项目指向另一个项目：{'/'.join(sorted(others))[:40]}"
    return "unknown", "财务项目未出现该项目名，属于证据不足而非不兼容"


def _period(event: SustainabilityEvent, item: FinancialItem) -> tuple[str, str]:
    if not event.period or not item.period:
        return "unknown", "事项或财务项目期间未明示"
    if event.period == item.period:
        return "true", "事项与财务项目属于同一报告期间"
    return "false", f"期间不一致：事项{event.period}，财务项目{item.period}"


def _scope(event: SustainabilityEvent, item: FinancialItem) -> tuple[str, str]:
    if event.scope == "未明示" or item.scope == "未明示":
        return "unknown", "合并范围未在原文明确"
    if event.scope == item.scope:
        return "true", "合并范围一致"
    return "false", f"合并范围不一致：事项{event.scope}，财务项目{item.scope}"


def _comparability(event: SustainabilityEvent, item: FinancialItem) -> tuple[str, str]:
    """事项没有金额时是“无法比较”，不是“性质冲突”。"""
    if event.amount_nature == AmountNature.NONE or not [a for a in event.amounts if a.dimension == "money"]:
        return "unknown", "事项原文未披露金额，无法与财务项目比较"
    allowed = COMPATIBLE_NATURES.get(event.amount_nature, set())
    if item.value_semantics == AmountNature.NONE:
        return "unknown", "财务项目的金额语义未识别，不能比较"
    if item.value_semantics in allowed:
        return "true", f"金额性质可比：{event.amount_nature.value} 与 {item.value_semantics.value}"
    return "false", (f"金额性质不可比：事项为{event.amount_nature.value}，"
                     f"财务项目为{item.value_semantics.value}（预算/余额/发生额不得互相替代）")


def reconcile(event: SustainabilityEvent, item: FinancialItem, *, tolerance: Decimal = Decimal("0.005")) -> dict:
    """确定性金额勾稽。只在性质可比时执行，且给出容差与差额方向。"""
    for status, reason in (_identity(event, item), _period(event, item), _scope(event, item)):
        if status != "true":
            return {"status": "not_comparable", "reason": reason}
    if not event.page_verified or not item.page_verified:
        return {"status": "not_comparable", "reason": "两端原文未同时核实"}
    if event.currency == '未明示' or item.currency == '未明示' or event.currency != item.currency:
        return {"status": "not_comparable", "reason": "币种未知或不一致"}
    if item.unit == '未明示' or not item.normalized:
        return {"status": "not_comparable", "reason": "财务单位或归一化金额未核实"}
    money = [amount for amount in event.amounts if amount.dimension == "money" and amount.as_decimal is not None]
    if len(money) != 1 or money[0].qualifier != 'exact':
        return {"status": "not_comparable", "reason": "金额有多个、约数或上下界，不能选最大金额直接勾稽"}
    if not money or item.value_semantics == AmountNature.NONE:
        return {"status": "not_comparable", "reason": "缺少可比的金额或语义"}
    if item.value_semantics not in COMPATIBLE_NATURES.get(event.amount_nature, set()):
        return {"status": "not_comparable",
                "reason": f"金额性质不可比：事项为{event.amount_nature.value}，财务项目为{item.value_semantics.value}"}
    try:
        item_value = Decimal(item.normalized)
    except Exception:
        return {"status": "not_comparable", "reason": "财务金额不可解析"}
    if not item_value.is_finite() or not money[0].as_decimal.is_finite():
        return {"status": "not_comparable", "reason": "非有限金额不允许计算"}
    if item_value == 0:
        return {"status": "not_comparable", "reason": "财务项目金额为零，不具有勾稽意义"}
    event_value = max((amount.as_decimal for amount in money if amount.as_decimal), default=None)
    if event_value is None:
        return {"status": "not_comparable", "reason": "事项金额无法解析"}
    difference = event_value - item_value
    ratio = abs(difference) / abs(item_value)
    within = ratio <= tolerance
    return {"status": "reconciled" if within else "difference", "event_value": str(event_value),
            "item_value": str(item_value), "difference": str(difference),
            "ratio": str(round(ratio, 6)), "tolerance": str(tolerance),
            "note": "仅在同一期间、同一范围、同一金额性质下执行；差异不等于错报。"}


def _evidence_check(support: list[dict], item: FinancialItem) -> tuple[str, str]:
    usable = [entry for entry in support if entry.get("filter_ok") and entry.get("quote") and entry.get('verified')
              and entry.get('document_id') == item.document_id and entry.get('pdf_page') == item.pdf_page
              and entry.get('file_sha256') == item.file_sha256 and item.page_verified]
    if not usable:
        return "unknown", "没有通过主体/期间过滤的候选证据"
    return "true", f"存在{len(usable)}条通过过滤的候选证据，仍需逐条核对原文"


def build_relation(event: SustainabilityEvent, item: FinancialItem | None, treatment,
                   *, support: list[dict] | None = None, counter: list[dict] | None = None,
                   previous: ImpactRelation | None = None) -> ImpactRelation:
    support = support or []
    counter = [entry for entry in (counter or []) if entry.get('verified') and entry.get('document_id')]
    checks: list[ConditionCheck] = []
    grade = RelationGrade.D
    explanation_parts: list[str] = []
    reconciliation: dict = {"status": "not_comparable", "reason": "未定位到财务项目"}

    if item is not None:
        identity_status, identity_reason = _identity(event, item)
        period_status, period_reason = _period(event, item)
        cross_period = (identity_status == 'true' and period_status == 'false' and event.page_verified
            and item.page_verified and event.period in event.quote + item.quote and item.period in event.quote + item.quote
            and bool(re.search(r'跨年|跨期|持续建设|多年', event.quote + item.quote)))
        if cross_period:
            period_status, period_reason = 'unknown', '原文支持同项目跨期延续，只建立跨期业务关系，禁止同期金额勾稽'
        scope_status, scope_reason = _scope(event, item)
        comparable_status, comparable_reason = _comparability(event, item)
        evidence_status, evidence_reason = _evidence_check(support, item)
        counter_status = "false" if counter else "true"
        accounting_evidence = getattr(treatment, 'conditions', [])
        grounded_conditions = bool(accounting_evidence) and all(
            condition.get('status') == 'true' and condition.get('evidence') and
            all(ref.get('verified') for ref in condition['evidence']) for condition in accounting_evidence)
        accounting_status = "true" if getattr(treatment, "status", "hypothesis") == "supported" and grounded_conditions else (
            "false" if getattr(treatment, "status", "") == "refuted" else "unknown")
        reconciliation = reconcile(event, item) if comparable_status != "false" else {
            "status": "not_comparable", "reason": comparable_reason}
        if reconciliation.get("status") == "not_comparable" and reconciliation.get("reason") == "缺少可比的金额或语义":
            reconciliation["reason"] = comparable_reason
        reconciliation_status = ("true" if reconciliation["status"] == "reconciled"
                                 else "false" if reconciliation["status"] == "difference" else "unknown")

        checks = [
            ConditionCheck(key="identity", label="业务身份一致", status=identity_status, reason=identity_reason,
                           evidence=[_evidence(item, event)]),
            ConditionCheck(key="period", label="事项期间与财务期间一致", status=period_status, reason=period_reason),
            ConditionCheck(key="scope", label="合并范围一致", status=scope_status, reason=scope_reason),
            ConditionCheck(key="accounting_conditions", label="会计处理前提满足", status=accounting_status,
                           reason="路径仍为假设" if accounting_status == "unknown" else "路径状态已裁决"),
            ConditionCheck(key="comparability", label="金额性质可比", status=comparable_status, reason=comparable_reason),
            ConditionCheck(key="cross_reference", label="存在项目级交叉索引", status=identity_status,
                           reason=identity_reason),
            ConditionCheck(key="evidence", label="证据充分", status=evidence_status, reason=evidence_reason,
                           evidence=[_evidence(item, event)]),
            ConditionCheck(key="no_counter_evidence", label="无反向证据", status=counter_status,
                           reason="存在反向证据" if counter else "未检索到反向证据",
                           evidence=[_candidate_ref(entry) for entry in counter[:3]]),
            ConditionCheck(key="reconciliation", label="可执行确定性金额勾稽", status=reconciliation_status,
                           reason="{status}: {reason}".format(**reconciliation) if reconciliation.get("reason")
                           else f"勾稽结果：{reconciliation['status']}"),
        ]
        statuses = {check.key: check.status for check in checks}
        if statuses["identity"] == "false" or statuses["period"] == "false" or statuses["scope"] == "false":
            grade = RelationGrade.INCOMPATIBLE
            explanation_parts.append("存在明确不兼容项：身份、期间或合并范围不一致")
        elif statuses["no_counter_evidence"] == "false":
            grade = RelationGrade.CONTRADICTED
            explanation_parts.append("存在反向证据，原假设被挑战")
        elif (statuses["identity"] == "true" and statuses["period"] == "true" and statuses["scope"] == "true"
              and statuses["accounting_conditions"] == "true" and statuses["comparability"] == "true"
              and statuses["evidence"] == "true" and statuses["reconciliation"] == "true"):
            grade = RelationGrade.A
            explanation_parts.append("身份、期间、范围、会计前提与金额勾稽同时成立")
        elif (statuses["identity"] == "true" and (statuses["period"] == "true" or cross_period)
              and statuses["evidence"] == "true" and statuses["comparability"] != "false"):
            grade = RelationGrade.B
            explanation_parts.append("同项目跨期证据已定位，金额不作同期勾稽" if cross_period else "项目身份、期间与原文证据成立")
        elif statuses["accounting_conditions"] != "false" and statuses["comparability"] != "false":
            grade = RelationGrade.C
            explanation_parts.append("可以提出会计候选路径，但项目身份或金额证据不足")
        else:
            grade = RelationGrade.D
            explanation_parts.append("已有财务项目但不满足最低证据条件，缺口记待补证")
    else:
        checks = [
            ConditionCheck(key="identity", label="业务身份一致", status="unknown", reason="未检索到项目级财务项目"),
            ConditionCheck(key="period", label="事项期间与财务期间一致", status="unknown", reason="无财务项目"),
            ConditionCheck(key="scope", label="合并范围一致", status="unknown", reason="无财务项目"),
            ConditionCheck(key="accounting_conditions", label="会计处理前提满足", status="unknown", reason="待补证"),
            ConditionCheck(key="comparability", label="金额性质可比", status="unknown", reason="无财务项目"),
            ConditionCheck(key="cross_reference", label="存在项目级交叉索引", status="unknown", reason="无财务项目"),
            ConditionCheck(key="evidence", label="证据充分", status="unknown", reason="仅有事项原文，无财务证据"),
            ConditionCheck(key="no_counter_evidence", label="无反向证据", status="true" if not counter else "false",
                           reason="未检索到反向证据" if not counter else "存在反向证据"),
            ConditionCheck(key="reconciliation", label="可执行确定性金额勾稽", status="unknown", reason="无可比项目"),
        ]
        if counter:
            grade = RelationGrade.CONTRADICTED
        elif support:
            grade = RelationGrade.C
            explanation_parts.append("存在候选会计逻辑与相关文本，但缺项目级金额证据，缺口记待补证")
        else:
            grade = RelationGrade.D
            explanation_parts.append("当前公开资料未找到可归属的项目级财务证据；缺口记待补证，不推断企业未披露")

    unmet = [check.label for check in checks if check.status != "true" and check.key != "no_counter_evidence"]
    if grade == RelationGrade.A:
        explanation_parts = ["九项条件全部成立"]
    elif unmet:
        explanation_parts.append("尚未满足：" + "、".join(unmet[:5]))
    relation = ImpactRelation(
        relation_id=f"IR-{event.event_id}-{(item.item_id if item else 'NOITEM')}",
        event_id=event.event_id, financial_item_id=item.item_id if item else None,
        treatment_id=getattr(treatment, "treatment_id", None),
        relation_type=('contradicted_by' if grade == RelationGrade.CONTRADICTED else
                       'incompatible' if grade == RelationGrade.INCOMPATIBLE else
                       "unresolved" if grade in {RelationGrade.D, RelationGrade.C} else "supported_by"),
        grade=grade, conditions=checks,
        supporting=[_candidate_ref(entry) for entry in support[:3]],
        counter=[_candidate_ref(entry) for entry in counter[:3]],
        numeric_reconciliation=reconciliation,
        explanation="；".join(explanation_parts) + "。" + GRADE_MEANING,
    )
    if previous is not None and previous.grade != relation.grade:
        relation.history = list(previous.history) + [{
            "from": previous.grade.value, "to": relation.grade.value,
            "reason": "条件复核后等级变化", "at": "calculation"}]
    return relation


def _candidate_ref(entry: dict) -> EvidenceRef:
    """检索引用保留自己的文档身份，不能借用事项或所选财务项目的身份。"""
    return EvidenceRef(document_id=str(entry.get('document_id') or ''),
        file_sha256=str(entry.get('file_sha256') or ''), report_type=str(entry.get('report_type') or ''),
        pdf_page=int(entry.get('pdf_page') or 0), bbox=entry.get('bbox') or [],
        quote=str(entry.get('quote') or ''), verified=bool(entry.get('verified')))


def summarize(relations: list[ImpactRelation]) -> dict:
    counts: dict[str, int] = {}
    for relation in relations:
        counts[relation.grade.value] = counts.get(relation.grade.value, 0) + 1
    return {"total": len(relations), "grades": counts, "labels": {key: GRADE_LABELS[RelationGrade(key)] for key in counts},
            "notice": GRADE_MEANING}
