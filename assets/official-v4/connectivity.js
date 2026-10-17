/* 事实、计算与未决条件来自同一后端结果；阅读视角不创建模型调用。 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {bootstrap:null, task:null, selected:null, timer:null, generation:0};
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {supported:'依据齐备',unknown:'依据待补',conflicting:'存在冲突',consistent:'所选关系计算一致',precision_explained:'已知精度可解释',unexplained_difference:'未解释差异',not_comparable:'暂不可比较',not_executable:'暂不可执行',not_applicable:'不适用数值计算',read_confirmed:'使用者已阅读',unreviewed:'未人工复核',demo_modified:'演示更正',completed:'已完成',running:'执行中',queued:'排队中',degraded:'部分完成',failed:'失败',cancelled:'已取消',interrupted:'已中断',expired:'已过期',skipped:'未执行',pending:'等待',not_requested:'未调用模型',three_agents_completed:'三角色实际完成',single_completed:'单模型实际完成'};
  const roles = {left:'左侧',right:'右侧',total:'总额',component:'组成项',numerator:'分子',denominator:'分母',reported_ratio:'披露比例',occurrence:'披露位置'};
  const phases = {evidence_load:'读取原件',rule_calculation:'前提与计算',knowledge_retrieval:'原文补查',agent_collaboration:'角色协作',evidence_validation:'核实与重算',structured_output:'保存记录'};
  const badge = status => `<span class="cn-badge" data-state="${escape(status)}">${escape(labels[status]||status)}</span>`;
  const message = (text,error=false) => { $('cn-message').textContent=text; $('cn-message').classList.toggle('error',error); };
  const busy = value => document.querySelectorAll('#cn-form input,#cn-form select,#cn-run').forEach(control=>{control.disabled=value;});
  async function api(path,options={}) {
    const response=await fetch(`/api/connectivity${path}`,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json',...options.headers}});
    const data=await response.json().catch(()=>({detail:'服务未返回可读取的结果'}));
    if(!response.ok) {const error=new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));error.status=response.status;throw error;}
    return data;
  }
  function rememberTask(taskId){localStorage.setItem('audittrace-connectivity-task',taskId);const url=new URL(location.href);url.searchParams.set('connectivity_task',taskId);history.replaceState({},'',url);}
  const current = () => state.task?.result;
  const occurrence = id => current()?.occurrences.find(row=>row.occurrence_id===id);
  const check = () => current()?.checks.find(row=>row.check_id===state.selected);
  const sourceUrl = (id,page) => `/api/connectivity/sources/${encodeURIComponent(id)}?view=true&page=${page}`;
  function refs(items=[]) { return items.map(ref=>{ const row=occurrence(ref.occurrence_id); return row?`<button class="cn-evidence" type="button" data-source="${escape(row.occurrence_id)}">原文 PDF ${row.pdf_page} · ${escape(row.document_id)}</button>`:''; }).join(''); }
  function reportCards() {
    const pair=state.bootstrap.pairs.find(p=>p.pair_id===$('cn-pair').value);
    $('cn-documents').innerHTML=pair?pair.documents.map(d=>`<div class="cn-document"><strong>${escape(d.report_type==='AR'?'年度报告':'可持续发展 / ESG报告')} · ${escape(d.period)}</strong><small>${escape(d.version)}</small><a href="${sourceUrl(d.document_id,1)}" target="_blank" rel="noopener">阅读登记原件 ↗</a> <small>${escape(d.source_kind==='announcement_mirror'?'公告镜像，已单独标识':d.available?'本地原件已登记':'运行时从已登记官方来源取得')}</small></div>`).join(''):'';
  }
  async function poll(taskId,generation=state.generation) {
    try {
      const task=await api(`/runs/${encodeURIComponent(taskId)}`);
      if(generation!==state.generation) return;
      state.task=task; renderProgress(task);
      if(['queued','running'].includes(task.status)) { busy(true);state.timer=setTimeout(()=>poll(taskId,generation),1800); return; }
      busy(false); $('cn-cancel').disabled=true;
      if(task.result) { render(); message(`${labels[task.status]||task.status}。${task.result.occurrences.length}处候选、${task.result.checks.length}项关系；模型状态：${labels[task.result.model_status]||task.result.model_status}。`); }
      else { message(task.error||`任务${labels[task.status]||task.status}；未生成可读取结果。`,true); }
    } catch(error) {
      if(generation!==state.generation)return;
      if([404,410].includes(error.status)){busy(false);localStorage.removeItem('audittrace-connectivity-task');message(`原任务无法取得：${error.message}。可以显式开始新运行。`,true);return;}
      busy(true); message(`读取暂时失败：${error.message}。保留任务编号，正在重试读取原任务。`,true);
      state.timer=setTimeout(()=>poll(taskId,generation),4500);
    }
  }
  function renderProgress(task) {
    // 修订只保存重算结果，没有重新执行原模型阶段，不显示虚假的等待进度。
    $('cn-progress').hidden=Boolean(task.result?.parent_run_id)||(!['queued','running'].includes(task.status)&&!Object.keys(task.steps||{}).length);
    $('cn-stages').innerHTML=Object.entries(phases).map(([key,title])=>`<li data-status="${escape(task.steps?.[key]?.status||'pending')}">${escape(title)} · ${escape(labels[task.steps?.[key]?.status||'pending'])}</li>`).join('');
    $('cn-cancel').disabled=!['queued','running'].includes(task.status);
  }
  function render() {
    const run=current(); if(!run)return;
    const pair=state.bootstrap.pairs.find(p=>p.pair_id===run.documents[0]?.case_id);
    if(pair){$('cn-pair').value=pair.pair_id;reportCards();}
    if([...$('cn-mode').options].some(option=>option.value===run.execution_mode))$('cn-mode').value=run.execution_mode;
    $('cn-results').hidden=false; $('cn-result-title').textContent=`${run.company} · ${run.period} 关联核对`;
    const modes={calculation_only:'自动发现 · 仅计算',three_agents:'自动发现 · 三角色核对',single_model:'自动发现 · 完整单模型对照'};
    $('cn-run-meta').textContent=`版本${run.result_revision} / ${modes[run.execution_mode]||run.execution_mode} / ${run.parent_run_id?'原自动运行耗时':''}${(run.duration_ms/1000).toFixed(1)}秒${run.parent_run_id?'；本次修订未新增模型调用':''}`;
    $('cn-exports').innerHTML=['json','csv','docx'].map(format=>`<a href="/api/connectivity/runs/${encodeURIComponent(state.task.task_id)}/export/${format}">${format==='docx'?'Word':format.toUpperCase()}</a>`).join('');
    if(!run.checks.some(c=>c.check_id===state.selected)) state.selected=(run.checks.find(c=>c.relationship_evidence.length&&['RD-001','ENV-001','INT-001'].includes(c.rule_id))||run.checks[0])?.check_id;
    renderList();renderDetail();renderFindings();renderUserRecords();
    $('cn-coverage').innerHTML=run.coverage.map(c=>`<p>${escape(c.document_id)}：${c.total_pages}页 / 解析${c.parsed_pages}页 / 实际搜索${c.searched_pages.length}页 / 候选${c.discovered_count}处。失败：${escape(c.failed_pages.map(f=>`第${f.page}页 ${f.reason}`).join('；')||'无记录')}。</p>`).join('');
    $('cn-agents').innerHTML=(run.parent_run_id?'<p>以下是沿用的原运行调用记录，本次修订没有新增模型调用。</p>':'')+`<p>实际模型状态：${escape(labels[run.model_status]||run.model_status)}；发出调用${run.provider_calls.filter(c=>c.performed).length}次。</p>`+run.agent_steps.map(s=>`<p><strong>${escape(s.role)}</strong> ${escape(labels[s.status]||s.status)} · 采纳${s.accepted_check_ids?.length||0}项 / 拒绝${s.rejected?.length||0}项${s.failure_code?' · '+escape(s.failure_code):''}</p>`).join('')+run.provider_calls.map(c=>`<p>${escape(c.role)}：${escape(c.model||c.failure_code||'未配置')}；输入${c.input_tokens??'未知'} / 输出${c.output_tokens??'未知'} tokens；费用${c.cost??'未计价'}。</p>`).join('');
    const parent=state.task.parent_task_id;
    $('cn-revisions').innerHTML=`<p>父运行：${escape(run.parent_run_id||'无，原始自动运行')}。当前版本${run.result_revision}。${parent?`<a href="?connectivity_task=${encodeURIComponent(parent)}" target="_blank" rel="noopener">打开更正前记录 ↗</a>`:''}</p>`+run.reviews.map(r=>`<details><summary>${escape(r.created_at)} · ${escape(r.actor)} · ${escape(r.reason)}</summary><p>操作：${escape({relationship_correction:'关系更正',personal_observation:'个人观察',reading_confirmation:'已阅读记录'}[r.action]||r.action)}；${escape(r.check_id)}</p><h4>更正前</h4>${reviewRecord(r.before)}<h4>更正后</h4>${reviewRecord(r.after)}</details>`).join('');
  }
  function reviewRecord(record){
    return `<p>${escape(record.title||'')} · ${escape(labels[record.criteria_status]||record.criteria_status||'')} / ${escape(labels[record.calculation_status]||record.calculation_status||'')} / ${escape(labels[record.review_status]||record.review_status||'')}</p><ul>${(record.members||[]).map(m=>{const o=occurrence(m.occurrence_id);return `<li>${escape(roles[m.role])}：${escape(o?.label||m.occurrence_id)} ${escape(o?.value??'')} ${escape(o?.unit||'')} ${o?`<a href="${sourceUrl(o.document_id,o.pdf_page)}" target="_blank" rel="noopener">原文 PDF${o.pdf_page}</a>`:''}</li>`;}).join('')}</ul><p>计算：${escape(record.calculation?.expression||'无数值算式')}；差额${escape(record.calculation?.residual??'未计算')}</p><p>未决：${escape((record.unresolved||[]).join('；')||'本次选定关系无额外未决条件')}</p>`;
  }
  function renderList() {
    const run=current();if(!run)return;
    const view=$('cn-perspective').value;
    const notes={public:'先看指标含义与比较条件，再沿原文查看计算。未说明的范围会继续保留。',investor:'优先关注研发及环保投入构成，以及金额与年报的衔接；阅读视角不改变计算结果。',environment:'优先关注环保投入、强度分母与统计边界；不同范围的数字需分别说明。',professional:'展开完整口径、原文成员、计算、覆盖与角色记录；演示更正不构成正式专业批准。'};
    $('cn-perspective-note').textContent=notes[view];
    const checks=[...run.checks].sort((a,b)=>view==='environment'?Number(b.topic!=='research')-Number(a.topic!=='research'):view==='investor'?Number(b.topic==='research')-Number(a.topic==='research'):0);
    checks.sort((a,b)=>Number(b.relationship_evidence.length>0)-Number(a.relationship_evidence.length>0));
    $('cn-count').textContent=String(checks.length);
    $('cn-check-list').innerHTML=checks.length?checks.map(c=>`<button type="button" class="cn-check${c.check_id===state.selected?' active':''}" data-check="${escape(c.check_id)}" aria-pressed="${c.check_id===state.selected}"><small>${escape(state.bootstrap.rules[c.rule_id]?.name||c.rule_id)}</small><strong>${escape(c.title)}</strong><small>${badge(c.criteria_status)} ${badge(c.calculation_status)}</small></button>`).join(''):'<p>尚未形成关系候选，请查看实际覆盖及提取情况。</p>';
  }
  function renderDetail() {
    const c=check();if(!c){$('cn-detail').textContent='没有可显示的关系记录。';return;}
    $('cn-detail').innerHTML=`<p class="cn-subtitle">${escape(c.check_id)} / ${escape(c.rule_id)} / ${escape(c.rule_version)}</p><h2>${escape(c.title)}</h2><div class="cn-statuses"><div><small>口径</small>${badge(c.criteria_status)}</div><div><small>计算</small>${badge(c.calculation_status)}</div><div><small>使用者处理</small>${badge(c.review_status)}</div></div><h3>先看能否比较</h3>${c.conditions.map(cond=>`<div class="cn-condition"><div class="cn-condition-head"><strong>${escape(cond.name)}</strong>${badge(cond.status)}</div><p>${escape(cond.reason)}</p>${refs(cond.evidence)}</div>`).join('')}<h3>关系成员</h3>${c.members.map(m=>{const o=occurrence(m.occurrence_id);return o?`<div class="cn-member"><strong>${escape(roles[m.role]||m.role)} · ${escape(o.label)}</strong><div class="cn-number">${escape(o.value??'未提取数值')} <small>${escape(o.unit||'单位尚未确定')}</small></div><small>${escape(o.document_id)} · PDF ${o.pdf_page} · 年度${escape(o.year||'待核实')} · ${escape(o.quality)}</small>${refs([{occurrence_id:o.occurrence_id}])}${o.currency_source_id?`<small>币种采用报告声明：${refs([{occurrence_id:o.currency_source_id}])}</small>`:''}</div>`:'';}).join('')}<h3>计算与差额</h3><div class="cn-equation">${escape(c.calculation.expression||'尚无可执行算式')}<br>差额：${escape(c.calculation.residual??'未计算')} ${escape(c.calculation.normalized_unit||'')}${c.calculation.hypothetical?'<br>条件未齐备，以上仅为列明成员的试算。':''}</div><p>${refs(c.relationship_evidence)}</p><h3>关联记录</h3><p>${c.related_checks.map(id=>`<button type="button" data-related="${escape(id)}">查看 ${escape(id)}</button>`).join(' ')||'本项尚无其它解释分组记录。'}</p><h3>解释与仍待说明的部分</h3><div class="cn-explanation">${escape(c.explanation||'本次尚未找到充分的具体解释。')}${refs(c.explanation_evidence)}</div><ul>${c.unresolved.map(u=>`<li>${escape(u)}</li>`).join('')||'<li>当前所选关系无额外未决条件，不代表企业整体已获证实。</li>'}</ul><button id="cn-edit" type="button">更正成员、关系依据并重算</button><details><summary>计算明细与精度区间</summary><pre>${escape(JSON.stringify(c.calculation,null,2))}</pre></details>`;
    $('cn-edit').disabled=state.task.can_modify===false;$('cn-edit').title=state.task.can_modify===false?'当前浏览器可阅读，创建任务的浏览器可更正':'';$('cn-edit').addEventListener('click',openCorrection);
    const selected=c.members.map(m=>occurrence(m.occurrence_id)).filter(Boolean);
    renderSources(selected);
  }
  function renderSources(selected) {
    const run=current();if(!run)return;
    $('cn-sources').innerHTML=run.documents.map(doc=>{const row=selected.find(o=>o.document_id===doc.document_id);const page=row?.pdf_page||1;return `<section class="cn-source"><h3>${escape(doc.report_type==='AR'?'年度报告':'可持续发展 / ESG报告')} · ${escape(doc.document_id)}</h3><form data-page-form="${escape(doc.document_id)}"><label>PDF顺序页<input type="number" min="1" max="${doc.pages}" value="${page}" required aria-label="${escape(doc.document_id)}的PDF顺序页"><button type="submit">定位</button></label></form><a href="${sourceUrl(doc.document_id,page)}" target="_blank" rel="noopener">放大阅读第${page}页 ↗</a><div class="cn-page-frame"><div class="cn-page-layer"><img width="${Number(row?.page_width||595)}" height="${Number(row?.page_height||842)}" src="/api/connectivity/sources/${encodeURIComponent(doc.document_id)}/pages/${page}.png" alt="${escape(doc.company)} ${escape(doc.report_type)} 原件第${page}页" loading="lazy">${row?.page_width&&row?.page_height&&row.bbox.length===4&&row.bbox.every(Number.isFinite)?`<svg class="cn-location" viewBox="0 0 ${row.page_width} ${row.page_height}" aria-label="所选原文坐标标记"><rect x="${row.bbox[0]}" y="${row.bbox[1]}" width="${row.bbox[2]-row.bbox[0]}" height="${row.bbox[3]-row.bbox[1]}"></rect></svg>`:''}</div></div><p>${escape(row?.row_header||'可点击成员或依据定位具体原文。')}</p></section>`;}).join('');
  }
  function renderFindings(){const items=current().findings;$('cn-findings').innerHTML=items.length?items.map(f=>`<article class="cn-finding"><strong>${escape(f.question)}</strong><small>${escape(f.check_id)} · ${escape(f.known_facts)}</small><p>进一步了解：${escape(f.requested_material)}</p><p>用途：${escape(f.purpose)}</p></article>`).join(''):'<p>当前选定关系未保留待查问题；不代表已全面核实报告。</p>';}
  function renderUserRecords(){
    const run=current();
    $('cn-save-review').disabled=state.task.can_modify===false;
    if(state.task.can_modify===false)$('cn-review-message').textContent='当前为只读记录；创建任务的浏览器可保存更正与观察。';
    $('cn-review-checks').innerHTML=run.checks.map(c=>`<label><input type="checkbox" name="review-check" value="${escape(c.check_id)}"> ${escape(c.title)}</label>`).join('');
    $('cn-personal-notes').innerHTML=run.professional_notes.map(n=>`<article class="cn-finding"><strong>个人观察 · ${escape(n.check_id)}</strong><p>${escape(n.observation)}</p><small>${escape(n.actor)} · ${escape(n.created_at)} · 理由：${escape(n.reason)}</small></article>`).join('');
  }
  function preparePrint(){
    const run=current();if(!run)return;
    $('cn-print-all').innerHTML=run.checks.map(c=>`<article class="cn-print-relation"><h2>${escape(c.title)}</h2><p>${escape(c.check_id)} · ${escape(c.rule_id)} · ${escape(labels[c.criteria_status]||c.criteria_status)} / ${escape(labels[c.calculation_status]||c.calculation_status)} / ${escape(labels[c.review_status]||c.review_status)}</p>${c.conditions.map(n=>`<p><strong>${escape(n.name)}</strong>：${escape(labels[n.status]||n.status)}；${escape(n.reason)}${n.evidence.map(r=>`<br>原文 ${escape(r.occurrence_id)}：${escape(r.quote)}`).join('')}</p>`).join('')}${c.members.map(m=>{const o=occurrence(m.occurrence_id);return o?`<p><strong>${escape(roles[m.role])}：${escape(o.label)}</strong> ${escape(o.value??'未提取数值')} ${escape(o.unit)}<br>${escape(o.document_id)} / PDF ${o.pdf_page}<br>${escape(o.context)}</p>`:'';}).join('')}<p>计算明细：${escape(JSON.stringify(c.calculation))}</p><p>解释：${escape(c.explanation||'尚无充分解释')}</p>${[...c.relationship_evidence,...c.explanation_evidence].map(r=>`<p>关系或解释依据 ${escape(r.occurrence_id)}：${escape(r.quote)}</p>`).join('')}<p>未决：${escape(c.unresolved.join('；')||'当前选定关系无额外未决条件')}</p></article>`).join('');
  }
  window.addEventListener('beforeprint',preparePrint);
  function occurrenceOptions(selected){return current().occurrences.map(o=>`<option value="${escape(o.occurrence_id)}"${o.occurrence_id===selected?' selected':''}>${escape(o.document_id)} / PDF${o.pdf_page} / ${escape(o.label.slice(0,35))} / ${escape(o.value??'文字')} ${escape(o.unit)}</option>`).join('');}
  function evidenceTail(items,key){
    if(items.length<2)return '';
    return `<details class="cn-reference-tail"><summary>其它已保存出处（${items.length-1}条）</summary>${items.slice(1).map((r,i)=>{const o=occurrence(r.occurrence_id);return `<label><input type="checkbox" checked data-extra-ref="${key}" value="${i+1}">保留 ${escape(o?.document_id||r.occurrence_id)} PDF${o?.pdf_page||'?'}：${escape(r.quote)}</label>`;}).join('')}</details>`;
  }
  function retainedReferences(original,key,source,quote){
    const extra=[...document.querySelectorAll(`[data-extra-ref="${key}"]:checked`)].map(input=>original[Number(input.value)]).filter(Boolean);
    return (quote.trim()?[{occurrence_id:source,quote}]:[]).concat(extra);
  }
  function collectCorrection(){
    const c=structuredClone(state.editDraft);
    c.title=$('cn-relation-title').value.trim();c.rule_id=$('cn-edit-rule').value;c.operator=state.bootstrap.rules[c.rule_id].operator;
    c.members=[...document.querySelectorAll('[data-member]')].map(select=>({occurrence_id:select.value,role:document.querySelector(`[data-member-role="${select.dataset.member}"]`).value}));
    c.conditions=c.conditions.map((cond,i)=>({...cond,status:document.querySelector(`[data-condition-status="${i}"]`).value,reason:document.querySelector(`[data-condition-reason="${i}"]`).value,evidence:retainedReferences(cond.evidence,`condition-${i}`,document.querySelector(`[data-condition-source="${i}"]`).value,document.querySelector(`[data-condition-quote="${i}"]`).value)}));
    c.relationship_evidence=retainedReferences(c.relationship_evidence,'relation',$('cn-relation-source').value,$('cn-relation-quote').value);
    c.explanation=$('cn-edit-explanation').value.trim();c.explanation_evidence=retainedReferences(c.explanation_evidence,'explanation',$('cn-explanation-source').value,$('cn-explanation-quote').value);
    return c;
  }
  function renderCorrectionFields(){
    const c=state.editDraft;const rule=state.bootstrap.rules[c.rule_id];
    $('cn-correction-fields').innerHTML=`<label>关系名称<input id="cn-relation-title" required maxlength="200" value="${escape(c.title)}"></label><label>核对关系<select id="cn-edit-rule">${Object.entries(state.bootstrap.rules).map(([id,r])=>`<option value="${id}"${id===c.rule_id?' selected':''}>${escape(r.name)}</option>`).join('')}</select></label><label>查找原文成员或依据<input id="cn-source-filter" type="search" placeholder="输入指标名、报告ID或PDF页码"></label><p>可增删关系成员；新关系仍需逐项核实比较前提。筛选会保留各字段当前所选原文。</p>`;
    $('cn-correction-fields').insertAdjacentHTML('beforeend',c.members.map((m,i)=>`<fieldset class="cn-edit-condition"><legend>成员${i+1}</legend><label>成员角色<select data-member-role="${i}">${rule.roles.map(role=>`<option value="${role}"${role===m.role?' selected':''}>${escape(roles[role])}</option>`).join('')}</select></label><label>原文位置<select data-member="${i}">${occurrenceOptions(m.occurrence_id)}</select></label><button type="button" data-remove-member="${i}">移除此成员</button></fieldset>`).join('')+'<button type="button" id="cn-add-member">增加原文成员</button>');
    $('cn-correction-fields').insertAdjacentHTML('beforeend',c.conditions.map((cond,i)=>`<fieldset class="cn-edit-condition"><legend>${escape(cond.name)}</legend><label>依据状态<select data-condition-status="${i}">${['unknown','supported','conflicting'].map(status=>`<option value="${status}"${status===cond.status?' selected':''}>${escape(labels[status])}</option>`).join('')}</select></label><label>依据位置<select data-condition-source="${i}">${occurrenceOptions(cond.evidence[0]?.occurrence_id||c.members[0]?.occurrence_id)}</select></label><label>逐字引用原文<textarea data-condition-quote="${i}" rows="2">${escape(cond.evidence[0]?.quote||'')}</textarea></label><label>理由<textarea data-condition-reason="${i}" rows="2">${escape(cond.reason)}</textarea></label>${evidenceTail(cond.evidence,`condition-${i}`)}</fieldset>`).join(''));
    $('cn-correction-fields').insertAdjacentHTML('beforeend',`<fieldset class="cn-edit-condition"><legend>具体关系依据</legend><label>原文位置<select id="cn-relation-source">${occurrenceOptions(c.relationship_evidence[0]?.occurrence_id||c.members[0]?.occurrence_id)}</select></label><label>支持本次关系的原文<textarea id="cn-relation-quote" rows="3" required>${escape(c.relationship_evidence[0]?.quote||'')}</textarea></label>${evidenceTail(c.relationship_evidence,'relation')}</fieldset><fieldset class="cn-edit-condition"><legend>差异解释及其出处</legend><label>具体解释<textarea id="cn-edit-explanation" rows="3">${escape(c.explanation||'')}</textarea></label><label>解释出处<select id="cn-explanation-source">${occurrenceOptions(c.explanation_evidence[0]?.occurrence_id||c.members[0]?.occurrence_id)}</select></label><label>解释所用原句<textarea id="cn-explanation-quote" rows="3">${escape(c.explanation_evidence[0]?.quote||'')}</textarea></label>${evidenceTail(c.explanation_evidence,'explanation')}</fieldset>`);
    $('cn-edit-rule').addEventListener('change',()=>{
      state.editDraft=collectCorrection();const next=state.bootstrap.rules[state.editDraft.rule_id];
      const required=next.conditions||(['主体','期间','定义','范围','单位'].concat(next.operator==='sum'?['组成完整','互不重叠']:next.operator==='ratio'?['公式']:[]));
      state.editDraft.conditions=required.map(name=>({name,status:'unknown',reason:'关系类型已更改，请按本次关系补充具体依据',evidence:[]}));
      state.editDraft.members.forEach((m,i)=>{m.role=next.roles[Math.min(i,next.roles.length-1)];});renderCorrectionFields();
    });
    $('cn-add-member').addEventListener('click',()=>{
      state.editDraft=collectCorrection();if(state.editDraft.members.length>=100){$('cn-correction-message').textContent='单项关系最多100个成员。';return;}
      const allowed=state.bootstrap.rules[state.editDraft.rule_id].roles;const used=state.editDraft.members.map(m=>m.role);
      state.editDraft.members.push({occurrence_id:current().occurrences[0].occurrence_id,role:allowed.find(role=>!used.includes(role))||allowed[allowed.length-1]});renderCorrectionFields();
    });
    document.querySelectorAll('[data-remove-member]').forEach(button=>button.addEventListener('click',()=>{state.editDraft=collectCorrection();state.editDraft.members.splice(Number(button.dataset.removeMember),1);renderCorrectionFields();}));
    $('cn-source-filter').addEventListener('input',event=>{
      const query=event.target.value.trim().toLowerCase();document.querySelectorAll('#cn-correction-fields select[data-member],#cn-correction-fields select[data-condition-source],#cn-relation-source,#cn-explanation-source').forEach(select=>{
        const selected=select.value;select.innerHTML=current().occurrences.filter(o=>o.occurrence_id===selected||!query||`${o.document_id} PDF${o.pdf_page} ${o.label} ${o.value??''}`.toLowerCase().includes(query)).map(o=>`<option value="${escape(o.occurrence_id)}"${o.occurrence_id===selected?' selected':''}>${escape(o.document_id)} / PDF${o.pdf_page} / ${escape(o.label.slice(0,35))} / ${escape(o.value??'文字')} ${escape(o.unit)}</option>`).join('');
      });
    });
  }
  function openCorrection(){state.editDraft=structuredClone(check());renderCorrectionFields();$('cn-correction-message').textContent='';$('cn-correction-reason').value='';$('cn-correction').showModal();}

  $('cn-form').addEventListener('submit',async event=>{event.preventDefault();const topics=[...document.querySelectorAll('#cn-form input[name="topic"]:checked')].map(n=>n.value);if(!topics.length){message('至少选择一个关注事项。',true);return;}clearTimeout(state.timer);state.generation++;state.selected=null;busy(true);$('cn-results').hidden=true;$('cn-progress').hidden=true;$('cn-cancel').disabled=true;message('已提交真实报告核对，请查看实际阶段。');try{const task=await api('/runs',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({pair_id:$('cn-pair').value,topics,mode:$('cn-mode').value})});rememberTask(task.task_id);await poll(task.task_id);}catch(error){message(error.message,true);busy(false);}});
  $('cn-cancel').addEventListener('click',async()=>{if(!state.task)return;try{await api(`/runs/${encodeURIComponent(state.task.task_id)}/cancel`,{method:'POST'});await poll(state.task.task_id);}catch(error){message(error.message,true);}});
  $('cn-pair').addEventListener('change',reportCards);$('cn-perspective').addEventListener('change',renderList);$('cn-print').addEventListener('click',()=>{preparePrint();window.print();});
  $('cn-check-list').addEventListener('click',event=>{const button=event.target.closest('[data-check]');if(button){state.selected=button.dataset.check;renderList();renderDetail();}});
  $('cn-detail').addEventListener('click',event=>{const related=event.target.closest('[data-related]');if(related){state.selected=related.dataset.related;renderList();renderDetail();return;}const button=event.target.closest('[data-source]');if(button){const row=occurrence(button.dataset.source);renderSources([row]);$('cn-sources').scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}});
  $('cn-sources').addEventListener('submit',event=>{const form=event.target.closest('[data-page-form]');if(!form)return;event.preventDefault();const doc=current().documents.find(d=>d.document_id===form.dataset.pageForm);const page=Number(form.querySelector('input').value);if(!Number.isInteger(page)||page<1||page>doc.pages)return;const section=form.closest('.cn-source');section.querySelector('.cn-location')?.remove();section.querySelector('img').src=`/api/connectivity/sources/${encodeURIComponent(doc.document_id)}/pages/${page}.png`;section.querySelector('a').href=sourceUrl(doc.document_id,page);section.querySelector('a').textContent=`放大阅读第${page}页 ↗`;});
  $('cn-correction-form').addEventListener('submit',async event=>{event.preventDefault();const c=collectCorrection();try{const task=await api(`/runs/${encodeURIComponent(state.task.task_id)}/corrections`,{method:'POST',body:JSON.stringify({expected_revision:current().result_revision,check:c,reason:$('cn-correction-reason').value,actor:'演示使用者',action_id:crypto.randomUUID()})});$('cn-correction').close();clearTimeout(state.timer);state.generation++;rememberTask(task.task_id);await poll(task.task_id);}catch(error){$('cn-correction-message').textContent=error.message;}});
  $('cn-review-action').addEventListener('change',()=>{
    const observation=$('cn-review-action').value==='personal_observation';
    $('cn-review-selection').hidden=observation;$('cn-observation').required=observation;
  });
  $('cn-review-form').addEventListener('submit',async event=>{
    event.preventDefault();const action=$('cn-review-action').value;
    const ids=action==='personal_observation'?[state.selected]:[...document.querySelectorAll('[name="review-check"]:checked')].map(n=>n.value);
    if(!ids.length){$('cn-review-message').textContent='请选择已阅读的关系。';return;}
    $('cn-save-review').disabled=true;
    try{
      const task=await api(`/runs/${encodeURIComponent(state.task.task_id)}/reviews`,{method:'POST',body:JSON.stringify({expected_revision:current().result_revision,action,check_ids:ids,reason:$('cn-review-reason').value,observation:$('cn-observation').value,actor:'公开报告使用者',action_id:crypto.randomUUID()})});
      clearTimeout(state.timer);state.generation++;rememberTask(task.task_id);await poll(task.task_id);
      $('cn-review-reason').value='';$('cn-observation').value='';$('cn-review-message').textContent='已保存新版本，原结果和未决条件均保留。';
    }catch(error){$('cn-review-message').textContent=error.message;}finally{$('cn-save-review').disabled=state.task.can_modify===false;}
  });
  $('cn-close-correction').addEventListener('click',()=>$('cn-correction').close());
  $('cn-history').addEventListener('click',()=>{$('redesign-home').hidden=true;$('connectivity-root').hidden=true;$('legacy-workspace').hidden=false;document.dispatchEvent(new Event('audittrace:legacy-open'));$('cn-back').focus();});$('cn-back').addEventListener('click',()=>{$('legacy-workspace').hidden=true;$('redesign-home').hidden=false;$('connectivity-root').hidden=false;$('cn-history').focus();});
  (async()=>{try{state.bootstrap=await api('/bootstrap');$('cn-notice').textContent=state.bootstrap.notice;$('cn-pair').innerHTML=state.bootstrap.pairs.map(pair=>`<option value="${escape(pair.pair_id)}">${escape(pair.company)} · ${escape(pair.period)}</option>`).join('');$('cn-run').disabled=!state.bootstrap.pairs.length;reportCards();const shared=new URL(location.href).searchParams.get('connectivity_task');const saved=shared&&/^(?:CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}$/.test(shared)?shared:localStorage.getItem('audittrace-connectivity-task');if(saved)await poll(saved);}catch(error){message(`工作台读取失败：${error.message}`,true);}})();
})();
