"""供真人追加一条已签名的人工评分记录；本工具不代评分、不改历史行。

用法（必须由评分者本人执行，把姓名与分数如实填入）：

    backend/.venv/Scripts/python.exe scripts/record_human_score.py \
        --run-id RUN-V7-30E58BC730C6 \
        --i-am-human "张三" \
        --rubric-version B0B3-RUBRIC-V1 \
        --score 相关性=4 --score 依据充分性=3 --score 可执行性=4 \
        --note "第2条主张缺账龄佐证，扣分理由见盲评表"

检查项：
1. 评分人姓名必须显式给出，且不接受 AI、auto、codex、unknown、待填写等自动化身份；
2. 分数必须逐项写成 `名称=数值`，留空、非数值或超出 1—5 分都拒绝写入；
3. 记录只追加，`record_id` 重复即拒绝，不改写也不删除历史行；
4. 每行自带 `signed_payload_sha256`，绑定该行内容与评分人，供发布门禁独立回查。

边界：本脚本只负责把真人的评分如实落盘。它不校验分数是否“合理”，不代替第二
名评分者，也不生成任何效果结论。AI 不应代为运行本脚本填写他人分数。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_LEDGER = ROOT / "backend/release_records/human_scores/EVAL-20260828-RELEASE-CANDIDATE-V1.jsonl"
# 自动化身份一律不接受，避免把 AI 预评分混进真人评分门禁。
AUTOMATED_IDENTITIES = {"ai", "auto", "automatic", "codex", "qoder", "chatgpt", "gpt", "unknown", "待填写", "tbd", "n/a"}
SCORE_PATTERN = re.compile(r"^(?P<label>[^=]+)=(?P<value>-?\d+(?:\.\d+)?)$")
SCORE_MIN, SCORE_MAX = 1, 5
RUN_ID_PATTERN = re.compile(r"^RUN-[A-Z0-9-]{6,64}$")


def canonical_sha256(value: Any) -> str:
    """对行内容做规范化哈希，保证同一内容在任何机器上得到同一摘要。"""

    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_scores(pairs: list[str]) -> dict[str, float]:
    """把 `名称=数值` 解析成评分字典；任何一项不合规都直接终止。"""

    if not pairs:
        raise SystemExit("至少需要一项 --score 名称=数值；留空不得视为评分完成。")
    scores: dict[str, float] = {}
    for raw in pairs:
        match = SCORE_PATTERN.match(raw.strip())
        if not match:
            raise SystemExit(f"评分格式必须是 名称=数值，收到：{raw}")
        label = match.group("label").strip()
        value = float(match.group("value"))
        if not label:
            raise SystemExit(f"评分项名称为空：{raw}")
        if not SCORE_MIN <= value <= SCORE_MAX:
            raise SystemExit(f"评分项 {label} 的值 {value} 超出 {SCORE_MIN}—{SCORE_MAX} 分区间")
        scores[label] = value
    return scores


def _existing_record_ids(ledger: Path) -> set[str]:
    """读取已有行的 record_id，用于拒绝重复写入。"""

    if not ledger.is_file():
        return set()
    identifiers: set[str] = set()
    for line in ledger.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            identifiers.add(str(json.loads(text).get("record_id")))
        except json.JSONDecodeError:
            raise SystemExit("现有人工评分台账存在损坏行，先人工修复后再追加")
    return identifiers


def main() -> int:
    parser = argparse.ArgumentParser(description="追加一条真人已签名的人工评分记录")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--i-am-human", dest="scorer", default="", help="评分者本人真实姓名；不接受自动化身份")
    parser.add_argument("--score", action="append", default=[], help="评分项，形如 相关性=4，可重复")
    parser.add_argument("--rubric-version", default="", help="本次使用的评分标准版本，由真人先冻结")
    parser.add_argument("--blind-form-sha256", default="", help="所填盲评表文件的 SHA-256，便于回查")
    parser.add_argument("--note", default="")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    args = parser.parse_args()

    scorer = args.scorer.strip()
    if not scorer:
        raise SystemExit("必须显式提供 --i-am-human 姓名；缺少评分人时不写入，也不留空占位。")
    if scorer.lower() in AUTOMATED_IDENTITIES:
        raise SystemExit(f"评分人 {scorer} 是自动化身份，人工评分门禁不接受。")
    if not RUN_ID_PATTERN.fullmatch(args.run_id.strip()):
        raise SystemExit("run_id 格式不合法")
    scores = _parse_scores(args.score)
    if not args.rubric_version.strip():
        raise SystemExit("必须提供 --rubric-version；评分标准需由真人先冻结，不能默认套用。")

    ledger = Path(args.ledger)
    record_id = f"SCORE-{uuid.uuid4().hex[:12].upper()}"
    if record_id in _existing_record_ids(ledger):
        raise SystemExit("record_id 重复，拒绝写入")

    row: dict[str, Any] = {
        "schema_version": "human_score_record_v1",
        "record_id": record_id,
        "run_id": args.run_id.strip(),
        "scorer": scorer,
        "rubric_version": args.rubric_version.strip(),
        "scores": scores,
        "blind_form_sha256": args.blind_form_sha256.strip(),
        "note": args.note.strip(),
        "scored_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "signed_payload_sha256": "",
    }
    # 摘要绑定行内容与评分人；先算内容再填摘要位，避免自引用。
    row["signed_payload_sha256"] = canonical_sha256(row)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    try:
        display_path = str(ledger.resolve().relative_to(ROOT))
    except ValueError:
        # 台账允许放在仓库之外，此时直接显示绝对路径，不让打印失败掩盖写入结果。
        display_path = str(ledger.resolve())
    print(json.dumps({"appended": display_path, "record": row}, ensure_ascii=False, indent=2))
    print("提示：发布门禁要求同一次运行至少有两名不同真人的记录；本行只算一条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
