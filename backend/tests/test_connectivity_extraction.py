"""定位器曾发生的单位和断开表头错误，以独立合成布局重现。"""
from app.connectivity_extraction import _unit, _extract_tables, _join_indicator_fragments, _coordinate_year, _number_box, NUMBER
from app.connectivity_schemas import ReportDocument


def test_currency_word_does_not_create_people_unit():
    assert _unit("金额为人民币，具体计量尺度另见各表") == ""
    assert _unit("年度总用水量 百万立方米") == "百万立方米"
    assert _unit("报告期内投入环保资金（单位：万元）") == "万元"


def test_split_header_needs_matching_width_columns_and_proximity():
    document = ReportDocument(document_id="SYN", case_id="SYN-PAIR", company_id="SYN", company="合成企业",
        report_type="ESG", period="2025", source_url="https://example.invalid/synthetic")
    header = {"text": "2025 年", "bbox": [100, 0, 200, 20], "table_bbox": [0, 0, 200, 20]}
    table = {"bbox": [0, 30, 200, 50], "data": [["环保投入", "亿元", "20"]],
        "cells": [[[0, 30, 60, 50], [60, 30, 100, 50], [100, 30, 200, 50]]], "headers": []}
    page = {"page": 1, "lines": [], "tables": [
        {"bbox": [0, 0, 200, 20], "data": [["项目", "单位", "2025 年"]], "cells": [], "headers": [header]}, table]}
    row = _extract_tables(page, document, ["environment"])[0]
    assert (row.value, row.unit, row.year) == ("20", "亿元", "2025")
    table["bbox"] = [0, 100, 200, 120]
    table["cells"][0][2] = [100, 100, 200, 120]
    assert _extract_tables(page, document, ["environment"])[0].year == ""


def test_unit_within_label_is_used_without_assuming_year():
    document = ReportDocument(document_id="SYN", case_id="SYN-PAIR", company_id="SYN", company="合成企业",
        report_type="AR", period="2025", source_url="https://example.invalid/synthetic")
    page = {"page": 1, "lines": [], "tables": [{"bbox": [0, 0, 200, 20],
        "data": [["报告期内投入环保资金（单位：万元）", "80"]],
        "cells": [[[0, 0, 100, 20], [100, 0, 200, 20]]], "headers": []}]}
    row = _extract_tables(page, document, ["environment"])[0]
    assert row.unit == "万元"
    assert row.year == ""
    page["tables"][0]["data"][0][0] = "研发投入金额（元）"
    research_row = _extract_tables(page, document, ["research"])[0]
    assert research_row.unit == "元"


def test_fragmented_intensity_keeps_original_numeric_coordinates_and_missing_columns():
    def line(text,bounds,spans=None,side=0):
        return {"text":text,"bbox":bounds,"spans":spans or [(bounds,text)],"side":side}
    headers = line("2023 年 2024 年 2025 年",[100,0,350,15],
        [([100,0,140,15],"2023 年"),([200,0,240,15],"2024 年"),([300,0,340,15],"2025 年")])
    first = line("能源 兆瓦时/",[0,30,90,45])
    numeric = line("8.3 / 9.1",[110,35,330,50],
        [([110,35,130,50],"8.3"),([210,35,220,50],"/"),([310,35,330,50],"9.1")])
    suffix = line("强度比 吨粗钢",[0,43,90,58])
    source = [headers,first,numeric,suffix]
    joined = _join_indicator_fragments(source)
    assert joined[1]["text"] == "能源强度比 兆瓦时/吨粗钢 8.3 / 9.1"
    match = list(NUMBER.finditer(joined[1]["text"]))[-1]
    bounds = _number_box(joined[1],match)
    assert bounds == [310,35,330,50]
    assert _coordinate_year(joined,joined[1],bounds)[0] == "2025"
    assert source[1]["text"] == "能源 兆瓦时/"
    suffix["side"] = 1
    assert _join_indicator_fragments(source)[1]["text"] == first["text"]


def test_coordinate_year_does_not_use_prose_or_other_column():
    line = {"text":"能源强度 9.1","bbox":[0,30,100,45],"spans":[],"side":0}
    paragraph = {"text":"2023年开展建设，2025年投入运行","bbox":[0,0,100,15],"spans":[],"side":0}
    assert _coordinate_year([paragraph,line],line,[80,30,100,45]) == ("","")
