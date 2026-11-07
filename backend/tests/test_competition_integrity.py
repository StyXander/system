"""Regression tests for experiment provenance; synthetic fixtures are not professional gold."""
import json
from pathlib import Path
import pytest
from scripts.evaluate_matter_benchmark import load_gold_cases, extract_run_verdict, evaluate_comparison, compute_binary_metrics, extract_verdict_from_assessment
from scripts.compute_iaa_metrics import compute_cohens_kappa, VERDICT_CLASSES
from backend.tests.test_matter_connectivity import reports


def test_engineering_expectations_cannot_become_gold(tmp_path):
    p=tmp_path/'gold.json'
    p.write_text(json.dumps({'scenarios':[{'case_id':'C','expected_engineering_behavior':'明示不可直接比','annotations':[]}]}))
    assert load_gold_cases(p)['C']['gold_verdict'] is None


def test_wrong_matter_never_falls_back_to_first():
    with pytest.raises(ValueError,match='MATTER_MAPPING_MISSING'):
        extract_run_verdict({'matter_assessments':[{'matter_id':'M1'}]},'M2')


def test_all_abstentions_have_undefined_fcr():
    result=compute_binary_metrics(['CONFIRMED_CONSISTENT'],['INSUFFICIENT_EVIDENCE'],{'CONFIRMED_CONSISTENT'})
    assert result['fcr'] is None
    assert result['coverage']==0
    assert result['recall']==0


def test_relationship_support_does_not_prove_numeric_equality():
    assert extract_verdict_from_assessment({'relation_support':'supported','amount_comparability':'comparable','supporting_evidence_ids':['E']})=='INSUFFICIENT_EVIDENCE'


def test_actual_schema_explanation_requires_supporting_evidence():
    assessment={'relation_support':'conflicting'}
    assert extract_verdict_from_assessment(assessment,[{'status':'supported_as_reported','supporting_evidence_ids':['E']}])=='EXPLAINED_DIFFERENCE'
    assert extract_verdict_from_assessment(assessment,[{'status':'supported_as_reported','supporting_evidence_ids':[]}])=='SUSPECTED_CONFLICT'


def test_summary_resolves_only_its_own_case_and_full_result(tmp_path):
    (tmp_path/'run.json').write_text(json.dumps({'run_id':'R','model_status':'five_agents_completed','matter_assessments':[{'matter_id':'M','relation_support':'supported','amount_comparability':'not_comparable'}]}))
    p=tmp_path/'comparison.json'
    p.write_text(json.dumps({'runs':[{'group_id':'G3','case_id':'C','matter_id':'M','run_id':'R','result_file':'run.json','repeat':1,'status':'recorded'}]}))
    gold={'C':{'gold_verdict':'NOT_COMPARABLE'},'UNRELATED':{'gold_verdict':'CONFIRMED_CONSISTENT'}}
    result=evaluate_comparison(p,gold)
    assert result['independent_cases']==1
    assert result['evaluations'][0]['classification']['accuracy']==1
    assert result['evaluations'][0]['attempted']==1


def test_failures_are_counted_not_converted_to_abstentions(tmp_path):
    p=tmp_path/'comparison.json';p.write_text(json.dumps({'runs':[{'group_id':'G3','case_id':'C','status':'failed','failure':'timeout'}]}))
    e=evaluate_comparison(p,{'C':{'gold_verdict':'NOT_COMPARABLE'}})['evaluations'][0]
    assert e['failed']==1 and e['completion_rate']==0 and e['classification'] is None


def test_nominal_labels_have_no_weighted_kappa():
    result=compute_cohens_kappa(VERDICT_CLASSES,VERDICT_CLASSES,VERDICT_CLASSES)
    assert result['cohens_kappa']==1 and result['weighted_kappa'] is None


def test_single_rater_is_not_independent_gold(tmp_path):
    p=tmp_path/'gold.json'
    p.write_text(json.dumps({'scenarios':[{'case_id':'C','annotations':[{'annotator_id':'one','verdict':'NOT_COMPARABLE'}]}]}))
    assert load_gold_cases(p)['C']['gold_verdict'] is None
    p.write_text(json.dumps({'scenarios':[{'case_id':'C','annotations':[{'annotator_id':'one','verdict':'NOT_COMPARABLE'}]*2}]}))
    assert load_gold_cases(p)['C']['gold_verdict'] is None


def test_kappa_is_undefined_when_both_raters_only_use_one_category():
    result=compute_cohens_kappa(['NOT_COMPARABLE']*2,['NOT_COMPARABLE']*2,VERDICT_CLASSES)
    assert result['percent_agreement']==1 and result['cohens_kappa'] is None


def test_restricted_pack_does_not_leave_dangling_seed_evidence(reports):
    from backend.tests.test_matter_connectivity import request,fake_provider
    from backend.app.connectivity_matter_pipeline import run_matter_pipeline
    from backend.app.connectivity_schemas import RunRequest
    root,rs=reports
    screened=run_matter_pipeline(root,RunRequest(report_set_id=rs.report_set_id,mode='calculation_only'))
    req=request(rs,root=root,experiment_mode='fixed_evidence',comparison_run=True)
    target=next(m for m in screened.matters if m.matter_id==req.selected_matter_ids[0])
    ids=target.evidence_ids+[next(e.evidence_id for e in screened.matter_evidence if e.report_type=='AR')]
    req.fixed_evidence_ids=ids
    run=run_matter_pipeline(root,req,caller=fake_provider)
    assert next(t for t in run.matter_tasks if t['role']=='A1')['status']=='completed'
    assert run.versions['fixed_evidence_excluded_seed_ids']
    assert all(set(m.evidence_ids)<=set(ids) for m in run.matters)


def test_combined_baseline_resolves_forward_event_and_path_ids_atomically(reports):
    from backend.app.connectivity_matter_pipeline import run_matter_pipeline
    from backend.app.connectivity_schemas import RunRequest
    from backend.app.connectivity_matter_schemas import AgentMatterResult
    from backend.app.connectivity_matters import integrate_combined_result
    root, rs=reports
    run=run_matter_pipeline(root,RunRequest(report_set_id=rs.report_set_id,mode='calculation_only'))
    matter=run.matters[0];eid=matter.evidence_ids[0]
    evidence=next(e for e in run.matter_evidence if e.evidence_id==eid)
    result=AgentMatterResult.model_validate({'matter_id':matter.matter_id,'input_revision':run.result_revision,
        'paths':[{'path_id':'temporary-path','matter_id':matter.matter_id,'financial_item':'固定资产',
                  'steps':[{'label':'待核实关联','evidence_ids':[eid]}]}],
        'events':[{'event_id':'temporary-event','matter_id':matter.matter_id,'kind':'action','label':'披露项目',
                   'report_period':evidence.report_period,'evidence_ids':[eid]}],
        'relations':[{'edge_id':'temporary-edge','matter_id':matter.matter_id,'source_id':'temporary-path',
                      'target_id':'temporary-event','relation_kind':'potential_mechanism',
                      'explanation':'待核实的关系','evidence_ids':[eid]}]})
    integrate_combined_result(run,matter,result,run.result_revision,('A2','A3','A4','A5'))
    edge=run.matter_relations[-1]
    assert edge.source_id==run.matter_paths[-1].path_id
    assert edge.target_id==run.matter_events[-1].event_id
    before=run.model_dump()
    result.relations[0].target_id='invented-node'
    with pytest.raises(ValueError,match='关系端点未登记'):
        integrate_combined_result(run,matter,result,run.result_revision,('A2','A3','A4','A5'))
    assert run.model_dump()==before
