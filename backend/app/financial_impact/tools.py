"""财务工具仅访问本次已登记文档，不接受任意路径、URL或模型提供的金额。"""
from __future__ import annotations

from .models import FinancialItem, SustainabilityEvent
from .textutil import compact
from .impact_verifier import _scope, _period, reconcile


def execute(root, run, name: str, args: dict) -> dict:
    from ..connectivity_tool_registry import execute_tool, ToolRequest
    data = run.financial_impact or {}
    documents = {doc.document_id: doc for doc in run.documents}
    def owned(row):
        doc = documents.get(row.get('document_id'))
        return bool(doc and row.get('file_sha256') == doc.file_sha256)
    events = {row['event_id']: row for row in data.get('events', []) if owned(row)}
    items = {row['item_id']: row for row in data.get('items', []) if owned(row)}
    event = events.get(args.get('event_id'))
    item = items.get(args.get('item_id'))
    if name == 'inspect_financial_table':
        if not item:
            return {'status': 'rejected', 'reason': 'item_id不属于本次报告版本'}
        ref = execute_tool(root, run, ToolRequest('verify_evidence', {
            'document_id': item['document_id'], 'page': item['pdf_page'], 'quote': item['row_header']}))
        excerpt = execute_tool(root, run, ToolRequest('open_source_page', {
            'document_id': item['document_id'], 'page': item['pdf_page'], 'terms': [item['row_header']]}))
        return {'status': 'ok' if ref.get('verified') else 'gap',
                'source_hash': item['file_sha256'], 'result': {'item': item, 'source_check': ref, 'page_excerpt': excerpt.get('result')}}
    if not event:
        return {'status': 'rejected', 'reason': 'event_id不属于本次报告版本'}
    if name == 'search_project_aliases':
        names = [event.get('project_name'), *event.get('aliases', [])]
        hits = [row for row in items.values() if any(value and compact(value) in compact(row['row_header']) for value in names)]
        return {'status': 'ok', 'result': {'event_id': event['event_id'], 'names': names,
            'items': hits[:6], 'note': '别名仅帮助检索，不能单独证明项目相同'}}
    if name == 'search_counter_evidence':
        project = event.get('project_name', '')
        if not project:
            return {'status': 'gap', 'reason': '事项未命名，反证不能归属到具体项目'}
        from .financial_linker import Index, Unit, search_counter
        units = []
        for doc in run.documents:
            if doc.report_type != 'AR':
                continue
            receipt = execute_tool(root, run, ToolRequest('search_registered_reports',
                {'document_id': doc.document_id, 'terms': [project]}))
            for hit in (receipt.get('result') or {}).get('hits', []):
                units.append(Unit(str(hit.get('page')), doc.document_id, 'AR', int(hit.get('page') or hit.get('pdf_page') or 0),
                    str(hit.get('snippet') or hit.get('quote') or ''), file_sha256=doc.file_sha256))
        hits = search_counter(SustainabilityEvent.model_validate(event), Index(units))
        return {'status': 'hit' if hits else 'no_match', 'result': {'event_id': event['event_id'], 'counter': hits,
            'note': '未命中不等于不存在反证；本次只检索登记报告且受工具时间限制'}}
    if not item:
        return {'status': 'rejected', 'reason': 'item_id不属于本次报告版本'}
    parsed_event, parsed_item = SustainabilityEvent.model_validate(event), FinancialItem.model_validate(item)
    if name == 'compare_reporting_scope':
        return {'status': 'ok', 'result': {'scope': _scope(parsed_event, parsed_item),
                                          'period': _period(parsed_event, parsed_item)}}
    if name == 'recalculate_financial_bridge':
        return {'status': 'ok', 'result': reconcile(parsed_event, parsed_item)}
    return {'status': 'rejected', 'reason': '未知财务工具'}
