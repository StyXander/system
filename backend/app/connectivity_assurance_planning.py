"""将保存的事项结论单向投影为鉴证前期两清单；不新增模型判断。"""
from __future__ import annotations
import hashlib

PLANNING_VERSION = 'assurance_planning_v1'


def build_assurance_planning(run):
    evidence = {e.evidence_id: e for e in run.matter_evidence}
    assessments = {a.matter_id: a for a in run.matter_assessments}
    findings, requests = [], {}
    reviews = run.assurance_planning_reviews
    def identity(kind, *parts):
        return kind+'-'+hashlib.sha256('|'.join(parts).encode()).hexdigest()[:20].upper()
    def refs(ids):
        return [dict(evidence_id=eid, document_id=evidence[eid].document_id,
                     pdf_page=evidence[eid].pdf_page, quote=evidence[eid].quote,
                     source_verified=evidence[eid].source_verified, invalid_reason=evidence[eid].invalid_reason)
                for eid in sorted(set(ids)) if eid in evidence]
    for matter in run.matters:
        assessment = assessments.get(matter.matter_id)
        paths = [p for p in run.matter_paths if p.matter_id == matter.matter_id]
        explanations = [h for h in run.matter_explanations if h.matter_id == matter.matter_id]
        # 初筛候选不是风险发现，未深查范围集中说明，避免淹没实际调查结果。
        investigated=assessment or paths or explanations or any(t.get('matter_id')==matter.matter_id for t in run.matter_tasks)
        if not investigated:
            continue
        reasons = list(assessment.unresolved) if assessment else ['综合复核未完成，当前只有待调查线索']
        reasons += [f'{p.financial_item}：财务传导仍有待证环节' for p in paths if p.support != 'supported']
        reasons += [h.explanation for h in explanations if h.status in {'challenged', 'unresolved'}]
        if assessment:
            reasons += assessment.disagreements
        if reasons:
            entry_id = identity('FINDING', matter.matter_id)
            support = assessment.supporting_evidence_ids if assessment else matter.evidence_ids
            counter = list(assessment.counter_evidence_ids) if assessment else []
            counter += [eid for h in explanations for eid in h.counter_evidence_ids]
            findings.append(dict(entry_id=entry_id, matter_ids=[matter.matter_id], matter=matter.name,
                reason='；'.join(dict.fromkeys(reasons)), current_assessment=assessment.summary if assessment else '',
                evidence=refs(support), counter_evidence=refs(counter),
                alternative_explanations=[h.explanation for h in explanations],
                unresolved=list(dict.fromkeys(reasons)), priority='high' if matter.attention_signals else 'medium',
                investigation_status=matter.investigation_status,
                review_status=reviews.get(entry_id, {}).get('status', 'unreviewed'),
                assessment_review_status=assessment.review_status if assessment else 'unreviewed'))
        for action in assessment.next_actions if assessment else []:
            key=' '.join(action.requested_material.split()).casefold()
            if key not in requests:
                entry_id=identity('REQUEST', key)
                requests[key]=dict(entry_id=entry_id, matter_ids=[], matters=[], requested_material=action.requested_material,
                    questions=[], purposes=[], distinguishing_explanations=[], priority=action.priority,
                    internal_target_roles=[], responsible_person='项目组待处理', acquisition_status='待取得',
                    review_status=reviews.get(entry_id, {}).get('status', 'unreviewed'))
            row=requests[key]
            for field,value in (('matter_ids',matter.matter_id),('matters',matter.name),('questions',action.question),
                                ('purposes',action.purpose),('internal_target_roles',action.target_role)):
                if value not in row[field]:row[field].append(value)
            for h in explanations:
                if h.discriminating_evidence and h.discriminating_evidence not in row['distinguishing_explanations']:
                    row['distinguishing_explanations'].append(h.discriminating_evidence)
            if {'high':0,'medium':1,'low':2}[action.priority] < {'high':0,'medium':1,'low':2}[row['priority']]:row['priority']=action.priority
    pending=[m for m in run.matters if not any(t.get('matter_id')==m.matter_id for t in run.matter_tasks)
             and m.matter_id not in assessments and not any(p.matter_id==m.matter_id for p in run.matter_paths)
             and not any(h.matter_id==m.matter_id for h in run.matter_explanations)]
    gaps=list(run.report_set.coverage_gaps) if run.report_set else []
    if pending:
        gaps.append(f'{len(pending)}项初筛候选尚未深查，保留在事项档案；未逐项列为风险发现，也不代表没有风险。')
    for gap in gaps:
        entry_id=identity('COVERAGE', gap)
        findings.append(dict(entry_id=entry_id,matter_ids=[],matter='本次资料覆盖',reason=gap,
            current_assessment='未取得的资料不等于企业未披露', evidence=[],counter_evidence=[],alternative_explanations=[],
            unresolved=[gap],priority='medium',investigation_status='partial',review_status=reviews.get(entry_id,{}).get('status','unreviewed')))
    return dict(schema_version=PLANNING_VERSION,result_revision=run.result_revision,
        risk_findings=findings,evidence_requests=list(requests.values()),
        notice='供可持续信息鉴证项目组前期准备与风险识别。优先级只表示调查顺序，不表示风险发生概率、重要性或鉴证结论。未取得资料不等于企业未披露。')
