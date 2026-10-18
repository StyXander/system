/* 真实后端搜索回归：只读取已有任务，不创建或重跑模型任务。
   NODE_PATH 指向 Playwright 所在目录；SEARCH_TEST_TASK、SEARCH_TEST_BASE_URL 指定任务与服务。
   SEARCH_TEST_COOKIE_FILE 可选，读取本机 Netscape cookie 文件，不输出 cookie 内容。 */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.SEARCH_TEST_BASE_URL || 'http://127.0.0.1:8767';
const task = process.env.SEARCH_TEST_TASK;
const out = path.resolve(process.env.SEARCH_TEST_OUTPUT || 'outputs/connectivity-search-check');
assert(task, '请用 SEARCH_TEST_TASK 指定已有真实任务');
fs.mkdirSync(out, {recursive:true});
let browser;
(async () => {
  browser = await chromium.launch({headless:true,channel:'msedge'});
  const context = await browser.newContext({locale:'zh-CN',reducedMotion:'reduce'});
  if (process.env.SEARCH_TEST_COOKIE_FILE) {
    const cookies = fs.readFileSync(process.env.SEARCH_TEST_COOKIE_FILE,'utf8').split(/\r?\n/).filter(line => line && !line.startsWith('#')).map(line => {
      const fields = line.split('\t');
      return {name:fields[5],value:fields[6],domain:fields[0],path:fields[2]||'/',secure:fields[3]==='TRUE',sameSite:'Lax'};
    });
    await context.addCookies(cookies);
  }
  const page = await context.newPage(), errors = [], failed = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if(message.type()==='error') errors.push(message.text()); });
  page.on('response', response => { if(response.status()>=400) failed.push(`${response.status()} ${response.url()}`); });
  page.on('request', request => { if(request.method()==='POST') writes.push(request.url()); });
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(`${base}/?connectivity_task=${task}#connectivity-root`,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(() => document.querySelector('#cn-check-list [data-check]'),{timeout:60000});
  const before = await (await context.request.get(`${base}/api/connectivity/runs/${task}`)).json();
  const run = before.result;
  assert(run?.occurrences?.length, '必须读取真实报告结果');
  const search = page.locator('#aw-search');
  await search.fill('同比');
  const expectedSources = run.occurrences.filter(row => [row.label,row.context,row.document_id,row.pdf_page,row.row_header,row.column_header,row.year,row.value,row.unit,...(row.footnotes||[])].join(' ').normalize('NFKC').replace(/\s+/g,'').toLowerCase().includes('同比')).length;
  assert(expectedSources > 0, '该真实任务必须有“同比”原文片段');
  await page.waitForFunction(n => document.querySelectorAll('[data-search-source]').length===n,expectedSources);
  assert.equal(await page.locator('#aw-search-results [data-search-source]').count(),expectedSources);
  const relationships = await page.locator('#aw-search-results [data-search-check]').count();
  assert(relationships > 0, '关系应可通过原文或AI意见命中');
  await page.locator('[data-cn-filter="priority"]').click();
  assert.equal(await page.locator('#aw-search-results [data-search-source]').count(),expectedSources,'切换概览筛选不能清掉搜索');
  await page.locator('[data-cn-filter="all"]').click();
  const relation = page.locator('#aw-search-results [data-search-check]').first();
  const id = await relation.getAttribute('data-search-check');
  await relation.click();
  assert.equal(await page.locator('#cn-relation-focus').getAttribute('data-check-id'),id);
  const source = page.locator('#aw-search-results [data-search-source]').first();
  await source.click();
  await page.locator('#cn-reader').waitFor({state:'visible'});
  await page.waitForFunction(() => [...document.querySelectorAll('#cn-reader img')].some(img => img.naturalWidth>0),{timeout:45000});
  await page.keyboard.press('Escape');
  assert(await page.locator('#cn-reader').isHidden());
  // 未命中有反馈；特殊字符按普通文本查找；全角空白不影响“同 比”匹配。
  for (const query of ['不存在的搜索词xyz987','<img src=x onerror=alert(1)>']) {
    await search.fill(query);
    assert((await page.locator('#aw-search-results').innerText()).includes('本次结果中未命中'));
    assert.equal(await page.locator('#aw-search-results img').count(),0);
  }
  await search.fill('同　比');
  assert.equal(await page.locator('#aw-search-results [data-search-source]').count(),expectedSources);
  await search.fill('');
  assert(await page.locator('#aw-search-results').isHidden());
  assert.equal(await page.locator('#cn-check-list [data-check]:visible').count(),run.checks.length);
  const sizes = [];
  for (const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844]]) {
    await page.setViewportSize({width,height});
    assert(await search.isVisible(),'搜索框在手机和平板也应可用');
    await search.fill('同比');
    await search.scrollIntoViewIfNeeded();
    const drawer = page.locator('#cn-list-open');
    if (await drawer.isVisible()) {
      await drawer.click();
      assert(await page.evaluate(() => !document.activeElement.hidden && document.activeElement.getClientRects().length>0),'抽屉不能把焦点移到被搜索隐藏的关系');
      await page.keyboard.press('Escape');
      await search.scrollIntoViewIfNeeded();
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth>innerWidth+1);
    assert(!overflow, `${width}px页面横向溢出`);
    await page.screenshot({path:path.join(out,`${width}-search.png`)});
    sizes.push({width,height,overflow});
  }
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(() => document.querySelector('#cn-check-list [data-check]'),{timeout:60000});
  const after = await (await context.request.get(`${base}/api/connectivity/runs/${task}`)).json();
  assert.deepEqual(after.result.provider_calls,run.provider_calls,'搜索不得触发模型调用');
  assert.deepEqual(writes,[]);
  assert.deepEqual(errors,[]);
  assert.deepEqual(failed,[]);
  const result = {task,sourceMatches:expectedSources,relationshipMatches:relationships,titleOnlyMatches:run.checks.filter(check => check.title.includes('同比')).length,sizes,errors,failed,writes,providerCallsUnchanged:true};
  fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
})().catch(error => { console.error(error.stack);process.exitCode=1; }).finally(async () => { await browser?.close(); });
