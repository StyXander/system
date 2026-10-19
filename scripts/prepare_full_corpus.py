"""按台账下载标准股份年报全文并校验 SHA-256，供年报依赖档复算使用。

只读官方来源 URL（PROJECT_STATUS.json 的 standard_annual_report_sources
已是登记过核验状态的台账），哈希不符时删除临时文件并拒绝落盘为正式资料。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.corpus import corpus_filename

STATUS = ROOT / "PROJECT_STATUS.json"
TIMEOUT_SECONDS = 120


def ledger() -> list[dict[str, str]]:
    """从状态文件读取年报台账：标题、URL、期望哈希。"""
    data: dict[str, Any] = json.loads(STATUS.read_text(encoding="utf-8"))
    return [
        {
            "announcement": corpus_filename(entry["announcement_title"]),
            "url": entry["source_url"],
            "sha256": entry["file_sha256"],
        }
        for entry in data.get("standard_annual_report_sources", [])
    ]


def verify(path: Path, expected_sha256: str) -> bool:
    """逐块哈希比对：文件缺失或哈希不符都判 False。"""
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().lower() == expected_sha256.lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载并校验标准股份年报全文（供年报依赖档测试复算）")
    parser.add_argument("--force", action="store_true", help="哈希已一致时仍重新下载")
    arguments = parser.parse_args(argv)
    failures: list[str] = []
    entries = ledger()
    if not entries:
        print("错误：未在 PROJECT_STATUS.json 中找到 standard_annual_report_sources 台账", file=sys.stderr)
        return 1

    for entry in entries:
        target = ROOT / entry["announcement"]
        if verify(target, entry["sha256"]) and not arguments.force:
            print(f"OK   {entry['announcement']}")
            continue
        temporary = target.with_suffix(".pdf.download")
        print(f"FETCH {entry['announcement']} <- {entry['url']}")
        try:
            with urllib.request.urlopen(entry["url"], timeout=TIMEOUT_SECONDS) as response:
                temporary.write_bytes(response.read())
        except Exception as error:  # noqa: BLE001 - 网络失败要逐条报出但不能中断其余文件
            temporary.unlink(missing_ok=True)
            failures.append(f"{entry['announcement']}: {type(error).__name__}: {error}")
            continue
        if not verify(temporary, entry["sha256"]):
            temporary.unlink(missing_ok=True)
            failures.append(f"{entry['announcement']}: SHA-256 与台账不符，已丢弃")
            continue
        temporary.replace(target)
        print(f"OK   {entry['announcement']}（哈希一致）")
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        print("至少一份年报未就绪；依赖档测试将继续按边界跳过，不得当作全量复现。", file=sys.stderr)
        return 1
    print("全部 4 份年报就绪，可运行 pytest 复算完整档位。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
