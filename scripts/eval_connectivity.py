"""从原PDF跑批；参考字段只在运行结束后比对，不进入运行服务。

统计可观察的定位结果、未知条件与调用，不伪造真人基线或专业评分。
开发、既有研究接触和本轮保留评价身份分别说明。
"""
from __future__ import annotations

import argparse
import re
from decimal import InvalidOperation
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.connectivity_pipeline import run_pipeline
from app.connectivity_schemas import RunRequest
from app.connectivity_extraction import load_registry
from app.connectivity_engine import number, numeric_unit


def clean(text):
    return "".join(str(text or "").split()).replace("（", "(").replace("）", ")")


def evaluate(pair_ids=None):
    from datetime import datetime, timezone
    target = ROOT / "outputs/connectivity-v1-acceptance/evaluations" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target.mkdir(parents=True, exist_ok=True)
    docs = load_registry(ROOT)
    pairs = sorted({d.case_id for d in docs})
    if pair_ids:
        unknown = set(pair_ids) - set(pairs)
        if unknown:
            raise ValueError("未登记的报告对：" + ", ".join(sorted(unknown)))
        pairs = [p for p in pairs if p in pair_ids]
    references = ROOT / "backend/evaluation/connectivity/reference_fields.json"
    all_samples = json.loads(references.read_text(encoding="utf-8"))["samples"]
    summary = []
    for pair_id in pairs:
        print(json.dumps({"pair": pair_id, "state": "running"}), flush=True)
        run = run_pipeline(ROOT, RunRequest(pair_id=pair_id, mode="calculation_only"))
        # 美的此前已有研究接触，但未用其原PDF调本轮提取/关系代码。
        if pair_id.startswith("000333-"):
            run.dataset_role = "held_out"
        (target / f"{pair_id}-raw-pdf-run.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
        mapping = {doc.document_id.rsplit("_", 1)[0]: doc.document_id for doc in run.documents}
        results = []
        # 到此为止原件解析和规则执行已结束，下面才读取参考字段做对比。
        for sample in all_samples:
            if sample["company"] != run.company or run.period != "2025":
                continue
            for reference in sample.get("observations", []):
                document_id = mapping.get(reference["source_id"])
                if not document_id:
                    continue
                try:
                    expected = number(reference["value_as_printed"])
                except (ValueError, InvalidOperation):
                    continue
                label = clean(reference.get("original_label")).replace("人员的数量", "人员数量")
                matches = []
                for row in run.occurrences:
                    if row.document_id != document_id or row.pdf_page != reference["pdf_page"] or row.value is None:
                        continue
                    try:
                        equal = number(row.value) == expected
                    except ValueError:
                        equal = False
                    if equal and (label in clean(row.row_header).replace("人员的数量", "人员数量") or label in clean(row.label).replace("人员的数量", "人员数量")):
                        matches.append(row)
                expected_year = re.search(r"20\d{2}", reference.get("period", ""))
                expected_year = expected_year.group() if expected_year else run.period
                expected_unit = numeric_unit(reference.get("unit_as_printed", ""))
                results.append({"sample_id": sample["id"], "topic": sample["topic"], "document_id": document_id,
                    "pdf_page": reference["pdf_page"], "reference_label": reference.get("original_label"),
                    "reference_value": reference["value_as_printed"], "found": bool(matches),
                    "expected_year": expected_year, "expected_unit": reference.get("unit_as_printed", ""),
                    "bound_year_and_unit": any(row.quality == "located" and row.year == expected_year
                        and expected_unit[0] != "unknown" and numeric_unit(row.unit) == expected_unit for row in matches),
                    "occurrence_ids": [row.occurrence_id for row in matches]})
        found = sum(row["found"] for row in results)
        qualified = sum(row["bound_year_and_unit"] for row in results)
        row = {"pair_id": pair_id, "company": run.company, "period": run.period, "dataset_role": run.dataset_role,
            "raw_locations": len(run.occurrences), "relationships": len(run.checks),
            "parsed_pages": sum(c.parsed_pages for c in run.coverage), "failed_pages": sum(len(c.failed_pages) for c in run.coverage),
            "reference_count": len(results), "found": found, "bound_year_and_unit": qualified,
            "capture_rate": found/len(results) if results else None,
            "qualified_rate": qualified/len(results) if results else None,
            "unresolved_relationships": sum(bool(c.unresolved) for c in run.checks), "duration_ms": run.duration_ms,
            "reference_results": results, "false_pair_rate": None,
            "false_pair_note": "当前参考资料不是完整候选正负标签集，不能据此伪报错误配对比例。"}
        summary.append(row)
        (target / "raw-pdf-evaluation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k:v for k,v in row.items() if k not in {"reference_results", "false_pair_note"}}, ensure_ascii=True), flush=True)
    lines = ["# 原PDF关联核对跑批结果", "", "原件自动发现不读取参考答案；字段样本在运行结束后独立比对。以下是定位与程序行为统计，不是专业准确率。", "",
        "| 报告对 | 身份 | 参考位置找到/分母 | 年度单位绑定/分母 | 未决关系 | 毫秒 |", "| --- | --- | --- | --- | --- | --- |"]
    for row in summary:
        lines.append(f"| {row['company']} {row['period']} | {row['dataset_role']} | {row['found']}/{row['reference_count']} | {row['bound_year_and_unit']}/{row['reference_count']} | {row['unresolved_relationships']} | {row['duration_ms']} |")
    lines += ["", "宝钢2024的独立核读样本尚未转换为本脚本参考表，分母为0表示未统计，不能写成100%。美的为本轮保留评价，资料此前已进入研究视野，不称完全未见。", "",
        "G1：计算边界以实际运行的专门检查记录为准；G2：定位命中不能替代原页视觉核对；G3：保留未知与第三处差异，另见合成行为记录；G4：以上给出找到与年度单位绑定的实际分母；G5：保留身份如上；G6：浏览器操作、导出及修订另外记录，不能由本脚本代填。", "",
        "原质量目标仍保留：核心目标位置85%、主表核心100%、全部位置80%、错误配对不高于15%。当前参考表尚未标定各类目标的完整分母及候选负例，不能用总体找到比例冒充全部指标达标。", "",
        "人工PDF与Excel基线、会计教师/从业者评价未由该脚本执行，均不生成虚假用时或签字。"]
    (target / "原PDF自动发现评价.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", action="append")
    args = parser.parse_args()
    evaluate(args.pair)
