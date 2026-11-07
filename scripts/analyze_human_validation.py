"""Import actual participant exports and separate independent labels from timed studies.

Empty inputs yield not_evaluated. This tool validates records, not a person's identity
or the truth of their professional opinion. No AI-generated labels are supplied.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import statistics


def analyze(manifest,responses):
    cases={c['case_id']:c for c in manifest['scenarios']}
    answers=defaultdict(dict);sessions=[];reviews={};seen_sessions=set()
    for row in responses:
        purpose=row.get('purpose')
        if purpose=='review':
            if not row.get('session_id') or not row.get('reviewer_id') or not isinstance(row.get('quality_accepted'),bool):
                raise ValueError('QUALITY_REVIEW_INCOMPLETE')
            if row['session_id'] in reviews:raise ValueError('DUPLICATE_QUALITY_REVIEW')
            reviews[row['session_id']]=row;continue
        if purpose not in {'annotation','timed_study'}:raise ValueError('UNKNOWN_RESPONSE_PURPOSE')
        case=cases.get(row.get('case_id'))
        if not case or row.get('question_id')!=case['question_id'] or row.get('question')!=case['question']:
            raise ValueError('QUESTION_IDENTITY_MISMATCH')
        actor=str(row.get('participant_id') or '').strip()
        if not actor or len(str(row.get('reason') or '').strip())<3:raise ValueError('PARTICIPANT_OR_REASON_MISSING')
        labels=['supported','limited','pending','conflicting','not_comparable','invalid'] if case.get('research_task_type')=='relation_tracing' else ['CONFIRMED_CONSISTENT','SUSPECTED_CONFLICT','INSUFFICIENT_EVIDENCE','NOT_COMPARABLE','EXPLAINED_DIFFERENCE']
        if row.get('verdict') not in labels:raise ValueError('INVALID_TASK_LABEL')
        if purpose=='annotation':
            if actor in answers[case['case_id']]:raise ValueError('DUPLICATE_ANNOTATOR_CASE')
            answers[case['case_id']][actor]={'annotator_id':actor,'verdict':row['verdict'],
                'reason':row['reason'],'evidence_refs':row.get('evidence_refs',[]),'completed_at':row.get('submitted_at'),
                'origin':'participant_file','identity_verified':False}
        else:
            sid=row.get('session_id')
            if not sid or sid in seen_sessions:raise ValueError('DUPLICATE_OR_MISSING_SESSION')
            seen_sessions.add(sid)
            if row.get('condition') not in {'manual','assisted'}:raise ValueError('CONDITION_MISSING')
            start=datetime.fromisoformat(row['started_at'].replace('Z','+00:00'))
            end=datetime.fromisoformat(row['submitted_at'].replace('Z','+00:00'))
            elapsed=(end-start).total_seconds()/60
            if elapsed<=0:raise ValueError('INVALID_ELAPSED_TIME')
            sessions.append({**row,'elapsed_minutes':elapsed})
    annotated=[]
    for case in cases.values():
        copied={**case,'annotations':list(answers[case['case_id']].values())}
        # Preserve supplied adjudication; do not invent one from participant scores.
        annotated.append(copied)
    history=set();eligible=[];excluded=[]
    for row in sessions:
        key=(row['participant_id'],row['case_id'])
        review=reviews.get(row['session_id'])
        issue=None
        if key in history:issue='same_case_repeated_learning_effect'
        elif row['participant_id'] in answers[row['case_id']]:issue='participant_already_annotated_this_case'
        elif not review:issue='awaiting_independent_quality_review'
        elif review['reviewer_id']==row['participant_id']:issue='participant_cannot_grade_own_work'
        elif review.get('major_errors') is None or type(review.get('major_errors')) is not int or review['major_errors']<0:issue='major_error_review_missing'
        elif (not review['quality_accepted'] or review['major_errors']>0 or
              review.get('conclusion_correct') is not True or review.get('evidence_supported') is not True):issue='quality_not_accepted'
        history.add(key)
        if issue:excluded.append({'session_id':row['session_id'],'reason':issue})
        else:eligible.append({**row,'quality_review':review})
    groups={}
    for condition in ['manual','assisted']:
        attempted=[s for s in sessions if s['condition']==condition]
        accepted=[s for s in eligible if s['condition']==condition]
        groups[condition]={'attempted':len(attempted),'quality_accepted':len(accepted),
            'qualified_delivery_rate':len(accepted)/len(attempted) if attempted else None,
            'elapsed_minutes_all':[s['elapsed_minutes'] for s in attempted],
            'median_qualified_minutes':statistics.median(s['elapsed_minutes'] for s in accepted) if accepted else None}
    paired=[]
    for actor in sorted({s['participant_id'] for s in eligible}):
        manual=[s['elapsed_minutes'] for s in eligible if s['participant_id']==actor and s['condition']=='manual']
        assisted=[s['elapsed_minutes'] for s in eligible if s['participant_id']==actor and s['condition']=='assisted']
        if manual and assisted:
            a,b=statistics.median(manual),statistics.median(assisted)
            paired.append({'participant_id':actor,'manual_median_minutes':a,'assisted_median_minutes':b,
                           'difference_minutes':b-a,'interpretation':'different matched tasks; review comparability before attributing an effect'})
    report={'annotation_status':'participants_received' if any(answers.values()) else 'not_evaluated',
        'cases':len(cases),'independently_double_annotated_cases':sum(len(a)>=2 for a in answers.values()),
        'human_comparison_status':'descriptive_results' if paired else 'not_evaluated',
        'groups':groups,'paired_participants':paired,'excluded_or_pending':excluded,
        'limitation':'Participant files are self-reported; identity and actual use require real participant confirmation. No inference of professional certification or causal efficiency gain.'}
    return {'dataset_version':manifest.get('dataset_version'),'scenarios':annotated},report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--responses-dir',type=Path,required=True)
    p.add_argument('--gold-output',type=Path,required=True);p.add_argument('--report-output',type=Path,required=True)
    a=p.parse_args();responses=[]
    if a.responses_dir.exists():
        for path in sorted(a.responses_dir.glob('*.json')):
            value=json.loads(path.read_text());responses.extend(value if isinstance(value,list) else [value])
    gold,report=analyze(json.loads(a.manifest.read_text()),responses)
    for path,value in [(a.gold_output,gold),(a.report_output,report)]:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
