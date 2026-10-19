"""AI1 五对登记报告无模型复测：字段填充、门禁结果与真实样例定位。

只读登记原件与既有解析缓存；不调用模型、不写运行存储。输出所有统计的
分母和本次运行标识，找不到的样例明确记为阻断，不拿预期值代替实测。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectivity_conditions import upgrade_conditions  # noqa: E402
from app.connectivity_engine import calculate, display_precision_assumption, number, numeric_unit  # noqa: E402
from app.connectivity_extraction import load_registry  # noqa: E402
from app.connectivity_pipeline import run_pipeline  # noqa: E402
from app.connectivity_schemas import (ComparisonCondition, RelationshipCheck, RelationshipMember,  # noqa: E402
    RunRequest)
from app.connectivity_tables import build_table_composition_candidates  # noqa: E402

TOPICS = ["research", "environment", "intensity"]
PAIR_ORDER = ["000858-2025", "000333-2025", "300750-2025", "600019-2025", "600019-2024"]
TARGETS = {
    "449183817.50元": Decimal("449183817.50"),
    "4.49亿元": Decimal("449000000"),
    "37.79亿元": Decimal("3779000000"),
    "12.50亿元": Decimal("1250000000"),
    "0.66%": Decimal("0.0066"),
}


def _normalized(row):
    try:
        value = number(row.value)
        dimension, factor = numeric_unit(row.unit)
        return value * factor, dimension
    except ValueError:
        return None, ""


def _row_brief(row):
    return {"occurrence_id": row.occurrence_id, "document_id": row.document_id, "pdf_page": row.pdf_page,
            "label": row.label, "value": row.value, "unit": row.unit, "year": row.year,
            "scope": row.scope, "scope_level": row.scope_level, "table_scope": row.table_scope,
            "report_boundary": row.report_boundary, "currency": row.currency,
            "currency_status": row.currency_status, "display_precision": row.display_precision,
            "rounding_method": row.rounding_method, "content_class": row.content_class,
            "quality": row.quality, "quality_reason": row.quality_reason,
            "row_role": row.row_role, "column_role": row.column_role, "table_id": row.table_id}


def _sample_occurrences(run):
    """按归一化金额/比例定位报告中的关键样例，返回命中与明确未命中。"""
    matches = {name: [] for name in TARGETS}
    for row in run.occurrences:
        value, dimension = _normalized(row)
        if value is None:
            continue
        for name, target in TARGETS.items():
            tolerance = Decimal("0.0001") if name.endswith("%") else Decimal("1")
            if abs(value - target) <= tolerance:
                matches[name].append(_row_brief(row))
    return {name: {"target": str(target), "hit_count": len(rows), "rows": rows[:8]}
            for name, (target, rows) in ((name, (TARGETS[name], matches[name])) for name in TARGETS)}


def _sample_attempt(run):
    """若两份真实披露都被抽到，按显示精度假设做一次 L0 试算；否则记录阻断。"""
    ar_docs = {doc.document_id for doc in run.documents if doc.report_type == "AR"}
    esg_docs = {doc.document_id for doc in run.documents if doc.report_type == "ESG"}

    def best(candidates):
        # 优先已定位、边界已知、币种已知且显示两位小数的披露，避免用弱候选演示。
        return max(candidates, key=lambda row: (row.quality == "located",
            row.report_boundary != "unknown", bool(row.currency), row.display_precision == 2), default=None)

    left = best([row for row in run.occurrences
                 if row.document_id in ar_docs and _normalized(row)[0] is not None
                 and abs(_normalized(row)[0] - Decimal("449183817.50")) <= Decimal("1")])
    right = best([row for row in run.occurrences
                  if row.document_id in esg_docs and _normalized(row)[0] is not None
                  and abs(_normalized(row)[0] - Decimal("449000000")) <= Decimal("1")])
    if left is None or right is None:
        return {"status": "blocked", "reason": "五粮液2025未同时抽到AR的449,183,817.50元与ESG的4.49亿元两处披露",
                "left": _row_brief(left) if left else None, "right": _row_brief(right) if right else None}
    check = RelationshipCheck(check_id="AI1-SAMPLE-449", rule_id="EQ-001", title="五粮液研发投入显示精度条件试算",
        topic="research", operator="equal",
        members=[RelationshipMember(occurrence_id=left.occurrence_id, role="left"),
                 RelationshipMember(occurrence_id=right.occurrence_id, role="right")],
        conditions=[ComparisonCondition(name=name) for name in ("主体", "期间", "定义", "范围", "单位")],
        relationship_basis="auto_label_match")
    try:
        result = calculate(check, run.occurrences)
    except ValueError as error:
        return {"status": "blocked", "reason": str(error), "left": _row_brief(left), "right": _row_brief(right)}
    return {"status": "computed_conditionally", "left": _row_brief(left), "right": _row_brief(right),
            "calculation_status": result.calculation_status,
            "conclusion_level": result.conclusion_level, "basis_level": result.basis_level,
            "residual": (result.hypothetical or {}).get("residual"),
            "assumption_check": (result.calculation or {}).get("assumption_check"),
            "note": "只证明两处实际抽取值的显示精度条件区间；不宣称业务口径可比或正式一致"}


def _table_candidates(run):
    candidates = build_table_composition_candidates(run.occurrences, run.period)
    results = []
    for candidate in candidates:
        try:
            upgraded, names = upgrade_conditions(candidate, run, run.period)
            calculated = calculate(upgraded, run.occurrences)
            results.append({"check_id": candidate.check_id, "rule_id": candidate.rule_id,
                            "layout": candidate.table_structure.get("layout"),
                            "total": candidate.table_structure.get("total", {}).get("label"),
                            "components": [item.get("label") for item in candidate.table_structure.get("components", [])],
                            "component_columns": [item.get("column_header") for item in candidate.table_structure.get("components", [])],
                            "coverage": candidate.table_structure.get("coverage"),
                            "upgraded_conditions": names,
                            "criteria_status": calculated.criteria_status,
                            "calculation_status": calculated.calculation_status,
                            "conclusion_level": calculated.conclusion_level,
                            "basis_level": calculated.basis_level,
                            "formal_residual": (calculated.calculation or {}).get("residual"),
                            "trial_residual": (calculated.hypothetical or {}).get("residual")})
        except (ValueError, ArithmeticError, KeyError, IndexError, TypeError) as error:
            results.append({"check_id": candidate.check_id, "layout": candidate.table_structure.get("layout"),
                            "error": f"{type(error).__name__}: {error}"})
    return results


def _boundary_probe(run):
    """用宝钢真实合并/母公司研发费用两处披露验证主体边界闸门。"""
    money = []
    for row in run.occurrences:
        value, dimension = _normalized(row)
        if value is None or dimension != "money":
            continue
        if "研发费用" not in (row.label or ""):
            continue
        money.append((row, value))
    parent = next(((row, value) for row, value in money
                   if row.report_boundary == "parent" and abs(value - Decimal("1249616010.99")) <= Decimal("1")), None)
    consolidated = next(((row, value) for row, value in money
                         if row.report_boundary == "consolidated" and abs(value - Decimal("3779320686.31")) <= Decimal("1")), None)
    esg = next(((row, value) for row, value in money
                if row.document_id in {doc.document_id for doc in run.documents if doc.report_type == "ESG"}
                and abs(value - Decimal("3779000000")) <= Decimal("10000000")), None)
    if parent is None or (consolidated is None and esg is None):
        return {"status": "blocked", "reason": "未同时抽到母公司研发费用与合并/ESG研发费用披露",
                "parent": _row_brief(parent[0]) if parent else None,
                "consolidated": _row_brief(consolidated[0]) if consolidated else None,
                "esg": _row_brief(esg[0]) if esg else None}
    probes = {}
    for name, other in (("parent_vs_consolidated", consolidated), ("parent_vs_esg", esg)):
        if other is None:
            probes[name] = {"status": "blocked", "reason": "对应披露未抽到"}
            continue
        check = RelationshipCheck(check_id=f"AI1-BOUNDARY-{name}", rule_id="EQ-001", title="宝钢研发费用主体边界闸门",
            topic="research", operator="equal",
            members=[RelationshipMember(occurrence_id=parent[0].occurrence_id, role="left"),
                     RelationshipMember(occurrence_id=other[0].occurrence_id, role="right")],
            conditions=[ComparisonCondition(name=item) for item in ("主体", "期间", "定义", "范围", "单位")],
            relationship_basis="auto_label_match")
        try:
            result = calculate(check, run.occurrences)
        except ValueError as error:
            probes[name] = {"status": "blocked", "reason": str(error)}
            continue
        probes[name] = {"status": "computed", "calculation_status": result.calculation_status,
                        "conclusion_level": result.conclusion_level, "basis_level": result.basis_level,
                        "boundary": result.comparability.get("boundary"),
                        "unresolved": result.unresolved,
                        "formal_residual": (result.calculation or {}).get("residual"),
                        "trial_residual": (result.hypothetical or {}).get("residual")}
    return {"status": "computed", "parent": _row_brief(parent[0]),
            "consolidated": _row_brief(consolidated[0]) if consolidated else None,
            "esg": _row_brief(esg[0]) if esg else None, "probes": probes}


def _gate_reasons(checks):
    """按门禁类别统计未决原因；同一关系可命中多个条件，分母为检查项数。"""
    categories = {"主体": "主体", "期间": "期间", "定义": "定义", "范围": "范围", "单位": "单位",
                  "组成完整": "组成完整", "互不重叠": "互不重叠", "关系依据": "关系本身",
                  "币种": "币种", "合并/母公司": "不同口径"}
    counts = Counter()
    for check in checks:
        text = "；".join(check.unresolved or [])
        for label, needle in categories.items():
            if needle in text:
                counts[label] += 1
    return dict(counts)


def _fill(rows, predicate):
    hit = sum(1 for row in rows if predicate(row))
    return {"value": hit, "denominator": len(rows), "rate": round(hit / len(rows), 4) if rows else None}


def main():
    started = time.perf_counter()
    registry = load_registry(ROOT)
    pairs = defaultdict(list)
    for doc in registry:
        pairs[doc.case_id].append(doc)
    output = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "root": ".", "execution_mode": "calculation_only", "model_called": False,
              "pairs": {}, "blocked_pairs": []}
    for pair_id in PAIR_ORDER:
        documents = pairs.get(pair_id, [])
        print(f"[pair] {pair_id} ({len(documents)} docs)", flush=True)
        if len(documents) != 2:
            output["blocked_pairs"].append({"pair_id": pair_id, "reason": f"登记文件数为{len(documents)}，不是2"})
            continue
        try:
            run = run_pipeline(ROOT, RunRequest(pair_id=pair_id, topics=TOPICS, mode="calculation_only"))
        except Exception as error:  # 单对失败不掩盖其他对的实测结果
            output["blocked_pairs"].append({"pair_id": pair_id, "reason": f"{type(error).__name__}: {error}"})
            print(f"[blocked] {pair_id}: {error}", flush=True)
            continue
        rows = run.occurrences
        checks = run.checks
        money_rows = [row for row in rows if "money" in numeric_unit(row.unit)[0]]
        statuses = Counter(check.calculation_status for check in checks)
        conclusions = Counter(check.conclusion_level for check in checks)
        levels = Counter(check.basis_level for check in checks)
        sample = _sample_occurrences(run)
        table_results = _table_candidates(run)
        result = {
            "run_id": run.run_id, "company": run.company, "period": run.period,
            "documents": [{"document_id": doc.document_id, "report_type": doc.report_type,
                           "pages": doc.pages, "file_sha256": doc.file_sha256} for doc in run.documents],
            "occurrences": len(rows),
            "coverage": [{"document_id": item.document_id, "total_pages": item.total_pages,
                          "parsed_pages": item.parsed_pages, "failed_pages": item.failed_pages,
                          "searched_pages": len(item.searched_pages)} for item in run.coverage],
            "exclusions": {"value": len(run.extraction_exclusions),
                           "reasons": Counter(item.reason for item in run.extraction_exclusions).most_common(8)},
            "fill": {
                "scope_nonempty": _fill(rows, lambda row: bool(row.scope)),
                "scope_metric": _fill(rows, lambda row: row.scope_level == "metric"),
                "scope_table": _fill(rows, lambda row: row.scope_level == "table"),
                "scope_report": _fill(rows, lambda row: row.scope_level == "report"),
                "scope_level": dict(Counter(row.scope_level for row in rows)),
                "report_boundary_known": _fill(rows, lambda row: row.report_boundary != "unknown"),
                "report_boundary": dict(Counter(row.report_boundary for row in rows)),
                "currency_known": _fill(rows, lambda row: bool(row.currency)),
                "currency_known_money": _fill(money_rows, lambda row: bool(row.currency)),
                "money_occurrences": len(money_rows),
                "currency_status": dict(Counter(row.currency_status for row in rows)),
                "currency_status_money": dict(Counter(row.currency_status for row in money_rows)),
                "unit_known": _fill(rows, lambda row: bool(row.unit)),
                "unit_status": dict(Counter(row.unit_status for row in rows)),
                "display_precision_known": _fill(rows, lambda row: row.display_precision is not None),
                "rounding_method": dict(Counter(row.rounding_method for row in rows)),
                "table_identity": _fill(rows, lambda row: bool(row.table_id)),
                "metric_identity": _fill(rows, lambda row: bool(row.metric_id)),
                "metric_id": dict(Counter(row.metric_id for row in rows if row.metric_id)),
                "quality_located": _fill(rows, lambda row: row.quality == "located"),
                "content_class": dict(Counter(row.content_class for row in rows)),
                "row_role": dict(Counter(row.row_role for row in rows)),
                "column_role": dict(Counter(row.column_role for row in rows)),
            },
            "checks": {"total": len(checks),
                       "criteria_status": dict(Counter(check.criteria_status for check in checks)),
                       "calculation_status": dict(statuses),
                       "conclusion_level": dict(conclusions),
                       "basis_level": dict(levels),
                       "formal_with_residual": sum(1 for check in checks if (check.calculation or {}).get("residual") is not None),
                       "trial_with_residual": sum(1 for check in checks if (check.hypothetical or {}).get("residual") is not None),
                       "boundary_different": sum(1 for check in checks
                                                 if (check.comparability or {}).get("boundary", {}).get("status") == "different"),
                       "boundary_blocked": sum(1 for check in checks
                                               if (check.comparability or {}).get("boundary", {}).get("status") in {"different", "undetermined"}),
                       "gate_reasons": _gate_reasons(checks),
                       "explanations_unsupported": sum(1 for check in checks
                                                       if (check.comparability or {}).get("explanation", {}).get("status") == "unsupported")},
            "samples": sample,
            "sample_attempt": _sample_attempt(run),
            "boundary_probe": _boundary_probe(run) if pair_id.startswith("600019") else None,
            "table_composition": {"candidate_count": len(table_results), "items": table_results[:20]},
            "duration_ms": run.duration_ms,
        }
        output["pairs"][pair_id] = result
        print(f"[done] {pair_id}: occurrences={len(rows)} checks={len(checks)} "
              f"tables={len(table_results)} formal={result['checks']['formal_with_residual']}", flush=True)
    output["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    target = ROOT / "docs/ai_handoff/ai1_core_regression_2026-10-19.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[written] {target}", flush=True)
    print(json.dumps({pair: {"occurrences": value["occurrences"], "checks": value["checks"]["total"],
                             "formal": value["checks"]["formal_with_residual"],
                             "tables": value["table_composition"]["candidate_count"]}
                      for pair, value in output["pairs"].items()}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
