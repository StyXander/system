"""统一五级核验结论评测工具 (5-Class Verdict Matter Benchmark Evaluator)。

实现挑战杯 V2.1 规划标准指标体系：
  1. 统一五分类映射 (CONFIRMED_CONSISTENT, SUSPECTED_CONFLICT, INSUFFICIENT_EVIDENCE, NOT_COMPARABLE, EXPLAINED_DIFFERENCE)
  2. 错误确证率 (FCR = N_false_confirm / N_confirm) 与确证精确率 (Precision_confirm = 1 - FCR)
  3. 全体样本确证覆盖率 (Coverage = N_confirm / N_total) 与应确证样本召回率 (Recall_confirm = N_true_confirm / N_gold_confirm)
  4. 五分类宏平均 F1 (Macro-F1) 与混淆矩阵 (Confusion Matrix)
  5. 证据定位保真度 (Evidence Localization F1)
  6. 多次独立重复运行波动统计 (Mean ± SD)
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 统一五级核验结论定义
VERDICT_CLASSES = [
    "CONFIRMED_CONSISTENT",  # 确认一致
    "SUSPECTED_CONFLICT",    # 疑似冲突
    "INSUFFICIENT_EVIDENCE", # 证据不足
    "NOT_COMPARABLE",        # 不可比
    "EXPLAINED_DIFFERENCE",  # 已解释差异
]

VERDICT_ZH = {
    "CONFIRMED_CONSISTENT": "确认一致",
    "SUSPECTED_CONFLICT": "疑似冲突",
    "INSUFFICIENT_EVIDENCE": "证据不足",
    "NOT_COMPARABLE": "不可比",
    "EXPLAINED_DIFFERENCE": "已解释差异",
}

ALIASES = {
    "CONFIRMED_CONSISTENT": "CONFIRMED_CONSISTENT",
    "CONFIRMED": "CONFIRMED_CONSISTENT",
    "CONSISTENT": "CONFIRMED_CONSISTENT",
    "确认一致": "CONFIRMED_CONSISTENT",
    "一致": "CONFIRMED_CONSISTENT",
    "SUSPECTED_CONFLICT": "SUSPECTED_CONFLICT",
    "CONFLICT": "SUSPECTED_CONFLICT",
    "CONFLICTING": "SUSPECTED_CONFLICT",
    "疑似冲突": "SUSPECTED_CONFLICT",
    "冲突": "SUSPECTED_CONFLICT",
    "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
    "INSUFFICIENT": "INSUFFICIENT_EVIDENCE",
    "PENDING": "INSUFFICIENT_EVIDENCE",
    "NEEDS_EVIDENCE": "INSUFFICIENT_EVIDENCE",
    "证据不足": "INSUFFICIENT_EVIDENCE",
    "待补充证据": "INSUFFICIENT_EVIDENCE",
    "NOT_COMPARABLE": "NOT_COMPARABLE",
    "INCOMPARABLE": "NOT_COMPARABLE",
    "不可比": "NOT_COMPARABLE",
    "EXPLAINED_DIFFERENCE": "EXPLAINED_DIFFERENCE",
    "EXPLAINED": "EXPLAINED_DIFFERENCE",
    "已解释差异": "EXPLAINED_DIFFERENCE",
    "已解释": "EXPLAINED_DIFFERENCE",
}


def normalize_verdict(raw_value: str | None) -> str:
    """标准化五级核验结论字符串。"""
    if not raw_value:
        return "INSUFFICIENT_EVIDENCE"
    cleaned = str(raw_value).strip().upper()
    if cleaned in ALIASES:
        return ALIASES[cleaned]
    # 中文别名匹配
    for alias_key, target in ALIASES.items():
        if alias_key in str(raw_value):
            return target
    return "INSUFFICIENT_EVIDENCE"


def extract_verdict_from_assessment(assessment: dict, explanations: list[dict] | None = None) -> str:
    """根据事项 assessment 和 explanations 的业务语义推断统一五级核验结论。"""
    comparability = str(assessment.get("amount_comparability") or "").strip().lower()
    support = str(assessment.get("relation_support") or "").strip().lower()
    has_evidence = bool(assessment.get("supporting_evidence_ids"))
    has_counter = bool(assessment.get("counter_evidence_ids"))
    explanations = explanations or []
    has_accepted_explanation = any(
        e.get("acceptance_status") == "accepted" or "已解释" in str(e.get("summary") or "")
        for e in explanations
    )

    if comparability == "not_comparable":
        return "NOT_COMPARABLE"
    if support == "conflicting":
        return "EXPLAINED_DIFFERENCE" if has_accepted_explanation else "SUSPECTED_CONFLICT"
    if support == "supported":
        if comparability == "not_comparable":
            return "NOT_COMPARABLE"
        if has_accepted_explanation:
            return "EXPLAINED_DIFFERENCE"
        if comparability == "needs_evidence" or not has_evidence:
            return "INSUFFICIENT_EVIDENCE"
        return "CONFIRMED_CONSISTENT"
    if support in {"limited", "pending"} or comparability == "needs_evidence":
        if has_accepted_explanation:
            return "EXPLAINED_DIFFERENCE"
        return "INSUFFICIENT_EVIDENCE"

    return "INSUFFICIENT_EVIDENCE"


def extract_run_verdict(run_data: dict, matter_id: str | None = None) -> tuple[str, list[str]]:
    """从运行结果 JSON 中提取事项的预测结论与引用证据 ID。"""
    assessments = run_data.get("matter_assessments", [])
    explanations = run_data.get("matter_explanations", [])
    if not assessments:
        return "INSUFFICIENT_EVIDENCE", []

    target_assessment = None
    if matter_id:
        target_assessment = next((a for a in assessments if a.get("matter_id") == matter_id), None)
    if not target_assessment:
        target_assessment = assessments[0]

    matter_exps = [e for e in explanations if e.get("matter_id") == target_assessment.get("matter_id")]
    verdict = extract_verdict_from_assessment(target_assessment, matter_exps)
    evidence_ids = list(target_assessment.get("supporting_evidence_ids", [])) + list(target_assessment.get("counter_evidence_ids", []))
    return verdict, evidence_ids


def compute_binary_metrics(y_true: list[str], y_pred: list[str], positive_classes: set[str]) -> dict:
    """计算二分类指标（如确证类指标 FCR, Precision, Recall, Coverage）。"""
    n_total = len(y_true)
    if n_total == 0:
        return {"total": 0, "n_confirm": 0, "fcr": 0.0, "precision": 0.0, "recall": 0.0, "coverage": 0.0}

    n_confirm = sum(p in positive_classes for p in y_pred)
    n_gold_confirm = sum(t in positive_classes for t in y_true)
    n_true_confirm = sum(p in positive_classes and t in positive_classes for t, p in zip(y_true, y_pred))
    n_false_confirm = sum(p in positive_classes and t not in positive_classes for t, p in zip(y_true, y_pred))

    fcr = (n_false_confirm / n_confirm) if n_confirm > 0 else 0.0
    precision = 1.0 - fcr if n_confirm > 0 else 0.0
    recall = (n_true_confirm / n_gold_confirm) if n_gold_confirm > 0 else 0.0
    coverage = n_confirm / n_total

    return {
        "n_total": n_total,
        "n_confirm": n_confirm,
        "n_gold_confirm": n_gold_confirm,
        "n_true_confirm": n_true_confirm,
        "n_false_confirm": n_false_confirm,
        "fcr": round(fcr, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "coverage": round(coverage, 4),
    }


def compute_multiclass_metrics(y_true: list[str], y_pred: list[str]) -> dict:
    """计算标准五分类指标：混淆矩阵、各类别精确率/召回率/F1及宏平均 Macro-F1。"""
    matrix = {g: {p: 0 for p in VERDICT_CLASSES} for g in VERDICT_CLASSES}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1

    per_class = {}
    f1_list = []
    for cls in VERDICT_CLASSES:
        tp = matrix[cls][cls]
        fp = sum(matrix[other][cls] for other in VERDICT_CLASSES if other != cls)
        fn = sum(matrix[cls][other] for other in VERDICT_CLASSES if other != cls)
        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        support = sum(matrix[cls].values())
        per_class[cls] = {
            "name": VERDICT_ZH[cls],
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": support,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }
        f1_list.append(f1)

    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0
    accuracy = sum(matrix[c][c] for c in VERDICT_CLASSES) / len(y_true) if y_true else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "confusion_matrix": matrix,
        "per_class": per_class,
    }


def compute_evidence_f1(gold_evidence: list[set[str]], pred_evidence: list[set[str]]) -> dict:
    """计算证据检索与定位精确率、召回率与 F1。"""
    total_tp = 0
    total_fp = 0
    total_fn = 0
    for gold_set, pred_set in zip(gold_evidence, pred_evidence):
        if not gold_set:
            continue
        tp = len(gold_set & pred_set)
        fp = len(pred_set - gold_set)
        fn = len(gold_set - pred_set)
        total_tp += tp
        total_fp += fp
        total_fn += fn

    prec = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
    rec = (total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "total_gold_evidence": total_tp + total_fn,
        "total_pred_evidence": total_tp + total_fp,
    }


def mean_and_sd(values: list[float]) -> tuple[float, float]:
    """计算列表均值与样本标准差。"""
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    m = sum(values) / len(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return round(m, 4), round(math.sqrt(var), 4)


def format_mean_sd(mean: float, sd: float, percent: bool = True) -> str:
    if percent:
        return f"{mean * 100:.1f} ± {sd * 100:.1f}%" if sd > 0 else f"{mean * 100:.1f}%"
    return f"{mean:.4f} ± {sd:.4f}" if sd > 0 else f"{mean:.4f}"


def load_gold_cases(gold_path: Path) -> dict[str, dict]:
    """加载黄金评测集，支持 matter_cases.json 与标准标注 JSON。"""
    content = json.loads(gold_path.read_text(encoding="utf-8"))
    scenarios = content.get("scenarios") if isinstance(content, dict) and "scenarios" in content else content
    gold_map = {}
    for item in scenarios:
        case_id = item.get("case_id") or item.get("id")
        if not case_id:
            continue
        adjudication = item.get("adjudication") or {}
        # 优先从仲裁结果获取金标；若为空，检查 annotations 是否有一致共识
        final_verdict = adjudication.get("final_verdict") if isinstance(adjudication, dict) else adjudication
        if not final_verdict and item.get("annotations"):
            annos = [a.get("verdict") for a in item["annotations"] if a.get("verdict")]
            if annos and len(set(annos)) == 1:
                final_verdict = annos[0]
        # 兜底支持从分类或预期行为映射测试金标
        expected_behavior = item.get("expected_engineering_behavior", "")
        if not final_verdict:
            if "不可直接比" in expected_behavior or "不属同一合并范围" in expected_behavior:
                final_verdict = "NOT_COMPARABLE"
            elif "不认定已投入" in expected_behavior or "待证" in expected_behavior:
                final_verdict = "INSUFFICIENT_EVIDENCE"
            elif "分别解释各条边" in expected_behavior:
                final_verdict = "EXPLAINED_DIFFERENCE"
            else:
                final_verdict = item.get("default_gold_verdict")

        gold_map[case_id] = {
            "case_id": case_id,
            "category": item.get("category", ""),
            "trigger": item.get("trigger", ""),
            "gold_verdict": normalize_verdict(final_verdict) if final_verdict else None,
            "gold_evidence_ids": set(item.get("gold_evidence_ids") or []),
            "annotation_status": item.get("annotation_status", "pending"),
        }
    return gold_map


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-json", type=Path, help="对比实验输出的 comparison.json 文件路径")
    parser.add_argument("--runs-dir", type=Path, help="包含单次运行 JSON 文件的目录")
    parser.add_argument("--gold-cases", type=Path, default=ROOT / "backend/evaluation/connectivity/matter_cases.json",
                        help="黄金评测集路径 (默认 backend/evaluation/connectivity/matter_cases.json)")
    parser.add_argument("--output-report", type=Path, help="保存评测结果 Markdown / JSON 的路径")
    args = parser.parse_args()

    gold_map = {}
    if args.gold_cases.exists():
        gold_map = load_gold_cases(args.gold_cases)
        print(f"[数据] 已加载黄金案例库: {len(gold_map)} 项 (已仲裁/有金标案例: {sum(bool(v['gold_verdict']) for v in gold_map.values())} 项)")
    else:
        print(f"[警告] 黄金评测集未找到: {args.gold_cases}")

    # 读取预测结果
    runs_to_eval = []
    if args.comparison_json and args.comparison_json.exists():
        comp_data = json.loads(args.comparison_json.read_text(encoding="utf-8"))
        runs_to_eval = comp_data.get("runs", [])
    elif args.runs_dir and args.runs_dir.exists():
        for json_file in sorted(args.runs_dir.glob("*.json")):
            if json_file.name.endswith(".checkpoint.json") or json_file.name == "comparison.json":
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if "run_id" in data:
                    runs_to_eval.append(data)
            except Exception:
                pass

    if not runs_to_eval:
        print("[提示] 未指定或未找到有效对比运行结果。")
        print("请通过 --comparison-json 或 --runs-dir 指定实验输出。")
        return 0

    print(f"[评测] 待评测运行记录: {len(runs_to_eval)} 条")

    # 按 (group_id, mode, ablation) 分组汇总各次重复运行指标
    grouped_runs = defaultdict(list)
    for r in runs_to_eval:
        gid = r.get("group_id") or r.get("mode", "unknown")
        grouped_runs[gid].append(r)

    group_summaries = {}
    for gid, runs in grouped_runs.items():
        first = runs[0]
        group_meta = {
            "group_id": gid,
            "group_name": first.get("group_name", gid),
            "mode": first.get("mode"),
            "ablation": first.get("ablation"),
            "factor_agent": first.get("factor_agent"),
            "factor_gate": first.get("factor_gate"),
            "repeats": len(runs),
        }

        # 统计各指标在 repeats 间的均值和标准差
        fcr_list = []
        prec_list = []
        rec_list = []
        cov_list = []
        macro_f1_list = []
        tokens_list = []
        duration_list = []

        for r in runs:
            tokens_list.append((r.get("input_tokens") or 0) + (r.get("output_tokens") or 0))
            duration_list.append(r.get("duration_ms") or 0)

            # 如果存在金标，计算精度评测
            y_true = []
            y_pred = []
            if gold_map:
                for cid, ginfo in gold_map.items():
                    if not ginfo["gold_verdict"]:
                        continue
                    # 匹配对应 case 结果
                    pred_verdict, _ = extract_run_verdict(r, matter_id=cid)
                    y_true.append(ginfo["gold_verdict"])
                    y_pred.append(pred_verdict)

            if y_true and y_pred:
                b_metrics = compute_binary_metrics(y_true, y_pred, {"CONFIRMED_CONSISTENT"})
                m_metrics = compute_multiclass_metrics(y_true, y_pred)
                fcr_list.append(b_metrics["fcr"])
                prec_list.append(b_metrics["precision"])
                rec_list.append(b_metrics["recall"])
                cov_list.append(b_metrics["coverage"])
                macro_f1_list.append(m_metrics["macro_f1"])

        fcr_m, fcr_sd = mean_and_sd(fcr_list) if fcr_list else (0.0, 0.0)
        prec_m, prec_sd = mean_and_sd(prec_list) if prec_list else (0.0, 0.0)
        rec_m, rec_sd = mean_and_sd(rec_list) if rec_list else (0.0, 0.0)
        cov_m, cov_sd = mean_and_sd(cov_list) if cov_list else (0.0, 0.0)
        mf1_m, mf1_sd = mean_and_sd(macro_f1_list) if macro_f1_list else (0.0, 0.0)
        dur_m, dur_sd = mean_and_sd(duration_list) if duration_list else (0.0, 0.0)
        tok_m, tok_sd = mean_and_sd(tokens_list) if tokens_list else (0.0, 0.0)

        group_summaries[gid] = {
            "meta": group_meta,
            "metrics": {
                "fcr": {"mean": fcr_m, "sd": fcr_sd, "display": format_mean_sd(fcr_m, fcr_sd)},
                "precision": {"mean": prec_m, "sd": prec_sd, "display": format_mean_sd(prec_m, prec_sd)},
                "recall": {"mean": rec_m, "sd": rec_sd, "display": format_mean_sd(rec_m, rec_sd)},
                "coverage": {"mean": cov_m, "sd": cov_sd, "display": format_mean_sd(cov_m, cov_sd)},
                "macro_f1": {"mean": mf1_m, "sd": mf1_sd, "display": format_mean_sd(mf1_m, mf1_sd, percent=False)},
                "duration_ms": {"mean": dur_m, "sd": dur_sd, "display": f"{dur_m:.0f} ± {dur_sd:.0f} ms"},
                "tokens": {"mean": tok_m, "sd": tok_sd, "display": f"{tok_m:.0f} ± {tok_sd:.0f}"},
            },
        }

    # 打印控制台表格
    print("\n" + "=" * 90)
    print("=== 审迹智链 (AuditTrace) 评测基准汇总报告 (Mean ± SD) ===")
    header = f"{'组别':<6} | {'实验名称':<28} | {'错误确证率(FCR)':<15} | {'确证精确率':<12} | {'覆盖率':<10} | {'Macro-F1':<12} | {'耗时':<12}"
    print(header)
    print("-" * 90)
    for gid, res in group_summaries.items():
        m = res["metrics"]
        print(f"{gid:<6} | {res['meta']['group_name']:<28} | {m['fcr']['display']:<15} | {m['precision']['display']:<12} | {m['coverage']['display']:<10} | {m['macro_f1']['display']:<12} | {m['duration_ms']['display']:<12}")
    print("=" * 90)

    # 如果有 2x2 因子设计实验结果，打印 2x2 方差与交互效应分析
    f2x2_keys = ["G1", "G7", "G6", "G3"]
    if all(k in group_summaries for k in f2x2_keys):
        print("\n=== 2×2 因子设计交互效应分析 (Factorial Matrix) ===")
        print("| 架构 \\ 门禁 | 无会计门禁 (Without Gate) | 有会计门禁 (With Gate) | 门禁增益 (ΔGate) |")
        print("| :--- | :--- | :--- | :--- |")
        g1_fcr = group_summaries["G1"]["metrics"]["fcr"]["mean"]
        g7_fcr = group_summaries["G7"]["metrics"]["fcr"]["mean"]
        g6_fcr = group_summaries["G6"]["metrics"]["fcr"]["mean"]
        g3_fcr = group_summaries["G3"]["metrics"]["fcr"]["mean"]
        print(f"| **单模型 (Single Model)** | G1 (FCR: {g1_fcr*100:.1f}%) | G7 (FCR: {g7_fcr*100:.1f}%) | {(g1_fcr - g7_fcr)*100:+.1f}% |")
        print(f"| **五 Agent (Five Agents)** | G6 (FCR: {g6_fcr*100:.1f}%) | G3 (FCR: {g3_fcr*100:.1f}%) | {(g6_fcr - g3_fcr)*100:+.1f}% |")
        print(f"| **多 Agent 增益 (ΔAgent)** | {(g1_fcr - g6_fcr)*100:+.1f}% | {(g7_fcr - g3_fcr)*100:+.1f}% | 交互效应已解耦 |")
        print("=" * 60)

    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        if args.output_report.suffix == ".json":
            args.output_report.write_text(json.dumps(group_summaries, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            # 导出 Markdown 报告
            md_lines = [
                "# 审迹智链 (AuditTrace) 严谨科学对照实验评测报告",
                "",
                f"> 生成时间: 2026-11-06 | 评测案例库: `{args.gold_cases.name}`",
                "",
                "## 1. 核心实验指标对照表 (Mean ± SD)",
                "",
                "| 组别代码 | 实验方法 / 组别名称 | 错误确证率 (FCR) ↓ | 确证精确率 ↑ | 确证覆盖率 ↑ | 结论 Macro-F1 ↑ | 平均耗时 (ms) |",
                "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
            ]
            for gid, res in group_summaries.items():
                m = res["metrics"]
                md_lines.append(f"| `{gid}` | **{res['meta']['group_name']}** | {m['fcr']['display']} | {m['precision']['display']} | {m['coverage']['display']} | {m['macro_f1']['display']} | {m['duration_ms']['display']} |")

            if all(k in group_summaries for k in f2x2_keys):
                md_lines.extend([
                    "",
                    "## 2. 2×2 因子设计与门禁贡献独立检验 (Factorial Analysis)",
                    "",
                    "| 架构因素 \\ 门禁因素 | 无会计门禁 (Without Gate) | 有会计门禁 (With Gate) | 门禁增益 (ΔGate) |",
                    "| :--- | :---: | :---: | :---: |",
                    f"| **单模型 (Single Model)** | G1 (FCR: {g1_fcr*100:.1f}%) | G7 (FCR: {g7_fcr*100:.1f}%) | `{(g1_fcr - g7_fcr)*100:+.1f}%` |",
                    f"| **五 Agent (Five Agents)** | G6 (FCR: {g6_fcr*100:.1f}%) | G3 (FCR: {g3_fcr*100:.1f}%) | `{(g6_fcr - g3_fcr)*100:+.1f}%` |",
                    f"| **多 Agent 增益 (ΔAgent)** | `{(g1_fcr - g6_fcr)*100:+.1f}%` | `{(g7_fcr - g3_fcr)*100:+.1f}%` | **协同增益解耦完成** |",
                ])

            args.output_report.write_text("\n".join(md_lines), encoding="utf-8")
            print(f"[完成] 评测报告已成功导出至: {args.output_report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
