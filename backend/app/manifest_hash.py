"""Stable hashing helpers for release manifests.

发布清单的哈希必须只反映清单语义，不能受平台换行差异影响。
这里保留 JSON 数组顺序，并对键进行稳定排序后再计算摘要。
该摘要用于本地、清洁包和部署环境之间的发布口径比对。
它不代表模型调用成功，也不代表人工批准或竞赛发布通过。
清单读取或解析失败时必须交由调用方处理，不能静默沿用旧摘要。
来源许可、人工复核和运行状态仍由各自记录单独证明。

The manifest is checked out with different newline conventions on Windows and
Linux.  Hashing the parsed JSON rather than the file's presentation bytes
keeps the release gate independent of CRLF/LF conversion while preserving
array order and every semantic value.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CANONICAL_MANIFEST_HASH_ALGORITHM = "canonical_json_v1"


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically for cross-platform hashing."""

    # UTF-8 与 ensure_ascii=False 保留中文清单内容，避免摘要只对转义形式敏感。
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_sha256(value: Any, *, uppercase: bool = False) -> str:
    """Return the SHA-256 digest of deterministic JSON bytes."""

    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return digest.upper() if uppercase else digest


def manifest_sha256(path: Path, *, uppercase: bool = False) -> str:
    """Read a manifest and hash its semantic JSON representation."""

    value = json.loads(path.read_text(encoding="utf-8"))
    return canonical_json_sha256(value, uppercase=uppercase)
