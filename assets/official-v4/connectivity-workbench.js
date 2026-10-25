/* 原生分层有向图：每次突出一条真实关系，SVG 仅绘制边；节点使用可键盘操作的按钮。 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), VM = window.AuditTraceViewModel, S = window.AuditTraceStatus;
  const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const arr = value => Array.isArray(value) ? value : [];
  const edgeLabels = {supported:'已支持的披露关系',indirect:'间接线索',model:'模型推断',gap:'依据不足 / 待证实'};
  let run = null, task = null, model = null, selected = null, node = 'verdict', role = null;
  let collaborationRun = null, collaborationTask = null;
  const started = new Set();
  const chip = (text,tone='neutral') => `<span class="at-chip" data-tone="${esc(tone)}">${esc(text)}</span>`;
  const source = o => `<button type="button" class="at-source" data-reader="${esc(o.occurrence_id)}"><small>${esc(model.documents.get(o.document_id)?.report_type === 'AR' ? '年度报告' : '可持续发展报告')} · PDF ${esc(o.pdf_page)}</small><strong>${esc(o.label)}</strong><span class="at-number">${esc(o.value ?? '未提取数值')} ${esc(o.unit)}</span><span>${esc(o.context)}</span><em>回查原页 ↗</em></button>`;
  const pick = id => document.dispatchEvent(new CustomEvent('audittrace:connectivity-select-check',{detail:{check_id:id,task_id:task?.task_id}}));
  function reset() { run=null;task=null;model=null;selected=null;node='verdict';role=null;collaborationRun=null;collaborationTask=null; }
  function renderOverview(value,job,id) {
    const changed = task?.task_id !== job.task_id;
    run=value;task=job;model=VM.project(run,S);
    selected=model.paths.some(p=>p.id===id) ? id : model.paths[0]?.id;
    if(changed) node='verdict';
    $('cn-fourq').innerHTML = `<div class="at-verdict-meta"><span>分析研判 / DISCLOSURE INSIGHTS</span>${chip(VM.provenance(task,started.has(task.task_id)))}</div>
      <h2 class="at-main-verdict" id="at-main-verdict">${esc(model.sentence)}</h2>
      <p class="at-verdict-boundary">披露关系有证据支持，仍不等于已证明财务因果影响。程序结论与 AI 意见分别保留。</p>
      <div class="at-findings-grid"><section><span>01 / 关联发现</span><strong><b class="at-summary-number">${model.covered.length}</b> 项双报告证据路径</strong><p>${model.supported.length ? `${model.supported.length} 项达到已支持的披露关系条件。` : '尚无达到全部条件的已支持披露关系。'}点击路径查看实际报告项目。</p></section>
      <section><span>02 / 优先核查</span><strong>${model.priorities.length ? model.priorities.length+' 项优先事项' : '未登记高优先级事项'}</strong><p>沿用程序 / 模型登记的优先级，并纳入程序差异；不自造风险评分。</p></section>
      <section><span>03 / 证据缺口</span><strong><b class="at-summary-number">${model.gaps.length}</b> 项需补充依据</strong><p>报告单侧定位、缺失比较前提分别展示；缺口不记为核验成功。</p></section></div>`;
    $('cn-nextq').innerHTML = `<section class="at-graph-section" aria-labelledby="at-graph-title"><header class="at-section-head"><div><p class="at-eyebrow">SUSTAINABILITY → FINANCIAL DISCLOSURES</p><h2 id="at-graph-title">可持续信息—财务影响穿透图</h2></div><span>选择事项，再点击路径节点回查依据</span></header>
      <div class="at-legend">${Object.entries(edgeLabels).map(([key,text])=>`<span data-edge="${key}"><i></i>${text}</span>`).join('')}</div>
      <div id="at-paths" class="at-paths" role="group" aria-label="选择完整关联路径">${model.paths.map(p=>`<button type="button" data-path="${esc(p.id)}" aria-pressed="${p.id===selected}"><strong>${esc(p.check.title)}</strong><small>${esc(p.level.label)} · ${p.both?'双报告证据':'单侧 / 未定位'}</small></button>`).join('')}</div>
      ${model.paths.length ? '<div class="at-graph-layout"><div id="at-path-canvas" class="at-path-canvas"></div><aside id="at-inspector" class="at-inspector" aria-label="所选节点证据与研判" aria-live="polite"></aside></div>' : '<p class="at-empty">本次没有关联路径，不生成装饰节点。运行记录与搜索覆盖仍可查看。</p>'}
      <p class="at-caption">图中仅使用本任务已定位的披露、关系依据和计算记录。行动、财务影响或因果依据缺失时直接标记缺口；不自动补齐链条。</p></section>
      <section class="at-priority" aria-labelledby="at-priority-title"><header class="at-section-head"><div><p class="at-eyebrow">NEXT INVESTIGATION</p><h2 id="at-priority-title">本次最值得关注的事项</h2></div><button type="button" data-at-stage="4">全部事项与证据 ↗</button></header>
      ${model.paths.slice(0,3).map((p,i)=>`<article class="at-priority-row"><span class="at-rank">0${i+1}</span><div><button type="button" data-path="${esc(p.id)}">${esc(p.check.title)} ↗</button><p>${esc(p.priorityReason || p.check.unresolved?.[0] || p.level.definition)}</p><small>下一步：${esc(p.next[0] || '回查已登记关系依据和披露原页；本次未登记追加动作。')}</small></div><div>${chip(p.level.label,p.level.key)}${p.priority?chip(({high:'高优先级',medium:'中优先级',low:'低优先级'})[p.priority]):chip('未登记优先级')}</div></article>`).join('') || '<p class="at-empty">没有可排序的事项；不等于已全面核实报告。</p>'}
      <p class="at-caption">排序依据：登记的高 / 中 / 低优先级，程序差异优先，同级保留原结果顺序；未分级项不推定风险等级。</p></section>
      <section class="at-matrix" aria-labelledby="at-matrix-title"><header class="at-section-head"><div><p class="at-eyebrow">EVIDENCE COVERAGE</p><h2 id="at-matrix-title">哪些路径已有依据，哪里还缺证据？</h2></div><span>覆盖情况不等于核验结论</span></header>
      <div class="at-table-scroll"><table><caption class="sr-only">本次全部关系的报告定位、比较前提和程序结论</caption><thead><tr><th scope="col">关联事项</th><th scope="col">可持续披露</th><th scope="col">年报项目</th><th scope="col">比较前提</th><th scope="col">程序状态</th></tr></thead><tbody>${model.paths.map(p=>`<tr><th scope="row"><button type="button" data-path="${esc(p.id)}">${esc(p.check.title)}</button></th><td>${p.esg.length?chip('已定位 '+p.esg.length+' 处','located'):chip('未定位','gap')}</td><td>${p.financial.length?chip('已定位 '+p.financial.length+' 处','located'):chip('未定位','gap')}</td><td>${p.missing.length?esc(p.missing.map(c=>c.name).join('、'))+' 待核实':'已登记前提有依据'}</td><td>${chip(p.level.label,p.level.key)}</td></tr>`).join('')}</tbody></table></div></section>`;
    select(selected);
  }
  function select(id) {
    if(!model || !model.paths.some(p=>p.id===id)) return;
    selected=id;
    document.querySelectorAll('#at-paths [data-path]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.path===selected)));
    const p=model.paths.find(p=>p.id===selected), c=p.check;
    const specs = [
      ['esg','可持续事项',p.esg[0]?.label,p.esg[0]?'报告披露事实':'缺口：未定位可持续报告原文'],
      ['basis','行动 / 关系依据',p.reason?'已定位披露关系依据':null,p.reason?edgeLabels[p.edge]+'；行动依据见原文':'缺口：未登记可核实的行动或关系依据'],
      ['impact','财务影响路径',p.relation.label,(p.relation.pending?p.relation.pending+'；':'')+'财务因果影响未证实'],
      ['financial','年报项目',p.financial[0]?.label,p.financial[0]?'报告披露事实':'缺口：未定位年报财务项目'],
      ['verdict','核验结论',p.level.label,p.missing.length?'缺少 '+p.missing.map(c=>c.name).join('、')+' 的支持':p.level.definition]
    ];
    $('at-path-canvas').innerHTML = `<div class="at-path-title"><strong>${esc(c.title)}</strong>${chip(edgeLabels[p.edge],p.edge)}</div><div class="at-directed-graph" data-edge="${p.edge}"><svg class="at-edges" viewBox="0 0 1000 180" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="at-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="currentColor"/></marker></defs>${[176,378,580,782].map(x=>`<path d="M${x} 90 H${x+43}" marker-end="url(#at-arrow)"/>`).join('')}</svg>${specs.map(([key,title,text,note],i)=>`<button type="button" class="at-node ${!text?'at-node-gap':''}" data-node="${key}" aria-pressed="${node===key}"><span>0${i+1} / ${title}</span><strong>${esc(text || '依据缺失')}</strong><small>${esc(note)}</small></button>`).join('')}</div><div class="at-path-progress"><span>可持续披露 ${p.esg.length?'已定位':'待定位'}</span><span>年报披露 ${p.financial.length?'已定位':'待定位'}</span><span>比较前提 ${arr(c.conditions).length-p.missing.length}/${arr(c.conditions).length} 项有据</span></div>`;
    const nodeTitles={esg:'可持续事项的披露依据',basis:'行动、关系依据与边类型',impact:'财务路径与计算边界',financial:'年度报告项目与原文',verdict:'程序事实 · AI 研判 · 下一步'};
    const analysis=p.ai;
    const calc=c.calculation || {};
    let body='';
    if(node==='esg' || node==='financial') {
      const rows=node==='esg'?p.esg:p.financial;
      body=rows.map(source).join('') || '<p class="at-gap">本任务未定位这一侧的报告证据。不能据此认定企业没有披露，也不能推定关联已成立。</p>';
    } else if(node==='basis') {
      body=`<h4>${esc(edgeLabels[p.edge])}</h4><p>${esc(p.reason || '未登记关系依据。')}</p><p class="at-caption">边类型按双报告位置、原文引用、关系依据类型与程序状态生成；有联系不代表具有财务因果关系。</p>${arr(c.relationship_evidence).map(r=>model.occurrences.get(r.occurrence_id)).filter(Boolean).map(source).join('')}`;
    } else if(node==='impact') {
      body=`<h4>${esc(p.relation.label)}</h4><p>${esc(c.mapping_reason || p.relation.pending || '按登记的成员角色核对披露关系。')}</p><h4>实际计算</h4><p class="at-formula">${esc(calc.expression || '尚无可执行算式')}</p>${calc.gate?`<p class="at-gap">${esc(calc.gate.conclusion)}；本次不输出正式差额。</p>`:`<p>程序状态：${esc(p.level.label)}</p>`}${c.hypothetical?`<p>条件试算：${esc(c.hypothetical.expression || '')}；假设 ${esc(arr(c.hypothetical.assumptions).join('；'))}。不计作正式结论。</p>`:''}<p class="at-caption">本版未提供完整的战略—行动—财务因果识别字段。不将固定资产变化自动认定为环保投资。</p>`;
    } else {
      body=`<h4>程序事实</h4>${chip(p.level.label,p.level.key)}<p>${esc(p.level.definition)}</p>${p.missing.length?`<p class="at-gap">待核实前提：${esc(p.missing.map(x=>x.name+'：'+x.reason).join('；'))}</p>`:''}<h4>AI 意见 · 仅供参考</h4><p>${esc(analysis?.summary || (run.execution_mode==='calculation_only'?'本次仅计算，未调用模型。':'本事项没有当前有效的模型意见；旧意见和被驳回意见不作为当前判断。'))}</p>${analysis?`<small>模型贡献：${esc(VM.roleNames[analysis.producer_role] || analysis.producer_role || '见角色记录')} · ${esc(analysis.producer_model || '模型身份见调用记录')}</small>`:''}<h4>下一步检查</h4><ul>${p.next.slice(0,4).map(n=>`<li>${esc(n)}</li>`).join('') || '<li>回查关系原文与比较前提，本次未登记追加程序。</li>'}</ul>`;
    }
    $('at-inspector').innerHTML=`<p class="at-eyebrow">SELECTED NODE / ${esc(c.check_id)}</p><h3 tabindex="-1" id="at-node-title">${nodeTitles[node]}</h3>${body}<button type="button" class="at-detail-link" data-at-evidence="${esc(c.check_id)}">打开完整事项与双报告证据 ↗</button>`;
  }
  function handoffs(value,current) {
    const entries=current.events.filter(e=>['role_context','role_contribution','agent_tool_result'].includes(e.kind));
    if(!entries.length) return '<p>本角色未登记可展示的交接输入；不推定读取了全部报告。</p>';
    return entries.slice(-6).map(e=>{
      const ids=arr(e.check_ids).length?e.check_ids:[e.check_id].filter(Boolean);
      const titles=ids.map(id=>arr(value?.checks).find(c=>c.check_id===id)?.title || id);
      const evidence=arr(e.delivered_evidence_ids || e.sent_ids);
      return `<p><strong>${esc(titles.join('；') || '本次报告上下文')}</strong><small>${evidence.length ? '实际交付 '+evidence.length+' 处原文' : '本条未登记交付原文ID'}${e.producer_role?' · 来自 '+esc(e.producer_role):''}${e.consumer_role?' → '+esc(e.consumer_role):''}</small>${esc(e.note || e.reason || '')}</p>`;
    }).join('') + `<small>显示最近 ${Math.min(entries.length,6)} 条交接摘要；完整输入标识与工具轨迹见下方实际记录。</small>`;
  }
  function roleJudgments(value,current) {
    const analyses=arr(value?.ai_analyses).filter(a=>a.producer_role===current.role && a.status!=='needs_refresh' && a.review_status!=='rejected');
    return analyses.slice(0,3).map(a=>`<p><strong>${esc(arr(value?.checks).find(c=>c.check_id===a.check_id)?.title || a.check_id)}</strong><br>${esc(a.summary)}<br><button type="button" data-at-result="${esc(a.check_id)}">查看这项研判及证据路径 ↗</button></p>`).join('');
  }
  function renderCollaboration(value,job) {
    collaborationRun=value;collaborationTask=job;
    const calculationOnly=value?.execution_mode==='calculation_only' || (!value && $('cn-mode')?.value==='calculation_only');
    const rows=calculationOnly?[]:VM.collaboration(value,job), trace=arr(value?.intelligence_trace);
    if(!rows.some(r=>r.role===role)) role=rows[0]?.role;
    const current=rows.find(r=>r.role===role);
    $('cn-collaboration').innerHTML=`<p class="at-caption">语义规划与解释由模型承担，数值复算与引文约束由程序承担。下方状态来自实际回执；不按时间模拟进度。</p><div class="at-agent-flow">${rows.map(r=>`<button type="button" data-agent-role="${esc(r.role)}" aria-pressed="${r.role===role}"><span>${esc(r.role)} / ${esc(VM.statusNames[r.status] || r.status)}</span><strong>${esc(r.name)}</strong><small>${r.calls.filter(c=>c.performed).length} 次已发出调用 · ${r.events.length} 条交接 / 工具记录</small></button>`).join('') || '<p class="at-empty">本次没有智能体执行记录。仅计算与没有轨迹的历史任务不会补造角色节点。</p>'}</div>
      ${current?`<section class="at-agent-detail" aria-live="polite"><h3>${esc(current.role)} · ${esc(current.name)}</h3>${current.live?.detail && current.live.status===current.status?`<p>${esc(current.live.detail)}</p>`:''}<div class="at-agent-io"><div><h4>实际输入与交接</h4>${handoffs(value,current)}</div><div><h4>实际产出与约束</h4>${current.steps.map(s=>`<p>${esc(VM.statusNames[s.status] || s.status)} · 新增关系 ${arr(s.new_check_ids).length} 项 / 更新 ${arr(s.updated_check_ids).length} 项 / 采纳研判 ${arr(s.accepted_analysis_ids).length} 项</p>${arr(s.analysis_rejections).map(r=>`<p class="at-gap">意见未采纳：${esc(r.reason)}</p>`).join('')}${s.failure_code?`<p class="at-gap">${esc(s.failure_code)}</p>`:''}`).join('') || '<p>尚无角色产出回执。</p>'}${roleJudgments(value,current)}${current.calls.filter(c=>c.failure_code || c.failure_message).map(c=>`<p class="at-gap">调用失败：${esc(c.failure_code)} ${esc(c.failure_message)}</p>`).join('')}</div></div></section>`:''}
      ${trace.length?`<details class="at-trace"><summary>查看 ${trace.length} 条实际工具、反馈与约束记录</summary><ol>${trace.map(e=>`<li><strong>${esc(e.producer_role || e.role || '程序')} · ${esc(({agent_tool_request:'申请报告检索',agent_tool_result:'工具结果交付',role_context:'角色实际上下文',role_contribution:'角色贡献',feedback_decision:'反馈 / 停止',adaptive_procedure_plan:'缺口程序规划',adaptive_procedure_effect:'程序复核结果',hypothesis_update:'解释修订'})[e.kind] || e.kind)}</strong><p>${esc(e.reason || e.note || e.stop_reason || '')}</p><small>${esc(e.check_id || '')} ${e.tool?'工具：'+esc(e.tool):''} ${arr(e.terms).length?'查询：'+esc([e.metric,...e.terms].filter(Boolean).join(' / ')):''} ${e.rejection?'未执行：'+esc(e.rejection):''} ${e.consumer_role?'交给：'+esc(e.consumer_role):''}</small></li>`).join('')}</ol></details>`:''}`;
  }
  document.addEventListener('click',event=>{
    const path=event.target.closest('[data-path]');
    if(path && model?.paths.some(p=>p.id===path.dataset.path)) { node='verdict';pick(path.dataset.path);$('at-graph-title')?.scrollIntoView({block:'start'}); }
    const hit=event.target.closest('[data-node]'); if(hit) {node=hit.dataset.node;select(selected);$('at-node-title')?.focus({preventScroll:true});}
    const evidence=event.target.closest('[data-at-evidence]'); if(evidence){pick(evidence.dataset.atEvidence);document.dispatchEvent(new CustomEvent('audittrace:connectivity-stage',{detail:{stage:4}}));}
    const result=event.target.closest('[data-at-result]'); if(result){pick(result.dataset.atResult);document.dispatchEvent(new CustomEvent('audittrace:connectivity-stage',{detail:{stage:3}}));}
    const agent=event.target.closest('[data-agent-role]'); if(agent){role=agent.dataset.agentRole;renderCollaboration(collaborationRun,collaborationTask);}
  });
  document.addEventListener('audittrace:connectivity-start',()=>{reset();});
  document.addEventListener('audittrace:connectivity-task',e=>{if(e.detail.result) renderCollaboration(e.detail.result,e.detail);else renderCollaboration(null,e.detail);});
  document.addEventListener('audittrace:connectivity-created',e=>started.add(e.detail.task_id));
  document.addEventListener('audittrace:connectivity-reset',reset);
  window.AuditTraceWorkbench={renderOverview,select,renderCollaboration,reset};
})();
