"""登记真实PDF重抽候选的工程更正；不更改冻结种子、T0或真人签字。"""
import json
import sys
import hashlib
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.source_corrections import row_fingerprint
from backend.app.field_extraction import FIELD_EXTRACTION_VERSION


def main():
    records = json.loads((ROOT / "outputs/决赛整改_2026-10-09/抽取修改后_v4.json").read_text(encoding="utf-8"))
    entries = []
    for record in records:
        for original in record["old"]:
            if original.get("human_review", {}).get("decision"):
                raise ValueError("不得自动覆盖真人意见")
            replacement = deepcopy(original)
            candidate = record["candidate"]
            replacement["candidate_quality_issues"] = []
            replacement["extractor_version"] = FIELD_EXTRACTION_VERSION
            if candidate:
                replacement.update({"value": candidate["value"], "pdf_page": candidate["page"], "source_unit": candidate["source_unit"] or "unknown", "unit": "元", "field_basis": "net" if record["field_kind"] == "accounts_receivable" else "reported", "raw_excerpt": candidate["raw_excerpt"], "locator": candidate["locator"], "column_identity": candidate["column_identity"], "period_labels": candidate["period_labels"], "adopted_cell_index": candidate["adopted_cell_index"], "cell_values": candidate["cell_values"], "row_bbox": candidate.get("row_bbox"), "amount_bbox": candidate.get("amount_bbox"), "statement_title": candidate.get("statement_title"), "extraction_method": "pdf_text_heuristic_candidate", "source_review_status": "auto_extracted_pending_human_page_confirmation", "candidate": candidate})
            else:
                replacement["source_conflicts"] = ["本轮重新抽取未形成对应科目候选，旧值保留回查，不参与计算。"]
            entries.append({"case_id": record["case_id"], "evidence_id": original["evidence_id"], "previous_row_sha256": row_fingerprint(original), "document_sha256": record["document_sha256"], "replacement": replacement})
    target = ROOT / "backend/source_corrections_20261009.json"
    if target.is_file():
        content = target.read_bytes()
        archive = ROOT / "outputs/决赛整改_2026-10-09" / ("更正记录_" + hashlib.sha256(content).hexdigest()[:12] + ".json")
        if not archive.exists():
            archive.write_bytes(content)
    payload = {"schema_version": "public_engineering_corrections_v1", "revision_id": "SOURCE-CORRECTION-20261009-R3", "extractor_version": FIELD_EXTRACTION_VERSION, "source": "registered_pdf_reextraction", "professional_review": "pending", "frozen_seed_unchanged": True, "frozen_t0_unchanged": True, "entries": entries, "ai_generated_content_notice": "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"}
    (ROOT / "backend/source_corrections_20261009.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("engineering correction entries:", len(entries))


if __name__ == "__main__":
    main()
