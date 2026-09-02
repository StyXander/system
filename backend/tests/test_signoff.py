"""R1 v0.4 签字加载器测试：状态解析、哈希校验、配置一致性。

不修改真实签字文件；通过 monkeypatch 指向临时记录，并替换文件哈希函数，
保证测试不依赖工作区磁盘上的正式签字记录。
"""

from __future__ import annotations

import hashlib
import json

import pytest

from backend.app import signoff
from backend.app.signoff import (
    SIGNOFF_RECORD_STATUS,
    SIGNOFF_STALE_STATUS,
    current_r1_config_canonical,
    load_signoff_status,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_record(*, status: str = SIGNOFF_RECORD_STATUS, rule_version: str = "0.4") -> dict:
    thresholds = {"r1_absolute_threshold": 0.0, "r1_gap_threshold": 0.15, "r1_strong_gap_threshold": 0.3}
    config_canonical = current_r1_config_canonical()
    signed_payload = json.dumps(
        {
            "approved_assertion_mapping": {
                "accounts_receivable": ["存在", "计价和分摊"],
                "revenue": ["发生", "截止", "准确性"],
            },
            "approved_thresholds": thresholds,
            "confirmation_source": "codex_user_explicit_confirmation",
            "rule_id": "R1",
            "rule_version": rule_version,
            "scope": "竞赛演示版、销售与收款循环、审计计划阶段风险预筛",
            "signed_at": "2026-08-25",
            "signed_by_role": "项目队长（用户本人）",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "schema_version": "professional_signoff_v1",
        "signoff_id": "SIGNOFF-R1-V0.4-20260825-CAPTAIN",
        "rule_id": "R1",
        "rule_version": rule_version,
        "signed_by_role": "项目队长（用户本人）",
        "signer_name": None,
        "signed_at": "2026-08-25",
        "confirmation_source": "codex_user_explicit_confirmation",
        "status": status,
        "scope": "竞赛演示版、销售与收款循环、审计计划阶段风险预筛",
        "approved_thresholds": thresholds,
        "approved_assertion_mapping": {
            "revenue": ["发生", "截止", "准确性"],
            "accounts_receivable": ["存在", "计价和分摊"],
        },
        "rule_config_canonical": config_canonical,
        "rule_config_sha256": _sha(config_canonical),
        "signed_payload_canonical": signed_payload,
        "signed_payload_sha256": _sha(signed_payload),
        "signoff_record_sha256": _sha(signed_payload),
        "signoff_record_hash_scope": "UTF-8 bytes of signed_payload_canonical",
        "source_file_sha256": {"backend/app/schemas.py": "fake-schema-hash"},
    }


@pytest.fixture()
def signoff_file(tmp_path, monkeypatch):
    """把签字文件指向临时记录，并固定源文件哈希函数，返回写记录的辅助函数。"""
    target = tmp_path / "R1-v0.4-captain-signoff-20260825.json"
    monkeypatch.setattr(signoff, "SIGNOFF_FILE", target)
    monkeypatch.setattr(signoff, "_sha256_file", lambda _path: "fake-schema-hash")

    def write(record: dict) -> None:
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    return write


def test_signoff_missing_record(tmp_path, monkeypatch):
    monkeypatch.setattr(signoff, "SIGNOFF_FILE", tmp_path / "does-not-exist.json")
    result = load_signoff_status()
    assert result["signoff_status"] == "no_signoff_record"
    assert "未找到" in result["reason"]


def test_signoff_invalid_json(signoff_file, tmp_path, monkeypatch):
    monkeypatch.setattr(signoff, "SIGNOFF_FILE", tmp_path / "bad.json")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    result = load_signoff_status()
    assert result["signoff_status"] == SIGNOFF_STALE_STATUS
    assert "无法解析" in result["reason"]


def test_signoff_approved_when_consistent(signoff_file):
    signoff_file(_make_record())
    result = load_signoff_status()
    assert result["signoff_status"] == SIGNOFF_RECORD_STATUS
    assert result["signoff_id"] == "SIGNOFF-R1-V0.4-20260825-CAPTAIN"
    assert result["signed_by_role"] == "项目队长（用户本人）"
    assert result["approved_thresholds"]["r1_gap_threshold"] == 0.15
    assert result["approved_assertion_mapping"]["revenue"] == ["发生", "截止", "准确性"]


def test_signoff_tampered_payload_is_stale(signoff_file):
    record = _make_record()
    record["signed_payload_canonical"] = record["signed_payload_canonical"].replace("R1", "R9")
    signoff_file(record)
    result = load_signoff_status()
    assert result["signoff_status"] == SIGNOFF_STALE_STATUS
    assert "哈希不一致" in result["reason"]


def test_signoff_rule_version_change_is_stale(signoff_file, monkeypatch):
    # 先按当前版本生成记录，再模拟代码 R1 版本变化：
    # 签字配置规范串由代码生成，版本变化后与记录不一致即视为需要重新确认。
    signoff_file(_make_record())
    monkeypatch.setattr(signoff, "current_rule_version", lambda: "0.5")
    result = load_signoff_status()
    assert result["signoff_status"] == SIGNOFF_STALE_STATUS
    assert "配置" in result["reason"]


def test_signoff_unapproved_status_is_stale(signoff_file):
    signoff_file(_make_record(status="draft_pending"))
    result = load_signoff_status()
    assert result["signoff_status"] == SIGNOFF_STALE_STATUS
    assert "状态不是已批准" in result["reason"]


def test_signoff_source_file_change_is_stale(signoff_file, monkeypatch):
    monkeypatch.setattr(signoff, "_sha256_file", lambda _path: "changed-hash")
    signoff_file(_make_record())
    result = load_signoff_status()
    assert result["signoff_status"] == SIGNOFF_STALE_STATUS
    assert "源文件" in result["reason"]


def test_signoff_missing_required_field_is_stale(signoff_file):
    record = _make_record()
    del record["signed_at"]
    signoff_file(record)
    result = load_signoff_status()
    assert result["signoff_status"] == SIGNOFF_STALE_STATUS
    assert "缺少必要字段" in result["reason"]


def test_signoff_status_endpoint_exposes_snapshot():
    """/api/status 必须带 signoff 快照，且不允许把批准写成专业标准。"""
    from fastapi.testclient import TestClient

    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert "signoff" in payload
    assert payload["signoff"]["rule_id"] == "R1"
    assert "boundary" in payload["signoff"]
    assert payload["signoff"]["signoff_status"] in {
        SIGNOFF_RECORD_STATUS,
        SIGNOFF_STALE_STATUS,
        "no_signoff_record",
    }
    assert "注册会计师" not in payload["signoff"]["signoff_status"]


def test_current_r2_signoff_requires_reapproval_after_rule_changes():
    """规则合同已变更时，当前签字必须 fail-closed。"""
    current = load_signoff_status()
    assert current["signoff_status"] == SIGNOFF_STALE_STATUS
    assert "重新确认" in current["reason"]
    assert current["signoff_id"] == "SIGNOFF-R1-V0.4-20260825-CAPTAIN-R2"
    assert signoff.SIGNOFF_FILE.name == "r1_signoff_20260825_r2.json"


def test_superseded_captain_signoff_remains_traceable():
    """被取代的队长签字原件必须仍在磁盘上可追溯。

    该原件在团队内部 outputs/ 签字目录里，按交付边界不随任何代码包分发；
    所以在清洁包中如实记为 skip，而不是把内部证据塞进包里或删掉这项检查。
    """
    legacy = signoff.SIGNOFF_DIR / "R1-v0.4-captain-signoff-20260825.json"
    if not legacy.is_file():
        pytest.skip("内部签字原件不随交付包分发，仅在源码仓库可追溯")
    assert legacy.is_file()
