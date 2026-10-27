/* 企业发现与报告接入独立于结果搜索；选择下一企业不改写当前核验结果。 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {ready:'已验证可运行', paired:'资料已配对、待处理', partial:'部分资料可用', identity_only:'仅发现企业'};
  const state = {cards:[], candidates:[], company:null, found:null, canImport:false, generation:0, timer:null};
  async function request(url, options={}) {
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),90000);
    try{
      const response = await fetch(url, {credentials:'same-origin', headers:{'Content-Type':'application/json'}, signal:controller.signal, ...options});
      let data;
      try{data=await response.json();}catch{throw new Error('服务未返回有效数据，请稍后重试。');}
      if (!response.ok) throw new Error(typeof data.detail==='string'?data.detail:data.detail?.message||'来源服务暂不可用，请稍后重试。');
      return data;
    }catch(error){if(error.name==='AbortError')throw new Error('查询超时。已登记案例和已有结果仍保留，可稍后重试。');throw error;}
    finally{clearTimeout(timer);}
  }
  const status = text => { $('cn-company-status').textContent = text; };
  function drawCards() {
    const industry=$('cn-company-industry').value, year=$('cn-company-year-filter').value, ready=$('cn-company-state').value;
    const rows=state.cards.filter(r=>(!industry||r.industry===industry)&&(!year||r.period===year)&&(!ready||r.state===ready)).sort((a,b)=>({ready:0,paired:1,partial:2}[a.state]-{ready:0,paired:1,partial:2}[b.state]));
    $('cn-company-cards').innerHTML=rows.map(r=>`<button type="button" class="cn-company-card" data-select-pair="${esc(r.pair_id)}"><strong>${esc(r.company)} <small>${esc(r.company_id)}</small></strong><span>${esc(r.period)} · 业务线索：${esc(r.industry)} · ${esc(labels[r.state])}</span><small>${r.state==='ready'?'选择双报告':'按登记版本恢复原件后核验'} · 模型状态另见本次任务</small></button>`).join('')||'<p>当前筛选条件下没有登记报告对。</p>';
  }
  async function refresh() {
    const data=await request('/api/connectivity/catalog');
    state.cards=data.items;state.canImport=data.can_import;
    const preserve=$('cn-company-industry').value;
    $('cn-company-industry').innerHTML='<option value="">全部行业</option>'+[...new Set(data.items.map(r=>r.industry))].map(v=>`<option>${esc(v)}</option>`).join('');
    $('cn-company-industry').value=preserve;
    $('cn-company-year-filter').innerHTML='<option value="">全部年度</option>'+[...new Set(data.items.map(r=>r.period))].sort().reverse().map(v=>`<option>${esc(v)}</option>`).join('');
    drawCards();
    status(`已读取 ${data.items.length} 组登记报告，可选择企业或搜索。`);
    $('cn-company-storage').textContent=data.persistence==='snapshot_only_remote_unavailable'?'远端目录暂不可用，当前使用已核实的离线目录；新报告接入暂不可用。':'已登记双报告优先展示；身份搜索不会启动下载或模型。';
  }
  async function auth() {
    const result=await request('/api/auth/me');
    $('cn-company-login').hidden=!result.authentication_required;
    $('cn-company-auth-status').textContent=result.authenticated?'已登录；报告接入仍按组织角色授权。':'使用现有组织账号。身份搜索和程序核验无需付费模型权限。';
  }
  $('cn-company-login-form').addEventListener('submit',async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;
    try{
      await request('/api/auth/login',{method:'POST',body:JSON.stringify({email:$('cn-company-email').value,password:$('cn-company-password').value})});
      $('cn-company-password').value='';await auth();await refresh();status('已登录，可按组织权限准备报告或运行核验。');
    }catch(error){$('cn-company-auth-status').textContent=error.message;}
    finally{button.disabled=false;}
  });
  $('cn-company-logout').addEventListener('click',async()=>{
    try{await request('/api/auth/logout',{method:'POST'});await auth();await refresh();status('已退出登录。当前核验结果仍保留。');}
    catch(error){$('cn-company-auth-status').textContent=error.message;}
  });
  async function search() {
    const query=$('cn-company-query').value.trim(), generation=++state.generation;
    if (!query) { $('cn-company-results').innerHTML='';status('输入企业名称、简称、代码或目录支持的拼音。');return; }
    status('正在查询官方企业身份…');
    try {
      const data=await request('/api/companies/search?q='+encodeURIComponent(query));
      if(generation!==state.generation)return;
      state.candidates=data.candidates;
      $('cn-company-results').innerHTML=data.candidates.map((r,i)=>`<button type="button" data-confirm-company="${i}"><strong>${esc(r.company_alias||r.company_name)} · ${esc(r.ticker)}</strong><span>${esc(labels[r.state])} · ${r.report_pairs.length?'已有 '+r.report_pairs.length+' 组报告对':'尚未核对报告'} · 点击确认身份</span></button>`).join('');
      status(data.candidates.length?`找到 ${data.match_count} 个身份候选，请确认企业。身份命中不代表可以分析。`:'未找到匹配企业。请检查名称、六位代码或缩短关键词。');
    }catch(error){if(generation===state.generation)status(error.message+' 已登记案例仍可使用；可修改关键词或重新搜索。');}
  }
  function choose(index) {
    state.generation++;
    state.company=state.candidates[index];state.found=null;
    const company=state.company;
    $('cn-company-confirmed').hidden=false;
    $('cn-company-name').textContent=`已确认：${company.company_alias||company.company_name} · ${company.ticker}`;
    $('cn-company-reports').innerHTML='';
    $('cn-company-existing').innerHTML=company.report_pairs.map(r=>`<button type="button" data-select-pair="${esc(r.pair_id)}">选择 ${esc(r.period)} 双报告 · ${esc(labels[r.state])}</button>`).join('');
    $('cn-company-confirmed').scrollIntoView({block:'nearest',behavior:'instant'});
    status('企业身份已确认。选择年度后查询双报告；当前结果仍保留。');
  }
  async function reports() {
    if(!state.company)return;
    const company=state.company, year=$('cn-company-report-year').value;
    const generation=++state.generation;
    $('cn-company-find-reports').disabled=true;status('正在查询同公司、同年度的官方年报与可持续披露…');
    try {
      const found=await request(`/api/companies/${company.ticker}/report-pair?year=${year}`);
      if(generation!==state.generation)return;
      state.found=found;
      const options=(items)=>items.map(r=>`<option value="${esc(r.source_url)}">${esc(r.announcement_title)} · ${esc(r.announcement_date)}</option>`).join('');
      $('cn-company-reports').innerHTML=`<p><strong>${esc(labels[found.state])}</strong> · ${esc(found.boundary)}</p><div class="cn-company-report-options"><label>年度报告<select id="cn-company-ar" ${found.annual?'':'disabled'}>${options(found.annual_candidates)||'<option>缺少合格年度报告</option>'}</select></label><label>可持续发展 / ESG 报告<select id="cn-company-esg" ${found.sustainability?'':'disabled'}>${options(found.sustainability_candidates)||'<option>缺少合格可持续披露报告</option>'}</select></label></div><p>${found.missing.length?'缺少：'+esc(found.missing.join('、')):'下一步核对 PDF 正文、版本、主体、期间和每一页解析。'}</p><button id="cn-company-import" type="button" ${found.state==='paired'&&state.canImport?'':'disabled'}>下载校验并登记双报告</button>${!state.canImport?'<p>新原件接入需要登录后的接入权限；当前可查询元数据、选择已验证案例。请使用已授权的工作台会话。</p>':''}`;
      status(found.query_complete?'官方公告查询完成；尚未运行核验或模型。':'官方查询未完整结束，暂不能接入。请稍后重试。');
    }catch(error){if(generation===state.generation)status(error.message+' 可以重试，当前已保存的核验结果不受影响。');}
    finally{$('cn-company-find-reports').disabled=false;}
  }
  async function watchImport(taskId) {
    const deadline=Date.now()+15*60*1000;
    while(Date.now()<deadline){
      const task=await request('/api/connectivity/catalog/imports/'+encodeURIComponent(taskId));
      if(task.status==='completed'){
        localStorage.removeItem('audittrace-company-import');await refresh();
        await select(task.result.pair_id);status('双报告已经校验并持久登记。请选择运行方式，点击“开始关联核对”。');return;
      }
      if(['failed','cancelled'].includes(task.status)){localStorage.removeItem('audittrace-company-import');throw new Error(task.error?.message||task.error||'报告准备失败，请检查官方来源后重试。');}
      const stages=task.stages||[];
      const latest=Array.isArray(stages)?stages.at(-1):Object.values(stages).at(-1);
      status(task.result?.import_progress?.detail||latest?.message||latest?.detail||'后台正在下载、校验并逐页解析报告；尚未调用模型。');
      await new Promise(resolve=>setTimeout(resolve,1500));
    }
    status('报告准备仍在后台运行。刷新后可继续查看此任务，不重复下载。');
  }
  async function importPair() {
    const button=$('cn-company-import');button.disabled=true;
    try{
      const task=await request('/api/connectivity/catalog/imports',{method:'POST',body:JSON.stringify({ticker:state.company.ticker,year:Number($('cn-company-report-year').value),confirmed_identity:true,annual_url:$('cn-company-ar').value,sustainability_url:$('cn-company-esg').value})});
      localStorage.setItem('audittrace-company-import',task.task_id);await watchImport(task.task_id);
    }catch(error){status(error.message);button.disabled=false;}
  }
  async function select(pairId) {
    document.dispatchEvent(new CustomEvent('audittrace:select-pair',{detail:{pairId}}));
    status('已选择下一组双报告；下方已有任务结果保持原企业身份，点击开始后才创建新任务。');
  }
  $('cn-company-search').addEventListener('submit',event=>{event.preventDefault();clearTimeout(state.timer);search();});
  $('cn-company-query').addEventListener('input',()=>{clearTimeout(state.timer);state.timer=setTimeout(search,600);});
  ['cn-company-industry','cn-company-year-filter','cn-company-state'].forEach(id=>$(id).addEventListener('change',drawCards));
  $('cn-company-find-reports').addEventListener('click',reports);
  $('cn-company-selector').addEventListener('click',event=>{
    const confirm=event.target.closest('[data-confirm-company]');if(confirm){choose(Number(confirm.dataset.confirmCompany));return;}
    const pair=event.target.closest('[data-select-pair]');if(pair){select(pair.dataset.selectPair);return;}
    if(event.target.closest('#cn-company-import'))importPair();
  });
  $('cn-company-report-year').innerHTML=Array.from({length:5},(_,i)=>new Date().getFullYear()-1-i).map(y=>`<option>${y}</option>`).join('');
  refresh().then(()=>{const pending=localStorage.getItem('audittrace-company-import');if(pending&&state.canImport)watchImport(pending).catch(error=>status(error.message));}).catch(error=>status(error.message));
  auth().catch(error=>{$('cn-company-auth-status').textContent=error.message;});
})();
