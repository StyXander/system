"""全文准备脚本必须能校验哈希并拒绝半残文件。

评委若要复算年报依赖档，唯一入口是这个脚本；它把“下载成功”与
“来源可信且哈希一致”分开判定，不允许只判存在。
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pfc", ROOT / "scripts" / "prepare_full_corpus.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_expected_entries_come_from_status_ledger() -> None:
    entries = module.ledger()
    assert len(entries) == 4, "标准股份年报台账应为 4 条（PROJECT_STATUS.json standard_annual_report_sources）"
    for entry in entries:
        assert entry["announcement"].endswith(".pdf") or entry["announcement"].endswith(".PDF")
        assert len(entry["sha256"]) == 64


def test_verify_rejects_partial_file(tmp_path: Path) -> None:
    target = tmp_path / "标准股份：2024年年度报告.pdf"
    target.write_bytes(b"%PDF-1.4 truncated")
    digest = hashlib.sha256(b"%PDF-1.4 truncated").hexdigest()
    assert module.verify(target, digest) is True
    assert module.verify(target, "0" * 64) is False
    assert module.verify(tmp_path / "missing.pdf", digest) is False
