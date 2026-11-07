"""Synthetic regression fixtures for measurement defects, never human gold."""
import json
from copy import deepcopy
import pytest
from fastapi import HTTPException

from scripts.competition_receipts import execution_eligibility, usage_receipt, resolve_case
from scripts.evaluate_matter_benchmark import evaluate_comparison, extract_run_verdict
from scripts.run_render_comparison import receipt
from backend.app.connectivity_api import validate_retry_scope
from backend.app.connectivity_schemas import RunRequest
from backend.tests.test_matter_connectivity import reports, request, fake_provider


def comparison(tmp_path, run, **row_overrides):
    (tmp_path/'run.json').write_text(json.dumps(run))
    row={'case_id':'SYN-C','matter_id':'SYN-M','run_id':'SYN-R','result_file':'run.json',
         'group_id':'G3','status':'recorded','task_status':'completed', **row_overrides}
    path=tmp_path/'comparison.json'; path.write_text(json.dumps({'runs':[row]}))
    return path


def complete_run():
    return {'run_id':'SYN-R','execution_mode':'five_agents','model_status':'five_agents_completed',
            'matter_assessments':[{'matter_id':'SYN-M','relation_support':'pending','amount_comparability':'needs_evidence'}]}


def test_provider_outage_is_failure_even_if_legacy_receipt_says_recorded(tmp_path):
    run={'run_id':'SYN-R','model_status':'five_agents_partial','matter_assessments':[],
         'provider_calls':[{'status':'failed','failure_code':'MODEL_HTTP_500'}]}
    path=comparison(tmp_path,run,task_status='degraded')
    report=evaluate_comparison(path,{'SYN-C':{'gold_verdict':'INSUFFICIENT_EVIDENCE'}})
    result=report['evaluations'][0]
    assert result['failed']==1 and result['evaluated']==0 and result['completion_rate']==0
    assert result['classification'] is None and report['evaluation_status']=='not_evaluated'


def test_completed_business_abstention_remains_evaluable(tmp_path):
    path=comparison(tmp_path,complete_run())
    result=evaluate_comparison(path,{'SYN-C':{'gold_verdict':'INSUFFICIENT_EVIDENCE'}})['evaluations'][0]
    assert result['evaluated']==1 and result['classification']['accuracy']==1
    assert result['confirmation']['fcr'] is None


def test_saved_partial_assessment_does_not_hide_failed_roles(tmp_path):
    run=complete_run();run['matter_tasks']=[{'role':'A4','status':'failed'}]
    assert execution_eligibility(run)[0] is False


def test_successful_retry_retains_history_without_counting_old_failure_as_current():
    run=complete_run()
    run['matter_tasks']=[{'run_id':'OLD','role':'A4','matter_id':'SYN-M','status':'failed'},
                         {'run_id':'SYN-R','role':'A4','matter_id':'SYN-M','status':'completed'}]
    assert execution_eligibility(run)==(True,'completed')


def test_absent_assessment_cannot_be_a_business_prediction():
    with pytest.raises(ValueError,match='ASSESSMENT_MISSING'):
        extract_run_verdict({'matter_assessments':[]},'SYN-M')


def test_only_fully_executed_declared_ablation_is_eligible():
    run=complete_run();run.update(model_status='five_agents_partial',versions={'ablation':'no_counterevidence'})
    run['matter_tasks']=[{'role':role,'status':'completed'} for role in ('A1','A2','A3','A5')]
    assert execution_eligibility(run,'degraded')==(True,'completed_declared_ablation')
    run['matter_tasks'][-1]['status']='partial'
    assert not execution_eligibility(run,'degraded')[0]


def test_unknown_usage_is_not_zero_or_estimated_upper_bound():
    calls=[{'request_attempted':True,'input_tokens':12,'output_tokens':3},
           {'request_attempted':True,'input_tokens':None,'output_tokens':None,'input_token_upper_bound':500}]
    usage=usage_receipt(calls)
    assert usage['input_tokens'] is None and usage['output_tokens'] is None
    assert usage['known_input_tokens']==12 and usage['unknown_usage_calls']==1
    row={'matter_id':'SYN-M'}
    receipt(row,{'status':'degraded','result':{'provider_calls':calls,'model_status':'five_agents_partial'}})
    assert row['status']=='recorded' and row['execution_eligible'] is False and row['input_tokens'] is None


def test_manifest_mismatch_is_rejected_before_running(tmp_path):
    path=tmp_path/'cases.json'
    case={'case_id':'SYN-C','question_id':'Q1','question':'合成测试问题','report_set_id':'SET',
          'matter_id':'SYN-M','as_of_date':'2026-11-07'}
    path.write_text(json.dumps({'scenarios':[case]}))
    assert resolve_case(path,'SYN-C',report_set_id='SET',matter_id='SYN-M',as_of='2026-11-07')['research_question']==case['question']
    with pytest.raises(ValueError,match='CASE_ID_UNKNOWN'):
        resolve_case(path,'invented',report_set_id='SET',matter_id='SYN-M',as_of='2026-11-07')
    with pytest.raises(ValueError,match='CASE_INPUT_MISMATCH'):
        resolve_case(path,'SYN-C',report_set_id='SET',matter_id='other',as_of='2026-11-07')


def test_a_different_or_missing_question_cannot_be_scored_as_the_gold_task(tmp_path):
    run=complete_run()
    path=comparison(tmp_path,run)
    gold={'SYN-C':{'gold_verdict':'INSUFFICIENT_EVIDENCE','question':'明确问题','question_id':'Q1'}}
    assert evaluate_comparison(path,gold)['evaluations'][0]['cases'][0]['failure']=='question_identity_unverified'
    run['versions']={'research_question':{'text':'明确问题','question_id':'Q1','case_id':'SYN-C'}}
    path=comparison(tmp_path,run)
    assert evaluate_comparison(path,gold)['evaluations'][0]['evaluated']==1


@pytest.mark.parametrize('change',[
    {'experiment_mode':'fixed_evidence'}, {'selected_matter_ids':['M2']},
    {'fixed_evidence_ids':['E2']}, {'comparison_run':True}, {'research_question':'changed'},
])
def test_incremental_retry_cannot_mix_experiment_conditions(change):
    req=RunRequest(report_set_id='SET',mode='five_agents',selected_matter_ids=['M1'])
    original=req.model_dump(mode='json')
    validate_retry_scope(original,req)
    changed=RunRequest.model_validate({**original,**change})
    with pytest.raises(HTTPException) as exc:validate_retry_scope(original,changed)
    assert exc.value.status_code==422


def test_question_reaches_every_role_and_changes_the_fixed_input_hash(reports):
    from backend.app.connectivity_matter_pipeline import run_matter_pipeline
    root,rs=reports;seen=[]
    def caller(role,payload):
        seen.append((role,deepcopy(payload['research_question'])))
        output,record=fake_provider(role,payload)
        output.tool_requests=[]
        return output,record
    req=request(rs,root=root,experiment_mode='fixed_evidence',research_question='合成问题一',question_id='Q1',benchmark_case_id='SYN-C')
    run=run_matter_pipeline(root,req,caller=caller)
    assert {r for r,_ in seen}=={'A1','A2','A3','A4','A5'}
    assert all(q['text']=='合成问题一' for _,q in seen)
    req.research_question='合成问题二'
    second=run_matter_pipeline(root,req,caller=caller)
    assert run.versions['fixed_input_sha256']!=second.versions['fixed_input_sha256']


def test_provider_settings_follow_the_selected_key_and_health_matches(monkeypatch):
    from backend.app.connectivity_matter_agents import matter_model_settings
    from backend.app.connectivity_app import health
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    monkeypatch.setenv('DEEPSEEK_BASE_URL','https://api.deepseek.com')
    monkeypatch.setenv('DEEPSEEK_MODEL','should-not-shadow')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-not-a-key')
    monkeypatch.setenv('OPENAI_BASE_URL','https://api.openai.com/v1')
    monkeypatch.setenv('OPENAI_MODEL','explicit-fixture-model')
    _,base,model=matter_model_settings()
    assert base=='https://api.openai.com/v1' and model=='explicit-fixture-model'
    assert health()['model_status']=='configured' and health()['model_id']==model
