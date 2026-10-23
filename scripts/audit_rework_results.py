"""汇总全部成功与失败；逐字引文可查率不冒充专业准确率。"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.connectivity_schemas import ConnectivityRun
from backend.app.connectivity_engine import validate_refs

OUT = ROOT / 'outputs/rework-20261022'
records = []
for path in sorted(OUT.rglob('*.json')):
    if path.name not in {'calculation_only.json', 'single_model.json', 'three_agents.json'}:
        continue
    run = ConnectivityRun.model_validate_json(path.read_text(encoding='utf-8'))
    found = {o.occurrence_id: o for o in run.occurrences}
    refs = [ref for a in run.ai_analyses for ref in a.supporting_evidence + a.counter_evidence]
    invalid = [ref.model_dump() for ref in refs if not validate_refs([ref], found)]
    calls = [c for c in run.provider_calls if c.get('performed')]
    incoming = sum(c.get('input_tokens') or 0 for c in calls)
    outgoing = sum(c.get('output_tokens') or 0 for c in calls)
    # 当前官方价目支持缓存及峰谷价；旧记录缺少缓存分拆，因此只给区间，不造账单。
    row = dict(path=str(path.relative_to(ROOT)), run_id=run.run_id,
        mode=run.execution_mode, status=run.model_status, relations=len(run.checks),
        opinions=sum(a.status == 'current' for a in run.ai_analyses),
        calls=len(calls), input_tokens=incoming, output_tokens=outgoing,
        seconds=round(run.duration_ms / 1000, 3), citations=len(refs), invalid_citations=invalid,
        counter_refs=len({(r.occurrence_id, r.quote) for a in run.ai_analyses for r in a.counter_evidence}),
        estimated_usd_range=[round((incoming*.003+outgoing*.6)/1e6, 6),
                             round((incoming*.3+outgoing*1.2)/1e6, 6)],
        cost_status='published_rate_range_not_invoice',
        failures=[c.get('failure_code') for c in run.provider_calls if c.get('failure_code')],
        citation_scope='仅校验逐字引文存在；不代表引用充分或专业判断正确',
        professional_accuracy=None,
        rejected_outputs=[r for s in run.agent_steps for key in ['rejected', 'analysis_rejections'] for r in s.get(key, [])],
        tool_requests=run.overview.get('collaboration', {}).get('tool_requests', 0),
        new_evidence_ids=run.overview.get('collaboration', {}).get('new_evidence_ids', []))
    records.append(row)
(OUT/'audit-results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
for row in records:
    print(json.dumps({k:v for k,v in row.items() if k not in {'rejected_outputs', 'invalid_citations'}}, ensure_ascii=False))
