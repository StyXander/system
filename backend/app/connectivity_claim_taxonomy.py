"""统一主张分类合同：九类主张、计划/实绩区分、关联证据五态与唯一状态映射。

本模块是财务穿透层（bridge）与概览语义之间唯一的分类与状态翻译来源；
前端与导出不得各自另写一套翻译，避免同一主张在不同位置显示不同语态。
分类只描述披露语态与会计属性，不判断企业实际绩效真假。
"""
from __future__ import annotations

import re

VERSION = "claim_taxonomy_v2"

# 九类主张：覆盖战略承诺到财务影响的完整链条。
CLAIM_KINDS = (
    "target",                # 目标：有基准年/目标年的量化承诺
    "policy",                # 政策/制度性承诺
    "plan",                  # 计划：拟开展、拟投入，尚未发生
    "action",                # 行动：报告期内实际开展的项目/措施
    "input",                 # 投入：资金、能耗、人力等资源投入
    "output",                # 产出：项目建成、产能形成等直接结果
    "outcome",               # 成果：减排量、节能总量等绩效结果
    "risk",                  # 风险：可持续相关风险与机遇披露
    "financial_implication", # 潜在财务影响：对资产/费用/现金流的影响表述
)

# 关联证据五态：描述"披露关联的证据支持"，不描述已验证的企业实际绩效。
LINK_STATES = (
    "supported_link",       # 原文明确支持关联
    "plausible_link",       # 合理假设，缺直接原文
    "missing_explanation",  # 公开材料中未定位到充分解释
    "refuted_link",         # 有直接相反证据
    "not_applicable",       # 本运行不适用（如行业无此机制）
)

# 语态关键词：区分承诺/目标/计划与已发生事项，防止"计划减排"写成"已减排"。
_TARGET_RE = re.compile(r"目标|力争|争取|到20\d{2}年|承诺|愿景|规划到")
_PLAN_RE = re.compile(r"拟|计划|将(?:投|建|开展|实施|推进)|预算|预计投入|安排")
_PERF_RE = re.compile(r"实现|达到|完成|同比|下降|上升|减少|节约|总计达|共计|累计|总投入|合计投入")
_ACTION_RE = re.compile(r"实施|开展|推进|建设|改造|投产|建成|投用|组织")
_OUTPUT_RE = re.compile(r"建成|投产|投用|新增.{0,12}产能|形成.{0,12}产能")
_POLICY_RE = re.compile(r"制度|管理办法|方针|体系|委员会|政策")
_RISK_RE = re.compile(r"风险|机遇|可能导[致致]|或将对|可能影响|潜在影响")
_FIN_IMPACT_RE = re.compile(r"影响(?:当期|本期)?(?:利润|成本|费用|资产|现金流)|计入(?:当期)?损益|资本化|费用化")

# 计划/实绩与会计属性：预算、拟投入、实际资本性支出、费用、现金流分别标记。
_PLANNED_VALUES = {"plan", "budget"}
_REALIZED_VALUES = {"realized"}
# 会计属性：资本性支出进入资产负债表，费用性支出进入利润表，现金流为流量口径。
_ACCOUNTING_NATURES = ("capex", "opex", "cash_out", "cash_in", "non_monetary", "unknown")


def classify_claim(text: str, amounts: list[dict] | None = None) -> dict:
    """把一句 ESG 原文分类为九类主张之一，并给出计划/实绩与语态依据。

    返回 dict：claim_kind（九类之一）、planned_or_realized（plan/budget/realized/unknown）、
    status_language（命中的语态关键词列表）、accounting_nature。
    分类只看原文语态；没有金额时默认 non_monetary，不得凭语气升级。
    """
    body = str(text or "")
    amounts = amounts or []
    status_language = []
    for name, pattern in (("target", _TARGET_RE), ("plan", _PLAN_RE), ("performance", _PERF_RE),
                          ("action", _ACTION_RE), ("policy", _POLICY_RE), ("risk", _RISK_RE),
                          ("financial_implication", _FIN_IMPACT_RE)):
        if pattern.search(body):
            status_language.append(name)
    has_money = any(amount.get("dimension") == "money" for amount in amounts)
    money_prefix = ""
    for amount in amounts:
        if amount.get("dimension") == "money":
            start = body.find(str(amount.get("text") or ""))
            if start >= 0:
                money_prefix = body[max(0, start - 24):start]
            break
    # 未来目标优先；“减少”等方向词不证明已经实现。
    achieved_target = bool(re.search(r"(?:已|提前)(?:完成|达成|实现).{0,16}目标|目标.{0,8}已(?:完成|达成|实现)", body))
    if _TARGET_RE.search(body) and not achieved_target:
        kind = "target"
    elif _PLAN_RE.search(body) and not achieved_target:
        kind = "input" if _budget_word(body) else "plan"
    elif _RISK_RE.search(body) and not _PERF_RE.search(body):
        kind = "risk"
    elif _FIN_IMPACT_RE.search(body):
        # 潜在财务影响必须带金额才是财务影响主张；否则只是风险语态，不得凭语气升级。
        kind = "financial_implication" if has_money else "risk"
    elif _POLICY_RE.search(body) and not _PERF_RE.search(body) and not has_money:
        kind = "policy"
    elif _OUTPUT_RE.search(body):
        kind = "output"
    elif _PERF_RE.search(body):
        kind = "outcome" if not has_money else "input"
    elif _ACTION_RE.search(body):
        kind = "action"
    else:
        kind = "policy"
    planned_or_realized = _phase(kind, body, money_prefix)
    return {
        "claim_kind": kind,
        "planned_or_realized": planned_or_realized,
        "status_language": status_language,
        "accounting_nature": _accounting_nature(kind, body, has_money),
        "taxonomy_version": VERSION,
    }


def _budget_word(body: str) -> bool:
    return bool(re.search(r"预算|总投资|合计投入|总投入", body))


def _phase(kind: str, body: str, money_prefix: str) -> str:
    """区分计划/预算与已发生：拟/计划/预算一律不是实绩，已/累计/实现才是实绩语态。"""
    if kind in {"target", "policy"}:
        return "plan"
    if re.search(r"拟|计划|预计|将投|预算", body + money_prefix):
        return "budget" if _budget_word(body + money_prefix) else "plan"
    if re.search(r"已(?:投|完|建|实)|累计|实现|达到|总投入|合计投入|共计|总计|报告期内.{0,12}(?:投入|支出)", body):
        return "realized"
    if kind in {"outcome", "action", "output"}:
        return "realized"
    return "unknown"


def _accounting_nature(kind: str, body: str, has_money: bool) -> str:
    """金额型主张标注会计属性；资本化/费用化/现金流不得混写为"环保投入金额"。"""
    if not has_money:
        return "non_monetary"
    if re.search(r"现金流|支付的现金", body):
        return "cash_out"
    if re.search(r"资本化|在建工程|固定资产|购建", body):
        return "capex"
    if re.search(r"费用|费用化|成本|损益", body):
        return "opex"
    return "unknown"


# 视图映射：九类主张在现有 bridge 视图（target/action/performance/commitment）中的展示类别。
# 该映射是唯一的翻译点；图谱、概览、导出都用它，不各自维护第二张表。
_CANONICAL_TO_VIEW = {
    "target": "target",
    "policy": "commitment",
    "plan": "commitment",
    "action": "action",
    "input": "performance",
    "output": "performance",
    "outcome": "performance",
    "risk": "commitment",
    "financial_implication": "performance",
}


def canonical_to_view(kind: str) -> str:
    """九类主张映射到现有视图类别；未登记类别一律回退 commitment，不猜。"""
    return _CANONICAL_TO_VIEW.get(kind, "commitment")


def observed_from_phase(planned_or_realized: str) -> str:
    """计划/实绩映射到现有 observed_or_plan 语义：plan/budget → plan，实绩 → observed。"""
    if planned_or_realized in _PLANNED_VALUES:
        return "plan"
    if planned_or_realized in _REALIZED_VALUES:
        return "observed"
    return "commitment"


# 关联五态 → 概览语义的唯一转换；概览与前端禁止各自翻译。
_LINK_TO_OVERVIEW = {
    "supported_link": "limited_support",      # 披露关联被原文支持，但仍是披露层面
    "plausible_link": "pending_evidence",     # 合理假设，待补证
    "missing_explanation": "pending_evidence",
    "refuted_link": "challenged",
    "not_applicable": "insufficient",
}


def map_link_to_overview(link_state: str) -> str:
    """把关联五态映射到概览状态词；未登记状态直接报错，不静默降级。"""
    if link_state not in _LINK_TO_OVERVIEW:
        raise ValueError(f"未登记的关联状态：{link_state}")
    return _LINK_TO_OVERVIEW[link_state]


def completion_rate_allowed(*, baseline_year: str, target_year: str, realized_period: str,
                            subject_scope: str, metric_definition: str,
                            formula_compatible: bool) -> tuple[bool, str]:
    """目标完成率门禁：基准年、目标年、实绩期间、范围、定义与公式全部齐备才允许计算。

    任一缺失都返回不允许及原因；跨年财务滞后不得用当年承诺强配当年金额。
    """
    missing = [name for name, value in (
        ("基准年", baseline_year), ("目标年", target_year), ("实绩期间", realized_period),
        ("主体范围", subject_scope), ("指标定义", metric_definition)) if not str(value or "").strip()]
    if missing:
        return False, "缺少可比前提：" + "、".join(missing) + "；不计算目标完成率。"
    if not formula_compatible:
        return False, "基准与实绩的计量方法或公式不可比；不计算目标完成率。"
    return True, "前提齐备，可计算目标完成率。"


def planned_vs_realized_conflict(claim_a: dict, claim_b: dict) -> bool:
    """两笔金额一笔是计划/预算、一笔是实绩时，不得直接对等比较。"""
    phase_a = claim_a.get("planned_or_realized", "unknown")
    phase_b = claim_b.get("planned_or_realized", "unknown")
    return ((phase_a in _PLANNED_VALUES and phase_b in _REALIZED_VALUES)
            or (phase_b in _PLANNED_VALUES and phase_a in _REALIZED_VALUES))
