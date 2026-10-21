"""跨行人数倍率与当前数字限定语；真实缺陷结构以离线原文布局复现。"""
import pytest

from app import connectivity_extraction as extraction
from test_round3_extraction_conditions import extract_pages, line


@pytest.mark.parametrize("word,unit", [("万名", "万人"), ("名", "人"), ("万人", "万人"), ("人", "人")])
def test_immediate_person_unit_normalizes_without_losing_scale(monkeypatch, tmp_path, word, unit):
    rows = extract_pages(monkeypatch, tmp_path, [[f"2025年研发人员数量2.3{word}。"]], topics=["research"])
    row = next(row for row in rows if row.value == "2.3")
    assert row.unit == unit and row.unit_status == "explicit"
    assert f"2.3{word}" in row.unit_source_quote
    assert row.unit_source_quote in row.context


def test_observed_midea_split_person_unit_does_not_borrow_yuan_or_percent(monkeypatch, tmp_path):
    first = "亿元，2025年研发投入为178亿元，同比增幅9.6%。截至2025年底，在全球拥有研发人员超过2.3 万"
    second = "名，占非生产人员比例超过50%。美的在未来三年还将投入超过600亿元。"
    rows = extract_pages(monkeypatch, tmp_path, [[line(first, [56, 310, 539, 322]),
        line(second, [56, 334, 539, 345])]], topics=["research"])
    person = next(row for row in rows if row.value == "2.3")
    assert person.unit == "万人" and person.unit_status == "explicit"
    assert person.unit_source == "同栏紧接换行单位"
    assert person.unit_source_quote == "2.3 万\n名"
    assert person.unit_source_quote in person.context
    assert person.value_qualifier == "lower_bound"
    amount = next(row for row in rows if row.value == "178")
    percent = next(row for row in rows if row.value == "9.6")
    assert amount.unit == "亿元" and percent.unit == "%"
    assert amount.value_qualifier == percent.value_qualifier == "unspecified"


@pytest.mark.parametrize("next_line", [
    line("名，占研发人员比例。", [56, 334, 539, 345], side=1),
    line("名，占研发人员比例。", [600, 334, 700, 345]),
    line("名，占研发人员比例。", [56, 400, 539, 412]),
    line("名称为研发中心。", [56, 334, 539, 345]),
])
def test_split_unit_does_not_cross_column_gap_or_word_boundary(next_line):
    current = line("2025年研发人员超过2.3 万", [56, 310, 539, 322])
    match = next(match for match in extraction.NUMBER.finditer(current["text"]) if match.group() == "2.3")
    assert extraction._number_unit([current, next_line], 0, match) == ("", "", "")


def test_split_unit_does_not_skip_intervening_line():
    current = line("2025年研发人员超过2.3 万", [56, 310, 539, 322])
    match = next(match for match in extraction.NUMBER.finditer(current["text"]) if match.group() == "2.3")
    assert extraction._number_unit([current, line("其他说明", [56, 334, 539, 345]),
        line("名。", [56, 350, 539, 362])], 0, match) == ("", "", "")


@pytest.mark.parametrize("prefix,expected", [
    ("超过", "lower_bound"), ("至少", "lower_bound"), ("不少于", "lower_bound"),
    ("不低于", "lower_bound"), ("逾", "lower_bound"),
    ("不超过", "upper_bound"), ("不高于", "upper_bound"), ("不大于", "upper_bound"),
    ("最多", "upper_bound"), ("少于", "upper_bound"),
    ("约", "approximate"), ("大约", "approximate"), ("约为", "approximate"),
    ("恰为", "exact"), ("精确为", "exact"), ("不等于", "unspecified"),
])
def test_qualifier_uses_current_numeric_prefix(prefix, expected):
    text = f"研发人员{prefix} 2.3万名"
    match = next(extraction.NUMBER.finditer(text))
    assert extraction._value_qualifier(text, match) == expected


def test_qualifier_does_not_leak_from_another_number_or_nonadjacent_phrase():
    text = "研发投入约178亿元，研发人员数量23926名，占比12.05%"
    matches = list(extraction.NUMBER.finditer(text))
    assert [extraction._value_qualifier(text, match) for match in matches] == ["approximate", "unspecified", "unspecified"]
    text = "研发人员至少包括23926名"
    assert extraction._value_qualifier(text, next(extraction.NUMBER.finditer(text))) == "unspecified"


def test_name_character_inside_name_label_is_not_a_person_unit():
    assert extraction._unit("研发项目名称") == ""
    assert extraction._unit_from_text("单位：万名") == "万人"
    assert extraction._unit_from_text("单位：名") == "人"
