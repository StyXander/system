"""AI 主张的证据账本：把数字、列语义、年份和派生算式拆开核验。

这里是纯确定性代码，不调用模型，也不修改程序计算状态。账本只回答三件事：
这条主张引用了哪一处原文、该处原文能否支持这个含义、派生数字能否由算式复算。
它不能证明企业披露真实，也不能替代人工复核。

证据状态的阅读边界：
有据支持只指绑定原文或已复算公式支持当前主张。
它不证明企业披露真实，也不代表专业人员已经采纳。
明确矛盾需要能够指出具体原文、列义或公式冲突。
依据不足说明主张尚缺材料，不能当作主张错误。
未核验保留无法由当前规则判定的文字语义。
变动比例列与本期数值列使用不同的语义身份。
某个数值出现在引用中，不等于支持对它的业务解释。
同比、占比与强度都需要各自的分母或比较基准。
派生数字需要明确算式，不能仅靠数字同时出现。
算式复算成功也不能替代主体与统计范围检查。
计划、目标与承诺不能直接改写成已经实现的成果。
解释假设需要记录支持证据与相反证据。
没有搜到反证不能使解释自动变成已证实。
已反驳解释继续保留，避免后续阶段无痕重新采用。
主张账本既保存接受记录，也保存因矛盾拒绝的记录。
质量标签描述论证完整度，不是模型正确概率。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import re

from .connectivity_engine import number, normalized, numeric_unit, text_number, validate_refs

CLAIM_LEDGER_VERSION = "claim_ledger_v1"
CLAIM_SEMANTICS = (
    "period_value", "change_ratio", "yoy", "share", "intensity", "ratio",
    "multi_year_ambiguous", "count", "unknown",
)

#: 变动/同比列不是年度值；这些词必须先于“比例”判断，否则 0.66% 会被误当成年度占比。
#: 列头优先于行名：同一行可能同时出现“2025 年、2024 年、变动比例”三列，
#: 只有列头的“变动比例”能决定 0.66% 的语义，行名里的“占比”不能反推年度值。
CHANGE_PATTERN = re.compile(r"变动(?:比例|幅度|率)|同比|环比|增减(?:幅度|比例)|较上(?:年|期).{0,12}(?:增长|下降|增加|减少)")
INTENSITY_PATTERN = re.compile(r"强度|单位(?:产品|产量|营收|收入|能耗|排放)|每(?:吨|万元|人|立方米)")
SHARE_PATTERN = re.compile(r"占比|比重|占.{2,24}(?:比例|比重)|结构比例")
RATIO_PATTERN = re.compile(r"比例|比率|率$")
PERIOD_PATTERN = re.compile(r"(?:19|20)\d{2}\s*年|本期|本年|当期|期末|年末")
MULTI_YEAR_PATTERN = re.compile(r"(?:19|20)\d{2}\s*年.*(?:19|20)\d{2}\s*年")
COUNT_SUFFIX = re.compile(r"^\s*(?:处|项|条|个|份|页|批|家|次|名|类)")
YEAR_TOKEN = re.compile(r"(?:19|20)\d{2}")
NUMBER_TOKEN = re.compile(r"[-−+]?\d[\d,，]*(?:\.\d+)?%?")
YEAR_ASSERTION = re.compile(r"((?:19|20)\d{2})\s*年(?:度)?")
MATERIAL_UNIT = re.compile(r"(?:元|万元|亿元|百万元|千元|吨|万吨|立方米|人|千瓦时|吉焦|吨标准煤|二氧化碳当量)")

#: 公式必须显式写出运算符和等号，才允许把派生值当作可复核结果。
#: 同时接受“0.0644 由 26.12÷405.29 得出”这种中文表达；
#: 只有数字并列而没有运算符或“得出/等于”的句子不能当成算式。
FORMULA_PATTERNS = (
    re.compile(r"(?P<a>\d[\d,]*(?:\.\d+)?)\s*(?P<au>%?)\s*(?P<op>[÷/×*+\-−])\s*"
               r"(?P<b>\d[\d,]*(?:\.\d+)?)\s*(?P<bu>%?)\s*[=＝]\s*"
               r"(?P<c>\d[\d,]*(?:\.\d+)?)\s*(?P<cu>%?)"),
    re.compile(r"(?P<c>\d[\d,]*(?:\.\d+)?)\s*(?P<cu>%?)\s*[=＝]\s*"
               r"(?P<a>\d[\d,]*(?:\.\d+)?)\s*(?P<au>%?)\s*(?P<op>[÷/×*+\-−])\s*"
               r"(?P<b>\d[\d,]*(?:\.\d+)?)\s*(?P<bu>%?)"),
    re.compile(r"\(\s*(?P<a>\d[\d,]*(?:\.\d+)?)\s*[-−]\s*(?P<b>\d[\d,]*(?:\.\d+)?)\s*\)\s*"
               r"[÷/]\s*(?P<b2>\d[\d,]*(?:\.\d+)?)\s*(?P<bu>%?)\s*[=＝]\s*"
               r"(?P<c>\d[\d,]*(?:\.\d+)?)\s*(?P<cu>%?)"),
    re.compile(r"(?P<c>\d[\d,]*(?:\.\d+)?)\s*(?P<cu>%?)\s*(?:由|来自)\s*"
               r"(?P<a>\d[\d,]*(?:\.\d+)?)\s*(?P<au>%?)\s*(?P<op>÷|/|除以)\s*"
               r"(?P<b>\d[\d,]*(?:\.\d+)?)\s*(?P<bu>%?)\s*(?:得出|得到|计算)"),
    re.compile(r"(?P<a>\d[\d,]*(?:\.\d+)?)\s*(?P<au>%?)\s*(?P<op>÷|/|除以)\s*"
               r"(?P<b>\d[\d,]*(?:\.\d+)?)\s*(?P<bu>%?)\s*(?:得出|得到|等于|为)\s*"
               r"(?P<c>\d[\d,]*(?:\.\d+)?)\s*(?P<cu>%?)"),
)

NEXT_EVIDENCE = {
    "主体": ("补齐报告封面或“报告范围”页中载明公司全称的原文，确认两处属于同一会计主体", "报告封面/报告范围", "L0"),
    "期间": ("补齐表头年度列或“报告期间”说明，确认两处披露均属于同一比较期间", "表头年度列/报告期间说明", "L0"),
    "定义": ("补齐该指标的定义句或附注（如“研发投入包括……”“环保投入是指……”）", "指标定义/附注", "L1"),
    "范围": ("补齐与本指标同段的统计范围、合并范围或组织边界说明，不能用报告总体范围代替", "指标统计范围/合并范围", "L1"),
    "单位": ("补齐表头单位行、脚注和币种说明，并保留原始值与归一化值", "表头单位/币种脚注", "L0"),
    "组成完整": ("补齐该合计的完整分项清单，或说明“其他”项包含哪些内容", "合计行/分项表", "L1"),
    "互不重叠": ("补充分项是否互斥、是否重复计入的原文说明", "附注/表下注释", "L1"),
    "公式": ("补充分母定义、分母数值和公式说明，确认披露比例与分子分母同口径", "指标定义/分母披露", "L1"),
}

COUNTER_QUERY = {
    "主体": "母公司 合并 范围 不同 口径",
    "期间": "重述 更正 上期 本期 期间 不同",
    "定义": "不包括 仅包括 口径 定义 例外",
    "范围": "不包括 未纳入 母公司 合并范围 组织边界 例外",
    "单位": "千元 万元 亿元 单位 脚注 换算",
    "组成完整": "其他 未列示 分项 合计 不完整",
    "互不重叠": "重复 包含 重叠 其中 已计入",
    "公式": "分母 调整 口径 不一致 非营业收入",
}


def _compact(text: str) -> str:
    """去掉空白，只用于词形命中；引用核验仍用原文。"""
    return re.sub(r"\s+", "", str(text or ""))


def _row_text(row) -> str:
    """列语义同时看列头、行名和上下文，但以列头为最高优先级。"""
    return " ".join(str(getattr(row, name, "") or "") for name in ("column_header", "label", "row_header"))


def classify_column_semantics(row) -> str:
    """识别一条披露值所在列的含义，优先拒绝“变动比例=年度值”的误读。"""
    header = str(getattr(row, "column_header", "") or "")
    text = _row_text(row)
    years = set(YEAR_TOKEN.findall(header))
    if CHANGE_PATTERN.search(text):
        return "change_ratio" if ("变动" in text or "增减" in text) else "yoy"
    if len(years) > 1:
        return "multi_year_ambiguous"
    if INTENSITY_PATTERN.search(text):
        return "intensity"
    if SHARE_PATTERN.search(text):
        return "share"
    if RATIO_PATTERN.search(text):
        return "ratio"
    year_status = str(getattr(row, "year_status", "") or "")
    if years or PERIOD_PATTERN.search(header) or (year_status == "attributed" and getattr(row, "year", "")):
        return "period_value"
    if str(getattr(row, "unit", "") or "").strip() == "人":
        return "count"
    return "unknown"


def semantic_problem(row) -> str:
    """数值关系不能把变动列、多年混列或占比列当作同年绝对值。"""
    semantics = classify_column_semantics(row)
    if semantics in {"change_ratio", "yoy"}:
        return "该值位于变动/同比列，不是本期或上期的年度值"
    if semantics == "multi_year_ambiguous":
        return "列头同时含多个年度，无法确定该值属于哪一期"
    if semantics in {"share", "intensity"} and numeric_unit(getattr(row, "unit", ""))[0] != "ratio":
        return "该值是占比或强度，不能当作绝对金额或数量"
    return ""


def _token_value(token: str) -> Decimal | None:
    """把带百分号或千分位的文本还原为 Decimal；空值不返回零。"""
    try:
        cleaned = str(token).replace(",", "").replace("，", "").replace("−", "-").rstrip("%")
        return number(cleaned)
    except (ValueError, InvalidOperation):
        return None


def _token_spans(text: str) -> list[tuple[int, int, str]]:
    return [(match.start(), match.end(), match.group()) for match in NUMBER_TOKEN.finditer(text)]


def _is_year(token: str, text: str, start: int, end: int) -> bool:
    """年份是期间断言，不按金额或比例参与“无来源数字”判断。"""
    return bool(YEAR_TOKEN.fullmatch(token.replace(",", "").replace("，", ""))) and bool(
        re.match(r"\s*年", text[end:end + 3])
    )


def _is_material(token: str, text: str, start: int, end: int) -> bool:
    """小整数和处数属于过程统计；带单位、小数、百分号或大额才是业务数值。"""
    stripped = token.replace(",", "").replace("，", "").replace("−", "-")
    if _is_year(token, text, start, end):
        return False
    if COUNT_SUFFIX.match(text[end:end + 2]) and "." not in stripped.rstrip("%"):
        return False
    if "%" in token or "." in stripped:
        return True
    if MATERIAL_UNIT.match(text[end:end + 12]):
        return True
    try:
        return abs(Decimal(stripped)) >= 1000
    except InvalidOperation:
        return False


def _collect_numbers(value, output: set[Decimal], key: str = "") -> None:
    """把程序计算中的派生值加入允许集合，避免把已验证结果误报为编造。"""
    keys = {"left", "right", "residual", "original_residual", "remaining_residual", "contribution",
            "current", "previous", "change_percent", "actual_change_percent", "low", "high", "amount",
            "value", "normalized", "computed"}
    if isinstance(value, dict):
        for name, child in value.items():
            _collect_numbers(child, output, name)
    elif isinstance(value, list):
        for child in value:
            _collect_numbers(child, output, key)
    elif key in keys and value is not None and not isinstance(value, bool):
        try:
            parsed = number(str(value))
        except ValueError:
            return
        output.update((parsed, abs(parsed)))


def _grounded_values(check, occurrences: list, refs: list) -> set[Decimal]:
    """允许值来自成员、被引原文与程序结果；不把“数字在文里出现过”当作语义成立。

    金额同时保留元、万元、百万元和亿元的等值形态，是为了让 4.49 亿元与
    449,183,817.50 元这种真实披露可以在显示精度内比较；单位换算本身
    不等于企业已经确认舍入方法。
    """
    allowed: set[Decimal] = {Decimal(0)}
    found = {row.occurrence_id: row for row in occurrences}
    ids = {item.occurrence_id for item in check.members} | {ref.occurrence_id for ref in refs}
    for occurrence_id in ids:
        row = found.get(occurrence_id)
        if row is None:
            continue
        for _, _, token in _token_spans(row.context):
            parsed = _token_value(token)
            if parsed is not None:
                allowed.update((parsed, abs(parsed)))
        if row.year and YEAR_TOKEN.fullmatch(row.year):
            allowed.add(Decimal(row.year))
        if not row.value:
            continue
        try:
            value, dimension, _ = normalized(row)
        except (ValueError, ArithmeticError):
            continue
        allowed.update((value, abs(value)))
        if dimension == "money":
            allowed.update(value / Decimal(scale) for scale in (1, 10000, 1000000, 100000000))
        elif dimension == "ratio":
            allowed.update((value * 100, value / 100))
    for data in (check.calculation, check.hypothetical, check.scenario_adjustment, check.narrative_test):
        _collect_numbers(data, allowed)
    left, right = check.calculation.get("left"), check.calculation.get("right")
    if left is not None and right is not None:
        try:
            a, b = number(str(left)), number(str(right))
            if max(abs(a), abs(b)):
                allowed.update((abs(a - b) / max(abs(a), abs(b)) * 100, abs(a - b)))
        except (ValueError, ArithmeticError):
            pass
    return allowed


def _matches_allowed(value: Decimal, allowed: set[Decimal]) -> bool:
    """按主张自己的小数位比较，允许原文显示精度造成的舍入差。

    这里只判断“能不能由已知值或已验证算式解释”，不判断企业真实值；
    显示到两位小数不等于企业承诺按四舍五入编制。
    """
    for candidate in allowed:
        if value == candidate:
            return True
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and -8 <= exponent < 0:
            try:
                if candidate.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_UP) == value:
                    return True
            except InvalidOperation:
                continue
    return False


def _dec(groups: dict, name: str) -> Decimal:
    value = _token_value(groups.get(name, ""))
    if value is None:
        raise ValueError("公式成员不是明确数值")
    if groups.get(name + "u") == "%":
        value = value / 100
    return value


def _formula_checks(text: str) -> list[dict]:
    """抽取显式算式并用 Decimal 复算；没有算式的派生数只能标待核。"""
    checks = []
    for pattern in FORMULA_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groupdict()
            try:
                a, b = _dec(groups, "a"), _dec(groups, "b")
                if groups.get("b2"):
                    denominator = _dec(groups, "b2")
                    if denominator == 0:
                        raise ZeroDivisionError
                    computed = (a - b) / denominator
                    raw_formula = f"({text_number(a)}−{text_number(b)})÷{text_number(denominator)}"
                else:
                    op = groups.get("op", "")
                    if op in {"÷", "/", "除以"}:
                        if b == 0:
                            raise ZeroDivisionError
                        computed = a / b
                    elif op in {"×", "*"}:
                        computed = a * b
                    elif op == "+":
                        computed = a + b
                    else:
                        computed = a - b
                    raw_formula = f"{text_number(a)}{op}{text_number(b)}"
                if groups.get("cu") == "%":
                    computed *= 100
                claimed = _token_value(groups.get("c", ""))
                if claimed is None:
                    raise ValueError("公式结果不是明确数值")
                exponent = claimed.as_tuple().exponent
                precision = Decimal(1).scaleb(exponent) if isinstance(exponent, int) else Decimal(1)
                rounded = computed.quantize(precision, rounding=ROUND_HALF_UP)
                checks.append({
                    "raw": match.group(), "span": [match.start(), match.end()],
                    "formula": raw_formula, "claimed": text_number(claimed),
                    "inputs": [{"symbol": "a", "value": text_number(a)},
                               {"symbol": "b", "value": text_number(b)}],
                    "computed": text_number(computed),
                    "computed_at_claim_precision": text_number(rounded),
                    "precision": str(precision), "matches": rounded == claimed,
                    "status": "supported" if rounded == claimed else "contradicted",
                    "reason": "" if rounded == claimed else
                              f"按{raw_formula}复算为{text_number(rounded)}，与叙述的{text_number(claimed)}不符",
                })
            except (ValueError, ZeroDivisionError, InvalidOperation):
                checks.append({"raw": match.group(), "span": [match.start(), match.end()],
                               "formula": match.group(), "claimed": groups.get("c", ""),
                               "computed": None, "matches": False, "status": "insufficient_basis",
                               "reason": "算式无法用明确十进制数复算"})
    return checks


def parse_claimed_magnitude(text: str) -> dict | None:
    """解析“同比增加10.89%”一类幅度；只认方向和百分比都写明的句子。"""
    if not text:
        return None
    patterns = (
        re.compile(r"(?:同比|环比|较上(?:年|期))?\s*(增长|增加|上升|提高|下降|减少|降低)\s*"
                   r"(?:了|幅度为|约|达)?\s*(\d+(?:\.\d+)?)\s*%"),
        re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:的)?\s*(增长|增加|上升|提高|下降|减少|降低)"),
    )
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        first, second = match.group(1), match.group(2)
        if first[0].isdigit():
            value, direction = first, second
        else:
            direction, value = first, second
        normalized_direction = "decrease" if direction in {"下降", "减少", "降低"} else "increase"
        claimed = Decimal(value)
        return {"direction": normalized_direction, "value": claimed,
                "precision": claimed.as_tuple().exponent, "raw": match.group()}
    return None


def verify_narrative_magnitude(check, claim, occurrences: list) -> dict:
    """复算叙述幅度；只有方向没有幅度时只能标“方向已核、幅度未核”。"""
    found = {row.occurrence_id: row for row in occurrences}
    current, previous = found.get(claim.current_id), found.get(claim.previous_id)
    base = {"claimed_direction": claim.direction, "indicator": claim.indicator,
            "claimed_text": claim.basis_description, "note": "",
            "base_period": getattr(previous, "year", "") if previous else "",
            "base_period_status": "supported" if previous and getattr(previous, "year", "") else "insufficient_basis"}
    if current is None or previous is None:
        return {**base, "status": "not_executable", "reason": "绑定的本期或上期成员不存在"}
    if claim.current_id == claim.previous_id:
        return {**base, "status": "not_executable", "reason": "本期与上期绑定同一成员，不能证明同比"}
    try:
        a, dim_a, _ = normalized(current)
        b, dim_b, _ = normalized(previous)
    except (ValueError, ArithmeticError) as error:
        return {**base, "status": "not_executable", "reason": str(error)}
    if dim_a != dim_b or dim_a == "unknown":
        return {**base, "status": "not_executable", "reason": "两期数据量纲不同"}
    if current.currency and previous.currency and current.currency != previous.currency:
        return {**base, "status": "not_executable", "reason": "两期数据币种不同"}
    try:
        consecutive = bool(current.year and previous.year and int(current.year) - int(previous.year) == 1)
    except ValueError:
        consecutive = False
    if not consecutive:
        return {**base, "status": "not_executable", "reason": "同比需要明确的连续两期指标年度"}
    actual_direction = "increase" if a > b else "decrease" if a < b else "stable"
    change_percent = (a - b) / abs(b) * 100 if b else None
    result = {
        **base, "status": "direction_only",
        "current": text_number(a), "previous": text_number(b), "dimension": dim_a,
        "direction": actual_direction, "direction_matches": actual_direction == claim.direction,
        "actual_change_percent": text_number(change_percent) if change_percent is not None else None,
        "change_percent": text_number(change_percent) if change_percent is not None else None,
        "magnitude_status": "not_verified",
    }
    if change_percent is None:
        result.update(status="not_executable", reason="上期为零，不能计算百分比幅度")
        return result
    if actual_direction != claim.direction:
        result.update(status="contradicted", magnitude_status="contradicted",
                      reason=f"实际方向为{actual_direction}，与叙述方向{claim.direction}相反")
        return result
    claimed = parse_claimed_magnitude(claim.basis_description)
    if claimed is None:
        result["note"] = "只核对了方向；叙述未给出可复算幅度，不能宣称幅度一致"
        return result
    if claimed["direction"] != actual_direction:
        result.update(status="contradicted", magnitude_status="contradicted",
                      reason="叙述幅度方向与绑定数据方向相反")
        return result
    precision = Decimal(1).scaleb(claimed["precision"]) if isinstance(claimed["precision"], int) else Decimal(1)
    # 叙述写“下降20%”时幅度是正数，实际复算是 -20；方向和幅度分开比较。
    rounded = abs(change_percent).quantize(precision, rounding=ROUND_HALF_UP)
    matches = rounded == claimed["value"]
    result.update({
        "claimed_value": text_number(claimed["value"]), "claimed_precision": text_number(precision),
        "recomputed_value": text_number(rounded), "magnitude_matches": matches,
        "magnitude_status": "supported" if matches else "contradicted",
        "status": "supported" if matches else "contradicted",
        "reason": "" if matches else
                  f"按两期数据复算为{text_number(rounded)}%，叙述为{text_number(claimed['value'])}%",
    })
    narrative_text = f"{claim.basis_description} {check.explanation}"
    is_target = bool(re.search(r"目标|计划|拟|承诺|规划|力争", claim.basis_description))
    says_achieved = bool(re.search(r"已实现|已完成|达到目标|完成目标|实现目标", narrative_text))
    result["narrative_type"] = "target" if is_target else "result"
    result["target_as_result"] = bool(is_target and says_achieved)
    if result["target_as_result"]:
        result.update(status="contradicted", note="把减排/研发目标写成已实现结果，需区分目标与当期事实")
    if "强度" in claim.indicator and re.search(r"总量.{0,12}(?:增长|上升|增加)", narrative_text):
        result["total_and_intensity_coexist"] = True
        result["note"] = (result["note"] + "；" if result["note"] else "") + \
                         "总量上升与强度下降可以同时成立，不能仅凭方向判矛盾"
    return result


def _sentence_around(text: str, start: int, end: int) -> str:
    """取数字所在的句子，避免把下一句的诊断语当成支持证据。"""
    left = max(text.rfind(mark, 0, start) for mark in ("\n", "。", "；")) + 1
    right_candidates = [index for index in (text.find(mark, end) for mark in ("\n", "。", "；")) if index >= 0]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left:right].strip()


def _column_claims(check, text: str, occurrences: list, refs: list) -> list[dict]:
    """把绑定成员的列语义与叙述对照，专门拦住 0.66% 这类错列。

    只看数字所在句子，不把下一句的诊断说明当成支持证据；
    变动列被写成年度值、占比被写成绝对金额、多年混列被绑定单一年份，
    都会留下可回查的 claim 记录。
    """
    found = {row.occurrence_id: row for row in occurrences}
    ids = {item.occurrence_id for item in check.members} | {ref.occurrence_id for ref in refs}
    claims = []
    for occurrence_id in sorted(ids):
        row = found.get(occurrence_id)
        if row is None or row.value in (None, ""):
            continue
        semantics = classify_column_semantics(row)
        if semantics not in {"change_ratio", "yoy", "share", "intensity", "multi_year_ambiguous"}:
            continue
        target = _token_value(row.value)
        if target is None:
            continue
        for start, end, token in _token_spans(text):
            parsed = _token_value(token)
            if parsed is None or parsed != target:
                continue
            window = _sentence_around(text, start, end)
            status, reason = "not_verified", "未看出该值被当作何种语义"
            if semantics in {"change_ratio", "yoy"}:
                misuse = bool(re.search(r"(?:被|把|将).{0,12}(?:当作|当成|作为|误作).{0,8}年度|当作年度值", window))
                negated = bool(re.search(r"不能|不得|不应|不是|并非|不可|勿", window))
                if misuse and not negated:
                    status, reason = "contradicted", "明确把变动/同比列当作年度值使用"
                elif CHANGE_PATTERN.search(window):
                    status, reason = "supported", "叙述按变动/同比语义引用"
                elif re.search(r"(?:20\d{2}\s*年|年度|本期|本年|当期|金额|绝对额|占比为)", window):
                    status, reason = "contradicted", "把变动/同比列当作年度值或绝对值使用"
            elif semantics in {"share", "intensity"}:
                if MATERIAL_UNIT.search(window) or re.search(r"金额|绝对额|达到", window):
                    status, reason = "contradicted", "把占比或强度当作绝对金额/数量使用"
                else:
                    status, reason = "supported", "按占比或强度语义引用"
            elif semantics == "multi_year_ambiguous":
                if re.search(r"20\d{2}\s*年", window):
                    status, reason = "contradicted", "该值所在列混有多个年度，不能绑定单一年份"
            claims.append({
                "claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|{occurrence_id}|{start}".encode()).hexdigest()[:10].upper(),
                "kind": "column_semantics", "token": token, "value": row.value,
                "occurrence_id": occurrence_id, "indicator": row.label,
                "year": row.year, "column_header": row.column_header,
                "column_semantics": semantics, "support_status": status,
                "material": True, "reason": reason, "text": window.strip(),
            })
            break
    return claims


def _year_claims(check, text: str, occurrences: list, refs: list) -> list[dict]:
    """年份主张必须指向对应年度的 occurrence，不能拿变动列跨年。

    同一年度存在其他指标不能自动支持本指标；只有绑定成员或引用原文
    能落到该年度时，年份断言才算有依据。
    """
    found = {row.occurrence_id: row for row in occurrences}
    ids = {item.occurrence_id for item in check.members} | {ref.occurrence_id for ref in refs}
    bound = [found[item] for item in ids if item in found]
    claims = []
    for match in YEAR_ASSERTION.finditer(text):
        year = match.group(1)
        window = text[max(0, match.start() - 20): min(len(text), match.end() + 40)]
        tokens = [token for _, _, token in _token_spans(window)
                  if not YEAR_TOKEN.fullmatch(token.replace(",", "").replace("，", ""))]
        same_year = [row for row in bound if row.year == year and row.year_status == "attributed"]
        other_year = [row for row in bound if row.year and row.year != year]
        if same_year:
            status, reason = "supported", f"存在{year}年度已归属成员"
        elif other_year:
            status, reason = "contradicted", f"绑定成员年度为{other_year[0].year}，不是{year}"
        else:
            status, reason = "insufficient_basis", f"没有可回查的{year}年度成员"
        # 0.66% 这类列没有 year 字段，但列头写明“变动比例”；年份断言仍不得把它变成年度值。
        change_rows = [row for row in bound if classify_column_semantics(row) in {"change_ratio", "yoy"}]
        if change_rows and tokens and not same_year:
            status, reason = "contradicted", "该数值来自变动/同比列，不能绑定到断言年份"
        claims.append({
            "claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|year|{match.start()}".encode()).hexdigest()[:10].upper(),
            "kind": "year_assertion", "token": year, "value": year,
            "occurrence_id": same_year[0].occurrence_id if same_year else "",
            "indicator": "", "year": year, "column_header": "",
            "column_semantics": "period_value" if same_year else "unknown",
            "support_status": status, "material": True, "reason": reason, "text": window.strip(),
        })
    return claims


def _semantic_claims(check, text: str, refs: list, narrative: dict | None) -> list[dict]:
    """引用真实不等于语义成立：方向断言和因果解释要单独看原文是否支持。"""
    claims = []
    direction_words = {"increase": ("增长", "增加", "上升", "提高"), "decrease": ("下降", "减少", "降低")}
    for sentence in re.split(r"[。；\n]", text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if narrative and narrative.get("direction"):
            if getattr(check.narrative_claim, "indicator", "") and check.narrative_claim.indicator in sentence:
                found_directions = {name for name, words in direction_words.items()
                                    if any(word in sentence for word in words)}
                if len(found_directions) == 1 and narrative["direction"] not in found_directions:
                    claims.append({
                        "claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|direction|{sentence[:40]}".encode()).hexdigest()[:10].upper(),
                        "kind": "direction_claim", "token": "", "value": "", "occurrence_id": "",
                        "indicator": check.narrative_claim.indicator, "year": "", "column_header": "",
                        "column_semantics": "narrative", "support_status": "contradicted",
                        "material": True, "reason": "叙述方向与绑定两期数据的实际方向相反", "text": sentence,
                    })
        if re.search(r"因为|由于|主要系|原因|导致|因此|说明", sentence):
            causal = [ref for ref in refs
                      if re.search(r"因为|由于|主要系|原因|导致|因此|说明|受.{0,12}影响", ref.quote)]
            claims.append({
                "claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|causal|{sentence[:40]}".encode()).hexdigest()[:10].upper(),
                "kind": "causal_explanation", "token": "", "value": "", "occurrence_id": "",
                "indicator": check.title, "year": "", "column_header": "",
                "column_semantics": "explanation",
                "support_status": "supported" if causal else "insufficient_basis",
                "material": True,
                "reason": "引用中含因果/范围解释" if causal else "所引原文只出现数字或事实，没有说明该因果关系",
                "text": sentence,
            })
    return claims


def build_claim_ledger(check, analysis, occurrences: list, *, role: str = "", model: str = "") -> dict:
    """逐条生成 AI 意见的 claim 账本；支持、反驳、依据不足分别计数。

    账本不是“正确率评分”：一条意见可以引用真实原文但语义仍不足；
    只有明确列义矛盾或算式不符才进入 material_contradictions 并阻断采纳。
    未发现反证、只核方向、显示精度相容都单独标注，不能冒充已验证。
    """
    refs = list(analysis.supporting_evidence) + list(analysis.counter_evidence)
    for hypothesis in getattr(analysis, "hypotheses", []):
        refs.extend(hypothesis.supporting_evidence)
        refs.extend(hypothesis.counter_evidence)
    texts = [analysis.summary, *analysis.reasons, *analysis.assumptions,
             *analysis.alternative_explanations, *analysis.next_actions]
    text = "\n".join(str(item) for item in texts if item)
    formulas = _formula_checks(text)
    claims = _column_claims(check, text, occurrences, refs)
    claims.extend(_year_claims(check, text, occurrences, refs))
    for formula in formulas:
        claims.append({
            "claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|formula|{formula['raw']}".encode()).hexdigest()[:10].upper(),
            "kind": "derived_value", "token": formula.get("claimed", ""), "value": formula.get("claimed", ""),
            "occurrence_id": "", "indicator": check.title, "year": "", "column_header": "",
            "column_semantics": "derived", "support_status": formula["status"],
            "material": True, "reason": formula["reason"], "formula": formula.get("formula", ""),
            "inputs": formula.get("inputs", []), "computed": formula.get("computed"),
            "text": formula["raw"],
        })
    allowed = _grounded_values(check, occurrences, refs)
    for formula in formulas:
        if formula.get("matches") and formula.get("computed") is not None:
            try:
                allowed.add(Decimal(formula["computed"]))
            except InvalidOperation:
                pass
    narrative = None
    if getattr(check, "narrative_claim", None):
        narrative = verify_narrative_magnitude(check, check.narrative_claim, occurrences)
        if narrative.get("actual_change_percent") is not None:
            try:
                allowed.add(abs(Decimal(narrative["actual_change_percent"])))
            except InvalidOperation:
                pass
        status = narrative.get("status")
        if status == "supported":
            claims.append({"claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|narrative".encode()).hexdigest()[:10].upper(),
                           "kind": "narrative_magnitude", "token": narrative.get("claimed_value", ""),
                           "value": narrative.get("claimed_value", ""), "occurrence_id": check.narrative_claim.current_id,
                           "indicator": check.narrative_claim.indicator, "year": "", "column_header": "",
                           "column_semantics": "narrative", "support_status": "supported", "material": True,
                           "reason": "方向与幅度均与两期绑定数据复算一致", "text": check.narrative_claim.basis_description})
        elif status in {"contradicted", "not_executable"}:
            claims.append({"claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|narrative".encode()).hexdigest()[:10].upper(),
                           "kind": "narrative_magnitude", "token": narrative.get("claimed_value", ""),
                           "value": narrative.get("claimed_value", ""), "occurrence_id": check.narrative_claim.current_id,
                           "indicator": check.narrative_claim.indicator, "year": "", "column_header": "",
                           "column_semantics": "narrative",
                           "support_status": "contradicted" if status == "contradicted" else "insufficient_basis",
                           "material": True, "reason": narrative.get("reason", "叙述幅度无法复算"),
                           "text": check.narrative_claim.basis_description})
    claims.extend(_semantic_claims(check, text, refs, narrative))
    if check.narrative_claim and not (narrative or {}).get("target_as_result"):
        basis = check.narrative_claim.basis_description
        if re.search(r"目标|计划|承诺|规划|力争", basis) and re.search(r"已实现|已完成|达到目标|完成目标|实现目标", text):
            claims.append({
                "claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|target|{basis[:30]}".encode()).hexdigest()[:10].upper(),
                "kind": "target_as_result", "token": "", "value": "", "occurrence_id": "",
                "indicator": check.narrative_claim.indicator, "year": "", "column_header": "",
                "column_semantics": "narrative", "support_status": "contradicted", "material": True,
                "reason": "AI 把目标/承诺写成已实现结果，需区分目标与当期事实", "text": basis,
            })
    formula_spans = [span for formula in formulas for span in [formula.get("span")] if span]
    for start, end, token in _token_spans(text):
        if any(left <= start < right for left, right in formula_spans):
            continue
        if not _is_material(token, text, start, end):
            continue
        parsed = _token_value(token)
        if parsed is None:
            continue
        if _matches_allowed(parsed, allowed) or (token.endswith("%") and _matches_allowed(parsed / 100, allowed)):
            continue
        claims.append({
            "claim_id": "CLM-" + hashlib.sha256(f"{check.check_id}|{start}|{token}".encode()).hexdigest()[:10].upper(),
            "kind": "numeric_value", "token": token, "value": text_number(parsed),
            "occurrence_id": "", "indicator": "", "year": "", "column_header": "",
            "column_semantics": "unknown", "support_status": "insufficient_basis",
            "material": True, "reason": "该数字既不是绑定成员值，也没有可复核算式",
            "text": text[max(0, start - 30): min(len(text), end + 30)].strip(),
        })
    summary = {"supported": 0, "contradicted": 0, "insufficient_basis": 0, "not_verified": 0}
    for claim in claims:
        summary[claim["support_status"]] = summary.get(claim["support_status"], 0) + 1
    if summary["contradicted"]:
        status = "contradicted"
    elif summary["insufficient_basis"]:
        status = "insufficient_basis"
    elif summary["supported"]:
        status = "supported"
    else:
        status = "not_verified"
    return {
        "schema_version": CLAIM_LEDGER_VERSION, "check_id": check.check_id,
        "producer_role": role, "model": model, "verdict": analysis.verdict,
        "claims": claims, "derived_checks": formulas, "narrative_test": narrative,
        "support_summary": summary, "support_status": status,
        "material_contradictions": [claim for claim in claims
                                    if claim["support_status"] == "contradicted" and claim.get("material")],
        "notes": ["引用逐字通过不等于业务含义成立", "未发现反证不等于解释已被证实",
                  "显示精度复算不等于企业实际舍入方法"],
    }


def should_reject_analysis(ledger: dict) -> tuple[bool, str]:
    """明确矛盾的主张不能进入正式意见；依据不足交给现有数字门禁再拦一次。

    这里只拒绝“能被原文或算式直接推翻”的主张；证据不足仍保留为可补查意见，
    以免把所有未知都误删，也避免把未知写成已确认。
    """
    contradictions = ledger.get("material_contradictions") or []
    if contradictions:
        first = contradictions[0]
        return True, f"AI主张与原文/算式矛盾：{first.get('reason', '列义或算术不符')}"
    return False, ""


def build_next_evidence(check, rule_basis: list[dict] | None = None) -> list[dict]:
    """每个未决条件给出具体补证动作、来源位置和升级路径，不能只写“建议关注”。"""
    actions = []
    basis_by_condition = {}
    for entry in rule_basis or []:
        for condition in entry.get("conditions", []):
            basis_by_condition.setdefault(condition, []).append(entry)
    for condition in check.conditions:
        if condition.status == "supported":
            continue
        action, source, level = NEXT_EVIDENCE.get(
            condition.name, (f"补齐“{condition.name}”的原文依据", "报告原文", "L1"))
        basis = basis_by_condition.get(condition.name, [])
        actions.append({
            "action_id": "NEXT-" + hashlib.sha256(f"{check.check_id}|{condition.name}".encode()).hexdigest()[:10].upper(),
            "check_id": check.check_id, "condition": condition.name,
            "action": action, "material": source,
            "upgrade_effect": (f"补齐后可先达到{level}有限支持；全部必要前提支持后才可进入L2程序复算" if level != "L0"
                               else "补齐后才可进入确定性计算（L0 数值试算）；不能先用假设值代替"),
            "counter_query": COUNTER_QUERY.get(condition.name, "反证 例外 不同口径"),
            "rule_basis_ids": [entry.get("basis_id") for entry in basis],
            "basis_verification": [entry.get("verification_status") for entry in basis],
            "reason_now": condition.reason,
        })
    if check.mapping_type in {"different_metric", "related_only"} and not actions:
        actions.append({
            "action_id": "NEXT-" + hashlib.sha256(f"{check.check_id}|mapping".encode()).hexdigest()[:10].upper(),
            "check_id": check.check_id, "condition": "关系类型",
            "action": "确认两项指标是否属于同一概念；若不是，保留为背景关联而不作数值比较",
            "material": "指标定义/口径说明", "upgrade_effect": "避免把不同指标强行比较",
            "counter_query": "定义 不同 口径 不可比", "rule_basis_ids": [], "basis_verification": [],
            "reason_now": check.mapping_reason,
        })
    return actions


def hypothesis_ledger(check) -> list[dict]:
    """输出竞争解释的可检验条件、区分证据与更新状态；无来源的“已解释”不成立。"""
    records = []
    for hypothesis in check.hypotheses:
        testable = next((re.sub(r"^可检验条件[:：]\s*", "", item) for item in hypothesis.assumptions
                         if item.startswith("可检验条件")), "")
        discriminating = next((re.sub(r"^区分证据[:：]\s*", "", item) for item in hypothesis.assumptions
                               if item.startswith("区分证据")), "")
        if not testable:
            testable = hypothesis.retrieval_queries[0] if hypothesis.retrieval_queries else "补齐能区分该解释的原文条件"
        if not discriminating:
            discriminating = "；".join(ref.quote[:60] for ref in hypothesis.counter_evidence) or "尚未找到可区分证据"
        status = hypothesis.status
        reason = "保留模型给出的状态"
        if hypothesis.counter_evidence:
            status = "refuted"
            reason = "存在指向该解释不成立的原文/反证"
        elif not hypothesis.supporting_evidence:
            status = "open" if status == "supported" else status
            reason = "没有支持证据，不能标记为已支持"
        elif status == "supported":
            reason = "有支持证据，但仍需排除竞争解释"
        records.append({
            "hypothesis_id": hypothesis.hypothesis_id, "check_id": check.check_id,
            "explanation": hypothesis.explanation, "status": status, "before_status": hypothesis.status,
            "testable_condition": testable, "discriminating_evidence": discriminating,
            "supporting_ids": [ref.occurrence_id for ref in hypothesis.supporting_evidence],
            "counter_ids": [ref.occurrence_id for ref in hypothesis.counter_evidence],
            "update_reason": reason,
            "unverified_note": "未找到反证不等于解释成立" if not hypothesis.counter_evidence else "",
        })
    return records


def apply_hypothesis_updates(check, occurrences: list) -> list[dict]:
    """用已取得的原文更新假设状态；反证可以使解释撤回，新支持不能静默抹掉反证。"""
    found = {row.occurrence_id: row for row in occurrences}
    updates = []
    for hypothesis in check.hypotheses:
        before = hypothesis.status
        counter_valid = bool(hypothesis.counter_evidence) and validate_refs(hypothesis.counter_evidence, found)
        support_valid = bool(hypothesis.supporting_evidence) and validate_refs(hypothesis.supporting_evidence, found)
        if counter_valid:
            hypothesis.status = "refuted"
        elif hypothesis.status == "supported" and not support_valid:
            hypothesis.status = "open"
        if hypothesis.status != before:
            updates.append({
                "check_id": check.check_id, "hypothesis_id": hypothesis.hypothesis_id,
                "before": before, "after": hypothesis.status,
                "reason": "新增反证使解释撤回" if hypothesis.status == "refuted" else "支持依据未能复核，退回未决",
                "counter_ids": [ref.occurrence_id for ref in hypothesis.counter_evidence],
            })
    return updates
