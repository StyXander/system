/* 公网实际浏览器验收：只读搜索；仅在新增企业就绪时允许一次程序核验。 */
const fs=require('fs'),path=require('path'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=path.join(root,'outputs/enterprise-expansion');
const base='https://audittrace-demo.onrender.com',pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const receipt={checked_at:new Date().toISOString(),target:base,errors:[],model_requests_sent:0,new_entry:false};
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
 await context.route('**/*',route=>{
  const request=route.request();
  if(request.method()==='POST'){
   const url=new URL(request.url());let data={};try{data=JSON.parse(request.postData());}catch{}
   if(url.origin!==base||url.pathname!=='/api/connectivity/runs'||data.mode!=='calculation_only')return route.abort();
  }
  return route.continue();
 });
 const page=await context.newPage();page.on('pageerror',e=>receipt.errors.push(e.message));
 await page.goto(base,{waitUntil:'networkidle',timeout:90000});
 const health=await context.request.get(base+'/api/health');receipt.health=await health.json();
 receipt.new_entry=await page.locator('#cn-company-query').count()>0;
 if(receipt.new_entry){
  await page.locator('[data-enter-connectivity]').first().click();
  await page.locator('.at-stages [data-at-stage="1"]').click();
  await page.locator('#cn-company-query').fill('601012');
  await page.locator('#cn-company-search button').click();
  await page.locator('[data-confirm-company]').first().waitFor({timeout:90000});
  receipt.search=await page.locator('#cn-company-results').innerText();
  await page.locator('[data-confirm-company]').first().click();
  receipt.confirmed=await page.locator('#cn-company-name').innerText();
  await page.locator('#cn-company-report-year').selectOption('2025');
  await page.locator('#cn-company-find-reports').click();
  await page.waitForFunction(()=>!document.querySelector('#cn-company-find-reports').disabled,null,{timeout:90000});
  receipt.report_query=await page.locator('#cn-company-reports').innerText();
  receipt.query_status=await page.locator('#cn-company-status').innerText();
  const response=await context.request.get(base+'/api/connectivity/catalog');const catalog=await response.json();
  receipt.catalog={status:response.status(),pairs:catalog.items?.length,ready:catalog.items?.filter(r=>r.state==='ready').length,persistence:catalog.persistence};
  const ready=catalog.items?.find(r=>r.company_id==='600887'&&r.state==='ready');
  if(ready||process.env.AUDITTRACE_REPLAY_TASK){
   let task;
   if(process.env.AUDITTRACE_REPLAY_TASK){
    task=await(await context.request.get(base+'/api/connectivity/runs/'+process.env.AUDITTRACE_REPLAY_TASK)).json();
    receipt.resumed_existing_task=true;
   }else{
   await page.locator(`[data-select-pair="${ready.pair_id}"]`).first().click();
   await page.waitForFunction(id=>document.querySelector('#cn-pair').value===id,ready.pair_id);
   await page.locator('#cn-mode').selectOption('calculation_only');
   const created=page.waitForResponse(r=>r.url().endsWith('/api/connectivity/runs')&&r.request().method()==='POST');
   await page.locator('#cn-run').click();const response=await created;task=await response.json();
   receipt.calculation_creation_status=response.status();
   }
   receipt.calculation_task_id=task.task_id;
   const deadline=Date.now()+600000;
   while(task.task_id&&['queued','running'].includes(task.status)&&Date.now()<deadline){await pause(3000);task=await(await context.request.get(base+'/api/connectivity/runs/'+task.task_id)).json();}
   receipt.calculation_status=task.status;receipt.calculation_error=task.detail||task.error;
   if(task.result){
    receipt.calculation_checks=task.result.checks.length;
    receipt.calculation_model_calls=task.result.provider_calls.filter(c=>c.performed).length;
    receipt.company_isolated=task.result.documents.every(d=>d.company_id==='600887');
    if(receipt.calculation_model_calls)throw Error('只计算模式产生了模型请求');
    fs.writeFileSync(path.join(out,'production-calculation-task.json'),JSON.stringify(task,null,2));
    await page.goto(base+'/?connectivity_task='+task.task_id,{waitUntil:'networkidle',timeout:90000});
    await page.locator('#cn-results').waitFor({state:'visible',timeout:60000});
    receipt.result_visible=true;receipt.exports={};
    for(const format of ['json','csv','docx']){
     const response=await context.request.get(base+`/api/connectivity/runs/${task.task_id}/export/${format}`);
     receipt.exports[format]=response.status();
     fs.writeFileSync(path.join(out,'production-export.'+format),await response.body());
    }
    const doc=task.result.documents[0];
    const source=await context.request.get(base+'/api/connectivity/sources/'+encodeURIComponent(doc.document_id)+'?view=true&page=1');
    receipt.source_status=source.status();
   }
  }else receipt.calculation_status='not_run_new_company_sources_not_ready';
 }
 await page.screenshot({path:path.join(out,'production-desktop.png')});
 await page.setViewportSize({width:390,height:844});
 receipt.mobile_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);
 await page.screenshot({path:path.join(out,'production-mobile.png')});
 await browser.close();
 fs.writeFileSync(path.join(out,'production-browser.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
})().catch(e=>{console.error(e);process.exitCode=1;});
