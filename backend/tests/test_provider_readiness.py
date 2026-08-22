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
    snapshot = probe_provider(api_key="", base_url="https://api.deepseek.com")
    assert snapshot.status == "unavailable"
    assert snapshot.reason_code == "api_key_missing"
    assert "尚未配置" in snapshot.message and "API Key" in snapshot.message
    assert snapshot.source == "probe"
    assert snapshot.provider_kind == "deepseek_direct"


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


def test_probe_disabled_is_unverified_and_never_ready(monkeypatch):
    """REQ-BACKEND: 关闭主动探测只能表示未验证，不能伪装成模型就绪。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-disabled-probe")
    monkeypatch.delenv("AUDITTRACE_PROVIDER_PROBE_ENABLED", raising=False)

    snapshot = get_provider_snapshot()

    assert snapshot.status == "unavailable"
    assert snapshot.reason_code == "provider_probe_disabled"
    assert snapshot.paid_probe_performed is False
    assert snapshot.next_action_code == "enable_provider_probe_or_run_live"


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


def test_background_probe_deduplication_under_concurrency(monkeypatch):
    """测试软过期窗口期多线程并发访问时只触发一次后台探测，避免雷群效应。"""
    monkeypatch.setenv("AUDITTRACE_PROVIDER_PROBE_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-mock-key")

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "is_available": True,
        "balance_infos": [{"currency": "CNY", "total_balance": "100.00"}],
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    import time
    with patch("backend.app.provider_readiness.urlopen", return_value=mock_response) as mock_url:
        # 先获取一次新鲜快照
        snap1 = get_provider_snapshot()
        assert snap1.status == "ready"
        assert mock_url.call_count == 1

        # 手动将上次探测时间调整为 400 秒前（进入 300~600 秒的软过期 stale 窗口）
        import backend.app.provider_readiness as pr
        with pr._lock:
            pr._last_probe_timestamp = time.time() - 400

        # 多线程并发调用 get_provider_snapshot
        import threading
        threads = [threading.Thread(target=get_provider_snapshot) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 等待后台线程执行结束
        time.sleep(0.2)
        # 验证 urlopen 仅在初始一次 + 后台异步一次 = 2 次，而不是 1 + 10 = 11 次
        assert mock_url.call_count == 2


def test_classify_provider_channel():
    """测试供应商通道分类解析。"""
    from backend.app.provider_readiness import classify_provider_channel

    # 1. DeepSeek 直连
    ds = classify_provider_channel("https://api.deepseek.com")
    assert ds["provider_kind"] == "deepseek_direct"
    assert ds["provider_label"] == "DeepSeek 官方直连"
    assert ds["provider_host"] == "api.deepseek.com"

    # 2. OpenCode Go
    go = classify_provider_channel("https://opencode.ai/zen/go/v1")
    assert go["provider_kind"] == "opencode_go"
    assert go["provider_label"] == "OpenCode Go"
    assert go["provider_host"] == "opencode.ai"

    # 3. OpenCode Zen
    zen = classify_provider_channel("https://opencode.ai/zen/v1")
    assert zen["provider_kind"] == "opencode_zen"
    assert zen["provider_label"] == "OpenCode Zen"
    assert zen["provider_host"] == "opencode.ai"

    # 4. 其他 OpenAI 兼容通道
    other = classify_provider_channel("https://custom-gateway.corp.com/v1")
    assert other["provider_kind"] == "openai_compatible_other"
    assert "custom-gateway.corp.com" in other["provider_label"]
    assert other["provider_host"] == "custom-gateway.corp.com"


def test_get_provider_error_guidance():
    """测试不同通道下的 402/401/403/429 错误引导文案。"""
    from backend.app.provider_readiness import get_provider_error_guidance

    # DeepSeek 直连 402
    ds_402 = get_provider_error_guidance("MODEL_PROVIDER_BALANCE_EXHAUSTED", base_url="https://api.deepseek.com", http_code=402)
    assert "api.deepseek.com" in ds_402["message"]
    assert "未消耗 OpenCode 余额" in ds_402["message"]
    assert ds_402["next_action_code"] == "check_deepseek_balance_or_switch_opencode"

    # OpenCode Go 402
    go_402 = get_provider_error_guidance("MODEL_PROVIDER_BALANCE_EXHAUSTED", base_url="https://opencode.ai/zen/go/v1", http_code=402)
    assert "OpenCode Go" in go_402["message"]
    assert "工作区" in go_402["message"]
    assert go_402["next_action_code"] == "check_opencode_go_workspace_quota"

    # OpenCode Zen 402
    zen_402 = get_provider_error_guidance("MODEL_PROVIDER_BALANCE_EXHAUSTED", base_url="https://opencode.ai/zen/v1", http_code=402)
    assert "OpenCode Zen" in zen_402["message"]
    assert zen_402["next_action_code"] == "check_opencode_zen_balance"

    # 401 鉴权
    auth_err = get_provider_error_guidance("MODEL_PROVIDER_AUTH_FAILED", base_url="https://opencode.ai/zen/go/v1", http_code=401)
    assert "OpenCode Go" in auth_err["message"]
    assert auth_err["next_action_code"] == "check_opencode_api_key"

    # 403 区域协议
    reg_err = get_provider_error_guidance("MODEL_PROVIDER_REGION_OPT_IN_REQUIRED", base_url="https://opencode.ai/zen/go/v1", http_code=403, detail="hosted in china requires explicit opt in")
    assert "中国托管模型" in reg_err["message"]
    assert reg_err["next_action_code"] == "enable_china_hosted_model_in_workspace"
