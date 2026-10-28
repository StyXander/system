"""Focused zero-carbon project dossier built from registered, SHA-verified public PDFs.

This is a deterministic investigation aid, NOT an AI conclusion or assurance opinion.
No model call is triggered by reading this endpoint. All monetary outputs are
derived from a table row in a verified source document; never from case hints.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re
import threading
import time

from .connectivity_extraction import load_registry
from .connectivity_matter_extraction import read_corpus, compact
from .source_viewer import PDF_ACCESS_LOCK

_CACHE: dict = {}
_LOCK = threading.RLock()
RULE_VERSION = "construction_reconciliation_v1"


def load_demo_config(root: Path) -> dict:
    return json.loads((root / "backend/demo_cases/baosteel_zhanjiang.json").read_text(encoding="utf-8"))


def _number(value):
    raw = str(value or "").strip().replace(",", "").replace("，", "").replace(" ", "")
    if not raw or raw in {"—", "-", "–", "－", "不适用", "N/A"}:
        return None
    raw = raw.replace("（", "(").replace("）", ")")
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    if not re.fullmatch(r"-?\d+(?:\.\d{1,4})?", raw):
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def reconcile_construction(values: dict) -> dict:
    """Fail closed: no assumed zero for a dash or missing cash-flow cell."""
    required = ("opening", "increase", "to_fixed", "to_long_term", "other_decrease", "closing")
    parsed = {key: _number(values.get(key)) for key in required}
    if any(parsed[k] is None for k in required):
        return {"status": "insufficient_fields", "rule_version": RULE_VERSION,
                "missing": [k for k in required if parsed[k] is None],
                "note": "原文缺项或破折号未明确口径，不能按零值强制复算。"}
    expected = parsed["opening"] + parsed["increase"] - parsed["to_fixed"] - parsed["to_long_term"] - parsed["other_decrease"]
    difference = expected - parsed["closing"]
    return {"status": "balanced" if abs(difference) <= Decimal("0.01") else "difference",
            "rule_version": RULE_VERSION, "computed_closing": str(expected),
            "reported_closing": str(parsed["closing"]), "difference": str(difference),
            "expression": "期初 + 本期增加 − 转固 − 长期待摊 − 其他减少 = 期末",
            "values": {k: str(v) for k, v in parsed.items()},
            "note": "金额勾稽仅说明这行会计科目变动在表内相符，不证明整个零碳项目身份或转固时点正确。"}


def _header_index(header: str, *terms) -> int | None:
    for i, term in enumerate(terms):
        if term in header:
            return i
    return None


def _table_amount(raw):
    """PyMuPDF table cells can separate digit groups from punctuation."""
    value = _number(raw)
    if value is not None:
        return value
    text = str(raw or "").strip()
    if not text or text in {"-", "—", "–"}:
        return None
    # Example from the actual annual-report table:
    # '1 326 600 000 00\n, , , .' represents 1,326,600,000.00.
    first = text.splitlines()[0].strip()
    if not re.fullmatch(r"\d+(?:\s+\d+)+", first):
        return None
    groups = first.split()
    if len(groups[-1]) != 2 or not all(len(group) == 3 for group in groups[1:-1]):
        return None
    return _number("".join(groups[:-1]) + "." + groups[-1])


def _table_row(pdf, page_idx: int):
    """Read the named zero-carbon subproject row from actual source table cells."""
    page = pdf[page_idx]
    try:
        tables = page.find_tables()
    except (AttributeError, ValueError, RuntimeError):
        return None
    for table in tables.tables:
        try:
            rows = table.extract()
        except (ValueError, RuntimeError):
            continue
        if not rows:
            continue
        for row_index, row in enumerate(rows):
            raw_cells = [str(v or "").strip() for v in row]
            cells = [compact(v) for v in raw_cells]
            if not any("炼钢工程" in cell and "零碳" in cell for cell in cells):
                continue
            pre = rows[max(0, row_index-5):row_index]
            header = [compact("".join(str(r[c] or "") for r in pre)) for c in range(len(cells))]
            aliases = {
                "opening": ("期初余额", "期初数"), "increase": ("本期增加", "本年增加"),
                "to_fixed": ("转入固定资产", "转固"), "to_long_term": ("长期待摊",),
                "closing": ("期末余额", "期末数"),
            }
            mapping = {}
            for key, names in aliases.items():
                candidates = [i for i, h in enumerate(header) if any(name in h for name in names)]
                if len(candidates) == 1:
                    mapping[key] = candidates[0]
            if len(mapping) != len(aliases) or len(set(mapping.values())) != len(mapping):
                continue
            parsed = {k: _table_amount(raw_cells[i]) for k,i in mapping.items()}
            if any(parsed[k] is None for k in ("opening", "increase", "to_fixed")):
                return {"status": "insufficient_fields", "rule_version": RULE_VERSION,
                        "source_page": page_idx+1, "note": "期初、本期增加、转固金额未能按同一行完整解析。"}
            subtotal = parsed["opening"] + parsed["increase"] - parsed["to_fixed"]
            # A displayed dash is not a certified 0. We report the subtotal,
            # withhold formal equality until closing and deduction are explicit.
            if parsed["to_long_term"] is None or parsed["closing"] is None:
                status="subtotal_computed"
                difference=None
                note="已复算本行三项明确披露的金额；长期待摊转出或期末余额采用破折号，未查明其计量含义，不标记完整勾稽通过。"
            else:
                calculated=subtotal-parsed["to_long_term"]
                difference=calculated-parsed["closing"]
                status="balanced" if abs(difference)<=Decimal("0.01") else "difference"
                note="按表中明确数值核算；算术成立不等于转固时点和项目全部投入已确认。"
            page_text=page.get_text("text")
            units=re.findall(r"单位[：:\s]*(元|万元|千元|亿元)",page_text[:650])
            unique_units=set(units)
            if len(unique_units)!=1:
                return {"status":"unit_unverified","rule_version":RULE_VERSION,
                        "source_page":page_idx+1,"note":"核实到炼钢工程表格行，但无法唯一确认表头金额单位。"}
            unit=unique_units.pop()
            multiplier={"元":Decimal(1),"千元":Decimal(1000),"万元":Decimal(10000),"亿元":Decimal(100000000)}[unit]
            result={
                "status":status,"rule_version":RULE_VERSION,"source_page":page_idx+1,
                "source_row_label":raw_cells[0],"source_row_matched":True,
                "subproject_identity":"yearly_report_explicit_project_and_subproject",
                "extraction":"pymupdf_verified_table_cells",
                "unit":unit,
                "formula":"期初余额 + 本期增加 − 本期转固（其他扣减列按真实表头另行核查）",
                "values":{k:(str(v) if v is not None else None) for k,v in parsed.items()},
                "values_yuan":{k:(str(v*multiplier) if v is not None else None) for k,v in parsed.items()},
                "reported_markers":{k:raw_cells[i] for k,i in mapping.items()},
                "known_component_subtotal_yuan":str(subtotal*multiplier),
                "difference_yuan":str(difference*multiplier) if difference is not None else None,
                "note":note,
                "missing":["to_long_term","closing"] if status=="subtotal_computed" else [],
                "other_decrease_column_present":False,
            }
            return result
    return None


def _extract_reconciliation(root: Path, annual_doc, relevant_pages):
    from .connectivity_extraction import ensure_source
    import pymupdf
    # ensure_source verifies the actual bytes against the registered sha256.
    path = ensure_source(root, annual_doc)
    with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
        pages = sorted(p for p in relevant_pages if 1 <= p <= len(pdf))
        for p in pages[:12]:
            row = _table_row(pdf, p-1)
            if row:
                return {**row, "document_id": annual_doc.document_id,
                        "source_sha256": annual_doc.file_sha256}
    return {"status": "awaiting_verified_table_row",
            "rule_version": RULE_VERSION, "document_id": annual_doc.document_id,
            "source_sha256": annual_doc.file_sha256,
            "source_pages": sorted(relevant_pages)[:12],
            "note": "已定位到真实附注线索，但未成功以表头及单行单元格确认全部金额；禁止使用事先填好的数字代替提取结果。"}


def _disclosure_timeline(root: Path, documents, reconciliation):
    """Read-only presentation projection from SHA-verified pages; no inferred dates."""
    from .connectivity_extraction import ensure_source
    import pymupdf
    rows = []
    if reconciliation.get("source_row_matched"):
        rows.append({"kind": "subproject_annual", "date_label": "2025 报告期间",
            "label": "炼钢子工程本期增加与转固", "note": "具体发生月份未知，不套用整体投产日期",
            "document_id": reconciliation["document_id"], "pdf_page": reconciliation["source_page"]})
    checks = [
        ("AR", 26, r"东山基地零碳高等级薄钢板工厂项目[：:].{0,100}?(2025年12月)[，,]项目正式建成投产",
         "project_operation", "整体项目建成投产", "2025 年 12 月"),
        ("ESG", 32, r"(2025年12月23日)[，,].{0,100}?近零碳钢铁产线在宝钢股份湛江钢铁全线贯通",
         "line_connection", "近零碳产线贯通", "2025 年 12 月 23 日"),
    ]
    for report_type, page, pattern, kind, label, date_label in checks:
        doc = next((d for d in documents if d.report_type == report_type), None)
        if not doc:
            continue
        path = ensure_source(root, doc)
        with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
            if page > len(pdf):
                continue
            text = compact(pdf[page-1].get_text())
        match = re.search(pattern, text)
        if match:
            rows.append({"kind": kind, "date_label": date_label, "label": label,
                "document_id": doc.document_id, "pdf_page": page, "quote": match.group(0),
                "source_sha256": doc.file_sha256, "note": "整体/产线披露，不代表炼钢子工程转固或折旧日期"})
    return rows


def build_baosteel_dossier(root: Path):
    cfg = load_demo_config(root)
    registry = {doc.document_id: doc for doc in load_registry(root)}
    documents = []
    for doc_id in cfg["document_ids"]:
        doc = registry.get(doc_id)
        if doc is None or doc.company_id != cfg["company_id"] or doc.period != "2025":
            raise ValueError("宝钢专项报告来源登记不一致，拒绝使用不明原件")
        documents.append(doc)
    # Preserve the existing verified-source and cached-index workflow.
    fingerprint = tuple((d.document_id, d.file_sha256) for d in documents)
    with _LOCK:
        cached = _CACHE.get(fingerprint)
        if cached and time.monotonic() - cached[0] < 120:
            return json.loads(json.dumps(cached[1], ensure_ascii=False))
    corpus, coverage = read_corpus(root, documents)
    aliases = cfg["aliases"]
    hits = []
    annual_pages = set()
    for ev in corpus:
        quote = compact(ev.quote)
        matched = [name for name in aliases if compact(name) in quote]
        if ev.document_id == "BAOSTEEL_AR_2025" and "炼钢工程" in quote:
            annual_pages.add(ev.pdf_page)
            annual_pages.update([ev.pdf_page-1, ev.pdf_page+1])
        if not matched:
            continue
        # Do not drown the case in unrelated Dongshan-base mentions.
        concrete = any(term in quote for term in ("零碳高等级薄钢板","近零碳示范产线","绿色电炉","炼钢工程"))
        if not concrete and not ("零碳" in quote and ("湛江钢铁" in quote or "东山基地" in quote)):
            continue
        score = sum(5 if term in {"零碳高等级薄钢板", "近零碳示范产线", "绿色电炉", "炼钢工程"} else 2 for term in matched)
        if ev.report_type == "ESG":
            score += 1
        hits.append({"evidence_id": ev.evidence_id, "document_id": ev.document_id,
                     "source_sha256": ev.source_sha256, "report_type": ev.report_type,
                     "report_period": ev.report_period, "pdf_page": ev.pdf_page,
                     "quote": ev.quote[:640], "matched_terms": matched,
                     "source_verified": ev.source_verified and not ev.invalid_reason,
                     "_score":score})
    # Distinct document/page proof; general accounting policies cannot outrank concrete project text.
    hits.sort(key=lambda h:(-h["_score"],h["document_id"],h["pdf_page"]))
    seen=set()
    sources=[]
    for h in hits:
        k=(h["document_id"],h["pdf_page"])
        if k in seen:
            continue
        seen.add(k)
        h.pop("_score",None)
        sources.append(h)
        if len(sources)>=18:break
    annual=next(d for d in documents if d.report_type=="AR")
    reconciliation=_extract_reconciliation(root, annual, annual_pages)
    ar_project=any(s["report_type"]=="AR" and any(x in s["matched_terms"] for x in
                   ("近零碳示范产线","零碳高等级薄钢板","绿色电炉")) for s in sources)
    esg_project=any(s["report_type"]=="ESG" and any(x in s["matched_terms"] for x in
                    ("近零碳示范产线","零碳工厂","绿色电炉")) for s in sources)
    basis=[x for x in ["已定位年报项目披露" if ar_project else "",
                       "已定位可持续报告项目披露" if esg_project else "",
                       "在建工程已按原表数值完成已知金额试算" if reconciliation["status"] in {"balanced","difference","subtotal_computed"} else "在建工程明细尚需核对"] if x]
    dossier={"case_id":cfg["case_id"], "company":cfg["company"],"project_label":cfg["project_label"],
        "pair_id":cfg["pair_id"],"title":cfg["title"],"questions":cfg["questions"],
        "source_type":"registered_public_pdf","data_origin":"fresh_verified_pdf_or_verified_index",
        "case_scope":"2025年两份已登记报告；不声称完成2024跨年验证",
        "evidence":sources,"evidence_count":len(sources),"total_matching_blocks":len(hits),
        "coverage":coverage,"reconciliation":reconciliation,
        "disclosure_timeline":_disclosure_timeline(root, documents, reconciliation),
        "project_mapping":"annual_explicit_subproject" if reconciliation.get("source_row_matched") else "unconfirmed",
        "mapping_note":("2025年报同一表格单行明确将炼钢工程列于宝钢湛江钢铁零碳高等级薄钢板工厂项目下；该原文身份不自动证明与ESG所有披露的统计范围一致。" if reconciliation.get("source_row_matched") else cfg["matching_policy"]),
        "investigation_value":"A" if ar_project and esg_project and reconciliation["status"] in {"balanced","subtotal_computed"} else "B" if sources else "C",
        "ranking_reasons":basis,"rule_checks":[
          {"rule":"R1 转固与确认时点","status":"needs_evidence","question":"是否取得验收日期、达到预定可使用状态的依据及折旧起点？"},
          {"rule":"R2 工程范围差异","status":"needs_evidence","question":"零碳项目整体与炼钢工程部分完工是否属于不同工程边界？"},
          {"rule":"R3 跨口径金额等价","status":"blocked_without_scope","question":"不将总体规划投资、子工程预算、年度支出和转固金额直接相加或等同。"}],
        "audit_procedures":cfg["audit_procedures"],"agents":{"status":"not_run_in_dossier",
         "notice":"专项确定性核验不自动调用模型；五Agent须另行启动并依据对应真实任务回执展示。"},
        "source_warnings":[x for x in [cfg["source_notes"],cfg["external_source_policy"]] if x],
        "generated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    with _LOCK:
        _CACHE[fingerprint]=(time.monotonic(),dossier)
    return dossier
