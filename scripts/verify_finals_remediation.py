"""当前实例真实HTTP验收，零模型预检与来源时点核对，不填写人工意见。"""
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def main():
    out = ROOT / "outputs/决赛整改_2026-10-09"
    base = os.getenv("AUDITTRACE_VERIFY_URL", "http://127.0.0.1:8026")
    records = []
    with httpx.Client(base_url=base, trust_env=False, timeout=40) as client:
        for endpoint in ("/api/health", "/api/status", "/api/demo/bootstrap"):
            response = client.get(endpoint)
            response.raise_for_status()
            (out / (endpoint.rsplit("/", 1)[1] + "_当前.json")).write_text(json.dumps(response.json(), ensure_ascii=False, indent=2), encoding="utf-8")
        for ticker in ("600276", "000333", "600588", "300015", "601668", "000002", "601398", "688111"):
            started = time.monotonic()
            response = client.post(f"/api/demo/expanded-cases/{ticker}/preview")
            response.raise_for_status()
            data = response.json()
            analysis = data["result"]["analysis"]
            assert analysis["model_check"]["provider_call_count"] == 0
            assert data["request"]["analysis_mode"] == "snapshot_preview"
            records.append({"ticker": ticker, "http_status": response.status_code, "elapsed_seconds": round(time.monotonic() - started, 3), "payload": data})
            print(ticker, [(r["rule_id"], r["status"], r["metrics"].get("growth_gap")) for r in analysis["rule_results"]], "calls=0", "analysis_year=" + str(analysis["context"].get("current_year")))
        (out / "八案整改后真实预检.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        for cutoff in ("2026-03-30", "2026-10-09"):
            response = client.get("/api/companies/000333/reports", params={"year": 2025, "source_cutoff_date": cutoff})
            (out / ("美的公告截止日_" + cutoff + ".json")).write_text(json.dumps({"http_status": response.status_code, "payload": response.json()}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("metadata", cutoff, response.status_code, response.json().get("status", response.json().get("detail")))
    return records


if __name__ == "__main__":
    main()
