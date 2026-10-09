/* 真实页面验收：匿名查询、候选确认、公告来源、扩展预检与四屏宽。 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const base = process.env.AUDITTRACE_VERIFY_URL || 'http://127.0.0.1:8019';
const out = path.resolve(process.env.AUDITTRACE_VERIFY_OUTPUT || path.join('outputs', '决赛系统优化_2026-10-09'));
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const results = [];
  for (const [width, height] of [[1440, 1000], [1024, 768], [768, 1024], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height }, locale: 'zh-CN', reducedMotion: 'reduce', acceptDownloads: true });
    const page = await context.newPage();
    page.setDefaultTimeout(45000);
    const errors = [], failedRequests = [], httpErrors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('requestfailed', req => failedRequests.push({ url: req.url(), reason: req.failure()?.errorText }));
    page.on('response', res => { if (res.status() >= 400) httpErrors.push({ url: res.url(), status: res.status() }); });
    const record = { width, height, errors, failedRequests, httpErrors };
    try {
      // 页面能操作后以真实业务控件判定准备完成，图片加载不作为企业搜索的前置条件。
      await page.goto(base, { waitUntil: 'domcontentloaded' });
      await page.locator('#demo-enter-workspace').click();
      await page.screenshot({ path: path.join(out, `工作台首屏_${width}x${height}.png`) });
      await page.locator('#demo-secondary-menu summary').click();
      await page.locator('#demo-open-live-sample').click();
      await page.waitForFunction(() => document.querySelectorAll('#demo-expanded-cases button').length === 8);
      record.expandedCount = await page.locator('#demo-expanded-cases button').count();
      await page.locator('#demo-live-company').fill('ＳＺ０００３３３');
      await page.locator('#demo-company-search').click();
      await page.locator('#demo-company-candidates button').first().waitFor();
      record.normalizedCandidate = await page.locator('#demo-company-candidates').innerText();
      await page.locator('#demo-company-candidates button').first().focus();
      await page.keyboard.press('Enter');
      record.keyboardConfirmed = true;
      record.confirmed = await page.locator('#demo-company-search-status').innerText();
      await page.locator('#demo-live-latest-year').fill('2025');
      await page.locator('#demo-report-search').click();
      await page.waitForFunction(() => !document.querySelector('#demo-report-search').disabled);
      record.reportStatus = await page.locator('#demo-report-status').innerText();
      record.reportLinks = await page.locator('#demo-report-results a').evaluateAll(links => links.map(a => ({ href: a.href, text: a.textContent })));
      const axePath = path.resolve('backend/.venv/Lib/site-packages/axe_playwright_python/axe.min.js');
      if (fs.existsSync(axePath)) {
        await page.route('**/__axe_audit/axe.min.js', route => route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(axePath) }));
        await page.addScriptTag({ url: `${base}/__axe_audit/axe.min.js` });
        record.axe = await page.evaluate(async () => {
          const result = await axe.run(document.querySelector('#demo-live-sample-drawer'), { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } });
          return { version: axe.version, violations: result.violations.map(v => ({ id: v.id, impact: v.impact, targets: v.nodes.map(n => n.target) })), incomplete: result.incomplete.map(v => v.id), passes: result.passes.length };
        });
      } else record.axe = { unavailable: true };
      await page.locator('#demo-live-sample-drawer').evaluate(el => { el.scrollTop = 0; });
      await page.screenshot({ path: path.join(out, `企业搜索_${width}x${height}.png`) });
      await page.locator('#demo-report-results').scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(out, `年报结果_${width}x${height}.png`) });
      record.overflow = await page.evaluate(() => ({ page: document.documentElement.scrollWidth > innerWidth, drawer: document.querySelector('#demo-live-sample-drawer').scrollWidth > document.querySelector('#demo-live-sample-drawer').clientWidth + 2 }));
      // 修改查询时点必须立即清除已展示的旧公告，重新查询才可恢复。
      await page.locator('#demo-live-cutoff').fill('2026-01-01');
      record.oldReportsCleared = await page.locator('#demo-report-results a').count() === 0;
      await page.locator('#demo-live-cutoff').fill('');
      await page.locator('#demo-live-company').fill('银行');
      await page.locator('#demo-company-search').click();
      await page.locator('#demo-company-candidates button').first().waitFor();
      record.ambiguousCount = await page.locator('#demo-company-candidates button').count();
      record.unconfirmedDisabled = await page.locator('#demo-live-submit').isDisabled();
      await page.locator('#demo-live-company').fill('腾讯');
      await page.locator('#demo-company-search').click();
      await page.waitForFunction(() => !document.querySelector('#demo-company-search').disabled);
      record.notFoundText = await page.locator('#demo-company-search-status').innerText();
      await page.locator('#demo-expanded-toggle').click();
      await page.locator('#demo-expanded-cases button').filter({ hasText: '美的集团' }).click();
      record.snapshotEnabled = !await page.locator('#demo-live-submit').isDisabled();
      await page.locator('#demo-live-cutoff').fill('2026-01-01');
      await page.locator('#demo-live-cutoff').dispatchEvent('change');
      record.sharedCutoffBlocked = await page.locator('#demo-live-submit').isDisabled();
      await page.locator('#demo-live-cutoff').fill('');
      await page.locator('#demo-live-cutoff').dispatchEvent('change');
      {
        await page.locator('#demo-live-submit').click();
        await page.waitForFunction(() => ['需要人工确认', '处理完成', '处理失败'].some(label => document.querySelector('#demo-live-task-state').textContent.includes(label)), null, { timeout: 45000 });
        record.taskState = await page.locator('#demo-live-task-state').innerText();
        record.taskId = await page.locator('#demo-live-task-id').innerText();
        record.taskMessage = await page.locator('#demo-live-message').innerText();
        record.structuredRows = await page.locator('#demo-live-structured-table-body tr').count();
        record.metricLabelWidth = (await page.locator('#demo-live-structured-table-body tr').first().locator('td').nth(1).boundingBox()).width;
        await page.locator('#demo-live-task-state').scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(out, `真实预检_${width}x${height}.png`) });
        await page.locator('#demo-live-table-wrap thead').scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(out, `结构化指标_${width}x${height}.png`) });
        const downloadPromise = page.waitForEvent('download');
        await page.locator('#demo-live-download-json').click();
        const download = await downloadPromise;
        await download.saveAs(path.join(out, width === 1440 ? '浏览器扩展案例导出.json' : `浏览器扩展案例导出_${width}.json`));
        record.downloaded = true;
      }
      await page.keyboard.press('Escape');
      record.escapeClosed = await page.locator('#demo-live-sample-drawer').evaluate(el => !el.open);
      record.focusRestored = await page.locator('#demo-secondary-menu summary').evaluate(el => document.activeElement === el);
      if (!record.axe.unavailable) {
        record.workbenchAxe = await page.evaluate(async () => {
          const result = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } });
          return { violations: result.violations.map(v => ({ id: v.id, impact: v.impact, targets: v.nodes.map(n => n.target) })), incomplete: result.incomplete.map(v => v.id) };
        });
      }
      record.passed = !record.overflow.page && !record.overflow.drawer && errors.length === 0 && failedRequests.length === 0 && httpErrors.length === 0 && record.metricLabelWidth >= 100 && record.structuredRows > 0 && record.oldReportsCleared && record.expandedCount === 8 && record.ambiguousCount > 1 && record.unconfirmedDisabled && record.snapshotEnabled && record.sharedCutoffBlocked && record.escapeClosed && record.focusRestored && record.keyboardConfirmed && record.reportLinks.length > 0 && !(record.axe.violations || []).length && !(record.workbenchAxe?.violations || []).length;
    } catch (error) { record.failure = error.message; record.passed = false; await page.screenshot({ path: path.join(out, `失败_${width}.png`) }); }
    results.push(record);
    await context.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(out, '真实浏览器验收.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results.map(({ width, height, passed, failure, errors, reportLinks, taskState }) => ({ width, height, passed, failure, errors, reportCount: reportLinks?.length, taskState }))));
  process.exitCode = results.every(r => r.passed) ? 0 : 1;
})().catch(error => { console.error(error.message); process.exitCode = 1; });
