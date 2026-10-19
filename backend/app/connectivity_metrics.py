"""指标身份字典：别名只帮助召回，不自动证明两个指标等价。

当前首批覆盖研发、环保、温室气体、能源和用水。字典记录规范名称、量纲、
事项、严格别名和“不得等同”的反例；范围、期间、定义仍须由原文明示。
"""
from __future__ import annotations

import re

# strict_aliases 可在同口径下作为同一指标召回；aliases 只作候选线索。
# not_equal 中的名称必须保留独立身份，避免“研发投入=研发费用”这类偷换。
METRIC_IDENTITIES: dict[str, dict] = {
    "研发投入金额": {
        "topic": "research",
        "dimension": "money",
        "strict_aliases": ("研发投入金额", "研发投入合计", "研发投入总额"),
        "aliases": ("研发投入", "研发支出", "研发总投入", "研究开发投入"),
        "not_equal": ("研发费用", "费用化研发", "资本化研发"),
        "note": "研发投入与研发费用不默认等价；资本化/费用化只作组成项或限定语",
    },
    "研发费用": {
        "topic": "research",
        "dimension": "money",
        "strict_aliases": ("研发费用", "研发费用合计"),
        "aliases": ("研究开发费用", "研发费"),
        "not_equal": ("研发投入金额", "研发投入合计"),
        "note": "研发费用是会计科目口径，不能自动替代研发投入",
    },
    "研发人员数量": {
        "topic": "research",
        "dimension": "people",
        "strict_aliases": ("研发人员数量", "研发人员总数", "研发人员合计"),
        "aliases": ("研发人员", "研发人员人数"),
        "not_equal": ("研发人员数量占比", "研发人员数量人次", "研发人员人均"),
        "note": "人次、占比与人数不是同一量纲；母公司/合并边界仍须单独核实",
    },
    "环保投入": {
        "topic": "environment",
        "dimension": "money",
        "strict_aliases": ("环保投入", "环境保护投入", "环保投入合计", "环保资金投入"),
        "aliases": ("环保资金", "环保投资", "环境保护资金", "环保支出"),
        "not_equal": ("环保费用", "环保资本化", "环保费用化"),
        "note": "环保费用与环保投入不默认等价；资本化/费用化是组成项",
    },
    "温室气体排放量": {
        "topic": "intensity",
        "dimension": "co2e",
        "strict_aliases": ("温室气体排放量", "温室气体排放总量", "碳排放量", "碳排放总量"),
        "aliases": ("范围一排放", "范围二排放", "scope1排放", "scope2排放", "ghg排放"),
        "not_equal": ("排放强度", "单位营收排放", "碳排放强度"),
        "note": "范围一/范围二与总量是组成关系；强度是比例关系，不能与总量等同",
    },
    "综合能源消耗量": {
        "topic": "intensity",
        "dimension": "standard_coal",
        "strict_aliases": ("综合能源消耗量", "综合能源消费量", "综合能耗", "能源消耗总量"),
        "aliases": ("能源消耗量", "能源消费量", "综合能源消耗"),
        "not_equal": ("能源强度", "单位产品能耗", "能源使用强度"),
        "note": "能耗总量与强度不是同一指标；折标煤与实物量不能无依据互换",
    },
    "年度总用水量": {
        "topic": "intensity",
        "dimension": "volume",
        "strict_aliases": ("年度总用水量", "总用水量", "总取水量", "取水总量"),
        "aliases": ("取水量", "用水量", "新鲜水取用量", "新水取用量"),
        "not_equal": ("用水强度", "取水强度", "单位产品用水量"),
        "note": "取水与用水、总用水与单位强度不能自动等同",
    },
    "营业收入": {
        "topic": "intensity",
        "dimension": "money",
        "strict_aliases": ("营业收入", "营业总收入", "主营业务收入"),
        "aliases": ("营收",),
        "not_equal": ("营业收入占比", "收入增长率"),
        "note": "营业收入可作为强度分母，但不能与强度指标本身等同",
    },
}

MODIFIER_PATTERNS = (
    ("capitalized", re.compile(r"资本化")),
    ("expensed", re.compile(r"费用化|费用化支出")),
    ("total", re.compile(r"合计|总计|总额|总投入|总量")),
    ("component", re.compile(r"其中|分项|明细|组成部分")),
    ("intensity", re.compile(r"强度|单位营收|单位产品|占比|比例|率$")),
)

CURRENCY_WORDS = ("人民币", "美元", "港元", "欧元", "日元")
_ASCII = re.compile(r"[a-z0-9]")


def compact_label(label: str) -> str:
    """去掉空白、单位和行次标点，保留可用于身份比较的业务名称。"""
    text = re.sub(r"\s+", "", str(label or ""))
    text = re.sub(r"[（(][^）)]{0,20}[）)]", "", text)
    text = re.sub(r"^[一二三四五六七八九十百]+[、.．]", "", text)
    return text.strip("：:，,。；;·-—_")


def _contains(text: str, needle: str) -> bool:
    if not needle:
        return False
    if _ASCII.search(needle):
        return needle.lower() in text.lower()
    return needle in text


def metric_modifier(label: str) -> str:
    """识别资本化/费用化/合计/强度等限定语，限定语不改变指标身份但改变可比范围。"""
    compact = compact_label(label)
    for name, pattern in MODIFIER_PATTERNS:
        if pattern.search(compact):
            return name
    return ""


def _not_equal_hit(compact: str, canonical: str, spec: dict) -> str:
    for name in spec.get("not_equal", ()):
        if _contains(compact, name) and name != canonical:
            return name
    return ""


def metric_identity(label: str) -> dict:
    """返回规范指标身份；未登记指标返回空身份并明确 match=none。

    先检查“不得等同”的反例，再匹配严格别名和普通别名，避免研发费用被
    研发投入的别名抢先召回。
    """
    compact = compact_label(label)
    empty = {"metric_id": "", "canonical": "", "topic": "", "dimension": "",
             "match": "none", "equivalence": "none", "modifier": metric_modifier(label),
             "source_label": str(label or ""), "note": "未登记指标身份，不能自动跨报告配对"}
    if not compact:
        return empty
    # 反例优先：例如“研发费用”不能被“研发投入”的别名吞掉。
    for canonical, spec in METRIC_IDENTITIES.items():
        if _not_equal_hit(compact, canonical, spec):
            continue
        strict = (canonical,) + tuple(spec.get("strict_aliases", ()))
        if any(_contains(compact, name) for name in strict):
            return {"metric_id": canonical, "canonical": canonical, "topic": spec["topic"],
                    "dimension": spec["dimension"], "match": "exact", "equivalence": "exact",
                    "modifier": metric_modifier(label), "source_label": str(label or ""),
                    "note": spec.get("note", "")}
    for canonical, spec in METRIC_IDENTITIES.items():
        if _not_equal_hit(compact, canonical, spec):
            continue
        aliases = tuple(spec.get("aliases", ()))
        if any(_contains(compact, name) for name in aliases):
            return {"metric_id": canonical, "canonical": canonical, "topic": spec["topic"],
                    "dimension": spec["dimension"], "match": "alias", "equivalence": "limited",
                    "modifier": metric_modifier(label), "source_label": str(label or ""),
                    "note": "别名只作召回线索；仍须原文证明定义、范围与期间一致"}
    return empty


def classify_topic(label: str) -> str:
    """按指标身份返回事项；未登记时交由原有关键词召回。"""
    return metric_identity(label).get("topic", "")


def currency_in_text(text: str) -> str:
    """只在原文明确写出币种时返回代码，不从“元”字推定币种。"""
    for word, code in (("人民币", "CNY"), ("美元", "USD"), ("港元", "HKD"), ("欧元", "EUR"), ("日元", "JPY")):
        if word in str(text or ""):
            return code
    return ""


MACRO_PREFIX = re.compile(r"^(?:我国|全国|国内|全行业|行业|全球|全省|全市|全社会)")
MACRO_WORDS = re.compile(r"价格指数|行业平均|同业平均|行业总产量|全国总产量|宏观|统计公报|景气指数")
COMPANY_WORDS = re.compile(r"本公司|公司|本集团|集团|母公司|合并范围")


def content_classification(label: str, heading: str = "") -> tuple[str, str]:
    """区分公司自身披露与宏观/行业背景；返回类别和可复核理由。

    只在标签或表标题明确出现“我国/全国/行业/指数”等宏观标记时排除；
    公司自己的“粗钢产量”不能因为表标题含行业背景就被误删。
    """
    label_text = re.sub(r"\s+", "", str(label or ""))
    heading_text = re.sub(r"\s+", "", str(heading or ""))
    if MACRO_PREFIX.search(label_text) or MACRO_WORDS.search(label_text):
        if not re.search(r"本公司|公司自身", label_text):
            return "macro", "标签属于全国/行业统计或价格指数，不是公司自身指标"
    if COMPANY_WORDS.search(label_text):
        return "company", ""
    if MACRO_PREFIX.search(heading_text) or MACRO_WORDS.search(heading_text):
        if COMPANY_WORDS.search(heading_text):
            return "company", ""
        return "industry", "表标题为行业/全国统计背景，未证明属于公司自身披露"
    return "company", ""
