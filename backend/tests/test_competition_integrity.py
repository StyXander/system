"""Regression tests for experiment provenance; synthetic fixtures are not professional gold."""
import json
from pathlib import Path
import pytest
from scripts.evaluate_matter_benchmark import load_gold_cases, extract_run_verdict, evaluate_comparison, compute_binary_metrics, extract_verdict_from_assessment
from scripts.compute_iaa_metrics import compute_cohens_kappa, VERDICT_CLASSES


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
    (tmp_path/'run.json').write_text(json.dumps({'run_id':'R','matter_assessments':[{'matter_id':'M','relation_support':'supported','amount_comparability':'not_comparable'}]}))
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
