"""文本与金额工具：单一口径来源，避免各模块各写一套解析。

底层复用 connectivity_financial_bridge 中已被真实报告验证过的实现，
这里只做类型化封装，不重复实现数字、单位与句子切分。
"""
from __future__ import annotations


def project_key(value: str) -> str:
    """只忽略脚注标记，保留基地、一期/二期等具有业务身份意义的限定。"""
    import re
    return compact(re.sub(r'[（(]注\s*\d+[）)]|[①②③④⑤⑥⑦⑧⑨⑩]', '', str(value or '')))

import re
from decimal import Decimal

from ..connectivity_financial_bridge import (
    _amounts as _raw_amounts,
    _compact as compact,
    _decimal as decimal,
    _page_text as page_text,
    _sentences as sentences,
)
from .models import Amount, AmountNature, Stage

__all__ = ["compact", "decimal", "sentences", "page_text", "to_amounts",
           "detect_stage", "detect_amount_nature", "activity_type", "clean_quote"]


NATURE_RULES: tuple[tuple[AmountNature, re.Pattern], ...] = (
    (AmountNature.CLOSING_BALANCE, re.compile(r"期末余额|期末数|年末余额")),
    (AmountNature.OPENING_BALANCE, re.compile(r"期初余额|期初数|年初余额")),
    (AmountNature.BUDGET, re.compile(r"预算数|预算金额|计划投资总额|总投资额|投资总额")),
    (AmountNature.TRANSFER_OUT, re.compile(r"转入固定资产|转固|转入")),
    (AmountNature.PERIOD_INCREASE, re.compile(r"本期增加|本年增加|增加金额")),
    (AmountNature.PERIOD_DECREASE, re.compile(r"本期减少|本年减少|减少金额")),
    (AmountNature.EXPENSE, re.compile(r"费用|支出计入当期|计入管理费用|计入销售费用")),
    (AmountNature.ACTUAL_PAYMENT, re.compile(r"现金支付|支付的现金|已支付|实付")),
    (AmountNature.INVESTMENT_INCURRED, re.compile(r"总投入|累计投入|投入超|投资超|已完成投资")),
    (AmountNature.PLANNED_INVESTMENT, re.compile(r"拟投资|计划投资|预计投资|将投资|规划投资"
                                                 r"|(?:计划|拟|预计|未来).{0,10}(?:投资|投入)")),
    (AmountNature.PERFORMANCE, re.compile(r"节能量|减排量|处理能力|回用水量|综合利用量")),
)

STAGE_RULES: tuple[tuple[Stage, re.Pattern], ...] = (
    (Stage.SETTLED, re.compile(r"已结算|已支付|已投运并结算")),
    (Stage.RECOGNIZED, re.compile(r"已确认为|已计入在建工程|已计入固定资产|已计入当期损益")),
    (Stage.COMPLETED, re.compile(r"已建成|建成投产|竣工|完工|已投运|已投产|完成建设")),
    (Stage.EXECUTING, re.compile(r"在建|实施中|推进中|建设中|施工中|改造中|正在实施|已开工|投运|投产")),
    (Stage.CONTRACTED, re.compile(r"已签约|签订合同|合同金额|中标|已签署|签订协议")),
    (Stage.STRATEGY, re.compile(r"战略|愿景|承诺|力争|总体目标|规划期|十四五|十五五")),
    (Stage.PLANNED, re.compile(r"拟建|拟投资|拟投入|拟于|拟在|计划投资|计划投入|计划在|预计投资|规划建设"
                               r"|将投资|将投入|开展前期|可行性研究|未来\s*\d+\s*年")),
)

ACTIVITY_RULES: tuple[tuple[str, str, re.Pattern], ...] = (
    ("carbon_compliance", "碳排放履约与碳资产", re.compile(r"碳配额|碳履约|碳资产|碳交易|CCER|核查排放|碳排放权")),
    ("restoration_obligation", "环境修复与退役义务", re.compile(r"生态修复|矿山修复|退役|封场|闭库|土壤修复|复垦")),
    ("pollution_treatment", "环境污染治理", re.compile(r"污染治理|废水处理|污水处理|脱硫|脱硝|除尘|固废|危废|超低排放|治理项目")),
    ("green_rnd", "绿色研发项目", re.compile(r"绿色研发|低碳技术研发|氢冶金|绿色工艺|研发项目|技术攻关|试验线")),
    ("green_equipment", "绿色设备购置", re.compile(r"购置|采购设备|引进设备|更换设备|设备更新")),
    ("efficiency_retrofit", "节能减排技术改造", re.compile(r"节能改造|技术改造|技改|余热|余压|变频|高效电机|节能降碳改造")),
    ("facility_retrofit", "环保设施建设与改造",
     re.compile(r"环保设施|环保工程|建设改造|新建项目|扩建|配套设施|配套建设|绿色制造|超低排放改造"
                r"|沼气|生物质|分布式光伏|风电|储能|中水回用|水资源回用")),
)


def to_amounts(text: str, period: str = "") -> list[Amount]:
    """把一句原文中的数值转成带性质的金额；性质只由本句限定语判断。"""
    nature = detect_amount_nature(text)
    result = []
    for raw in _raw_amounts(text):
        result.append(Amount(
            raw=str(raw.get("raw") or ""),
            value=str(raw.get("value") or ""),
            unit=str(raw.get("unit") or ""),
            dimension=str(raw.get("dimension") or ""),
            normalized=str(raw.get("normalized") or ""),
            nature=nature if raw.get("dimension") == "money" else AmountNature.PERFORMANCE,
            qualifier=str(raw.get("qualifier") or "exact"),
            period=period,
        ))
    return result


def detect_amount_nature(text: str) -> AmountNature:
    """金额性质：同一句里同时出现预算与支出时，按最具体的限定语优先。"""
    for nature, pattern in NATURE_RULES:
        if pattern.search(text):
            return nature
    return AmountNature.NONE


def detect_stage(text: str) -> Stage:
    for stage, pattern in STAGE_RULES:
        if pattern.search(text):
            return stage
    return Stage.UNKNOWN


def activity_type(text: str) -> tuple[str, str]:
    for key, label, pattern in ACTIVITY_RULES:
        if pattern.search(text):
            return key, label
    return "other", "其他可持续事项"


def clean_quote(text: str) -> str:
    """去掉项目符号与页眉噪声，保留可直接回查的原文。"""
    value = re.sub(r"^[\s•·□■☑√⌧*\-—]+", "", str(text or ""))
    value = re.sub(r"\s+", "", value)
    return value[:400]


LEADING_VERBS = ("配套建设", "投资建设", "建设", "实施", "推进", "开展", "建成", "投运", "新建扩建")
NAME_STOPWORDS = ("承诺", "不低于", "分红", "股利", "目标", "议题", "矩阵", "排名", "品牌价值",
                   "毛利率", "净利润", "营业收入", "每股", "原则", "政策", "规划", "战略",
                   "碳达峰", "碳中和", "双碳", "绿色低碳运营", "ESG")


def project_name(sentence: str) -> str:
    """抽取项目名。只接受书名号、引号或明确的工程类后缀；含财务指标词的片段一律丢弃。"""
    for candidate in re.findall(r"[《“\"]([^》”\"]{4,40})[》”\"]", sentence):
        if not any(word in candidate for word in NAME_STOPWORDS):
            return candidate
    for match in re.finditer(r"([\u4e00-\u9fffA-Za-z0-9（）()·\-+＋]{4,40}?(?:项目|工程|改造|生产线|装置|设施))", sentence):
        candidate = match.group(1)
        candidate = re.sub(r"^(?:20\d{2}年|本年度|报告期内|我们|公司|本公司|其中|以及|并将|拟对|对)+", "", candidate)
        if any(word in candidate for word in NAME_STOPWORDS):
            continue
        candidate = _after_last_verb(candidate)
        if candidate.endswith(("改造", "建设", "扩建")) and candidate + "项目" in sentence:
            candidate = candidate + "项目"
        if len(candidate) < 5:
            continue
        return candidate
    return ""


NAME_VERBS = ("建设", "投资", "新建", "扩建", "实施", "改造", "推进", "开展", "建成", "投运")


def _after_last_verb(candidate: str) -> str:
    """项目名可能带“计划投资5亿元建设”这类前缀；含金额时取最后一个动词之后的部分。"""
    has_amount = bool(re.search(r"\d", candidate)) or any(word in candidate for word in ("计划", "拟", "投资", "投入"))
    best = candidate
    for verb in NAME_VERBS:
        position = candidate.rfind(verb)
        if position < 0:
            continue
        remainder = candidate[position + len(verb):]
        if len(remainder) >= 5 or (has_amount and len(remainder) >= 4):
            if len(remainder) < len(best):
                best = remainder
    return best


def strip_leading_verbs(name: str) -> str:
    value = str(name or "")
    for verb in sorted(LEADING_VERBS, key=len, reverse=True):
        if value.startswith(verb) and len(value) > len(verb) + 4 and not value.startswith("新建集中"):
            return value[len(verb):]
    return value


def period_from_text(text: str, default: str = "") -> str:
    years = re.findall(r"(20\d{2})\s*年", text)
    if years:
        return years[-1]
    return default
