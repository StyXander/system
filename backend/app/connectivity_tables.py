"""表内结构自证：合计行/列、分项行/列与必要的跨表桥接候选。

只从已定位的同一表格结构生成候选；结构证据支持的是 L1 有限可比，
不证明指标定义、统计范围、期间或业务互不重叠。是否正式闭合仍由
`upgrade_conditions` 与 `calculate` 的原文条件门禁决定。
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import hashlib
import re

from .connectivity_engine import number, numeric_unit, text_number
from .connectivity_rules import RULES, required_conditions
from .connectivity_schemas import (ComparisonCondition, DisclosureOccurrence, EvidenceRef, RelationshipCheck,
    RelationshipMember)

TOTAL_LABEL = re.compile(r"(?:合计|总计|总额|小计|总投入|投入合计)$")
COMPONENT_HINT = re.compile(r"^(?:其中|资本化|费用化|专项|其他|其它|钢铁|分项|明细)")
COMPONENT_IN_LABEL = re.compile(r"其中|资本化|费用化|钢铁|其他|其它|分项|明细")
SUM_TOPICS = {"environment": "ENV-001", "research": "RD-001"}


def _position(occurrence: DisclosureOccurrence) -> dict | None:
    """表内自证只接受新提取器写入的显式表格身份；旧运行须重新提取。"""
    if not (occurrence.table_id and occurrence.row_index is not None and occurrence.column_index is not None):
        return None
    return {"table_id": occurrence.table_id, "row": occurrence.row_index, "column": occurrence.column_index,
            "page": occurrence.pdf_page, "document": occurrence.document_id}


def _usable(row: DisclosureOccurrence, period: str) -> bool:
    """组成候选只读已定位、公司自身、有明确数值和量纲的单元格。"""
    if row.value is None or row.quality != "located":
        return False
    if row.content_class in {"macro", "industry", "peer", "background"}:
        return False
    if period and row.year and row.year != period:
        return False
    try:
        number(row.value)
    except ValueError:
        return False
    return numeric_unit(row.unit)[0] != "unknown"


def _normalized(row: DisclosureOccurrence) -> tuple[Decimal, str]:
    value = number(row.value)
    dimension, factor = numeric_unit(row.unit)
    return value * factor, dimension


def _reference(row: DisclosureOccurrence) -> EvidenceRef:
    quote = (row.row_header or row.context or "").strip()[:800]
    return EvidenceRef(occurrence_id=row.occurrence_id, quote=quote)


def _rows_by_table(occurrences: list[DisclosureOccurrence], period: str) -> dict[str, dict]:
    """按真实 table_id 聚合行/列位置；没有结构身份的坐标行不参与表内自证。"""
    tables: dict[str, dict] = {}
    for row in occurrences:
        if not _usable(row, period):
            continue
        position = _position(row)
        if position is None:
            continue
        table = tables.setdefault(position["table_id"], {
            "table_id": position["table_id"], "document_id": row.document_id,
            "pdf_page": position["page"], "rows": defaultdict(dict), "row_labels": {},
            "column_labels": {}, "header_paths": {},
        })
        table["rows"][position["row"]][position["column"]] = row
        table["row_labels"].setdefault(position["row"], row.label)
        table["column_labels"].setdefault(position["column"], row.column_header or " / ".join(row.header_path))
        table["header_paths"].setdefault(position["column"], list(row.header_path))
    return tables


def _role_from_label(label: str) -> str:
    compact = re.sub(r"[\s：:（）()]", "", label or "")
    if TOTAL_LABEL.search(compact):
        return "total"
    if COMPONENT_HINT.search(compact) or COMPONENT_IN_LABEL.search(compact):
        return "component"
    return "detail"


def _role_from_header(header: str) -> str:
    compact = re.sub(r"\s+", "", header or "")
    if re.search(r"合计|总计|总额|小计", compact):
        return "total"
    if re.search(r"钢铁|其他|其它|范围一|范围二|费用化|资本化|分项|明细", compact):
        return "component"
    if re.search(r"20\d{2}|本期|本年", compact):
        return "period"
    return "unknown"


def _member(row: DisclosureOccurrence, role: str) -> RelationshipMember:
    return RelationshipMember(occurrence_id=row.occurrence_id, role=role)


def _condition(name: str, reason: str, evidence: list[EvidenceRef]) -> ComparisonCondition:
    return ComparisonCondition(name=name, reason=reason, evidence=evidence,
                               evidence_kind="table_structure" if name in {"组成完整", "互不重叠"} else "unspecified")


def _structure_payload(table_id: str, layout: str, total: DisclosureOccurrence,
                       components: list[DisclosureOccurrence], *, coverage: dict,
                       non_overlap: dict, limitations: list[str]) -> dict:
    """结构证据保存可复核的坐标、角色、覆盖与限制，不用“加平”代替完整性。"""
    return {
        "table_id": table_id,
        "layout": layout,
        "pdf_page": total.pdf_page,
        "header_path": list(total.header_path),
        "total": {"occurrence_id": total.occurrence_id, "label": total.label, "row_index": total.row_index,
                  "column_index": total.column_index, "row_role": "total",
                  "column_role": total.column_role if total.column_role != "unknown" else "period",
                  "column_header": total.column_header, "header_path": list(total.header_path),
                  "raw": total.value, "unit": total.unit},
        "components": [{"occurrence_id": row.occurrence_id, "label": row.label, "row_index": row.row_index,
                        "column_index": row.column_index, "row_role": row.row_role,
                        "column_role": row.column_role, "column_header": row.column_header,
                        "header_path": list(row.header_path), "raw": row.value, "unit": row.unit} for row in components],
        "coverage": coverage,
        "non_overlap": non_overlap,
        "limitations": limitations,
    }


def _check(rule_id: str, title: str, topic: str, total: DisclosureOccurrence,
           components: list[DisclosureOccurrence], structure: dict) -> RelationshipCheck:
    required = required_conditions(RULES[rule_id]["operator"])
    reasons = {
        "组成完整": "表内结构显示合计覆盖已识别分项；仅支持 L1 有限比较，指标定义与完整性仍待原文",
        "互不重叠": "表内结构显示分项为同一合计下的兄弟行/列；业务互斥仍待原文定义",
    }
    conditions = [_condition(name, reasons.get(name, "由表内结构自动登记；待指标级原文确认"), []) for name in required]
    digest = hashlib.sha1(f"{total.occurrence_id}-{structure.get('layout')}".encode("utf-8")).hexdigest()[:10].upper()
    return RelationshipCheck(check_id=f"TABLE-{digest}", rule_id=rule_id, title=title[:160], topic=topic,
        operator=RULES[rule_id]["operator"],
        members=[_member(total, "total")] + [_member(row, "component") for row in components],
        conditions=conditions, relationship_evidence=[_reference(total)],
        relationship_basis="table_structure", table_structure=structure)


def _sum_values(rows: list[DisclosureOccurrence]) -> tuple[Decimal | None, str]:
    values, dimensions = [], set()
    for row in rows:
        value, dimension = _normalized(row)
        values.append(value)
        dimensions.add(dimension)
    if len(dimensions) != 1:
        return None, ""
    return sum(values, Decimal(0)), next(iter(dimensions))


def _column_candidates(table: dict) -> list[RelationshipCheck]:
    """同一行、不同列：合计列覆盖相邻分项列（如钢铁+其他=合计）。"""
    checks = []
    for row_index, columns in table["rows"].items():
        if len(columns) < 3:
            continue
        cells = [columns[index] for index in sorted(columns)]
        roles = {row.occurrence_id: _role_from_header(table["column_labels"].get(row.column_index, "")) for row in cells}
        totals = [row for row in cells if roles[row.occurrence_id] == "total" or row.column_role == "total"]
        components = [row for row in cells if row not in totals and (
            roles[row.occurrence_id] == "component" or row.column_role == "component")]
        if len(totals) != 1 or len(components) < 2:
            continue
        total = totals[0]
        components = sorted(components, key=lambda row: row.column_index)
        if total.column_index < max(row.column_index for row in components):
            continue
        selected_ids = {row.occurrence_id for row in components} | {total.occurrence_id}
        between = [row for column, row in columns.items()
                   if min(item.column_index for item in components) <= column < total.column_index]
        if any(row.occurrence_id not in selected_ids for row in between):
            # 合计与分项之间还有未识别的同表列，不能宣称覆盖全部。
            continue
        total_value, _ = _normalized(total)
        component_sum, _ = _sum_values(components)
        if component_sum is None:
            continue
        coverage = {"component_count": len(components),
                    "total_covers_columns": True,
                    "all_components_between_total": True,
                    "total_equals_sum": total_value == component_sum,
                    "sum_residual": text_number(total_value - component_sum),
                    "basis": "同一表格、同一指标行、合计列位于分项列右侧"}
        non_overlap = {"status": "structural_assumption",
                       "basis": "分项列为同一合计行下的兄弟列，坐标上互不重复",
                       "limitations": ["列结构不证明业务分类互斥，仍需原文定义"]}
        structure = _structure_payload(table["table_id"], "column_sum", total, components,
            coverage=coverage, non_overlap=non_overlap,
            limitations=["表内结构仅支持 L1 有限可比；指标定义、统计范围与期间仍需原文核实",
                         "合计列等于分项之和只证明算术相容，不证明企业披露正确"])
        rule_id = SUM_TOPICS.get(total.topic)
        if not rule_id:
            continue
        checks.append(_check(rule_id, f"{total.label[:60]} · 表内合计列与分项列", total.topic,
                             total, components, structure))
    return checks


def _previous_total_index(table: dict, row_index: int) -> int:
    previous = [index for index in table["rows"] if index < row_index
                and _role_from_label(table["row_labels"].get(index, "")) == "total"]
    return max(previous) if previous else -1


def _row_candidates(table: dict) -> list[RelationshipCheck]:
    """同一列、不同行：合计行覆盖其上分项行（如费用化+资本化=总投入）。"""
    checks = []
    by_column: dict[int, list[tuple[int, DisclosureOccurrence]]] = defaultdict(list)
    for row_index, columns in table["rows"].items():
        for column_index, row in columns.items():
            by_column[column_index].append((row_index, row))
    for column_index, items in by_column.items():
        items.sort(key=lambda pair: pair[0])
        for position, (row_index, total) in enumerate(items):
            if _role_from_label(total.label) != "total" and total.row_role != "total":
                continue
            if position == 0:
                continue
            lower = _previous_total_index(table, row_index)
            between = [row for index, row in items[position - 1::-1] if index > lower]
            components = [row for row in between
                          if total.document_id == row.document_id
                          and numeric_unit(row.unit)[0] == numeric_unit(total.unit)[0]]
            # 只接受紧邻合计行、带分项语义的行；普通明细不能凑数。
            components = [row for row in components if _role_from_label(row.label) == "component"][:12]
            if len(components) < 2:
                continue
            if any(_role_from_label(row.label) != "component" and row.value is not None for row in between
                   if row.occurrence_id not in {item.occurrence_id for item in components}):
                # 合计与分项之间还有未识别的同列数值，不能宣称覆盖完整。
                continue
            components.reverse()
            total_value, dimension = _normalized(total)
            component_sum, component_dimension = _sum_values(components)
            if component_dimension and component_dimension != dimension:
                continue
            coverage = {"component_count": len(components),
                        "total_covers_rows": True,
                        "all_components_between_total": True,
                        "total_equals_sum": component_sum is not None and total_value == component_sum,
                        "sum_residual": text_number(total_value - component_sum) if component_sum is not None else "",
                        "basis": "同一表格、同一数值列，合计行位于分项行之后"}
            non_overlap = {"status": "structural_assumption",
                           "basis": "分项行为同一合计行上方的兄弟行，坐标上互不重复",
                           "limitations": ["行结构不证明业务分类互斥，仍需原文定义"]}
            structure = _structure_payload(table["table_id"], "row_sum", total, components,
                coverage=coverage, non_overlap=non_overlap,
                limitations=["表内结构仅支持 L1 有限可比；指标定义、统计范围与期间仍需原文核实",
                             "分项加总等于合计只证明算术相容，不证明分项完整"])
            rule_id = SUM_TOPICS.get(total.topic)
            if not rule_id:
                continue
            checks.append(_check(rule_id, f"{total.label[:60]} · 表内合计行与分项行", total.topic,
                                 total, components, structure))
    return checks


def _cross_table_candidates(tables: dict[str, dict]) -> list[RelationshipCheck]:
    """跨表桥接只在同文档、相邻页、同期间且标签同源时生成；默认不启用。"""
    checks = []
    table_items = list(tables.values())
    for left in table_items:
        for right in table_items:
            if left is right or left["document_id"] != right["document_id"]:
                continue
            if abs(left["pdf_page"] - right["pdf_page"]) > 1:
                continue
            left_rows = [row for columns in left["rows"].values() for row in columns.values()]
            right_rows = [row for columns in right["rows"].values() for row in columns.values()]
            totals = [row for row in left_rows if _role_from_label(row.label) == "total"]
            components_pool = [row for row in right_rows if _role_from_label(row.label) == "component"]
            for left_total in totals:
                components = [row for row in components_pool
                              if row.year == left_total.year
                              and numeric_unit(row.unit)[0] == numeric_unit(left_total.unit)[0]]
                if len(components) < 2:
                    continue
                total_core = re.sub(r"(合计|总计|总额|小计)$", "", re.sub(r"[\s：:（）()]", "", left_total.label))
                if not total_core or not all(total_core[:2] in row.label or row.label[:2] in total_core
                                             for row in components):
                    continue
                total_value, _ = _normalized(left_total)
                component_sum, _ = _sum_values(components)
                coverage = {"component_count": len(components),
                            "total_equals_sum": component_sum is not None and total_value == component_sum,
                            "sum_residual": text_number(total_value - component_sum) if component_sum is not None else "",
                            "basis": "同文档相邻页、同期间列、标签同源的跨表桥接"}
                non_overlap = {"status": "unknown",
                               "basis": "跨表结构无法证明业务互斥",
                               "limitations": ["跨表桥接仅作线索，必须由原文定义确认"]}
                structure = _structure_payload(left["table_id"], "cross_table", left_total, components,
                    coverage=coverage, non_overlap=non_overlap,
                    limitations=["跨表桥接只支持 L1 线索；表间对应关系仍需原文说明",
                                 "未确认两张表是否同一统计范围与期间"])
                rule_id = SUM_TOPICS.get(left_total.topic)
                if not rule_id:
                    continue
                checks.append(_check(rule_id, f"{left_total.label[:60]} · 跨表合计与分项", left_total.topic,
                                     left_total, components, structure))
    return checks


def build_table_composition_candidates(occurrences: list[DisclosureOccurrence], period: str, *,
                                       include_cross_table: bool = False) -> list[RelationshipCheck]:
    """返回表内合计/分项候选；默认只做高置信同表结构。

    返回的 check_id 以 TABLE- 开头，成员、条件和结构证据可直接序列化。
    调用方仍须执行 `upgrade_conditions` 与 `calculate`，不能把结构候选
    直接计为企业异常或正式结论。
    """
    tables = _rows_by_table(occurrences, period)
    checks = []
    for table in tables.values():
        checks.extend(_column_candidates(table))
        checks.extend(_row_candidates(table))
    if include_cross_table:
        checks.extend(_cross_table_candidates(tables))
    # 同一合计/分项集合只保留一次，避免列与行两种读法重复计数。
    unique, seen = [], set()
    for check in checks:
        signature = (check.rule_id, tuple(sorted((member.occurrence_id, member.role) for member in check.members)))
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(check)
    return unique
