const {chromium}=require('playwright');
const fs=require('fs');
const out='outputs/connectivity-fixes-20261017';
const base=process.env.BASE||'http://127.0.0.1:8796';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true});
 let task=''; const records=[];
 for(const [width,height] of [[1440,1000],[1024,768],[768,1024],[390,844]]){
  const page=await browser.newPage({viewport:{width,height},reducedMotion:'reduce'});
  const errors=[],failed=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  page.on('response',r=>{if(r.status()>=400)failed.push([r.status(),r.url()]);});
  page.on('requestfailed',r=>failed.push([r.url(),r.failure()?.errorText]));
  await page.goto(`${base}/${task?'?connectivity_task='+task:'#top'}`,{waitUntil:'networkidle'});
  if(!task){
   await page.locator('[data-enter-connectivity]').first().click();
   await page.locator('#cn-pair option[value="000858-2025"]').waitFor({state:'attached'});
   await page.selectOption('#cn-pair','000858-2025');await page.locator('#cn-next').click();
   await page.locator('.cn-advanced').evaluate(e=>e.open=true);
   await page.selectOption('#cn-mode','calculation_only');await page.locator('#cn-next').click();await page.locator('#cn-run').click();
  }
  await page.waitForFunction(()=>!document.querySelector('#cn-results').hidden, null,{timeout:60000});
  task=new URL(page.url()).searchParams.get('connectivity_task');
  const before=await page.locator('#cn-fourq').innerText();
  await page.selectOption('#cn-perspective','professional');
  const professional=(await page.locator('#cn-perspective-note').innerText()).includes('事务所核对');
  const unchanged=before===await page.locator('#cn-fourq').innerText();
  if(width>=768&&width<1200){
   await page.locator('#cn-list-open').click();await page.locator('.cn-check').nth(1).click();
   await page.locator('#cn-list-open').click();await page.keyboard.press('Escape');
  }else{
   await page.locator('#cn-list-toggle').click();await page.locator('#cn-list-toggle').click();
   await page.locator('.cn-check').filter({hasText:'研发人员数量'}).first().click();
  }
  await page.locator('#cn-master').evaluate(e=>e.scrollIntoView({block:'start'}));
  const layout=await page.evaluate(()=>{
   const a=document.querySelector('#cn-list-panel').getBoundingClientRect(),b=document.querySelector('#cn-detail').getBoundingClientRect();
   return {list:{x:a.x,y:a.y,width:a.width},detail:{x:b.x,y:b.y,width:b.width},overflow:document.documentElement.scrollWidth>innerWidth,
    desktopButton:getComputedStyle(document.querySelector('#cn-list-open')).display};
  });
  await page.screenshot({path:`${out}/result-${width}.png`});
  const ok=professional&&unchanged&&!layout.overflow&&!errors.length&&!failed.length&&(width<1200||(layout.list.x<layout.detail.x&&Math.abs(layout.list.y-layout.detail.y)<10&&layout.desktopButton==='none'));
  records.push({width,height,task,professional,unchanged,layout,errors,failed,ok});await page.close();
 }
 await browser.close();fs.writeFileSync(`${out}/browser.json`,JSON.stringify(records,null,2));
 console.log(JSON.stringify(records,null,2));if(records.some(r=>!r.ok))process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
