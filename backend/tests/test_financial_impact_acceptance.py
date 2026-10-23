"""新增安全/专业边界及自主循环合同。合成PDF与离线模型不计入真实企业或真实调用。"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json

import pymupdf
import pytest

from backend.app.financial_impact import agents, impact_verifier, impact_graph, impact_analysis
from backend.app.financial_impact.models import Stage, Amount, AmountNature, SustainabilityEvent
from backend.app.financial_impact.engine import _item_for_event
from backend.app.financial_impact.financial_notes import parse_notes, _currency, _semantics
from backend.app.connectivity_schemas import ReportDocument, ConnectivityRun
from backend.app.connectivity_extraction import source_path
from backend.app.connectivity_tool_registry import ToolRequest, execute_tool
from backend.tests.test_financial_impact import event, item, treatment, SUPPORT


@pytest.mark.parametrize('changes', [{'period':'2024'}, {'scope':'母公司'}, {'currency':'美元'},
    {'currency':'未明示'}, {'unit':'未明示'}, {'company_id':'OTHER'}, {'page_verified':False},
    {'normalized':'NaN'}, {'normalized':'Infinity'}])
def test_no_reconciliation_when_prerequisite_missing(changes):
    assert impact_verifier.reconcile(event(company_id='SYN'), item(**{'company_id':'SYN', **changes}))['status'] == 'not_comparable'


def test_unknown_accounting_conditions_cannot_be_overridden_by_status_string():
    path = treatment()
    path.conditions[0]['status'] = 'unknown'
    relation = impact_verifier.build_relation(event(), item(), path, support=SUPPORT)
    assert relation.grade.value != 'A'


def test_two_amounts_and_bound_cannot_be_cherry_picked():
    source = event()
    source.amounts.append(deepcopy(source.amounts[0]))
    assert impact_verifier.reconcile(source, item())['status'] == 'not_comparable'
    source.amounts = source.amounts[:1]
    source.amounts[0].qualifier = 'above'
    assert impact_verifier.reconcile(source, item())['status'] == 'not_comparable'


def test_cash_payment_is_not_accrual_increase():
    assert impact_verifier.reconcile(event(amount_nature=AmountNature.ACTUAL_PAYMENT), item())['status'] == 'not_comparable'


def test_support_and_counter_keep_their_own_document_identity():
    counter = {'document_id':'OTHER-AR','file_sha256':'c'*64,'pdf_page':33,'quote':'原文反证','verified':True}
    relation = impact_verifier.build_relation(event(), item(), treatment(), support=SUPPORT, counter=[counter])
    assert relation.counter[0].document_id == 'OTHER-AR'
    assert relation.counter[0].file_sha256 == 'c'*64
    assert relation.supporting[0].document_id == 'AR-DOC'


def test_similar_names_and_page_neighbour_cannot_borrow_project():
    source = event(project_name='低碳生产一期项目')
    target = item(row_header='低碳生产二期项目', quote='低碳生产一期项目和二期项目列表')
    selected, _ = _item_for_event(source, [target], {154})
    assert selected is None
    relation = impact_verifier.build_relation(source, target, treatment(), support=SUPPORT)
    assert relation.grade.value not in {'A','B'}


def test_budget_is_not_current_recognized_financial_effect():
    target = item(value_semantics=AmountNature.BUDGET)
    relation = impact_verifier.build_relation(event(amount_nature=AmountNature.NONE, amounts=[]), target, treatment(), support=SUPPORT)
    assert impact_analysis.build([event()], [relation], [treatment()], [target])['current'] == []
    assert impact_analysis.state_of(event(stage=Stage.COMPLETED))['state'] == 'completed'
    assert impact_analysis.state_of(event(stage=Stage.UNKNOWN))['state'] == 'unknown'


def test_graph_cannot_verify_path_by_ignoring_unknown_accounting_edge():
    relation = impact_verifier.build_relation(event(), item(), treatment(status='hypothesis'), support=SUPPORT)
    graph = impact_graph.build([event()], [item()], [treatment(status='hypothesis')], [relation])
    assert graph['paths'] and not any(path['verified'] for path in graph['paths'])
    evidence = [node['id'] for node in graph['nodes'] if node['type']=='evidence']
    assert evidence == [node['id'] for node in impact_graph.build([event()], [item()], [treatment(status='hypothesis')], [relation])['nodes'] if node['type']=='evidence']


def test_currency_and_statement_semantics_are_not_guessed_from_unit():
    assert _currency('单位：元') == '未明示'
    assert _currency('单位：美元') == '美元'
    assert _semantics('2025年度','支付其他与经营活动有关的现金','合并现金流量表') == AmountNature.ACTUAL_PAYMENT
    assert _semantics('2025年度','研发费用','合并利润表') == AmountNature.EXPENSE


def test_future_stage_cannot_be_completed_by_model_assertion():
    from backend.app.financial_impact.sustainability_events import apply_model_fields
    source = event(stage=Stage.UNKNOWN, amount_nature=AmountNature.NONE, quote='正在研究的低碳项目')
    result, _ = apply_model_fields([source], lambda _:json.dumps([{'event_id':source.event_id,'stage':'completed','amount_nature':'actual_payment'}]), {10:source.quote})
    assert result[0].stage == Stage.UNKNOWN and result[0].amount_nature == AmountNature.NONE


@pytest.fixture
def workspace(tmp_path):
    docs=[]
    for kind in ('ESG','AR'):
        doc=ReportDocument(document_id='SYN-'+kind,case_id='SYN-2025',company_id='SYN',company='合成企业',
            report_type=kind,period='2025',pages=2,source_url='https://example.invalid/synthetic')
        text='本期投入人民币1亿元建设羧甲基纤维素改造项目。' if kind=='ESG' else '羧甲基纤维素改造项目 本期增加金额 100000000'
        pdf=pymupdf.open()
        for _ in range(2):
            page=pdf.new_page();page.insert_text((30,60),text,fontname='china-s',fontsize=10)
        content=pdf.tobytes();pdf.close();doc.file_sha256=hashlib.sha256(content).hexdigest()
        path=source_path(tmp_path,doc);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content);docs.append(doc)
    source=event(event_id='SYN-E',company_id='SYN',document_id=docs[0].document_id,file_sha256=docs[0].file_sha256,
        pdf_page=1,quote='本期投入人民币1亿元建设羧甲基纤维素改造项目。')
    target=item(item_id='SYN-I',company_id='SYN',document_id=docs[1].document_id,file_sha256=docs[1].file_sha256,
        pdf_page=2,quote='羧甲基纤维素改造项目 本期增加金额 100000000')
    run=ConnectivityRun(run_id='SYNTHETIC-AGENT-TEST',company='合成企业',period='2025',documents=docs,dataset_role='synthetic')
    run.financial_impact={'events':[source.model_dump(mode='json')],'items':[target.model_dump(mode='json')],
        'treatments':[],'relations':[],'stats':{}}
    return tmp_path,run,source,target


def test_full_quote_hash_and_arguments_are_verified(workspace):
    root,run,source,target=workspace
    common={'document_id':source.document_id,'page':1,'quote':source.quote}
    assert execute_tool(root,run,ToolRequest('verify_evidence',common))['verified']
    assert not execute_tool(root,run,ToolRequest('verify_evidence',{**common,'quote':source.quote+'虚构尾句'}))['verified']
    assert execute_tool(root,run,ToolRequest('verify_evidence',{**common,'page':'bad'}))['status']=='rejected'
    path=source_path(root,run.documents[0]);path.write_bytes(b'changed')
    assert execute_tool(root,run,ToolRequest('verify_evidence',common))['status']=='rejected'


def test_real_tool_cycle_changes_second_query_and_passes_receipts_between_roles(workspace):
    root,run,source,target=workspace
    seen=[]
    def invoke(role,payload):
        seen.append((role,payload))
        round_no=payload['round']; who=role.split('_')[-1]
        output={}
        if round_no==1:
            tool={'A1':'search_esg_events','A2':'inspect_financial_table','A3':'search_counter_evidence'}[who]
            output={'tool_requests':[{'event_id':source.event_id,'tool_name':tool,
                'arguments':{'query':'羧甲基纤维素','item_id':target.item_id}}]}
        elif who in {'A2','A3'}:
            assert payload['tool_receipts']
            output={'proposals':[{'event_id':source.event_id,'item_id':target.item_id,'rule_id':'AR-01',
                'reason':'同项目的候选会计路径，确认前提仍待验证', 'citations':[
                    {'document_id':source.document_id,'pdf_page':1,'quote':source.quote},
                    {'document_id':target.document_id,'pdf_page':2,'quote':target.row_header}]}]}
        return output,{'performed':True,'model':'OFFLINE_TEST_DOUBLE','input_tokens':1,'output_tokens':1,'cost':None}
    receipt=agents.investigate(root,run,invoke)
    assert receipt['model_status']=='completed' and len(seen)==6
    assert receipt['judgments'] and all(j['program_grade']!='A' for j in receipt['judgments'])
    assert {r['tool_name'] for r in receipt['tool_receipts']} >= {'search_esg_events','inspect_financial_table','search_counter_evidence','verify_evidence'}
    assert source.amounts == SustainabilityEvent.model_validate(run.financial_impact['events'][0]).amounts


def test_model_cannot_set_grade_or_exceed_call_budget(workspace):
    root,run,source,target=workspace
    invoke=lambda *args:({'grade':'A'},{'performed':True,'model':'OFFLINE_TEST_DOUBLE'})
    result=agents.investigate(root,run,invoke,max_calls=1)
    assert result['model_status']=='partial' and result['calls']==1
    assert not result['judgments'] and not run.financial_impact['relations']


def test_quota_failure_never_looks_like_three_agents_completed(workspace):
    root,run,*_=workspace
    def denied(*_):raise ValueError('MODEL_TOKEN_BUDGET_EXHAUSTED')
    result=agents.investigate(root,run,denied)
    assert result['model_status']=='partial' and result['calls']==1
    assert len([row for row in result['roles'] if row['status']=='skipped'])==2


def test_metrics_require_independent_labels_and_use_actual_predictions():
    from backend.app.financial_impact.evaluation import evaluate
    hashes={'ESG':'a'*64}
    packet={'status':'human_reviewed','closed_world':True,'samples':[{'pair_id':'P','event':{'event_id':'E'},
        'label':True,'provenance':'human','reviewer':'SYNTHETIC_TEST_REVIEWER','source_hashes':hashes,
        'candidate_relations':[{'grade':'A'}],'relation_keys':['I|AR-01'],'relevant_page_refs':['AR#2'],
        'correct_rule_ids':['AR-01'],'should_abstain':False}]}
    payload={'events':[{'event_id':'E'}],'relations':[],'retrieval':{'rankings':[{'event_id':'E','pages':['AR#2']}]}}
    metrics=evaluate(payload,packet,'P',hashes)['metrics']
    assert metrics['relation_recall']==0 and metrics['relation_precision'] is None
    assert metrics['note_recall_at_5']==1
    assert evaluate(payload,{**packet,'status':'not_completed'},'P',hashes)['metrics'] is None
    assert evaluate(payload,packet,'P',{'ESG':'b'*64})['metrics'] is None
    assert evaluate({'events':[{'event_id':'UNLABELED'}]},packet,'P',hashes)['metrics'] is None


def test_source_change_invalidates_new_financial_projection_without_overwriting_history(workspace,monkeypatch):
    from backend.app import connectivity_extraction
    from backend.app.connectivity_graph import refresh_run_sources
    root,run,source,target=workspace
    run.financial_impact.update(relations=[{'grade':'B','numeric_reconciliation':{'status':'matched'}}],
        graph={'paths':[{'verified':True}],'nodes':[]},analysis={'current':[{'value':'100'}]})
    monkeypatch.setattr(connectivity_extraction,'load_registry',lambda _:run.documents)
    source_path(root,run.documents[0]).write_bytes(b'changed')
    current=refresh_run_sources(root,run)
    assert current.financial_impact['relations'][0]['grade']=='D'
    assert current.financial_impact['relations'][0]['historical_grade']=='B'
    assert not current.financial_impact['graph']['paths'][0]['verified']
    assert current.financial_impact['analysis']['current']==[]
    assert run.financial_impact['relations'][0]['grade']=='B'


def test_a1_discovers_only_source_verified_new_events(workspace):
    root,run,source,target=workspace
    run.financial_impact['events']=[]
    run.financial_impact['retrieval']={'disclosure_candidates':[{'quote':source.quote}]}
    def invoke(role,payload):
        return {'new_events':[{'citation':{'document_id':source.document_id,'pdf_page':1,'quote':source.quote},
            'activity_type':'facility_retrofit'}]}, {'performed':True,'model':'OFFLINE_TEST_DOUBLE'}
    agents.investigate(root,run,invoke,mode='single_model')
    assert len(run.financial_impact['events'])==1
    found=run.financial_impact['events'][0]
    assert found['page_verified'] and found['extraction_method']=='model'
    assert found['file_sha256']==source.file_sha256


def test_ai_hypothesis_cannot_add_unquoted_numbers(workspace):
    root,run,source,target=workspace
    def invoke(*_):
        return {'proposals':[{'event_id':source.event_id,'item_id':target.item_id,'rule_id':'AR-01',
            'reason':'本期增加999亿元，已全部确认', 'citations':[
                {'document_id':source.document_id,'pdf_page':1,'quote':source.quote},
                {'document_id':target.document_id,'pdf_page':2,'quote':target.row_header}]}]}, {'performed':True,'model':'OFFLINE_TEST_DOUBLE'}
    receipt=agents.investigate(root,run,invoke,mode='single_model')
    assert not receipt['judgments'] and receipt['rejected']


def test_api_read_uses_one_store_lookup_and_hides_internal_fields(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app import connectivity_api
    from backend.app.demo_run_tasks import DemoRunTaskStore
    monkeypatch.setattr(connectivity_api,'demo_task_supabase_enabled',lambda:False)
    monkeypatch.setattr(connectivity_api,'load_registry',lambda _:[])
    calls=[]
    def get(_,task_id):
        calls.append(task_id)
        return {'task_id':task_id,'status':'failed','result':{'private':'hidden'},'lease_token':'secret',
            'run_body':{'kind':'connectivity','owner':'not-session'},'request_payload':{'secret':'hidden'},'_file_path':'hidden'}
    monkeypatch.setattr(DemoRunTaskStore,'get',get)
    monkeypatch.setattr(DemoRunTaskStore,'snapshot',lambda *_:pytest.fail('重复读取远程台账'))
    app=FastAPI();app.include_router(connectivity_api.build_router(tmp_path,lambda _:None,lambda:None))
    with TestClient(app) as client:
        response=client.get('/api/connectivity/runs/CONNJOB-SYN')
    assert response.status_code==200 and calls==['CONNJOB-SYN']
    body=response.json()
    assert body['result'] is None and not {'lease_token','run_body','request_payload','_file_path'} & body.keys()


@pytest.mark.parametrize('role',['financial_A1','financial_A2','financial_A3','financial_single'])
def test_production_transport_accepts_financial_contract_without_legacy_role_lookup(monkeypatch,role):
    from backend.app import connectivity_pipeline as pipeline
    monkeypatch.setenv('DEEPSEEK_API_KEY','SYNTHETIC_TEST_KEY')
    monkeypatch.setenv('AUDITTRACE_DEMO_USE_EXTERNAL_MODEL','true')
    monkeypatch.setenv('DEEPSEEK_BASE_URL','https://api.deepseek.com')
    monkeypatch.setenv('DEEPSEEK_MODEL','OFFLINE_TEST_DOUBLE')
    captured=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def read(self):return json.dumps({'model':'OFFLINE_TEST_DOUBLE','usage':{'prompt_tokens':7,'completion_tokens':3},
            'choices':[{'finish_reason':'tool_calls','message':{'tool_calls':[{'function':{
                'name':'submit_connectivity_relationships','arguments':'{"decision_reason":"合成传输合同"}'}}]}}]}).encode()
    def offline(request,**kwargs):
        captured.append(json.loads(request.data));return Response()
    monkeypatch.setattr(pipeline,'urlopen',offline)
    output,record=pipeline.call_role(role,{'role':role})
    assert output['decision_reason']=='合成传输合同' and record['input_tokens']==7
    assert captured[0]['max_tokens']==3000
    assert 'tool_requests' in captured[0]['tools'][0]['function']['parameters']['properties']
