const {chromium}=require('playwright');
const fs=require('fs');
const out='outputs/home-zoom-fix-20261017';
const base=process.env.BASE||'http://127.0.0.1:8796';
async function bounds(page,id){return page.locator('#world-'+id).evaluate(c=>{
 const r=c.getBoundingClientRect(),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
 let l=c.width,t=c.height,b=0,rr=0;
 for(let y=0;y<c.height;y+=2)for(let x=0;x<c.width;x+=2)if(d[(y*c.width+x)*4+3]>240){l=Math.min(l,x);rr=Math.max(rr,x);t=Math.min(t,y);b=Math.max(b,y);}
 return {cx:(l+rr)/2/c.width*r.width,cy:(t+b)/2/c.height*r.height,width:(rr-l)/c.width*r.width,height:(b-t)/c.height*r.height};
});}
(async()=>{
 fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({channel:'msedge',headless:true});const rows=[];
 for(const [width,height]of[[1440,1000],[1024,768],[768,1024],[390,844]]){
  const page=await browser.newPage({viewport:{width,height},reducedMotion:'reduce'});const errors=[],failed=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  page.on('requestfailed',r=>failed.push(r.url()));page.on('response',r=>{if(r.status()>=400)failed.push(r.status()+':'+r.url());});
  await page.goto(base+'/#top',{waitUntil:'networkidle'});await page.waitForTimeout(2000);
  await page.screenshot({path:`${out}/home-${width}.png`});const models=[];
  for(const[id,name]of[['a','left'],['b','right']]){
   const before=await bounds(page,name);
   await page.locator(`[data-model="${id}"][data-model-action="zoom-in"]`).click();await page.waitForTimeout(1200);
   const enlarged=await bounds(page,name);await page.screenshot({path:`${out}/${name}-zoom-${width}.png`});
   await page.locator(`[data-model="${id}"][data-model-action="zoom-out"]`).click();await page.waitForTimeout(1200);
   const restored=await bounds(page,name);
   await page.locator('#model-'+name).focus();await page.keyboard.press('+');await page.waitForTimeout(1200);
   await page.keyboard.press('Home');await page.waitForTimeout(1200);const reset=await bounds(page,name);
   models.push({id,before,enlarged,restored,reset,resetDrift:Math.hypot(reset.cx-before.cx,reset.cy-before.cy),roundTripDrift:Math.hypot(restored.cx-before.cx,restored.cy-before.cy)});
  }
  await page.locator('[data-enter-connectivity]').first().click();await page.waitForFunction(()=>document.querySelector('#cn-pair').options.length>0);
  const removed=await page.locator('#cn-history').count()===0,ready=!(await page.locator('#cn-run').isDisabled());
  await page.screenshot({path:`${out}/workspace-${width}.png`});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  rows.push({width,height,models,removed,ready,overflow,errors,failed});await page.close();
 }
 await browser.close();fs.writeFileSync(`${out}/browser.json`,JSON.stringify(rows,null,2));console.log(JSON.stringify(rows,null,2));
 if(rows.some(r=>!r.removed||!r.ready||r.overflow||r.errors.length||r.failed.length||r.models.some(m=>m.roundTripDrift>3||m.resetDrift>3)))process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
