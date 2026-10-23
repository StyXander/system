"""只读观察现有 Render 实例；未读到运行时提交时不以本地或声明文件代替。"""
from pathlib import Path
from datetime import datetime, timezone
import json
import httpx

ROOT = Path(__file__).resolve().parents[1]
target = 'https://audittrace-demo.onrender.com'
receipt = {'target': target, 'checked_at': datetime.now(timezone.utc).isoformat(), 'requests': [],
    'runtime_commit': None, 'new_company_entry_present': False, 'catalog_available': False,
    'new_version_verified': False, 'model_requests_sent': 0}
with httpx.Client(timeout=httpx.Timeout(35, connect=10), follow_redirects=False) as client:
    for path in ('/api/health', '/', '/api/connectivity/catalog', '/api/connectivity/bootstrap'):
        try:
            response = client.get(target + path)
            row = {'path': path, 'status': response.status_code}
            if path == '/':
                receipt['new_company_entry_present'] = response.status_code == 200 and 'connectivity-companies.js' in response.text
            else:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                if path == '/api/health':
                    deployment = body.get('deployment') or {}
                    if deployment.get('identity_source') == 'runtime_environment':
                        receipt['runtime_commit'] = deployment.get('commit')
                    row['deployment'] = deployment
                    row['project_facts'] = body.get('project_facts')
                if path.endswith('/catalog'):
                    receipt['catalog_available'] = response.status_code == 200 and isinstance(body.get('items'), list)
                    row['pair_count'] = len(body.get('items', []))
                    row['ready_count'] = sum(r.get('state') == 'ready' for r in body.get('items', []))
                    row['persistence'] = body.get('persistence')
                if path.endswith('/bootstrap'):
                    row['project_facts'] = body.get('project_facts')
            receipt['requests'].append(row)
        except httpx.HTTPError as error:
            receipt['requests'].append({'path': path, 'status': 'unavailable', 'error': type(error).__name__})
receipt['new_version_verified'] = bool(receipt['new_company_entry_present'] and receipt['catalog_available'] and receipt['runtime_commit'])
out = ROOT / 'docs/enterprise-expansion/deployment-observation.json'
out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False))
