#!/usr/bin/env python3
"""从用户已导出的运行JSON汇总真实耗时/失败；不请求网络或模型。"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics


def distribution(values):
    values=sorted(v for v in values if isinstance(v,(int,float)))
    return {'n':len(values),'p50_ms':statistics.median(values) if values else None,
            'p95_ms':values[max(0,math.ceil(len(values)*.95)-1)] if values else None,
            'max_ms':max(values) if values else None}


def summarize(paths):
    runs=[]
    stages=defaultdict(list)
    roles=defaultdict(list)
    failure_codes=Counter()
    for path in paths:
        body=json.loads(path.read_text())
        run=body.get('result') or body
        if not run.get('matter_schema_version'):
            raise ValueError(f'{path.name}不是事项运行导出')
        calls=run.get('provider_calls',[])
        for row in calls:
            roles[row.get('role','unknown')].append(row.get('duration_ms'))
            if row.get('failure_code'):failure_codes[row['failure_code']]+=1
        for stage,row in run.get('versions',{}).get('stage_timings',{}).items():
            stages[stage].append(row.get('duration_ms'))
        runs.append({'run_id':run['run_id'],'company':run.get('company'),'mode':run.get('execution_mode'),
            'model_status':run.get('model_status'),'duration_ms':run.get('duration_ms'),
            'dataset_role':run.get('dataset_role'),'actual_provider_responses':sum(bool(c.get('performed')) for c in calls),
            'attempts':len(calls),'input_tokens_known':sum(c['input_tokens'] for c in calls if isinstance(c.get('input_tokens'),int)),
            'output_tokens_known':sum(c['output_tokens'] for c in calls if isinstance(c.get('output_tokens'),int)),
            'calls_with_unknown_usage':sum(c.get('input_tokens') is None or c.get('output_tokens') is None for c in calls),
            'index_cache_hits':sum(bool(c.get('cache_hit')) for c in run.get('matter_coverage',[])),
            'documents':len(run.get('documents',[]))})
    return {'samples':runs,'duration':distribution([r['duration_ms'] for r in runs]),
        'stage_durations':{key:distribution(value) for key,value in stages.items()},
        'role_durations':{key:distribution(value) for key,value in roles.items()},'failure_codes':dict(failure_codes),
        'notice':'样本来自指定导出文件；不同企业、模式和环境需分组调用，不能直接据混合样本宣称提速。未知用量不补零。没有样本时指标为空。'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exports',nargs='+',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=summarize(args.exports)
    payload=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(payload)
    else:print(payload)
