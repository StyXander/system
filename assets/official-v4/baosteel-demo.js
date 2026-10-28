/* Real-source Baosteel brief. All conclusions originate in the server's verified PDF dossier. */
(function(){
  'use strict';
  function $(id){return document.getElementById(id);}
  function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c];});}
  function html(lines){return lines.join('');}
  function origin(row){return '/api/connectivity/sources/'+encodeURIComponent(row.document_id)+'?page='+encodeURIComponent(row.pdf_page);}
  function panel(name,body,theme){return '<section class="ba-panel" data-ba-theme="'+esc(theme||'history')+'"><h3>'+esc(name)+'</h3>'+body+'</section>';}
  var root=$('connectivity-root'), main=$('cn-workspace');
  if(!root || !main || !document.querySelector('.aw-nav'))return;
  var nav=document.querySelector('.aw-nav');
  nav.insertAdjacentHTML('afterbegin','<button type="button" data-at-view="demo" id="ba-nav">◈ 宝钢专项核查 <span>★</span></button>');
  var pane=document.createElement('section');
  pane.id='ba-demo';pane.className='ba-demo';pane.hidden=true;
  main.append(pane);
  var source=null, loading=false, featured=null;
  function splash(){
    pane.innerHTML=html([
      '<header class="ba-top"><div><p class="ba-eyebrow">AUDITTRACE / 宝钢专项核查</p><h1>宝钢专项核查 <span>证据驾驶舱</span></h1><p class="ba-save-state" id="ba-save-state">正在读取已保存真实结果…</p></div>',
      '<div class="ba-toolbar"><button type="button" id="ba-evidence" class="ba-primary">查看原文证据</button><button type="button" id="ba-process">查看调查过程</button>',
      '<details class="ba-more"><summary aria-label="更多操作">···</summary><div><button type="button" id="ba-read">刷新原件索引</button><button type="button" id="ba-saved">其他历史记录</button><button type="button" id="ba-new">新建核验任务</button></div></details>',
      '<div class="ba-export-bar" role="group" aria-label="导出宝钢专项核查报告">',
      '<a href="/api/connectivity/demo/baosteel/export/docx" download>Word</a><a href="/api/connectivity/demo/baosteel/export/json" download>JSON</a><a href="/api/connectivity/demo/baosteel/export/pdf" download>下载 PDF</a><a href="/api/connectivity/demo/baosteel/export/csv" download>CSV</a></div></div></header>',
      '<section class="ba-brief"><figure><img src="/assets/official-v4/baosteel-factory.jpg" alt="宝钢股份湛江钢铁近零碳产线实景" width="640" height="360"><figcaption><a href="https://finance.sina.com.cn/jjxw/2025-12-23/doc-inhcuyuh0613938.shtml" target="_blank" rel="noopener noreferrer">宝钢股份供图 · 上观新闻</a></figcaption></figure><div class="ba-brief-copy"><h2>宝钢股份 · 湛江近零碳工厂</h2><strong>从可持续披露，追到财务附注</strong><p>围绕一个真实项目：建设承诺有无实施线索？钱进入哪些资产？工程范围与转固时点还要核实什么？</p></div><div class="ba-brief-stat"><small>核查对象</small><strong>湛江近零碳项目</strong><span>身份与子工程边界仍待核</span></div><div class="ba-brief-stat"><small>已定位原文页</small><b id="ba-evidence-count">—</b><span>真实官方 PDF 来源<br>不是风险数</span></div></section>',
      '<div id="ba-message" class="ba-feedback" role="status">正在读取官方证据索引；当前刷新不会调用模型。</div><div id="ba-output" aria-busy="true"><div class="ba-loading">正在载入证据关系图、资金图与披露时间线…</div></div>',
      '<details id="ba-process-detail" class="ba-secondary"><summary>五 Agent 调查过程与历史回执 <span>复用 / 当前调用 / 历史调用分别保留</span></summary><div id="ba-featured-agent"></div></details><div id="ba-saved-runs"></div>'
    ]);
  }
  splash();
  function flash(s){$('ba-message').textContent=s;}
  var featuredLoaded=false,featuredLoading=false;
  function roleBadge(t){
    var labels={completed:'已完成',failed:'失败',partial:'部分完成',reused:'复用',running:'运行中',not_run:'未执行',skipped:'跳过'};
    return '<div class="ba-agent-row"><strong>'+esc(t.role)+'</strong><span>'+esc(t.identity_outcome==='candidate_retained_identity_unconfirmed'?(labels[t.status]||t.status)+' · 来源已核验 / 归并待证':labels[t.status]||t.status)+'</span><small>'+esc(t.stop_reason||t.failure_code||'')+'</small></div>';
  }
  function drawFeatured(payload){
    var items=payload.items||[];
    featured=items[0]||null;updateReceipt();
    if(!items.length){
      $('ba-save-state').textContent='已保存回执暂不可读 · 当前查看不调用模型';
      if($('ba-receipt'))$('ba-receipt').textContent='历史回执当前不可用；请通过更多操作重试刷新。';
      $('ba-featured-agent').innerHTML=panel('真实五 Agent 历史记录','<p>尚未读到通过服务端校验的历史回执。请检查保存任务的有效期，不使用预制模拟记录替代。</p>');
      return;
    }
    var rows=items.map(function(run,n){
      var total=(run.role_results||[]).filter(function(r){return r.status==='completed'||r.status==='reused';}).length;
      var claims=(run.next_actions||[]).map(function(a){
        return '<li><strong>'+esc(a.question)+'</strong><p>'+esc(a.requested_material)+'</p></li>';
      }).join('');
      var realPaths=(run.path_examples||[]).map(function(p){
        var steps=(p.steps||[]).map(function(step){
          return '<li>'+esc(step.label)+'<p>'+esc(step.explanation||'')+'</p><small>证据等级：'+esc(step.support||'未判定')+' · 来源类型：'+esc(step.origin||'未知')+'</small></li>';
        }).join('');
        return '<details class="ba-evidence"><summary><strong>'+esc(p.financial_item)+'</strong> · '+esc(p.support||'待核')+'</summary><ol class="ba-procedures">'+steps+'</ol></details>';
      }).join('');
      var realCounter=(run.counter_explanations||[]).map(function(e){
        return '<li><strong>'+esc(e.explanation)+'</strong><p>需要的判别证据：'+esc(e.required_evidence||'未提出')+'</p><small>状态：'+esc(e.status||'待核')+'</small></li>';
      }).join('');
      var table=run.verified_table_detail||null;
      var cells=table?.values_yuan||{};
      var sourceRows=table?'<div class="ba-calculation"><h4>独立核验的原表金额（不是模型编造）</h4>'+
        '<p>年报 PDF '+esc(table.source_page)+' 页 · 单位：元</p>'+
        '<div class="ba-numbers">'+[['期初余额',cells.opening],['本期增加',cells.increase],['本期转固',cells.to_fixed]]
          .map(function(c){return '<div><span>'+esc(c[0])+'</span><strong>'+esc(c[1]||'尚未取得')+'</strong></div>';}).join('')+'</div>'+
        '<p>上述三项试算结余：'+esc(table.known_component_subtotal_yuan||'未计算')+' 元。'
        +esc(table.note||'其他金额与口径待核')+'</p></div>':'';
      var status=run.investigation_status==='completed'?'五 Agent 调查流程完成 · 资料缺口另列':'真实模型已运行 · 调查尚未完整完成';
      var usage=run.usage||{};
      function tokens(n){return typeof n==='number'?n.toLocaleString():'未记录';}
      var priorLine=run.prior_actual_model_requests?'<p>本次为同一调查的定向续查，复用已完成角色；前次真实请求 '+esc(run.prior_actual_model_requests)+' 次，回执保留在来源链中。</p>':'';
      var usageLine=priorLine+'<p>累计取证工具（已包含来源运行，不重复相加）：<strong>'+esc(run.actual_tool_requests??'未记录')+'</strong> 次；本次输入 '+esc(tokens(usage.input_tokens))+' tokens，输出 '+esc(tokens(usage.output_tokens))+' tokens。缓存命中输入 '+esc(tokens(usage.cache_hit_input_tokens))+' tokens；缓存未命中不代表检索失败。</p>';
      return '<details class="ba-real-run" '+''+'><summary><strong>'+esc(status)+'</strong><span>'+esc(run.models?.join(', ')||'模型未记录')+' · '+esc(run.actual_model_requests)+' 次当前真实请求 · '+total+'/5 角色完成调查</span><small>'+esc(run.task_id)+'</small></summary>'+
       '<p>来源：生产数据库保存的真实模型调用回执。财务结构化表格已传入模型：<strong>'+esc(run.verified_financial_table?'是':'否')+'</strong></p>'+sourceRows+usageLine+
       '<div class="ba-agent-list">'+(run.role_results||[]).map(roleBadge).join('')+'</div>'+
       '<h4>A2 · 真实财务穿透路径</h4>'+(realPaths||'<p>本次未登记可用路径。</p>')+
       '<h4>A4 · 竞争解释与反证</h4><ol class="ba-procedures">'+(realCounter||'<li>本次未登记可用反证解释。</li>')+'</ol>'+
       '<h4>模型实际综合意见</h4><p>'+esc(run.assessment_summary||'没有有效综合意见')+'</p>'+
       '<h4>财务关联阶段</h4><p>'+esc(run.financial_stage||'未形成可用财务阶段')+'</p>'+
       '<h4>实际产生的后续核查任务</h4><ol class="ba-procedures">'+(claims||'<li>无有效建议</li>')+'</ol>'+
       '<p class="ba-muted">模型路径：'+esc(run.financial_paths)+' 条；项目级金额记录：'+esc(run.financial_occurrences)+' 条。此处展示的是历史运行，不是专项试算冒充的AI结果。</p></details>';
    }).join('');
    $('ba-featured-agent').innerHTML=panel('真实 DeepSeek 五 Agent 历史运行记录 · 可直接展开',rows);
  }
  async function loadFeatured(){
    if(featuredLoading)return;
    featuredLoading=true;
    try{
      var res=await fetch('/api/connectivity/demo/baosteel/featured-runs',{credentials:'same-origin'});
      if(!res.ok)throw new Error('已保存的真实模型回执读取失败');
      var d=await res.json();
      drawFeatured(d);featuredLoaded=true;
    }catch(e){
      $('ba-save-state').textContent='已保存结果暂不可读 · 可重试刷新';
      $('ba-featured-agent').innerHTML=panel('真实 Agent 历史读取异常','<p>'+esc(e.message)+'。不使用模拟替代。</p>');
    }finally{featuredLoading=false;}
  }
  function investigations(data){
    var body = (data.audit_procedures||[]).map(function(p){
      return '<li><strong>'+esc(p.question)+'</strong><p>建议取得：'+esc(p.material)+'</p><p>核查目的：'+esc(p.purpose)+'</p></li>';
    }).join('');
    return '<ol class="ba-procedures">'+body+'</ol>';
  }
  function financial(data){
    var f=data.reconciliation||{},value=f.values_yuan||{};
    var complete=f.status==='balanced'||f.status==='difference';
    var partial=f.status==='subtotal_computed';
    var shown=complete||partial;
    var state=complete?(f.status==='balanced'?'完整金额勾稽成立':'明确金额出现差额'):
      partial?'已复算三项真实金额 · 期末破折号待核':'原始财务表格核验尚未完成';
    var lines=shown?[
      ['期初余额',value.opening],['本期增加',value.increase],['转入固定资产',value.to_fixed],
      ['转入长期待摊费用',value.to_long_term],['披露期末余额',value.closing]
    ]:[];
    var rows=lines.map(function(a){return '<div><span>'+esc(a[0])+'</span><strong>'+esc(a[1]==null?'—（未确认为零）':a[1])+'</strong></div>';}).join('');
    return html([
      '<div class="ba-calculation"><strong>'+esc(state)+'</strong>',
      '<p>'+esc(f.note||'未取得可复算的原始表格单元格。')+'</p>',
      shown?'<p class="ba-math">已知金额试算：期初 + 本期增加 − 本期转固 = '+esc(f.known_component_subtotal_yuan||'请见数值')+' 元</p><div class="ba-numbers">'+rows+'</div>':'',
      complete?'<p>正式表内差额：'+esc(f.difference_yuan||'0')+' 元。只说明该行算术关系，不证明转固时点恰当。</p>':'',
      partial?'<p>关键边界：披露期末金额及部分减少项为破折号，不能据此声称完整金额勾稽已经确认。</p>':'',
      f.source_page?'<p><a target="_blank" rel="noopener" href="'+esc(origin({document_id:f.document_id,pdf_page:f.source_page}))+'">打开已核验年报 PDF '+esc(f.source_page)+' 页原文 ↗</a></p>':'',
      '<small>规则：'+esc(f.rule_version||'construction_reconciliation_v1')+' · 来源表格单位 '+esc(f.unit||'尚未确认')+' · 不自动把破折号当成零</small></div>'
    ]);
  }
  function evidence(data){
    var rows=(data.evidence||[]).slice(0,12).map(function(r){
      return html(['<article class="ba-evidence"><div class="ba-evidence-meta"><span>',
        esc(r.report_type==='AR'?'年度报告':'可持续发展报告'),' · PDF ',esc(r.pdf_page),' · ',esc(r.report_period),
        '</span><a href="',esc(origin(r)),'" target="_blank" rel="noopener">打开原文 ↗</a></div>',
        '<p>',esc(r.quote),'</p><small>SHA256 来源校验 · ',esc(r.source_sha256?.slice(0,16)),'…</small></article>']);
    }).join('');
    return '<div class="ba-evidence-list">'+rows+'</div>';
  }
  function lastSaved(){
    try{
      var rows=JSON.parse(localStorage.getItem('audittrace-connectivity-history-v2')||'[]');
      return rows.find(function(r){return /宝钢/.test(r.company||'') && /^(CONNJOB|DEMO-RUN)-[A-Z0-9]{8,40}$/.test(r.id);});
    }catch(_){return null;}
  }
  function sourceLink(row,label,cls){
    return row?'<a class="'+esc(cls||'')+'" href="'+esc(origin(row))+'" target="_blank" rel="noopener">'+label+'</a>':'<span class="ba-unavailable">来源尚未定位</span>';
  }
  function updateReceipt(){
    if(!featured){if(featuredLoaded&&$('ba-receipt'))$('ba-receipt').textContent='历史回执当前不可用；请通过更多操作重试刷新。';return;}
    var date=featured.saved_at||featured.created_at;
    var saved=date?new Date(date).toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'}):'保存日期未记录';
    var current=featured.actual_model_requests,prior=featured.prior_actual_model_requests;
    var complete=featured.investigation_status==='completed';
    $('ba-save-state').textContent='已保存真实结果 · '+saved+' · 当前查看不调用模型';
    var footer=$('ba-receipt');if(footer)footer.innerHTML='<strong>'+esc(complete?'五 Agent 调查流程已完成':'已保存调查 · 部分完成')+'</strong><span>专业事实与资料缺口另列</span><span>累计模型请求：<b>'+esc(current+prior)+'</b> 次（当前 '+esc(current)+' / 历史 '+esc(prior)+'）</span><span>累计工具调用：<b>'+esc(featured.actual_tool_requests)+'</b> 次（已含来源运行）</span><span>保存日期：'+esc(saved)+'</span>';
  }
  function dashboard(data){
    var f=data.reconciliation||{},v=f.values_yuan||{};
    var rows=[['opening','期初余额'],['increase','本期增加'],['to_fixed','本期转固']];
    function amount(k){var raw=v[k];return raw!==null&&raw!==undefined&&raw!==''&&Number.isFinite(Number(raw))?Number(raw)/1e8:null;}
    function shown(k){var n=amount(k);return n===null?'待核':n.toFixed(2);}
    var ev=data.evidence||[];
    function find(doc,page){return ev.find(function(r){return r.document_id===doc&&r.pdf_page===page&&r.source_verified;});}
    var ar=find('BAOSTEEL_AR_2025',26),esg=find('BAOSTEEL_ESG_2025',32),table=f.source_row_matched?{document_id:f.document_id,pdf_page:f.source_page}:null;
    var timeline=data.disclosure_timeline||[];
    var whole=timeline.find(function(t){return t.kind==='project_operation';}),line=timeline.find(function(t){return t.kind==='line_connection';});
    function svgNode(x,y,w,h,title,lines,row,tone){
      var text='<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="5" class="ba-node '+(tone||'')+'"/><text x="'+(x+13)+'" y="'+(y+25)+'" class="ba-node-title">'+esc(title)+'</text>';
      lines.forEach(function(l,i){text+='<text x="'+(x+13)+'" y="'+(y+46+i*20)+'" class="ba-node-copy">'+esc(l)+'</text>';});
      return row?'<a href="'+esc(origin(row))+'" target="_blank" rel="noopener" aria-label="'+esc(title+'，打开 PDF 第 '+row.pdf_page+' 页')+'"><title>打开已核验原文 PDF 第 '+esc(row.pdf_page)+' 页</title>'+text+'</a>':'<g>'+text+'</g>';
    }
    var graph='<svg class="ba-graph" viewBox="0 0 660 420" role="group" aria-label="官方报告到项目事实及财务落点的证据关系图">'+
      '<defs><marker id="ba-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#21866b"/></marker><marker id="ba-pending" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#d58a21"/></marker></defs>'+
      '<g class="ba-col-label"><text x="12" y="24">官方报告来源</text><text x="240" y="24">项目与工程节点</text><text x="492" y="24">财务落点 / 亿元</text></g>'+
      '<g class="ba-solid"><path d="M174 99H238"/><path d="M174 214H238"/><path d="M174 329H238"/>'+
      (table?'<path d="M415 329H445V92H488"/><path d="M415 329H458V205H488"/><path d="M415 329H488"/>':'')+'</g>'+
      '<g class="ba-dashed"><path d="M325 147V166"/><path d="M325 262V286"/><path d="M325 373V395H488"/></g>'+
      '<g class="ba-edge-label"><text x="190" y="88">披露</text><text x="190" y="203">披露</text><text x="190" y="318">披露</text><text x="335" y="158">范围待核</text><text x="335" y="280">范围待核</text><text x="342" y="388">起点待核</text></g>'+
      svgNode(10,55,164,92,'宝钢股份年报',['2025 年度报告','PDF 第 26 页'],ar)+
      svgNode(10,170,164,92,'宝钢股份 ESG 报告',['2025 ESG 报告','PDF 第 32 页'],esg)+
      svgNode(10,285,164,88,'宝钢股份年报',['在建工程明细','PDF 第 '+esc(f.source_page||'—')+' 页'],table,'ba-blue')+
      svgNode(240,55,175,92,'整体项目建成投产',[whole?whole.date_label:'日期待原文核验','湛江近零碳项目'],whole||ar)+
      svgNode(240,170,175,92,'近零碳产线贯通',[line?line.date_label:'日期待原文核验','氢基竖炉及电炉'],line||esg)+
      svgNode(240,285,175,88,'炼钢子工程',['年报明确列示子工程','跨报告范围仍待核'],table,'ba-blue')+
      svgNode(490,55,158,85,'在建工程本期增加',[shown('increase'),'已核验原表金额'],table)+
      svgNode(490,168,158,85,'本期转入固定资产',[shown('to_fixed'),'具体月份未知'],table)+
      svgNode(490,285,158,88,'期初余额',[shown('opening'),'仅为炼钢子工程'],table)+
      '<text x="492" y="401" class="ba-pending-text">折旧起点：未取得证据</text></svg>';
    var mobileGraph='<div class="ba-mobile-graph">'+[[ar,'年报 PDF 26 页','整体项目建成投产',whole?whole.date_label:'日期待核'],[esg,'ESG PDF 32 页','近零碳产线贯通',line?line.date_label:'日期待核'],[table,'年报 PDF '+(f.source_page||'—')+' 页','炼钢子工程','在建工程明细']].map(function(r){return '<div class="ba-mobile-relation">'+sourceLink(r[0],esc(r[1]))+'<span>已核验披露</span><strong>'+esc(r[2])+'<small>'+esc(r[3])+'</small></strong></div>';}).join('')+'<p class="ba-mobile-pending">跨报告范围待核：整体项目 / 近零碳产线 / 炼钢子工程</p><div class="ba-mobile-amounts">'+rows.map(function(r){return sourceLink(table,esc(r[1])+'<b>'+shown(r[0])+' 亿元</b>');}).join('')+'</div><p class="ba-mobile-pending">转固与折旧起点之间：证据缺失，不能确认</p></div>';
    var nums=rows.map(function(r){return amount(r[0]);}).filter(function(n){return n!==null;});
    var max=nums.length?Math.max.apply(null,nums):0,step=max>0?Math.pow(10,Math.floor(Math.log10(max)))/2:1;
    var top=max>0?Math.ceil(max*1.2/step)*step:1;
    var chart='<svg class="ba-chart" viewBox="0 0 440 330" role="group" aria-label="炼钢子工程资金变化，单位亿元；点击柱形查看原文，原值列于图下">';
    for(var i=0;i<=5;i++){var y=275-i*48;chart+='<line x1="43" y1="'+y+'" x2="427" y2="'+y+'" class="ba-gridline"/><text x="29" y="'+(y+5)+'" text-anchor="end" class="ba-axis">'+esc((top*i/5).toFixed(top<1?2:0))+'</text>';}
    rows.forEach(function(r,i){var n=amount(r[0]),h=n===null?0:n/top*240,x=68+i*125;var shape='<text x="'+(x+38)+'" y="'+(264-h)+'" text-anchor="middle" class="ba-bar-value">'+shown(r[0])+'</text>'+(n===null?'':'<rect x="'+x+'" y="'+(275-h)+'" width="76" height="'+h+'" class="ba-bar ba-bar-'+i+'"/>')+'<text x="'+(x+38)+'" y="300" text-anchor="middle" class="ba-axis ba-axis-label">'+r[1]+'</text>';
      chart+=table?'<a href="'+esc(origin(table))+'" target="_blank" rel="noopener" aria-label="'+r[1]+' '+esc(v[r[0]])+' 元，打开来源"><title>'+r[1]+'：'+esc(v[r[0]]??'未取得')+' 元；年报 PDF '+esc(f.source_page)+' 页</title>'+shape+'</a>':shape;
    });chart+='</svg>';
    var raw=rows.map(function(r){return '<span>'+r[1]+' <b>'+esc(v[r[0]]??'未取得')+'</b> 元</span>';}).join('');
    var timelineHTML=timeline.map(function(t){return '<li><strong>'+esc(t.date_label)+'</strong><p>'+esc(t.label)+'</p>'+sourceLink(t,'PDF 第 '+esc(t.pdf_page)+' 页')+(t.note?'<small>'+esc(t.note)+'</small>':'')+'</li>';}).join('');
    return '<div class="ba-dashboard"><section class="ba-viz ba-relationships"><div class="ba-viz-head"><div><h2>证据关系图谱</h2><p>已定位投产与转固证据，范围及折旧起点待核。</p></div><div class="ba-legend"><span>实线：已核验披露关系</span><span>虚线：范围 / 因果待核</span></div></div>'+graph+mobileGraph+'<div class="ba-graph-note">年报直接列明子工程及金额（实线）；整体项目、产线与子工程的跨报告范围仍待核（虚线）。</div></section>'+
      '<section class="ba-viz ba-funds"><div class="ba-viz-head"><h2>炼钢子工程资金变化</h2><span>单位：亿元</span></div>'+chart+'<div class="ba-chart-notes"><div>'+sourceLink(table,'来源：宝钢股份 2025 年报<br>PDF 第 '+esc(f.source_page||'—')+' 页')+'<details><summary>查看原始金额（元）</summary><div class="ba-raw-values">'+raw+'</div></details></div><div class="ba-warning"><strong>期末破折号未确认为零</strong><p>三项已知金额试算结余 '+esc(f.known_component_subtotal_yuan??'未取得')+' 元，不等于完整勾稽已通过。部分列仍为破折号。</p></div></div><p class="ba-scope">子工程金额不等同于整个工厂投资额或 ESG 汇总投入。</p></section></div>'+
      '<section class="ba-viz ba-timeline"><div class="ba-timeline-title"><h2>关键披露时间线</h2><span>基于官方原文；具体月份以原文为准</span></div>'+(timelineHTML?'<ol>'+timelineHTML+'</ol>':'<p>日期尚未取得原文核验；不推定开工、验收、转固或折旧日期。</p>')+'</section><div class="ba-receipt" id="ba-receipt">已保存调查回执读取中；当前查看不会调用模型。</div>';
  }
  function render(data){
    $('ba-evidence-count').textContent=data.evidence_count??'—';
    $('ba-output').setAttribute('aria-busy','false');
    $('ba-output').innerHTML=dashboard(data)+
      '<section class="ba-findings"><h2>核心发现与证据缺口</h2><div><article><strong>已核验 · 项目披露与金额</strong><p>整体投产、产线贯通有原文线索；炼钢子工程三项金额已按原表核验。</p></article><article><strong>待核 · 范围与确认时点</strong><p>跨报告统计范围、破折号含义、转固类别及折旧起点尚缺证据。流程完成不等于所有专业事实已证实。</p></article></div></section>'+
      '<details id="ba-source-detail" class="ba-secondary"><summary>原文证据与来源索引 <span>'+esc(data.evidence_count)+' 处原文页</span></summary>'+evidence(data)+'</details>'+
      '<details class="ba-secondary"><summary>核查程序与原表复算 <span>按需展开</span></summary>'+financial(data)+investigations(data)+'<p class="ba-muted">'+esc(data.mapping_note)+' '+esc(data.source_warnings?.join('；'))+'</p></details>';
    updateReceipt();flash('已读取 '+data.evidence_count+' 处官方 PDF 页面证据；当前刷新页面不会调用模型。');
  }
  async function load(){
    if(loading)return;
    loading=true;$('ba-read').disabled=true;
    flash('正在按 SHA256 校验已登记原件并检索项目证据；不会触发模型调用。');
    try{
      var res=await fetch('/api/connectivity/demo/baosteel',{credentials:'same-origin'});
      var data=await res.json();
      if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'服务端原件核验失败');
      source=data;render(data);
    }catch(e){flash('专项读取未成功：'+e.message+'。可通过更多操作重试。');if(!source){$('ba-output').setAttribute('aria-busy','false');$('ba-output').innerHTML='<div class="ba-loading">官方证据暂不可读。请在更多操作中刷新原件索引；未使用替代结论。</div>';}}
    finally{loading=false;$('ba-read').disabled=false;}
  }
  function demoOpen(){
    pane.hidden=false;root.dataset.awView='demo';$('ba-nav').setAttribute('aria-current','page');
    document.body.dataset.route='workspace';
    if($('redesign-home'))$('redesign-home').hidden=true;
    root.hidden=false;
    if(source)render(source);
    loadFeatured();
    main.scrollIntoView({block:'start'});
  }
  document.addEventListener('click',function(e){
    var b=e.target.closest('button');if(!b)return;
    if(b.id==='ba-read'){load();loadFeatured();return;}
    if(b.id==='ba-evidence'||b.id==='ba-process'){var target=$(b.id==='ba-evidence'?'ba-source-detail':'ba-process-detail');if(target){target.open=true;target.scrollIntoView({block:'start',behavior:'smooth'});target.querySelector('summary').focus({preventScroll:true});}return;}
    if(b.id==='ba-saved'){
      b.disabled=true;flash('正在按本浏览器的授权会话查询服务端保存的宝钢任务…');
      fetch('/api/connectivity/demo/baosteel/runs',{credentials:'same-origin'})
        .then(function(response){if(!response.ok)throw new Error('服务端历史暂不可用');return response.json();})
        .then(function(payload){
          var items=payload.items||[];
          if(!items.length){
            var row=lastSaved();
            if(row){pane.hidden=true;document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:row.id}}));}
            else flash('当前会话没有可读取的宝钢历史记录。请运行一次真实任务并保留任务编号。');
            return;
          }
          var rows=items.map(function(item){
            var label=item.model_mode==='five_agents'?'真实五 Agent 调查':item.model_mode==='calculation_only'?'确定性初筛':'其他已保存任务';
            var status=({completed:'已完成',degraded:'部分完成',running:'进行中',failed:'失败',interrupted:'已中断'})[item.status]||item.status;
            return '<li><button data-open-task="'+esc(item.task_id)+'" type="button"><strong>'+esc(label)+'</strong> · '+esc(status)+' · '+esc(item.task_id)+'</button></li>';
          }).join('');
          $('ba-saved-runs').innerHTML='<section class="ba-panel"><h3>服务端已保存的真实运行记录</h3><p>只显示当前会话可查看的真实任务；前序初筛与五 Agent 的完成状态不合并造假。</p><ul class="ba-saved-list">'+rows+'</ul></section>';
          flash('已读取 '+items.length+' 条真实任务台账。请打开一次已经完成或部分完成的运行结果。');
        })
        .catch(function(e){flash(e.message+'；不会以预置假数据替代。');})
        .finally(function(){b.disabled=false;});
      return;
    }
    if(b.id==='ba-new'){
      pane.hidden=true;
      document.querySelector('[data-at-view="workflow"]')?.click();
      var pair=$('cn-pair');if(pair && [...pair.options].some(function(o){return o.value==='600019-2025';})){pair.value='600019-2025';pair.dispatchEvent(new Event('change',{bubbles:true}));}
      return;
    }
    if(b.dataset.atView==='demo'){demoOpen();if(!source)load();return;}
    if(b.dataset.atView||b.dataset.atStage||b.dataset.openTask||b.dataset.view||b.dataset.cmSelect){pane.hidden=true;$('ba-nav').removeAttribute('aria-current');}
  });
  document.addEventListener('audittrace:connectivity-task',function(){pane.hidden=true;});
  if(new URL(location.href).searchParams.get('demo')==='baosteel'){
    document.querySelector('#ba-nav')?.click();
  }
})();
