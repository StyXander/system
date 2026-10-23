"""反证循环：状态只能由条件门禁改变，且必须保留证据与前后差异。"""
from __future__ import annotations

from backend.app.connectivity_financial_bridge import build
from backend.app.connectivity_revision import STATE_MACHINE, build_revision_loop
from backend.tests.test_financial_bridge import _docs, _pages


def _revision():
    return build_revision_loop(build(None, documents=_docs(), pages=_pages(), industry="steel"))


def test_state_machine_is_complete():
    assert STATE_MACHINE[0] == "CLAIM_IDENTIFIED"
    assert STATE_MACHINE[-1] == "REVIEWED"
    assert "EVIDENCE_RETURNED" in STATE_MACHINE and "HYPOTHESIS_UPDATED" in STATE_MACHINE


def test_numeric_candidate_is_refuted_by_scope_and_definition_evidence():
    revision = _revision()
    assert revision["summary"]["refuted"] >= 1
    refuted = [item for item in revision["hypotheses"] if item["status"] == "refuted"]
    assert refuted
    transition = next(item for item in revision["transitions"]
                      if item["hypothesis_id"] == refuted[0]["hypothesis_id"])
    assert transition["before"] == "plausible" and transition["after"] == "refuted"
    assert transition["evidence_ids"]
    assert "定义" in transition["reason"] or "范围" in transition["reason"] or "口径" in transition["reason"]


def test_semantic_link_is_weakened_not_claimed_as_supported():
    revision = _revision()
    weakened = [item for item in revision["hypotheses"] if item["status"] == "weakened"]
    assert weakened
    assert all(item["source"] == "program_candidate" for item in weakened)


def test_model_note_enters_ledger_but_cannot_change_gate_state():
    bridge = build(None, documents=_docs(), pages=_pages(), industry="steel")
    revision = build_revision_loop(bridge, model_notes=[{
        "hypothesis_id": "MODEL-TEST", "explanation": "模型提出的竞争解释",
        "status": "supported", "claim_id": bridge["claims"][0]["claim_id"],
    }])
    note = next(item for item in revision["hypotheses"] if item["hypothesis_id"] == "MODEL-TEST")
    assert note["source"] == "model"
    assert note["status"] == "open" and note["reported_status"] == "supported"
    # 模型记录不产生门禁转移；转移列表里不应出现 MODEL-TEST 的 before/after。
    assert not [item for item in revision["transitions"] if item["hypothesis_id"] == "MODEL-TEST"]
