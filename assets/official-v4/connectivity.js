/* 事实、计算与未决条件来自同一后端结果；阅读视角不创建模型调用。 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {bootstrap:null, task:null, selected:null, timer:null, generation:0, detailTab:'conditions', reader:null};
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {supported:'有依据支持',unknown:'未说明',conflicting:'明确冲突',consistent:'所选关系计算一致',precision_explained:'已知精度可解释',
    adjustment_explained:'有据调节后与0相容',unexplained_difference:'未解释差异',not_comparable:'暂不可比较',not_executable:'暂不可执行',
    not_applicable:'不适用数值计算',read_confirmed:'使用者已阅读',unreviewed:'未人工复核',demo_modified:'使用者修订',
    completed:'已完成',running:'进行中',queued:'排队中',degraded:'部分完成',failed:'失败',cancelled:'已取消',interrupted:'已中断',
    expired:'已过期',skipped:'未执行',pending:'未开始',not_requested:'未调用模型',three_agents_completed:'三角色实际完成',three_agents_partial:'三角色已运行，部分关系超出本次预算',no_relations_to_review:'未形成可研判关系',single_completed:'单模型实际完成'};
  const roles = {left:'左侧',right:'右侧',total:'总额',component:'组成项',numerator:'分子',denominator:'分母',reported_ratio:'披露比例',occurrence:'披露位置'};
  const aiVerdicts = {lean_consistent:'倾向一致',potential_conflict:'存在潜在矛盾',plausible_explanation:'存在合理解释路径',insufficient_basis:'依据不足但可继续核查',not_comparable:'当前不可直接比较'};
  // 六个阶段与后端 steps 键一一对应，名称即阶段含义，不由前端估算。
  const phases = {evidence_load:'报告识别与披露定位',rule_calculation:'前提判断与关系计算',knowledge_retrieval:'原文补查（解释与反证）',
    agent_collaboration:'角色协作',evidence_validation:'核实与重算',structured_output:'未决与记录生成'};
  const STATE_ICON = {supported:'✓',consistent:'✓',precision_explained:'≈',adjustment_explained:'≈',unknown:'?',not_comparable:'!',
    conflicting:'×',unexplained_difference:'×',pending:'·',running:'▶',completed:'✓',degraded:'!',failed:'×',skipped:'–'};
  const status = value => `<span class="cn-badge" data-state="${escape(value)}"><span aria-hidden="true">${escape(STATE_ICON[value]||'·')}</span> ${escape(labels[value]||value)}</span>`;
  const message = (text, error=false) => { $('cn-message').textContent=text; $('cn-message').classList.toggle('error', error); };
  const busy = value => document.querySelectorAll('#cn-form input,#cn-form select,#cn-run').forEach(control => { control.disabled=value; });
  async function api(path, options={}) {
    const response = await fetch(`/api/connectivity${path}`, {credentials:'same-origin', ...options, headers:{'Content-Type':'application/json', ...options.headers}});
    const data = await response.json().catch(() => ({detail:'服务未返回可读取的结果'}));
    if (!response.ok) { const error = new Error(typeof data.detail==='string' ? data.detail : JSON.stringify(data.detail)); error.status=response.status; throw error; }
    return data;
  }
  function rememberTask(taskId) {
    localStorage.setItem('audittrace-connectivity-task', taskId);
    const url = new URL(location.href); url.searchParams.set('connectivity_task', taskId); history.replaceState({}, '', url);
  }
  const current = () => state.task?.result;
  const occurrence = id => current()?.occurrences.find(row => row.occurrence_id===id);
  const check = () => current()?.checks.find(row => row.check_id===state.selected);
  const sourceUrl = (id, page) => `/api/connectivity/sources/${encodeURIComponent(id)}?view=true&page=${page}`;
  const pageImage = (id, page) => `/api/connectivity/sources/${encodeURIComponent(id)}/pages/${page}.png`;
  const documentOf = id => current()?.documents.find(doc => doc.document_id===id);
  const docName = doc => doc ? `${doc.report_type==='AR' ? '年度报告' : '可持续发展 / ESG 报告'} · ${doc.document_id}` : '未登记文档';
  const refs = (items=[]) => items.map(ref => { const row = occurrence(ref.occurrence_id);
    return row ? `<button class="cn-evidence" type="button" data-reader="${escape(row.occurrence_id)}">原页 PDF ${row.pdf_page}</button>` : ''; }).join('');

  function reportCards() {
    const pair = state.bootstrap.pairs.find(p => p.pair_id===$('cn-pair').value);
    $('cn-documents').innerHTML = pair ? pair.documents.map(d => `<div class="cn-document"><strong>${escape(d.report_type==='AR'?'年度报告':'可持续发展 / ESG报告')} · ${escape(d.report_period||d.period)}</strong><small>${escape(d.version)}</small><a href="${sourceUrl(d.document_id,1)}" target="_blank" rel="noopener">阅读登记原件 ↗</a> <small>${escape(d.source_kind==='announcement_mirror'?'公告镜像，已单独标识':d.available?'本地原件已登记':'运行时从已登记官方来源取得')}</small></div>`).join('') : '';
  }

  async function poll(taskId, generation=state.generation) {
    try {
      const task = await api(`/runs/${encodeURIComponent(taskId)}`);
      if (generation!==state.generation) return;
      state.task = task; renderProgress(task);
      if (['queued','running'].includes(task.status)) {
        document.dispatchEvent(new CustomEvent('audittrace:connectivity-task', {detail:task}));
        busy(true); state.timer = setTimeout(() => poll(taskId, generation), 1800); return;
      }
      busy(false); $('cn-cancel').disabled = true;
      if (task.result) {
        render();
        document.dispatchEvent(new CustomEvent('audittrace:connectivity-task', {detail:task}));
        message(`${labels[task.status]||task.status}。${task.result.occurrences.length}处候选、${task.result.checks.length}项关系；模型状态：${labels[task.result.model_status]||task.result.model_status}。`);
      } else {
        document.dispatchEvent(new CustomEvent('audittrace:connectivity-task', {detail:task}));
        message(task.error || `任务${labels[task.status]||task.status}；未生成可读取结果。`, true);
      }
    } catch (error) {
      if (generation!==state.generation) return;
      if ([404,410].includes(error.status)) { busy(false); localStorage.removeItem('audittrace-connectivity-task'); message(`原任务无法取得：${error.message}。可以显式开始新运行。`, true); return; }
      $('cn-progress-state').textContent = '连接暂时中断 · 保留原阶段，正在重试读取';
      busy(true); message(`读取暂时失败：${error.message}。保留任务编号，正在重试读取原任务。`, true);
      state.timer = setTimeout(() => poll(taskId, generation), 4500);
    }
  }

  function renderStagebar(task) {
    const bar = $('cn-stagebar');
    if (!task || (!task.steps && !task.result)) { bar.hidden = true; return; }
    bar.hidden = false;
    const steps = task.steps || {};
    $('cn-stagebar-list').innerHTML = Object.entries(phases).map(([key, title], index) => {
      const item = steps[key] || {status:'pending', detail:'等待后端阶段记录'};
      const value = item.status || 'pending';
      return `<li data-status="${escape(value)}"><span class="cn-stage-index" aria-hidden="true">${index+1}</span><div><strong>${escape(title)}</strong><small>${escape(labels[value]||value)}${item.updated_at ? ` · ${escape(String(item.updated_at).replace('T',' ').slice(0,19))}` : ''}</small></div></li>`;
    }).join('');
    const failed = Object.entries(steps).filter(([, item]) => item.status==='failed');
    $('cn-stagebar-note').innerHTML = failed.length
      ? `阶段失败：${failed.map(([key]) => escape(phases[key]||key)).join('、')}。已完成阶段的产物仍可查看；失败原因见运行记录。<button type="button" id="cn-retry" class="cn-retry">重试本次核对</button>`
      : (task.result ? '阶段状态来自后端实际记录；修订只重算，不重跑模型阶段。' : '阶段状态来自后端实际记录，前端不估算百分比。');
  }

  function renderProgress(task) {
    // 修订只保存重算结果，没有重新执行原模型阶段，不显示虚假的等待进度。
    $('cn-progress').hidden = Boolean(task.result?.parent_run_id) || (!['queued','running'].includes(task.status) && !Object.keys(task.steps||{}).length);
    $('cn-cancel').disabled = !['queued','running'].includes(task.status);
    $('cn-progress').open = ['queued','running'].includes(task.status);
    $('cn-progress-summary').textContent = `运行记录 · ${labels[task.status]||task.status} · ${task.task_id}`;
    $('cn-progress-state').textContent = `${labels[task.status]||task.status} · ${task.task_id}`;
    $('cn-progress-details').innerHTML = Object.entries(phases).map(([key, title]) => { const item = task.steps?.[key];
      return `<p><strong>${escape(title)}</strong> · ${escape(labels[item?.status||'pending']||item?.status)}<br>${escape(item?.detail||'等待后端阶段记录')}${item?.updated_at?`<small>更新于 ${escape(item.updated_at)}</small>`:''}</p>`; }).join('')
      + Object.entries(task.agent_steps||{}).map(([role, item]) => `<p>${escape(role)} · ${escape(labels[item.status]||item.status)}：${escape(item.detail||'暂无记录')}</p>`).join('');
    renderStagebar(task);
  }

  function conclusionText(c) {
    const gate = c.calculation?.gate;
    if (gate) return `${gate.conclusion}：缺少${(gate.missing||[]).join('、')||'关键前提'}的原文依据。`;
    if (c.calculation_status==='consistent') return '所选成员在同口径下计算一致。';
    if (c.calculation_status==='precision_explained') return '差额可由已声明的精度区间解释。';
    if (c.calculation_status==='adjustment_explained') return '有原文依据的加性调节后，剩余残差区间含0。';
    if (c.calculation_status==='unexplained_difference') return `仍有未解释差额 ${c.calculation?.residual ?? ''} ${c.calculation?.normalized_unit||''}。`;
    if (c.calculation_status==='not_executable') return '本次关系暂不可执行计算，原因见未决条件。';
    if (c.calculation_status==='not_applicable') return '叙述关系只记录支持命题，不生成算式。';
    return '本次尚未形成可比较结论。';
  }

  function plainLayer(c) {
    const gate = c.calculation?.gate;
    const canSay = c.criteria_status==='supported' ? (gate ? '前提已支持，但算式仍待确认' : '前提与算式都已记录') : '前提尚未说明完整';
    const ask = current()?.findings.find(f => f.check_id===c.check_id)?.question || '可向公司了解该指标的口径、范围与版本。';
    return `<div class="cn-plain"><h3>这是什么</h3><p>${escape(c.title)}，按“${escape(state.bootstrap.rules[c.rule_id]?.name||c.rule_id)}”核对两处披露之间的关系。</p><h3>它和另一份报告哪处相关</h3><p>${escape(c.members.map(m => roles[m.role]+'：'+(occurrence(m.occurrence_id)?.label||'')).join('；')||'本次未登记成员')}。</p><h3>现在能确认什么、不能确认什么</h3><p>${escape(canSay)}；${escape(gate ? '因此不输出正式差额。' : conclusionText(c))}</p><h3>下一步可以问公司什么</h3><p>${escape(ask)}</p></div>`;
  }

  function render() {
    const run = current(); if (!run) return;
    const pair = state.bootstrap.pairs.find(p => p.pair_id===run.documents[0]?.case_id);
    if (pair) { $('cn-pair').value = pair.pair_id; reportCards(); }
    if ([...$('cn-mode').options].some(option => option.value===run.execution_mode)) $('cn-mode').value = run.execution_mode;
    $('cn-results').hidden = false;
    $('cn-result-title').textContent = `${run.company} · ${run.period} 关联核对`;
    const modes = {calculation_only:'自动发现 · 仅计算',three_agents:'自动发现 · 三角色核对',single_model:'自动发现 · 完整单模型对照'};
    $('cn-run-meta').textContent = `版本${run.result_revision} / ${modes[run.execution_mode]||run.execution_mode} / ${run.parent_run_id?'原自动运行耗时':''}${(run.duration_ms/1000).toFixed(1)}秒${run.parent_run_id?'；本次修订未新增模型调用':''}`;
    const exportBase = `/api/connectivity/runs/${encodeURIComponent(state.task.task_id)}/export`;
    $('cn-exports').innerHTML = ['json','csv','docx'].map(format => `<a href="${exportBase}/${format}">${format==='docx'?'Word':format.toUpperCase()}</a>`).join('')
      + (state.task.can_modify ? `<a href="${exportBase}/json?private=1" title="仅本人可见：导出含个人观察正文">JSON（含个人观察）</a>` : '');
    if (!run.checks.some(c => c.check_id===state.selected)) state.selected = (run.checks.find(c => c.relationship_evidence.length && ['RD-001','ENV-001','INT-001'].includes(c.rule_id)) || run.checks[0])?.check_id;
    renderOverview(); renderList(); renderDetail(); renderFindings(); renderCoverage(); renderUserRecords(); renderTimeline();
    $('cn-revisions').innerHTML = `<p>父运行：${escape(run.parent_run_id||'无，原始自动运行')}。当前版本${run.result_revision}。${state.task.parent_task_id?`<a href="?connectivity_task=${encodeURIComponent(state.task.parent_task_id)}" target="_blank" rel="noopener">打开修订前记录 ↗</a>`:''}</p>` + run.reviews.map(r => `<details><summary>${escape(r.created_at)} · ${escape(r.actor)} · ${escape(r.reason)}</summary><p>操作：${escape({relationship_correction:'关系更正',personal_observation:'个人观察',reading_confirmation:'阅读确认',ai_accept:'采纳AI意见',ai_reject:'驳回AI意见'}[r.action]||r.action)}；${escape(r.check_id)}</p><h4>修订前</h4>${reviewRecord(r.before)}<h4>修订后</h4>${reviewRecord(r.after)}</details>`).join('');
  }

  function renderOverview() {
    const run = current(); if (!run) return;
    const ov = run.overview || {};
    if (!ov.confirmable) {
      $('cn-fourq').innerHTML = '<p class="cn-empty">该记录生成于旧版结果合同，未包含四问汇总。请重新运行并保存新结果；旧记录仍可逐项阅读。</p>';
      $('cn-nextq').innerHTML = '';
      return;
    }
    const blocks = [
      ['能确认什么', ov.confirmable, '条件支持且计算成立', '关系数'],
      ['不能确认什么', ov.unconfirmable, '缺前提或存在冲突', '关系数'],
      ['还没解释什么', ov.unexplained, '仍有未解释残差', '关系数'],
      ['还没找到什么', ov.not_found, '未定位或提取失败', '页'],
    ];
    $('cn-fourq').innerHTML = blocks.map(([label, item, hint, unit]) => {
      const missing = (item?.missing_breakdown||[]).slice(0,4)
        .map(m => `${escape(m.name)} ${m.unsupported}${m.without_evidence ? `（无依据 ${m.without_evidence}）` : ''}`).join(' · ');
      const undecidable = item?.undecidable?.value ? `<p class="cn-fq-missing">另有 ${item.undecidable.value}/${item.undecidable.denominator} 项因前提未支持，无法判断差额是否已解释</p>` : '';
      const gap = label==='不能确认什么' && missing ? `<p class="cn-fq-missing">缺：${missing}</p>` : '';
      if (label === '还没找到什么') {
        // 未计入位置按"处"、失败页按"页"，两个比值分开写，不合成一个分数。
        const rows = item?.unattributed || {};
        const pages = item?.failed_pages || {};
        return `<div class="cn-fq"><span class="cn-fq-label">${escape(label)}</span>
          <p><strong>${escape(String(rows.value ?? 0))}</strong><span class="cn-fq-den">/ ${escape(String(rows.denominator ?? 0))} <em>处</em></span></p>
          <small>已提取但未计入的位置</small>
          <p><strong>${escape(String(pages.value ?? 0))}</strong><span class="cn-fq-den">/ ${escape(String(pages.denominator ?? 0))} <em>页</em></span></p>
          <small>解析失败的页</small></div>`;
      }
      const denominator = item?.denominator !== undefined ? `<span class="cn-fq-den">/ ${item.denominator} <em>${unit}</em></span>` : '';
      const extra = item?.denominator_label ? `<small>${escape(item.denominator_label)}</small>` : `<small>${escape(hint)}</small>`;
      return `<div class="cn-fq"><span class="cn-fq-label">${escape(label)}</span><p><strong>${escape(String(item?.value ?? 0))}</strong>${denominator}</p>${extra}${gap}${undecidable}</div>`;
    }).join('');
    if (run.versions?.intelligence) {
      const ai = ov.ai_analysis || {};
      const cards = [
        ['已检查关联', run.checks.length, '候选关系及其原文'],
        ['程序复算', ov.confirmable.value, `正式计算成立；另有${ov.trial_calculations?.value||0}项条件试算`],
        ['AI分析意见', ai.value||0, run.execution_mode==='calculation_only' ? '本次仅计算，未生成新AI意见' : `本次已保存研判；${ai.stale||0}项待重新分析`],
        ['优先待查事项', run.findings.length, '具体问题、反证与后续资料'],
      ];
      $('cn-fourq').innerHTML = cards.map(([title, value, note]) => `<div class="cn-fq"><span class="cn-fq-label">${escape(title)}</span><p><strong>${escape(value)}</strong><span class="cn-fq-den">项</span></p><small>${escape(note)}</small></div>`).join('');
    }
    const causes = (ov.unresolved_causes||[]).filter(c => c.count);
    const causeLine = causes.length
      ? `<div class="cn-causes"><h3>未决原因分布（同一关系可归多类）</h3><p>${causes.map(c => `<span class="cn-cause"><strong>${escape(c.code)}</strong> ${escape(c.name)} <em>${c.count}</em></span>`).join('')}</p></div>`
      : '';
    const questions = (ov.next_questions||[]).map((q, index) => `<button type="button" class="cn-nextq-row" data-goto="${escape(q.check_id)}"><span>0${index+1}</span>${escape(q.question)}</button>`).join('');
    $('cn-nextq').innerHTML = (questions ? `<h3>下一步可以问公司什么</h3>${questions}` : '') + causeLine + `<p class="cn-fq-note">${escape(ov.note||'')}</p>`;
  }

  function renderList() {
    const run = current(); if (!run) return;
    const view = $('cn-perspective').value;
    const notes = {public:'先看指标含义与比较条件，再沿原页查看计算。未说明的范围会继续保留。',investor:'优先关注投入构成与金额衔接；阅读视角不改变计算结果。',environment:'优先关注环保投入、强度分母与统计边界；不同范围的数字需分别说明。',professional:'事务所核对：优先查看尚缺依据的关系，展开条件、计算与搜索覆盖；从原文定位到待索取资料，用于项目组进一步核查。阅读确认不代表专业批准。'};
    const glossary = {public:'口径：同一个指标在两份报告里使用的定义与范围。残差：比较后剩下、还没有解释的差额。',
      investor:'合并范围：哪些子公司被算进来。基准（basis）：解释差额时使用的同一比较基础。',
      environment:'统计边界（scope）：组织边界与运营控制权的覆盖方式。强度（intensity）：分子÷分母得到的相对值。',
      professional:'门控（gate）：前提未支持时不输出正式差额。假设试算（hypothesis）：仅供算术参考，不进入统计。'};
    $('cn-perspective-note').innerHTML = `${escape(notes[view])}<details class="cn-glossary"><summary>本视角术语就地解释</summary><p>${escape(glossary[view]||'')}</p><p>主体、期间、定义、范围、单位：五项比较前提；任一未支持即"暂不能直接比较"。</p></details>`;
    const checks = [...run.checks].sort((a, b) => {
      const byTopic = view==='environment' ? Number(b.topic!=='research')-Number(a.topic!=='research') : view==='investor' ? Number(b.topic==='research')-Number(a.topic==='research') : 0;
      const byGap = view==='professional' ? Number(b.criteria_status!=='supported')-Number(a.criteria_status!=='supported') : 0;
      return byGap || byTopic || Number(b.relationship_evidence.length>0)-Number(a.relationship_evidence.length>0);
    });
    $('cn-count').textContent = String(checks.length);
    $('cn-check-list').innerHTML = checks.length ? checks.map(c => `<button type="button" class="cn-check${c.check_id===state.selected?' active':''}" data-check="${escape(c.check_id)}" aria-pressed="${c.check_id===state.selected}"><small>${escape(state.bootstrap.rules[c.rule_id]?.name||c.rule_id)}</small><strong>${escape(c.title)}</strong><small>${status(c.criteria_status)} ${status(c.calculation_status)}</small></button>`).join('') : '<p class="cn-empty">本次未生成关系候选：可查看“问题”页的搜索覆盖与已提取未计入清单。</p>';
  }

  function memberRows(c) {
    return `<table class="cn-table cn-member-table"><caption class="cn-sr">成员与角色</caption><thead><tr><th scope="col">角色</th><th scope="col">原标签</th><th scope="col">原值</th><th scope="col">单位</th><th scope="col">规范化值</th><th scope="col">位置</th><th scope="col">原页</th></tr></thead><tbody>${c.members.map(m => { const o = occurrence(m.occurrence_id); if (!o) return '';
      const normalized = (c.calculation?.inputs||[]).find(i => i.occurrence_id===o.occurrence_id)?.normalized;
      return `<tr><th scope="row">${escape(roles[m.role]||m.role)}</th><td>${escape(o.label)}</td><td class="cn-num">${escape(o.value ?? '未提取数值')}</td><td>${escape(o.unit||'单位待定')}</td><td class="cn-num">${escape(normalized ?? '—')}</td><td><small>${escape(docName(documentOf(o.document_id)))} · PDF ${o.pdf_page} · 年度${escape(o.year||'未归属')}${o.scope?` · ${escape(o.scope)}`:''}</small></td><td><button class="cn-evidence" type="button" data-reader="${escape(o.occurrence_id)}">打开</button></td></tr>`; }).join('')}</tbody></table>`;
  }

  function conditionsBlock(c) {
    return `<div class="cn-conditions">${c.conditions.map(cond => `<div class="cn-condition"><div class="cn-condition-head"><strong>${escape(cond.name)}</strong>${status(cond.status)}</div><p>${escape(cond.reason)}</p><div>${refs(cond.evidence)}${cond.evidence.map(r => { const o = occurrence(r.occurrence_id); return o?`<button class="cn-evidence" type="button" data-reader="${escape(o.occurrence_id)}">查看原页</button>`:''; }).join('')}</div></div>`).join('')}</div>`;
  }

  function calculationBlock(c) {
    const calc = c.calculation || {};
    const gate = calc.gate;
    const adjustment = calc.adjustment;
    const interval = calc.residual_interval;
    const formal = gate
      ? `<p class="cn-gate"><strong>${escape(gate.conclusion)}</strong>；缺少：${escape((gate.missing||[]).join('、'))}。正式差额与正式残差字段为空，不以0填充。</p><p class="cn-muted">${escape(gate.needed||'')}</p>`
      : `<p>正式差额：<strong class="cn-num">${escape(calc.residual ?? '—')}</strong> ${escape(calc.normalized_unit||'')}</p>
         <p class="cn-muted">残差区间：[${escape(interval?.low ?? '—')}, ${escape(interval?.high ?? '—')}]${interval ? `；端点${interval.low_closed?'闭':'开'}/${interval.high_closed?'闭':'开'}；含0：${interval.contains_zero?'是':'否'}` : ''}</p>`;
    const adjustmentBlock = adjustment && (adjustment.applied?.length || adjustment.rejected?.length) ? `<div class="cn-adjustment"><h4>差异解释的加性调节</h4>${(adjustment.applied||[]).map(a => `<p><strong>${escape(a.label)}</strong> ${escape(a.sign)}${escape(a.amount)} ${escape(a.unit)} · 效果${escape(a.effect_id)} · ${a.path==='grouping'?'分组':'金额桥接'}</p>`).join('')}${(adjustment.rejected||[]).map(a => `<p class="cn-rejected">未采纳 ${escape(a.adjustment_id)}：${escape(a.reason)}</p>`).join('')}<p class="cn-muted">${escape(adjustment.note||'')}</p></div>` : '';
    const trial = c.hypothetical ? `<details class="cn-detail-block"><summary>查看假设诊断（仅供算术参考，不进入概览计数）</summary><p class="cn-muted">假设：${escape((c.hypothetical.assumptions||[]).join('；'))}</p><p class="cn-equation">${escape(c.hypothetical.expression)}<br>试算差额：${escape(c.hypothetical.residual)} ${escape(c.hypothetical.normalized_unit||'')}</p></details>` : '';
    const bridge = c.scenario_adjustment;
    const bridgeBlock = bridge ? `<div class="cn-scenario"><h4>条件调节试算</h4><p>原始候选差额：${escape(bridge.original_residual)} ${escape(bridge.unit)}</p>${(bridge.applied||[]).map(a => `<p><strong>${escape(a.label)}</strong> · 有符号贡献 ${escape(a.amount)} ${escape(a.unit)}${refs(a.evidence)}<br>${escape(a.reason)}</p>`).join('')}${(bridge.rejected||[]).map(a => `<p class="cn-rejected">未用于试算：${escape(a.reason)}</p>`).join('')}<p><strong>剩余候选差额：${escape(bridge.remaining_residual)} ${escape(bridge.unit)}</strong></p><p class="cn-muted">假设：${escape((bridge.assumptions||[]).join('；'))}。${escape(bridge.note)}</p></div>` : '';
    const plan = c.calculation_plan ? `<p class="cn-muted">计算方案：${escape(c.calculation_plan.reason)}；${escape({formal:'已执行正式计算',trial:'已执行条件试算',rejected:'暂不可执行',proposed:'模型建议'}[c.calculation_plan.status])}。${escape((c.calculation_plan.assumptions||[]).join('；'))}</p>` : '';
    const narrative = c.narrative_test ? `<div class="cn-scenario"><h4>文字与数值方向核对</h4>${c.narrative_test.status==='not_executable' ? `<p>${escape(c.narrative_test.reason)}</p>` : `<p>程序计算变化方向：${escape({increase:'上升',decrease:'下降',stable:'持平'}[c.narrative_test.direction])}；与所绑定主张${c.narrative_test.direction_matches?'方向相符':'方向不同'}。${c.narrative_test.change_percent!==null?`变化${escape(c.narrative_test.change_percent)}%。`:''}</p><p class="cn-muted">${escape(c.narrative_test.note)}</p>`}</div>` : '';
    return `<div class="cn-equation">${escape(calc.expression || '尚无可执行算式')}</div>${plan}${formal}${adjustmentBlock}${trial}${bridgeBlock}${narrative}<details class="cn-detail-block"><summary>计算明细（机器可读）</summary><pre>${escape(JSON.stringify(calc, null, 2))}</pre></details>`;
  }

  function aiAnalysisBlock(c) {
    const opinion = (current()?.ai_analyses||[]).find(a => a.check_id===c.check_id);
    if (!opinion) return '<div class="cn-ai-opinion"><h3>AI分析意见</h3><p class="cn-muted">该关系尚未保存AI研判；计算结果和原文仍可查看。</p></div>';
    const list = (title, values) => values?.length ? `<h4>${title}</h4><ul>${values.map(v => `<li>${escape(v)}</li>`).join('')}</ul>` : '';
    return `<section class="cn-ai-opinion" aria-label="AI分析意见"><div class="cn-ai-heading"><h3>${escape(aiVerdicts[opinion.verdict]||opinion.verdict)}</h3><small>AI分析意见，仅供核查参考</small></div>${opinion.status==='needs_refresh'?'<p class="cn-rejected">该意见来自修订前结果，输入已变化，需重新分析。</p>':''}<p class="cn-ai-summary">${escape(opinion.summary)}</p>${list('判断依据',opinion.reasons)}${escapedRefs(opinion.supporting_evidence)}${refs(opinion.supporting_evidence)}${list('尚待核实的假设',opinion.assumptions)}${opinion.counter_evidence?.length?`<h4>相反证据</h4>${escapedRefs(opinion.counter_evidence)}${refs(opinion.counter_evidence)}`:''}${list('其他可能解释',opinion.alternative_explanations)}${list('下一步',opinion.next_actions)}<small>使用者处理：${escape({unreviewed:'未复核',accepted:'已采纳',rejected:'已驳回'}[opinion.review_status]||'未复核')} · 分析质量：${escape({high:'高',medium:'中',low:'低'}[opinion.analysis_quality]||opinion.analysis_quality)} · ${escape((opinion.quality_reasons||[]).join('；'))}</small></section>`;
  }

  function explanationBlock(c) {
    const adjustment = c.calculation?.adjustment;
    return `<div class="cn-explanation">${escape(c.explanation || '本次尚未找到充分的具体解释。')}${refs(c.explanation_evidence)}</div>${adjustment?.applied?.length ? `<div class="cn-adjustment"><h4>已被采纳的解释与其覆盖</h4>${adjustment.applied.map(a => `<p><strong>${escape(a.label)}</strong>：${escape(a.sign)}${escape(a.amount)} ${escape(a.unit)}；仍须说明：${escape((c.unresolved||[]).join('；')||'无额外未决')}</p>`).join('')}</div>` : ''}`;
  }

  function positionsBlock(c) {
    const run = current();
    const ids = new Set(c.members.map(m => m.occurrence_id));
    const label = occurrence(c.members[0]?.occurrence_id)?.label || c.title;
    const key = label.replace(/[\s：:（）()%％]/g, '').slice(0, 12);
    const others = run.occurrences.filter(o => !ids.has(o.occurrence_id) && o.label.replace(/[\s：:（）()%％]/g, '').startsWith(key)).slice(0, 40);
    const groups = new Map();
    others.forEach(row => {
      const key = `${row.document_id}|${row.year||'未归属'}|${row.scope||'未标注层级'}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    });
    const body = [...groups.entries()].map(([key, rows]) => {
      const [documentId, year, scope] = key.split('|');
      const heading = `${documentOf(documentId)?.report_type==='AR' ? '年度报告' : 'ESG 报告'} · ${year} · ${scope} · ${rows.length} 处`;
      return `<tbody><tr class="cn-group-row"><th scope="colgroup" colspan="8">${escape(heading)}</th></tr>${rows.map(o => `<tr><td><small>${escape(documentOf(o.document_id)?.report_type||o.document_id)}</small></td><td>${escape({original:'原版',correction:'更正',unknown:'未登记'}[o.version_role]||o.version_role)}</td><td>${escape(o.year||'未归属')}</td><td class="cn-num">${o.pdf_page}</td><td><small>${escape((o.row_header||'').slice(0,60))}</small></td><td>${escape(o.scope||'—')}</td><td class="cn-num">${escape(o.value ?? '—')}</td><td><button class="cn-evidence" type="button" data-reader="${escape(o.occurrence_id)}">打开</button></td></tr>`).join('')}</tbody>`;
    }).join('');
    const rows = others.length ? `<table class="cn-table"><caption class="cn-sr">其余已发现位置（按文档、年度、位置层级分组）</caption><thead><tr><th scope="col">文档</th><th scope="col">版本角色</th><th scope="col">指标年度</th><th scope="col">页码</th><th scope="col">表名 / 行头</th><th scope="col">位置层级</th><th scope="col">原值</th><th scope="col">原页</th></tr></thead>${body}</table>` : '<p class="cn-empty">除本关系成员外，本次检索未发现同标签的其它位置。该结论只覆盖本次检索范围，不表示报告不存在其它披露。</p>';
    const exclusions = run.extraction_exclusions.filter(e => e.label.replace(/[\s：:（）()%％]/g, '').startsWith(key));
    const excluded = exclusions.length ? `<h4>已提取但未计入（${exclusions.length}处）</h4><ul class="cn-excluded">${exclusions.slice(0,20).map(e => `<li>${escape(e.label)} · PDF ${e.pdf_page} · ${escape(e.value)} ${escape(e.unit)} · ${escape(e.reason)}</li>`).join('')}</ul>` : '';
    return `<h3 class="cn-section-h">其余位置</h3>${rows}${excluded}`;
  }

  function detailTab(key, focus=false) {
    state.detailTab = key;
    document.querySelectorAll('#cn-detail [data-detail-tab]').forEach(button => {
      const active = button.dataset.detailTab===key;
      button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1;
      if (active && focus) button.focus();
    });
    document.querySelectorAll('#cn-detail [role="tabpanel"]').forEach(panel => { panel.hidden = panel.id!==`cn-pane-${key}`; });
  }

  function renderDetail() {
    const c = check(); if (!c) { $('cn-detail-conclusion').textContent = '没有可显示的关系记录。'; return; }
    const conclusion = `<p class="cn-subtitle">${escape(c.check_id)} / ${escape(c.rule_id)} / 规则版本 ${escape(c.rule_version)}</p><h2>${escape(c.title)}</h2><div class="cn-conclusion-band"><p class="cn-conclusion-text">${escape(conclusionText(c))}</p><div class="cn-statuses"><div><small>口径</small>${status(c.criteria_status)}</div><div><small>计算</small>${status(c.calculation_status)}</div><div><small>使用者处理</small>${status(c.review_status)}</div></div></div>${$('cn-perspective').value==='public' ? plainLayer(c) : ''}<h3 class="cn-section-h">成员与角色</h3>${memberRows(c)}`;
    $('cn-detail-conclusion').innerHTML = conclusion + aiAnalysisBlock(c);
    $('cn-pane-conditions').innerHTML = `<h3 class="cn-section-h">五项前提</h3>${conditionsBlock(c)}<h3 class="cn-section-h">算式与残差</h3>${calculationBlock(c)}`;
    $('cn-pane-positions').innerHTML = `<h3 class="cn-section-h">解释与反证</h3>${explanationBlock(c)}<h3 class="cn-section-h">关系依据</h3><div class="cn-explanation">${escapedRefs(c.relationship_evidence)}</div>${positionsBlock(c)}`;
    $('cn-pane-questions').querySelector('#cn-findings') && renderFindings();
    $('cn-revision-actions').innerHTML = `<p>更正成员、前提依据并重算：原始自动结果保留，更正生成子版本；修订不等于正式专业批准。</p><button type="button" id="cn-edit" data-edit="1">更正成员、关系依据并重算</button>`;
    $('cn-edit').disabled = state.task.can_modify===false;
    $('cn-edit').title = state.task.can_modify===false ? '当前浏览器可阅读，创建任务的浏览器可更正' : '';
    // 视角决定默认展开层级：专业明细展开计算与覆盖明细，公众与投资视角保持收起。
    const expand = $('cn-perspective').value==='professional';
    document.querySelectorAll('#cn-detail details.cn-detail-block').forEach(node => { node.open = expand; });
    detailTab(state.detailTab);
  }

  function escapedRefs(items) {
    return (items||[]).map(r => { const o = occurrence(r.occurrence_id); return `<p><small>${escape(o?docName(documentOf(o.document_id)):'')} PDF ${o?.pdf_page||'?'}</small><br>${escape(r.quote)}</p>`; }).join('') || '<p class="cn-muted">本次未登记具体关系依据。</p>';
  }

  function renderFindings() {
    const run = current(); if (!run) return;
    const c = check();
    const items = c ? run.findings.filter(f => f.check_id===c.check_id) : run.findings;
    $('cn-findings').innerHTML = items.length ? items.map(f => `<article class="cn-finding"><strong>${escape(f.question)}</strong><small>${escape(f.check_id)} · ${escape(f.known_facts)}</small><p>进一步了解：${escape(f.requested_material)}</p><p>用途：${escape(f.purpose)}</p></article>`).join('') : '<p class="cn-empty">当前所选关系未保留待查问题；不代表已全面核实报告。未决条件见“条件·计算”页。</p>';
  }

  function renderCoverage() {
    const run = current(); if (!run) return;
    $('cn-coverage').innerHTML = run.coverage.map(c => `<p>${escape(c.document_id)}：${c.total_pages}页 / 解析${c.parsed_pages}页 / 实际搜索${c.searched_pages.length}页 / 候选${c.discovered_count}处。失败：${escape(c.failed_pages.map(f => `第${f.page}页 ${f.reason}`).join('；')||'无记录')}。</p>`).join('');
    const exclusions = run.extraction_exclusions || [];
    $('cn-exclusions').innerHTML = `<h4>已提取但未计入（${exclusions.length}处）</h4>` + (exclusions.length ? `<p class="cn-muted">这些位置不作为“没有披露”的证据，也不进入候选筛选。</p><ul class="cn-excluded">${exclusions.slice(0,40).map(e => `<li>${escape(e.document_id)} · PDF ${e.pdf_page} · ${escape(e.label)} · ${escape(e.value)} ${escape(e.unit)} · ${escape(e.reason)}</li>`).join('')}</ul>` : '<p class="cn-muted">本次没有达到候选门槛后被排除的位置。</p>');
    $('cn-agents').innerHTML = (run.parent_run_id ? '<p>以下是沿用的原运行调用记录，本次修订没有新增模型调用。</p>' : '') + `<p>实际模型状态：${escape(labels[run.model_status]||run.model_status)}；发出调用${run.provider_calls.filter(c => c.performed).length}次。</p>` + run.agent_steps.map(s => `<p><strong>${escape(s.role)}</strong> ${escape(labels[s.status]||s.status)} · 采纳${s.accepted_check_ids?.length||0}项 / 拒绝${s.rejected?.length||0}项 · AI研判${s.accepted_analysis_ids?.length||0}项 · 计算方案${s.calculation_plan_ids?.length||0}项 · 调节建议${s.adjustment_check_ids?.length||0}项${s.failure_code?' · '+escape(s.failure_code):''}${(s.analysis_rejections||[]).map(r=>`<br>意见未采纳：${escape(r.reason)}`).join('')}</p>`).join('') + run.provider_calls.map(c => `<p>${escape(c.role)}：${escape(c.model||c.failure_code||'未配置')}；输入${c.input_tokens??'未知'} / 输出${c.output_tokens??'未知'} tokens；费用${c.cost??'未计价'}。</p>`).join('');
    if ((run.intelligence_trace||[]).length) $('cn-agents').innerHTML += `<details><summary>定向补查与批次覆盖</summary><pre>${escape(JSON.stringify(run.intelligence_trace,null,2))}</pre></details>`;
  }

  function renderTimeline() {
    const run = current(); if (!run) return;
    // 修订编号按顺序递增，与 result_revision 解耦，多条修订不再全部显示 v2。
    const revisions = [{label:'v1 自动结果', at:run.created_at, note:'模型与程序产出'}];
    (run.reviews||[]).forEach((r, index) => {
      revisions.push({label:`v${index+2} ${({relationship_correction:'关系更正',reading_confirmation:'阅读确认',personal_observation:'个人观察',ai_accept:'采纳AI意见',ai_reject:'驳回AI意见'})[r.action]||r.action}`,
        at:r.created_at, note:r.reason});
    });
    // 公司披露版本按报告类型分条：AR 与 ESG 不是彼此的版本，不能并到一条轴上。
    const byType = new Map();
    (run.version_records||[]).forEach(record => {
      const type = record.report_type || (documentOf(record.document_id)?.report_type) || '未登记类型';
      if (!byType.has(type)) byType.set(type, []);
      byType.get(type).push({...record, at: record.disclosure_date || ''});
    });
    const axis = (title, items, kind) => `<div class="cn-axis cn-axis-${kind}"><h4>${escape(title)}</h4><ol>${items.map(item => `<li><span class="cn-axis-dot" aria-hidden="true"></span><div><strong>${escape(item.label)}</strong><small>${item.at ? escape(item.at) : '披露日期未登记'}${item.note?` · ${escape(item.note)}`:''}${item.version_role?` · ${escape({original:'原版',correction:'更正',unknown:'角色未登记'}[item.version_role]||item.version_role)}`:''}</small>${kind==='company'&&item.metric_period?`<small>指标期间 ${escape(item.metric_period)} · 报告年度 ${escape(item.report_period||'—')}</small>`:''}</div></li>`).join('') || '<li><small>未登记</small></li>'}</ol></div>`;
    const companyAxes = [...byType.entries()].map(([type, items]) => axis(`${type==='ESG'?'ESG 报告':'年度报告'}版本轴`, items, 'company')).join('')
      || axis('公司披露版本轴', [], 'company');
    const changes = (run.version_changes||[]).length ? `<p class="cn-muted">版本变化（只作版本证据链，不相加成跨报告结论）：${run.version_changes.map(ch => `${escape(ch.label)} ${escape(ch.display_change)} ${escape(ch.unit)}`).join('；')}</p>` : '<p class="cn-muted">本次未登记多版本对照；版本金额变化不生成正式跨报告差额。</p>';
    $('cn-timeline').innerHTML = companyAxes + '<div class="cn-axis-divider" aria-hidden="true"></div>' + axis('系统结果修订轴', revisions, 'system') + changes;
  }

  function renderUserRecords() {
    const run = current();
    $('cn-save-review').disabled = state.task.can_modify===false;
    if (state.task.can_modify===false) $('cn-review-message').textContent = '当前为只读记录；创建任务的浏览器可保存更正与观察。';
    $('cn-review-checks').innerHTML = run.checks.map(c => `<label><input type="checkbox" name="review-check" value="${escape(c.check_id)}"> ${escape(c.title)}</label>`).join('');
    const count = run.personal_observation_count ?? (run.professional_notes||[]).length;
    $('cn-personal-notes').innerHTML = (run.professional_notes||[]).map(n => `<article class="cn-finding"><strong>个人观察 · ${escape(n.check_id)}</strong><p>${escape(n.observation)}</p><small>${escape(n.actor)} · ${escape(n.created_at)} · 理由：${escape(n.reason)}</small></article>`).join('') || (count ? `<p class="cn-muted">存在${count}条个人观察；当前视图不展示正文，仅本人可展开。</p>` : '<p class="cn-muted">本次尚无个人观察记录。</p>');
  }

  function overviewFingerprint() {
    const run = current(); if (!run) return null;
    return JSON.stringify(run.checks.map(c => [c.check_id, c.criteria_status, c.calculation_status, c.calculation?.residual ?? null])).length + ':' + run.checks.length;
  }

  function preparePrint() {
    const run = current(); if (!run) return;
    $('cn-print-all').innerHTML = run.checks.map(c => `<article class="cn-print-relation"><h2>${escape(c.title)}</h2>${aiAnalysisBlock(c)}<p>${escape(c.check_id)} · ${escape(c.rule_id)} · ${escape(labels[c.criteria_status]||c.criteria_status)} / ${escape(labels[c.calculation_status]||c.calculation_status)} / ${escape(labels[c.review_status]||c.review_status)}</p>${c.conditions.map(n => `<p><strong>${escape(n.name)}</strong>：${escape(labels[n.status]||n.status)}；${escape(n.reason)}${n.evidence.map(r => `<br>原文 ${escape(r.occurrence_id)}：${escape(r.quote)}`).join('')}</p>`).join('')}${c.members.map(m => { const o = occurrence(m.occurrence_id); return o?`<p><strong>${escape(roles[m.role])}：${escape(o.label)}</strong> ${escape(o.value??'未提取数值')} ${escape(o.unit)}<br>${escape(o.document_id)} / PDF ${o.pdf_page}<br>${escape(o.context)}</p>`:''; }).join('')}<p>正式计算：${escape(JSON.stringify(c.calculation))}</p>${c.scenario_adjustment?`<p>条件调节试算：${escape(JSON.stringify(c.scenario_adjustment))}</p>`:''}${c.hypothetical?`<p>假设试算（非正式结论）：${escape(c.hypothetical.expression)}；差额${escape(c.hypothetical.residual)}</p>`:''}<p>解释：${escape(c.explanation||'尚无充分解释')}</p>${[...c.relationship_evidence,...c.explanation_evidence].map(r => `<p>关系或解释依据 ${escape(r.occurrence_id)}：${escape(r.quote)}</p>`).join('')}<p>未决：${escape(c.unresolved.join('；')||'当前选定关系无额外未决条件')}</p></article>`).join('');
  }
  window.addEventListener('beforeprint', preparePrint);

  // ---- 证据阅读器：全屏覆盖层，桌面并排两份原页，坐标可靠才画框 ----
  function readerFocus(){ return document.activeElement; }
  function openReader(occurrenceId, trigger) {
    const run = current(); if (!run) return;
    const anchor = occurrence(occurrenceId);
    // 触发元素由调用方传入：不依赖 activeElement，覆盖键盘与脚本触发两种入口。
    state.readerTrigger = trigger || readerFocus();
    const c = check();
    const pages = {};
    run.documents.forEach(doc => {
      const hit = [anchor, ...(c?.members||[]).map(m => occurrence(m.occurrence_id))].filter(Boolean).find(o => o?.document_id===doc.document_id);
      pages[doc.document_id] = hit ? {page:hit.pdf_page, hit} : {page:1, hit:null};
    });
    state.reader = {pages, focus:anchor?.document_id || run.documents[0]?.document_id, check:c};
    renderReader();
    $('cn-reader').hidden = false;
    $('cn-reader-close').focus();
    document.body.classList.add('cn-reader-open');
  }
  function renderReader() {
    const run = current(); const reader = state.reader; if (!run || !reader) return;
    const c = reader.check;
    const focusRow = reader.pages[reader.focus]?.hit;
    $('cn-reader-title').textContent = focusRow
      ? `${documentOf(focusRow.document_id)?.company||run.company} · ${focusRow.document_id} · PDF ${focusRow.pdf_page} · 印刷页 ${focusRow.printed_page||'未登记'} · ${focusRow.row_header?.slice(0,40)||focusRow.label}`
      : `${run.company} · ${run.period} 原件`;
    $('cn-reader-open').href = sourceUrl(reader.focus, reader.pages[reader.focus]?.page||1);
    $('cn-reader-docs').innerHTML = run.documents.map(doc => {
      const entry = reader.pages[doc.document_id] || {page:1, hit:null};
      const hit = entry.hit;
      const reliable = hit && hit.page_width && hit.page_height && Array.isArray(hit.bbox) && hit.bbox.length===4 && hit.bbox.every(Number.isFinite);
      const caption = hit ? `${escape(doc.report_type==='AR'?'年度报告':'ESG 报告')} · PDF ${hit.pdf_page} · 印刷页 ${escape(hit.printed_page||'未登记')} · 列头 ${escape(hit.column_header||'未登记')} · 行 ${escape((hit.row_header||hit.label).slice(0,40))}` : `${escape(doc.report_type==='AR'?'年度报告':'ESG 报告')} · 本关系未在此文档定位到位置（显示第${entry.page}页整页）`;
      return `<figure class="cn-reader-doc" data-doc="${escape(doc.document_id)}"><figcaption>${caption}</figcaption><div class="cn-page-layer"><img width="${Number(hit?.page_width||595)}" height="${Number(hit?.page_height||842)}" src="${pageImage(doc.document_id, entry.page)}" alt="${escape(doc.company)} ${escape(doc.report_type)} 原件第${entry.page}页" loading="lazy">${reliable?`<svg class="cn-location" viewBox="0 0 ${hit.page_width} ${hit.page_height}" aria-label="所选原文坐标标记"><rect x="${hit.bbox[0]}" y="${hit.bbox[1]}" width="${hit.bbox[2]-hit.bbox[0]}" height="${hit.bbox[3]-hit.bbox[1]}"></rect></svg>`:''}</div>${reliable?'':`<p class="cn-muted">坐标不足以可靠定位，本次只展示整页与文字定位处，不画猜测框。</p>`}</figure>`;
    }).join('');
    $('cn-reader-note').textContent = c ? `当前关系：${c.title}` : '按文档分别翻页；关闭后回到原关系与滚动位置。';
  }
  function closeReader() {
    if ($('cn-reader').hidden) return;
    $('cn-reader').hidden = true;
    document.body.classList.remove('cn-reader-open');
    state.reader = null;
    const trigger = state.readerTrigger;
    if (trigger && typeof trigger.focus==='function') trigger.focus();
  }
  function flipReader(delta) {
    if (!state.reader) return;
    const entry = state.reader.pages[state.reader.focus];
    const doc = documentOf(state.reader.focus);
    entry.page = Math.min(Math.max(1, entry.page + delta), doc?.pages || 9999);
    state.reader.pages[state.reader.focus] = entry;
    renderReader();
  }

  // ---- 更正窗口：成员、前提、依据与加性调节 ----
  function occurrenceOptions(selected) {
    return current().occurrences.map(o => `<option value="${escape(o.occurrence_id)}"${o.occurrence_id===selected?' selected':''}>${escape(o.document_id)} / PDF${o.pdf_page} / ${escape(o.label.slice(0,32))} / ${escape(o.value??'文字')} ${escape(o.unit)}</option>`).join('');
  }
  function evidenceTail(items, key) {
    if (items.length<2) return '';
    return `<details class="cn-reference-tail"><summary>其它已保存出处（${items.length-1}条）</summary>${items.slice(1).map((r, i) => { const o = occurrence(r.occurrence_id);
      return `<label><input type="checkbox" checked data-extra-ref="${key}" value="${i+1}">保留 ${escape(o?.document_id||r.occurrence_id)} PDF${o?.pdf_page||'?'}：${escape(r.quote)}</label>`; }).join('')}</details>`;
  }
  function retainedReferences(original, key, source, quote) {
    const extra = [...document.querySelectorAll(`[data-extra-ref="${key}"]:checked`)].map(input => original[Number(input.value)]).filter(Boolean);
    return (quote.trim() ? [{occurrence_id:source, quote}] : []).concat(extra);
  }
  function collectCorrection() {
    const c = structuredClone(state.editDraft);
    c.title = $('cn-relation-title').value.trim();
    c.rule_id = $('cn-edit-rule').value;
    c.operator = state.bootstrap.rules[c.rule_id].operator;
    c.members = [...document.querySelectorAll('[data-member]')].map(select => ({occurrence_id:select.value, role:document.querySelector(`[data-member-role="${select.dataset.member}"]`).value}));
    c.conditions = c.conditions.map((cond, i) => ({...cond, status:document.querySelector(`[data-condition-status="${i}"]`).value, reason:document.querySelector(`[data-condition-reason="${i}"]`).value, evidence:retainedReferences(cond.evidence, `condition-${i}`, document.querySelector(`[data-condition-source="${i}"]`).value, document.querySelector(`[data-condition-quote="${i}"]`).value)}));
    c.relationship_evidence = retainedReferences(c.relationship_evidence, 'relation', $('cn-relation-source').value, $('cn-relation-quote').value);
    c.explanation = $('cn-edit-explanation').value.trim();
    c.explanation_evidence = retainedReferences(c.explanation_evidence, 'explanation', $('cn-explanation-source').value, $('cn-explanation-quote').value);
    c.adjustments = [...document.querySelectorAll('[data-adjustment]')].map(box => ({
      adjustment_id:box.dataset.adjustment, effect_id:box.querySelector('[data-adj-effect]').value.trim(),
      label:box.querySelector('[data-adj-label]').value.trim(), sign:box.querySelector('[data-adj-sign]').value,
      amount:box.querySelector('[data-adj-amount]').value.trim(), unit:box.querySelector('[data-adj-unit]').value.trim(),
      metric_period:box.querySelector('[data-adj-period]').value.trim(), scope:box.querySelector('[data-adj-scope]').value.trim(),
      basis_id:box.querySelector('[data-adj-basis]').value.trim(), path:'amount_bridge', overlap_with:[], overlap_basis:'',
      evidence:[{occurrence_id:box.querySelector('[data-adj-source]').value, quote:box.querySelector('[data-adj-quote]').value}], note:'由使用者在更正窗口登记'}))
      .filter(item => item.effect_id && item.amount && item.label);
    return c;
  }
  function renderCorrectionFields() {
    const c = state.editDraft; const rule = state.bootstrap.rules[c.rule_id];
    $('cn-correction-fields').innerHTML = `<label>关系名称<input id="cn-relation-title" required maxlength="200" value="${escape(c.title)}"></label><label>核对关系<select id="cn-edit-rule">${Object.entries(state.bootstrap.rules).map(([id, r]) => `<option value="${id}"${id===c.rule_id?' selected':''}>${escape(r.name)}</option>`).join('')}</select></label><label>查找原文成员或依据<input id="cn-source-filter" type="search" placeholder="输入指标名、报告ID或PDF页码"></label><p>可增删关系成员；新关系仍需逐项核实比较前提。</p>`;
    $('cn-correction-fields').insertAdjacentHTML('beforeend', c.members.map((m, i) => `<fieldset class="cn-edit-condition"><legend>成员${i+1}</legend><label>成员角色<select data-member-role="${i}">${rule.roles.map(role => `<option value="${role}"${role===m.role?' selected':''}>${escape(roles[role])}</option>`).join('')}</select></label><label>原文位置<select data-member="${i}">${occurrenceOptions(m.occurrence_id)}</select></label><button type="button" data-remove-member="${i}">移除此成员</button></fieldset>`).join('') + '<button type="button" id="cn-add-member">增加原文成员</button>');
    $('cn-correction-fields').insertAdjacentHTML('beforeend', c.conditions.map((cond, i) => `<fieldset class="cn-edit-condition"><legend>${escape(cond.name)}</legend><label>依据状态<select data-condition-status="${i}">${['unknown','supported','conflicting'].map(value => `<option value="${value}"${value===cond.status?' selected':''}>${escape(labels[value])}</option>`).join('')}</select></label><label>依据位置<select data-condition-source="${i}">${occurrenceOptions(cond.evidence[0]?.occurrence_id||c.members[0]?.occurrence_id)}</select></label><label>逐字引用原文<textarea data-condition-quote="${i}" rows="2">${escape(cond.evidence[0]?.quote||'')}</textarea></label><label>理由<textarea data-condition-reason="${i}" rows="2">${escape(cond.reason)}</textarea></label>${evidenceTail(cond.evidence, `condition-${i}`)}</fieldset>`).join(''));
    $('cn-correction-fields').insertAdjacentHTML('beforeend', `<fieldset class="cn-edit-condition"><legend>具体关系依据</legend><label>原文位置<select id="cn-relation-source">${occurrenceOptions(c.relationship_evidence[0]?.occurrence_id||c.members[0]?.occurrence_id)}</select></label><label>支持本次关系的原文<textarea id="cn-relation-quote" rows="3" required>${escape(c.relationship_evidence[0]?.quote||'')}</textarea></label>${evidenceTail(c.relationship_evidence, 'relation')}</fieldset><fieldset class="cn-edit-condition"><legend>差异解释及其出处</legend><label>具体解释<textarea id="cn-edit-explanation" rows="3">${escape(c.explanation||'')}</textarea></label><label>解释出处<select id="cn-explanation-source">${occurrenceOptions(c.explanation_evidence[0]?.occurrence_id||c.members[0]?.occurrence_id)}</select></label><label>解释所用原句<textarea id="cn-explanation-quote" rows="3">${escape(c.explanation_evidence[0]?.quote||'')}</textarea></label>${evidenceTail(c.explanation_evidence, 'explanation')}</fieldset>`);
    const adjustments = c.adjustments || [];
    $('cn-correction-fields').insertAdjacentHTML('beforeend', `<fieldset class="cn-edit-condition"><legend>差异解释的加性调节（同基准，首版不支持乘性变换）</legend><p class="cn-muted">符号表示该解释对差额的贡献方向；剩余残差＝原始差额−Σ有符号调节额。同一效果只能采用一次。</p>${adjustments.map((a, i) => `<div class="cn-adjustment-row" data-adjustment="ADJ-${i+1}"><label>效果编号<input data-adj-effect value="${escape(a.effect_id||'')}" placeholder="EFF-1"></label><label>名称<input data-adj-label value="${escape(a.label||'')}"></label><label>符号<select data-adj-sign><option value="-"${a.sign==='-'?' selected':''}>−（抵扣差额）</option><option value="+"${a.sign==='+'?' selected':''}>＋（追加差额）</option></select></label><label>金额<input data-adj-amount value="${escape(a.amount||'')}" inputmode="decimal"></label><label>单位<input data-adj-unit value="${escape(a.unit||'万元')}"></label><label>指标期间<input data-adj-period value="${escape(a.metric_period||'')}"></label><label>范围<input data-adj-scope value="${escape(a.scope||'')}"></label><label>基准编号<input data-adj-basis value="${escape(a.basis_id||'')}"></label><label>依据位置<select data-adj-source>${occurrenceOptions(a.evidence?.[0]?.occurrence_id||c.members[0]?.occurrence_id)}</select></label><label>依据原句<textarea data-adj-quote rows="2">${escape(a.evidence?.[0]?.quote||'')}</textarea></label></div>`).join('')}<button type="button" id="cn-add-adjustment">增加调节项</button></fieldset>`);
    $('cn-edit-rule').addEventListener('change', () => {
      state.editDraft = collectCorrection(); const next = state.bootstrap.rules[state.editDraft.rule_id];
      const required = next.conditions || ['主体','期间','定义','范围','单位'];
      state.editDraft.conditions = required.map(name => ({name, status:'unknown', reason:'关系类型已更改，请按本次关系补充具体依据', evidence:[]}));
      state.editDraft.members.forEach((m, i) => { m.role = next.roles[Math.min(i, next.roles.length-1)]; });
      renderCorrectionFields();
    });
    $('cn-add-member').addEventListener('click', () => {
      state.editDraft = collectCorrection();
      if (state.editDraft.members.length>=100) { $('cn-correction-message').textContent = '单项关系最多100个成员。'; return; }
      const allowed = state.bootstrap.rules[state.editDraft.rule_id].roles; const used = state.editDraft.members.map(m => m.role);
      state.editDraft.members.push({occurrence_id:current().occurrences[0].occurrence_id, role:allowed.find(role => !used.includes(role))||allowed[allowed.length-1]});
      renderCorrectionFields();
    });
    $('cn-add-adjustment').addEventListener('click', () => {
      state.editDraft = collectCorrection();
      (state.editDraft.adjustments ||= []).push({adjustment_id:`ADJ-${state.editDraft.adjustments.length+1}`, effect_id:'', label:'', sign:'-', amount:'', unit:'万元', metric_period:'', scope:'', basis_id:'', evidence:[]});
      renderCorrectionFields();
    });
    document.querySelectorAll('[data-remove-member]').forEach(button => button.addEventListener('click', () => { state.editDraft = collectCorrection(); state.editDraft.members.splice(Number(button.dataset.removeMember), 1); renderCorrectionFields(); }));
    $('cn-source-filter').addEventListener('input', event => {
      const query = event.target.value.trim().toLowerCase();
      document.querySelectorAll('#cn-correction-fields select[data-member],#cn-correction-fields select[data-condition-source],#cn-relation-source,#cn-explanation-source').forEach(select => {
        const selected = select.value;
        select.innerHTML = current().occurrences.filter(o => o.occurrence_id===selected || !query || `${o.document_id} PDF${o.pdf_page} ${o.label} ${o.value??''}`.toLowerCase().includes(query)).map(o => `<option value="${escape(o.occurrence_id)}"${o.occurrence_id===selected?' selected':''}>${escape(o.document_id)} / PDF${o.pdf_page} / ${escape(o.label.slice(0,32))} / ${escape(o.value??'文字')} ${escape(o.unit)}</option>`).join('');
      });
    });
  }
  function correctionImpact() {
    const original = check(); const draft = state.editDraft || {};
    const memberChanged = (draft.members||[]).filter((m, i) => m.occurrence_id !== original.members[i]?.occurrence_id || m.role !== original.members[i]?.role).length
      + Math.abs((draft.members||[]).length - original.members.length);
    const conditionChanged = (draft.conditions||[]).filter((c, i) => {
      const before = original.conditions[i] || {};
      return c.status !== before.status || (c.reason||'') !== (before.reason||'');
    }).length;
    const adjustments = (draft.adjustments||[]).length;
    return `<h3>保存前请确认三件事</h3><ol><li><strong>将要改变什么</strong>：成员 ${memberChanged} 处、前提 ${conditionChanged} 项、加性调节 ${adjustments} 项。</li><li><strong>影响哪些下游计算</strong>：本关系重新计算 → 概览四问与未决原因分布 → 待查问题文本 → 导出与打印内容；其它关系不受影响。</li><li><strong>是否覆盖原结果</strong>：不覆盖。原自动结果保留，本次生成 v${(current()?.result_revision||1)+1} 子版本，修订记录可回溯。</li></ol>`;
  }
  function openCorrection() {
    state.editDraft = structuredClone(check());
    renderCorrectionFields();
    $('cn-correction-impact').innerHTML = correctionImpact();
    $('cn-correction-message').textContent=''; $('cn-correction-reason').value='';
    $('cn-correction').showModal();
  }

  function reviewRecord(record) {
    return `<p>${escape(record.title||'')} · ${escape(labels[record.criteria_status]||record.criteria_status||'')} / ${escape(labels[record.calculation_status]||record.calculation_status||'')} / ${escape(labels[record.review_status]||record.review_status||'')}</p><ul>${(record.members||[]).map(m => { const o = occurrence(m.occurrence_id);
      return `<li>${escape(roles[m.role])}：${escape(o?.label||m.occurrence_id)} ${escape(o?.value??'')} ${escape(o?.unit||'')} ${o?`<a href="${sourceUrl(o.document_id, o.pdf_page)}" target="_blank" rel="noopener">原文 PDF${o.pdf_page}</a>`:''}</li>`; }).join('')}</ul><p>计算：${escape(record.calculation?.expression||'无数值算式')}；正式差额：${escape(record.calculation?.residual ?? '暂不能直接比较')}</p><p>未决：${escape((record.unresolved||[]).join('；')||'本次选定关系无额外未决条件')}</p>`;
  }

  // ---- 事件 ----
  async function startRun(extra={}) {
    const topics = [...document.querySelectorAll('#cn-form input[name="topic"]:checked')].map(n => n.value);
    if (!topics.length) { message('至少选择一个关注事项。', true); return; }
    clearTimeout(state.timer); state.generation++; state.selected=null; busy(true);
    $('cn-results').hidden=true; $('cn-progress').hidden=true; $('cn-cancel').disabled=true;
    message('正在提交核验请求；收到任务编号后展示实际阶段。');
    try {
      const task = await api('/runs', {method:'POST', headers:{'Idempotency-Key':crypto.randomUUID()},
        body:JSON.stringify({pair_id:$('cn-pair').value, topics, mode:$('cn-mode').value, ...extra})});
      rememberTask(task.task_id); await poll(task.task_id);
    } catch (error) { message(error.message, true); busy(false); }
  }
  $('cn-form').addEventListener('submit', event => { event.preventDefault(); startRun(); });
  $('cn-stagebar').addEventListener('click', event => {
    if (!event.target.closest('#cn-retry')) return;
    // 失败阶段的可读原因已在运行记录；重试是对同一报告对重新发起，不覆盖原失败任务。
    startRun({retry_of_task_id: state.task?.task_id});
  });
  $('cn-cancel').addEventListener('click', async () => { if (!state.task) return; try { await api(`/runs/${encodeURIComponent(state.task.task_id)}/cancel`, {method:'POST'}); await poll(state.task.task_id); } catch (error) { message(error.message, true); } });
  $('cn-pair').addEventListener('change', reportCards);
  $('cn-perspective').addEventListener('change', () => { renderList(); renderDetail(); });
  $('cn-print').addEventListener('click', () => { preparePrint(); window.print(); });
  $('cn-check-list').addEventListener('click', event => {
    const button = event.target.closest('[data-check]');
    if (!button) return;
    state.selected = button.dataset.check; renderList(); renderDetail(); renderFindings();
    closeDrawer(false);
  });
  $('cn-nextq').addEventListener('click', event => { const button = event.target.closest('[data-goto]'); if (!button) return; state.selected = button.dataset.goto; renderList(); renderDetail(); renderFindings(); detailTab('questions', true); });
  $('cn-detail').addEventListener('click', event => {
    const related = event.target.closest('[data-related]'); if (related) { state.selected = related.dataset.related; renderList(); renderDetail(); return; }
    const readerButton = event.target.closest('[data-reader]'); if (readerButton) { openReader(readerButton.dataset.reader, readerButton); return; }
    if (event.target.closest('[data-edit]')) openCorrection();
    const tab = event.target.closest('[data-detail-tab]'); if (tab) detailTab(tab.dataset.detailTab, true);
  });
  $('cn-detail').addEventListener('keydown', event => {
    const tab = event.target.closest('[data-detail-tab]'); if (!tab) return;
    const keys = ['conditions','positions','questions','revision']; let index = keys.indexOf(state.detailTab);
    if (event.key==='ArrowRight') index = (index+1)%4; else if (event.key==='ArrowLeft') index = (index+3)%4;
    else if (event.key==='Home') index = 0; else if (event.key==='End') index = 3; else return;
    event.preventDefault(); detailTab(keys[index], true);
  });
  $('cn-list-toggle').addEventListener('click', () => {
    const collapsed = document.querySelector('.cn-master').classList.toggle('cn-list-collapsed');
    $('cn-list-toggle').setAttribute('aria-expanded', String(!collapsed));
    $('cn-list-toggle').textContent = collapsed ? '展开' : '折叠';
  });
  // 768—1199px：事项列表为抽屉，打开时锁定焦点，Esc 或遮罩关闭并返回触发按钮。
  function drawerKeys(event) {
    if (event.key === 'Escape') { event.preventDefault(); closeDrawer(); return; }
    if (event.key !== 'Tab') return;
    const items = [...$('cn-list-panel').querySelectorAll('button,a,[tabindex]:not([tabindex="-1"])')].filter(node => !node.disabled);
    if (!items.length) return;
    if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items[items.length-1].focus(); }
    else if (!event.shiftKey && document.activeElement === items[items.length-1]) { event.preventDefault(); items[0].focus(); }
  }
  function openDrawer() {
    $('cn-master').classList.add('cn-list-open');
    $('cn-list-open').setAttribute('aria-expanded', 'true');
    $('cn-list-backdrop').hidden = false;
    const first = $('cn-check-list').querySelector('button');
    (first || $('cn-list-toggle')).focus();
    document.addEventListener('keydown', drawerKeys);
  }
  function closeDrawer(restore=true) {
    if (!$('cn-master').classList.contains('cn-list-open')) return;
    $('cn-master').classList.remove('cn-list-open');
    $('cn-list-open').setAttribute('aria-expanded', 'false');
    $('cn-list-backdrop').hidden = true;
    document.removeEventListener('keydown', drawerKeys);
    if (restore) $('cn-list-open').focus();
  }
  $('cn-list-open').addEventListener('click', openDrawer);
  $('cn-list-backdrop').addEventListener('click', () => closeDrawer());
  $('cn-reader-close').addEventListener('click', closeReader);
  $('cn-reader-prev').addEventListener('click', () => flipReader(-1));
  $('cn-reader-next').addEventListener('click', () => flipReader(1));
  $('cn-reader-docs').addEventListener('click', event => { const figure = event.target.closest('[data-doc]'); if (figure) { state.reader.focus = figure.dataset.doc; renderReader(); } });
  document.addEventListener('keydown', event => { if (event.key==='Escape') closeReader(); });

  $('cn-correction-form').addEventListener('submit', async event => {
    event.preventDefault();
    const c = collectCorrection();
    try {
      const task = await api(`/runs/${encodeURIComponent(state.task.task_id)}/corrections`, {method:'POST', body:JSON.stringify({expected_revision:current().result_revision, check:c, reason:$('cn-correction-reason').value, actor:'演示使用者', action_id:crypto.randomUUID()})});
      $('cn-correction').close(); clearTimeout(state.timer); state.generation++; rememberTask(task.task_id); await poll(task.task_id);
    } catch (error) { $('cn-correction-message').textContent = error.message; }
  });
  $('cn-review-action').addEventListener('change', () => {
    const action = $('cn-review-action').value;
    const observation = action==='personal_observation';
    $('cn-review-selection').hidden = action!=='reading_confirmation'; $('cn-observation').required = observation;
  });
  $('cn-review-form').addEventListener('submit', async event => {
    event.preventDefault();
    const action = $('cn-review-action').value;
    const ids = action!=='reading_confirmation' ? [state.selected] : [...document.querySelectorAll('[name="review-check"]:checked')].map(n => n.value);
    if (!ids.length) { $('cn-review-message').textContent = '请选择已阅读的关系。'; return; }
    // 保存前再次提示可见范围，不靠常驻说明代替确认。
    if (action==='personal_observation' && !window.confirm('个人观察保存后可能随任务链接被他人读取；公共视图只显示条数。确认保存？')) return;
    $('cn-save-review').disabled = true;
    try {
      const task = await api(`/runs/${encodeURIComponent(state.task.task_id)}/reviews`, {method:'POST', body:JSON.stringify({expected_revision:current().result_revision, action, check_ids:ids, reason:$('cn-review-reason').value, observation:$('cn-observation').value, actor:'公开报告使用者', action_id:crypto.randomUUID()})});
      clearTimeout(state.timer); state.generation++; rememberTask(task.task_id); await poll(task.task_id);
      $('cn-review-reason').value=''; $('cn-observation').value=''; $('cn-review-message').textContent='已保存新版本，原结果和未决条件均保留。';
    } catch (error) { $('cn-review-message').textContent = error.message; }
    finally { $('cn-save-review').disabled = state.task.can_modify===false; }
  });
  $('cn-close-correction').addEventListener('click', () => $('cn-correction').close());
  $('cn-back').addEventListener('click', () => { $('legacy-workspace').hidden=true; $('redesign-home').hidden=true; $('connectivity-root').hidden=false; $('cn-workspace').focus(); });

  (async () => {
    try {
      state.bootstrap = await api('/bootstrap');
      $('cn-notice').textContent = state.bootstrap.notice;
      $('cn-pair').innerHTML = state.bootstrap.pairs.map(pair => `<option value="${escape(pair.pair_id)}">${escape(pair.company)} · ${escape(pair.period)}</option>`).join('');
      $('cn-run').disabled = !state.bootstrap.pairs.length;
      reportCards();
      const shared = new URL(location.href).searchParams.get('connectivity_task');
      const saved = shared && /^(?:CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}$/.test(shared) ? shared : localStorage.getItem('audittrace-connectivity-task');
      if (saved) await poll(saved);
    } catch (error) { message(`工作台读取失败：${error.message}`, true); }
  })();
})();
