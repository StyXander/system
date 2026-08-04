"""公开演示所需官方年报的受控下载与本地临时缓存。

公开仓库不保存年报全文，避免把“公开可下载”误写成已获再分发许可。
Render 只从案例注册表中的巨潮资讯固定地址取得文件，不接受用户 URL。
下载结果必须同时通过 PDF 文件头、最大体积和登记哈希三项检查。
任一检查失败都删除临时文件，并让本次构建或运行保持失败关闭。
缓存只服务确定性计算、来源完整性校验和本地 RAG，不进入模型许可判断。
是否允许把证据片段传给外部模型仍由案例 manifest 和真人记录决定。
公开来源接口即使发现本地缓存，也必须把访问者送回巨潮资讯原件。
同一年度年报可能支持多个财务字段，因此下载前按年度清单去重。
正确缓存可以复用，但每次复用前仍重新计算整份文件的 SHA-256。
符号链接和越出工作区的路径被拒绝，避免缓存写入任意文件位置。
临时文件使用随机名称，只有全部校验通过后才原子替换正式缓存。
网络代理不参与官方来源下载，减少环境代理改变受信来源的风险。
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from pathlib import Path
from typing import Any

import httpx

from .data import ANNUAL_REPORT_SOURCES


TRUSTED_SOURCE_PREFIX = "https://static.cninfo.com.cn/finalpage/"
MAX_SOURCE_BYTES = 50 * 1024 * 1024
_SOURCE_CACHE_LOCK = threading.Lock()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _registered_sources() -> list[dict[str, str | int]]:
    """按年度去重，避免同一份年报因多个字段证据被重复下载。"""
    sources: list[dict[str, str | int]] = []
    for year, source in sorted(ANNUAL_REPORT_SOURCES.items()):
        source_url = str(source["source_url"])
        source_file = str(source["source_file"])
        if not source_url.startswith(TRUSTED_SOURCE_PREFIX):
            raise ValueError(f"{year} 年来源 URL 不在巨潮资讯受信白名单。")
        if Path(source_file).name != source_file:
            raise ValueError(f"{year} 年来源文件名包含非法路径。")
        sources.append(
            {
                "year": year,
                "source_url": source_url,
                "source_file": source_file,
                "file_sha256": str(source["file_sha256"]).upper(),
            }
        )
    return sources


def _download_source(client: httpx.Client, source: dict[str, Any], target: Path) -> int:
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
    digest = hashlib.sha256()
    byte_count = 0
    first_bytes = b""
    try:
        with client.stream("GET", str(source["source_url"])) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for block in response.iter_bytes(1024 * 1024):
                    if not block:
                        continue
                    byte_count += len(block)
                    if byte_count > MAX_SOURCE_BYTES:
                        raise ValueError(f"{source['year']} 年来源文件超过 50MB 安全上限。")
                    if len(first_bytes) < 5:
                        first_bytes += block[: 5 - len(first_bytes)]
                    digest.update(block)
                    handle.write(block)
        if not first_bytes.startswith(b"%PDF-"):
            raise ValueError(f"{source['year']} 年来源响应不是 PDF。")
        actual_sha256 = digest.hexdigest().upper()
        if actual_sha256 != source["file_sha256"]:
            raise ValueError(f"{source['year']} 年来源文件 SHA-256 与登记值不一致。")
        temporary.replace(target)
        return byte_count
    finally:
        temporary.unlink(missing_ok=True)


def ensure_standard_sources(
    workspace_root: Path,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """确保四份标准案例年报存在且哈希正确；公开路由仍回到官方原件。"""
    root = workspace_root.resolve()
    downloaded: list[dict[str, Any]] = []
    reused: list[dict[str, Any]] = []
    owns_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(120.0, connect=30.0),
        follow_redirects=True,
        trust_env=False,
        headers={"User-Agent": "AuditTrace/0.7.1 official-source-cache"},
    )
    try:
        with _SOURCE_CACHE_LOCK:
            for source in _registered_sources():
                target = (root / str(source["source_file"])).resolve()
                try:
                    target.relative_to(root)
                except ValueError as error:
                    raise ValueError("来源缓存路径越出工作区。") from error
                if target.is_symlink():
                    raise ValueError(f"{source['year']} 年来源缓存不能是符号链接。")
                if target.is_file() and _file_sha256(target) == source["file_sha256"]:
                    reused.append({"year": source["year"], "bytes": target.stat().st_size})
                    continue
                target.unlink(missing_ok=True)
                byte_count = _download_source(http_client, source, target)
                downloaded.append({"year": source["year"], "bytes": byte_count})
    finally:
        if owns_client:
            http_client.close()
    return {
        "status": "ready",
        "source_count": len(downloaded) + len(reused),
        "downloaded": downloaded,
        "reused": reused,
        "boundary": "文件只在运行环境中用于哈希校验、确定性计算与本地RAG；公开来源入口仍跳转巨潮资讯原件。",
    }
