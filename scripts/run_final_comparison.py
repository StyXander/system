"""同一资料集合的离线/单模型/三角色/五角色及2x2因子设计对照实验脚本。

支持 G0–G7 完整对照与消融实验条件：
  G0: 纯规则/离线计算基线 (Rule-Only Baseline)
  G1: 单模型无本体门禁 (Raw Single Model, No Ontology Gate)
  G2: 三Agent协作基线 (3-Agent Baseline)
  G3: 完整五Agent系统 (Full 5-Agent System with Ontology Gate)
  G4: 五Agent去A3跨期追踪消融 (5-Agent Ablation: No Temporal)
  G5: 五Agent去A4反证机制消融 (5-Agent Ablation: No Counterevidence)
  G6: 五Agent去本体门禁消融 (5-Agent Ablation: No Ontology Gate)
  G7: 单模型+本体门禁对照 (Single Model + Ontology Gate)

支持双轨对照模式：
  --experiment-mode end_to_end    (实验 A：端到端自主检索核验，默认)
  --experiment-mode fixed_evidence (实验 B：固定候选证据包推理核验)

真实模型调用必须显式声明 --allow-models，绝不静默消耗额度。
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.competition_receipts import execution_eligibility, usage_receipt, resolve_case

EXPERIMENT_GROUPS = {
    "G0": {
        "group_id": "G0",
        "name": "纯规则基线 (Rule-Only Baseline)",
        "mode": "calculation_only",
        "ablation": "none",
        "factor_agent": "rule_only",
        "factor_gate": "rule_only",
        "description": "纯规则与确定性抽取，不调用任何大语言模型",
    },
    "G1": {
        "group_id": "G1",
        "name": "单模型基线 (Raw Single Model, No Ontology Gate)",
        "mode": "single_model",
        "ablation": "no_ontology_gate",
        "factor_agent": "single_model",
        "factor_gate": "without_gate",
        "description": "单模型端到端推理，无本体门禁拦截与自动降级",
    },
    "G2": {
        "group_id": "G2",
        "name": "三Agent基线 (3-Agent Baseline)",
        "mode": "three_agents",
        "ablation": "none",
        "factor_agent": "three_agents",
        "factor_gate": "with_gate",
        "description": "A1(建档) + A2(合并调查) + A5(复核裁决)",
    },
    "G3": {
        "group_id": "G3",
        "name": "完整五Agent系统 (Full 5-Agent System with Ontology Gate)",
        "mode": "five_agents",
        "ablation": "none",
        "factor_agent": "five_agents",
        "factor_gate": "with_gate",
        "description": "完整五Agent系统：A1(建档)+A2(财务)+A3(跨期)+A4(反证)+A5(复核)+本体门禁",
    },
    "G4": {
        "group_id": "G4",
        "name": "五Agent消融：去A3跨期追踪 (5-Agent Ablation: No Temporal)",
        "mode": "five_agents",
        "ablation": "no_temporal",
        "factor_agent": "five_agents",
        "factor_gate": "with_gate",
        "description": "五Agent系统移除A3跨期追踪角色",
    },
    "G5": {
        "group_id": "G5",
        "name": "五Agent消融：去A4反证机制 (5-Agent Ablation: No Counterevidence)",
        "mode": "five_agents",
        "ablation": "no_counterevidence",
        "factor_agent": "five_agents",
        "factor_gate": "with_gate",
        "description": "五Agent系统移除A4反证与竞争性解释角色",
    },
    "G6": {
        "group_id": "G6",
        "name": "五Agent消融：去本体门禁 (5-Agent Ablation: No Ontology Gate)",
        "mode": "five_agents",
        "ablation": "no_ontology_gate",
        "factor_agent": "five_agents",
        "factor_gate": "without_gate",
        "description": "五Agent系统完全关闭会计语义与勾稽门禁拦截",
    },
    "G7": {
        "group_id": "G7",
        "name": "单模型+本体门禁 (Single Model + Ontology Gate)",
        "mode": "single_model",
        "ablation": "none",
        "factor_agent": "single_model",
        "factor_gate": "with_gate",
        "description": "单模型推理后经程序本体门禁校验与自动降级",
    },
}

FACTORIAL_2X2_GROUPS = ["G1", "G7", "G6", "G3"]


def usage(calls, name):
    return sum(
        c.get(name) if c.get(name) is not None else
        (c.get(name.replace('_tokens', '_token_upper_bound'), 0) if c.get('request_attempted') else 0)
        for c in calls
    )


def resolve_groups(args) -> list[str]:
    if args.factor_design:
        return FACTORIAL_2X2_GROUPS
    if args.groups:
        raw_items = [item.strip().upper() for item in args.groups.split(",") if item.strip()]
        resolved = []
        for item in raw_items:
            if item in EXPERIMENT_GROUPS:
                resolved.append(item)
            elif item == "ALL":
                resolved = list(EXPERIMENT_GROUPS.keys())
                break
            elif item in {"FACTORIAL", "2X2"}:
                resolved = list(FACTORIAL_2X2_GROUPS)
                break
            elif item == "BASELINE":
                resolved = ["G0", "G1", "G2", "G3"]
                break
            else:
                raise ValueError(f"未知的实验组别代码: {item}，可选: {list(EXPERIMENT_GROUPS.keys())}")
        return resolved

    # 默认行为（保持向后兼容）：
    if not args.allow_models:
        return ["G0"]
    if args.ablations:
        return ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]
    return ["G0", "G1", "G2", "G3"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--report-set", help="资料集合ID (如 REPORT-SET-000858-2025)")
    source.add_argument("--pair", help="双报告配对ID (如 CNINFO_000858_T0_20260430)")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--allow-models", action="store_true", help="允许本次真实付费调用；不绕过额度")
    parser.add_argument("--local", action="store_true", help="显式选择独立本地账本；默认沿用环境持久化配置")
    parser.add_argument("--groups", type=str, help="逗号分隔的实验组代码，如 G0,G1,G3,G6,G7 或 factorial, all")
    parser.add_argument("--factor-design", action="store_true", help="快捷启用2x2因子设计对照 (G1, G7, G6, G3)")
    parser.add_argument("--ablations", action="store_true", help="追加G4(无跨期)、G5(无反证)、G6(无门禁)、G7(单模型+门禁)")
    parser.add_argument("--experiment-mode", choices=["end_to_end", "fixed_evidence"], default="end_to_end",
                        help="实验对照模式：end_to_end(端到端自主检索，实验A) 或 fixed_evidence(固定候选证据，实验B)")
    parser.add_argument("--repeat", type=int, choices=range(1, 6), default=1, help="独立重复运行次数 (1-5，默认1)")
    parser.add_argument("--max-matters", type=int, choices=range(1, 11), default=3, help="深查事项数量上限")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/matter-comparison-20261026")
    parser.add_argument("--matter-id", help="预筛档案中选中的单一事项ID")
    parser.add_argument("--case-id", help="人工标注表中的案例ID，默认使用事项ID")
    parser.add_argument("--case-manifest", type=Path, default=ROOT / "docs/competition/development_cases.json")
    parser.add_argument("--max-provider-calls", type=int, choices=range(1, 41), default=20)
    parser.add_argument("--max-role-rounds", type=int, choices=range(1, 7), default=2)
    parser.add_argument("--evidence-ids", type=Path, help="固定证据ID列表JSON，未指定时冻结共享预处理候选")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    if args.local:
        os.environ["AUDITTRACE_DEMO_TASK_PERSISTENCE"] = "local"
        os.environ["AUDITTRACE_RUNTIME_NAMESPACE"] = "matter-comparison-20261026"

    selected_group_ids = resolve_groups(args)
    requires_models = any(EXPERIMENT_GROUPS[gid]["mode"] != "calculation_only" for gid in selected_group_ids)

    if requires_models and not args.allow_models:
        parser.error("所选条件需要真实模型，必须显式指定 --allow-models；未替换为离线实验")

    if requires_models and not args.matter_id:
        parser.error("真实对照必须指定 --matter-id，先用程序预筛建立候选档案")

    if requires_models and not any(os.getenv(k, "").strip() for k in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY")):
        parser.error("缺少真实供应商配置，未执行真实对照")
    question = {}
    if requires_models:
        if not args.case_id:
            parser.error("真实对照必须指定 --case-id 和可核对的问题清单")
        try:
            question = resolve_case(args.case_manifest, args.case_id, report_set_id=args.report_set,
                                    matter_id=args.matter_id, as_of=args.as_of)
        except ValueError as error:
            parser.error(str(error))

    from backend.app.connectivity_pipeline import run_pipeline
    from backend.app.connectivity_schemas import RunRequest
    from backend.app.connectivity_matter_schemas import InvestigationBudget
    from backend.app.connectivity_delivery import export_run
    from backend.app.main import _public_model_ledger

    args.output.mkdir(parents=True, exist_ok=True)
    summary = []

    print(f"=== 审迹智链 AuditTrace 严谨对照实验 ===")
    print(f"模式: {args.experiment_mode.upper()} ({'实验 A: 端到端' if args.experiment_mode == 'end_to_end' else '实验 B: 固定证据'})")
    print(f"组别: {', '.join(selected_group_ids)}")
    print(f"重复次数: {args.repeat} 次")
    print(f"输出目录: {args.output}")
    print("=" * 45)

    for repeat in range(args.repeat):
        for gid in selected_group_ids:
            group_info = EXPERIMENT_GROUPS[gid]
            mode = group_info["mode"]
            ablation = group_info["ablation"]
            tag = f"{gid}_{mode}" if ablation == "none" else f"{gid}_{mode}-{ablation}"
            print(f"\n[运行] Repeat {repeat+1}/{args.repeat} | 组别: {gid} ({group_info['name']}) | Mode: {mode} | Ablation: {ablation}")

            reservation = None
            latest = None
            run = None
            ledger = _public_model_ledger()

            def reserve():
                nonlocal reservation
                reservation = ledger.reserve_batch("matter-comparison-20261026")

            def checkpoint(value):
                nonlocal latest
                latest = value.model_copy(deep=True)
                (args.output / f"{repeat+1}-{tag}.checkpoint.json").write_text(
                    value.model_dump_json(indent=2), encoding="utf-8"
                )

            def provider_budget(value):
                if reservation:
                    ledger.checkpoint_usage(
                        reservation,
                        input_tokens=usage(value.provider_calls, "input_tokens"),
                        output_tokens=usage(value.provider_calls, "output_tokens"),
                    )

            body = RunRequest(
                **question,
                pair_id=args.pair,
                report_set_id=args.report_set,
                as_of_date=args.as_of,
                analysis_scope="matter_connectivity",
                mode=mode,
                ablation=ablation,
                experiment_mode=args.experiment_mode,
                selected_matter_ids=[args.matter_id] if args.matter_id else [],
                comparison_run=True,
                fixed_evidence_ids=json.loads(args.evidence_ids.read_text()) if args.evidence_ids else [],
                budget=InvestigationBudget(max_matters=1, max_provider_calls=args.max_provider_calls, max_role_rounds=args.max_role_rounds),
            )

            row = {
                "repeat": repeat + 1,
                "case_id": args.case_id or args.matter_id,
                "matter_id": args.matter_id,
                "result_file": f"{repeat+1}-{tag}.json",
                "budget": body.budget.model_dump(),
                "group_id": gid,
                "group_name": group_info["name"],
                "mode": mode,
                "ablation": ablation,
                "experiment_mode": args.experiment_mode,
                "factor_agent": group_info["factor_agent"],
                "factor_gate": group_info["factor_gate"],
                "status": "failed",
                "human_scoring": "not_run",
                "professional_quality": "not_evaluated",
            }

            try:
                run = run_pipeline(
                    ROOT,
                    body,
                    before_model=reserve,
                    checkpoint=checkpoint,
                    provider_budget=provider_budget,
                    progress=lambda stage, status, detail: print(f"  [{gid}] {stage}: {status} - {detail}", flush=True),
                )
                (args.output / f"{repeat+1}-{tag}.json").write_text(
                    run.model_dump_json(indent=2), encoding="utf-8"
                )
                for fmt in ("csv", "docx"):
                    try:
                        content, _ = export_run(run, fmt)
                        (args.output / f"{repeat+1}-{tag}.{fmt}").write_bytes(content)
                    except Exception as export_err:
                        print(f"  [警告] 导出 {fmt} 失败: {export_err}")

                row.update(
                    status="recorded",
                    run_id=run.run_id,
                    model_status=run.model_status,
                    report_set=run.report_set.model_dump(mode="json") if run.report_set else None,
                    matter_overview=run.matter_overview,
                    fixed_evidence_sha256=run.versions.get("fixed_evidence_sha256"),
                    provider_calls=len(run.provider_calls),
                    successful_calls=sum(c.get("status") == "completed" for c in run.provider_calls),
                    **usage_receipt(run.provider_calls),
                    duration_ms=run.duration_ms,
                    cost=None,
                    cost_note="无已验证计价，不估算费用",
                )
                eligible, reason = execution_eligibility(run.model_dump(mode="json"))
                row.update(execution_eligible=eligible, execution_reason=reason,
                           fixed_input_sha256=run.versions.get("fixed_input_sha256"))
                canonical=run.versions.get('investigation_scope', {}).get('selected_matter_ids', [])
                if len(canonical)==1:
                    row['requested_matter_id']=args.matter_id
                    row['matter_id']=canonical[0]
            except Exception as error:
                row["failure"] = type(error).__name__ + ": " + str(error)[:300]
                print(f"  [失败] {row['failure']}")
            finally:
                if reservation:
                    calls = (run or latest).provider_calls if (run or latest) else []
                    try:
                        ledger.settle(
                            reservation,
                            input_tokens=usage(calls, "input_tokens"),
                            output_tokens=usage(calls, "output_tokens"),
                        )
                    except Exception as error:
                        row["quota_settlement_error"] = type(error).__name__
                summary.append(row)
                (args.output / "comparison.json").write_text(
                    json.dumps(
                        {
                            "origin": "actual_execution_records",
                            "experiment_mode": args.experiment_mode,
                            "comparison_status": "real_models_requested" if args.allow_models else "offline_only",
                            "factorial_matrix": {
                                "single_model_without_gate": "G1",
                                "single_model_with_gate": "G7",
                                "five_agents_without_gate": "G6",
                                "five_agents_with_gate": "G3",
                            },
                            "executed_groups": selected_group_ids,
                            "runs": summary,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

    print("\n" + "=" * 45)
    print("=== 实验运行汇总表 ===")
    print(f"{'组别':<6} | {'模式':<14} | {'消融':<18} | {'状态':<10} | {'调用次数':<8} | {'耗时(ms)':<8}")
    print("-" * 75)
    for r in summary:
        print(f"{r['group_id']:<6} | {r['mode']:<14} | {r['ablation']:<18} | {r['status']:<10} | {r.get('provider_calls', 0):<8} | {r.get('duration_ms', 0):<8}")
    print("=" * 45)

    return 1 if any(not r.get("execution_eligible") for r in summary) else 0


if __name__ == "__main__":
    raise SystemExit(main())
