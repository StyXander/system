from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.public_model import PublicModelLedger, PublicModelQuotaError, QuotaConfig, build_cache_key


def test_public_model_ledger_enforces_ip_and_cache_key_scope(tmp_path: Path) -> None:
    ledger = PublicModelLedger(
        tmp_path,
        config=QuotaConfig(per_ip=1, global_window=4, max_concurrent=2, daily_runs=4),
    )
    reservation = ledger.reserve("198.51.100.7")
    with pytest.raises(PublicModelQuotaError):
        ledger.reserve("198.51.100.7")
    ledger.settle(reservation, input_tokens=12, output_tokens=8)
    key_a = build_cache_key(case_id="CASE_A", year=2026, rule_ids=["R2", "R1"], source_snapshot_id="S1", prompt_version="P1", model_id="deepseek-v4-flash", supplement_hash="A")
    key_b = build_cache_key(case_id="CASE_A", year=2026, rule_ids=["R1", "R2"], source_snapshot_id="S1", prompt_version="P1", model_id="deepseek-v4-flash", supplement_hash="B")
    assert key_a != key_b
    ledger.put_cache(key_a, {"run_id": "RUN-1"})
    assert ledger.get_cache(key_a) == {"run_id": "RUN-1"}


def test_demo_readonly_contracts_are_available() -> None:
    client = TestClient(app)
    evaluation = client.get("/api/evaluations/current")
    assert evaluation.status_code == 200
    assert evaluation.json()["evaluation_id"] == "EVAL-20260811-COMPETITION-8CASE-V1"
    samples = client.get("/api/supplement-samples")
    assert samples.status_code == 200
    assert {item["sample_id"] for item in samples.json()["samples"]} == {"aging", "receipts"}


def test_summary_case_directory_is_compact() -> None:
    client = TestClient(app)
    response = client.get("/api/cases?summary=true")
    assert response.status_code == 200
    assert len(response.content) < 100_000
    assert all(set(item) >= {"case_id", "company_name", "available_years"} for item in response.json()["cases"])
