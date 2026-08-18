from __future__ import annotations

import io
import json
import time
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

import pytest

from backend.app.provider_readiness import (
    DEFAULT_PROBE_TTL_SECONDS,
    ProviderSnapshot,
    get_provider_snapshot,
    is_provider_probe_enabled,
    probe_provider,
    record_provider_failure,
    record_provider_success,
    reset_provider_readiness,
)


@pytest.fixture(autouse=True)
def clean_readiness_state():
    reset_provider_readiness()
    yield
    reset_provider_readiness()


def test_probe_provider_missing_key():
    snapshot = probe_provider(api_key="")
    assert snapshot.status == "unavailable"
    assert snapshot.reason_code == "api_key_missing"
    assert "尚未配置模型 API Key" in snapshot.message
    assert snapshot.source == "probe"


def test_probe_provider_deepseek_balance_success():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "is_available": True,
        "balance_infos": [{"currency": "CNY", "total_balance": "100.00"}],
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("backend.app.provider_readiness.urlopen", return_value=mock_response):
        snapshot = probe_provider(
            api_key="sk-test-key",
            base_url="https://api.deepseek.com",
            model_id="deepseek-v4-flash",
        )
        assert snapshot.status == "ready"
        assert snapshot.reason_code == "ready"
        assert "探测通过" in snapshot.message


def test_probe_provider_deepseek_balance_unavailable():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "is_available": False,
        "balance_infos": [{"currency": "CNY", "total_balance": "0.00"}],
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("backend.app.provider_readiness.urlopen", return_value=mock_response):
        snapshot = probe_provider(
            api_key="sk-test-key",
            base_url="https://api.deepseek.com",
            model_id="deepseek-v4-flash",
        )
        assert snapshot.status == "unavailable"
        assert snapshot.reason_code == "provider_balance_exhausted"
        assert "余额不足" in snapshot.message


def test_probe_provider_auth_failed_401():
    http_error = HTTPError(
        url="https://api.deepseek.com/user/balance",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b'{"error": "invalid api key"}'),
    )
    with patch("backend.app.provider_readiness.urlopen", side_effect=http_error):
        snapshot = probe_provider(
            api_key="sk-invalid-key",
            base_url="https://api.deepseek.com",
            model_id="deepseek-v4-flash",
        )
        assert snapshot.status == "unavailable"
        assert snapshot.reason_code == "provider_auth_failed"
        assert "鉴权失败" in snapshot.message


def test_probe_provider_balance_exhausted_402():
    http_error = HTTPError(
        url="https://api.deepseek.com/user/balance",
        code=402,
        msg="Payment Required",
        hdrs={},
        fp=io.BytesIO(b'{"error": "insufficient balance"}'),
    )
    with patch("backend.app.provider_readiness.urlopen", side_effect=http_error):
        snapshot = probe_provider(
            api_key="sk-test-key",
            base_url="https://api.deepseek.com",
            model_id="deepseek-v4-flash",
        )
        assert snapshot.status == "unavailable"
        assert snapshot.reason_code == "provider_balance_exhausted"
        assert "余额不足" in snapshot.message


def test_probe_provider_rate_limited_429():
    http_error = HTTPError(
        url="https://api.deepseek.com/user/balance",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(b'{"error": "rate limit reached"}'),
    )
    with patch("backend.app.provider_readiness.urlopen", side_effect=http_error):
        snapshot = probe_provider(
            api_key="sk-test-key",
            base_url="https://api.deepseek.com",
            model_id="deepseek-v4-flash",
        )
        assert snapshot.status == "unavailable"
        assert snapshot.reason_code == "provider_temporarily_unavailable"
        assert "429" in snapshot.message


def test_probe_provider_timeout():
    with patch("backend.app.provider_readiness.urlopen", side_effect=TimeoutError("Probe timeout")):
        snapshot = probe_provider(
            api_key="sk-test-key",
            base_url="https://api.deepseek.com",
            model_id="deepseek-v4-flash",
        )
        assert snapshot.status == "unavailable"
        assert snapshot.reason_code == "provider_temporarily_unavailable"
        assert "超时" in snapshot.message or "TimeoutError" in snapshot.message


def test_probe_provider_custom_gateway_models_check():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "object": "list",
        "data": [{"id": "deepseek-ai/deepseek-v3"}, {"id": "deepseek-ai/deepseek-r1"}],
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("backend.app.provider_readiness.urlopen", return_value=mock_response):
        snapshot = probe_provider(
            api_key="sk-gateway-key",
            base_url="https://custom.gateway.example.com/v1",
            model_id="deepseek-ai/deepseek-v3",
        )
        assert snapshot.status == "ready"
        assert snapshot.reason_code == "ready"


def test_probe_provider_custom_gateway_missing_model():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "object": "list",
        "data": [{"id": "gpt-4o"}, {"id": "claude-3-5-sonnet"}],
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("backend.app.provider_readiness.urlopen", return_value=mock_response):
        snapshot = probe_provider(
            api_key="sk-gateway-key",
            base_url="https://custom.gateway.example.com/v1",
            model_id="deepseek-unsupported-model",
        )
        assert snapshot.status == "unavailable"
        assert snapshot.reason_code == "provider_model_unavailable"
        assert "未找到配置的模型" in snapshot.message


def test_get_provider_snapshot_caching(monkeypatch):
    monkeypatch.setenv("AUDITTRACE_PROVIDER_PROBE_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-cache-key")

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "is_available": True,
        "balance_infos": [],
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("backend.app.provider_readiness.urlopen", return_value=mock_response) as mock_url:
        snap1 = get_provider_snapshot()
        assert snap1.status == "ready"
        assert mock_url.call_count == 1

        # 第二次调用在 TTL 内直接复用缓存
        snap2 = get_provider_snapshot()
        assert snap2.status == "ready"
        assert mock_url.call_count == 1

        # 强制刷新时会重新请求
        snap3 = get_provider_snapshot(force_refresh=True)
        assert snap3.status == "ready"
        assert mock_url.call_count == 2


def test_circuit_breaker_record_failure_and_success(monkeypatch):
    monkeypatch.setenv("AUDITTRACE_PROVIDER_PROBE_ENABLED", "true")
    
    # 模拟真实调用失败触发熔断
    record_provider_failure("MODEL_PROVIDER_AUTH_FAILED", "API Key 已被供应商失效")
    snap = get_provider_snapshot()
    assert snap.status == "unavailable"
    assert snap.reason_code == "provider_auth_failed"
    assert snap.source == "circuit_breaker"
    assert "API Key 已被供应商失效" in snap.message

    # 模拟真实调用成功恢复
    record_provider_success("deepseek-v4-flash")
    snap_after = get_provider_snapshot()
    assert snap_after.status == "ready"
    assert snap_after.reason_code == "ready"
    assert snap_after.source == "live_run"
