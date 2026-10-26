/* 事项工作台只呈现保存结果，不在浏览器推断专业结论或触发隐性模型调用。 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.AuditTraceMatters=api;
})(typeof window==='undefined'?globalThis:window,function(){
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const roles={A1:'事项识别与建档',A2:'财务影响调查',A3:'跨期承诺与后果追踪',A4:'边界解释与反证',A5:'综合复核与补证'};
  const labels={pending:'待调查',running:'调查中',completed:'已完成',partial:'部分完成',skipped:'未执行',failed:'失败',cancelled:'已取消',
    candidate:'身份待确认',evidence_linked:'有据关联候选',human_confirmed:'人工确认身份',limited:'部分支持',supported:'有据支持',
    conflicting:'存在反证',not_comparable:'不可直接比较',invalid:'来源失效',not_assessed:'尚未评价',needs_evidence:'待补证',
    hypothesis:'候选解释',supported_as_reported:'报告披露支持',challenged:'受到质疑',unresolved:'尚未解决',
    not_due:'目标期限未到',progress_unknown:'进展待核',revised:'目标已修订',needs_review:'需要核查',
    promise:'承诺',revision:'修订',action:'行动',investment:'投入',commissioning:'投运',performance:'绩效',financial:'财务信息',risk:'风险',termination:'终止',
    five_agents_partial:'五Agent部分完成',five_agents_completed:'五Agent角色已完成',matter_three_partial:'三Agent对照部分完成',matter_three_completed:'三Agent对照已完成',matter_single_partial:'单模型对照部分完成',matter_single_completed:'单模型对照已完成',not_requested:'未调用模型',
    unreviewed:'未人工采用',accepted:'已采用为核查参考',rejected:'已驳回',report_statement:'企业原文陈述',model_hypothesis:'模型机制假设'};
  const label=k=>labels[k]||k;
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
  let selected=null,task=null,documents=[],catalog=null,choicesCompany=null;
  const $=id=>document.getElementById(id);
  async function api(path,options={}){
    const response=await fetch('/api/connectivity'+path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json',...options.headers}});
    const data=await response.json().catch(()=>({detail:'服务未返回可读取结果'}));
    if(!response.ok){const detail=data.detail,error=new Error(typeof detail==='string'?detail:(detail?.message||'请求未完成')+(detail?.documents||[]).map(d=>`；${d.company||''} ${d.period||''} ${d.report_type||''}（${d.document_id}）：${d.message||''}`).join(''));error.status=response.status;error.code=detail?.code;error.documents=detail?.documents;error.preflight=path==='/report-sets';throw error;}return data;
  }
  function refs(ids,run){return(ids||[]).map(id=>{const b=(run.matter_evidence||[]).find(e=>e.evidence_id===id);return b?`<a href="/api/connectivity/sources/${encodeURIComponent(b.document_id)}?page=${b.pdf_page}" target="_blank" rel="noopener">${esc(b.report_period)} ${esc(b.report_type)} PDF ${b.pdf_page} ↗</a>`:'';}).join(' · ');}
  function list(values){return values?.length?`<ul>${values.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`:'<p class="cm-muted">当前没有保存的记录。</p>';}
  function render(value){
    task=value;const run=value.result,p=project(run,selected);selected=p.matter?.matter_id;
    let host=$('cn-matter-results');if(!host){host=document.createElement('section');host.id='cn-matter-results';$('cn-results').append(host);}
    host.hidden=false;document.body.classList.add('cm-active');
    ['cn-financial','cn-all-relations'].forEach(id=>{if($(id))$(id).hidden=true;});
    document.querySelectorAll('.cn-overview').forEach(e=>e.hidden=true);
    const overview=run.matter_overview||{};
    host.innerHTML=`<header class="cm-heading"><p class="at-eyebrow">MATTER INVESTIGATION</p><h2>可持续事项与财务影响</h2><p>观察截至 ${esc(run.report_set?.as_of_date)} · ${esc(run.documents.length)} 份报告 · ${esc(label(run.model_status))}</p></header>
      <div class="cm-counts">${[['事项',overview.matter_total],['已深查',overview.investigated],['待调查',overview.pending],['综合意见',overview.assessment_count]].map(([k,n])=>`<div><span>${esc(k)}</span><strong>${esc(n??0)}</strong></div>`).join('')}</div>
      <p class="cm-muted">${esc(overview.notice||'未形成事项不代表报告没有相关事项，请检查资料和解析覆盖。')}</p>
      ${run.report_set?.coverage_gaps?.length?`<details><summary>资料缺口</summary>${list(run.report_set.coverage_gaps)}</details>`:''}
      <div class="cm-layout"><aside class="cm-list" aria-label="事项档案"><h3>事项档案</h3>${(run.matters||[]).map(m=>`<div class="cm-list-row"><input type="checkbox" aria-label="选择整理事项 ${esc(m.name)}" data-cm-merge="${esc(m.matter_id)}"><button type="button" data-cm-select="${esc(m.matter_id)}" aria-pressed="${m.matter_id===selected}"><strong>${esc(m.name)}</strong><span>${esc(label(m.identity_status))} · ${esc(label(m.investigation_status))}</span></button></div>`).join('')||'<p>没有已保存事项。</p>'}</aside>
      <article class="cm-detail" aria-live="polite">${p.matter?detailHtml(p,run):'<h3>尚未形成可展示事项</h3><p>请查看原件与解析覆盖，或选择其他资料。</p>'}</article></div>
      <details class="cm-coverage"><summary>解析覆盖和调用预算</summary><p>首轮 ${esc(run.versions?.seed_coverage?.seed_blocks??0)} 个原文块 / 已索引 ${esc(overview.indexed_blocks??0)} 个。首轮未入选块可由工具继续检索。</p>${(run.matter_coverage||[]).map(c=>`<p>${esc(c.document_id)} · ${esc(c.total_pages)} 页 · ${esc(c.failed_pages?.length??0)} 页解析限制 · OCR ${c.ocr_enabled?'开启':'关闭'}</p>`).join('')}<pre>${esc(JSON.stringify(run.versions?.budget||{},null,2))}</pre></details>`;
    renderEvidence(p,run);
    const col=$('cn-collaboration');if(col)col.innerHTML=collaborationHtml(run);
  }
  function detailHtml(p,run){
    const a=p.assessment,m=p.matter;
    return`<h3 tabindex="-1" id="cm-selected-title">${esc(m.name)}</h3><p>${esc(m.identity_basis)}</p>${m.attention_signals?.length?`<details open><summary>本次关注变化（调查顺序参考）</summary>${list(m.attention_signals)}<p class="cm-muted">这些信号不代表财务重要性阈值或错误认定。</p></details>`:''}
      <section class="cm-verdict"><h4>当前判断与模型综合意见</h4><p>${esc(a?.summary||'该事项尚未完成综合复核，当前仅保留原文线索。')}</p><div class="cm-tags"><span>关联 ${esc(label(a?.relation_support||'pending'))}</span><span>金额 ${esc(label(a?.amount_comparability||'not_assessed'))}</span><span>采用 ${esc(label(a?.review_status||'unreviewed'))}</span></div><p>承诺进展：${esc(a?.commitment_progress||'待调查')}</p><p>财务阶段：${esc(a?.financial_stage||'待调查')}</p>${list(a?.unresolved)}</section>
      <section><h4>财务影响路径</h4>${p.paths.map(path=>`<div class="cm-path"><strong>${esc(path.financial_item)} · ${esc(label(path.support))}</strong><ol>${path.steps.map(s=>`<li><strong>${esc(s.label)}</strong> · ${esc(label(s.support))}<p>${esc(s.explanation)}</p><small>${esc(label(s.origin))}</small><div>${refs(s.evidence_ids,run)}</div></li>`).join('')}</ol></div>`).join('')||'<p>尚未建立有证据约束的财务路径。主题相近或金额相等均不能替代该调查。</p>'}</section>
      ${p.relations?.length?`<section><h4>信息关系与共同归属</h4>${p.relations.map(e=>{const name=id=>(run.matter_graph?.nodes||[]).find(n=>n.id===id)?.label||id;return `<div class="cm-hypothesis"><p>${esc(name(e.source_id))} → ${esc(name(e.target_id))}</p><small>${esc(e.relation_kind)} · ${esc(label(e.evidence_status))} · ${esc(label(e.assertion_origin))}</small><p>${esc(e.explanation)}</p>${refs(e.evidence_ids,run)}</div>`;}).join('')}</section>`:''}
      <section><h4>承诺与财务两线追踪</h4><div class="cm-timelines">${[['承诺 行动与绩效',false],['财务影响',true]].map(([title,financial])=>`<div><h5>${title}</h5><ol>${p.events.filter(e=>(e.kind==='financial')===financial).map(e=>`<li><strong>${esc(e.report_period)} · ${esc(label(e.kind))}${e.evidence_status==='invalid'?' · 来源失效':''}</strong><p>${esc(e.label)}</p><small>发生期间 ${esc(e.occurred_period||'原文未明确')} · 披露 ${esc(e.disclosure_date||'未登记')}</small><div>${refs(e.evidence_ids,run)}</div></li>`).join('')||'<li>当前未取得该线的事件证据。</li>'}</ol></div>`).join('')}</div>${p.commitments.map(c=>`<p class="cm-commitment">基期 ${esc(c.baseline_year||'未明确')} · 目标期 ${esc(c.target_year||'未明确')} · ${esc(label(c.status))}${c.evidence_status==='invalid'?' · 来源失效':''}${c.supersedes?' · 修订自 '+esc(c.supersedes):''}<br>${esc(c.label)}<br>${refs(c.evidence_ids,run)}</p>`).join('')}</section>
      <section><h4>边界与竞争解释</h4>${p.explanations.map(h=>`<div class="cm-hypothesis"><strong>${esc(label(h.status))}</strong><p>${esc(h.explanation)}</p><p>区分证据：${esc(h.discriminating_evidence)}</p><p>支持 ${refs(h.supporting_evidence_ids,run)||'待取得'} · 反证 ${refs(h.counter_evidence_ids,run)||'未取得'}</p></div>`).join('')||'<p>当前没有保存的竞争解释；不能据此认定差异合理。</p>'}</section>
      <section><h4>下一步核查</h4>${(a?.next_actions||[]).map(n=>`<div class="cm-action"><strong>${esc(n.target_role)} · ${esc(n.question)}</strong><p>资料：${esc(n.requested_material)}</p><p>用途：${esc(n.purpose)}</p></div>`).join('')||'<p>尚未形成具体补证任务。</p>'}${a?.assumptions?.length?'<h5>成立所需假设</h5>'+list(a.assumptions):''}${a?.disagreements?.length?'<h5>未解决分歧</h5>'+list(a.disagreements):''}</section>
      <details><summary>当前事项的角色记录</summary>${p.tasks.map(t=>`<p><strong>${esc(t.role)} ${esc(roles[t.role]||'')}</strong> · ${esc(label(t.status))} · ${esc(t.stop_reason)}</p>`).join('')||'<p>没有实际角色记录。</p>'}</details>
      ${task.can_modify?'<details class="cm-review"><summary>事项整理与意见采用</summary><p>归并请勾选左侧事项；拆分请在原文列表勾选部分证据。操作保存为子版本，原记录保留。</p><label>理由<input id="cm-review-reason" type="text" minlength="3" maxlength="2000"></label><div class="cm-review-actions"><button type="button" data-cm-action="merge">归并已选事项</button><button type="button" data-cm-action="split">按已选证据拆分</button><button type="button" data-cm-action="accept">采用当前意见</button><button type="button" data-cm-action="reject">驳回当前意见</button></div><p id="cm-review-message" role="status"></p></details>':''}`;
  }
  function renderEvidence(p,run){
    let host=$('cn-matter-evidence');if(!host){host=document.createElement('section');host.id='cn-matter-evidence';($('at-evidence')||$('cn-results')).append(host);}
    host.hidden=false;
    host.innerHTML=`<h3>${esc(p.matter?.name||'事项原文')}</h3><p>引文与页码来自同一保存版本；通过链接打开登记原页。</p>${p.evidence.map(b=>`<article class="cm-evidence"><label><input type="checkbox" data-cm-evidence="${esc(b.evidence_id)}"> ${esc(b.report_period)} ${esc(b.report_type)} · PDF ${b.pdf_page}</label><p>${esc(b.quote)}</p><small>${esc(b.evidence_id)} · ${esc(b.extraction_method)}${b.invalid_reason?' · '+esc(b.invalid_reason):''}</small><div>${refs([b.evidence_id],run)}</div></article>`).join('')||'<p>当前没有可回查的事项引用。</p>'}`;
  }
  function collaborationHtml(run){
    return`<div class="cm-agent-grid">${Object.entries(roles).map(([role,name])=>{const tasks=(run.matter_tasks||[]).filter(t=>t.role===role);return`<article><h4>${role} ${name}</h4>${tasks.map(t=>`<p>${esc(label(t.status))} · ${esc(t.stop_reason)}</p>`).join('')||'<p>没有该角色的实际回执。</p>'}</article>`;}).join('')}</div><details><summary>工具查询与新证据</summary>${(run.matter_tool_receipts||[]).map(r=>`<p><strong>${esc(r.role)} · ${esc(r.tool_name)}</strong> · ${esc(r.status)}<br>${esc(r.result?.query||r.reason||'')}<br>返回 ${esc(r.result?.evidence?.length??0)} 个证据块</p>`).join('')||'<p>没有实际工具调用。</p>'}</details>`;
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
    if(body.retry_of_task_id&&task?.result?.report_set){delete body.pair_id;body.report_set_id=task.result.report_set.report_set_id;body.analysis_scope='matter_connectivity';return body;}
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
    setup.innerHTML=`<summary>事项调查与多年资料范围</summary><label><input id="cm-matter-scope" type="checkbox" checked>按可持续事项调查财务影响与跨期进展</label><p>同一企业可选多个年度，允许缺年或只有一类报告。每年同类型请选择一个版本。</p><fieldset id="cm-matter-types"><legend>调查事项</legend><label><input type="checkbox" name="matter_type" value="climate_risk" checked>气候风险与会计估计</label><label><input type="checkbox" name="matter_type" value="transition_project" checked>绿色改造与转型项目</label><label><input type="checkbox" name="matter_type" value="commitment" checked>目标与跨年承诺</label><label><input type="checkbox" name="matter_type" value="resource_efficiency" checked>资源效率与绩效</label><label><input type="checkbox" name="matter_type" value="other" checked>其他财务线索</label></fieldset><label>观察截至日期<input id="cm-as-of" type="date" value="${new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'})}"></label><div id="cm-documents" class="cm-document-choices"></div><button type="button" id="cm-refresh-docs">刷新登记资料</button><details><summary>接入尚未登记的年度报告</summary><label>证券代码<input id="cm-import-ticker" pattern="[0-9]{6}" maxlength="6"></label><label>年度 用逗号分隔<input id="cm-import-years" placeholder="2023,2024,2025"></label><label><input id="cm-import-confirm" type="checkbox">已确认企业身份</label><button type="button" id="cm-import-start">准备多年资料</button><p id="cm-import-message" role="status"></p></details>`;
    $('cn-form').after(setup);$('cm-refresh-docs').addEventListener('click',()=>loadDocuments().catch(e=>{$('cm-documents').textContent=e.message;}));
    const scopeChanged=()=>{const active=$('cn-mode').value==='five_agents'||($('cm-matter-scope').checked&&$('cn-mode').value!=='adaptive_agents');document.querySelector('.cn-topics').hidden=active;$('cm-matter-types').hidden=!active;};
    $('cm-matter-scope').addEventListener('change',scopeChanged);$('cn-mode').addEventListener('change',scopeChanged);scopeChanged();
    $('cn-pair').addEventListener('change',drawDocumentChoices);$('cm-as-of').addEventListener('change',drawDocumentChoices);
    document.addEventListener('audittrace:connectivity-ready',e=>{if(e.detail?.matter_enabled===false){setup.hidden=true;$('cm-matter-scope').checked=false;const option=$('cn-mode').querySelector('[value=five_agents]');if(option)option.disabled=true;scopeChanged();}drawDocumentChoices();});
    document.addEventListener('audittrace:select-pair',()=>setTimeout(()=>loadDocuments().catch(()=>{}),0));
    document.addEventListener('audittrace:connectivity-task',e=>{if(e.detail.result?.matter_schema_version){task=e.detail;const c=$('cn-collaboration');if(c)c.innerHTML=collaborationHtml(task.result);}});
    document.addEventListener('audittrace:connectivity-reset',()=>{selected=null;task=null;activateLegacy();});
    document.addEventListener('click',async e=>{
      const choice=e.target.closest('[data-cm-select]');if(choice&&task){selected=choice.dataset.cmSelect;render(task);$('cm-selected-title')?.focus({preventScroll:true});}
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
  return{project,render,prepareRequest,activateLegacy,labels};
});
