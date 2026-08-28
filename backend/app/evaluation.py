"""竞赛演示 B0—B3 评估的冻结清单与只读仪表盘。

2026-08-22 起正式评估使用 evaluation_v4 不可覆盖目录：仪表盘只是派生只读汇总，
正式原始记录（合同、盲包、运行、评分快照）保存在同目录下并由冻结脚本追加。
旧 evaluation_v3 合同 EVAL-20260811 只读保留为历史，不再写入。
八个案例全部进入 B0—B3 四组：负向与行业案例的正确输出同样是比较对象，
不得预先标注不适用，避免只评正向候选造成选择偏差。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EVALUATION_ID = "EVAL-20260822-COMPETITION-8CASE-V3"
EVALUATION_SCHEMA = "evaluation_dashboard_v1"
# 正式记录目录按评估编号独立创建，文件存在即拒绝覆盖。
EVALUATION_DIRNAME = "evaluation_v4"
B0_B3_DEFINITIONS = {
    "B0": "人工仅查看字段和原文，自行判断",
    "B1": "只使用确定性规则",
    "B2": "确定性规则加一次直接模型复核，不使用 RAG 和多智能体",
    "B3": "确定性规则、RAG、三智能体和硬校验完整链",
}
# stratum 保留用于结果分层报告；不再据此排除任何案例的 B2/B3。
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


def _dashboard_path(workspace_root: Path) -> Path:
    return Path(workspace_root) / "outputs" / EVALUATION_DIRNAME / EVALUATION_ID / "dashboard.json"


def load_evaluation_dashboard(workspace_root: Path) -> dict[str, Any]:
    path = _dashboard_path(workspace_root)
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
    """离线评估脚本使用；线上 API 不提供写入入口。

    仪表盘属于派生汇总，允许在评估推进时重写；
    但合同、盲包、运行与评分原始记录必须落在同目录的独立文件中并拒绝覆盖。
    """
    if payload.get("evaluation_id") != EVALUATION_ID:
        raise ValueError("评估编号不匹配")
    path = _dashboard_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
