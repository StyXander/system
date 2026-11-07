"""Server-side Decimal comparison of source occurrences with explicit semantic conditions.

No amount is accepted from the client or language model. Human-reviewed conditions
are labelled as user attestations and excluded from unattended AI benchmark results.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json

CONDITIONS={"主体","期间","范围","项目归属","计量基础","互不重叠"}
FACTORS={"元":Decimal(1),"千元":Decimal(1000),"万元":Decimal(10000),"亿元":Decimal(100000000)}
VERSION="matter_amount_v1"


def verify_amounts(run,plan):
    if run.result_revision!=plan.expected_revision:raise ValueError("金额核验绑定的结果版本已变化")
    if not any(m.matter_id==plan.matter_id for m in run.matters):raise ValueError("事项未登记")
    parts=[*plan.left,*plan.right];ids=[p.occurrence_id for p in parts]
    if len(set(ids))!=len(ids):raise ValueError("操作数重复或左右使用同一原值，不能自证一致")
    occurrences={o.occurrence_id:o for o in run.occurrences}
    if not set(ids)<=occurrences.keys():raise ValueError("操作数必须来自本运行定位的原值")
    rows=[occurrences[k] for k in ids]
    docs={d.document_id:d for d in run.documents}
    refs={e.evidence_id:e for e in run.matter_evidence if e.source_verified and not e.invalid_reason
          and e.document_id in docs and e.source_sha256==docs[e.document_id].file_sha256}
    if any(not set(v)<=refs.keys() for v in plan.condition_evidence.values()):raise ValueError("口径依据包含失效或未登记引用")
    if plan.reviewed_conditions and (not plan.actor.strip() or len(plan.reason.strip())<3):
        raise ValueError("人工口径复核须记录真实操作者和理由；不接受匿名自动确认")
    reviewed=set(plan.reviewed_conditions)
    if any(not plan.condition_evidence.get(k) for k in reviewed):raise ValueError("人工复核的每个条件都须有原文依据")
    guards=[]
    if run.versions.get('source_validity',{}).get('status')=='invalid':guards.append('source_invalid')
    for row in rows:
        if row.document_id not in docs or row.quality!='located':guards.append('unverified_occurrence')
        if not any(e.document_id==row.document_id and e.pdf_page==row.pdf_page for e in refs.values()):guards.append('missing_source_page')
        if row.value_qualifier in {'approximate','lower_bound','upper_bound'}:guards.append('non_exact_value')
        if row.unit not in FACTORS or not row.currency or row.currency_status in {'unknown','assumed'}:guards.append('unit_or_currency_unverified')
    years={r.year for r in rows};currencies={r.currency for r in rows}
    incompatible=[]
    if len(years)>1 and all(years):incompatible.append('period_mismatch')
    if any(not r.year or r.year_status!='attributed' for r in rows):guards.append('period_unverified')
    if len(currencies)>1 and all(currencies):incompatible.append('currency_mismatch')
    boundaries={r.report_boundary for r in rows}-{'unknown'}
    if len(boundaries)>1:incompatible.append('report_boundary_mismatch')
    companies={docs[r.document_id].company_id for r in rows if r.document_id in docs}
    if len(companies)>1:incompatible.append('subject_mismatch')
    values={}
    for row in rows:
        try:
            v=Decimal(str(row.value).replace(',',''))
            if not v.is_finite():raise InvalidOperation
            values[row.occurrence_id]=v*FACTORS.get(row.unit,Decimal(1))
        except (InvalidOperation,ValueError):guards.append('unparsed_value')
    def total(side):return sum((values[p.occurrence_id]*p.sign for p in side),Decimal(0))
    left=right=delta=tolerance=None
    if len(values)==len(rows):
        left,right=total(plan.left),total(plan.right);delta=left-right
        bounds=[]
        for row in rows:
            if row.rounding_method=='exact':bounds.append(Decimal(0))
            elif row.rounding_method=='half_up' and row.display_precision is not None:
                bounds.append(Decimal('0.5')*(Decimal(10)**(-row.display_precision))*FACTORS.get(row.unit,Decimal(1)))
            else:guards.append('rounding_unverified')
        if len(bounds)==len(rows):tolerance=sum(bounds,Decimal(0))
    missing=sorted(CONDITIONS-reviewed)
    if incompatible:verdict='NOT_COMPARABLE'
    elif guards or missing:verdict='INSUFFICIENT_EVIDENCE'
    elif abs(delta)<=tolerance:verdict='CONFIRMED_CONSISTENT'
    else:verdict='SUSPECTED_CONFLICT'
    serial=plan.model_dump(mode='json')
    proof={'record_id':'MAMT-'+hashlib.sha256(json.dumps(serial,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20],
        'matter_id':plan.matter_id,'input_revision':run.result_revision,'rule_version':VERSION,
        'verification_origin':'human_reviewed_conditions' if reviewed else 'program_arithmetic_only',
        'numeric_consistency':'consistent' if verdict=='CONFIRMED_CONSISTENT' else 'different' if verdict=='SUSPECTED_CONFLICT' else 'not_verified',
        'verdict':verdict,'formal':False,'currency':rows[0].currency if len(currencies)==1 else None,'normalized_unit':'元',
        'left_value':str(left) if left is not None else None,'right_value':str(right) if right is not None else None,
        'difference':str(delta) if delta is not None else None,'tolerance':str(tolerance) if tolerance is not None else None,
        'incompatible_conditions':sorted(set(incompatible)),'guards':sorted(set(guards)),
        'missing_semantic_review':missing,'conditions':{k:{'evidence_ids':plan.condition_evidence.get(k,[]),
             'review_status':'user_attested' if k in reviewed else 'unreviewed'} for k in sorted(CONDITIONS)},
        'review':{'actor':plan.actor,'reason':plan.reason,'identity_verified':False},
        'operands':[{'side':side,'occurrence_id':p.occurrence_id,'sign':p.sign,'value':occurrences[p.occurrence_id].value,
            'unit':occurrences[p.occurrence_id].unit,'document_id':occurrences[p.occurrence_id].document_id,
            'pdf_page':occurrences[p.occurrence_id].pdf_page,'source_sha256':docs[occurrences[p.occurrence_id].document_id].file_sha256 if occurrences[p.occurrence_id].document_id in docs else None}
             for side,items in [('left',plan.left),('right',plan.right)] for p in items],
        'notice':'程序核对所引原值及算术；口径复核为操作者声明，不等于身份认证、审计鉴证意见或企业真实入账。人工复核结果不并入纯AI实验。'}
    return proof
