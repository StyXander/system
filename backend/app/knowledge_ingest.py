"""官方来源采集适配器：尊重站点条款、固定 UA、低并发、哈希与版本化。

边界（G3-3）：
- 只接受官方域名白名单主机，拒绝登录后、验证码后或来源不明内容；
- 网络失败不生成合成文档；同一文档版本变化时生成新版本，不覆盖旧哈希；
- 固定 User-Agent 与低并发，单次采集文件大小有上限；
- 输出 record 只包含来源元数据与哈希，不回传正文到任何外部服务。

接线状态：本模块当前未被 backend/app 任何路由调用，属于"已实现未接入"的
来源适配器。新增外部来源时必须连同测试一起接线，不得当成已可用的入库链。
"""
from __future__ import annotations

import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .knowledge_sources import OFFICIAL_HOST_SUFFIXES, normalize_source_entry
from .secure_download import SecureDownloadError, download_bounded


USER_AGENT = "AuditTrace-KnowledgeBot/0.1 (+audit-planning research; public official sources)"
MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024
MIN_DELAY_SECONDS = 2.0
# 节流状态是模块级的：多个调用方共享同一份采集预算。
_last_call_at = 0.0
_throttle_lock = threading.Lock()

# 登录/验证码/未知来源的页面标记；命中即拒绝，不把错误页面当原文。
# 只对 HTML 正文判定，PDF 二进制里偶然出现这些字节不算挑战页。
BLOCKED_BODY_HINTS = ("验证码", "登录", "login", "captcha", "机房访问", "禁止访问", "access denied")


@dataclass
class FetchAssessment:
    ok: bool
    code: str
    detail: str
    content_type: str = ""
    final_url: str = ""
    sha256: str = ""


def _is_official_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES)


def _throttle() -> None:
    """按模块级状态节流，落实 MIN_DELAY_SECONDS 而不是只声明它。"""

    global _last_call_at
    with _throttle_lock:
        wait = MIN_DELAY_SECONDS - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


def assess_official_document(
    url: str,
    *,
    expect_pdf: bool,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> FetchAssessment:
    """下载并校验一份官方文档；通过后返回内容哈希与最终 URL。

    校验规则：
    1. 初始地址与每一跳落点都必须在官方域名白名单内；
    2. HTTP 2xx；期望 PDF 时以文件头 %PDF- 为准，Content-Type 只作辅助；
    3. HTML 正文不命中登录/验证码标记；
    4. 120MiB 上限、超时与模块级节流。
    不通过时绝不生成合成文档。
    """
    if not _is_official_url(url):
        return FetchAssessment(False, "host_not_official", "来源主机不在官方域名白名单。")
    _throttle()
    owns_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(timeout, connect=min(20.0, timeout)),
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,text/plain,*/*"},
    )
    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix="audittrace-source-") as scratch:
            try:
                downloaded = download_bounded(
                    url,
                    Path(scratch) / "source-document",
                    client=http_client,
                    max_bytes=MAX_DOWNLOAD_BYTES,
                    require_pdf=expect_pdf,
                    # 每一跳都重新过白名单，防止官方地址把人带出站外。
                    is_allowed_url=_is_official_url,
                )
            except SecureDownloadError as error:
                return FetchAssessment(False, error.code.lower(), f"{error}。")
            # 只有非 PDF 正文才需要判断登录/验证码标记；PDF 二进制不作文本解读。
            if not expect_pdf and "pdf" not in downloaded.content_type:
                head = downloaded.path.read_bytes()[:2048].decode("utf-8", "replace").lower()
                if any(hint in head for hint in BLOCKED_BODY_HINTS):
                    return FetchAssessment(False, "blocked_page", "页面命中登录/验证码标记。")
            sha256 = downloaded.sha256
            final_url = downloaded.final_url
            content_type = downloaded.content_type
    finally:
        if owns_client:
            http_client.close()
    return FetchAssessment(
        True,
        "ok",
        f"下载完成，耗时 {round((time.perf_counter() - started) * 1000)}ms。",
        content_type=content_type,
        final_url=final_url,
        sha256=sha256,
    )


def register_downloaded_source(
    base_entry: dict,
    *,
    document_id: str,
    sha256: str,
    final_url: str,
) -> dict:
    """把已校验文档登记为统一来源条目；返回带哈希与文档号的规范化条目。"""
    entry = normalize_source_entry({**base_entry, "document_id": document_id, "sha256": sha256, "official_url": final_url})
    entry["validation_status"] = "pending" if entry.get("validation_status") == "pending" else entry["validation_status"]
    return entry


def versioned_source_id(base_source_id: str, sha256: str) -> str:
    """同一来源不同哈希生成新版本 ID，避免覆盖旧版本。"""
    return f"{base_source_id}-SHA-{sha256[:8].upper()}"
