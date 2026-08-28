#!/usr/bin/env python3
"""Classify preserved R3 B2 failures without mutating raw records.

R3 was executed once per contract.  This report applies the current failure
taxonomy to the preserved error text so an earlier generic envelope can be
read alongside the more actionable stage classification.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_controlled_b1_b3_prescore import _validation_failure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.evaluation_dir.resolve()
    rows: list[dict[str, object]] = []
    for path in sorted((root / "runs").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("group") != "B2":
            continue
        error_text = str(record.get("failure_summary") or record.get("result", {}).get("validation_error") or "")
        code, stage = _validation_failure(ValueError(error_text))
        rows.append(
            {
                "record_file": path.name,
                "run_id": record.get("run_id"),
                "raw_failure_code": record.get("failure_code"),
                "raw_validation_failure_stage": record.get("validation_failure_stage"),
                "raw_failure_summary": error_text,
                "current_taxonomy_failure_code": code,
                "current_taxonomy_stage": stage,
                "raw_record_unchanged": True,
            }
        )
    if len(rows) != 3:
        raise SystemExit("expected three preserved B2 records")
    payload = {
        "schema_version": "b2_failure_classification_v1",
        "evaluation_id": root.name,
        "raw_records_mutated": False,
        "rows": rows,
        "boundary": "原始 R3 JSON 保留原样；current_taxonomy 是按当前代码对已记录错误文本的可行动分类，不是重新调用模型。",
    }
    (root / "B2_FAILURE_CLASSIFICATION.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# B2 失败分类补充说明｜{root.name}",
        "",
        "> 原始 JSON 未改写；本文件仅将已记录错误文本按当前分类器映射为可行动阶段。",
        "",
        "| run_id | 原始码 | 原始阶段 | 当前分类码 | 当前阶段 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| `{row['run_id']}` | `{row['raw_failure_code']}` | `{row['raw_validation_failure_stage']}` | `{row['current_taxonomy_failure_code']}` | `{row['current_taxonomy_stage']}` |")
    lines += ["", "当前 R3 没有重新调用或无限重试；原始响应哈希、token、耗时和失败摘要仍以对应 JSON 为准。"]
    (root / "B2_FAILURE_CLASSIFICATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "raw_records_mutated": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
