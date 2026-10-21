"""新增单位必须从PDF坐标行进入计算，且质量与碳当量不可混算。"""
import pytest
from test_round3_extraction_conditions import extract_pages
from app.connectivity_engine import numeric_unit


@pytest.mark.parametrize("label,unit,topic,dimension", [
    ("温室气体排放量", "千克二氧化碳当量", "intensity", "co2e"),
    ("环保投入", "千克", "environment", "mass"),
    ("环保投入", "公斤", "environment", "mass"),
])
def test_pdf_line_preserves_extended_unit(monkeypatch, tmp_path, label, unit, topic, dimension):
    rows = extract_pages(monkeypatch, tmp_path, [[f"2025年{label} 42{unit}"]], topics=[topic])
    value = next(row for row in rows if row.value == "42")
    assert value.unit == unit
    assert unit in value.unit_source_quote
    assert numeric_unit(value.unit)[0] == dimension
