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


def _table_row(pdf, page_idx: int):
    """Extract a *single* row only when headers and all source cells are unambiguous."""
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
            cells = [compact(v or "") for v in row]
            if not any("炼钢工程" in cell for cell in cells):
                continue
            pre = rows[max(0, row_index-5):row_index]
            header = [compact("".join(str(r[c] or "") for r in pre)) for c in range(len(cells))]
            aliases = {
                "opening": ("期初余额", "期初数"), "increase": ("本期增加", "本年增加"),
                "to_fixed": ("转入固定资产", "转固"), "to_long_term": ("长期待摊",),
                "other_decrease": ("其他减少",), "closing": ("期末余额", "期末数"),
            }
            mapping = {}
            for key, names in aliases.items():
                candidates = [i for i, h in enumerate(header) if any(name in h for name in names)]
                if len(candidates) == 1:
                    mapping[key] = candidates[0]
            # Only use a table which explicitly identifies every movement column.
            if len(mapping) != len(aliases) or len(set(mapping.values())) != len(mapping):
                continue
            values = {k: cells[c] for k, c in mapping.items()}
            result = reconcile_construction(values)
            if result["status"] == "insufficient_fields":
                return {"status": "needs_manual_cell_review", "source_page": page_idx+1,
                        "note": result["note"], "missing": result["missing"]}
            result["source_page"] = page_idx+1
            result["extraction"] = "pymupdf_verified_table_cells"
            result["unit"] = "未确认"
            # Never silently infer yuan from a table printed in ten-thousands.
            page_text = page.get_text("text")
            p = page_text.find("在建工程")
            nearby = page_text[max(0,p-400):p+800] if p>=0 else page_text[:2000]
            unit_matches = re.findall(r"单位[：:\s]*(元|万元|千元|亿元)", nearby)
            if len(set(unit_matches)) == 1:
                unit = unit_matches[0]
                multiplier = {"元": Decimal(1), "千元": Decimal(1000),
                              "万元": Decimal(10000), "亿元": Decimal(100000000)}[unit]
                result["unit"] = unit
                result["values_yuan"] = {k: str(Decimal(v)*multiplier) for k,v in result["values"].items()}
                result["difference_yuan"] = str(Decimal(result["difference"])*multiplier)
            else:
                result["status"] = "unit_unverified"
                result["note"] = "表格单元格可计算，但单位不明确，不显示为已核验的人民币金额。"
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
                       "在建工程表格具备可复算字段" if reconciliation["status"] in {"balanced","difference"} else "在建工程明细尚需核对"] if x]
    dossier={"case_id":cfg["case_id"], "company":cfg["company"],"project_label":cfg["project_label"],
        "pair_id":cfg["pair_id"],"title":cfg["title"],"questions":cfg["questions"],
        "source_type":"registered_public_pdf","data_origin":"fresh_verified_pdf_or_verified_index",
        "case_scope":"2025年两份已登记报告；不声称完成2024跨年验证",
        "evidence":sources,"evidence_count":len(sources),"total_matching_blocks":len(hits),
        "coverage":coverage,"reconciliation":reconciliation,
        "project_mapping":"unconfirmed","mapping_note":cfg["matching_policy"],
        "investigation_value":"A" if ar_project and esg_project and reconciliation["status"]=="balanced" else "B" if sources else "C",
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
