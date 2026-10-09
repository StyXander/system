"""把当前真实取数与日期更正整理成可复核材料，不替人批准或填写成绩。"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.seed_catalog import load_seed_cases

NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"


def main():
    out = ROOT / "决赛准备/整改_2026-10-09"
    out.mkdir(parents=True, exist_ok=True)
    cases = load_seed_cases(ROOT)
    rows = []
    for case in cases:
        for row in case.get("financial_fields", []):
            correction = row.get("engineering_correction")
            if not correction:
                continue
            old = correction["previous_row"]
            rows.append({"企业": case["company_name"], "案例": case["case_id"], "字段": row["field_kind"], "年度": row["year"], "原值_元": old.get("value"), "新候选_元": row.get("value"), "金额改变": old.get("value") != row.get("value"), "原PDF页": old.get("pdf_page"), "新PDF页": row.get("pdf_page"), "原表单位": row.get("source_unit"), "财务口径": row.get("field_basis"), "列身份": row.get("column_identity"), "来源哈希": row.get("file_sha256"), "原表行": row.get("raw_excerpt"), "专业采用": "待真人确认", "AI声明": NOTICE})
    with (out / "07_逐字段工程更正待确认.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    records = json.loads((ROOT / "backend/source_date_verifications_20261009.json").read_text(encoding="utf-8"))["verifications"]
    with (out / "08_官方公告日期核验.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        names = ["case_id", "document_id", "announcement_id", "registered_disclosure_date", "official_announcement_date", "official_source_url", "document_sha256"]
        writer = csv.DictWriter(fh, fieldnames=names)
        writer.writeheader()
        writer.writerows({name: row.get(name) for name in names} for row in records)
    proposals = []
    for case in cases:
        verified = [r for r in records if r["case_id"] == case["case_id"]]
        if not verified:
            continue
        latest_year = max(int(d.get("report_year") or 0) for d in case["documents"])
        latest_docs = [d for d in case["documents"] if int(d.get("report_year") or 0) == latest_year]
        latest_verified = [r for r in verified if r["document_id"] in {d["document_id"] for d in latest_docs}]
        proposals.append({"existing_case_id": case["case_id"], "existing_frozen_t0": case.get("t0"), "latest_report_year": latest_year, "proposed_new_snapshot_cutoff": max(r["official_announcement_date"] for r in latest_verified) if latest_verified else None, "status": "pending_human_adoption" if latest_verified else "pending_official_source_verification", "registered_or_frozen": False, "adopted_by": None, "adopted_at": None, "evidence_document_ids": [r["document_id"] for r in latest_verified]})
    (out / "09_新截止日快照采用建议_未登记.json").write_text(json.dumps({"status": "proposal_only", "existing_manifest_unchanged": True, "proposals": proposals, "ai_generated_content_notice": NOTICE}, ensure_ascii=False, indent=2), encoding="utf-8")
    extraction = json.loads((ROOT / "outputs/决赛整改_2026-10-09/陌生企业/零模型字段与计算/实际字段抽取.json").read_text(encoding="utf-8"))
    with (out / "10_陌生企业真实字段接口样本.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        names = ["evidence_id", "field_kind", "year", "value", "unit", "source_unit", "field_basis", "document_id", "pdf_page", "column_identity", "source_review_status"]
        writer = csv.DictWriter(fh, fieldnames=names)
        writer.writeheader()
        writer.writerows({name: row.get(name) for name in names} for row in extraction["rows"])
    print(json.dumps({"reextracted_rows": len(rows), "numeric_values_changed": sum(r["金额改变"] for r in rows), "official_date_records": len(records), "dates_changed": sum(r["registered_disclosure_date"] != r["official_announcement_date"] for r in records), "cutoff_proposals": len(proposals)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
