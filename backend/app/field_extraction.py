"""巨潮年报中的财务字段候选提取与硬校验。

字段提取只读取已经通过来源校验的 PDF，不访问任意本机文件。
程序先按财务报表关键词定位页面，再从同一行附近提取候选数字。
候选数字必须保留文档编号、报告年度、PDF 页码、单位、口径和原文窗口。
模块不声称自动提取就是专业确认；不确定时返回 needs_human 并停止完整分析。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz

from .cases import get_case, get_case_documents, update_cninfo_financial_fields


FIELD_CONFIG: dict[str, dict[str, Any]] = {
    "revenue": {
        "terms": ["营业收入"],
        "hints": ["主要会计数据", "利润表及现金流量表相关科目变动分析表", "合并利润表"],
        "basis": "reported",
    },
    "accounts_receivable": {
        "terms": ["应收账款"],
        "hints": ["资产及负债状况", "资产负债表", "按欠款方归集"],
        "basis": "gross",
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
# 数字解析只服务于候选生成，任何候选都必须带原文窗口和 PDF 页码。
NUMBER_PATTERN = re.compile(r"(?<![\d.])[-−]?(?:\(?\d[\d,]*(?:\.\d+)?\)?)(?![\d.])")
UNIT_PATTERN = re.compile(r"单位\s*[:：]\s*(元|千元|万元|百万元)")
UNIT_MULTIPLIER = {"元": 1.0, "千元": 1_000.0, "万元": 10_000.0, "百万元": 1_000_000.0}
NOTE_REFERENCE_PATTERN = re.compile(r"^[一二三四五六七八九十百千万]+[、.．]\d{1,3}$")


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


def _line_candidates(lines: list[str], start: int, *, term: str = "") -> list[tuple[float, str]]:
    """读取关键词所在行之后的有限窗口，避免把整页其他表的数字串进来。"""

    # 限定窗口长度，减少把同页其他表格的金额误绑定到关键词。
    window_lines = lines[start : min(len(lines), start + 14)]
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
            after = line[match.end() : match.end() + 2]
            if "年" in after or "%" in after or "％" in after:
                continue
            value = _number(raw)
            if value is None or abs(value) > 1e16:
                continue
            if 2000 <= abs(value) <= 2100 and len(raw.replace(",", "").replace(".", "")) == 4:
                continue
            candidates.append((value, line.strip()))
    return candidates


def _find_page_candidate(
    pages: list[str], config: dict[str, Any]
) -> dict[str, Any] | None:
    """在所有页面中选择同时命中专业词和报表标题的最高分候选。"""

    # 以关键词、表格提示、单位和页码共同评分，保留最高分供人工复核。
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for page_index, text in enumerate(pages):
        if not text.strip():
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        unit_name, multiplier = _unit(text)
        for term_rank, term in enumerate(config["terms"]):
            for line_index, line in enumerate(lines):
                if term not in line:
                    continue
                candidates = _line_candidates(lines, line_index, term=term)
                if not candidates:
                    continue
                value, raw_line = candidates[0]
                hint_hits = sum(1 for hint in config["hints"] if hint in text)
                exact_bonus = max(0, len(config["terms"]) - term_rank)
                score = hint_hits * 10 + exact_bonus * 3
                if unit_name:
                    score += 5
                if page_index < 80:
                    score += 1
                ranked.append(
                    (
                        score,
                        -page_index,
                        {
                            "page": page_index + 1,
                            "raw_value": value,
                            "value": value * multiplier,
                            "unit": unit_name,
                            "locator": f"PDF 第 {page_index + 1} 页：{term}",
                            "raw_excerpt": " | ".join(lines[max(0, line_index - 2) : min(len(lines), line_index + 8)]),
                            "term": term,
                            "score": score,
                            "page_hints": [hint for hint in config["hints"] if hint in text],
                        },
                    )
                )
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def _required_kinds(rule_ids: list[str]) -> tuple[set[str], set[str]]:
    """按现有 R1/R2 规则区分必需字段和可选增强字段。"""

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
) -> dict[str, Any]:
    """从巨潮案例的每份年度报告提取当前年度字段候选并写入案例。"""

    case = get_case(workspace_root, case_id)
    if case is None:
        raise ValueError("案例未登记。")
    documents = get_case_documents(workspace_root, case_id)
    required, optional = _required_kinds(rule_ids)
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
            candidate = _find_page_candidate(pages, FIELD_CONFIG[kind])
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
                {
                    "evidence_id": f"{case_id}_{kind.upper()}_{report_year}",
                    "field_kind": kind,
                    "year": report_year,
                    "value": candidate["value"],
                    "field_basis": FIELD_CONFIG[kind]["basis"],
                    "document_id": document["document_id"],
                    "pdf_page": candidate["page"],
                    "locator": candidate["locator"],
                    "raw_excerpt": candidate["raw_excerpt"],
                    "extraction_method": "pdf_text_heuristic_candidate",
                    "source_review_status": "auto_extracted_pending_human_page_confirmation",
                }
            )

    # 每个必需字段都应覆盖所有目标报告年度，避免只找到最新年就误判三年完整。
    found_required = {(row["field_kind"], row["year"]) for row in rows if row["field_kind"] in required}
    for year in sorted(years):
        for kind in sorted(required):
            if (kind, year) not in found_required:
                issue = f"{year}年{kind}字段未形成可回查候选。"
                if issue not in issues:
                    issues.append(issue)
    status = "passed_technical_pending_human" if not issues else "needs_human"
    if not rows:
        status = "failed"
    case = update_cninfo_financial_fields(
        workspace_root,
        case_id,
        rows,
        status=status,
        material_gaps=issues + optional_missing,
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
        "human_review_required": True,
    }
