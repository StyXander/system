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
