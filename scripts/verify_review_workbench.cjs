/* 复审验收使用真实任务与接口；只对读取故障注入一次503，不制造分析结果。 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const base = process.env.AUDITTRACE_VERIFY_URL || 'http://127.0.0.1:8030';
const taskId = process.env.AUDITTRACE_VERIFY_TASK || 'DEMO-RUN-21E29E9CF1D2';
const out = path.resolve(process.env.AUDITTRACE_VERIFY_OUTPUT || 'outputs/决赛整改_2026-10-09/复审整改_最终浏览器验收');
fs.mkdirSync(out, {recursive:true});
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const records = [];
  try {
    for (const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844]]) {
      const context = await browser.newContext({viewport:{width,height},locale:'zh-CN',reducedMotion:'reduce',acceptDownloads:true});
      const p = await context.newPage();
      p.setDefaultTimeout(45000);
      const errors=[], posts=[];
      p.on('pageerror', e=>errors.push(e.message));
      p.on('request', r=>{if(r.method()==='POST')posts.push(r.url());});
      const record = {width,height,errors,posts};
      records.push(record);
      try {
        await p.addInitScript(({taskId})=>sessionStorage.setItem('audittrace_demo_task_v1',JSON.stringify({task_id:taskId,case_id:'STD_DEV_T0',mode:'primary'})),{taskId});
        await p.goto(base,{waitUntil:'domcontentloaded'});
        await p.locator('#demo-result').waitFor({state:'visible'});
        await p.locator('#demo-enter-workspace').click();
        record.identity = await p.locator('#demo-result-summary').textContent();
        record.badge = await p.locator('#demo-execution-badge').textContent();
        assert.match(record.badge,/本次新增 0 次/);
        record.facts = await p.locator('#demo-established-facts').textContent();
        assert.match(record.facts,/个百分点/);
        assert.equal(await p.locator('#demo-structured-table-body tr').first().locator('td').count(),3);
        assert.equal(await p.locator('#demo-live-sample-drawer').evaluate(e=>e.tagName),'SECTION');
        record.geometry = await p.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,main:document.querySelector('.demo-analysis-main').getBoundingClientRect().width,axis:document.querySelector('.demo-evidence-axis').getBoundingClientRect().width}));
        assert.equal(record.geometry.overflow,false);
        if(width===390) assert.ok(record.geometry.main>=320);
        await p.locator('#demo-established-facts').scrollIntoViewIfNeeded();
        record.factsViewport=await p.locator('#demo-established-facts').boundingBox();
        assert.ok(record.factsViewport.y < height && record.factsViewport.y + record.factsViewport.height > 0);
        await p.screenshot({path:path.join(out,`结果正文_${width}.png`)});
        await p.locator('.demo-inline-evidence summary').first().click();
        record.sourceLink = await p.locator('.demo-inline-evidence a').first().getAttribute('href');
        assert.match(record.sourceLink,/#page=\d+/);
        if(width===1440){
          await p.locator('.demo-axis-nav').nth(2).click();
          assert.equal(await p.locator('.demo-axis-nav[aria-current]').getAttribute('aria-label'),'定位到下一步准备什么');
        }
        const previous = await p.locator('#demo-result details').evaluateAll(items=>items.map(e=>e.open));
        await p.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));
        record.printAllOpen=await p.locator('#demo-result details').evaluateAll(items=>items.every(e=>e.open));
        assert.ok(record.printAllOpen);
        if(width===1440) await p.pdf({path:path.join(out,'同源结果打印.pdf'),format:'A4',printBackground:true});
        await p.evaluate(()=>window.dispatchEvent(new Event('afterprint')));
        assert.deepEqual(await p.locator('#demo-result details').evaluateAll(items=>items.map(e=>e.open)),previous);
        const axePath=path.resolve('backend/.venv/Lib/site-packages/axe_playwright_python/axe.min.js');
        if(fs.existsSync(axePath)){
          await p.route('**/__review_axe.js',r=>r.fulfill({contentType:'application/javascript',body:fs.readFileSync(axePath)}));
          await p.addScriptTag({url:base+'/__review_axe.js'});
          record.axe=await p.evaluate(async()=>{const r=await axe.run(document.querySelector('#demo-result'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,targets:v.nodes.map(n=>n.target)}));});
          assert.equal(record.axe.length,0);
        }
        assert.equal(posts.length,0);
        assert.equal(errors.length,0);
        record.passed=true;
      }catch(e){record.failure=e.message;}
      await context.close();
      fs.writeFileSync(path.join(out,'验收.json'),JSON.stringify(records,null,2));
    }
    const c=await browser.newContext(); const p=await c.newPage(); const posts=[];
    p.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});
    await p.addInitScript(({taskId})=>sessionStorage.setItem('audittrace_demo_task_v1',JSON.stringify({task_id:taskId,case_id:'STD_DEV_T0',mode:'primary'})),{taskId});
    let injected=false;
    await p.route(`**/api/demo/runs/${taskId}`,async r=>{if(!injected){injected=true;await r.fulfill({status:503,contentType:'application/json',body:'{"detail":"acceptance temporary read failure"}'});}else await r.continue();});
    await p.goto(base);
    await p.locator('#demo-read-result').waitFor({state:'visible'});
    assert.ok(await p.evaluate(()=>sessionStorage.getItem('audittrace_demo_task_v1')));
    await p.locator('#demo-read-result').click();
    await p.locator('#demo-result').waitFor({state:'visible'});
    assert.equal(posts.length,0);
    records.push({recovery:'one injected 503',sameTask:taskId,posts,passed:true});
    await c.close();
    fs.writeFileSync(path.join(out,'验收.json'),JSON.stringify(records,null,2));
    console.log(JSON.stringify(records.map(({width,passed,failure,recovery,geometry})=>({width,passed,failure,recovery,geometry}))));
    if(records.some(r=>!r.passed))process.exitCode=1;
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
