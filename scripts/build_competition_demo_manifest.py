"""生成竞赛演示版 15 案例候选 manifest 与 G0—G9 准入矩阵（批次 1 工具）。

批次 1 只建立 pending 候选清单，不修改页面、后端业务代码或模型配置。
数据来源限定为三个可复验文件/模块：
  1. backend/cache_seed.lock.json（14 家 CNINFO 案例的来源冻结与 RAG 登记事实）；
  2. outputs/external_model_acceptance/current.json（历史外部模型技术链证据，仅作线索）；
  3. backend/app/data.py（标准股份内置案例常量）。
本脚本不臆造任何 admission_status=passed；最终冻结由批次 5 完成后另行写入。
写入文件后按最终字节计算 SHA-256，供后续核对与冻结记录使用。
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))

MANIFEST_PATH = WORKSPACE_ROOT / "backend" / "competition_demo_cases.json"
MATRIX_DIR = WORKSPACE_ROOT / "outputs" / "competition_demo_admission"
MATRIX_PATH = MATRIX_DIR / "admission_matrix.json"

# 计划 15.2/15.3 的候选：case_id、演示分组、首页讲解重点。
# 顺序即首页/抽屉展示顺序，featured 恰好 3 个且必须是 cases 子集。
FEATURED_FOCUS = {
    "STD_DEV_T0": "完整主链",
    "CNINFO_000858_T0_20260430": "风险候选案例",
    "CNINFO_600938_T0_20260326": "能源行业案例",
}
EXTENDED_GROUPS = {
    "CNINFO_601857_T0_20260329": "能源与资源",
    "CNINFO_600028_T0_20260322": "能源与资源",
    "CNINFO_600900_T0_20260429": "能源与资源",
    "CNINFO_601899_T0_20260320": "能源与资源",
    "CNINFO_002594_T0_20260327": "汽车与装备制造",
    "CNINFO_300750_T0_20260309": "汽车与装备制造",
    "CNINFO_600031_T0_20260330": "汽车与装备制造",
    "CNINFO_000333_T0_20260330": "消费、家电与科技制造",
    "CNINFO_000651_T0_20260428": "消费、家电与科技制造",
    "CNINFO_600690_T0_20260326": "消费、家电与科技制造",
    "CNINFO_600519_T0_20260416": "消费、家电与科技制造",
    "CNINFO_002415_T0_20260417": "消费、家电与科技制造",
}
# 计划 15.5 的候补池：不进入 15 案 manifest，只在准入矩阵中登记为候补目标。
BACKUP_CASE_IDS = [
    "CNINFO_002475_T0_20260414",
    "CNINFO_600104_T0_20260401",
    "CNINFO_600309_T0_20260420",
    "CNINFO_600276_T0_20260325",
    "CNINFO_601985_T0_20260429",
]

# G0—G9 十项硬门槛定义（计划 16.1）；失败处理保持中文原文，供矩阵与报告引用。
GATE_DEFINITIONS = {
    "G0": {"name": "身份唯一", "check": "case_id、公司、股票代码、T0 唯一一致", "required": "无重复、无跨案例污染", "on_fail": "修复注册表后重验"},
    "G1": {"name": "来源冻结", "check": "三年年报标题、URL、页数、SHA-256", "required": "全部存在且与写入字节一致", "on_fail": "重新冻结，不沿用旧结果"},
    "G2": {"name": "行业适配", "check": "行业闸门与规则范围", "required": "direct 或已单独批准的明确适配", "on_fail": "移出正式列表"},
    "G3": {"name": "字段质量", "check": "R1/R2 所需字段、单位、年度、页码、口径", "required": "无阻断质量问题；缺失项被诚实标注", "on_fail": "人工回页或替换案例"},
    "G4": {"name": "RAG", "check": "案例隔离索引、来源指纹、固定问题检索", "required": "ready、片段数大于 0、固定问题能命中本案例", "on_fail": "重建索引并重验"},
    "G5": {"name": "确定性链", "check": "固定规则计算和 Schema", "required": "HTTP 成功，无异常，无跨案例数据", "on_fail": "修复后端后重验全部 15 案"},
    "G6": {"name": "真实模型链", "check": "challenge、counter、review 三角色", "required": "当前最终 HEAD 完成；调用数和 token 留痕正确", "on_fail": "不得用回放冒充"},
    "G7": {"name": "事实语言", "check": "结论、claims、证据 ID、风险措辞", "required": "无无证据断言、无审计结论化表达", "on_fail": "修复 Prompt 或闸门后重验"},
    "G8": {"name": "浏览器链", "check": "选择、运行、结果、证据抽屉、重置", "required": "无卡死、无 console error、无意外失败请求", "on_fail": "修复前端后重验"},
    "G9": {"name": "恢复能力", "check": "刷新、超时、重复点击、服务重启", "required": "状态可解释，最多一次操作恢复", "on_fail": "修复状态机后重验"},
}


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def _cninfo_documents(entry: dict) -> list[dict]:
    """从缓存锁登记中提取 G1 需要的来源冻结字段，未登记的字段保持缺失。"""
    documents = []
    for doc in sorted(entry.get("documents", []), key=lambda item: -int(item.get("report_year") or 0)):
        documents.append(
            {
                "report_year": doc.get("report_year"),
                "announcement_title": doc.get("announcement_title"),
                "disclosure_date": doc.get("disclosure_date"),
                "source_url": doc.get("source_url"),
                "page_count": doc.get("page_count"),
                "byte_count": doc.get("byte_count"),
                "sha256": doc.get("sha256"),
                "validation_status": doc.get("validation_status"),
            }
        )
    return documents


def _std_case() -> dict:
    """标准股份内置案例：从冻结数据模块读取，不使用命令行临时输入。"""
    import backend.app.data as data

    documents = []
    for year in (2025, 2024, 2023):
        doc = data.ANNUAL_REPORT_SOURCES.get(year)
        if not doc:
            continue
        # 内置案例登记中没有页数字段，保持 None 而不是估算。
        documents.append(
            {
                "report_year": year,
                "announcement_title": doc.get("announcement_title"),
                "disclosure_date": doc.get("disclosure_date"),
                "source_url": doc.get("source_url"),
                "page_count": None,
                "byte_count": None,
                "sha256": doc.get("file_sha256"),
                "validation_status": "registered_local_pdf",
            }
        )
    period = data.PERIODS.get("2025") or {}
    return {
        "ticker": data.TICKER,
        "company_name": data.CASE_NAME,
        "industry_family": None,
        "report_years": [2025, 2024, 2023],
        "source_fingerprint": data.SOURCE_SNAPSHOT_ID,
        "rag_index_version": None,
        "allowed_rules": ["R1", "R2"],
        "t0": period.get("t0"),
        "documents": documents,
    }


def build_manifest() -> dict:
    lock = json.load(io.open(WORKSPACE_ROOT / "backend" / "cache_seed.lock.json", encoding="utf-8"))
    entries = {entry["case_id"]: entry for entry in lock["entries"]}
    acceptance = json.load(io.open(WORKSPACE_ROOT / "outputs" / "external_model_acceptance" / "current.json", encoding="utf-8"))
    acceptance_runs = {case["case_id"]: case for case in acceptance.get("cases", [])}

    cases = []
    std = _std_case()
    order = list(FEATURED_FOCUS) + list(EXTENDED_GROUPS)
    for case_id in order:
        featured = case_id in FEATURED_FOCUS
        if case_id == "STD_DEV_T0":
            source = std
            acceptance_run = acceptance_runs.get(case_id)
        else:
            entry = entries.get(case_id)
            if entry is None:
                raise SystemExit(f"候选案例未在 cache_seed.lock.json 登记：{case_id}")
            gate = entry.get("industry_gate") or {}
            period_t0 = None
            for doc in entry.get("documents", []):
                if int(doc.get("report_year") or 0) == int((entry.get("report_years") or [0])[0]):
                    period_t0 = doc.get("disclosure_date")
                    break
            source = {
                "ticker": entry["ticker"],
                "company_name": entry["company_name"],
                "industry_family": entry.get("industry_family"),
                "report_years": entry.get("report_years"),
                "source_fingerprint": entry.get("source_fingerprint"),
                "rag_index_version": entry.get("rag_index_version"),
                "allowed_rules": gate.get("allowed_rules") or ["R1"],
                "t0": period_t0,
                "documents": _cninfo_documents(entry),
            }
            acceptance_run = acceptance_runs.get(case_id)
        if acceptance_run is None:
            raise SystemExit(f"候选案例缺少历史外部模型技术链证据：{case_id}")
        cases.append(
            {
                "case_id": case_id,
                "ticker": source["ticker"],
                "company_name": source["company_name"],
                "category": "featured" if featured else EXTENDED_GROUPS[case_id],
                "demo_focus": FEATURED_FOCUS.get(case_id, "扩展行业覆盖"),
                "report_years": source["report_years"],
                "t0": source["t0"],
                "rule_ids": source["allowed_rules"],
                "industry_family": source["industry_family"],
                "source_fingerprint": source["source_fingerprint"],
                "rag_index_version": source["rag_index_version"],
                "documents": source["documents"],
                "historical_external_model_run": {
                    "run_id": acceptance_run.get("run_id"),
                    "route": acceptance_run.get("route"),
                    "provider_call_count": acceptance_run.get("provider_call_count"),
                    "run_completeness": acceptance_run.get("run_completeness"),
                    "evidence": "outputs/external_model_acceptance/current.json",
                },
                "admission_status": "pending",
                "admission_evidence": None,
            }
        )

    manifest = {
        "schema_version": "competition_demo_cases_v1",
        "frozen_at": "待最终冻结",
        "source_head": _git_head(),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "case_count": len(cases),
        "featured_case_ids": list(FEATURED_FOCUS),
        "backup_candidate_case_ids": BACKUP_CASE_IDS,
        "notes": [
            "admission_status 仅允许在最终 HEAD 十项门槛全部复验后写为 passed。",
            "historical_external_model_run 只是传输、Schema 与 Agent 技术链证据，不代表字段正确或专业效果已批准。",
            "demo_focus 只说明讲解重点，不预写任何运行结论。",
        ],
        "cases": cases,
    }
    _validate_manifest(manifest, entries)
    return manifest


def _validate_manifest(manifest: dict, entries: dict) -> None:
    if manifest["case_count"] != len(manifest["cases"]) != 15:
        raise SystemExit("case_count 必须等于 cases.length 且为 15")
    ids = [case["case_id"] for case in manifest["cases"]]
    if len(set(ids)) != len(ids):
        raise SystemExit("case_id 存在重复")
    featured = manifest["featured_case_ids"]
    if len(featured) != 3 or not set(featured).issubset(set(ids)):
        raise SystemExit("featured_case_ids 必须恰好 3 个且属于 cases")
    for case in manifest["cases"]:
        if case["admission_status"] != "pending":
            raise SystemExit("批次 1 manifest 只允许 pending 状态")
        years = case["report_years"] or []
        if len(years) < 3:
            raise SystemExit(f"{case['case_id']} 三年年报登记不足")
        if case["case_id"] != "STD_DEV_T0" and entries.get(case["case_id"], {}).get("cache_status") != "ready":
            raise SystemExit(f"{case['case_id']} 缓存状态不是 ready")


def build_matrix(manifest: dict) -> dict:
    cases: dict[str, dict] = {}
    for case in manifest["cases"]:
        cases[case["case_id"]] = {
            "company_name": case["company_name"],
            "category": case["category"],
            "level_target": "A" if case["case_id"] in manifest["featured_case_ids"] else "B",
            "gates": {gate: {"status": "not_run", "evidence": None} for gate in GATE_DEFINITIONS},
        }
    for case_id in BACKUP_CASE_IDS:
        cases[case_id] = {
            "company_name": None,
            "category": "backup",
            "level_target": "C",
            "gates": {gate: {"status": "not_run", "evidence": None} for gate in GATE_DEFINITIONS},
        }
    return {
        "schema_version": "competition_demo_admission_v1",
        "generated_at": manifest["generated_at"],
        "source_head": manifest["source_head"],
        "gate_definitions": GATE_DEFINITIONS,
        "status_enum": ["not_run", "passed", "failed"],
        "cases": cases,
    }


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    io.open(path, "w", encoding="utf-8", newline="\n").write(data)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def main() -> None:
    manifest = build_manifest()
    matrix = build_matrix(manifest)
    manifest_sha = _write_json(MANIFEST_PATH, manifest)
    matrix_sha = _write_json(MATRIX_PATH, matrix)
    print(
        json.dumps(
            {
                "manifest": {"path": str(MANIFEST_PATH.relative_to(WORKSPACE_ROOT)), "sha256": manifest_sha, "cases": manifest["case_count"]},
                "admission_matrix": {"path": str(MATRIX_PATH.relative_to(WORKSPACE_ROOT)), "sha256": matrix_sha, "cases": len(matrix["cases"])},
                "all_admission_status": "pending",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
