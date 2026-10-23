"""真实登记案例程序运行与答辩筛选；固定评分表示演示适配，不是企业风险。"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.connectivity_extraction import load_registry
from backend.app.connectivity_schemas import RunRequest
from backend.app.connectivity_pipeline import run_pipeline
from backend.app.connectivity_catalog import list_pairs, save_pair, export_snapshot


def evaluate(run, elapsed):
    """各分项有明确数量分母，不从企业披露好坏或风险高低打分。"""
    documents = {d.document_id for d in run.documents}
    refs = [o for o in run.occurrences if o.document_id in documents and o.pdf_page >= 1]
    finance = [e for e in run.financial_edges if e.get('esg_document_id') in documents
        and e.get('financial_document_id') in documents]
    # 历史桥接字段名兼容：节点本身也必须绑定当前两份文档。
    if not finance:
        finance = [e for e in run.financial_edges if e.get('claim_document_id') in documents and e.get('financial_document_id') in documents]
    direct = sum(e.get('status') == 'directly_supported' for e in run.financial_edges)
    performed = [c for c in run.provider_calls if c.get('performed')]
    scored = {
        '原件完整': {'value': 20 if len(documents) == 2 and all(d.file_sha256 and d.pages for d in run.documents) else 0, 'maximum': 20, 'basis': '两份登记原件均有哈希和页数，各10分'},
        '可复算检查': {'value': min(20, sum(bool(c.calculation) for c in run.checks) * 4), 'maximum': 20, 'basis': '每条保存程序计算过程的关系4分，上限20；不代表正式一致'},
        '财务路径': {'value': min(20, len(finance) * 2), 'maximum': 20, 'basis': '双方来源均属于当前报告对的财务候选每条2分，上限20；缺口边不计分，候选不等于因果或支持'},
        '原页解释': {'value': min(20, len({(o.document_id,o.pdf_page) for o in refs}) * 2), 'maximum': 20, 'basis': '可定位的不同报告页每页2分，上限20'},
        '真实智能体': {'value': 10 if run.model_status == 'three_agents_completed' and performed else 0, 'maximum': 10, 'basis': '本轮三角色实际成功才记10分，否则0'},
        '现场速度': {'value': 10 if elapsed <= 90 else 5 if elapsed <= 180 else 0, 'maximum': 10, 'basis': '本机该次程序运行≤90秒10分，≤180秒5分；不作线上速度承诺'},
    }
    return {'total': sum(v['value'] for v in scored.values()), 'dimensions': scored,
        'elapsed_seconds': round(elapsed, 2), 'checks': len(run.checks), 'financial_edges': len(finance),
        'direct_financial_edges': direct, 'model_status': run.model_status, 'provider_calls': len(performed),
        'outcomes': dict(Counter(c.conclusion_level for c in run.checks)),
        'occurrences': len(run.occurrences)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tickers', default='')
    parser.add_argument('--output', default='outputs/enterprise-expansion')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    os.environ['AUDITTRACE_DEMO_USE_EXTERNAL_MODEL'] = 'false'
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    docs = load_registry(ROOT)
    pairs = sorted({d.case_id for d in docs if not args.tickers or d.company_id in args.tickers.split(',')})
    results = []
    for pair in pairs:
        saved = out / (pair + '-calculation.json')
        began = time.perf_counter()
        try:
            if args.resume and saved.exists():
                from backend.app.connectivity_schemas import ConnectivityRun
                run = ConnectivityRun.model_validate(json.loads(saved.read_text(encoding='utf-8'))['run'])
                elapsed = json.loads(saved.read_text(encoding='utf-8'))['elapsed_seconds']
            else:
                run = run_pipeline(ROOT, RunRequest(pair_id=pair, mode='calculation_only'))
                elapsed = time.perf_counter() - began
                saved.write_text(json.dumps({'elapsed_seconds': elapsed, 'run': run.model_dump(mode='json')}, ensure_ascii=False), encoding='utf-8')
            assert not any(c.get('performed') for c in run.provider_calls)
            own = {d.document_id for d in run.documents}
            assert all(o.document_id in own for o in run.occurrences)
            assert all(m.occurrence_id in {o.occurrence_id for o in run.occurrences} for c in run.checks for m in c.members)
            result = {'pair_id': pair, 'company': run.company, 'company_id': run.documents[0].company_id,
                'period': run.period, 'status': 'completed', **evaluate(run, elapsed),
                'run_id': run.run_id, 'raw_file': saved.name,
                'raw_sha256': hashlib.sha256(saved.read_bytes()).hexdigest(), 'industry_context': run.industry_context}
            records, _ = list_pairs(ROOT)
            record = next((r for r in records if r['pair_id'] == pair), None)
            if record:
                record['last_program_run'] = {'run_id': run.run_id, 'status': 'completed', 'elapsed_seconds': round(elapsed, 2)}
                record['runnable_rules'] = sorted({c.rule_id for c in run.checks})
                record['demo_evaluation'] = result
                context = run.industry_context
                record['industry_profile'] = record.get('industry_profile') or record['industry']
                record['industry'] = context.get('industry') if context.get('source') == 'company_report' else '待核行业'
                record['industry_evidence'] = context
                save_pair(ROOT, record)
        except Exception as error:
            result = {'pair_id': pair, 'status': 'failed', 'error': f'{type(error).__name__}: {str(error)[:600]}'}
        results.append(result)
        (out / 'case-evaluation.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: result.get(k) for k in ('pair_id', 'company', 'status', 'checks', 'financial_edges', 'elapsed_seconds', 'error')}, ensure_ascii=False), flush=True)
    records, persistence = list_pairs(ROOT, refresh=True)
    export_snapshot(ROOT, records, persistence)


if __name__ == '__main__':
    main()
