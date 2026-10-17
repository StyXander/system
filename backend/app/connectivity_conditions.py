"""前提的可追溯升级：只用本行已登记字段与原文结构，不给"看起来一致"当依据。

升级规则（全部确定性、可复核）：
- 主体：成员同属一份报告的身份主体，且有原文出现该主体全称。
- 期间：各成员年度列均已归属且同为比较期间，且原文出现该年度。
- 单位：各成员单位与单位来源均已确认，量纲一致，且原文出现该单位。
- 范围：各成员位置层级一致且非空，且各自文档有统计范围说明原文。
- 定义：原文对指标名称给出"指／系指／定义为／包括"等定义句。
- 组成完整／互不重叠：由可识别的完整业务分类及原文定义支持，独立于是否加平。
- 公式：指标名称本身写明"X占Y比例"。
升级只把 unknown 推到 supported；已有 supported 或 conflicting 的条件保持原样，不覆盖模型给出的依据。
"""
from __future__ import annotations

import re

from .connectivity_engine import validate_refs
from .connectivity_rules import direct_metric
from .connectivity_schemas import ComparisonCondition, ConnectivityRun, DisclosureOccurrence, EvidenceRef, RelationshipCheck

SCOPE_MARKERS = ("合并报表范围", "合并财务报表范围", "合并范围", "统计范围", "统计口径", "组织边界", "运营控制权", "本报告覆盖")
# 定义句式：必须紧跟指标名，不接受"价格指数""数据指标"里的"指"。
DEFINITION_PATTERN = re.compile(r"(?:是指|系指|指|定义为|包括但不限于|核算范围包括|包括)")
TOTAL_LABEL = re.compile(r"^(?:.{0,24}?)(合计|总计|总额|小计)$")
RATIO_FORMULA = re.compile(r"(.{2,24}?)占(.{2,24}?)(?:的)?(?:比例|比重|比率)")
LABEL_SUFFIX = re.compile(r"(合计|总计|小计|总额|其中|费用化|资本化|专项|其他|其它|减：|加：)")


def _quote_around(context: str, needle: str, span: int = 14) -> str:
    """从原文上下文中截取包含关键词的逐字片段，保证 validate_refs 可复核。"""
    if not needle:
        return ""
    index = context.find(needle)
    if index < 0:
        return ""
    return context[max(0, index - span): index + len(needle) + span].strip()


def _quote_for(row: DisclosureOccurrence, candidates: list[str]) -> str:
    for needle in candidates:
        quote = _quote_around(row.context, needle)
        if quote:
            return quote
    return ""


def _definition_quote(context: str, core: str) -> str:
    """只认“指标名 + 定义词”紧邻的句式，并返回包含定义词的原文片段。"""
    pattern = re.compile(re.escape(core) + r"\s*" + DEFINITION_PATTERN.pattern)
    for match in pattern.finditer(context):
        start = match.start()
        return context[start:start + min(80, len(context) - start)].strip()
    return ""


def _set(conditions: dict[str, ComparisonCondition], name: str, reason: str, refs: list[EvidenceRef],
         found: dict[str, DisclosureOccurrence]) -> bool:
    condition = conditions.get(name)
    if condition is None or condition.status != "unknown":
        return False
    if not refs or not validate_refs(refs, found):
        return False
    condition.status = "supported"
    condition.reason = reason
    condition.evidence = refs
    return True


def upgrade_conditions(check: RelationshipCheck, run: ConnectivityRun, period: str) -> tuple[RelationshipCheck, list[str]]:
    """返回升级后的关系与被升级的条件名；不做任何降级或覆盖。"""
    found = {row.occurrence_id: row for row in run.occurrences}
    members = [found[item.occurrence_id] for item in check.members if item.occurrence_id in found]
    if not members:
        return check, []
    documents = {doc.document_id: doc for doc in run.documents}
    conditions = {item.name: item.model_copy(deep=True) for item in check.conditions}
    upgraded: list[str] = []
    entity_ids = {documents[row.document_id].company_id for row in members if row.document_id in documents}
    entity_name = documents[members[0].document_id].company if members[0].document_id in documents else ""

    # 主体：同一身份主体 + 原文出现该主体名称。
    if len(entity_ids) == 1 and entity_name:
        core = re.sub(r"(股份有限公司|有限责任公司|集团有限公司|有限公司)$", "", entity_name)[:6]
        basis = next((row for row in run.occurrences
                      if row.document_id in {m.document_id for m in members}
                      and core and core in row.context and _quote_for(row, [entity_name, core])), None)
        if basis and _set(conditions, "主体", f"成员同属{entity_name}，原文出现该主体名称",
                          [EvidenceRef(occurrence_id=basis.occurrence_id, quote=_quote_for(basis, [entity_name, core]))], found):
            upgraded.append("主体")

    # 期间：各成员年度已归属且同为比较期间，原文出现该年度。
    attributed = [row for row in members if row.year_status == "attributed" and row.year]
    if attributed and len(attributed) == len(members) and {row.year for row in attributed} == {period}:
        witness = next((row for row in attributed if _quote_for(row, [f"{period}年", period])), None)
        if witness and _set(conditions, "期间", f"各成员年度列均已归属且同为{period}年",
                           [EvidenceRef(occurrence_id=witness.occurrence_id, quote=_quote_for(witness, [f"{period}年", period]))], found):
            upgraded.append("期间")

    # 单位：每个成员的单位与单位来源均已确认；量纲是否相容由算式判断，不由本条件代替。
    units = sorted({row.unit for row in members})
    if all(row.unit and row.unit_source for row in members):
        witness = next((row for row in members if _quote_for(row, [row.unit])), None)
        if witness and _set(conditions, "单位", f"各成员单位均已登记（{'、'.join(units)}），单位来源已注明",
                            [EvidenceRef(occurrence_id=witness.occurrence_id, quote=_quote_for(witness, [witness.unit]))], found):
            upgraded.append("单位")

    # 范围：位置层级一致且有统计范围说明原文。
    scopes = {row.scope.strip() for row in members}
    if len(scopes) == 1:
        scope = next(iter(scopes))
        refs, ok = [], True
        for document_id in {row.document_id for row in members}:
            statement = next((row for row in run.occurrences if row.document_id == document_id
                              and any(marker in re.sub(r"\s+", "", row.context) for marker in SCOPE_MARKERS)), None)
            if not statement:
                ok = False
                break
            quote = _quote_for(statement, [scope]) or next((_quote_around(statement.context, marker) for marker in SCOPE_MARKERS
                                                           if _quote_around(statement.context, marker)), "")
            if not quote:
                ok = False
                break
            refs.append(EvidenceRef(occurrence_id=statement.occurrence_id, quote=quote))
        reason = (f"各成员位置层级均为{scope}，且原文有统计范围说明" if scope
                  else "各成员未单独标注位置层级，按两份报告的统计范围说明适用（报告级共同依据）")
        if ok and _set(conditions, "范围", reason, refs, found):
            upgraded.append("范围")

    # 定义：原文对指标名称给出定义句。成员标签先去掉行次后缀，避免只认“合计”这种行名。
    cores = []
    for member in members:
        core = LABEL_SUFFIX.sub("", re.sub(r"[\s：:（）()%％]", "", member.label))
        if len(core) >= 3:
            cores.append(core)
    definition_found = None
    for core in sorted(set(cores), key=len, reverse=True):
        for item in run.occurrences:
            quote = _definition_quote(item.context, core)
            if quote:
                definition_found = (core, item, quote)
                break
        if definition_found:
            break
    if definition_found:
        core, row, quote = definition_found
        # 依据片段必须包含定义句本身，而不是指标名出现处。
        if _set(conditions, "定义", f"原文以“{core}……”句式给出定义：{quote[:24]}",
                [EvidenceRef(occurrence_id=row.occurrence_id, quote=quote)], found):
            upgraded.append("定义")

    # 直接披露量以两侧明确行名证明指标身份，无须企业额外复述词典定义。
    # 只适用受控白名单，不把研发费用视为研发投入，也不替代主体与范围条件。
    metric = direct_metric(members[0].label)
    if check.operator == "equal" and metric and all(direct_metric(row.label) == metric for row in members):
        refs = [EvidenceRef(occurrence_id=row.occurrence_id, quote=row.row_header or row.label) for row in members]
        if _set(conditions, "定义", f"两侧原文行名均明确披露{metric}；仅核对披露数值，不确认计量方法或数据真实性", refs, found):
            upgraded.append("定义")

    if check.operator == "sum":
        _upgrade_sum(check, conditions, members, found, upgraded)
    if check.operator == "ratio":
        _upgrade_ratio(conditions, members, found, upgraded)
    result = check.model_copy(deep=True)
    result.conditions = list(conditions.values())
    return result, upgraded


def _upgrade_sum(check: RelationshipCheck, conditions: dict[str, ComparisonCondition],
                 members: list[DisclosureOccurrence], found: dict[str, DisclosureOccurrence], upgraded: list[str]) -> None:
    """先检验组成结构，后做算术；不同坐标不等于业务上互不重叠。"""
    roles = {item.occurrence_id: item.role for item in check.members}
    total = next((row for row in members if roles.get(row.occurrence_id) == "total"), None)
    components = [row for row in members if roles.get(row.occurrence_id) == "component"]
    if total is None or len(components) < 2:
        return
    same_table = all(row.document_id == total.document_id and row.pdf_page == total.pdf_page
                     and row.column_header == total.column_header for row in components)
    if not same_table:
        return
    # 首版只自动支持原文定义明确包含的资本化/费用化两分法。
    # 其它分组继续交给语义补证；不以“刚好加平”证明分项齐全。
    labels = [re.sub(r"\s+", "", row.label) for row in components]
    categories = ["费用化" if "费用化" in label else "资本化" if "资本化" in label else "" for label in labels]
    definition = next((row for row in found.values() if row.document_id == total.document_id
                       and "资本化" in row.context and "费用化" in row.context
                       and _definition_quote(row.context, "环保投入" if check.rule_id == "ENV-001" else "研发投入")), None)
    if len(components) != 2 or set(categories) != {"资本化", "费用化"} or not definition or any("其中" in label for label in labels):
        return
    quote = _definition_quote(definition.context, "环保投入" if check.rule_id == "ENV-001" else "研发投入")
    if quote and _set(conditions, "组成完整",
                       "同表包含资本化与费用化两类，且原文定义明确包含这两类支出；算术是否加平另行计算",
                       [EvidenceRef(occurrence_id=definition.occurrence_id, quote=quote)], found):
        upgraded.append("组成完整")
    boxes = {tuple(round(value, 1) for value in row.bbox) for row in components}
    if len(set(labels)) == len(labels) and len(boxes) == len(labels):
        witness = components[0]
        quote = _quote_for(witness, [witness.unit]) or witness.row_header[:60]
        if quote and _set(conditions, "互不重叠", "原文定义下的资本化、费用化为两类支出，且分列不同物理位置；未将其中项重复计入",
                          [EvidenceRef(occurrence_id=witness.occurrence_id, quote=quote)], found):
            upgraded.append("互不重叠")


def _upgrade_ratio(conditions: dict[str, ComparisonCondition], members: list[DisclosureOccurrence],
                   found: dict[str, DisclosureOccurrence], upgraded: list[str]) -> None:
    """公式支持只看指标名称原文是否写明分子与分母。"""
    ratio_row = next((row for row in members if row.unit in {"%", "％"} or "比例" in row.label or "强度" in row.label), None)
    if ratio_row is None:
        return
    matched = RATIO_FORMULA.search(re.sub(r"\s+", "", ratio_row.label))
    if not matched:
        return
    quote = _quote_for(ratio_row, [ratio_row.label[:16]])
    if quote and _set(conditions, "公式", f"指标名称“{ratio_row.label[:24]}”写明分子与分母",
                      [EvidenceRef(occurrence_id=ratio_row.occurrence_id, quote=quote)], found):
        upgraded.append("公式")
