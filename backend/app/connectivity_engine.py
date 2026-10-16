"""有依据才计算的确定性引擎，模型不得覆盖残差与未知条件。

同值、组成和比例只读原文成员的十进制值。
试算与可比性判断分别记录；相等不反向证明定义及范围。
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import re

from .connectivity_schemas import DisclosureOccurrence, EvidenceRef, RelationshipCheck
from .connectivity_rules import RULES, required_conditions

# 单位表只包含确定倍率；不同币种不能靠数量级换算。
UNITS = {
    "元": ("money", "1"), "千元": ("money", "1000"), "万元": ("money", "10000"),
    "百万元": ("money", "1000000"), "亿元": ("money", "100000000"),
    "吨": ("mass", "1"), "万吨": ("mass", "10000"),
    "千瓦时": ("electric_energy", "1"), "万千瓦时": ("electric_energy", "10000"), "兆瓦时": ("electric_energy", "1000"),
    "吉焦": ("heat_energy", "1"), "太焦": ("heat_energy", "1000"),
    "吨标准煤": ("standard_coal", "1"), "万吨标准煤": ("standard_coal", "10000"),
    "吨二氧化碳当量": ("co2e", "1"), "万吨二氧化碳当量": ("co2e", "10000"),
    "吨粗钢": ("crude_steel_mass", "1"), "万吨粗钢": ("crude_steel_mass", "10000"),
    "吨产品": ("product_mass", "1"), "万吨产品": ("product_mass", "10000"),
    "立方米": ("volume", "1"), "千立方米": ("volume", "1000"), "万立方米": ("volume", "10000"), "百万立方米": ("volume", "1000000"), "亿立方米": ("volume", "100000000"),
    "人": ("people", "1"), "万人": ("people", "10000"), "%": ("ratio", "0.01"),
    "倍": ("ratio", "1"), "": ("unknown", "1"),
}


def number(value: str | None) -> Decimal:
    """空白、破折号和缺失均不等于零，拒绝非有限数值。"""
    text = str(value or "").strip().replace(",", "").replace("，", "").replace("−", "-")
    if re.fullmatch(r"\([\d.]+\)", text):
        text = "-" + text[1:-1]
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        raise ValueError("数值缺失或不是明确的十进制数")
    result = Decimal(text)
    if not result.is_finite():
        raise ValueError("数值必须有限")
    return result


def text_number(value: Decimal) -> str:
    return format(value, "f")


@dataclass(frozen=True)
class Interval:
    low: Decimal
    high: Decimal
    low_closed: bool = True
    high_closed: bool = True

    def overlaps(self, other: "Interval") -> bool:
        """端点相碰时同时包含该点才兼容，避免边界被错误放宽。"""
        if self.high < other.low or other.high < self.low:
            return False
        if self.high == other.low:
            return self.high_closed and other.low_closed
        if other.high == self.low:
            return other.high_closed and self.low_closed
        return True

    def plus(self, other: "Interval") -> "Interval":
        return Interval(self.low + other.low, self.high + other.high,
                        self.low_closed and other.low_closed, self.high_closed and other.high_closed)

    def as_dict(self) -> dict:
        return {"low": text_number(self.low), "high": text_number(self.high), "low_closed": self.low_closed, "high_closed": self.high_closed}


def numeric_unit(unit: str) -> tuple[str, Decimal]:
    """复合单位按量纲化简，吨与立方米不作默认密度转换。"""
    cleaned = unit.strip().replace("人民币", "").replace("／", "/").replace("％", "%")
    if cleaned in UNITS:
        dimension, factor = UNITS[cleaned]
        return dimension, Decimal(factor)
    if "/" in cleaned:
        left, right = cleaned.split("/", 1)
        dl, fl = numeric_unit(left)
        dr, fr = numeric_unit(right)
        if "unknown" not in (dl, dr):
            return "ratio" if dl == dr else f"{dl}/{dr}", fl / fr
    return "unknown", Decimal(1)


def normalized(occurrence: DisclosureOccurrence) -> tuple[Decimal, str, Interval]:
    raw = number(occurrence.value)
    dimension, factor = numeric_unit(occurrence.unit)
    if dimension == "unknown":
        raise ValueError(f"{occurrence.label}的单位尚未确定")
    value = raw * factor
    interval = Interval(value, value)
    # 只有来源明确声明舍入方法才使用半单位区间；小数位数本身不是方法依据。
    if occurrence.rounding == "half_up":
        precision = Decimal(1).scaleb(raw.as_tuple().exponent) * factor / 2
        interval = Interval(value - precision, value + precision, raw > 0, raw < 0)
    return value, dimension, interval


def validate_refs(refs: list[EvidenceRef], occurrences: dict[str, DisclosureOccurrence]) -> bool:
    """引用必须属于本次报告且逐字存在于对应上下文，不接受模型编造出处。"""
    compact = lambda s: re.sub(r"\s+", "", s)
    return bool(refs) and all(ref.occurrence_id in occurrences and
        compact(ref.quote) in compact(occurrences[ref.occurrence_id].context)
        for ref in refs)


def calculate(check: RelationshipCheck, occurrences: list[DisclosureOccurrence]) -> RelationshipCheck:
    """从原始关系重建状态，忽略前端或模型提交的既有计算结论。"""
    result = check.model_copy(deep=True)
    result.calculation = {}
    result.unresolved = []
    result.criteria_status = "unknown"
    result.calculation_status = "not_executable"
    found = {item.occurrence_id: item for item in occurrences}
    if RULES[result.rule_id]["operator"] != result.operator:
        raise ValueError("规则与算子不一致")
    if len({m.occurrence_id for m in result.members}) != len(result.members):
        raise ValueError("同一披露不能重复计入关系")
    if any(m.occurrence_id not in found for m in result.members):
        raise ValueError("关系成员超出本次报告")
    # 表格与坐标回退可能指向同一个物理单元格，不能靠换一个ID重复计入。
    located_members = [found[m.occurrence_id] for m in result.members]
    for index, first in enumerate(located_members):
        if len(first.bbox) != 4 or first.value is None:
            continue
        for second in located_members[index+1:]:
            if first.document_id != second.document_id or first.pdf_page != second.pdf_page or len(second.bbox) != 4 or first.value != second.value:
                continue
            a, b = first.bbox, second.bbox
            overlap = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
            area = min(max(0, a[2]-a[0])*max(0, a[3]-a[1]), max(0, b[2]-b[0])*max(0, b[3]-b[1]))
            if area > 0 and overlap/area > .7:
                raise ValueError("成员重复指向同一个原文单元格")
    conditions = {}
    for condition in result.conditions:
        if condition.name in conditions:
            raise ValueError("同一比较条件不能重复提交")
        if condition.status != "unknown" and not validate_refs(condition.evidence, found):
            condition.status = "unknown"
            condition.reason = "所引依据缺失、越界或原文不匹配"
        conditions[condition.name] = condition
    for name in required_conditions(result.operator):
        if name not in conditions or conditions[name].status == "unknown":
            result.unresolved.append(f"{name}依据尚未充分说明")
        elif conditions[name].status == "conflicting":
            result.unresolved.append(f"{name}存在明确冲突：{conditions[name].reason}")
    if not validate_refs(result.relationship_evidence, found):
        result.unresolved.append("本次具体关系缺少有效原文依据")
    money_members = [found[m.occurrence_id] for m in result.members if "money" in numeric_unit(found[m.occurrence_id].unit)[0]]
    if any(not row.currency for row in money_members):
        result.unresolved.append("货币成员币种尚未证实，金额换算只能列假设试算")
    explicit_years = {found[m.occurrence_id].year for m in result.members if found[m.occurrence_id].year}
    if len(explicit_years) > 1:
        result.unresolved.append("成员明确属于不同期间，不能作为本期同口径关系")
    if result.explanation and not validate_refs(result.explanation_evidence, found):
        result.unresolved.append("解释尚缺有效原文支持")
    conflict = any(c.status == "conflicting" for c in result.conditions)
    result.criteria_status = "conflicting" if conflict else "unknown" if result.unresolved else "supported"
    if result.operator == "narrative":
        result.calculation_status = "not_applicable"
        result.calculation = {"statement": result.explanation, "evidence_supported": validate_refs(result.explanation_evidence, found)}
        return result
    try:
        with localcontext() as ctx:
            ctx.prec = 40
            result.calculation = _arithmetic(result, found)
    except (ValueError, InvalidOperation, ZeroDivisionError) as error:
        result.unresolved.append(str(error))
        return result
    # 缺条件时展示明确标记的试算，不能将零残差升级为可衔接。
    result.calculation["hypothetical"] = result.criteria_status != "supported"
    if result.criteria_status != "supported":
        result.calculation_status = "not_comparable"
    elif result.calculation["residual"] == "0":
        result.calculation_status = "consistent"
    elif result.calculation.get("precision_compatible"):
        result.calculation_status = "precision_explained"
    else:
        result.calculation_status = "unexplained_difference"
        result.unresolved.append("同口径计算仍有未解释差额")
    return result


def _arithmetic(check: RelationshipCheck, found: dict[str, DisclosureOccurrence]) -> dict:
    """仅支持固定成员角色，不运行模型生成的表达式。"""
    grouped: dict[str, list] = {}
    inputs = []
    currencies = set()
    for member in check.members:
        occurrence = found[member.occurrence_id]
        value, dimension, interval = normalized(occurrence)
        grouped.setdefault(member.role, []).append((value, dimension, interval))
        inputs.append({"occurrence_id": occurrence.occurrence_id, "role": member.role, "label": occurrence.label,
                       "raw": occurrence.value, "unit": occurrence.unit, "normalized": text_number(value), "dimension": dimension})
        if "money" in dimension:
            if occurrence.currency:
                currencies.add(occurrence.currency)
    if len(currencies) > 1:
        raise ValueError("币种不同，未采用有依据的币种调节")

    def one(role: str):
        items = grouped.get(role, [])
        if len(items) != 1:
            raise ValueError(f"关系需要且只能有一个{role}成员")
        return items[0]

    expected_roles = set(RULES[check.rule_id]["roles"])
    if set(grouped) != expected_roles:
        raise ValueError("关系成员角色不完整或含额外角色")
    comparisons = []
    if check.operator == "equal":
        a, da, ia = one("left")
        b, db, ib = one("right")
        if da != db:
            raise ValueError("两侧量纲不一致")
        expression = f"{text_number(a)} − {text_number(b)}"
    elif check.operator == "sum":
        a, da, ia = one("total")
        components = grouped["component"]
        if any(d != da for _, d, _ in components):
            raise ValueError("组成成员量纲不一致")
        b = sum((v for v, _, _ in components), Decimal(0))
        ib = Interval(Decimal(0), Decimal(0))
        for _, _, interval in components:
            ib = ib.plus(interval)
        expression = f"{text_number(a)} − (" + " + ".join(text_number(v) for v, _, _ in components) + ")"
    elif check.operator == "ratio":
        n, dn, ni = one("numerator")
        d, dd, di = one("denominator")
        a, da, ia = one("reported_ratio")
        expected_dimension = "ratio" if dn == dd else f"{dn}/{dd}"
        if da != expected_dimension:
            raise ValueError("分子分母与披露比例的量纲不匹配")
        if d == 0 or di.low <= 0 <= di.high:
            raise ValueError("分母为零或精度区间跨零")
        scale = number(check.ratio_scale)
        if scale != 1:
            # 百分数及常见单位已在规范化阶段处理，额外倍率要有公式依据。
            raise ValueError("额外比例倍率须转换为明确单位后计算")
        b = n / d
        candidates = [ni.low / di.low, ni.low / di.high, ni.high / di.low, ni.high / di.high]
        closed = ni.low_closed and ni.high_closed and di.low_closed and di.high_closed
        ib = Interval(min(candidates), max(candidates), closed, closed)
        expression = f"披露{ text_number(a) } − ({text_number(n)} ÷ {text_number(d)})"
    elif check.operator == "occurrences":
        items = grouped["occurrence"]
        if len(items) < 2 or len({dim for _, dim, _ in items}) != 1:
            raise ValueError("多位置核对至少需要两处同量纲数值")
        a, da, ia = items[0]
        for value, _, interval in items[1:]:
            comparisons.append({"residual": text_number(a - value), "precision_compatible": ia.overlaps(interval)})
        b, _, ib = max(items[1:], key=lambda item: abs(a - item[0]))
        expression = "首处与每一已发现位置分别比较，保留全部差异"
    else:
        raise ValueError("不支持的数值算子")
    residual = a - b
    return {"inputs": inputs, "expression": expression, "left": text_number(a), "right": text_number(b),
            "normalized_unit": {"money": "元", "mass": "吨", "volume": "立方米", "people": "人", "ratio": "无量纲（1表示100%）", "electric_energy": "千瓦时", "heat_energy": "吉焦", "standard_coal": "吨标准煤", "co2e": "吨二氧化碳当量", "crude_steel_mass": "吨粗钢", "product_mass": "吨产品", "mass/money": "吨/元", "volume/money": "立方米/元"}.get(da, da),
            "residual": "0" if residual == 0 else text_number(residual),
            "precision_compatible": all(x["precision_compatible"] for x in comparisons) if comparisons else ia.overlaps(ib),
            "left_interval": ia.as_dict(), "right_interval": ib.as_dict(), "positions": comparisons}
