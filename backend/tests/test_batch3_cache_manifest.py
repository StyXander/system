"""第三批热缓存白名单与锁定清单验收。"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cache_seed_and_lock_manifest_cover_exactly_fifty_traceable_companies() -> None:
    seed = json.loads((ROOT / "backend" / "cache_seed.example.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "backend" / "cache_seed.lock.json").read_text(encoding="utf-8"))
    seed_tickers = {str(item["ticker"]).zfill(6) for item in seed["companies"]}
    entries = lock["entries"]

    assert len(seed["companies"]) == 50
    assert len(seed_tickers) == 50
    assert lock["company_count"] == 50
    assert lock["ready_count"] == 50
    assert lock["requested_years"] == [2025, 2024, 2023]
    assert {entry["ticker"] for entry in entries} == seed_tickers
    for entry in entries:
        assert entry["cache_status"] == "ready"
        assert entry["report_years"] == [2025, 2024, 2023]
        assert entry["rag"]["status"] == "ready"
        assert entry["source_fingerprint"] == entry["rag"]["source_fingerprint"]
        assert len(entry["documents"]) == 3
        for document in entry["documents"]:
            assert document["source_url"].startswith("https://static.cninfo.com.cn/")
            assert re.fullmatch(r"[0-9A-F]{64}", document["sha256"])
            assert int(document["page_count"]) > 0
            assert document["validation_status"] == "passed"
        assert "storage_relpath" not in entry
