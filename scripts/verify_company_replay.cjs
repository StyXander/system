/* 本脚本不发付费请求；恢复已获准的真实任务，检查搜索、切换、原页及导出。 */
const fs=require('fs'),path=require('path'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=path.join(root,'outputs','enterprise-expansion'),base='http://127.0.0.1:8893';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 const original=JSON.parse(fs.readFileSync(path.join(out,'real-model-task.json'))),receipt={task_id:original.task_id,errors:[],search:[],viewports:[]};
 const browser=await chromium.launch({headless:true,channel:'msedge'}),context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',reducedMotion:'reduce'});
 await context.route('**/*',route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.hostname!=='127.0.0.1')return route.abort();
  if(url.pathname==='/api/connectivity/runs'&&request.method()==='POST'&&JSON.parse(request.postData()).mode!=='calculation_only')throw Error('禁止重复付费运行');
  return route.continue();
 });
 const page=await context.newPage();page.on('pageerror',error=>receipt.errors.push(error.message));
 await page.goto(base+'/?connectivity_task='+original.task_id,{waitUntil:'networkidle'});
 await page.locator('#cn-results').waitFor({state:'visible'});
 const body=await page.locator('#cn-results').innerText(),taskLink=page.url();
 await page.locator('.at-stages [data-at-stage="1"]').click();
 await page.locator('[data-select-pair="600019-2025"]').click();
 await page.waitForFunction(()=>document.querySelector('#cn-pair').value==='600019-2025');
 await page.locator('.at-stages [data-at-stage="3"]').click();
 receipt.switch_preserves_result=await page.locator('#cn-results').isVisible()&&(await page.locator('#cn-results').innerText())===body&&page.url()===taskLink;
 if(!receipt.switch_preserves_result)throw Error('企业切换丢失已完成结果');
 receipt.actual_model_status=original.result.model_status;
 receipt.actual_calls=original.result.provider_calls.filter(c=>c.performed).length;
 receipt.complete_three_agents=original.result.model_status==='three_agents_completed';
 receipt.input_tokens=original.result.provider_calls.reduce((s,c)=>s+(c.input_tokens||0),0);
 receipt.output_tokens=original.result.provider_calls.reduce((s,c)=>s+(c.output_tokens||0),0);
 receipt.final_ai_opinions=original.result.ai_opinions.length;
 for(const query of ['隆基绿能','601012','隆基绿能科技股份有限公司','ljln','福耀玻璃','中国中','这是不存在的合成企业ZZQ']){
   const response=await context.request.get(base+'/api/companies/search?q='+encodeURIComponent(query));
   const data=await response.json();if(response.status()!==200)throw Error(query+': '+JSON.stringify(data));
   receipt.search.push({query,status:response.status(),match_count:data.match_count,requires_confirmation:data.requires_confirmation,
    identities:data.candidates.map(r=>({ticker:r.ticker,name:r.company_alias,state:r.state}))});
   if(['隆基绿能','601012','隆基绿能科技股份有限公司','ljln'].includes(query)&&!data.candidates.some(c=>c.ticker==='601012'))throw Error('registered search '+query);
   if(query==='福耀玻璃'&&!data.candidates.some(c=>c.ticker==='600660'&&c.state==='identity_only'))throw Error('unregistered business state');
   if(query==='中国中'&&data.match_count<2)throw Error('fuzzy confirmation missing');
   if(query.includes('不存在')&&data.match_count!==0)throw Error('nonexistent company falsely ready');
 }
 const partial=await context.request.get(base+'/api/companies/601088/report-pair?year=2025'),partialData=await partial.json();
 receipt.partial_report={status:partial.status(),state:partialData.state,missing:partialData.missing};
 if(partial.status()!==200||partialData.state!=='partial'||!partialData.missing.length)throw Error('partial report state');
 const invalidYear=await context.request.get(base+'/api/companies/601012/report-pair?year=2099');
 receipt.future_year_status=invalidYear.status();if(invalidYear.status()!==422)throw Error('future period');
 for(const format of ['json','csv','docx']){
  const response=await context.request.get(base+`/api/connectivity/runs/${original.task_id}/export/${format}`);
  if(response.status()!==200)throw Error('export '+format);
  fs.writeFileSync(path.join(out,'隆基绿能_最终复验.'+format),await response.body());
 }
 const own=new Set(original.result.documents.map(d=>d.document_id));
 receipt.cross_company_isolated=original.result.occurrences.every(o=>own.has(o.document_id))&&original.result.documents.every(d=>d.company_id==='601012');
 if(!receipt.cross_company_isolated)throw Error('cross-company leakage');
 const source=await context.request.get(base+'/api/connectivity/sources/'+encodeURIComponent(original.result.documents[0].document_id)+'?view=true&page=125');
 receipt.source_status=source.status();if(source.status()!==200)throw Error('PDF source');
 await page.locator('.at-stages [data-at-stage="3"]').click();
 await page.screenshot({path:path.join(out,'04-真实模型结果与降级.png')});
 for(const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844]]){
  await page.setViewportSize({width,height});
  await page.locator('.at-stages [data-at-stage="1"]').click();await pause(200);
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);
  if(overflow)throw Error('search overflow '+width);
  const file='企业搜索最终_'+width+'x'+height+'.png';await page.screenshot({path:path.join(out,file)});
  receipt.viewports.push({width,height,overflow,file});
 }
 // 只计算模式再跑另一新增企业，验证浏览器实际选择进入同一流水线。
 const ili=await page.locator('[data-select-pair^="CONNPAIR-600887-2025-"]').getAttribute('data-select-pair');
 await page.locator(`[data-select-pair="${ili}"]`).click();
 await page.waitForFunction(pair=>document.querySelector('#cn-pair').value===pair,ili);
 await page.locator('#cn-mode').selectOption('calculation_only');
 const creation=page.waitForResponse(r=>r.url().endsWith('/api/connectivity/runs')&&r.request().method()==='POST');
 await page.locator('#cn-run').click();let task=await(await creation).json();
 const deadline=Date.now()+300000;
 while(['queued','running'].includes(task.status)&&Date.now()<deadline){await pause(2000);task=await(await context.request.get(base+'/api/connectivity/runs/'+task.task_id)).json();}
 if(!task.result||task.result.documents.some(d=>d.company_id!=='600887')||task.result.provider_calls.some(c=>c.performed))throw Error('new company calculation pipeline');
 fs.writeFileSync(path.join(out,'ili-browser-task.json'),JSON.stringify(task,null,2));
 receipt.new_company_browser_calculation={task_id:task.task_id,status:task.status,company:task.result.company,provider_calls:0,checks:task.result.checks.length};
 fs.writeFileSync(path.join(out,'browser-company-final.json'),JSON.stringify(receipt,null,2));
 await browser.close();console.log(JSON.stringify(receipt));if(receipt.errors.length)process.exitCode=1;
})().catch(error=>{console.error(error);fs.writeFileSync(path.join(out,'browser-replay-error.txt'),error.stack);process.exitCode=1;});
