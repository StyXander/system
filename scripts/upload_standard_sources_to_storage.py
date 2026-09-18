#!/usr/bin/env python
"""把四份已核验的标准股份年报原件回填到现有 Supabase 私有桶，并可回验读路径。

为什么需要它：Render 免费实例没有持久磁盘，官方来源又在运行期返回 403，
所以"构建能过、运行必挂"。私有桶让运行环境有一个不依赖官方站的取回通道。

安全边界：
  - 上传前逐份核对本地文件 SHA-256 与登记值；不一致直接拒绝，不静默改登记哈希。
  - 只接受 %PDF 文件头与 50MB 上限内的文件。
  - 对象路径由登记内容寻址（年度 + 登记哈希），不接受任何外部输入。
  - 不打印密钥、不打印对象存储凭据，只打印年度、字节数与哈希前缀。
  - 公开来源回查入口仍指向巨潮官方原件，本脚本不创建任何公开全文镜像。

用法（需要本机 .env 或环境里有 SUPABASE_URL 与 SUPABASE_SERVICE_ROLE_KEY）：
  python scripts/upload_standard_sources_to_storage.py            # 上传并回验
  python scripts/upload_standard_sources_to_storage.py --verify   # 只回验读路径
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.data import ANNUAL_REPORT_SOURCES  # noqa: E402
from backend.app.secure_download import PDF_MAGIC  # noqa: E402
from backend.app.source_cache import (  # noqa: E402
    MAX_SOURCE_BYTES,
    _standard_source_object_path,
)
from backend.app.supabase_adapter import get_demo_task_client  # noqa: E402


def _load_and_verify(workspace_root: Path, year: int, source: dict) -> tuple[str, bytes]:
    """读本地原件并核对登记哈希；任何不符都拒绝上传。"""

    relative = str(source["source_file"])
    path = (workspace_root / relative).resolve()
    try:
        path.relative_to(workspace_root.resolve())
    except ValueError as error:
        raise SystemExit(f"{year} 年：登记路径超出工作区边界，拒绝处理。") from error
    if not path.is_file():
        raise SystemExit(f"{year} 年：本地找不到 {relative}，无法上传。")
    content = path.read_bytes()
    if not content.startswith(PDF_MAGIC):
        raise SystemExit(f"{year} 年：文件不是 PDF，拒绝上传。")
    if len(content) > MAX_SOURCE_BYTES:
        raise SystemExit(f"{year} 年：文件超过 {MAX_SOURCE_BYTES} 字节上限，拒绝上传。")
    actual = hashlib.sha256(content).hexdigest().upper()
    expected = str(source["file_sha256"]).upper()
    if actual != expected:
        raise SystemExit(f"{year} 年：SHA-256 与登记值不一致，拒绝上传。\n  登记 {expected[:16]}…\n  实际 {actual[:16]}…")
    return actual, content


def main() -> int:
    parser = argparse.ArgumentParser(description="回填并回验标准股份年报的私有桶缓存")
    parser.add_argument("--verify", action="store_true", help="只从私有桶读回并核对哈希，不上传")
    args = parser.parse_args()

    try:
        adapter = get_demo_task_client()
    except Exception as error:  # noqa: BLE001 - 凭据缺失要如实报阻塞，不能假装成功
        print(f"BLOCKED: 无法取得 Supabase 服务端凭据（{type(error).__name__}: {error}）")
        print("       本机 .env 未配置 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 时会走到这里。")
        return 2

    bucket = adapter.config.private_bucket
    print(f"目标 bucket：{bucket}（凭据已就位，未读取任何密钥值）")
    failed = 0
    for year in sorted(ANNUAL_REPORT_SOURCES):
        source = ANNUAL_REPORT_SOURCES[year]
        object_path = _standard_source_object_path(int(year), str(source["file_sha256"]))
        actual, content = _load_and_verify(ROOT, int(year), source)
        if not args.verify:
            try:
                adapter.upload_private_object(
                    bucket=bucket,
                    object_path=object_path,
                    content=content,
                    # 路径含内容哈希，同内容重试可安全覆盖；异内容不会撞同一路径。
                    upsert=True,
                )
            except Exception as error:  # noqa: BLE001 - 单份失败不掩盖，继续报其余年度
                print(f"FAIL  {year} 上传失败：{type(error).__name__}: {str(error)[:160]}")
                failed += 1
                continue
        try:
            fetched = adapter.download_private_object(bucket=bucket, object_path=object_path)
        except Exception as error:  # noqa: BLE001 - 读回失败就是验收不通过
            print(f"FAIL  {year} 读回失败：{type(error).__name__}: {str(error)[:160]}")
            failed += 1
            continue
        read_back = hashlib.sha256(fetched).hexdigest().upper()
        ok = read_back == actual and len(fetched) == len(content)
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {year}  字节 {len(fetched)}  读回哈希 {read_back[:16]}…  路径 {object_path}")

    if failed:
        print(f"\n{failed} 个年度未通过；私有桶来源缓存尚不可用，标准股份在 Render 上仍会降级。")
        return 1
    print("\n四份原件均已写入私有桶并通过读回校验；Render 重建时可从私有桶恢复。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
