"""严格复核既有 51 案外部模型运行并生成可跟踪的脱敏验收清单。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.schemas import AI_GENERATED_CONTENT_NOTICE, RunResponse  # noqa: E402


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} 顶层不是 JSON 对象。")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _strict_success(record: dict[str, Any]) -> bool:
    roles = {
        str(item.get("role")): str(item.get("status"))
        for item in record.get("roles") or []
        if isinstance(item, dict)
    }
    return bool(
        record.get("status_code") == 200
        and record.get("model_status") == "model_success"
        and record.get("execution_mode") == "external_live"
        and record.get("provider_call_count") == 3
        and record.get("cache_hit") is False
        and str(record.get("run_completeness") or "").startswith("complete_")
        and roles == {"challenge": "completed", "counter": "completed", "review": "completed"}
    )


def _attempt_records(record: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = record.get("attempts")
    if isinstance(attempts, list) and attempts:
        return [item for item in attempts if isinstance(item, dict)]
    return [record]


def _collect_run_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "run_id" and isinstance(child, str):
                found.append(child)
            else:
                found.extend(_collect_run_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_collect_run_ids(child))
    return found


def _validate_run_file(path: Path, expected: dict[str, Any]) -> tuple[RunResponse, str]:
    wrapper = _read_json(path)
    if wrapper.get("ai_generated_content_notice") != AI_GENERATED_CONTENT_NOTICE:
        raise ValueError(f"{path.name} 缺少统一 AI 声明。")
    run = RunResponse.model_validate(wrapper.get("run"))
    if run.run_id != expected.get("run_id"):
        raise ValueError(f"{path.name} 的 run_id 与摘要不一致。")
    if run.context.get("case_id") != expected.get("case_id"):
        raise ValueError(f"{path.name} 的 case_id 与摘要不一致。")
    if run.model_check.status != "model_success" or run.execution_mode != "external_live":
        raise ValueError(f"{path.name} 不是外部模型成功运行。")
    if run.cache_hit or run.provider_call_count != 3:
        raise ValueError(f"{path.name} 使用了缓存或 provider call 数量不等于 3。")
    completed = {step.role for step in run.agent_steps if step.status == "completed"}
    if completed != {"challenge", "counter", "review"}:
        raise ValueError(f"{path.name} 没有完成三个角色。")
    if run.input_tokens <= 0 or run.output_tokens <= 0:
        raise ValueError(f"{path.name} 没有正数 token 记录。")
    nested_run_ids = set(_collect_run_ids(run.model_dump(mode="json")))
    if nested_run_ids != {run.run_id}:
        raise ValueError(f"{path.name} 含有不一致的嵌套 run_id：{sorted(nested_run_ids)}")

    bundle = run.evidence_bundle or {}
    allowed_ids = {
        str(item.get("evidence_id"))
        for key in ("field_evidence", "rag_evidence", "supplement_evidence", "procedure_evidence")
        for item in bundle.get(key, [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    for step in run.agent_steps:
        if step.output is None:
            continue
        for claim in [*step.output.claims, *step.output.normal_explanations]:
            unknown = set(claim.evidence_ids) - allowed_ids
            if unknown:
                raise ValueError(f"{path.name} 引用了证据包外 ID：{sorted(unknown)}")
    return run, _sha256(path)


def validate(
    *,
    main_summary: Path,
    retry_summary: Path,
    runs_dir: Path,
) -> dict[str, Any]:
    main = _read_json(main_summary)
    retry = _read_json(retry_summary)
    main_results = [item for item in main.get("results") or [] if isinstance(item, dict)]
    retry_results = [item for item in retry.get("results") or [] if isinstance(item, dict)]
    if len(main_results) != 51:
        raise ValueError(f"主批次不是 51 案：{len(main_results)}")
    main_by_case = {str(item.get("case_id")): item for item in main_results}
    if len(main_by_case) != 51:
        raise ValueError("主批次 case_id 不唯一。")
    main_failures = {case_id for case_id, item in main_by_case.items() if not _strict_success(item)}
    retry_by_case = {str(item.get("case_id")): item for item in retry_results}
    if set(retry_by_case) != main_failures:
        raise ValueError(
            f"定向重试集合与主批次失败集合不一致：retry={sorted(retry_by_case)} failure={sorted(main_failures)}"
        )

    final_by_case = dict(main_by_case)
    final_by_case.update(retry_by_case)
    invalid = [case_id for case_id, item in final_by_case.items() if not _strict_success(item)]
    if invalid:
        raise ValueError(f"严格成功条件未通过：{invalid}")

    first_attempt_success = 0
    in_batch_retry_success = 0
    for record in main_results:
        attempts = _attempt_records(record)
        if _strict_success(attempts[0]):
            first_attempt_success += 1
        elif _strict_success(record):
            in_batch_retry_success += 1
    targeted_retry_success = sum(1 for record in retry_results if _strict_success(record))

    routes: Counter[str] = Counter()
    completeness: Counter[str] = Counter()
    prompt_versions: Counter[str] = Counter()
    run_hashes: dict[str, str] = {}
    cases: list[dict[str, Any]] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration_ms = 0
    for case_id in sorted(final_by_case):
        record = final_by_case[case_id]
        run_id = str(record.get("run_id") or "")
        run_path = runs_dir / f"{run_id}.json"
        if not run_path.is_file():
            raise ValueError(f"运行文件不存在：{run_path}")
        run, run_sha = _validate_run_file(run_path, record)
        run_hashes[run_id] = run_sha
        routes[run.ai_analysis_route] += 1
        completeness[run.run_completeness] += 1
        prompt_versions[str(run.prompt_version or "unknown")] += 1
        total_input_tokens += run.input_tokens
        total_output_tokens += run.output_tokens
        total_duration_ms += run.duration_ms
        cases.append(
            {
                "case_id": case_id,
                "company_name": str(record.get("company_name") or ""),
                "year": int(record.get("year") or 0),
                "run_id": run_id,
                "run_sha256": run_sha,
                "route": run.ai_analysis_route,
                "run_completeness": run.run_completeness,
                "provider_call_count": run.provider_call_count,
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "duration_ms": run.duration_ms,
            }
        )
    run_bundle_hash = hashlib.sha256(
        "\n".join(f"{run_id}:{run_hashes[run_id]}" for run_id in sorted(run_hashes)).encode("utf-8")
    ).hexdigest().upper()
    return {
        "schema_version": "external_model_acceptance_manifest_v2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "acceptance_scope": "既有 agent_prompt_v3 外部模型技术链；不构成字段专业确认、风险识别准确率或 B3 专业评分。",
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
        "strict_result": {
            "case_count": len(cases),
            "http_200": len(cases),
            "external_live": len(cases),
            "model_success": len(cases),
            "no_cache": len(cases),
            "three_completed_roles": len(cases),
            "provider_calls": len(cases) * 3,
            "first_attempt_success": first_attempt_success,
            "in_batch_retry_success": in_batch_retry_success,
            "later_targeted_retry_success": targeted_retry_success,
            "routes": dict(sorted(routes.items())),
            "run_completeness": dict(sorted(completeness.items())),
            "prompt_versions": dict(sorted(prompt_versions.items())),
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "duration_ms_sum": total_duration_ms,
        },
        "source_artifacts": {
            "main_summary": str(main_summary.relative_to(ROOT)).replace("\\", "/"),
            "main_summary_sha256": _sha256(main_summary),
            "retry_summary": str(retry_summary.relative_to(ROOT)).replace("\\", "/"),
            "retry_summary_sha256": _sha256(retry_summary),
            "runs_directory": str(runs_dir.relative_to(ROOT)).replace("\\", "/"),
            "run_bundle_sha256": run_bundle_hash,
        },
        "professional_validation": {
            "field_page_confirmation": "not_completed",
            "b0_b3_human_scoring": "not_completed",
            "universal_accuracy_claim_allowed": False,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-summary", type=Path, default=ROOT / "tmp" / "external-opencode-go-51.json")
    parser.add_argument("--retry-summary", type=Path, default=ROOT / "tmp" / "external-opencode-go-failures-retry.json")
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "backend" / "runtime" / "external-51-20260812" / "runs")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "external_model_acceptance" / "current.json")
    args = parser.parse_args()
    manifest = validate(
        main_summary=args.main_summary.resolve(),
        retry_summary=args.retry_summary.resolve(),
        runs_dir=args.runs_dir.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["strict_result"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
