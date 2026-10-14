"""托管迁移回归：仅社区可内嵌，快照身份不冒充原工作区提交。"""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_modelscope_allows_only_community_frame_ancestors(monkeypatch):
    monkeypatch.setenv("AUDITTRACE_DEPLOYMENT_PLATFORM", "modelscope")
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "frame-ancestors https://modelscope.cn https://www.modelscope.cn" in response.headers["content-security-policy"]
    assert "x-frame-options" not in response.headers
    assert "connect-src 'self'" in response.headers["content-security-policy"]


def test_other_deployments_keep_embedding_disabled(monkeypatch):
    monkeypatch.delenv("AUDITTRACE_DEPLOYMENT_PLATFORM", raising=False)
    response = TestClient(app).get("/")
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"


def test_modelscope_status_reports_snapshot_separately(monkeypatch):
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    monkeypatch.setenv("AUDITTRACE_DEMO_TASK_PERSISTENCE", "local")
    monkeypatch.setenv("AUDITTRACE_DEPLOYMENT_PLATFORM", "modelscope")
    monkeypatch.setenv("AUDITTRACE_DEPLOYMENT_SERVICE", "burgerhaamm/audittrace")
    monkeypatch.setenv("AUDITTRACE_SOURCE_SNAPSHOT_SHA256", "a" * 64)
    monkeypatch.setenv("AUDITTRACE_SOURCE_BASELINE_COMMIT", "b" * 40)
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    deployment = TestClient(app).get("/api/status").json()["deployment"]
    assert deployment["commit"] is None
    assert deployment["source"] == "modelscope_runtime_environment"
    assert deployment["service"] == "burgerhaamm/audittrace"
    assert deployment["source_snapshot_sha256"] == "a" * 64
    assert deployment["source_baseline_commit"] == "b" * 40
