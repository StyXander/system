/* 事项工作台只呈现保存结果，不在浏览器推断专业结论或触发隐性模型调用。 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.AuditTraceMatters=api;
})(typeof window==='undefined'?globalThis:window,function(){
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const roles={A1:'事项识别与建档',A2:'财务影响调查',A3:'跨期承诺与后果追踪',A4:'边界解释与反证',A5:'综合复核与补证'};
  const labels={pending:'待调查',running:'调查中',completed:'已完成',partial:'部分完成',skipped:'未执行',failed:'失败',cancelled:'已取消',interrupted:'父运行已中断',reused:'复用已完成结果',
    candidate:'身份待确认',evidence_linked:'有据关联候选',human_confirmed:'人工确认身份',limited:'部分支持',supported:'有据支持',
    conflicting:'存在反证',not_comparable:'不可直接比较',invalid:'来源失效',not_assessed:'尚未评价',needs_evidence:'待补证',
    hypothesis:'候选解释',supported_as_reported:'报告披露支持',challenged:'受到质疑',unresolved:'尚未解决',
    not_due:'目标期限未到',progress_unknown:'进展待核',revised:'目标已修订',needs_review:'需要核查',
    promise:'承诺',revision:'修订',action:'行动',investment:'投入',commissioning:'投运',performance:'绩效',financial:'财务信息',risk:'风险',termination:'终止',
    five_agents_partial:'五Agent部分完成',five_agents_completed:'五Agent角色已完成',matter_three_partial:'三Agent对照部分完成',matter_three_completed:'三Agent对照已完成',matter_single_partial:'单模型对照部分完成',matter_single_completed:'单模型对照已完成',not_requested:'未调用模型',
    adopted:'采纳为调查线索',deferred:'暂缓',excluded:'排除',unreviewed:'未人工采用',accepted:'已采用为核查参考',rejected:'已驳回',report_statement:'企业原文陈述',model_hypothesis:'模型机制假设'};
  const label=k=>labels[k]||k;
  Object.assign(labels,{climate_risk:'气候风险与会计估计',transition_project:'绿色改造与转型项目',commitment:'目标与跨年承诺',resource_efficiency:'资源效率与绩效',other:'其他财务线索'});
  function project(run,id){
    const matters=run.matters||[],matter=matters.find(m=>m.matter_id===id)||matters[0];
    if(!matter)return{matter:null,events:[],paths:[],explanations:[],commitments:[],evidence:[],tasks:[]};
    const of=key=>(run[key]||[]).filter(r=>r.matter_id===matter.matter_id);
    const paths=of('matter_paths'),assessment=of('matter_assessments')[0],events=of('matter_events').sort((a,b)=>String(a.report_period).localeCompare(String(b.report_period)));
    const evidenceIds=new Set(matter.evidence_ids||[]);
    function collect(v){if(!v||typeof v!=='object')return;for(const[k,item]of Object.entries(v)){if(k.endsWith('evidence_ids')&&Array.isArray(item))item.forEach(id=>evidenceIds.add(id));else if(item&&typeof item==='object')collect(item);}}
    [paths,events,of('matter_commitments'),of('matter_relations'),of('matter_explanations'),assessment].forEach(collect);
    return{matter,assessment,paths,events,relations:of('matter_relations'),commitments:of('matter_commitments'),explanations:of('matter_explanations'),tasks:of('matter_tasks'),
      evidence:(run.matter_evidence||[]).filter(e=>evidenceIds.has(e.evidence_id))};
  }
  let selected=null,task=null,documents=[],catalog=null,choicesCompany=null,detailGeneration=0,candidatePage=0,candidateQuery='',candidateType='';
  const detailCache=new Map();
  const $=id=>document.getElementById(id);
  async function api(path,options={}){
    const response=await fetch('/api/connectivity'+path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json',...options.headers}});
    const data=await response.json().catch(()=>({detail:'服务未返回可读取结果'}));
    if(!response.ok){const detail=data.detail,error=new Error(typeof detail==='string'?detail:(detail?.message||'请求未完成')+(detail?.documents||[]).map(d=>`；${d.company||''} ${d.period||''} ${d.report_type||''}（${d.document_id}）：${d.message||''}`).join(''));error.status=response.status;error.code=detail?.code;error.documents=detail?.documents;error.preflight=path==='/report-sets';throw error;}return data;
  }
  function refs(ids,run){return(ids||[]).map(id=>{const b=(run.matter_evidence||[]).find(e=>e.evidence_id===id);return b?`<a href="/api/connectivity/sources/${encodeURIComponent(b.document_id)}?page=${b.pdf_page}" target="_blank" rel="noopener">${esc(b.report_period)} ${esc(b.report_type)} PDF ${b.pdf_page} ↗</a>`:'';}).join(' · ');}
  function list(values){return values?.length?`<ul>${values.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`:'<p class="cm-muted">当前没有保存的记录。</p>';}
  const markedCandidates=new Set();
  function matterRow(m){return`<div class="cm-list-row"><input type="checkbox" aria-label="选择整理事项 ${esc(m.name)}" data-cm-merge="${esc(m.matter_id)}" ${markedCandidates.has(m.matter_id)?'checked':''}><button type="button" data-cm-select="${esc(m.matter_id)}" aria-pressed="${m.matter_id===selected}"><strong>${esc(m.name)}</strong><span>${esc(label(m.identity_status))} · ${esc(label(m.investigation_status))}</span></button></div>`;}
  function candidateRows(run){
    const candidates=(run.matters||[]).filter(m=>m.investigation_status==='pending'&&(!candidateType||m.matter_type===candidateType)&&(!candidateQuery||`${m.name} ${m.identity_basis}`.toLowerCase().includes(candidateQuery.toLowerCase())));
    const start=candidatePage*10;
    return candidates.slice(start,start+10).map(matterRow).join('')+`<p>共 ${candidates.length} 项 · 第 ${candidatePage+1} 页</p><button data-cm-page="${candidatePage-1}" ${candidatePage===0?'disabled':''}>上一页</button><button data-cm-page="${candidatePage+1}" ${start+10>=candidates.length?'disabled':''}>下一页</button><button data-cm-batch>逐项调查已勾选候选</button><p id="cm-batch-state" role="status"></p>`;
  }
  function summaryHtml(run){
    const investigated=(run.matters||[]).filter(m=>m.investigation_status!=='pending');
    const assessments=run.matter_assessments||[];
    const gaps=[...new Set(assessments.flatMap(a=>a.unresolved||[]))].slice(0,3);
    return`<section class="cm-investigation-summary"><h3>本次调查摘要</h3><p>${run.model_status==='not_requested'?'已整理':'已深查'} ${investigated.length} 项。未深查事项仅为候选，不视为已发现风险。</p>${run.versions?.source_validity?.status==='invalid'?'<p role="alert">依赖来源已变化，当前判断仅供历史回查，请强制重验原件。</p>':''}
    <div class="cm-key-matters">${investigated.slice(0,5).map(m=>{const a=assessments.find(a=>a.matter_id===m.matter_id);return`<article><span>${esc(label(m.investigation_status))}</span><h4>${esc(m.name)}</h4><dl><dt>当前证据支持的判断</dt><dd>${esc(a?.summary||'综合复核尚未完成；打开事项查看已取得线索。')}</dd><dt>财务影响</dt><dd>${esc(a?.financial_stage||'财务归属待核')}</dd><dt>证据与反证</dt><dd>支持引用 ${a?.supporting_evidence_ids?.length||0} 条 · 反证引用 ${a?.counter_evidence_ids?.length||0} 条</dd></dl><button data-cm-select="${esc(m.matter_id)}">查看证据链 ↗</button></article>`;}).join('')||'<p>当前仅完成程序初筛。请展开候选项，选择一个明确事项启动五Agent深查。</p>'}</div>
    <h4>仍缺的关键资料</h4>${list(gaps.length?gaps:investigated.length?['打开事项查看具体资料需求；空清单不代表资料齐备。']:['需先选择事项，才能形成有针对性的资料需求。'])}</section>`;
  }
  function evidenceChainHtml(p,run){
    const a=p.assessment,valid=ids=>(ids||[]).some(id=>p.evidence.some(e=>e.evidence_id===id&&e.source_verified&&!e.invalid_reason));
    const commitment=p.commitments[0]||p.events.find(e=>e.kind==='promise');
    const action=p.events.find(e=>['action','investment','commissioning','performance'].includes(e.kind));
    const ar=p.evidence.find(e=>e.report_type==='AR'&&e.source_verified&&!e.invalid_reason);
    const stages=[
      ['ESG 承诺',commitment?.label||'未取得明确承诺',commitment?(valid(commitment.evidence_ids)?'verified':'missing'):'missing'],
      ['企业行动',action?.label||'行动证据待补充',action?(valid(action.evidence_ids)?'verified':'missing'):'missing'],
      ['财务影响',p.paths.map(path=>path.financial_item).join('、')||'财务传导尚未建立',p.paths.length?'hypothesis':'missing'],
      ['年报证据',ar?ar.quote.slice(0,140):'未取得可对应的年报依据',ar?'verified':'missing'],
      ['未决条件',(a?.unresolved||[]).slice(0,2).join('；')||'对应关系与确认条件仍需核查','missing']
    ];
    const names={verified:'已核实原文',hypothesis:'模型假设',missing:'证据缺失 / 待核'};
    return`<section class="cm-chain-section"><h4>事项证据链</h4><p class="cm-muted">核实原文仅确认披露出处；财务因果和实际履约仍以相应证据为准。</p><ol class="cm-evidence-chain">${stages.map(([name,text,state])=>`<li data-support="${state}"><span>${names[state]}</span><h5>${name}</h5><p>${esc(text)}</p></li>`).join('')}</ol><div class="cm-financial-items">${p.paths.map(path=>`<span>${esc(path.financial_item)} · ${esc(label(path.support))}</span>`).join('')}</div></section>
    <section><h4>跨年度时间线</h4><ol class="cm-yearline">${p.events.slice(0,8).map(e=>`<li><strong>${esc(e.occurred_period||'发生期间未明确')}</strong><span>报告 ${esc(e.report_period)} · ${esc(label(e.kind))}</span><p>${esc(e.label)}</p>${refs(e.evidence_ids,run)}</li>`).join('')||'<li>尚未取得跨期事件证据。</li>'}</ol></section>`;
  }
  async function selectMatter(id){
    if(!task)return;
    selected=id;const generation=++detailGeneration,taskId=task.task_id,version=task.version;
    const key=`${taskId}:${version}:${id}`;
    const target=document.querySelector('.cm-detail');if(target)target.innerHTML='<p role="status">正在读取该事项的证据链…</p>';
    try{
      const detail=detailCache.get(key)||await api(`/runs/${encodeURIComponent(taskId)}/matters/${encodeURIComponent(id)}`);
      if(generation!==detailGeneration||task?.task_id!==taskId||task.version!==version)return;
      if(detail.version!==version){document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:taskId}}));return;}
      detailCache.set(key,detail);while(detailCache.size>10)detailCache.delete(detailCache.keys().next().value);
      const run=task.result,value=detail.result;
      for(const field of ['matter_events','matter_commitments','matter_paths','matter_relations','matter_explanations','matter_assessments','matter_tasks','matter_evidence','matter_tool_receipts','matter_rejections','matter_graph','current_task_ids'])run[field]=field==='matter_assessments'?[...(run[field]||[]).filter(a=>a.matter_id!==id),...(value[field]||[])]:value[field]||[];
      run.versions={...run.versions,...value.versions};
      run.matters=run.matters.map(m=>m.matter_id===id?value.matters[0]:m);run.loaded_matter_id=id;
      render(task);$('cm-selected-title')?.focus({preventScroll:true});
    }catch(error){if(generation===detailGeneration&&task?.task_id===taskId&&target)target.innerHTML=`<p role="alert">${esc(error.message)}</p><button data-cm-select="${esc(id)}">重新读取事项</button>`;}
  }
  function render(value){
    if(task?.task_id!==value.task_id||task?.version!==value.version){detailGeneration++;selected=null;}
    task=value;const run=value.result;
    if(!(run.matters||[]).some(m=>m.matter_id===selected))selected=(run.matters||[]).find(m=>m.investigation_status!=='pending')?.matter_id||run.matters?.[0]?.matter_id;
    const p=project(run,selected);selected=p.matter?.matter_id;
    let host=$('cn-matter-results');if(!host){host=document.createElement('section');host.id='cn-matter-results';$('cn-results').append(host);}
    host.hidden=false;document.body.classList.add('cm-active');
    ['cn-financial','cn-all-relations'].forEach(id=>{if($(id))$(id).hidden=true;});
    document.querySelectorAll('.cn-overview').forEach(e=>e.hidden=true);
    const overview=run.matter_overview||{};
    host.innerHTML=`<header class="cm-heading"><p class="at-eyebrow">MATTER INVESTIGATION</p><h2>${esc(run.company)} · ${esc(run.period)}</h2><p class="cm-result-state">${esc(label(value.status))} · ${esc(value.task_id)}</p><p>观察截至 ${esc(run.report_set?.as_of_date)} · ${esc(run.documents.length)} 份报告 · ${esc(label(run.model_status))}</p></header>
      <div class="cm-counts">${[['初筛候选',overview.matter_total],[run.model_status==='not_requested'?'已整理事项':'已深查',overview.investigated],['尚未深查',overview.pending]].map(([k,n])=>`<div><span>${esc(k)}</span><strong>${esc(n??0)}</strong></div>`).join('')}</div>
      <p class="cm-muted">${esc(overview.notice||'未形成事项不代表报告没有相关事项，请检查资料和解析覆盖。')}</p>
      ${run.report_set?.coverage_gaps?.length?`<details><summary>资料缺口</summary>${list(run.report_set.coverage_gaps)}</details>`:''}
      ${summaryHtml(run)}
      <details class="cm-planning-details"><summary>关注点与资料需求清单</summary>${planningHtml(run)}</details>
      <div class="cm-layout"><aside class="cm-list" aria-label="事项档案"><h3>${run.model_status==='not_requested'?'已整理事项（未调用模型）':'已深查事项'}</h3>${(run.matters||[]).filter(m=>m.investigation_status!=='pending').map(m=>matterRow(m)).join('')||'<p>尚无深查结果。</p>'}
      <details class="cm-candidates"><summary>其余候选项（${esc(overview.pending??0)}）</summary><p>未深查事项仅为候选，不视为已发现风险。</p><label>搜索候选<input id="cm-candidate-query" type="search" value="${esc(candidateQuery)}"></label><label>事项分类<select id="cm-candidate-type"><option value="">全部分类</option>${['climate_risk','transition_project','commitment','resource_efficiency','other'].map(k=>`<option value="${k}"${candidateType===k?' selected':''}>${esc(label(k))}</option>`).join('')}</select></label><div id="cm-candidate-rows">${candidateRows(run)}</div></details></aside>
      <article class="cm-detail" aria-live="polite">${p.matter?(run.loaded_matter_id===selected||run.projection_layer!=='summary'?detailHtml(p,run):`<h3>${esc(p.matter.name)}</h3><p>${esc(p.assessment?.summary||'当前仅完成程序初筛，尚未启动五Agent调查。')}</p><button type="button" data-cm-select="${esc(selected)}">打开事项证据链</button><button type="button" data-cm-investigate="${esc(selected)}">仅深查此事项（真实五Agent）</button>`):'<h3>尚未形成可展示事项</h3><p>请查看原件与解析覆盖，或选择其他资料。</p>'}</article></div>
      <details class="cm-coverage"><summary>解析覆盖和调用预算</summary><p>首轮 ${esc(run.versions?.seed_coverage?.seed_blocks??0)} 个原文块 / 已索引 ${esc(overview.indexed_blocks??0)} 个。首轮未入选块可由工具继续检索。</p>${(run.matter_coverage||[]).map(c=>`<p>${esc(c.document_id)} · ${esc(c.total_pages)} 页 · ${esc(c.failed_pages?.length??0)} 页解析限制 · OCR ${c.ocr_enabled?'开启':'关闭'}</p>`).join('')}<pre>${esc(JSON.stringify(run.versions?.budget||{},null,2))}</pre></details>`;
    renderEvidence(p,run);
    const col=$('cn-collaboration');if(col)col.innerHTML=collaborationHtml(run,selected);
    $('cm-candidate-query')?.addEventListener('input',e=>{candidateQuery=e.target.value;candidatePage=0;$('cm-candidate-rows').innerHTML=candidateRows(run);});
    $('cm-candidate-type')?.addEventListener('change',e=>{candidateType=e.target.value;candidatePage=0;$('cm-candidate-rows').innerHTML=candidateRows(run);});

  }
  function planningHtml(run){
    const planning=run.assurance_planning;if(!planning?.risk_findings)return run.model_status==='not_requested'?'<p>当前为程序初筛，未调用模型，不会自动生成风险关注点或资料需求清单。请选择一个具体事项启动深查。</p>':'<p>本次运行尚未取得可展示的风险关注点清单。这可能是深查未完成或服务端未保存清单投影，不代表历史数据损坏；请查看当前事项及角色回执。</p>';
    const review=row=>task.can_modify&&row.matter_ids?.length?`<div class="cm-review-actions">${[['adopt','采纳为调查线索'],['defer','暂缓'],['exclude','排除']].map(([action,text])=>`<button type="button" data-cm-planning="${action}" data-entry="${esc(row.entry_id)}">${text}</button>`).join('')}</div>`:'';
    return `<section class="cm-planning"><h3>风险关注点清单</h3><p>${esc(planning.notice)}</p>${planning.risk_findings.map(row=>`<article class="cm-hypothesis"><strong>${esc(row.matter)}</strong><p>${esc(row.reason)}</p><small>调查顺序 ${esc(row.priority)} · ${esc(label(row.review_status))} · ${esc(label(row.investigation_status))}</small><p>合理解释：${esc(row.alternative_explanations.join('；')||'仍待调查')}</p><div>依据 ${refs(row.evidence.map(e=>e.evidence_id),run)||'待取得'} · 反证 ${refs(row.counter_evidence.map(e=>e.evidence_id),run)||'待取得'}</div>${review(row)}</article>`).join('')||'<p>当前没有列示条目，不代表没有风险。</p>'}
      <h3>资料需求清单</h3>${planning.evidence_requests.map(row=>`<article class="cm-action"><strong>${esc(row.requested_material)}</strong><p>对应事项：${esc(row.matters.join('、'))}</p><p>解决问题：${esc(row.questions.join('；'))}</p><p>取得后核查：${esc(row.purposes.join('；'))}</p><p>区分解释：${esc(row.distinguishing_explanations.join('；')||'按问题核对，保留未决')}</p><small>${esc(row.responsible_person)} · ${esc(row.acquisition_status)} · ${esc(label(row.review_status))}</small>${review(row)}</article>`).join('')||'<p>当前尚未形成具体资料要求，不代表资料已齐备。</p>'}</section>`;
  }
  function detailHtml(p,run){
    const a=p.assessment,m=p.matter;
    return`<h3 tabindex="-1" id="cm-selected-title">${esc(m.name)}</h3><button type="button" data-cm-investigate="${esc(m.matter_id)}">仅深查此事项（真实五Agent）</button><p>${esc(m.identity_basis)}</p>${m.attention_signals?.length?`<details open><summary>本次关注变化（调查顺序参考）</summary>${list(m.attention_signals)}<p class="cm-muted">这些信号不代表财务重要性阈值或错误认定。</p></details>`:''}
      <section class="cm-verdict"><h4>当前判断与模型综合意见</h4><p>${esc(a?.summary||'该事项尚未完成综合复核，当前仅保留原文线索。')}</p><div class="cm-tags"><span>关联 ${esc(label(a?.relation_support||'pending'))}</span><span>金额 ${esc(label(a?.amount_comparability||'not_assessed'))}</span><span>采用 ${esc(label(a?.review_status||'unreviewed'))}</span></div><p>承诺进展：${esc(a?.commitment_progress||'待调查')}</p><p>财务阶段：${esc(a?.financial_stage||'待调查')}</p>${list(a?.unresolved)}</section>
      ${evidenceChainHtml(p,run)}<details><summary>财务路径、跨年度时间线与竞争解释</summary><section><h4>财务影响路径</h4>${p.paths.map(path=>`<div class="cm-path"><strong>${esc(path.financial_item)} · ${esc(label(path.support))}</strong><ol>${path.steps.map(s=>`<li><strong>${esc(s.label)}</strong> · ${esc(label(s.support))}<p>${esc(s.explanation)}</p><small>${esc(label(s.origin))}</small><div>${refs(s.evidence_ids,run)}</div></li>`).join('')}</ol></div>`).join('')||'<p>尚未建立有证据约束的财务路径。主题相近或金额相等均不能替代该调查。</p>'}</section>
      ${p.relations?.length?`<section><h4>信息关系与共同归属</h4>${p.relations.map(e=>{const name=id=>(run.matter_graph?.nodes||[]).find(n=>n.id===id)?.label||id;return `<div class="cm-hypothesis"><p>${esc(name(e.source_id))} → ${esc(name(e.target_id))}</p><small>${esc(e.relation_kind)} · ${esc(label(e.evidence_status))} · ${esc(label(e.assertion_origin))}</small><p>${esc(e.explanation)}</p>${refs(e.evidence_ids,run)}</div>`;}).join('')}</section>`:''}
      <section><h4>承诺与财务两线追踪</h4><div class="cm-timelines">${[['承诺 行动与绩效',false],['财务影响',true]].map(([title,financial])=>`<div><h5>${title}</h5><ol>${p.events.filter(e=>(e.kind==='financial')===financial).map(e=>`<li><strong>${esc(e.report_period)} · ${esc(label(e.kind))}${e.evidence_status==='invalid'?' · 来源失效':''}</strong><p>${esc(e.label)}</p><small>发生期间 ${esc(e.occurred_period||'原文未明确')} · 披露 ${esc(e.disclosure_date||'未登记')}</small><div>${refs(e.evidence_ids,run)}</div></li>`).join('')||'<li>当前未取得该线的事件证据。</li>'}</ol></div>`).join('')}</div>${p.commitments.map(c=>`<p class="cm-commitment">基期 ${esc(c.baseline_year||'未明确')} · 目标期 ${esc(c.target_year||'未明确')} · ${esc(label(c.status))}${c.evidence_status==='invalid'?' · 来源失效':''}${c.supersedes?' · 修订自 '+esc(c.supersedes):''}<br>${esc(c.label)}<br>${refs(c.evidence_ids,run)}</p>`).join('')}</section>
      <section><h4>边界与竞争解释</h4>${p.explanations.map(h=>`<div class="cm-hypothesis"><strong>${esc(label(h.status))}</strong><p>${esc(h.explanation)}</p><p>区分证据：${esc(h.discriminating_evidence)}</p><p>支持 ${refs(h.supporting_evidence_ids,run)||'待取得'} · 反证 ${refs(h.counter_evidence_ids,run)||'未取得'}</p></div>`).join('')||'<p>当前没有保存的竞争解释；不能据此认定差异合理。</p>'}</section>
      <section><h4>下一步核查</h4>${(a?.next_actions||[]).map(n=>`<div class="cm-action"><strong>项目组待处理 · ${esc(n.question)}</strong><p>资料：${esc(n.requested_material)}</p><p>用途：${esc(n.purpose)}</p></div>`).join('')||'<p>尚未形成具体补证任务。</p>'}${a?.assumptions?.length?'<h5>成立所需假设</h5>'+list(a.assumptions):''}${a?.disagreements?.length?'<h5>未解决分歧</h5>'+list(a.disagreements):''}</section>
      </details><details><summary>当前事项的完整角色记录</summary>${p.tasks.map(t=>`<p><strong>${esc(t.role)} ${esc(roles[t.role]||'')}</strong> · ${esc(label(t.status))} · ${esc(t.stop_reason)}${t.duration_ms!=null?` · 实际用时 ${(t.duration_ms/1000).toFixed(1)}秒`:""}</p><p>${esc(failureAdvice(t))}</p><pre>${esc(JSON.stringify(t.result||t.error_detail||{},null,2))}</pre>`).join('')||'<p>没有实际角色记录。</p>'}</details>
      ${task.can_modify?'<details class="cm-review"><summary>事项整理与意见采用</summary><p>归并请勾选左侧事项；拆分请在原文列表勾选部分证据。操作保存为子版本，原记录保留。</p><label>理由<input id="cm-review-reason" type="text" minlength="3" maxlength="2000"></label><div class="cm-review-actions"><button type="button" data-cm-action="merge">归并已选事项</button><button type="button" data-cm-action="split">按已选证据拆分</button><button type="button" data-cm-action="accept">采用当前意见</button><button type="button" data-cm-action="reject">驳回当前意见</button></div><p id="cm-review-message" role="status"></p></details>':''}`;
  }
  function renderEvidence(p,run){
    let host=$('cn-matter-evidence');if(!host){host=document.createElement('section');host.id='cn-matter-evidence';($('at-evidence')||$('cn-results')).append(host);}
    host.hidden=false;
    host.innerHTML=`<h3>${esc(p.matter?.name||'事项原文')}</h3><p>引文与页码来自同一保存版本；通过链接打开登记原页。</p>${p.evidence.map(b=>`<article class="cm-evidence"><label><input type="checkbox" data-cm-evidence="${esc(b.evidence_id)}"> ${esc(b.report_period)} ${esc(b.report_type)} · PDF ${b.pdf_page}</label><p>${esc(b.quote)}</p><small>${esc(b.evidence_id)} · ${esc(b.extraction_method)}${b.invalid_reason?' · '+esc(b.invalid_reason):''}</small><div>${refs([b.evidence_id],run)}</div></article>`).join('')||'<p>当前没有可回查的事项引用。</p>'}`;
  }
  function failureAdvice(t){
    const code=t.failure_code||t.stop_reason||'';
    if(/MODEL_HTTP_40[13]/.test(code))return '供应商认证或授权失败；已有结果保留，修正模型配置后再续跑。';
    if(/MODEL_HTTP_429/.test(code))return '供应商限流；已有结果保留，请按供应商等待要求稍后续跑。';
    if(/MODEL_(TRANSPORT|HTTP_50)/.test(code))return '供应商网络或服务暂不可用；自动重试有界，稍后可续跑。';
    if(/MODEL_(JSON_INVALID|FIELDS_INVALID|TOOL_REQUIRED|SCHEMA|OUTPUT)/.test(code))return '模型返回的结构化工具参数未通过解析或字段校验；本角色没有完成。请查看字段错误并限次纠正，不能跳过引文核验。';
    if(/EVIDENCE_VALIDATION_FAILED|建档结果输入版本/.test(code))return '角色结果未通过事项身份、输入版本或原文证据核验；请围绕所选具体事项纠错，不能自动采用该结论。';
    if(/BUDGET/.test(code))return '已达到本次执行保护，已有结果保留；可选择未完成事项续跑。这不是每日配额。';
    return '';
  }
  function latestRoleTasks(run,matterId){
    const ids=new Set(run.current_task_ids||(run.provider_calls||[]).map(c=>c.task_id));
    const scoped=(run.matter_tasks||[]).filter(t=>(t.matter_id===matterId||(t.role==='A1'&&!t.matter_id))&&(t.run_id===run.run_id||(!t.run_id&&ids.has(t.task_id))));
    return Object.fromEntries(Object.keys(roles).map(role=>[role,scoped.filter(t=>t.role===role).at(-1)||null]));
  }
  function collaborationHtml(run,matterId=selected){
    const current=latestRoleTasks(run,matterId);
    return`<p>所选事项 · ${esc((run.matters||[]).find(m=>m.matter_id===matterId)?.name||'尚未选择')} · 本次运行 ${esc(run.run_id)}</p><div class="cm-agent-grid">${Object.entries(roles).map(([role,name])=>{const t=current[role];return`<article data-role="${role}"><h4>${role} ${name}</h4><strong>${esc(t?label(t.status):'本运行尚无回执')}</strong><p>${esc(t?.stop_reason||'选择具体事项后按需读取角色记录。')}</p>${t?`<small>${esc(t.task_id)}${t.duration_ms!=null?` · ${(t.duration_ms/1000).toFixed(1)}秒`:''}</small>`:''}</article>`;}).join('')}</div><details><summary>历史调用与错误（按任务和时间回查）</summary>${(run.matter_tasks||[]).filter(t=>t.matter_id===matterId||(t.role==='A1'&&!t.matter_id)).map(t=>`<p>${esc(t.role)} · ${esc(label(t.status))} · ${esc(t.run_id||'旧运行未登记')} · ${esc(t.task_id||'无编号')} · ${esc(t.updated_at?new Date(Number(t.updated_at)*1000).toLocaleString('zh-CN'):'未登记时间')}</p><p>${esc(t.failure_code||t.stop_reason||'')}</p>`).join('')||'<p>当前未加载事项详情。</p>'}</details><details><summary>工具查询与新证据</summary>${(run.matter_tool_receipts||[]).map(r=>`<p><strong>${esc(r.role)} · ${esc(r.tool_name)}</strong> · ${esc(r.status)}<br>${esc(r.result?.query||r.reason||'')}<br>返回 ${esc(r.result?.evidence?.length??0)} 个证据块</p>`).join('')||'<p>没有实际工具调用。</p>'}</details>`;
  }
  async function loadDocuments(){catalog=await api('/report-sets');documents=catalog.documents||[];drawDocumentChoices();}
  function drawDocumentChoices(){
    if(!$('cm-documents'))return;
    const pair=$('cn-pair')?.value,selectedDoc=documents.find(d=>d.case_id===pair),company=selectedDoc?.company_id;
    choicesCompany=company;
    const seen=new Set(),docs=documents.filter(d=>!company||d.company_id===company).sort((a,b)=>String(b.disclosure_date).localeCompare(String(a.disclosure_date))).filter(d=>{const k=[d.company_id,d.report_type,d.period,d.file_sha256].join('|');if(seen.has(k))return false;seen.add(k);return true;});
    const asOf=$('cm-as-of')?.value||'',groups=new Map();
    docs.forEach(d=>{const key=(d.report_period||d.period)+d.report_type;if(!groups.has(key))groups.set(key,new Set());groups.get(key).add(d.file_sha256);});
    function issue(d){
      const raw=String(d.disclosure_date||'').trim();if(!raw)return '发布日期未登记｜需补齐或取消选择';
      const match=raw.match(/^(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?$/);
      if(!match)return '发布日期待核验';
      const iso=`${match[1]}-${match[2].padStart(2,'0')}-${match[3].padStart(2,'0')}`,parsed=new Date(iso+'T00:00:00Z');
      if(Number.isNaN(parsed.getTime())||parsed.toISOString().slice(0,10)!==iso)return '发布日期无效';
      if(iso>asOf)return '发布日晚于观察时点';
      if(!/^[a-fA-F0-9]{64}$/.test(d.file_sha256||'')||!['official','announcement_mirror'].includes(d.source_kind))return '来源身份待核验';
      if(groups.get((d.report_period||d.period)+d.report_type).size>1)return '同年度存在不同版本｜请明确选一份';
      return '';
    }
    const defaults=new Set();
    $('cm-documents').innerHTML=docs.map(d=>{const reason=issue(d),k=(d.report_period||d.period)+d.report_type,checked=!reason&&!defaults.has(k);if(checked)defaults.add(k);return`<label><input type="checkbox" value="${esc(d.document_id)}" ${checked?'checked':''}>${esc(d.company)} · ${esc(d.report_period||d.period)} ${esc(d.report_type)} · ${esc(d.version)} · ${esc(reason||d.disclosure_date)}</label>`;}).join('')||'<p>没有已登记的资料。</p>';
    if(docs.some(issue))$('cm-documents').insertAdjacentHTML('beforeend','<p>待核资料仍保留在列表中，未默认纳入。本次可继续使用其余已勾选的合格年度；有版本冲突时请明确选择一份。</p><button type="button" id="cm-use-qualified">仅保留合格资料</button>');
    $('cm-use-qualified')?.addEventListener('click',()=>{document.querySelectorAll('#cm-documents input').forEach(n=>{if(issue(docs.find(d=>d.document_id===n.value)))n.checked=false;});});
  }
  async function prepareRequest(body){
    body.budget={...(body.budget||{}),max_matters:1};
    if(body.mode!=='calculation_only'&&!body.selected_matter_ids?.length){const error=new Error('请先点击“建立候选档案”，再从候选中选择一个具体事项启动深查。');error.preflight=true;throw error;}
    if(body.retry_of_task_id&&task?.result?.report_set){body.matter_types=task.result.versions?.matter_types||body.matter_types;delete body.pair_id;body.report_set_id=task.result.report_set.report_set_id;body.analysis_scope='matter_connectivity';return body;}
    if(body.report_set_id){delete body.pair_id;body.analysis_scope='matter_connectivity';return body;}
    const matterScope=body.mode==='five_agents'||($('cm-matter-scope')?.checked&&body.mode!=='adaptive_agents');
    if(!matterScope)return body;
    body.matter_types=[...document.querySelectorAll('#cm-matter-types input:checked')].map(n=>n.value);
    if(!body.matter_types.length)throw new Error('请至少选择一种调查事项。');
    const currentCompany=documents.find(d=>d.case_id===$('cn-pair')?.value)?.company_id;
    if(currentCompany!==choicesCompany)drawDocumentChoices();
    const ids=[...document.querySelectorAll('#cm-documents input:checked')].map(n=>n.value);
    if(!ids.length)throw new Error('请至少选择一份已登记报告。');
    const set=await api('/report-sets',{method:'POST',body:JSON.stringify({document_ids:ids,as_of_date:$('cm-as-of').value})});
    delete body.pair_id;body.report_set_id=set.report_set_id;body.analysis_scope='matter_connectivity';body.as_of_date=set.as_of_date;return body;
  }
  function activateLegacy(){document.body.classList.remove('cm-active');['cn-matter-results','cn-matter-evidence'].forEach(id=>{if($(id))$(id).hidden=true;});document.querySelectorAll('.cn-overview').forEach(n=>n.hidden=false);if($('cn-all-relations'))$('cn-all-relations').hidden=false;}
  function init(){
    if(document.querySelector('.cm-setup'))return;
    const setup=document.createElement('details');setup.className='cm-setup';setup.open=true;
    setup.innerHTML=`<summary>事项调查与多年资料范围</summary><label><input id="cm-matter-scope" type="checkbox" checked>按可持续事项调查财务影响与跨期进展</label><p>同一企业可选多个年度，允许缺年或只有一类报告。每年同类型请选择一个版本。</p><fieldset id="cm-matter-types"><legend>调查事项</legend><label><input type="checkbox" name="matter_type" value="climate_risk" checked>气候风险与会计估计</label><label><input type="checkbox" name="matter_type" value="transition_project" checked>绿色改造与转型项目</label><label><input type="checkbox" name="matter_type" value="commitment" checked>目标与跨年承诺</label><label><input type="checkbox" name="matter_type" value="resource_efficiency" checked>资源效率与绩效</label><label><input type="checkbox" name="matter_type" value="other" checked>其他财务线索</label></fieldset><label>深查范围<select id="cm-depth"><option value="1">1个重点事项（默认）</option><option value="2">2个事项（增加调用与等待）</option><option value="3">3个事项（增加调用与等待）</option></select></label><p>先做无模型事项初筛，再选一项调查；反证和综合复核保留。单次执行仍有20次请求保护，无每日配额。</p><button type="button" id="cm-screen">先建立事项档案（不调用模型）</button><label>观察截至日期<input id="cm-as-of" type="date" value="${new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'})}"></label><div id="cm-documents" class="cm-document-choices"></div><button type="button" id="cm-refresh-docs">刷新登记资料</button><details><summary>接入尚未登记的年度报告</summary><label>证券代码<input id="cm-import-ticker" pattern="[0-9]{6}" maxlength="6"></label><label>年度 用逗号分隔<input id="cm-import-years" placeholder="2023,2024,2025"></label><label><input id="cm-import-confirm" type="checkbox">已确认企业身份</label><button type="button" id="cm-import-start">准备多年资料</button><p id="cm-import-message" role="status"></p></details>`;
    $('cn-form').after(setup);
    const depth=$('cm-depth');depth.innerHTML='<option value="1">每个任务仅深查1个明确事项</option>';depth.disabled=true;
    $('cm-screen').addEventListener('click',()=>document.dispatchEvent(new CustomEvent('audittrace:connectivity-start-run',{detail:{mode:'calculation_only'}})));$('cm-refresh-docs').addEventListener('click',()=>loadDocuments().catch(e=>{$('cm-documents').textContent=e.message;}));
    const scopeChanged=()=>{const active=$('cn-mode').value==='five_agents'||($('cm-matter-scope').checked&&$('cn-mode').value!=='adaptive_agents');document.querySelector('.cn-topics').hidden=active;$('cm-matter-types').hidden=!active;$('cn-run').textContent=active?'建立候选档案（不调用模型） ↗':'开始关联核对 ↗';};
    $('cm-matter-scope').addEventListener('change',scopeChanged);$('cn-mode').addEventListener('change',scopeChanged);scopeChanged();
    $('cn-pair').addEventListener('change',drawDocumentChoices);$('cm-as-of').addEventListener('change',drawDocumentChoices);
    document.addEventListener('audittrace:connectivity-ready',e=>{if(e.detail?.matter_enabled===false){setup.hidden=true;$('cm-matter-scope').checked=false;const option=$('cn-mode').querySelector('[value=five_agents]');if(option)option.disabled=true;scopeChanged();}drawDocumentChoices();});
    document.addEventListener('audittrace:select-pair',()=>setTimeout(()=>loadDocuments().catch(()=>{}),0));
    document.addEventListener('audittrace:connectivity-task',e=>{if(e.detail.result?.matter_schema_version){task=e.detail;const c=$('cn-collaboration');if(c)c.innerHTML=collaborationHtml(task.result,selected);}});
    document.addEventListener('audittrace:connectivity-start',()=>{detailGeneration++;task=null;selected=null;});
    document.addEventListener('audittrace:connectivity-reset',()=>{detailGeneration++;selected=null;task=null;activateLegacy();});
    document.addEventListener('change',e=>{const input=e.target.closest('[data-cm-merge]');if(input){if(input.checked)markedCandidates.add(input.dataset.cmMerge);else markedCandidates.delete(input.dataset.cmMerge);}});
    document.addEventListener('click',async e=>{
      if(e.target.closest('[data-cm-batch]')&&task){
        const ids=(task.result.matters||[]).filter(m=>markedCandidates.has(m.matter_id)).map(m=>m.matter_id);
        if(!ids.length){$('cm-batch-state').textContent='请先勾选候选事项。';return;}
        const run=task.result;
        document.dispatchEvent(new CustomEvent('audittrace:connectivity-batch',{detail:ids.map(id=>({mode:'five_agents',report_set_id:run.report_set.report_set_id,as_of_date:run.report_set.as_of_date,selected_matter_ids:[id],matter_types:run.versions?.matter_types}))}));return;
      }
      const investigation=e.target.closest('[data-cm-investigate]');if(investigation&&task){
        const run=task.result,extra={mode:'five_agents',report_set_id:run.report_set.report_set_id,as_of_date:run.report_set.as_of_date,selected_matter_ids:[investigation.dataset.cmInvestigate],matter_types:run.versions?.matter_types};
        if(run.execution_mode==='five_agents')extra.retry_of_task_id=task.task_id;
        document.dispatchEvent(new CustomEvent('audittrace:connectivity-start-run',{detail:extra}));return;
      }
      const planningAction=e.target.closest('[data-cm-planning]');if(planningAction&&task){
        const planning=task.result.assurance_planning,row=[...planning.risk_findings,...planning.evidence_requests].find(r=>r.entry_id===planningAction.dataset.entry);
        const reason=window.prompt('请记录该处理决定的理由（至少三个字）');if(!reason||reason.trim().length<3)return;
        try{planningAction.disabled=true;const value=await api(`/runs/${encodeURIComponent(task.task_id)}/matter-revisions`,{method:'POST',body:JSON.stringify({expected_revision:task.result.result_revision,action_id:crypto.randomUUID(),action:'planning_'+planningAction.dataset.cmPlanning,planning_entry_ids:[row.entry_id],matter_ids:row.matter_ids,reason:reason.trim()})});document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:value.task_id}}));}catch(error){window.alert(error.message);}finally{planningAction.disabled=false;}return;
      }
      const paging=e.target.closest('[data-cm-page]');if(paging&&task){candidatePage=Number(paging.dataset.cmPage);$('cm-candidate-rows').innerHTML=candidateRows(task.result);return;}
      const choice=e.target.closest('[data-cm-select]');if(choice&&task){selectMatter(choice.dataset.cmSelect);}
      const action=e.target.closest('[data-cm-action]');if(action&&task){
        const kind=action.dataset.cmAction,reason=$('cm-review-reason').value.trim(),message=$('cm-review-message');
        if(reason.length<3){message.textContent='请写明至少三个字的处理理由。';return;}
        const matterIds=kind==='merge'?[...document.querySelectorAll('[data-cm-merge]:checked')].map(n=>n.dataset.cmMerge):[selected];
        try{action.disabled=true;const value=await api(`/runs/${encodeURIComponent(task.task_id)}/matter-revisions`,{method:'POST',body:JSON.stringify({expected_revision:task.result.result_revision,action_id:crypto.randomUUID(),action:kind,matter_ids:matterIds,evidence_ids:[...document.querySelectorAll('[data-cm-evidence]:checked')].map(n=>n.dataset.cmEvidence),reason})});document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:value.task_id}}));}catch(error){message.textContent=error.message;}finally{action.disabled=false;}
      }
    });
    $('cm-import-start').addEventListener('click',async()=>{const message=$('cm-import-message');try{const job=await api('/catalog/report-set-imports',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({ticker:$('cm-import-ticker').value,years:$('cm-import-years').value.split(/[,，]/).map(v=>Number(v.trim())).filter(Boolean),confirmed_identity:$('cm-import-confirm').checked})});message.textContent='资料准备任务 '+job.task_id;const poll=async()=>{try{const value=await api('/catalog/imports/'+encodeURIComponent(job.task_id));message.textContent=value.status+' · '+(value.error||JSON.stringify(value.result?.import_progress||{}));if(['queued','running'].includes(value.status))setTimeout(poll,2000);else loadDocuments().catch(()=>{});}catch(error){message.textContent=error.message;}};poll();}catch(error){message.textContent=error.message;}});
    loadDocuments().catch(e=>{$('cm-documents').textContent=e.message;});
  }
  if(typeof document!=='undefined'){
    if(document.readyState==='loading'&&!document.getElementById('cn-form'))document.addEventListener('DOMContentLoaded',init,{once:true});
    else init();
  }
  return{project,render,prepareRequest,activateLegacy,labels,latestRoleTasks};
});
