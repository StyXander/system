"""后续系统能力回归：硬校验、RAG、补充资料、缓存和导出。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.agents import validate_agent_output
from backend.app.data import ANNUAL_REPORT_SOURCES, get_period_sources
from backend.app.main import WORKSPACE_ROOT, _validate_sources, app


client = TestClient(app)


def _create_run() -> dict:
    response = client.post(
        "/api/runs",
        json={"current_year": 2023, "rule_ids": ["R1", "R2"], "check_model": False},
    )
    assert response.status_code == 200
    return response.json()


def test_registered_source_hashes_match_real_files() -> None:
    context, sources = get_period_sources(2023, ("R1", "R2"))
    assert _validate_sources(sources, context["t0"]) == []


def test_standard_case_annual_reports_expose_verified_official_urls() -> None:
    """四份年报的官方公告元数据只来自内置案例源表，并进入案例详情与字段证据。"""
    expected_urls = {
        2022: "https://static.cninfo.com.cn/finalpage/2023-04-19/1216455382.PDF",
        2023: "https://static.cninfo.com.cn/finalpage/2024-04-18/1219646140.PDF",
        2024: "https://static.cninfo.com.cn/finalpage/2025-04-29/1223359539.PDF",
        2025: "https://static.cninfo.com.cn/finalpage/2026-04-30/1225266733.PDF",
    }
    assert {year: source["source_url"] for year, source in ANNUAL_REPORT_SOURCES.items()} == expected_urls

    detail = client.get("/api/cases/STD_DEV_T0")
    assert detail.status_code == 200
    assert detail.json()["model_transfer_allowed"] is True
    assert detail.json()["retention_expires_at"] == "2026-12-31"
    assert detail.json()["legal_sample_confirmation_status"] == "project_owner_authorized_public_source"
    assert detail.json()["evidence_owner_review_status"] == "owner_confirmed"
    assert detail.json()["model_transfer_confirmation"]["approval_reference"] == "OWNER-AUTH-20260807-001"
    assert "项目所有者核验" in detail.json()["field_validation"]["boundary"]
    documents = {item["report_year"]: item for item in detail.json()["documents"]}
    assert set(documents) == set(expected_urls)
    for year, url in expected_urls.items():
        assert documents[year]["source_url"] == url
        assert documents[year]["announcement_title"] == ANNUAL_REPORT_SOURCES[year]["announcement_title"]
        assert documents[year]["disclosure_date"] == ANNUAL_REPORT_SOURCES[year]["disclosure_date"]
        assert documents[year]["sha256"] == ANNUAL_REPORT_SOURCES[year]["file_sha256"]

    _, sources = get_period_sources(2025, ("R1", "R2"))
    assert all(item["source_url"] == expected_urls[item["year"]] for item in sources)


def test_wrong_source_hash_is_a_hard_failure() -> None:
    context, sources = get_period_sources(2023, ("R1",))
    sources[0]["file_sha256"] = "0" * 64
    assert any("SHA-256不一致" in issue for issue in _validate_sources(sources, context["t0"]))


def test_forbidden_conclusion_is_blocked_in_data_gaps_too() -> None:
    payload = {
        "schema_version": "agent_output_v1",
        "run_id": "RUN-STRICT-ALL-FIELDS",
        "role": "challenge",
        "rule_id": "R1",
        "status": "candidate",
        "claims": [{"text": "需要进一步了解。", "evidence_ids": ["STD_REV_2023"]}],
        "normal_explanations": [],
        "data_gaps": ["需要确认是否造假"],
        "requested_materials": [],
        "reason_for_status": "仅作边界测试。",
    }
    with pytest.raises(ValueError, match="禁止定性"):
        validate_agent_output(
            payload,
            run_id="RUN-STRICT-ALL-FIELDS",
            role="challenge",
            rule_id="R1",
            allowed_evidence_ids={"STD_REV_2023"},
        )


def test_rag_index_is_ready_and_has_real_chunks() -> None:
    response = client.post("/api/rag/prepare")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["source_count"] == 4
    assert body["chunk_count"] > 100
    assert body["vector_backend"].startswith("faiss")


def test_rag_professional_question_set_is_versioned_and_bounded() -> None:
    response = client.get("/api/rag/questions")
    assert response.status_code == 200
    body = response.json()
    assert body["version"].startswith("rag-question-set-w3-v1.1")
    assert body["review_status"] == "professional_input_received_pending_team_source_page_review"
    assert len(body["questions"]) == 6
    assert {item["question_id"] for item in body["questions"]} == {f"RAG-Q{i}" for i in range(1, 7)}
    assert all(item["target_sections"] and item["expected_fields"] and item["no_hit_prompt"] for item in body["questions"])


def test_rag_fixed_question_returns_traceable_candidate_fragments() -> None:
    response = client.post(
        "/api/rag/retrieve",
        json={"question_id": "RAG-Q1", "t0": "2026-04-30", "rule_id": "R1", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["question"]["question_id"] == "RAG-Q1"
    assert body["question_set_version"].startswith("rag-question-set-w3-v1.1")
    assert body["retrieval_version"].startswith("rag-retrieval-v1.2")
    assert body["evidence_gap"]["requires_human_confirmation"] is True
    assert body["evidence_gap"]["auto_sync_to_risk_card"] is False
    assert body["results"]
    for item in body["results"]:
        assert item["evidence_id"].startswith("RAG-STD-")
        assert item["chunk_id"].startswith("STD-")
        assert item["document_id"].startswith("STD-AR-")
        assert item["pdf_page"] >= 1
        assert item["excerpt_is_verbatim"] is True
        assert 0 <= item["excerpt_char_start"] < item["excerpt_char_end"] <= item["chunk_char_length"]
        assert item["review_status"] == "candidate_fragment_pending_human_page_review"


def test_rag_fixed_question_rejects_wrong_rule_binding() -> None:
    response = client.post(
        "/api/rag/retrieve",
        json={"question_id": "RAG-Q1", "t0": "2026-04-30", "rule_id": "R2"},
    )
    assert response.status_code == 409
    assert "不属于规则" in response.json()["detail"]


def test_rag_no_hit_is_only_a_gap_candidate_and_never_auto_syncs() -> None:
    response = client.post(
        "/api/rag/retrieve",
        json={
            "question_id": "RAG-Q1",
            "t0": "2026-04-30",
            "rule_id": "R1",
            "company_name": "另一个未入库公司",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_hit"
    assert body["results"] == []
    assert body["evidence_gap"]["status"] == "retrieval_no_hit"
    assert body["evidence_gap"]["auto_sync_to_risk_card"] is False
    assert "不能据此认定" in body["evidence_gap"]["message"]


def test_rag_retrieval_enforces_t0_and_logs_pages() -> None:
    response = client.post(
        "/api/rag/retrieve",
        json={"query": "营业收入 应收账款", "t0": "2024-04-18", "rule_id": "R1", "top_k": 4},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "hit"
    assert body["retrieval_id"].startswith("RET-")
    assert all(item["disclosure_date"] <= "2024-04-18" for item in body["results"])
    assert all(item["pdf_page"] >= 1 and item["source_sha256"] for item in body["results"])
    logged = client.get(f"/api/rag/retrievals/{body['retrieval_id']}")
    assert logged.status_code == 200


def test_rag_company_filter_prevents_cross_company_hits() -> None:
    response = client.post(
        "/api/rag/retrieve",
        json={
            "query": "营业收入",
            "t0": "2026-04-30",
            "rule_id": "R1",
            "company_name": "另一个未入库公司",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "no_hit"
    assert response.json()["results"] == []


def test_supplement_without_authorization_is_rejected() -> None:
    run = _create_run()
    response = client.post(
        "/api/supplements",
        data={
            "parent_run_id": run["run_id"],
            "material_type": "账龄明细",
            "authorized": "false",
            "desensitized": "true",
            "bound_rule_ids": "R1",
            "as_of_date": "2024-05-01",
            "structured_json": '{"ar_current": 300000000}',
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert any("授权" in issue for issue in response.json()["issues"])


def test_structured_supplement_can_rerun_only_bound_rule() -> None:
    run = _create_run()
    registered = client.post(
        "/api/supplements",
        data={
            "parent_run_id": run["run_id"],
            "material_type": "应收账款补充字段",
            "authorized": "true",
            "desensitized": "true",
            "bound_rule_ids": '["R1"]',
            "as_of_date": "2024-05-01",
            "structured_json": '{"ar_current": 300000000, "ar_previous": 439176425.31}',
        },
    )
    assert registered.status_code == 200
    body = registered.json()
    assert body["status"] == "ready_for_rerun"
    rerun = client.post(f"/api/supplements/{body['supplement_id']}/rerun", json={"check_model": False})
    assert rerun.status_code == 200
    rerun_body = rerun.json()
    assert rerun_body["run_id"].startswith("RUN-SUP-")
    assert rerun_body["context"]["supplement_id"] == body["supplement_id"]
    assert [result["rule_id"] for result in rerun_body["rule_results"]] == ["R1"]
    assert any(source.get("supplement_id") == body["supplement_id"] for source in rerun_body["sources"])


def test_unreviewed_run_cannot_cache_or_export() -> None:
    run = _create_run()
    assert client.post(f"/api/runs/{run['run_id']}/cache").status_code == 409
    assert client.get(f"/api/runs/{run['run_id']}/report.docx").status_code == 409


def test_reviewed_run_can_cache_replay_and_export_word() -> None:
    run = _create_run()
    reviewed = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={
            "status": "保留为待核查候选",
            "note": "仅用于系统回归测试。",
            "reviewer": "测试复核人",
            "export_approved": True,
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["human_review"]["reviewed_at"]
    cached = client.post(f"/api/runs/{run['run_id']}/cache")
    assert cached.status_code == 200
    replayed = client.post(f"/api/cache/{cached.json()['cache_id']}/replay")
    assert replayed.status_code == 200
    assert replayed.json()["model_check"]["status"] == "cache_replay"
    report = client.get(f"/api/runs/{run['run_id']}/report.docx")
    assert report.status_code == 200
    assert report.content[:2] == b"PK"
    assert "wordprocessingml.document" in report.headers["content-type"]
    assert Path(WORKSPACE_ROOT, "backend", "runtime", "pytest", "reports").exists()
