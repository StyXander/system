/* 页面组织层：只管理导航、步骤和阅读，不生成核验事实或模型调用。 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const root = $('connectivity-root'), main = $('cn-workspace');
  const safe = value => String(value??'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let step = 1, task = null, view = 'new';
  const historyKey = 'audittrace-connectivity-history-v2';
  function historyRows() { try { return JSON.parse(localStorage.getItem(historyKey)||'[]').filter(row => /^(CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}$/.test(row.id)).slice(0,30); } catch { return []; } }
  const intro = document.querySelector('.cn-intro'), start = document.querySelector('.cn-start'), about = document.querySelector('.cn-about');
  // 导航只保留三个稳定入口：当前任务、历史记录、历史业务入口。
  main.insertAdjacentHTML('beforebegin', `<aside class="cn-sidebar"><a href="#top" class="cn-brand" data-home>审迹智链 <small>AuditTrace</small></a><p>关联核对工作台</p><span class="cn-nav-label">工作空间</span><nav aria-label="工作空间"><button type="button" data-view="new">新建核验 <span>＋</span></button><button type="button" data-view="history">历史记录 <span>↗</span></button><button type="button" data-view="result" id="cn-result-nav" hidden>当前任务 <span>↗</span></button><button type="button" data-view="method">方法说明 <span>↗</span></button></nav><div class="cn-sidebar-note">同一企业 · 同一期间<br>先核前提，再复算关系。</div></aside>`);
  const shell = document.createElement('div'); shell.className = 'cn-app-layout'; main.before(shell); shell.append(document.querySelector('.cn-sidebar'), main);
  main.insertAdjacentHTML('afterbegin', '<div class="cn-breadcrumb" id="cn-breadcrumb">工作台 / 新建核验</div>');
  const create = document.createElement('section'); create.id = 'cn-view-new'; create.dataset.workspaceView = 'new'; main.insertBefore(create, intro); create.append(intro, start);
  intro.querySelector('h1').textContent = '开始一次双报告核验';
  intro.querySelector('.cn-eyebrow').textContent = 'NEW VERIFICATION / 新建核验';
  document.querySelector('.cn-principles').hidden = true;
  const form = $('cn-form'), row = document.querySelector('.cn-form-row'), pair = $('cn-pair').parentElement, mode = $('cn-mode').parentElement, topics = document.querySelector('.cn-topics'), run = $('cn-run');
  form.innerHTML = ''; row.remove();
  form.insertAdjacentHTML('beforeend', `<ol class="cn-stepper" aria-label="新建核验步骤">${['选择报告','核对设置','确认并执行'].map((name, i) => `<li><button type="button" data-step="${i+1}"><span>0${i+1}</span>${name}</button></li>`).join('')}</ol><section id="cn-step-1"><h2>选择要核对的两份报告</h2><p class="cn-help">使用已登记的公开原件，企业与报告期间自动配对。</p></section><section id="cn-step-2" hidden><h2>这次想核对哪些事项？</h2><p class="cn-help">默认核对全部事项；三角色寻找关系依据、解释与反证。</p></section><section id="cn-step-3" hidden><h2>准备开始核验</h2><div id="cn-confirm"></div><p class="cn-help">实际阶段由服务端更新。模型未完成时，计算结果与未决条件仍分别保留。</p></section><div class="cn-step-actions"><button type="button" id="cn-prev">上一步</button><button type="button" id="cn-next" class="cn-primary">下一步：核对设置 →</button></div>`);
  $('cn-step-1').append(pair, $('cn-documents')); $('cn-step-2').append(topics);
  const advanced = document.createElement('details'); advanced.className = 'cn-advanced'; advanced.innerHTML = '<summary>高级设置：速度与模型调用</summary><p>三角色：计算并调用模型核对依据；仅计算：不调用模型；单模型：用于对照阅读，仍会调用模型。</p>'; advanced.append(mode); $('cn-step-2').append(advanced); $('cn-step-3').append(run);
  $('cn-results').dataset.workspaceView = 'result'; about.dataset.workspaceView = 'method'; about.open = true;
  main.insertAdjacentHTML('beforeend', '<section data-workspace-view="history" hidden><p class="cn-eyebrow">RECENT RECORDS</p><h1>历史记录</h1><p class="cn-help">仅列出本浏览器实际访问的任务，最多保留30条入口；任务内容从服务器重新读取，原有权限仍然适用。</p><form id="cn-open-task"><label>通过任务编号打开记录<input id="cn-task-id" required pattern="(CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}" placeholder="CONNJOB-… 或 DEMO-RUN-…"></label><button type="submit">读取记录</button></form><div id="cn-history-list"></div></section>');
  document.querySelectorAll('[data-workspace-view="dashboard"]').forEach(node => node.remove());
  function selectTab() { /* 详情标签由 connectivity.js 管理，这里不再维护结果级标签 */ }
  function showView(key) {
    if (key==='result' && !task?.result) return;
    view = key;
    root.querySelectorAll('[data-workspace-view]').forEach(el => { el.hidden = el.dataset.workspaceView!==key; });
    root.querySelectorAll('.cn-sidebar [data-view]').forEach(el => { if (el.dataset.view===key) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current'); });
    $('cn-breadcrumb').textContent = `工作台 / ${{new:'新建核验',history:'历史记录',method:'方法说明',result:'当前任务'}[key]||key}`;
    renderHistory();
  }
  function setStep(value, focus=false) {
    if (value>1 && !$('cn-pair').value) return;
    if (value===3 && !form.querySelector('[name="topic"]:checked')) { $('cn-message').textContent = '至少选择一个关注事项。'; return; }
    step = value;
    for (let i=1; i<=3; i++) $(`cn-step-${i}`).hidden = i!==step;
    form.querySelectorAll('[data-step]').forEach(button => { button.setAttribute('aria-current', Number(button.dataset.step)===step ? 'step' : 'false'); button.disabled = Number(button.dataset.step)>step; });
    $('cn-prev').hidden = step===1; $('cn-next').hidden = step===3;
    $('cn-next').textContent = step===1 ? '下一步：核对设置 →' : '下一步：确认并执行 →';
    if (focus) { const heading = $(`cn-step-${step}`).querySelector('h2'); heading.tabIndex = -1; heading.focus(); }
    $('cn-confirm').innerHTML = `<h3>${safe($('cn-pair').selectedOptions[0]?.textContent||'')}</h3><p>${[...form.querySelectorAll('[name="topic"]:checked')].map(el => safe(el.parentElement.textContent.trim())).join(' · ')}</p><p>${safe($('cn-mode').selectedOptions[0].textContent)}</p>`;
  }
  function renderHistory() {
    const rows = historyRows();
    const html = rows.length ? rows.map(row => `<article class="cn-history-row"><div><strong>${safe(row.company||'报告核对任务')}</strong><small>${safe(row.id)} · ${safe(row.status)} · ${safe(row.time)}</small></div><button type="button" data-open-task="${safe(row.id)}">打开记录 ↗</button></article>`).join('') : '<p class="cn-empty">尚无本浏览器访问记录。开始一次核验，或用已有任务编号读取。</p>';
    $('cn-history-list').innerHTML = html;
  }
  function openTask(id) { const url = new URL(location.href); url.searchParams.set('connectivity_task', id); url.hash = 'connectivity-root'; location.assign(url); }
  root.addEventListener('click', event => {
    const target = event.target.closest('button,a'); if (!target) return;
    if (target.dataset.view) showView(target.dataset.view);
    if (target.dataset.step) setStep(Number(target.dataset.step), true);
    if (target.dataset.openTask) openTask(target.dataset.openTask);
    if (target.hasAttribute('data-home')) {
      event.preventDefault(); root.hidden = true; $('redesign-home').hidden = false;
      const url = new URL(location.href); url.searchParams.delete('connectivity_task'); url.hash = 'top';
      history.replaceState(null, '', url); $('redesign-home').scrollIntoView({behavior:'instant'});
      document.querySelector('[data-enter-connectivity]').focus();
    }
  });
  $('cn-next').addEventListener('click', () => setStep(step+1, true));
  $('cn-prev').addEventListener('click', () => setStep(step-1, true));
  form.addEventListener('submit', event => { if (step!==3) { event.preventDefault(); event.stopImmediatePropagation(); setStep(step+1); } }, true);
  $('cn-open-task').addEventListener('submit', event => { event.preventDefault(); openTask($('cn-task-id').value.trim()); });
  document.addEventListener('audittrace:connectivity-task', event => {
    task = event.detail; const run = task.result;
    const rows = historyRows().filter(row => row.id!==task.task_id);
    rows.unshift({id:task.task_id, company:run?`${run.company} · ${run.period}`:$('cn-pair').selectedOptions[0]?.textContent,
      status:({completed:'已完成',running:'进行中',queued:'排队中',failed:'失败',degraded:'部分完成',cancelled:'已取消',interrupted:'已中断'})[task.status]||task.status,
      time:new Date().toLocaleString('zh-CN')});
    localStorage.setItem(historyKey, JSON.stringify(rows.slice(0,30))); renderHistory();
    if (run) { $('cn-result-nav').hidden = false; showView('result'); }
    else if (['queued','running'].includes(task.status)) showView('new');
  });
  // 深链接与刷新直接恢复工作空间，品牌首页保持独立。
  if (location.hash==='#connectivity-root' || new URL(location.href).searchParams.has('connectivity_task')) { $('redesign-home').hidden = true; root.hidden = false; }
  setStep(1); showView('new');
})();
