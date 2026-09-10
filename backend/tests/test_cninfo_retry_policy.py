"""巨潮请求按故障分类重试：5xx 可恢复，403 立即停止，429 尊重 Retry-After。

覆盖 2026-09-09 审查反例 C05：旧实现只重试 403/429，503 直接返回，且 403
耗尽后错误码被写成限流。测试使用注入时钟，不真的等待，也不压测官方站点。
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from backend.app import cninfo
from backend.app.cninfo import CNInfoClient, CNInfoError

TRUSTED_URL = "https://www.cninfo.com.cn/"


class FakeClock:
    """替换 cninfo 模块内的 time 引用，避免任何真实等待。"""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _client(handler, monkeypatch, **kwargs):
    clock = FakeClock()
    monkeypatch.setattr(cninfo, "time", clock)
    client = CNInfoClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_delay_seconds=0,
        **kwargs,
    )
    client.clock = clock  # type: ignore[attr-defined]
    return client


@pytest.mark.parametrize("status", [503, 502, 504, 408])
def test_transient_server_errors_are_retried(monkeypatch, status: int) -> None:
    """旧缺陷：503 只请求一次就交给上层报 PDF_HTTP_ERROR。"""

    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(status)
        return httpx.Response(status) if len(calls) == 1 else httpx.Response(200, json={"ok": True})

    client = _client(handler, monkeypatch, max_retries=2)
    response = client._request("GET", TRUSTED_URL, source="离线夹具")
    assert response.status_code == 200
    assert len(calls) == 2
    assert client.retry_summary()["retried_requests"] == 1


def test_exhausted_retries_return_last_response(monkeypatch) -> None:
    """重试用尽后返回真实状态码，由调用方决定如何记录，不伪装成成功。"""

    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    client = _client(handler, monkeypatch, max_retries=2)
    response = client._request("GET", TRUSTED_URL, source="离线夹具")
    assert response.status_code == 503
    assert len(calls) == 3
    assert client.retry_summary()["stop_reason"] == "retries_exhausted"


def test_access_denied_stops_immediately(monkeypatch) -> None:
    """403 属于访问限制，不再被当成限流反复冲击。"""

    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(403)

    client = _client(handler, monkeypatch, max_retries=3)
    with pytest.raises(CNInfoError) as error:
        client._request("GET", TRUSTED_URL, source="离线夹具")
    assert error.value.code == "CNINFO_ACCESS_DENIED"
    assert len(calls) == 1


def test_rate_limited_honours_retry_after(monkeypatch) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "3"}) if len(calls) == 1 else httpx.Response(200, json={})

    client = _client(handler, monkeypatch, max_retries=2)
    assert client._request("GET", TRUSTED_URL, source="离线夹具").status_code == 200
    assert client.clock.sleeps[0] == 3.0


def test_retry_deadline_stops_backoff(monkeypatch) -> None:
    """总预算用尽时立即返回，不在演示请求上无限退避。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = _client(handler, monkeypatch, max_retries=5, retry_deadline_seconds=4.0)
    response = client._request("GET", TRUSTED_URL, source="离线夹具")
    assert response.status_code == 503
    assert client.retry_summary()["stop_reason"] == "deadline_exceeded"
    assert sum(client.clock.sleeps) <= 4.0


def test_backoff_journal_is_deterministic(monkeypatch) -> None:
    """同一来源与次数的等待时长必须可复现，否则验收记录无法回看。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    first = _client(handler, monkeypatch, max_retries=2)
    first._request("GET", TRUSTED_URL, source="离线夹具")
    second = _client(handler, monkeypatch, max_retries=2)
    second._request("GET", TRUSTED_URL, source="离线夹具")
    assert first.clock.sleeps == second.clock.sleeps
    assert [item["reason"] for item in first.retry_summary()["journal"]] == [
        "backoff",
        "backoff",
        "retries_exhausted",
    ]
