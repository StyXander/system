"""End-to-end screenshot acceptance using REAL registered Baosteel PDF files, no model."""
import json
import os
import socket
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.environ.update(AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE='local',
                  AUDITTRACE_DEMO_TASK_PERSISTENCE='local',
                  AUDITTRACE_PUBLIC_DEMO='false')
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright
import uvicorn
from backend.app.connectivity_api import build_router

def main():
    app=FastAPI()
    app.mount('/assets',StaticFiles(directory=ROOT/'assets'),name='assets')
    app.include_router(build_router(ROOT,lambda request:None,lambda:None))
    @app.get('/')
    def index():return FileResponse(ROOT/'index.html')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning'))
    worker=threading.Thread(target=server.run,daemon=True)
    worker.start()
    for _ in range(200):
        if server.started:break
        time.sleep(0.025)
    if not server.started:raise AssertionError('server did not start')
    out=ROOT/'outputs'/'baosteel-browser'
    out.mkdir(parents=True,exist_ok=True)
    report={'evidence':[],'viewports':[],'errors':[]}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(f'http://127.0.0.1:{port}/') else route.abort())
        page.goto(f'http://127.0.0.1:{port}/?demo=baosteel',wait_until='domcontentloaded',timeout=60000)
        page.wait_for_selector('#ba-demo:not([hidden])',timeout=25000)
        page.wait_for_function("document.querySelector('#ba-message')?.textContent.includes('资料索引已返回')",timeout=160000)
        assert page.locator('.ba-evidence').count()>=4
        assert page.locator('#ba-output').inner_text().find('240078904.49')>=0
        assert page.locator('#ba-output').inner_text().find('1087415200.00')>=0
        assert page.locator('#ba-output').inner_text().find('0.00')>=0
        for width,height in ((1440,900),(1024,900),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            page.screenshot(path=str(out/f'baosteel-{width}.png'),full_page=True)
            overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
            report['viewports'].append({'width':width,'overflow':overflow})
            assert not overflow,f'Unexpected horizontal overflow at {width}'
        report['source_links']=page.locator('.ba-evidence-meta a').count()
        report['evidence']=[e.inner_text() for e in page.locator('.ba-evidence-meta').all()[:6]]
        print('BAOSTEEL_BROWSER',json.dumps(report,ensure_ascii=False),flush=True)
        assert not report['errors'],report['errors']
        browser.close()
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    server.should_exit=True
if __name__=='__main__':main()
