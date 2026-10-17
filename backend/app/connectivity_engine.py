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

    def minus(self, other: "Interval") -> "Interval":
        """区间减法；端点开闭随另一端反向继承，边界判定不因取整放宽。"""
        return Interval(self.low - other.high, self.high - other.low,
                        self.low_closed and other.high_closed, self.high_closed and other.low_closed)

    def contains_zero(self) -> bool:
        if self.low > 0 or self.high < 0:
            return False
        if self.low == 0 and not self.low_closed:
            return False
        if self.high == 0 and not self.high_closed:
            return False
        return True

    def as_dict(self) -> dict:
        return {"low": text_number(self.low), "high": text_number(self.high), "low_closed": self.low_closed, "high_closed": self.high_closed,
                "contains_zero": self.contains_zero()}


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
    if result.relationship_basis == "text_statement":
        if not validate_refs(result.relationship_evidence, found):
            result.unresolved.append("本次具体关系缺少有效原文依据")
    else:
        # 自动配对/多位置只是候选：成员行只能证明两处各自披露了什么，
        # 不能证明"这两处应当相互对照"。关系本身仍需原文或人工说明。
        label = "标签与量纲自动配对" if result.relationship_basis == "auto_label_match" else "同报告内多处同名披露"
        result.unresolved.append(f"该关系由{label}得到，尚缺原文对两者关系本身的说明")
    # 跨报告判定：同一文档内的重复位置不构成同值关系，只作多位置核对。
    document_ids = {found[m.occurrence_id].document_id for m in result.members}
    result.cross_document = len(document_ids) > 1
    if result.operator == "equal" and len(document_ids) < 2:
        result.unresolved.append("同值关系需要来自不同报告的两处披露；同一报告内的重复位置只作多位置核对")
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
            trial = _arithmetic(result, found)
    except (ValueError, InvalidOperation, ZeroDivisionError) as error:
        # 已知的规则性错误保留原提示（如币种不同、量纲不一致），便于页面直接说明。
        result.unresolved.append(str(error))
        return result
    except (ArithmeticError, AttributeError, KeyError, IndexError, TypeError) as error:
        result.unresolved.append(f"算式未完成：{type(error).__name__}")
        return result
    # 正式差额硬门禁：任一关键前提 unknown 或 conflicting 时不产出正式差额与残差。
    if result.criteria_status != "supported":
        result.calculation = _gated_calculation(result, trial)
        result.hypothetical = _trial_calculation(trial)
        result.calculation_status = "not_comparable"
        return result
    result.calculation = trial
    result.hypothetical = None
    adjustments = _apply_adjustments(result, trial, found)
    result.calculation["adjustment"] = adjustments
    residual = Decimal(trial["residual"])
    residual_interval = _residual_interval(trial)
    applied, rejected = adjustments["applied"], adjustments["rejected"]
    if rejected:
        result.unresolved.extend(f"解释项未被采纳：{item['reason']}" for item in rejected)
    if rejected and (applied or adjustments["basis_partitions"]):
        # 出现重复或覆盖交叉时保留已采纳记录供复核，但拒绝正式闭合，正式残差不采信调节。
        result.calculation["adjustment"] = {**adjustments, "closed": False}
        result.calculation_status = "unexplained_difference"
        result.unresolved.append("存在重复或覆盖交叉的解释项，本次不作正式闭合")
        result.calculation["residual_interval"] = residual_interval.as_dict()
        return result
    if applied:
        residual = Decimal(adjustments["remaining_residual"])
        remaining = adjustments["remaining_interval"]
        residual_interval = Interval(Decimal(remaining["low"]), Decimal(remaining["high"]),
            remaining["low_closed"], remaining["high_closed"])
    result.calculation["residual_interval"] = residual_interval.as_dict()
    # 残差区间含 0 只表示在与所述舍入及调节假设下相容，不代表解释真实或口径已支持。
    if applied and adjustments["interval_status"] != "known":
        result.calculation_status = "unexplained_difference"
        result.unresolved.append("调节额精度方法未声明，剩余残差区间不足以判定闭合")
    elif applied and residual_interval.contains_zero():
        result.calculation_status = "adjustment_explained"
        if residual_interval.as_dict()["low"] != residual_interval.as_dict()["high"]:
            result.unresolved.append("剩余残差仅区间含0，未排除舍入影响")
    elif applied:
        result.calculation_status = "unexplained_difference"
        result.unresolved.append(f"有依据调节后仍有未解释残差{text_number(residual)}")
    elif residual == 0:
        result.calculation_status = "consistent"
    elif trial.get("precision_compatible"):
        result.calculation_status = "precision_explained"
    else:
        result.calculation_status = "unexplained_difference"
        result.unresolved.append("同口径计算仍有未解释差额")
    return result


def _gated_calculation(check: RelationshipCheck, trial: dict) -> dict:
    """门禁输出：保留成员规范化值与算式，正式差额与正式残差字段置空。

    缺项直接从条件对象读取，不靠中文提示语反推。
    """
    unsupported = [item for item in check.conditions if item.status != "supported"]
    supported = [f"{item.name}：{item.reason}" for item in check.conditions if item.status == "supported"]
    return {"inputs": trial["inputs"], "expression": trial["expression"], "normalized_unit": trial.get("normalized_unit", ""),
            "left": trial.get("left"), "right": trial.get("right"), "residual": None, "residual_interval": None,
            "denominator_check": trial.get("denominator_check"),
            "formal_blocked": True,
            "gate": {"conclusion": "暂不能直接比较",
                     "missing": [item.name for item in unsupported] or ["关键前提未获支持"],
                     "conflicting": [item.name for item in unsupported if item.status == "conflicting"],
                     "supported_basis": supported,
                     "needed": "需补齐上述前提的原文依据后重新计算"}}


def _trial_calculation(trial: dict) -> dict:
    """假设试算独立存放，不占用正式差额字段，也不进入已衔接统计。"""
    return {"hypothetical": True,
            "assumptions": ["仅按已列成员做算术叠算", "未确认主体、期间、定义、范围与单位一致性"],
            "expression": trial["expression"], "residual": trial["residual"],
            "residual_interval": _residual_interval(trial).as_dict(),
            "left_interval": trial.get("left_interval"), "right_interval": trial.get("right_interval"),
            "positions": trial.get("positions", []), "normalized_unit": trial.get("normalized_unit", ""),
            "denominator_check": trial.get("denominator_check")}


def _residual_interval(trial: dict) -> Interval:
    """差额区间由两侧区间相减得到；多点位关系取各位置区间的包络，不伪造精确值。"""
    positions = trial.get("positions") or []
    if positions:
        intervals = [item.get("residual_interval") for item in positions if item.get("residual_interval")]
        if not intervals:
            # 无区间数据时标记为未知，不用点值冒充精确区间。
            value = Decimal(trial["residual"])
            return Interval(value, value, False, False)
        lows = [Decimal(item["low"]) for item in intervals]
        highs = [Decimal(item["high"]) for item in intervals]
        closed = all(item.get("low_closed") and item.get("high_closed") for item in intervals)
        return Interval(min(lows), max(highs), closed, closed)
    left = trial.get("left_interval") or {}
    right = trial.get("right_interval") or {}
    if not left or not right:
        value = Decimal(trial["residual"])
        return Interval(value, value, False, False)
    return Interval(Decimal(left["low"]), Decimal(left["high"]), left["low_closed"], left["high_closed"]).minus(
        Interval(Decimal(right["low"]), Decimal(right["high"]), right["low_closed"], right["high_closed"]))


def _amount_interval(amount: Decimal, factor: Decimal, rounding: str) -> tuple[Interval, str]:
    """调节额自身的精度区间：未声明舍入方法时不伪造区间。"""
    value = amount * factor
    if rounding == "exact":
        return Interval(value, value), "exact"
    if rounding == "half_up":
        precision = Decimal(1).scaleb(amount.as_tuple().exponent) * factor / 2
        return Interval(value - precision, value + precision), "known"
    return Interval(value, value, False, False), "unknown"


def _apply_adjustments(check: RelationshipCheck, trial: dict, found: dict[str, DisclosureOccurrence]) -> dict:
    """同基准加性调节：金额桥接才参与扣减，分组只登记为新基准。

    分组剔除后不得再从金额扣一次；重叠由原文依据判定，不是"声明即拒绝"。
    """
    applied, rejected, partitions = [], [], []
    base_dimension = next((item.get("dimension", "unknown") for item in trial.get("inputs", [])), "unknown")
    empty = {"applied": [], "rejected": [], "basis_partitions": [], "total": "0",
             "remaining_residual": trial["residual"], "remaining_interval": _residual_interval(trial).as_dict(),
             "interval_status": "known", "closed": False}
    if check.adjustments and check.operator not in {"equal", "sum"}:
        rejected.append({"adjustment_id": "*", "reason": "首版只支持同基准加性调节；比例与多位置关系需受控变换，暂未支持"})
        return {**empty, "rejected": rejected}
    if check.adjustments and base_dimension == "unknown":
        rejected.append({"adjustment_id": "*", "reason": "关系量纲尚未确定，不能登记金额调节"})
        return {**empty, "rejected": rejected}
    seen_effects: dict[str, str] = {}
    total = Decimal(0)
    total_interval = Interval(Decimal(0), Decimal(0))
    interval_status = "known"
    for item in check.adjustments:
        problems = []
        if not validate_refs(item.evidence, found):
            problems.append("调节缺少可在本次原文核实的出处")
        amount = None
        try:
            amount = number(item.amount)
        except ValueError:
            problems.append("调节额不是明确的十进制数")
        item_dimension, factor = numeric_unit(item.unit)
        if amount is not None and item_dimension != base_dimension:
            problems.append("调节额与关系量纲不一致")
        if item.effect_id in seen_effects:
            problems.append("同一解释效果不能在分组剔除后从金额中再次扣除")
        # 重叠须有互斥依据；仅当与本项已采纳的效果重叠时才拒绝叠加。
        if item.overlap_with:
            if not item.overlap_basis.strip():
                problems.append("声明与其它效果重叠，但未给出互斥依据")
            else:
                hits = [effect for effect in item.overlap_with if effect in seen_effects]
                if hits:
                    problems.append(f"与已采纳效果重叠：{'、'.join(hits)}，不能重复计入")
        if item.path == "grouping" and not item.basis_id.strip():
            problems.append("分组调节必须指明父基准（basis_id）")
        if problems:
            rejected.append({"adjustment_id": item.adjustment_id, "reason": "；".join(problems)})
            continue
        seen_effects[item.effect_id] = item.adjustment_id
        if item.path == "grouping":
            # 分组本身不扣减金额，只登记父基准下的新基准，供后续同基准关系使用。
            partitions.append({"adjustment_id": item.adjustment_id, "effect_id": item.effect_id, "label": item.label,
                               "parent_basis_id": item.basis_id, "metric_period": item.metric_period, "scope": item.scope,
                               "amount_not_deducted": item.amount, "unit": item.unit,
                               "overlap_basis": item.overlap_basis, "note": "分组不参与金额扣减，不重复计入差额"})
            continue
        signed = amount * factor if item.sign == "+" else -(amount * factor)
        amount_interval, status = _amount_interval(amount, factor, item.rounding)
        if item.sign == "-":
            amount_interval = Interval(-amount_interval.high, -amount_interval.low, amount_interval.high_closed, amount_interval.low_closed)
        if status == "unknown":
            interval_status = "unknown"
        total += signed
        total_interval = total_interval.plus(amount_interval)
        applied.append({"adjustment_id": item.adjustment_id, "effect_id": item.effect_id, "label": item.label,
                        "sign": item.sign, "amount": text_number(signed), "unit": trial.get("normalized_unit", ""),
                        "basis_id": item.basis_id, "path": item.path, "rounding": item.rounding,
                        "overlap_basis": item.overlap_basis, "note": item.note})
    remaining = Decimal(trial["residual"]) - total
    remaining_interval = _residual_interval(trial).minus(total_interval)
    return {"applied": applied, "rejected": rejected, "basis_partitions": partitions, "total": text_number(total),
            "remaining_residual": text_number(remaining),
            "remaining_interval": remaining_interval.as_dict(),
            "interval_status": interval_status,
            "closed": bool(applied) and not rejected and interval_status == "known" and remaining_interval.contains_zero(),
            "note": "分组只登记新基准不扣金额；金额桥接才参与抵扣；残差区间含0不证明解释真实"}


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
        # 分母相容区间逆推：由披露比例与分子区间反推分母区间，再与披露分母比较。
        implied = _implied_denominator(ni, ia)
        if implied is None:
            # 比例区间跨零（如披露 0%）时不逆推：给出空值，不让 None 继续参与运算。
            ratio_implied = {"implied": None, "disclosed": di.as_dict(), "compatible": None,
                             "note": "披露比例区间跨零，不逆推分母区间"}
        else:
            ratio_implied = {"implied": implied.as_dict(), "disclosed": di.as_dict(),
                             "compatible": bool(di.overlaps(implied)), "note": ""}
    elif check.operator == "occurrences":
        items = grouped["occurrence"]
        if len(items) < 2 or len({dim for _, dim, _ in items}) != 1:
            raise ValueError("多位置核对至少需要两处同量纲数值")
        a, da, ia = items[0]
        for value, _, interval in items[1:]:
            differences = ia.minus(interval)
            comparisons.append({"residual": text_number(a - value), "precision_compatible": ia.overlaps(interval),
                                "residual_interval": differences.as_dict()})
        b, _, ib = max(items[1:], key=lambda item: abs(a - item[0]))
        expression = "首处与每一已发现位置分别比较，保留全部差异"
    else:
        raise ValueError("不支持的数值算子")
    residual = a - b
    payload = {"inputs": inputs, "expression": expression, "left": text_number(a), "right": text_number(b),
            "normalized_unit": {"money": "元", "mass": "吨", "volume": "立方米", "people": "人", "ratio": "无量纲（1表示100%）", "electric_energy": "千瓦时", "heat_energy": "吉焦", "standard_coal": "吨标准煤", "co2e": "吨二氧化碳当量", "crude_steel_mass": "吨粗钢", "product_mass": "吨产品", "mass/money": "吨/元", "volume/money": "立方米/元"}.get(da, da),
            "residual": "0" if residual == 0 else text_number(residual),
            "precision_compatible": all(x["precision_compatible"] for x in comparisons) if comparisons else ia.overlaps(ib),
            "left_interval": ia.as_dict(), "right_interval": ib.as_dict(), "positions": comparisons}
    if check.operator == "ratio":
        payload["denominator_check"] = ratio_implied
    return payload


def _implied_denominator(numerator: Interval, ratio: Interval) -> Interval | None:
    """由 n 与披露比例的区间反推分母区间；比例区间跨零时不逆推，避免放大成无穷区间。"""
    if ratio.low <= 0 <= ratio.high:
        return None
    candidates = [numerator.low / ratio.low, numerator.low / ratio.high,
                  numerator.high / ratio.low, numerator.high / ratio.high]
    closed = numerator.low_closed and numerator.high_closed and ratio.low_closed and ratio.high_closed
    low, high = min(candidates), max(candidates)
    if low > high:
        low, high = high, low
    return Interval(low, high, closed, closed)
