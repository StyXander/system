"""汇总真实模型对照结果，生成可复核的 Markdown 表。

只读取 outputs/model_arms 下的实际运行记录；缺失的臂明确标 not_run。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/model_arms"


def load_index() -> list[dict]:
    """扫描逐次落盘的结果文件；index.json 只记录最后一次调用，不能作为全集。"""
    rows = []
    for path in sorted(OUT.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        calls = run.get("provider_calls") or []
        rows.append({
            "pair_id": path.stem.split("_")[0],
            "mode": "_".join(path.stem.split("_")[1:]),
            "status": "completed",
            "run_id": run.get("run_id"),
            "model_status": run.get("model_status"),
            "provider_calls": len(calls),
            "input_tokens": sum(int(c.get("input_tokens") or 0) for c in calls),
            "output_tokens": sum(int(c.get("output_tokens") or 0) for c in calls),
            "duration_ms": run.get("duration_ms"),
            "ai_analyses": len(run.get("ai_analyses") or []),
            "financial_assessments": [
                {"verdict": entry.get("verdict"), "project_name": entry.get("project_name")}
                for entry in run.get("intelligence_trace", []) if entry.get("kind") == "financial_assessment"],
        })
    return rows


def latest_by_arm(results: list[dict]) -> dict[tuple[str, str], dict]:
    latest = {}
    for row in results:
        if row.get("status") != "completed":
            continue
        latest[(row["pair_id"], row["mode"])] = row
    return latest


def row_for(label: str, data: dict | None) -> str:
    if not data:
        return f"| {label} | not_run | — | — | — | — | — |"
    assessments = data.get("financial_assessments") or []
    verdicts = ", ".join(f"{item.get('verdict')}" for item in assessments[:4]) or "无"
    return (f"| {label} | {data.get('model_status')} | {data.get('provider_calls')} | "
            f"{data.get('input_tokens')} / {data.get('output_tokens')} | "
            f"{round((data.get('duration_ms') or 0)/1000)}s | {len(assessments)}（{verdicts}） | "
            f"{data.get('ai_analyses')} |")


def main() -> int:
    results = load_index()
    latest = latest_by_arm(results)
    pairs = sorted({row["pair_id"] for row in results})
    lines = ["# 真实模型对照（自动生成）", "",
             "| 方案 | 模型状态 | 调用次数 | 输入/输出token | 时长 | 财务候选判断 | 意见数 |",
             "|---|---|---|---|---|---|---|"]
    for pair in pairs:
        single = latest.get((pair, "single_model"))
        three = latest.get((pair, "three_agents"))
        adaptive = latest.get((pair, "adaptive_agents"))
        lines.append(f"| **{pair}** | | | | | | |")
        lines.append(row_for("仅计算（无模型）", None))
        lines.append(row_for("单模型", single))
        lines.append(row_for("三角色", three))
        lines.append(row_for("自适应", adaptive))
    lines += ["", "说明：", "- 成本列未列，因供应商未回传计价；以 token 为可复核口径。",
              "- 「财务候选判断」为专用财务复核角色对穿透候选的逐条表态数量。",
              "- not_run 表示该臂未执行，不代表失败。"]
    text = "\n".join(lines)
    print(text)
    (ROOT / "outputs/model_arm_summary.md").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
