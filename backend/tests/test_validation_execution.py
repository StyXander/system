"""Synthetic component and integration regressions; not enterprise or human gold."""
from copy import deepcopy
import json
from io import BytesIO
import pytest
from backend.tests.test_matter_connectivity import reports,request,fake_provider
from backend.app.connectivity_matter_pipeline import run_matter_pipeline
from backend.app.connectivity_matter_tables import extract_rows,parse_cell
from backend.app.connectivity_matter_amounts import verify_amounts,CONDITIONS
from backend.app.connectivity_matter_schemas import AmountVerificationRequest
from backend.app.connectivity_schemas import DisclosureOccurrence
from backend.app.connectivity_read_models import project_result
from scripts.evaluate_matter_benchmark import load_gold_cases,evaluate_comparison


def table(rows=None):
    rows=rows or [['项目名称','期初余额','本期增加','转入固定资产','长期待摊','其他减少','期末余额'],
                 ['绿色生产线改造项目','100.00','50.00','20.00','0.00','0.00','130.00']]
    return extract_rows(rows,queries=['绿色生产线改造项目'],page_text='单位：万元 币种：人民币',
        document_id='SYN-AR',source_sha256='synthetic',page=17,table_id='T1')


def test_generic_row_has_no_company_or_page_requirement():
    row=table()[0]
    assert row['source_page']==17 and row['unit']=='万元'
    assert row['arithmetic']['status']=='exact_display_match'
    assert row['arithmetic']['difference']=='0.00'
    assert row['cross_report_identity']=='unverified'


def test_dash_or_absent_decrease_column_does_not_become_zero():
    row=table([['项目','期初余额','本期增加','转入固定资产','期末余额'],
               ['绿色生产线改造项目','100','50','20','—']])[0]
    assert row['values']['closing'] is None
    assert row['arithmetic']['difference'] is None
    assert {'other_decrease','to_long_term','closing'}<=set(row['arithmetic']['missing'])


def test_punctuation_layout_and_amount_like_labels_are_not_guessed():
    assert parse_cell('1 326 600 000 00\n, , , .')=='1326600000.00'
    assert parse_cell('—') is None and parse_cell('约100') is None


def test_ambiguous_page_units_are_kept_unknown():
    rows=[['项目','期初余额','本期增加','期末余额'],['绿色生产线改造项目','1','2','3']]
    r=extract_rows(rows,queries=['绿色生产线改造项目'],page_text='单位：元 单位：万元',document_id='S',source_sha256='x',page=1,table_id='T')[0]
    assert r['unit'] is None and r['unit_status']=='unverified'


def numeric_fixture(reports):
    root,rs=reports;run=run_matter_pipeline(root,request(rs,root=root),caller=fake_provider)
    m=run.matters[0];es=run.matter_evidence[:2]
    for i,e in enumerate(es):
        run.occurrences.append(DisclosureOccurrence(occurrence_id=f'SYN-N{i}',document_id=e.document_id,
            pdf_page=e.pdf_page,label='合成核验原值',value='100.00',value_qualifier='exact',unit='元',currency='CNY',
            currency_status='explicit',unit_status='explicit',year='2025',year_status='attributed',
            scope='同一合成项目',report_boundary='consolidated',rounding_method='exact',quality='located',context=e.quote))
    body=AmountVerificationRequest(expected_revision=run.result_revision,action_id='synthetic-operation',matter_id=m.matter_id,
        left=[{'occurrence_id':'SYN-N0'}],right=[{'occurrence_id':'SYN-N1'}],
        condition_evidence={k:[es[0].evidence_id,es[1].evidence_id] for k in CONDITIONS})
    return run,body


def test_numeric_equality_without_semantic_review_is_conditional(reports):
    run,body=numeric_fixture(reports);proof=verify_amounts(run,body)
    assert proof['difference']=='0.00' and proof['verdict']=='INSUFFICIENT_EVIDENCE'
    assert proof['numeric_consistency']=='not_verified' and not proof['formal']


def test_reviewed_numeric_comparison_records_the_user_attestation(reports):
    run,body=numeric_fixture(reports);body.reviewed_conditions=sorted(CONDITIONS)
    body.actor='合成测试操作者';body.reason='仅用于回归，不属于真实专家意见'
    proof=verify_amounts(run,body)
    assert proof['verdict']=='CONFIRMED_CONSISTENT'
    assert proof['verification_origin']=='human_reviewed_conditions'
    assert proof['review']['identity_verified'] is False
    assert not proof['formal']
    run.occurrences[-1].value='110.00'
    assert verify_amounts(run,body)['verdict']=='SUSPECTED_CONFLICT'


@pytest.mark.parametrize('change,expected',[
    ({'year':'2024'},'NOT_COMPARABLE'),
    ({'rounding_method':'unknown'},'INSUFFICIENT_EVIDENCE'),
    ({'value_qualifier':'approximate'},'INSUFFICIENT_EVIDENCE'),
    ({'currency_status':'assumed'},'INSUFFICIENT_EVIDENCE'),
    ({'report_boundary':'parent'},'NOT_COMPARABLE')])
def test_review_cannot_override_program_guards(reports,change,expected):
    run,body=numeric_fixture(reports);body.reviewed_conditions=sorted(CONDITIONS);body.actor='合成测试';body.reason='合成边界测试'
    for k,v in change.items():setattr(run.occurrences[-1],k,v)
    assert verify_amounts(run,body)['verdict']==expected


def test_same_number_cannot_prove_itself_and_fabricated_refs_are_rejected(reports):
    run,body=numeric_fixture(reports)
    body.right=deepcopy(body.left)
    with pytest.raises(ValueError,match='重复'):verify_amounts(run,body)
    body.right=[type(body.left[0])(occurrence_id='SYN-N1')]
    body.condition_evidence={'主体':['invented']}
    with pytest.raises(ValueError,match='引用'):verify_amounts(run,body)


def test_question_and_numeric_records_survive_projection_and_exports(reports):
    from backend.app.connectivity_delivery import export_run
    from docx import Document
    run,body=numeric_fixture(reports);run.matter_numeric_verifications=[verify_amounts(run,body)]
    run.versions['research_question']={'text':'合成测试问题','task_type':'amount_reconciliation'}
    view=project_result(run.model_dump(mode='json'),'detail',body.matter_id)
    assert view['versions']['research_question']['text']=='合成测试问题'
    assert view['matter_numeric_verifications'][0]['matter_id']==body.matter_id
    assert len(view['occurrences'])==2
    binary,_=export_run(run,'docx');text=''.join(p.text for p in Document(BytesIO(binary)).paragraphs)
    assert '合成测试问题' in text and '原值金额核验记录' in text
    csv,_=export_run(run,'csv');assert b'matter_numeric_verifications' in csv


def test_relation_task_has_its_own_labels_and_no_numeric_fcr(tmp_path):
    gold=tmp_path/'gold.json'
    gold.write_text(json.dumps({'scenarios':[{'case_id':'SYN-C','research_task_type':'relation_tracing','annotations':[
        {'annotator_id':'synthetic-A','verdict':'supported'},{'annotator_id':'synthetic-B','verdict':'supported'}]}]}))
    run={'run_id':'SYN-R','model_status':'five_agents_completed','matter_assessments':[{'matter_id':'SYN-M','relation_support':'supported'}]}
    (tmp_path/'run.json').write_text(json.dumps(run))
    p=tmp_path/'comparison.json';p.write_text(json.dumps({'runs':[{'group_id':'G3','case_id':'SYN-C','matter_id':'SYN-M','run_id':'SYN-R','result_file':'run.json','status':'recorded'}]}))
    result=evaluate_comparison(p,load_gold_cases(gold))['evaluations'][0]
    assert result['classification']['accuracy']==1 and result['confirmation'] is None
    assert result['end_to_end_correct_rate']==1
