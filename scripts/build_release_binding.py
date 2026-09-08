"""生成外置版本绑定锚点：把源码文件、运行原件与真人批准锁在同一条哈希上。

用法（默认只生成待签锚点，不伪造批准）：

    backend/.venv/Scripts/python.exe scripts/build_release_binding.py \
        --release-id RELEASE-CANDIDATE-20260828-V1 \
        --tracked-file backend/release_records/current_release.json \
        --run-id RUN-V7-30E58BC730C6 \
        --output ../audittrace-release-bindings/20260908.json

检查项：绑定文件必须落在工作区之外；git HEAD 必须是 40 位提交号；每个登记文件
与每个运行原件都必须能在磁盘上定位并算出哈希。批准人留空时锚点保持待签状态，
门禁会继续阻断，而不是把空缺补成“已批准”。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.release_evidence import build_release_binding  # noqa: E402


def _current_head() -> str:
    """读取当前提交号；读不到就终止，避免用猜测值生成锚点。"""

    process = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if process.returncode != 0:
        raise SystemExit("无法读取 git HEAD，绑定生成终止")
    return process.stdout.strip().lower()


def main() -> int:
    parser = argparse.ArgumentParser(description="生成外置版本绑定锚点")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--git-head", default=None, help="默认取当前 git HEAD")
    parser.add_argument("--tracked-file", action="append", default=[], help="需要锁定的仓库内文件，可重复")
    parser.add_argument("--run-id", action="append", default=[], help="需要锁定的运行原件编号，可重复")
    parser.add_argument("--output", required=True, help="锚点文件路径，必须位于工作区之外")
    parser.add_argument("--approver", default="", help="真人批准人姓名；留空则锚点保持待签")
    parser.add_argument("--approved-at", default="", help="批准时间戳，由批准人本人填写")
    args = parser.parse_args()

    binding_path = Path(args.output).expanduser().resolve()
    payload = build_release_binding(
        workspace_root=ROOT,
        release_id=args.release_id,
        git_head=args.git_head or _current_head(),
        tracked_files=args.tracked_file,
        run_ids=args.run_id,
        binding_path=binding_path,
        approver=args.approver,
        approved_at=args.approved_at,
    )
    print(
        json.dumps(
            {
                "output": str(binding_path),
                "git_head": payload["git_head"],
                "tracked_files": len(payload["repo_files"]),
                "run_records": len(payload["run_records"]),
                "content_sha256": payload["human_approval"]["content_sha256"],
                "approval_state": "signed" if payload["human_approval"]["signature_sha256"] else "pending_human_approval",
                "next_step": "由真人把姓名与批准时间写入 human_approval 并补 signature_sha256，或用 --approver 重新生成",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
