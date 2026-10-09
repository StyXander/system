"""按公告编号核对主清单与扩展案例日期，零模型、不下载原件。"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from backend.app.company_discovery import EXPANDED_TICKERS, _client, directory


def main():
    out = ROOT / "outputs/决赛整改_2026-10-09"
    seed = json.loads((ROOT / "backend/cache_seed.materialized.json").read_text(encoding="utf-8"))["cases"]
    manifest = json.loads((ROOT / "backend/competition_demo_cases.json").read_text(encoding="utf-8"))
    main_ids = {c["case_id"] for c in manifest["cases"]}
    companies, provenance = directory(ROOT)
    by_code = {c["ticker"]: c for c in companies}
    verifications, queries = [], []
    for case in seed:
        if case["case_id"] not in main_ids and case["ticker"] not in EXPANDED_TICKERS:
            continue
        for doc in case["documents"]:
            client = _client()
            client.set_operation_deadline(18)
            started = time.monotonic()
            record = {"case_id": case["case_id"], "document_id": doc["document_id"], "report_year": doc["report_year"], "registered_disclosure_date": doc["disclosure_date"], "source_url": doc["source_url"]}
            try:
                candidates, status = client.search_annual_reports_detailed(by_code[case["ticker"]], int(doc["report_year"]))
                record.update({"status": "query_complete" if not status.get("truncated") else "query_partial", "candidates": candidates, "query_status": status})
                announcement_id = re.search(r"/(\d+)\.PDF$", doc["source_url"], re.I)[1]
                matched = next((c for c in candidates if c.get("announcement_id") == announcement_id), None)
                if matched and matched.get("announcement_date"):
                    verifications.append({"case_id": case["case_id"], "document_id": doc["document_id"], "document_sha256": doc["sha256"].lower(), "announcement_id": announcement_id, "registered_disclosure_date": doc["disclosure_date"], "official_announcement_date": matched["announcement_date"], "official_source_url": matched["source_url"], "raw_announcement": matched.get("raw"), "verified_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), "status": "matched_same_announcement"})
                print(case["ticker"], doc["report_year"], doc["disclosure_date"], matched["announcement_date"] if matched else "not_matched")
            except Exception as error:
                record.update({"status": "query_failed", "failure_code": getattr(error, "code", type(error).__name__), "message": str(error)})
                print(case["ticker"], doc["report_year"], record["failure_code"])
            finally:
                client.client.close()
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            queries.append(record)
            (out / "主清单与扩展原公告日期查询.json").write_text(json.dumps({"directory": provenance, "queries": queries}, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(.2)
    payload = {"schema_version": "official_announcement_date_verifications_v1", "verifications": verifications, "human_t0_adoption": "pending", "ai_generated_content_notice": "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"}
    (ROOT / "backend/source_date_verifications_20261009.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("matched official announcements", len(verifications), "/", len(queries))


if __name__ == "__main__":
    main()
