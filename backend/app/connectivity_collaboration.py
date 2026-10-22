"""按智能体请求执行本报告内取证，记录消息传递和预算停止原因。

模型可以选择查询，但不能指定文件、网址或放宽证据校验。
检索命中、条件变化、专业意见分别计数，命中不等于核验成功。
"""
from __future__ import annotations

import hashlib
import re

from .connectivity_retrieval import retrieve_targeted_pages


def execute_search_requests(root, run, requests, consumer_role):
    """最多执行四个有效请求；同运行相同关系查询只查一次。"""
    checks = {c.check_id: c for c in run.checks}
    rows = {o.occurrence_id: o for o in run.occurrences}
    seen = {e.get('request_id') for e in run.intelligence_trace if e.get('kind') == 'agent_tool_request'}
    results = []
    for request in requests[:4]:
        cid = request.get('check_id', '')
        check = checks.get(cid)
        metric = str(request.get('metric', '')).strip()
        terms = [str(t).strip()[:50] for t in request.get('terms', []) if str(t).strip()][:5]
        signature = '|'.join([cid, metric, request.get('kind', 'counter'), *sorted(set(terms))])
        request_id = hashlib.sha256(signature.encode()).hexdigest()[:20]
        problem = ''
        if check is None:
            problem = 'unknown_check'
        elif not 2 <= len(metric) <= 50 or not any(metric in rows[m.occurrence_id].label for m in check.members if m.occurrence_id in rows):
            problem = 'metric_not_in_bound_members'
        elif not terms or any(re.search(r'https?://|[/\\]|[\x00-\x1f]', t) for t in [metric, *terms]):
            problem = 'invalid_query_terms'
        elif request_id in seen:
            problem = 'duplicate_query'
        event = {'kind': 'agent_tool_request', 'request_id': request_id, 'check_id': cid,
            'producer_role': request.get('producer_role', ''), 'consumer_role': consumer_role,
            'tool': 'search_registered_report', 'metric': metric, 'terms': terms,
            'reason': request.get('reason', ''), 'status': 'rejected' if problem else 'executed', 'rejection': problem}
        run.intelligence_trace.append(event)
        if problem:
            continue
        seen.add(request_id)
        query = {'query_id': request_id, 'kind': request.get('kind', 'counter'),
                 'terms': [metric, *terms], 'text': ' '.join([metric, *terms])}
        tasks = retrieve_targeted_pages(root, run, [check], 1, per_check=4, query_overrides={cid: [query]})
        for task in tasks:
            task.update(request_id=request_id, producer_role=request.get('producer_role', ''), tool='search_registered_report')
            results.append(task)
            run.intelligence_trace.append({'kind': 'agent_tool_result', 'role': consumer_role, **task})
    return results


def collaboration_summary(run):
    """页面和导出共用真实轨迹投影，不生成推理文字或假阶段。"""
    kinds = {'agent_tool_request', 'agent_tool_result', 'adaptive_procedure_plan',
             'adaptive_procedure_effect', 'feedback_decision', 'hypothesis_update'}
    events = [e for e in run.intelligence_trace if e.get('kind') in kinds]
    return {'version': 'autonomous_evidence_v1', 'events': events,
        'tool_requests': sum(e.get('kind') == 'agent_tool_request' and e.get('status') == 'executed' for e in events),
        'tool_rejections': sum(e.get('kind') == 'agent_tool_request' and e.get('status') == 'rejected' for e in events),
        'new_evidence_ids': sorted({oid for e in events if e.get('kind') == 'agent_tool_result' for oid in e.get('new_evidence_ids', [])}),
        'feedback': [e for e in events if e.get('kind') == 'feedback_decision'],
        'limits': {'requests_per_turn': 4, 'feedback_rounds': 1, 'model_calls': 20},
        'notice': '工具实际执行与条件改善分别计数；未命中不等于未披露。'}
