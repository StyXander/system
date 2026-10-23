"""B0–B3 对照实验框架：逐案例输出、诚实标注未测条件，不用单测通过率冒充识别率。

条件定义（与第二份修改意见 DELTA-08 一致）：
- B0 既有确定性计算/门禁（无模型，始终可运行）；
- B1 强单模型直接分析（关闭本体与调查闭环）；
- B2 单模型+本体+定向检索（公平的主要技术对照基线）；
- B3 自适应Agent+独立挑战+重规划（adaptive_agents）；
- 消融：B3 分别关闭 Challenger / 本体 / 定向检索。

样本分层：real_public（已登记原件）与 synthetic_adversarial（合成对抗样本），
各自报 N，绝不合并成"真实准确率"。B1/B2/B3 需要真实模型密钥；未配置时
本脚本如实记录 not_run，不生成任何表现百分比。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.connectivity_evidence_planner import build_plan, execute_action, rerank
from backend.app.connectivity_extraction import load_registry, source_path
from backend.app.connectivity_financial_bridge import build as build_bridge
from backend.app.connectivity_financial_scenario import build_scenario
from backend.app.connectivity_graph import build_impact_graph
from backend.app.connectivity_revision import build_revision_loop
from backend.app.connectivity_schemas import RunRequest

VERSION = "b_experiment_v1"


def _token_totals(provider_calls: list[dict]) -> dict:
    calls = [item for item in provider_calls if item.get("performed")]
    return {
        "performed_calls": len(calls),
        "input_tokens": sum(item.get("input_tokens") or 0 for item in calls),
        "output_tokens": sum(item.get("output_tokens") or 0 for item in calls),
        "attempted_calls": len(provider_calls),
        "provider_call_ids": [item.get("provider_call_id") for item in calls],
        "cost": sum(float(item["cost"]) for item in calls) if calls and all(item.get("cost") is not None for item in calls) else None,
    }


def _deterministic_summary(bridge: dict, plan: dict, investigation: dict | None) -> dict:
    graph = bridge.get("_graph") or {}
    return {
        "claims": len(bridge.get("claims", [])),
        "financial_nodes": len(bridge.get("nodes", [])),
        "edges": len(bridge.get("edges", [])),
        "edge_status": {status: sum(1 for edge in bridge.get("edges", [])
                                    if edge.get("status") == status)
                        for status in {edge.get("status") for edge in bridge.get("edges", [])}},
        "revision_changed": (bridge.get("_revision") or {}).get("summary", {}).get("changed", 0),
        "plan_primary_action": (plan.get("primary_action") or {}).get("action_id", ""),
        "investigation_outcome": (investigation or {}).get("outcome", "not_run"),
        "investigation_stop_reason": (investigation or {}).get("stop_reason", ""),
    }


def run_b0(root: Path, documents: list, pages: dict | None, industry: str) -> dict:
    """B0：确定性财务穿透 + 反证 + 补证规划；无任何模型调用。"""
    started = time.perf_counter()
    bridge = build_bridge(root, documents=documents, pages=pages, industry=industry)
    revision = build_revision_loop(bridge)
    plan = build_plan(bridge, revision)
    execution = None
    if plan.get("primary_action"):
        execution = execute_action(root, plan["primary_action"], documents)
        plan = rerank(plan, completed_conditions=[], new_evidence_ids=[],
                      reviewed_actions=[plan["primary_action"]["action_id"]])
        plan["execution"] = execution
    bridge["_graph"] = build_impact_graph(bridge)
    bridge["_revision"] = revision
    return {
        "condition": "B0", "status": "completed", "model": "none",
        "tokens": {"performed_calls": 0, "input_tokens": 0, "output_tokens": 0},
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "scenario_available": build_scenario(bridge)["available"],
        "summary": _deterministic_summary(bridge, plan, None),
        "graph_stats": bridge["_graph"].get("stats", {}),
        "artifacts": {"bridge": bridge, "revision": revision, "plan": plan, "scenario": build_scenario(bridge)},
    }


@contextmanager
def _condition_environment(condition, ablation, max_calls, token_budget):
    """实验参数逐条件恢复；异常不能污染后续条件。"""
    values = {"AUDITTRACE_DEMO_USE_EXTERNAL_MODEL": "true",
        "CONNECTIVITY_EXPERIMENT_DIRECT_SINGLE": "1" if condition == "B1" else None,
        "CONNECTIVITY_EXPERIMENT_MAX_CALLS": "1" if condition == "B1" else str(max_calls),
        "CONNECTIVITY_TOKEN_STOP_THRESHOLD": str(token_budget)}
    for key, flag in (("CONNECTIVITY_ABLATION_NO_CHALLENGER", "challenger"),
                      ("CONNECTIVITY_ABLATION_NO_ONTOLOGY", "ontology"),
                      ("CONNECTIVITY_ABLATION_NO_RETRIEVAL", "retrieval")):
        values[key] = "1" if ablation.get(flag) or (condition == "B1" and flag in {"retrieval", "ontology"}) else None
    saved = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_model_condition(root: Path, condition: str, mode: str, ablation: dict | None = None,
                        *, allow_models: bool = False, max_calls: int = 6, token_budget: int = 60000) -> dict:
    """B1/B2/B3：走完整 run_pipeline；未配置密钥时如实记录 not_run。"""
    if not allow_models:
        return {"condition": condition, "status": "not_run", "reason": "本次没有真实模型预算授权；未发出请求。"}
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        return {"condition": condition, "status": "not_run",
                "reason": "DEEPSEEK_API_KEY 未配置；本条件未执行，不生成任何表现数字。"}
    request = RunRequest(pair_id=os.environ["B_EXPERIMENT_PAIR_ID"], mode=mode)
    from backend.app.connectivity_pipeline import run_pipeline
    started = time.perf_counter()
    with _condition_environment(condition, ablation or {}, max_calls, token_budget):
        run = run_pipeline(root, request, progress=lambda *a: None, agent_progress=lambda *a: None)
    tokens = _token_totals(run.provider_calls)
    result = {
        "condition": condition, "status": "completed" if tokens["performed_calls"] and run.model_status in {"single_completed", "adaptive_completed"} else "partial", "run_id": run.run_id,
        "model_status": run.model_status, "tokens": tokens,
        "model": next((call.get("model") for call in run.provider_calls if call.get("performed")), None),
        "provider_calls": run.provider_calls,
        "budget": {"max_calls": 1 if condition == "B1" else max_calls, "token_stop_threshold": token_budget,
                   "note": "token停止线在下一请求前检查；单次在途响应可能越过，不表示精确消费上限。"},
        "professional_score": None, "annotation_status": "not_annotated",
        "artifacts": run.model_dump(mode="json"),
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "summary": _deterministic_summary(
            {"claims": run.financial_claims, "nodes": run.financial_nodes,
             "edges": run.financial_edges, "_revision": run.revision_loop,
             "_graph": run.impact_graph},
            run.evidence_plan, run.investigation),
        "investigation": {"outcome": run.investigation.get("outcome", ""),
                          "stop_reason": run.investigation.get("stop_reason", ""),
                          "summary": run.investigation.get("summary", {})},
    }
    return result


CONDITIONS = [
    ("B0", None, None),
    ("B1", "single_model", {"ontology": True}),
    ("B2", "single_model", None),
    ("B3", "adaptive_agents", None),
    ("B3-no-challenger", "adaptive_agents", {"challenger": True}),
    ("B3-no-ontology", "adaptive_agents", {"ontology": True}),
    ("B3-no-retrieval", "adaptive_agents", {"retrieval": True}),
]


def synthetic_adversarial_samples() -> list[dict]:
    """合成对抗样本：数值接近但口径冲突、目标语态、语义相近三类。"""
    from backend.tests.test_financial_bridge import _docs, _pages
    return [
        {"sample_id": "SYN-numeric-proximity", "sample_set": "synthetic_adversarial",
         "documents": _docs(), "pages": _pages(), "industry": "steel",
         "expected": "数值接近必须保留缺口，不得升级为直接关联"},
    ]


def real_public_samples(root: Path) -> list[dict]:
    docs = [doc for doc in load_registry(root) if doc.company == "宝钢股份" and doc.period == "2025"]
    if len(docs) != 2 or not all(source_path(root, doc).exists() for doc in docs):
        return []
    return [{"sample_id": "REAL-baosteel-2025", "sample_set": "real_public",
             "documents": docs, "pages": None, "industry": "steel",
             "expected": "32亿元ESG合计与32.89亿元单一项目预算必须保持口径冲突"}]


def main() -> int:
    parser = argparse.ArgumentParser(description="B0–B3 对照实验框架")
    parser.add_argument("--output", default=str(ROOT / "runtime" / "b_experiment"), help="输出目录")
    parser.add_argument("--allow-models", action="store_true", help="仅在已获真实调用授权后使用")
    parser.add_argument("--max-calls", type=int, default=6)
    parser.add_argument("--token-budget", type=int, default=60000)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"version": VERSION,
                "note": "分数/状态是确定性结果，不是正确率；B1/B2/B3 未配置密钥时如实记录 not_run。",
                "conditions": [item[0] for item in CONDITIONS],
                "samples": [], "runs": []}
    samples = real_public_samples(ROOT) + synthetic_adversarial_samples()
    for sample in samples:
        manifest["samples"].append({"sample_id": sample["sample_id"],
                                    "sample_set": sample["sample_set"],
                                    "expected": sample["expected"]})
        for condition, mode, ablation in CONDITIONS:
            record = {"sample_id": sample["sample_id"], "sample_set": sample["sample_set"],
                      "condition": condition}
            try:
                if condition == "B0":
                    record.update(run_b0(ROOT, sample["documents"], sample["pages"],
                                         sample["industry"]))
                else:
                    # 合成样本没有登记原件，模型条件只对 real_public 开放。
                    if sample["sample_set"] != "real_public":
                        record.update({"status": "not_applicable",
                                       "reason": "合成样本未走登记原件流程；模型条件不适用。"})
                    else:
                        pair = [doc for doc in sample["documents"]]
                        os.environ["B_EXPERIMENT_PAIR_ID"] = pair[0].case_id
                        record.update(run_model_condition(ROOT, condition, mode, ablation, allow_models=args.allow_models,
                                                          max_calls=args.max_calls, token_budget=args.token_budget))
            except Exception as error:  # noqa: BLE001 实验逐案例隔离，失败保留原状
                record.update({"status": "failed", "error": type(error).__name__,
                               "message": str(error)[:240]})
            path = output / f"{sample['sample_id']}__{condition}.json"
            path.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            manifest["runs"].append({"sample_id": sample["sample_id"], "condition": condition,
                                     "status": record.get("status", ""), "output": str(path)})
            print(f"[b-experiment] {sample['sample_id']} {condition}: {record.get('status')}")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print(f"[b-experiment] manifest -> {output / 'manifest.json'}")
    return 1 if any(run["status"] == "failed" for run in manifest["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
