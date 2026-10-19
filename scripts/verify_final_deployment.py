"""核验最终提交身份、线上资源及已保存任务跨部署读取；只发GET，不调用模型。"""
from pathlib import Path
import argparse, hashlib, json, subprocess, time
import httpx
ROOT=Path(__file__).resolve().parents[1]

def verify(expected, task_id):
    output=ROOT/'outputs/ai4/production'
    output.mkdir(parents=True,exist_ok=True)
    report={'expected_commit':expected,'task_id':task_id,'polls':[],'new_model_calls':0}
    files=['index.html','assets/official-v4/connectivity.js','assets/official-v4/connectivity-status.js','assets/official-v4/connectivity-results.css','assets/official-v4/connectivity-workspace.js']
    base='https://audittrace-demo.onrender.com'
    deadline=time.monotonic()+900
    with httpx.Client(timeout=45,trust_env=False,headers={'Cache-Control':'no-cache'}) as client:
        while time.monotonic()<deadline:
            try:
                response=client.get(base+'/api/status')
                actual=response.json().get('deployment',{}).get('commit') if response.status_code==200 else None
                report['polls'].append({'http':response.status_code,'commit':actual})
                print(json.dumps(report['polls'][-1]),flush=True)
                if actual==expected:
                    break
            except (httpx.HTTPError,ValueError) as error:
                report['polls'].append({'error':type(error).__name__})
            time.sleep(20)
        else:
            raise TimeoutError('目标提交尚未线上确认；未宣称部署成功')
        report['actual_commit']=actual
        report['health_http']=client.get(base+'/api/health').status_code
        boot=client.get(base+'/api/connectivity/bootstrap').json()
        report['intelligence_version']=boot['intelligence_version']
        assert boot['intelligence_version']=='hybrid_v3_claim_ledger'
        resources=[]
        for name in files:
            url=base+('/' if name=='index.html' else '/'+name)+'?verification='+expected[:12]
            response=client.get(url)
            source=subprocess.check_output(['git','show',expected+':'+name],cwd=ROOT)
            row={'file':name,'http':response.status_code,'expected_sha256':hashlib.sha256(source).hexdigest(),'actual_sha256':hashlib.sha256(response.content).hexdigest()}
            row['match']=row['http']==200 and row['expected_sha256']==row['actual_sha256']
            resources.append(row)
        report['resources']=resources
        assert all(row['match'] for row in resources)
        task_response=client.get(base+'/api/connectivity/runs/'+task_id)
        task_response.raise_for_status()
        task=task_response.json()
        assert task['status']=='completed' and task['result']['execution_mode']=='calculation_only'
        original=json.loads((output/'result.json').read_text(encoding='utf8'))
        assert task['result']['checks']==original['checks']
        report['run_id']=task['run_id']
        report['expires_at']=task['result_expires_at']
        report['retained_after_deploy']=True
        report['program_levels']=task['result']['overview']['program_levels']
        report['coverage_counts']=task['result']['overview']['coverage_counts']
        report['exports']={}
        for ext in ['json','csv','docx']:
            response=client.get(base+'/api/connectivity/runs/'+task_id+'/export/'+ext)
            report['exports'][ext]=response.status_code
            assert response.status_code==200
            if ext=='json':
                assert response.json()['checks']==original['checks']
        assert report['health_http']==200
        report['status']='passed'
    (output/'final-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'status':'passed','commit':expected,'task_id':task_id},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--commit',required=True)
    parser.add_argument('--task',required=True)
    args=parser.parse_args()
    verify(args.commit,args.task)
