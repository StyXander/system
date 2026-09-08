"""独立复验发布证据：重算运行原件哈希、调用 ID、事实闸门与外置版本绑定。

用法：

    backend/.venv/Scripts/python.exe scripts/verify_release_evidence.py \
        --run-id RUN-V7-30E58BC730C6 \
        --binding ../audittrace-release-bindings/20260908.json \
        --json artifacts/release-evidence-verify.json

检查项：
1. 原始运行记录能否唯一命中，文件 SHA-256 是否与记录内 run_id 自洽；
2. 三角色是否齐备且状态完成，缺角色或多角色都不放行；
3. 调用 ID 能否由逐次尝试的输入/响应哈希重算得到，并与存储值一致；
4. 运行级调用数与角色级调用数是否相等，缓存回放与备用子运行是否被排除；
5. 确定性事实语言闸门能否对落盘输出重跑通过；
6. 人工评分台账是否给出至少两名真人的已签名非空评分，且整行摘要可重算，
   维度与区间符合**已由真人冻结**的评分标准；
7. 外置版本绑定是否位于工作区之外、内容哈希是否自洽、必需清单是否齐、
   指向的文件与本次 --run-id 的运行原件是否漂移、是否覆盖了本次复验的运行。

任何一项不成立都以退出码 1 结束，并把原因写进报告；本脚本不写回任何状态文件。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.release_evidence import (  # noqa: E402
    HUMAN_SCORE_RUBRIC_DIR_RELATIVE,
    BINDING_VERIFIED,
    build_b3_evidence_from_disk,
    verify_release_binding,
)


def _git_head() -> str | None:
    """读取当前 HEAD；失败返回 None，让绑定校验自己报不可核验。"""

    process = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return process.stdout.strip().lower() if process.returncode == 0 else None


def _worktree_dirty() -> bool | None:
    """工作区是否脏；读不到时返回 None，不猜测为干净。"""

    process = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return bool(process.stdout.strip()) if process.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description="独立复验发布证据与外置版本绑定")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ledger", default=None, help="人工评分台账 JSONL 路径")
    parser.add_argument("--binding", default=None, help="外置版本绑定文件路径")
    parser.add_argument("--expected-model-id", default=None)
    parser.add_argument("--rubric-dir", default=str(ROOT / HUMAN_SCORE_RUBRIC_DIR_RELATIVE), help="已冻结人工评分标准目录")
    parser.add_argument("--json", dest="json_out", default=None, help="把完整报告另存为 JSON")
    args = parser.parse_args()

    ledger = Path(args.ledger).expanduser().resolve() if args.ledger else None
    rubric_dir = Path(args.rubric_dir).expanduser().resolve()
    ledger_relative: str | None = None
    if ledger is not None:
        try:
            ledger_relative = str(ledger.relative_to(ROOT))
        except ValueError:
            # 台账在仓库之外时无法与锚点里的相对路径对上，按原样传给绑定校验去拒绝。
            ledger_relative = str(ledger)
    result = build_b3_evidence_from_disk(
        args.run_id,
        workspace_root=ROOT,
        human_score_ledger_path=ledger,
        human_rubric_dir=rubric_dir,
        expected_model_id=args.expected_model_id,
    )
    failures: list[str] = []
    if result.get("status") != "loaded":
        failures.append(f"B3 证据重算未通过：{result.get('reason')}")
    evidence = result.get("evidence") or {}
    if evidence and evidence.get("posthoc_validation_error"):
        failures.append(f"事实语言闸门复算失败：{evidence['posthoc_validation_error']}")
    if evidence and not evidence.get("human_scores_completed"):
        failures.append("人工评分未完成或未绑定独立台账")

    binding_report: dict[str, Any] = {"status": "not_provided", "reason": "未提供绑定文件"}
    if args.binding:
        binding_report = verify_release_binding(
            Path(args.binding).expanduser().resolve(),
            workspace_root=ROOT,
            git_head=_git_head(),
            worktree_dirty=_worktree_dirty(),
            expected_run_ids=[args.run_id],
            expected_human_score_ledger=ledger_relative,
        )
        if binding_report.get("status") != BINDING_VERIFIED:
            failures.append(f"外置版本绑定未通过：{binding_report.get('reason')}")

    report = {
        "run_id": args.run_id,
        "evidence_status": result.get("status"),
        "evidence_reason": result.get("reason"),
        "provenance": result.get("provenance"),
        "binding": {k: v for k, v in binding_report.items() if k != "binding"},
        "failures": failures,
        "boundary": "本脚本只证明记录与磁盘原件一致；不证明专业判断正确、不证明效果提升，也不代替真人签字。",
    }
    if args.json_out:
        target = Path(args.json_out).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for line in failures or ["全部重算项一致"]:
        print(f"- {line}")
    print("RESULT:", "PASS" if not failures else "FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
