"""本地浏览器验收服务：仅合成PDF与注入的测试提供方，不调用外部模型。

启动：python scripts/task_center_acceptance_server.py --port 8877 --role-delay 2
终端保留实际HTTP时长、响应字节、缓存命中日志；不得作为真实模型验收。
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import logging
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(AUDITTRACE_SINGLE_USER='true',AUDITTRACE_PUBLIC_DEMO='false',
    AUDITTRACE_DEMO_TASK_PERSISTENCE='local',AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE='local')

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pytest import MonkeyPatch
import uvicorn
from backend.app import connectivity_api as api, connectivity_matter_pipeline as pipeline
from backend.app.connectivity_catalog_api import build_catalog_router
from backend.app.demo_run_tasks import DemoRunTaskStore
from backend.tests.test_matter_connectivity import reports, fake_provider


@contextmanager
def acceptance_app(role_delay=2):
    with tempfile.TemporaryDirectory(prefix='audittrace-task-center-') as tmp:
        monkey=MonkeyPatch();root,report_set=reports.__wrapped__(Path(tmp),monkey)
        store=DemoRunTaskStore(root/'tasks',task_id_prefix='CONNJOB')
        monkey.setattr(api,'DemoRunTaskStore',lambda *a,**k:store)
        original=pipeline.run_matter_pipeline
        def synthetic_provider(role,payload):
            time.sleep(role_delay)
            return fake_provider(role,payload)
        monkey.setattr(pipeline,'run_matter_pipeline',lambda *a,**k:original(*a,**k,caller=synthetic_provider))
        from backend.app.connectivity_schemas import RunRequest
        seed=original(root,RunRequest(report_set_id=report_set.report_set_id,mode='calculation_only'))
        for suffix in ('B','C'):
            history=seed.model_copy(deep=True);history.company=f'合成历史 {suffix}';history.dataset_role='synthetic'
            history.run_id='CONN-SYNTHETIC-'+suffix
            item=store._new_task(report_set.report_set_id,{'kind':'connectivity','analysis_scope':'matter_connectivity','company':history.company})
            item.update(status='completed',result=history.model_dump(mode='json'));store._tasks[item['task_id']]=item
        app=FastAPI();app.mount('/assets',StaticFiles(directory=ROOT/'assets'))
        app.include_router(api.build_router(root,lambda _:None,lambda:None));app.include_router(build_catalog_router(root))
        @app.middleware('http')
        async def timing(request,call_next):
            start=time.perf_counter();response=await call_next(request)
            if '/api/connectivity/runs' in request.url.path:
                ms=(time.perf_counter()-start)*1000;response.headers['Server-Timing']=f'app;dur={ms:.2f}'
                logging.info('acceptance_http method=%s path=%s status=%s duration_ms=%.2f bytes=%s',request.method,request.url.path,response.status_code,ms,response.headers.get('content-length','stream'))
                if getattr(app.state,'acceptance_log',None):
                    with app.state.acceptance_log.open('a') as handle:
                        handle.write(f'acceptance_http method={request.method} path={request.url.path} status={response.status_code} duration_ms={ms:.2f} bytes={response.headers.get("content-length","stream")}\n')
            return response
        @app.get('/')
        def home():return FileResponse(ROOT/'index.html')
        @app.get('/api/health')
        def health():return {'origin':'synthetic_engineering_only','real_model_calls':0}
        try:yield app
        finally:store.shutdown();monkey.undo()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8877)
    parser.add_argument('--role-delay',type=float,default=2)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    with acceptance_app(args.role_delay) as app:
        uvicorn.run(app,host='0.0.0.0',port=args.port,log_level='info')


if __name__=='__main__':main()
