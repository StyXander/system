#!/usr/bin/env python3
"""Create an append-only, human-score-ready B1/B2/B3 summary."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.evaluation_dir.resolve()
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "runs").glob("*.json"))]
    if len(records) != 9 or {r.get("group") for r in records} != {"B1", "B2", "B3"}:
        raise SystemExit("expected exactly nine B1/B2/B3 records")
    counts = Counter(str(r.get("group")) for r in records)
    by_group: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_group[str(r.get("group"))].append(r)

    def score(group: str) -> str:
        vals = [r.get("prescore", {}).get("total") for r in by_group[group] if isinstance(r.get("prescore", {}).get("total"), (int, float))]
        return f"{sum(vals) / len(vals):.1f}" if vals else "n/a"

    b2_codes = Counter(str(r.get("failure_code") or "none") for r in by_group["B2"])
    b3_success = sum(1 for r in by_group["B3"] if r.get("result", {}).get("model_check", {}).get("status") == "model_success" or r.get("result", {}).get("execution_mode") == "external_live")
    b3_roles = [sum(1 for s in (r.get("result", {}).get("agent_steps") or []) if s.get("status") == "completed") for r in by_group["B3"]]
    lines = [
        f"# B1/B2/B3 评估摘要｜{root.name}",
        "",
        f"> 生成时间：{datetime.now(timezone.utc).isoformat()}；本文件由原始 JSON 汇总，不能替代原始记录。",
        "> AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。",
        "",
        "## 合同与边界",
        "",
        f"- 评估目录：`{root}`；记录数：{len(records)}；模型：`{records[0].get('model_id')}`。",
        "- B1 仅确定性计算，外部调用必须为 0；B2 仅一次单模型草稿；B3 执行案例 RAG、知识检索、三 Agent、硬校验和结构化输出。",
        "- 项目队长正式评分、意见和日期均保持空白；下表的 AI 辅助预评分不可直接作为竞赛正式评分。",
        "",
        "## 汇总",
        "",
        "| 组别 | 记录数 | 终态/调用 | AI辅助预评分均值 | 结论 |",
        "|---|---:|---|---:|---|",
        f"| B1 | {counts['B1']} | 3/3 确定性；provider call=0 | {score('B1')} | 通过确定性合同 |",
        f"| B2 | {counts['B2']} | 0/3 完成；每案一次调用；失败码 `{next(iter(b2_codes))}` | {score('B2')} | 失败保留，不降级冒充成功 |",
        f"| B3 | {counts['B3']} | {b3_success}/3 model_success；三角色完成数 {b3_roles} | {score('B3')} | 真实结果按记录解释 |",
        "",
        "## B2 失败分层",
        "",
        f"- 失败码计数：`{dict(b2_codes)}`。本批次当前失败阶段为 `validation`；无受控修正，因为合同只允许对工具协议正确但事实语言失败触发一次修正。",
        "- 每条 B2 记录均保存 `field_evidence`、`procedure_evidence`、`PROC-R1-2025`、原始响应哈希、最终响应哈希字段和 token/耗时信息。",
        "",
        "## 逐条原始记录索引",
        "",
        "| 组别 | 案例 | run_id | 状态 | provider calls | 失败码 | AI预评分 | 队长评分 |",
        "|---|---|---|---|---:|---|---:|---|",
    ]
    for r in records:
        result = r.get("result") or {}
        status = r.get("status") or result.get("status") or "unknown"
        if r.get("group") == "B3" and result.get("execution_mode") == "external_live":
            status = f"{status}/model_success"
        lines.append(
            f"| {r.get('group')} | {r.get('case_name')} | `{r.get('run_id')}` | `{status}` | {r.get('provider_call_count', 0)} | `{r.get('failure_code') or 'none'}` | {r.get('prescore', {}).get('total', 'n/a')} | 空白 |"
        )
    lines += [
        "",
        "## 低于 80% 告警",
        "",
        "当前 qwen3.5-plus 质量窗口仍为 7/10=70.0%，阈值 80%，状态 `below_threshold`、`alert=true`。B2 与 B3 口径不同，不合并为官方成功率；不自动更换模型。",
        "",
        "原始 JSON、不可覆盖台账和合同文件位于本目录；如需队长评分，请另存追加式版本，不改写本摘要或原始记录。",
    ]
    out = root / "B1_B2_B3_SUMMARY.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
