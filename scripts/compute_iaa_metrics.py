"""独立标注一致性与 Cohen's Kappa 统计工具 (Inter-Annotator Agreement, IAA)。

用于挑战杯/科创杯科研论文中独立人工金标质量证明：
  1. 计算观察一致率 (Percent Observed Agreement, P_o) 与期望一致率 (P_e)
  2. 计算标准 Cohen's Kappa 统计量 (κ)
  3. 五类无序标签不计算线性加权Kappa
  4. 统计两名独立标注员分歧样本与独立专家仲裁 (Adjudication) 决议分布
  5. 导出学术报告标准 Markdown 表格与 JSON 结果
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERDICT_CLASSES = [
    "CONFIRMED_CONSISTENT",  # 确认一致
    "EXPLAINED_DIFFERENCE",  # 已解释差异
    "INSUFFICIENT_EVIDENCE", # 证据不足
    "NOT_COMPARABLE",        # 不可比
    "SUSPECTED_CONFLICT",    # 疑似冲突
]

VERDICT_ZH = {
    "CONFIRMED_CONSISTENT": "确认一致",
    "EXPLAINED_DIFFERENCE": "已解释差异",
    "INSUFFICIENT_EVIDENCE": "证据不足",
    "NOT_COMPARABLE": "不可比",
    "SUSPECTED_CONFLICT": "疑似冲突",
}


def normalize_verdict(val: str | None) -> str | None:
    if not val:
        return None
    cleaned = str(val).strip().upper()
    for c in VERDICT_CLASSES:
        if c == cleaned or VERDICT_ZH[c] in str(val):
            return c
    return None


def compute_cohens_kappa(rater_a: list[str], rater_b: list[str], categories: list[str]) -> dict:
    n = len(rater_a)
    if n == 0 or len(rater_b) != n:
        raise ValueError("需要非空且等长的独立标注")

    # 构建混淆矩阵
    cat_to_idx = {c: i for i, c in enumerate(categories)}
    k = len(categories)
    matrix = [[0] * k for _ in range(k)]

    for a, b in zip(rater_a, rater_b):
        ia = cat_to_idx[a]
        ib = cat_to_idx[b]
        matrix[ia][ib] += 1

    # 观察一致率 P_o
    agree_count = sum(matrix[i][i] for i in range(k))
    p_o = agree_count / n

    # 期望一致率 P_e
    row_sums = [sum(matrix[i]) for i in range(k)]
    col_sums = [sum(matrix[i][j] for i in range(k)) for j in range(k)]
    p_e = sum((row_sums[i] * col_sums[i]) for i in range(k)) / (n * n)

    # Cohen's Kappa
    kappa = (p_o - p_e) / (1.0 - p_e) if (1.0 - p_e) != 0 else None

    # These are nominal categories; list order does not define a meaningful distance.
    weighted_kappa = None

    # Kappa 解释区间 (Landis & Koch, 1977)
    interpretation = "Undefined (single-category marginals)" if kappa is None else "Almost Perfect" if kappa > 0.8 else \
                     "Substantial" if kappa > 0.6 else \
                     "Moderate" if kappa > 0.4 else \
                     "Fair" if kappa > 0.2 else "Slight / Poor"

    return {
        "n_samples": n,
        "n_agreed": agree_count,
        "percent_agreement": round(p_o, 4),
        "expected_agreement": round(p_e, 4),
        "cohens_kappa": round(kappa, 4) if kappa is not None else None,
        "weighted_kappa": weighted_kappa,
        "interpretation": interpretation,
        "matrix": matrix,
        "categories": categories,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "backend/evaluation/connectivity/matter_cases.json",
                        help="包含独立标注的案例 JSON 文件路径")
    parser.add_argument("--output-report", type=Path, help="保存统计结果 Markdown/JSON 的路径")
    parser.add_argument("--task-type",choices=['amount_reconciliation','relation_tracing'],default='amount_reconciliation')
    args = parser.parse_args()
    categories=VERDICT_CLASSES if args.task_type=='amount_reconciliation' else ['supported','limited','pending','conflicting','not_comparable','invalid']
    def normalize(value):
        return normalize_verdict(value) if args.task_type=='amount_reconciliation' else value if value in categories else None

    if not args.cases.exists():
        print(f"[错误] 案例文件未找到: {args.cases}")
        return 1

    content = json.loads(args.cases.read_text(encoding="utf-8"))
    scenarios = content.get("scenarios") if isinstance(content, dict) and "scenarios" in content else content

    pairs = []
    disagreements = []
    adjudicated = []

    for item in scenarios:
        if item.get('research_task_type','amount_reconciliation')!=args.task_type:continue
        cid = item.get("case_id") or item.get("id")
        annos = item.get("annotations", [])
        adjudication = item.get("adjudication")

        if len(annos) >= 2:
            v_a = normalize(annos[0].get("verdict"))
            v_b = normalize(annos[1].get("verdict"))
            if not v_a or not v_b or not annos[0].get('annotator_id') or not annos[1].get('annotator_id') or annos[0]['annotator_id']==annos[1]['annotator_id']:
                continue
            pairs.append({
                "case_id": cid,
                "category": item.get("category", ""),
                "rater_a": v_a,
                "rater_b": v_b,
                "rater_a_id": annos[0].get("annotator_id", "Rater-A"),
                "rater_b_id": annos[1].get("annotator_id", "Rater-B"),
                "agreed": (v_a == v_b),
                "adjudication": adjudication,
            })
            if v_a != v_b:
                final_v = None
                if isinstance(adjudication, dict):
                    final_v = adjudication.get("final_verdict")
                elif adjudication:
                    final_v = str(adjudication)
                disagreements.append({
                    "case_id": cid,
                    "category": item.get("category", ""),
                    "rater_a": v_a,
                    "rater_b": v_b,
                    "final_adjudication": normalize(final_v) if final_v else "待仲裁 (Pending)",
                })
        if adjudication:
            adjudicated.append(item)

    print(f"=== 独立人工标注信度 (IAA) 统计 ===")
    print(f"案例总数: {len(scenarios)}")
    print(f"完成双人独立标注案例数: {len(pairs)}")

    if not pairs:
        print("[提示] 当前案例库中的 annotations 尚未填入独立标注数据。")
        print("请在 matter_cases.json 中为各案例填入 annotations: [{'annotator_id':'A', 'verdict':'...'}, {'annotator_id':'B', 'verdict':'...'}] 后重新运行。")
        return 0

    rater_a_list = [p["rater_a"] for p in pairs]
    rater_b_list = [p["rater_b"] for p in pairs]
    stats = compute_cohens_kappa(rater_a_list, rater_b_list, categories)
    kappa_text=f"{stats['cohens_kappa']:.4f}" if stats['cohens_kappa'] is not None else 'N/A'

    print("\n--- 核心一致性指标 ---")
    print(f"有效标注对数量: {stats['n_samples']}")
    print(f"完全一致案例数: {stats['n_agreed']} ({stats['percent_agreement']*100:.1f}%)")
    print(f"期望一致率 (P_e): {stats['expected_agreement']*100:.1f}%")
    print(f"Cohen's Kappa (κ): {kappa_text} ({stats['interpretation']})")
    print("五类为无序类别，不计算线性加权Kappa")

    if disagreements:
        print(f"\n--- 分歧案例明细 (共 {len(disagreements)} 项) ---")
        print(f"{'Case ID':<12} | {'业务类别':<14} | {'标注员 A':<18} | {'标注员 B':<18} | {'专家最终仲裁':<16}")
        print("-" * 85)
        for d in disagreements:
            print(f"{d['case_id']:<12} | {d['category']:<14} | {VERDICT_ZH.get(d['rater_a'], d['rater_a']):<18} | {VERDICT_ZH.get(d['rater_b'], d['rater_b']):<18} | {VERDICT_ZH.get(d['final_adjudication'], d['final_adjudication']):<16}")

    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        if args.output_report.suffix == ".json":
            out_data = {
                "iaa_stats": stats,
                "disagreements": disagreements,
                "total_cases": len(scenarios),
                "annotated_cases": len(pairs),
            }
            args.output_report.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            md_lines = [
                "# 专家独立标注信度与一致性报告 (Inter-Annotator Agreement Report)",
                "",
                f"> 案例来源: `{args.cases.name}` | 样本总数: {len(scenarios)} | 完成独立案例数: {len(pairs)}",
                "",
                "## 1. 核心信度统计量",
                "",
                "| 统计指标 | 计算数值 | 学术标准释义 (Landis & Koch) |",
                "| :--- | :---: | :--- |",
                f"| **观察一致率 (Observed Agreement, $P_o$)** | **{stats['percent_agreement']*100:.1f}%** | 两位标注员直接达成完全共识的比例 |",
                f"| **期望一致率 (Expected Agreement, $P_e$)** | {stats['expected_agreement']*100:.1f}% | 仅凭偶然机遇达成一致的理论概率 |",
                f"| **Cohen's Kappa 统计量 ($\\kappa$)** | **`{kappa_text}`** | **{stats['interpretation']}** |",
                "",
            ]
            if disagreements:
                md_lines.extend([
                    "## 2. 分歧案例明细与独立专家终审仲裁表",
                    "",
                    "| 案例编号 (Case ID) | 业务类别 | 标注员 A 结论 | 标注员 B 结论 | 主审专家最终仲裁 (Adjudication) |",
                    "| :--- | :--- | :--- | :--- | :--- |",
                ])
                for d in disagreements:
                    md_lines.append(f"| `{d['case_id']}` | {d['category']} | {VERDICT_ZH.get(d['rater_a'], d['rater_a'])} | {VERDICT_ZH.get(d['rater_b'], d['rater_b'])} | **{VERDICT_ZH.get(d['final_adjudication'], d['final_adjudication'])}** |")

            args.output_report.write_text("\n".join(md_lines), encoding="utf-8")
            print(f"[完成] IAA 报告已导出至: {args.output_report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
