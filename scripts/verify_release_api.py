"""真实本地服务的游客、会话、历史、原页、导出验收；不替代浏览器视觉检查。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]


def verify(base_url):
    output = ROOT / 'outputs/ai4/api'
    output.mkdir(parents=True, exist_ok=True)
    evidence = {'base_url': base_url, 'started_at': datetime.now(timezone.utc).isoformat(),
                'browser_visual': 'not_verified', 'checks': []}
    def check(name, response, expected=200):
        evidence['checks'].append({'name': name, 'status': response.status_code, 'expected': expected})
        assert response.status_code == expected, (name, response.status_code, response.text[:200])
        return response
    with httpx.Client(base_url=base_url, timeout=120, trust_env=False) as client:
        status = check('status', client.get('/api/status')).json()
        assert status['project_facts']['task_kind'] == 'connectivity'
        check('anonymous_history', client.get('/api/connectivity/runs'), 409)
        boot = check('bootstrap', client.get('/api/connectivity/bootstrap')).json()
        assert boot['project_facts'] == status['project_facts']
        # 固定任务与本次新建任务分别验证，不把两个运行ID混成同一次调用。
        prepared_index = ROOT / 'outputs/ai4/demo/demo-index.json'
        if prepared_index.is_file():
            index = json.loads(prepared_index.read_text(encoding='utf-8'))
            fixed = check('prepared_readonly_task', client.get('/api/connectivity/runs/' + index['task_id'])).json()
            assert fixed['status'] == 'completed' and fixed['run_id'] == index['run_id']
            for extension in ['json', 'csv', 'docx']:
                response = check('prepared_export_' + extension, client.get(f"/api/connectivity/runs/{index['task_id']}/export/{extension}"))
                (prepared_index.parent / ('result.' + extension)).write_bytes(response.content)
            fixed_json = json.loads((prepared_index.parent / 'result.json').read_text(encoding='utf-8'))
            index['overview'] = fixed_json['overview']
            index['execution_provenance'] = fixed_json['overview']['execution_provenance']
            prepared_index.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
            evidence['fixed_task_id'] = index['task_id']
            evidence['fixed_run_id'] = index['run_id']
        ready = check('pair_readiness', client.get('/api/connectivity/readiness?pair_id=000858-2025')).json()
        assert ready['ready'] is True
        check('invalid_pair_readiness', client.get('/api/connectivity/readiness?pair_id=unknown'), 404)
        created = check('create_calculation_only', client.post('/api/connectivity/runs', json={'pair_id': '000858-2025', 'mode': 'calculation_only'})).json()
        task_id = created['task_id']
        deadline = time.monotonic() + 600
        while True:
            task = check('read_task', client.get('/api/connectivity/runs/' + task_id)).json()
            if task['status'] not in {'queued', 'running'}:
                break
            if time.monotonic() > deadline:
                raise TimeoutError('任务观察超时；未宣称完成')
            time.sleep(1)
        assert task['status'] == 'completed', task.get('failure_code')
        history = check('owned_history', client.get('/api/connectivity/runs')).json()
        assert task_id in {row['task_id'] for row in history['items']}
        check('invalid_history_limit', client.get('/api/connectivity/runs?limit=21'), 422)
        for ext in ['json', 'docx', 'csv']:
            response = check('export_' + ext, client.get(f'/api/connectivity/runs/{task_id}/export/{ext}'))
            (output / ('result.' + ext)).write_bytes(response.content)
        exported = json.loads((output / 'result.json').read_text(encoding='utf-8'))
        assert exported['checks'] == task['result']['checks']
        assert exported['overview']['execution_provenance']['provider_call_count'] == 0
        assert exported['overview']['coverage_counts'] == task['result']['overview']['coverage_counts']
        for document, page in [('WLY_AR_2025', 17), ('WLY_ESG_2025', 54)]:
            check('source_page_' + document, client.get(f'/api/connectivity/sources/{document}?page={page}'))
            response = check('source_png_' + document, client.get(f'/api/connectivity/sources/{document}/pages/{page}.png'))
            (output / (document + '.png')).write_bytes(response.content)
        with httpx.Client(base_url=base_url, timeout=30, trust_env=False) as stranger:
            check('stranger_bootstrap', stranger.get('/api/connectivity/bootstrap'))
            assert check('stranger_history', stranger.get('/api/connectivity/runs')).json()['items'] == []
            shared = check('known_link_public', stranger.get('/api/connectivity/runs/' + task_id)).json()
            assert not shared['can_modify']
            check('stranger_cancel', stranger.post(f'/api/connectivity/runs/{task_id}/cancel'), 403)
        evidence.update(task_id=task_id, run_id=task['run_id'], expires_at=task['result_expires_at'],
                        provider_calls=0, project_facts=status['project_facts'], overview=exported['overview'], status='passed')
    (output / 'verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'passed', 'task_id': task_id, 'run_id': task['run_id'], 'browser_visual': 'not_verified'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8774')
    args = parser.parse_args()
    verify(args.base_url)
