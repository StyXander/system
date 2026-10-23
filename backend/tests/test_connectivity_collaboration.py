"""合成合同测试：执行、消息传递、拒绝与去重，不冒充真实模型证据。"""
from pathlib import Path
from types import SimpleNamespace as N

from backend.app import connectivity_collaboration as module


def sample():
    return N(checks=[N(check_id='C1', members=[N(occurrence_id='O1')],
        relationship_evidence=[], explanation_evidence=[], conditions=[])],
        occurrences=[N(occurrence_id='O1', label='研发投入金额')], intelligence_trace=[])


def directive(**kw):
    return dict(check_id='C1', metric='研发投入', terms=['范围'], kind='counter',
                reason='核实合并边界', producer_role='A1', **kw)


def test_model_query_reaches_tool_and_next_role(monkeypatch):
    run = sample()
    received = []
    def search(root, current, checks, round_number, **kwargs):
        received.append(kwargs['query_overrides'])
        return [dict(check_id='C1', new_evidence_ids=['NEW'], queries=[])]
    monkeypatch.setattr(module, 'retrieve_targeted_pages', search)
    result = module.execute_search_requests(Path('.'), run, [directive()], 'A2')
    assert received[0]['C1'][0]['terms'] == ['研发投入', '范围']
    assert result[0]['producer_role'] == 'A1'
    summary = module.collaboration_summary(run)
    assert summary['tool_requests'] == 1 and summary['new_evidence_ids'] == ['NEW']


def test_repeat_query_stops_without_second_tool_call(monkeypatch):
    run = sample()
    calls = []
    monkeypatch.setattr(module, 'retrieve_targeted_pages', lambda *a, **k: calls.append(1) or [])
    module.execute_search_requests(Path('.'), run, [directive(), directive()], 'A2')
    assert len(calls) == 1
    assert run.intelligence_trace[-1]['rejection'] == 'duplicate_query'


def test_unbound_metric_and_unknown_check_rejected(monkeypatch):
    run = sample()
    monkeypatch.setattr(module, 'retrieve_targeted_pages', lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    wrong = directive()
    wrong['metric'] = '全国GDP'
    missing = directive()
    missing['check_id'] = 'MISSING'
    assert module.execute_search_requests(Path('.'), run, [wrong, missing], 'A2') == []
    assert module.collaboration_summary(run)['tool_rejections'] == 2


def test_url_and_path_queries_rejected():
    run = sample()
    req = directive()
    req['terms'] = ['https://example.com/private']
    assert module.execute_search_requests(Path('.'), run, [req], 'A2') == []
    assert run.intelligence_trace[0]['rejection'] == 'invalid_query_terms'


def test_no_requests_produces_no_fabricated_activity():
    run = sample()
    assert module.execute_search_requests(Path('.'), run, [], 'A3') == []
    assert module.collaboration_summary(run)['events'] == []


def test_existing_hit_is_delivered_once_to_relation(monkeypatch):
    run = sample()
    monkeypatch.setattr(module, 'retrieve_targeted_pages', lambda *a, **k:
        [dict(check_id='C1', new_evidence_ids=[], existing_hits=['O1', 'OLD'], queries=[])])
    first = module.execute_search_requests(Path('.'), run, [directive()], 'A2')[0]
    assert first['new_to_relation_ids'] == ['OLD']
    assert first['delivered_evidence_ids'] == ['O1', 'OLD']
    second = module.execute_search_requests(Path('.'), run, [{**directive(), 'terms': ['母公司']}], 'A3')[0]
    assert second['new_to_relation_ids'] == []


def test_controlled_alias_can_request_search_without_equating_metrics(monkeypatch):
    run = sample()
    calls = []
    monkeypatch.setattr(module, 'retrieve_targeted_pages', lambda *a, **k: calls.append(k) or [])
    module.execute_search_requests(Path('.'), run, [{**directive(), 'metric': '研发支出'}], 'A2')
    assert len(calls) == 1
    assert run.occurrences[0].label == '研发投入金额'
