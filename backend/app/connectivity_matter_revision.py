"""人工归并与拆分产生子版本；阅读采用不改变证据或计算状态。

人工归并和拆分保存成子结果，原运行继续用于历史回查。
结果版本与动作幂等键共同防止并发覆盖同一父版本。
改变事项身份会清除受影响的派生意见，重新进入待调查状态。
人工采用只记录阅读和使用决定，不增强原文支持程度。
数值调节只使用本运行定位的原值，重复操作数和混合口径被拒绝。
条件试算不会回写正式差额、企业实际影响或会计确认结论。
"""
from __future__ import annotations

from .connectivity_matter_extraction import digest
from .connectivity_matters import attach_events,finish_projection


def revise_matters(run, body):
    """在当前结果副本中执行经版本校验的人工处理。
    归并与拆分会使受影响的派生结论重新进入调查，原运行不变。
    采用与驳回只改变阅读记录，不提升证据支持或金额资格。
    动作身份和父子保存由API统一处理，函数不另写任务台账。
    """
    if run.result_revision!=body.expected_revision:raise ValueError("事项结果版本已变化")
    selected=[m for m in run.matters if m.matter_id in body.matter_ids]
    if len(selected)!=len(set(body.matter_ids)):raise ValueError("事项未登记")
    if body.action.startswith("planning_"):
        from .connectivity_assurance_planning import build_assurance_planning
        from .connectivity_schemas import now_iso
        planning=build_assurance_planning(run)
        entries={row['entry_id']:row for key in ('risk_findings','evidence_requests') for row in planning[key]}
        if not body.planning_entry_ids or not set(body.planning_entry_ids)<=entries.keys():
            raise ValueError("清单条目未登记")
        if any(not set(entries[key]['matter_ids'])<=set(body.matter_ids) for key in body.planning_entry_ids):
            raise ValueError("清单条目与所选事项不一致")
        for key in body.planning_entry_ids:
            run.assurance_planning_reviews[key]={'status':{'planning_adopt':'adopted','planning_defer':'deferred','planning_exclude':'excluded'}[body.action],
                'actor':body.actor,'reason':body.reason,'updated_at':now_iso()}
    elif body.action in {"accept","reject"}:
        count=0
        for assessment in run.matter_assessments:
            if assessment.matter_id in body.matter_ids:
                assessment.review_status="accepted" if body.action=="accept" else "rejected";count+=1
        if not count:raise ValueError("所选事项没有可采用的综合意见")
    else:
        if len({m.company_id for m in selected})!=1:raise ValueError("不能合并不同企业事项")
        all_ids=sorted({k for m in selected for k in m.evidence_ids})
        if body.action=="merge":
            if len(selected)<2:raise ValueError("归并至少需要两个事项")
            merged=selected[0].model_copy(deep=True)
            merged.matter_id="MAT-"+digest("merge|"+"|".join(sorted(body.matter_ids)))
            merged.evidence_ids=all_ids;merged.aliases=sorted({m.name for m in selected}|set(merged.aliases))
            children=[merged]
        else:
            if len(selected)!=1 or not body.evidence_ids or not set(body.evidence_ids)<set(all_ids):
                raise ValueError("拆分需要一个事项，以及严格属于该事项的部分证据")
            children=[]
            for i,ids in enumerate([body.evidence_ids,sorted(set(all_ids)-set(body.evidence_ids))],1):
                child=selected[0].model_copy(deep=True);child.matter_id="MAT-"+digest("split|"+"|".join(sorted(ids)))
                child.name+=f" 分项{i}";child.evidence_ids=ids;children.append(child)
        run.matters=[m for m in run.matters if m.matter_id not in body.matter_ids]+children
        for field in ("matter_events","matter_commitments","matter_paths","matter_relations","matter_explanations","matter_assessments"):
            setattr(run,field,[obj for obj in getattr(run,field) if obj.matter_id not in body.matter_ids])
        for m in children:
            m.identity_status="human_confirmed";m.identity_basis=body.reason;m.lineage+=body.matter_ids
            m.investigation_status="pending";m.event_ids=[];attach_events(run,m)
        run.model_status="five_agents_partial"
    run.matter_revisions.append({"action_id":body.action_id,"action":body.action,"matter_ids":body.matter_ids,
        "reason":body.reason,"actor":body.actor,"planning_entry_ids":body.planning_entry_ids,
        "input_revision":body.expected_revision})
    finish_projection(run)


def reconcile_matter(run, plan):
    """只复算已定位原值；身份与调节语义未复核时仍为条件试算。"""
    from decimal import Decimal,InvalidOperation
    matter=next((m for m in run.matters if m.matter_id==plan.matter_id),None)
    if matter is None:raise ValueError("事项未登记")
    refs={e.evidence_id:e for e in run.matter_evidence if e.source_verified and not e.invalid_reason}
    if not set(plan.identity_evidence_ids)<=refs.keys():raise ValueError("身份依据无效")
    rows={o.occurrence_id:o for o in run.occurrences}
    ids=[o.occurrence_id for o in plan.operands]
    if len(ids)!=len(set(ids)):raise ValueError("操作数重复，可能重复计量")
    if not all(k in rows for k in ids):raise ValueError("操作数不是本运行定位的数值")
    values=[rows[k] for k in ids]
    if len({(o.year,o.scope,o.unit,o.currency) for o in values})!=1:
        raise ValueError("期间、范围、单位或币种不同，拒绝直接加总")
    if any(not o.year or not o.scope or not o.unit or o.value_qualifier in {"approximate","lower_bound","upper_bound"} for o in values):
        raise ValueError("操作数计量身份或精确性不足")
    needed={"主体","期间","计量基础","项目归属","互不重叠"}
    if not needed<=plan.condition_evidence.keys() or any(not plan.condition_evidence[k] or not set(plan.condition_evidence[k])<=refs.keys() for k in needed):
        raise ValueError("调节缺少可回查的身份、期间、计量基础或去重证据")
    if not plan.measurement_basis.strip() or not plan.deduplication_basis.strip():raise ValueError("须说明计量与去重依据")
    try:
        result=sum((Decimal(rows[o.occurrence_id].value.replace(",",""))*o.sign for o in plan.operands),Decimal(0))
    except (InvalidOperation,AttributeError):raise ValueError("原文数值不能复算")
    return {"matter_id":plan.matter_id,"result_revision":run.result_revision,"result":str(result),"unit":values[0].unit,
        "operands":[{"occurrence_id":o.occurrence_id,"sign":o.sign,"value":rows[o.occurrence_id].value} for o in plan.operands],
        "classification":"conditional_calculation","formal":False,"measurement_basis":plan.measurement_basis,
        "deduplication_basis":plan.deduplication_basis,"evidence_ids":sorted(set(plan.identity_evidence_ids)),
        "notice":"算术已复算；项目归属与互不重叠的语义仍需专业复核，不写入企业实际影响或正式差额"}
