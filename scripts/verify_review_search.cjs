/* 查询与登记快照使用真实接口；四屏最多提交一次预检，明确零模型调用。 */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const base=process.env.AUDITTRACE_VERIFY_URL||'http://127.0.0.1:8030';
const out=path.resolve(process.env.AUDITTRACE_VERIFY_OUTPUT||'outputs/决赛整改_2026-10-09/搜索与统一结果验收');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});const records=[];
 try{for(const [width,height]of [[1440,1000],[1024,768],[768,1024],[390,844]]){
  const c=await browser.newContext({viewport:{width,height},reducedMotion:'reduce',locale:'zh-CN',acceptDownloads:true});const p=await c.newPage();p.setDefaultTimeout(45000);
  const errors=[];p.on('pageerror',e=>errors.push(e.message));const r={width,height,errors};records.push(r);
  try{
   await p.goto(base,{waitUntil:'domcontentloaded'});await p.locator('#demo-enter-workspace').click();await p.waitForFunction(()=>document.querySelectorAll('#demo-expanded-cases button').length===8);
   await p.locator('#demo-live-company').fill('ＳＺ０００３３３');
   const first=p.waitForResponse(res=>res.url().includes('/api/companies/search?'));const started=Date.now();await p.locator('#demo-company-search').click();const response=await first;r.directory=await response.json();r.firstSearchMs=Date.now()-started;r.firstStatus=response.status();assert.equal(r.firstStatus,200);assert.equal(r.directory.candidates[0].ticker,'000333');
   await p.locator('#demo-company-candidates button').first().focus();await p.keyboard.press('Enter');r.keyboardConfirmed=await p.locator('#demo-company-search-status').textContent();
   await p.locator('.demo-analysis-settings').first().locator('summary').click();
   await p.locator('#demo-live-latest-year').fill('2025');await p.locator('#demo-report-search').click();await p.waitForFunction(()=>!document.querySelector('#demo-report-search').disabled);
   r.reportStatus=await p.locator('#demo-report-status').textContent();r.reports=await p.locator('#demo-report-results a').evaluateAll(links=>links.map(a=>({url:a.href,text:a.textContent})));assert.ok(r.reports.length);assert.ok(r.reports.every(a=>a.url.startsWith('https://static.cninfo.com.cn/')));
   await p.locator('#demo-live-cutoff').fill('2026-01-01');assert.equal(await p.locator('#demo-report-results a').count(),0);await p.locator('#demo-live-cutoff').fill('');
   await p.locator('#demo-expanded-toggle').click();await p.locator('#demo-expanded-cases button').filter({hasText:'美的集团'}).click();await p.locator('#demo-live-mode').selectOption('rag_only');
   r.settings=await p.locator('#demo-live-action-boundary').textContent();r.mode=await p.locator('#demo-live-mode').inputValue();assert.equal(r.mode,'rag_only');
   await p.locator('#demo-live-sample-title').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(out,`企业入口_${width}.png`)});
   if(width===1440){
    const submission=p.waitForResponse(res=>res.request().method()==='POST' && (/\/api\/pipelines\/cninfo$/.test(res.url()) || /\/api\/demo\/expanded-cases\/.+\/preview$/.test(res.url())));
    await p.locator('#demo-live-submit').click();const created=await (await submission).json();await p.waitForFunction(()=>['处理完成','处理失败','需要人工确认'].some(t=>document.querySelector('#demo-live-task-state').textContent.includes(t)),null,{timeout:180000});
    r.taskState=await p.locator('#demo-live-task-state').textContent();assert.match(r.taskState,/处理完成/);await p.locator('#demo-result').waitFor({state:'visible'});
    r.identity=await p.locator('#demo-result-summary').textContent();assert.match(r.identity,/美的/);r.badge=await p.locator('#demo-execution-badge').textContent();
    const taskId=(await p.locator('#demo-live-task-id').textContent()).trim();r.task=created.request?.analysis_mode==='snapshot_preview'?created:await (await p.request.get(base+'/api/pipelines/'+encodeURIComponent(taskId))).json();assert.equal(r.task.result.analysis.provider_call_count,0);
    assert.equal(r.task.result.analysis.context.three_year_r1_ready,false);
    await p.locator('#demo-established-facts').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(out,'美的统一结果.png')});
    const download=p.waitForEvent('download');await p.locator('#demo-download-json').click();const d=await download;await d.saveAs(path.join(out,'实际预检导出.json'));
    const csvDownload=p.waitForEvent('download');await p.locator('#demo-download-csv').click();const csv=await csvDownload;await csv.saveAs(path.join(out,'实际预检指标.csv'));assert.match(fs.readFileSync(path.join(out,'实际预检指标.csv'),'utf8'),/百分点/);
    await p.reload();await p.locator('#demo-result').waitFor({state:'visible'});r.reloadIdentity=await p.locator('#demo-result-summary').textContent();assert.match(r.reloadIdentity,/美的/);
   }
   if(width===390){
    await p.route('**/api/companies/*/reports?*',route=>route.fulfill({status:503,contentType:'text/html',body:'<!DOCTYPE html><title>Deploy switching</title>'}));
    await p.locator('#demo-report-search').click();await p.waitForFunction(()=>!document.querySelector('#demo-report-search').disabled);
    r.injectedHtml503=await p.locator('#demo-report-status').textContent();assert.match(r.injectedHtml503,/HTTP 503/);assert.ok(!r.injectedHtml503.includes('Unexpected token'));
    await p.unroute('**/api/companies/*/reports?*');await p.locator('#demo-report-search').click();await p.waitForFunction(()=>!document.querySelector('#demo-report-search').disabled);assert.ok(await p.locator('#demo-report-results a').count());
   }
   r.overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert.equal(r.overflow,false);assert.equal(errors.length,0);r.passed=true;
  }catch(e){r.failure=e.message;}
  await c.close();fs.writeFileSync(path.join(out,'验收.json'),JSON.stringify(records,null,2));
 }}finally{await browser.close();}
 console.log(JSON.stringify(records.map(({width,passed,failure,firstStatus,firstSearchMs,taskState})=>({width,passed,failure,firstStatus,firstSearchMs,taskState}))));if(records.some(r=>!r.passed))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
