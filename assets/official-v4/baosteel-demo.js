/* Real-source Baosteel brief. All conclusions originate in the server's verified PDF dossier. */
(function(){
  'use strict';
  function $(id){return document.getElementById(id);}
  function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c];});}
  function html(lines){return lines.join('');}
  function origin(row){return '/api/connectivity/sources/'+encodeURIComponent(row.document_id)+'?page='+encodeURIComponent(row.pdf_page);}
  function panel(name,body){return '<section class="ba-panel"><h3>'+esc(name)+'</h3>'+body+'</section>';}
  var root=$('connectivity-root'), main=$('cn-workspace');
  if(!root || !main || !document.querySelector('.aw-nav'))return;
  var nav=document.querySelector('.aw-nav');
  nav.insertAdjacentHTML('afterbegin','<button type="button" data-at-view="demo" id="ba-nav">◈ 宝钢专项核查 <span>★</span></button>');
  var pane=document.createElement('section');
  pane.id='ba-demo';pane.className='ba-demo';pane.hidden=true;
  main.append(pane);
  var source=null, loading=false;
  function splash(){
    pane.innerHTML=html([
      '<div class="ba-header"><p class="ba-eyebrow">EVIDENCE-DRIVEN INVESTIGATION / 决赛专项案例</p>',
      '<h1>宝钢股份零碳工厂<span>从可持续披露，追到财务附注</span></h1>',
      '<p>围绕一个真实项目回答三件事：建设承诺有没有实施线索？钱进入了哪些资产？工程进度与转固时点还要核实什么？</p>',
      '<div class="ba-actions"><button type="button" id="ba-read" class="ba-primary">读取已登记官方原件，生成专项证据清单</button>',
      '<button type="button" id="ba-saved">查看当前会话其他宝钢运行记录</button>',
      '<button type="button" id="ba-new">创建新的真实五Agent任务</button></div></div>',
      '<div id="ba-message" class="ba-feedback" role="status">尚未读取原件。演示页面本身不触发模型调用，也不预置 AI 的判断。</div>',
      '<div id="ba-featured-agent"></div>',
      '<div id="ba-saved-runs"></div>',
      '<div id="ba-output"></div>'
    ]);
  }
  splash();
  function flash(s){$('ba-message').textContent=s;}
  var featuredLoaded=false,featuredLoading=false;
  function roleBadge(t){
    var labels={completed:'已完成',failed:'失败',partial:'部分完成',reused:'复用',running:'运行中',not_run:'未执行',skipped:'跳过'};
    return '<div class="ba-agent-row"><strong>'+esc(t.role)+'</strong><span>'+esc(labels[t.status]||t.status)+'</span><small>'+esc(t.failure_code||t.identity_outcome||t.stop_reason||'')+'</small></div>';
  }
  function drawFeatured(payload){
    var items=payload.items||[];
    if(!items.length){
      $('ba-featured-agent').innerHTML=panel('真实五 Agent 历史记录','<p>尚未读到通过服务端校验的历史回执。请检查保存任务的有效期，不使用预制模拟记录替代。</p>');
      return;
    }
    var rows=items.map(function(run,n){
      var total=(run.role_results||[]).filter(function(r){return r.status==='completed';}).length;
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
      var status=run.model_status==='five_agents_completed'?'真实五 Agent 完成':'真实模型已运行 · '+esc(run.model_status||run.status);
      return '<details class="ba-real-run" '+(n===0?'open':'')+'><summary><strong>'+esc(status)+'</strong><span>'+esc(run.models?.join(', ')||'模型未记录')+' · '+esc(run.actual_model_requests)+' 次真实请求 · '+total+'/5 角色完成</span><small>'+esc(run.task_id)+'</small></summary>'+
       '<p>来源：生产数据库保存的真实模型调用回执。财务结构化表格已传入模型：<strong>'+esc(run.verified_financial_table?'是':'否')+'</strong></p>'+sourceRows+
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
  function render(data){
    var f=data.reconciliation||{},isBalanced=f.status==='balanced',hasSource=(data.evidence||[]).length>0;
    var banners=[
      {name:'核查对象',value:'湛江近零碳项目',desc:'身份与子工程边界仍待核'},
      {name:'已定位原文页',value:String(data.evidence_count||0),desc:'真实官方 PDF 来源，不是风险数'},
      {name:'在建工程勾稽',value:isBalanced?'计算相符':f.status==='difference'?'需复算':f.status==='subtotal_computed'?'已知金额结余为零':'待表格核验',desc:'缺失字段不会填零'},
      {name:'五 Agent',value:'未在本页运行',desc:'从真实任务记录单独查看'}
    ];
    var metrics=banners.map(function(b){return '<div class="ba-metric"><span>'+esc(b.name)+'</span><strong>'+esc(b.value)+'</strong><small>'+esc(b.desc)+'</small></div>';}).join('');
    var cases=[
      {name:'01 · 资产变动金额勾稽',state:isBalanced?'有据计算':'待核原始单元格',hint:'使用 Decimal、完整原表字段及单位核验；金额平衡不代表转固正确。'},
      {name:'02 · 工程进度与转固日期',state:'核查问题',hint:'不同工程范围的“部分完工”与“投入运行”不能直接判为错报。'},
      {name:'03 · 项目整体与子工程口径',state:'关联未确认',hint:'建设项目总体投资、炼钢工程预算与年报资本性支出不得直接等价。'}
    ];
    var findings=cases.map(function(k){return '<article class="ba-finding"><div><strong>'+esc(k.name)+'</strong><span>'+esc(k.state)+'</span></div><p>'+esc(k.hint)+'</p></article>';}).join('');
    var docs=(data.coverage||[]).map(function(c){return '<span>'+esc(c.document_id)+' · '+esc(c.total_pages)+' 页 · 解析限制 '+esc((c.failed_pages||[]).length)+' 页</span>';}).join('');
    $('ba-output').innerHTML=html([
      '<div class="ba-metrics">',metrics,'</div>',
      panel('本次具体核查发现',findings),
      panel('财务穿透 · 年报在建工程',financial(data)),
      panel('跨报告证据链', '<div class="ba-chain"><span>项目披露</span><b>›</b><span>建设进展</span><b>›</b><span>在建工程</span><b>›</b><span>转固及折旧条件</span></div><p>这是一条待核机制路径，不代表每个节点已被证实。项目整体与炼钢子项目映射：<strong>'+esc(data.project_mapping==='annual_explicit_subproject'?'年报附注直接列明子项目':'仍待原文确认')+'</strong>。</p>'),
      panel('原文回查 · 已核验 PDF', evidence(data)),
      panel('建议审计人员取得的资料',investigations(data)),
      panel('真实五 Agent 与版本', '<p>专项只读页不调用模型，因此本页没有 A1–A5 执行回执。历史五 Agent 结果须在实际任务页面查看，失败或降级不得隐藏。</p><p>'+esc(data.mapping_note)+'</p>'),
      '<div class="ba-footer">','调查价值：',esc(data.investigation_value||'C'),' · ',
      esc((data.ranking_reasons||[]).join('；')),' · ',esc(data.case_scope),'</div>',
      '<p class="ba-muted">',esc(data.source_warnings?.join('；')||''),'</p>',
      '<p class="ba-muted">报告覆盖：',docs,'</p>'
    ]);
    flash('资料索引已返回：'+esc(data.evidence_count)+' 处不同 PDF 页面证据；模型未调用。');
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
    }catch(e){flash('专项读取未成功：'+e.message+'。可查看先前真实任务，不会显示伪造结论。');}
    finally{loading=false;$('ba-read').disabled=false;}
  }
  function demoOpen(){
    pane.hidden=false;
    document.body.dataset.route='workspace';
    if($('redesign-home'))$('redesign-home').hidden=true;
    root.hidden=false;
    if(source)render(source);
    loadFeatured();
    main.scrollIntoView({block:'start'});
  }
  document.addEventListener('click',function(e){
    var b=e.target.closest('button');if(!b)return;
    if(b.id==='ba-read'){load();return;}
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
    if(b.dataset.atView||b.dataset.atStage||b.dataset.openTask||b.dataset.view||b.dataset.cmSelect) pane.hidden=true;
  });
  document.addEventListener('audittrace:connectivity-task',function(){pane.hidden=true;});
  if(new URL(location.href).searchParams.get('demo')==='baosteel'){
    document.querySelector('#ba-nav')?.click();
  }
})();
