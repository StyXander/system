"""Synthetic fixtures verify the recorder importer; these are not participant results."""
import pytest
from scripts.analyze_human_validation import analyze


def manifest():
    return {'scenarios':[{'case_id':c,'question_id':c+'-Q','question':'合成问题'+c,'research_task_type':'relation_tracing','annotations':[]} for c in ['SYN-1','SYN-2']]}


def response(case='SYN-1',actor='synthetic-person',purpose='annotation',condition='manual'):
    return {'purpose':purpose,'case_id':case,'question_id':case+'-Q','question':'合成问题'+case,
        'participant_id':actor,'session_id':case+'-'+condition,'condition':condition,'verdict':'pending',
        'reason':'合成测试的判断理由','started_at':'2026-01-01T09:00:00Z','submitted_at':'2026-01-01T09:15:00Z'}


def review(row,**kwargs):
    return {'purpose':'review','session_id':row['session_id'],'reviewer_id':'synthetic-reviewer',
        'quality_accepted':True,'major_errors':0,'conclusion_correct':True,'evidence_supported':True,**kwargs}


def test_empty_forms_are_not_completed_human_research():
    gold,r=analyze(manifest(),[])
    assert r['annotation_status']==r['human_comparison_status']=='not_evaluated'
    assert r['independently_double_annotated_cases']==0
    assert r['groups']['manual']['qualified_delivery_rate'] is None
    assert all(not c['annotations'] for c in gold['scenarios'])


def test_same_annotator_cannot_count_twice():
    row=response()
    with pytest.raises(ValueError,match='DUPLICATE_ANNOTATOR_CASE'):analyze(manifest(),[row,row])
    _,r=analyze(manifest(),[row,response(actor='synthetic-other')])
    assert r['independently_double_annotated_cases']==1


def test_question_must_match_the_manifest():
    row=response();row['question']='合成篡改问题'
    with pytest.raises(ValueError,match='QUESTION_IDENTITY_MISMATCH'):analyze(manifest(),[row])


def test_time_without_independent_quality_review_is_not_a_success():
    _,r=analyze(manifest(),[response(purpose='timed_study')])
    assert r['groups']['manual']['attempted']==1
    assert r['groups']['manual']['quality_accepted']==0
    assert r['groups']['manual']['elapsed_minutes_all']==[15]
    assert r['excluded_or_pending'][0]['reason']=='awaiting_independent_quality_review'


def test_self_review_or_false_quality_does_not_count_as_accepted():
    row=response(purpose='timed_study')
    _,r=analyze(manifest(),[row,review(row,reviewer_id=row['participant_id'])])
    assert r['groups']['manual']['quality_accepted']==0
    _,r=analyze(manifest(),[row,review(row,evidence_supported=False)])
    assert r['groups']['manual']['quality_accepted']==0


def test_different_accepted_tasks_only_yield_descriptive_paired_times():
    a=response(purpose='timed_study');b=response('SYN-2',purpose='timed_study',condition='assisted')
    _,r=analyze(manifest(),[a,b,review(a),review(b)])
    assert r['human_comparison_status']=='descriptive_results'
    assert r['paired_participants'][0]['difference_minutes']==0
    assert 'causal' in r['limitation']


def test_repeating_the_same_task_or_prior_gold_annotation_is_excluded():
    a=response(purpose='timed_study');b=response(purpose='timed_study',condition='assisted')
    _,r=analyze(manifest(),[a,b,review(a),review(b)])
    assert r['human_comparison_status']=='not_evaluated'
    assert r['excluded_or_pending'][0]['reason']=='same_case_repeated_learning_effect'
    _,r=analyze(manifest(),[response(),a,review(a)])
    assert r['groups']['manual']['quality_accepted']==0
