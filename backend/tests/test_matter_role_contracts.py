import json
from contextlib import contextmanager

import pytest

from backend.tests.test_matter_connectivity import reports, request, fake_provider
from backend.app.connectivity_matter_pipeline import run_matter_pipeline
from backend.app.connectivity_matter_schemas import ROLE_RESULT_SCHEMAS, validate_role_result, AgentMatterResult, MatterToolCall
from backend.app.connectivity_matter_budget import allocate_role_budget
from backend.app.connectivity_matter_agents import call_matter_role, MatterCallFailure
from backend.app.connectivity_schemas import RunRequest


@pytest.mark.parametrize('role,expected',[
    ('A1',{'matters'}),('A2',{'paths','relations'}),('A3',{'events','commitments','relations'}),
    ('A4',{'explanations','relations'}),('A5',{'assessment'})])
def test_role_schema_rejects_another_roles_output(role,expected):
    schema=ROLE_RESULT_SCHEMAS[role]
    fields=set(schema.model_fields)-{'matter_id','input_revision','summary','tool_requests','stop_reason'}
    assert fields==expected
    value={'matter_id':'M','input_revision':1,'summary':'test','tool_requests':[]}
    for field in expected:value[field]=None if field=='assessment' else []
    forbidden=next(field for field in ('paths','events','matters','assessment') if field not in fields)
    value[forbidden]=[]
    with pytest.raises(ValueError):schema.model_validate(value)
    del value[forbidden];del value['input_revision']
    with pytest.raises(ValueError):schema.model_validate(value)


@pytest.mark.parametrize('kind,code,path',[
    ('json','MODEL_JSON_INVALID','tool_arguments'),('tool','MODEL_TOOL_REQUIRED','tool_calls'),
    ('fields','MODEL_FIELDS_INVALID','input_revision')])
def test_provider_errors_identify_role_and_field(monkeypatch,kind,code,path):
    import backend.app.connectivity_matter_agents as agents
    monkeypatch.setenv('DEEPSEEK_API_KEY','synthetic-key-not-a-credential')
    args='{' if kind=='json' else json.dumps({'matter_id':'','summary':'x','matters':[]})
    message={'tool_calls':[] if kind=='tool' else [{'function':{'name':'submit_matter_investigation','arguments':args}}]}
    raw=json.dumps({'choices':[{'message':message,'finish_reason':'tool_calls'}]}).encode()
    @contextmanager
    def response(*a,**k):
        yield type('Response',(),{'read':lambda self:raw})()
    monkeypatch.setattr(agents,'urlopen',response)
    with pytest.raises(MatterCallFailure) as captured:call_matter_role('A1',{})
    record=captured.value.record
    assert record['role']=='A1' and record['failure_code']==code
    assert any(path in e['location'] for e in record['invalid_fields'])


def test_no_selection_is_rejected_before_model_or_source_io(tmp_path):
    def forbidden(*a,**k):raise AssertionError('must not call model')
    with pytest.raises(ValueError,match='MATTER_SELECTION_REQUIRED'):
        run_matter_pipeline(tmp_path,RunRequest(pair_id='UNREGISTERED',mode='five_agents'),caller=forbidden)


def test_role_allocation_reserves_review_and_counter_budget():
    limits=allocate_role_budget(20)
    assert limits=={'A1':3,'A2':4,'A3':4,'A4':4,'A5':5}
    assert sum(limits.values())==20 and sum(limits[r] for r in ('A1','A2','A3'))==11


def test_single_matter_fresh_run_completes_five_roles_with_margin(reports):
    root,rs=reports
    run=run_matter_pipeline(root,request(rs,root=root),caller=fake_provider)
    assert run.parent_run_id is None and not run.prior_provider_calls
    assert run.model_status=='five_agents_completed'
    assert {t['role'] for t in run.matter_tasks if t['status']=='completed'}=={'A1','A2','A3','A4','A5'}
    assert len(run.provider_calls)<run.versions['budget']['limit']
    assert all(t.get('run_id')==run.run_id for t in run.matter_tasks)


def test_empty_tool_result_stops_investigation_then_synthesizes_once(reports):
    root,rs=reports;seen=[]
    def caller(role,payload):
        if role=='A2' and payload.get('finalize_only'):
            seen.append(payload.copy())
            return AgentMatterResult(matter_id=payload['matter_id'],input_revision=payload['input_revision'],summary='未取得新增证据，财务路径缺口保留。'),{'status':'completed','performed':True,'request_attempted':True}
        output,record=fake_provider(role,payload)
        if role=='A2':
            seen.append(payload.copy())
            if not payload.get('finalize_only'):
                output.tool_requests=[MatterToolCall(tool_name='search_matter_reports',arguments={'query':'不存在的XYZABCD'},reason='补查明确缺口')]
            else:output.tool_requests=[]
        return output,record
    run=run_matter_pipeline(root,request(rs,root=root),caller=caller)
    assert len(seen)==2 and seen[-1]['finalize_only']
    assert seen[-1]['missing_evidence_questions'][0]['question']=='补查明确缺口'
    assert next(t for t in run.matter_tasks if t['role']=='A2')['status']=='completed'


def test_year_rejection_keeps_field_path(reports):
    from backend.app.connectivity_matter_schemas import MatterEvent
    root,rs=reports
    def caller(role,payload):
        output,record=fake_provider(role,payload)
        if role=='A3':
            output.events=[MatterEvent(event_id='invented',matter_id=payload['matter_id'],kind='action',label='not supported year',
                report_period=payload['evidence'][0]['report_period'],occurred_period='2099',evidence_ids=[payload['evidence'][0]['evidence_id']])]
        return output,record
    run=run_matter_pipeline(root,request(rs,root=root),caller=caller)
    rejection=next(r for r in run.matter_rejections if r.get('code')=='EVENT_PERIOD_UNSUPPORTED')
    assert rejection['field_path']=='events.0.occurred_period' and rejection['role']=='A3'
    assert not any(e.occurred_period=='2099' for e in run.matter_events)
