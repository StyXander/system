"""生成新的本地无模型任务与离线同源备份，不续期或改写旧模型结果。"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.connectivity_bootstrap import source_readiness
from app.connectivity_extraction import load_registry, source_path
from app.connectivity_delivery import export_run
from app.connectivity_facts import execution_provenance, project_facts
from app.connectivity_pipeline import run_pipeline
from app.connectivity_schemas import RunRequest, NOTICE
from app.demo_run_tasks import DemoRunTaskStore, result_expiry_iso


def prepare(pair_id, sources_from=None):
    documents = [d for d in load_registry(ROOT) if d.case_id == pair_id]
    if not documents:
        raise ValueError('报告对未登记')
    if sources_from:
        for document in documents:
            origin = sources_from / (document.file_sha256 + '.pdf')
            if origin.is_file() and not source_path(ROOT, document).exists():
                target = source_path(ROOT, document)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, target)
    readiness = source_readiness(ROOT, pair_id=pair_id)
    output = ROOT / 'outputs/ai4/demo'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'readiness.json').write_text(json.dumps(readiness, ensure_ascii=False, indent=2), encoding='utf-8')
    if not readiness['ready']:
        raise RuntimeError('原件就绪检查未通过，见readiness.json；未替代版本或伪造演示结果')
    store = DemoRunTaskStore(ROOT / 'backend/runtime/connectivity/tasks', task_id_prefix='CONNJOB')
    def execute(item):
        result = run_pipeline(ROOT, RunRequest(pair_id=pair_id, mode='calculation_only'))
        store.update_task(item['task_id'], status='completed', run_id=result.run_id,
                          result=result.model_dump(mode='json'), result_expires_at=result_expiry_iso(minimum_seconds=30*86400))
    try:
        task = store.create(pair_id, {'kind': 'connectivity', 'owner': 'offline-release-preparation', 'mode': 'calculation_only'}, execute)
        deadline = time.monotonic() + 600
        while task['status'] in {'queued', 'running'}:
            if time.monotonic() > deadline:
                raise TimeoutError('观察超时；未取消或把运行中任务宣称完成')
            time.sleep(.2)
            task = store.get(task['task_id'])
        if task['status'] != 'completed':
            raise RuntimeError(f"任务未完成：{task.get('failure_code')}")
        from app.connectivity_schemas import ConnectivityRun
        result = ConnectivityRun.model_validate(task['result'])
        for extension in ['json', 'csv', 'docx']:
            payload, _ = export_run(result, extension, include_personal=False)
            (output / f'result.{extension}').write_bytes(payload)
        payload = json.loads((output / 'result.json').read_text(encoding='utf-8'))
        index = {'task_id': task['task_id'], 'run_id': result.run_id, 'expires_at': task['result_expires_at'],
                 'local_url': '/?connectivity_task=' + task['task_id'], 'scope': 'local_only_not_deployed',
                 'execution_provenance': execution_provenance(result), 'human_review': 'not_performed',
                 'project_facts': project_facts(ROOT), 'overview': payload['overview']}
        (output / 'demo-index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
        cards = ''.join('<details><summary>' + html.escape(c.title) + '</summary><p>' + html.escape(c.criteria_status + ' / ' + c.calculation_status) + '</p><pre>' + html.escape(json.dumps(c.model_dump(mode='json'), ensure_ascii=False, indent=2)) + '</pre></details>' for c in result.checks)
        page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>关联核对离线历史结果</title><style>body{max-width:70em;margin:2em auto;padding:1em;font:18px/1.7 sans-serif;background:#faf8f3;color:#222}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;padding:.8em;border-bottom:1px solid #ccc}</style><h1>关联核对离线历史结果</h1><p>已保存的本地无模型计算，不是实时模型分析；未完成人工专业复核。</p><p>' + html.escape(NOTICE) + '</p><p>' + html.escape(result.company + ' ' + result.period + ' / ' + result.run_id) + '</p><p><a href="result.json">同源JSON</a> · <a href="result.docx">同源Word</a></p>' + cards + '</html>'
        (output / 'offline.html').write_text(page, encoding='utf-8')
        print(json.dumps(index, ensure_ascii=False))
    finally:
        store.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', default='000858-2025')
    parser.add_argument('--sources-from', type=Path)
    args = parser.parse_args()
    prepare(args.pair, args.sources_from)
