/* 四阶段导航只管理可见性。运行事实、证据与状态由 connectivity.js 和接口持有。 */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), root=$('connectivity-root'), main=$('cn-workspace');
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const historyKey='audittrace-connectivity-history-v2';
  let task=null, stage=1, error=null, view='workflow',historyRows=null,historyGeneration=0,historyOffset=0,historyNext=null;
  const savedRows=()=>{try{return JSON.parse(localStorage.getItem(historyKey)||'[]').filter(r=>/^(CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}$/.test(r.id)).slice(0,30);}catch{return [];}};
  const route=mode=>{document.body.dataset.route=mode;$('redesign-home').hidden=mode==='workspace';root.hidden=false;};
  const heroSvg = `<svg viewBox="0 0 560 250" xmlns="http://www.w3.org/2000/svg" fill="none" aria-hidden="true">
    <defs>
      <linearGradient id="awPaperA" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff"/><stop offset="1" stop-color="#cfdfd2"/></linearGradient>
      <linearGradient id="awPaperB" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f2fbf3"/><stop offset="1" stop-color="#9fcdb3"/></linearGradient>
      <linearGradient id="awCable" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#bfe3ce"/><stop offset="1" stop-color="#6fbfa2"/></linearGradient>
    </defs>
    <path d="M45 199 C152 149 240 252 347 179 S500 170 570 112" stroke="#8fbfa8" stroke-width="1.2" opacity=".35" stroke-dasharray="4 7"/>
    <path d="M19 100C138 54 185 167 293 99S468 22 559 60" stroke="#a8c9b3" opacity=".28"/>
    <g opacity=".42" stroke="#aecbb8" stroke-width=".8">
      <path d="M41 211 130 182 221 211 129 244zM301 201 395 170 488 200 393 230z"/>
      <path d="M40 212v19m89-50v20m92 10v20m80-29v24m94-55v22m93 18v22"/>
    </g>
    <g class="aw-float">
      <g transform="translate(112 30) rotate(-8 87 95)">
        <rect x="11" y="21" width="154" height="180" rx="8" fill="#183c30" opacity=".18"/>
        <rect x="0" y="7" width="154" height="179" rx="6" fill="url(#awPaperA)" stroke="#fff" stroke-opacity=".6"/>
        <rect x="0" y="7" width="154" height="19" rx="6" fill="#dcebdd"/>
        <circle cx="12" cy="16" r="2" fill="#709a7e"/><circle cx="20" cy="16" r="2" fill="#709a7e"/>
        <text x="16" y="45" fill="#3e6352" font-family="Arial" font-size="9" letter-spacing="1.3">ANNUAL REPORT</text>
        <text x="16" y="72" fill="#1d4032" font-family="Arial" font-size="27" font-weight="700">2025</text>
        <path d="M16 84h69m-69 5h106" stroke="#8fa991" stroke-width="2" opacity=".55"/>
        <path d="M17 150v-46m0 46h114" stroke="#9aae9c" stroke-width="1"/>
        <path d="m25 137 20-13 21 9 19-30 19 12 22-33" stroke="#3f7a5e" stroke-width="3"/>
        <circle cx="126" cy="82" r="3" fill="#3f7a5e"/>
        <path d="M15 163h82m-82 7h110" stroke="#9eb5a2" stroke-width="2" opacity=".55"/>
      </g>
      <g transform="translate(303 20) rotate(9 73 104)">
        <rect x="11" y="24" width="151" height="180" rx="8" fill="#123b2d" opacity=".18"/>
        <rect x="0" y="9" width="151" height="182" rx="6" fill="url(#awPaperB)" stroke="#fff" stroke-opacity=".65"/>
        <rect x="0" y="9" width="151" height="20" rx="6" fill="#c6e3ce"/>
        <circle cx="13" cy="18" r="2" fill="#6f9e84"/><circle cx="21" cy="18" r="2" fill="#6f9e84"/>
        <text x="15" y="46" fill="#4b7563" font-family="Arial" font-size="9" letter-spacing="1.1">SUSTAINABILITY</text>
        <text x="15" y="73" fill="#255447" font-family="Arial" font-size="26" font-weight="700">ESG</text>
        <path d="M15 86h77m-77 5h106" stroke="#7fa28d" stroke-width="2" opacity=".55"/>
        <circle cx="75" cy="139" r="32" stroke="#a9cbb6" stroke-width="13"/>
        <path d="M75 107a32 32 0 0 1 27 50" stroke="#529278" stroke-width="13"/>
        <path d="M75 107a32 32 0 0 1 27 50" stroke="#d6f3e1" stroke-width="1"/>
        <path d="M15 174h82m-82 7h109" stroke="#94b3a0" stroke-width="2" opacity=".6"/>
      </g>
    </g>
    <path d="M255 114Q289 70 323 112" stroke="url(#awCable)" stroke-width="3" stroke-linecap="round" stroke-dasharray="5 6"/>
    <circle cx="287" cy="88" r="22" fill="#245444" stroke="#a9dfc6" stroke-width="1.5"/>
    <path d="M278 88h18m-9-9v18" stroke="#e6fff3" stroke-width="2" stroke-linecap="round"/>
    <circle cx="487" cy="72" r="2" fill="#c8f0dc"/><circle cx="72" cy="153" r="3" fill="#c8f0dc"/>
  </svg>`;

  main.insertAdjacentHTML('beforebegin', `<aside class="cn-sidebar aw-side">
    <a href="#top" class="aw-brand" data-home>
      <span class="aw-brand-mark"><svg viewBox="0 0 30 30" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 7h12l6 8-6 8H6V7Z"/><path d="M10 12h9m-9 6h9M15 7v16"/></svg></span>
      <span><span class="aw-brand-cn">审迹智链</span><span class="aw-brand-en">AUDITTRACE / 2026</span></span>
    </a>
    <div class="aw-side-section">WORKSPACE / 工作空间</div>
    <nav class="aw-nav" aria-label="工作空间">
      <button type="button" data-at-view="workflow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 5v14M5 12h14" stroke-linecap="round"/></svg>新建核验<span>01</span></button>
      <button type="button" data-at-view="history"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4m8-4v4M4 10h16M8 14h8m-8 3h5"/></svg>历史记录<span>02</span></button>
      <button type="button" data-view="result" id="cn-result-nav" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M5 4h10l4 4v12H5zM15 4v5h5M8 13h8M8 17h6"/></svg>当前任务<span>03</span></button>
      <button type="button" data-at-view="method"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.4v1.2" stroke-linecap="round"/></svg>方法说明<span>04</span></button>
    </nav>
    <div class="aw-note">
      <div class="aw-note-label">EVIDENCE FIRST —</div>
      <div class="aw-note-title">从披露出发，<br>让每个判断都有出处。</div>
      <div class="aw-note-desc">同一企业 · 跨年度承诺<br>事项 → 路径 → 反证 → 回查</div>
    </div>
    <div class="aw-side-spacer"></div>
    <div class="aw-side-user">
      <span class="aw-avatar">审</span>
      <span><span class="aw-user-name">公开核验工作区</span><span class="aw-user-desc">演示环境 / DEMO MODE</span></span>
      <span class="aw-chev">⌄</span>
    </div>
  </aside>`);

  const shell = document.createElement('div'); shell.className = 'cn-app-layout'; main.before(shell); shell.append(document.querySelector('.cn-sidebar'), main);


  main.insertAdjacentHTML('afterbegin',`<div class="at-workspace-top"><div><p class="at-eyebrow">AUDITTRACE / RESEARCH WORKSPACE</p><h1>可持续信息与财务关联分析</h1></div><label class="at-search">搜索本次事项<input id="aw-search" type="search" placeholder="指标、原文或 AI 意见" aria-label="搜索当前核对结果" autocomplete="off"></label></div>
    <nav class="at-stages" aria-label="分析工作流">${['资料准备','事项与五Agent调查','关注点与资料需求','原文回查与导出'].map((name,i)=>`<button type="button" data-at-stage="${i+1}" aria-current="${i===0?'step':'false'}"><span>0${i+1}</span><strong>${name}</strong><small id="at-stage-state-${i+1}">${i===0?'开始':'待开始'}</small></button>`).join('')}</nav>
    <div id="aw-search-results" class="at-search-results" hidden></div>`);
  const setup=document.createElement('section');setup.id='cn-view-new';setup.dataset.workspaceView='new';setup.dataset.atPanel='1';
  const intro=document.querySelector('.cn-intro'),start=document.querySelector('.cn-start');
  intro.before(setup);setup.append(intro,start,$('cn-message'));
  intro.innerHTML='<p class="at-eyebrow">01 / REPORT SELECTION</p><h2>从可持续披露，追踪财务影响的依据。</h2><p>选择同一企业多个年度的报告，定位可持续事项和财务项目。AI 寻找关联、解释与反证；程序检查引用、比较前提与计算。</p>';
  const hero=document.createElement('section');hero.className='aw-hero';hero.setAttribute('aria-label','可持续事项调查');hero.innerHTML=`<div class="aw-hero-copy"></div><div class="aw-hero-vis">${heroSvg}</div>`;intro.before(hero);hero.querySelector('.aw-hero-copy').append(intro);
  const execution=document.createElement('section');execution.id='at-execution';execution.dataset.atPanel='2';execution.hidden=true;
  execution.innerHTML='<div class="at-section-head"><div><p class="at-eyebrow">02 / MULTI-AGENT COLLABORATION</p><h2>看见判断怎样形成</h2></div><button type="button" data-at-stage="3" id="at-to-insights" disabled>查看已有结果 ↗</button></div><p id="at-execution-note">尚未启动分析。角色节点与执行记录在服务端回执到达后显示。</p>';
  setup.after(execution);execution.append($('cn-stagebar'),document.querySelector('.cn-collaboration'),$('cn-task-error'));
  const results=$('cn-results');results.dataset.atPanel='3';results.dataset.workspaceView='result';
  const evidence=document.createElement('section');evidence.id='at-evidence';evidence.dataset.atPanel='4';evidence.hidden=true;
  evidence.innerHTML='<header class="at-section-head"><div><p class="at-eyebrow">04 / EVIDENCE & DELIVERY</p><h2>依据可回查，结果可带走</h2><p>所选事项与穿透图保持一致。导出包含原始状态、AI 意见与待核条件。</p></div></header><div id="at-export-toolbar" class="at-export-toolbar"></div>';
  results.after(evidence);$('at-export-toolbar').append(document.querySelector('.cn-tools'));evidence.append(document.querySelector('.cn-reading-guide'),$('cn-all-relations'));
  const technical=document.createElement('details');technical.className='at-technical';technical.innerHTML='<summary>任务身份、运行方式与模型记录</summary>';
  $('cn-result-title').after(technical);technical.append($('cn-run-meta'),$('cn-task-strip'));
  const about=document.querySelector('.cn-about');about.dataset.workspaceView='method';about.open=true;about.hidden=true;
  const historyView=document.createElement('section');historyView.id='at-history';historyView.dataset.workspaceView='history';historyView.hidden=true;
  historyView.innerHTML='<p class="at-eyebrow">HISTORY / VERIFIED TASK RECORDS</p><h2>历史真实任务</h2><p>任务内容重新从服务器读取；保留原权限、失败和过期状态。</p><ol id="cn-history-list" class="cn-history-list"></ol><details><summary>按任务编号打开</summary><form id="cn-open-task"><label>任务编号<input id="cn-task-id" pattern="(CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}" required placeholder="CONNJOB-… 或 DEMO-RUN-…"></label><button type="submit">读取记录</button></form></details>';
  main.append(historyView);
  historyView.insertAdjacentHTML('beforeend','<p id="cn-history-state" role="status"></p><button type="button" id="cn-history-more" hidden>更多历史记录</button>');
  document.querySelector('.aw-nav').insertAdjacentHTML('beforeend','<button type="button" id="cn-active-entry" hidden></button>');
  document.querySelector('.aw-nav').insertAdjacentHTML('beforeend','<button type="button" id="cn-clear-queue" hidden></button>');
  document.addEventListener('audittrace:connectivity-queue',e=>{const count=e.detail.pending,b=$('cn-clear-queue');b.hidden=!count;b.textContent=`待逐项调查 ${count} 项 · 清空等待队列`;});
  $('cn-clear-queue').addEventListener('click',()=>document.dispatchEvent(new CustomEvent('audittrace:connectivity-clear-queue')));
  function renderHistory() {
    $('cn-history-list').innerHTML=(historyRows??savedRows()).map(row=>`<li><button type="button" data-open-task="${esc(row.id)}"><strong>${esc(row.company || row.id)}</strong><span>${esc(row.mode==='five_agents'?'真实五Agent深查':row.mode==='calculation_only'?'原文初筛':'核查任务')} · ${esc(row.status || '状态待读取')} · ${esc(row.time || '')}</span><small>${esc(row.id)}${row.parent_id?' · 前序任务 '+esc(row.parent_id):''}</small></button></li>`).join('') || '<li class="at-empty">暂无可读取的历史任务。</li>';
  }
  async function loadHistory(more=false){
    const generation=++historyGeneration,offset=more?(historyNext??0):0;
    $('cn-history-state').textContent='正在读取服务端历史…';
    try{
      const response=await fetch(`/api/connectivity/runs?limit=10&offset=${offset}`,{credentials:'same-origin'}),data=await response.json();
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'服务端历史读取失败');
      if(generation!==historyGeneration)return;
      const rows=data.items.map(r=>({id:r.task_id,company:r.company||r.case_id,status:window.AuditTraceViewModel.statusNames[r.status]||r.status,time:new Date(r.created_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}),mode:r.execution_mode,parent_id:r.parent_task_id}));
      historyRows=more?[...(historyRows||[]),...rows]:rows;historyOffset=offset;historyNext=data.next_offset;
      localStorage.setItem(historyKey,JSON.stringify(historyRows.slice(0,30)));renderHistory();
      $('cn-history-state').textContent='已读取服务端记录';$('cn-history-more').hidden=historyNext==null;
    }catch(error){if(generation!==historyGeneration)return;$('cn-history-state').textContent=`${error.message}；显示本浏览器缓存，状态以重新读取为准。`;historyRows=null;renderHistory();}
  }
  $('cn-history-more').addEventListener('click',()=>loadHistory(true));
  document.addEventListener('audittrace:connectivity-active',e=>{
    const active=e.detail,entry=$('cn-active-entry');entry.hidden=!active;
    if(active){const phases={evidence_load:'原文准备',rule_calculation:'事项初筛',knowledge_retrieval:'工具准备',agent_collaboration:'五Agent调查',evidence_validation:'证据复核',structured_output:'生成结果'};entry.dataset.openTask=active.task_id;entry.textContent=`${['queued','running'].includes(active.status)?'进行中任务':'最近运行'} · ${active.company||active.task_id} · ${active.connection_error?'连接待恢复':phases[active.current_stage]||window.AuditTraceViewModel.statusNames[active.status]||active.status}`;}
  });
  function openTask(id) {
    const url=new URL(location.href);url.searchParams.set('connectivity_task',id);url.hash='connectivity-root';history.pushState({},'',url);
    document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:id}}));
  }
  function showStage(next,focus=false) {
    if(next>=3&&!task?.result)return;
    stage=next;view='workflow';route('workspace');
    root.dataset.awView=next===1?'new':'result';
    document.querySelectorAll('[data-at-panel]').forEach(p=>p.hidden=Number(p.dataset.atPanel)!==next);
    about.hidden=true;historyView.hidden=true;
    document.querySelector('.at-stages').hidden=false;
    document.querySelectorAll('[data-at-stage]').forEach(b=>{if(b.closest('.at-stages'))b.setAttribute('aria-current',Number(b.dataset.atStage)===next?'step':'false');});
    if(focus){const title=(next===1?intro:next===2?execution:next===3?results:evidence).querySelector('h1,h2');if(title){title.tabIndex=-1;title.focus({preventScroll:true});}main.scrollIntoView({block:'start'});}
  }
  function showView(next) {
    if(next==='workflow'){showStage(task?.result?3:1,true);return;}
    view=next;route('workspace');root.dataset.awView=next;
    document.querySelectorAll('[data-at-panel]').forEach(p=>p.hidden=true);
    document.querySelector('.at-stages').hidden=true;about.hidden=next!=='method';historyView.hidden=next!=='history';
    $('aw-search-results').hidden=true;renderHistory();if(next==='history')loadHistory();
  }
  function renderError(detail) {
    error=detail;const target=$('cn-task-error');target.hidden=!detail;
    if(detail){
      window.CNAuditGraph?.reset();
      ['cn-collaboration','cn-agents','cn-fourq','cn-nextq'].forEach(id=>$(id).replaceChildren());
      $('cn-stagebar').hidden=true;
      window.AuditTraceWorkbench.reset();
    }
    target.innerHTML=detail?`<h3 id="cn-task-error-title">${esc(({expired:'任务已过期或不存在',forbidden:'当前浏览器无法读取',preflight_failed:'报告资料需要修正',failed:'本次分析未完成',unavailable:'服务暂时不可用'})[detail.status] || '任务未完成')}</h3><p>${esc(detail.message || detail.error || '服务端未返回可用结果。')}</p><p>${detail.preflight||detail.status==='preflight_failed'?'尚未创建分析任务。请调整资料选择；其余勾选不会因此丢失。':'已取得的结果以保存版本为准，未完成不代表没有风险线索。'}</p><button type="button" data-at-stage="1">返回选择报告</button>`:'';
  }
  function search() {
    const q=$('aw-search').value.trim().toLowerCase(),run=task?.result,target=$('aw-search-results');
    if(!q || !run){target.hidden=true;target.replaceChildren();return;}
    if(run.matter_schema_version){
      const hits=(run.matters||[]).filter(m=>[m.name,m.identity_basis,...(run.matter_evidence||[]).filter(b=>m.evidence_ids.includes(b.evidence_id)).map(b=>b.quote),...(run.matter_assessments||[]).filter(a=>a.matter_id===m.matter_id).map(a=>a.summary)].join(' ').toLowerCase().includes(q));
      target.hidden=false;target.innerHTML=`<p role="status">本任务保存内容中找到 ${hits.length} 项事项；未命中不代表企业未披露。</p>${hits.map(m=>`<button type="button" data-cm-select="${esc(m.matter_id)}">${esc(m.name)} ↗</button>`).join('')}`;
      return;
    }
    const occurrences=new Map((run.occurrences||[]).map(o=>[o.occurrence_id,o]));
    const hits=(run.checks||[]).filter(c=>[c.title,c.mapping_reason,c.explanation,...(c.members||[]).map(m=>occurrences.get(m.occurrence_id)?.context),...(run.ai_analyses||[]).filter(a=>a.check_id===c.check_id&&a.status!=='needs_refresh').map(a=>a.summary)].join(' ').toLowerCase().includes(q));
    target.hidden=false;target.innerHTML=`<p role="status">本任务已提取内容中找到 ${hits.length} 项；未命中不代表报告未披露。</p>${hits.map(c=>`<button type="button" data-search-check="${esc(c.check_id)}">${esc(c.title)} ↗</button>`).join('')}`;
  }
  root.addEventListener('click',e=>{
    const control=e.target.closest('button,a');if(!control)return;
    if(control.dataset.cmSelect){showStage(3);$('aw-search-results').hidden=true;}
    if(control.dataset.atStage)showStage(Number(control.dataset.atStage),true);
    if(control.dataset.atView){if(control.dataset.atView==='workflow'){showStage(1,true);}else{showView(control.dataset.atView);}}
    if(control.dataset.openTask)openTask(control.dataset.openTask);
    if(control.dataset.searchCheck){showStage(3);document.dispatchEvent(new CustomEvent('audittrace:connectivity-select-check',{detail:{check_id:control.dataset.searchCheck,task_id:task?.task_id}}));$('aw-search-results').hidden=true;}
  });
  document.addEventListener('click',e=>{
    if(e.target.closest('[data-enter-connectivity]')){route('workspace');showStage(task?.result?3:1);window.scrollTo({top:0,behavior:'instant'});}
    if(e.target.closest('[data-home]')){e.preventDefault();route('home');const url=new URL(location.href);url.searchParams.delete('connectivity_task');url.hash='top';history.pushState({},'',url);window.scrollTo({top:0});}
  });
  $('cn-open-task').addEventListener('submit',e=>{e.preventDefault();openTask($('cn-task-id').value.trim());});
  $('aw-search').addEventListener('input',search);
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'&&task?.result){e.preventDefault();$('aw-search').focus();}});
  document.addEventListener('audittrace:connectivity-stage',e=>showStage(Number(e.detail.stage),true));
  document.addEventListener('audittrace:connectivity-start',()=>{
    window.CNAuditGraph?.reset();
    task=null;renderError(null);
    ['cn-collaboration','cn-agents','cn-fourq','cn-nextq'].forEach(id=>$(id).replaceChildren());
    $('cn-stagebar').hidden=true;$('cn-progress').hidden=true;$('at-to-insights').disabled=true;
    document.querySelectorAll('.at-stages [data-at-stage]').forEach(b=>{b.disabled=Number(b.dataset.atStage)>=3;});
    [2,3,4].forEach(i=>$('at-stage-state-'+i).textContent='等待本次回执');
    showStage(2,true);$('at-execution-note').textContent='正在读取或创建任务。收到服务端回执后展示真实执行阶段。';
  });
  document.addEventListener('audittrace:connectivity-reset',()=>{
    window.CNAuditGraph?.reset();
    task=null;renderError(null);$('aw-search').value='';$('aw-search-results').hidden=true;
    ['cn-fourq','cn-nextq','cn-collaboration','cn-agents'].forEach(id=>$(id).replaceChildren());
    [2,3,4].forEach(i=>$('at-stage-state-'+i).textContent='待开始');showStage(1);
  });
  document.addEventListener('audittrace:connectivity-task',e=>{
    const previousId=task?.task_id,previousStatus=task?.status;task=e.detail;renderError(null);
    const active=['queued','running'].includes(task.status),complete=Boolean(task.result);
    const text=window.AuditTraceViewModel.statusNames[task.status]||task.status;
    $('at-execution-note').textContent=`${text} · 阶段与角色状态以服务端记录为准。${complete?'可回到此页查看实际协作与交接。':''}`;
    $('at-to-insights').disabled=!complete;
    $('at-stage-state-1').textContent='已选择';$('at-stage-state-2').textContent=text;
    $('at-stage-state-3').textContent=complete?'结果可读':'等待结果';$('at-stage-state-4').textContent=complete?'证据 / 导出就绪':'等待结果';
    document.querySelectorAll('.at-stages [data-at-stage]').forEach(b=>{b.disabled=Number(b.dataset.atStage)>=3&&!complete;});
    const rows=savedRows().filter(r=>r.id!==task.task_id);rows.unshift({id:task.task_id,company:task.result?`${task.result.company} · ${task.result.period}`:$('cn-pair').selectedOptions[0]?.textContent,status:text,time:new Date().toLocaleString('zh-CN')});
    localStorage.setItem(historyKey,JSON.stringify(rows.slice(0,30)));renderHistory();
    if(view==='workflow' && (previousId!==task.task_id || (previousStatus!==task.status&&complete)))showStage(complete?3:2);
    else if(active&&view==='workflow')showStage(2);
    search();
  });
  document.addEventListener('audittrace:connectivity-task-error',e=>{task=null;renderError(e.detail);showStage(2);document.querySelectorAll('.at-stages [data-at-stage]').forEach(b=>{b.disabled=Number(b.dataset.atStage)>=3;});$('at-to-insights').disabled=true;$('at-stage-state-2').textContent='未完成';$('at-execution-note').textContent='本次未形成完整结果，具体原因如下。';});
  window.addEventListener('popstate',()=>{const id=new URL(location.href).searchParams.get('connectivity_task');if(id)openTaskFromHistory(id);else if(location.hash==='#connectivity-root')showStage(task?.result?3:1);else route('home');});
  function openTaskFromHistory(id){document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:id}}));}
  window.addEventListener('hashchange',()=>{if(location.hash==='#connectivity-root')route('workspace');});
  renderHistory();
  route(location.hash==='#connectivity-root'||new URL(location.href).searchParams.has('connectivity_task')?'workspace':'home');
  document.querySelectorAll('.at-stages [data-at-stage]').forEach(b=>{b.disabled=Number(b.dataset.atStage)>=3;});
  document.documentElement.dataset.connectivityWorkspaceReady='true';
  document.dispatchEvent(new CustomEvent('audittrace:connectivity-workspace-ready'));
})();
