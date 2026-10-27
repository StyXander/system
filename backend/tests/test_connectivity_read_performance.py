import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.tests.test_matter_connectivity import reports
from backend.app.connectivity_api import build_router
from backend.app.connectivity_read_models import project_result
from backend.app.connectivity_source_cache import source_sha256, _cache
from backend.app.demo_run_tasks import DemoRunTaskStore, SupabaseDemoRunTaskStore


def test_hash_cache_hit_invalidation_and_force(tmp_path, monkeypatch):
    path=tmp_path/'source.pdf';path.write_bytes(b'original')
    real=Path.open;count=[]
    # 源码使用 open；计数真实二进制读，不用耗时阈值判缓存。
    import builtins
    original_open=builtins.open
    def counted(p,*args,**kwargs):
        if Path(p)==path and args and args[0]=='rb':count.append(p)
        return original_open(p,*args,**kwargs)
    monkeypatch.setattr(builtins,'open',counted)
    a=source_sha256(path);assert source_sha256(path)==a;assert len(count)==1
    path.write_bytes(b'replacement');b=source_sha256(path);assert b!=a;assert len(count)==2
    assert source_sha256(path,force=True)==b;assert len(count)==3


def test_status_and_layered_reads_do_not_call_full_get(tmp_path,monkeypatch):
    import backend.app.connectivity_api as api
    monkeypatch.setenv('AUDITTRACE_SINGLE_USER','true')
    store=DemoRunTaskStore(tmp_path/'tasks',task_id_prefix='CONNJOB')
    task_id='CONNJOB-ABCDEF123456'
    result={'run_id':'CONN-ABC','company':'测试企业','period':'2025','documents':[],
        'matter_schema_version':'matter_connectivity_v1','matters':[],
        'matter_evidence':[{'evidence_id':'secret','quote':'X'*100000}], 'model_status':'five_agents_partial'}
    item=store._new_task('case',{'kind':'connectivity','analysis_scope':'matter_connectivity','owner':'test'})
    item.update(task_id=task_id,status='running',result=result);store._tasks[task_id]=item
    monkeypatch.setattr(api,'DemoRunTaskStore',lambda *a,**k:store)
    app=FastAPI();app.include_router(build_router(tmp_path,lambda _:None,lambda:None))
    with TestClient(app) as client:
        original_get=store.get;store.get=Mock(wraps=original_get)
        response=client.get(f'/api/connectivity/runs/{task_id}/status')
        assert response.status_code==200
        assert 'result' not in response.json() and len(response.content)<2000
        assert store.get.call_count==0
        summary=client.get(f'/api/connectivity/runs/{task_id}/summary')
        assert summary.status_code==200 and 'matter_evidence' not in summary.json()['result']
        assert store.get.call_count==0
        # 完整兼容读取只 get 一次，snapshot 使用已有记录。
        result['matter_evidence']=[]
        response=client.get(f'/api/connectivity/runs/{task_id}')
        assert response.status_code==200 and store.get.call_count==1
    store.shutdown()


def test_remote_status_uses_projection_and_detail_uses_one_rpc():
    client=Mock();client.select_table.return_value=[{'task_id':'T','status':'running','kind':'connectivity','owner':'O','version':2}]
    store=SupabaseDemoRunTaskStore(client)
    view=store.get_projection('T')
    assert view['run_body']['owner']=='O'
    select=client.select_table.call_args.kwargs['select']
    assert '*' not in select and 'result' not in select.replace('result_expires_at','')
    client._request.return_value={'task_id':'T','result':{'matters':[{'matter_id':'M'}]}}
    store.get_projection('T','detail','M')
    assert client._request.call_count==1 and not client.get_demo_run_task.called
    assert client._request.call_args.kwargs['json_body']['p_matter_id']=='M'


def test_detail_projection_excludes_other_matters_and_evidence():
    run={'matter_schema_version':'v1','matters':[{'matter_id':'M1','evidence_ids':['E1']},{'matter_id':'M2','evidence_ids':['E2']}],
        'matter_evidence':[{'evidence_id':'E1','quote':'one'},{'evidence_id':'E2','quote':'two'}]}
    result=project_result(run,'detail','M1')
    assert [m['matter_id'] for m in result['matters']]==['M1']
    assert [e['evidence_id'] for e in result['matter_evidence']]==['E1']


def test_repeated_read_uses_cache_and_pdf_replacement_invalidates_api(reports,monkeypatch,caplog):
    import backend.app.connectivity_api as api
    from backend.tests.test_matter_connectivity import request as matter_request
    from backend.app.connectivity_matter_pipeline import run_matter_pipeline
    from backend.app.connectivity_schemas import RunRequest
    from backend.app.connectivity_extraction import source_path
    root,rs=reports;monkeypatch.setenv('AUDITTRACE_SINGLE_USER','true')
    run=run_matter_pipeline(root,RunRequest(report_set_id=rs.report_set_id,mode='calculation_only'))
    store=DemoRunTaskStore(root/'tasks',task_id_prefix='CONNJOB')
    item=store._new_task(rs.report_set_id,{'kind':'connectivity','analysis_scope':'matter_connectivity'})
    item.update(status='completed',result=run.model_dump(mode='json'));store._tasks[item['task_id']]=item
    monkeypatch.setattr(api,'DemoRunTaskStore',lambda *a,**k:store)
    app=FastAPI();app.include_router(build_router(root,lambda _:None,lambda:None))
    caplog.set_level('INFO')
    with TestClient(app) as c:
        url=f'/api/connectivity/runs/{item["task_id"]}/summary'
        assert c.get(url).status_code==200;caplog.clear()
        assert c.get(url).status_code==200
        assert any('connectivity_result cache=hit' in r.message for r in caplog.records)
        assert not any('source_hash cache=miss' in r.message for r in caplog.records)
        path=source_path(root,run.documents[0]);path.write_bytes(path.read_bytes()+b'changed')
        changed=c.get(url).json()['result']
        assert changed['versions']['source_validity']['status']=='invalid'
        caplog.clear();c.post(f'/api/connectivity/runs/{item["task_id"]}/revalidate-sources')
        assert any('forced=True' in r.message for r in caplog.records)
    store.shutdown()
