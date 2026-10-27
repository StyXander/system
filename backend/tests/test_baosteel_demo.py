"""Contract tests for the deterministic Baosteel demo. Production never reads these fixtures."""
from decimal import Decimal
from pathlib import Path

from backend.app.connectivity_project_demo import reconcile_construction, load_demo_config, _table_amount


def test_reconciliation_matches_real_example_without_ai():
    values = {
        "opening": "240,078,904.49",
        "increase": "847,336,295.51",
        "to_fixed": "1,087,415,200.00",
        "to_long_term": "0.00",
        "other_decrease": "0.00",
        "closing": "0.00",
    }
    result = reconcile_construction(values)
    assert result["status"] == "balanced"
    assert Decimal(result["difference"]) == 0


def test_missing_or_dash_must_not_become_zero():
    values = {
        "opening": "240,078,904.49",
        "increase": "847,336,295.51",
        "to_fixed": "1,087,415,200.00",
        "to_long_term": "—",
        "other_decrease": "0.00",
        "closing": "0.00",
    }
    result = reconcile_construction(values)
    assert result["status"] == "insufficient_fields"
    assert "to_long_term" in result["missing"]


def test_reconciliation_does_not_hide_a_difference():
    values = {"opening": "100.00", "increase": "30.00", "to_fixed": "20.00",
              "to_long_term": "0.00", "other_decrease": "0.00", "closing": "109.00"}
    result = reconcile_construction(values)
    assert result["status"] == "difference"
    assert Decimal(result["difference"]) == 1


def test_demo_config_contains_hints_not_prefilled_conclusions():
    root = Path(__file__).resolve().parents[2]
    cfg = load_demo_config(root)
    assert cfg["company_id"] == "600019"
    assert set(cfg["document_ids"]) == {"BAOSTEEL_AR_2025", "BAOSTEEL_ESG_2025"}
    assert "verified_amounts" not in cfg
    assert "ai_conclusion" not in cfg


def test_actual_pdf_cell_representation_reassembles_decimals():
    # Actual PyMuPDF table.extract format for BaoSteel 2025, PDF 154.
    assert _table_amount("1 326 600 000 00\n, , , .") == Decimal("1326600000.00")
    assert _table_amount("240 078 904 49\n, , .") == Decimal("240078904.49")
    assert _table_amount("847 336 295 51\n, , .") == Decimal("847336295.51")
    assert _table_amount("1 087 415 200 00\n, , , .") == Decimal("1087415200.00")
    assert _table_amount("-") is None
