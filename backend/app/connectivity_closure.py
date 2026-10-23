"""跨报告关系的「反事实闭合推演」：把"依据不足"变成可裁决的证据命题。

现有引擎在关键前提未获原文支持时 fail-closed，只产出 `unresolved` 中文本串与
`gate.missing` 条件名清单。对审计人员而言，"不可比"是一个死胡同：既不知道
差的是形式证据还是实质差异，也无法据以排班。本模块补上这一层，且不改动任何
正式结论字段：

1. `evidence_demands` —— 把每个未支持的前提翻译成有类型、有程序、有检索词项的
   取证需求（要什么、去哪找、找到后能支持哪一条前提）。
2. `closure_probe` —— 反事实上限：假定全部形式前提成立，再跑一次同一个确定性
   算式，看剩余差额。这是"纸面补齐后还会不会差钱"的唯一答案。
3. `single_point_probe` —— 单项补证效果：只补某一条前提，结论能到哪一级。
4. `attribution` —— 差额归因候选，逐项标注已证实/有依据/待核实，无量化边界时
   明确写"未量化"，不用模型自评冒充证据。
5. `summarize` —— 供概览、页面与导出共用的同源汇总。

硬约束（刻意如此设计）：
- 全部为纯函数，只读 `RelationshipCheck` 与 `DisclosureOccurrence`，不做 I/O，
  不调用模型，不产生新的证据。
- 推演结果写入独立的 `closure` 字段，绝不写入 `conclusion_level`、
  `calculation_status`、`criteria_status`、`adjustments`。
- 上限预测必须与正式结论同时展示，且带 `is_assumption` 标记；单独展示即为误导。
"""

from __future__ import annotations

import re
from decimal import Decimal

from .connectivity_engine import numeric_unit, validate_refs
from .connectivity_rules import required_conditions
from .connectivity_schemas import DisclosureOccurrence, RelationshipCheck

CLOSURE_VERSION = "connectivity_closure_v1"

# 每一个前提对应一条可执行取证程序。procedure 写给审计人员看，terms 给检索用。
CONDITION_SPECS: dict[str, dict] = {
    "主体": {
        "kind": "entity_identity",
        "procedure": "取得主体身份证明：报告封面、公司声明或附注中的公司全称与统一社会信用代码，确认两侧披露属同一法人主体",
        "terms": ["股份有限公司", "本公司", "公司名称", "统一社会信用代码"],
        "why": "主体不同则数值不可比，即使金额相等也不构成同一指标的一致",
    },
    "期间": {
        "kind": "period_attribution",
        "procedure": "取得指标所属期间归属：表头年度列、脚注或指标索引中注明本期/上期，确认成员数值均属同一会计期间",
        "terms": ["年度", "本期", "上年度", "单位："],
        "why": "期间错配产生的是伪差异，不能进入差额计算",
    },
    "定义": {
        "kind": "metric_definition",
        "procedure": "取得本指标的披露定义或计算口径原文：报表附注、ESG 指标索引或编制说明中对指标含义的界定",
        "terms": ["定义", "是指", "口径", "计算方法", "包括"],
        "why": "同名不同义是两个指标，定义未证实时不能假定可比",
    },
    "范围": {
        "kind": "scope_statement",
        "procedure": "取得本指标统计范围说明：合并范围/母公司/分部口径，以及该指标覆盖的主体与业务集合是否与对照指标一致",
        "terms": ["统计范围", "合并范围", "口径", "包含", "不包括", "涵盖"],
        "why": "范围差异是最常见的实质差异来源，报告级声明不能替代指标级边界",
    },
    "单位": {
        "kind": "unit_declaration",
        "procedure": "取得计量单位声明：表头单位行、表注或指标单位说明，确认换算系数与量纲",
        "terms": ["单位：", "万元", "元", "吨", "立方米"],
        "why": "单位未证实时的相等可能只是巧合，换算后可能相差数量级",
    },
    "组成完整": {
        "kind": "composition_coverage",
        "procedure": "取得分项覆盖完整性证据：合计项与全部分项在同一张表内闭合，并核对表外是否存在遗漏分项",
        "terms": ["合计", "其中", "小计", "总计"],
        "why": "分项不全时合计必然不等于分项之和，差额是构造性的而非披露错误",
    },
    "互不重叠": {
        "kind": "composition_exclusivity",
        "procedure": "取得分项互斥说明：确认各分项之间不存在交叉计数或重复归集",
        "terms": ["其中", "不含", "不包括", "扣除"],
        "why": "分项交叉会使分项之和大于合计，产生伪差异",
    },
    "公式": {
        "kind": "formula_statement",
        "procedure": "取得比例计算公式原文：明确分子、分母与计算基数，确认分母口径与所引指标一致",
        "terms": ["计算公式", "占", "比例", "除以"],
        "why": "分母口径不同会让比例差异失去解释意义",
    },
}

DEFAULT_SPEC = {
    "kind": "other_condition",
    "procedure": "取得该前提的原文依据后重新计算",
    "terms": ["口径", "说明"],
    "why": "该前提尚未获原文支持",
}

# 上限预测结局。is_assumption 恒为真：这是假设推演，不是结论。
# 映射直接读取引擎自身的结论阶梯（conclusion_level），不在此处重新推导一次判定；
# 否则会出现"引擎认为只是显示精度、推演却报实质差额"的口径分裂。
CONCLUSION_TO_CEILING = {
    "formal_consistent": ("would_confirm", "补齐纸面前提后算术语义一致（残差为零）"),
    "assumption_compatible": ("would_confirm_conditionally", "仅在显示精度或调节假设下相容，企业实际口径仍未证实"),
    "unexplained_difference": ("would_still_differ", "即使补齐全部纸面前提，仍存在未解释差额"),
    "insufficient_basis": ("not_executable", "补齐前提后算式仍不可执行"),
    "limited_support": ("limited_support", "补齐前提后也只能到有限支持，不足以形成正式结论"),
    "not_applicable": ("not_applicable", "叙述类关系不产生跨报告差额，不适用上限预测"),
    "not_assessed": ("not_executable", "补齐前提后仍未形成可读结论"),
}

TIER_LABELS = {
    "closed": "已闭合",
    "formal_gap": "形式证据缺口",
    "substantive_risk": "补齐纸面仍差钱",
    "blocked": "算式不可执行",
    "not_applicable": "不适用",
}

TIER_MEANING = {
    "closed": "正式结论为一致，差额已由确定性算式闭合",
    "formal_gap": "纸面前提补齐后可闭合或仅剩显示精度；当前阻挡来自证据形式而非数值本身",
    "substantive_risk": "即使补齐全部纸面前提仍有未解释差额；差额本身需要专业解释，补证无法消除",
    "blocked": "币种、量纲或约数使算式本身无法执行，补证不能解决，需先修数据",
    "not_applicable": "叙述类关系或多位置核对，不产生跨报告差额",
}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _metric_cores(members: list[DisclosureOccurrence]) -> list[str]:
    """成员行名去掉行次与括号单位后缀，得到可检索的指标核心词。"""
    cores: list[str] = []
    for row in members:
        label = re.sub(r"[（(][^）)]{0,12}[）)]\s*$", "", row.label or "")
        label = re.sub(r"^(?:其中|加：|减：|其中：)", "", _compact(label))
        label = re.sub(r"^\d+[、.．]", "", label)
        label = re.sub(r"(?:合计|小计|总计)$", "", label) or label
        if len(label) >= 2 and label not in cores:
            cores.append(label[:24])
    return cores[:4]


def _demand_terms(condition: str, members: list[DisclosureOccurrence], check: RelationshipCheck) -> list[str]:
    """检索词项 = 前提词 + 本关系指标核心词 + 年度 + 已登记边界。

    刻意不发散为近义词扩展：词项越宽，召回越多、可核验性越低。
    """
    spec = CONDITION_SPECS.get(condition, DEFAULT_SPEC)
    terms = list(spec["terms"])
    for core in _metric_cores(members):
        terms.append(core)
        terms.append(f"{core}{spec['terms'][0]}")
    years = sorted({row.year for row in members if row.year})
    for year in years[:2]:
        terms.append(f"{year}年")
    boundaries = {row.report_boundary for row in members if row.report_boundary not in {"", "unknown"}}
    for boundary in boundaries:
        terms.append({"consolidated": "合并", "parent": "母公司", "segment": "分部"}.get(boundary, boundary))
    seen: list[str] = []
    for term in terms:
        if term and term not in seen:
            seen.append(term)
    return seen[:14]


def _condition_blockers(check: RelationshipCheck) -> list[str]:
    """未获支持的必要前提名，按规则顺序排列，保证同一输入输出稳定。"""
    status = {item.name: item.status for item in check.conditions}
    return [name for name in required_conditions(check.operator) if status.get(name) != "supported"]


def evidence_demands(check: RelationshipCheck, occurrences: list[DisclosureOccurrence]) -> list[dict]:
    """把未支持的前提翻译成有类型、有程序、有检索词项的取证需求。

    叙述类关系不产生跨报告差额，其"未决"不是取证缺口，因此不生成需求清单，
    免得把文字核对也塞进工单里稀释重点。
    """
    if check.operator == "narrative":
        return []
    found = {row.occurrence_id: row for row in occurrences}
    members = [found[item.occurrence_id] for item in check.members if item.occurrence_id in found]
    conditions = {item.name: item for item in check.conditions}
    demands: list[dict] = []
    for name in required_conditions(check.operator):
        condition = conditions.get(name)
        if condition is not None and condition.status == "supported":
            continue
        spec = CONDITION_SPECS.get(name, DEFAULT_SPEC)
        demands.append({
            "demand_id": f"{check.check_id}::{spec['kind']}",
            "condition": name,
            "kind": spec["kind"],
            "status": condition.status if condition is not None else "missing",
            "evidence_kind": condition.evidence_kind if condition is not None else "unspecified",
            "current_reason": condition.reason if condition is not None else "本次运行未登记该前提",
            "procedure": spec["procedure"],
            "why": spec["why"],
            "search_terms": _demand_terms(name, members, check),
            "blocks_formal": True,
        })
    return demands


def structural_gaps(check: RelationshipCheck) -> list[str]:
    """不属于单项前提的未决事项：关系依据、跨报告、币种等关系级缺口。

    单独登记的理由：这些缺口不是"补一份定义"能解决的，混进前提清单会让审计人员
    误以为补证一定能让结论升级。
    """
    names = {item.name for item in check.conditions} | set(required_conditions(check.operator))
    gaps: list[str] = []
    for text in check.unresolved:
        stripped = (text or "").strip()
        if not stripped:
            continue
        if any(stripped.startswith(f"{name}依据尚未充分说明") or stripped.startswith(f"{name}存在明确冲突")
               for name in names):
            continue
        gaps.append(stripped)
    return gaps


def _decimal_text(value) -> str | None:
    if value is None:
        return None
    try:
        return format(Decimal(str(value)), "f")
    except (ArithmeticError, ValueError):
        return str(value)


def closure_probe(check: RelationshipCheck, occurrences: list[DisclosureOccurrence]) -> dict:
    """反事实上限：假定全部形式前提成立后，同一个确定性算式会得到什么。

    这是本模块最关键的一条：它把"依据不足"拆成"补纸面就能闭合"与"补纸面也差钱"
    两类，后者才是审计资源该去的地方。结局直接读引擎的 conclusion_level。
    """
    base = {"is_assumption": True, "version": CLOSURE_VERSION,
            "note": "上限预测：假定全部形式前提均已取得原文支持后的算术结局，不是结论，也不是证据"}
    if check.operator == "narrative" or check.calculation_status == "not_applicable":
        return {**base, "status": "not_applicable", "label": "叙述类关系不产生跨报告差额，不适用上限预测", "residual": None}
    if check.criteria_status == "conflicting":
        return {**base, "status": "conflicting", "label": "前提存在明确冲突；补证不能把冲突改写成闭合",
                "residual": None, "conflicts": [item.name for item in check.conditions if item.status == "conflicting"]}
    try:
        probe = calculate_with_gaps_ignored(check, occurrences)
    except (ValueError, ArithmeticError, AttributeError, KeyError, IndexError, TypeError) as error:
        return {**base, "status": "not_executable", "label": f"补齐前提后仍不可计算：{type(error).__name__}",
                "residual": None, "real_unresolved_count": len(check.unresolved)}
    status, label = CONCLUSION_TO_CEILING.get(probe.conclusion_level, ("not_executable", "补齐前提后仍不可计算"))
    calculation = probe.calculation or {}
    residual = calculation.get("residual")
    interval = calculation.get("residual_interval") or None
    # 显示精度以推演自身的试算为准（它在同一次调用里刚算过），
    # 不用正式结果里的旧值，避免两处口径分裂。
    assumption = calculation.get("assumption_check") or {}
    if not assumption:
        assumption = ((check.comparability or {}).get("numeric") or {}).get("assumption_check") or {}
    if probe.calculation_status == "adjustment_explained":
        status, label = "would_close_by_adjustment", "需借助有依据的调节项才能闭合，调节本身仍是待证主张"
    return {
        **base,
        "status": status,
        "label": label,
        "residual": _decimal_text(residual),
        "residual_interval": interval,
        "normalized_unit": calculation.get("normalized_unit", ""),
        "expression": calculation.get("expression", ""),
        "conclusion_level_after": probe.conclusion_level,
        "calculation_status_after": probe.calculation_status,
        "precision_assumption": assumption.get("status", "not_run"),
        "precision_interval": assumption.get("residual_interval"),
        "precision_excludes_zero": ((interval or {}).get("contains_zero") is False),
        "real_unresolved_count": len(check.unresolved),
    }


def calculate_with_gaps_ignored(check: RelationshipCheck, occurrences: list[DisclosureOccurrence]) -> RelationshipCheck:
    """调用引擎的反事实开关；单独包裹以便测试替换与异常收敛。"""
    from .connectivity_engine import calculate

    return calculate(check, occurrences, disregard_gaps=True)


def single_point_probe(check: RelationshipCheck, occurrences: list[DisclosureOccurrence],
                       demands: list[dict], limit: int = 6) -> list[dict]:
    """只补某一条前提时结论能到哪一级；`sufficient_alone` 表示仅此一项即可升级为正式。

    这不是"分重要性排序"，而是可复现的因果读数：假设 A 成立、其余不变，闸门是否打开。
    """
    from .connectivity_engine import calculate

    results: list[dict] = []
    for demand in demands[:limit]:
        name = demand["condition"]
        try:
            probe = calculate(check, occurrences, assume_supported={name})
        except (ValueError, ArithmeticError, AttributeError, KeyError, IndexError, TypeError):
            continue
        results.append({
            "condition": name,
            "sufficient_alone": probe.criteria_status == "supported",
            "criteria_after": probe.criteria_status,
            "conclusion_after": probe.conclusion_level,
            "calculation_after": probe.calculation_status,
        })
    return results


PARENT_WORDS = ("本公司", "母公司", "个别报表", "母公司口径")
CONSOLIDATED_WORDS = ("本集团", "合并", "集团口径", "合并口径")


def _label_boundary(row: DisclosureOccurrence) -> str:
    """行名与表内分组里直接写明的报告边界。只看行名，不扫正文，避免误伤。"""
    text = _compact(" ".join([row.label or "", row.row_header or "", row.table_scope or ""]))
    if any(word in text for word in PARENT_WORDS):
        return "parent"
    if any(word in text for word in CONSOLIDATED_WORDS):
        return "consolidated"
    return "unknown"


def _boundary_name(value: str) -> str:
    return {"parent": "母公司/本公司", "consolidated": "合并/本集团", "segment": "分部"}.get(value, value or "未写明")


def _normalized_values(members: list[DisclosureOccurrence]) -> list[tuple[DisclosureOccurrence, Decimal]]:
    from .connectivity_engine import normalized

    values: list[tuple[DisclosureOccurrence, Decimal]] = []
    for row in members:
        try:
            value, _, _ = normalized(row)
        except (ValueError, ArithmeticError):
            continue
        values.append((row, value))
    return values


def _page_boundary_hypothesis(members: list[DisclosureOccurrence]) -> dict | None:
    """同一文档、相邻不同页、较小值约为较大值的 20%–70%：与合并/母公司并列披露的特征一致。

    这只能是待核实假设，不是结论：真正的合并/母公司判断需要报表标题原文。
    比例区间取得宽，是为了减少漏报；因此状态固定为 pending，绝不写成 confirmed。
    """
    if len(members) < 2 or len({row.document_id for row in members}) != 1:
        return None
    if len({row.pdf_page for row in members}) < 2:
        return None
    values = _normalized_values(members)
    if len(values) < 2:
        return None
    ordered = sorted(values, key=lambda item: abs(item[1]))
    small, large = ordered[0], ordered[-1]
    if large[1] == 0:
        return None
    ratio = abs(small[1]) / abs(large[1])
    if not (Decimal("0.2") <= ratio <= Decimal("0.7")):
        return None
    return {"ratio": format(ratio, ".3f"),
            "detail": (f"两处披露分别在第{small[0].pdf_page}页与第{large[0].pdf_page}页，"
                       f"较小值约为较大值的 {ratio * 100:.1f}%，与合并/母公司并列披露的特征一致；"
                       f"需核对两页表标题分别属于合并报表还是母公司报表，未能取得标题前不作结论")}


def _outlier_member(members: list[DisclosureOccurrence]) -> dict | None:
    """三处以上同名披露中，若某一成员与最大成员相差两个数量级以上，提示成员错绑。"""
    if len(members) < 3:
        return None
    values = [(row, abs(value)) for row, value in _normalized_values(members) if value != 0]
    if len(values) < 3:
        return None
    values.sort(key=lambda item: item[1])
    smallest, largest = values[0], values[-1]
    if largest[1] == 0:
        return None
    ratio = smallest[1] / largest[1]
    if ratio > Decimal("0.01"):
        return None
    return {"ratio": format(ratio, ".6f"),
            "detail": (f"第{smallest[0].pdf_page}页成员（{smallest[0].label}）仅为最大成员的 {ratio * 100:.3f}%，"
                       f"疑似从其他行或分期列错误绑定；需回原页核对行列坐标")}


def attribution(check: RelationshipCheck, occurrences: list[DisclosureOccurrence]) -> list[dict]:
    """差额归因候选：逐项标注已证实/有依据/待核实/已排除，并说明是否量化。

    刻意不做"原因概率排序"：没有可核验依据的概率只是把模型的猜测写成数字。
    """
    found = {row.occurrence_id: row for row in occurrences}
    members = [found[item.occurrence_id] for item in check.members if item.occurrence_id in found]
    comparability = check.comparability or {}
    calculation = check.calculation or {}
    conditions = {item.name: item for item in check.conditions}
    items: list[dict] = []

    assumption = (comparability.get("numeric") or {}).get("assumption_check") or calculation.get("assumption_check") or {}
    rounding_status = assumption.get("status", "not_run")
    if rounding_status == "contains_zero":
        items.append({"mechanism": "rounding", "label": "显示精度（四舍五入）", "status": "supported",
                      "detail": "在显示小数位假设下残差区间含零", "quantified": True,
                      "bound": assumption.get("residual_interval")})
    elif rounding_status == "not_contains_zero":
        items.append({"mechanism": "rounding", "label": "显示精度（四舍五入）", "status": "excluded",
                      "detail": "显示精度区间不足以解释差额", "quantified": True,
                      "bound": assumption.get("residual_interval")})
    else:
        items.append({"mechanism": "rounding", "label": "显示精度（四舍五入）", "status": "pending",
                      "detail": assumption.get("reason") or "未执行显示精度试算", "quantified": False, "bound": None})

    factors = []
    for row in members:
        try:
            dimension, factor = numeric_unit(row.unit)
            factors.append((row.unit, dimension, factor))
        except (ValueError, AttributeError):
            factors.append((row.unit, "unknown", None))
    distinct = {factor for _, _, factor in factors if factor is not None}
    if any(item[2] is None for item in factors):
        items.append({"mechanism": "unit", "label": "计量单位换算", "status": "pending",
                      "detail": "存在单位未确定或量纲不可识别的成员", "quantified": False, "bound": None})
    elif len(distinct) > 1:
        items.append({"mechanism": "unit", "label": "计量单位换算", "status": "confirmed",
                      "detail": f"单位量纲不同，已按 {'、'.join(sorted({item[0] for item in factors}))} 换算后比较",
                      "quantified": True, "bound": calculation.get("normalized_unit")})
    else:
        items.append({"mechanism": "unit", "label": "计量单位换算", "status": "excluded",
                      "detail": f"成员单位同量纲（{factors[0][0] if factors else '未知'}），换算不产生差额",
                      "quantified": True, "bound": calculation.get("normalized_unit")})

    years = (comparability.get("period") or {}).get("years") or []
    if len(years) > 1:
        items.append({"mechanism": "period", "label": "期间归属", "status": "confirmed",
                      "detail": f"成员明确属于不同期间：{'、'.join(str(y) for y in sorted(years))}", "quantified": False, "bound": None})
    else:
        items.append({"mechanism": "period", "label": "期间归属", "status": "excluded",
                      "detail": f"成员期间归属一致（{years[0] if years else '未登记'}）", "quantified": False, "bound": None})

    boundary = comparability.get("boundary") or {}
    label_boundaries = {row.occurrence_id: _label_boundary(row) for row in members}
    stated = {value for value in label_boundaries.values() if value != "unknown"}
    if len(stated) > 1:
        # 行名自带主体限定词，是可直接回查的证据，不再只是"可能不同口径"。
        detail = "；".join(f"{row.label or row.occurrence_id}→{_boundary_name(label_boundaries[row.occurrence_id])}"
                           for row in members)
        items.append({"mechanism": "boundary", "label": "报告边界（合并/母公司/分部）", "status": "confirmed",
                      "detail": f"成员行名分别标明主体边界：{detail}", "quantified": False, "bound": None})
    elif boundary.get("status") in {"different", "undetermined"}:
        items.append({"mechanism": "boundary", "label": "报告边界（合并/母公司/分部）", "status": "supported",
                      "detail": boundary.get("message") or "报告边界不一致或未证实", "quantified": False, "bound": None})
    elif boundary.get("table_scopes"):
        items.append({"mechanism": "table_scope", "label": "表内分组口径", "status": "supported",
                      "detail": f"成员来自不同表内分组：{'、'.join(boundary['table_scopes'])}", "quantified": False, "bound": None})
    else:
        hypothesis = _page_boundary_hypothesis(members)
        if hypothesis:
            items.append({"mechanism": "boundary", "label": "报告边界（合并/母公司/分部）", "status": "pending",
                          "detail": hypothesis["detail"], "quantified": True, "bound": hypothesis["ratio"]})
        else:
            items.append({"mechanism": "boundary", "label": "报告边界（合并/母公司/分部）", "status": "excluded",
                          "detail": boundary.get("message") or "报告边界一致", "quantified": False, "bound": None})

    for name, mechanism, label in (("定义", "definition", "指标定义"), ("范围", "scope", "指标统计范围")):
        condition = conditions.get(name)
        status = condition.status if condition is not None else "missing"
        items.append({
            "mechanism": mechanism, "label": label,
            "status": "pending" if status in {"unknown", "missing"} else "excluded" if status == "supported" else "supported",
            "detail": condition.reason if condition is not None else "本次运行未登记该前提",
            "quantified": False, "bound": None,
        })

    bounded = [row.label for row in members if row.value_qualifier in {"approximate", "lower_bound", "upper_bound"}]
    if bounded:
        items.append({"mechanism": "data_quality", "label": "数据质量（约数/上下界）", "status": "confirmed",
                      "detail": f"成员为约数或上下界：{'、'.join(bounded[:3])}", "quantified": False, "bound": None})
    else:
        outlier = _outlier_member(members)
        if outlier:
            items.append({"mechanism": "data_quality", "label": "数据质量（成员错绑）", "status": "pending",
                          "detail": outlier["detail"], "quantified": True, "bound": outlier["ratio"]})
        else:
            items.append({"mechanism": "data_quality", "label": "数据质量（约数/上下界）", "status": "excluded",
                          "detail": "成员均为精确点值，量级无异常离群", "quantified": False, "bound": None})

    if check.relationship_basis != "text_statement":
        items.append({"mechanism": "relationship", "label": "关系依据本身", "status": "pending",
                      "detail": f"关系由 {check.relationship_basis} 得到，尚缺原文对两者关系本身的说明",
                      "quantified": False, "bound": None})
    return items


def _tier(check: RelationshipCheck, ceiling: dict, demands: list[dict]) -> str:
    if check.operator == "narrative" or check.calculation_status == "not_applicable":
        return "not_applicable"
    if check.conclusion_level == "formal_consistent" and check.criteria_status == "supported":
        return "closed"
    status = ceiling.get("status")
    if status in {"not_executable", "conflicting"}:
        return "blocked"
    if status == "would_still_differ":
        # 引擎判定"未解释"是严格口径：企业未声明舍入方法时，点值差额一律算未解释。
        # 但如果显示精度区间本身已覆盖差额，把这条报成实质差异就是假警报，
        # 因此降级为形式缺口，并在 tier_reason 里写明降级依据。
        if ceiling.get("precision_assumption") == "contains_zero":
            return "formal_gap"
        return "substantive_risk"
    if status in {"would_confirm", "would_confirm_conditionally", "would_close_by_adjustment"}:
        return "formal_gap"
    if status == "limited_support":
        return "formal_gap"
    return "blocked"


def _tier_reason(tier: str, ceiling: dict, scope: str) -> str:
    if tier == "substantive_risk":
        return ("同报告内两处披露在补齐口径依据后仍不一致：优先核对是否口径不同（如营业总收入与营业收入），"
                "其次判断是否披露不一致" if scope == "same_document"
                else "跨报告在补齐口径依据后仍有未解释差额")
    if tier == "formal_gap" and ceiling.get("status") == "would_still_differ":
        return "差额落在显示精度区间内，属于企业未声明舍入方法；补齐口径依据后可按精度相容处理"
    if tier == "formal_gap":
        return "差额本身可闭合，当前阻挡来自前提缺原文支持"
    if tier == "blocked":
        return "算术无法执行，补证不解决问题，需先修数据或单位"
    if tier == "closed":
        return "已由确定性算式闭合"
    return "不产生跨报告差额"


def build_closure(check: RelationshipCheck, occurrences: list[DisclosureOccurrence], *,
                  sensitivity_limit: int = 6) -> dict:
    """组装单条关系的闭合推演块。只读，不改写任何正式结论字段。"""
    demands = evidence_demands(check, occurrences)
    ceiling = closure_probe(check, occurrences)
    gaps = structural_gaps(check)
    tier = _tier(check, ceiling, demands)
    single = single_point_probe(check, occurrences, demands, limit=sensitivity_limit) if demands else []
    scope = "cross_document" if check.cross_document else "same_document"
    label = TIER_LABELS[tier]
    if tier == "substantive_risk":
        label = "同报告内两处披露仍不一致" if scope == "same_document" else "跨报告仍存在未解释差额"
    causes = attribution(check, occurrences)
    # 首选归因按"能否定位到原文"排优先级：边界与错绑能直接回到页码/行名，
    # 定义与范围只能回到一段说明，期间是硬冲突。显示精度不参与，它在任何算子下
    # 都可能 pending，若参与会顶掉真正的具体原因。
    priority = ["boundary", "table_scope", "data_quality", "period", "definition", "scope"]
    by_mechanism = {item["mechanism"]: item for item in causes}
    leading = None
    for statuses in ({"confirmed", "supported"}, {"pending"}):
        leading = next((by_mechanism[name] for name in priority
                        if name in by_mechanism and by_mechanism[name]["status"] in statuses), None)
        if leading:
            break
    return {
        "version": CLOSURE_VERSION,
        "tier": tier,
        "tier_label": label,
        "tier_meaning": TIER_MEANING[tier],
        "tier_reason": _tier_reason(tier, ceiling, scope),
        # 归因首选：只在有原文或坐标依据时给出，待核实项明确标 pending。
        "leading_hypothesis": ({"mechanism": leading["mechanism"], "label": leading["label"],
                                "status": leading["status"], "detail": leading["detail"]} if leading else None),
        # 同报告内多位置差额与跨报告差额性质不同：前者首先提示口径差异或披露不一致，
        # 后者才是跨报告衔接问题。合并成一个数字会让读者误判风险来源。
        "relation_scope": scope,
        "relation_scope_note": ("跨报告关系：差额指向两份报告之间的口径或披露差异" if scope == "cross_document"
                                else "同报告内多位置关系：差额首先提示同报告内口径不同或披露不一致，不是跨报告矛盾"),
        "current": {
            "criteria_status": check.criteria_status,
            "conclusion_level": check.conclusion_level,
            "calculation_status": check.calculation_status,
            "basis_level": check.basis_level,
        },
        "ceiling": ceiling,
        "demands": demands,
        "demand_count": len(demands),
        "structural_gaps": gaps,
        "single_point": single,
        "single_point_only": sum(1 for item in single if item["sufficient_alone"]) if single else 0,
        "attribution": causes,
        "reading_order": [
            "先看 ceiling：纸面补齐后是否仍差钱",
            "再看 demands：缺哪几条、每条对应什么取证程序",
            "最后看 structural_gaps：这些不是补一份定义能解决的",
        ],
    }


def attach(check: RelationshipCheck, occurrences: list[DisclosureOccurrence], *,
           sensitivity_limit: int = 6) -> RelationshipCheck:
    """返回带 closure 的关系副本；正式结论字段逐字段保持不变。"""
    result = check.model_copy(deep=True)
    result.closure = build_closure(check, occurrences, sensitivity_limit=sensitivity_limit)
    return result


def summarize(checks: list[RelationshipCheck]) -> dict:
    """概览、页面与导出共用的同源汇总。分母一律写清，不合成任何综合分数。"""
    tiers: dict[str, list[str]] = {key: [] for key in TIER_LABELS}
    ceilings: dict[str, int] = {}
    demand_by_condition: dict[str, int] = {}
    scope_split = {"cross_document": 0, "same_document": 0}
    gap_total = 0
    for check in checks:
        block = check.closure or {}
        tier = block.get("tier") or "not_applicable"
        tiers.setdefault(tier, []).append(check.check_id)
        status = (block.get("ceiling") or {}).get("status") or "unknown"
        ceilings[status] = ceilings.get(status, 0) + 1
        if tier == "substantive_risk":
            scope_split["cross_document" if check.cross_document else "same_document"] += 1
        for demand in block.get("demands") or []:
            demand_by_condition[demand["condition"]] = demand_by_condition.get(demand["condition"], 0) + 1
        gap_total += len(block.get("structural_gaps") or [])
    total = len(checks)
    substantive = tiers.get("substantive_risk") or []
    formal = tiers.get("formal_gap") or []
    split_note = (f"其中跨报告 {scope_split['cross_document']} 条、同报告内多位置 {scope_split['same_document']} 条"
                  if substantive else "")
    return {
        "version": CLOSURE_VERSION,
        "relation_total": total,
        "tiers": {key: {"count": len(ids), "check_ids": ids} for key, ids in tiers.items()},
        "ceiling_status": ceilings,
        "open_demand_by_condition": dict(sorted(demand_by_condition.items(), key=lambda item: -item[1])),
        "structural_gap_total": gap_total,
        "substantive_risk_count": len(substantive),
        "substantive_risk_scope": scope_split,
        "formal_gap_count": len(formal),
        "blocked_count": len(tiers.get("blocked") or []),
        "statement": (
            f"{total} 条关系中，{len(tiers.get('closed') or [])} 条已闭合；"
            f"{len(substantive)} 条即使补齐全部纸面前提仍存在未解释差额{split_note}；"
            f"{len(formal)} 条只缺形式证据；"
            f"{len(tiers.get('blocked') or [])} 条算式不可执行"
        ),
        "note": "分档来自确定性反事实推演，不读取模型意见；上限预测不是结论",
    }
