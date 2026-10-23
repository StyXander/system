/* 本轮真实工作台程序核验，不发起模型请求。 */
const fs=require('fs'),path=require('path'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=path.join(root,'outputs/financial-impact-acceptance/browser');
fs.mkdirSync(out,{recursive:true});const base=process.env.AUDITTRACE_VERIFY_URL||'http://127.0.0.1:8893';
(async()=>{
 const receipt={target:base,time:new Date().toISOString(),errors:[],model_requests:0,viewports:[]};
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
 await context.route('**/*',route=>{const r=route.request();if(r.method()==='POST'&&r.url().endsWith('/api/connectivity/runs')&&JSON.parse(r.postData()).mode!=='calculation_only')throw Error('禁止未授权模型请求');return route.continue()});
 const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>receipt.errors.push(e.message));
 await page.goto(base,{waitUntil:'networkidle'});await page.locator('[data-enter-connectivity]').first().click();
 await page.locator('#cn-company-cards [data-select-pair]').first().waitFor();
 await page.locator('#cn-company-query').fill('五粮液');await page.locator('#cn-company-search button').click();
 await page.locator('[data-confirm-company]').first().waitFor();receipt.search=await page.locator('#cn-company-results').innerText();
 await page.locator('[data-confirm-company]').first().click();
 await page.locator('[data-select-pair="000858-2025"]').first().click();
 await page.locator('#cn-mode').selectOption('calculation_only');
 const created=page.waitForResponse(r=>r.url().endsWith('/api/connectivity/runs')&&r.request().method()==='POST');
 await page.locator('#cn-run').click();let task=await(await created).json();receipt.task_id=task.task_id;
 for(let i=0;i<200&&['running','queued'].includes(task.status);i++){await new Promise(r=>setTimeout(r,3000));task=await(await context.request.get(base+'/api/connectivity/runs/'+task.task_id)).json();}
 fs.writeFileSync(path.join(out,'calculation-task.json'),JSON.stringify(task,null,2));
 if(!task.result?.financial_impact?.events?.length)throw Error('未生成财务穿透结果:'+JSON.stringify(task.error));
 receipt.status=task.status;receipt.stats=task.result.financial_impact.stats;receipt.model_requests=task.result.provider_calls.filter(r=>r.performed).length;
 await page.goto(base+'/?connectivity_task='+task.task_id,{waitUntil:'networkidle'});
 await page.locator('#cn-results').waitFor({state:'visible'});
 await page.locator('#cn-financial').scrollIntoViewIfNeeded();
 const select=page.locator('[data-fi-select]');receipt.options=await select.locator('option').count();
 const option=await select.locator('option').allTextContents();receipt.project_options=option;
 const project=await select.locator('option').evaluateAll(rows=>rows.find(r=>r.textContent.includes('包装'))?.value);
 if(project){await select.selectOption(project);receipt.project_visible=await page.locator('.cn-fi-item:visible').count();}
 receipt.paths=await page.locator('.cn-fi-evidence-paths article:visible').count();
 for(const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844]]){
  await page.setViewportSize({width,height});await page.locator('#cn-financial').scrollIntoViewIfNeeded();
  receipt.viewports.push({width,height,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth)});
  await page.screenshot({path:path.join(out,`financial-${width}.png`)});
 }
 receipt.exports={};for(const format of ['json','csv','docx']){const r=await context.request.get(base+`/api/connectivity/runs/${task.task_id}/export/${format}`);receipt.exports[format]=r.status();fs.writeFileSync(path.join(out,'export.'+format),await r.body());}
 const event=task.result.financial_impact.events.find(r=>r.project_name.includes('包装'))||task.result.financial_impact.events[0];
 const source=await context.request.get(base+'/api/connectivity/sources/'+event.document_id+'/pages/'+event.pdf_page+'.png');receipt.source_status=source.status();
 if(source.ok())fs.writeFileSync(path.join(out,'esg-source.png'),await source.body());
 receipt.health=await(await context.request.get(base+'/api/health')).json();
 fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));await browser.close();
 if(receipt.model_requests||receipt.errors.length||receipt.viewports.some(r=>r.overflow)||Object.values(receipt.exports).some(r=>r!==200))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
