"""杰克科技公开案例包的导入、勾稽、R1 反例和 RAG 隔离复验。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.cases import get_period_sources, import_case_zip
from backend.app.main import _r1_result
from backend.app.rag import _runtime_dir, prepare_index, retrieve


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    PROJECT_ROOT
    / "02_最终确定方案"
    / "07_杰克科技第二公开案例_2026-07-28"
    / "杰克科技_603337_公开案例包_2022-2024.zip"
)


def test_jack_public_case_imports_and_is_a_traceable_r1_negative_control(tmp_path: Path) -> None:
    case = import_case_zip(
        tmp_path,
        PACKAGE.read_bytes(),
        authorized=True,
        desensitized=True,
    )
    assert case["case_id"] == "JACK_603337_T0_20250415"
    assert case["model_transfer_allowed"] is False
    assert case["retention_expires_at"] == "2026-12-31"
    assert "AI生成内容" in case["ai_generated_content_notice"]
    assert len(case["structured_evidence"]) == 12
    assert case["material_gaps"] == ["期后回款", "信用政策变动", "主要客户合同结算条款"]

    context, sources = get_period_sources(tmp_path, case["case_id"], 2024, ("R1",))
    result = _r1_result(sources, [], planned_materiality=10_000_000)
    assert result.status == "RULE_NOT_TRIGGERED"
    assert result.metrics["revenue_growth"] == pytest.approx(0.151074515, abs=1e-8)
    assert result.metrics["ar_growth"] == pytest.approx(0.037934121, abs=1e-8)
    assert context["case_evidence_count"] == 12

    index = prepare_index(tmp_path, case_id=case["case_id"], force=True)
    assert index["status"] == "ready" and index["source_count"] == 3
    rag_root = _runtime_dir(tmp_path, case["case_id"])
    active = json.loads((rag_root / "active.json").read_text(encoding="utf-8"))
    version_dir = rag_root / "versions" / active["version"]
    assert (version_dir / "rag.sqlite3").is_file()
    assert (version_dir / "rag.faiss").is_file()
    assert (version_dir / "manifest.json").is_file()
    retrieval = retrieve(
        tmp_path,
        case_id=case["case_id"],
        company_name=case["company_name"],
        query="应收账款 账龄 坏账准备",
        t0=case["t0"],
        rule_id="R1",
        top_k=3,
    )
    assert retrieval["status"] == "hit"
    assert retrieval["filter"]["case_id"] == case["case_id"]
    assert all(item["chunk_id"].startswith(case["case_id"]) for item in retrieval["results"])
