"""受控下载组件：逐跳复校、块级限额、增量哈希与原子落盘。

巨潮年报与官方知识来源共用这一份实现，避免出现第三个下载器。设计约束：

- 每一跳在发出请求前复校目标地址，不只看初始 URL；
- 体积上限在接收过程中生效，超限立即中断，不消费剩余响应体；
- 边读边写临时文件并增量计算 SHA-256，成功后原子替换目标；
- 期望 PDF 时以文件头为准，Content-Type 只作辅助信息；
- 本模块不做重试与节流，那些属于调用方的请求策略。
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

BLOCK_SIZE = 1024 * 1024
MAX_REDIRECT_HOPS = 5
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
PDF_MAGIC = b"%PDF-"


class SecureDownloadError(RuntimeError):
    """受控下载失败；code 供调用方映射为各自的业务错误码。"""

    def __init__(self, code: str, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


@dataclass
class DownloadedFile:
    path: Path
    byte_count: int
    sha256: str
    final_url: str
    content_type: str
    hops: int


def download_bounded(
    url: str,
    target: Path,
    *,
    client: httpx.Client,
    max_bytes: int,
    require_pdf: bool,
    is_allowed_url: Callable[[str], bool],
    expected_sha256: str | None = None,
    min_bytes: int = 1,
    max_hops: int = MAX_REDIRECT_HOPS,
) -> DownloadedFile:
    """把一个小写受控 URL 下载为文件；任何一步不成立都不留下半成品。"""

    current = str(url)
    # 手动跟随重定向，才能在每一跳发出请求之前复校目标地址。
    for hop in range(max_hops + 1):
        if not is_allowed_url(current):
            raise SecureDownloadError("REDIRECT_NOT_ALLOWED", f"下载目标地址不在允许来源内：{current}")
        try:
            # stream=True 是关键：否则 httpx 会先把整个响应体读进内存，块级限额就失去意义。
            response = client.send(client.build_request("GET", current), stream=True, follow_redirects=False)
        except httpx.HTTPError as error:
            raise SecureDownloadError("NETWORK_ERROR", f"下载失败：{type(error).__name__}。") from error
        try:
            if response.status_code in REDIRECT_STATUSES:
                location = str(response.headers.get("location") or "").strip()
                if not location:
                    raise SecureDownloadError("REDIRECT_LOCATION_MISSING", "重定向响应缺少目标地址。")
                current = str(httpx.URL(str(response.url)).join(location))
                continue
            if response.status_code // 100 != 2:
                raise SecureDownloadError(
                    "HTTP_ERROR",
                    f"下载返回 HTTP {response.status_code}。",
                    detail={"status_code": response.status_code},
                )
            content_type = str(response.headers.get("content-type") or "").lower()
            byte_count, head, digest = _write_bounded(response, target, max_bytes=max_bytes)
        finally:
            # 关闭即中止剩余响应体读取，超限时不会继续拖流量。
            response.close()
        if require_pdf and not head.startswith(PDF_MAGIC):
            target.unlink(missing_ok=True)
            raise SecureDownloadError("PDF_MAGIC_INVALID", "响应内容不是 PDF 文件。")
        if byte_count < min_bytes:
            target.unlink(missing_ok=True)
            raise SecureDownloadError("TOO_SMALL", f"响应体仅 {byte_count} 字节，疑似错误页面。")
        if expected_sha256 and digest.upper() != str(expected_sha256).upper():
            target.unlink(missing_ok=True)
            raise SecureDownloadError(
                "SHA256_MISMATCH",
                "文件 SHA-256 与登记值不一致。",
                detail={"expected": str(expected_sha256).upper(), "actual": digest.upper()},
            )
        return DownloadedFile(
            path=target,
            byte_count=byte_count,
            sha256=digest.upper(),
            final_url=current,
            content_type=content_type,
            hops=hop,
        )
    raise SecureDownloadError("TOO_MANY_REDIRECTS", f"重定向超过 {max_hops} 次。")


def _write_bounded(response: httpx.Response, target: Path, *, max_bytes: int) -> tuple[int, bytes, str]:
    """边读边写并把体积上限施加在接收过程中；返回字节数、文件头和哈希。"""

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
    digest = hashlib.sha256()
    byte_count = 0
    head = b""
    try:
        with temporary.open("wb") as handle:
            for block in response.iter_bytes(BLOCK_SIZE):
                if not block:
                    continue
                byte_count += len(block)
                if byte_count > max_bytes:
                    # 立即抛出并中止读取，不把超限的响应体全部拖进本机。
                    raise SecureDownloadError(
                        "TOO_LARGE",
                        f"下载内容超过 {max_bytes} 字节上限。",
                        detail={"byte_count": byte_count, "max_bytes": max_bytes},
                    )
                if len(head) < len(PDF_MAGIC):
                    head += block[: len(PDF_MAGIC) - len(head)]
                digest.update(block)
                handle.write(block)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return byte_count, head, digest.hexdigest()
