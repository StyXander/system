/* 同一运行的展示投影。这里只组织证据，不生成披露、因果关系或模型调用。 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AuditTraceViewModel = api;
})(typeof window === 'undefined' ? globalThis : window, function () {
  'use strict';
  const list = value => Array.isArray(value) ? value : [];
  const roleNames = {A1:'证据发现与规划', A2:'专业质疑与反证', A3:'审计判断与程序复核'};
  const statusNames = {pending:'等待执行',queued:'排队中',running:'执行中',completed:'已完成',failed:'失败',
    partial:'部分完成',degraded:'部分完成',skipped:'未执行',not_requested:'未调用',cancelled:'已取消',
    interrupted:'已中断',expired:'已过期',reused:'复用原记录'};
  const canonicalRole = role => ({challenge:'A1',counter:'A2',review:'A3'})[role] || role;
  function analysis(run, check) {
    return list(run.ai_analyses).find(a => a.check_id === check.check_id && a.status !== 'needs_refresh' && a.review_status !== 'rejected') || null;
  }
  function project(run, status) {
    const documents = new Map(list(run.documents).map(d => [d.document_id,d]));
    const occurrences = new Map(list(run.occurrences).map(o => [o.occurrence_id,o]));
    const paths = list(run.checks).map((check,index) => {
      const refs = [...list(check.members),...list(check.relationship_evidence),...list(check.explanation_evidence),
        ...list(check.conditions).flatMap(c => list(c.evidence))];
      const members = list(check.members).map(m => ({...m,occurrence:occurrences.get(m.occurrence_id)}));
      const cited = [...new Set(refs.map(r => r.occurrence_id))].map(id => occurrences.get(id)).filter(Boolean);
      // 报告总体范围声明是辅助依据，不能充当另一份报告中的关联事项成员。
      const disclosed=[...new Map(members.filter(m=>m.occurrence).map(m=>[m.occurrence_id,m.occurrence])).values()];
      const esg = disclosed.filter(o => documents.get(o.document_id)?.report_type === 'ESG');
      const financial = disclosed.filter(o => documents.get(o.document_id)?.report_type === 'AR');
      const missing = list(check.conditions).filter(c => c.status !== 'supported');
      const level = status.programLevel(check);
      const ai = analysis(run,check);
      const hint = list(run.program_hints).find(h => h.check_id === check.check_id);
      const priority = hint?.priority || ai?.priority || null;
      const priorityReason = hint?.priority_reason || ai?.priority_reason || '';
      // “双报告证据”是位置覆盖；不能因此升级为已证实的业务关系。
      const both = esg.length > 0 && financial.length > 0;
      const validRefs = list(check.relationship_evidence).filter(ref => {
        const o = occurrences.get(ref.occurrence_id);
        const normalize = value => String(value || '').replace(/\s+/g,'');
        return o && normalize(ref.quote).length >= 2 && normalize(o.context).includes(normalize(ref.quote));
      });
      const explicit = ['text_statement','table_structure','metric_identity'].includes(check.relationship_basis) && validRefs.length > 0;
      const edge = both && explicit && level.key === 'formal' ? 'supported'
        : both && validRefs.length ? 'indirect' : ai ? 'model' : 'gap';
      const reason = validRefs[0]?.quote || check.mapping_reason || check.explanation || '';
      const next = [...new Set([...list(ai?.next_actions), ...list(run.next_evidence).filter(n => n.check_id === check.check_id).map(n => n.action),
        ...list(run.findings).filter(f => f.check_id === check.check_id).map(f => f.question),...list(check.unresolved)])].filter(Boolean);
      return {id:check.check_id,index,check,members,cited,esg,financial,both,missing,level,ai,priority,priorityReason,edge,reason,next,
        relation:status.relationType(check),
        rank:({high:30,medium:20,low:10}[priority] || 0) + (level.key === 'conflict' ? 5 : 0)};
    }).sort((a,b) => b.rank-a.rank || a.index-b.index);
    const gaps = paths.filter(p => !p.both || p.missing.length > 0);
    const priorities = paths.filter(p => p.priority === 'high' || p.level.key === 'conflict');
    const supported = paths.filter(p => p.edge === 'supported');
    const covered = paths.filter(p => p.both);
    const prefix = `${run.company || '本企业'} ${run.metric_period || run.period || ''}`;
    const focus=paths[0];
    const focusSubject=focus?.esg[0]?.label || focus?.check.title;
    const focusState=focus?.both ? `已定位年报对应披露，${focus.missing.length ? '但'+focus.missing.map(c=>c.name).join('、')+'依据仍待补齐' : '当前程序结论为'+focus.level.label}` : '尚未建立完整的双报告证据路径';
    const sentence = paths.length ? `${prefix}：${focusSubject}${focusState}。本次 ${gaps.length} 项关系仍有证据或比较前提缺口${priorities.length ? `，其中 ${priorities.length} 项应优先核查` : ''}；关联不等于已证明财务因果影响。`
      : `${prefix}：本次未形成可展示的关联关系。请先检查搜索覆盖与任务状态；无结果不代表零异常。`;
    return {paths,gaps,priorities,supported,covered,sentence,documents,occurrences};
  }
  function provenance(task,startedHere) {
    const run = task.result;
    if (!run) return '任务尚未形成结果';
    if (run.versions?.result_origin === 'user_revision') return '使用者修订 · 原模型记录沿用';
    if (run.execution_mode === 'calculation_only') return `${startedHere ? '本次程序运行' : '历史真实结果'} · 仅计算，未调用模型`;
    if (run.model_status === 'reused_completed') return '复用既有研判 · 无新增模型调用';
    return `${startedHere ? '本次任务结果' : '历史真实任务'} · ${statusNames[task.status] || task.status}`;
  }
  function collaboration(run,task) {
    const steps = list(run?.agent_steps);
    const calls = list(run?.provider_calls);
    const events = list(run?.intelligence_trace);
    const live = Object.fromEntries(Object.entries(task?.agent_steps || {}).map(([key,value])=>[canonicalRole(key),value]));
    const keys = [...new Set([...steps.map(s=>canonicalRole(s.role)),...calls.map(c=>canonicalRole(c.role)),...Object.keys(live)])].filter(Boolean);
    return keys.map(role => ({role,name:roleNames[role] || role,
      steps:steps.filter(s=>canonicalRole(s.role) === role),calls:calls.filter(c=>canonicalRole(c.role) === role),
      events:events.filter(e=>[e.role,e.producer_role,e.consumer_role].map(canonicalRole).includes(role)),
      live:live[role] || null,
      status:steps.filter(s=>canonicalRole(s.role) === role).at(-1)?.status || live[role]?.status || (calls.filter(c=>canonicalRole(c.role)===role && c.performed).at(-1)?.failure_code ? 'failed' : calls.some(c=>canonicalRole(c.role)===role && c.performed) ? 'completed' : 'not_requested')}));
  }
  return {project,analysis,collaboration,provenance,roleNames,statusNames};
});
