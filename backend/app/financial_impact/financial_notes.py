"""任务3：财务报表附注结构化解析。

只做结构化登记，不做判断：
- 每个数值都必须带 document_id / file_sha256 / pdf_page / bbox / row_header /
  column_header / raw_value / value_semantics。
- 预算数、期初余额、本期增加、转固金额、期末余额、当期费用严格分列，
  禁止把期末余额当投入、把预算当支出。
- 找不到表头或单位时保留 raw_value 并把语义记为 none，不猜。
"""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from pathlib import Path

import pymupdf

from .models import AmountNature, FinancialItem
from .textutil import compact, decimal

NOTES_VERSION = "financial_notes_v1.0"
NOTE_TERMS = ("在建工程", "固定资产", "无形资产", "开发支出", "研发费用", "管理费用",
              "预计负债", "长期待摊费用", "其他收益", "营业外支出", "政府补助",
              "现金流量表", "资产负债表", "利润表", "环保", "治理")
STATEMENT_TERMS = ("资产负债表", "利润表", "现金流量表")
MAX_PAGES = 48
MAX_ITEMS = 600

COLUMN_SEMANTICS: tuple[tuple[AmountNature, re.Pattern], ...] = (
    (AmountNature.BUDGET, re.compile(r"预算数|预算金额|预算投入|计划投资")),
    (AmountNature.OPENING_BALANCE, re.compile(r"期初余额|期初数|年初余额|年初数")),
    (AmountNature.PERIOD_DECREASE, re.compile(r"本期减少|本年减少|减少金额|本期转出")),
    (AmountNature.TRANSFER_OUT, re.compile(r"转入固定资产|转入无形资产|转固")),
    (AmountNature.PERIOD_INCREASE, re.compile(r"本期增加|本年增加|增加金额|本期投入")),
    (AmountNature.CLOSING_BALANCE, re.compile(r"期末余额|期末数|年末余额|年末数")),
    (AmountNature.EXPENSE, re.compile(r"本期费用|费用化|计入当期|本期发生额")),
    (AmountNature.ACTUAL_PAYMENT, re.compile(r"现金支付|支付现金|实际支付")),
)

UNIT_FACTORS = {"元": Decimal(1), "千元": Decimal(1000), "万元": Decimal(10000), "亿元": Decimal(100000000)}


def _item_id(document_id: str, page: int, title: str, row: str, column: str, raw: str) -> str:
    seed = f"{document_id}|{page}|{title}|{row}|{column}|{raw}"
    return "FI-" + hashlib.sha256(seed.encode()).hexdigest()[:10].upper()


def _semantics(column_header: str) -> AmountNature:
    text = compact(column_header)
    for nature, pattern in COLUMN_SEMANTICS:
        if pattern.search(text):
            return nature
    return AmountNature.NONE


def _unit_factor(page_text: str) -> tuple[Decimal, str]:
    """只认页面明示的单位；未写明按元并标记，绝不由数值大小反推。"""
    head = compact(page_text[:600])
    for label in ("亿元", "万元", "千元", "元"):
        if f"单位:{label}" in head or f"单位：{label}" in head:
            return UNIT_FACTORS[label], label
    if "人民币元" in head:
        return Decimal(1), "元"
    return Decimal(1), "未明示"


def _scope(page_text: str) -> str:
    head = compact(page_text[:400])
    if "母公司" in head:
        return "母公司"
    if "合并" in head:
        return "合并"
    return "未明示"


def _currency(page_text: str) -> str:
    head = compact(page_text[:400])
    return "人民币" if "人民币" in head or "单位:" in head or "单位：" in head else "未明示"


def _blocks(page) -> list[dict]:
    result = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        text = "".join(span.get("text", "") for line in block.get("lines", []) for span in line.get("spans", []))
        if text.strip():
            result.append({"text": text.strip(), "bbox": [round(v, 2) for v in block.get("bbox", [])]})
    return result


TITLE_NOISE = re.compile(r"适用|不适用|单位[:：]|^注|^-+$|币种")


def _title_above(blocks: list[dict], table_bbox: list[float]) -> str:
    """表标题只取紧邻上方、短且非噪声的文本块，不跨页拼接。"""
    candidates = []
    for block in blocks:
        text = str(block.get("text") or "").strip()
        if not block.get("bbox") or not text or len(text) > 48 or TITLE_NOISE.search(text):
            continue
        gap = table_bbox[1] - block["bbox"][3]
        if -25 <= gap <= 90:
            candidates.append(block)
    if not candidates:
        return ""
    return max(candidates, key=lambda block: block["bbox"][3])["text"]


NOTE_TABLE_TERMS = ("在建工程", "固定资产", "无形资产", "开发支出", "研发费用", "管理费用", "预计负债",
                    "长期待摊费用", "长期待摊", "其他收益", "营业外支出", "政府补助", "现金流量",
                    "资产负债表", "利润表", "资产减值", "存货", "营业成本")
SEMANTIC_COLUMN = re.compile(r"预算数|预算金额|期初余额|期初数|本期增加|本期减少|转入固定资产|转固|期末余额|期末数|本期费用|本期发生额")


def _header_row(rows: list[list[str]]) -> int | None:
    """只认含金额语义列的表头；仅有“2025年金额”的损益明细表不是附注明细表。"""
    for index, row in enumerate(rows[:6]):
        text = compact("".join(str(cell or "") for cell in row))
        if not ("项目" in text or "科目" in text):
            continue
        if SEMANTIC_COLUMN.search(text):
            return index
    return None


def _account_table(title: str, header: list[str], rows: list[list[str]]) -> bool:
    haystack = compact(title) + compact("".join(str(cell or "") for cell in header))
    haystack += compact("".join(str((row or [""])[0] or "") for row in rows[:24]))
    return any(term in haystack for term in NOTE_TABLE_TERMS)


def _numeric(cell: str) -> Decimal | None:
    text = str(cell or "").strip().replace("，", ",")
    if not text or text in {"-", "—", "不适用", "/"}:
        return None
    text = text.replace("(", "-").replace("（", "-").replace(")", "").replace("）", "")
    return decimal(text)


def load_note_pages(pdf_path: Path, *, max_pages: int = MAX_PAGES) -> tuple[list[dict], dict]:
    """只解析命中财务附注关键词的页面，避免全册表格检测拖垮运行时长。"""
    pages: list[dict] = []
    scanned = 0
    with pymupdf.open(pdf_path) as pdf:
        scored: list[tuple[int, int]] = []
        for index, page in enumerate(pdf):
            scanned += 1
            text = page.get_text("text")
            if not any(term in text for term in NOTE_TERMS) or not re.search(r"单位[:：]|余额|增加|减少|预算|费用", text):
                continue
            score = sum(3 for term in NOTE_TABLE_TERMS if term in text)
            score += 2 if re.search(r"预算数|本期增加|本期减少|期末余额", text) else 0
            score += 1 if "单位" in text else 0
            scored.append((-score, index))
        scored.sort()
        for _rank, index in scored[:max_pages]:
            page = pdf[index]
            text = page.get_text("text")
            blocks = _blocks(page)
            tables = []
            try:
                for table in page.find_tables().tables:
                    tables.append({"bbox": [round(v, 2) for v in table.bbox],
                                   "data": [[str(cell or "") for cell in row] for row in table.extract()],
                                   "cells": [row.cells for row in table.rows]})
            except (RuntimeError, ValueError):
                tables = []
            pages.append({"page": index + 1, "text": text, "blocks_detail": blocks, "tables": tables})
    receipt = {"version": NOTES_VERSION, "scanned_pages": scanned, "selected_pages": len(pages),
               "note": "只解析命中附注关键词的页面；未命中页不作为没有该项目。"}
    return pages, receipt


def parse_notes(pages: list[dict], document, *, limit: int = MAX_ITEMS) -> tuple[list[FinancialItem], dict]:
    items: list[FinancialItem] = []
    seen: set[str] = set()
    tables_seen = 0
    last_header: list[str] | None = None
    last_title = ""
    for page in pages:
        page_no = int(page.get("page") or 0)
        text = str(page.get("text") or "")
        factor, unit_label = _unit_factor(text)
        scope = _scope(text)
        currency = _currency(text)
        for table in page.get("tables") or []:
            rows = table.get("data") or []
            if not rows:
                continue
            header_index = _header_row(rows)
            title = _title_above(page.get("blocks_detail") or [], table.get("bbox") or [])
            inherited = False
            if header_index is None:
                # 跨页续表：本页无表头，且表在页面顶部、列数与上页表头一致时继承表头。
                top = (table.get("bbox") or [0, 9999])[1]
                title = title or last_title
                if last_header and top <= 140 and len(rows[0]) == len(last_header) and _account_table(title, last_header, rows):
                    header, header_index, inherited = last_header, -1, True
                else:
                    continue
            else:
                header = rows[header_index]
            if not _account_table(title, header, rows[header_index + 1:] if header_index >= 0 else rows):
                continue
            last_header = header
            last_title = title
            tables_seen += 1
            for row_index in range(header_index + 1, len(rows)):
                row = rows[row_index]
                if not row:
                    continue
                row_header = str(row[0] or "").strip()
                if not row_header or _numeric(row_header) is not None:
                    continue
                for column_index in range(1, min(len(row), len(header))):
                    raw = str(row[column_index] or "").strip()
                    value = _numeric(raw)
                    if value is None:
                        continue
                    column_header = str(header[column_index] or "").strip()
                    nature = _semantics(column_header)
                    year_match = re.search(r"(20\d{2})", column_header)
                    item_period = year_match.group(1) if year_match else str(getattr(document, "period", ""))
                    normalized = value * factor
                    key = f"{page_no}|{title}|{row_header}|{column_header}|{raw}"
                    if key in seen:
                        continue
                    seen.add(key)
                    bbox: list[float] = []
                    cells = table.get("cells") or []
                    if row_index < len(cells) and column_index < len(cells[row_index] or []):
                        bbox = [round(float(v), 2) for v in (cells[row_index][column_index] or [])]
                    items.append(FinancialItem(
                        item_id=_item_id(document.document_id, page_no, title, row_header, column_header, raw),
                        company=document.company, company_id=getattr(document, "company_id", ""),
                        row_header=row_header[:80],
                        column_header=column_header[:40], value_semantics=nature,
                        raw_value=raw, value=str(value), unit=unit_label,
                        normalized=str(normalized), period=item_period,
                        scope=scope, currency=currency,
                        document_id=document.document_id, file_sha256=getattr(document, "file_sha256", ""),
                        pdf_page=page_no, bbox=bbox,
                        quote=compact(" | ".join(cell for cell in row if cell))[:300],
                        page_verified=compact(row_header)[:20] in compact(text),
                        table_title=(title or ("跨页续表" if inherited else ""))[:60],
                    ))
                    if len(items) >= limit:
                        return items, {"version": NOTES_VERSION, "items": len(items), "tables": tables_seen,
                                       "truncated": True}
    receipt = {"version": NOTES_VERSION, "items": len(items), "tables": tables_seen, "truncated": False,
               "note": "只登记原文明确写出的行列与数值；语义为 none 的列不参与金额勾稽。"}
    return items, receipt
