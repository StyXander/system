"""财务穿透规则/单模型/多智能体实验；模型臂通过正式API，默认禁止付费。"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
import time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.connectivity_extraction import load_registry
from backend.app.financial_impact import build


def selected_pairs(wanted=None):
    documents=load_registry(ROOT)
    keys=list(dict.fromkeys(doc.case_id for doc in documents))
    if not wanted:
        wanted=['000858-2025','600019-2025','300750-2025','000333-2025']
    result=[]
    for query in wanted:
        matches=[key for key in keys if key==query or any(doc.case_id==key and f'{doc.company_id}-{doc.period}'==query for doc in documents)]
        if len(matches)!=1:raise ValueError(f'报告对必须唯一登记：{query}')
        if matches[0] not in result:result.append(matches[0])
    return [(key,[doc for doc in documents if doc.case_id==key]) for key in result]


def run_rule_arm(pairs,max_events,out):
    results=[]
    for pair_id,documents in pairs:
        began=time.monotonic()
        try:
            payload=build(ROOT,documents=documents,max_events=max_events)
            target=out/f'rule-{pair_id}.json'
            target.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
            results.append({'pair_id':pair_id,'company':documents[0].company,'status':'completed',
                'duration_ms':round((time.monotonic()-began)*1000),'raw_file':target.name,**payload['stats'],
                'source_hashes':{doc.document_id:doc.file_sha256 for doc in documents},'provider_calls':0})
        except Exception as error:
            results.append({'pair_id':pair_id,'status':'failed','error':type(error).__name__+': '+str(error)[:180]})
    return {'arm':'rule_only','status':'completed' if all(row['status']=='completed' for row in results) else 'partial','results':results}


def model_arm(name,pairs,args,out):
    if not args.allow_models:
        return {'arm':name,'status':'not_run','reason':'本轮没有付费授权；默认不请求模型'}
    if args.max_calls is None or args.token_budget is None:
        raise ValueError('模型实验必须显式指定每臂max-calls与token-budget')
    mode='single_model' if name=='single_model' else 'three_agents'
    records=[]
    with httpx.Client(base_url=args.base_url,timeout=90) as client:
        bootstrap=client.get('/api/connectivity/bootstrap');bootstrap.raise_for_status()
        for pair_id,documents in pairs:
            began=time.monotonic()
            response=client.post('/api/connectivity/runs',json={'pair_id':pair_id,'mode':mode,
                'model_scope':'financial_impact','max_model_calls':args.max_calls,'token_stop_threshold':args.token_budget})
            if response.status_code>=400:
                records.append({'pair_id':pair_id,'status':'blocked','http_status':response.status_code,'detail':response.json()})
                continue
            task=response.json();deadline=time.monotonic()+args.timeout
            while task['status'] in {'queued','running'} and time.monotonic()<deadline:
                time.sleep(2)
                response=client.get('/api/connectivity/runs/'+task['task_id']);response.raise_for_status();task=response.json()
            target=out/f'{name}-{pair_id}.json';target.write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
            run=task.get('result') or {};calls=run.get('provider_calls',[])
            records.append({'pair_id':pair_id,'task_id':task['task_id'],'task_status':task['status'],
                'status':run.get('financial_impact',{}).get('agents',{}).get('model_status','not_completed'),
                'raw_file':target.name,'duration_ms':round((time.monotonic()-began)*1000),
                'actual_calls':sum(bool(call.get('performed')) for call in calls),
                'input_tokens':sum(call.get('input_tokens') or 0 for call in calls),
                'output_tokens':sum(call.get('output_tokens') or 0 for call in calls),'cost':None,
                'cost_note':'记录真实用量，人民币账单未核对',
                'stats':run.get('financial_impact',{}).get('stats',{})})
    return {'arm':name,'status':'completed' if records and all(row['status']=='completed' for row in records) else 'partial','results':records}


def label_packet(rule,out):
    samples=[]
    for result in rule['results']:
        if result['status']!='completed':continue
        raw=json.loads((out/result['raw_file']).read_text(encoding='utf-8'))
        for event in raw['events']:
            samples.append({'sample_id':result['pair_id']+':'+event['event_id'],'pair_id':result['pair_id'],
                'event':event,'candidate_relations':[r for r in raw['relations'] if r['event_id']==event['event_id']],
                'label':None,'relevant_item_ids':None,'relevant_page_refs':None,'relation_keys':None,'correct_rule_ids':None,'should_abstain':None,'reviewer':None,'provenance':'unreviewed',
                'source_hashes':result['source_hashes']})
    return {'schema':'financial_label_packet_v1','status':'not_completed','samples':samples,
        'notice':'原文候选不是正确标签。逐页复核后由会计专业人员独立标注；模型和程序不能代填真人标签。'}


def evaluate_labels(path,rule,out):
    if not path:return {'status':'not_completed','metrics':None,'reason':'没有独立会计专业人工标注'}
    from backend.app.financial_impact.evaluation import evaluate
    packet=json.loads(Path(path).read_text(encoding='utf-8'))
    results=[]
    for row in rule.get('results',[]):
        if not row.get('raw_file'):continue
        raw=json.loads((out/row['raw_file']).read_text(encoding='utf-8'))
        payload=raw.get('result',{}).get('financial_impact',{}) if 'task_id' in raw else raw
        hashes=row.get('source_hashes') or {doc['document_id']:doc['file_sha256'] for doc in raw.get('result',{}).get('documents',[])}
        results.append({'pair_id':row['pair_id'],**evaluate(payload,packet,row['pair_id'],hashes)})
    return {'status':'evaluated' if results else 'not_completed','results':results}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pair',action='append')
    parser.add_argument('--max-events',type=int,default=14)
    parser.add_argument('--allow-models',action='store_true')
    parser.add_argument('--max-calls',type=int,choices=range(1,13))
    parser.add_argument('--token-budget',type=int)
    parser.add_argument('--timeout',type=int,default=1200)
    parser.add_argument('--base-url',default='http://127.0.0.1:8893')
    parser.add_argument('--labels')
    parser.add_argument('--out',default=str(ROOT/'outputs/financial-impact-acceptance/experiment'))
    args=parser.parse_args()
    if args.token_budget is not None and not 1000<=args.token_budget<=120000:parser.error('每臂停止线限1000到120000 Token')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    pairs=selected_pairs(args.pair);rule=run_rule_arm(pairs,args.max_events,out)
    labels=label_packet(rule,out);(out/'annotation-packet.json').write_text(json.dumps(labels,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'schema':'financial_impact_experiment_v2','generated_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'protocol':'相同登记原件、程序抽取底座和预算；仅比较单角色与三角色的财务调查。六项规则仍计算，但旧数值模型角色不占实验额度。',
        'rule_only':rule,'single_model':model_arm('single_model',pairs,args,out),
        'multi_agent':model_arm('multi_agent',pairs,args,out),'labels':evaluate_labels(args.labels,rule,out),
        'boundary':'未执行模型臂或没有专业标签时不计算技术提升；离线替身不进入真实用量或企业统计。'}
    report['labels_by_arm']={name:evaluate_labels(args.labels,report[name],out) for name in ('rule_only','single_model','multi_agent')}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'rule_pairs':len(rule['results']),'single':report['single_model']['status'],
        'multi':report['multi_agent']['status'],'labels':report['labels']['status']},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
