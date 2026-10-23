"""跨年比较与同业对标：缺口显式、口径严格配对、无授权不生成排名。"""
from __future__ import annotations

from backend.app.connectivity_peer_benchmark import load_registry, peer_benchmark
from backend.app.connectivity_schemas import ConnectivityRun, ReportDocument
from backend.app.connectivity_temporal import compare_periods, temporal_status
from backend.app.connectivity_tool_registry import ToolRequest, execute_tool


def _context():
    """合成同口径样本显式声明资格，缺省身份不再默认为可比。"""
    return {"company": "本企业", "period": "2025", "industry": "steel", "region": "中国",
            "scope": "集团合并", "metric_definition": "年度环保投入总额", "denominator": "不适用（金额）",
            "comparable_range": "报告期全年", "source_verified": True, "document_id": "SYN-OWN", "pdf_page": 1}


def _qualify(registry):
    for sample in registry["samples"]:
        sample.update({**_context(), **sample, "source_verified": True,
                       "document_id": "SYN-" + sample["company"], "pdf_page": 1})
    return registry


def _doc(document_id: str, report_type: str, period: str):
    return ReportDocument(document_id=document_id, case_id="CASE-2025", company_id="CO",
                          company="测试钢铁", report_type=report_type, period=period,
                          source_url=f"https://example.invalid/{document_id}.pdf",
                          file_sha256="a" * 64, pages=10)


def test_temporal_status_requires_two_periods_of_same_company():
    single = ConnectivityRun(run_id="RUN-1", company="测试钢铁", period="2025",
                             documents=[_doc("AR-2025", "AR", "2025")])
    status = temporal_status(single)
    assert status["available"] is False
    assert "未登记同企业其他年度报告" in status["reason"]
    two = ConnectivityRun(run_id="RUN-2", company="测试钢铁", period="2025",
                          documents=[_doc("AR-2025", "AR", "2025"), _doc("AR-2024", "AR", "2024")])
    assert temporal_status(two)["registered_eligible"] is True
    assert temporal_status(two)["available"] is False  # 仅登记不能冒充原件核验成功。
    mixed = ConnectivityRun(run_id="RUN-3", company="测试钢铁", period="2025",
                            documents=[_doc("AR-A", "AR", "2025"), _doc("AR-B", "AR", "2024")])
    mixed.documents[1].company = "另一家钢铁"
    status = temporal_status(mixed)
    assert status["available"] is False


def test_compare_periods_strict_identity_units_and_pages():
    current = {"label": "环保投入", "value": "12.50", "unit": "亿元",
               "document_id": "AR-2025", "pdf_page": 40, "period": "2025"}
    prior = {"label": "环保投入", "value": "10.00", "unit": "亿元",
             "document_id": "AR-2024", "pdf_page": 38, "period": "2024"}
    current = {**_context(), **current}
    prior = {**_context(), **prior}
    result = compare_periods(current, prior)
    assert result["available"] is True
    assert result["difference"] == "2.50"
    assert result["percent_change"] == "25.0000%"
    assert result["direction"] == "上升"
    assert result["current"]["pdf_page"] == 40 and result["prior"]["pdf_page"] == 38
    # 无页码：不作为证据。
    no_page = compare_periods({**current, "pdf_page": None}, prior)
    assert no_page["available"] is False and "pdf_page" in no_page["reason"]
    # 口径不同：拒绝。
    mismatch = compare_periods(current, {**prior, "label": "研发投入"})
    assert mismatch["available"] is False and "metric_identity" in mismatch["reason"]
    # 单位不同：拒绝换算。
    units = compare_periods(current, {**prior, "unit": "万元"})
    assert units["available"] is False and "单位不一致" in units["reason"]


def test_peer_benchmark_refuses_empty_registry():
    result = peer_benchmark("环保投入", "12.50", "亿元", registry={"samples": [], "authorized": False})
    assert result["available"] is False
    assert "未登记或未获授权" in result["reason"]


def test_peer_benchmark_needs_identity_and_three_samples():
    registry = {"authorized": True, "samples": [
        {"company": "甲钢", "label": "环保投入", "value": "10", "unit": "亿元",
         "period": "2025", "source": "甲钢2025年报p40"},
        {"company": "乙钢", "label": "环保投入", "value": "15", "unit": "亿元",
         "period": "2025", "source": "乙钢2025年报p33"},
    ]}
    _qualify(registry)
    result = peer_benchmark("环保投入", "12.50", "亿元", registry=registry, context=_context())
    assert result["available"] is False
    assert result["comparable_samples"] == 2 and "不足3个" in result["reason"]
    # 单位不同的样本不计入可比集合。
    registry["samples"].append({"company": "丙钢", "label": "环保投入", "value": "20",
                                "unit": "万元", "period": "2025", "source": "丙钢2025年报p12"})
    _qualify(registry)
    result = peer_benchmark("环保投入", "12.50", "亿元", registry=registry, context=_context())
    assert result["available"] is False and result["comparable_samples"] == 2


def test_peer_benchmark_ranks_only_matching_scope():
    registry = {"authorized": True, "samples": [
        {"company": "甲钢", "label": "环保投入", "value": "10", "unit": "亿元",
         "period": "2025", "source": "甲钢2025年报p40"},
        {"company": "乙钢", "label": "环保投入", "value": "15", "unit": "亿元",
         "period": "2025", "source": "乙钢2025年报p33"},
        {"company": "丙钢", "label": "环保投入", "value": "20", "unit": "亿元",
         "period": "2025", "source": "丙钢2025年报p12"},
    ]}
    _qualify(registry)
    result = peer_benchmark("环保投入", "12.50", "亿元", registry=registry, context=_context())
    assert result["available"] is True
    assert result["rank"] == 2 and result["sample_count"] == 3
    assert all(sample["source"] for sample in result["samples"])


def test_load_registry_drops_entries_without_source_or_period():
    registry = load_registry()
    assert registry["samples"] == []
    assert registry["authorized"] is False


def test_tool_registry_reports_temporal_and_peer_gaps():
    run = ConnectivityRun(run_id="RUN-1", company="测试钢铁", period="2025",
                          documents=[_doc("AR-2025", "AR", "2025")])
    annual = execute_tool(None, run, ToolRequest("lookup_annual_comparison", {"company": "测试钢铁"}))
    assert annual["status"] == "gap"
    assert "未登记同企业其他年度报告" in annual["reason"]
    peer = execute_tool(None, run, ToolRequest("lookup_peer_sample", {}))
    assert peer["status"] == "gap"
    assert "未登记授权" in peer["reason"]
