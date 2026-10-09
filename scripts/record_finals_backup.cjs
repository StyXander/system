/* 当前版本机真实备用演示与导出录屏；明确断言零模型调用，不填写人工批准。 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const base = process.env.AUDITTRACE_VERIFY_URL || 'http://127.0.0.1:8026';
const out = path.resolve('outputs/决赛整改_2026-10-09/主演示备用录屏');
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true, recordVideo: { dir: out, size: { width: 1440, height: 1000 } } });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base, { waitUntil: 'networkidle' });
    await page.locator('#demo-enter-workspace').click();
    await page.screenshot({ path: path.join(out, '当前准备完成首屏.png') });
    await page.locator('#demo-backup').click();
    await page.waitForFunction(() => !document.querySelector('#demo-download-json').disabled && !document.querySelector('#demo-result').hidden, null, { timeout: 120000 });
    for (const [button, filename] of [['#demo-download-json', '真实备用结果.json'], ['#demo-download-csv', '真实备用结果.csv']]) {
      const waiting = page.waitForEvent('download');
      await page.locator(button).click();
      await (await waiting).saveAs(path.join(out, filename));
    }
    const payload = JSON.parse(fs.readFileSync(path.join(out, '真实备用结果.json'), 'utf8'));
    const run = payload.run || payload;
    const calls = run.model_check?.provider_call_count ?? run.provider_call_count;
    if (calls !== 0) throw Error(`备用结果模型调用次数不是0: ${calls}`);
    await page.locator('#demo-result').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(out, '当前版真实备用结果.png') });
    fs.writeFileSync(path.join(out, '录屏验收.json'), JSON.stringify({ run_id: run.run_id, provider_calls: calls, errors, csv_exported: true, video_file: path.basename(await page.video().path()), model_chain_verified: false, human_approval_performed: false, ai_generated_content_notice: 'AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。' }, null, 2));
    if (errors.length) throw Error(errors.join(';'));
    console.log(JSON.stringify({ run_id: run.run_id, provider_calls: calls, status: 'passed' }));
  } finally {
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
