"""真实本地HTTP与并发历史读取测量；提供方为显式合成注入，不是浏览器/真实模型验收。"""
import argparse
import concurrent.futures
import json
import logging
from pathlib import Path
import sys
import threading
import time

import httpx
import uvicorn
from task_center_acceptance_server import acceptance_app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    logfile=args.output.with_suffix('.log')
    logging.basicConfig(filename=logfile,filemode='w',level=logging.INFO,format='%(asctime)s %(message)s')
    with acceptance_app(role_delay=.4) as app:
        app.state.acceptance_log=logfile
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8878,log_level='warning',access_log=False))
        worker=threading.Thread(target=server.run,daemon=True);worker.start()
        try:
            with httpx.Client(base_url='http://127.0.0.1:8878/api/connectivity',trust_env=False) as client:
                for _ in range(100):
                    if server.started:break
                    time.sleep(.05)
                client.get('/bootstrap');rs=client.get('/report-sets').json()['items'][0]
                created=client.post('/runs',json={'report_set_id':rs['report_set_id'],'mode':'calculation_only'}).json();tid=created['task_id']
                def wait(id):
                    for _ in range(200):
                        status=client.get(f'/runs/{id}/status').json()
                        if status['status'] not in ['queued','running']:return status
                        time.sleep(.05)
                    raise TimeoutError('本地任务未在10秒内结束')
                wait(tid);screen=client.get(f'/runs/{tid}/summary').json()
                candidates=screen['result']['matters']
                m=next((m for m in candidates if m['matter_type']=='transition_project'),candidates[0])
                fresh=client.post('/runs',json={'report_set_id':rs['report_set_id'],'mode':'five_agents','selected_matter_ids':[m['matter_id']]}).json();aid=fresh['task_id']
                rows=client.get('/runs?limit=10').json()['items']
                histories=[next(r['task_id'] for r in rows if r['company']==f'合成历史 {s}') for s in ('B','C')]
                def read(path):
                    start=time.perf_counter();response=client.get(path)
                    return {'path':path,'status':response.status_code,'bytes':len(response.content),
                        'rtt_ms':round((time.perf_counter()-start)*1000,2),'server_timing':response.headers.get('server-timing')}
                samples=[]
                for _ in range(3):
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        samples.extend(pool.map(read,[f'/runs/{aid}/status',*[f'/runs/{id}/summary' for id in histories]]))
                    time.sleep(.15)
                status=wait(aid);final=client.get(f'/runs/{aid}').json();run=final['result']
                selected=run['versions']['investigation_scope']['selected_matter_ids'][0]
                detail=read(f'/runs/{aid}/matters/{selected}');detail_cached=read(f'/runs/{aid}/matters/{selected}')
                output={'origin':'synthetic_engineering_only','browser_verified':False,'real_model_calls':0,
                    'task_id':aid,'status':status['status'],'model_status':run['model_status'],'calls':len(run['provider_calls']),
                    'remaining':run['versions']['budget']['remaining'],'roles':[{k:t.get(k) for k in ('role','status','run_id','task_id')} for t in run['matter_tasks']],
                    'prior_provider_calls':len(run['prior_provider_calls']),'parent_run_id':run['parent_run_id'],
                    'samples':samples,'detail':detail,'detail_cached':detail_cached}
                assert status['status']=='completed' and len(run['provider_calls'])==6
                assert {t['role'] for t in run['matter_tasks'] if t['status']=='completed'}=={'A1','A2','A3','A4','A5'}
                assert not run['parent_run_id'] and not run['prior_provider_calls']
                assert all(s['status']==200 for s in samples)
                args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2));print(json.dumps(output,ensure_ascii=False))
        finally:server.should_exit=True;worker.join(timeout=3)


if __name__=='__main__':main()
