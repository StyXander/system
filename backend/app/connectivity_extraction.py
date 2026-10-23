"""原始PDF自动发现：坐标行、年度表头、单位和上下文独立留存。

不读取人工字段样本，不接受目标页、目标金额或预期答案。
跨页继承只在表头和续表线索吻合时使用，失败页不伪装已解析。
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import hashlib
import json
import re
import time
from typing import Callable

import pymupdf
import httpx
from fastapi import HTTPException

from .connectivity_rules import TOPICS
from .connectivity_schemas import DisclosureOccurrence, ExtractionExclusion, ReportDocument, SearchCoverage
from .source_viewer import PDF_ACCESS_LOCK
from .secure_download import download_bounded, SecureDownloadError

EXTRACTION_VERSION = "coordinates_v1.9"
# 原始布局结构未变化时复用解析缓存，运行仍记录完整提取算法的新版号。
PARSER_CACHE_VERSION = "coordinates_v1.5"
NUMBER = re.compile(r"(?<![\d.])(?:[（(]?-?\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?[)）]?|[（(]?-?\d+(?:\.\d+)?[)）]?)(?![\d.])")
# 长单位排在短单位前，保留二氧化碳当量、粗钢与产品的不同口径。
UNIT_ATOM = r"(?:万吨二氧化碳当量|吨二氧化碳当量|万吨标准煤|吨标准煤|万吨粗钢|吨粗钢|万吨产品|吨产品|万千瓦时|千瓦时|兆瓦时|吉焦|太焦|万吨|吨|百万立方米|千立方米|万立方米|亿立方米|立方米|百万元|千元|万元|亿元|元|万人|人)"
UNIT = re.compile(UNIT_ATOM + r"(?:[/／]" + UNIT_ATOM + r")?|[%％]")
# 币种声明：金额／货币／数据＋人民币，覆盖"人民币元""单位：人民币"等常见写法。
CURRENCY_DECLARATION = re.compile(r"(?:货币|金额|数据|单位)[^。；;]{0,25}(?:均为人民币|均以人民币|为人民币元|以人民币|人民币元)")


def source_path(root: Path, document: ReportDocument) -> Path:
    """文件名只来自已登记的内容身份，不接受客户端路径。"""
    if not re.fullmatch(r"[0-9a-f]{64}", document.file_sha256):
        raise ValueError("来源未登记有效版本")
    return root / "backend/runtime/connectivity/sources" / f"{document.file_sha256}.pdf"


def ensure_source(root: Path, document: ReportDocument) -> Path:
    """仅获取登记的准确URL与版本，支持交易所来源及明确标识的公告镜像。"""
    path = source_path(root, document)
    if path.exists():
        with path.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != document.file_sha256:
                raise HTTPException(409, "原件与登记版本不符，已停止读取")
        return path
    url = document.source_url
    allowed_source = bool(re.fullmatch(r"https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/\d+\.pdf", url, re.I)
        or re.fullmatch(r"https://disc\.static\.szse\.cn/disc/disk\d+/finalpage/\d{4}-\d{2}-\d{2}/[a-f0-9-]+\.pdf", url, re.I)
        or (document.source_kind == "announcement_mirror" and re.fullmatch(r"https://file\.finance\.sina\.com\.cn/[^?#]+\.pdf", url, re.I)))
    if not allowed_source:
        raise HTTPException(404, "该登记来源暂不支持自动获取，请使用公开出处")
    try:
        with httpx.Client(timeout=60, trust_env=False, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.cninfo.com.cn/"}) as client:
            for attempt in range(2):
                try:
                    download_bounded(url, path, client=client, max_bytes=120*1024*1024, require_pdf=True,
                        is_allowed_url=lambda candidate: candidate == url, expected_sha256=document.file_sha256)
                    break
                except (SecureDownloadError,httpx.HTTPError) as error:
                    # 仅短暂网络及服务端限流错误重试同一版本；内容或版本不符立即停止。
                    temporary = isinstance(error,httpx.HTTPError) or error.code == "NETWORK_ERROR" or (
                        error.code == "HTTP_ERROR" and error.detail.get("status_code") in {429,500,502,503,504})
                    if attempt or not temporary:
                        raise
                    time.sleep(1)
    except (SecureDownloadError, httpx.HTTPError, OSError) as error:
        raise HTTPException(503, "登记原件当前无法获取，未用其他版本替代") from error
    return path


def load_registry(root: Path) -> list[ReportDocument]:
    path = root / "backend/connectivity_reports.json"
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))["documents"]
    result = [ReportDocument.model_validate(row) for row in rows]
    for doc in result:
        doc.available = source_path(root, doc).is_file()
    return result


def _lines(page) -> list[dict]:
    """按真实坐标拼同行；双印刷页及明确双栏保持左右顺序。"""
    blocks = page.get_text("dict")["blocks"]
    text_blocks = [b for b in blocks if b.get("type") == 0]
    width = page.rect.width
    split = width > page.rect.height * 1.15
    if not split:
        paragraphs = [b for b in text_blocks if len(b.get("lines", [])) >= 4]
        split = any(b["bbox"][2] < width * .53 for b in paragraphs) and any(b["bbox"][0] > width * .46 for b in paragraphs)
    groups = defaultdict(list)
    for block in text_blocks:
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                box = span["bbox"]
                side = int((box[0] + box[2]) / 2 >= width / 2) if split else 0
                groups[(side, round(box[1] / 2) * 2)].append((box, text))
    result = []
    for (side, y), spans in sorted(groups.items()):
        spans.sort(key=lambda row: row[0][0])
        result.append({"text": " ".join(t for _, t in spans), "side": side,
            "bbox": [min(b[0] for b, _ in spans), min(b[1] for b, _ in spans), max(b[2] for b, _ in spans), max(b[3] for b, _ in spans)],
            "spans": spans})
    return result


def _unit(text: str) -> str:
    match = re.search(r"(?:单位|单\s*位)\s*[:：]?\s*(人民币)?\s*(" + UNIT.pattern + r")", text)
    if match:
        return match.group(2).replace("／", "/").replace("％", "%")
    # 人民币中的“人”不是人数单位，金额未注明尺度时仍然保留未知。
    found = UNIT.findall(text.replace("人民币", ""))
    return found[-1].replace("／", "/").replace("％", "%") if found else ""


def _unit_source(label: str, above: list[str]) -> str:
    """单位来源必须可追溯：本标签、本表上方说明或表前注，不跨段继承。"""
    if "单位" in label:
        return "行标签内单位"
    if above:
        return "本表上方单位说明"
    return ""


def _quality(year: str, unit: str, column_header: str, has_number: bool = True) -> tuple[str, str]:
    """质量失败关闭：只有年度、单位与行列绑定同时成立才升级为 located。"""
    if not has_number:
        return "text_only", "该行无独立数值，仅作文字依据"
    if not year:
        return "uncertain", "年度列无法归属，未回退为报告期间"
    if not unit:
        return "uncertain", "单位待定，未从本表或本行确认"
    if not (column_header or "").strip():
        return "uncertain", "行列头未绑定，无法确认列归属"
    return "located", "年度、单位与行列头均已绑定"


def _footnote_for(table: dict, lines: list[dict], tables: list[dict]) -> str:
    """脚注只绑定其适用表：限在本表下方 60pt 内，且不越过下一张表的表头。"""
    bottom = table["bbox"][3]
    next_tops = [item["bbox"][1] for item in tables if item.get("bbox") and item["bbox"][1] >= bottom]
    limit = min(next_tops) if next_tops else float("inf")
    for row in sorted(lines, key=lambda item: item["bbox"][1]):
        top = row["bbox"][1]
        if top < bottom - 1:
            continue
        if top > bottom + 60 or top >= limit:
            break
        if re.match(r"注[:：\d]|\*", row["text"]):
            return row["text"]
    return ""


def _table_layout(page, lines: list[dict]) -> dict:
    """用真实合并单元格边界绑定年度及分组，支持同一年下钢铁/其他/合计。"""
    keywords = [word for topic in TOPICS.values() for word in topic["keywords"]]
    if not any(any(word in line["text"].replace(" ", "") for word in keywords) for line in lines):
        return {"headers": [], "tables": []}
    headers = []
    tables = []
    try:
        for table in page.find_tables().tables:
            data = table.extract()
            table_headers = []
            tables.append({"bbox": list(table.bbox), "data": data, "cells": [row.cells for row in table.rows], "headers": table_headers})
            for row_index, values in enumerate(data[:4]):
                for col_index, value in enumerate(values):
                    value = str(value or "")
                    bounds = table.rows[row_index].cells[col_index]
                    if bounds and (re.fullmatch(r"\s*(?:20\d{2}\s*年?(?:度|末)?|本期(?:金额|发生额)?|本年(?:金额|发生额)?|合计|钢铁\d*|其他|单位|币种[:：]?人民币)\s*", value)):
                        entry = {"text": value, "bbox": list(bounds), "table_bbox": list(table.bbox)}
                        headers.append(entry)
                        table_headers.append(entry)
    except (RuntimeError, ValueError):
        # 表格检测不足不冒充成功，坐标原文仍可作为不确定候选读取。
        return {"headers": [], "tables": []}
    return {"headers": headers, "tables": tables}


def _table_heading(lines: list[dict], table: dict) -> str:
    """取表格上方最近的短行，作为表标题/单位/主体层级的原文来源。"""
    near = []
    for row in lines:
        gap = table["bbox"][1] - row["bbox"][3]
        text = row["text"].strip()
        if 0 <= gap <= 55 and text and len(text) <= 90:
            near.append((row["bbox"][3], text))
    near.sort()
    return " / ".join(text for _, text in near[-3:])


def _extract_tables(page: dict, document: ReportDocument, topics: list[str]) -> list[DisclosureOccurrence]:
    """优先按表格单元格取数，避免把换行标签、脚注号和年度值拼成同一行。"""
    result = []
    lines = page["lines"]
    for table_index, table in enumerate(page.get("tables", [])):
        headers = table.get("headers", [])
        if not any(re.search(r"20\d{2}|本期|本年", h["text"]) for h in headers):
            # 检测器会把表头与表体断成两块；仅接回同宽、紧邻且列数相同的表头。
            previous_headers = [t for t in page.get("tables", []) if t.get("headers")
                and 0 <= table["bbox"][1]-t["bbox"][3] <= 32
                and abs(table["bbox"][0]-t["bbox"][0]) < 3 and abs(table["bbox"][2]-t["bbox"][2]) < 3
                and len(t["data"][0]) == len(table["data"][0])
                and any(re.search(r"20\d{2}|本期|本年", h["text"]) for h in t["headers"])]
            if previous_headers:
                headers = max(previous_headers, key=lambda t:t["bbox"][3])["headers"]
        data = table["data"]
        heading = _table_heading(lines, table)
        # 只认表标题/表头里的合并或母公司；同时出现两者视为口径不明，不猜。
        scope_hint = ""
        if "母公司" in heading and not re.search(r"合并(?!范围)", heading):
            scope_hint = "母公司"
        elif re.search(r"合并(?!范围)", heading) and "母公司" not in heading:
            scope_hint = "合并"
        currency_hint = "CNY" if "人民币" in heading else ""
        table_text = "\n".join(" | ".join(str(v or "") for v in row) for row in data)
        table_topics = [topic for topic in topics if any(word in table_text.replace(" ", "") for word in TOPICS[topic]["keywords"])]
        for row_index, values in enumerate(data):
            if not values or not any(values):
                continue
            label = str(next((v for v in values if v), "")).strip()
            matched = [topic for topic in topics if any(word in re.sub(r"\s+", "", label) for word in TOPICS[topic]["keywords"])]
            if not matched and len(table_topics) == 1 and re.match(r"合计|总计|其中|资本化|费用化", label):
                matched = table_topics
            if not matched:
                continue
            cells = table["cells"][row_index]
            units = [str(v).replace("\n", "").replace(" ", "").replace("／", "/").replace("％", "%") for v in values if v and UNIT.fullmatch(str(v).replace("\n", "").replace(" ", ""))]
            above = [r["text"] for r in lines if r["bbox"][3] <= table["bbox"][1]+3 and "单位" in r["text"]]
            label_unit = re.search(r"[（(]\s*(" + UNIT.pattern + r")\s*[)）]", label)
            unit = units[0] if units else _unit(label) if "单位" in label else label_unit.group(1) if label_unit else _unit(above[-1]) if above else ""
            for column_index, raw in enumerate(values):
                token = str(raw or "").strip().replace("\n", "").replace("（", "(").replace("）", ")")
                if not re.fullmatch(r"\(?-?\d[\d,，]*(?:\.\d+)?\)?", token):
                    continue
                bounds = cells[column_index]
                if not bounds or column_index == 0:
                    continue
                x = (bounds[0]+bounds[2])/2
                applicable = [h for h in headers if h["bbox"][0]-.5 <= x <= h["bbox"][2]+.5 and h["bbox"][3] <= bounds[1]+3]
                years = [h for h in applicable if re.search(r"20\d{2}|本期|本年", h["text"])]
                year = ""
                column_header = ""
                scope = ""
                selected = []
                if years:
                    top = max(years, key=lambda h:h["bbox"][3])
                    match = re.search(r"20\d{2}", top["text"])
                    # 年度列解析失败时保持空值；不得用报告期间顶替指标年度。
                    year = match.group() if match else ""
                    selected = [h["text"] for h in applicable if h["bbox"][1] >= top["bbox"][1]]
                    column_header = " / ".join(selected)
                    scope = " / ".join(text for text in selected if re.fullmatch(r"钢铁\d*|其他|合计", text))
                row_text = " | ".join(str(v or "").replace("\n", " ") for v in values)
                context_rows = data[max(0,row_index-2):row_index+3]
                context = "\n".join(" | ".join(str(v or "").replace("\n", " ") for v in row) for row in context_rows)
                prefix = ([f"表标题/上方文字：{heading}"] if heading else []) + (["币种：人民币"] if currency_hint else [])
                context = f"本页对应列头：{column_header}\n{context}"
                if above:
                    context = above[-1] + "\n" + context
                if prefix:
                    context = "\n".join(prefix) + "\n" + context
                quality, reason = _quality(year, unit, column_header)
                scope_value = scope or scope_hint
                scope_quote = ((column_header if scope else heading)[:200]) if scope_value else ""
                currency_value = currency_hint or ("CNY" if "人民币" in context else "")
                currency_quote = heading[:200] if "人民币" in heading else ("人民币" if "人民币" in context else "")
                result.append(DisclosureOccurrence(occurrence_id=f"{document.document_id}-{page['page']}-T{table_index}-R{row_index}-C{column_index}",
                    document_id=document.document_id, pdf_page=page["page"], bbox=list(bounds), label=label,
                    value=token, unit=unit, unit_source="本表单位列" if units else _unit_source(label, above),
                    currency=currency_value,
                    currency_source_id=f"{document.document_id}-{page['page']}-T{table_index}-R{row_index}-C{column_index}" if currency_value else "",
                    currency_source_quote=currency_quote,
                    year=year, scope=scope_value,
                    scope_source_id=f"{document.document_id}-{page['page']}-T{table_index}-R{row_index}-C{column_index}" if scope_value else "",
                    scope_source_quote=scope_quote,
                    year_status="attributed" if year else "unattributed",
                    row_header=row_text, column_header=column_header, header_path=selected,
                    context=context[:7000], footnote_scope=_footnote_for(table, lines, page.get("tables", [])),
                    quality=quality, quality_reason=reason, topic=matched[0],
                    version_role=document.version_role))
    return result


def _number_box(line: dict, match) -> list[float]:
    """回到组成该行的原始span，避免把同行不同列全部绑定首个年度。"""
    offset = 0
    for bounds, text in line["spans"]:
        if offset <= match.start() < offset + len(text):
            start = (match.start() - offset) / max(1, len(text))
            end = min(1, (match.end() - offset) / max(1, len(text)))
            return [bounds[0]+(bounds[2]-bounds[0])*start, bounds[1], bounds[0]+(bounds[2]-bounds[0])*end, bounds[3]]
        offset += len(text) + 1
    return line["bbox"]


def _join_indicator_fragments(lines: list[dict]) -> list[dict]:
    """接合跨两行的强度标签和分式单位，数值仍保留各自原始坐标。"""
    result = list(lines)
    for index, line in enumerate(lines):
        start = re.fullmatch(r"(.{2,8}?)\s+(\S+[/／])", line["text"])
        if not start:
            continue
        nearby = lines[index+1:index+4]
        suffix = next((row for row in nearby if row["side"] == line["side"]
            and 0 <= row["bbox"][1]-line["bbox"][1] <= 35
            and re.fullmatch(r"强度(?:比)?\s+\S+", row["text"])), None)
        numeric = next((row for row in nearby if row["side"] == line["side"]
            and 0 <= row["bbox"][1]-line["bbox"][1] <= 20
            and re.fullmatch(r"[\d,，.\s/／%％-]+", row["text"])), None)
        if not suffix or not numeric:
            continue
        ending = re.fullmatch(r"(强度(?:比)?)\s+(\S+)", suffix["text"])
        unit = (start.group(2)+ending.group(2)).replace("／", "/")
        if not UNIT.fullmatch(unit):
            continue
        label = start.group(1)+ending.group(1)
        spans = [(line["bbox"],label), (suffix["bbox"],unit), *numeric["spans"]]
        result[index] = {**line,"text":" ".join(text for _,text in spans),"spans":spans,
            "bbox":[min(row["bbox"][0] for row in [line,suffix,numeric]),line["bbox"][1],
                max(row["bbox"][2] for row in [line,suffix,numeric]),max(row["bbox"][3] for row in [line,suffix,numeric])]}
    return result


def _coordinate_year(lines: list[dict], line: dict, number_box: list[float]) -> tuple[str,str]:
    """按最近的纯年度表头列中心绑定；跳过空列符号时不靠数值序号猜年度。"""
    headers = [row for row in lines if row["side"] == line["side"]
        and 0 < line["bbox"][1]-row["bbox"][1] <= 120
        and re.fullmatch(r"(?:20\d{2}\s*年?(?:度|末)?\s*){2,}",row["text"])]
    if not headers:
        return "",""
    header = max(headers,key=lambda row:row["bbox"][1])
    positions = [(match.group(),_number_box(header,match)) for match in re.finditer(r"20\d{2}",header["text"])]
    x = (number_box[0]+number_box[2])/2
    year,_ = min(positions,key=lambda item:abs((item[1][0]+item[1][2])/2-x))
    return year,header["text"]


def extract_document(root: Path, document: ReportDocument, topics: list[str], cancelled: Callable[[], bool] = lambda: False) -> tuple[list[DisclosureOccurrence], SearchCoverage, list[ExtractionExclusion]]:
    """全页读取后召回候选；缓存不包含参考答案，只复用同版原文解析。"""
    path = ensure_source(root, document)
    cache_dir = root / "backend/runtime/connectivity/extraction"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{document.file_sha256}-{PARSER_CACHE_VERSION}.json"
    if cache_path.exists():
        pages = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        pages = []
        with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
            for index, page in enumerate(pdf):
                if cancelled():
                    raise InterruptedError("用户取消了原件解析")
                try:
                    lines = _lines(page)
                    layout = _table_layout(page, lines)
                    pages.append({"page": index + 1, "width": page.rect.width, "height": page.rect.height, "lines": lines, **layout, "error": "" if lines else "无可读取文字层"})
                except (ValueError, RuntimeError) as error:
                    pages.append({"page": index + 1, "lines": [], "error": type(error).__name__})
        import uuid
        temporary = cache_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        temporary.replace(cache_path)
    if any(not page.get("width") for page in pages):
        # 旧布局缓存只补读页面几何，不重复解析正文，也不根据屏幕像素猜坐标。
        with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
            for info, original in zip(pages, pdf):
                info["width"], info["height"] = original.rect.width, original.rect.height
    occurrences = []
    coverage = SearchCoverage(document_id=document.document_id, total_pages=len(pages), parsed_pages=0)
    previous = []
    for page in pages:
        if cancelled():
            raise InterruptedError("用户取消了候选定位")
        if page["error"]:
            coverage.failed_pages.append({"page": page["page"], "reason": page["error"]})
            continue
        coverage.parsed_pages += 1
        coverage.searched_pages.append(page["page"])
        lines = _join_indicator_fragments(page["lines"])
        table_rows = _extract_tables(page, document, topics)
        occurrences.extend(table_rows)
        for index, line in enumerate(lines):
            text = line["text"]
            matched = [topic for topic in topics if any(key in re.sub(r"\s+", "", text) for key in TOPICS[topic]["keywords"])]
            is_basis = bool(re.search(r"报告范围|统计口径|统计范围|除.*特别说明|报告主体|编制依据|币种.*人民币|金额.*人民币|货币.*人民币|报告时间范围|本报告覆盖的周期|报告期.*20\d{2}", text)
                or (page["page"] <= 5 and re.search(r"股份有限公司|有限责任公司", text)))
            basis_only = is_basis and not matched
            if not matched and is_basis:
                matched = ["basis"]
            if not matched and re.search(r"资本化|费用化|用化投入", text):
                nearby = "".join(r["text"] for r in lines[max(0,index-2):index+2] if r["side"] == line["side"])
                if "environment" in topics and re.search(r"环保|环境保护", nearby):
                    matched = ["environment"]
            if not matched:
                continue
            same_side = [r for r in lines[max(0, index - 5):index + 6] if r["side"] == line["side"]]
            context = "\n".join(r["text"] for r in same_side)
            # 续表只继承上一页尾部的单位和表头，不把任意上页标题作为事实。
            continued = index < 6 and "续" in " ".join(r["text"] for r in lines[:5])
            inherited = "\n".join(r["text"] for r in previous[-8:]) if continued else ""
            if inherited:
                context = inherited + "\n[本页续表]\n" + context
            units_above = "\n".join(r["text"] for r in same_side if r["bbox"][1] <= line["bbox"][1])
            explicit_above = [r["text"] for r in lines[max(0,index-18):index] if r["side"] == line["side"] and "单位" in r["text"]]
            unit_hint = _unit(text) or (_unit(explicit_above[-1]) if explicit_above else "") or _unit(inherited)
            numeric_line = line
            numbers = list(NUMBER.finditer(text))
            # 图形表格可能把指标名称和数值放在相邻行；只作不确定候选。
            if not numbers and index + 1 < len(lines) and lines[index + 1]["side"] == line["side"] and re.match(r"^[\d,，.\s%-]+$", lines[index+1]["text"]):
                numeric_line = lines[index + 1]
                numbers = list(NUMBER.finditer(numeric_line["text"]))
            header = [r for r in same_side if r["bbox"][1] < line["bbox"][1] and re.search(r"20\d{2}|本年|本期", r["text"])]
            year_labels = re.findall(r"20\d{2}", header[-1]["text"]) if header else []
            valid = [n for n in numbers if not (
                re.fullmatch(r"20\d{2}", n.group()) and ("年" in numeric_line["text"][n.end():n.end()+2] or len(numbers) == 1)
                or re.search(r"[A-Za-z]$", numeric_line["text"][:n.start()])
                or re.match(r"[A-Za-z]", numeric_line["text"][n.end():])
                or (n.start() < 2 and re.match(r"[)）.、]", numeric_line["text"][n.end():]))
                or (n.group().startswith("(") and not n.group().endswith(")")))]
            if basis_only:
                valid = []
            # 无数值的定义段落也进入检索，NAR和五项前提需要原文证据。
            candidates = valid or [None]
            for offset, match in enumerate(candidates):
                raw = match.group().replace("（", "(").replace("）", ")") if match else None
                explicit_years = re.findall(r"(20\d{2})年", text)
                year = year_labels[offset] if offset < len(year_labels) and len(valid) == len(year_labels) else explicit_years[0] if len(set(explicit_years)) == 1 else ""
                label = re.split(NUMBER, text)[0].strip(" ：:，,。") or text[:70]
                column_header = header[-1]["text"] if header else ""
                number_box = _number_box(numeric_line, match) if match else line["bbox"]
                if match:
                    coordinate_year, coordinate_header = _coordinate_year(lines,line,number_box)
                    if coordinate_year:
                        year,column_header = coordinate_year,coordinate_header
                    x = (number_box[0]+number_box[2])/2
                    candidates_above = [h for h in page.get("headers", []) if h["bbox"][0] <= x <= h["bbox"][2] and h["bbox"][3] <= number_box[1]+3
                        and h["table_bbox"][0]-2 <= x <= h["table_bbox"][2]+2 and h["table_bbox"][1]-2 <= number_box[1] <= h["table_bbox"][3]+80]
                    if candidates_above:
                        nearest_band = max(h["table_bbox"][1] for h in candidates_above)
                        candidates_above = [h for h in candidates_above if h["table_bbox"][1] == nearest_band]
                    years_above = [h for h in candidates_above if re.search(r"20\d{2}|本期|本年", h["text"])]
                    if years_above:
                        nearest = max(years_above, key=lambda h:h["bbox"][3])
                        year_match = re.search(r"20\d{2}", nearest["text"])
                        year = year_match.group() if year_match else ""
                        column_header = " / ".join(h["text"] for h in candidates_above if h["bbox"][1] >= nearest["bbox"][1])
                        context = context + "\n本页对应列头：" + column_header
                    # 句内明确写出的年度高于邻近表头，不能把表后文字误绑到上一张表。
                    inline_periods = re.findall(r"(20\d{2})\s*年", numeric_line["text"][:match.start()])
                    if inline_periods:
                        year = inline_periods[-1]
                        column_header = "句内明示" + year + "年"
                    # 句内多指标使用各数值前的局部标签，避免费用化和资本化共用名称。
                    prefix = numeric_line["text"][:match.start()]
                    phrase = re.split(r"[，；;。]", prefix)[-1].strip()
                    if re.search(r"[，；;。]", prefix) and phrase and re.search(r"投入|费用|支出|人员|比例|强度", phrase) and len(phrase) < 70:
                        label = re.sub(r"^20\d{2}\s*年[，,\s]*", "", phrase)
                suffix = numeric_line["text"][match.end():match.end()+16] if match else ""
                immediate = re.match(r"\s*(" + UNIT.pattern + r")", suffix)
                unit = immediate.group(1).replace("％", "%").replace("／", "/") if immediate else unit_hint
                inline_units = UNIT.findall(text)
                if "强度" in text and len(inline_units) == 2 and numeric_line["text"].lstrip().startswith("/"):
                    unit = inline_units[0] + "/" + inline_units[1]
                # 同一单元格已按表格结构提取时，不再提交另一份位置身份重复相加。
                if match:
                    duplicates = [row for row in table_rows if row.value == raw and row.bbox[0]-2 <= (number_box[0]+number_box[2])/2 <= row.bbox[2]+2
                        and row.bbox[1]-2 <= (number_box[1]+number_box[3])/2 <= row.bbox[3]+2]
                    if duplicates:
                        # 同一物理单元格合并两种读取的依据，不能让较差的表格结果吞掉坐标层的单位与年度。
                        for row in duplicates:
                            row.unit = row.unit or unit
                            row.year = row.year or year
                            row.column_header = row.column_header or column_header
                            if "人民币" in context:
                                row.currency = row.currency or "CNY"
                            row.context = (row.context + "\n[同页坐标补充]\n" + context)[:7000]
                            row.year_status = "attributed" if row.year else "unattributed"
                            row.unit_source = row.unit_source or ("同页坐标补充" if unit else "")
                            row.quality, row.quality_reason = _quality(row.year, row.unit, row.column_header)
                        continue
                # 金额原币种只在上下文明示人民币时确认，不由元字推定币种。
                currency = "CNY" if "人民币" in context else ""
                identity = f"{document.document_id}-{page['page']}-{index}-{offset}"
                # 行列绑定可由列头、表头或句内明示年度提供；三者都没有才算未绑定。
                binding = column_header or (header[-1]["text"] if header else "") or (f"句内明示{year}" if year else "")
                quality, reason = _quality(year, unit, binding, bool(match))
                if match and numeric_line is not line:
                    quality, reason = "uncertain", "数值来自相邻行，指标与数值未同行绑定"
                occurrences.append(DisclosureOccurrence(occurrence_id=identity, document_id=document.document_id,
                    pdf_page=page["page"], bbox=number_box, label=label[:160], value=raw, unit=unit,
                    unit_source="同行紧跟单位" if immediate else "本页单位说明" if unit_hint else "",
                    currency=currency, year=year, year_status="attributed" if year else "unattributed",
                    row_header=text, column_header=column_header,
                    header_path=[column_header] if column_header else [],
                    context=context[:7000], footnotes=[r["text"] for r in same_side if re.match(r"注[:：\d]|\*", r["text"])],
                    footnote_scope=(next((r["text"] for r in same_side if re.match(r"注[:：\d]|\*", r["text"])), "")[:120]),
                    quality=quality, quality_reason=reason, version_role=document.version_role,
                    topic=matched[0]))
        previous = lines
    for row in occurrences:
        page = pages[row.pdf_page-1]
        row.page_width, row.page_height = page.get("width", 0), page.get("height", 0)
    # 全报告币种声明可适用于未特别注明的金额，但必须另记声明的实际页源。
    declarations = []
    for row in occurrences:
        compact = re.sub(r"\s+", "", row.context)
        if row.topic == "basis" and CURRENCY_DECLARATION.search(compact):
            declarations.append(row)
    if declarations:
        declaration = declarations[0]
        declared_quote = CURRENCY_DECLARATION.search(re.sub(r"\s+", "", declaration.context)).group()
        for row in occurrences:
            if not row.currency and re.search(r"元", row.unit) and not re.search(r"美元|港元|欧元|日元", row.context):
                row.currency = "CNY"
                row.currency_source_id = declaration.occurrence_id
                row.currency_source_quote = declared_quote
    coverage.discovered_count = len(occurrences)
    return occurrences, coverage, _exclusions(occurrences)


def _exclusions(occurrences: list[DisclosureOccurrence]) -> list[ExtractionExclusion]:
    """已提取但未进入候选的行必须显式列示，不允许静默丢弃或改标签消化。"""
    rows = []
    for row in occurrences:
        if row.quality == "located":
            continue
        if row.quality == "text_only":
            continue  # 文字依据仍可用于叙述关系，不算"提取了数值却没计入"。
        reason = row.quality_reason or "未达到候选门槛"
        rows.append(ExtractionExclusion(occurrence_id=row.occurrence_id, document_id=row.document_id,
            pdf_page=row.pdf_page, label=row.label, value=row.value or "", year=row.year, unit=row.unit, reason=reason))
    return rows


def report_industry_context(root: Path, run) -> dict:
    """从本公司业务介绍提取行业出处，三行业试点仅提供本项目检索重点。"""
    trials = {'白酒': ['用水与取水', '包装材料', '研发投入'],
              '钢铁': ['粗钢产量', '综合能耗', '排放强度', '环保投入'],
              '电池': ['能源结构', '材料回收', '产能与产量', '排放强度']}
    identity = re.compile(r'公司.{0,18}(主营业务|主要从事|所属|所处|属于)|主营业务为|所属行业|主要业务是')
    for document in run.documents:
        path = root / 'backend/runtime/connectivity/extraction' / f'{document.file_sha256}-{PARSER_CACHE_VERSION}.json'
        if not path.is_file():
            continue
        for page in json.loads(path.read_text(encoding='utf-8')):
            lines = page.get('lines', [])
            for index, line in enumerate(lines):
                context = '\n'.join(r['text'] for r in lines[max(0,index-1):index+3])
                if not identity.search(context):
                    continue
                industry = next((name for name in trials if name in context), None)
                if not industry:
                    continue
                oid = f'{document.document_id}-{page["page"]}-IND-{index}'
                if not any(o.occurrence_id == oid for o in run.occurrences):
                    run.occurrences.append(DisclosureOccurrence(occurrence_id=oid,document_id=document.document_id,
                        pdf_page=page['page'],bbox=line.get('bbox',[]),page_width=page.get('width',0),page_height=page.get('height',0),
                        label='公司业务与行业说明',row_header=line['text'],context=context,quality='text_only',topic='basis'))
                return {'industry': industry, 'evidence_id': oid, 'quote': context,
                        'search_priorities': trials[industry], 'source': 'company_report',
                        'note': '本项目三行业检索试点；不是评级权重或同业平均值'}
    return {'industry': '未取得明确行业依据', 'search_priorities': [], 'source': 'generic',
            'note': '使用通用指标指导，不猜测行业分类或行业均值'}


def retrieve_targeted_pages(root: Path, run, checks: list, round_number: int = 1, per_check: int = 8) -> list[dict]:
    """按具体缺口和模型检索词搜索已解析全文，补出初次主题召回之外的文字依据。

    新片段仅作原文证据，不猜数值、单位或年度归属；没有文字层的页单独记失败。
    缓存按登记哈希读取，不接受模型传入路径或联网地址。
    """
    if round_number not in (1, 2):
        return []
    from .connectivity_intelligence import GAP_KEYWORDS
    sources = {o.occurrence_id: o for o in run.occurrences}
    cached = {}
    for document in run.documents:
        path = root / 'backend/runtime/connectivity/extraction' / f'{document.file_sha256}-{PARSER_CACHE_VERSION}.json'
        if path.is_file():
            cached[document.document_id] = json.loads(path.read_text(encoding='utf-8'))
    tasks = []
    for check in checks:
        members = [sources[m.occurrence_id] for m in check.members if m.occurrence_id in sources]
        doc_ids = {m.document_id for m in members}
        queries = [q for h in check.hypotheses for q in h.retrieval_queries]
        words = list(dict.fromkeys([w for c in check.conditions if c.status != 'supported'
                                    for w in GAP_KEYWORDS.get(c.name, [])] + queries))
        if not words:
            continue
        topic_words = TOPICS.get(check.topic, {}).get('keywords', [])
        ranked, pages_scanned, failed = [], {}, []
        for doc_id in doc_ids:
            pages_scanned[doc_id] = []
            for page in cached.get(doc_id, []):
                if page.get('error'):
                    failed.append({'document_id': doc_id, 'page': page['page'], 'reason': page['error']})
                    continue
                pages_scanned[doc_id].append(page['page'])
                lines = page.get('lines', [])
                nearby = any(m.document_id == doc_id and abs(m.pdf_page-page['page']) <= 1 for m in members)
                for index, line in enumerate(lines):
                    text = re.sub(r'\s+', '', line['text'])
                    hits = sum(w in text for w in words)
                    if not hits or not (nearby or any(w in text for w in topic_words) or any(q in text for q in queries)):
                        continue
                    context = '\n'.join(r['text'] for r in lines[max(0,index-2):index+3]
                                        if r.get('side') == line.get('side'))
                    identity = f'{doc_id}-{page["page"]}-SUP-{index}'
                    if identity in sources or any(o.document_id == doc_id and o.pdf_page == page['page']
                                                 and context in o.context for o in run.occurrences):
                        continue
                    ranked.append(((any(q in text for q in queries), nearby, hits), DisclosureOccurrence(
                        occurrence_id=identity, document_id=doc_id, pdf_page=page['page'],
                        bbox=line.get('bbox', []), page_width=page.get('width', 0), page_height=page.get('height', 0),
                        label=line['text'][:180], row_header=line['text'], context=context,
                        quality='text_only', quality_reason='按具体关系补查的原文；未绑定数值字段', topic=check.topic)))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        added = []
        for _, occurrence in ranked[:per_check]:
            if occurrence.occurrence_id not in sources:
                run.occurrences.append(occurrence)
                sources[occurrence.occurrence_id] = occurrence
                added.append(occurrence.occurrence_id)
        tasks.append({'check_id': check.check_id, 'round': round_number, 'queries': words,
                      'model_queries': queries, 'source': 'parsed_report_pages', 'scanned_pages': pages_scanned,
                      'failed_pages': failed, 'new_evidence_ids': added,
                      'note': '仅搜索登记版本已解析文字；未命中不等于企业未披露'})
    return tasks


def search_context(occurrences: list[DisclosureOccurrence], keywords: list[str], limit: int = 40) -> list[DisclosureOccurrence]:
    """只在本次原件候选内补查定义和反证，保留真实命中上限。"""
    scored = [(sum(word in row.context for word in keywords), row) for row in occurrences]
    return [row for score, row in sorted(scored, key=lambda item: item[0], reverse=True) if score][:limit]
