/* 仅一次经明确授权的隆基绿能真实模型运行；失败后不自动重发付费任务。 */
const fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=path.join(root,'outputs','enterprise-expansion');
const base='http://127.0.0.1:8893';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',reducedMotion:'reduce'});
 await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const receipt={case:'隆基绿能 2025',trial_authorized:true,provider_destination:'api.deepseek.com',requested_model:'deepseek-flash',errors,steps:[],viewports:[]};
 await page.goto(base,{waitUntil:'networkidle'});
 await page.locator('[data-enter-connectivity]').first().click();
 await page.locator('#cn-company-cards [data-select-pair]').first().waitFor();
 await page.locator('#cn-company-query').fill('隆基绿能');
 await page.locator('#cn-company-search button').click();
 await page.locator('[data-confirm-company]').first().waitFor();
 if(!(await page.locator('#cn-company-results').innerText()).includes('601012'))throw Error('incorrect company identity');
 await page.locator('#cn-company-selector').screenshot({path:path.join(out,'01-企业搜索.png')});
 await page.locator('[data-confirm-company]').first().click();
 receipt.steps.push('official_identity_confirmed_601012');
 await page.locator('#cn-company-report-year').selectOption('2025');
 await page.locator('#cn-company-find-reports').click();
 await page.locator('#cn-company-import').waitFor({timeout:90000});
 if(await page.locator('#cn-company-import').isDisabled())throw Error(await page.locator('#cn-company-reports').innerText());
 await page.locator('#cn-company-confirmed').screenshot({path:path.join(out,'02-双报告候选.png')});
 const importReply=page.waitForResponse(r=>r.url().endsWith('/api/connectivity/catalog/imports')&&r.request().method()==='POST');
 await page.locator('#cn-company-import').click();
 const imported=await importReply;const importTask=await imported.json();
 if(imported.status()!==202)throw Error(JSON.stringify(importTask));
 receipt.import_task_id=importTask.task_id;
 const deadline=Date.now()+600000;let progress;
 do{
   progress=await(await context.request.get(base+'/api/connectivity/catalog/imports/'+importTask.task_id)).json();
   if(['failed','cancelled'].includes(progress.status))throw Error(JSON.stringify(progress));
   if(progress.status==='completed')break;
   await pause(1500);
 }while(Date.now()<deadline);
 if(progress.status!=='completed')throw Error('report intake timeout; model not started');
 const pair=progress.result.pair_id;
 if(!pair.startsWith('CONNPAIR-601012-2025-'))throw Error('cross-company pair');
 await page.waitForFunction(pair=>document.querySelector('#cn-pair').value===pair,pair);
 receipt.pair_id=pair;receipt.steps.push('real_pdf_validated_and_pair_persisted');
 await page.locator('#cn-company-selector').screenshot({path:path.join(out,'03-原件接入完成.png')});
 await page.locator('#cn-mode').selectOption('three_agents');
 const creation=page.waitForResponse(r=>r.url().endsWith('/api/connectivity/runs')&&r.request().method()==='POST');
 await page.locator('#cn-run').click();
 const response=await creation;let task=await response.json();
 if(response.status()!==200&&response.status()!==202)throw Error('one authorized attempt rejected '+JSON.stringify(task));
 receipt.task_id=task.task_id;receipt.steps.push('three_agents_started_once');
 console.log('model_task',task.task_id);
 const end=Date.now()+900000;let shown='';
 while(['queued','running'].includes(task.status)&&Date.now()<end){
   await pause(3000);
   task=await(await context.request.get(base+'/api/connectivity/runs/'+task.task_id)).json();
   const next=JSON.stringify(task.stages||{});
   if(next!==shown){console.log('progress',task.status,next.slice(-500));shown=next;}
 }
 fs.writeFileSync(path.join(out,'real-model-task.json'),JSON.stringify(task,null,2));
 if(!task.result)throw Error('model run did not produce result: '+JSON.stringify(task.error));
 const run=task.result,own=new Set(run.documents.map(d=>d.document_id));
 if(run.documents.some(d=>d.company_id!=='601012')||run.occurrences.some(o=>!own.has(o.document_id)))throw Error('cross-company evidence');
 receipt.task_status=task.status;receipt.run_id=run.run_id;receipt.model_status=run.model_status;
 receipt.provider_calls=run.provider_calls.filter(c=>c.performed).length;
 receipt.provider_records=run.provider_calls;
 if(receipt.provider_calls>12)throw Error('authorized request ceiling exceeded');
 receipt.input_tokens=run.provider_calls.reduce((sum,c)=>sum+(c.input_tokens||0),0);
 receipt.output_tokens=run.provider_calls.reduce((sum,c)=>sum+(c.output_tokens||0),0);
 receipt.steps.push('actual_result_and_current_company_evidence_verified');
 await page.locator('#cn-results').waitFor({state:'visible',timeout:20000});
 for(const format of ['json','csv','docx']){
   const exported=await context.request.get(base+`/api/connectivity/runs/${task.task_id}/export/${format}`);
   if(exported.status()!==200)throw Error('export '+format+' '+exported.status());
   fs.writeFileSync(path.join(out,'隆基绿能_真实运行.'+format),await exported.body());
   receipt.steps.push('export_'+format+'_200');
 }
 const source=await context.request.get(base+'/api/connectivity/sources/'+encodeURIComponent(run.documents[0].document_id)+'?view=true&page=1');
 receipt.source_status=source.status();if(source.status()!==200)throw Error('original PDF inaccessible');
 for(const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844]]){
   await page.setViewportSize({width,height});await pause(500);
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth);
   if(overflow)throw Error('horizontal overflow '+width);
   const file='企业搜索验收_'+width+'x'+height+'.png';await page.screenshot({path:path.join(out,file)});
   receipt.viewports.push({width,height,overflow,file});
 }
 // 改选另一企业只改变下一次运行参数，当前任务仍属于隆基，不能伪装为新企业结果。
 const current=await page.locator('#cn-results').innerText();
 await page.locator('[data-select-pair="600019-2025"]').click();
 await page.waitForFunction(()=>document.querySelector('#cn-pair').value==='600019-2025');
 receipt.switch_preserves_result=await page.locator('#cn-results').isVisible()&&(await page.locator('#cn-results').innerText())===current;
 if(!receipt.switch_preserves_result)throw Error('switch cleared current result');
 fs.writeFileSync(path.join(out,'browser-company-acceptance.json'),JSON.stringify(receipt,null,2));
 console.log(JSON.stringify({task_id:receipt.task_id,status:receipt.task_status,model_status:receipt.model_status,provider_calls:receipt.provider_calls,errors}));
 await browser.close();if(errors.length)process.exitCode=1;
})().catch(error=>{console.error(error);fs.writeFileSync(path.join(out,'browser-company-error.txt'),error.stack);process.exitCode=1;});
