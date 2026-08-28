"""竞赛演示版启动快照：把 15 案 manifest 聚合成一次只读 bootstrap。

启动快照只汇总既有登记事实，不复制规则、RAG 或 Agent 实现；
正式运行仍走 /api/runs 业务链，原文回查仍走受保护案例接口。
manifest 缺失或结构不一致时返回发布阻断原因码，前端据此显示
“演示资源未就绪”，不允许进入 ready 状态（计划 19.2 发布阻断层）。
模型就绪字段按白名单复制，绝不透出 API Key、Base URL 等凭据。
案例卡只携带评委选择案例所需元数据，不含旧运行模型输出，
也不包含本机绝对路径或人工复核人身份。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEMO_MANIFEST_PATH = WORKSPACE_ROOT / "backend" / "competition_demo_cases.json"

BOOTSTRAP_SCHEMA_VERSION = "demo_bootstrap_v1"
MANIFEST_SCHEMA_VERSION = "competition_demo_cases_v1"

# admission_status 只有最终 HEAD 验收完成后才允许写 passed；
# 其它取值一律视为登记错误并触发发布阻断。
ALLOWED_ADMISSION_STATUS = {"pending", "passed"}

# 启动快照公开的模型就绪白名单字段：全部是不可识别个人的状态事实。
MODEL_READINESS_FIELDS = (
    "full_analysis_ready",
    "full_analysis_reason_code",
    "full_analysis_message",
    "deterministic_backup_available",
    "model_id",
    "provider_label",
)

# 版本字段直接取自 PROJECT_STATUS.json 的 versions 登记。
VERSION_FIELDS = (
    "engine",
    "r1",
    "r2",
    "rag_index",
    "rag_retrieval",
    "rag_question_set",
    "agent_prompt",
    "agent_output",
)

# 案例卡字段：来源冻结明细（URL、SHA-256、页数）留在证据抽屉，
# 由正式案例详情与来源接口按需提供，启动快照保持轻量。
CASE_CARD_FIELDS = (
    "case_id",
    "ticker",
    "company_name",
    "category",
    "demo_focus",
    "report_years",
    "t0",
    "rule_ids",
    "industry_family",
    "admission_status",
    "admission_evidence",
)


def load_demo_manifest(path: Path | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """读取并校验演示 manifest；返回 (manifest, 发布阻断原因码)。"""

    manifest_path = path or DEMO_MANIFEST_PATH
    if not manifest_path.is_file():
        return None, "demo_manifest_missing"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "demo_manifest_invalid"
    failure = _manifest_failure_reason(manifest)
    if failure:
        return None, failure
    return manifest, None


def _manifest_failure_reason(manifest: Any) -> str | None:
    """逐项执行计划 18.6 的 manifest 结构约束，任一失败即阻断发布。"""

    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        return "demo_manifest_schema_mismatch"
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 15:
        return "demo_manifest_case_count_mismatch"
    if manifest.get("case_count") != len(cases):
        return "demo_manifest_case_count_mismatch"
    ids = [case.get("case_id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        return "demo_manifest_duplicate_case"
    if len(set(ids)) != len(ids):
        return "demo_manifest_duplicate_case"
    featured = manifest.get("featured_case_ids")
    if not isinstance(featured, list) or len(featured) != 3 or not set(featured).issubset(set(ids)):
        return "demo_manifest_featured_invalid"
    for case in cases:
        if case.get("admission_status") not in ALLOWED_ADMISSION_STATUS:
            return "demo_manifest_admission_status_invalid"
        if not isinstance(case.get("report_years"), list) or len(case["report_years"]) < 3:
            return "demo_manifest_report_years_insufficient"
    return None


def build_bootstrap_payload(
    manifest: dict[str, Any],
    *,
    model_readiness: dict[str, Any],
    versions: dict[str, Any],
    rag_status_resolver: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """组装启动快照；rag_status_resolver 由调用方提供以复用正式状态解析。"""

    cases = []
    for case in manifest["cases"]:
        rag = rag_status_resolver(case["case_id"])
        card = {field: case.get(field) for field in CASE_CARD_FIELDS}
        # RAG 就绪只保留状态与片段数；来源指纹等细节由案例详情接口提供。
        card["rag"] = {
            "status": rag.get("status"),
            "chunk_count": rag.get("chunk_count"),
        }
        cases.append(card)
    readiness = {field: model_readiness.get(field) for field in MODEL_READINESS_FIELDS}
    return {
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "bootstrap_ready": True,
        "bootstrap_reason_code": None,
        "source_head": manifest.get("source_head"),
        "manifest_frozen_at": manifest.get("frozen_at"),
        "engine_version": versions.get("engine"),
        "model_readiness": readiness,
        "versions": {field: versions.get(field) for field in VERSION_FIELDS},
        "case_count": len(cases),
        "featured_case_ids": manifest["featured_case_ids"],
        "cases": cases,
        "capabilities": {
            # 评委主线只有一个主按钮；运行走分阶段异步任务轮询。
            "single_primary_action": True,
            "run_endpoint": "/api/demo/runs",
            "evidence_drawer": True,
            "agent_drawer": True,
            "reset": True,
        },
    }


def blocked_bootstrap_payload(reason_code: str) -> dict[str, Any]:
    """manifest 阻断时的最小快照：不返回案例，前端显示演示资源未就绪。"""

    return {
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "bootstrap_ready": False,
        "bootstrap_reason_code": reason_code,
        "cases": [],
        "case_count": 0,
        "featured_case_ids": [],
    }
