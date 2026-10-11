"""将八个已有公开快照并入统一案例清单，不改来源、T0 或历史验收。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.company_discovery import EXPANDED_TICKERS
from backend.app.manifest_hash import canonical_json_sha256
from backend.app.seed_catalog import load_seed_cases


def promote() -> dict:
    """只补登记事实；没有新模型验收的案例保持 pending。"""
    path = ROOT / "backend/competition_demo_cases.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    seeds = {case["ticker"]: case for case in load_seed_cases(ROOT)}
    lock = json.loads((ROOT / "backend/cache_seed.lock.json").read_text(encoding="utf-8"))
    entries = {case["case_id"]: case for case in lock["entries"]}
    ids = {case["case_id"] for case in manifest["cases"]}
    categories = {
        "600276": "医药与医疗", "300015": "医药与医疗",
        "000333": "消费、家电与科技制造", "600588": "软件与信息服务",
        "688111": "软件与信息服务", "601668": "建筑与房地产",
        "000002": "建筑与房地产", "601398": "金融",
    }
    for ticker in EXPANDED_TICKERS:
        seed = seeds[ticker]
        if seed["case_id"] in ids:
            continue
        entry = entries[seed["case_id"]]
        documents = [{key: doc.get(key) for key in (
            "report_year", "announcement_title", "disclosure_date", "source_url",
            "page_count", "byte_count", "sha256", "validation_status",
            "registered_disclosure_date", "source_date_conflict",
        ) if key in doc} for doc in seed["documents"]]
        manifest["cases"].append({
            "case_id": seed["case_id"], "ticker": ticker,
            "company_name": seed.get("company_alias") or seed["company_name"],
            "category": categories[ticker], "demo_focus": "登记资料完整分析",
            "report_years": sorted({int(doc["report_year"]) for doc in documents}, reverse=True),
            "t0": seed["t0"],
            "rule_ids": (entry.get("industry_gate") or {}).get("allowed_rules") or ["R1"],
            "industry_family": entry.get("industry_family"),
            "source_fingerprint": entry.get("source_fingerprint"),
            "rag_index_version": entry.get("rag_index_version"), "documents": documents,
            "admission_status": "pending", "admission_evidence": None,
            "historical_external_model_run": None,
            "registered_at": "2026-10-11",
            "registration_note": "由原扩展快照并入统一案例库；未新增模型成功或专业批准记录。",
        })
    assert len(manifest["cases"]) == len({case["case_id"] for case in manifest["cases"]}) == 23
    manifest["case_count"] = 23
    admitted = {case["case_id"] for case in manifest["cases"]}
    manifest["backup_candidate_case_ids"] = [case for case in manifest.get("backup_candidate_case_ids", []) if case not in admitted]
    manifest["roster_updated_at"] = "2026-10-11"
    note = "2026-10-11：案例库由15案扩为23案，统一完整分析入口；原15案冻结验收与新增8案的历史预检不混记。"
    if note not in manifest["notes"]:
        manifest["notes"].append(note)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 发布候选绑定新清单，保持评估、人工签字与历史源版本原样。
    release_path = ROOT / "backend/release_records/current_release.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release["demo"].update(case_count=23, manifest_sha256=canonical_json_sha256(manifest))
    release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = promote()
    print(json.dumps({"case_count": result["case_count"], "promoted_tickers": EXPANDED_TICKERS}))
