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
      '<button type="button" id="ba-saved">打开本浏览器已有宝钢运行记录</button>',
      '<button type="button" id="ba-new">创建新的真实五Agent任务</button></div></div>',
      '<div id="ba-message" class="ba-feedback" role="status">尚未读取原件。演示页面本身不触发模型调用，也不预置 AI 的判断。</div>',
      '<div id="ba-output"></div>'
    ]);
  }
  splash();
  function flash(s){$('ba-message').textContent=s;}
  function investigations(data){
    var body = (data.audit_procedures||[]).map(function(p){
      return '<li><strong>'+esc(p.question)+'</strong><p>建议取得：'+esc(p.material)+'</p><p>核查目的：'+esc(p.purpose)+'</p></li>';
    }).join('');
    return '<ol class="ba-procedures">'+body+'</ol>';
  }
  function financial(data){
    var f=data.reconciliation||{},value=f.values_yuan||{};
    var valid=f.status==='balanced'||f.status==='difference';
    var state=valid?(f.status==='balanced'?'金额勾稽成立':'金额勾稽出现差额'):'原件结构化单行核验尚未完成';
    var lines=valid?[
      ['期初余额',value.opening],['本期增加',value.increase],['转入固定资产',value.to_fixed],
      ['转入长期待摊费用',value.to_long_term],['其他减少',value.other_decrease],
      ['披露期末余额',value.closing]
    ]:[];
    var rows=lines.map(function(a){return '<div><span>'+esc(a[0])+'</span><strong>'+esc(a[1])+'</strong></div>';}).join('');
    return html([
      '<div class="ba-calculation"><strong>'+esc(state)+'</strong>',
      '<p>'+esc(f.note||'未取得可复算的原始表格单元格。')+'</p>',
      valid?'<p class="ba-math">期初 + 增加 − 转固 − 长期待摊 − 其他减少 = 期末</p><div class="ba-numbers">'+rows+'</div>':'',
      valid?'<p>差额：'+esc(f.difference_yuan||f.difference)+' 元。该数值不等于可持续项目全部投资。</p>':'',
      f.source_page?'<a target="_blank" rel="noopener" href="'+esc(origin({document_id:f.document_id,pdf_page:f.source_page}))+'">打开已核验年报 PDF '+esc(f.source_page)+' 页原文</a>':'',
      '<small>规则：'+esc(f.rule_version||'construction_reconciliation_v1')+' · 不自动把破折号当成零</small></div>'
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
      {name:'在建工程勾稽',value:isBalanced?'计算相符':f.status==='difference'?'需复算':'待表格核验',desc:'缺失字段不会填零'},
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
      panel('跨报告证据链', '<div class="ba-chain"><span>项目披露</span><b>›</b><span>建设进展</span><b>›</b><span>在建工程</span><b>›</b><span>转固及折旧条件</span></div><p>这是一条待核机制路径，不代表每个节点已被证实。项目整体与炼钢子项目映射：<strong>尚未确认</strong>。</p>'),
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
    main.scrollIntoView({block:'start'});
  }
  document.addEventListener('click',function(e){
    var b=e.target.closest('button');if(!b)return;
    if(b.id==='ba-read'){load();return;}
    if(b.id==='ba-saved'){
      var row=lastSaved();
      if(row){pane.hidden=true;document.dispatchEvent(new CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:row.id}}));}
      else flash('本浏览器没有宝钢已保存任务。请从左侧历史记录查看服务端列表；不自动拼造运行结果。');
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
