"""冻结合成关系的程序基线；不联网、不生成真人标签或专业准确率。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.connectivity_engine import calculate
from app.connectivity_rules import RULES, required_conditions
from app.connectivity_schemas import DisclosureOccurrence, EvidenceRef, ComparisonCondition, RelationshipCheck, RelationshipMember


def evaluate():
    source = ROOT / 'backend/evaluation/connectivity/release_cases.json'
    data = json.loads(source.read_text(encoding='utf-8'))
    results = []
    for sample in data['samples']:
        if sample['expected'] is None:
            results.append({'id': sample['id'], 'status': 'unmeasured', 'reason': '需要AI1/AI2接口及双人专业标签，未用简单数值比较替代'})
            continue
        start = time.perf_counter()
        units = sample['units'] or ['万元'] * len(sample['values'])
        context = '合成企业2025年，同一统计范围。原文明示完整且互不重叠的组成关系、单位和公式。'
        rows = [DisclosureOccurrence(occurrence_id=f'SYN-{i}', document_id='SYN-AR' if role == 'left' else 'SYN-ESG' if role == 'right' else 'SYN',
                    pdf_page=1, label=f'合成成员{i}', value=value, unit=unit, currency='CNY', year='2025',
                    context=context, row_header='合成企业2025年')
                for i, (role, value, unit) in enumerate(zip(sample['roles'], sample['values'], units))]
        refs = [EvidenceRef(occurrence_id='SYN-0', quote='原文明示完整且互不重叠的组成关系、单位和公式')]
        operator = RULES[sample['rule']]['operator']
        check = RelationshipCheck(check_id=sample['id'], rule_id=sample['rule'], title='冻结合成关系', operator=operator,
                    members=[RelationshipMember(occurrence_id=row.occurrence_id, role=role) for row, role in zip(rows, sample['roles'])],
                    conditions=[ComparisonCondition(name=name, status='supported', evidence=refs, reason='合成前提') for name in required_conditions(operator)],
                    relationship_evidence=refs)
        if sample['id'] == 'unknown_scope':
            check.conditions[3].status = 'unknown'
        if sample['id'] == 'different_currency':
            rows[1].currency = 'USD'
        if sample['id'] == 'known_rounding':
            rows[0].rounding = 'half_up'
        result = calculate(check, rows)
        results.append({'id': sample['id'], 'status': 'expectation_match' if result.calculation_status == sample['expected'] else 'expectation_mismatch',
                        'expected': sample['expected'], 'actual': result.calculation_status,
                        'duration_ms': round((time.perf_counter()-start)*1000, 3), 'result': result.model_dump(mode='json')})
    report = {'dataset_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'dataset_role': 'synthetic', 'human_annotation': 'pending_two_independent_people',
              'groups': {'A_rules': {'status': 'executed', 'samples': results, 'provider_calls': 0, 'tokens': 0},
                         'B_single_model': {'status': 'not_run', 'reason': '未授权本轮付费调用预算'},
                         'C_original_three_stage': {'status': 'not_run', 'reason': '未授权付费预算；未冻结对照模型与同证据预算'},
                         'D_upgraded_three_stage': {'status': 'not_run', 'reason': '等待AI2提交及付费预算'}},
              'professional_precision': None, 'professional_recall': None, 'time_saved': None}
    target = ROOT / 'outputs/ai4/evaluation.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'samples': len(results), 'machine_expectation_match': sum(r['status'] == 'expectation_match' for r in results),
                      'unmeasured': sum(r['status'] == 'unmeasured' for r in results), 'professional_accuracy': None}, ensure_ascii=False))
    return any(r['status'] == 'expectation_mismatch' for r in results)


if __name__ == '__main__':
    raise SystemExit(evaluate())
