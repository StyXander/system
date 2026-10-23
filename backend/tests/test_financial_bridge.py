"""财务穿透层：合成样本只验证抽取与关系门槛，不冒充任何企业事实。"""
from __future__ import annotations

from backend.app.connectivity_financial_bridge import INDUSTRY_PROFILES, build, extract_claims, extract_financial_nodes
from backend.app.connectivity_schemas import ReportDocument


def _docs():
    return [
        ReportDocument(document_id="TEST_AR", case_id="TEST-2025", company_id="TEST", company="测试钢铁",
                       report_type="AR", period="2025", source_url="https://example.invalid/ar.pdf",
                       file_sha256="a" * 64, pages=10),
        ReportDocument(document_id="TEST_ESG", case_id="TEST-2025", company_id="TEST", company="测试钢铁",
                       report_type="ESG", period="2025", source_url="https://example.invalid/esg.pdf",
                       file_sha256="b" * 64, pages=10),
    ]


def _pages():
    esg_text = "2025年，公司各基地共计开展87项节能改造与低碳项目，总投入超32亿元，节能总量达到25.85万吨标煤，减少碳排放64.5万吨。"
    esg_env = "报告期内，公司在环保领域的总投入达到103.41亿元，资本化项目投入为3.66亿元。"
    esg = [{"page": 34, "text": esg_text, "blocks": [esg_text], "tables": []},
           {"page": 40, "text": esg_env, "blocks": [esg_env], "tables": []}]
    ar_text = "单位：元\n在建工程\n营业成本\n购建固定资产、无形资产和其他长期资产支付的现金 18,507,325,935.15"
    project_table = [
        ["项目名称", "预算数", "期初余额", "本期增加金额", "期末余额"],
        ["高端取向硅钢绿色制造结构优化工程", "3,289,215,370.00", "237,701,113.45", "1,167,824,269.11", "1,405,525,382.56"],
    ]
    cash_table = [
        ["项目", "2025年度", "2024年度"],
        ["购建固定资产、无形资产和其他长期资产支付的现金", "18,507,325,935.15", "19,336,433,651.03"],
        ["营业成本", "29,452,277,6086.63", "30,454,636,0573.04"],
    ]
    env_table = [
        ["项目", "期末余额"],
        ["梅钢焦炉项目环保搬迁费", "551,728,350.16"],
    ]
    ar = [
        {"page": 100, "text": ar_text, "blocks": [ar_text], "tables": [cash_table]},
        {"page": 154, "text": "单位：元\n在建工程\n高端取向硅钢绿色制造结构优化工程 3,289,215,370.00 1,167,824,269.11",
         "blocks": ["单位：元", "在建工程"], "tables": [project_table]},
        {"page": 162, "text": "单位：元\n项目 期末余额\n梅钢焦炉项目环保搬迁费 551,728,350.16",
         "blocks": ["单位：元"], "tables": [env_table]},
    ]
    return {"TEST_ESG": esg, "TEST_AR": ar}


def test_claim_and_financial_node_extraction():
    docs = _docs()
    pages = _pages()
    claims = extract_claims(pages["TEST_ESG"], docs[1], INDUSTRY_PROFILES["steel"])
    assert claims and all(claim["claim_kind"] == "performance" for claim in claims)
    assert any(claim["pdf_page"] == 34 for claim in claims)
    nodes = extract_financial_nodes(pages["TEST_AR"], docs[0], INDUSTRY_PROFILES["steel"])
    roles = {node["industry_role"] for node in nodes}
    assert "green_project" in roles and "capex_cash" in roles
    assert all(node["page_verified"] for node in nodes)


def test_numeric_proximity_is_rejected_when_scope_and_definition_conflict():
    result = build(None, documents=_docs(), pages=_pages(), industry="steel")
    contradictions = [edge for edge in result["edges"] if edge["relation_type"] == "CONTRADICTED"]
    assert contradictions, result["stats"]
    edge = contradictions[0]
    assert edge["definition_compatible"] is False
    assert edge["boundary_compatible"] is False
    assert edge["missing_conditions"]
    assert edge["numeric_gap"] is not None and edge["numeric_gap"] < 0.05


def test_semantic_link_keeps_gap_instead_of_upgrading():
    result = build(None, documents=_docs(), pages=_pages(), industry="steel")
    semantic = [edge for edge in result["edges"] if edge["relation_type"] == "SEMANTIC_ASSOCIATION"]
    assert semantic
    assert all(edge["missing_conditions"] for edge in semantic)
    assert all(edge["status"] in {"limited_support", "pending_evidence"} for edge in semantic)


def test_old_documents_without_financial_fields_load():
    from backend.app.connectivity_schemas import ConnectivityRun
    docs = _docs()
    run = ConnectivityRun(run_id="RUN-OLD", company="测试钢铁", period="2025", documents=docs)
    assert run.financial_claims == []
    assert run.impact_graph == {}
    assert run.evidence_plan == {}
