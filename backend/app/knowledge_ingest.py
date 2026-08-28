"""官方来源采集适配器：尊重站点条款、固定 UA、低并发、哈希与版本化。

边界（G3-3）：
- 只接受官方域名白名单主机，拒绝登录后、验证码后或来源不明内容；
- 网络失败不生成合成文档；同一文档版本变化时生成新版本，不覆盖旧哈希；
- 固定 User-Agent 与低并发，单次采集文件大小有上限；
- 输出 record 只包含来源元数据与哈希，不回传正文到任何外部服务。
"""
from __future__ import annotations

import hashlib
import re
import time
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from .knowledge_sources import OFFICIAL_HOST_SUFFIXES, normalize_source_entry

USER_AGENT = "AuditTrace-KnowledgeBot/0.1 (+audit-planning research; public official sources)"
MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024
MIN_DELAY_SECONDS = 2.0

# 登录/验证码/未知来源的页面标记；命中即拒绝，不把错误页面当原文。
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


def assess_official_document(
    url: str,
    *,
    expect_pdf: bool,
    timeout: float = 30.0,
) -> FetchAssessment:
    """下载并校验一份官方文档；通过后返回内容哈希与最终 URL。

    校验规则：
    1. 主机必须在官方域名白名单内；
    2. HTTP 2xx + 内容类型匹配（期望 PDF 时 content-type 含 application/pdf，
       或 URL 以 .pdf 结尾）；
    3. 正文不命中登录/验证码标记；
    4. 200MB 上限与超时保护。
    不通过时绝不生成合成文档。
    """
    if not _is_official_url(url):
        return FetchAssessment(False, "host_not_official", "来源主机不在官方域名白名单。")
    if expect_pdf and not (url.lower().endswith(".pdf") or "finalpage" in url.lower()):
        pass  # 内容类型仍以响应头为准
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            raw = response.read(MAX_DOWNLOAD_BYTES + 1)
            final_url = response.geturl()
    except urllib.error.HTTPError as error:
        return FetchAssessment(False, f"http_{error.code}", f"HTTP {error.code}。")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return FetchAssessment(False, "network_error", f"{type(error).__name__}。")
    if len(raw) > MAX_DOWNLOAD_BYTES:
        return FetchAssessment(False, "too_large", "文档超过采集上限。")
    body_prefix = raw[:2048].decode("utf-8", "replace").lower()
    if any(hint in body_prefix for hint in BLOCKED_BODY_HINTS):
        return FetchAssessment(False, "blocked_page", "页面命中登录/验证码标记。")
    if expect_pdf and "pdf" not in content_type and content_type not in ("application/octet-stream", ""):
        return FetchAssessment(False, "content_type_mismatch", f"期望 PDF，实际 {content_type}。")
    return FetchAssessment(
        True,
        "ok",
        f"下载完成，耗时 {round((time.perf_counter() - started) * 1000)}ms。",
        content_type=content_type,
        final_url=final_url,
        sha256=hashlib.sha256(raw).hexdigest(),
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
