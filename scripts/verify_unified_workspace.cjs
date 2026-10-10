const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const out=path.resolve(process.env.AUDITTRACE_OUTPUT||'outputs/企业工作台_2026-10-10');fs.mkdirSync(out,{recursive:true});
const base=process.env.AUDITTRACE_URL||'http://127.0.0.1:8030';
const active=new Set(['queued','running','resolving_company','searching','downloading','validating','registering','rag_building','indexing','extracting_fields','analyzing','ready_for_analysis']);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.setDefaultTimeout(60000);const errors=[],posts=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.method()==='POST')posts.push({url:r.url(),body:r.postData()});});
 const evidence={base,started_at:new Date().toISOString(),checks:[],posts};
 function check(name,value){assert(value,name);evidence.checks.push(name);console.log('PASS',name);}
 const save=()=>fs.writeFileSync(path.join(out,'本轮真实验收.json'),JSON.stringify(evidence,null,2));
 try{
  await page.goto(base,{waitUntil:'domcontentloaded'});await page.locator('#demo-enter-workspace').click();
  await page.waitForFunction(()=>document.querySelectorAll('#demo-featured-cases button').length===3);
  await page.locator('#demo-featured-cases button').filter({hasText:'中国海油'}).click();
  await page.locator('#demo-live-company').fill('000333');await page.locator('#demo-company-search').click();
  await page.locator('#demo-company-candidates button').first().click();
  check('中国海油切换美的：统一标题与启动按钮', (await page.locator('#demo-current-case-name').textContent())==='美的集团'&&(await page.locator('#demo-start').textContent()).includes('美的集团'));
  if(process.env.AUDITTRACE_REAL_RUN==='1'){
   // 只延迟真实创建响应，服务端照常运行；用此窗口检验重复点击与浏览限制。
   await page.route('**/api/pipelines/cninfo',async route=>{
    const response=await route.fetch();const task=await response.json();
    evidence.task_id=task.task_id;evidence.created_task=task;save();
    console.log('CREATED',task.task_id);await sleep(7000);await route.fulfill({response});
   });
   await page.locator('#demo-start').click();
   check('提交后启动按钮立即禁用',await page.locator('#demo-start').isDisabled());
   await page.locator('#demo-open-all-cases').click();
   check('案例库15＋8且运行期间企业不可切换',await page.locator('#demo-cases-drawer [data-demo-case]').count()===15&&await page.locator('#demo-expanded-cases button').count()===8&&await page.locator('#demo-cases-drawer [data-demo-case]').first().isDisabled());
   await page.locator('#demo-cases-drawer [data-demo-close]').click();
   await page.locator('#demo-live-company').fill('000858');await page.locator('#demo-company-search').click();
   await page.locator('#demo-company-candidates button').first().waitFor();
   check('运行时可搜索但候选不可切换',await page.locator('#demo-company-candidates button').first().isDisabled());
   check('浏览搜索后当前对象仍是美的',(await page.locator('#demo-current-case-name').textContent())==='美的集团');
   for(let i=0;i<180;i++){
    if(evidence.task_id){const response=await page.request.get(base+'/api/pipelines/'+evidence.task_id);if(response.ok()){
     const task=await response.json();evidence.latest_task=task;save();
     if(!active.has(task.status)){console.log('TERMINAL',task.status);break;}
     if(i%6===0)console.log('WAIT',task.status,Object.entries(task.steps||{}).filter(([name,s])=>s.status==='running').map(([name])=>name));
    }}await sleep(5000);
   }
   check('真实任务在限定时间结束',evidence.latest_task&&!active.has(evidence.latest_task.status));
  }else{
   evidence.task_id=process.env.AUDITTRACE_TASK_ID||'CNINFO-E88A17CF009B';
   await page.evaluate(taskId=>sessionStorage.setItem('audittrace_workspace_session_v2',JSON.stringify({origin:'live',task_id:taskId,selection:{origin:'live',ticker:'000333',company_name:'美的集团'}})),evidence.task_id);
  }
  await page.reload();await page.locator('#demo-result').waitFor({state:'visible',timeout:90000});
  check('刷新结果身份仍是美的',(await page.locator('#demo-current-case-name').textContent())==='美的集团'&&(await page.locator('#demo-result').textContent()).includes('美的集团'));
  evidence.state=await page.locator('#demo-result-state').textContent();evidence.gate=await page.locator('#demo-gate').textContent();
  for(const [width,height,padding] of [[1440,1000,28],[1024,768,24],[768,1024,24],[390,844,16]]){
   await page.setViewportSize({width,height});await page.locator('.demo-inline-evidence > summary').first().evaluate(e=>e.parentElement.open=true);
   check(`${width}白框内边距${padding}px`,await page.locator('.demo-analysis-main').evaluate((e,p)=>getComputedStyle(e).paddingLeft===p+'px',padding));
   check(`${width}四个原表链接`,await page.locator('.demo-growth-evidence a').count()===4);
   check(`${width}页面没有水平溢出`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(width===390)check('手机基础金额完整一行显示',await page.locator('.demo-growth-evidence td p').first().evaluate(e=>e.getBoundingClientRect().height<35));
   await page.locator('#demo-result').screenshot({path:path.join(out,`结果-${width}.png`)});
   await page.locator('#demo-result').scrollIntoViewIfNeeded();
   await page.screenshot({path:path.join(out,`阅读视窗-${width}.png`)});
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.emulateMedia({media:'print'});check('打印没有水平溢出',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.pdf({path:path.join(out,'结果打印.pdf'),format:'A4',printBackground:true});await page.emulateMedia({media:'screen'});
  const downloadPromise=page.waitForEvent('download');await page.locator('#demo-download-json').click();
  const download=await downloadPromise;await download.saveAs(path.join(out,'结果下载.json'));
  const exported=JSON.parse(fs.readFileSync(path.join(out,'结果下载.json'),'utf8'));
  check('下载JSON与当前美的身份一致',exported.run?.context?.ticker==='000333'&&exported.run?.context?.company_name==='美的集团'&&exported.run_id===exported.run.run_id);
  const before=posts.length;
  let failOnce=true;await page.route('**/api/pipelines/'+evidence.task_id,async route=>{if(failOnce){failOnce=false;await route.fulfill({status:503,body:'temporarily unavailable'});}else await route.continue();});
  await page.reload();await page.locator('#demo-read-result').waitFor({state:'visible'});await page.locator('#demo-read-result').click();await page.locator('#demo-result').waitFor({state:'visible'});
  check('503重读与刷新不创建任务',posts.length===before);
  await page.unroute('**/api/pipelines/'+evidence.task_id);
  await page.evaluate(taskId=>{sessionStorage.removeItem('audittrace_workspace_session_v2');sessionStorage.setItem('audittrace_demo_task_v1',JSON.stringify({task_id:'DEMO-RUN-1EA92A6EC1B9',case_id:'STD_DEV_T0'}));sessionStorage.setItem('audittrace_live_task_v1',JSON.stringify({task_id:taskId}));},evidence.task_id);
  await page.reload();await page.locator('#demo-result').waitFor({state:'visible'});
  check('双旧记录按真实创建时间恢复较新的美的',(await page.locator('#demo-current-case-name').textContent())==='美的集团'&&posts.length===before);
  const actual=await (await page.request.get(base+'/api/pipelines/'+evidence.task_id)).json();
  evidence.latest_task=actual;
  for(const fixture of ['缺字段','零分母']){
   const task=JSON.parse(JSON.stringify(actual)),analysis=task.result.analysis;
   if(fixture==='缺字段') analysis.evidence_bundle.field_evidence=analysis.evidence_bundle.field_evidence.filter(row=>row.field_id!=='revenue_previous');
   else analysis.evidence_bundle.field_evidence.find(row=>row.field_id==='revenue_previous').value=0;
   const rule=analysis.rule_results.find(row=>row.rule_id==='R1');rule.metrics.revenue_growth=null;rule.metrics.growth_gap=null;
   await page.route('**/api/pipelines/'+evidence.task_id,route=>route.fulfill({json:task}));
   await page.reload();await page.locator('#demo-result').waitFor({state:'visible'});
   check(`合同样例：${fixture}不编造增长率`,(await page.locator('.demo-inline-evidence').textContent()).includes('营业收入增长率：本次不可复算'));
   await page.unroute('**/api/pipelines/'+evidence.task_id);
  }
  await page.reload();await page.locator('#demo-result').waitFor({state:'visible'});
  let delayedResolve;const delayed=new Promise(r=>delayedResolve=r);
  await page.route('**/api/companies/search?q=000333',async route=>{const response=await route.fetch();delayedResolve();await sleep(3000);await route.fulfill({response});});
  await page.locator('#demo-live-company').fill('000333');await page.locator('#demo-company-search').click();await delayed;
  await page.locator('#demo-featured-cases button').filter({hasText:'中国海油'}).click();await sleep(3500);
  check('旧查询晚到不能覆盖新企业或显示旧候选',(await page.locator('#demo-current-case-name').textContent())==='中国海油'&&await page.locator('#demo-company-candidates button').count()===0);
  await page.unroute('**/api/companies/search?q=000333');
  await page.evaluate(taskId=>sessionStorage.setItem('audittrace_workspace_session_v2',JSON.stringify({origin:'live',task_id:taskId,selection:{origin:'live',ticker:'000333',company_name:'美的集团'}})),evidence.task_id);
  await page.reload();await page.locator('#demo-result').waitFor({state:'visible'});
  await page.locator('.demo-console .demo-analysis-settings > summary').click();await page.locator('#demo-live-latest-year').fill('2024');
  check('改变条件收起旧结果并更新请求年度',await page.locator('#demo-result').isHidden()&&(await page.locator('#demo-current-case-meta').textContent()).includes('请求年度 2024'));
  if(process.env.AUDITTRACE_REAL_RUN==='1')check('只有一次美的创建、没有中国海油任务',posts.filter(p=>p.url.endsWith('/api/pipelines/cninfo')).length===1&&JSON.parse(posts.find(p=>p.url.endsWith('/api/pipelines/cninfo')).body).company_query==='000333');
  else check('读取回归没有创建分析任务',posts.length===0);
  check('页面无运行时错误',errors.length===0);
 }catch(e){evidence.error=e.stack;console.error(e.stack);process.exitCode=1;await page.screenshot({path:path.join(out,'验收失败.png'),fullPage:true}).catch(()=>{});}
 finally{evidence.errors=errors;evidence.finished_at=new Date().toISOString();save();await browser.close();}
})();
