"""第六批行业专用预筛与状态边界回归。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from starlette.requests import Request
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.cases import _case_dir, _runtime_base, get_case
from backend.app.field_extraction import FIELD_CONFIG, _find_page_candidate
from backend.app.industry_gate import evaluate_industry_gate
from backend.app.industry_rules import build_industry_prescreen


def _gate(name: str, ticker: str = "600000") -> dict:
    return evaluate_industry_gate(
        company={"ticker": ticker, "company_name": name, "source_mode": "cninfo_official"},
        case={"case_id": "B6-CASE", "ticker": ticker, "company_name": name},
        rule_ids=["R1", "R2"],
    )


def _source(tmp_path: Path, kind: str, year: int, value: float, *, basis: str = "reported") -> dict:
    path = tmp_path / f"{kind}-{year}.pdf"
    path.write_bytes(f"{kind}-{year}".encode("utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    return {
        "evidence_id": f"E-{kind.upper()}-{year}",
        "field_id": f"industry_{kind}_{year}",
        "field_kind": kind,
        "year": year,
        "value": value,
        "unit": "%" if kind.endswith("ratio") else "元",
        "source_unit": "%" if kind.endswith("ratio") else "亿元",
        "field_basis": basis,
        "statement_scope": "合并",
        "document_id": f"DOC-{year}",
        "pdf_page": 8,
        "file_sha256": digest,
        "source_file": path.name,
        "storage_relpath": path.name,
        "disclosure_date": "2024-04-30",
        "locator": f"PDF 第 8 页：{kind}",
        "source_review_status": "auto_extracted_pending_human_page_confirmation",
    }


def test_gate_covers_specialized_families_and_keeps_general_business() -> None:
    assert _gate("中国海油", "600938")["specialized_rule"] == "energy_mining_ar_revenue"
    assert _gate("中国建筑", "601668")["specialized_rule"] == "construction_real_estate_contract_cycle"
    assert _gate("招商银行", "600036")["specialized_rule"] == "banking_credit_quality"
    assert _gate("中国人寿", "601628")["specialized_rule"] == "insurance_service_result"
    assert _gate("中信证券", "600030")["specialized_rule"] == "securities_margin_commission"
    assert _gate("宁德时代", "300750")["specialized_rule"] is None


def test_specialized_prescreen_keeps_source_pass_and_reports_data_gap(tmp_path: Path) -> None:
    gate = _gate("中国海油", "600938")
    rows = [
        _source(tmp_path, "revenue", 2024, 1000),
        _source(tmp_path, "revenue", 2023, 800),
        _source(tmp_path, "accounts_receivable", 2024, 300, basis="net"),
    ]
    result = build_industry_prescreen(gate=gate, rows=rows, current_year=2024, t0="2024-12-31")

    assert result["status"] == "DATA_GAP"
    assert result["source_validation"]["status"] == "passed"
    assert result["data_gaps"]
    assert result["requested_materials"]
    assert result["field_evidence"][0]["document_id"].startswith("DOC-")
    assert result["field_evidence"][0]["pdf_page"] == 8
    assert result["professional_signoff_status"] == "draft_pending_professional_signoff"


def test_specialized_prescreen_calculates_candidate_with_traceable_evidence(tmp_path: Path) -> None:
    gate = _gate("中国海油", "600938")
    rows = [
        _source(tmp_path, "revenue", 2024, 1000),
        _source(tmp_path, "revenue", 2023, 800),
        _source(tmp_path, "accounts_receivable", 2024, 300, basis="net"),
        _source(tmp_path, "accounts_receivable", 2023, 200, basis="net"),
    ]
    result = build_industry_prescreen(gate=gate, rows=rows, current_year=2024, t0="2024-12-31")

    assert result["status"] == "candidate"
    assert result["metrics"]["growth_gap"] == 0.25
    assert {item["document_id"] for item in result["field_evidence"]} == {"DOC-2024", "DOC-2023"}
    assert result["configured_thresholds"]["professional_review_status"] == "draft_pending_professional_signoff"


def test_ratio_field_requires_explicit_percent_unit() -> None:
    candidate = _find_page_candidate(
        ["单位：%\n主要监管指标\n不良贷款率 1.25%"],
        FIELD_CONFIG["nonperforming_loan_ratio"],
    )
    assert candidate is not None
    assert candidate["unit"] == "%"
    assert candidate["value"] == 1.25


def test_execute_run_returns_specialized_completion_without_model(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main_module, "WORKSPACE_ROOT", tmp_path)
    gate = _gate("中国海油", "600938")
    rows = [
        _source(tmp_path, "revenue", 2024, 1000),
        _source(tmp_path, "revenue", 2023, 800),
        _source(tmp_path, "accounts_receivable", 2024, 300, basis="net"),
        _source(tmp_path, "accounts_receivable", 2023, 200, basis="net"),
    ]
    request = Request({"type": "http", "method": "POST", "path": "/api/runs", "headers": [], "client": ("test", 1), "server": ("test", 80), "scheme": "http"})
    response = main_module._execute_run(
        context={
            "case_id": "B6-CASE",
            "company_name": "中国海油",
            "ticker": "600938",
            "current_year": 2024,
            "previous_year": 2023,
            "t0": "2024-12-31",
            "currency": "CNY",
            "amount_unit": "元",
            "statement_scope": "合并",
            "sample_type": "public",
            "model_transfer_allowed": False,
            "public_prescreen": True,
            "prescreen_plan": {"mode": "public_prescreen", "analysis_current_year": 2024, "analysis_years": [2024, 2023], "missing_fields": [], "skipped_rules": [], "rule_plans": {}, "confidence": "technical"},
            "industry_gate": gate,
        },
        sources=rows,
        # 选择 R2 专门锁定行业卡片的外层规则编号不能被硬编码成 R1。
        rule_ids=["R2"],
        run_mode="full_analysis",
        r2_min_gap=0.0,
        planned_materiality=None,
        r1_gap_threshold=0.15,
        r1_strong_gap_threshold=0.30,
        r1_absolute_threshold=0.0,
        http_request=request,
        run_prefix="RUN-V7",
    )

    assert response.screening_status == "candidate"
    assert response.run_completeness == "complete_public_prescreen_industry_rule"
    assert response.model_check.status == "not_applicable"
    assert response.rule_results[0].rule_id == "R2"
    assert response.rule_results[0].risk_card["rule_id"] == "IND-ENERGY-AR-REV"
    assert response.context["industry_prescreen"]["professional_signoff_status"] == "draft_pending_professional_signoff"


def test_runs_api_uses_specialized_sources_and_keeps_data_gap_as_passed_source(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main_module, "WORKSPACE_ROOT", tmp_path)
    case_id = "B6_API_CASE"
    case_dir = _runtime_base(tmp_path) / "cases" / case_id
    case_rel = case_dir.relative_to(tmp_path).as_posix()
    documents_dir = case_dir / "documents"
    documents_dir.mkdir(parents=True)
    content = b"registered public report"
    report_path = documents_dir / "2024.pdf"
    report_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest().upper()
    documents = [
        {
            "document_id": "DOC-B6-2024",
            "source_file": f"documents/{report_path.name}",
                "storage_relpath": f"{case_rel}/documents/{report_path.name}",
            "report_year": 2024,
            "disclosure_date": "2024-04-30",
            "announcement_title": "中国海油2024年年度报告全文",
            "source_url": "https://static.cninfo.com.cn/finalpage/b6-2024.PDF",
            "sha256": digest,
        },
        {
            "document_id": "DOC-B6-2023",
            "source_file": "documents/2023.pdf",
                "storage_relpath": f"{case_rel}/documents/2023.pdf",
            "report_year": 2023,
            "disclosure_date": "2023-04-30",
            "announcement_title": "中国海油2023年年度报告全文",
            "source_url": "https://static.cninfo.com.cn/finalpage/b6-2023.PDF",
            "sha256": digest,
        },
    ]
    # The same bytes are intentional: source validation hashes the registered file;
    # the second document is only used to expose a missing prior AR field.
    (documents_dir / "2023.pdf").write_bytes(content)
    case = {
        "schema_version": "case_manifest_v1",
        "case_id": case_id,
        "company_name": "中国海油",
        "company_alias": "中国海油",
        "ticker": "600938",
        "t0": "2024-12-31",
        "currency": "CNY",
        "amount_unit": "元",
        "statement_scope": "合并",
        "sample_type": "public",
        "registry_mode": "cninfo_official_auto",
        "model_transfer_allowed": False,
        "source_snapshot_id": "SNAP-B6-API",
        "source_review_status": "validated",
        "documents": documents,
        "available_years": [2024, 2023],
        "available_report_years": [2024, 2023],
        "structured_evidence": [],
        "material_gaps": [],
    }
    (case_dir / "case.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    (case_dir / "financial_fields.json").write_text(json.dumps([
        {"field_kind": "revenue", "year": 2024, "value": 1000, "unit": "元", "field_basis": "reported", "document_id": "DOC-B6-2024", "pdf_page": 8, "evidence_id": "E-REV-2024", "locator": "PDF 第 8 页：营业收入", "file_sha256": digest, "source_file": documents[0]["source_file"], "storage_relpath": documents[0]["storage_relpath"], "disclosure_date": "2024-04-30"},
        {"field_kind": "revenue", "year": 2023, "value": 800, "unit": "元", "field_basis": "reported", "document_id": "DOC-B6-2023", "pdf_page": 8, "evidence_id": "E-REV-2023", "locator": "PDF 第 8 页：营业收入", "file_sha256": digest, "source_file": documents[1]["source_file"], "storage_relpath": documents[1]["storage_relpath"], "disclosure_date": "2023-04-30"},
        {"field_kind": "accounts_receivable", "year": 2024, "value": 300, "unit": "元", "field_basis": "net", "document_id": "DOC-B6-2024", "pdf_page": 8, "evidence_id": "E-AR-2024", "locator": "PDF 第 8 页：应收账款", "file_sha256": digest, "source_file": documents[0]["source_file"], "storage_relpath": documents[0]["storage_relpath"], "disclosure_date": "2024-04-30"},
    ], ensure_ascii=False), encoding="utf-8")
    assert (case_dir / "case.json").is_file()
    assert _case_dir(tmp_path, case_id) == case_dir
    assert get_case(tmp_path, case_id) is not None

    response = TestClient(main_module.app).post(
        "/api/runs",
        json={"case_id": case_id, "current_year": 2024, "run_mode": "full_analysis", "rule_ids": ["R1"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["screening_status"] == "DATA_GAP"
    assert body["run_completeness"] == "complete_public_prescreen_industry_rule_with_gaps"
    assert body["source_validation"]["status"] == "passed"
    assert body["context"]["industry_prescreen"]["industry_rule_id"] == "IND-ENERGY-AR-REV"
