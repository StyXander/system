"""第一批正确性和安全边界回归测试。"""

from pathlib import Path

from backend.app.cases import _complete_r1_years, _has_three_consecutive_years
from backend.app.field_extraction import _unit
from backend.app.pipeline import load_task
from backend.app.run_store import load_run
from backend.app.supplements import create_supplement, _to_number


def test_amount_units_include_rmb_yuan_and_nonfinite_values_are_rejected() -> None:
    assert _unit("合并利润表\n单位：人民币亿元\n") == ("亿元", 100_000_000.0)
    assert _unit("合并利润表\n人民币亿元\n") == ("亿元", 100_000_000.0)
    assert _to_number("NaN") is None
    assert _to_number("Infinity") is None


def test_rejected_supplement_does_not_write_original_file(tmp_path: Path) -> None:
    record = create_supplement(
        tmp_path,
        parent_run_id="RUN-V7-REGRESSION",
        material_type="内部资料",
        authorized=False,
        desensitized=False,
        bound_rule_ids=["R1"],
        as_of_date="2026-08-08",
        note="拒绝落盘测试",
        filename="secret.txt",
        content=b"private content",
        structured_json=None,
    )

    directory = tmp_path / "backend" / "runtime" / "pytest" / "supplements" / record["supplement_id"]
    assert record["status"] == "rejected"
    assert record["content_stored"] is False
    assert (directory / "record.json").is_file()
    assert not (directory / "secret.txt").exists()


def test_invalid_task_and_run_ids_are_treated_as_not_found(tmp_path: Path) -> None:
    assert load_task(tmp_path, "../../secret") is None
    assert load_run(tmp_path, "../../secret") is None


def test_three_year_readiness_requires_complete_consecutive_years() -> None:
    rows = [
        {"year": 2025, "field_kind": "revenue"},
        {"year": 2025, "field_kind": "accounts_receivable"},
        {"year": 2024, "field_kind": "revenue"},
        {"year": 2024, "field_kind": "accounts_receivable"},
        {"year": 2022, "field_kind": "revenue"},
        {"year": 2022, "field_kind": "accounts_receivable"},
    ]
    complete = _complete_r1_years(rows)
    assert complete == [2025, 2024, 2022]
    assert _has_three_consecutive_years(complete) is False
