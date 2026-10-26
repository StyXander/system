#!/usr/bin/env python3
"""只读审计公告元数据。默认不连接生产、不写回任何资料或历史集合。"""
import argparse
import csv
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.disclosure_dates import normalize_disclosure_date


def audit(root, *, supabase=False):
    rows, coverage = [], []
    def visit(value, source, pointer=''):
        if isinstance(value, dict):
            if value.get('document_id') and ('disclosure_date' in value or value.get('report_type') in {'AR', 'ESG'}):
                raw = value.get('disclosure_date')
                try:
                    normalized = normalize_disclosure_date(raw)
                    issue = 'MISSING_DISCLOSURE_DATE' if not normalized else 'NON_CANONICAL' if raw != normalized else ''
                except ValueError:
                    normalized, issue = '', 'INVALID_DISCLOSURE_DATE'
                rows.append(dict(source=source, pointer=pointer, document_id=value['document_id'],
                    company=value.get('company', ''), period=value.get('report_period') or value.get('period', ''),
                    report_type=value.get('report_type', ''), case_id=value.get('case_id', ''),
                    raw_value=raw, normalized=normalized, issue=issue, source_url=value.get('source_url', '')))
            for key, item in value.items():
                visit(item, source, pointer+'/'+key)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                visit(item, source, pointer+'/'+str(i))
    files = [root/'backend/connectivity_reports.json', root/'backend/connectivity_catalog.snapshot.json']
    runtime = root/'backend/runtime/connectivity'
    files += list(runtime.glob('report_sets/*.json')) + list(runtime.glob('catalog*.json'))
    coverage.append({'source': 'historical_task_snapshots', 'status': 'not_scanned_sensitive_results_excluded'})
    for path in files:
        if not path.exists():
            coverage.append({'source': str(path.relative_to(root)), 'status': 'absent'})
            continue
        try:
            visit(json.loads(path.read_text()), str(path.relative_to(root)))
            coverage.append({'source': str(path.relative_to(root)), 'status': 'scanned'})
        except (ValueError, OSError) as error:
            coverage.append({'source': str(path.relative_to(root)), 'status': type(error).__name__})
    for path in runtime.glob('*.sqlite*'):
        if path.suffix not in {'.sqlite', '.sqlite3', '.db'}:
            continue
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
            for table in ('pairs', 'source_cache'):
                if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    for payload, in db.execute(f'SELECT payload FROM {table}'):
                        visit(json.loads(payload), str(path.relative_to(root))+':'+table)
        coverage.append({'source': str(path.relative_to(root)), 'status': 'scanned_read_only'})
    if supabase:
        from backend.app.supabase_adapter import get_demo_task_client
        client = get_demo_task_client()
        # 公开案例元数据分页读取；不读取用户任务正文或客户原件。
        offset = 0
        while True:
            batch = client.select_table('cases', filters={'tenant_id': 'is.null', 'sample_type': 'eq.public', 'limit': '500', 'offset': str(offset), 'order': 'case_id.asc'},
                                        select='case_id,metadata', service=True)
            for row in batch:
                visit(row.get('metadata') or {}, 'supabase:cases:'+row['case_id'])
            if len(batch) < 500:
                break
            offset += 500
        coverage.append({'source': 'supabase:cases', 'status': 'scanned'})
    else:
        coverage.append({'source': 'production_supabase_and_platform_caches', 'status': 'not_scanned'})
    return {'mode': 'dry_run', 'coverage': coverage, 'records': rows,
            'summary': {'records': len(rows), 'issues': sum(bool(r['issue']) for r in rows)},
            'migration': 'No writes. Missing dates require verified official evidence; immutable saved sets are never rewritten.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='默认且唯一模式：只读')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--supabase', action='store_true', help='显式读取已配置的生产公开案例元数据')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = audit(args.root, supabase=args.supabase)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        with args.output.with_suffix('.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(report['records'][0]) if report['records'] else ['document_id'])
            writer.writeheader(); writer.writerows(report['records'])
    print(json.dumps(report['summary'], ensure_ascii=False))
