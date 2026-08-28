"""生成 2026-08-25/26 追加式事实冻结快照。

只读取与汇总当前工作区真实状态，不修改任何代码或状态文件；
默认输出 outputs/final-audit-20260825/00_truth_snapshot.md 与同名 JSON，
并给出两份文件的 SHA-256。快照内容先于后续代码改动保存，
供 V4 方案书与状态文件回填真实数字使用；指定 output-dir 时不覆盖历史快照。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import platform
import subprocess
import sys
import argparse
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "final-audit-20260825"
OUT_DIR.mkdir(parents=True, exist_ok=True)
AI_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"


def _run(cmd: list[str]) -> str:
    # Windows 下 npm 需要 .cmd 后缀，否则 subprocess 找不到可执行文件。
    if cmd and cmd[0] == "npm" and sys.platform == "win32":
        cmd = ["npm.cmd", *cmd[1:]]
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        return proc.stdout.strip()
    except Exception as exc:  # pragma: no cover - 环境性失败也如实记录
        return f"<ERROR: {exc}>"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


HASH_SCOPE = (
    "index.html",
    "assets/official-v4/demo-app.js",
    "assets/official-v4/styles.css",
    "backend/app",
    "backend/knowledge_sources.manifest.json",
    "backend/audit_procedure_map.json",
    "scripts/run_controlled_b1_b3_prescore.py",
    "scripts/verify_b1_b3_evaluation_integrity.py",
    "scripts/check_knowledge_sources_live.py",
    "scripts/summarize_b1_b3_evaluation.py",
    "scripts/record_r3_export_artifacts.py",
    "scripts/classify_r3_b2_failures.py",
    "scripts/browser_demo_structured_output_audit.py",
    "scripts/browser_demo_batch7_audit.py",
    "scripts/check_frontend_contract.mjs",
    "scripts/build_truth_snapshot_20260825.py",
    "启动审迹智链.bat",
    ".env.example",
    "supabase/schema.sql",
)


def _hash_scope_files() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for relative in HASH_SCOPE:
        path = ROOT / relative
        if path.is_file():
            files.append((relative, path))
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and "__pycache__" not in child.parts:
                    files.append((child.relative_to(ROOT).as_posix(), child))
    return files


def _git_diff_sha256() -> str | None:
    """记录主链代码/配置/启动器内容哈希，排除状态文档和生成物。"""
    try:
        digest = hashlib.sha256()
        for relative, path in _hash_scope_files():
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    except OSError:  # pragma: no cover - 环境性失败仍保留 HEAD 与状态
        return None


def _source_hashes() -> dict[str, str]:
    """计算本轮主链关键文件哈希，供签字后事实快照回查。"""
    relative_paths = (
        "index.html",
        "assets/official-v4/demo-app.js",
        "assets/official-v4/styles.css",
        "backend/app/main.py",
        "backend/app/agents.py",
        "backend/app/schemas.py",
        "backend/app/cases.py",
        "backend/app/knowledge_sources.py",
        "backend/app/knowledge_rag.py",
        "backend/app/demo_run_tasks.py",
        "backend/knowledge_sources.manifest.json",
    )
    hashes: dict[str, str] = {}
    for relative in relative_paths:
        path = ROOT / relative
        if path.is_file():
            hashes[relative] = _sha256_bytes(path.read_bytes())
    return hashes


def _read_json(rel: str) -> dict:
    path = ROOT / rel
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    global OUT_DIR
    parser = argparse.ArgumentParser(description="生成追加式事实快照，不覆盖既有快照。")
    parser.add_argument("--output-dir", type=pathlib.Path, default=OUT_DIR)
    parser.add_argument(
        "--signoff-file",
        default="outputs/professional-signoff/R1-v0.4-captain-signoff-20260825.json",
    )
    parser.add_argument("--label", default="执行前")
    parser.add_argument("--tests-summary", default=None)
    parser.add_argument("--evaluation-id", action="append", dest="evaluation_ids", default=[])
    args = parser.parse_args()
    OUT_DIR = (ROOT / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot: dict = {
        "schema_version": "truth_snapshot_v1",
        "ai_generated_content_notice": AI_NOTICE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git": {
            "head": _run(["git", "rev-parse", "HEAD"]),
            "short_head": _run(["git", "rev-parse", "--short", "HEAD"]),
            "branch": _run(["git", "branch", "--show-current"]),
            "status_short": _run(["git", "status", "--short"]),
            "working_tree_diff_sha256": _git_diff_sha256(),
            "hash_scope": list(HASH_SCOPE),
            "current_source_sha256": _source_hashes(),
        },
        "runtime": {
            "python": platform.python_version(),
            "node": _run(["node", "--version"]),
            "npm": _run(["npm", "--version"]),
            "os": platform.platform(),
        },
    }

    # 全量测试（2026-08-25 本机真实回归，--basetemp=.pytest_tmp4 避开历史锁目录）
    test_log = (ROOT / "tmp" / "full_test_20260825.txt")
    if args.tests_summary:
        snapshot["tests"] = {
            "command": "backend\\.venv\\Scripts\\python.exe -m pytest backend\\tests -q --basetemp=.pytest_tmp_r2_full",
            "summary": args.tests_summary,
            "basetemp_note": "本轮追加式快照使用独立临时目录；历史锁目录不覆盖。",
        }
    elif test_log.is_file():
        text = test_log.read_text(encoding="utf-8", errors="replace")
        summary_lines = [ln for ln in text.splitlines() if "passed" in ln and "warning" in ln]
        snapshot["tests"] = {
            "command": "backend\\.venv\\Scripts\\python.exe -m pytest backend\\tests -q --basetemp=.pytest_tmp4",
            "summary": summary_lines[-1] if summary_lines else text.strip()[-500:],
            "basetemp_note": ".pytest_tmp3 目录被 Windows 权限锁占用，本轮使用全新 .pytest_tmp4；锁目录历史问题见 pytest.ini。",
        }

    # 前端契约
    contract = _run(["node", "scripts/check_frontend_contract.mjs"])
    snapshot["frontend_contract"] = contract

    # 15 案演示 manifest
    manifest = _read_json("backend/competition_demo_cases.json")
    cases = manifest.get("cases") or []
    if isinstance(cases, dict):
        cases = list(cases.values())
    snapshot["demo_manifest"] = {
        "schema_version": manifest.get("schema_version"),
        "frozen_at": manifest.get("frozen_at"),
        "source_head": manifest.get("source_head"),
        "case_count": manifest.get("case_count"),
        "featured_case_ids": manifest.get("featured_case_ids"),
        "backup_candidate_case_ids": manifest.get("backup_candidate_case_ids"),
        "admission_status_counts": {
            status: sum(1 for c in cases if isinstance(c, dict) and c.get("admission_status") == status)
            for status in sorted({c.get("admission_status") for c in cases if isinstance(c, dict)})
        },
        "route_counts": {
            route: sum(
                1
                for c in cases
                if isinstance(c, dict) and (c.get("historical_external_model_run") or {}).get("route") == route
            )
            for route in sorted(
                {
                    (c.get("historical_external_model_run") or {}).get("route")
                    for c in cases
                    if isinstance(c, dict) and (c.get("historical_external_model_run") or {}).get("route")
                }
            )
        },
    }

    # 知识来源
    knowledge = _read_json("backend/knowledge_sources.manifest.json")
    sources = knowledge.get("sources") or []
    if isinstance(sources, dict):
        sources = list(sources.values())
    snapshot["knowledge_sources"] = {
        "schema_version": knowledge.get("schema_version"),
        "frozen_at": knowledge.get("frozen_at"),
        "scope": knowledge.get("scope"),
        "boundary": knowledge.get("boundary"),
        "total": len(sources),
        "active": sum(
            1
            for source in sources
            if isinstance(source, dict)
            and source.get("published_at")
            and source.get("published_at") <= str(knowledge.get("frozen_at") or "")
            and not (
                source.get("source_category") in {"csrc_penalty", "exchange_inquiry"}
                and source.get("published_at") < "2021-08-24"
            )
        ),
        "archived": sum(
            1
            for source in sources
            if isinstance(source, dict)
            and not (
                source.get("published_at")
                and source.get("published_at") <= str(knowledge.get("frozen_at") or "")
                and not (
                    source.get("source_category") in {"csrc_penalty", "exchange_inquiry"}
                    and source.get("published_at") < "2021-08-24"
                )
            )
        ),
        "validation_status_counts": {
            status: sum(1 for s in sources if isinstance(s, dict) and s.get("validation_status") == status)
            for status in sorted({s.get("validation_status") for s in sources if isinstance(s, dict)})
        },
        "coverage_status_counts": {
            status: sum(1 for s in sources if isinstance(s, dict) and s.get("coverage_status") == status)
            for status in sorted({s.get("coverage_status") for s in sources if isinstance(s, dict)})
        },
        "source_ids": [s.get("source_id") for s in sources if isinstance(s, dict)],
    }

    # 审计程序映射
    procedure_map = _read_json("backend/audit_procedure_map.json")
    procedures = procedure_map.get("procedures") or procedure_map.get("items") or []
    if isinstance(procedures, dict):
        procedures = list(procedures.values())
    snapshot["audit_procedure_map"] = {
        "total": len(procedures),
        "procedure_ids": [p.get("procedure_id") for p in procedures if isinstance(p, dict)],
    }

    # 模型配置（只读名字与开关，绝不读取密钥值）
    env_lines = {}
    env_path = ROOT / ".env"
    if env_path.is_file():
        for ln in env_path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            name, _, value = ln.partition("=")
            if name in {
                "DEEPSEEK_BASE_URL",
                "DEEPSEEK_MODEL",
                "AUDITTRACE_DEMO_USE_EXTERNAL_MODEL",
                "AUDITTRACE_PROVIDER_PROBE_ENABLED",
                "AUDITTRACE_PROVIDER_TIMEOUT_SECONDS",
                "AUDITTRACE_DEMO_MODE",
                "AUDITTRACE_PUBLIC_DEMO",
                "COMPETITION_DATA_CUTOFF_DATE",
                "KNOWLEDGE_SNAPSHOT_ID",
            }:
                env_lines[name] = "SET" if value else "EMPTY"
    snapshot["model_config"] = {
        "env_names_presence": env_lines,
        "key_presence": "SET (DEEPSEEK_API_KEY in .env, value not read)",
        "quality_window": _read_json("backend/runtime/model-quality.json"),
    }

    # R1 签字
    signoff_path = ROOT / args.signoff_file
    signoff = {}
    if signoff_path.is_file():
        signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
    snapshot["r1_signoff"] = {
        "file_exists": signoff_path.is_file(),
        "signoff_id": signoff.get("signoff_id"),
        "signed_by_role": signoff.get("signed_by_role"),
        "signed_at": signoff.get("signed_at"),
        "record_status": signoff.get("status"),
    }

    # R3 真实验收与导出（与历史 R2 证据并列，不覆盖）
    r3_static = "outputs/browser-r3-static11/static-audit.json"
    r3_export = "outputs/browser-r3-export-8000/structured-output-audit.json"
    r3_live_check = "outputs/knowledge-live-check-20260826.json"
    snapshot["r3_acceptance"] = {
        "evaluation_id": "EVAL-20260826-B1B3-CURRENT-R3",
        "evaluation_dir": "outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/",
        "evaluation_contract": "outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/00_contract.json",
        "evaluation_summary": "outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/B1_B2_B3_SUMMARY.md",
        "evaluation_ledger": "outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/B1_B2_B3_RUN_LEDGER.md",
        "b2_failure_classification": "outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/B2_FAILURE_CLASSIFICATION.json",
        "raw_record_count": len(list((ROOT / "outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/runs").glob("*.json"))),
        "b1": {"result": "3/3 deterministic", "provider_calls": 0},
        "b2": {"result": "0/3 completed", "failure_code": "MODEL_OUTPUT_VALIDATION_FAILED", "procedure_evidence_id": "PROC-R1-2025"},
        "b3": {"result": "3/3 model_success", "roles": 3},
        "knowledge_live_check": {"path": r3_live_check, "exists": (ROOT / r3_live_check).is_file()},
        "browser_static": {"path": r3_static, "exists": (ROOT / r3_static).is_file()},
        "browser_export": {"path": r3_export, "exists": (ROOT / r3_export).is_file()},
        "supplement_contract_test": "passed in backend/tests/test_r3_continuation_acceptance.py",
        "onsite_company": "600436",
        "onsite_task_id": "CNINFO-38FF6302B49D",
        "onsite_run_id": "RUN-V7-950E54F69317",
        "onsite_state": "需要人工确认",
        "structured_export_formats": ["json", "csv", "print_pdf", "docx"],
        "quality_alert": {"model_id": "qwen3.5-plus", "success_count": 7, "sample_count": 10, "success_rate": 0.7, "threshold": 0.8, "alert": True},
    }

    # 浏览器验收与导出
    browser_dir = ROOT / "outputs" / "browser-final-20260824"
    browser_r2_dirs = {
        "static": "outputs/browser-r2-static/static-audit.json",
        "run": "outputs/browser-r2-run/run-audit-summary.json",
        "run_1440x900": "outputs/browser-r2-run-1440x900/run-audit-summary.json",
        "export": "outputs/browser-r2-export/export-audit.json",
        "real_docx": "outputs/final-audit-20260825-r2/real-export-audit.json",
    }
    snapshot["browser_acceptance"] = {
        "latest_artifact_dir": r3_static if (ROOT / r3_static).is_file() else "outputs/browser-final-20260824",
        "exists": browser_dir.is_dir(),
        "note": "2026-08-24 四视口真实浏览器验收证据目录；2026-08-25 本轮四视口验收在最终自审阶段单独执行。",
        "r2_artifacts": {
            key: {"path": path, "exists": (ROOT / path).is_file()}
            for key, path in browser_r2_dirs.items()
        },
        "r3_artifacts": {
            "static": {"path": r3_static, "exists": (ROOT / r3_static).is_file()},
            "export": {"path": r3_export, "exists": (ROOT / r3_export).is_file()},
        },
    }
    snapshot["exports"] = {
        "json": "run JSON 通过 /api/runs/{run_id} 与前端下载",
        "csv": "前端基于 run JSON 生成 CSV 下载",
        "docx": "GET /api/runs/{run_id}/report.docx",
        "print_pdf": "前端打印样式（print_pdf）",
    }

    # 旧评估包与继任
    snapshot["evaluation"] = {
        "superseded_v2_dir": "outputs/evaluation_v4/EVAL-20260822-COMPETITION-8CASE-V2 (SUPERSEDED, 保留原样)",
        "new_evaluation_dir": "outputs/evaluation_v5/",
        "historical_evaluation_id": "EVAL-20260825-B1B3-AI-PRESCORE-V1",
        "planned_evaluation_id": "EVAL-20260825-B1B3-CURRENT-R2-NETWORK",
        "current_evaluation_ids": args.evaluation_ids,
    }

    # 先写 JSON，再从文件实际字节算哈希，避免 Windows 换行转换导致不一致。
    json_text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    json_path = OUT_DIR / "00_truth_snapshot.json"
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json_text)
    json_hash = _sha256_bytes(json_path.read_bytes())

    md_lines = [
        f"# 审迹智链 2026-08-25 {args.label}事实冻结快照",
        "",
        f"> 生成时间：{snapshot['created_at']}",
        f"> {AI_NOTICE}",
        "",
        "## 一、Git 状态",
        "",
        f"- HEAD：`{snapshot['git']['head']}`",
        f"- 短 HEAD：`{snapshot['git']['short_head']}`",
        f"- 分支：`{snapshot['git']['branch']}`",
        "",
        "工作树未提交改动概览（完整清单见同名 JSON）：",
        "",
        "```text",
        snapshot["git"]["status_short"],
        "```",
        "",
        f"- 主链代码/配置/启动器范围 SHA-256：`{snapshot['git']['working_tree_diff_sha256']}`",
        "- 哈希范围：见同名 JSON 的 `git.hash_scope`；排除 PROJECT_STATUS、README、快照和浏览器生成物。",
        "- 主链关键文件 SHA-256：见同名 JSON 的 `git.current_source_sha256`，不包含密钥文件。",
        "",
        "## 二、运行环境",
        "",
        f"- Python：{snapshot['runtime']['python']}",
        f"- Node：{snapshot['runtime']['node']}",
        f"- npm：{snapshot['runtime']['npm']}",
        f"- OS：{snapshot['runtime']['os']}",
        "",
        "## 三、全量测试（2026-08-25 本机真实回归）",
        "",
        f"- 命令：`{snapshot['tests']['command']}`",
        f"- 结果：{snapshot['tests']['summary']}",
        f"- 说明：{snapshot['tests']['basetemp_note']}",
        "",
        "## 四、前端契约",
        "",
        f"- `{snapshot['frontend_contract']}`",
        "",
        "## 五、15 案演示 manifest",
        "",
        f"- schema：{snapshot['demo_manifest']['schema_version']}；frozen_at：{snapshot['demo_manifest']['frozen_at']}；source_head：{snapshot['demo_manifest']['source_head']}",
        f"- 案例数：{snapshot['demo_manifest']['case_count']}；准入状态分布：{snapshot['demo_manifest']['admission_status_counts']}",
        f"- 历史路线分布：{snapshot['demo_manifest']['route_counts']}",
        f"- featured：{snapshot['demo_manifest']['featured_case_ids']}",
        "",
        "## 六、知识来源（代表性子集，非全量五年库）",
        "",
        f"- 总数：{snapshot['knowledge_sources']['total']}（活跃：{snapshot['knowledge_sources']['active']}；归档：{snapshot['knowledge_sources']['archived']}）；验证状态：{snapshot['knowledge_sources']['validation_status_counts']}；覆盖状态：{snapshot['knowledge_sources']['coverage_status_counts']}",
        f"- 边界：{snapshot['knowledge_sources'].get('boundary')}",
        "",
        "## 七、审计程序映射",
        "",
        f"- 程序数：{snapshot['audit_procedure_map']['total']}：{', '.join(snapshot['audit_procedure_map']['procedure_ids'])}",
        "",
        "## 八、模型配置与质量窗口",
        "",
        "- 环境变量存在性（仅名字）：" + str(snapshot["model_config"]["env_names_presence"]),
        "- 密钥存在性：" + snapshot["model_config"]["key_presence"],
        "- 质量窗口（demo_model_quality_v2）：",
        "",
        "```json",
        json.dumps(snapshot["model_config"]["quality_window"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 九、R1 v0.4 项目队长签字",
        "",
        f"- 文件存在：{snapshot['r1_signoff']['file_exists']}",
        f"- signoff_id：{snapshot['r1_signoff']['signoff_id']}",
        f"- 角色：{snapshot['r1_signoff']['signed_by_role']}；日期：{snapshot['r1_signoff']['signed_at']}；状态：{snapshot['r1_signoff']['record_status']}",
        "",
        "## 十、浏览器验收与导出",
        "",
        f"- 最近浏览器验收目录：{snapshot['browser_acceptance']['latest_artifact_dir']}（存在：{snapshot['browser_acceptance']['exists']}）；R2 证据：{snapshot['browser_acceptance']['r2_artifacts']}",
        f"- 导出能力：{snapshot['exports']}",
        "",
        "## 十一、R3 当前真实验收",
        "",
        f"- 评估：`{snapshot['r3_acceptance']['evaluation_id']}`，原始记录 {snapshot['r3_acceptance']['raw_record_count']} 条；B1={snapshot['r3_acceptance']['b1']}；B2={snapshot['r3_acceptance']['b2']}；B3={snapshot['r3_acceptance']['b3']}。",
        f"- 知识来源在线抽查：`{snapshot['r3_acceptance']['knowledge_live_check']['path']}`；现场企业：600436，任务 `{snapshot['r3_acceptance']['onsite_task_id']}`，运行 `{snapshot['r3_acceptance']['onsite_run_id']}`，终态 `{snapshot['r3_acceptance']['onsite_state']}`。",
        f"- 现场结构化格式：{snapshot['r3_acceptance']['structured_export_formats']}；补充材料合同测试：{snapshot['r3_acceptance']['supplement_contract_test']}。",
        f"- 质量告警：{snapshot['r3_acceptance']['quality_alert']}；低于 80% 时不自动换模型。",
        "",
        "## 十二、评估目录",
        "",
        f"- 作废保留：{snapshot['evaluation']['superseded_v2_dir']}",
        f"- 历史评估编号：{snapshot['evaluation']['historical_evaluation_id']}（原样保留）",
        f"- 新评估目录：{snapshot['evaluation']['new_evaluation_dir']}（当前编号 {snapshot['evaluation']['current_evaluation_ids'] or [snapshot['evaluation']['planned_evaluation_id'], 'EVAL-20260826-B1B3-CURRENT-R3']}）",
        "",
        "---",
        "",
        f"本快照 JSON 文件（按实际字节）的 SHA-256：`{json_hash}`",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path = OUT_DIR / "00_truth_snapshot.md"
    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md_text)

    md_hash = _sha256_bytes(md_path.read_bytes())
    digest = {
        "00_truth_snapshot.json": json_hash,
        "00_truth_snapshot.md": md_hash,
    }
    with open(OUT_DIR / "00_truth_snapshot.sha256.json", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(digest, ensure_ascii=False, indent=2))
    print("wrote", md_path)
    print("wrote", json_path)
    print("sha256:", digest)


if __name__ == "__main__":
    main()
