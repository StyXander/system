"""Regression cases for premature closure, evidence feedback and truthful receipts."""
from contextlib import contextmanager
from copy import deepcopy
import json

from backend.tests.test_matter_connectivity import reports, request, fake_provider
from backend.app.connectivity_matter_pipeline import run_matter_pipeline
from backend.app.connectivity_matter_schemas import MatterToolCall, AgentMatterResult
from backend.app.connectivity_matter_budget import allocate_role_budget
from backend.app.connectivity_matter_completion import effective_role_status, known_usage


def test_one_round_allows_a_real_tool_before_finalization(reports):
    root, rs = reports
    observed = []
    def caller(role, payload):
        if role == 'A2':
            observed.append(deepcopy(payload))
            if not payload.get('finalize_only'):
                assert payload['investigation_round']['remaining_tool_rounds'] == 1
        return fake_provider(role, payload)
    req = request(rs, root=root)
    req.budget.max_role_rounds = 1
    run = run_matter_pipeline(root, req, caller=caller)
    assert len(observed) == 2 and observed[-1]['finalize_only']
    assert observed[-1]['tool_results']
    assert any(r['role'] == 'A2' for r in run.matter_tool_receipts)
    task = next(t for t in run.matter_tasks if t['role'] == 'A2')
    assert task['status'] == 'partial'
    assert task['termination_reason'] == 'tool_round_limit'
    assert run.model_status == 'five_agents_partial'


def test_rules_then_search_are_both_valid_investigation_progress(reports):
    root, rs = reports
    observed = []
    def caller(role, payload):
        if role == 'A2':
            observed.append(deepcopy(payload))
            result = AgentMatterResult(matter_id=payload['matter_id'],input_revision=payload['input_revision'],summary='合成工具续查')
            receipt = {'status':'completed','performed':True,'request_attempted':True,'input_tokens':10,'output_tokens':5}
            if len(observed) == 1:
                result.tool_requests = [MatterToolCall(tool_name='lookup_ontology_rule', arguments={'keyword':'减值'}, reason='先明确要核查的会计机制')]
            elif len(observed) == 2:
                result.tool_requests = [MatterToolCall(tool_name='search_matter_reports', arguments={'query':'减值 现金流预测','report_type':'AR'}, reason='再查原件中的具体假设')]
            else:
                return fake_provider(role, payload)
            return result, receipt
        return fake_provider(role, payload)
    req = request(rs, root=root)
    req.budget.max_role_rounds = 3
    run = run_matter_pipeline(root, req, caller=caller)
    assert len(observed) == 3
    assert not any(p.get('finalize_only') for p in observed)
    tools = [r['tool_name'] for r in run.matter_tool_receipts if r['role'] == 'A2']
    assert tools[:2] == ['lookup_ontology_rule','search_matter_reports']
    assert next(t for t in run.matter_tasks if t['role']=='A2')['status'] == 'completed'


def test_legacy_premature_completion_is_derived_without_rewriting_history():
    old = {'status':'completed','stop_reason':'remaining_tool_rounds=0，无法再检索。'}
    original = deepcopy(old)
    assert effective_role_status(old) == 'partial'
    assert old == original
    concluded = {**old,'termination_reason':'source_exhausted'}
    assert effective_role_status(concluded) == 'completed'


def test_explicit_deep_budget_is_not_silently_discarded_at_twenty():
    limits = allocate_role_budget(40)
    assert sum(limits.values()) == 40
    assert min(limits.values()) >= 7
    assert allocate_role_budget(20) == {'A1':3,'A2':4,'A3':4,'A4':4,'A5':5}


def test_unknown_cache_usage_remains_unknown():
    assert known_usage([{'request_attempted':True,'input_tokens':100,'output_tokens':10}]) == {
        'input_tokens':100,'output_tokens':10,'cache_hit_input_tokens':None,'cache_miss_input_tokens':None}


def test_provider_cache_counts_and_input_are_preserved(monkeypatch):
    import backend.app.connectivity_matter_agents as agents
    monkeypatch.setenv('DEEPSEEK_API_KEY','synthetic-key-not-a-credential')
    monkeypatch.setenv('AUDITTRACE_DEMO_USE_EXTERNAL_MODEL','true')
    captured=[]
    value={'choices':[{'message':{'tool_calls':[{'function':{'name':'submit_matter_investigation','arguments':json.dumps({'matter_id':'','input_revision':1,'summary':'fixture','matters':[],'tool_requests':[{'tool_name':'lookup_ontology_rule','arguments':{'keyword':'减值'},'reason':'合成测试规则查询'}]})}}]},'finish_reason':'tool_calls'}],
        'usage':{'prompt_tokens':100,'completion_tokens':10,'prompt_cache_hit_tokens':40,'prompt_cache_miss_tokens':60}}
    @contextmanager
    def response(req, **kwargs):
        captured.append(json.loads(req.data))
        yield type('Response',(),{'read':lambda self:json.dumps(value).encode()})()
    monkeypatch.setattr(agents,'urlopen',response)
    payload={'input_revision':1,'matter_id':'','documents':[{'document_id':'fixture'}],'evidence':[],'investigation_round':{'remaining_tool_rounds':1}}
    _, receipt=agents.call_matter_role('A1', payload)
    assert json.loads(captured[0]['messages'][1]['content']) == payload
    assert captured[0]['messages'][1]['content'].startswith('{"documents":')
    assert receipt['cache_hit_input_tokens']==40 and receipt['cache_miss_input_tokens']==60