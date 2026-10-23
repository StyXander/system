/* 财务穿透图谱：只读取同一运行结果；图为投影，不新增事实或颜色语义。 */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const state = {run:null, graph:null, selected:null, detail:null, zoom:1, taskId:null, scenarioRequest:0,
    filters:{only_financial:false, show_gaps:true, show_challenged:true, full_graph:false, year:'', evidence_status:''}};
  const relationLabel = {DIRECT_RECONCILIATION:'直接证实', DISCLOSED_ALLOCATION:'披露归属',
    TEMPORAL_ASSOCIATION:'跨期关联', SEMANTIC_ASSOCIATION:'语义关联',
    HYPOTHESIZED_MECHANISM:'机制假设', CONTRADICTED:'被证据挑战', INSUFFICIENT:'依据不足'};
  const statusLabel = {pending_evidence:'待补证', limited_support:'有限支持', challenged:'被反证挑战',
    insufficient:'依据不足', observed:'已披露', plan:'计划/目标'};
  const typeLabel = {claim:'主张', performance:'绩效', financial:'财务', gap:'缺口'};
  const changeLabel = {refuted:'撤回', supported:'获支持', weakened:'降级', open:'未决', plausible:'待验证'};

  const pageUrl = (doc, page) => doc && page
    ? `/api/connectivity/sources/${encodeURIComponent(doc)}?view=true&page=${page}` : '';
  const pageLink = (doc, page, label) => state.run?.versions?.source_validity?.documents?.[doc]
    ? '<span class="cn-fin-warn">原件已变更，当前原页入口停用</span>' : pageUrl(doc, page)
    ? `<a class="cn-fin-link" href="${esc(pageUrl(doc, page))}" target="_blank" rel="noopener">${esc(label || ('p' + page))} ↗</a>`
    : '<span class="cn-fin-muted">未登记页码</span>';

  function svgEl(name, attrs = {}) {
    const node = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  }

  function wrap(text, perLine = 15, maxLines = 3) {
    const value = String(text || '').replace(/\s+/g, ' ').trim();
    const lines = [];
    for (let i = 0; i < value.length && lines.length < maxLines; i += perLine) {
      lines.push(value.slice(i, i + perLine));
    }
    if (value.length > perLine * maxLines) lines[maxLines - 1] = lines[maxLines - 1].slice(0, -1) + '…';
    return lines;
  }

  function statsHtml(stats) {
    const items = [
      ['主张', stats.claims], ['财务项目', stats.financial], ['直接证实', stats.direct],
      ['语义关联', stats.semantic], ['被挑战', stats.challenged], ['缺口', stats.insufficient],
    ];
    return `<div class="cn-fin-stats">${items.map(([label, value]) =>
      `<div class="cn-fin-stat"><strong>${Number(value || 0)}</strong><span>${esc(label)}</span></div>`).join('')}</div>`;
  }

  function legendHtml(legend) {
    return `<div class="cn-fin-legend" aria-label="关系图例">${(legend || []).map(item =>
      `<span class="cn-fin-legend-item"><i class="cn-fin-legend-line" data-kind="${esc(item.kind)}"></i>${esc(item.label)}</span>`).join('')}</div>`;
  }

  function toolbarHtml(graph) {
    const button = (key, label) => `<button type="button" data-fin-filter="${key}" aria-pressed="${state.filters[key]}">${esc(label)}</button>`;
    return `<div class="cn-fin-toolbar" role="group" aria-label="图谱过滤与缩放">
      ${button('only_financial', '只看有财务证据')}${button('show_gaps', '显示缺口')}${button('show_challenged', '显示被推翻路径')}
      ${button('full_graph', '展开完整图谱')}
      <label>年度<select data-fin-year aria-label="图谱年度"><option value="">全部年度</option>${[...new Set(graph.nodes.map(node=>node.year).filter(Boolean))].sort().map(year=>`<option value="${esc(year)}">${esc(year)}</option>`).join('')}</select></label>
      <label>证据状态<select data-fin-status aria-label="图谱证据状态"><option value="">全部状态</option>${Object.entries(graph.evidence_status_labels||{}).map(([key,label])=>`<option value="${esc(key)}">${esc(label)}</option>`).join('')}<option value="invalid">来源失效</option></select></label>
      <span class="cn-fin-zoom" role="group" aria-label="缩放">
        <button type="button" data-fin-zoom="out" aria-label="缩小">−</button>
        <button type="button" data-fin-zoom="reset" aria-label="复位">100%</button>
        <button type="button" data-fin-zoom="in" aria-label="放大">+</button>
      </span>
    </div>`;
  }

  function visibleGraph() {
    const graph = state.graph;
    if (!graph) return {nodes:[], edges:[]};
    let edges = graph.edges.filter(edge => {
      if (!state.filters.show_gaps && edge.kind === 'gap') return false;
      if (!state.filters.show_challenged && edge.kind === 'challenged') return false;
      if (state.filters.only_financial && edge.kind === 'gap') return false;
      if (!state.filters.full_graph && graph.key_path?.length && (!graph.key_path.includes(edge.source) || !graph.key_path.includes(edge.target))) return false;
      if (state.filters.evidence_status === 'invalid' && !edge.invalid) return false;
      if (state.filters.evidence_status && state.filters.evidence_status !== 'invalid' && (edge.invalid || edge.evidence_status !== state.filters.evidence_status)) return false;
      if (state.filters.year && !graph.nodes.some(node=>(node.id===edge.source||node.id===edge.target)&&String(node.year)===state.filters.year)) return false;
      return true;
    });
    const ids = new Set();
    edges.forEach(edge => { ids.add(edge.source); ids.add(edge.target); });
    const nodes = graph.nodes.filter(node => ids.has(node.id));
    return {nodes, edges};
  }

  function drawSvg() {
    const host = $('cn-graph-svg');
    if (!host) return;
    const {nodes, edges} = visibleGraph();
    host.innerHTML = '';
    if (!edges.length) {
      host.innerHTML = '<p class="cn-graph-empty">当前过滤下没有可展示的关系。关闭过滤可查看缺口或反证路径。</p>';
      return;
    }
    const nodeMap = Object.fromEntries(nodes.map(node => [node.id, node]));
    const order = {claim:0, performance:1, gap:1, financial:2};
    const columns = {0:20, 1:330, 2:640};
    const width = 900;
    const rows = {0:0, 1:0, 2:0};
    nodes.sort((a, b) => (order[a.type]??3) - (order[b.type]??3) || String(a.label).localeCompare(String(b.label), 'zh'));
    nodes.forEach(node => {
      const col = order[node.type] ?? 3;
      node._x = columns[col] ?? 20;
      node._y = 20 + (rows[col] || 0) * 96;
      node._col = col;
      rows[col] = (rows[col] || 0) + 1;
    });
    const height = Math.max(360, 40 + Math.max(...Object.values(rows), 1) * 96);
    const svg = svgEl('svg', {viewBox:`0 0 ${width} ${height}`, width:'100%', height:String(height), preserveAspectRatio:'xMinYMin meet', role:'img',
      'aria-label':'可持续主张、绩效与财务项目的证据化关系图'});
    const defs = svgEl('defs');
    defs.innerHTML = '<marker id="cn-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8a9a90"/></marker>';
    svg.appendChild(defs);
    const zoom = svgEl('g', {id:'cn-graph-zoom', transform:`scale(${state.zoom})`});
    svg.appendChild(zoom);
    const edgeLayer = svgEl('g', {class:'cn-graph-edges'});
    const nodeLayer = svgEl('g', {class:'cn-graph-nodes'});
    zoom.append(edgeLayer, nodeLayer);

    edges.forEach(edge => {
      const source = nodeMap[edge.source], target = nodeMap[edge.target];
      if (!source || !target) return;
      const x1 = source._x + 238, y1 = source._y + 34;
      const x2 = target._x, y2 = target._y + 34;
      const mid = Math.max(40, (x1 + x2) / 2);
      const path = svgEl('path', {d:`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`,
        fill:'none', stroke:edge.color || '#8a9a90', 'stroke-width':edge.kind === 'challenged' ? 2.2 : 1.5,
        'stroke-dasharray':edge.dash || '', class:`cn-graph-edge cn-edge-${edge.kind || 'semantic'}`,
        'data-edge':edge.id, 'marker-end':'url(#cn-arrow)'});
      path.appendChild(svgEl('title')).textContent = `${edge.label}：${edge.why || ''}`;
      edgeLayer.appendChild(path);
    });

    nodes.forEach(node => {
      const group = svgEl('g', {class:`cn-graph-node cn-node-${node.type}`,
        transform:`translate(${node._x},${node._y})`, 'data-node':node.id, tabindex:'0', role:'button',
        'aria-label':`${typeLabel[node.type] || node.type}：${node.label}`});
      const rect = svgEl('rect', {x:0, y:0, width:238, height:68, rx:4,
        fill:node.type === 'gap' ? '#F7F4ED' : node.type === 'financial' ? '#FFFFFF' : '#FBFCF8',
        stroke:node.type === 'gap' ? '#9A9488' : node.type === 'performance' ? '#6E8F7C' : '#2F4F43',
        'stroke-width':1, 'stroke-dasharray':node.type === 'gap' ? '4 3' : ''});
      group.appendChild(rect);
      const stripeColor = node.type === 'financial' ? '#1F6F5C' : node.type === 'gap' ? '#9A9488'
        : node.claim_kind === 'target' ? '#8A6FA8' : '#2F6F9F';
      group.appendChild(svgEl('rect', {x:0, y:0, width:4, height:68, fill:stripeColor}));
      const typeText = svgEl('text', {x:12, y:14, class:'cn-graph-type'});
      typeText.textContent = `${typeLabel[node.type] || node.type} · ${node.pdf_page || ''}`;
      group.appendChild(typeText);
      const lines = wrap(node.label, 16, 2);
      lines.forEach((line, index) => {
        const text = svgEl('text', {x:12, y:32 + index * 15, class:'cn-graph-label'});
        text.textContent = line;
        group.appendChild(text);
      });
      const sub = svgEl('text', {x:12, y:62, class:'cn-graph-sub'});
      const subLabel = String(node.sub_label || '');
      sub.textContent = subLabel.length > 15 ? subLabel.slice(0, 14) + '…' : subLabel;
      group.appendChild(sub);
      group.addEventListener('click', () => selectNode(node.id));
      group.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectNode(node.id); } });
      group.addEventListener('mouseenter', () => highlight(node.id, true));
      group.addEventListener('mouseleave', () => highlight(node.id, false));
      nodeLayer.appendChild(group);
    });
    host.appendChild(svg);
    host.setAttribute('aria-label', '可持续主张与财务项目关系图，可用表格视图查看完整关系');
  }

  function highlight(nodeId, active) {
    const host = $('cn-graph-svg');
    if (!host) return;
    host.classList.toggle('has-focus', active);
    host.querySelectorAll('.cn-graph-edge').forEach(edge => {
      const match = edge.dataset.edge && state.graph.edges.find(item => item.id === edge.dataset.edge);
      edge.classList.toggle('is-active', Boolean(active && match && (match.source === nodeId || match.target === nodeId)));
    });
    host.querySelectorAll('.cn-graph-node').forEach(node => {
      const match = state.graph.edges.find(item => item.id && (item.source === nodeId || item.target === nodeId));
      node.classList.toggle('is-related', Boolean(active && match && (match.source === node.dataset.node || match.target === node.dataset.node)));
    });
  }

  function selectNode(nodeId) {
    const node = state.graph.nodes.find(item => item.id === nodeId);
    if (!node) return;
    state.selected = nodeId;
    const related = state.graph.edges.filter(edge => edge.source === nodeId || edge.target === nodeId);
    const rows = related.map(edge => {
      const otherId = edge.source === nodeId ? edge.target : edge.source;
      const other = state.graph.nodes.find(item => item.id === otherId);
      return `<li><span class="cn-fin-rel" data-kind="${esc(edge.kind)}">${esc(relationLabel[edge.relation_type] || edge.label)}</span>
        <span>${esc(other?.label || '')}</span><small>${esc(statusLabel[edge.status] || edge.status)}</small></li>`;
    }).join('');
    const detail = $('cn-fin-detail');
    detail.innerHTML = `<button type="button" class="cn-fin-close" data-fin-close aria-label="关闭详情">关闭</button>
      <p class="cn-fin-kicker">${esc(typeLabel[node.type] || node.type)} · ${esc(node.pdf_page ? 'p' + node.pdf_page : '')}</p>
      <h4>${esc(node.label)}</h4>
      ${node.sub_label ? `<p class="cn-fin-sub">${esc(node.sub_label)}</p>` : ''}
      <p class="cn-fin-meta">${node.document_id ? pageLink(node.document_id, node.pdf_page, node.document_id + ' p' + node.pdf_page) : ''}
        ${node.status ? `<span>${esc(statusLabel[node.status] || node.status)}</span>` : ''}
        ${node.verified === false ? '<span class="cn-fin-warn">引用待复核</span>' : ''}</p>
      ${node.quote ? `<blockquote>${esc(node.quote)}</blockquote>` : ''}
      <h5>相关关系（${related.length}）</h5><ul class="cn-fin-related">${rows || '<li>没有其他关系</li>'}</ul>`;
    detail.hidden = false;
    positionDetail();
    detail.focus?.();
    detail.querySelector('[data-fin-close]')?.addEventListener('click', closeDetail);
  }

  function selectEdge(edgeId) {
    const edge = state.graph.edges.find(item => item.id === edgeId);
    if (!edge) return;
    const source = state.graph.nodes.find(item => item.id === edge.source);
    const target = state.graph.nodes.find(item => item.id === edge.target);
    const condition = (label, value) => `<div><dt>${esc(label)}</dt><dd data-value="${value === true ? 'true' : value === false ? 'false' : 'unknown'}">${value === true ? '一致' : value === false ? '冲突' : '未证明'}</dd></div>`;
    const detail = $('cn-fin-detail');
    detail.innerHTML = `<button type="button" class="cn-fin-close" data-fin-close aria-label="关闭详情">关闭</button>
      <p class="cn-fin-kicker">关系 · ${esc(relationLabel[edge.relation_type] || edge.label)}</p>
      <h4>${esc(source?.label || '')}</h4>
      <p class="cn-fin-arrow">→ ${esc(target?.label || '')}</p>
      <p class="cn-fin-meta"><span class="cn-fin-badge" data-state="${esc(edge.invalid?'insufficient':edge.status)}">${esc(edge.invalid?'来源失效':statusLabel[edge.status] || edge.status)}</span>
        <span>${esc(edge.confidence_label || '')}</span></p>
      ${edge.invalid ? `<p class="cn-fin-warn" role="status">来源失效：${esc(edge.invalid_reason)}</p>` : ''}
      <p>${esc(edge.why || '')}</p>
      <dl class="cn-fin-conditions">${condition('主体', edge.same_entity)}${condition('期间', edge.same_period)}${condition('定义', edge.definition_compatible)}${condition('范围', edge.boundary_compatible)}</dl>
      ${edge.numeric_gap !== null && edge.numeric_gap !== undefined ? `<p class="cn-fin-note">数值召回锚点差额率：${(edge.numeric_gap * 100).toFixed(2)}%。若原句含“超/约”等限定，此值仅比较抽取锚点，不是企业金额的精确差额率。数值接近不证明同一口径。</p>` : ''}
      <p class="cn-fin-meta">${pageLink(source?.document_id, source?.pdf_page, 'ESG 原页')} ${pageLink(target?.document_id, target?.pdf_page, '年报原页')}</p>
      <h5>仍缺什么</h5><ul class="cn-fin-gaps">${(edge.missing_conditions || []).map(item => `<li>${esc(item)}</li>`).join('') || '<li>无显式缺口</li>'}</ul>`;
    detail.hidden = false;
    positionDetail();
    detail.focus?.();
    detail.querySelector('[data-fin-close]')?.addEventListener('click', closeDetail);
  }

  function closeDetail() {
    const detail = $('cn-fin-detail');
    if (detail) { detail.hidden = true; detail.innerHTML = ''; }
    state.selected = null;
  }

  function positionDetail() {
    const detail=$('cn-fin-detail');
    const parent=window.innerWidth<760?$('cn-fin-mobile-detail'):document.querySelector('.cn-fin-graph-layout');
    if(detail&&parent)parent.append(detail);
  }

  function listHtml() {
    const {edges} = visibleGraph();
    return `<div class="cn-fin-list" role="list">${edges.map(edge => {
      const source = state.graph.nodes.find(item => item.id === edge.source);
      const target = state.graph.nodes.find(item => item.id === edge.target);
      return `<button type="button" class="cn-fin-list-row" data-fin-edge="${esc(edge.id)}" role="listitem">
        <span class="cn-fin-rel" data-kind="${esc(edge.kind)}">${esc(relationLabel[edge.relation_type] || edge.label)}</span>
        <span class="cn-fin-list-main"><strong>${esc(source?.label || '')}</strong><small>→ ${esc(target?.label || '')}</small></span>
        <span class="cn-fin-badge" data-state="${esc(edge.invalid?'insufficient':edge.status)}">${esc(edge.invalid?'来源失效':statusLabel[edge.status] || edge.status)}</span>
      </button>`;
    }).join('')}</div>`;
  }

  function tableHtml() {
    const rows = state.graph.edges.map(edge => {
      const source = state.graph.nodes.find(item => item.id === edge.source);
      const target = state.graph.nodes.find(item => item.id === edge.target);
      return `<tr><td>${esc(source?.label || '')}</td><td>${esc(relationLabel[edge.relation_type] || edge.label)}</td>
        <td>${esc(target?.label || '')}</td><td>${esc(edge.invalid?'来源失效（历史状态：'+(statusLabel[edge.status]||edge.status)+'）':statusLabel[edge.status] || edge.status)}</td>
        <td>${pageLink(source?.document_id, source?.pdf_page, 'p' + (source?.pdf_page || ''))}</td>
        <td>${pageLink(target?.document_id, target?.pdf_page, 'p' + (target?.pdf_page || ''))}</td></tr>`;
    }).join('');
    return `<details class="cn-fin-table-wrap"><summary>以表格查看 ${state.graph.edges.length} 条关系（屏幕阅读器可用）</summary>
      <table class="cn-fin-table"><caption>可持续主张与财务项目关系</caption><thead><tr><th>可持续主张</th><th>关系</th><th>财务项目</th><th>状态</th><th>ESG页</th><th>年报页</th></tr></thead><tbody>${rows}</tbody></table></details>`;
  }

  function scenarioHtml(scenario) {
    if (!scenario || !scenario.available) {
      return `<section class="cn-fin-block"><h4>风险传导情景模拟</h4><p class="cn-fin-note">${esc(scenario?.reason || '本次运行未生成情景模拟。')}</p></section>`;
    }
    // 兼容两种情景合同：ranges（单参数）与 baseline+scenarios（双参数）。
    const ranges = scenario.ranges || [scenario.baseline, ...(scenario.scenarios || [])].filter(Boolean);
    const max = Math.max(...ranges.map(item => Number(item.value)), 0.01);
    const bars = ranges.map(item => `<div class="cn-fin-bar-row"><span>${esc(item.name || '')}</span>
      <progress class="cn-fin-bar" max="100" value="${Math.max(2, Number(item.value) / max * 100)}"></progress>
      <b>${esc(item.value)} 亿元</b><small>${esc(item.share_of_cost || '')} 营业成本</small></div>`).join('');
    const sensitivityRows = (scenario.sensitivity || []).map(item => {
      const change = item.price_change ?? '';
      const usage = item.usage_change ?? '';
      const value = (item.two_param || {}).value ?? item.value ?? '';
      return `<tr><td>${esc(change)}</td><td>${esc(usage)}</td><td>${esc(value)} 亿元</td></tr>`;
    }).join('');
    const assumptions = (scenario.assumptions || []).map(item => {
      if (typeof item === 'string') return `<li>${esc(item)}</li>`;
      return `<li>${esc(item.name || '')}：${esc(item.value || '')} ${esc(item.unit || '')}${item.source ? `（${esc(item.source)}）` : ''}</li>`;
    }).join('');
    const parameters = scenario.parameters;
    const current = scenario.scenario_result || scenario.baseline || {};
    return `<section class="cn-fin-block" data-fin-scenario><h4>风险传导情景模拟</h4>
      <p class="cn-fin-note">${esc(scenario.note)}</p>
      <div class="cn-fin-scenario-grid">
        <div><span>${esc(scenario.resource_label||'资源量')}（原文）</span><strong>${esc(scenario.base.value)} ${esc(scenario.base.unit)}</strong><small>${pageLink(scenario.base.document_id, scenario.base.pdf_page, 'ESG p' + scenario.base.pdf_page)}</small></div>
        <div><span>营业成本（原文）</span><strong>${Number(scenario.target.value).toLocaleString('zh-CN')} ${esc(scenario.target.unit)}</strong><small>${pageLink(scenario.target.document_id, scenario.target.pdf_page, '年报 p' + scenario.target.pdf_page)}</small></div>
      </div>
      <div class="cn-fin-bars">${bars}</div>
      ${parameters ? `<fieldset class="cn-fin-scenario-controls"><legend>调整用户假设</legend>
        <label>资源单价（${esc(parameters.price.unit)}）<input type="range" data-scenario-price aria-label="资源单价" min="${esc(parameters.price.min)}" max="${esc(parameters.price.max)}" step="0.1" value="${esc(parameters.price.value)}"><output data-scenario-price-label>${esc(parameters.price.value)}</output></label>
        <label>实现比例（%）<input type="range" data-scenario-usage aria-label="实现比例" min="${esc(parameters.usage.min)}" max="${esc(parameters.usage.max)}" step="1" value="${esc(parameters.usage.value)}"><output data-scenario-usage-label>${esc(parameters.usage.value)}</output></label>
        <p>用户情景：<output data-scenario-current-value>${esc(current.value)}</output> 亿元；占披露营业成本 <output data-scenario-current-share>${esc(current.share_of_cost)}</output></p>
        <progress data-scenario-current-bar max="100" value="${Math.min(100,Number(current.value)/Math.max(...ranges.map(item=>Number(item.value)),0.01)*100)}" aria-label="当前情景影响"></progress>
        <p data-scenario-status role="status" aria-live="polite">原值保留，参数由同一后端公式复算。</p></fieldset>` : '<p>历史情景缺少参数合同，请重新运行后调整。</p>'}
      <p class="cn-fin-formula">${esc(scenario.formula)}</p>
      <details><summary>敏感性区间与假设</summary><table class="cn-fin-table"><thead><tr><th>价格变动</th><th>用量变动</th><th>情景影响</th></tr></thead><tbody>${sensitivityRows}</tbody></table>
      <ul class="cn-fin-gaps">${assumptions}</ul></details>
    </section>`;
  }

  function investigationHtml(investigation) {
    if (!investigation?.events?.length) return '<section class="cn-fin-block"><h4>自适应调查过程</h4><p>本次未运行自适应调查，未生成模型工具闭环记录。</p></section>';
    const rounds = [...new Set(investigation.events.map(event=>event.round_id))];
    const outcomes={completed:'调查执行结束',degraded_no_model:'模型未参与，按程序降级运行',blocked:'工具执行受阻'};
    const stops={no_actions:'没有剩余可执行行动',no_increment:'没有新增证据，停止重复调查',rounds_exhausted:'已达到轮数上限',tool_budget_exhausted:'已达到工具预算上限',all_actions_done:'本轮行动已结束'};
    const realCalls=(state.run?.provider_calls||[]).filter(call=>call.performed&&call.role==='challenger').length;
    return `<section class="cn-fin-block" data-investigation><h4>自适应调查过程</h4><p>结果：${esc(outcomes[investigation.outcome]||investigation.outcome)}；停止原因：${esc(stops[investigation.stop_reason]||investigation.stop_reason)}。实际工具 ${esc(investigation.summary?.tool_calls||0)} 次，Challenger尝试 ${esc(investigation.summary?.challenger_calls||0)} 次，真实模型调用 ${realCalls} 次。</p>
      <label>查看轮次<select data-investigation-round aria-label="调查轮次"><option value="">全部轮次</option>${rounds.map(round=>`<option value="${esc(round)}">${esc(round)}</option>`).join('')}</select></label>
      ${investigation.events.map(event=>`<article data-inv-round="${esc(event.round_id)}"><h5>${esc(event.round_id)} · ${esc(event.role)} · ${esc(event.outcome)}</h5><p>${esc(event.tool_name)} ${esc(event.decision_reason)}</p><p>假设：${esc((event.old_hypotheses||[]).join('；'))} → ${esc((event.new_hypotheses||[]).join('；'))}</p><small>实际调用ID：${esc(event.actual_provider_call_id||'未调用')}；tokens：${esc(event.token_cost??'未记录')}</small></article>`).join('')}
      ${(investigation.tool_receipts||[]).map(receipt=>`<details data-inv-round="${esc(receipt.round_id)}"><summary>${esc(receipt.round_id)} 原文回执 · ${esc(receipt.status)}</summary>${(receipt.result?.evidence_refs||[]).map(ref=>`<p>${pageLink(ref.document_id,ref.pdf_page,ref.document_id+' p'+ref.pdf_page)}</p><blockquote>${esc(ref.quote)}</blockquote><small>SHA256 ${esc(ref.source_sha256)}</small>`).join('')||'<p>未取得可引用的原页，不视为已解决条件。</p>'}</details>`).join('')}</section>`;
  }

  function comparisonHtml(comparison) {
    if(!comparison) return '';
    return `<section class="cn-fin-block"><h4>跨年与行业资格</h4><p>${esc(comparison.notice)}</p><p>跨年：${esc(comparison.temporal?.reason||'其他年度原件已登记；逐指标口径尚需核验。')}</p><p>同业：${esc(comparison.peer?.reason||'未取得合格样本，不生成排名。')}</p><div class="cn-fin-table-wrap"><table class="cn-fin-table"><thead><tr><th>企业</th><th>期间</th><th>行业配置</th><th>已缓存原件</th></tr></thead><tbody>${(comparison.industry_sources||[]).map(row=>`<tr><td>${esc(row.company)}</td><td>${esc(row.period)}</td><td>${esc(row.industry)}</td><td>${esc(row.cached_documents)} 份（来源覆盖）</td></tr>`).join('')}</tbody></table></div></section>`;
  }

  async function updateScenario() {
    const root = document.querySelector('[data-fin-scenario]');
    if (!root || !state.taskId) return;
    const price = root.querySelector('[data-scenario-price]')?.value;
    const usage = root.querySelector('[data-scenario-usage]')?.value;
    const status = root.querySelector('[data-scenario-status]');
    const request = ++state.scenarioRequest;
    status.textContent = '正在按同一公式复算…';
    try {
      const response = await fetch(`/api/connectivity/runs/${encodeURIComponent(state.taskId)}/scenario?`+new URLSearchParams({price,usage}),{credentials:'same-origin'});
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail==='string'?payload.detail:'参数复算失败');
      if (request !== state.scenarioRequest) return;
      const scenario = payload.scenario;
      state.run.financial_scenario = scenario;
      root.querySelector('[data-scenario-current-value]').textContent=scenario.scenario_result.value;
      root.querySelector('[data-scenario-current-share]').textContent=scenario.scenario_result.share_of_cost;
      const max = Math.max(Number(scenario.baseline.value),...(scenario.scenarios||[]).map(item=>Number(item.value)),0.01);
      root.querySelector('[data-scenario-current-bar]').value=Math.min(100,Number(scenario.scenario_result.value)/max*100);
      status.textContent=`已按单价 ${price}、实现比例 ${usage}% 复算；导出采用这组参数。`;
      document.querySelectorAll('#cn-exports a').forEach(link=>{const url=new URL(link.href);url.searchParams.set('scenario_price',price);url.searchParams.set('scenario_usage',usage);link.href=url.href;});
    } catch(error) {if(request===state.scenarioRequest) status.textContent='复算未完成：'+error.message;}
  }

  function revisionHtml(revision) {
    if (!revision || !revision.transitions?.length) {
      return `<section class="cn-fin-block"><h4>证据驱动的反证时间轴</h4><p class="cn-fin-note">本次运行没有可展示的状态变化；不以模型文字替代证据门禁。</p></section>`;
    }
    const priority = {refuted:0, supported:1, weakened:2, open:3, plausible:4};
    const transitions = [...revision.transitions].sort((a, b) =>
      (priority[a.after] ?? 5) - (priority[b.after] ?? 5)).slice(0, 12);
    const byId = Object.fromEntries((revision.hypotheses || []).map(item => [item.hypothesis_id, item]));
    const items = transitions.map(item => {
      const hypothesis = byId[item.hypothesis_id] || {};
      return `<li data-state="${esc(item.after)}"><span class="cn-fin-dot" aria-hidden="true"></span>
        <div><strong>${esc(item.hypothesis_id)}</strong> <span class="cn-fin-change">${esc(changeLabel[item.before] || item.before)} → ${esc(changeLabel[item.after] || item.after)}</span>
        <p>${esc(item.reason)}</p>
        <p class="cn-fin-meta">${pageLink(hypothesis.claim_document_id || hypothesis.document_id, hypothesis.claim_page, 'ESG p' + (hypothesis.claim_page || ''))}
          ${pageLink(hypothesis.financial_document_id, hypothesis.financial_page, '年报 p' + (hypothesis.financial_page || ''))}</p></div></li>`;
    }).join('');
    const summary = revision.summary || {};
    return `<section class="cn-fin-block"><h4>证据驱动的反证时间轴</h4>
      <p class="cn-fin-note">状态只由页码证据与条件门禁改变；撤回 ${Number(summary.refuted || 0)} 条、降级 ${Number(summary.weakened || 0)} 条、获支持 ${Number(summary.supported || 0)} 条。</p>
      <ol class="cn-fin-timeline">${items}</ol>
      <details><summary>查看全部竞争解释账本</summary><table class="cn-fin-table"><thead><tr><th>假设</th><th>类型</th><th>状态</th><th>可检验条件</th></tr></thead><tbody>
      ${(revision.hypotheses || []).map(item => `<tr><td>${esc(item.hypothesis_id)}</td><td>${esc(relationLabel[item.relation_type] || item.role || '')}</td><td>${esc(changeLabel[item.status] || item.status)}</td><td>${esc(item.testable_condition || '')}</td></tr>`).join('')}
      </tbody></table></details></section>`;
  }

  function plannerHtml(plan, run) {
    if (!plan || !plan.primary_action) {
      return `<section class="cn-fin-block"><h4>补证优先级</h4><p class="cn-fin-note">本次运行未生成可执行的补证行动。</p></section>`;
    }
    const action = plan.primary_action;
    const alternative = plan.alternative_action;
    const scores = action.score_breakdown || {};
    const scoreRows = Object.entries(scores).filter(([key]) => key !== 'total')
      .map(([key, value]) => `<div><dt>${esc({discrimination:'区分假设', gap_coverage:'覆盖缺口', specificity:'条件前置性', availability:'证据已可得', novelty:'新增信息', cost:'成本', dependency:'依赖'}[key] || key)}</dt><dd>${esc(value)}</dd></div>`).join('');
    const execution = plan.execution || {};
    const rerank = plan.rerank || {};
    const page = (action.exact_target.match(/(?:p|页)\s*(\d+)/) || [])[1];
    const doc = String(action.proposed_source || '').split(/\s+/)[0];
    const link = pageUrl(doc, page);
    return `<section class="cn-fin-block cn-fin-planner"><h4>补证优先级 <small>预算 ${esc(plan.budget?.max_actions)} 个行动 / ${esc(plan.budget?.call_budget)} 次调用</small></h4>
      <p class="cn-fin-note">${esc(plan.comparison)}</p>
      <div class="cn-fin-action-primary"><span class="cn-fin-kicker">第一优先 · 总分 ${esc(scores.total)}</span>
        <strong>${esc(action.condition)}：${esc(action.exact_target)}</strong>
        <p>${esc(action.purpose)}</p>
        <p class="cn-fin-meta">${link ? `<a class="cn-fin-link" href="${esc(link)}" target="_blank" rel="noopener">打开目标页核对 ↗</a>` : '<span class="cn-fin-muted">需人工定位</span>'}
          ${action.requires_entity ? '<span class="cn-fin-warn">需向企业索取，系统不假装已读取</span>' : ''}</p>
        <dl class="cn-fin-scores">${scoreRows}</dl></div>
      ${alternative ? `<div class="cn-fin-action-alt"><span class="cn-fin-kicker">第二优先</span><strong>${esc(alternative.condition)}：${esc(alternative.exact_target)}</strong><p>${esc(alternative.purpose)}</p></div>` : ''}
      <div class="cn-fin-exec"><h5>本次实际执行回执</h5>
        <p><span class="cn-fin-badge" data-state="${esc(execution.status || 'pending')}">${esc(execution.status === 'hit' ? '已打开并命中关键词' : execution.status === 'no_match' ? '已打开但未命中' : execution.status || '未执行')}</span>
        ${execution.page ? `年报/ESG p${esc(execution.page)}` : ''} ${esc((execution.matched_terms || []).join('、'))}</p>
        ${execution.quote ? `<blockquote>${esc(execution.quote)}</blockquote>` : ''}
        ${rerank.changed ? `<p class="cn-fin-note">重排：${esc(rerank.old_first)} → ${esc(rerank.new_first)}。${esc(rerank.reason)}</p>` : '<p class="cn-fin-note">执行回执未改变第一动作；排序保持。</p>'}
      </div>
      <details><summary>查看逐关系行动单与评分口径</summary>
        <p class="cn-fin-note">${esc(plan.algorithm)}；权重 ${esc(JSON.stringify(plan.weights))}。分数是优先级，不是正确率。</p>
        <table class="cn-fin-table"><thead><tr><th>关系</th><th>缺口</th><th>第一行动</th><th>区分假设</th><th>成本</th><th>总分</th></tr></thead><tbody>
        ${Object.entries(plan.by_edge || {}).slice(0, 14).map(([edgeId, actions]) => {
          const first = actions[0] || {};
          return `<tr><td>${esc(edgeId)}</td><td>${esc(first.condition || '')}</td><td>${esc(first.exact_target || '')}</td><td>${esc(first.expected_discrimination || 0)}</td><td>${esc(first.estimated_cost_tier || 0)}</td><td>${esc(first.score_breakdown?.total || 0)}</td></tr>`;
        }).join('')}</tbody></table></details>
    </section>`;
  }

  function render(run, context = {}) {
    state.run = run;
    state.graph = run?.impact_graph || null;
    state.taskId = context.taskId || state.taskId;
    const host = $('cn-financial-content');
    const section = $('cn-financial');
    if (!host || !section) return;
    if (!state.graph || !state.graph.nodes?.length) {
      section.hidden = false;
      host.innerHTML = `<p class="cn-fin-note">本次运行未生成财务穿透层。${run?.intelligence_trace?.some(item => item.kind === 'financial_bridge_error') ? '原因：' + esc(run.intelligence_trace.find(item => item.kind === 'financial_bridge_error').message) : '旧结果或报告对不完整时保持空值，不补造关系。'}</p>`;
      return;
    }
    section.hidden = false;
    const stats = state.graph.stats || {};
    host.innerHTML = `<div class="cn-fin-intro"><p>${esc(state.graph.industry_name || '')} · ${esc(state.graph.notice || '')}</p></div>
      ${run.versions?.source_validity?.status==='invalid'?`<p class="cn-fin-warn" role="status">${esc(run.versions.source_validity.notice)}</p>`:''}
      <div id="cn-fin-filter-stats">${statsHtml(stats)}</div>
      ${toolbarHtml(state.graph)}
      ${legendHtml(state.graph.legend)}
      <div class="cn-fin-graph-layout">
        <div class="cn-fin-graph-scroll"><div id="cn-graph-svg" class="cn-graph-svg" role="img"></div></div>
        <aside id="cn-fin-detail" class="cn-fin-detail" tabindex="-1" hidden></aside>
      </div>
      <div id="cn-fin-list-host" class="cn-fin-list-host"></div>
      <div id="cn-fin-mobile-detail"></div>
      ${tableHtml()}
      ${scenarioHtml(run.financial_scenario)}
      ${investigationHtml(run.investigation)}
      ${comparisonHtml(run.comparison_summary)}
      ${revisionHtml(run.revision_loop)}
      ${plannerHtml(run.evidence_plan, run)}`;
    bind();
    if (!state.bound) {
      document.addEventListener('keydown', event => { if (event.key === 'Escape') closeDetail(); });
      window.addEventListener('resize', () => {
        if (!state.graph) return;
        const layout = document.querySelector('.cn-fin-graph-layout');
        const list = $('cn-fin-list-host');
        positionDetail();
        if (window.innerWidth < 760) {
          if (layout) layout.hidden = true;
          if (list) list.innerHTML = listHtml();
        } else {
          if (layout) layout.hidden = false;
          if (list) list.innerHTML = '';
          drawSvg();
        }
      });
      state.bound = true;
    }
    redrawGraph();
    if (window.innerWidth < 760) {
      host.querySelector('.cn-fin-graph-layout').hidden = true;
      $('cn-fin-list-host').innerHTML = listHtml();
    } else {
      drawSvg();
    }
  }

  function redrawGraph() {
    const visible=visibleGraph();
    const stats={claims:visible.nodes.filter(n=>n.type==='claim').length,financial:visible.nodes.filter(n=>n.type==='financial').length};
    for(const [key,kind] of Object.entries({direct:'direct',semantic:'semantic',challenged:'challenged',insufficient:'gap'})) stats[key]=visible.edges.filter(edge=>edge.kind===kind).length;
    if($('cn-fin-filter-stats')) $('cn-fin-filter-stats').innerHTML=statsHtml(stats);
    if(window.innerWidth<760){$('cn-fin-list-host').innerHTML=listHtml();}else{drawSvg();}
  }

  function bind() {
    document.querySelectorAll('[data-fin-filter]').forEach(button => {
      button.addEventListener('click', () => {
        const key = button.dataset.finFilter;
        state.filters[key] = !state.filters[key];
        button.setAttribute('aria-pressed', String(state.filters[key]));
        redrawGraph();
      });
    });
    document.querySelector('[data-fin-year]')?.addEventListener('change',event=>{state.filters.year=event.target.value;redrawGraph();});
    document.querySelector('[data-fin-status]')?.addEventListener('change',event=>{state.filters.evidence_status=event.target.value;redrawGraph();});
    document.querySelector('[data-investigation-round]')?.addEventListener('change',event=>{document.querySelectorAll('[data-inv-round]').forEach(row=>row.hidden=Boolean(event.target.value)&&row.dataset.invRound!==event.target.value);});
    let scenarioTimer;
    document.querySelectorAll('[data-scenario-price],[data-scenario-usage]').forEach(input=>input.addEventListener('input',()=>{
      document.querySelector('[data-scenario-price-label]').textContent=document.querySelector('[data-scenario-price]').value;
      document.querySelector('[data-scenario-usage-label]').textContent=document.querySelector('[data-scenario-usage]').value;
      ++state.scenarioRequest;
      clearTimeout(scenarioTimer);scenarioTimer=setTimeout(updateScenario,180);
    }));
    document.querySelectorAll('[data-fin-zoom]').forEach(button => {
      button.addEventListener('click', () => {
        const action = button.dataset.finZoom;
        state.zoom = action === 'in' ? Math.min(1.6, state.zoom + 0.2)
          : action === 'out' ? Math.max(0.6, state.zoom - 0.2) : 1;
        drawSvg();
      });
    });
    $('cn-fin-list-host').onclick=event=>{const button=event.target.closest('[data-fin-edge]');if(button) selectEdge(button.dataset.finEdge);};
  }

  function reset() {++state.scenarioRequest;state.run=null;state.graph=null;state.taskId=null;state.selected=null;state.filters={only_financial:false,show_gaps:true,show_challenged:true,full_graph:false,year:'',evidence_status:''};if($('cn-financial')) $('cn-financial').hidden=true;if($('cn-financial-content')) $('cn-financial-content').replaceChildren();}
  window.CNAuditGraph = {render, selectNode, selectEdge, reset};
})();
