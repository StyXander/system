"""同报告同事项的三模式实测，真实模型费用与运行状态分别保存。"""
from pathlib import Path
import json
import sys
import time
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
# 本机独立验收使用本地持久额度账本，生产配置保持原样；不绕过每日预算。
os.environ['AUDITTRACE_DEMO_TASK_PERSISTENCE'] = 'local'
from backend.app.connectivity_pipeline import run_pipeline
from backend.app.connectivity_schemas import RunRequest
from backend.app.connectivity_delivery import export_run
from backend.app.main import _public_model_ledger

PAIR = os.getenv('EXPERIMENT_PAIR', '000858-2025')
TOPIC = os.getenv('EXPERIMENT_TOPIC', 'research')
GROUP = os.getenv('EXPERIMENT_GROUP', 'natural')
OUT = ROOT / 'outputs/rework-20261022' / GROUP / (PAIR + '-' + TOPIC)
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('CONNECTIVITY_TOKEN_STOP_THRESHOLD', '180000')
summary = []
for mode in os.getenv('EXPERIMENT_MODES', 'calculation_only,three_agents,single_model').split(','):
    reservation = None
    run = None
    def reserve():
        global reservation
        reservation = _public_model_ledger().reserve_batch('final-20261022')
    def checkpoint(current):
        (OUT / f'{mode}-partial.json').write_text(current.model_dump_json(indent=2), encoding='utf-8')
    print('START', mode, flush=True)
    try:
        run = run_pipeline(ROOT, RunRequest(pair_id=PAIR, topics=[TOPIC], mode=mode),
            before_model=reserve,
            checkpoint=checkpoint,
            progress=lambda *a: print(mode, *a, flush=True),
            agent_progress=lambda *a: print(mode, *a, flush=True))
        (OUT / f'{mode}.json').write_text(run.model_dump_json(indent=2), encoding='utf-8')
        payload, _ = export_run(run, 'docx')
        (OUT / f'{mode}.docx').write_bytes(payload)
        row = {'mode': mode, 'pair': PAIR, 'topic': TOPIC, 'group': GROUP,
            'token_stop_threshold': int(os.getenv('CONNECTIVITY_TOKEN_STOP_THRESHOLD', '0')),
            'run_id': run.run_id, 'model_status': run.model_status,
            'relations': len(run.checks), 'ai_opinions': len([a for a in run.ai_analyses if a.status == 'current']),
            'provider_calls': len([c for c in run.provider_calls if c.get('performed')]),
            'successful_calls': len([c for c in run.provider_calls if c.get('status') == 'completed']),
            'input_tokens': sum(c.get('input_tokens') or 0 for c in run.provider_calls),
            'output_tokens': sum(c.get('output_tokens') or 0 for c in run.provider_calls),
            'duration_ms': run.duration_ms, 'collaboration': run.overview.get('collaboration'),
            'counter_evidence': len({(r.occurrence_id, r.quote) for a in run.ai_analyses for r in a.counter_evidence}),
            'models': sorted({c.get('model', '') for c in run.provider_calls}),
            'failures': [c.get('failure_code') for c in run.provider_calls if c.get('failure_code')]}
        summary.append(row)
        (OUT / 'comparison.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print('RESULT', json.dumps({k:v for k,v in row.items() if k!='collaboration'}, ensure_ascii=False), flush=True)
    finally:
        if reservation:
            partial = OUT / f'{mode}-partial.json'
            calls = run.provider_calls if run else json.loads(partial.read_text(encoding='utf-8')).get('provider_calls', []) if partial.exists() else []
            _public_model_ledger().settle(reservation, input_tokens=sum(c.get('input_tokens') or 0 for c in calls),
                output_tokens=sum(c.get('output_tokens') or 0 for c in calls))
