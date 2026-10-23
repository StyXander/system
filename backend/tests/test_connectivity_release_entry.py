"""新版正式入口不能继续暴露历史业务API。"""
from backend.app.connectivity_app import app


def test_only_current_business_api_is_published():
    paths = set(app.openapi()['paths'])
    assert '/api/connectivity/runs' in paths and '/api/health' in paths
    assert not any(p.startswith(('/api/rag', '/api/cases', '/api/demo/runs', '/api/supplements', '/api/industry')) for p in paths)


def test_main_page_has_no_legacy_workspace():
    from pathlib import Path
    page = (Path(__file__).resolve().parents[2] / 'index.html').read_text(encoding='utf-8')
    assert 'id="legacy-workspace"' not in page
    assert 'demo-app.js' not in page
    assert '多智能体智能审计（推荐）' in page


def test_new_entry_keeps_proxy_configuration_fail_closed(monkeypatch):
    from fastapi.testclient import TestClient
    import pytest
    monkeypatch.setenv('AUDITTRACE_TRUSTED_PROXY_HOPS', '1')
    monkeypatch.delenv('AUDITTRACE_TRUSTED_PROXY_CIDRS', raising=False)
    with pytest.raises(RuntimeError, match='AUDITTRACE_TRUSTED_PROXY_HOPS'):
        with TestClient(app):
            pass


def test_health_reports_runtime_identity_without_guessing_commit(monkeypatch):
    from backend.app.connectivity_app import health
    monkeypatch.delenv('RENDER_GIT_COMMIT', raising=False)
    monkeypatch.delenv('GIT_COMMIT', raising=False)
    assert health()['deployment']['commit'] is None
    monkeypatch.setenv('RENDER_GIT_COMMIT', 'a' * 40)
    assert health()['deployment']['commit'] == 'a' * 40


def test_public_legacy_start_command_exports_formal_app_in_both_import_orders():
    """公开服务保存旧命令时仍须具备新搜索与付费授权，且不暴露旧业务。"""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, AUDITTRACE_PUBLIC_DEMO='true', AUDITTRACE_DEMO_USE_EXTERNAL_MODEL='false',
               AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE='local', AUDITTRACE_DEMO_TASK_PERSISTENCE='local')
    for module in ('backend.app.main', 'backend.app.connectivity_app'):
        code = f'''import importlib,json
from fastapi.testclient import TestClient
m=importlib.import_module({module!r})
paths=set(m.app.openapi()['paths'])
assert '/api/connectivity/catalog' in paths and '/api/companies/search' in paths
assert not any(p.startswith(('/api/rag','/api/cases','/api/demo/runs','/api/industry')) for p in paths)
client=TestClient(m.app)
health=client.get('/api/health').json()
assert health['deployment']['entry']=='backend.app.connectivity_app:app'
assert client.post('/api/connectivity/runs',json={{'pair_id':'600019-2025','mode':'three_agents'}}).status_code==401
print(json.dumps({{'entry':health['deployment']['entry'],'release':health['deployment']['release']}}))
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=root, env=env,
                                capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)['release'] == '2026.10.23.enterprise.1'
