"""用最新正文门禁复核本轮冻结原件；复用缓存，不重新发现或调用模型。"""
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE'] = 'local'
from backend.app.connectivity_catalog import list_pairs, record_execution, export_snapshot
from backend.app.connectivity_onboarding import prepare_pair
from backend.app.connectivity_schemas import ConnectivityRun

OUT = ROOT / 'outputs/enterprise-expansion'
records, _ = list_pairs(ROOT)
result = []
for before in records:
    ticker = before['company_id']
    found = json.loads((OUT / (ticker + '-discovery.json')).read_text(encoding='utf-8'))
    for field, kind in [('annual', 'AR'), ('sustainability', 'ESG')]:
        doc = next(d for d in before['documents'] if d['report_type'] == kind)
        pool = found['annual_candidates' if kind == 'AR' else 'sustainability_candidates']
        found[field] = next({**r, 'report_type': kind} for r in pool if r['source_url'] == doc['source_url'])
    after = prepare_pair(ROOT, found, industry=before.get('industry_profile') or before['industry'])
    assert before['pair_id'] == after['pair_id']
    assert [(d['document_id'], d['file_sha256']) for d in before['documents']] == [(d['document_id'], d['file_sha256']) for d in after['documents']]
    result.append({'pair_id': after['pair_id'], 'status': 'passed', 'inspection': after['inspection']})
    print(ticker, 'passed', flush=True)
model = OUT / 'real-model-task.json'
if model.exists():
    task = json.loads(model.read_text(encoding='utf-8'))
    record_execution(ROOT, ConnectivityRun.model_validate({key: value for key, value in task['result'].items()
        if key in ConnectivityRun.model_fields}), task['task_id'])
records, mode = list_pairs(ROOT)
export_snapshot(ROOT, records, mode)
(OUT / 'frozen-source-revalidation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'all_verified': len(result)}, ensure_ascii=False))
