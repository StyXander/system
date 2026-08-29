# -*- coding: utf-8 -*-
"""生成 B0—B3 正式受控评估的完整冻结合同（evaluation_v4，不可覆盖）。

2026-08-22 外部审查整改版，相对初版的关键修正：
1. RAG 冻结改为真实问题集：version、完整 questions、问题集 SHA-256 和逐案索引状态；
   不再把 question_set() 的顶层键当作问题编号。
2. 模型冻结补齐 temperature、角色输出上限、超时、thinking 配置和实现源码指纹；
   密钥仍然只记录存在性，不记录值。
3. available_years 从字段年度推导，不再照抄种子（修复中国人寿空年度表）。
4. 字段值显式携带冻结状态（candidate_pending_human_review / human_confirmed）
   和回页复核标记（数量级异常、负值），防止候选值被误当已冻结事实。
5. 正式目录在字段未完成人工复核时拒绝生成（--allow-pending-fields 显式豁免），
   机制自测请用 --output-root 指向临时目录，不污染正式评估目录。
本脚本不填任何人工姓名、分数或签字，也不调用模型。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import data as std_data
from backend.app.agents import ROLE_MAX_OUTPUT_TOKENS, THINKING_CONFIG
from backend.app.evaluation import (
    B0_B3_DEFINITIONS,
    EVALUATION_ID,
    FIXED_CASES,
    write_evaluation_dashboard,
)
from backend.app.rag import question_set
from backend.app.seed_catalog import load_seed_cases


def _sha256_json(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field_review_flag(value, unit: str) -> list[str]:
    """回页复核标记：只做保守提示，不替代人工判断。"""
    flags: list[str] = []
    if isinstance(value, (int, float)):
        if value < 0:
            flags.append("负值：应收/收入类字段出现负数，须回页确认")
        if abs(value) < 10000 and unit == "元":
            flags.append("数量级异常：大型上市公司金额低于 1 万元，疑似行列取数错误")
    return flags


def _field_freeze_status(human_status) -> str:
    if human_status in ("confirmed", "corrected"):
        return "human_confirmed"
    if human_status == "rejected":
        return "human_rejected"
    return "candidate_pending_human_review"


def _std_case_snapshot() -> dict:
    """标准股份从冻结注册表取数：T0、年度、字段值与四份年报哈希一次成型。"""
    context, rows = std_data.get_period_sources(2025, ("R1", "R2"))
    fields = []
    for row in rows:
        flags = _field_review_flag(row["value"], row["unit"])
        fields.append(
            {
                "field_id": row["field_id"],
                "field_kind": row["field_kind"],
                "year": row["year"],
                "value": row["value"],
                "unit": row["unit"],
                "evidence_id": row["evidence_id"],
                "document_id": row["document_id"],
                "pdf_page": row["pdf_page"],
                "locator": row["locator"],
                "field_basis": row["field_basis"],
                "field_freeze_status": "registry_technical_crosscheck_pending_human",
                "review_flags": flags,
            }
        )
    documents = [
        {
            "document_id": f"STD-AR-{year}-{meta['file_sha256'][:12]}",
            "document_type": "annual_report",
            "report_year": year,
            "disclosure_date": meta["disclosure_date"],
            "announcement_title": meta["announcement_title"],
            "source_url": meta["source_url"],
            "sha256": meta["file_sha256"],
        }
        for year, meta in sorted(std_data.ANNUAL_REPORT_SOURCES.items(), reverse=True)
    ]
    return {
        "case_id": std_data.CASE_ID,
        "company_name": std_data.CASE_NAME,
        "stratum": "rule_not_triggered",
        "t0": context["t0"],
        "analysis_year": 2025,
        "available_years": sorted({f["year"] for f in fields}, reverse=True),
        "source_snapshot_id": std_data.SOURCE_SNAPSHOT_ID,
        "source_review_status": std_data.SOURCE_REVIEW_STATUS,
        "documents": documents,
        "financial_fields": fields,
        "data_origin": "backend/app/data.py 冻结注册表（W2 技术复核样例，人工确认待完成）",
    }


def _cninfo_case_snapshot(seed: dict, stratum: str) -> dict:
    fields = []
    for row in seed.get("financial_fields", []):
        human_status = (row.get("human_review") or {}).get("status", "pending")
        value = row.get("value")
        flags = _field_review_flag(value, row.get("unit") or "元")
        fields.append(
            {
                "field_id": row.get("field_id"),
                "field_kind": row.get("field_kind"),
                "year": row.get("year"),
                "value": value,
                "unit": row.get("unit"),
                "evidence_id": row.get("evidence_id"),
                "document_id": (row.get("candidate") or {}).get("document_id"),
                "pdf_page": (row.get("candidate") or {}).get("pdf_page"),
                "locator": (row.get("candidate") or {}).get("locator"),
                "field_basis": row.get("field_basis"),
                "field_freeze_status": _field_freeze_status(human_status),
                "review_flags": flags,
            }
        )
    documents = [
        {
            "document_id": doc.get("document_id"),
            "document_type": doc.get("document_type"),
            "report_year": doc.get("report_year"),
            "disclosure_date": doc.get("disclosure_date"),
            "announcement_title": doc.get("announcement_title"),
            "source_url": doc.get("source_url"),
            "sha256": doc.get("sha256") or doc.get("file_sha256"),
        }
        for doc in seed.get("documents", [])
    ]
    return {
        "case_id": seed.get("case_id"),
        "company_name": seed.get("company_name"),
        "stratum": stratum,
        "t0": seed.get("t0"),
        "analysis_year": max({f["year"] for f in fields if f["year"]} or {2025}),
        # 年度从字段推导，不再照抄种子目录（修复空年度表）。
        "available_years": sorted({f["year"] for f in fields if f["year"]}, reverse=True),
        "available_report_years_note": seed.get("available_report_years") or [],
        "source_snapshot_id": seed.get("source_snapshot_id"),
        "source_review_status": seed.get("source_review_status"),
        "documents": documents,
        "financial_fields": fields,
        "data_origin": "backend/cache_seed.materialized.json 物化种子（候选值，人工回页复核待完成）",
    }


def _rules_section() -> dict:
    from backend.app.schemas import RunRequest

    defaults = {
        name: field.default
        for name, field in RunRequest.model_fields.items()
        if name in {"planned_materiality", "r1_gap_threshold", "r1_strong_gap_threshold", "r1_absolute_threshold", "r2_min_gap"}
    }
    return {
        "rule_ids": ["R1"],
        "r1_version": "r1_v0.4-draft",
        "r1_status": "工程草案，待 A 成员/指导老师专业签署",
        "threshold_defaults": defaults,
        "industry_gate": "industry_gate 按案例行业口径执行；行业不适用时返回 not_applicable 而非候选",
    }


def _model_section() -> dict:
    import os

    from backend.app.provider_readiness import classify_provider_channel

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    channel = classify_provider_channel(base_url)
    # 实现指纹：提示词、工具结构和校验逻辑的源码 SHA-256，代码变化即指纹变化。
    agents_sha = _sha256_file(ROOT / "backend" / "app" / "agents.py")
    schemas_sha = _sha256_file(ROOT / "backend" / "app" / "schemas.py")
    return {
        "model_id": os.getenv("DEEPSEEK_MODEL", "qwen3.5-plus"),
        "provider_kind": channel["provider_kind"],
        "provider_label": channel["provider_label"],
        "api_key_present": bool(os.getenv("DEEPSEEK_API_KEY")),
        "api_key_value_included": False,
        "prompt_version": "agent_prompt_v3",
        "implementation_fingerprints": {
            "agents.py_sha256": agents_sha,
            "schemas.py_sha256": schemas_sha,
            "note": "提示词、角色工具模式与硬校验的实现源码指纹；任一变化须新建评估编号",
        },
        "parameters": {
            "temperature": 0.1,
            "role_max_output_tokens": dict(ROLE_MAX_OUTPUT_TOKENS),
            "request_timeout_seconds": 35,
            "thinking": THINKING_CONFIG,
        },
        "roles": ["challenge", "counter", "review"],
        "b2_calls_per_case": 1,
        "b3_calls_per_case": 3,
    }


def _rag_section() -> dict:
    qs = question_set()
    questions = qs.get("questions", []) if isinstance(qs, dict) else []
    return {
        "index": "案例隔离 SQLite + FAISS",
        "question_set_version": qs.get("version") if isinstance(qs, dict) else None,
        "question_set_review_status": qs.get("review_status") if isinstance(qs, dict) else None,
        "question_ids": [q.get("question_id") for q in questions],
        "question_count": len(questions),
        "question_set_sha256": _sha256_json(questions),
        "chunk_size": 900,
        "chunk_overlap": 120,
        "low_confidence_note_threshold": 0.50,
        "per_case_index_note": "逐案索引状态见 cases[].rag_snapshot；B3 执行时记录检索编号与快照指纹",
    }


def _rag_snapshots(cases: list[dict]) -> dict:
    """逐案 RAG 状态快照：种子案读 seed_rag 元数据，标准案查本地索引状态。"""
    from fastapi.testclient import TestClient

    from backend.app.main import app

    client = TestClient(app)
    snapshots = {}
    for case in cases:
        try:
            resp = client.get("/api/rag/status", params={"case_id": case["case_id"]})
            body = resp.json() if resp.status_code == 200 else {"http_status": resp.status_code}
            snapshots[case["case_id"]] = {
                key: body.get(key)
                for key in ("status", "chunk_count", "snapshot_id", "version", "case_id", "http_status")
                if isinstance(body, dict) and key in body
            }
        except Exception as error:  # noqa: BLE001 - 快照失败不阻断冻结，如实记录
            snapshots[case["case_id"]] = {"error": type(error).__name__}
    return snapshots


def _execution_rules_section() -> dict:
    return {
        "b1": "仅确定性计算，0 次模型调用",
        "b2": "确定性结果 + 一次单模型草稿；无 RAG、无三 Agent",
        "b3": "确定性计算 + 冻结 RAG + Challenge/Counter/Review 三调用 + 硬校验",
        "failure_policy": "结构超限、参数错误、事实闸门失败原样记失败；不自动裁剪；不把备用写成模型成功",
        "retry_policy": "默认不重试；确需重试用新 attempt 编号与新哈希，原失败记录保留",
        "change_policy": "模型、提示词、规则或输入任何变化必须新建评估编号",
        "budget_cap": {"input_tokens": 400000, "output_tokens": 30000},
        "stop_conditions": ["预算超限", "任一硬校验失败且复现", "案例来源指纹漂移", "真人叫停"],
    }


def _governance_section() -> dict:
    return {
        "evaluators": {"required": 2, "names": [None, None], "note": "姓名由真人在此登记，AI 不代填"},
        "adjudicator": {"required": 1, "name": None, "note": "总分差 >10 分且讨论不一致时裁决"},
        "blind_mapping": "B1/B2/B3 每案随机映射 X/Y/Z，密封保存，评分锁定后揭盲；分发物不含分层信息",
        "b0_first": "评分人先完成全部 B0 并锁定后才可接触机器输出；提前看到机器结果则其 B0 作废",
        "rubric": {
            "dimensions": ["证据可回查", "事实准确", "缺口完整", "专业边界", "工作可用性"],
            "scale": "每维 0—20 分，五维合计 0—100",
            "counts": ["有效引用数", "无支持事实断言数", "标准缺口数/识别缺口数", "完成用时（分钟）"],
        },
        "consents": {case["case_id"]: "pending_human_registration" for case in FIXED_CASES},
        "t1_policy": "后验 T1 或参考答案只在全部输出锁定后用于差异裁决，不提前进入模型或 B0",
        "claims_boundary": "8 案配对结果不构成通用准确率声明，不写“B3 显著优于 B0”",
        "ai_reference_scores_policy": "AI 参考评分在正式评分完成前密封，不得用于同案例校准；校准须另用非正式案例",
    }


def build_contract(output_root: Path, allow_pending_fields: bool) -> dict:
    seeds = {str(item.get("case_id")): item for item in load_seed_cases(ROOT)}
    cases = []
    for item in FIXED_CASES:
        if item["case_id"] == "STD_DEV_T0":
            snapshot = _std_case_snapshot()
        else:
            seed = seeds.get(item["case_id"])
            if seed is None:
                raise SystemExit(f"案例缺失：{item['case_id']} 不在种子目录，评估不得带缺口开跑")
            snapshot = _cninfo_case_snapshot(seed, item["stratum"])
        snapshot["case_payload_sha256"] = _sha256_json(
            {k: snapshot[k] for k in ("t0", "analysis_year", "available_years", "documents", "financial_fields")}
        )
        cases.append(snapshot)

    pending_fields = [
        {"case_id": c["case_id"], "field_id": f["field_id"]}
        for c in cases
        for f in c["financial_fields"]
        if f["field_freeze_status"].startswith("candidate")
    ]
    flagged_fields = [
        {"case_id": c["case_id"], "field_id": f["field_id"], "flags": f["review_flags"]}
        for c in cases
        for f in c["financial_fields"]
        if f.get("review_flags")
    ]
    if pending_fields and not allow_pending_fields:
        raise SystemExit(
            f"拒绝生成正式合同：仍有 {len(pending_fields)} 个字段未完成人工回页复核。"
            "先完成字段复核（见 field-review 工作底稿），或用 --allow-pending-fields 显式生成带待复核状态的合同。"
        )

    sections = {
        "meta": {
            "evaluation_id": EVALUATION_ID,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "pending_field_review_and_human_signoff" if pending_fields else "pending_human_freeze_signoff",
            "pending_field_count": len(pending_fields),
            "flagged_field_count": len(flagged_fields),
            "ai_generated_content_notice": "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。",
            "supersedes": "EVAL-20260822-COMPETITION-8CASE-V2（盲性泄露与哈希缺陷，作废；见其目录 SUPERSEDED.md）",
            "immutable": "本文件存在即拒绝覆盖；后续变更新建评估编号",
        },
        "b0_b3_definitions": B0_B3_DEFINITIONS,
        "cases": cases,
        "rules": _rules_section(),
        "model": _model_section(),
        "rag": _rag_section(),
        "execution_rules": _execution_rules_section(),
        "governance": _governance_section(),
        # 复核状态明细纳入被哈希的章节，不留在哈希覆盖之外。
        "field_review_status": {
            "note": "由 cases 章节派生；逐字段明细见下，篡改可与 cases 章节交叉验出",
            "pending_fields": pending_fields,
            "flagged_fields": flagged_fields,
        },
    }
    sections["rag"]["per_case_snapshots"] = _rag_snapshots(cases)
    integrity = {name: _sha256_json(payload) for name, payload in sections.items()}
    return {**sections, "integrity": integrity}


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 B0—B3 正式冻结合同；存在即拒绝覆盖。")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs" / "evaluation_v4",
                        help="正式目录默认 outputs/evaluation_v4；机制自测请指向临时目录。")
    parser.add_argument("--allow-pending-fields", action="store_true",
                        help="字段未完成人工复核时仍生成合同（状态如实标记为待复核）。")
    args = parser.parse_args()

    out_dir = args.output_root / EVALUATION_ID
    contract_path = out_dir / "contract.json"
    if contract_path.exists():
        raise SystemExit(f"拒绝覆盖：正式冻结合同已存在 {contract_path}")

    # 纪律约束：--allow-pending-fields 只服务机制自测目录；
    # 正式目录必须先完成全部字段人工回页复核，先复核后冻结的顺序不得豁免。
    # 该检查必须在任何目录创建动作之前，避免拒绝时留下空壳正式目录。
    formal_root = (ROOT / "outputs" / "evaluation_v4").resolve()
    if args.allow_pending_fields and args.output_root.resolve() == formal_root:
        raise SystemExit("拒绝：正式目录不允许用 --allow-pending-fields 跳过字段复核；先完成回页复核再冻结。")

    out_dir.mkdir(parents=True, exist_ok=True)

    contract = build_contract(args.output_root, args.allow_pending_fields)
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    cases = contract["cases"]
    dashboard = {
        "schema_version": "evaluation_dashboard_v1",
        "evaluation_id": EVALUATION_ID,
        "status": contract["meta"]["status"],
        "frozen_at": None,
        "model_id": contract["model"]["model_id"],
        "reviewers_required": 2,
        "cases_required": len(cases),
        "review_forms_required": len(cases) * 2,
        "review_forms_completed": 0,
        "metrics": None,
        "groups": {
            group: {"status": "not_started", "definition": definition, "completed": 0, "total": len(cases)}
            for group, definition in B0_B3_DEFINITIONS.items()
        },
        "cases": [
            {
                "case_id": case["case_id"],
                "company_name": case["company_name"],
                "stratum": case["stratum"],
                "t0": case["t0"],
                "available_years": case["available_years"],
                "source_snapshot_id": case["source_snapshot_id"],
                "groups": {group: {"status": "not_started", "definition": definition} for group, definition in B0_B3_DEFINITIONS.items()},
            }
            for case in cases
        ],
        "disputes": 0,
        "boundary": "评分仅用于竞赛效果展示，不用于训练模型或修改规则。",
    }
    dashboard_path = out_dir / "dashboard.json"
    if args.output_root == ROOT / "outputs" / "evaluation_v4":
        dashboard_path = write_evaluation_dashboard(ROOT, dashboard)
    else:
        dashboard_path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "evaluation_id": EVALUATION_ID,
        "status": contract["meta"]["status"],
        "pending_fields": contract["meta"]["pending_field_count"],
        "flagged_fields": contract["meta"]["flagged_field_count"],
        "contract": str(contract_path),
        "dashboard": str(dashboard_path),
        "cases": len(cases),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
