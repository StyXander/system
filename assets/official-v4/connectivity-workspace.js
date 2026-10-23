/* 页面组织层：只管理导航、步骤和阅读，不生成核验事实或模型调用。 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const root = $('connectivity-root'), main = $('cn-workspace');
  const safe = value => String(value??'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let step = 1, task = null, view = 'new', taskError = null;
  const historyKey = 'audittrace-connectivity-history-v2';
  function historyRows() { try { return JSON.parse(localStorage.getItem(historyKey)||'[]').filter(row => /^(CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}$/.test(row.id)).slice(0,30); } catch { return []; } }
  /* 首页与工作台是两条路由：进入工作台后收起长 hero，返回首页才恢复，
     这样结果页不会再被首页大图反复打断。 */
  function setRoute(mode) {
    document.body.dataset.route = mode;
    if (mode==='workspace') document.getElementById('redesign-home')?.setAttribute('aria-hidden', 'true');
    else document.getElementById('redesign-home')?.removeAttribute('aria-hidden');
  }
  const intro = document.querySelector('.cn-intro'), start = document.querySelector('.cn-start'), about = document.querySelector('.cn-about');

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
      <button type="button" data-view="new"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 5v14M5 12h14" stroke-linecap="round"/></svg>新建核验<span>01</span></button>
      <button type="button" data-view="history"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4m8-4v4M4 10h16M8 14h8m-8 3h5"/></svg>历史记录<span>02</span></button>
      <button type="button" data-view="result" id="cn-result-nav" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M5 4h10l4 4v12H5zM15 4v5h5M8 13h8M8 17h6"/></svg>当前任务<span>03</span></button>
      <button type="button" data-view="method"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.4v1.2" stroke-linecap="round"/></svg>方法说明<span>04</span></button>
    </nav>
    <div class="aw-note">
      <div class="aw-note-label">EVIDENCE FIRST —</div>
      <div class="aw-note-title">从披露出发，<br>让每个判断都有出处。</div>
      <div class="aw-note-desc">同一企业 · 同一期间<br>定位 → 对齐 → 计算 → 解释</div>
    </div>
    <div class="aw-side-spacer"></div>
    <div class="aw-side-user">
      <span class="aw-avatar">审</span>
      <span><span class="aw-user-name">公开核验工作区</span><span class="aw-user-desc">演示环境 / DEMO MODE</span></span>
      <span class="aw-chev">⌄</span>
    </div>
  </aside>`);

  const shell = document.createElement('div'); shell.className = 'cn-app-layout'; main.before(shell); shell.append(document.querySelector('.cn-sidebar'), main);

  main.insertAdjacentHTML('afterbegin', `<div class="cn-breadcrumb aw-toolbar" id="cn-breadcrumb">
    <div class="aw-crumb"><span>审迹智链</span><i>/</i><span>工作空间</span><i>/</i><b id="aw-crumb-current">新建核验</b></div>
    <div class="aw-toolbar-right">
      <label class="aw-search" for="aw-search">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="7" cy="7" r="4.6"/><path d="M10.6 10.6 14 14"/></svg>
        <input id="aw-search" type="search" placeholder="搜索关系、原文片段或AI意见" aria-label="搜索当前核对结果" aria-controls="aw-search-results cn-check-list" autocomplete="off">
        <kbd>⌘K</kbd>
      </label>
      <button class="aw-circle" type="button" data-view="method" aria-label="方法说明" title="方法说明">?</button>
      <span class="aw-top-tag">PUBLIC WORKSPACE</span>
    </div>
  </div>`);

  const create = document.createElement('section');
  create.id = 'cn-view-new';
  create.dataset.workspaceView = 'new';
  main.insertBefore(create, intro);
  create.innerHTML = `<div class="aw-headrow">
      <div>
        <div class="aw-kicker">DISCLOSURE INTELLIGENCE / 工作台</div>
        <h1 class="aw-page-title">关联核对工作台<span>/ 新建核验</span></h1>
        <p class="aw-sub">面向年报与可持续发展报告的证据关联、口径比对与差异追踪。</p>
      </div>
      <div class="aw-head-meta">
        <span class="aw-label">任务模式&nbsp; <b>公开报告</b></span>
        <span class="aw-label">资料来源&nbsp; <b>已登记原件</b></span>
      </div>
    </div>
    <section class="aw-hero" aria-label="双报告核验">
      <div class="aw-hero-copy"></div>
      <div class="aw-hero-vis">${heroSvg}</div>
    </section>
    <div class="aw-grid">
      <div class="aw-form-col"></div>
      <aside class="aw-path" aria-label="核验流程">
        <div class="aw-card-kicker">VERIFICATION MAP / WORKFLOW</div>
        <h3>一次核验，怎样形成判断？</h3>
        <p>不是黑箱分数；从前提到证据，逐段留痕。</p>
        <div class="aw-path-mini"><span>✦</span><div><b>双报告关联分析</b><small>4 个关键动作 · 实际执行以后台为准</small></div></div>
        <ol class="aw-timeline">
          <li><b>01</b><div><strong>接入两份登记原件</strong><small>企业、期间与报告版本配对</small></div></li>
          <li><b>02</b><div><strong>确认可比较的前提</strong><small>主体 / 期间 / 定义 / 范围 / 单位</small></div></li>
          <li><b>03</b><div><strong>执行规则核对与试算</strong><small>关系计算、假设诊断及差异定位</small></div></li>
          <li><b>04</b><div><strong>寻找解释与反向证据</strong><small>必要时调用模型，保留未决条件</small></div></li>
        </ol>
      </aside>
    </div>
    <div class="aw-new-bottom">
      <div class="aw-bottom-card">
        <div class="aw-bottom-heading">本次关注事项</div>
        <div class="aw-topic-chips" id="aw-topic-chips"></div>
        <span class="aw-bottom-hint">默认全部关注 ↗</span>
      </div>
      <div class="aw-bottom-card aw-bottom-note">
        <span class="aw-bottom-icon">⬡</span>
        <div><b>公开核验 · 原文优先</b><small>界面展示；实际阶段与结果以本次运行留痕为准</small></div>
      </div>
    </div>`;

  create.querySelector('.aw-hero-copy').append(intro);
  create.querySelector('.aw-form-col').append(start, $('cn-message'));

  intro.querySelector('h1').innerHTML = '两份报告，一条证据链。<br><span class="aw-hero-line">从数字差异，回到原文事实。</span>';
  intro.querySelector('.cn-eyebrow').textContent = 'ANNUAL REPORT × SUSTAINABILITY REPORT';
  const introP = intro.querySelector('p:not(.cn-eyebrow)');
  if (introP) introP.innerHTML = '比较主体、期间和披露口径，再追溯关系、计算与解释。<br>条件不完整时，继续给出带假设的分析。';
  const principles = intro.querySelector('.cn-principles');
  if (principles) { principles.hidden = false; principles.innerHTML = '<span>报告关联</span><span>口径核对</span><span>原文追溯</span>'; }

  const form = $('cn-form'), row = document.querySelector('.cn-form-row'), pair = $('cn-pair').parentElement, mode = $('cn-mode').parentElement, topics = document.querySelector('.cn-topics'), run = $('cn-run');
  form.innerHTML = ''; row.remove();
  form.insertAdjacentHTML('beforeend', `<div class="aw-form-top"><span class="aw-card-kicker">NEW VERIFICATION / 核验任务</span><span class="aw-pill">● 新建任务</span></div><ol class="cn-stepper" aria-label="新建核验步骤">${['选择报告','核对设置','确认并执行'].map((name, i) => `<li><button type="button" data-step="${i+1}"><span>0${i+1}</span>${name}</button></li>`).join('')}</ol><section id="cn-step-1"><h2>选择要核对的两份报告</h2><p class="cn-help">同一企业与期间自动配对，核验从真实登记原件开始。</p></section><section id="cn-step-2" hidden><h2>这次想核对哪些事项？</h2><p class="cn-help">默认核对全部事项；三角色寻找关系依据、解释与反证。</p></section><section id="cn-step-3" hidden><h2>准备开始核验</h2><div id="cn-confirm"></div><p class="cn-help">实际阶段由服务端更新。模型未完成时，计算结果与未决条件仍分别保留。</p></section><div class="cn-step-actions"><button type="button" id="cn-prev">上一步</button><button type="button" id="cn-next" class="cn-primary">下一步：核对设置 →</button></div>`);
  $('cn-step-1').append(pair, $('cn-documents')); $('cn-step-2').append(topics);
  const advanced = document.createElement('details'); advanced.className = 'cn-advanced'; advanced.innerHTML = '<summary>高级设置：速度与模型调用</summary><p>三角色：计算并调用模型核对依据；仅计算：不调用模型；单模型：用于对照阅读，仍会调用模型。</p>'; advanced.append(mode); $('cn-step-2').append(advanced); $('cn-step-3').append(run);
  $('cn-results').dataset.workspaceView = 'result'; about.dataset.workspaceView = 'method'; about.open = true;
  main.insertAdjacentHTML('beforeend', `<section class="aw-history" data-workspace-view="history" hidden>
    <p class="cn-eyebrow">RECENT RECORDS / 历史记录</p>
    <h1>历史记录</h1>
    <p class="cn-help">默认列出本浏览器最近 5 条任务，按完成、失败、过期分开标注。任务内容从服务器重新读取，原有权限仍然适用；这里不借用他人会话的数据。</p>
    <ol id="cn-history-list" class="cn-history-list"></ol>
    <details class="aw-history-advanced"><summary>按任务编号打开（高级入口）</summary>
      <form id="cn-open-task"><label>任务编号<input id="cn-task-id" required pattern="(CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}" placeholder="CONNJOB-… 或 DEMO-RUN-…"></label><button type="submit">读取记录</button></form>
      <p class="cn-help">任务编号见结果页顶部“任务”一行；复制链接可连同编号一起分享。</p>
    </details>
    <div id="cn-history-more"></div>
  </section>`);
  document.querySelectorAll('[data-workspace-view="dashboard"]').forEach(node => node.remove());

  function syncTopicChips() {
    const wrap = $('aw-topic-chips'); if (!wrap) return;
    wrap.innerHTML = [...form.querySelectorAll('[name="topic"]')].map(el => {
      const text = el.parentElement.textContent.trim();
      return `<span class="aw-chip${el.checked ? ' on' : ''}">${el.checked ? '✓ ' : ''}${safe(text)}</span>`;
    }).join('');
  }
  syncTopicChips();
  form.addEventListener('change', event => { if (event.target.name === 'topic') syncTopicChips(); });

  function selectTab() { /* 详情标签由 connectivity.js 管理，这里不再维护结果级标签 */ }
  function showView(key) {
    if (key==='result' && !task?.result && !taskError) return;
    view = key;
    root.dataset.awView = key;
    if (key!=='result' && taskError) renderTaskError(null);
    if (document.activeElement !== document.body || root.getBoundingClientRect().top < 0) {
      /* 同页模式下切视图回到工作台顶部，而不是整页顶部 */
      if (root.getBoundingClientRect().top < -4) root.scrollIntoView({block:'start'});
    }
    root.querySelectorAll('[data-workspace-view]').forEach(el => { el.hidden = el.dataset.workspaceView!==key; });
    root.querySelectorAll('.cn-sidebar [data-view]').forEach(el => { if (el.dataset.view===key) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current'); });
    const current = $('aw-crumb-current');
    if (current) current.textContent = {new:'新建核验',history:'历史记录',method:'方法说明',result:'当前任务'}[key]||key;
    else $('cn-breadcrumb').textContent = `工作台 / ${{new:'新建核验',history:'历史记录',method:'方法说明',result:'当前任务'}[key]||key}`;
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
  /* 历史入口按“能不能直接点开”设计：默认 5 条，状态分开，编号只作高级入口。 */
  const historyTone = row => {
    const text = String(row.status||'');
    if (text.includes('完成')) return 'ok';
    if (text.includes('失败') || text.includes('中断') || text.includes('无法读取')) return 'warn';
    if (text.includes('过期') || text.includes('不存在')) return 'expired';
    if (text.includes('进行') || text.includes('排队')) return 'run';
    return 'neutral';
  };
  function historyItem(row) {
    const tone = historyTone(row);
    return `<li class="cn-history-row" data-tone="${tone}"><div class="cn-history-main"><span class="cn-history-dot" aria-hidden="true"></span><div><strong>${safe(row.company||'报告核对任务')}</strong><small>${safe(row.id)} · ${safe(row.time||'时间未记录')}</small></div></div><span class="cn-history-status">${safe(row.status||'状态未记录')}</span><button type="button" data-open-task="${safe(row.id)}">打开记录 ↗</button></li>`;
  }
  function renderHistory() {
    const rows = historyRows();
    const list = $('cn-history-list');
    if (!list) return;
    list.innerHTML = rows.length ? rows.slice(0,5).map(historyItem).join('') : '<li class="cn-empty">尚无本浏览器访问记录。开始一次核验，或用任务编号读取。</li>';
    $('cn-history-more').innerHTML = rows.length>5 ? `<details class="aw-history-all"><summary>查看其余 ${rows.length-5} 条</summary><ol class="cn-history-list">${rows.slice(5).map(historyItem).join('')}</ol></details>` : '';
  }
  function openTask(id) { const url = new URL(location.href); url.searchParams.set('connectivity_task', id); url.hash = 'connectivity-root'; location.assign(url); }

  /* 深链失败必须说清是哪一种：过期、无权限、还是服务不可用。 */
  function renderTaskError(error) {
    taskError = error || null;
    const box = $('cn-task-error');
    if (!error) { box.hidden = true; box.innerHTML = ''; return; }
    const expired = error.status==='expired' || error.code===410;
    const forbidden = error.status==='forbidden' || error.code===403;
    box.hidden = false;
    box.innerHTML = `<div class="cn-task-error-head"><p class="cn-eyebrow">TASK UNAVAILABLE</p><h2 id="cn-task-error-title">${expired?'这条任务链接已不可用':forbidden?'当前浏览器无权读取该任务':'任务结果未能读取'}</h2><p>${safe(error.message||'请稍后重试。')}</p></div>
      <div class="cn-task-error-actions"><button type="button" data-view="new">新建一次核验</button><button type="button" data-view="history">打开历史记录</button>${error.task_id?`<button type="button" data-retry-task="${safe(error.task_id)}">重新读取</button>`:''}</div>
      <p class="cn-help">链接仍可复制；能否读取取决于原任务的权限与保留期限。</p>`;
  }

  const search = $('aw-search');
  const searchResults = document.createElement('section');
  searchResults.id = 'aw-search-results'; searchResults.className = 'aw-search-results'; searchResults.hidden = true;
  searchResults.setAttribute('aria-label', '当前结果搜索命中');
  $('cn-results').prepend(searchResults);
  const normalizeSearch = value => String(value ?? '').normalize('NFKC').replace(/\s+/g, '').toLowerCase();
  const searchText = value => value && typeof value === 'object' ? Object.values(value).map(searchText).join(' ') : String(value ?? '');
  const occurrenceText = row => [row.label,row.context,row.document_id,row.pdf_page,row.row_header,row.column_header,row.year,row.value,row.unit,...(row.footnotes||[])].join(' ');
  function searchExcerpt(row, query) {
    const text = String(row.context || row.label || '').replace(/\s+/g, ' ');
    const at = text.toLowerCase().indexOf(query.trim().toLowerCase());
    const start = Math.max(0, at - 45);
    return `${start ? '…' : ''}${text.slice(start, start + 190)}${text.length > start + 190 ? '…' : ''}`;
  }
  function applySearch() {
    const run = task?.result, query = search.value.trim(), q = normalizeSearch(query);
    const buttons = [...$('cn-check-list').querySelectorAll('[data-check]')];
    if (!q || !run) {
      buttons.forEach(button => { button.hidden = false; });
      $('cn-count').textContent = String(buttons.length); searchResults.hidden = true; searchResults.replaceChildren(); return;
    }
    const occurrences = run.occurrences || [], rows = new Map(occurrences.map(row => [row.occurrence_id,row]));
    const analyses = [...(run.ai_analyses || []),...(run.ai_opinions || [])].filter(item => item.status !== 'needs_refresh');
    const matches = (run.checks || []).filter(check => {
      const refs = [...(check.members || []),...(check.relationship_evidence || []),...(check.conditions || []).flatMap(item => item.evidence || [])];
      const context = [...new Set(refs.map(ref => ref.occurrence_id))].map(id => rows.get(id)).filter(Boolean).map(occurrenceText).join(' ');
      return normalizeSearch([searchText(check),context,...analyses.filter(item => item.check_id === check.check_id).map(searchText)].join(' ')).includes(q);
    });
    const ids = new Set(matches.map(check => check.check_id));
    buttons.forEach(button => { button.hidden = !ids.has(button.dataset.check); });
    const visible = buttons.filter(button => !button.hidden).length;
    $('cn-count').textContent = `${visible} / ${buttons.length}`;
    const sourceMatches = occurrences.filter(row => normalizeSearch(occurrenceText(row)).includes(q));
    const documents = new Map((run.documents || []).map(doc => [doc.document_id,doc]));
    searchResults.hidden = false;
    searchResults.innerHTML = `<p role="status">“${safe(query)}”：${matches.length}项相关关系，${sourceMatches.length}处原文片段。左侧当前筛选显示${visible}项。</p><p class="cn-help">搜索范围：本次结果的关系、已提取原文片段和AI意见；不代表已搜索整份PDF。清空搜索恢复列表。</p>${matches.length ? `<details open><summary>相关关系（${matches.length}）</summary><div class="aw-search-hits">${matches.map(check => `<button type="button" data-search-check="${safe(check.check_id)}">${safe(check.title)}<small>查看关系及AI意见 ↗</small></button>`).join('')}</div></details>` : ''}${sourceMatches.length ? `<details open><summary>原文片段（${sourceMatches.length}）</summary><div class="aw-search-hits">${sourceMatches.map(row => `<button type="button" data-search-source="${safe(row.occurrence_id)}"><strong>${safe(documents.get(row.document_id)?.report_type === 'AR' ? '年报' : '报告')} · PDF ${safe(row.pdf_page)} · ${safe(row.label)}</strong><span>${safe(searchExcerpt(row, query))}</span><small>打开原页 ↗</small></button>`).join('')}</div></details>` : ''}${!matches.length && !sourceMatches.length ? '<p>本次结果中未命中。可尝试指标名或报告ID；这里未命中不代表报告原文不存在。</p>' : ''}`;
  }
  search.addEventListener('input', applySearch);
  // 切换视角、概览筛选或选中关系会重建列表；持续应用当前关键词。
  new MutationObserver(applySearch).observe($('cn-check-list'), {childList:true});
  searchResults.addEventListener('click', event => {
    const button = event.target.closest('[data-search-check],[data-search-source]'); if (!button) return;
    document.dispatchEvent(new CustomEvent('audittrace:connectivity-search-open', {detail:{check_id:button.dataset.searchCheck,occurrence_id:button.dataset.searchSource,trigger:button}}));
  });
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase()==='k' && root.dataset.awView==='result') { event.preventDefault(); search?.focus(); }
  });

  root.addEventListener('click', event => {
    const target = event.target.closest('button,a'); if (!target) return;
    if (target.dataset.view) { showView(target.dataset.view); }
    if (target.dataset.step) setStep(Number(target.dataset.step), true);
    if (target.dataset.openTask) openTask(target.dataset.openTask);
    if (target.dataset.retryTask) {
      renderTaskError(null);
      document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task', {detail:{task_id:target.dataset.retryTask}}));
    }
    if (target.hasAttribute('data-home')) {
      event.preventDefault();
      const url = new URL(location.href); url.searchParams.delete('connectivity_task'); url.hash = 'top';
      history.replaceState(null, '', url);
      setRoute('home');
      window.scrollTo({top:0, behavior:'smooth'});
      document.querySelector('#redesign-home .identity')?.focus({preventScroll:true});
    }
  });
  $('cn-next').addEventListener('click', () => setStep(step+1, true));
  $('cn-prev').addEventListener('click', () => setStep(step-1, true));
  form.addEventListener('submit', event => { if (step!==3) { event.preventDefault(); event.stopImmediatePropagation(); setStep(step+1); } }, true);
  $('cn-open-task').addEventListener('submit', event => { event.preventDefault(); openTask($('cn-task-id').value.trim()); });
  document.addEventListener('audittrace:connectivity-task', event => {
    task = event.detail; const run = task.result;
    taskError = null; renderTaskError(null); setRoute('workspace');
    const bar = $('cn-stagebar'); if (bar) { if (run) bar.dataset.stale='true'; else delete bar.dataset.stale; }
    const rows = historyRows().filter(row => row.id!==task.task_id);
    rows.unshift({id:task.task_id, company:run?`${run.company} · ${run.period}`:$('cn-pair').selectedOptions[0]?.textContent,
      status:({completed:'已完成',running:'进行中',queued:'排队中',failed:'失败',degraded:'部分完成',cancelled:'已取消',interrupted:'已中断'})[task.status]||task.status,
      time:new Date().toLocaleString('zh-CN')});
    localStorage.setItem(historyKey, JSON.stringify(rows.slice(0,30))); renderHistory();
    if (run) { $('cn-result-nav').hidden = false; showView('result'); applySearch(); }
    else if (['queued','running'].includes(task.status)) showView('new');
  });
  document.addEventListener('audittrace:connectivity-task-error', event => {
    const detail = Object.assign({}, event.detail);
    setRoute('workspace');
    task = null;
    // 过期或不存在时同步更新历史条目，避免列表里仍显示“已完成”。
    if (['expired','forbidden'].includes(detail.status)) {
      const rows = historyRows().map(row => row.id===detail.task_id
        ? {...row, status: detail.status==='expired' ? '已过期' : '无法读取（无权限）'} : row);
      localStorage.setItem(historyKey, JSON.stringify(rows));
    }
    renderTaskError(detail);
    $('cn-result-nav').hidden = true;
    showView('result');
  });
  // 首页与工作台是两条路由：深链只负责定位，不再把长 hero 留在结果页上方。
  const shared = new URL(location.href).searchParams.get('connectivity_task');
  if (location.hash==='#connectivity-root' || shared) {
    setRoute('workspace');
    requestAnimationFrame(() => root.scrollIntoView({block:'start'}));
  } else {
    setRoute('home');
  }
  // 浏览器前进/后退与刷新走同一条读取路径。
  window.addEventListener('popstate', () => {
    const id = new URL(location.href).searchParams.get('connectivity_task');
    if (id) {
      setRoute('workspace');
      document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task', {detail:{task_id:id}}));
      return;
    }
    if (location.hash==='#connectivity-root') { setRoute('workspace'); return; }
    setRoute('home'); showView('new');
  });
  // 任何“进入工作台”的入口都切到工作台路由，返回首页再恢复 hero。
  document.addEventListener('click', event => {
    if (event.target.closest('[data-enter-connectivity]')) setRoute('workspace');
  }, true);
  window.addEventListener('hashchange', () => { if (location.hash==='#connectivity-root') setRoute('workspace'); });
  // 首页样例只指向本浏览器真实访问过的记录，没有记录就不显示，不编造数字。
  const sampleRow = historyRows().find(row => historyTone(row)==='ok') || historyRows()[0];
  const heroSample = $('hero-sample');
  if (heroSample && sampleRow) {
    heroSample.hidden = false;
    heroSample.textContent = `查看最近一次真实记录 · ${sampleRow.company || sampleRow.id}`;
    heroSample.addEventListener('click', event => { event.preventDefault(); openTask(sampleRow.id); });
  }
  setStep(1); showView('new');
  // 初始视图就绪之后才允许恢复任务，避免结果事件被初始化的新建视图覆盖。
  document.documentElement.dataset.connectivityWorkspaceReady = 'true';
  document.dispatchEvent(new Event('audittrace:connectivity-workspace-ready'));
})();
