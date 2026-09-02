"""真实外部三 Agent 成功率窗口与告警口径。"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from backend.app.model_quality import is_external_three_agent_run, quality_snapshot, record_external_run


def _response(run_id: str, *, status: str = "model_success", mode: str = "external_live", roles: tuple[str, ...] = ("challenge", "counter", "review")):
    return SimpleNamespace(
        run_id=run_id,
        execution_mode=mode,
        model_id="deepseek-v4-flash-vision-exp",
        model_check=SimpleNamespace(status=status, provider_call_count=3, model_id="deepseek-v4-flash-vision-exp"),
        agent_steps=[SimpleNamespace(role=role, status="completed" if status == "model_success" else "provider_unavailable", provider_call_performed=True) for role in roles],
    )


def test_quality_excludes_replay_and_deterministic_runs(tmp_path: Path):
    assert not is_external_three_agent_run(_response("REPLAY", mode="cache_replay"))
    assert not is_external_three_agent_run(_response("BACKUP", mode="deterministic_backup"))
    assert is_external_three_agent_run(_response("LIVE"))


def test_quality_does_not_write_pytest_provider_mocks(tmp_path: Path, monkeypatch):
    workspace = tmp_path
    (workspace / "backend").mkdir()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "synthetic-provider-run")
    snapshot = record_external_run(workspace, _response("TEST-MOCK"))
    assert snapshot is not None and snapshot["sample_count"] == 0
    assert not (workspace / "backend" / "runtime" / "model-quality.json").exists()


def test_quality_alerts_below_eighty_percent_and_is_idempotent(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # model_quality resolves from workspace root; use a temporary root-shaped directory.
    workspace = tmp_path
    (workspace / "backend").mkdir()
    for index in range(5):
        record_external_run(workspace, _response(f"FAIL-{index}", status="provider_unavailable", roles=("challenge",)), allow_test_recording=True)
    for index in range(4):
        record_external_run(workspace, _response(f"PASS-{index}"), allow_test_recording=True)
    snapshot = record_external_run(workspace, _response("PASS-4"), allow_test_recording=True)
    assert snapshot is not None
    assert snapshot["sample_count"] == 10
    assert snapshot["success_count"] == 5
    assert snapshot["alert"] is True
    record_external_run(workspace, _response("PASS-4"), allow_test_recording=True)
    assert quality_snapshot(workspace)["sample_count"] == 10


def test_quality_excludes_legacy_rows_without_current_profile(tmp_path: Path):
    workspace = tmp_path
    ledger = workspace / "backend" / "runtime"
    ledger.mkdir(parents=True)
    (ledger / "model-quality.json").write_text(
        '[{"run_id":"OLD-1","model_id":"deepseek-v4-flash","success":true,"provider_call_count":3}]',
        encoding="utf-8",
    )
    snapshot = quality_snapshot(workspace, model_id="deepseek-v4-flash")
    assert snapshot["status"] == "unmeasured"
    assert snapshot["sample_count"] == 0
