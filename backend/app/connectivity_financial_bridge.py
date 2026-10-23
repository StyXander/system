"""可持续主张与财务项目的穿透关联：只登记能回到原页的节点和受控关系。

设计边界（比赛与专业用途都必须成立）：
- 主张、财务节点、关系候选全部来自已登记 PDF 的原文或表格；模型不新增来源。
- 数值接近只是候选，必须同时通过主体、期间、定义、范围条件才能升级为直接关联。
- 语义相同、名称相似、金额接近都不等于经济因果成立；缺口必须显式保留。
- 年报没有逐项对应金额时，输出“有限支持/待补证”，不把总额硬拆到某个科目。
"""
from __future__ import annotations

import hashlib
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .connectivity_claim_taxonomy import classify_claim, canonical_to_view, observed_from_phase
from .connectivity_financial_ontology import evaluate_mapping

VERSION = "financial_bridge_v1"

# 行业配置：只影响召回词与情景参数，不改变证据门槛。
INDUSTRY_PROFILES = {
    "steel": {
        "name": "钢铁/高耗能制造",
        "claim_terms": ("节能", "低碳", "减排", "碳排放", "超低排放", "环保", "绿色", "能耗", "余热",
                        "焦化", "烧结", "固废", "光伏", "绿电", "风电", "储能", "循环"),
        "project_terms": ("绿色", "低碳", "节能", "环保", "污水", "固废", "生态", "清洁能源",
                          "光伏", "风电", "余热", "超低排放", "焦化", "烧结", "零碳"),
        "link_terms": ("节能", "低碳", "绿色制造", "超低排放", "环保搬迁", "固废", "污水",
                       "焦化", "烧结", "光伏", "绿电", "生物质", "余热", "节水"),
        "scenario": {"kind": "energy_cost", "unit": "吨标准煤", "price_unit": "元/吨标准煤",
                     "price_base": "850", "price_low": "700", "price_high": "1000",
                     "label": "标准煤价格假设", "source": "用户输入假设，不是企业实际采购价"},
    },
    "food_beverage": {
        "name": "食品饮料/消费品制造",
        "claim_terms": ("节能", "节水", "减排", "污水", "废水", "固废", "绿色", "清洁能源",
                        "沼气", "生物质", "光伏", "水耗", "包装", "循环"),
        "project_terms": ("污水", "废水", "节能", "环保", "沼气", "生物质", "光伏",
                          "清洁能源", "绿色包装", "可循环包装"),
        "link_terms": ("节能", "节水", "污水", "废水", "固废", "沼气", "生物质", "光伏",
                       "包装", "水耗", "清洁能源"),
        "scenario": {"kind": "water_cost", "unit": "立方米", "price_unit": "元/立方米",
                     "price_base": "4.5", "price_low": "3.0", "price_high": "6.0",
                     "label": "水资源价格假设", "source": "用户输入假设，不是企业实际水价"},
    },
    "general": {
        "name": "通用制造",
        "claim_terms": ("节能", "减排", "环保", "绿色", "低碳", "能耗", "水耗", "固废", "研发"),
        "project_terms": ("绿色", "低碳", "节能", "环保", "污水", "固废", "生态", "技改"),
        "link_terms": ("节能", "减排", "环保", "绿色", "低碳", "固废", "污水", "研发"),
        "scenario": {"kind": "none", "unit": "", "price_unit": "", "price_base": "",
                     "price_low": "", "price_high": "", "label": "", "source": ""},
    },
}

# 同一业务主题的别名组：只用于召回，不证明两个项目是同一项目。
TERM_GROUPS = {
    "节能": ("节能", "能效", "余热", "节能量", "能耗强度"),
    "低碳": ("低碳", "降碳", "绿色制造", "绿色低碳", "零碳", "绿色"),
    "超低排放": ("超低排放", "脱硫", "脱硝", "除尘", "废气治理"),
    "环保": ("环保", "环境保护", "环境治理", "环保搬迁", "环保设施", "污水", "废水", "固废"),
    "焦化": ("焦化", "焦炉"),
    "烧结": ("烧结", "环冷机", "球团"),
    "固废": ("固废", "固体废物", "钢渣", "堆场", "资源化"),
    "污水": ("污水", "废水", "水处理", "中水", "再生水"),
    "节水": ("节水", "水耗", "取水", "用水"),
    "光伏": ("光伏", "分布式光伏"),
    "绿电": ("绿电", "绿色电力", "绿证"),
    "生物质": ("生物质", "沼气", "热电联产"),
    "包装": ("包装", "包材", "瓶"),
    "研发": ("研发", "研究开发", "研发投入", "研发费用"),
}

FINANCIAL_LINES = (
    ("CAPEX_CASH", ("购建固定资产、无形资产和其他长期资产支付的现金",), "capex_cash",
     "现金流量表—购建固定资产、无形资产和其他长期资产支付的现金"),
    ("CONSTRUCTION", ("在建工程",), "construction", "资产负债表—在建工程"),
    ("FIXED_ASSETS", ("固定资产",), "fixed_assets", "资产负债表—固定资产"),
    ("RND_EXPENSE", ("研发费用",), "rnd_expense", "利润表—研发费用"),
    ("OPERATING_COST", ("营业成本",), "operating_cost", "利润表—营业成本"),
    ("REVENUE", ("营业收入",), "revenue", "利润表—营业收入"),
    ("ENVIRONMENT", ("环保费用", "环境治理", "环保投入", "环保支出"), "environmental_expense",
     "附注—环保项目/费用"),
)

MONEY_UNITS = {"元": Decimal(1), "千元": Decimal(1000), "万元": Decimal(10000), "亿元": Decimal(100000000)}
ENERGY_UNITS = {"吨标准煤": Decimal(1), "吨标煤": Decimal(1), "万吨标准煤": Decimal(10000),
                "万吨标煤": Decimal(10000)}
# 碳排放独立计量，不能将二氧化碳当量乘以煤价。
EMISSION_UNITS = {"吨二氧化碳当量": Decimal(1), "吨CO2e": Decimal(1),
                  "万吨二氧化碳当量": Decimal(10000), "万吨CO2e": Decimal(10000)}
MASS_UNITS = {"吨": Decimal(1), "万吨": Decimal(10000)}
VOLUME_UNITS = {"立方米": Decimal(1), "万立方米": Decimal(10000)}
ELECTRICITY_UNITS = {"千瓦时": Decimal(1), "万千瓦时": Decimal(10000), "万度": Decimal(10000),
                     "亿千瓦时": Decimal(100000000), "亿度": Decimal(100000000)}

UNIT_PATTERN = ("亿元|万元|千元|元|万吨标准煤|万吨标煤|万吨二氧化碳当量|万吨CO2e|"
                "吨标准煤|吨标煤|吨二氧化碳当量|吨CO2e|万吨|吨|亿千瓦时|万千瓦时|"
                "亿度|万度|千瓦时|万立方米|立方米")
AMOUNT_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(" + UNIT_PATTERN + r")")

TARGET_RE = re.compile(r"目标|计划|承诺|拟|将|力争|到\s*20\d{2}\s*年")
PERFORMANCE_RE = re.compile(r"完成|建成|投运|实现|达到|已达成|减少|降低|下降|提升|节约")
ACTION_RE = re.compile(r"投入|投资|实施|开展|推进|建设|改造|采购|使用|建成|布局|完成")

PROJECT_TOTAL_RE = re.compile(r"总投入|总投资|合计投入|累计投入|投入超|投资超")


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _cell(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _decimal(value: str) -> Decimal | None:
    text = str(value or "").replace(",", "").replace("，", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _unit_dimension(unit: str) -> str:
    if unit in MONEY_UNITS:
        return "money"
    if unit in ENERGY_UNITS:
        return "energy"
    if unit in EMISSION_UNITS:
        return "co2"
    if unit in MASS_UNITS:
        return "mass"
    if unit in VOLUME_UNITS:
        return "volume"
    if unit in ELECTRICITY_UNITS:
        return "electricity"
    return ""


def _normalized(value: Decimal, unit: str) -> tuple[Decimal, str] | None:
    for table, dimension in ((MONEY_UNITS, "money"), (ENERGY_UNITS, "energy"), (EMISSION_UNITS, "co2"), (MASS_UNITS, "mass"),
                             (VOLUME_UNITS, "volume"), (ELECTRICITY_UNITS, "electricity")):
        if unit in table:
            return value * table[unit], dimension
    return None


def _sentences(block: str) -> list[str]:
    """按中文句末标点切句；PDF 换行先合并，避免把一句话拆成两个节点。"""
    text = re.sub(r"[ \t\u3000]+", "", str(block or ""))
    text = re.sub(r"\n+", "", text)
    parts = re.split(r"(?<=[。！？；])", text)
    return [part.strip() for part in parts if 12 <= len(part.strip()) <= 360]


def _amounts(text: str) -> list[dict]:
    result = []
    for match in AMOUNT_RE.finditer(text):
        raw, unit = match.group(1), match.group(2)
        value = _decimal(raw)
        if value is None:
            continue
        dimension = _unit_dimension(unit)
        prefix = text[max(0, match.start() - 24):match.start()]
        if dimension == "mass" and re.search(r"碳|CO2|二氧化碳|温室气体", prefix):
            dimension = "co2"
        if dimension == "mass" and re.search(r"标煤|标准煤", unit):
            dimension = "energy"
            unit = unit.replace("万吨", "万吨标准煤") if unit == "万吨" else unit
        normalized = _normalized(value, unit)
        if normalized is None:
            continue
        before_number = text[max(0, match.start() - 8):match.start()]
        after_unit = text[match.end():match.end() + 3]
        # 限定语须贴近数值；“节约用水”的“约”不是近似符号。
        qualifier = ("upper_bound" if re.search(r"(?:至多|不超过|不高于)\s*$", before_number) or after_unit.startswith("以下") else
                     "lower_bound" if re.search(r"(?:超过|超|至少|不低于)\s*$", before_number) or after_unit.startswith("以上") else
                     "approximate" if re.search(r"(?:大约|(?<!节)约|近)\s*$", before_number) else "exact")
        result.append({"raw": raw, "value": value, "unit": unit, "dimension": dimension,
                       "normalized": normalized[0], "text": match.group(0),
                       "qualifier": qualifier})
    return result


def _claim_kind(text: str, amounts: list[dict]) -> tuple[str, str]:
    """承诺/目标、行动、绩效分开；计划减排不能写成已减排。"""
    has_target = bool(TARGET_RE.search(text))
    has_perf = bool(PERFORMANCE_RE.search(text))
    has_action = bool(ACTION_RE.search(text))
    if has_target and not has_perf:
        return "target", "plan"
    if has_perf:
        return "performance", "observed"
    if has_action:
        return "action", "observed"
    return "commitment", "commitment"


def _topic(text: str, profile: dict) -> str:
    for term in profile["claim_terms"]:
        if term in text:
            return term
    return "可持续披露"


def _page_text(page: dict) -> str:
    blocks = page.get("blocks") or []
    if blocks:
        return "\n".join(str(block) for block in blocks)
    return str(page.get("text") or "")


def _claim_score(sentence: str, amounts: list[dict], kind: str) -> int:
    score = 0
    if amounts:
        score += 3
    if kind == "performance":
        score += 2
    if kind == "target":
        score += 1
    if PROJECT_TOTAL_RE.search(sentence):
        score += 3
    if re.search(r"投入|投资|实施|改造|建成|开展|推进", sentence):
        score += 1
    if len(re.findall(r"\d", sentence)) > 8:
        score -= 4
    if re.search(r"目录|指标|单位|序号|备注|页码", sentence):
        score -= 2
    return score


def extract_claims(pages: list[dict], document, profile: dict, *, limit: int = 14) -> list[dict]:
    """从 ESG 报告中抽取句子级主张，保留页码、原句与语态。"""
    candidates = []
    seen = set()
    for page in pages:
        page_no = int(page.get("page") or 0)
        text = _page_text(page)
        for block in (page.get("blocks") or [text]):
            for sentence in _sentences(block):
                if not any(term in sentence for term in profile["claim_terms"]):
                    continue
                if not (TARGET_RE.search(sentence) or PERFORMANCE_RE.search(sentence)
                        or ACTION_RE.search(sentence) or "投入" in sentence):
                    continue
                amounts = _amounts(sentence)
                kind, observed = _claim_kind(sentence, amounts)
                if not amounts and kind != "target":
                    continue
                # 统一主张分类：九类语态与计划/实绩、会计属性由 taxonomy 唯一定义；
                # 视图类别 claim_kind 保持既有取值，避免破坏下游消费与历史结果。
                taxonomy = classify_claim(sentence, amounts)
                kind = canonical_to_view(taxonomy["claim_kind"])
                observed = observed_from_phase(taxonomy["planned_or_realized"])
                sentence = re.sub(r"^[\s•·□■☑√⌧*\-—]+", "", sentence)
                compact = _compact(sentence)
                if compact.startswith("钢股份") and "宝钢股份" in _compact(text):
                    # PDF 分块偶尔把公司名首字切到上一块；只补回可核对的固定前缀。
                    sentence = "宝" + sentence
                    compact = _compact(sentence)
                if compact in seen:
                    continue
                seen.add(compact)
                score = _claim_score(sentence, amounts, kind)
                if score <= 0:
                    continue
                candidates.append({
                    "claim_id": "CLAIM-" + hashlib.sha256(
                        f"{document.document_id}|{page_no}|{compact}".encode()).hexdigest()[:10].upper(),
                    "document_id": document.document_id,
                    "company": document.company,
                    "company_id": document.company_id,
                    "report_type": "ESG",
                    "pdf_page": page_no,
                    "quote": sentence[:1500],
                    "text": sentence[:600],
                    "claim_kind": kind,
                    "claim_kind_canonical": taxonomy["claim_kind"],
                    "planned_or_realized": taxonomy["planned_or_realized"],
                    "accounting_nature": taxonomy["accounting_nature"],
                    "status_language": taxonomy["status_language"],
                    "observed_or_plan": observed,
                    "topic": _topic(sentence, profile),
                    "amounts": amounts,
                    "value": amounts[0]["raw"] if amounts else "",
                    "unit": amounts[0]["unit"] if amounts else "",
                    "year": _claim_year(sentence, document),
                    "reported_period": str(document.period),
                    "realized_period": str(document.period) if observed == "observed" else "",
                    "target_year": (re.search(r"到\s*(20\d{2})\s*年", sentence).group(1)
                                    if re.search(r"到\s*(20\d{2})\s*年", sentence) else ""),
                    "baseline_year": (re.search(r"(?:以|较)\s*(20\d{2})\s*年", sentence).group(1)
                                      if re.search(r"(?:以|较)\s*(20\d{2})\s*年", sentence) else ""),
                    "subject_scope": _claim_scope(sentence),
                    "reporting_entity": document.company,
                    "accounting_scope": _claim_scope(sentence),
                    "metric_definition": _definition_hint(sentence),
                    "page_verified": compact in _compact(text),
                    "evidence_hash": hashlib.sha256(compact.encode()).hexdigest()[:16],
                    "_score": score,
                })
    candidates.sort(key=lambda item: (-item["_score"], item["pdf_page"]))
    selected = candidates[:limit]
    for item in selected:
        item.pop("_score", None)
    return selected


def _claim_year(sentence: str, document) -> str:
    years = re.findall(r"(20\d{2})\s*年", sentence)
    return years[0] if years else str(document.period)


def _claim_scope(sentence: str) -> str:
    if re.search(r"各基地|四基地|所属基地|全部基地", sentence):
        return "多基地"
    if re.search(r"母公司|单体", sentence):
        return "母公司"
    if re.search(r"子公司|基地|厂区", sentence):
        return "单一时点/单项目"
    return "公司/合并范围未明示"


def _definition_hint(sentence: str) -> str:
    if PROJECT_TOTAL_RE.search(sentence):
        return "项目/行动总投入口径"
    if re.search(r"吨标煤|标准煤|节能量", sentence):
        return "节能量（折标煤）"
    if re.search(r"碳排放|CO2|二氧化碳", sentence):
        return "碳排放量"
    if re.search(r"水耗|用水|取水", sentence):
        return "水资源使用量"
    return "可持续披露指标"


def _project_amounts(row: list[str], header: list[str]) -> list[dict]:
    mapping = {}
    for index, name in enumerate(header):
        compact = _compact(name)
        if "预算" in compact:
            mapping.setdefault("budget", index)
        elif "本期增加" in compact:
            mapping.setdefault("current", index)
        elif "期末余额" in compact:
            mapping.setdefault("ending", index)
        elif "期初余额" in compact:
            mapping.setdefault("opening", index)
        elif "转入固定资产" in compact:
            mapping.setdefault("transferred", index)
    amounts = []
    for kind, label in (("budget", "预算数"), ("current", "本期增加金额"),
                        ("ending", "期末余额"), ("opening", "期初余额")):
        index = mapping.get(kind)
        if index is None or index >= len(row):
            continue
        value = _decimal(row[index])
        if value is None:
            continue
        amounts.append({"kind": label, "value": value, "unit": "元", "dimension": "money",
                        "normalized": value, "raw": str(value)})
    return amounts


def extract_financial_nodes(pages: list[dict], document, profile: dict, *, limit: int = 18) -> list[dict]:
    """从年报表格抽取财务项目；项目表优先，其次报表行与附注行。"""
    nodes = []
    seen = set()
    last_project_header = None
    for page in pages:
        page_no = int(page.get("page") or 0)
        # 财务表格核验用原始页文本；blocks 用于主张切句，可能不含表格行。
        text = str(page.get("text") or _page_text(page))
        for table in page.get("tables") or []:
            rows = [[_cell(cell) for cell in row] for row in table]
            if not rows:
                continue
            header_index = _header_index(rows)
            if header_index is None:
                # 跨页续表没有表头时，沿用上一页的项目表表头；只接受明显的数据行。
                if last_project_header and _looks_like_project_rows(rows):
                    nodes.extend(_project_nodes(rows, last_project_header, document, page_no, profile, text))
                continue
            header = rows[header_index]
            is_project = any("项目名称" in _compact(cell) for cell in header)
            if is_project:
                last_project_header = header
                nodes.extend(_project_nodes(rows[header_index + 1:], header, document, page_no, profile, text))
            else:
                nodes.extend(_statement_nodes(rows[header_index + 1:], header, document, page_no, text, profile))
        # 表格识别失败时的保守兜底：只在页面出现明确标签时尝试。
        table_roles = {(node["pdf_page"], node["industry_role"]) for node in nodes}
        fallback = _regex_nodes(text, document, page_no)
        nodes.extend(node for node in fallback
                     if (node["pdf_page"], node["industry_role"]) not in table_roles)
        if len(nodes) >= limit * 2:
            break
    # 去重并优先保留项目行、资本开支、在建工程、营业成本。
    priority = {"green_project": 0, "capex_cash": 1, "construction": 2, "operating_cost": 3,
                "rnd_expense": 4, "environmental_expense": 5, "revenue": 6, "fixed_assets": 7}
    unique = {}
    for node in nodes:
        key = (node["document_id"], node["pdf_page"], node["label"], node["value"], node["value_kind"])
        if key in seen:
            continue
        seen.add(key)
        unique[key] = node
    ordered = sorted(unique.values(), key=lambda item: (priority.get(item["industry_role"], 9),
                                                       item["pdf_page"], item["label"]))
    # 同一页同一科目可能因合计/其中/串列出现多个数：保留最小合理值，避免把附注号拼进金额。
    by_role = {}
    for node in ordered:
        role = node["industry_role"]
        if role in {"capex_cash", "construction", "operating_cost", "rnd_expense", "revenue", "fixed_assets"}:
            key = (node["document_id"], node["pdf_page"], role)
            if key in by_role:
                try:
                    if Decimal(node["value"]) < Decimal(by_role[key]["value"]):
                        by_role[key] = node
                except InvalidOperation:
                    pass
                continue
            by_role[key] = node
    kept = {id(node) for node in by_role.values()} | {
        id(node) for node in ordered if node["industry_role"] in {"green_project", "environmental_expense"}}
    selected = [node for node in ordered if id(node) in kept][:limit]
    for node in selected:
        node.pop("_score", None)
    return selected


def _looks_like_project_rows(rows: list[list[str]]) -> bool:
    """跨页续表的第一行通常是项目名而不是表头；至少两个金额列才算数据行。"""
    if not rows:
        return False
    first = rows[0]
    if len(first) < 6:
        return False
    if any("项目名称" in _compact(cell) for cell in first):
        return False
    numeric = sum(1 for cell in first[1:] if _decimal(cell) is not None)
    return numeric >= 2 and bool(_compact(first[0]))


def _header_index(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows[:6]):
        compact = [_compact(cell) for cell in row]
        if any("项目名称" in cell for cell in compact):
            return index
        if any(cell in {"项目", "项目名称"} for cell in compact) and any(
                "余额" in cell or "本期" in cell or "年度" in cell for cell in compact):
            return index
    return None


def _project_nodes(rows, header, document, page_no, profile, page_text: str) -> list[dict]:
    result = []
    for row in rows:
        if not row:
            continue
        name = _compact(row[0])
        if not name or name in {"合计", "总计", "小计"}:
            continue
        if not any(term in name for term in profile["project_terms"]):
            continue
        amounts = _project_amounts(row, header)
        if not amounts:
            continue
        primary = next((item for item in amounts if item["kind"] == "本期增加金额"), amounts[0])
        quote = " | ".join(cell for cell in row if cell)[:1200]
        result.append({
            "node_id": "FIN-" + hashlib.sha256(
                f"{document.document_id}|{page_no}|{name}|{primary['kind']}".encode()).hexdigest()[:10].upper(),
            "document_id": document.document_id,
            "company": document.company,
            "company_id": document.company_id,
            "report_type": "AR",
            "pdf_page": page_no,
            "label": name[:120],
            "financial_statement_line": "在建工程—重要在建工程项目—" + name[:100],
            "value": _decimal_text(primary["value"]),
            "unit": primary["unit"],
            "value_kind": primary["kind"],
            "amounts": amounts,
            "year": str(document.period),
            "scope": "单项目",
            "reporting_entity": document.company,
            "accounting_scope": "合并范围未逐项说明",
            "industry_role": "green_project",
            "quote": quote,
            "page_verified": _compact(quote.split(" | ")[0]) in _compact(page_text),
            "evidence_hash": hashlib.sha256(_compact(quote).encode()).hexdigest()[:16],
        })
    return result


def _page_unit(page_text: str) -> tuple[Decimal, str]:
    """只读取页面明示的金额单位；未写明时按元，绝不从数值大小反推。"""
    compact = _compact(page_text)
    if "单位：万元" in compact or "单位:万元" in compact:
        return Decimal(10000), "万元"
    if "单位：千元" in compact or "单位:千元" in compact:
        return Decimal(1000), "千元"
    if "单位：亿元" in compact or "单位:亿元" in compact:
        return Decimal(100000000), "亿元"
    return Decimal(1), "元"


def _statement_nodes(rows, header, document, page_no, page_text: str, profile: dict) -> list[dict]:
    result = []
    # 母公司报表与合并报表是不同报告范围，不在同一关系里混用。
    if re.search(r"母公司(资产负债表|利润表|现金流量表)", page_text):
        return result
    unit_factor, unit_label = _page_unit(page_text)
    header_compact = [_compact(cell) for cell in header]
    # 优先年度列，其次期末余额；附注项目行尤其不能用“本期摊销”冒充期末余额。
    value_index = 1
    for preferred in ("2025年度", "本期金额", "期末余额", "本期增加金额"):
        for index, cell in enumerate(header_compact):
            if index and preferred in cell:
                value_index = index
                break
        else:
            continue
        break
    for row in rows:
        if not row:
            continue
        label = _compact(row[0])
        if not label:
            continue
        matched_line = None
        for key, patterns, role, line in FINANCIAL_LINES:
            if any(pattern in label for pattern in patterns):
                matched_line = (key, role, line)
                break
        # 附注中的环保/绿色项目行：即使不是标准报表科目，也保留可定位金额。
        if matched_line is None and any(term in label for term in profile["project_terms"]):
            matched_line = ("ENV_PROJECT", "environmental_expense", "附注—环保/绿色项目")
        if matched_line is None:
            continue
        key, role, line = matched_line
        numbers = [_decimal(cell) for cell in row[value_index:] if _decimal(cell) is not None]
        if not numbers:
            continue
        value = numbers[0] * unit_factor
        # 单行超过十万亿元视为表格串列/拼接错误，宁可漏记也不写入假数。
        if value > Decimal("1e12"):
            continue
        floors = {"capex_cash": Decimal("1e8"), "construction": Decimal("1e6"),
                  "operating_cost": Decimal("1e9"), "revenue": Decimal("1e9"),
                  "rnd_expense": Decimal("1e7"), "fixed_assets": Decimal("1e8")}
        if role in floors and value < floors[role]:
            continue
        quote = " | ".join(cell for cell in row if cell)[:1000]
        result.append({
            "node_id": "FIN-" + hashlib.sha256(
                f"{document.document_id}|{page_no}|{key}|{label}|{value}".encode()).hexdigest()[:10].upper(),
            "document_id": document.document_id,
            "company": document.company,
            "company_id": document.company_id,
            "report_type": "AR",
            "pdf_page": page_no,
            "label": label[:120],
            "financial_statement_line": line,
            "value": _decimal_text(value),
            "unit": unit_label,
            "value_kind": "本期/期末金额",
            "amounts": [{"kind": "本期/期末金额", "value": value, "unit": unit_label,
                         "dimension": "money", "normalized": value, "raw": _decimal_text(value)}],
            "year": str(document.period),
            "scope": "合并范围" if "合并" in page_text[:200] else "未明示",
            "reporting_entity": document.company,
            "accounting_scope": "合并财务报表" if "合并" in page_text[:200] else "未明示",
            "industry_role": role,
            "quote": quote,
            "page_verified": _compact(label) in _compact(page_text),
            "evidence_hash": hashlib.sha256(_compact(quote).encode()).hexdigest()[:16],
        })
    return result


def _regex_nodes(page_text: str, document, page_no: int) -> list[dict]:
    """表格抽取失败时，只对明确标签做保守兜底，不猜测行间关系。"""
    result = []
    if re.search(r"母公司(资产负债表|利润表|现金流量表)", page_text):
        return result
    unit_factor, unit_label = _page_unit(page_text)
    flat = re.sub(r"\s*\n\s*", "", page_text)
    for key, patterns, role, line in FINANCIAL_LINES:
        for pattern in patterns:
            match = re.search(re.escape(pattern) + r"[^\d]{0,12}(\d[\d,]*\.\d{2})", flat)
            if not match:
                continue
            value = _decimal(match.group(1))
            if value is None:
                continue
            value *= unit_factor
            if value > Decimal("1e12"):
                continue
            floors = {"capex_cash": Decimal("1e8"), "construction": Decimal("1e6"),
                      "operating_cost": Decimal("1e9"), "revenue": Decimal("1e9"),
                      "rnd_expense": Decimal("1e7"), "fixed_assets": Decimal("1e8")}
            if role in floors and value < floors[role]:
                continue
            quote = flat[max(0, match.start() - 20):match.end() + 20][:300]
            result.append({
                "node_id": "FIN-" + hashlib.sha256(
                    f"{document.document_id}|{page_no}|{key}|{value}".encode()).hexdigest()[:10].upper(),
                "document_id": document.document_id,
                "company": document.company,
                "company_id": document.company_id,
                "report_type": "AR",
                "pdf_page": page_no,
                "label": pattern,
                "financial_statement_line": line,
                "value": _decimal_text(value),
                "unit": unit_label,
                "value_kind": "本期/期末金额",
                "amounts": [{"kind": "本期/期末金额", "value": value, "unit": unit_label,
                             "dimension": "money", "normalized": value, "raw": _decimal_text(value)}],
                "year": str(document.period),
                "scope": "未明示",
                "reporting_entity": document.company,
                "accounting_scope": "未明示",
                "industry_role": role,
                "quote": quote,
                "page_verified": _compact(quote) in _compact(flat),
                "evidence_hash": hashlib.sha256(_compact(quote).encode()).hexdigest()[:16],
            })
            break
    return result


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _groups(text: str) -> set[str]:
    return {name for name, aliases in TERM_GROUPS.items() if any(alias in text for alias in aliases)}


def _money_amounts(claim: dict) -> list[dict]:
    return [item for item in claim.get("amounts", []) if item.get("dimension") == "money"]


def _closest_gap(claim: dict, node: dict) -> tuple[float | None, dict | None]:
    claim_amounts = _money_amounts(claim)
    if not claim_amounts:
        return None, None
    best = None
    for amount in claim_amounts:
        for node_amount in node.get("amounts", []):
            if node_amount.get("dimension") != "money":
                continue
            left, right = Decimal(amount["normalized"]), Decimal(node_amount["normalized"])
            if right == 0:
                continue
            gap = abs(left - right) / max(abs(right), Decimal(1))
            if best is None or gap < best[0]:
                best = (float(gap), {"claim": amount, "node": node_amount})
    return best if best else (None, None)


def _definition_compatible(claim: dict, node: dict, explicit: bool) -> bool | None:
    if explicit:
        return True
    claim_text = claim["text"]
    node_label = node["label"]
    if len(_compact(node_label)) >= 4 and _compact(node_label) in _compact(claim_text):
        return True
    if PROJECT_TOTAL_RE.search(claim_text) and (
            node.get("value_kind") == "预算数"
            or any(amount.get("kind") == "预算数" for amount in node.get("amounts", []))):
        return False
    if PROJECT_TOTAL_RE.search(claim_text) and node.get("industry_role") in {
            "capex_cash", "construction", "operating_cost", "revenue", "fixed_assets"}:
        return False
    if claim.get("claim_kind") == "performance" and node.get("industry_role") == "operating_cost":
        return False
    return None


def _boundary_compatible(claim: dict, node: dict) -> bool | None:
    claim_scope, node_scope = claim.get("accounting_scope", ""), node.get("scope", "")
    if not claim_scope or not node_scope:
        return None
    if "多基地" in claim_scope and "单项目" in node_scope:
        return False
    if "公司" in claim_scope and "单项目" in node_scope:
        return False
    if "多基地" in claim_scope and "合并" in node_scope:
        return False
    if "公司" in claim_scope and "合并" in node_scope:
        return True
    if "单项目" in claim_scope and "单项目" in node_scope:
        return True
    return None


def _period_compatible(claim: dict, node: dict) -> bool | None:
    if node.get("value_kind") == "预算数":
        return False
    if not claim.get("year") or not node.get("year"):
        return None
    return str(claim["year"]) == str(node["year"])


def _explicit_allocation(claim: dict, node: dict) -> bool:
    """只有原句明确出现项目名/“其中/用于”时，才承认资金归属。"""
    claim_text = _compact(claim["text"])
    label = _compact(node["label"])
    if len(label) >= 5 and label in claim_text:
        return True
    return bool(re.search(r"其中|用于|投向|专项用于", claim["text"]) and len(label) >= 4 and label[:4] in claim_text)


def link_claims(claims: list[dict], nodes: list[dict], documents: list, profile: dict) -> tuple[list[dict], list[dict]]:
    """生成受控关系；数值接近只产生候选或反例，不直接判一致。"""
    edges, unlinked = [], []
    document_map = {document.document_id: document for document in documents}
    for claim in claims:
        matched = []
        claim_groups = _groups(claim["text"])
        for node in nodes:
            node_groups = _groups(node["label"] + " " + node.get("financial_statement_line", ""))
            shared = claim_groups & node_groups
            gap, pair = _closest_gap(claim, node)
            aggregate_finance = bool(PROJECT_TOTAL_RE.search(claim["text"]) and node.get("industry_role") in {
                "capex_cash", "construction"})
            if not shared and not aggregate_finance and (gap is None or gap > 0.05):
                continue
            explicit = _explicit_allocation(claim, node)
            same_entity = claim.get("company_id") == node.get("company_id")
            same_period = _period_compatible(claim, node)
            definition = _definition_compatible(claim, node, explicit)
            boundary = _boundary_compatible(claim, node)
            if gap is not None and gap <= 0.05:
                if definition is False or boundary is False or same_period is False or not same_entity:
                    relation, status = "CONTRADICTED", "challenged"
                    why = ("金额接近（差{:.2%}），但主体/期间/定义/范围至少一项冲突，"
                           "不能作为一致证据；保留为需要解释的反例。").format(gap)
                else:
                    relation, status = "DIRECT_RECONCILIATION", "pending_evidence"
                    why = ("金额接近（差{:.2%}），且主体、期间、定义、范围未发现冲突；"
                           "仍须原文明确同一项目/同一口径后才可复算。").format(gap)
            elif explicit:
                relation, status = "DISCLOSED_ALLOCATION", "limited_support"
                why = "原句明确出现项目名或用途，可将该财务项目视为披露的资金归属；仍须核对金额与期间。"
            elif aggregate_finance and not shared:
                relation, status = "HYPOTHESIZED_MECHANISM", "pending_evidence"
                why = ("主张披露了项目/行动总投入，财务项目是资本开支或在建工程总额；"
                       "总额之间可能存在包含关系，但原文未给出逐项对应，只能作待验证的传导假设。")
            elif claim.get("claim_kind") == "target":
                relation, status = "TEMPORAL_ASSOCIATION", "pending_evidence"
                why = "主张属于目标/计划，财务项目是已发生金额；只能建立跨期关联，不能当作目标已完成。"
            elif node.get("industry_role") == "operating_cost":
                relation, status = "HYPOTHESIZED_MECHANISM", "pending_evidence"
                why = "绩效主张与营业成本存在可能的经营传导，但报告未给出可归属金额；只能作机制假设。"
            else:
                relation, status = "SEMANTIC_ASSOCIATION", "limited_support"
                why = "主题词/项目名相近，原报告未明确该项目就是该主张的财务对应项；只作语义关联。"
            # 本体许可检查：命中禁止等价时强制降级，并把双因素解释卡挂到边上。
            # 消融实验可通过环境变量关闭本体，但边必须显式标注 ablated，不冒充已检查。
            ontology_missing = []
            if os.getenv("CONNECTIVITY_ABLATION_NO_ONTOLOGY") == "1":
                ontology = {"verdict": "ablated_off", "supporting_factors": [],
                            "exclusion_factors": [], "suggested_relation_kind": relation,
                            "explanation": "消融运行：本体许可检查已关闭；关系强度未经本体门禁。"}
            else:
                ontology = evaluate_mapping(
                    claim, node, relation_kind=relation, same_entity=same_entity,
                    same_period=same_period, definition_compatible=definition,
                    boundary_compatible=boundary)
                if ontology["verdict"] == "forbidden" and ontology["suggested_relation_kind"] != relation:
                    relation = ontology["suggested_relation_kind"]
                    status = "pending_evidence"
                    why = why + "本体禁止等价命中：" + ontology["explanation"]
                    ontology_missing.append(f"本体规则：{ontology['explanation']}")
            missing = [*ontology_missing]
            if definition is not True:
                missing.append(f"定义：主张为“{claim.get('metric_definition')}”，财务项目为“{node.get('value_kind')}”，须原文证明同一计量口径")
            if boundary is not True:
                missing.append(f"范围：主张口径为“{claim.get('accounting_scope')}”，财务项目口径为“{node.get('scope')}”")
            if same_period is not True:
                missing.append(f"期间：主张年度 {claim.get('year')}，财务项目为 {node.get('value_kind')} / {node.get('year')}")
            if not same_entity:
                missing.append("主体：主张与财务项目未证明属于同一报告主体")
            if relation != "DIRECT_RECONCILIATION":
                missing.append("金额归属：年报未将该可持续投入逐项对应到这一财务项目")
            confidence = "program_quote_verified" if claim.get("page_verified") and node.get("page_verified") else "quote_unverified"
            confidence += "+" + ("numeric_candidate" if gap is not None and gap <= 0.05 else "semantic_overlap")
            edge = {
                "edge_id": "EDGE-" + hashlib.sha256(f"{claim['claim_id']}|{node['node_id']}|{relation}".encode()).hexdigest()[:10].upper(),
                "source_node_id": claim["claim_id"],
                "target_node_id": node["node_id"],
                "claim_id": claim["claim_id"],
                "financial_node_id": node["node_id"],
                "relation_type": relation,
                "direction": "esg_to_financial",
                "same_entity": bool(same_entity),
                "same_period": same_period,
                "definition_compatible": definition,
                "boundary_compatible": boundary,
                "financial_statement_line": node.get("financial_statement_line", ""),
                "evidence_ids": [claim["claim_id"], node["node_id"]],
                "missing_conditions": missing,
                "derived_formula": (f"差额率 = |{pair['claim']['raw']}{pair['claim']['unit']} - "
                                    f"{pair['node']['raw']}{pair['node']['unit']}| ÷ {pair['node']['raw']}{pair['node']['unit']}"
                                    if pair else ""),
                "numeric_gap": gap,
                "confidence_label": confidence,
                "counterevidence_ids": [],
                "status": status,
                "why": why,
                "claim_kind": claim.get("claim_kind", ""),
                "claim_kind_canonical": claim.get("claim_kind_canonical", ""),
                "ontology_check": {"verdict": ontology["verdict"],
                                   "supporting_factors": ontology["supporting_factors"],
                                   "exclusion_factors": ontology["exclusion_factors"]},
                "claim_document_id": claim["document_id"],
                "claim_page": claim["pdf_page"],
                "financial_document_id": node["document_id"],
                "financial_page": node["pdf_page"],
                "financial_label": node["label"], "claim_text": claim["text"],
                "company": claim["company"], "period": claim.get("reported_period", claim.get("year")),
            }
            edges.append(edge)
            matched.append(edge)
        if not matched:
            unlinked.append(claim)
    return edges, unlinked


def _gap_edges(unlinked: list[dict], limit: int = 6) -> list[dict]:
    edges = []
    for claim in unlinked[:limit]:
        edges.append({
            "edge_id": "EDGE-GAP-" + hashlib.sha256(claim["claim_id"].encode()).hexdigest()[:10].upper(),
            "source_node_id": claim["claim_id"],
            "target_node_id": "GAP:" + claim["claim_id"],
            "claim_id": claim["claim_id"],
            "financial_node_id": "",
            "relation_type": "INSUFFICIENT",
            "direction": "esg_to_financial",
            "same_entity": True,
            "same_period": None,
            "definition_compatible": None,
            "boundary_compatible": None,
            "financial_statement_line": "",
            "evidence_ids": [claim["claim_id"]],
            "missing_conditions": ["年报未找到可归属的财务项目；不因此推定企业未投入或披露失实"],
            "derived_formula": "",
            "numeric_gap": None,
            "confidence_label": "no_financial_node",
            "counterevidence_ids": [],
            "status": "insufficient",
            "why": "本报告对内没有出现与该主张同主题、可定位的财务项目；保留为待补证，不强行映射。",
            "claim_kind": claim.get("claim_kind", ""),
            "claim_document_id": claim["document_id"],
            "claim_page": claim["pdf_page"],
            "financial_document_id": "",
            "financial_page": None,
        })
    return edges


def industry_for(company: str, industry_context: dict | None = None) -> str:
    text = f"{company} {industry_context or ''}"
    if re.search(r"钢|钢铁|冶金|宝钢|宝山钢铁", text):
        return "steel"
    if re.search(r"酒|食品|饮料|五粮液|茅台|乳", text):
        return "food_beverage"
    return "general"


def _load_pages(root: Path, document) -> list[dict]:
    """按登记哈希打开本地原件；此处不做下载，缺失即抛错而不是换版本。"""
    from .connectivity_extraction import source_path
    from .source_viewer import PDF_ACCESS_LOCK
    import pymupdf
    path = source_path(root, document)
    # 只对有财务/项目线索的页做表格识别；逐页 find_tables 在 300 页报告上过慢。
    table_terms = ("在建工程", "购建固定资产", "营业成本", "研发费用", "固定资产", "环保", "环境治理",
                   "项目名称", "预算数", "本期增加", "工程进度")
    pages = []
    # 原生PDF解析与原页阅读共用锁，防止并发任务同时进入不支持线程并行的解析器。
    with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
        for index, page in enumerate(pdf):
            text = page.get_text("text")
            blocks = [block[4] for block in page.get_text("blocks") if len(block) > 6 and block[6] == 0]
            tables = []
            if any(term in text for term in table_terms):
                try:
                    tables = [table.extract() for table in page.find_tables().tables]
                except Exception:
                    tables = []
            pages.append({"page": index + 1, "text": text, "blocks": blocks, "tables": tables})
    return pages


def _limit_edges(edges: list[dict], per_claim: int = 3, total: int = 30) -> list[dict]:
    """页面只展示最有信息量的边；反例与直接关联优先，其次语义/机制，最后缺口。"""
    priority = {"DIRECT_RECONCILIATION": 0, "CONTRADICTED": 1, "DISCLOSED_ALLOCATION": 2,
                "SEMANTIC_ASSOCIATION": 3, "TEMPORAL_ASSOCIATION": 4,
                "HYPOTHESIZED_MECHANISM": 5, "INSUFFICIENT": 6}
    grouped = {}
    for edge in edges:
        grouped.setdefault(edge["claim_id"], []).append(edge)
    chosen, gaps = [], []
    for claim_id, items in grouped.items():
        items.sort(key=lambda edge: (priority.get(edge["relation_type"], 9),
                                     edge["numeric_gap"] if edge["numeric_gap"] is not None else 99,
                                     edge["financial_page"] or 999))
        limit = 1 if items[0].get("claim_kind") == "target" else per_claim
        for edge in items[:limit]:
            (gaps if edge["relation_type"] == "INSUFFICIENT" else chosen).append(edge)
    chosen.sort(key=lambda edge: (priority.get(edge["relation_type"], 9), edge["claim_page"], edge["financial_page"] or 999))
    gaps.sort(key=lambda edge: edge["claim_page"])
    caps = {"CONTRADICTED": 3, "SEMANTIC_ASSOCIATION": 4, "TEMPORAL_ASSOCIATION": 2,
            "HYPOTHESIZED_MECHANISM": 3, "DIRECT_RECONCILIATION": 3, "DISCLOSED_ALLOCATION": 3}
    capped, counts = [], {}
    for edge in chosen:
        kind = edge["relation_type"]
        if counts.get(kind, 0) >= caps.get(kind, 99):
            continue
        counts[kind] = counts.get(kind, 0) + 1
        capped.append(edge)
    # 缺口边至少保留 4 条，避免被“有财务节点”的边挤掉“没有对应项”的诚实结果。
    return capped[:max(0, total - 4)] + gaps[:4]


def build(root: Path, run=None, documents=None, *, pages: dict | None = None,
          industry: str | None = None, limit_claims: int = 14, limit_nodes: int = 18) -> dict:
    """构建一次运行的财务穿透层；不调用模型，不改变任何正式结论。"""
    docs = list(documents or getattr(run, "documents", []) or [])
    if len(docs) < 2:
        return {"version": VERSION, "claims": [], "nodes": [], "edges": [], "stats": {},
                "industry": industry or "general", "notice": "报告对不足，未构建财务穿透层"}
    esg_docs = [doc for doc in docs if doc.report_type == "ESG"]
    ar_docs = [doc for doc in docs if doc.report_type == "AR"]
    if not esg_docs or not ar_docs:
        return {"version": VERSION, "claims": [], "nodes": [], "edges": [], "stats": {},
                "industry": industry or "general", "notice": "缺少ESG或年报，未构建财务穿透层"}
    industry = industry or industry_for(esg_docs[0].company, getattr(run, "industry_context", None))
    from copy import deepcopy
    profile = deepcopy(INDUSTRY_PROFILES.get(industry, INDUSTRY_PROFILES["general"]))
    pages = pages or {}
    if not pages:
        for doc in docs:
            pages[doc.document_id] = _load_pages(root, doc)
    claims = extract_claims(pages.get(esg_docs[0].document_id, []), esg_docs[0], profile, limit=limit_claims)
    nodes = extract_financial_nodes(pages.get(ar_docs[0].document_id, []), ar_docs[0], profile, limit=limit_nodes)
    edges, unlinked = link_claims(claims, nodes, docs, profile)
    edges.extend(_gap_edges(unlinked))
    edges = _limit_edges(edges)
    stats = {
        "claims": len(claims),
        "financial_nodes": len(nodes),
        "edges": len(edges),
        "linked_claims": len(claims) - len(unlinked),
        "unlinked_claims": len(unlinked),
        "by_relation": {kind: sum(edge["relation_type"] == kind for edge in edges) for kind in (
            "DIRECT_RECONCILIATION", "DISCLOSED_ALLOCATION", "TEMPORAL_ASSOCIATION",
            "SEMANTIC_ASSOCIATION", "HYPOTHESIZED_MECHANISM", "CONTRADICTED", "INSUFFICIENT")},
        "by_status": {kind: sum(edge["status"] == kind for edge in edges) for kind in (
            "pending_evidence", "limited_support", "challenged", "insufficient")},
        "page_verified_claims": sum(bool(claim.get("page_verified")) for claim in claims),
        "page_verified_nodes": sum(bool(node.get("page_verified")) for node in nodes),
    }
    return {
        "version": VERSION,
        "industry": industry,
        "industry_name": profile["name"],
        "claims": claims,
        "nodes": nodes,
        "edges": edges,
        "unlinked_claims": [claim["claim_id"] for claim in unlinked],
        "stats": stats,
        "profile": {"claim_terms": list(profile["claim_terms"]), "project_terms": list(profile["project_terms"]),
                    "scenario": profile["scenario"]},
        "case_facts": _case_facts(claims, nodes, docs),
        "notice": "财务穿透层只登记原文可定位的主张大财务关系；数值接近不等于因果成立，语义关联不等于资金归属。",
    }


def _case_facts(claims: list[dict], nodes: list[dict], docs) -> list[dict]:
    """可移交人工复核的事实清单，含两份原文URL、SHA、页码与原句。"""
    by_id = {doc.document_id: doc for doc in docs}
    facts = []
    for claim in claims:
        doc = by_id.get(claim["document_id"])
        facts.append({
            "fact_id": claim["claim_id"], "kind": "claim", "company": claim["company"],
            "year": claim["year"], "document_id": claim["document_id"],
            "source_url": getattr(doc, "source_url", ""), "file_sha256": getattr(doc, "file_sha256", ""),
            "pdf_page": claim["pdf_page"], "quote": claim["quote"],
            "claim_kind": claim["claim_kind"], "observed_or_plan": claim["observed_or_plan"],
            "mapping_reason": "ESG句子级主张；未由模型生成", "manual_review": "pending",
        })
    for node in nodes:
        doc = by_id.get(node["document_id"])
        facts.append({
            "fact_id": node["node_id"], "kind": "financial_node", "company": node["company"],
            "year": node["year"], "document_id": node["document_id"],
            "source_url": getattr(doc, "source_url", ""), "file_sha256": getattr(doc, "file_sha256", ""),
            "pdf_page": node["pdf_page"], "quote": node["quote"],
            "financial_statement_line": node["financial_statement_line"],
            "value": node["value"], "unit": node["unit"], "value_kind": node["value_kind"],
            "mapping_reason": "年报表格行/附注行；未由模型生成", "manual_review": "pending",
        })
    return facts
