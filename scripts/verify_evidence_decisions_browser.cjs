/* 实际后端、四个视口、加入与撤回、键盘和导出的认定级工作流验收。 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const base = process.env.AUDITTRACE_VERIFY_URL || 'http://127.0.0.1:8024';
const out = path.resolve(process.env.AUDITTRACE_VERIFY_OUT || '决赛准备/认定级取证整改_2026-10-14/浏览器验收');
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const results = [];
  for (const [width, height] of [[1440,1000], [1024,768], [768,1024], [390,844]]) {
    const context = await browser.newContext({ viewport: { width, height }, locale: 'zh-CN', reducedMotion: 'reduce', acceptDownloads: true });
    const page = await context.newPage();
    const errors=[], requestsFailed=[], httpErrors=[];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', msg => { if(msg.type()==='error') errors.push(msg.text()); });
    page.on('requestfailed', r => requestsFailed.push({url:r.url(),failure:r.failure()?.errorText}));
    page.on('response', r => { if(r.status()>=400) httpErrors.push({url:r.url(),status:r.status()}); });
    page.setDefaultTimeout(30000);
    const record={width,height,errors,requestsFailed,httpErrors};
    try {
      await page.goto(base, {waitUntil:'networkidle'});
      await page.screenshot({path:path.join(out,`首页_${width}.png`)});
      await page.locator('[data-open-evidence]').click();
      record.directEntry=await page.locator('#evidence-demo-section').getAttribute('open')!==null;
      const summary=page.locator('#evidence-demo-section > summary');
      // 先验证首页入口，再分别检查折叠与键盘展开。
      await summary.focus(); await page.keyboard.press('Enter'); await page.keyboard.press('Enter');
      const root=page.locator('#evidence-scenario-workbench');
      await root.locator('[data-action="scenario"]').waitFor();
      const status=q=>root.locator(`[data-question="${q}"]`).getAttribute('data-state');
      const select=id=>root.locator(`input[value="${id}"]`);
      record.guidedOperations=true;
      for(const [index, expected] of [[0,'partial'],[1,'conflicting'],[2,'partial']]){
        const response=page.waitForResponse(r=>r.url().endsWith('/api/evidence-checks')&&r.request().method()==='POST');
        await root.locator(`[data-evidence-step="${index}"]`).click();
        const data=await (await response).json();
        await root.locator('.evidence-check-status').filter({hasText:'已完成'}).waitFor();
        const valid=(await status('REV-CUT'))===expected&&data.provider_call_count===0;
        const focus=await root.locator(`[data-evidence-step="${index}"]`).evaluate(e=>e===document.activeElement);
        record.guidedOperations=record.guidedOperations&&valid&&focus;
      }
      await root.locator('[data-action="restore"]').click();
      async function check(){
        const pending=page.waitForResponse(r=>r.url().endsWith('/api/evidence-checks')&&r.request().method()==='POST');
        await root.locator('[data-action="check"]').click();
        const data=await (await pending).json();
        await root.locator('.evidence-check-status').filter({hasText:'已完成'}).waitFor();
        if(data.provider_call_count!==0) throw new Error('独立检验调用了供应商');
        return data;
      }
      record.keyboardOpened=await page.locator('#evidence-demo-section').evaluate(e=>e.open);
      await select('A-REC').check(); await check();
      record.receiptDoesNotCloseCutoff=(await status('REV-CUT'))==='partial';
      await select('A-ACC').check(); const conflict=await check();
      record.acceptanceRevealsConflict=(await status('REV-CUT'))==='conflicting';
      record.originalHash=conflict.investigation.source_snapshot_sha256;
      await root.locator('[data-question="REV-CUT"]').scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(out,`截止冲突_${width}x${height}.png`)});
      await select('A-CON').uncheck(); const withdrawn=await check();
      record.withdrawalRemovesSupport=(await status('REV-CUT'))==='partial';
      record.hashUnchanged=withdrawn.investigation.source_snapshot_sha256===record.originalHash;
      record.focusAfterCheck=await root.locator('[data-action="check"]').evaluate(e=>e===document.activeElement);
      await root.locator('[data-action="restore"]').click();
      record.restored=!(await select('A-ACC').isChecked())&&await select('A-CON').isChecked();
      await root.locator('[data-action="scenario"]').selectOption('ANON-SALE-B');
      await select('B-INV').check(); await check();
      record.amountMatches=(await status('REV-ACC'))==='rule_supported';
      await select('B-BAD').check(); await check();
      record.amountConflict=(await status('REV-ACC'))==='conflicting';
      await root.locator('[data-action="scenario"]').selectOption('ANON-AR-C');
      await select('C-SUM').check(); await select('C-IMP').check(); await check();
      record.summaryDoesNotCloseDetail=(await status('AR-VAL'))==='partial';
      record.partialReceiptDoesNotCloseBalance=(await status('AR-EXI'))==='partial';
      await select('C-AGE').check(); await select('C-CON').check(); const final=await check();
      record.customerMaterialsMeetRules=(await status('AR-VAL'))==='rule_supported'&&(await status('AR-EXI'))==='rule_supported';
      record.professionalNotPerformed=final.investigation.professional_review_status==='not_performed';
      await root.locator('[data-question="AR-VAL"]').scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(out,`客户资料用途_${width}x${height}.png`)});
      record.overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
      record.touchTargets=await root.locator('button,select,summary,.evidence-options label').evaluateAll(es=>es.filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height<44).map(e=>e.textContent.trim().slice(0,40)));
      for(const action of ['json','csv','word']){
        const promise=page.waitForEvent('download'); await root.locator(`[data-action="${action}"]`).click();
        const file=await promise; await file.saveAs(path.join(out,`${width}-${file.suggestedFilename()}`));
      }
      record.exports=true;
      if(width===1440){
        await page.evaluate(()=>{window.print=()=>{};});
        await root.locator('[data-action="print"]').click();
        record.printClone=await page.locator('#evidence-print-copy').count()===1;
        await page.pdf({path:path.join(out,'同源独立检验打印验收.pdf'),format:'A4',printBackground:true});
        await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));
        record.printRestored=await page.locator('#evidence-print-copy').count()===0;
      }
      // 扫描限定本次新增组件；已有页面问题不伪称已全部修复。
      try {
        await page.addScriptTag({path:require.resolve('axe-core/axe.min.js')});
        record.axe=await page.evaluate(async()=>{const r=await axe.run(document.querySelector('#evidence-scenario-workbench'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa']}});return{violations:r.violations.map(v=>({id:v.id,impact:v.impact,targets:v.nodes.map(n=>n.target)})),incomplete:r.incomplete.map(v=>v.id)};});
      } catch(error){record.axe={unavailable:error.message};}
      if(width===1440 && !process.env.AUDITTRACE_VERIFY_SKIP_REAL_RUN){
        await page.locator('#demo-enter-workspace').click();
        const backup=page.locator('#demo-backup');
        if(await backup.isVisible()) await backup.click(); else await page.locator('#demo-start').click();
        await page.locator('#evidence-run-workbench').waitFor({state:'visible',timeout:90000});
        record.realRunTasks=await page.locator('#evidence-run-workbench .evidence-question').count();
        await page.locator('#evidence-run-workbench').scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(out,'真实年报取证任务_1440.png')});
      }
      record.passed=['directEntry','guidedOperations','keyboardOpened','receiptDoesNotCloseCutoff','acceptanceRevealsConflict','withdrawalRemovesSupport','hashUnchanged','focusAfterCheck','restored','amountMatches','amountConflict','summaryDoesNotCloseDetail','partialReceiptDoesNotCloseBalance','customerMaterialsMeetRules','professionalNotPerformed','exports'].every(k=>record[k])&&!record.overflow&&!record.touchTargets.length&&!errors.length&&!requestsFailed.length&&!httpErrors.length&&!(record.axe.violations||[]).length&&(width!==1440||((record.realRunTasks===5||process.env.AUDITTRACE_VERIFY_SKIP_REAL_RUN)&&record.printClone&&record.printRestored));
    } catch(error){record.failure=error.message;record.passed=false;await page.screenshot({path:path.join(out,`失败_${width}.png`)});}
    results.push(record); await context.close();
  }
  await browser.close();fs.writeFileSync(path.join(out,'四视口真实浏览器验收.json'),JSON.stringify(results,null,2));
  console.log(JSON.stringify(results.map(r=>({width:r.width,passed:r.passed,failure:r.failure,errors:r.errors,httpErrors:r.httpErrors,axe:r.axe}))));
  process.exitCode=results.every(r=>r.passed)?0:1;
})().catch(error=>{console.error(error.message);process.exitCode=1;});
