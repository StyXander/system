"""竞赛演示 B0—B3 评估的冻结清单与只读仪表盘。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EVALUATION_ID = "EVAL-20260811-COMPETITION-8CASE-V1"
EVALUATION_SCHEMA = "evaluation_dashboard_v1"
B0_B3_DEFINITIONS = {
    "B0": "人工仅查看字段和原文，自行判断",
    "B1": "只使用确定性规则",
    "B2": "确定性规则加一次直接模型复核，不使用 RAG 和多智能体",
    "B3": "确定性规则、RAG、三智能体和硬校验完整链",
}
FIXED_CASES: tuple[dict[str, str], ...] = (
    {"case_id": "CNINFO_000002_T0_20260331", "company_name": "万科A", "stratum": "strong_direct_candidate"},
    {"case_id": "CNINFO_601390_T0_20260330", "company_name": "中国中铁", "stratum": "standard_direct_candidate"},
    {"case_id": "CNINFO_601186_T0_20260330", "company_name": "中国铁建", "stratum": "strong_direct_candidate"},
    {"case_id": "CNINFO_000858_T0_20260430", "company_name": "五粮液", "stratum": "strong_direct_candidate"},
    {"case_id": "STD_DEV_T0", "company_name": "标准股份", "stratum": "rule_not_triggered"},
    {"case_id": "CNINFO_600938_T0_20260326", "company_name": "中国海油", "stratum": "rule_not_triggered"},
    {"case_id": "CNINFO_601668_T0_20260417", "company_name": "中国建筑", "stratum": "conditional_industry"},
    {"case_id": "CNINFO_601628_T0_20260325", "company_name": "中国人寿", "stratum": "industry_not_applicable"},
)


def _default_dashboard() -> dict[str, Any]:
    cases = []
    for item in FIXED_CASES:
        groups = {group: {"status": "not_started", "definition": definition} for group, definition in B0_B3_DEFINITIONS.items()}
        if item["stratum"] in {"rule_not_triggered", "conditional_industry", "industry_not_applicable"}:
            groups["B2"] = {"status": "not_applicable_no_call"}
            groups["B3"] = {"status": "not_applicable_no_call"}
        cases.append({**item, "groups": groups})
    aggregate_groups = {
        group: {
            "status": "not_started",
            "definition": definition,
            "completed": 0,
            "total": len(FIXED_CASES),
        }
        for group, definition in B0_B3_DEFINITIONS.items()
    }
    for item in cases:
        for group in ("B2", "B3"):
            if item["groups"][group].get("status") == "not_applicable_no_call":
                aggregate_groups[group]["not_applicable_count"] = aggregate_groups[group].get("not_applicable_count", 0) + 1
    return {
        "schema_version": EVALUATION_SCHEMA,
        "evaluation_id": EVALUATION_ID,
        "status": "not_started",
        "frozen_at": None,
        "model_id": None,
        "reviewers_required": 2,
        "cases_required": len(FIXED_CASES),
        "review_forms_required": len(FIXED_CASES) * 2,
        "review_forms_completed": 0,
        "metrics": None,
        "groups": aggregate_groups,
        "cases": cases,
        "disputes": 0,
        "boundary": "评估分数仅用于竞赛效果展示，不用于训练模型、修改规则或替代人工判断。",
    }


def load_evaluation_dashboard(workspace_root: Path) -> dict[str, Any]:
    path = Path(workspace_root) / "outputs" / "evaluation_v3" / "current.json"
    dashboard = _default_dashboard()
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and payload.get("evaluation_id") == EVALUATION_ID:
            dashboard.update(payload)
            dashboard["schema_version"] = EVALUATION_SCHEMA
    return dashboard


def write_evaluation_dashboard(workspace_root: Path, payload: dict[str, Any]) -> Path:
    """离线评估脚本使用；线上 API 不提供写入入口。"""
    if payload.get("evaluation_id") != EVALUATION_ID:
        raise ValueError("评估编号不匹配")
    path = Path(workspace_root) / "outputs" / "evaluation_v3"
    path.mkdir(parents=True, exist_ok=True)
    target = path / "current.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
