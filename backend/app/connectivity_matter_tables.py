"""Bounded source-table extraction without company codes, fixed pages or preset amounts.

Rows are candidates within the selected evidence pages. Row matching never establishes
cross-report identity. Raw cells, headers, coordinates and unknown markers are retained.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import hashlib
import re

RULE_VERSION = "matter_table_v1"
HEADERS = {
    "opening": ("期初余额", "期初数", "年初余额"),
    "increase": ("本期增加", "本年增加"),
    "to_fixed": ("转入固定资产", "转固"),
    "to_long_term": ("长期待摊",),
    "other_decrease": ("其他减少", "其它减少"),
    "closing": ("期末余额", "期末数", "年末余额"),
}
GENERIC_TERMS = {"项目", "工程", "环保", "绿色", "投入", "建设", "公司", "集团", "投资"}


def compact(value):
    return re.sub(r"\s+", "", str(value or ""))


def parse_cell(raw):
    text = str(raw or "").strip()
    if not text or text in {"—", "-", "–", "－", "不适用", "N/A"}:
        return None
    value = re.sub(r"[\s,，]", "", text).replace("（", "(").replace("）", ")")
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return str(Decimal(value))
    # Preserve the source-specific punctuation-separated digit layout, not a guess.
    lines = text.splitlines()
    if len(lines) == 2 and re.fullmatch(r"[\s,，.。]+", lines[1]):
        groups = lines[0].split()
        if len(groups) > 1 and len(groups[-1]) == 2 and all(len(g) == 3 for g in groups[1:-1]) and all(g.isdigit() for g in groups) and "." in lines[1]:
            return str(Decimal("".join(groups[:-1])+"."+groups[-1]))
    return None


def row_match(label, queries):
    label = compact(label)
    for query in queries:
        q = re.sub(r"（[^）]*）|\([^)]*\)","",compact(query))
        q = re.sub(r"(?:财务线索|披露)$","",q)
        if len(q) >= 4 and (q in label or label in q and len(label) >= 6):
            return "exact_name_candidate"
        significant = [part for part in re.split(r"[\s、，,（）()—:：/]+", str(query)) if len(part) >= 3 and part not in GENERIC_TERMS]
        if any(compact(part) in label for part in significant):
            return "name_fragment_candidate"
        pairs = {q[i:i+2] for i in range(max(0,len(q)-1))} - GENERIC_TERMS
        if len(label) >= 6 and len(pairs) >= 3 and sum(p in label for p in pairs) / len(pairs) >= .55:
            return "lexical_candidate_requires_identity_review"
    return None


def extract_rows(rows, *, queries, page_text, document_id, source_sha256, page, table_id, bbox=None):
    results=[]
    for index,row in enumerate(rows):
        cells=[str(v or "").strip() for v in row]
        if len(cells)<3:continue
        label=next((v for v in cells[:2] if len(compact(v))>=4 and parse_cell(v) is None), "")
        match=row_match(label,queries)
        if not match:continue
        # Headers come from the table's first rows, not the five preceding data rows.
        header_rows=[]
        for candidate in rows[:min(index,6)]:
            has_heading=any(any(term in compact(v) for names in HEADERS.values() for term in names) for v in candidate)
            if sum(parse_cell(v) is not None for v in candidate)>=2 and not has_heading:break
            header_rows.append(candidate)
        headers=[" / ".join(str(r[c] or "").strip() for r in header_rows if c<len(r) and r[c]) for c in range(len(cells))]
        mapping={}
        for key,names in HEADERS.items():
            found=[i for i,h in enumerate(headers) if any(n in compact(h) for n in names)]
            if len(found)==1:mapping[key]=found[0]
        # Multiple roles attached to the same cell are ambiguous.
        if len(set(mapping.values()))!=len(mapping):mapping={}
        raw={k:cells[i] for k,i in mapping.items()}
        values={k:parse_cell(v) for k,v in raw.items()}
        units=set(re.findall(r"单位[：:\s]*(亿元|万元|千元|元)",page_text))
        unit=next(iter(units)) if len(units)==1 else None
        missing=[k for k in HEADERS if values.get(k) is None]
        arithmetic={"status":"needs_evidence","difference":None,"tolerance":None,
                    "scope":"within_report_row","missing":missing,
                    "notice":"未解析到的列、破折号及未明确的舍入方式保持未知；候选行不证明跨报告项目身份。"}
        if not missing and unit:
            calculated=Decimal(values['opening'])+Decimal(values['increase'])-Decimal(values['to_fixed'])-Decimal(values['to_long_term'])-Decimal(values['other_decrease'])
            difference=calculated-Decimal(values['closing'])
            arithmetic.update(status="exact_display_match" if difference==0 else "display_difference",
                computed_closing=str(calculated),reported_closing=values['closing'],difference=str(difference),
                expression="opening + increase - to_fixed - to_long_term - other_decrease = closing")
        fingerprint=hashlib.sha256(f"{source_sha256}|{page}|{table_id}|{index}|{cells}".encode()).hexdigest()
        results.append({"record_id":"MTBL-"+fingerprint[:20],"rule_version":RULE_VERSION,
            "document_id":document_id,"source_sha256":source_sha256,"source_page":page,
            "table_id":table_id,"row_index":index,"bbox":list(bbox or []),
            "source_row_label":label,"match_basis":match,"cross_report_identity":"unverified",
            "raw_cells":cells,"headers":headers,"column_mapping":mapping,"values":values,
            "reported_markers":raw,"unit":unit,"unit_status":"page_unique" if unit else "unverified",
            "currency":"CNY" if re.search(r"币种[：:\s]*人民币",page_text) else "",
            "arithmetic":arithmetic,"extraction":"pymupdf_verified_table_cells"})
    return results


def extract_matter_tables(root, documents, evidence, matters, selected_ids, *, max_pages=8):
    from .connectivity_extraction import ensure_source
    from .source_viewer import PDF_ACCESS_LOCK
    import pymupdf
    selected=[m for m in matters if m.matter_id in selected_ids or set(m.lineage)&set(selected_ids)]
    queries=[v for m in selected for v in [m.name,*m.aliases] if v]
    refs={eid for m in selected for eid in m.evidence_ids}
    candidates=[e for e in evidence if e.source_verified and not e.invalid_reason]
    candidates.sort(key=lambda e:(e.evidence_id not in refs,e.report_type!='AR',e.document_id,e.pdf_page))
    pages=[]
    for e in candidates:
        key=(e.document_id,e.pdf_page)
        if key not in pages:pages.append(key)
    allowed=pages[:max_pages];records=[];coverage=[]
    for doc in documents:
        requested=[p for d,p in allowed if d==doc.document_id]
        if not requested:continue
        path=ensure_source(root,doc)
        with PDF_ACCESS_LOCK,pymupdf.open(path) as pdf:
            for page_number in requested:
                if not 1<=page_number<=len(pdf):continue
                page=pdf[page_number-1];count=0
                try:
                    text=page.get_text()
                    if not any(term in compact(text) for names in HEADERS.values() for term in names):
                        coverage.append({'document_id':doc.document_id,'page':page_number,'status':'no_financial_movement_header'})
                        continue
                    if len(page.get_drawings())>2000:
                        coverage.append({'document_id':doc.document_id,'page':page_number,'status':'graphics_complexity_limit'})
                        continue
                    tables=page.find_tables().tables
                    for ti,table in enumerate(tables):
                        rows=table.extract()
                        matches=extract_rows(rows,queries=queries,page_text=text,
                            document_id=doc.document_id,source_sha256=doc.file_sha256,page=page_number,
                            table_id=f"{doc.document_id}:{page_number}:{ti}",bbox=table.bbox)
                        for row in matches:
                            row['report_period']=doc.effective_period if doc.effective_period in compact(text) else ''
                            row['page_evidence_ids']=[e.evidence_id for e in candidates if e.document_id==doc.document_id and e.pdf_page==page_number]
                            row['matter_ids']=[m.matter_id for m in selected if row_match(row['source_row_label'],[m.name,*m.aliases])]
                        records.extend(matches);count+=len(matches)
                    coverage.append({"document_id":doc.document_id,"page":page_number,"candidate_rows":count,
                        "status":"matched" if count else "no_supported_row_match"})
                except (ValueError,RuntimeError,AttributeError) as error:
                    coverage.append({"document_id":doc.document_id,"page":page_number,"status":"extraction_failed","error":type(error).__name__})
    return {"rule_version":RULE_VERSION,"records":records[:12],"coverage":coverage,
            "page_limit":max_pages,"unscanned_evidence_pages":max(0,len(pages)-len(allowed)),
            "notice":"通用候选表格取证；仅核实来源和单元格，不自动确认项目同一性或企业实际入账。"}


def located_table_values(pack):
    """Retain individual cells for the amount checker, without asserting rounding or scope."""
    from .connectivity_schemas import DisclosureOccurrence
    result=[]
    for row in pack.get('records',[]):
        for key,value in row['values'].items():
            if value is None:continue
            column=row['column_mapping'][key]
            period=row.get('report_period','')
            result.append(DisclosureOccurrence(occurrence_id=row['record_id']+':'+key,
                document_id=row['document_id'],pdf_page=row['source_page'],bbox=row['bbox'],
                label=row['source_row_label']+' / '+row['headers'][column],value=value,
                unit=row.get('unit') or '',unit_status='table' if row.get('unit') else 'unknown',
                unit_source='已验证原页唯一金额单位',currency=row.get('currency') or '',
                currency_status='table' if row.get('currency') else 'unknown',
                year=period,year_status='attributed' if period else 'unattributed',
                year_binding='cell_header' if period else 'unattributed',
                table_id=row['table_id'],row_index=row['row_index'],column_index=column,
                row_header=row['source_row_label'],column_header=row['headers'][column],
                display_precision=len(value.split('.')[1]) if '.' in value else 0,
                context=' | '.join(row['raw_cells']),quality='located' if row.get('unit') and period else 'uncertain',
                quality_reason='原页表格行、表头及单元格已定位；舍入方式和跨报告口径仍未确认'))
    return result
