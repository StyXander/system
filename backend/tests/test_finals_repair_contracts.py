"""修复回归：真实失败模式与边界，不调用外部服务；合成输入明确隔离。"""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import os
import importlib.util

import pytest

from backend.app.connectivity_claim_taxonomy import classify_claim
from backend.app.connectivity_financial_bridge import build, _amounts
from backend.app.connectivity_financial_scenario import build_scenario, recalculate_scenario
from backend.app.connectivity_graph import build_impact_graph, invalidate_graph, refresh_run_sources
from backend.app.connectivity_schemas import ConnectivityRun
from backend.app.connectivity_agent_orchestrator import run_investigation
from backend.app import connectivity_agent_orchestrator as agent
from backend.app.connectivity_evidence_planner import rerank
from backend.app.connectivity_temporal import compare_periods
from backend.app.connectivity_peer_benchmark import peer_benchmark
from backend.tests.test_financial_bridge import _docs, _pages
from backend.tests.test_agent_orchestrator import _plan, _revision
from backend.tests.test_temporal_peer import _context, _qualify


@pytest.mark.parametrize('text', ['公司目标到2030年减少碳排放20%。', '公司计划实现节能25万吨标准煤。',
    '公司拟投入32亿元，预计减少碳排放64万吨。', '公司承诺未来实现零碳排放。'])
def test_future_language_never_becomes_realized(text):
    assert classify_claim(text, _amounts(text))['planned_or_realized'] != 'realized'


def test_resource_selection_uses_the_actual_matching_amount():
    bridge = build(None, documents=_docs(), pages=_pages(), industry='steel')
    result = build_scenario(bridge)
    assert result['base']['unit'] in {'万吨标煤', '万吨标准煤'}
    assert Decimal(result['base']['normalized']) == Decimal('258500')
    for claim in bridge['claims']:
        claim['planned_or_realized'] = 'plan'
    assert build_scenario(bridge)['available'] is False


def test_recalculation_is_same_source_and_rejects_nonfinite_values():
    scenario = build_scenario(build(None, documents=_docs(), pages=_pages(), industry='steel'))
    original = deepcopy(scenario)
    result = recalculate_scenario(scenario, '1000', '110')
    assert result['scenario_result']['value'] == '2.84'
    assert result['base'] == scenario['base'] and scenario == original
    for price, usage in [('NaN', '100'), ('Infinity', '100'), ('1001', '100'), ('850', '-1'), ('850', '111')]:
        with pytest.raises(ValueError):
            recalculate_scenario(scenario, price, usage)


def test_biogas_volume_and_approximate_savings_are_not_water_savings():
    bridge = build(None, documents=_docs(), pages=_pages(), industry='food_beverage')
    for text in ('厌氧发酵产生的沼气发电，年处理沼气400万立方米以上，减少二氧化碳排放量。',
                 '报告期内节约用水约400万立方米。'):
        bridge['claims'] = [{'claim_id':'SYN-VOLUME','document_id':'TEST_ESG','pdf_page':1,
                            'text':text,'planned_or_realized':'realized','amounts':_amounts(text)}]
        assert build_scenario(bridge)['available'] is False


def test_exact_water_savings_use_water_price_only():
    bridge = build(None, documents=_docs(), pages=_pages(), industry='food_beverage')
    text='报告期内实现节约用水400万立方米。'
    bridge['claims']=[{'claim_id':'SYN-WATER','document_id':'TEST_ESG','pdf_page':1,
                      'text':text,'planned_or_realized':'realized','amounts':_amounts(text)}]
    scenario=build_scenario(bridge)
    assert scenario['available'] is True
    assert scenario['baseline']['value']=='0.18'
    assert scenario['parameters']['price']['unit']=='元/立方米'


def test_source_refresh_detects_changed_annual_without_mutating_history(tmp_path):
    documents = _docs()
    folder = tmp_path/'backend/runtime/connectivity/sources'
    folder.mkdir(parents=True)
    for doc in documents:
        data = doc.document_id.encode()
        doc.file_sha256 = hashlib.sha256(data).hexdigest()
        (folder/(doc.file_sha256+'.pdf')).write_bytes(data)
    (tmp_path/'backend/connectivity_reports.json').write_text(json.dumps({'documents':[doc.model_dump() for doc in documents]}),encoding='utf-8')
    bridge = build(None, documents=documents, pages=_pages(), industry='steel')
    run = ConnectivityRun(run_id='SYN-REFRESH', company='合成测试', period='2025', documents=documents,
                          financial_claims=bridge['claims'], financial_nodes=bridge['nodes'], financial_edges=bridge['edges'],
                          impact_graph=build_impact_graph(bridge), financial_scenario=build_scenario(bridge))
    (folder/(documents[0].file_sha256+'.pdf')).write_bytes(b'changed annual report')
    projected = refresh_run_sources(tmp_path, run)
    assert projected.versions['source_validity']['status'] == 'invalid'
    assert any(edge.get('invalid') for edge in projected.impact_graph['edges'])
    assert projected.financial_scenario['available'] is False
    assert any(edge.get('invalid') for edge in projected.financial_edges)
    from backend.app.connectivity_delivery import export_run
    from docx import Document
    from io import BytesIO
    payload,_=export_run(projected,'docx')
    word=Document(BytesIO(payload))
    assert any('历史结果 来源已失效' in paragraph.text for paragraph in word.paragraphs)
    assert run.financial_scenario['available'] is True
    assert not run.impact_graph['invalidations']


def test_legacy_graph_without_dependencies_still_checks_both_nodes():
    graph = build_impact_graph(build(None, documents=_docs(), pages=_pages(), industry='steel'))
    for edge in graph['edges']:
        edge.pop('source_dependencies', None)
    invalidate_graph(graph, {'TEST_AR':'f'*64})
    assert graph['invalidations']


def test_replanning_keeps_unreviewed_actions_and_conditions():
    plan = _plan(count=2)
    plan['by_edge'] = {'EDGE-1': deepcopy(plan['best_path'])}
    result = rerank(plan, completed_conditions=[], new_evidence_ids=[], reviewed_actions=['ACT-1'])
    assert result['by_edge']['EDGE-1'][0]['action_id'] == 'ACT-2'
    assert result['rerank']['completed_conditions'] == ['ACT-1']


def test_challenger_calls_are_counted_and_new_tools_are_reachable(monkeypatch):
    seen = []
    def tool(root, run, request):
        seen.append(request.tool_name)
        return {'tool_name':request.tool_name,'args_hash':'a','status':'hit','output_digest':f'E-{len(seen)}',
                'source_hash':'s','elapsed_ms':1,'result':{'quote':'预算数 本期增加'},'reason':''}
    monkeypatch.setattr(agent,'execute_tool',tool)
    def challenger(payload):
        return {'hypotheses':[{'edge_id':'EDGE-1','explanation':'可能存在分阶段预算口径差异。',
            'testable_condition':'核查项目列名','next_tool':'lookup_ontology_rule','tool_arguments':{'keyword':'研发'}}]}, {
            'provider_call_id':f'CALL-{len(seen)}','performed':True,'role':'challenger','status':'completed','input_tokens':10,'output_tokens':5}
    run = ConnectivityRun(run_id='SYN-INV',company='合成测试',period='2025',documents=[])
    result = run_investigation(None,run,bridge={'edges':[]},revision=_revision(),plan=_plan(count=1),challenger=challenger,max_rounds=3)
    assert 'lookup_ontology_rule' in seen
    assert len(run.provider_calls) == result['summary']['challenger_calls']
    assert sum(call['input_tokens'] for call in run.provider_calls) >= 10
    assert result['final_plan']['by_edge']


def test_missing_sources_and_incompatible_peer_identity_stay_unavailable():
    context = _context()
    registry = _qualify({'authorized':True,'samples':[{'company':company,'label':'环保投入','value':str(index+10),'unit':'亿元',
        'source':'合成来源','period':'2025'} for index,company in enumerate(['甲','乙','丙'])]})
    assert peer_benchmark('环保投入','12','亿元',registry=registry,context=context)['available']
    registry['samples'][0]['period']='2024'
    result = peer_benchmark('环保投入','12','亿元',registry=registry,context=context)
    assert not result['available'] and result['comparable_samples']==2
    current={**context,'label':'环保投入','value':'12','unit':'亿元'}
    prior={**current,'period':'2024','value':'10','scope':'母公司'}
    assert not compare_periods(current,prior)['available']


def test_experiment_environment_restored_and_models_require_opt_in(monkeypatch):
    path=Path(__file__).resolve().parents[2]/'scripts/run_b_experiment.py'
    spec=importlib.util.spec_from_file_location('repair_b_experiment',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('DEEPSEEK_API_KEY','synthetic-not-a-key')
    result=module.run_model_condition(Path('.'),'B3','adaptive_agents')
    assert result['status']=='not_run'
    monkeypatch.setenv('CONNECTIVITY_ABLATION_NO_RETRIEVAL','original')
    with pytest.raises(RuntimeError):
        with module._condition_environment('B1',{},6,60000):
            assert os.environ['CONNECTIVITY_EXPERIMENT_MAX_CALLS']=='1'
            assert os.environ['CONNECTIVITY_ABLATION_NO_RETRIEVAL']=='1'
            raise RuntimeError('synthetic failure')
    assert os.environ['CONNECTIVITY_ABLATION_NO_RETRIEVAL']=='original'
