"""登记事实与运行性质投影：不把历史审计案例当作当前报告数量。"""
from __future__ import annotations

from .connectivity_extraction import load_registry
from .connectivity_rules import TOPICS, RULES
from .connectivity_schemas import NOTICE, SCHEMA_VERSION

PRODUCT_SCOPE = "基于已登记、公开的年度报告与可持续发展报告，辅助专业人员判断披露关系是否可比、追踪可持续事项的财务传导、跨期承诺、竞争解释，完成可复算检查并定位证据及待补条件。"


def project_facts(root):
    """实时读取登记表；数量不依赖网页或历史材料中的常数。"""
    documents = load_registry(root)
    return {"task_kind": "connectivity", "formal_scope": PRODUCT_SCOPE,
            "pair_count": len({d.case_id for d in documents}), "document_count": len(documents),
            "company_count": len({d.company_id for d in documents}),
            "topic_count": len(TOPICS), "rule_count": len(RULES),
            "schema_version": SCHEMA_VERSION, "notice": NOTICE,
            "matter_schema_version":"matter_connectivity_v1","matter_agent_count":5,
            "default_mode":"five_agents","matter_types":["climate_risk","transition_project","commitment","resource_efficiency","other"],
            "capability_boundary": "已登记公开报告专项核验；未承诺任意上传、全指标覆盖或审计鉴证意见"}


def execution_provenance(run):
    """根据实际调用记录分类，缺调用记录时不宣称实时模型成功。"""
    calls = run.provider_calls
    origin = run.versions.get("result_origin", "")
    if run.dataset_role == "synthetic":
        kind, label = "synthetic", "合成样本验证"
    elif origin in {"snapshot", "historical_snapshot"}:
        kind, label = "historical_snapshot", "历史结果快照，非本次模型调用"
    elif any(c.get("performed") for c in calls):
        kind, label = "provider_recorded", "本运行含实际模型调用记录，成功状态单列"
    elif calls:
        kind, label = "model_not_sent", "仅有尝试记录，未证实已发出模型请求"
    elif run.model_status == "reused_completed":
        kind, label = "reused", "复用既有模型意见，未新增调用"
    elif run.execution_mode == "calculation_only":
        kind, label = "calculation_only", "仅程序计算，未调用模型"
    else:
        kind, label = "unverified_model", "未取得可验证的模型调用记录"
    return {"kind": kind, "label": label, "provider_call_count": sum(bool(c.get("performed")) for c in calls), "attempt_count": len(calls),
            "execution_mode": run.execution_mode, "model_status": run.model_status,
            "run_id": run.run_id, "result_origin": origin or "original"}
