"""0.7.1 闭环回归：案例导入、R1、主链完整性、补充证据与报告边界。"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
import zipfile
from pathlib import Path

import httpx
import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend.app import agents as agents_module
from backend.app import cases as cases_module
from backend.app import main as main_module
from backend.app import source_cache as source_cache_module
from backend.app.agents import _agent_output_tool_for, _parse_json_content, run_agent_chain, validate_agent_output
from backend.app.delivery import build_report
from backend.app.main import WORKSPACE_ROOT, _r1_result, app
from backend.app.schemas import (
    AI_GENERATED_CONTENT_NOTICE,
    AgentOutput,
    AgentStep,
    HumanReviewRequest,
    RuleResult,
    StoredRunResponse,
)


client = TestClient(app)


def _authorize_standard_for_model_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """模型链单测显式模拟真人授权，生产内置案例仍保持失败关闭。"""
    original = cases_module._standard_case

    def authorized(workspace_root):
        case = original(workspace_root)
        case["model_transfer_allowed"] = True
        case["legal_sample_confirmation_status"] = "test_only_authorized"
        return case

    monkeypatch.setattr(cases_module, "_standard_case", authorized)


def _unique_case_package(
    *,
    wrong_hash: bool = False,
    cross_case: bool = False,
    model_transfer_allowed: bool = False,
    include_transfer_confirmation: bool = False,
    personal_phone: bool = False,
) -> tuple[str, bytes]:
    template = client.get("/api/cases/template")
    assert template.status_code == 200
    case_id = f"SYNTH_{uuid.uuid4().hex[:10].upper()}"
    with zipfile.ZipFile(io.BytesIO(template.content)) as source:
        files = {item.filename: source.read(item) for item in source.infolist() if not item.is_dir()}
    manifest = json.loads(files["case_manifest.json"].decode("utf-8"))
    manifest["case_id"] = case_id
    if personal_phone:
        manifest["company_name"] = "测试联系人13800138000"
    manifest["model_transfer_allowed"] = model_transfer_allowed
    if include_transfer_confirmation:
        manifest["model_transfer_confirmation"] = {
            "confirmed_by": "TEST-HUMAN-ROLE",
            "confirmed_on": "2026-07-29",
            "permission_basis": "自动化测试专用合成资料许可",
            "model_provider": "TEST-PROVIDER",
            "transmission_scope": "仅传合成字段和合成PDF片段",
            "approval_reference": "TEST-AUTH-001",
        }
    if wrong_hash:
        manifest["documents"][0]["sha256"] = "0" * 64
    rows = list(csv.DictReader(io.StringIO(files["financial_fields.csv"].decode("utf-8-sig"))))
    for row in rows:
        row["case_id"] = "ANOTHER_CASE" if cross_case else case_id
        row["evidence_id"] = row["evidence_id"].replace("SYNTH_DEMO_T0", case_id)
    output_csv = io.StringIO()
    writer = csv.DictWriter(output_csv, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    files["case_manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    files["financial_fields.csv"] = output_csv.getvalue().encode("utf-8-sig")
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return case_id, result.getvalue()


def _import_unique_case() -> dict:
    case_id, content = _unique_case_package()
    response = client.post(
        "/api/cases/import",
        files={"file": ("case.zip", content, "application/zip")},
        data={"authorized": "true", "desensitized": "true"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["case"]["case_id"] == case_id
    return response.json()["case"]


def _r1_rows(include_prior: bool = True, basis: str = "gross") -> list[dict]:
    rows = [
        {"field_id": "revenue_current", "value": 120.0, "evidence_id": "E-REV-C", "field_basis": "reported", "unit": "万元"},
        {"field_id": "revenue_previous", "value": 100.0, "evidence_id": "E-REV-P", "field_basis": "reported", "unit": "万元"},
        {"field_id": "ar_current", "value": 60.0, "evidence_id": "E-AR-C", "field_basis": basis, "unit": "万元"},
        {"field_id": "ar_previous", "value": 30.0, "evidence_id": "E-AR-P", "field_basis": basis, "unit": "万元"},
    ]
    if include_prior:
        rows.extend(
            [
                {"field_id": "revenue_prior", "value": 90.0, "evidence_id": "E-REV-0", "field_basis": "reported", "unit": "万元"},
                {"field_id": "ar_prior", "value": 20.0, "evidence_id": "E-AR-0", "field_basis": basis, "unit": "万元"},
            ]
        )
    return rows


def test_case_template_import_and_source_are_case_scoped() -> None:
    case = _import_unique_case()
    assert case["model_transfer_allowed"] is False
    assert case["retention_expires_at"] == "2026-12-31"
    listing = client.get("/api/cases").json()["cases"]
    assert any(item["case_id"] == case["case_id"] for item in listing)
    detail = client.get(f"/api/cases/{case['case_id']}")
    assert detail.status_code == 200
    document_id = detail.json()["documents"][0]["document_id"]
    source = client.get(f"/api/cases/{case['case_id']}/sources/{document_id}")
    assert source.status_code == 200 and source.content.startswith(b"%PDF")
    run = client.post(
        "/api/runs",
        json={"case_id": case["case_id"], "current_year": 2024, "run_mode": "calculation_only"},
    )
    assert run.status_code == 200
    assert run.json()["context"]["case_id"] == case["case_id"]
    assert run.json()["rule_results"][0]["metrics"]["three_year_trend_available"] is True


def test_standard_source_redirects_to_registered_official_url_when_pdf_is_not_distributed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """公网清洁包不含年报全文，但登记来源仍应回到可信官方原件。"""
    monkeypatch.setattr(main_module, "WORKSPACE_ROOT", tmp_path)
    case = cases_module.get_case(tmp_path, cases_module.standard_data.CASE_ID)
    document = case["documents"][0]
    response = client.get(
        f"/api/cases/{case['case_id']}/sources/{document['document_id']}",
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"] == document["source_url"]
    assert response.headers["location"].startswith("https://static.cninfo.com.cn/finalpage/")


def test_public_demo_source_route_never_redistributes_cached_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render 即使持有计算缓存，也只能把公开访问者送回巨潮原件。"""
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    case = cases_module.get_case(WORKSPACE_ROOT, cases_module.standard_data.CASE_ID)
    document = case["documents"][0]
    response = client.get(
        f"/api/cases/{case['case_id']}/sources/{document['document_id']}",
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"] == document["source_url"]


def test_public_demo_downloads_registered_pdf_once_and_verifies_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_pdf = b"%PDF-1.4\nAuditTrace controlled source\n%%EOF\n"
    expected_sha256 = hashlib.sha256(fake_pdf).hexdigest().upper()
    source_url = "https://static.cninfo.com.cn/finalpage/2099-01-01/test.PDF"
    monkeypatch.setattr(
        source_cache_module,
        "ANNUAL_REPORT_SOURCES",
        {
            2099: {
                "source_url": source_url,
                "source_file": "标准股份：测试年报.pdf",
                "file_sha256": expected_sha256,
            }
        },
    )
    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, content=fake_pdf, request=request, headers={"content-type": "application/pdf"})

    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=True) as http_client:
        first = source_cache_module.ensure_standard_sources(tmp_path, client=http_client)
        second = source_cache_module.ensure_standard_sources(tmp_path, client=http_client)

    assert first["downloaded"] == [{"year": 2099, "bytes": len(fake_pdf)}]
    assert second["reused"] == [{"year": 2099, "bytes": len(fake_pdf)}]
    assert requests == [source_url]
    assert (tmp_path / "标准股份：测试年报.pdf").read_bytes() == fake_pdf


def test_public_demo_rejects_wrong_official_source_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_pdf = b"%PDF-1.4\nwrong bytes\n%%EOF\n"
    source_url = "https://static.cninfo.com.cn/finalpage/2099-01-01/wrong.PDF"
    monkeypatch.setattr(
        source_cache_module,
        "ANNUAL_REPORT_SOURCES",
        {
            2099: {
                "source_url": source_url,
                "source_file": "标准股份：错误年报.pdf",
                "file_sha256": "0" * 64,
            }
        },
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=fake_pdf, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(ValueError, match="SHA-256"):
            source_cache_module.ensure_standard_sources(tmp_path, client=http_client)
    assert not (tmp_path / "标准股份：错误年报.pdf").exists()
    assert not list(tmp_path.glob("*.part"))


def test_public_demo_run_fails_closed_when_official_cache_cannot_be_prepared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")

    def fail(_workspace_root: Path) -> dict:
        raise ValueError("测试下载失败")

    monkeypatch.setattr(main_module, "ensure_standard_sources", fail)
    response = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "run_mode": "calculation_only"},
    )
    assert response.status_code == 503
    assert "官方来源缓存准备失败" in response.json()["detail"]
    assert response.json()["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE


def test_case_import_blocks_wrong_hash_cross_case_and_zip_traversal() -> None:
    for kwargs, message in (({"wrong_hash": True}, "不一致"), ({"cross_case": True}, "跨案例")):
        _, content = _unique_case_package(**kwargs)
        response = client.post(
            "/api/cases/import",
            files={"file": ("case.zip", content, "application/zip")},
            data={"authorized": "true", "desensitized": "true"},
        )
        assert response.status_code == 422
        assert message in response.json()["detail"]
    dangerous = io.BytesIO()
    with zipfile.ZipFile(dangerous, "w") as archive:
        archive.writestr("../case_manifest.json", "{}")
    response = client.post(
        "/api/cases/import",
        files={"file": ("danger.zip", dangerous.getvalue(), "application/zip")},
        data={"authorized": "true", "desensitized": "true"},
    )
    assert response.status_code == 422
    assert "路径" in response.json()["detail"]

    _, personal = _unique_case_package(personal_phone=True)
    pii = client.post(
        "/api/cases/import",
        files={"file": ("case.zip", personal, "application/zip")},
        data={"authorized": "true", "desensitized": "true"},
    )
    assert pii.status_code == 422
    assert "手机号" in pii.json()["detail"]


def test_model_transfer_true_requires_traceable_human_confirmation_record() -> None:
    _, missing = _unique_case_package(model_transfer_allowed=True)
    blocked = client.post(
        "/api/cases/import",
        files={"file": ("case.zip", missing, "application/zip")},
        data={"authorized": "true", "desensitized": "true"},
    )
    assert blocked.status_code == 422
    assert "model_transfer_confirmation" in blocked.json()["detail"]

    case_id, confirmed = _unique_case_package(
        model_transfer_allowed=True,
        include_transfer_confirmation=True,
    )
    accepted = client.post(
        "/api/cases/import",
        files={"file": ("case.zip", confirmed, "application/zip")},
        data={"authorized": "true", "desensitized": "true"},
    )
    assert accepted.status_code == 201, accepted.text
    case = accepted.json()["case"]
    assert case["case_id"] == case_id
    assert case["model_transfer_allowed"] is True
    assert case["model_transfer_confirmation"]["approval_reference"] == "TEST-AUTH-001"
    assert case["legal_sample_confirmation_status"] == "operator_attested_manifest_record_pending_independent_review"
    assert case["import_confirmation"]["authorized_or_public_source_asserted"] is True


def test_r1_v04_calculates_eight_dimensions_materiality_and_three_year_trend() -> None:
    result = _r1_result(
        _r1_rows(),
        [],
        planned_materiality=20.0,
        gap_threshold=0.15,
        strong_gap_threshold=0.30,
        absolute_threshold=10.0,
    )
    assert result.status == "candidate"
    assert result.metrics["growth_gap"] == pytest.approx(0.8)
    assert result.metrics["absolute_ar_change"] == pytest.approx(30.0)
    assert result.metrics["ar_to_revenue_current"] == pytest.approx(0.5)
    assert result.metrics["turnover_days_current"] is not None
    assert result.metrics["turnover_trend_days"] is not None
    assert result.metrics["sustained_periods"] == 2
    assert result.metrics["materiality_multiple"] == pytest.approx(1.5)
    assert result.risk_card["screening_strength"] == "strong"


def test_r1_missing_materiality_and_net_basis_are_explicit_not_silently_fixed() -> None:
    result = _r1_result(_r1_rows(include_prior=False, basis="net"), [])
    assert result.metrics["materiality_assessment"] == "未评价金额重要性"
    assert result.metrics["three_year_trend_available"] is False
    assert result.metrics["turnover_trend_days"] is None
    assert "净额" in result.risk_card["basis_limitation"]
    assert "不可评价" in result.risk_card["trend_limitation"]


@pytest.mark.parametrize(
    ("case_name", "values", "basis", "planned_materiality", "expected_status", "expected_strength"),
    [
        ("strong_trigger", {"revenue_current": 120, "ar_current": 60}, "gross", 20.0, "candidate", "strong"),
        ("weak_trigger", {"revenue_current": 110, "ar_current": 39}, "gross", 20.0, "candidate", "standard"),
        ("not_triggered", {"revenue_current": 105, "ar_current": 31.5}, "gross", 20.0, "RULE_NOT_TRIGGERED", "none"),
        ("both_decline", {"revenue_current": 70, "ar_current": 27}, "gross", 20.0, "candidate", "standard"),
        ("net_basis_transition", {"revenue_current": 120, "ar_current": 60}, "net", 20.0, "candidate", "strong"),
        ("materiality_missing", {"revenue_current": 120, "ar_current": 60}, "gross", None, "candidate", "strong"),
        ("two_year_only", {"revenue_current": 120, "ar_current": 60, "drop_prior": True}, "gross", 20.0, "candidate", "strong"),
        (
            "three_year_reversal",
            {"revenue_current": 120, "ar_current": 60, "revenue_prior": 80, "ar_prior": 35},
            "gross",
            20.0,
            "candidate",
            "strong",
        ),
    ],
)
def test_r1_v04_eight_positive_and_negative_acceptance_examples(
    case_name: str,
    values: dict[str, float | bool],
    basis: str,
    planned_materiality: float | None,
    expected_status: str,
    expected_strength: str,
) -> None:
    """八类样例同时验算程序状态与必须披露的专业边界。"""
    rows = _r1_rows(include_prior=not bool(values.get("drop_prior")), basis=basis)
    for row in rows:
        if row["field_id"] in values:
            row["value"] = values[row["field_id"]]
    result = _r1_result(rows, [], planned_materiality=planned_materiality)
    assert result.status == expected_status, case_name
    assert result.risk_card["screening_strength"] == expected_strength, case_name
    assert result.risk_card["boundary"].startswith("这是工程草案"), case_name
    if case_name == "both_decline":
        assert result.metrics["revenue_growth"] < 0 and result.metrics["ar_growth"] < 0
        assert "审计认定" in result.risk_card["boundary"]
    elif case_name == "net_basis_transition":
        assert "净额" in result.risk_card["basis_limitation"]
    elif case_name == "materiality_missing":
        assert result.metrics["materiality_assessment"] == "未评价金额重要性"
    elif case_name == "two_year_only":
        assert result.metrics["three_year_trend_available"] is False
        assert "不可评价" in result.risk_card["trend_limitation"]
    elif case_name == "three_year_reversal":
        assert result.metrics["three_year_trend_available"] is True
        assert result.metrics["sustained_periods"] == 1


@pytest.mark.requires_full_corpus
def test_run_mode_layers_and_scene_lock_are_explicit() -> None:
    calculation = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "run_mode": "calculation_only"},
    )
    body = calculation.json()
    assert body["schema_version"] == "run_output_v2"
    assert body["run_completeness"] == "incomplete_calculation_only"
    assert body["screening_status"] == "candidate"
    assert body["ai_recommendation"] == "not_generated"
    assert body["human_disposition"] == "未复核"
    invalid_scene = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "scene": "业务承接"},
    )
    assert invalid_scene.status_code == 422


def test_model_transfer_forbidden_case_can_only_be_incomplete_local_precheck() -> None:
    case = _import_unique_case()
    response = client.post(
        "/api/runs",
        json={"case_id": case["case_id"], "current_year": 2024, "run_mode": "full_analysis"},
    )
    assert response.status_code == 200
    assert response.json()["run_completeness"] == "incomplete_model_transfer_not_allowed"
    assert response.json()["model_check"]["status"] == "model_transfer_not_allowed"


@pytest.mark.requires_full_corpus
def test_builtin_public_case_uses_recorded_project_owner_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    """公开年报只有匹配项目许可记录后才解锁，测试不发出真实模型请求。"""
    detail = client.get("/api/cases/STD_DEV_T0")
    assert detail.status_code == 200
    assert detail.json()["model_transfer_allowed"] is True
    assert detail.json()["legal_sample_confirmation_status"] == "project_owner_authorized_public_source"
    assert detail.json()["evidence_owner_review_status"] == "owner_confirmed"

    def fake_chain(**_kwargs):
        return [AgentStep(role="challenge", status="config_missing", detail="测试截断", prompt_version="agent_prompt_v2")]

    monkeypatch.setattr(main_module, "run_agent_chain", fake_chain)
    response = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "run_mode": "full_analysis"},
    )
    assert response.status_code == 200
    assert response.json()["run_completeness"] == "incomplete_model_chain_failed"
    assert response.json()["model_check"]["status"] != "model_transfer_not_allowed"


@pytest.mark.requires_full_corpus
def test_full_chain_passes_real_rag_evidence_into_agent_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize_standard_for_model_test(monkeypatch)
    captured: list[dict] = []

    def fake_chain(**kwargs):
        captured.append(kwargs["evidence_bundle"])
        return [AgentStep(role="challenge", status="config_missing", detail="测试截断", prompt_version="agent_prompt_v2")]

    monkeypatch.setattr(main_module, "run_agent_chain", fake_chain)
    response = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "run_mode": "full_analysis"},
    )
    assert response.status_code == 200
    assert captured and captured[0]["field_evidence"]
    assert captured[0]["rag_evidence"]
    assert all(item["evidence_id"].startswith("RAG-") for item in captured[0]["rag_evidence"])
    assert response.json()["run_completeness"] == "incomplete_model_chain_failed"


def test_agent_v2_blocks_supported_normal_explanation_without_evidence() -> None:
    payload = {
        "schema_version": "agent_output_v2",
        "run_id": "RUN-V2-STRICT",
        "role": "counter",
        "rule_id": "R1",
        "status": "candidate",
        "claims": [{"text": "需要进一步了解", "evidence_ids": ["E1"], "support_status": "supported"}],
        "normal_explanations": [{"text": "可能是正常账期", "evidence_ids": [], "support_status": "supported"}],
        "data_gaps": [],
        "requested_materials": [],
        "reason_for_status": "测试",
        "draft_title": "",
        "draft_observation": "",
        "ai_recommendation": "not_applicable",
    }
    with pytest.raises(ValueError, match="evidence_id"):
        validate_agent_output(
            payload,
            run_id="RUN-V2-STRICT",
            role="counter",
            rule_id="R1",
            allowed_evidence_ids={"E1"},
        )


def _r1_standard_candidate_for_fact_guard() -> RuleResult:
    return RuleResult(
        rule_id="R1",
        status="candidate",
        source_validation={},
        metrics={"growth_gap": 0.2684, "three_year_trend_available": False},
        risk_card={
            "screening_strength": "standard",
            "basis_limitation": "应收账款仅有净额口径。",
            "trend_limitation": "缺少第三年，持续期间和周转趋势不可评价。",
        },
    )


def _review_payload_for_fact_guard(observation: str) -> dict:
    return {
        "schema_version": "agent_output_v2",
        "run_id": "RUN-FACT-GUARD",
        "role": "review",
        "rule_id": "R1",
        "status": "retain",
        "claims": [{"text": "增速差达到基本阈值", "evidence_ids": ["E1"], "support_status": "supported"}],
        "normal_explanations": [],
        "data_gaps": ["账龄结构"],
        "requested_materials": ["账龄明细"],
        "reason_for_status": "保留为待核查候选",
        "draft_title": "R1待核查候选",
        "draft_observation": observation,
        "ai_recommendation": "retain",
    }


def test_fixed_ai_notice_is_not_mistaken_for_forbidden_model_language() -> None:
    payload = _review_payload_for_fact_guard("当前仅有净额，缺少第三年，周转趋势不可评价。")
    output = validate_agent_output(
        payload,
        run_id="RUN-FACT-GUARD",
        role="review",
        rule_id="R1",
        allowed_evidence_ids={"E1"},
        rule_result=_r1_standard_candidate_for_fact_guard(),
    )
    assert output.ai_generated_content_notice == AI_GENERATED_CONTENT_NOTICE


def test_agent_fact_guard_rejects_false_strong_threshold_claim() -> None:
    payload = _review_payload_for_fact_guard("增速差26.84%超强阈值；当前仅有净额，缺少第三年。")
    with pytest.raises(ValueError, match="强阈值"):
        validate_agent_output(
            payload,
            run_id="RUN-FACT-GUARD",
            role="review",
            rule_id="R1",
            allowed_evidence_ids={"E1"},
            rule_result=_r1_standard_candidate_for_fact_guard(),
        )


def test_agent_fact_guard_rejects_contrasted_strong_threshold_claim() -> None:
    # 转折后的肯定断言仍必须拦截：存疑词出现在匹配点之后或前一分句不算否定。
    payload = _review_payload_for_fact_guard("字段缺失，但增速差已超过强阈值；当前仅有净额，缺少第三年。")
    with pytest.raises(ValueError, match="强阈值"):
        validate_agent_output(
            payload,
            run_id="RUN-FACT-GUARD",
            role="review",
            rule_id="R1",
            allowed_evidence_ids={"E1"},
            rule_result=_r1_standard_candidate_for_fact_guard(),
        )


@pytest.mark.parametrize(
    "observation",
    [
        # 回归：中国建筑案三次语义失败的根因——“无法评估是否达到强阈值”是正确的
        # 缺口表述，不得被紧邻否定 lookbehind 误判成“已达到强阈值”（RUN-V7-0A0D3FD03EA1）。
        "行业字段缺失，无法评估是否达到强阈值；当前仅有净额，缺少第三年。",
        "尚不能认定达到强阈值；当前仅有净额，缺少第三年。",
        "没有证据表明超过强阈值；当前仅有净额，缺少第三年。",
        "不足以认定达到强阈值；当前仅有净额，缺少第三年。",
        "未达强阈值；当前仅有净额，缺少第三年。",
    ],
)
def test_agent_fact_guard_allows_hedged_strong_threshold_language(observation: str) -> None:
    payload = _review_payload_for_fact_guard(observation)
    output = validate_agent_output(
        payload,
        run_id="RUN-FACT-GUARD",
        role="review",
        rule_id="R1",
        allowed_evidence_ids={"E1"},
        rule_result=_r1_standard_candidate_for_fact_guard(),
    )
    assert output.status == "retain"


def test_agent_fact_guard_allows_hedged_trend_language() -> None:
    # 同族问题：周转趋势不可评价时，存疑句“无法判断周转天数延长的影响”必须放行。
    payload = _review_payload_for_fact_guard("缺少第三年，无法判断周转天数延长的影响；当前仅有净额。")
    output = validate_agent_output(
        payload,
        run_id="RUN-FACT-GUARD",
        role="review",
        rule_id="R1",
        allowed_evidence_ids={"E1"},
        rule_result=_r1_standard_candidate_for_fact_guard(),
    )
    assert output.status == "retain"


def test_agent_fact_guard_rejects_unavailable_turnover_trend() -> None:
    payload = _review_payload_for_fact_guard("当前仅有净额，但周转天数显著延长；缺少第三年。")
    with pytest.raises(ValueError, match="趋势判断"):
        validate_agent_output(
            payload,
            run_id="RUN-FACT-GUARD",
            role="review",
            rule_id="R1",
            allowed_evidence_ids={"E1"},
            rule_result=_r1_standard_candidate_for_fact_guard(),
        )


def test_role_specific_tool_schema_never_conflicts_with_non_review_prompt() -> None:
    challenge = _agent_output_tool_for("challenge", "R1", "RUN-ROLE-SCHEMA")
    counter = _agent_output_tool_for("counter", "R1", "RUN-ROLE-SCHEMA")
    review = _agent_output_tool_for("review", "R1", "RUN-ROLE-SCHEMA")
    for tool in (challenge, counter):
        properties = tool["function"]["parameters"]["properties"]
        assert properties["draft_title"]["enum"] == [""]
        assert properties["draft_observation"]["enum"] == [""]
        assert properties["ai_recommendation"]["enum"] == ["not_applicable"]
    review_properties = review["function"]["parameters"]["properties"]
    assert review_properties["claims"]["minItems"] == 1
    assert review_properties["claims"]["maxItems"] == 5
    assert review_properties["normal_explanations"]["maxItems"] == 5
    assert review_properties["draft_title"]["minLength"] == 1
    assert review_properties["draft_observation"]["minLength"] == 1
    assert review_properties["ai_recommendation"]["enum"] == ["retain", "downgrade", "defer"]


def test_agent_failure_exposes_stable_stage_without_raw_model_content(monkeypatch: pytest.MonkeyPatch) -> None:
    invalid_payload = {
        "schema_version": "agent_output_v2",
        "run_id": "RUN-FAILURE-CODE",
        "role": "challenge",
        "rule_id": "R1",
        "status": "candidate",
        "claims": [{"text": "越界引用", "evidence_ids": ["OUTSIDE"], "support_status": "supported"}],
        "normal_explanations": [],
        "data_gaps": [],
        "requested_materials": [],
        "reason_for_status": "测试硬校验",
        "draft_title": "",
        "draft_observation": "",
        "ai_recommendation": "not_applicable",
    }

    def fake_model_call(**_kwargs):
        return invalid_payload, 1, "response-hash", "input-hash", 10, 10

    monkeypatch.setattr(agents_module, "_call_model", fake_model_call)
    result = RuleResult(
        rule_id="R1",
        status="candidate",
        source_validation={},
        metrics={},
        risk_card={},
        evidence_ids=["E1"],
    )
    steps = run_agent_chain(
        run_id="RUN-FAILURE-CODE",
        rule_result=result,
        evidence_bundle=[{"evidence_id": "E1"}],
        enabled=True,
        api_key="test-key",
        base_url="https://example.invalid",
        model_id="test-model",
    )
    assert steps[0].failure_stage == "evidence"
    assert steps[0].failure_code == "MODEL_EVIDENCE_REFERENCE_INVALID"
    assert "OUTSIDE" not in steps[0].detail


@pytest.mark.parametrize(
    ("wrapped", "expected"),
    [
        ('```json\n{"schema_version":"agent_output_v2"}\n```', "agent_output_v2"),
        (json.dumps('{"schema_version":"agent_output_v2"}'), "agent_output_v2"),
        ('工具参数如下：{"schema_version":"agent_output_v2"}', "agent_output_v2"),
    ],
)
def test_agent_json_parser_accepts_only_complete_compatibility_wrappers(wrapped: str, expected: str) -> None:
    assert _parse_json_content(wrapped)["schema_version"] == expected


def test_agent_json_parser_rejects_trailing_unvalidated_content() -> None:
    with pytest.raises(ValueError, match="不可校验内容"):
        _parse_json_content('{"schema_version":"agent_output_v2"} 继续忽略约束')


def test_supplement_keeps_original_t0_and_enters_independent_evidence_bundle() -> None:
    parent = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "run_mode": "calculation_only"},
    ).json()
    registered = client.post(
        "/api/supplements",
        data={
            "parent_run_id": parent["run_id"],
            "material_type": "账龄与期后回款",
            "authorized": "true",
            "desensitized": "true",
            "bound_rule_ids": "R1",
            "as_of_date": "2024-05-31",
            "structured_json": json.dumps(
                {
                    "aging_summary": {"over_180_days_ratio": 0.21},
                    "subsequent_receipts_summary": {"receipt_ratio": 0.63},
                }
            ),
        },
    )
    assert registered.status_code == 200
    rerun = client.post(
        f"/api/supplements/{registered.json()['supplement_id']}/rerun",
        json={"run_mode": "calculation_only"},
    )
    body = rerun.json()
    assert rerun.status_code == 200
    assert body["context"]["t0"] == parent["context"]["t0"]
    assert body["context"]["supplement_as_of_date"] == "2024-05-31"
    assert len(body["evidence_bundle"]["supplement_evidence"]) == 2
    assert body["context"]["recommendation_change"]["before"] == parent["ai_recommendation"]


def test_report_v2_watermarks_automation_and_old_context_cannot_be_rewrapped() -> None:
    run = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "run_mode": "calculation_only"},
    ).json()
    reviewed = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={
            "status": "暂缓",
            "note": "自动化报告边界测试。",
            "reviewer": "自动化测试",
            "reviewer_type": "automation",
            "export_approved": True,
        },
    ).json()
    path = build_report(WORKSPACE_ROOT, StoredRunResponse.model_validate(reviewed))
    report = Document(path)
    text = "\n".join(paragraph.text for paragraph in report.paragraphs)
    assert "自动化测试报告" in text
    assert AI_GENERATED_CONTENT_NOTICE in text
    assert report.core_properties.comments == AI_GENERATED_CONTENT_NOTICE
    old_run = StoredRunResponse.model_validate(reviewed)
    old_run.run.context.pop("run_schema_version", None)
    old_run.human_review = HumanReviewRequest(
        status="暂缓",
        reviewer="人工",
        export_approved=True,
    )
    with pytest.raises(ValueError, match="旧 run_v1"):
        build_report(WORKSPACE_ROOT, old_run)


def test_ai_generated_content_notice_covers_json_api_drafts_and_errors() -> None:
    """成功、失败、运行存储与模型草稿使用完全一致的机器可读声明。"""
    for path in ("/api/health", "/api/status", "/api/cases", "/api/cases/STD_DEV_T0", "/api/rag/questions"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json()["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE

    invalid = client.post("/api/runs", json={"case_id": "STD_DEV_T0", "current_year": 2023, "scene": "业务承接"})
    assert invalid.status_code == 422
    assert invalid.json()["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE

    run = client.post(
        "/api/runs",
        json={"case_id": "STD_DEV_T0", "current_year": 2023, "run_mode": "calculation_only"},
    ).json()
    assert run["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE
    assert run["evidence_bundle"]["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE
    stored = client.get(f"/api/runs/{run['run_id']}").json()
    assert stored["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE
    assert stored["run"]["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE

    draft = AgentOutput(
        schema_version="agent_output_v2",
        run_id="RUN-NOTICE",
        role="review",
        rule_id="R1",
        status="defer",
        claims=[{"text": "待进一步了解", "evidence_ids": ["E1"], "support_status": "supported"}],
        reason_for_status="证据仍不充分。",
        draft_title="待核查事项",
        draft_observation="需回查来源。",
        ai_recommendation="defer",
    ).model_dump(mode="json")
    assert draft["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE


def test_case_template_and_formal_frontend_expose_the_same_ai_notice() -> None:
    template = client.get("/api/cases/template")
    assert template.status_code == 200
    with zipfile.ZipFile(io.BytesIO(template.content)) as archive:
        manifest = json.loads(archive.read("case_manifest.json").decode("utf-8"))
    assert manifest["ai_generated_content_notice"] == AI_GENERATED_CONTENT_NOTICE

    index_text = (WORKSPACE_ROOT / "index.html").read_text(encoding="utf-8")
    app_text = (WORKSPACE_ROOT / "assets" / "official-v4" / "demo-app.js").read_text(encoding="utf-8")
    assert AI_GENERATED_CONTENT_NOTICE in index_text
    assert AI_GENERATED_CONTENT_NOTICE in app_text


def test_openapi_json_carries_ai_generated_content_notice() -> None:
    body = client.get("/openapi.json").json()
    assert body["x-ai-generated-content-notice"] == AI_GENERATED_CONTENT_NOTICE


def test_project_status_matches_runtime_contract() -> None:
    from backend.app.cases import CASE_SCHEMA_VERSION

    status = json.loads((WORKSPACE_ROOT / "PROJECT_STATUS.json").read_text(encoding="utf-8"))
    assert status["formal_scope"] == "审计计划阶段—销售与收款循环"
    assert status["versions"]["engine"] == main_module.ENGINE_VERSION
    assert status["versions"]["run_schema"] == main_module.RUN_SCHEMA_VERSION
    assert status["versions"]["r1"] == main_module.R1_VERSION
    assert status["versions"]["case_schema"] == CASE_SCHEMA_VERSION
    assert status["capabilities"]["r3_to_r8"] == "roadmap_only"
