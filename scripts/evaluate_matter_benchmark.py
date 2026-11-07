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
        (e.get("status") == "supported_as_reported" or e.get("acceptance_status") == "accepted")
        and bool(e.get("supporting_evidence_ids"))
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
        if comparability == "comparable" and assessment.get("numeric_consistency") == "consistent":
            return "CONFIRMED_CONSISTENT"
        return "INSUFFICIENT_EVIDENCE"
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
    if matter_id and target_assessment is None:
        raise ValueError(f"MATTER_MAPPING_MISSING: {matter_id}")
    if target_assessment is None:
        if len(assessments) != 1:
            raise ValueError("MATTER_MAPPING_REQUIRED: 必须明确选择事项")
        target_assessment = assessments[0]

    matter_exps = [e for e in explanations if e.get("matter_id") == target_assessment.get("matter_id")]
    verdict = extract_verdict_from_assessment(target_assessment, matter_exps)
    evidence_ids = list(target_assessment.get("supporting_evidence_ids", [])) + list(target_assessment.get("counter_evidence_ids", []))
    return verdict, evidence_ids


def compute_binary_metrics(y_true: list[str], y_pred: list[str], positive_classes: set[str]) -> dict:
    """计算二分类指标（如确证类指标 FCR, Precision, Recall, Coverage）。"""
    if len(y_true) != len(y_pred):
        raise ValueError("标签和预测数量不一致")
    n_total = len(y_true)
    if n_total == 0:
        return {"total": 0, "n_confirm": 0, "fcr": None, "precision": None, "recall": None, "coverage": 0.0}

    n_confirm = sum(p in positive_classes for p in y_pred)
    n_gold_confirm = sum(t in positive_classes for t in y_true)
    n_true_confirm = sum(p in positive_classes and t in positive_classes for t, p in zip(y_true, y_pred))
    n_false_confirm = sum(p in positive_classes and t not in positive_classes for t, p in zip(y_true, y_pred))

    fcr = (n_false_confirm / n_confirm) if n_confirm > 0 else None
    precision = 1.0 - fcr if n_confirm > 0 else None
    recall = (n_true_confirm / n_gold_confirm) if n_gold_confirm > 0 else None
    coverage = n_confirm / n_total

    return {
        "n_total": n_total,
        "n_confirm": n_confirm,
        "n_gold_confirm": n_gold_confirm,
        "n_true_confirm": n_true_confirm,
        "n_false_confirm": n_false_confirm,
        "fcr": round(fcr, 4) if fcr is not None else None,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
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
        if final_verdict and str(final_verdict).strip() not in VERDICT_CLASSES + list(VERDICT_ZH.values()):
            raise ValueError(f"未知人工结论: {case_id}: {final_verdict}")

        if case_id in gold_map:
            raise ValueError(f"重复人工案例ID: {case_id}")
        gold_map[case_id] = {
            "case_id": case_id,
            "matter_id": item.get("matter_id"),
            "category": item.get("category", ""),
            "trigger": item.get("trigger", ""),
            "gold_verdict": normalize_verdict(final_verdict) if final_verdict else None,
            "gold_evidence_ids": set(item.get("gold_evidence_ids") or []),
            "annotation_status": item.get("annotation_status", "pending"),
        }
    return gold_map


def evaluate_comparison(comparison_path: Path, gold_map: dict) -> dict:
    """Resolve each summary row to its full result and its own independently labelled case."""
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    excluded = []
    seen = set()
    for row in comparison.get("runs", []):
        case_id = row.get("case_id")
        gold = gold_map.get(case_id)
        if not gold or not gold.get("gold_verdict"):
            excluded.append({"case_id": case_id, "reason": "no_independent_gold"})
            continue
        key = (row.get("group_id"), row.get("experiment_mode", "end_to_end"), row.get("repeat", 1))
        identity = (*key, case_id)
        if identity in seen:
            raise ValueError(f"重复案例记录: {identity}")
        seen.add(identity)
        result_path = comparison_path.parent / str(row.get("result_file") or "")
        item = {"case_id": case_id, "gold": gold["gold_verdict"], "prediction": None,
                "status": row.get("status"), "failure": row.get("failure")}
        if row.get("status") == "recorded":
            if not row.get("result_file") or not result_path.is_file():
                raise ValueError(f"完整运行文件缺失: {case_id}")
            run = json.loads(result_path.read_text(encoding="utf-8"))
            if run.get("run_id") != row.get("run_id"):
                raise ValueError(f"运行身份不匹配: {case_id}")
            matter_id = row.get("matter_id") or gold.get("matter_id")
            if not matter_id:
                raise ValueError(f"事项映射缺失: {case_id}")
            item["prediction"], item["evidence_ids"] = extract_run_verdict(run, matter_id)
        grouped[key].append(item)
    evaluations = []
    for (group, mode, repeat), items in sorted(grouped.items()):
        valid = [item for item in items if item["prediction"] is not None]
        truth = [item["gold"] for item in valid]
        predictions = [item["prediction"] for item in valid]
        evaluations.append({"group_id": group, "experiment_mode": mode, "repeat": repeat,
            "attempted": len(items), "evaluated": len(valid), "failed": len(items)-len(valid),
            "completion_rate": len(valid)/len(items),
            "conditional_on_completion": True,
            "classification": compute_multiclass_metrics(truth, predictions) if valid else None,
            "confirmation": compute_binary_metrics(truth, predictions, {"CONFIRMED_CONSISTENT"}) if valid else None,
            "cases": items})
    return {"evaluation_status": "evaluated" if evaluations else "not_evaluated",
            "independent_cases": len({i["case_id"] for rows in grouped.values() for i in rows}),
            "unlabelled_gold_cases": sum(not g.get("gold_verdict") for g in gold_map.values()),
            "excluded": excluded, "evaluations": evaluations,
            "interpretation": "关系支持不等于数值一致；确认一致须有明确数值核验状态。各轮按同一测试集配对比较，失败率单列。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--comparison-json", type=Path)
    source.add_argument("--runs-dir", type=Path, help="包含comparison.json及完整运行文件的目录")
    parser.add_argument("--gold-cases", type=Path, default=ROOT / "backend/evaluation/connectivity/matter_cases.json")
    parser.add_argument("--output-report", type=Path)
    args = parser.parse_args()
    path = args.comparison_json or args.runs_dir / "comparison.json"
    report = evaluate_comparison(path, load_gold_cases(args.gold_cases))
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        if args.output_report.suffix == ".json":
            args.output_report.write_text(output, encoding="utf-8")
        else:
            lines = ["# 技术效果评测", "", "状态 " + report["evaluation_status"], "",
                     "| 组别 | 模式 | 重复 | 尝试 | 失败 | Macro-F1 | FCR |", "|---|---|---|---|---|---|---|"]
            for e in report["evaluations"]:
                mf = e["classification"]["macro_f1"] if e["classification"] else "N/A"
                fcr = e["confirmation"]["fcr"] if e["confirmation"] else None
                lines.append(f"| {e['group_id']} | {e['experiment_mode']} | {e['repeat']} | {e['attempted']} | {e['failed']} | {mf} | {fcr if fcr is not None else 'N/A'} |")
            lines.extend(["", report["interpretation"], "", "```json", output, "```"])
            args.output_report.write_text("\n".join(lines), encoding="utf-8")
    print(output)
    return 0 if report["evaluation_status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
