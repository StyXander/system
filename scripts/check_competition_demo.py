"""验收竞赛 Demo 的 50 家案例、样例补充资料与免登录报告主链。"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["AUDITTRACE_DEMO_MODE"] = "true"
os.environ["AUDITTRACE_PUBLIC_DEMO"] = "true"
os.environ["AUDITTRACE_PERSISTENCE"] = "local"
os.environ["AUDITTRACE_DEMO_USE_EXTERNAL_MODEL"] = "false"
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ.setdefault("AUDITTRACE_RUNTIME_NAMESPACE", "competition-demo-contract")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


def main() -> None:
    client = TestClient(app)
    status = client.get("/api/status")
    status.raise_for_status()
    assert status.json()["demo_mode"]["enabled"] is True
    assert status.json()["demo_mode"]["login_required"] is False

    listing = client.get("/api/cases")
    listing.raise_for_status()
    cases = [row for row in listing.json()["cases"] if str(row.get("case_id", "")).startswith("CNINFO_")]
    by_ticker = {str(row.get("ticker") or ""): row for row in cases if row.get("ticker")}
    assert len(by_ticker) == 50, f"预期 50 家演示企业，实际 {len(by_ticker)} 家。"

    run_statuses: Counter[str] = Counter()
    parent_run: dict | None = None
    full_demo_case: dict | None = None
    for case in by_ticker.values():
        years = [
            int(year)
            for year in (case.get("available_years") or case.get("available_report_years") or [])
        ]
        if not years:
            years = [
                int(document["report_year"])
                for document in case.get("documents", [])
                if document.get("report_year") is not None
            ]
        assert years, f"{case['company_name']} 没有可运行年度。"
        response = client.post(
            "/api/runs",
            json={
                "case_id": case["case_id"],
                "current_year": max(years),
                "scene": "审计计划",
                "rule_ids": ["R1"],
                "run_mode": "calculation_only",
            },
        )
        assert response.status_code == 200, f"{case['company_name']} 运行失败：{response.text}"
        body = response.json()
        assert "SOURCE_INCOMPLETE" not in json.dumps(body, ensure_ascii=False), case["company_name"]
        run_statuses[str(body.get("status") or "unknown")] += 1
        if body.get("status") == "candidate" and full_demo_case is None:
            full_demo_case = case
        if str(case.get("ticker")) == "601628":
            parent_run = body

    assert parent_run is not None, "50 家目录中缺少中国人寿 601628。"
    assert full_demo_case is not None, "50 家目录中没有可验证完整演示草稿的候选企业。"

    rag_checked = 0
    for case in by_ticker.values():
        t0 = str(case.get("t0") or "2026-04-30")
        rag = client.post(
            "/api/rag/retrieve",
            json={
                "case_id": case["case_id"],
                "company_name": case.get("company_name"),
                "query": "应收账款",
                "t0": t0,
                "rule_id": "R1",
                "top_k": 3,
            },
        )
        assert rag.status_code == 200, f"{case['company_name']} RAG 检索失败：{rag.text}"
        rag_body = rag.json()
        assert rag_body.get("results") or rag_body.get("status") == "no_hit", case["company_name"]
        rag_checked += 1

    full_years = [
        int(year)
        for year in (full_demo_case.get("available_years") or full_demo_case.get("available_report_years") or [])
    ]
    full = client.post(
        "/api/runs",
        json={
            "case_id": full_demo_case["case_id"],
            "current_year": max(full_years),
            "scene": "审计计划",
            "rule_ids": ["R1"],
            "run_mode": "full_analysis",
        },
    )
    full.raise_for_status()
    full_body = full.json()
    assert full_body["model_check"]["status"] == "demo_fallback"
    assert full_body["run_completeness"].startswith("complete_")
    assert full_body["execution_mode"] == "deterministic_backup"
    assert full_body["final_ai_draft"] and len(full_body["final_ai_draft"]["items"]) >= 1
    registered = client.post(
        "/api/supplements/from-sample",
        json={
            "parent_run_id": parent_run["run_id"],
            "sample_id": "aging",
            "bound_rule_ids": ["R1"],
            "note": "仅用于比赛演示的公开样例补充资料。",
        },
    )
    registered.raise_for_status()
    supplement = registered.json()
    assert supplement["status"] == "ready_for_rerun"
    assert supplement["authorized"] is True and supplement["desensitized"] is True

    rerun = client.post(
        f"/api/supplements/{supplement['supplement_id']}/rerun",
        json={"run_mode": "calculation_only"},
    )
    rerun.raise_for_status()
    rerun_body = rerun.json()
    assert len(rerun_body["evidence_bundle"]["supplement_evidence"]) == 1
    assert rerun_body["context"]["recommendation_change"]

    report = client.get(f"/api/runs/{rerun_body['run_id']}/report.docx")
    report.raise_for_status()
    assert report.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert report.content.startswith(b"PK") and len(report.content) > 10_000

    print(
        json.dumps(
            {
                "demo_mode": True,
                "login_required": False,
                "company_count": len(by_ticker),
                "run_statuses": dict(run_statuses),
                "source_incomplete": 0,
                "rag_checked": rag_checked,
                "full_demo_case": full_demo_case["case_id"],
                "full_model_status": full_body["model_check"]["status"],
                "supplement_evidence": 1,
                "report_bytes": len(report.content),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
