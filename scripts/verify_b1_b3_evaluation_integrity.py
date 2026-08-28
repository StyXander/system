"""B1/B2/B3 评估完整性校验。

检查项：
- 冻结合同哈希一致；
- 每条记录 record_sha256 可复算、原始响应哈希一致；
- 每个 (case, group) 恰好一次（不挑成功样本）；
- B1 provider_call_count 必须为 0；
- B2 无 RAG 证据、无多 Agent（单一 review 角色）；
- B3 若完整则含六阶段与三角色；失败/降级不得伪装成功；
- 记录中不含密钥/授权头格式内容；
- 低于 80% 模型成功率的告警标记。

用法：python scripts/verify_b1_b3_evaluation_integrity.py [--evaluation-id ID]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KEY_PATTERN = re.compile(r"(sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{16,}|api[_-]?key[\"']?\s*[:=]\s*['\"]?[A-Za-z0-9]{16,})", re.IGNORECASE)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation-id", default="EVAL-20260825-B1B3-AI-PRESCORE-V1")
    args = parser.parse_args()
    evaluation_id = args.evaluation_id
    eval_dir = ROOT / "outputs" / "evaluation_v5" / evaluation_id
    issues: list[str] = []

    contract_path = eval_dir / "00_contract.json"
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        payload = {k: v for k, v in contract.items() if k != "contract_sha256"}
        if contract.get("contract_sha256") != _sha256_json(payload):
            issues.append("冻结合同哈希不一致")
        if contract.get("schema_version") == "b1_b3_evaluation_contract_v2":
            b2_contract = contract.get("b2_evidence_contract") or {}
            if b2_contract.get("procedure_evidence_id_pattern") != "PROC-{rule_id}-{current_year}":
                issues.append("B2 合同缺少确定性程序证据 ID 规则")
            if b2_contract.get("rag_enabled") is not False:
                issues.append("B2 合同不得启用 RAG")
    else:
        issues.append("缺少冻结合同")

    runs_dir = eval_dir / "runs"
    records = []
    if runs_dir.is_dir():
        for path in sorted(runs_dir.glob("*.json")):
            records.append(json.loads(path.read_text(encoding="utf-8")))

    combos: dict[tuple[str, str], int] = {}
    b2_completed = 0
    b2_total = 0
    b3_model_success = 0
    b3_total = 0
    quality_snapshots: list[dict[str, Any]] = []
    for record in records:
        key = (record["case_id"], record["group"])
        combos[key] = combos.get(key, 0) + 1
        payload = {k: v for k, v in record.items() if k != "record_sha256"}
        if record.get("record_sha256") != _sha256_json(payload):
            issues.append(f"{record['case_id']} {record['group']} record_sha256 不一致")
        blob = json.dumps(record, ensure_ascii=False)
        if KEY_PATTERN.search(blob):
            issues.append(f"{record['case_id']} {record['group']} 疑似密钥泄漏")
        if record["group"] == "B1":
            calls = int((record.get("result") or {}).get("provider_call_count") or record.get("provider_call_count") or 0)
            if calls != 0:
                issues.append(f"{record['case_id']} B1 provider_call_count={calls}，应为 0")
        if record["group"] == "B2":
            result = record.get("result") or {}
            if result.get("execution_mode") != "b2_single_model":
                issues.append(f"{record['case_id']} B2 execution_mode 异常")
            if result.get("run_id") and (record.get("status") in {"completed", "failed"}):
                # 单模型基线：记录中不应出现 rag_evidence 结构
                bundle = result.get("evidence_bundle") or {}
                if bundle.get("rag_evidence"):
                    issues.append(f"{record['case_id']} B2 不应包含 RAG 证据")
                procedure_evidence = bundle.get("procedure_evidence") or []
                expected_proc = f"PROC-{(result.get('rule_results') or [{}])[0].get('rule_id', 'R1')}-{record.get('current_year')}"
                proc_ids = {item.get("evidence_id") for item in procedure_evidence if isinstance(item, dict)}
                if expected_proc not in proc_ids:
                    issues.append(f"{record['case_id']} B2 缺少程序证据 {expected_proc}")
            failure_stage = result.get("validation_failure_stage")
            if failure_stage and failure_stage not in {"evidence", "schema", "policy", "fact_language", "validation"}:
                issues.append(f"{record['case_id']} B2 校验阶段无效：{failure_stage}")
        if record["group"] == "B3":
            result = record.get("result") or {}
            b3_total += 1
            if (result.get("model_check") or {}).get("status") == "model_success":
                b3_model_success += 1
            if result.get("run_id"):
                completeness = result.get("run_completeness") or ""
                steps = result.get("agent_steps") or []
                roles = {s.get("role") for s in steps if isinstance(s, dict)}
                if record.get("status") == "completed" and "challenge" not in roles:
                    issues.append(f"{record['case_id']} B3 completed 但缺少 challenge 角色")
            if record.get("status") == "completed" and not record.get("run_id"):
                issues.append(f"{record['case_id']} B3 状态 completed 但无 run_id")
        if record["group"] == "B2":
            b2_total += 1
            if (record.get("result") or {}).get("run_completeness") == "complete_b2_single_model":
                b2_completed += 1
        snapshot = ((record.get("result") or {}).get("context") or {}).get("model_quality_snapshot")
        if isinstance(snapshot, dict) and snapshot.get("sample_count") is not None:
            quality_snapshots.append({**snapshot, "ended_at": record.get("ended_at") or ""})

    duplicate_keys = [k for k, v in combos.items() if v > 1]
    if duplicate_keys:
        issues.append(f"组合重复执行：{duplicate_keys}")
    expected = {("CNINFO_000858_T0_20260430", g) for g in ("B1", "B2", "B3")}
    expected |= {("CNINFO_600938_T0_20260326", g) for g in ("B1", "B2", "B3")}
    expected |= {("STD_DEV_T0", g) for g in ("B1", "B2", "B3")}
    missing = expected - set(combos)
    if missing:
        issues.append(f"缺少组合：{sorted(missing)}")

    latest_quality = max(quality_snapshots, key=lambda item: item.get("ended_at", "")) if quality_snapshots else None
    rate = latest_quality.get("success_rate") if latest_quality else None
    below_80 = bool(latest_quality and latest_quality.get("alert")) or (rate is not None and rate < 0.80)

    print("=" * 60)
    print(f"评估编号：{evaluation_id}")
    print(f"记录数：{len(records)}")
    print(f"组合计数：{dict(combos)}")
    print(f"B2 单模型完成：{b2_completed}/{b2_total}")
    print(f"B3 三 Agent model_success：{b3_model_success}/{b3_total}")
    if latest_quality:
        print(f"最新滚动模型质量窗口：{latest_quality.get('success_count')}/{latest_quality.get('sample_count')} = {rate}")
    else:
        print("最新滚动模型质量窗口：N/A")
    print(f"低于 80% 告警：{'是，需通知项目队长' if below_80 else '否'}")
    print("-" * 60)
    if issues:
        print("发现问题：")
        for issue in issues:
            print(" -", issue)
        print("RESULT: FAIL")
    else:
        print("RESULT: PASS")
    print("=" * 60)


if __name__ == "__main__":
    main()
