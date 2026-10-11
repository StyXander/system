/* 实际界面展开受影响的引用说明，并打开同一运行的原文PDF。 */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const ctx=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 await ctx.addInitScript(()=>sessionStorage.setItem('audittrace_workspace_session_v2',JSON.stringify({origin:'fixed',task_id:'DEMO-RUN-478070609368',selection:{origin:'fixed',case_id:'CNINFO_000858_T0_20260430',company_name:'五粮液',ticker:'000858',report_years:[2025,2024]}})));
 const p=await ctx.newPage();p.setDefaultTimeout(45000);await p.goto('http://127.0.0.1:8031',{waitUntil:'networkidle'});
 if(await p.locator('#demo-enter-workspace').isVisible())await p.locator('#demo-enter-workspace').click();
 await p.waitForFunction(()=>!document.querySelector('#demo-result').hidden);
 await p.locator('summary').filter({hasText:'核验一条主张与关键数字'}).click();
 const link=p.locator('#demo-challenge-open-source');const href=await link.getAttribute('href');
 if(!href)throw Error('原文链接缺失');
 const popupPromise=p.waitForEvent('popup');await link.click();const popup=await popupPromise;await popup.waitForLoadState('domcontentloaded');
 const response=await ctx.request.get(new URL(href.split('#')[0],p.url()).href);const bytes=await response.body();
 if(!response.ok()||bytes.subarray(0,4).toString()!=='%PDF')throw Error('真实原文未返回PDF');
 await popup.close();
 await p.locator('summary').filter({hasText:'三个角色的完整输出'}).click();
 const label=p.getByText('已绑定引用，支持关系待复核',{exact:false});
 if(!(await label.count()))throw Error('受影响的引用标签未呈现');
 await label.first().scrollIntoViewIfNeeded();
 await p.screenshot({path:'outputs/finals-20261011-browser/semantic-label-source.png'});
 fs.writeFileSync('outputs/finals-20261011-browser/source-check.json',JSON.stringify({source_link:href,source_bytes:bytes.length,source_popup_opened:true,semantic_label_present:true,run_id:'RUN-V7-DCF895BC5377',model_calls:0},null,2));
 console.log('原文PDF与语义待复核标签检查通过');await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
