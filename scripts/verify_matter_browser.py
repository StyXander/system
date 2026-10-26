"""本机合成端到端验收；运行真实API/页面，明确注入测试提供方，禁止外网。"""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'backend/tests')]
os.environ.update(AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE='local',AUDITTRACE_DEMO_TASK_PERSISTENCE='local',AUDITTRACE_PUBLIC_DEMO='false')
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright
from pytest import MonkeyPatch
import uvicorn
from backend.app.connectivity_api import build_router
from backend.app.connectivity_catalog_api import build_catalog_router
from backend.app import connectivity_matter_pipeline as pipeline
from test_matter_connectivity import reports,fake_provider


def main():
    output=ROOT/'outputs/matter-browser-20261026';output.mkdir(parents=True,exist_ok=True)
    result={'origin':'synthetic_engineering_only','real_model_calls':0,'viewports':[],'errors':[]}
    monkey=MonkeyPatch()
    with tempfile.TemporaryDirectory(prefix='audittrace-matter-browser-') as directory:
        workspace,report_set=reports.__wrapped__(Path(directory),monkey)
        original=pipeline.run_matter_pipeline
        monkey.setattr(pipeline,'run_matter_pipeline',lambda *args,**kwargs:original(*args,**kwargs,caller=fake_provider))
        app=FastAPI();app.mount('/assets',StaticFiles(directory=ROOT/'assets'))
        app.include_router(build_router(workspace,lambda request:None,lambda:None));app.include_router(build_catalog_router(workspace))
        @app.get('/')
        def index():return FileResponse(ROOT/'index.html')
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error'))
        worker=threading.Thread(target=server.run,daemon=True);worker.start()
        for _ in range(200):
            if server.started:break
            time.sleep(.025)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=os.getenv('AUDITTRACE_TEST_CHROMIUM') or None,args=['--no-sandbox','--disable-dev-shm-usage'])
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror',lambda error:result['errors'].append(str(error)))
            page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(f'http://127.0.0.1:{port}/') else route.abort())
            page.goto(f'http://127.0.0.1:{port}/',wait_until='networkidle')
            assert page.locator('#world').is_visible()
            page.screenshot(path=str(output/'home.png'),full_page=False)
            assert page.locator('#connectivity-root').is_visible()
            page.locator('[data-enter-connectivity]').first.click()
            assert page.locator('.cn-sidebar').is_visible()
            assert page.locator('.cn-sidebar').evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(25, 59, 52)'
            page.wait_for_selector('#cm-documents input')
            assert page.locator('#cn-mode').input_value()=='five_agents'
            assert page.locator('#cm-documents input:checked').count()==6
            page.locator('#cm-as-of').fill('2026-10-26')
            page.screenshot(path=str(output/'setup.png'),full_page=False)
            page.locator('#cn-run').click()
            page.wait_for_selector('#cn-matter-results h2',timeout=30000)
            page.wait_for_function("document.querySelector('#cn-matter-results')?.textContent.includes('五Agent部分完成')",timeout=30000)
            page.wait_for_timeout(300)
            task_id=page.evaluate("new URL(location.href).searchParams.get('connectivity_task')")
            saved=page.request.get(f'http://127.0.0.1:{port}/api/connectivity/runs/{task_id}').json()
            assert saved['result']['dataset_role']=='synthetic'
            assert len(saved['result']['provider_calls'])>=6
            assert {t['role'] for t in saved['result']['matter_tasks']}=={'A1','A2','A3','A4','A5'}
            # 挑选已归并事项，主张/机制/假设和反证均来自保存结果。
            identified=next(m for m in saved['result']['matters'] if m['identity_status']=='evidence_linked')
            page.locator('[data-cm-select="'+identified['matter_id']+'"]').click()
            assert page.locator('.cm-detail').inner_text().find('候选机制')>=0
            assert page.locator('.cm-detail').inner_text().find('区分证据')>=0
            for width,height in [(1440,1000),(1024,900),(768,1024),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                page.screenshot(path=str(output/f'result-{width}.png'),full_page=True)
                overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                assert not overflow,f'{width}有横向溢出'
                result['viewports'].append({'width':width,'overflow':overflow,'result_visible':page.locator('#cn-matter-results').is_visible()})
            late=browser.new_page(viewport={'width':1440,'height':1000})
            late.route('**/connectivity-matters.js*',lambda route:route.abort())
            late.goto(f'http://127.0.0.1:{port}/',wait_until='networkidle')
            late.unroute('**/connectivity-matters.js*')
            late.add_script_tag(url=f'http://127.0.0.1:{port}/assets/official-v4/connectivity-matters.js')
            late.wait_for_selector('#cm-documents input',state='attached')
            assert late.locator('.cm-setup').count()==1
            late.add_script_tag(url=f'http://127.0.0.1:{port}/assets/official-v4/connectivity-matters.js')
            assert late.locator('.cm-setup').count()==1
            result['late_script_initialization']='passed'
            late.close()
            page.set_viewport_size({'width':1440,'height':1000})
            page.locator('[data-at-stage="3"]').first.click()
            page.screenshot(path=str(output/'result-top.png'),full_page=False)
            page.locator('[data-at-stage="2"]').first.click()
            page.screenshot(path=str(output/'collaboration.png'),full_page=False)
            page.locator('[data-at-stage="4"]').first.click()
            assert page.locator('#cn-matter-evidence').is_visible()
            assert page.locator('#cn-matter-evidence .cm-evidence').count()>0
            page.locator('#cn-matter-evidence').scroll_into_view_if_needed()
            page.screenshot(path=str(output/'evidence.png'),full_page=False)
            # 导出与页面保存版本一致，不产生追加模型调用。
            for fmt in ('json','csv','docx'):
                response=page.request.get(f'http://127.0.0.1:{port}/api/connectivity/runs/{task_id}/export/{fmt}')
                assert response.ok
                (output/f'synthetic-export.{fmt}').write_bytes(response.body())
            after=page.request.get(f'http://127.0.0.1:{port}/api/connectivity/runs/{task_id}').json()
            assert len(after['result']['provider_calls'])==len(saved['result']['provider_calls'])
            result.update(task_id=task_id,provider_records=len(saved['result']['provider_calls']),status='passed')
            browser.close()
        server.should_exit=True;worker.join(timeout=5)
    monkey.undo()
    (output/'browser-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
    assert not result['errors']


if __name__=='__main__':main()
