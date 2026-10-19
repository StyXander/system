"""AI2 离线真实缓存评估：用五粮液/宝钢已保存的提取结果跑新增门禁。

本脚本不调用模型、不联网，只读登记运行 JSON。输出前后对照、排除日志、
列组成、非同名映射、0.66% 列义和宝钢合并/母公司案例的判定结果。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectivity_claims import build_claim_ledger  # noqa: E402
from app.connectivity_pipeline import _proposal_problem, candidate_checks  # noqa: E402
from app.connectivity_schemas import (AIAnalysis, ConnectivityRun, EvidenceRef, RelationshipMember,  # noqa: E402
                                      RelationshipProposal)

TOPICS = ["research", "environment", "intensity"]


def _quote(row) -> str:
    for line in (row.context or "").split("\n"):
        if row.value and row.value.replace(",", "") in line.replace(",", ""):
            return line.strip()[:160]
    return (row.context or "")[:80]


def _summary(run: ConnectivityRun, checks: list, rejections: list) -> dict:
    distribution = {}
    for check in checks:
        distribution[check.rule_id] = distribution.get(check.rule_id, 0) + 1
    roles = {}
    for item in rejections:
        role = item.get("role") or "other"
        roles[role] = roles.get(role, 0) + 1
    return {
        "company": run.company, "period": run.period,
        "occurrences": len(run.occurrences), "before_checks": len(run.checks),
        "after_checks": len(checks), "rule_distribution": distribution,
        "rejections": len(rejections), "rejections_by_role": roles,
        "coverage": [item for item in run.intelligence_trace if item.get("kind") == "topic_coverage"],
        "scope_gates": [item for item in run.intelligence_trace if item.get("kind") == "scope_gate"],
        "column_compositions": [
            {"check_id": check.check_id, "title": check.title,
             "expression": (check.calculation or {}).get("expression"),
             "residual": (check.hypothetical or {}).get("residual"),
             "status": check.calculation_status}
            for check in checks if "合计列" in check.title
        ],
        "non_identical_mappings": [
            {"check_id": check.check_id, "title": check.title, "mapping_type": check.mapping_type,
             "reason": check.mapping_reason}
            for check in checks if check.rule_id == "EQ-001" and check.mapping_type == "same_metric"
        ],
        "zero_point_six_six_members": [
            {"check_id": check.check_id, "title": check.title, "value": row.value, "label": row.label}
            for check in checks for member in check.members
            for row in [next((r for r in run.occurrences if r.occurrence_id == member.occurrence_id), None)]
            if row is not None and str(row.value) == "0.66"
        ],
    }


def _wly_claim_case(run: ConnectivityRun) -> dict:
    change = next((row for row in run.occurrences
                   if str(row.value) == "0.66" and "研发投入" in row.label), None)
    current = next((row for row in run.occurrences
                    if row.year == run.period and row.value and row.label.startswith("研发投入金额")), None)
    previous = next((row for row in run.occurrences
                     if row.year == "2024" and row.value and row.label.startswith("研发投入金额")), None)
    if not (change and current and previous):
        return {"available": False}
    from app.connectivity_schemas import ComparisonCondition, RelationshipCheck
    check = RelationshipCheck(check_id="REAL-066", rule_id="EQ-001", title="研发投入金额核对",
        topic="research", operator="equal",
        members=[RelationshipMember(occurrence_id=current.occurrence_id, role="left"),
                 RelationshipMember(occurrence_id=previous.occurrence_id, role="right")],
        conditions=[ComparisonCondition(name=name) for name in ("主体", "期间", "定义", "范围", "单位")],
        relationship_basis="auto_label_match",
        relationship_evidence=[EvidenceRef(occurrence_id=current.occurrence_id, quote=_quote(current))])
    analysis = AIAnalysis(check_id=check.check_id, verdict="potential_conflict",
        summary=f"{change.column_header} 的0.66%被当作年度值。",
        reasons=["该值位于变动比例列，年度列无法归属。"],
        supporting_evidence=[EvidenceRef(occurrence_id=change.occurrence_id, quote=_quote(change)),
                             EvidenceRef(occurrence_id=current.occurrence_id, quote=_quote(current))])
    ledger = build_claim_ledger(check, analysis, run.occurrences, role="A3", model="offline-cache")
    return {"available": True, "change_column": change.column_header, "change_year": change.year,
            "support_status": ledger["support_status"], "summary": ledger["support_summary"],
            "claims": [{"kind": claim["kind"], "status": claim["support_status"],
                        "reason": claim["reason"]} for claim in ledger["claims"]]}


def _numeric(value):
    try:
        return float(str(value or "").replace(",", "").replace("，", ""))
    except ValueError:
        return None


def _bso_eq_case(run: ConnectivityRun) -> dict:
    first = next((row for row in run.occurrences
                  if _numeric(row.value) is not None and abs(_numeric(row.value) - 37.79) < 1e-9), None)
    if first is None:
        first = next((row for row in run.occurrences if row.value and row.value.startswith("3779320686")), None)
    candidates = [row for row in run.occurrences if row.value and row.label.strip() == "研发费用"
                  and row.occurrence_id != (first.occurrence_id if first else "")]
    second = next((row for row in candidates
                   if _numeric(row.value) is not None and abs(_numeric(row.value) - 1249616010.99) < 1), None)
    if not (first and second):
        return {"available": False}
    proposal = RelationshipProposal(rule_id="EQ-001", title="研发费用跨表对比", topic="research",
        members=[RelationshipMember(occurrence_id=first.occurrence_id, role="left"),
                 RelationshipMember(occurrence_id=second.occurrence_id, role="right")],
        conditions=[], relationship_evidence=[])
    problem = _proposal_problem(proposal, run, {row.occurrence_id: row for row in run.occurrences})
    return {"available": True, "left": [first.occurrence_id, first.value, first.pdf_page],
            "right": [second.occurrence_id, second.value, second.pdf_page],
            "eq_problem": problem, "rejected": bool(problem)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-repo", default=str(ROOT.parent / "审迹智链系统"),
                        help="包含 backend/runtime/connectivity/tasks 的原仓库")
    parser.add_argument("--output", default=str(ROOT / "docs" / "ai_handoff" / "AI2_offline_eval.json"))
    args = parser.parse_args()
    task_dir = Path(args.data_repo) / "backend/runtime/connectivity/tasks"
    tasks = sorted(task_dir.glob("CONNJOB-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    selected = {}
    for path in tasks:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        result = data.get("result") or {}
        case_id = data.get("case_id") or result.get("case_id")
        if case_id and case_id not in selected and result.get("checks"):
            selected[case_id] = (path, result)
    report = {"schema_version": "ai2_offline_eval_v1",
              "data_repo": Path(args.data_repo).name,
              "tasks_dir": "backend/runtime/connectivity/tasks", "cases": {}}
    for case_id, (path, result) in selected.items():
        run = ConnectivityRun.model_validate(result)
        baseline_checks = len(run.checks)
        run.intelligence_trace = []
        rejections = []
        checks = candidate_checks(run.occurrences, run.period, run=run,
                                  rejections=rejections, topics=TOPICS)
        item = {"task_file": path.name, "run_id": run.run_id,
                **_summary(run, checks, rejections)}
        item["before_checks"] = baseline_checks
        if case_id.startswith("000858"):
            item["claim_case"] = _wly_claim_case(run)
        if case_id.startswith("600019"):
            item["scope_case"] = _bso_eq_case(run)
        report["cases"][case_id] = item
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({case: {key: value for key, value in item.items()
                             if key in {"company", "period", "before_checks", "after_checks",
                                        "rule_distribution", "rejections_by_role", "claim_case",
                                        "scope_case", "column_compositions"}}
                      for case, item in report["cases"].items()}, ensure_ascii=False, indent=2))
    print(f"written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
