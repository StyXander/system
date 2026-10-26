"""统一事项档案、候选归并、引用校验及结果投影。

同名和同金额仅能形成候选，不自动证明跨期事项身份。
归并需要各份证据的主体、地点与名称依据，未归并项保留。
专业路径逐段存证，企业陈述与模型机制推演使用不同来源类型。
每次角色合并使用独立副本，任何校验失败均不留下半份建议。
综合意见、金额可比性及人工采用保持独立，不互相覆盖。
图谱与概览从保存对象投影，前端不补造财务节点或结论。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re

from .connectivity_matter_extraction import compact, digest, MATTER_TERMS
from .connectivity_matter_schemas import (SustainabilityMatter, MatterEvent, MatterCommitment,
    MatterAssessment, NextAction, AgentMatterResult)


def classify(text):
    for kind in ("climate_risk", "transition_project", "commitment", "resource_efficiency"):
        if any(word in text for word in MATTER_TERMS[kind]):
            return kind
    return "other"


def project_label(text):
    quoted = re.search(r"[“「《]([^”」》]{3,55}(?:项目|工程|改造))[^”」》]*[”」》]", text)
    if quoted:
        return quoted.group(1)
    candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{3,30}(?:改造项目|技改项目|建设项目|治理工程|节能工程)", compact(text))
    return candidates[0] if candidates else ""


def seed_matters(evidence, matter_types):
    """按披露保留候选；没有明确身份时不自动跨年度合并。"""
    found = {}
    for b in evidence:
        kind = classify(b.quote)
        if kind not in matter_types:
            continue
        name = project_label(b.quote)
        named = bool(name)
        if not name:
            labels = {"climate_risk":"气候风险披露", "transition_project":"绿色改造披露", "commitment":"目标与承诺披露",
                      "resource_efficiency":"资源与绩效披露", "other":"财务估计与附注线索"}
            name = f"{labels[kind]} · {b.report_period} · PDF {b.pdf_page}"
        # 即使名称相同，也先按披露位置留候选，归并由A1或人工提供身份依据。
        key = "MAT-" + digest(f"{b.company_id}|{b.evidence_id}|{name}")
        found[key] = SustainabilityMatter(matter_id=key, company_id=b.company_id, name=name,
            matter_type=kind, evidence_ids=[b.evidence_id],
            identity_basis="项目名是归并线索，主体与地点仍需核对" if named else "按单处披露建候选，尚未确认跨报告身份")
    return list(found.values())


def attach_events(run, matter):
    evidence = {b.evidence_id:b for b in run.matter_evidence}
    for eid in matter.evidence_ids:
        b = evidence[eid]
        text = compact(b.quote)
        if re.search(r"(?:调整目标|修订目标|重述|变更基准年)",text):kind="revision"
        elif re.search(r"(?:终止|取消项目|停止建设)",text):kind="termination"
        elif re.search(r"(?:目标|承诺|计划|拟|将于|到20\d{2}年)", text):kind="promise"
        elif re.search(r"(?:投运|投产|转固|达到预定可使用状态)",text):kind="commissioning"
        elif re.search(r"(?:减值|折旧|寿命|预计负债|在建工程|资本开支)",text):kind="financial"
        elif matter.matter_type=="climate_risk":kind="risk"
        elif re.search(r"(?:实际|完成|降低|节约|下降)",text):kind="performance"
        else:kind="action"
        event_id="EV-"+digest(matter.matter_id+eid+kind)
        if any(e.event_id==event_id for e in run.matter_events):continue
        # 发生期间未知保留空值；报告年度仅用于定位披露。
        run.matter_events.append(MatterEvent(event_id=event_id,matter_id=matter.matter_id,kind=kind,
            label=b.quote[:180],report_period=b.report_period,disclosure_date=b.disclosure_date,evidence_ids=[eid]))
        matter.event_ids.append(event_id)
        if kind=="promise":
            target=re.search(r"(?:到|截至|于|在)\s*(20\d{2})\s*年[^。；]{0,40}(?:目标|实现|完成|达到)|(?:目标|计划|承诺)[^。；]{0,35}?(20\d{2})年",text)
            baseline=re.search(r"(?:较|以|基准年为|基期为)\s*(20\d{2})年",text)
            year=next((v for v in target.groups() if v),"") if target else ""
            cid="COM-"+digest(matter.matter_id+eid)
            run.matter_commitments.append(MatterCommitment(commitment_id=cid,matter_id=matter.matter_id,
                label=b.quote[:400],evidence_ids=[eid],proposed_period=b.report_period,
                baseline_year=baseline.group(1) if baseline else "",target_year=year,
                status="not_due" if year and int(year)>run.report_set.as_of_date.year else "needs_review"))


def apply_identification(run, proposals):
    evidence={b.evidence_id:b for b in run.matter_evidence if b.source_verified and not b.invalid_reason}
    if not proposals:return
    identified=[];used=set()
    for proposal in proposals:
        refs=[evidence.get(k) for k in proposal.evidence_ids]
        if any(b is None for b in refs) or len({b.company_id for b in refs})!=1:
            run.matter_rejections.append({"role":"A1","reason":"事项身份引用缺失或跨主体","name":proposal.name});continue
        # 多个地点若没有明确身份说明不能被金额相同替代。
        if len(refs)>1 and not all(any(compact(alias) in compact(b.quote) for alias in [proposal.name,*proposal.aliases]
                                  if len(alias)>=3) for b in refs):
            run.matter_rejections.append({"role":"A1","reason":"归并缺少可定位的项目名或别名锚点","name":proposal.name});continue
        if len(refs)>1 and any(anchor and not all(compact(anchor) in compact(b.context or b.quote) for b in refs)
                               for anchor in (proposal.subject,proposal.location)):
            run.matter_rejections.append({"role":"A1","reason":"归并主体或地点未在每份证据中定位","name":proposal.name});continue
        key="MAT-"+digest(f"{refs[0].company_id}|{proposal.name}|{proposal.subject}|{proposal.location}")
        if any(m.matter_id==key for m in identified):
            run.matter_rejections.append({"role":"A1","reason":"重复事项身份建议","name":proposal.name});continue
        identified.append(SustainabilityMatter(matter_id=key,company_id=refs[0].company_id,name=proposal.name,
            matter_type=proposal.matter_type,subject=proposal.subject,location=proposal.location,aliases=proposal.aliases,
            identity_status="evidence_linked",identity_basis=proposal.identity_basis,evidence_ids=proposal.evidence_ids,
            lineage=[m.matter_id for m in run.matters if set(m.evidence_ids)<=set(proposal.evidence_ids)]))
        used.update(proposal.evidence_ids)
    if identified:
        # 未归并候选保留，不能通过删除未调查资料改善覆盖数字。
        run.matters=identified+[m for m in run.matters if not set(m.evidence_ids)<=used]
        run.matter_events=[];run.matter_commitments=[]
        for m in run.matters:m.event_ids=[];attach_events(run,m)


def _all_refs(value):
    if isinstance(value,dict):
        for k,v in value.items():
            if k.endswith("evidence_ids") and isinstance(v,list):yield from v
            else:yield from _all_refs(v)
    elif isinstance(value,list):
        for item in value:yield from _all_refs(item)


def integrate_result(run, matter, role, result:AgentMatterResult, expected_revision):
    # 一份角色建议整体校验，失败不得留下半份路径或修改共享状态。
    """在副本上校验并整体提交角色建议。
    任何引用、事项或版本不一致都会拒绝整份建议。
    共享写入由主管线加锁，本函数只负责对象层的一致性。
    拒绝结果不得留下已经添加的第一条路径或修改旧承诺。
    """
    working=run.model_copy(deep=True)
    target=next(m for m in working.matters if m.matter_id==matter.matter_id)
    _integrate_result(working,target,role,result.model_copy(deep=True),expected_revision)
    for field in ("matter_paths","matter_events","matter_commitments","matter_explanations","matter_relations","matter_assessments"):
        setattr(run,field,getattr(working,field))


def _integrate_result(run, matter, role, result:AgentMatterResult, expected_revision):
    if result.input_revision!=expected_revision or result.matter_id not in {"",matter.matter_id}:
        raise ValueError("角色结果对应的事项或输入版本已变化")
    refs={b.evidence_id:b for b in run.matter_evidence if b.source_verified and not b.invalid_reason}
    requested=set(_all_refs(result.model_dump()))
    if not requested<=refs.keys():
        raise ValueError("角色结果含未取得、未核验或失效引用")
    if any(refs[k].company_id!=matter.company_id for k in requested):
        raise ValueError("角色引用跨企业证据")
    if role=="A2":
        from .connectivity_financial_ontology import matter_rules
        known_rules={r["rule_id"] for r in matter_rules()}
        for p in result.paths:
            if not set(p.rule_ids)<=known_rules:raise ValueError("路径引用了未登记规则")
            if p.matter_id!=matter.matter_id:raise ValueError("财务路径事项不一致")
            for step in p.steps:
                if step.origin in {"human_review","program_calculation"}:step.origin="model_hypothesis"
                if not step.evidence_ids:step.support="pending"
                elif step.origin=="model_hypothesis" and step.support=="supported":step.support="limited"
            if any(s.support=="conflicting" for s in p.steps):p.support="conflicting"
            elif all(s.support=="supported" and s.origin=="report_statement" for s in p.steps):p.support="supported"
            elif any(s.evidence_ids for s in p.steps):p.support="limited"
            else:p.support="pending"
            p.path_id="PATH-"+digest(matter.matter_id+p.financial_item+str([s.label for s in p.steps]))
            run.matter_paths=[old for old in run.matter_paths if old.path_id!=p.path_id]+[p]
    if role=="A3":
        for event in result.events:
            if event.matter_id!=matter.matter_id or not event.evidence_ids:raise ValueError("时序事件缺少同事项证据")
            cited=[refs[k] for k in event.evidence_ids]
            if event.report_period not in {b.report_period for b in cited}:raise ValueError("事件报告期间与来源不一致")
            if event.occurred_period and not any(compact(event.occurred_period) in compact(b.quote) for b in cited):
                raise ValueError("发生期间未得到引文支持，不能由报告年度代填")
            event.origin="model_interpretation"
            event.evidence_status="limited"
            event.event_id="EV-"+digest(matter.matter_id+event.kind+"|".join(sorted(event.evidence_ids)))
            run.matter_events=[e for e in run.matter_events if e.event_id!=event.event_id]+[event]
        for commitment in result.commitments:
            if commitment.matter_id!=matter.matter_id or not commitment.evidence_ids:raise ValueError("承诺缺少同事项证据")
            cited=" ".join(refs[k].quote for k in commitment.evidence_ids)
            if any(y and y not in cited for y in (commitment.baseline_year,commitment.target_year)):
                raise ValueError("承诺年份没有原文支持")
            if commitment.supersedes and not any(c.commitment_id==commitment.supersedes for c in run.matter_commitments):
                raise ValueError("被修订承诺未登记")
            if commitment.target_year and int(commitment.target_year)>run.report_set.as_of_date.year:
                commitment.status="not_due"
            if commitment.supersedes:
                previous=next(c for c in run.matter_commitments if c.commitment_id==commitment.supersedes)
                if previous.matter_id!=matter.matter_id:raise ValueError("不能修订另一事项的承诺")
                previous.status="revised"
            if any(c.commitment_id==commitment.commitment_id and c.matter_id!=matter.matter_id for c in run.matter_commitments):
                raise ValueError("承诺标识与其他事项冲突")
            run.matter_commitments=[c for c in run.matter_commitments if c.commitment_id!=commitment.commitment_id]+[commitment]
    if role=="A4":
        for hypothesis in result.explanations:
            if hypothesis.matter_id!=matter.matter_id:raise ValueError("竞争解释事项不一致")
            if not hypothesis.supporting_evidence_ids:hypothesis.status="hypothesis"
            hypothesis.hypothesis_id="HYP-"+digest(matter.matter_id+hypothesis.explanation)
            run.matter_explanations=[h for h in run.matter_explanations if h.hypothesis_id!=hypothesis.hypothesis_id]+[hypothesis]
    if role in {"A2","A3","A4"}:
        for edge in result.relations:
            if edge.matter_id!=matter.matter_id:raise ValueError("关系边事项不一致")
            # 两端必须可解析；模型不能凭一个名称生成“真实财务节点”。
            ids={*(m.matter_id for m in run.matters),*refs.keys(),*(o.occurrence_id for o in run.occurrences),*(e.event_id for e in run.matter_events),*(p.path_id for p in run.matter_paths),
                 *(c.commitment_id for c in run.matter_commitments)}
            if edge.source_id not in ids or edge.target_id not in ids:raise ValueError("关系端点未登记")
            if edge.assertion_origin in {"human_review","program_calculation"}:edge.assertion_origin="model_hypothesis"
            if not edge.evidence_ids:edge.evidence_status="pending"
            if edge.assertion_origin=="model_hypothesis" and edge.evidence_status=="supported":edge.evidence_status="limited"
            run.matter_relations=[e for e in run.matter_relations if e.edge_id!=edge.edge_id]+[edge]
    if role=="A5" and result.assessment:
        a=result.assessment
        if a.matter_id!=matter.matter_id:raise ValueError("综合判断事项不一致")
        paths=[p for p in run.matter_paths if p.matter_id==matter.matter_id]
        if a.relation_support=="supported" and (not a.supporting_evidence_ids or not paths or any(p.support!="supported" for p in paths)):
            a.relation_support="limited" if a.supporting_evidence_ids else "pending"
        # 只有程序调节工具可以确认数值可比，文字意见不能自行放行。
        if a.amount_comparability=="comparable":a.amount_comparability="needs_evidence"
        a.review_status="unreviewed"
        a.result_revision=run.result_revision
        run.matter_assessments=[old for old in run.matter_assessments if old.matter_id!=matter.matter_id]+[a]


def finish_projection(run):
    """从保存对象生成图谱、关注变化和覆盖计数。
    待调查事项与未决问题单列，不将零意见解释为零异常。
    所有关系端点保持原标识，多个事项可以连接同一信息对象。
    程序关注信号不评价会计重要性，也不预测企业后果。
    """
    assessed={a.matter_id:a for a in run.matter_assessments}
    nodes=[];edges=[]
    for m in run.matters:
        signals=[];basis=set()
        for e in run.matter_events:
            if e.matter_id==m.matter_id and e.kind in {"revision","termination","financial","commissioning"}:
                signals.append({"revision":"目标或基准发生修订","termination":"发现终止披露","financial":"存在财务估计或确认线索","commissioning":"进入投运或转固阶段"}[e.kind]);basis.update(e.evidence_ids)
        if any(p.matter_id==m.matter_id and p.support in {"conflicting","invalid"} for p in run.matter_paths):signals.append("路径存在矛盾或来源失效")
        if any(c.matter_id==m.matter_id and c.target_year and c.target_year.isdigit() and int(c.target_year)<=run.report_set.as_of_date.year and c.status in {"needs_review","progress_unknown"} for c in run.matter_commitments):signals.append("目标期已至或进入目标年，进展仍需核对")
        m.attention_signals=list(dict.fromkeys(signals));m.attention_evidence_ids=sorted(basis)
        nodes.append({"id":m.matter_id,"kind":"matter","label":m.name,"matter_id":m.matter_id})
        for eid in m.evidence_ids:
            edges.append({"source":m.matter_id,"target":eid,"kind":"disclosed_in","status":"limited","matter_id":m.matter_id})
    for b in run.matter_evidence:
        nodes.append({"id":b.evidence_id,"kind":"evidence","label":f"{b.report_period} {b.report_type} PDF {b.pdf_page}",
                      "document_id":b.document_id,"pdf_page":b.pdf_page,"evidence_id":b.evidence_id,"verified":b.source_verified,"invalid_reason":b.invalid_reason})
    for p in run.matter_paths:
        previous=p.matter_id
        for i,s in enumerate(p.steps):
            key=p.path_id+f"-S{i}"
            nodes.append({"id":key,"kind":"mechanism","label":s.label,"matter_id":p.matter_id,"evidence_ids":s.evidence_ids})
            edges.append({"source":previous,"target":key,"kind":s.origin,"status":s.support,"matter_id":p.matter_id})
            previous=key
        nodes.append({"id":p.path_id,"kind":"financial","label":p.financial_item,"matter_id":p.matter_id})
        edges.append({"source":previous,"target":p.path_id,"kind":"financial_path","status":p.support,"matter_id":p.matter_id})
    for event in run.matter_events:
        nodes.append({"id":event.event_id,"kind":"event","label":event.label,"matter_id":event.matter_id,"status":event.evidence_status,
                      "report_period":event.report_period,"occurred_period":event.occurred_period,"evidence_ids":event.evidence_ids})
    for commitment in run.matter_commitments:
        nodes.append({"id":commitment.commitment_id,"kind":"commitment","label":commitment.label,
                      "matter_id":commitment.matter_id,"status":commitment.status,"evidence_status":commitment.evidence_status,"evidence_ids":commitment.evidence_ids})
    for occurrence in run.occurrences:
        nodes.append({"id":occurrence.occurrence_id,"kind":"amount","label":occurrence.label,
                      "document_id":occurrence.document_id,"pdf_page":occurrence.pdf_page})
    edges.extend({"source":e.source_id,"target":e.target_id,"kind":e.relation_kind,"status":e.evidence_status,
                  "matter_id":e.matter_id,"evidence_ids":e.evidence_ids,"origin":e.assertion_origin,"id":e.edge_id}
                 for e in run.matter_relations)
    run.matter_graph={"version":"matter_graph_v1","nodes":nodes,"edges":edges}
    run.matter_overview={"matter_total":len(run.matters),"investigated":sum(m.investigation_status in {"completed","partial"} for m in run.matters),
        "completed":sum(m.investigation_status=="completed" for m in run.matters),"pending":sum(m.investigation_status in {"pending","skipped"} for m in run.matters),
        "assessment_count":len(assessed),"supported_paths":sum(p.support=="supported" for p in run.matter_paths),
        "unresolved":sum(len(a.unresolved) for a in assessed.values()),"indexed_blocks":sum(c.get("indexed_blocks",0) for c in run.matter_coverage),
        "notice":"关联状态描述公开材料对具体主张的支持程度，不构成会计确认或鉴证结论"}

    from .connectivity_assurance_planning import build_assurance_planning
    run.assurance_planning=build_assurance_planning(run)


def missing_assessment(matter, reason):
    return MatterAssessment(matter_id=matter.matter_id,summary="当前调查未完成，已保留原文线索和待查问题。",
        unresolved=[reason],next_actions=[NextAction(question="该事项与财务信息的具体联系是什么？",
            requested_material="该事项对应的项目明细、相关财务附注及后续年度进展",purpose="确认事项身份及财务传导的缺失环节")])
