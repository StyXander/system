"""判断层：把"对／错"二值核对，升级为"证据充分度 → 披露风险刻度 → AI 意见"。

本模块是新增层，不改动 connectivity_engine 的既有判定，只在其之上补两件事：

1. 容差判定（解决"死板"）
   - 数值容差沿用 XBRL US DQC_0084 的精度放大法：tol = 末位精度 × 2
   - 历史筛查参数分三层，比例为项目自设值，并非 ISA 320 统一公式：明显微小(CT) → 执行重要性(PM) → 整体重要性(OM)
   - 两者取大，先吸收舍入噪声，再谈重要性

2. 风险分解（解决"不出结论"）
   - Unmanaged = Exposure × (1 - Managed / Manageable)
   - 结构与 Morningstar Sustainalytics 的 ESG Risk Ratings 同构，
     但计量对象是"披露一致性风险"，不是 ESG 绩效
   - 关键效果：证据不足不再导致"无结论"，而是压低 Managed、抬高风险分

3. AI 意见（解决"没有观点"）
   - AI 只输出"可能是什么原因 + 建议怎么查"，不裁定对错
   - 模型推理的置信度上限 0.70，低于原文直证的 0.90
   - 低于复核阈值的意见强制落 HUMAN_REVIEW

对外声明沿用 connectivity_schemas.NOTICE，不另造口径。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Iterable, Literal, Sequence

DISCLAIMER = "AI生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，不构成审计结论、鉴证结论或鉴证意见。"

# ---------------------------------------------------------------------------
# 一、容差：两套来源取大
# ---------------------------------------------------------------------------

#: CEAOB 2023 年对爱尔兰 PIE 审计的调查：执行重要性 75% 出现率 57.5%，明显微小 5% 出现率 87.5%。
#: 取这两个最常见值作默认参数，不表示唯一正确取值。
PERFORMANCE_RATIO = Decimal("0.75")
CLEARLY_TRIVIAL_RATIO = Decimal("0.05")


@dataclass(frozen=True)
class Materiality:
    """历史三层筛查参数，非准则规定的重要性公式。overall为项目自设比例。"""

    overall: Decimal
    performance: Decimal
    clearly_trivial: Decimal
    basis: str = ""

    @classmethod
    def from_base(cls, base: Decimal, overall_ratio: Decimal = Decimal("0.01"), basis: str = "") -> "Materiality":
        # 阈值是计算参数，不按货币显示位数截断；比例基数为1时仍保留0.0075和0.0005。
        overall = base * overall_ratio
        return cls(
            overall=overall,
            performance=overall * PERFORMANCE_RATIO,
            clearly_trivial=overall * CLEARLY_TRIVIAL_RATIO,
            basis=basis or f"{base} × {overall_ratio}",
        )


def rounding_tolerance(values: Sequence[Decimal], decimals: int | None = None) -> Decimal:
    """DQC_0084 的精度放大法：容差 = 最小末位精度 × 2。

    说明：原文若只报到万元（decimals=-4），两处各舍入一次，最大偏差即 2 个末位单位。
    """
    if decimals is None:
        decimals = 0
        for value in values:
            exponent = value.as_tuple().exponent
            if isinstance(exponent, int):
                decimals = min(decimals, exponent)
    return (Decimal(10) ** decimals) * 2


@dataclass(frozen=True)
class Band:
    """一次数值比较落在哪一档。"""

    grade: Literal["EXACT", "ROUNDING", "TRIVIAL", "MINOR", "MATERIAL", "SIGNIFICANT"]
    diff: Decimal
    tolerance: Decimal
    materiality: Materiality
    narrative: str


def infer_base(left: Decimal, right: Decimal, is_ratio: bool = False) -> Decimal:
    """重要性基数：比例/强度类指标按百分点尺度，金额类按金额尺度。

    比例值在引擎内已规范化为小数（4.86% = 0.0486），因此基数取 1，
    整体重要性才是 1 个百分点；若输入仍是百分数（4.86），基数取 100。
    比例指标若沿用金额基数，会把 0.26 个百分点判成舍入噪声，这是典型的量纲误用。
    """
    scale = max(abs(left), abs(right))
    if is_ratio:
        return Decimal("1") if scale <= 1 else Decimal("100")
    return scale if scale > 0 else Decimal("1")


def compare(left: Decimal, right: Decimal, materiality: Materiality) -> Band:
    """先吃舍入噪声，再按三层重要性分档。这是替代 `if a != b` 的核心。"""
    diff = abs(left - right)
    tol = max(rounding_tolerance([left, right]), materiality.clearly_trivial / 4)
    if diff == 0:
        return Band("EXACT", diff, tol, materiality, "两侧数值完全相同")
    if diff <= tol:
        return Band("ROUNDING", diff, tol, materiality,
                    f"差额 {diff} 在舍入容差 {tol} 内，属精度噪声，不构成差异")
    if diff <= materiality.clearly_trivial:
        return Band("TRIVIAL", diff, tol, materiality,
                    f"差额 {diff} 低于明显微小错报临界值 {materiality.clearly_trivial}，按准则不累积")
    if diff <= materiality.performance:
        return Band("MINOR", diff, tol, materiality,
                    f"差额 {diff} 介于临界值与执行重要性 {materiality.performance} 之间，提示关注")
    if diff <= materiality.overall:
        return Band("MATERIAL", diff, tol, materiality,
                    f"差额 {diff} 已达整体重要性 {materiality.overall} 区间，需解释或调整")
    return Band("SIGNIFICANT", diff, tol, materiality,
                f"差额 {diff} 超过整体重要性 {materiality.overall}，单独即可能影响使用者判断")


# ---------------------------------------------------------------------------
# 二、证据画像与风险分解
# ---------------------------------------------------------------------------

#: 关键条件权重。主体/期间错了，后面算得再准也没意义，故权重最高。
CONDITION_WEIGHT = {
    "主体": 20, "期间": 20, "单位": 15, "范围": 15, "定义": 15,
    "组成完整": 10, "互不重叠": 5, "公式": 20,
}
#: 前置条件：不知道就无法把两个数放在一起比。未知只记 0.15 信用，接近不算数。
PREREQUISITE = {"主体", "期间", "范围", "公式"}
#: 状态折算：supported 满分；conflicting 归零；unknown 按条件类型分档。
#: 这一处分档就是"不再 all-or-nothing"的落点：未知不清零，但也不假装知道一半。
STATUS_CREDIT = {"supported": 1.0, "conflicting": 0.0}
UNKNOWN_CREDIT = {"prerequisite": 0.15, "supporting": 0.5}


def _credit(name: str, status: str) -> float:
    if status in STATUS_CREDIT:
        return STATUS_CREDIT[status]
    kind = "prerequisite" if name in PREREQUISITE else "supporting"
    return UNKNOWN_CREDIT[kind]


@dataclass
class ConditionView:
    name: str
    status: Literal["supported", "conflicting", "unknown"]
    reason: str = ""


@dataclass
class EvidenceProfile:
    """把一串条件压成三个可直接进公式的数。"""

    managed: float          # 实际披露充分度 0-100
    manageable: float       # 该行业本可达到的充分度 0-100
    exposure: float         # 指标本身的披露风险敞口 0-100
    conflict_count: int = 0
    unknown_names: list[str] = field(default_factory=list)
    supported_names: list[str] = field(default_factory=list)

    @property
    def unmanaged(self) -> float:
        """Sustainalytics 式分解：未被管理掉的那部分风险。"""
        if self.manageable <= 0:
            return self.exposure
        ratio = min(1.0, max(0.0, self.managed / self.manageable))
        return round(self.exposure * (1 - ratio), 2)


def build_profile(
    conditions: Iterable[ConditionView],
    exposure: float = 60.0,
    manageable: float = 85.0,
) -> EvidenceProfile:
    """条件 → 证据画像。exposure/manageable 由行业基准与指标性质给定，此处作参数。"""
    rows = list(conditions)
    total_weight = sum(CONDITION_WEIGHT.get(row.name, 10) for row in rows) or 1
    credit = sum(CONDITION_WEIGHT.get(row.name, 10) * _credit(row.name, row.status) for row in rows)
    managed = round(100 * credit / total_weight, 2)
    return EvidenceProfile(
        managed=managed,
        manageable=manageable,
        exposure=exposure,
        conflict_count=sum(1 for row in rows if row.status == "conflicting"),
        unknown_names=[row.name for row in rows if row.status == "unknown"],
        supported_names=[row.name for row in rows if row.status == "supported"],
    )


# ---------------------------------------------------------------------------
# 三、披露质量风险标签（Wind 1200+ 风险标签的迷你版）
# ---------------------------------------------------------------------------

#: 结构性标签：指向口径/方法层面的系统问题，命中后放大风险（MSCI：结构性争议扣分 > 近期表现争议）
#: 第三个数是"分数地板"：结构性标签一旦命中，无论差异多小都不许判成可忽略。
STRUCTURAL_TAGS = {
    "SCOPE_DRIFT": ("口径漂移", 12.0, "同一指标在两份报告的统计范围表述不一致", 55.0),
    "DENOMINATOR_SWITCH": ("分母切换", 12.0, "比例指标的分母在不同期间或不同报告间被替换", 45.0),
    "PERIOD_MISMATCH": ("期间错配", 10.0, "比较期间与本期数据混用，或指标期间与报告期间不一致", 50.0),
    "UNIT_JUMP": ("单位跳变", 10.0, "量纲在万元/元/亿元之间跳变且未注明换算", 50.0),
    "VERSION_ROLLBACK": ("版本回撤", 15.0, "修订版数据回退到修订前，或与公告版本不一致", 70.0),
    "SELECTIVE_DISCLOSURE": ("选择性披露", 8.0, "仅在单一载体披露关键指标，另一载体缺失", 40.0),
    "BOUNDARY_OPAQUE": ("范围未界定", 8.0, "指标的组织边界或统计范围在两份报告中均未说明", 35.0),
    "DEFINITION_OPAQUE": ("定义未界定", 7.0, "指标定义或计算方法在两份报告中均未说明", 32.0),
    "MULTI_LOCATION_DRIFT": ("多位置漂移", 9.0, "同一指标在同报告多处披露且数值不一致", 45.0),
    "RELATION_UNCONFIRMED": ("关系待确认", 6.0, "两处披露的对照关系由自动配对或多位置得到，尚缺原文说明", 0.0),
}
#: 表现性标签：指向单次笔误，放大系数较小，不设地板
PRESENTATIONAL_TAGS = {
    "TYPO": ("疑似笔误", 5.0, "数字位序或小数点位置异常，量级偏离同表其他行"),
    "LABEL_MISMATCH": ("标签错配", 5.0, "行名与数值组合在同表中不合常理"),
    "FOOTNOTE_ORPHAN": ("脚注脱节", 4.0, "数值引用的脚注编号在页内无对应说明"),
}


def apply_tags(score: float, tags: Iterable[str]) -> tuple[float, list[dict], float]:
    """标签按"结构性 1.12 倍 / 表现性 1.05 倍"放大，并给出分数地板，封顶 100。"""
    hits, factor, floor = [], 1.0, 0.0
    for tag in tags:
        if tag in STRUCTURAL_TAGS:
            name, weight, why, tag_floor = STRUCTURAL_TAGS[tag]
            factor *= 1 + weight / 100
            floor = max(floor, tag_floor)
            hits.append({"code": tag, "name": name, "kind": "结构性", "weight": weight, "why": why})
        elif tag in PRESENTATIONAL_TAGS:
            name, weight, why = PRESENTATIONAL_TAGS[tag]
            factor *= 1 + weight / 200
            hits.append({"code": tag, "name": name, "kind": "表现性", "weight": weight, "why": why})
    return round(min(100.0, score * factor), 2), hits, floor


#: 数值差异压力：把 Band 档位换成 0-100 的分数。这一步取代了"差额是否为零"的二值开关。
DIFF_PRESSURE = {"EXACT": 5.0, "ROUNDING": 10.0, "TRIVIAL": 20.0,
                 "MINOR": 40.0, "MATERIAL": 65.0, "SIGNIFICANT": 85.0}

#: 有原文依据的口径解释可回调分数，但只回调 35%，不归零——否则又回到"解释了就没事"。
EXPLAINED_DISCOUNT = 0.65


def disclosure_risk(band: Band, profile: EvidenceProfile, verdict: str) -> float:
    """披露风险分：差异压力与证据缺口两条腿，取更重的一条。

    两条腿的量纲不同（一个是差额档位，一个是充分度），所以不能像 Sustainalytics 那样
    直接相减，改为取大：数对不上、或数说不清，任一成立即构成披露风险。
    证据缺口沿用其分解精神——缺口 × 敞口 = 未被管理掉的风险。
    """
    diff_drive = DIFF_PRESSURE.get(band.grade, 60.0)
    gap_drive = (100.0 - profile.managed) * (profile.exposure / 100.0)
    base = max(diff_drive, gap_drive)
    if verdict == "EXPLAINABLE_DIFFERENCE":
        base *= EXPLAINED_DISCOUNT
    elif verdict == "UNEXPLAINED":
        base *= 1.15
    return round(min(100.0, base), 2)


#: 五档刻度，与 Morningstar Sustainalytics 的 negligible/low/medium/high/severe 同构，
#: 便于评委把我们的分数直接对到熟悉的语言上。
RISK_BANDS = (
    (20.0, "可忽略", "Negligible", "披露链条自洽，差异在容差内或无差异"),
    (40.0, "低", "Low", "存在可解释的小额差异，不影响指标可用性"),
    (60.0, "中", "Medium", "差异需解释，或关键前提有未知项，建议索取底稿"),
    (80.0, "高", "High", "存在结构性口径问题，指标跨报告不可直接比较"),
    (100.01, "严重", "Severe", "差异达整体重要性，或关键前提相互冲突"),
)


def risk_band(score: float) -> dict:
    for ceiling, label, en, meaning in RISK_BANDS:
        if score < ceiling:
            return {"score": score, "label": label, "en": en, "meaning": meaning}
    return {"score": score, "label": "严重", "en": "Severe", "meaning": RISK_BANDS[-1][3]}


# ---------------------------------------------------------------------------
# 四、AI 意见
# ---------------------------------------------------------------------------

Verdict = Literal[
    "CONSISTENT",              # 一致
    "EXPLAINABLE_DIFFERENCE",  # 差异可解释，且有原文依据
    "PROBABLE_EXPLAINABLE",    # 差异可能可解释，仅为推理，无直接原文
    "UNEXPLAINED",             # 未解释
    "LIKELY_ERROR",            # 疑似错报
    "INSUFFICIENT_EVIDENCE",   # 证据不足
    "HUMAN_REVIEW",            # 强制人工
]

#: 置信度天花板：写进代码的治理原则——推理永远不许冒充直证。
CONFIDENCE_CAP = {"direct": 0.90, "inference": 0.70, "insufficient": 0.50}
REVIEW_THRESHOLD = 0.60


@dataclass
class AIOpinion:
    target: str
    verdict: Verdict
    confidence: float
    headline: str
    rationale: list[str]
    alternatives: list[str]
    recommended_actions: list[str]
    needs_human: bool
    evidence: list[str] = field(default_factory=list)
    score: float = 0.0
    band: dict = field(default_factory=dict)
    tags: list[dict] = field(default_factory=list)
    source: Literal["direct", "inference", "insufficient"] = "inference"
    model: str = "offline-reasoner"
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _confidence(profile: EvidenceProfile, band: Band, source: str) -> float:
    """置信度不是拍的，是三个因子的乘积，再压天花板。

    数值一致性 0.4 + 证据完整度 0.4 + 标签洁净度 0.2。
    """
    numeric = {"EXACT": 1.0, "ROUNDING": 0.95, "TRIVIAL": 0.85,
               "MINOR": 0.6, "MATERIAL": 0.35, "SIGNIFICANT": 0.15}[band.grade]
    completeness = min(1.0, profile.managed / 100)
    cleanliness = max(0.0, 1 - 0.25 * profile.conflict_count)
    raw = 0.4 * numeric + 0.4 * completeness + 0.2 * cleanliness
    return round(min(raw, CONFIDENCE_CAP[source]), 3)


#: 离线推理器：不联网、不调模型，用标签 + 差额方向给出"最可能原因"。
#: 接真模型时只需替换这个函数，签名不变。返回 (verdict, headline, rationale, alternatives, actions, tags)
Reasoner = Callable[[dict], tuple]


def offline_reasoner(ctx: dict) -> tuple:
    band: Band = ctx["band"]
    profile: EvidenceProfile = ctx["profile"]
    tags: list[str] = list(ctx.get("tags", []))
    direction: str = ctx.get("direction", "")
    label: str = ctx.get("label", "该指标")

    if band.grade in {"EXACT", "ROUNDING", "TRIVIAL"}:
        return (
            "CONSISTENT",
            f"{label}两侧在容差内一致（差额 {band.diff}），不构成差异",
            [band.narrative, f"证据完整度 {profile.managed}/100"],
            [],
            ["归档本次比对，无需后续程序"],
            tags,
        )

    # 证据缺口优先于差异归因：前提都没拿到，谈原因就是猜。但仍出分数。
    if profile.managed < 50:
        missing = "、".join(profile.unknown_names[:3]) or "关键前提"
        return (
            "INSUFFICIENT_EVIDENCE",
            f"{label}的{missing}等前提未取得原文支持，暂无法归因，风险已计入分数",
            [band.narrative, f"未获支持的前提：{missing}", f"证据完整度仅 {profile.managed}/100"],
            ["原文确实未披露该前提", "披露位置未被本次抽取覆盖", "该载体本就不披露此项"],
            ["补充检索该前提的披露位置", "若确未披露，按披露缺失处理而非数据错误"],
            tags,
        )

    if band.grade in {"MATERIAL", "SIGNIFICANT"}:
        if "SCOPE_DRIFT" in tags or "DENOMINATOR_SWITCH" in tags:
            return (
                "EXPLAINABLE_DIFFERENCE",
                f"{label}差额 {band.diff}，两处统计口径表述不同，可解释",
                [band.narrative, "两份报告的统计范围/分母表述不一致，属口径差异而非计算错误"],
                [f"{label}在另一载体采用不同合并范围", "口径调整后差额落在执行重要性以内"],
                ["索取口径调整表", "在核对底稿中记录口径差异，不调整为同一数"],
                tags,
            )
        return (
            "UNEXPLAINED",
            f"{label}差额 {band.diff} 已达重要性区间，且无口径解释",
            [band.narrative, "关键前提均已取得原文支持，差异无法归因于口径"],
            ["存在未披露的调整项", "其中一个载体的数字为笔误或旧版数据"],
            ["向编制人索取差异说明", "检查是否为版本回撤", "考虑将该指标列为重点核对项"],
            tags,
        )

    if band.grade == "MINOR":
        if ctx.get("is_ratio"):
            return (
                "PROBABLE_EXPLAINABLE",
                f"{label}相差 {band.diff} 个百分点，最可能为分母口径或计算基数差异",
                [band.narrative, "差额方向单一，未出现反向差异，符合口径差异特征而非计算错误"],
                ["分母取营业收入还是营业总收入", "分子是否含资本化部分"],
                ["核对指标定义句中的分母表述，不必重算全表"],
                tags,
            )
        return (
            "PROBABLE_EXPLAINABLE",
            f"{label}存在小额差额 {band.diff}，最可能为分项归集边界差异",
            [band.narrative, "差额方向单一，未见反向差异，符合归集口径差异特征"],
            ["四舍五入的累积效应", "分项在两次编制中的归集边界微调"],
            ["抽取一个分项做穿行测试即可，不必全量重算"],
            tags,
        )

    # 兜底：一侧数值缺失等无法归入上述分档的情形
    missing = "、".join(profile.unknown_names[:3]) or "关键前提"
    return (
        "INSUFFICIENT_EVIDENCE",
        f"{label}的{missing}等前提未取得原文支持，暂无法归因，风险已计入分数",
        [band.narrative, f"未获支持的前提：{missing}", f"证据完整度仅 {profile.managed}/100"],
        ["原文确实未披露该前提", "披露位置未被本次抽取覆盖"],
        ["补充检索该前提的披露位置", "若确未披露，按披露缺失处理而非数据错误"],
        tags,
    )


def judge(
    *,
    target: str,
    left: Decimal | None,
    right: Decimal | None,
    conditions: Sequence[ConditionView],
    base_amount: Decimal | None = None,
    exposure: float = 60.0,
    manageable: float = 85.0,
    tags: Iterable[str] = (),
    reasoner: Reasoner = offline_reasoner,
    model: str = "offline-reasoner",
    is_ratio: bool | None = None,
) -> AIOpinion:
    """一次判断的完整出口：容差 → 证据画像 → 风险分 → AI 意见。"""
    ratio_value = bool(left is not None and right is not None and max(abs(left), abs(right)) <= Decimal("1")) if is_ratio is None else is_ratio
    base = base_amount if base_amount is not None else (
        infer_base(left, right, is_ratio=ratio_value) if left is not None and right is not None else Decimal("1")
    )
    materiality = Materiality.from_base(base)
    if left is None or right is None:
        band = Band("SIGNIFICANT", Decimal(0), Decimal(0), materiality, "一侧数值缺失，无法比对")
        grade_known = False
    else:
        band = compare(left, right, materiality)
        grade_known = True

    profile = build_profile(conditions, exposure=exposure, manageable=manageable)

    ctx = {
        "band": band,
        "profile": profile,
        "tags": list(tags),
        "label": target,
        "is_ratio": ratio_value,
        "direction": "left>right" if (grade_known and left is not None and right is not None and left > right) else "",
    }
    verdict, headline, rationale, alternatives, actions, used_tags = reasoner(ctx)

    # 先有结论，再定分：可解释的差异回调，未解释的加重；标签给乘数与地板。
    raw_score = disclosure_risk(band, profile, verdict)
    score, tag_hits, floor = apply_tags(raw_score, used_tags)
    score = round(max(score, floor), 2)
    band_info = risk_band(score)

    # 无原文直证的一律按推理计，置信度压到 0.70
    source = "direct" if verdict in {"CONSISTENT", "EXPLAINABLE_DIFFERENCE", "UNEXPLAINED"} else "inference"
    if verdict == "INSUFFICIENT_EVIDENCE":
        source = "insufficient"
    confidence = _confidence(profile, band, source)
    needs_human = confidence < REVIEW_THRESHOLD or verdict in {"LIKELY_ERROR", "HUMAN_REVIEW"}

    return AIOpinion(
        target=target,
        verdict=verdict,
        confidence=confidence,
        headline=headline,
        rationale=list(rationale),
        alternatives=list(alternatives),
        recommended_actions=list(actions),
        needs_human=needs_human,
        evidence=[f"{row.name}：{row.reason}" for row in conditions if row.status == "supported"][:6],
        score=score,
        band=band_info,
        tags=tag_hits,
        source=source,
        model=model,
    )


# ---------------------------------------------------------------------------
# 五、自测：四个典型场景，直接跑就有输出
# ---------------------------------------------------------------------------

def _demo() -> None:
    cases = [
        dict(
            target="研发投入金额 2024（年报 vs ESG报告）",
            left=Decimal("128600000"), right=Decimal("128600000"),
            conditions=[ConditionView("主体", "supported", "同属标准股份，原文出现全称"),
                        ConditionView("期间", "supported", "均为2024年度"),
                        ConditionView("单位", "supported", "均为元"),
                        ConditionView("范围", "supported", "均为合并口径"),
                        ConditionView("定义", "supported", "原文行名均为研发投入金额")],
            base_amount=Decimal("128600000"),
        ),
        dict(
            target="环保投入 2024（年报 vs ESG报告）",
            left=Decimal("42180000"), right=Decimal("38980000"),
            conditions=[ConditionView("主体", "supported", "同属标准股份"),
                        ConditionView("期间", "supported", "均为2024年度"),
                        ConditionView("单位", "supported", "均为元"),
                        ConditionView("范围", "conflicting", "年报为合并口径，ESG为母公司口径"),
                        ConditionView("定义", "supported", "均含环保设施运行费")],
            base_amount=Decimal("42180000"), exposure=70.0, manageable=85.0,
            tags=["SCOPE_DRIFT"],
        ),
        dict(
            target="研发投入占营业收入比例 2024",
            left=Decimal("4.86"), right=Decimal("5.12"),
            conditions=[ConditionView("主体", "supported", "同属标准股份"),
                        ConditionView("期间", "supported", "均为2024年度"),
                        ConditionView("公式", "unknown", "未写明分母取营业收入还是营业总收入"),
                        ConditionView("单位", "supported", "均为%")],
            exposure=75.0, manageable=90.0,
            tags=["DENOMINATOR_SWITCH"],        ),
        dict(
            target="温室气体排放总量 2024（ESG报告 vs 年报）",
            left=Decimal("58200"), right=Decimal("58600"),
            conditions=[ConditionView("主体", "unknown", "ESG报告未注明主体范围"),
                        ConditionView("期间", "unknown", "未标注数据年度"),
                        ConditionView("单位", "supported", "均为吨二氧化碳当量"),
                        ConditionView("范围", "unknown", "未说明组织边界")],
            base_amount=Decimal("58200"), exposure=80.0, manageable=80.0,
            tags=["SELECTIVE_DISCLOSURE"],
        ),
    ]

    for case in cases:
        opinion = judge(**case)
        print("=" * 78)
        print(f"[{opinion.band['label']}] 风险分 {opinion.score}  |  {opinion.target}")
        print(f"结论 {opinion.verdict}  置信度 {opinion.confidence}  来源 {opinion.source}  需人工 {opinion.needs_human}")
        print(f"意见 {opinion.headline}")
        for line in opinion.rationale:
            print(f"  · 依据：{line}")
        for line in opinion.alternatives:
            print(f"  · 另一可能：{line}")
        for line in opinion.recommended_actions:
            print(f"  → 建议：{line}")
        if opinion.tags:
            print("  · 命中标签：" + "、".join(t["name"] for t in opinion.tags))


if __name__ == "__main__":
    _demo()
