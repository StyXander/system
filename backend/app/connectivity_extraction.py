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
from .connectivity_metrics import content_classification, currency_in_text, metric_identity
from .connectivity_schemas import DisclosureOccurrence, ExtractionExclusion, ReportDocument, SearchCoverage
from .source_viewer import PDF_ACCESS_LOCK
from .secure_download import download_bounded, SecureDownloadError

EXTRACTION_VERSION = "coordinates_v1.14"
# 本轮补充合并/母公司表头，旧布局缓存缺这些单元格，须按新版重建。
# v1.9：槽位下限改为“数值不少于年度列”，旧缓存 year 需重建。
PARSER_CACHE_VERSION = "coordinates_v1.9"
NUMBER = re.compile(r"(?<![\d.])(?:[（(]?-?\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?[)）]?|[（(]?-?\d+(?:\.\d+)?[)）]?)(?![\d.])")
# 长单位排在短单位前，保留二氧化碳当量、粗钢与产品的不同口径。
UNIT_ATOM = r"(?:万吨二氧化碳当量|吨二氧化碳当量|万吨标准煤|吨标准煤|万吨粗钢|吨粗钢|万吨产品|吨产品|万千瓦时|千瓦时|兆瓦时|吉焦|太焦|万吨|吨|百万立方米|千立方米|万立方米|亿立方米|立方米|百万元|千元|万元|亿元|(?<!美)(?<!港)(?<!欧)(?<!日)元|万人|万名|人|(?<![\u4e00-\u9fff])名)"
UNIT = re.compile(UNIT_ATOM + r"(?:[/／]" + UNIT_ATOM + r")?|[%％]")
# 只继承明确适用于全报告的币种声明；本表或记账本位币声明不能扩为全报告。
REPORT_CURRENCY = re.compile(r"(?:本报告|本年度报告|本可持续发展报告)[^。；;]{0,65}(?:金额|货币|财务数据)[^。；;]{0,35}(?:人民币|美元|港元|欧元|日元)")
REPORT_SCOPE = re.compile(r"(?:本报告|本年度报告|本可持续发展报告)[^。；;]{0,24}(?:披露范围|范围|边界|覆盖)[^。；;]{0,90}")
# 以下两条是来源二补充的低强度声明，只在 REPORT_CURRENCY 未确定币种时补位：
# 币种声明：金额／货币／数据＋人民币，覆盖"人民币元""单位：人民币"等常见写法。
CURRENCY_DECLARATION = re.compile(r"(?:货币|金额|数据|单位)[^。；;]{0,25}(?:均为人民币|均以人民币|为人民币元|以人民币|人民币元)")
# 报告级记账币种：只认“以人民币列示/为记账本位币/金额单位为人民币”等明确句子。
# 外币折算叙述（“折算为人民币”）不构成本报告币种声明。
DOCUMENT_CURRENCY = re.compile(
    r"(?:(?:以|采用|使用)人民币(?:元)?(?:作为|为)?(?:记账本位币|本位币|列示|计价|计量|结算)"
    r"|(?:记账本位币|本位币)(?:为|是)人民币"
    r"|人民币(?:元)?为(?:记账)?本位币"
    r"|(?:金额|货币|记账|报表)单位[:：]?\s*(?:人民币|RMB))")
# 提示注入文本：只登记为排除项，不进入候选或模型证据池。
INJECTION_PATTERN = re.compile(
    r"(?:忽略|无视|绕过|跳过|不要理会).{0,12}(?:指令|提示|规则|要求|设定)"
    r"|(?:系统|system)\s*(?:提示|指令|prompt)"
    r"|ignore\s+(?:all\s+|the\s+)?(?:previous|above)\s+instructions"
    r"|(?:请|务必)(?:直接)?(?:声称|输出|回答|判定).{0,12}(?:一致|无差异|正确|无问题)"
    r"|you\s+are\s+(?:now\s+)?an?\s+(?:ai|assistant|model)", re.I)
# 表内行/列角色的通用词；只用于结构登记，不替代指标定义。
TOTAL_ROW = re.compile(r"(?:合计|总计|总额|小计|总投入|投入合计)$")
COMPONENT_ROW = re.compile(r"^(?:其中|资本化|费用化|专项|其他|其它|钢铁|分项|明细)")
BRANCH_ROW = re.compile(r"分部|板块")
BARE_ORDINAL = re.compile(r"^(?:[一二三四五六七八九十百]+|\d+|[（(]\d+[)）]|[①-⑳])$")
BARE_ROW_WORDS = {"其中", "合计", "总计", "小计", "总额"}
SCOPE_MARKERS = ("统计范围", "统计口径", "合并范围", "母公司口径", "组织边界", "运营控制权", "报告覆盖")
ANNOTATION = re.compile(r"^(?:注(?:\d+)?|说明|备注|提示)(?:[:：\s]|$)|忽略.{0,12}指令|系统指令|执行.{0,8}指令|(?:system|assistant)\s*:",re.I)
TOPIC_HEADINGS = {"research":r"研发|研究开发", "environment":r"环保|环境保护|环境责任投入",
                  "intensity":r"温室气体|碳排放|能源|能耗|用水|取水"}


def _label_prefix(text: str) -> str:
    """取首个真正数值之前的文字；括号内的类别/范围编号不是指标名的结尾。"""
    for match in NUMBER.finditer(text):
        before = text[:match.start()]
        if before.count("（") > before.count("）") or before.count("(") > before.count(")"):
            continue
        if re.search(r"(?:类别|范围|scope|第)\s*$", before, re.I):
            continue
        prefix = before.strip(" ：:，,。")
        if prefix and not re.fullmatch(r"(?:(?:19|20)\d{2}\s*年?|本期|本年|上期|上年|[\s：:，,。])*", prefix):
            return prefix
    return re.split(NUMBER, text)[0].strip(" ：:，,。") or text[:70]


def _compound_labels(text: str, matches: list) -> list[tuple[str,str,str]]:
    """仅拆同一实绩单元格里明确成对的名称/单位与数值，缺项或普通除法不猜。"""
    if len(matches) != 2 or not re.fullmatch(r"\s*[/／]\s*", text[matches[0].end():matches[1].start()]):
        return []
    prefix = text[:matches[0].start()].strip(" ：:|/／")
    found = re.fullmatch(r"([^（）()]+)[（(]([^（）()]+)[）)]\s*[/／]\s*([^（）()]+)[（(]([^（）()]+)[）)]",prefix)
    if not found:
        return []
    left,unit_left,right,unit_right = [part.strip() for part in found.groups()]
    if not UNIT.fullmatch(unit_left) or not UNIT.fullmatch(unit_right):
        return []
    if right in {"比例","占比","比重"}:
        right = re.sub(r"(?:数量|人数|金额)$", "", left) + right
    quoted = re.findall(r"[^/／]+",prefix)
    return [(left,unit_left,quoted[0].strip()),(right,unit_right,quoted[1].strip())]


def _display_precision(value: str | None) -> int | None:
    """显示精度只记录原文小数位；整数不凭空扩展为半个单位区间。"""
    text = str(value or "").strip().strip("()（）").replace(",", "").replace("，", "")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return None
    return len(text.split(".", 1)[1]) if "." in text else 0


def _rounding_method(text: str) -> str:
    """舍入方法必须有原文声明；看不到声明时保持 unknown，不从位数推定。"""
    compact = re.sub(r"\s+", "", str(text or ""))
    if re.search(r"四舍五入|按四舍五入", compact):
        return "half_up"
    if re.search(r"截断|舍去|向下取整", compact):
        return "truncate"
    if re.search(r"精确值|未舍入|未进行舍入", compact):
        return "exact"
    return "unknown"


def _boundary_from_text(text: str) -> str:
    """从表标题/章节识别报告边界；同时出现合并与母公司时保持未知，不猜。"""
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return "unknown"
    parent = "母公司" in compact
    consolidated = bool(re.search(r"合并(?:财务报表|报表|范围|口径|数据|利润表|资产负债表|现金流量表)", compact)) or "合并" in compact
    if parent and consolidated:
        return "unknown"
    if parent:
        return "parent"
    if consolidated:
        return "consolidated"
    if BRANCH_ROW.search(compact):
        return "segment"
    return "unknown"


def _core_label(label: str) -> str:
    text = re.sub(r"[\s：:（）()%％]", "", str(label or ""))
    return re.sub(r"(合计|总计|小计|总额|其中|费用化|资本化|专项|其他|其它)$", "", text)


def _metric_scope_from_heading(heading: str, label: str) -> str:
    """只有表标题同时出现指标名和统计边界词时，才作为指标级范围线索。"""
    compact = re.sub(r"\s+", "", str(heading or ""))
    if not compact or not any(marker in compact for marker in SCOPE_MARKERS):
        return ""
    core = _core_label(label)
    identity = metric_identity(label)
    aliases = [name for name in (core, identity.get("canonical", "")) if len(name) >= 3]
    if len(core) >= 4:
        aliases.append(core[:4])
    if aliases and not any(alias in compact for alias in aliases):
        return ""
    if not aliases:
        return ""
    return compact[:200]


def _table_heading(lines: list[dict], table: dict) -> str:
    """取表格上方最近的短行，作为表标题、单位、主体层级的原文来源。"""
    near = []
    for row in lines:
        gap = table["bbox"][1] - row["bbox"][3]
        text = row["text"].strip()
        if 0 <= gap <= 60 and text and len(text) <= 100:
            near.append((row["bbox"][3], text))
    near.sort()
    return " / ".join(text for _, text in near[-3:])


def _heading_above(lines: list[dict], index: int, line: dict) -> str:
    """坐标行上方紧邻的短句；只作继承线索，不跨页或跨栏拼接。"""
    near = []
    for row in lines[max(0, index - 14):index]:
        gap = line["bbox"][1] - row["bbox"][3]
        text = row["text"].strip()
        if row.get("side") == line.get("side") and 0 <= gap <= 120 and text and len(text) <= 100:
            near.append(text)
    return " / ".join(near[-3:])


def _row_role(label: str) -> str:
    compact = re.sub(r"[\s：:（）()]", "", str(label or ""))
    if TOTAL_ROW.search(compact) or compact in BARE_ROW_WORDS - {"其中"}:
        return "total"
    if COMPONENT_ROW.search(compact) or "其中" in compact or re.search(r"资本化|费用化|分项|明细", compact):
        return "component"
    if len(compact) >= 2:
        return "detail"
    return "unknown"


def _column_role(headers: list[str], column_header: str) -> str:
    text = re.sub(r"\s+", "", "".join(headers) + str(column_header or ""))
    if re.search(r"合计|总计|总额|小计", text):
        return "total"
    if re.search(r"钢铁|其他|其它|范围一|范围二|费用化|资本化|分项|明细", text):
        return "component"
    if re.search(r"20\d{2}|本期|本年", text):
        return "period"
    if re.search(r"单位|币种", text):
        return "unit"
    return "unknown"


def _label_from_row(values: list) -> tuple[str, int | None]:
    """跳过行次与金额列，优先取真正表达指标身份的文字单元格。"""
    candidates: list[tuple[int, str]] = []
    for index, value in enumerate(values):
        text = str(value or "").strip()
        if not text:
            continue
        compact = text.replace(" ", "")
        if re.fullmatch(r"[（(]?-?\d[\d,，]*(?:\.\d+)?[)）]?", compact):
            continue
        if BARE_ORDINAL.fullmatch(compact):
            continue
        candidates.append((index, text))
    for index, text in candidates:
        business = re.sub(r"[^\u4e00-\u9fffA-Za-z]", "", text)
        if len(business) >= 2 and not UNIT.fullmatch(text.replace(" ", "")):
            return text, index
    return (candidates[0][1], candidates[0][0]) if candidates else ("", None)


def _nearest_parent_label(data: list, row_index: int) -> str:
    """向上寻找最近的实体指标行名，供“其中/合计”等依赖父级的行恢复身份。"""
    for previous in reversed(data[:row_index]):
        label, _ = _label_from_row(previous)
        compact = re.sub(r"[\s：:（）()]", "", label)
        if label and not BARE_ORDINAL.fullmatch(compact) and compact not in BARE_ROW_WORDS and len(compact) >= 2:
            return label
    return ""


def _resolve_row_identity(data: list, row_index: int, values: list) -> tuple[str, str, bool]:
    """恢复依赖父级的行名；无法还原则标记为不可候选，而不是一律删除合计。"""
    label, _ = _label_from_row(values)
    if not label:
        return "", "", False
    compact = re.sub(r"[\s：:（）()]", "", label)
    if BARE_ORDINAL.fullmatch(compact):
        # 独立序号没有业务含义，不能靠父级猜成“某指标”；直接拒绝自动配对。
        return label, _nearest_parent_label(data, row_index), False
    if compact in BARE_ROW_WORDS:
        parent = _nearest_parent_label(data, row_index)
        if not parent:
            return label, "", False
        return f"{parent}·{label}", parent, True
    return label, "", True


def _unit_from_text(text: str) -> str:
    """从表标题/单位说明取确定倍率的单位；人民币不是计量尺度。"""
    if not text:
        return ""
    match = re.search(r"(?:单位|单\s*位)\s*[:：]?\s*(?:人民币)?\s*(" + UNIT.pattern + r")", text)
    if match:
        return _normalize_unit(match.group(1))
    compact = re.sub(r"\s+", "", text)
    if re.search(r"人民币(?:元|万元|亿元)$", compact):
        return re.search(r"(万元|亿元|元)$", compact).group(1)
    return ""



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


def _normalize_unit(unit: str) -> str:
    """人数的名/万名归一为人/万人，原文仍保留在单位引文中。"""
    return unit.replace("／", "/").replace("％", "%").replace("万名", "万人").replace("名", "人")


def _value_qualifier(text: str, match) -> str:
    """限定语只取当前数字紧邻前缀，不借用同句其他金额或人数的修饰词。"""
    if match is None:
        return "unspecified"
    prefix = text[:match.start()]
    for qualifier, pattern in (
        ("upper_bound", r"不超过|不高于|不大于|至多|最多|不足|不到|(?<!不)少于|(?<!不)低于|(?<!不)小于"),
        ("lower_bound", r"超过|至少|不少于|不低于|大于|高于|逾"),
        ("approximate", r"大约|约为|约|接近|近"),
        ("exact", r"精确为|恰为|(?<!不)等于"),
    ):
        if re.search(r"(?:" + pattern + r")\s*$", prefix):
            return qualifier
    return "unspecified"


def _number_unit(lines: list[dict], index: int, match) -> tuple[str, str, str]:
    """优先数字后缀单位；仅同栏紧接的下一行开头名可补全跨行万名。"""
    if match is None:
        return "", "", ""
    line = lines[index]
    suffix = line["text"][match.end():]
    immediate = re.match(r"\s*(" + UNIT.pattern + r")", suffix)
    if immediate:
        return _normalize_unit(immediate.group(1)), line["text"][match.start():match.end()+immediate.end()], "同行紧跟单位"
    if not re.fullmatch(r"\s*万\s*", suffix) or index + 1 >= len(lines):
        return "", "", ""
    following = lines[index + 1]
    left, right = line.get("bbox") or [], following.get("bbox") or []
    same_column = line.get("side") is not None and following.get("side") == line["side"]
    if not same_column or len(left) != 4 or len(right) != 4:
        return "", "", ""
    gap = right[1] - left[3]
    if not (0 <= gap <= max(24, 2*(left[3]-left[1]))) or min(left[2],right[2]) <= max(left[0],right[0]):
        return "", "", ""
    next_unit = re.match(r"\s*名(?=[，,。；;\s]|$)", following["text"])
    if not next_unit:
        return "", "", ""
    quote = line["text"][match.start():] + "\n" + following["text"][:next_unit.end()]
    return "万人", quote, "同栏紧接换行单位"


def _unit(text: str) -> str:
    match = re.search(r"(?:单位|单\s*位)\s*[:：]?\s*(人民币)?\s*(" + UNIT.pattern + r")", text)
    if match:
        return _normalize_unit(match.group(2))
    # 人民币中的“人”不是人数单位，金额未注明尺度时仍然保留未知。
    found = UNIT.findall(text.replace("人民币", ""))
    return _normalize_unit(found[-1]) if found else ""


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
                    if bounds and (re.fullmatch(r"\s*(?:20\d{2}\s*年?(?:度|末)?|本期(?:金额|发生额)?|本年(?:金额|发生额)?|合计|钢铁\d*|其他|合并|母公司|单位|币种[:：]?人民币)\s*", value)):
                        entry = {"text": value, "bbox": list(bounds), "table_bbox": list(table.bbox)}
                        headers.append(entry)
                        table_headers.append(entry)
    except (RuntimeError, ValueError):
        # 表格检测不足不冒充成功，坐标原文仍可作为不确定候选读取。
        return {"headers": [], "tables": []}
    return {"headers": headers, "tables": tables}


def _extract_tables(page: dict, document: ReportDocument, topics: list[str]) -> list[DisclosureOccurrence]:
    """优先按表格单元格取数，并继承表标题的主体边界、单位、币种与分组。

    表标题只证明“表所属层级”；指标统计范围仍须本指标原文说明，二者不混用。
    """
    result = []
    lines = page["lines"]
    for table_index, table in enumerate(page.get("tables", [])):
        headers = list(table.get("headers", []))
        # “公司”只在同表明确与“合并”并列时表示单体，不从一般公司名称推断。
        parallel_company = any(h["text"].strip()=="合并" for h in headers) and any(
            str(value or "").strip()=="公司" for values in table["data"][:4] for value in values)
        if parallel_company:
            for row_index,values in enumerate(table["data"][:4]):
                for column_index,value in enumerate(values):
                    if str(value or "").strip()=="公司" and table["cells"][row_index][column_index]:
                        headers.append({"text":"公司","bbox":table["cells"][row_index][column_index],"table_bbox":table["bbox"]})
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
        boundary = _boundary_from_text(heading)
        table_currency = currency_in_text(heading) if not REPORT_CURRENCY.search(re.sub(r"\s+", "", heading)) else ""
        table_unit = _unit_from_text(heading)
        table_id = f"{document.document_id}-{page['page']}-T{table_index}"
        table_text = "\n".join(" | ".join(str(v or "") for v in row) for row in data)
        table_topics = [topic for topic in topics if any(word in table_text.replace(" ", "") for word in TOPICS[topic]["keywords"])]
        for row_index, values in enumerate(data):
            if not values or not any(values):
                continue
            label, parent_label, label_valid = _resolve_row_identity(data, row_index, values)
            if not label:
                continue
            compact_label = re.sub(r"\s+", "", label)
            matched = [topic for topic in topics if any(word in compact_label for word in TOPICS[topic]["keywords"])]
            if not matched and len(table_topics) == 1 and re.match(r"合计|总计|其中|资本化|费用化", compact_label):
                matched = table_topics
            if not matched:
                continue
            cells = table["cells"][row_index]
            units = [str(v).replace("\n", "").replace(" ", "").replace("／", "/").replace("％", "%")
                     for v in values if v and UNIT.fullmatch(str(v).replace("\n", "").replace(" ", ""))]
            above = [r["text"] for r in lines if r["bbox"][3] <= table["bbox"][1]+3 and "单位" in r["text"]]
            label_unit = re.search(r"[（(]\s*(" + UNIT.pattern + r")\s*[)）]", label)
            unit = units[0] if units else _unit(label) if "单位" in label else label_unit.group(1) if label_unit else table_unit or _unit(above[-1]) if above else table_unit
            unit = _normalize_unit(unit)
            unit_status = "table" if units or table_unit or (above and unit) else "explicit" if (label_unit or "单位" in label) else "unknown"
            unit_quote = " / ".join(units) if units else label if (label_unit or "单位" in label) else table_unit or (above[-1] if above else "")
            row_role = _row_role(label)
            identity = metric_identity(label)
            content_class, content_reason = content_classification(label, heading)
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
                table_scope = ""
                selected = []
                if years:
                    top = max(years, key=lambda h:h["bbox"][3])
                    match = re.search(r"20\d{2}", top["text"])
                    # 年度列解析失败时保持空值；不得用报告期间顶替指标年度。
                    year = match.group() if match and len(set(re.findall(r"20\d{2}",top["text"]))) == 1 else ""
                    if not year:
                        # 合并表头（如“2025 年 2024 年”）跨多列时，用单元格列中心与
                        # 年度文本 span 的坐标匹配定位本列年度；对不上就留空，不按序号猜。
                        coord_year, _coord_quote = _coordinate_year(
                            lines, {"side": _side_at(lines, bounds), "bbox": bounds}, bounds)
                        if coord_year:
                            year = coord_year
                    # 合并/母公司可能位于年度行上方，同列边界不能因层级较高而丢弃。
                    selected = [h["text"] for h in applicable if h["bbox"][1] >= top["bbox"][1] or re.fullmatch(r"合并|母公司|公司",h["text"])]
                    column_header = " / ".join(selected)
                    if year:
                        # 列头里的年度文本改写为明确绑定年度，保持原有层级顺序：
                        # 否则“列头含多个年度”的通道会在判定层把已由坐标归属的列整条误杀。
                        parts, seen_year = [], False
                        for text in selected:
                            if re.search(r"20\d{2}", text):
                                if not seen_year:
                                    parts.append(f"{year}年")
                                    seen_year = True
                            else:
                                parts.append(text)
                        if not seen_year:
                            parts.append(f"{year}年")
                        column_header = " / ".join(parts)
                    table_scope = " / ".join(text for text in selected
                        if re.fullmatch(r"钢铁\d*|其他|其它|合计|总计|范围一|范围二|费用化|资本化|分项|合并|母公司|公司", text))
                local_boundary_text = label + " / " + column_header
                has_local_boundary = bool(re.search(r"合并|母公司|分部", local_boundary_text))
                member_boundary = _boundary_from_text(local_boundary_text) if has_local_boundary else boundary
                if parallel_company and "公司" in selected:
                    member_boundary, has_local_boundary = "parent",True
                boundary_quote = column_header if re.search(r"合并|母公司|分部", column_header) or (parallel_company and "公司" in selected) else label if has_local_boundary else heading
                metric_scope = _metric_scope_from_heading(heading, label)
                if table_scope:
                    scope_value, scope_level, scope_quote = table_scope, "table", column_header or table_scope
                elif metric_scope:
                    scope_value, scope_level, scope_quote = metric_scope, "metric", metric_scope
                elif member_boundary != "unknown":
                    # 报告边界单独登记；它不是指标统计范围，但可作为报告层覆盖线索。
                    scope_value = {"consolidated": "合并", "parent": "母公司", "segment": "分部"}.get(member_boundary, "")
                    scope_level, scope_quote = "table" if has_local_boundary else "report", boundary_quote
                else:
                    scope_value, scope_level, scope_quote = "", "unknown", ""
                row_text = " | ".join(str(v or "").replace("\n", " ") for v in values)
                context_rows = data[max(0,row_index-2):row_index+3]
                context = "\n".join(" | ".join(str(v or "").replace("\n", " ") for v in row) for row in context_rows)
                prefix = []
                if heading:
                    prefix.append(f"表标题/上方文字：{heading}")
                if member_boundary != "unknown":
                    prefix.append(f"报告边界：{member_boundary}")
                if table_currency:
                    prefix.append(f"币种：{table_currency}")
                if table_unit:
                    prefix.append(f"单位：{table_unit}")
                if metric_scope:
                    prefix.append(f"指标统计范围：{metric_scope}")
                context = "\n".join(prefix + [f"本页对应列头：{column_header}", context])
                if above:
                    context = above[-1] + "\n" + context
                quality, reason = _quality(year, unit, column_header)
                if content_class in {"macro", "industry"}:
                    quality, reason = "uncertain", content_reason or "宏观/行业背景，不作为公司自身指标候选"
                elif not label_valid:
                    quality, reason = "uncertain", "行名仅为序号或通用词，无法表达指标身份，已拒绝自动配对"
                # 邻行可能是另一币种；只绑定本行或本列明示，不扫描整段上下文取首个。
                local_currency = currency_in_text(row_text + " / " + column_header)
                currency = table_currency or local_currency
                if table_currency:
                    currency_status = "table"
                elif local_currency:
                    currency_status = "explicit"
                else:
                    currency_status = "unknown"
                currency_quote = heading if table_currency else ""
                if not currency_quote and local_currency:
                    needle = next((word for word in ("人民币", "美元", "港元", "欧元", "日元") if word in row_text + column_header), "")
                    if needle:
                        at = context.find(needle)
                        currency_quote = context[max(0, at-20):at+len(needle)+25].strip()
                occurrence_id = f"{document.document_id}-{page['page']}-T{table_index}-R{row_index}-C{column_index}"
                rounding_method = _rounding_method(context)
                result.append(DisclosureOccurrence(occurrence_id=occurrence_id,
                    document_id=document.document_id, pdf_page=page["page"], bbox=list(bounds), label=label[:160],
                    value=token, unit=unit, unit_source="本表单位列" if units else _unit_source(label, above),
                    unit_status=unit_status, unit_source_quote=unit_quote[:300],
                    currency=currency, currency_status=currency_status,
                    currency_source_id=occurrence_id if currency else "", currency_source_quote=currency_quote[:300],
                    year=year, year_status="attributed" if year else "unattributed",
                    report_boundary=member_boundary,
                    report_boundary_source_id=occurrence_id if member_boundary != "unknown" else "",
                    report_boundary_source_quote=boundary_quote[:300] if member_boundary != "unknown" else "",
                    scope=scope_value[:200], table_scope=table_scope[:120], scope_level=scope_level,
                    scope_source_id=occurrence_id if scope_value else "", scope_source_quote=scope_quote[:300],
                    display_precision=_display_precision(token), rounding_method=rounding_method,
                    rounding=rounding_method if rounding_method in {"exact", "half_up"} else "unknown",
                    content_class=content_class, metric_id=identity.get("metric_id", ""), metric_identity=identity,
                    table_id=table_id, row_index=row_index, column_index=column_index,
                    row_role=row_role, column_role=_column_role(selected, column_header), row_parent_label=parent_label,
                    row_header=(label + " | " + row_text) if label not in row_text else row_text,
                    column_header=column_header, header_path=selected,
                    full_table_header=" / ".join(h["text"] for h in headers),
                    year_binding="cell_header" if year else "unattributed",
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


def _side_at(lines: list[dict], bounds: list[float]) -> int:
    """表格单元格不带栏位标记，按垂直距离取最近文本行的栏位。

    年报常见双栏排版；用表格单元格自己的 y 坐标推断所在栏，比固定取 0 栏稳。
    """
    if not lines or not bounds:
        return 0
    nearest = min(lines, key=lambda row: abs(row["bbox"][1] - bounds[1]))
    return int(nearest.get("side", 0))


def _coordinate_year(lines: list[dict], line: dict, number_box: list[float]) -> tuple[str,str]:
    """按最近的纯年度表头列中心绑定；跳过空列符号时不靠数值序号猜年度。"""
    headers = [row for row in lines if row["side"] == line["side"]
        and 0 < line["bbox"][1]-row["bbox"][1] <= 120
        and re.fullmatch(r"(?:(?:项目|指标|名称)\s+)?(?:20\d{2}\s*年?(?:度|末)?\s*){2,}",row["text"])]
    if not headers:
        return "",""
    header = max(headers,key=lambda row:row["bbox"][1])
    positions = [(match.group(1),_number_box(header,match)) for match in re.finditer(r"(20\d{2})\s*年?(?:度|末)?",header["text"])]
    x = (number_box[0]+number_box[2])/2
    centers = sorted((bounds[0]+bounds[2])/2 for _,bounds in positions)
    if len(centers) < 2 or not header.get("spans"):
        return "", ""
    spacing = min(right-left for left,right in zip(centers,centers[1:]))
    # 首尾列仅延展半个列距；中点不能归属任一列，避免把邻表或错位值拉进来。
    distances = sorted((abs((bounds[0]+bounds[2])/2-x),year) for year,bounds in positions)
    if spacing <= 0 or distances[0][0] >= spacing/2 or abs(distances[0][0]-distances[1][0]) < .5:
        return "", ""
    year = distances[0][1]
    selected = re.search(re.escape(year)+r"\s*年?(?:度|末)?",header["text"]).group().strip()
    return year,selected


def _coordinate_boundary(lines: list[dict], line: dict, number_box: list[float]) -> tuple[str,str,bool]:
    """合并与公司并列表头按真实列位置定主体；单独“公司”不推断母公司。"""
    headers = [row for row in lines if row["side"] == line["side"]
        and 0 < line["bbox"][1]-row["bbox"][1] <= 120
        and re.fullmatch(r"(?:合并|母公司|公司)(?:\s+(?:合并|母公司|公司))+",row["text"])
        and "合并" in row["text"] and re.search(r"母公司|公司",row["text"])]
    if not headers:
        return "unknown", "", False
    header=max(headers,key=lambda row:row["bbox"][1])
    spans=[(bounds,text.strip()) for bounds,text in header.get("spans",[])
           if re.fullmatch(r"合并|母公司|公司",text.strip())]
    if len(spans) < 2:
        return "unknown",header["text"],True
    centers=sorted((bounds[0]+bounds[2])/2 for bounds,_ in spans)
    spacing=min(right-left for left,right in zip(centers,centers[1:]))
    x=(number_box[0]+number_box[2])/2
    nearest=sorted((abs((bounds[0]+bounds[2])/2-x),text) for bounds,text in spans)
    if spacing <= 0 or nearest[0][0] >= spacing/2 or abs(nearest[0][0]-nearest[1][0]) < .5:
        return "unknown",header["text"],True
    return "consolidated" if nearest[0][1]=="合并" else "parent",header["text"],True


def _table_context_topic(lines: list[dict], index: int, topics: list[str]) -> tuple[str,str,bool]:
    """只召回明确主题小表内陌生名称，不建立同义关系，也不跨栏或跨新标题。"""
    line=lines[index]
    text=line["text"]
    if ANNOTATION.search(text) or not NUMBER.search(text):
        return "", "", False
    prefix=re.split(NUMBER,text)[0].strip()
    if not 2 <= len(prefix) <= 50 or content_classification(prefix)[0] != "company":
        return "", "", False
    before=[row for row in lines[:index] if row["side"]==line["side"]
            and 0 < line["bbox"][1]-row["bbox"][1] <= 120]
    headers=[row for row in before if re.fullmatch(
        r"(?:(?:项目|指标|名称)\s+)?(?:(?:20\d{2}\s*年?(?:度|末)?|本期|上期|本年|上年)\s*){2,}",row["text"])]
    if not headers:
        return "", "", False
    header=max(headers,key=lambda row:row["bbox"][1])
    # 新的小节会终止表内继承；不把主题延伸到整份报告。
    if any(header["bbox"][1] < row["bbox"][1] < line["bbox"][1] and not NUMBER.search(row["text"])
           and not ANNOTATION.search(row["text"]) and not re.search(r"单位|币种",row["text"])
           for row in before):
        return "", "", False
    headings=[row for row in lines[:index] if row["side"]==line["side"]
              and 0 < header["bbox"][1]-row["bbox"][1] <= 120 and len(row["text"]) <= 48
              and not NUMBER.search(row["text"]) and not re.search(r"单位|币种",row["text"])]
    if not headings:
        return "", "", False
    heading=max(headings,key=lambda row:row["bbox"][1])["text"]
    matched=[topic for topic in topics if re.search(TOPIC_HEADINGS[topic],heading)]
    if len(matched) != 1 or content_classification(prefix,heading)[0] != "company":
        return "", "", False
    return matched[0],heading,bool(re.search(r"20\d{2}",header["text"]))


def _apply_report_declarations(pages: list[dict], occurrences: list[DisclosureOccurrence], document: ReportDocument) -> None:
    """登记真实报告声明位置，再按层级继承；报告范围永远只是有限比较线索。"""
    declarations = []
    for page in pages:
        for index, line in enumerate(page.get("lines", [])):
            text = line["text"]
            compact = re.sub(r"\s+", "", text)
            currency_match = REPORT_CURRENCY.search(compact)
            scope_match = REPORT_SCOPE.search(compact)
            currency = currency_in_text(compact) if currency_match else ""
            boundary = _boundary_from_text(scope_match.group()) if scope_match else "unknown"
            if not currency and boundary == "unknown":
                continue
            identity = f"{document.document_id}-{page['page']}-DECL-{index}"
            source = DisclosureOccurrence(occurrence_id=identity, document_id=document.document_id,
                pdf_page=page["page"], bbox=list(line["bbox"]), label="报告币种与边界声明", row_header=text,
                page_width=page.get("width",0),page_height=page.get("height",0),
                context=text, quality="text_only", topic="basis")
            occurrences.append(source)
            declarations.append((source, currency, boundary))
    currencies = {currency for _,currency,_ in declarations if currency}
    boundaries = {boundary for _,_,boundary in declarations if boundary != "unknown"}
    for row in occurrences:
        if row.value is None:
            continue
        # 局部原文的币种、范围和例外优先；存在多币种、排除条款时不扩张报告声明。
        local = row.row_header + "\n" + row.footnote_scope
        ambiguous_currency = sum(word in local for word in ("人民币", "美元", "港元", "欧元", "日元")) > 1
        if not row.currency and "元" in row.unit and len(currencies) == 1 and not ambiguous_currency:
            if not re.search(r"另以|另行.*币|不适用|美元|港元|欧元|日元",local):
                source, currency, _ = next(item for item in declarations if item[1])
                row.currency, row.currency_status = currency, "report_declaration"
                row.currency_source_id, row.currency_source_quote = source.occurrence_id, source.context
        if row.report_boundary == "unknown" and row.scope_level != "table" and len(boundaries) == 1 and not re.search(r"不包括|不含|仅统计|仅覆盖|另行|母公司|分部",local):
            source, _, boundary = next(item for item in declarations if item[2] != "unknown")
            row.report_boundary = boundary
            row.report_boundary_source_id, row.report_boundary_source_quote = source.occurrence_id, source.context
            if row.scope_level == "unknown":
                row.scope, row.scope_level = {"consolidated":"合并", "parent":"母公司", "segment":"分部"}[boundary], "report"
                row.scope_source_id, row.scope_source_quote = source.occurrence_id, source.context


def _apply_document_currency(pages: list[dict], occurrences: list[DisclosureOccurrence],
                             document: ReportDocument) -> None:
    """表内“单位：人民币”与记账本位币声明；只在报告级声明未确定币种时补位。

    A 股年报常在财务报表附注写“以人民币为记账本位币/以人民币列示”，该句不含
    指标数值，不会进入候选行，须单独按原文句子登记一份声明证据。证据强度仍为
    report_declaration，不得冒充表内明示，也不从单个“元”字推定人民币。
    """
    declarations = [row for row in occurrences
                    if row.topic == "basis" and CURRENCY_DECLARATION.search(re.sub(r"\s+", "", row.context))]
    if not declarations:
        declared = _document_currency_declaration(pages)
        if declared:
            page_no, quote = declared
            declaration = DisclosureOccurrence(
                occurrence_id=f"{document.document_id}-{page_no}-CCY-DECL",
                document_id=document.document_id, pdf_page=page_no,
                label="报告币种声明", row_header=quote[:200], context=quote,
                quality="text_only", quality_reason="报告级币种声明；本身不是指标数值",
                topic="currency_declaration")
            occurrences.append(declaration)
            declarations.append(declaration)
    if not declarations:
        return
    declaration = declarations[0]
    compact_declaration = re.sub(r"\s+", "", declaration.context)
    # 声明句本身出现多种币种时，任一币种都不是报告默认，保持未知。
    if re.search(r"美元|港元|欧元|日元", compact_declaration):
        return
    # “本公司/母公司/本财务报表”的记账本位币不能扩张到合并 ESG 指标；
    # 记账货币也不等于每个指标的计量与列报币种。
    if re.search(r"本公司|母公司|本财务报表|个别报表", compact_declaration):
        return
    # 只接受“金额/货币/单位…人民币”这类列报口径表述；仅命中记账本位币不足以赋值。
    found = CURRENCY_DECLARATION.search(compact_declaration)
    if not found:
        return
    declared_quote = found.group()
    for row in occurrences:
        # 局部已明示币种、或上下文出现其他币种时不扩张，避免把报告声明当成指标级证据。
        if not row.currency and re.search(r"元", row.unit) and not re.search(r"美元|港元|欧元|日元", row.context):
            row.currency = "CNY"
            row.currency_status = "report_declaration"
            row.currency_source_id = declaration.occurrence_id
            row.currency_source_quote = declared_quote


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
    # 指令性文本单独登记：既不让它进入候选，也不静默消失。
    injection_rows: list[ExtractionExclusion] = []
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
        inherited_topic_counts=defaultdict(int)
        for index, line in enumerate(lines):
            text = line["text"]
            instruction = INJECTION_PATTERN.search(text)
            if instruction:
                injection_rows.append(ExtractionExclusion(
                    occurrence_id=f"{document.document_id}-{page['page']}-INJ-{index}",
                    document_id=document.document_id, pdf_page=page["page"],
                    label=text[:120], value="",
                    reason=f"原文含指令性表述（{instruction.group()[:20]}），已隔离；不作为企业披露证据进入候选或模型输入"))
                continue
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
            topic_source, topic_quote, topic_has_year = "", "", False
            if not matched:
                topic_source,topic_quote,topic_has_year = _table_context_topic(lines,index,topics)
                if topic_source and inherited_topic_counts[topic_source] < 24:
                    matched=[topic_source]
                    inherited_topic_counts[topic_source] += 1
            if not matched:
                continue
            same_side = [r for r in lines[max(0, index - 5):index + 6] if r["side"] == line["side"]]
            context = "\n".join(r["text"] for r in same_side)
            if topic_source:
                context += "\n主题召回来源（不证明指标等价）：" + topic_quote
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
            if basis_only or ANNOTATION.search(text) or (topic_source and not topic_has_year):
                valid = []
            # 无数值的定义段落也进入检索，NAR和五项前提需要原文证据。
            compound_labels = _compound_labels(numeric_line["text"], valid)
            candidates = valid or [None]
            base_context = context
            # 年度列数决定可绑定年度的数值个数；多出的尾部列通常是变动/占比列。
            year_slots = len(year_labels)
            for offset, match in enumerate(candidates):
                # 同一行的多个数值共用本行基础上下文，列头补充不得串到下一个数值。
                context = base_context
                raw = match.group().replace("（", "(").replace("）", ")") if match else None
                explicit_years = re.findall(r"(20\d{2})年", text)
                # 槽位绑定的下限是“数值不少于年度列”，不是“严格相等”：
                # 年报常见“项目 | 2025 | 2024 | 变动比例”结构，多出的尾部列是
                # 计算列而不是第三个年度。要求严格相等会让这类行整体失去年度，
                # 进而被“列头含多个年度”通道误杀。数值少于年度列时不绑定（无法确定对应列）。
                year = (year_labels[offset] if offset < len(year_labels) and len(valid) >= len(year_labels)
                        else explicit_years[0] if len(set(explicit_years)) == 1 else "")
                label = _label_prefix(text)
                column_header = header[-1]["text"] if header else ""
                full_table_header = column_header
                year_binding = "cell_header" if year and header and len(set(year_labels)) == 1 else "unattributed"
                if year and len(set(re.findall(r"20\d{2}", column_header))) > 1:
                    # 槽位已确定本值属于哪一年，列头必须同步改写为明确年度：
                    # 否则判定层会因“列头同时含多个年度”把已归属的值整条拒绝，
                    # 槽位绑定等于白做（这是真实报告候选被误杀的主要来源）。
                    rest = [part for part in re.split(r"\s*/\s*", column_header)
                            if part and not re.search(r"20\d{2}", part)]
                    column_header = " / ".join([*rest, f"{year}年"])
                    year_binding = "cell_header"
                number_box = _number_box(numeric_line, match) if match else line["bbox"]
                # 数值多于年度列时，超出部分的年度保持空值，不按最近的年度词硬绑。
                if match and (year_slots == 0 or offset < year_slots):
                    coordinate_year, coordinate_header = _coordinate_year(lines,line,number_box)
                    if coordinate_year:
                        # 坐标年度优先于合并表头文本：列头记明确绑定年度，
                        # 否则整行会因“列头含多个年度”被判定层误杀。
                        year = coordinate_year
                        column_header = f"{coordinate_year}年"
                        year_binding = "coordinate"
                        selected_header = next((h for h in reversed(lines) if h.get("side") == line.get("side")
                            and h["bbox"][1] < line["bbox"][1] and coordinate_header in h["text"]), None)
                        full_table_header = selected_header["text"] if selected_header else full_table_header
                        context = context + "\n年度列头：" + coordinate_header
                    elif len(set(year_labels)) > 1 and len(valid) != len(year_labels):
                        # 多年度表头且数值个数与年度列不一一对应时无槽位可依，保持待归属；
                        # 一一对应的情况由上面的 year_labels[offset] 槽位绑定处理，不再误杀。
                        year, column_header = "", ""
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
                        full_table_header = " / ".join(h["text"] for h in page.get("headers", []))
                        year_binding = "cell_header" if year else "unattributed"
                        context = context + "\n本页对应列头：" + column_header
                    # 句内明确写出的年度高于邻近表头，不能把表后文字误绑到上一张表。
                    inline_periods = re.findall(r"(20\d{2})\s*年", numeric_line["text"][:match.start()])
                    if inline_periods:
                        year = inline_periods[-1]
                        column_header = "句内明示" + year + "年"
                        year_binding = "inline"
                    # 句内多指标使用各数值前的局部标签，避免费用化和资本化共用名称。
                    prefix = numeric_line["text"][:match.start()]
                    phrase = re.split(r"[，；;。]", prefix)[-1].strip()
                    if re.search(r"[，；;。]", prefix) and phrase and re.search(r"投入|费用|支出|人员|比例|强度", phrase) and len(phrase) < 70:
                        label = re.sub(r"^20\d{2}\s*年[，,\s]*", "", phrase)
                elif match:
                    # 该数值位于年度列之外（变动率、占比等），不得继承任何年度。
                    year = ""
                    column_header = "年度列外"
                compound_part = compound_labels[offset] if offset < len(compound_labels) else None
                if compound_part:
                    label = compound_part[0]
                inline_unit, inline_quote, inline_source = _number_unit(lines, index if numeric_line is line else index+1, match)
                unit = _normalize_unit(compound_part[1]) if compound_part else inline_unit or unit_hint
                value_qualifier = _value_qualifier(numeric_line["text"], match)
                inline_units = UNIT.findall(text)
                if "强度" in text and len(inline_units) == 2 and numeric_line["text"].lstrip().startswith("/"):
                    unit = inline_units[0] + "/" + inline_units[1]
                # 坐标行只从紧邻的短标题继承边界、范围和币种，避免把报告总声明当成指标级证据。
                heading_above = _heading_above(lines, index, line)
                local_boundary = bool(re.search(r"合并|母公司|分部",label))
                boundary = _boundary_from_text(label) if local_boundary else _boundary_from_text(heading_above)
                boundary_quote = label if local_boundary else heading_above
                column_boundary, column_boundary_quote, parallel_boundary = _coordinate_boundary(lines,line,number_box)
                if parallel_boundary:
                    boundary, boundary_quote = column_boundary, column_boundary_quote
                    context += "\n原始主体分组列头：" + column_boundary_quote
                content_class, content_reason = content_classification(label, heading_above)
                identity_info = metric_identity(label)
                if topic_source:
                    identity_info.update(topic_source="table_context",topic_source_quote=topic_quote,
                                         identity_status="unverified_candidate")
                metric_scope = _metric_scope_from_heading(heading_above, label)
                if metric_scope:
                    scope_value, scope_level, scope_quote = metric_scope, "metric", metric_scope
                elif boundary != "unknown":
                    scope_value = {"consolidated": "合并", "parent": "母公司", "segment": "分部"}.get(boundary, "")
                    scope_level, scope_quote = "table" if local_boundary or parallel_boundary else "report", boundary_quote
                else:
                    scope_value, scope_level, scope_quote = "", "table" if parallel_boundary else "unknown", boundary_quote if parallel_boundary else ""
                rounding_method = _rounding_method(context)
                compact_label = re.sub(r"[\s：:（）()]", "", label)
                label_valid = bool(compact_label) and not BARE_ORDINAL.fullmatch(compact_label)
                unit_quote = compound_part[2] if compound_part else inline_quote if inline_unit else (explicit_above[-1] if explicit_above else heading_above)
                unit_status = "explicit" if compound_part or inline_unit else "table" if unit_hint else "unknown"
                heading_currency = currency_in_text(heading_above) if not REPORT_CURRENCY.search(re.sub(r"\s+", "", heading_above)) else ""
                currency_hint = currency_in_text(text) or heading_currency
                currency_status = "explicit" if currency_in_text(text) else "table" if heading_currency else "unknown"
                # 同一单元格已按表格结构提取时，不再提交另一份位置身份重复相加。
                if match:
                    duplicates = [row for row in table_rows if row.value == raw and row.bbox[0]-2 <= (number_box[0]+number_box[2])/2 <= row.bbox[2]+2
                        and row.bbox[1]-2 <= (number_box[1]+number_box[3])/2 <= row.bbox[3]+2]
                    if duplicates:
                        # 同一物理单元格合并两种读取的依据，不能让较差的表格结果吞掉坐标层的单位与年度。
                        for row in duplicates:
                            row.unit = row.unit or unit
                            if inline_unit:
                                row.unit, row.unit_status, row.unit_source_quote = inline_unit, "explicit", inline_quote[:300]
                                row.unit_source = inline_source
                            row.value_qualifier = value_qualifier
                            row.year = row.year or year
                            row.column_header = row.column_header or column_header
                            row.full_table_header = row.full_table_header or full_table_header
                            if row.year_binding == "unattributed" and row.column_header == column_header:
                                row.year_binding = year_binding
                            row.unit_status = row.unit_status if row.unit_status != "unknown" else unit_status
                            row.unit_source_quote = row.unit_source_quote or unit_quote[:300]
                            if currency_hint:
                                row.currency = row.currency or currency_hint
                                row.currency_status = row.currency_status if row.currency_status != "unknown" else currency_status
                                row.currency_source_id = row.currency_source_id or row.occurrence_id
                                row.currency_source_quote = row.currency_source_quote or heading_above[:300]
                            if boundary != "unknown" and row.report_boundary == "unknown":
                                row.report_boundary = boundary
                                row.report_boundary_source_id = row.occurrence_id
                                row.report_boundary_source_quote = heading_above[:300]
                            if metric_scope and row.scope_level == "unknown":
                                row.scope, row.scope_level = metric_scope[:200], "metric"
                                row.scope_source_id = row.occurrence_id
                                row.scope_source_quote = metric_scope[:300]
                            elif boundary != "unknown" and row.scope_level == "unknown":
                                row.scope = {"consolidated": "合并", "parent": "母公司", "segment": "分部"}.get(boundary, "")
                                row.scope_level = "report"
                                row.scope_source_id = row.occurrence_id
                                row.scope_source_quote = heading_above[:300]
                            if content_class in {"macro", "industry"}:
                                row.content_class = content_class
                                row.quality = "uncertain"
                                row.quality_reason = content_reason or "宏观/行业背景，不作为公司自身指标候选"
                            if not label_valid:
                                row.quality = "uncertain"
                                row.quality_reason = "行名仅为序号或通用词，无法表达指标身份，已拒绝自动配对"
                            row.context = (row.context + "\n[同页坐标补充]\n" + context)[:7000]
                            row.year_status = "attributed" if row.year else "unattributed"
                            row.unit_source = row.unit_source or ("同页坐标补充" if unit else "")
                            if row.quality != "uncertain":
                                row.quality, row.quality_reason = _quality(row.year, row.unit, row.column_header)
                        continue
                # 金额原币种只在上下文明示人民币时确认，不由元字推定币种。
                currency = currency_hint
                currency_source_quote = ""
                if currency:
                    needle = next((word for word in ("人民币", "美元", "港元", "欧元", "日元") if word in heading_above + context), "")
                    if needle:
                        at = (heading_above + "\n" + context).find(needle)
                        currency_source_quote = (heading_above + "\n" + context)[max(0, at-20):at+len(needle)+25].strip()
                identity = f"{document.document_id}-{page['page']}-{index}-{offset}"
                # 行列绑定可由列头、表头或句内明示年度提供；三者都没有才算未绑定。
                binding = column_header or (header[-1]["text"] if header else "") or (f"句内明示{year}" if year else "")
                quality, reason = _quality(year, unit, binding, bool(match))
                if match and numeric_line is not line:
                    quality, reason = "uncertain", "数值来自相邻行，指标与数值未同行绑定"
                if match and parallel_boundary and boundary == "unknown":
                    quality, reason = "uncertain", "并列合并与公司列的主体未能按坐标归属"
                if match and content_class in {"macro", "industry"}:
                    quality, reason = "uncertain", content_reason or "宏观/行业背景，不作为公司自身指标候选"
                elif match and not label_valid:
                    quality, reason = "uncertain", "行名仅为序号或通用词，无法表达指标身份，已拒绝自动配对"
                occurrences.append(DisclosureOccurrence(occurrence_id=identity, document_id=document.document_id,
                    pdf_page=page["page"], bbox=number_box, label=label[:160], value=raw, unit=unit,
                    unit_source="同行复合单位映射" if compound_part else inline_source if inline_unit else "本页单位说明" if unit_hint else "",
                    unit_status=unit_status, unit_source_quote=unit_quote[:300] if unit_quote else "",
                    value_qualifier=value_qualifier,
                    currency=currency, currency_status=currency_status,
                    currency_source_id=identity if currency else "", currency_source_quote=currency_source_quote[:300],
                    year=year, year_status="attributed" if year else "unattributed",
                    report_boundary=boundary,
                    report_boundary_source_id=identity if boundary != "unknown" else "",
                    report_boundary_source_quote=boundary_quote[:300] if boundary != "unknown" else "",
                    scope=scope_value[:200], scope_level=scope_level,
                    scope_source_id=identity if scope_value else "", scope_source_quote=scope_quote[:300],
                    display_precision=_display_precision(raw), rounding_method=rounding_method,
                    rounding=rounding_method if rounding_method in {"exact", "half_up"} else "unknown",
                    content_class=content_class, metric_id=identity_info.get("metric_id", ""), metric_identity=identity_info,
                    row_role=_row_role(label),
                    row_header=text, column_header=column_header,
                    full_table_header=full_table_header, year_binding=year_binding,
                    header_path=[column_header] if column_header else [],
                    context=context[:7000], footnotes=[r["text"] for r in same_side if re.match(r"注[:：\d]|\*", r["text"])],
                    footnote_scope=(next((r["text"] for r in same_side if re.match(r"注[:：\d]|\*", r["text"])), "")[:120]),
                    quality=quality, quality_reason=reason, version_role=document.version_role,
                    topic=matched[0]))
        previous = lines
    for row in occurrences:
        page = pages[row.pdf_page-1]
        row.page_width, row.page_height = page.get("width", 0), page.get("height", 0)
    _apply_report_declarations(pages, occurrences, document)
    # 报告级声明未覆盖时，用“以人民币为记账本位币/金额单位：人民币”这类
    # 无指标数值的明确句子补位；强度仍记 report_declaration，不冒充表内明示。
    _apply_document_currency(pages, occurrences, document)
    coverage.discovered_count = len(occurrences)
    return occurrences, coverage, _exclusions(occurrences, injection_rows)


def _document_currency_declaration(pages: list[dict]) -> tuple[int, str] | None:
    """按原文句子找报告级币种声明；找不到就保持未知，不从“元”字猜币种。

    只接受“以人民币列示/为记账本位币/金额单位为人民币”这类明确句子，
    外币折算叙述（如“折算为人民币”）不构成本报告的记账币种声明。
    """
    for page in pages:
        if page.get("error"):
            continue
        for line in page.get("lines", []):
            text = line.get("text", "")
            if DOCUMENT_CURRENCY.search(re.sub(r"\s+", "", text)):
                return int(page["page"]), text[:300]
    return None


def _exclusions(occurrences: list[DisclosureOccurrence],
                extra: list[ExtractionExclusion] | None = None) -> list[ExtractionExclusion]:
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
    if extra:
        seen = {row.occurrence_id for row in rows}
        rows.extend(item for item in extra if item.occurrence_id not in seen)
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
