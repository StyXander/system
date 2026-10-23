"""验证并拍摄真实模型封存记录，清楚保留回放身份。"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/final-20261022/browser'
snapshot=json.loads((ROOT/'outputs/final-20261022/snapshot.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    results=[]
    for width,height in [(1440,1000),(390,844)]:
        context=browser.new_context(viewport={'width':width,'height':height},locale='zh-CN',reduced_motion='reduce')
        page=context.new_page(); errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(snapshot['url'],wait_until='networkidle')
        page.locator('#cn-collaboration li').first.wait_for(timeout=30000)
        page.locator('#cn-collaboration-title').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/f'collaboration-{width}.png'))
        view=context.request.get('http://127.0.0.1:8877/api/connectivity/runs/'+snapshot['task_id']).json()
        result=view['result']
        assert result['versions']['result_origin']=='historical_snapshot'
        assert result['model_status']=='three_agents_completed'
        assert result['overview']['collaboration']['tool_requests']==9
        assert result['overview']['collaboration']['feedback'][0]['stop_reason']=='no_new_evidence'
        overflow=page.evaluate('() => document.documentElement.scrollWidth>innerWidth')
        assert not errors and not overflow
        results.append({'width':width,'errors':errors,'overflow':overflow,'origin':'historical_snapshot','tool_requests':9})
        if width==1440:
            for fmt in ['json','csv','docx']:
                response=context.request.get('http://127.0.0.1:8877/api/connectivity/runs/'+snapshot['task_id']+'/export/'+fmt)
                assert response.status==200
                (OUT/f'live-snapshot-export.{fmt}').write_bytes(response.body())
        context.close()
    browser.close()
(OUT/'snapshot-acceptance.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results))
