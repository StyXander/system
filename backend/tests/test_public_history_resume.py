"""服务重启后公开任务结果续接，不重新调用模型或扩大私有访问范围。"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import main
from backend.app.supabase_adapter import SupabaseClient

RUN_ID = "RUN-V7-FFFFFFFFFFFF"


@pytest.fixture
def history(monkeypatch, tmp_path):
    payload = json.loads((Path(__file__).parent / "fixtures/run_contract_mock.json").read_text(encoding="utf-8"))
    payload["run_id"] = RUN_ID
    payload["context"].pop("request_identity", None)
    row = {"run_id": RUN_ID, "case_id": payload["context"]["case_id"], "result": payload}
    calls, saved = [], []
    monkeypatch.setattr(main, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(main, "supabase_enabled", lambda: False)
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setattr(main, "demo_task_supabase_enabled", lambda: True)
    monkeypatch.setattr(main, "get_demo_task_client", lambda: SimpleNamespace(
        find_completed_demo_run=lambda run_id: calls.append(run_id) or row))
    monkeypatch.setattr(main, "load_run", lambda *_: None)
    monkeypatch.setattr(main, "save_run", lambda root, run: saved.append(run))
    monkeypatch.setattr(main, "_case_record", lambda _: {"sample_type": "public"})
    return row, calls, saved


def test_completed_public_result_restores_exact_parent(history):
    row, calls, saved = history
    stored, owner = main._load_stored_run_record(RUN_ID)
    assert calls == [RUN_ID] and owner is None
    assert stored.run.model_dump(mode="json") == main.RunResponse.model_validate(row["result"]).model_dump(mode="json")
    assert saved == [stored.run]


@pytest.mark.parametrize("invalid", ["run_id", "case_id", "tenant", "private_case"])
def test_history_resume_rejects_foreign_result(history, monkeypatch, invalid):
    row, _, saved = history
    if invalid == "run_id":
        row["result"]["run_id"] = "RUN-V7-AAAAAAAAAAAA"
    elif invalid == "case_id":
        row["case_id"] = "ANOTHER_CASE"
    elif invalid == "tenant":
        row["result"]["context"]["request_identity"] = {"tenant_id": "private-team"}
    else:
        monkeypatch.setattr(main, "_case_record", lambda _: {"sample_type": "public", "tenant_id": "private-team"})
    assert main._load_stored_run_record(RUN_ID) is None
    assert saved == []


def test_history_resume_only_operates_in_anonymous_public_demo(history, monkeypatch):
    _, calls, saved = history
    assert main._load_stored_run_record(RUN_ID, owner_tenant_id="team") is None
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "false")
    assert main._load_stored_run_record(RUN_ID) is None
    assert calls == saved == []


def test_history_lookup_excludes_unfinished_and_expired_tasks(monkeypatch):
    observed = {}
    def select(self, table, **kwargs):
        observed.update(table=table, **kwargs)
        return []
    monkeypatch.setattr(SupabaseClient, "select_table", select)
    assert SupabaseClient.find_completed_demo_run(SupabaseClient.__new__(SupabaseClient), RUN_ID) is None
    assert observed["table"] == "demo_run_tasks" and observed["service"] is True
    assert observed["filters"]["run_id"] == "eq." + RUN_ID
    assert observed["filters"]["status"] == "in.(completed,degraded)"
    assert observed["filters"]["result_expires_at"].startswith("gt.")
