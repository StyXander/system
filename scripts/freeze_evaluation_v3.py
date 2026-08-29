"""已安全退役：本脚本属于 2026-08-11 旧评估（evaluation_v3）的历史冻结工具。

退役原因：它动态导入 evaluation 模块的当前 EVALUATION_ID 与写入函数；
在评估编号升级后再次运行，会把新目录的 dashboard.json 重写为旧结构
（模型为空、部分案例 B2/B3 被标为不适用），污染正式评估的派生汇总。

正式冻结请使用 freeze_evaluation_v4.py（不可覆盖目录 + 逐节 SHA-256）。
旧合同 EVAL-20260811-COMPETITION-8CASE-V1 与其产物只读保留为历史。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUCCESSOR = ROOT / "scripts" / "freeze_evaluation_v4.py"
OLD_CONTRACT = ROOT / "outputs" / "evaluation_v3" / "current.json"


def main() -> None:
    raise SystemExit(
        "安全停止：freeze_evaluation_v3.py 已退役，拒绝写入任何评估目录。\n"
        f"旧合同只读保留：{OLD_CONTRACT}\n"
        f"正式冻结请使用：{SUCCESSOR}"
    )


if __name__ == "__main__":
    main()
