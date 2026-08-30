"""Stable hashing helpers for release manifests.

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

