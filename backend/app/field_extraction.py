"""巨潮年报中的财务字段候选提取与硬校验。

字段提取只读取已经通过来源校验的 PDF，不访问任意本机文件。
程序先按财务报表关键词定位页面，再从同一行附近提取候选数字。
候选数字必须保留文档编号、报告年度、PDF 页码、单位、口径和原文窗口。
模块不声称自动提取就是专业确认；公开预筛会返回明确缺口并按可比期间降级，正式采用与导出前仍需真人复核。
提取器只打开案例清单登记的相对路径，调用参数不能指定任意本机 PDF。
页面关键词只缩小候选范围，不能单凭出现字段名称就认定报表项目。
字段提示词用于提高报表页优先级，不会绕过文档年度和来源身份检查。
数字解析会移除常见千位分隔符，但不会猜测缺失小数点或负号。
括号负数保持负值含义，不能为方便比较而转换为正数。
破折号和空白不被解释为零，缺失金额必须形成资料缺口。
单位从候选页原文识别，无法识别时不能静默套用一个任意倍率。
金额统一换算到案例登记口径，同时保留原始单位供人工复验。
百分比字段使用独立单位规则，不能乘以万元或百万元倍率。
同一行附近存在多个数字时按受控距离选择，结果仍只是自动候选。
候选原文窗口限制长度，既支持回查也避免把整页内容扩散到日志。
PDF 页码从一开始记录，与阅读器展示页保持一致并受总页数校验。
报告年度来自已登记文档元数据，不能从页面零散年份自由推断。
必需字段由所选普通规则或行业专用规则决定，二者不能混合凑齐。
可选字段缺失只影响增强信息，必需字段缺失才进入对应资料缺口。
每个年度逐文档提取，不能从下一年度比较列替代本年度官方原件。
来源时点过滤在案例登记和规则阶段再次执行，提取成功不等于当期可用。
技术通过状态只表示形成候选行，人工确认状态仍保持待处理。
未形成任何候选时明确失败，部分字段存在时返回带缺口的降级状态。
提取器写回案例前保留证据编号和页面定位，不能只保存最终浮点值。
任何自动化准确率提升都不能取消原 PDF 页回查和人工更正入口。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf as fitz

from .cases import (
    annotate_financial_field_quality,
    annotate_financial_field_rows_quality,
    financial_field_candidate_quality_issues,
    get_case,
    get_case_documents,
    update_cninfo_financial_fields,
)
from .industry_rules import SPECIALIZED_FIELD_CONFIG, get_specialized_spec


FIELD_CONFIG: dict[str, dict[str, Any]] = {
    "revenue": {
        "terms": ["营业收入"],
        "hints": ["主要会计数据", "利润表及现金流量表相关科目变动分析表", "合并利润表"],
        "basis": "reported",
    },
    "accounts_receivable": {
        "terms": ["应收账款"],
        "hints": ["资产及负债状况", "资产负债表", "按欠款方归集"],
        # 自动候选优先读取合并资产负债表列示额；该金额通常已扣除减值准备，
        # 因此必须标为 net，不能把报表列示额冒充应收账款账面余额。
        "basis": "net",
    },
    "operating_cash_flow": {
        "terms": ["经营活动产生的现金流量净额", "经营活动现金流量净额"],
        "hints": ["利润表及现金流量表相关科目变动分析表", "现金流量表"],
        "basis": "reported",
    },
    "net_profit": {
        "terms": ["归属于上市公司股东的净利润", "归属于母公司股东的净利润", "净利润"],
        "hints": ["主要会计数据", "合并利润表", "利润表及现金流量表相关科目变动分析表"],
        "basis": "reported",
    },
}
FIELD_CONFIG.update(SPECIALIZED_FIELD_CONFIG)
# 数字解析只服务于候选生成，任何候选都必须带原文窗口和 PDF 页码。
NUMBER_PATTERN = re.compile(r"(?<![\d.])[-−]?(?:\(?\d[\d,]*(?:\.\d+)?\)?)(?![\d.])")
# 兼容“单位：亿元”“单位：人民币亿元”“单位：百万元”和“人民币百万元”等常见表头。
# 仍然只接受明确写出的金额单位，不根据企业规模或数值大小猜单位。
# 除“单位：元”表头外，巨潮年度报告还常把单位写在字段标题后，例如“营业收入（元）”。
# 两种写法都必须显式出现，不能根据企业规模猜测数量级。
UNIT_PATTERN = re.compile(
    r"(?:单位\s*[:：]?\s*(?:人民币)?|人民币\s*|[（(]\s*(?:人民币)?)(亿元|百万元|万元|千元|元)\s*[）)]?"
)
UNIT_MULTIPLIER = {"元": 1.0, "千元": 1_000.0, "万元": 10_000.0, "百万元": 1_000_000.0, "亿元": 100_000_000.0}
# 附注编号可能写成“七、5”，也可能写成“（六）4”；都不能当成金额。
NOTE_REFERENCE_PATTERN = re.compile(
    r"^(?:[一二三四五六七八九十百千万]+[、.．]\d{1,3}|[（(][一二三四五六七八九十百千万]+[）)]\d{1,3})$"
)
# 列身份来自表头：附注列标签与期间列标签都要显式出现在表头文本中。
NOTE_COLUMN_LABELS = ("附注", "注释", "附注号")
PERIOD_LABEL_PATTERN = re.compile(
    r"\d{4}\s*年(?:\s*12\s*月\s*31\s*日|末|度|底)?|本期|上期|期末|期初|本年|上年"
)


def _number(raw: str) -> float | None:
    """解析会计表中的逗号、负号和括号负数。"""

    # 会计负数既可能用减号表示，也可能用括号表示，统一成数值负号。
    value = raw.replace(",", "").replace("−", "-").strip()
    negative_parentheses = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    try:
        result = float(value)
    except ValueError:
        return None
    if negative_parentheses:
        result = -abs(result)
    return result


def _unit(text: str) -> tuple[str | None, float]:
    """从页面标题或报表表头识别金额单位；不识别时不自动猜单位。"""

    # 单位不明确时不放大数值，调用方会把该候选标记为人工处理。
    match = UNIT_PATTERN.search(text[:2500])
    if not match:
        return None, 1.0
    name = match.group(1)
    return name, UNIT_MULTIPLIER[name]


def _scan_number_cells(
    lines: list[str], start: int, *, term: str = "", allow_percent: bool = False
) -> list[tuple[float, str]]:
    """按文档顺序读取关键词之后的有限窗口，产出可供列位置判定的单元格。

    本函数不排序、不猜本期列；列身份由 _resolve_column 依据表头决定。
    """

    # 限定窗口长度，减少把同页其他表格的金额误绑定到关键词。
    window_lines = lines[start : min(len(lines), start + 8)]
    candidates: list[tuple[float, str]] = []
    for offset, original_line in enumerate(window_lines):
        line = original_line
        # 关键词前的同行金额属于上一行，关键词后的附注编号也不是字段金额。
        if offset == 0 and term and term in line:
            line = line[line.find(term) + len(term) :]
        compact_line = re.sub(r"\s+", "", line)
        if NOTE_REFERENCE_PATTERN.fullmatch(compact_line):
            continue
        for match in NUMBER_PATTERN.finditer(line):
            raw = match.group(0)
            before = line[max(0, match.start() - 4) : match.start()]
            after = line[match.end() : match.end() + 2]
            if (
                "附注" in before
                or any(marker in after for marker in ("年", "个月", "天", "页"))
                or (not allow_percent and ("%" in after or "％" in after))
            ):
                continue
            value = _number(raw)
            if value is None or abs(value) > 1e16:
                continue
            if 2000 <= abs(value) <= 2100 and len(raw.replace(",", "").replace(".", "")) == 4:
                continue
            candidates.append((value, line.strip()))
    return candidates


def _reorder_for_visibility(scanned: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """把疑似附注号的小整数排到后面，只用于候选展示顺序。

    该排序不再决定自动采用值；采用值必须由表头列身份确立，否则标为歧义。
    """

    if not scanned or abs(scanned[0][0]) > 100:
        return scanned
    material = [item for item in scanned if abs(item[0]) > 100]
    if not material:
        return scanned
    return material + [item for item in scanned if abs(item[0]) <= 100]


def _label_year(label: str) -> int | None:
    """只在表头期间标签显式写出四位数年度时才返回年度。"""

    match = re.match(r"\s*(\d{4})\s*年", str(label))
    return int(match.group(1)) if match else None


def _header_layout(lines: list[str], start: int) -> dict[str, Any]:
    """回看有限表头，得到期间列数量、顺序与附注列是否位于期间列之前。"""

    # 只回看四行，避免把上一张表的列头接到本字段行上。
    header_text = " ".join(lines[max(0, start - 4) : start + 1])
    labels = [match.group(0) for match in PERIOD_LABEL_PATTERN.finditer(header_text)]
    note_position = min(
        (header_text.find(label) for label in NOTE_COLUMN_LABELS if label in header_text),
        default=-1,
    )
    first_period = PERIOD_LABEL_PATTERN.search(header_text)
    return {
        "period_count": len(labels),
        "period_labels": labels,
        "note_first": bool(labels) and note_position >= 0 and note_position < first_period.start(),
    }


def _resolve_column(
    scanned: list[tuple[float, str]], layout: dict[str, Any], *, report_year: int | None = None
) -> tuple[int | None, str]:
    """返回本期单元格下标；表头不能唯一确立时给出可诊断的歧义原因。"""

    if not scanned:
        return None, "unresolved_no_cell"
    if not layout["period_count"]:
        return None, "unresolved_no_period_header"
    # 附注列在期间列之前且多出一个单元格时按位置丢掉附注单元格，不按数值丢掉。
    offset = 1 if layout["note_first"] and len(scanned) > layout["period_count"] else 0
    if len(scanned) - offset < layout["period_count"]:
        return None, "unresolved_cell_count_below_period_columns"
    if report_year:
        # 比较列可能倒序排列，因此按目标报告年度对齐，而不是固定取第一列。
        matched = [
            index
            for index, label in enumerate(layout["period_labels"])
            if _label_year(label) == int(report_year)
        ]
        if not matched:
            return None, "unresolved_report_year_not_in_header"
        if len(matched) > 1:
            return None, "unresolved_ambiguous_year_columns"
        index = offset + matched[0]
        if index >= len(scanned):
            return None, "unresolved_cell_count_below_period_columns"
        return index, "resolved_by_header_position"
    return offset, "resolved_by_header_position"


def _find_page_candidate(
    pages: list[str], config: dict[str, Any], *, report_year: int | None = None
) -> dict[str, Any] | None:
    """在所有页面中选择同时命中专业词和报表标题的最高分候选。"""

    # 以关键词、表格提示、单位和页码共同评分，保留最高分供人工复核。
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for page_index, text in enumerate(pages):
        if not text.strip():
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        is_ratio = config.get("value_type") == "ratio"
        unit_name, multiplier = ("%", 1.0) if is_ratio and re.search(r"%|％|百分比", text) else _unit(text)
        for term_rank, term in enumerate(config["terms"]):
            for line_index, line in enumerate(lines):
                if term not in line:
                    continue
                scanned = _scan_number_cells(lines, line_index, term=term, allow_percent=is_ratio)
                if not scanned:
                    continue
                layout = _header_layout(lines, line_index)
                cell_index, column_identity = _resolve_column(
                    scanned, layout, report_year=None if is_ratio else report_year
                )
                if cell_index is None:
                    # 表头未确立列身份时沿用可见性排序，只保留候选可读性；
                    # 该候选会在质量闸门处成为资料缺口，不再冒充已确认的本期值。
                    value, raw_line = scanned[0] if is_ratio else _reorder_for_visibility(scanned)[0]
                else:
                    value, raw_line = scanned[cell_index]
                if is_ratio and unit_name is None:
                    # 比例字段必须在同页或同一表头明确出现百分比单位，不能把普通金额猜成比例。
                    continue
                hint_hits = sum(1 for hint in config["hints"] if hint in text)
                exact_bonus = max(0, len(config["terms"]) - term_rank)
                score = hint_hits * 10 + exact_bonus * 3
                if unit_name:
                    score += 5
                if page_index < 80:
                    score += 1
                if column_identity.startswith("resolved"):
                    # 已确立本期列的页面必须优先于仅靠排序可见的歧义页面。
                    score += 8
                ranked.append(
                    (
                        score,
                        -page_index,
                        {
                            "page": page_index + 1,
                            "raw_value": value,
                            "value": value if is_ratio else value * multiplier,
                            "unit": unit_name,
                            "source_unit": unit_name,
                            "locator": f"PDF 第 {page_index + 1} 页：{term}",
                            "raw_excerpt": " | ".join(lines[max(0, line_index - 2) : min(len(lines), line_index + 8)]),
                            "term": term,
                            "score": score,
                            "column_identity": column_identity,
                            "period_labels": layout["period_labels"],
                            "cell_values": [item[0] for item in scanned],
                            "adopted_cell_index": cell_index,
                            "adopted_line": raw_line,
                            "page_hints": [hint for hint in config["hints"] if hint in text],
                        },
                    )
                )
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def _required_kinds(rule_ids: list[str], industry_family: str | None = None) -> tuple[set[str], set[str]]:
    """按现有 R1/R2 规则区分必需字段和可选增强字段。"""

    specialized = get_specialized_spec(industry_family)
    if specialized:
        return set(specialized.get("required_fields") or []), set(specialized.get("optional_fields") or [])
    required: set[str] = set()
    optional: set[str] = set()
    if "R1" in rule_ids:
        required.update({"revenue", "accounts_receivable"})
    if "R2" in rule_ids:
        required.update({"revenue", "operating_cash_flow"})
        optional.add("net_profit")
    return required, optional


def extract_cninfo_fields(
    workspace_root: Path,
    case_id: str,
    *,
    rule_ids: list[str],
    requested_years: list[int] | None = None,
    industry_family: str | None = None,
) -> dict[str, Any]:
    """从巨潮案例的每份年度报告提取当前年度字段候选并写入案例。"""

    case = get_case(workspace_root, case_id)
    if case is None:
        raise ValueError("案例未登记。")
    documents = get_case_documents(workspace_root, case_id)
    required, optional = _required_kinds(rule_ids, industry_family)
    years = set(requested_years or case.get("available_report_years", []))
    # 每个年度、每个字段最多生成一个候选，避免重复行影响连续年度判断。
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    optional_missing: list[str] = []
    for document in documents:
        report_year = int(document["report_year"])
        if years and report_year not in years:
            continue
        path = (workspace_root / document["storage_relpath"]).resolve()
        try:
            path.relative_to(workspace_root.resolve())
        except ValueError:
            issues.append(f"{document['document_id']}来源文件超出工作区边界。")
            continue
        if not path.is_file():
            issues.append(f"{document['document_id']}来源文件不存在。")
            continue
        try:
            pdf = fitz.open(path)
        except Exception as error:
            issues.append(f"{document['document_id']} PDF无法解析：{type(error).__name__}。")
            continue
        try:
            pages = [page.get_text("text") for page in pdf]
        finally:
            pdf.close()
        if sum(len(text.strip()) for text in pages) < 500:
            # 文本层过短通常意味着扫描件，需要人工 OCR 或直接回看原页。
            issues.append(f"{document['document_id']}文本过少，可能需要 OCR。")
            continue
        for kind in sorted(required | optional):
            config = FIELD_CONFIG.get(kind)
            if config is None:
                # 行业规则词表和提取器版本可能暂时不同步；可选字段应形成
                # 明确资料缺口，不能把配置缺口升级为未处理的 KeyError。
                message = f"字段提取器尚未登记{kind}字段词表。"
                if kind in required:
                    issues.append(message)
                else:
                    optional_missing.append(message)
                continue
            candidate = _find_page_candidate(pages, config, report_year=report_year)
            if candidate is None:
                if kind in required:
                    issues.append(f"{report_year}年缺少{kind}字段候选。")
                else:
                    optional_missing.append(f"{report_year}年缺少{kind}增强字段。")
                continue
            if candidate["unit"] is None:
                message = f"{report_year}年{kind}字段未识别金额单位。"
                if kind in required:
                    issues.append(message)
                else:
                    optional_missing.append(message)
                continue
            rows.append(
                annotate_financial_field_quality(
                    {
                    "evidence_id": f"{case_id}_{kind.upper()}_{report_year}",
                    "field_kind": kind,
                    "year": report_year,
                    "value": candidate["value"],
                    # value 已按页面单位归一化；source_unit 保留原始表头，
                    # 比例字段则以百分比点保存，不混入金额倍率。
                    "unit": "元" if candidate["unit"] in {"元", "千元", "万元", "百万元", "亿元"} else candidate["unit"],
                    "source_unit": candidate.get("source_unit") or candidate["unit"],
                    "field_basis": FIELD_CONFIG[kind]["basis"],
                    "document_id": document["document_id"],
                    "pdf_page": candidate["page"],
                    "locator": candidate["locator"],
                    "raw_excerpt": candidate["raw_excerpt"],
                    # 列身份与候选单元格集合一起保存，人工复核能看到放弃了哪些列。
                    "column_identity": candidate["column_identity"],
                    "period_labels": candidate["period_labels"],
                    "cell_values": candidate["cell_values"],
                    "adopted_cell_index": candidate["adopted_cell_index"],
                    "extraction_method": "pdf_text_heuristic_candidate",
                    "source_review_status": "auto_extracted_pending_human_page_confirmation",
                    }
                )
            )

    # 同字段跨年数量级异常要在写入任务结果前标出，不能等到规则运行才暴露。
    rows = annotate_financial_field_rows_quality(rows)
    # 每个必需字段都应覆盖所有目标报告年度，避免只找到最新年就误判三年完整。
    for row in rows:
        for quality_issue in financial_field_candidate_quality_issues(row):
            message = f"{row['year']}年{row['field_kind']}：{quality_issue}"
            target = issues if row["field_kind"] in required else optional_missing
            if message not in target:
                target.append(message)
    found_required = {
        (row["field_kind"], row["year"])
        for row in rows
        if row["field_kind"] in required and not financial_field_candidate_quality_issues(row)
    }
    for year in sorted(years):
        for kind in sorted(required):
            if (kind, year) not in found_required:
                issue = f"{year}年{kind}字段未形成可回查候选。"
                if issue not in issues:
                    issues.append(issue)
    # 公开预筛允许带着明确缺口继续运行；人工确认保留为正式采用/导出前的推荐动作。
    status = "passed_technical_pending_human" if not issues else "passed_technical_with_gaps"
    if not rows and industry_family:
        # 专用规则允许先形成“来源已校验但字段缺口”的结果，不能因普通 R1
        # 字段不存在就把能源、银行或保险流程报成巨潮下载失败。
        status = "passed_technical_with_gaps"
    elif not rows:
        status = "failed"
    case = update_cninfo_financial_fields(
        workspace_root,
        case_id,
        rows,
        status=status,
        material_gaps=issues + optional_missing,
        specialized_required_fields=sorted(required) if industry_family else None,
        industry_rule=industry_family,
    )
    return {
        "status": status,
        "case_id": case_id,
        "rows": rows,
        "row_count": len(rows),
        "required_kinds": sorted(required),
        "optional_kinds": sorted(optional),
        "issues": issues,
        "optional_missing": optional_missing,
        "available_years": case.get("available_years", []),
        "human_review_required": False,
        "human_review_recommended": bool(rows),
        "formal_adoption_requires_human_review": True,
    }
