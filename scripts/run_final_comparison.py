"""同一资料集合的离线/单模型/三角色/五角色对照；真实调用必须显式启用。"""
from __future__ import annotations
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def usage(calls,name):
    return sum(c.get(name) if c.get(name) is not None else
        (c.get(name.replace('_tokens','_token_upper_bound'),0) if c.get('request_attempted') else 0) for c in calls)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--report-set');source.add_argument('--pair')
    parser.add_argument('--as-of',type=date.fromisoformat,default=date.today())
    parser.add_argument('--allow-models',action='store_true',help='允许本次真实付费调用；不绕过额度')
    parser.add_argument('--local',action='store_true',help='显式选择独立本地账本；默认沿用环境持久化配置')
    parser.add_argument('--ablations',action='store_true',help='真实五Agent对照后追加移除跨期、移除反证的消融')
    parser.add_argument('--repeat',type=int,choices=range(1,6),default=1)
    parser.add_argument('--max-matters',type=int,choices=range(1,11),default=3)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/matter-comparison-20261026')
    args=parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    if args.local:
        os.environ['AUDITTRACE_DEMO_TASK_PERSISTENCE']='local'
        os.environ['AUDITTRACE_RUNTIME_NAMESPACE']='matter-comparison-20261026'
    if args.allow_models and not os.getenv('DEEPSEEK_API_KEY','').strip():parser.error('缺少真实供应商配置，未执行真实对照')
    from backend.app.connectivity_pipeline import run_pipeline
    from backend.app.connectivity_schemas import RunRequest
    from backend.app.connectivity_matter_schemas import InvestigationBudget
    from backend.app.connectivity_delivery import export_run
    from backend.app.main import _public_model_ledger
    args.output.mkdir(parents=True,exist_ok=True)
    modes=['calculation_only','single_model','three_agents','five_agents'] if args.allow_models else ['calculation_only']
    conditions=[(mode,'none') for mode in modes]
    if args.ablations and args.allow_models:conditions += [('five_agents','no_temporal'),('five_agents','no_counterevidence')]
    summary=[]
    for repeat in range(args.repeat):
        for mode,ablation in conditions:
            tag=mode if ablation=='none' else mode+'-'+ablation
            reservation=None;latest=None;run=None
            ledger=_public_model_ledger()
            def reserve():
                nonlocal reservation
                reservation=ledger.reserve_batch('matter-comparison-20261026')
            def checkpoint(value):
                nonlocal latest
                latest=value.model_copy(deep=True)
                (args.output/f'{repeat+1}-{tag}.checkpoint.json').write_text(value.model_dump_json(indent=2),encoding='utf-8')
            def provider_budget(value):
                if reservation:ledger.checkpoint_usage(reservation,input_tokens=usage(value.provider_calls,'input_tokens'),output_tokens=usage(value.provider_calls,'output_tokens'))
            body=RunRequest(pair_id=args.pair,report_set_id=args.report_set,as_of_date=args.as_of,
                analysis_scope='matter_connectivity',mode=mode,ablation=ablation,budget=InvestigationBudget(max_matters=args.max_matters))
            row={'repeat':repeat+1,'mode':mode,'ablation':ablation,'status':'failed','human_scoring':'not_run','professional_quality':'not_evaluated'}
            try:
                run=run_pipeline(ROOT,body,before_model=reserve,checkpoint=checkpoint,provider_budget=provider_budget,
                    progress=lambda *a:print(mode,*a,flush=True))
                (args.output/f'{repeat+1}-{tag}.json').write_text(run.model_dump_json(indent=2),encoding='utf-8')
                for fmt in ('csv','docx'):
                    content,_=export_run(run,fmt);(args.output/f'{repeat+1}-{tag}.{fmt}').write_bytes(content)
                row.update(status='recorded',run_id=run.run_id,model_status=run.model_status,report_set=run.report_set.model_dump(mode='json'),
                    matter_overview=run.matter_overview,provider_calls=len(run.provider_calls),successful_calls=sum(c.get('status')=='completed' for c in run.provider_calls),
                    input_tokens=sum(c.get('input_tokens') or 0 for c in run.provider_calls),output_tokens=sum(c.get('output_tokens') or 0 for c in run.provider_calls),
                    unknown_usage_calls=sum(c.get('request_attempted') and (c.get('input_tokens') is None or c.get('output_tokens') is None) for c in run.provider_calls),
                    duration_ms=run.duration_ms,cost=None,cost_note='无已验证计价，不估算费用')
            except Exception as error:row['failure']=type(error).__name__+': '+str(error)[:300]
            finally:
                if reservation:
                    calls=(run or latest).provider_calls if (run or latest) else []
                    try:ledger.settle(reservation,input_tokens=usage(calls,'input_tokens'),output_tokens=usage(calls,'output_tokens'))
                    except Exception as error:row['quota_settlement_error']=type(error).__name__
                summary.append(row)
                (args.output/'comparison.json').write_text(json.dumps({'origin':'actual_execution_records','comparison_status':'real_models_requested' if args.allow_models else 'offline_only',
                    'not_run_modes':[] if args.allow_models else ['single_model','three_agents','five_agents'],'runs':summary},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 1 if any(r['status']=='failed' for r in summary) else 0


if __name__=='__main__':raise SystemExit(main())
