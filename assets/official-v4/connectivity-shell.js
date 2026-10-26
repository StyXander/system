/* 四阶段导航只管理可见性。运行事实、证据与状态由 connectivity.js 和接口持有。 */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), root=$('connectivity-root'), main=$('cn-workspace');
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const historyKey='audittrace-connectivity-history-v2';
  let task=null, stage=1, error=null, view='workflow';
  const savedRows=()=>{try{return JSON.parse(localStorage.getItem(historyKey)||'[]').filter(r=>/^(CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}$/.test(r.id)).slice(0,30);}catch{return [];}};
  const route=mode=>{document.body.dataset.route=mode;$('redesign-home').hidden=mode==='workspace';root.hidden=mode!=='workspace';};
  main.insertAdjacentHTML('afterbegin',`<div class="at-workspace-top"><div><p class="at-eyebrow">AUDITTRACE / RESEARCH WORKSPACE</p><h1>可持续信息与财务关联分析</h1></div><label class="at-search">搜索本次事项<input id="aw-search" type="search" placeholder="指标、原文或 AI 意见" aria-label="搜索当前核对结果" autocomplete="off"></label></div>
    <nav class="at-stages" aria-label="分析工作流">${['选择企业与报告','多智能体协同分析','关联分析与审计研判','证据回查与结果导出'].map((name,i)=>`<button type="button" data-at-stage="${i+1}" aria-current="${i===0?'step':'false'}"><span>0${i+1}</span><strong>${name}</strong><small id="at-stage-state-${i+1}">${i===0?'开始':'待开始'}</small></button>`).join('')}</nav>
    <div id="aw-search-results" class="at-search-results" hidden></div>`);
  const setup=document.createElement('section');setup.id='cn-view-new';setup.dataset.workspaceView='new';setup.dataset.atPanel='1';
  const intro=document.querySelector('.cn-intro'),start=document.querySelector('.cn-start');
  intro.before(setup);setup.append(intro,start,$('cn-message'));
  intro.innerHTML='<p class="at-eyebrow">01 / REPORT SELECTION</p><h2>从可持续披露，追踪财务影响的依据。</h2><p>选择同一企业多个年度的报告，定位可持续事项和财务项目。AI 寻找关联、解释与反证；程序检查引用、比较前提与计算。</p>';
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
  function renderHistory() {
    $('cn-history-list').innerHTML=savedRows().map(row=>`<li><button type="button" data-open-task="${esc(row.id)}"><strong>${esc(row.company || row.id)}</strong><span>${esc(row.status || '状态待读取')} · ${esc(row.time || '')}</span><small>${esc(row.id)}</small></button></li>`).join('') || '<li class="at-empty">本浏览器暂无任务。完成一次分析后可从这里恢复真实记录。</li>';
  }
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
    $('aw-search-results').hidden=true;renderHistory();
  }
  function renderError(detail) {
    error=detail;const target=$('cn-task-error');target.hidden=!detail;
    if(detail){
      window.CNAuditGraph?.reset();
      ['cn-collaboration','cn-agents','cn-fourq','cn-nextq'].forEach(id=>$(id).replaceChildren());
      $('cn-stagebar').hidden=true;
      window.AuditTraceWorkbench.reset();
    }
    target.innerHTML=detail?`<h3 id="cn-task-error-title">${esc(({expired:'任务已过期或不存在',forbidden:'当前浏览器无法读取',failed:'分析失败',unavailable:'服务暂时不可用'})[detail.status] || '任务未完成')}</h3><p>${esc(detail.message || detail.error || '服务端未返回可用结果。')}</p><p>没有分析结果，不代表零异常。</p><button type="button" data-at-stage="1">返回选择报告</button>`:'';
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
    if(control.dataset.atView)showView(control.dataset.atView);
    if(control.dataset.openTask)openTask(control.dataset.openTask);
    if(control.dataset.searchCheck){showStage(3);document.dispatchEvent(new CustomEvent('audittrace:connectivity-select-check',{detail:{check_id:control.dataset.searchCheck,task_id:task?.task_id}}));$('aw-search-results').hidden=true;}
  });
  document.addEventListener('click',e=>{
    if(e.target.closest('[data-enter-connectivity]')){route('workspace');showStage(task?.result?3:1);}
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
