"""受控下载组件：限额必须在接收过程中生效，重定向每一跳都要复校。

覆盖 2026-09-09 审查反例 C04 与结构风险 4.1：旧实现先看 Content-Type 或收完
整个响应体再判体积，且只对初始 URL 做白名单校验。
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from backend.app.secure_download import SecureDownloadError, download_bounded

PDF_BYTES = b"%PDF-1.7\n" + b"x" * 4096


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_size_limit_stops_the_stream_early(tmp_path: Path) -> None:
    """旧缺陷是先收完整 body 再判体积；现在必须在块级别停止。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=iter([PDF_BYTES] * 64),
            headers={"content-type": "application/pdf"},
        )

    with pytest.raises(SecureDownloadError) as error:
        download_bounded(
            "https://www.cninfo.com.cn/a.pdf",
            tmp_path / "a.pdf",
            client=_client(handler),
            max_bytes=8192,
            require_pdf=True,
            is_allowed_url=lambda url: True,
        )
    assert error.value.code == "TOO_LARGE"
    assert not (tmp_path / "a.pdf").exists()
    assert not list(tmp_path.glob(".*.part"))


def test_redirect_to_disallowed_host_is_rejected(tmp_path: Path) -> None:
    """重定向落点必须逐跳复校，不能只信初始 URL。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.cninfo.com.cn":
            return httpx.Response(302, headers={"location": "https://evil.example/a.pdf"}, request=request)
        return httpx.Response(200, content=PDF_BYTES, request=request)

    with pytest.raises(SecureDownloadError) as error:
        download_bounded(
            "https://www.cninfo.com.cn/a.pdf",
            tmp_path / "a.pdf",
            client=_client(handler),
            max_bytes=1024 * 1024,
            require_pdf=True,
            is_allowed_url=lambda url: "cninfo.com.cn" in str(url),
        )
    assert error.value.code == "REDIRECT_NOT_ALLOWED"


def test_fake_pdf_is_rejected_by_magic_bytes(tmp_path: Path) -> None:
    """伪装成 PDF 的 HTML 正文必须被文件头拦住，而不是只看 Content-Type。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not a pdf</html>", headers={"content-type": "application/pdf"})

    with pytest.raises(SecureDownloadError) as error:
        download_bounded(
            "https://www.cninfo.com.cn/a.pdf",
            tmp_path / "a.pdf",
            client=_client(handler),
            max_bytes=1024 * 1024,
            require_pdf=True,
            is_allowed_url=lambda url: True,
        )
    assert error.value.code == "PDF_MAGIC_INVALID"


def test_expected_sha256_mismatch_is_rejected(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PDF_BYTES, request=request)

    with pytest.raises(SecureDownloadError) as error:
        download_bounded(
            "https://www.cninfo.com.cn/a.pdf",
            tmp_path / "a.pdf",
            client=_client(handler),
            max_bytes=1024 * 1024,
            require_pdf=True,
            is_allowed_url=lambda url: True,
            expected_sha256="0" * 64,
        )
    assert error.value.code == "SHA256_MISMATCH"
    assert not (tmp_path / "a.pdf").exists()


def test_too_small_response_is_rejected(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-1.4 tiny", request=request)

    with pytest.raises(SecureDownloadError) as error:
        download_bounded(
            "https://www.cninfo.com.cn/a.pdf",
            tmp_path / "a.pdf",
            client=_client(handler),
            max_bytes=1024 * 1024,
            require_pdf=True,
            is_allowed_url=lambda url: True,
            min_bytes=128,
        )
    assert error.value.code == "TOO_SMALL"


def test_successful_download_is_atomic_and_reported(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PDF_BYTES, request=request, headers={"content-type": "application/pdf"})

    result = download_bounded(
        "https://www.cninfo.com.cn/a.pdf",
        tmp_path / "a.pdf",
        client=_client(handler),
        max_bytes=1024 * 1024,
        require_pdf=True,
        is_allowed_url=lambda url: True,
    )
    assert (tmp_path / "a.pdf").read_bytes() == PDF_BYTES
    assert result.byte_count == len(PDF_BYTES)
    assert len(result.sha256) == 64
    assert result.content_type == "application/pdf"
    assert result.final_url == "https://www.cninfo.com.cn/a.pdf"
    assert not list(tmp_path.glob(".*.part"))


def test_http_error_status_is_reported(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    with pytest.raises(SecureDownloadError) as error:
        download_bounded(
            "https://www.cninfo.com.cn/a.pdf",
            tmp_path / "a.pdf",
            client=_client(handler),
            max_bytes=1024 * 1024,
            require_pdf=False,
            is_allowed_url=lambda url: True,
        )
    assert error.value.code == "HTTP_ERROR"
