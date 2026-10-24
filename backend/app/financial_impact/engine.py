"""财务穿透引擎：把事项、附注、会计路径、检索、裁决串成一次可复算的运行。

只读派生：不修改既有六类规则、正式核验状态与三智能体结论。
任何一步失败都降级并留痕，不静默当作成功。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pymupdf

from ..connectivity_extraction import load_registry, source_path, ensure_source
from ..source_viewer import PDF_ACCESS_LOCK
from . import accounting_mapping, financial_linker, financial_notes, impact_analysis, impact_graph, impact_verifier
from .models import FinancialImpactResult
from .sustainability_events import extract_events
from .textutil import compact, project_key

ENGINE_VERSION = "financial_impact_v1.1"
ESG_TERMS = ("节能", "环保", "减排", "绿色", "低碳", "污染治理", "碳", "生态", "循环",
             "清洁生产", "技术改造", "资源综合利用", "研发投入")
MAX_ESG_PAGES = 36


def _load_pages(pdf_path: Path, terms: tuple[str, ...], *, max_pages: int) -> tuple[list[dict], dict]:
    pages: list[dict] = []
    scanned = 0
    with PDF_ACCESS_LOCK, pymupdf.open(pdf_path) as pdf:
        hits = []
        for index, page in enumerate(pdf):
            scanned += 1
            text = page.get_text("text")
            if sum(1 for term in terms if term in text) >= 2:
                hits.append(index)
        for index in hits[:max_pages]:
            page = pdf[index]
            blocks = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                text = "".join(span.get("text", "") for line in block.get("lines", []) for span in line.get("spans", []))
                text = text.strip()
                # 页眉导航（含多个“｜”与篇号）不是正文，不拼进引文。
                if text and text.count("｜") < 2 and not re.search(r"报告\d{2}｜.*篇\d{2}", text):
                    blocks.append({"text": text, "bbox": [round(float(v), 2) for v in block.get("bbox", [])]})
            pages.append({"page": index + 1, "text": page.get_text("text"), "blocks_detail": blocks, "tables": []})
    return pages, {"scanned": scanned, "selected": len(pages)}


def _match_documents(documents):
    esg = next((doc for doc in documents if str(getattr(doc, "report_type", "")).upper() == "ESG"), None)
    ar = next((doc for doc in documents if str(getattr(doc, "report_type", "")).upper() == "AR"), None)
    return esg, ar


AGGREGATE_ROWS = {"合计", "总计", "小计", "总额"}
SEMANTIC_PRIORITY = {"budget": 0, "period_increase": 1, "transfer_out": 2, "closing_balance": 3,
                     "opening_balance": 4, "expense": 5, "actual_payment": 6, "period_decrease": 7}


def _item_for_event(event, items, support_pages: set[int]):
    """只从候选证据页挑项目级财务项目；汇总行与其他项目不得拿来凑数。"""
    usable = [item for item in items
              if item.normalized and item.value_semantics.value not in {"none"}
              and compact(item.row_header) not in AGGREGATE_ROWS
              and "合计" not in compact(item.row_header)]
    if not usable:
        return None, {"status": "no_items", "reason": "附注未解析出带语义的金额项目"}
    same_page = [item for item in usable if item.pdf_page in support_pages]
    names = [compact(value) for value in [event.project_name, *event.aliases] if compact(value)]
    if names:
        named = [item for item in same_page
                 if any(project_key(name) == project_key(item.row_header) for name in names)]
        if named:
            best = min(named, key=lambda item: (SEMANTIC_PRIORITY.get(item.value_semantics.value, 9),
                                                -abs(float(item.normalized or 0))))
            return best, {"status": "project_level", "matched_name": next(
                (name for name in names if name in compact(best.table_title + best.row_header + best.quote)), names[0])}
        return None, {"status": "no_name_match",
                      "reason": "候选页有金额项目，但没有出现同名项目；不跨项目借用"}
    if same_page:
        return None, {"status": "same_page_only", "reason": "事项未给项目名，同页金额无法归属到该项目"}
    return None, {"status": "no_page_evidence", "reason": "候选证据页没有可解析的金额项目"}


def build(root: Path, documents=None, *, industry: str | None = None, model_runner=None,
          allow_vector: bool = False, max_events: int = 14) -> dict:
    started = time.time()
    root = Path(root)
    documents = documents if documents is not None else load_registry(root)
    esg, ar = _match_documents(documents)
    if esg and ar and (len(documents) != 2 or esg.company_id != ar.company_id or esg.case_id != ar.case_id or esg.period != ar.period):
        raise ValueError('财务穿透只能处理本次同企业、同版本登记的双报告')
    receipt: dict = {"version": ENGINE_VERSION, "industry": industry, "degraded": []}
    if esg is None or ar is None:
        return {"version": ENGINE_VERSION, "degraded": ["缺少 ESG 或年报原件"], "events": [], "items": [],
                "relations": [], "graph": {"nodes": [], "edges": [], "paths": [], "stats": {}},
                "analysis": {"current": [], "expected": [], "note": ""}, "stats": {}, "retrieval": receipt,
                "note": "双报告缺一不可；未生成财务穿透结果。"}

    esg_pages, esg_receipt = _load_pages(ensure_source(root, esg), ESG_TERMS, max_pages=MAX_ESG_PAGES)
    note_pages, note_receipt = financial_notes.load_note_pages(ensure_source(root, ar))
    for policy in note_receipt.get('policy_sections', []):
        policy.update(document_id=ar.document_id, file_sha256=ar.file_sha256)
    for doc, pages in ((esg, esg_pages), (ar, note_pages)):
        for page in pages:
            page.update(report_type=doc.report_type, file_sha256=doc.file_sha256)
    events, event_receipt = extract_events(esg_pages, esg, limit=max_events, model_runner=model_runner)
    items, item_receipt = financial_notes.parse_notes(note_pages, ar)
    treatments, mapping_receipt = accounting_mapping.map_events(events)

    # 财务支持证据只从年报检索，不能把ESG自身命中当作另一份报告的支持。
    index, index_receipt = financial_linker.build_index({ar.document_id: note_pages})
    relations = []
    support_count = 0
    counter_count = 0
    rankings = []
    for event in events:
        event_treatments = [treatment for treatment in treatments
                            if treatment.treatment_id.startswith(event.event_id + ":")]
        found = financial_linker.search(event, event_treatments, index, allow_vector=allow_vector)
        rankings.append({'event_id': event.event_id, 'query': found['query'], 'receipt': found['receipt'],
            'pages': list(dict.fromkeys(f"{row['document_id']}#{row['pdf_page']}" for row in found['candidates'] if row['filter_ok']))})
        counter = financial_linker.search_counter(event, index)
        support_count += len(found["candidates"])
        counter_count += len(counter)
        pages = {int(candidate["pdf_page"]) for candidate in found["candidates"] if candidate["filter_ok"]}
        item, selection = _item_for_event(event, items, pages)
        matches = [candidate for candidate in items if candidate.normalized and
                   candidate.document_id == ar.document_id and candidate.pdf_page in pages and
                   project_key(candidate.row_header) in {project_key(event.project_name), *map(project_key, event.aliases)}]
        # 同事项允许多项会计明细；每列保留预算/发生额/余额语义，不取最大数凑金额。
        for chosen in matches[:6] or [item]:
            for treatment in event_treatments[:3] or [None]:
                relation = impact_verifier.build_relation(event, chosen, treatment, support=found["candidates"], counter=counter)
                relation.relation_id += ':' + (treatment.rule_id if treatment else 'none')
                relation.numeric_reconciliation["item_selection"] = selection
                relations.append(relation)

    rules_by_id = {rule.rule_id: rule for rule in accounting_mapping.load_rules()}
    graph = impact_graph.build(events, items, treatments, relations, rules_by_id)
    analysis = impact_analysis.build(events, relations, treatments, items)
    stats = {
        "events": len(events), "items": len(items), "treatments": len(treatments),
        "relations": len(relations), "support_candidates": support_count, "counter_candidates": counter_count,
        "grades": impact_verifier.summarize(relations)["grades"],
        "project_level": len({relation.event_id for relation in relations
                             if relation.grade.value in {'A', 'B'} and relation.numeric_reconciliation.get("item_selection", {}).get("status") == "project_level"}),
        "verified_items": sum(1 for item in items if item.page_verified),
        "duration_ms": int((time.time() - started) * 1000),
    }
    receipt.update({"esg_pages": esg_receipt, "note_pages": note_receipt, "events": event_receipt,
                    "mapping": mapping_receipt, "index": index_receipt,
                    "verifier": impact_verifier.VERIFIER_VERSION, "analysis": impact_analysis.ANALYSIS_VERSION})
    receipt['rankings'] = rankings
    receipt['disclosure_candidates'] = [{'document_id': esg.document_id, 'file_sha256': esg.file_sha256,
        'pdf_page': page['page'], 'quote': block['text'][:450]} for page in esg_pages
        for block in page['blocks_detail'] if len(block['text']) > 30 and any(term in block['text'] for term in ESG_TERMS)][:18]
    if receipt["events"].get("status") == "degraded":
        receipt["degraded"].append("model_extraction_failed")
    result = FinancialImpactResult(
        version=ENGINE_VERSION, company=getattr(esg, "company", ""), period=str(getattr(esg, "period", "")),
        events=events, items=items, treatments=treatments, relations=relations, graph=graph,
        stats=stats, retrieval=receipt,
        analysis=analysis, note="等级是证据支持程度，不是模型正确概率；缺口记待补证，不推断企业未披露。",
    )
    return result.model_dump(mode="json")


def for_pair(root: Path, pair_id: str, **kwargs) -> dict:
    documents = [doc for doc in load_registry(Path(root)) if str(getattr(doc, "case_id", "")) == pair_id]
    if not documents:
        documents = [doc for doc in load_registry(Path(root))
                     if f"{getattr(doc, 'company_id', '')}-{getattr(doc, 'period', '')}" == pair_id]
    return build(Path(root), documents=documents, **kwargs)
