/* 使用真实后端读取历史任务，四视口、同源导出、刷新和离线文件检查；不请求新分析。 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const base='http://127.0.0.1:8031';
const out=path.resolve('outputs/finals-20261011-browser');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});const records=[];
 for(const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844]]){
  const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce',acceptDownloads:true});
  await context.addInitScript(()=>{sessionStorage.setItem('audittrace_workspace_session_v2',JSON.stringify({origin:'fixed',task_id:'DEMO-RUN-478070609368',selection:{origin:'fixed',case_id:'CNINFO_000858_T0_20260430',company_name:'五粮液',ticker:'000858',report_years:[2025,2024]}}));});
  const page=await context.newPage();page.setDefaultTimeout(45000);const errors=[],posts=[],httpErrors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  page.on('request',r=>{if(r.method()==='POST')posts.push(r.url())});page.on('response',r=>{if(r.status()>=400)httpErrors.push([r.status(),r.url()])});
  const start=Date.now();await page.goto(base,{waitUntil:'networkidle'});
  if(await page.locator('#demo-enter-workspace').isVisible())await page.locator('#demo-enter-workspace').click();
  await page.waitForFunction(()=>!document.querySelector('#demo-result').hidden&&!document.querySelector('#demo-download-json').disabled);
  await page.locator('#demo-result').scrollIntoViewIfNeeded();
  const taskResponse=await context.request.get(base+'/api/demo/runs/DEMO-RUN-478070609368');
  const historical=await taskResponse.json();
  if(historical.run_id!=='RUN-V7-DCF895BC5377')throw Error('恢复运行身份错误');
  await page.screenshot({path:path.join(out,`result-${width}.png`),fullPage:false});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
  const record={width,height,restore_seconds:(Date.now()-start)/1000,overflow,errors,httpErrors,posts,run_id:'RUN-V7-DCF895BC5377'};
  if(width===1440){
   for(const [id,name] of [['#demo-download-json','历史运行导出.json'],['#demo-download-csv','历史运行导出.csv']]){
    const downloading=page.waitForEvent('download');await page.locator(id).click();await(await downloading).saveAs(path.join(out,name));
   }
   const d=JSON.parse(fs.readFileSync(path.join(out,'历史运行导出.json'),'utf8'));const run=d.run||d.result||d;
   if(run.run_id!=='RUN-V7-DCF895BC5377')throw Error('JSON身份错误');
   if(!fs.readFileSync(path.join(out,'历史运行导出.csv'),'utf8').includes('semantic_support_status'))throw Error('CSV未给出语义未验证状态');
   record.export_identity_verified=true;
   await page.keyboard.press('Tab');record.keyboard_focus=await page.evaluate(()=>document.activeElement?.tagName);
   await page.reload({waitUntil:'networkidle'});await page.waitForFunction(()=>!document.querySelector('#demo-result').hidden);
   record.refresh_same_run=(await (await context.request.get(base+'/api/demo/runs/DEMO-RUN-478070609368')).json()).run_id==='RUN-V7-DCF895BC5377';
  }
  if(posts.length)throw Error('读取路径意外新建POST请求');if(overflow||errors.length||httpErrors.length)record.status='needs_attention';else record.status='passed';
  records.push(record);await context.close();
 }
 const ctx=await browser.newContext({viewport:{width:1440,height:1000}});await ctx.setOffline(true);
 const p=await ctx.newPage();const staticPath=path.resolve('决赛准备/整改_2026-10-11/同源备用.html');
 await p.goto('file:///'+staticPath.replaceAll('\\','/'),{waitUntil:'load'});
 const images=await p.locator('img').evaluateAll(xs=>xs.map(x=>({loaded:x.complete&&x.naturalWidth>0,src:x.getAttribute('src')})));
 if(images.some(i=>!i.loaded))throw Error('离线原文图片未打开');
 await p.screenshot({path:path.join(out,'offline.png')});records.push({offline_static_opened:true,images,run_id:'RUN-V7-DCF895BC5377',model_calls_created:0});
 fs.writeFileSync(path.join(out,'browser-record.json'),JSON.stringify(records,null,2));await ctx.close();await browser.close();
 console.log(JSON.stringify(records));
})().catch(e=>{console.error(e.stack);process.exit(1)});
