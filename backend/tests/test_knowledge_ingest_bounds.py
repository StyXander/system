"""官方来源采集适配器的边界：逐跳复校、真实文件头、节流与上限一致。

覆盖 2026-09-09 审查反例 C04。注意：本模块当前未被 backend/app 任何路由
调用，这些测试固定的是"接入前必须成立"的边界，不是线上行为。
"""
from __future__ import annotations

import httpx

from backend.app import knowledge_ingest
from backend.app.knowledge_ingest import MAX_DOWNLOAD_BYTES, assess_official_document

PDF_BYTES = b"%PDF-1.7\n" + b"y" * 2048


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def perf_counter(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_official_constant_matches_documented_limit() -> None:
    """说明文字不得再写 200MB；实现上限就是 120MiB。"""

    assert MAX_DOWNLOAD_BYTES == 120 * 1024 * 1024
    assert "200MB" not in assess_official_document.__doc__


def test_fake_pdf_is_rejected_by_magic_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not a pdf</html>", headers={"content-type": "application/pdf"})

    assessment = assess_official_document(
        "https://www.cninfo.com.cn/test.pdf", expect_pdf=True, client=_client(handler)
    )
    assert assessment.ok is False
    assert assessment.code == "pdf_magic_invalid"


def test_redirect_off_the_official_host_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.cninfo.com.cn":
            return httpx.Response(302, headers={"location": "https://evil.example/a.pdf"}, request=request)
        return httpx.Response(200, content=PDF_BYTES, request=request)

    assessment = assess_official_document(
        "https://www.cninfo.com.cn/a.pdf", expect_pdf=True, client=_client(handler)
    )
    assert assessment.ok is False
    assert assessment.code == "redirect_not_allowed"


def test_registered_min_delay_is_actually_enforced() -> None:
    """MIN_DELAY_SECONDS 不能只是声明；连续调用必须被节流。"""

    clock = FakeClock()
    original = knowledge_ingest.time
    knowledge_ingest.time = clock  # type: ignore[assignment]
    try:
        knowledge_ingest._last_call_at = 0.0

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=PDF_BYTES, request=request)

        for _ in range(2):
            assess_official_document("https://www.cninfo.com.cn/a.pdf", expect_pdf=True, client=_client(handler))
        assert clock.sleeps and clock.sleeps[0] >= knowledge_ingest.MIN_DELAY_SECONDS
    finally:
        knowledge_ingest.time = original  # type: ignore[assignment]
        knowledge_ingest._last_call_at = 0.0


def test_valid_pdf_returns_hash_and_final_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PDF_BYTES, request=request, headers={"content-type": "application/pdf"})

    assessment = assess_official_document("https://www.cninfo.com.cn/a.pdf", expect_pdf=True, client=_client(handler))
    assert assessment.ok is True
    assert assessment.code == "ok"
    assert len(assessment.sha256) == 64
    assert assessment.final_url.startswith("https://www.cninfo.com.cn/")


def test_login_hint_only_blocks_html_bodies_not_pdf() -> None:
    """PDF 正文里出现"登录"字节不应把正常原件判成挑战页。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="%PDF-1.7\n登录 captcha\n".encode("utf-8") + b"z" * 2048, request=request)

    assessment = assess_official_document("https://www.cninfo.com.cn/a.pdf", expect_pdf=True, client=_client(handler))
    assert assessment.ok is True
