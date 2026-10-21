"""水资源及排放口径反例；编号不代表企业披露体系之间已建立映射。"""
import pytest

from app.connectivity_engine import calculate
from app.connectivity_metrics import metric_comparison, metric_identity, metric_qualifiers
from app.connectivity_pipeline import candidate_checks
from test_connectivity_engine import relationship
from test_connectivity_conditions_20261017 import row, run_with


@pytest.mark.parametrize("left,right,status", [
    ("年度总用水量", "年度总用水量－雨水回用", "unknown"),
    ("年度总用水量25", "年度总用水量-\n雨水回用", "unknown"),
    ("年度总用水量－雨水回用", "年度总用水量－循环水", "conflicting"),
    ("直接温室气体排放量（类别", "间接温室气体排放量（类别", "conflicting"),
    ("温室气体排放量（类别1）", "温室气体排放量（类别2）", "conflicting"),
    ("温室气体排放量（类别1+2）", "温室气体排放量（类别1）", "conflicting"),
    ("温室气体排放量（类别1）", "范围一温室气体排放量", "unknown"),
    ("温室气体排放量（类别1）", "温室气体排放量（类别", "conflicting"),
    ("范围三价值链上游温室气体排放量", "范围三价值链下游温室气体排放量", "conflicting"),
    ("Scope 3上游温室气体排放量", "Scope 3温室气体排放量", "unknown"),
])
def test_distinct_resource_qualifiers_never_formally_equal(left, right, status):
    assert metric_comparison(left, right)["status"] == status
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    rows[0].label, rows[1].label = left, right
    result = calculate(check, rows)
    assert result.conclusion_level != "formal_consistent"
    assert result.calculation["residual"] is None


@pytest.mark.parametrize("label", ["温室气体排放量（类别1+2）", "温室气体排放量（类别1+类别2）", "温室气体排放量（类别一及二）"])
def test_category_numbers_have_one_stable_identity_without_scope_mapping(label):
    qualifiers = metric_qualifiers(label)
    assert qualifiers["emission_category"] == "1+2"
    assert "emission_scope" not in qualifiers
    assert metric_identity(label)["metric_id"] == "温室气体排放量"


@pytest.mark.parametrize("label", ["年度总用水量－雨水回用", "温室气体排放量（类别2）", "范围三价值链上游温室气体排放量"])
def test_same_explicit_caliber_still_allows_fully_evidenced_equal_case(label):
    rows, check = relationship("EQ-001", ["100", "100"], ["left", "right"])
    rows[0].label = rows[1].label = label
    assert calculate(check, rows).conclusion_level == "formal_consistent"


@pytest.mark.parametrize("left,right,unit", [
    ("年度总用水量", "年度总用水量－雨水回用", "立方米"),
    ("温室气体排放量（类别1）", "温室气体排放量（类别2）", "吨二氧化碳当量"),
    ("范围三价值链上游温室气体排放量", "范围三价值链下游温室气体排放量", "吨二氧化碳当量"),
])
def test_rule_candidates_do_not_merge_distinct_calibers(left, right, unit):
    rows = [row(1, left, "100"), row(2, left, "100"), row(3, right, "100"), row(4, right, "100")]
    for item in rows:
        item.unit = unit
    found = candidate_checks(rows, "2025", run=run_with(rows))
    labels = {item.occurrence_id: item.label for item in rows}
    occurrences = [check for check in found if check.rule_id == "OCC-001"]
    assert len(occurrences) == 2
    assert all(len({labels[m.occurrence_id] for m in check.members}) == 1 for check in occurrences)


def test_segment_total_columns_are_not_multi_location_disclosures():
    """宝钢第91页实际结构：同一行并列钢铁/其他/合计列，不是同一指标的重复披露。"""
    cells, index = [], 0
    for row_index, label, values in ((2, "年度总用水量", ("129.90", "7.97", "137.87")),
                                     (5, "年度总用水量-雨水回用", ("3.15", "0", "3.15"))):
        for column_index, header, value in zip((8, 9, 10), ("2025 年 / 钢铁", "2025 年 / 其他", "2025 年 / 合计"), values):
            index += 1
            cells.append(row(index, label, value, unit="百万立方米").model_copy(update={
                "table_id": "SYN-91-T0", "row_index": row_index, "column_index": column_index,
                "column_header": header, "header_path": header.split(" / "),
                "column_role": "total" if header.endswith("合计") else "component"}))
    found = candidate_checks(cells, "2025", run=run_with(cells))
    assert not [check for check in found if check.rule_id == "OCC-001"]
    by_id = {item.occurrence_id: item.label for item in cells}
    for check in found:
        assert len({by_id[member.occurrence_id] for member in check.members}) <= 1, check.title


def test_segment_columns_in_narrative_rows_are_not_multi_location_disclosures():
    """宝钢2024实际写法：无表格坐标的同行三列“钢铁/其他/合计”也属不同口径。"""
    cells = []
    for index, (header, value) in enumerate(zip(("2024 年 / 钢铁", "2024 年 / 其他", "2024 年 / 合计"),
                                                 ("126.44", "9.23", "135.67")), 1):
        item = row(index, "年度总用水量 百万立方米", value, unit="百万立方米",
                   context="年度总用水量 百万立方米 126.44 9.23 135.67")
        cells.append(item.model_copy(update={"table_id": "", "column_header": header,
                                             "header_path": header.split(" / ")}))
    found = candidate_checks(cells, "2025", run=run_with(cells))
    assert not [check for check in found if check.rule_id == "OCC-001"]


def test_same_total_column_disclosed_twice_keeps_multi_location_candidate():
    """全组口径一致时不能因列口径修复丢掉真正的重复披露。"""
    cells = []
    for index, value in enumerate(("135.67", "135.67"), 1):
        item = row(index, "年度总用水量", value, unit="百万立方米",
                   context="年度总用水量 百万立方米 135.67 135.67")
        cells.append(item.model_copy(update={"table_id": "", "column_header": "2025 年 / 合计",
                                             "header_path": ["2025 年", "合计"]}))
    found = candidate_checks(cells, "2025", run=run_with(cells))
    assert [check for check in found if check.rule_id == "OCC-001"]
