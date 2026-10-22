"""真实后端四视口验收；离线模式取真实PDF，不伪造模型结果。"""
from pathlib import Path
import json
import time
import httpx
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/final-20261022/browser'
OUT.mkdir(parents=True,exist_ok=True)
BASE='http://127.0.0.1:8877'
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    for width,height in [(1440,1000),(1024,768),(768,1024),(390,844)]:
        context=browser.new_context(viewport={'width':width,'height':height},locale='zh-CN',reduced_motion='reduce',accept_downloads=True)
        page=context.new_page()
        errors=[]; failed=[]; bad=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('requestfailed',lambda req:failed.append({'url':req.url,'reason':req.failure}))
        page.on('response',lambda res:bad.append({'url':res.url,'status':res.status}) if res.status>=400 else None)
        page.goto(BASE,wait_until='networkidle')
        page.wait_for_function("() => document.querySelector('#cn-pair option[value=\"000858-2025\"]')")
        assert page.locator('#cn-mode').input_value()=='three_agents'
        page.screenshot(path=str(OUT/f'home-{width}.png'))
        page.locator('.hero-cta').click()
        page.locator('#cn-pair').select_option('000858-2025')
        page.locator('#cn-next').click()
        page.locator('.cn-advanced summary').click()
        page.locator('#cn-mode').select_option('calculation_only')
        page.locator('#cn-next').click()
        page.locator('#cn-run').click()
        page.wait_for_function("() => document.querySelector('#cn-results') && !document.querySelector('#cn-results').hidden",timeout=60000)
        page.wait_for_function("() => document.querySelector('#cn-agents')?.textContent.includes('not_requested') || document.querySelector('#cn-agents')?.textContent.includes('未调用模型')",timeout=60000)
        page.screenshot(path=str(OUT/f'result-{width}.png'),full_page=True)
        task_id=page.url.split('connectivity_task=')[1].split('&')[0].split('#')[0]
        payload=context.request.get(BASE+'/api/connectivity/runs/'+task_id).json()
        result=payload['result']
        assert result['execution_mode']=='calculation_only' and result['provider_calls']==[]
        assert result['overview']['collaboration']['tool_requests']==0
        for fmt in ['json','csv','docx']:
            res=context.request.get(BASE+f'/api/connectivity/runs/{task_id}/export/{fmt}')
            assert res.status==200,(fmt,res.status)
            if width==1440: (OUT/f'export.{fmt}').write_bytes(res.body())
        before=result['run_id']
        page.reload(wait_until='networkidle')
        page.wait_for_function("() => document.querySelector('#cn-agents')?.textContent.includes('未调用模型')",timeout=30000)
        restored=context.request.get(BASE+'/api/connectivity/runs/'+task_id).json()['result']
        assert restored['run_id']==before
        overflow=page.evaluate('() => document.documentElement.scrollWidth>innerWidth')
        item={'viewport':[width,height],'task_id':task_id,'relations':len(result['checks']),
            'overflow':overflow,'errors':errors,'failed_requests':failed,'http_errors':bad,'refresh_same_run':True}
        results.append(item)
        (OUT/'acceptance.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        assert not overflow and not errors and not bad and not failed,item
        context.close()
    browser.close()
print(json.dumps(results,ensure_ascii=True))
