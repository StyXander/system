"""审迹智链 51 案例端到端验收脚本。

对指定后端（默认本地 http://127.0.0.1:8000，可用 --base-url 指向部署站）执行：
1. /api/health 与 /api/status 基础可用性；
2. /api/cases?summary=true 案例目录完整性（51 个内置案例）；
3. 每个案例的详情接口（含统一 AI 声明不变式）；
4. 每个案例一次 calculation_only 的 R1 确定性运行（不调用外部模型）；
5. 每个案例一次 RAG 检索烟测（查询词“应收账款”）；
6. 只读边界抽查（公开站写入路径应被拒绝）。

用法：
    backend\\.venv\\Scripts\\python.exe scripts\\run_51_case_acceptance.py
    backend\\.venv\\Scripts\\python.exe scripts\\run_51_case_acceptance.py --base-url https://audittrace-demo.onrender.com
    backend\\.venv\\Scripts\\python.exe scripts\\run_51_case_acceptance.py --skip-rag --only-readonly

退出码：全部通过为 0，任何失败为 1。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

AI_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
EXPECTED_RUN_STATUSES = {"RULE_NOT_TRIGGERED", "candidate", "DATA_GAP"}
TIMEOUT_SECONDS = 120


def request_json(base_url: str, path: str, method: str = "GET", payload: dict | None = None, retries: int = 3) -> tuple[int, Any]:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read()
                try:
                    body = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    body = {"_raw": raw[:200].decode("utf-8", errors="replace")}
                return response.status, body
        except urllib.error.HTTPError as error:
            # HTTP 错误状态码（4xx/5xx）不再盲目重试，直接上抛给调用方分类。
            raise
        except Exception as error:  # noqa: BLE001
            last_error = error
            if attempt < retries:
                time.sleep(2 * attempt)
    raise last_error  # type: ignore[misc]


def check(condition: bool, message: str) -> bool:
    if condition:
        return True
    print(f"  [FAIL] {message}")
    return False


def has_notice(body: Any) -> bool:
    if isinstance(body, dict):
        if str(body.get("ai_generated_content_notice") or "") == AI_NOTICE:
            return True
        return any(has_notice(value) for value in body.values())
    if isinstance(body, list):
        return any(has_notice(item) for item in body)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="审迹智链 51 案例端到端验收")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--skip-rag", action="store_true", help="跳过每个案例的 RAG 检索烟测")
    parser.add_argument("--skip-runs", action="store_true", help="跳过 calculation_only 运行")
    parser.add_argument("--only-readonly", action="store_true", help="只测只读边界抽查")
    parser.add_argument("--json-out", default=None, help="把结果写到 JSON 文件")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    failures: list[str] = []
    case_results: list[dict[str, Any]] = []
    started = time.time()

    def record(case_id: str, stage: str, ok: bool, detail: str = "") -> None:
        case_results.append({"case_id": case_id, "stage": stage, "ok": ok, "detail": detail})
        if not ok:
            failures.append(f"{case_id} [{stage}] {detail}")

    def gate(condition: bool, message: str, stage: str = "health") -> None:
        if not condition:
            failures.append(f"{stage}: {message}")
        check(condition, message)

    # 1. health / status
    try:
        code, health = request_json(base_url, "/api/health")
        if isinstance(health, dict) and code == 200:
            gate(code == 200, f"/api/health HTTP {code}")
            gate(str(health.get("service_status")) == "ready", f"health service_status={health.get('service_status')}")
            for key in ("full_analysis_ready", "full_analysis_reason_code", "full_analysis_message", "deterministic_backup_available"):
                gate(key in health, f"health 缺少 {key}")
        else:
            gate(False, f"/api/health HTTP {code}")
    except Exception as error:  # noqa: BLE001
        failures.append(f"/api/health 异常: {error}")
    try:
        code, status = request_json(base_url, "/api/status")
        gate(code == 200, f"/api/status HTTP {code}", "status")
        if isinstance(status, dict):
            print(f"  [info] demo_mode={bool((status.get('demo_mode') or {}).get('enabled'))} "
                  f"model_execution_mode={(status.get('model') or {}).get('execution_mode')} "
                  f"full_analysis_ready={(status.get('model') or {}).get('full_analysis_ready')}")
            gate(has_notice(status), "/api/status 缺少统一 AI 声明", "status")
            model = status.get("model") or {}
            for key in ("full_analysis_ready", "full_analysis_reason_code", "full_analysis_message", "deterministic_backup_available"):
                gate(key in model, f"/api/status.model 缺少 {key}", "status")
    except Exception as error:  # noqa: BLE001
        failures.append(f"/api/status 异常: {error}")

    if args.only_readonly:
        run_readonly_checks(base_url, failures)
        return 1 if failures else 0

    # 2. 案例目录
    try:
        code, summary = request_json(base_url, "/api/cases?summary=true")
        check(code == 200, f"/api/cases?summary=true HTTP {code}")
        cases = (summary or {}).get("cases") or []
        print(f"  [info] 目录案例数 = {len(cases)}")
        check(len(cases) >= 51, f"案例数 {len(cases)} < 51")
        for item in cases:
            check(set(item) >= {"case_id", "company_name", "available_years"}, f"摘要缺字段: {item.get('case_id')}")
    except Exception as error:  # noqa: BLE001
        cases = []
        failures.append(f"/api/cases?summary=true 异常: {error}")

    # 3. 每个案例详情 + calculation_only 运行 + RAG
    for index, item in enumerate(cases, start=1):
        case_id = str(item.get("case_id") or "")
        label = f"[{index}/{len(cases)}] {case_id}"
        print(f"{label} 开始", flush=True)
        try:
            code, detail = request_json(base_url, f"/api/cases/{urllib.parse.quote(case_id)}")
            ok = check(code == 200, f"详情 HTTP {code}")
            if ok and isinstance(detail, dict):
                ok = check(str(detail.get("case_id") or "") == case_id, "详情 case_id 不一致") and ok
                check(has_notice(detail), "详情缺少统一 AI 声明")
            years = sorted({int(y) for y in ((detail or {}).get("available_years") or []) if str(y).isdigit()}, reverse=True)
            if not years:
                years = sorted({int(y) for y in item.get("available_years") or [] if str(y).isdigit()}, reverse=True)
            record(case_id, "detail", ok, f"years={years[:3]}")
            if not ok or not years:
                continue

            # calculation_only 确定性运行（不调用外部模型）
            if not args.skip_runs:
                current_year = years[0]
                payload = {
                    "case_id": case_id,
                    "current_year": current_year,
                    "rule_ids": ["R1"],
                    "run_mode": "calculation_only",
                }
                try:
                    code, run = request_json(base_url, "/api/runs", method="POST", payload=payload)
                    run_ok = check(code == 200, f"runs HTTP {code}")
                    status_value = ""
                    completeness = ""
                    run_id = ""
                    if run_ok and isinstance(run, dict):
                        status_value = str(run.get("screening_status") or run.get("status") or "")
                        completeness = str(run.get("run_completeness") or "")
                        run_id = str(run.get("run_id") or "")
                        run_ok = check(status_value in EXPECTED_RUN_STATUSES, f"意外运行状态 {status_value}") and run_ok
                        run_ok = check(has_notice(run), "运行结果缺少统一 AI 声明") and run_ok
                        check(run_id.startswith("RUN-V7"), f"run_id 异常: {run_id}")
                    record(case_id, "calculation_only", run_ok, f"year={current_year} status={status_value} completeness={completeness}")
                except urllib.error.HTTPError as error:
                    detail_text = ""
                    try:
                        detail_text = str(error.read().decode("utf-8", errors="replace"))[:200]
                    except Exception:  # noqa: BLE001
                        pass
                    record(case_id, "calculation_only", False, f"HTTP {error.code}: {detail_text}")
                except Exception as error:  # noqa: BLE001
                    record(case_id, "calculation_only", False, str(error))

            # RAG 检索烟测
            if not args.skip_rag:
                try:
                    payload = {"case_id": case_id, "query": "应收账款、回款与收入变化是否存在需要回查的披露？", "top_k": 5}
                    code, rag = request_json(base_url, "/api/rag/retrieve", method="POST", payload=payload)
                    rag_ok = check(code == 200, f"rag HTTP {code}")
                    count = 0
                    if rag_ok and isinstance(rag, dict):
                        results = rag.get("results") or []
                        count = len(results)
                        rag_ok = check(count > 0, "RAG 检索返回 0 条结果") and rag_ok
                        check(has_notice(rag), "RAG 结果缺少统一 AI 声明")
                    record(case_id, "rag", rag_ok, f"hits={count}")
                except urllib.error.HTTPError as error:
                    record(case_id, "rag", False, f"HTTP {error.code}")
                except Exception as error:  # noqa: BLE001
                    record(case_id, "rag", False, str(error))
        except Exception as error:  # noqa: BLE001
            record(case_id, "detail", False, str(error))

    readonly_failures = run_readonly_checks(base_url, failures)

    elapsed = round(time.time() - started, 1)
    total = len(case_results)
    ok_count = total - len(failures)
    print(f"\n==== 验收汇总：共 {total} 项检查，失败 {len(failures)} 项，耗时 {elapsed}s ====")
    for failure in failures[:30]:
        print(f"  - {failure}")
    if len(failures) > 30:
        print(f"  ... 其余 {len(failures) - 30} 项略")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "base_url": base_url,
                    "elapsed_seconds": elapsed,
                    "total_checks": total,
                    "failed": len(failures),
                    "failures": failures,
                    "case_results": case_results,
                    "readonly_failures": readonly_failures,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        print(f"结果已写入 {args.json_out}")
    return 1 if failures else 0


def run_readonly_checks(base_url: str, failures: list[str]) -> list[str]:
    """公开站写入路径抽查：未登录用户应得到 403 而不是 5xx 或放行。

    注意：命中 50 家内置种子企业的巨潮流程在公开站是被允许的幂等路径
    （复用冻结快照、不触发外网下载），因此必须用非内置企业探测拒绝逻辑。
    """
    readonly_failures: list[str] = []
    probes = [
        ("POST", "/api/pipelines/cninfo", {"company_query": "688981", "analysis_mode": "rag_only"}),
        ("POST", "/api/cases/STD_DEV_T0/fields/confirm", {"field_id": "revenue_2024", "decision": "confirm", "reviewer": "probe"}),
    ]
    for method, path, payload in probes:
        try:
            code, _body = request_json(base_url, path, method=method, payload=payload)
            if code in (401, 403, 404, 405):
                print(f"  [info] 只读边界 {method} {path} -> HTTP {code}（符合公开站只读预期）")
            else:
                message = f"只读边界 {method} {path} 意外返回 HTTP {code}"
                print(f"  [FAIL] {message}")
                failures.append(message)
                readonly_failures.append(message)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 404, 405):
                print(f"  [info] 只读边界 {method} {path} -> HTTP {error.code}（符合公开站只读预期）")
            else:
                message = f"只读边界 {method} {path} HTTP {error.code}"
                failures.append(message)
                readonly_failures.append(message)
        except Exception as error:  # noqa: BLE001
            message = f"只读边界 {method} {path} 异常: {error}"
            failures.append(message)
            readonly_failures.append(message)

    # 案例 ZIP 导入是 multipart 接口，单独探测。
    boundary = "----audittrace-probe"
    body_bytes = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="t.zip"\r\n'
        "Content-Type: application/zip\r\n\r\nPK\x05\x06probe\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="authorized"\r\n\r\ntrue\r\n'
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="desensitized"\r\n\r\ntrue\r\n'
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    url = base_url.rstrip("/") + "/api/cases/import"
    req = urllib.request.Request(url, data=body_bytes, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            message = f"只读边界 POST /api/cases/import 意外返回 HTTP {response.status}"
            print(f"  [FAIL] {message}")
            failures.append(message)
            readonly_failures.append(message)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403, 404, 405):
            print(f"  [info] 只读边界 POST /api/cases/import -> HTTP {error.code}（符合公开站只读预期）")
        else:
            message = f"只读边界 POST /api/cases/import HTTP {error.code}"
            failures.append(message)
            readonly_failures.append(message)
    except Exception as error:  # noqa: BLE001
        message = f"只读边界 POST /api/cases/import 异常: {error}"
        failures.append(message)
        readonly_failures.append(message)
    return readonly_failures


if __name__ == "__main__":
    sys.exit(main())
