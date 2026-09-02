"""第四批：公网认证、租户边界、Supabase 配置与 worker 骨架验收。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from starlette.requests import Request

from backend.app import auth as auth_module
from backend.app import main as main_module
from backend.app.auth import UserIdentity, attach_identity, authorize_case_access, authorize_case_write, authorize_pipeline_task, is_public_case
from backend.app.pipeline import load_task, materialize_task
from backend.app.schemas import RunResponse
from backend.app.supabase_adapter import SupabaseAuthError, SupabaseConfig, SupabaseNotConfigured, SupabaseClient


ROOT = Path(__file__).resolve().parents[2]


def test_local_mode_keeps_offline_identity_and_all_cases_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    response = TestClient(main_module.app).get("/api/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["persistence"]["mode"] == "local"
    listing = TestClient(main_module.app).get("/api/cases")
    assert listing.status_code == 200


def test_supabase_mode_anonymous_public_boundary_does_not_claim_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    response = TestClient(main_module.app).get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    private_case = {"sample_type": "authorized_deidentified", "tenant_id": "tenant-a"}
    scope = {"type": "http", "headers": [], "client": ("test", 123), "method": "GET", "path": "/"}
    with pytest.raises(HTTPException) as caught:
        authorize_case_access(Request(scope), private_case)
    assert caught.value.status_code == 503


def test_supabase_config_never_treats_missing_url_as_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon")
    config = SupabaseConfig.from_env()
    assert config.is_supabase is True
    assert config.configured is False
    with pytest.raises(SupabaseNotConfigured):
        SupabaseClient(config)


def test_supabase_schema_contains_rls_storage_contract_and_lease_rpc() -> None:
    schema = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8")
    for table in (
        "organizations",
        "organization_members",
        "cases",
        "report_documents",
        "field_evidence",
        "rag_chunks",
        "analysis_runs",
        "pipeline_tasks",
        "model_transfer_consents",
        "audit_events",
    ):
        assert f"create table if not exists public.{table}" in schema
        assert f"alter table public.{table} enable row level security" in schema
    assert "create or replace function public.claim_pipeline_task" in schema
    assert "for update skip locked" in schema
    assert "audittrace-private" in schema
    assert "insert into storage.buckets" in schema
    assert "model_transfer_consents_active_idx" in schema


def test_render_declares_single_web_competition_demo_without_login_worker() -> None:
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "type: web" in render
    assert "type: worker" not in render
    assert "python -m backend.app.worker" not in render
    assert "key: AUDITTRACE_DEMO_MODE\n        value: \"true\"" in render
    assert "key: AUDITTRACE_PERSISTENCE\n        value: local" in render
    assert "key: AUDITTRACE_DEMO_TASK_PERSISTENCE\n        value: supabase" in render
    assert "key: AUDITTRACE_DEMO_EXECUTOR_MODE\n        value: web" in render
    assert "key: AUDITTRACE_PROVIDER_PROBE_ENABLED\n        value: \"true\"" in render
    assert "key: DEEPSEEK_MODEL\n        value: deepseek-v4-flash" in render
    # Service-role credentials are declared as Render secrets only; no value is
    # committed and no paid worker is activated by the current blueprint.
    assert "key: SUPABASE_SERVICE_ROLE_KEY" in render
    assert "sync: false" in render[render.index("key: SUPABASE_SERVICE_ROLE_KEY"):]


def test_worker_can_materialize_a_database_task_without_web_task_file(tmp_path: Path) -> None:
    task = materialize_task(tmp_path, "CNINFO-WORKER1234", {"company_query": "600000"}, attempt=2)
    assert task["task_id"] == "CNINFO-WORKER1234"
    assert task["attempt"] == 2
    assert load_task(tmp_path, "CNINFO-WORKER1234")["request"]["company_query"] == "600000"


def test_supabase_status_does_not_expose_local_private_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    private = {"case_id": "PRIVATE_CASE", "sample_type": "authorized_deidentified", "tenant_id": "tenant-a", "company_name": "内部企业", "documents": [], "available_years": []}
    public = {"case_id": "PUBLIC_CASE", "sample_type": "public", "company_name": "公开企业", "documents": [], "available_years": []}
    monkeypatch.setattr(main_module, "list_cases", lambda _root: [public, private])
    monkeypatch.setattr(main_module, "rag_status", lambda _root, _case_id: {"status": "not_ready", "chunk_count": 0})
    monkeypatch.setattr(SupabaseClient, "list_case_metadata", lambda _self, tenant_id=None: [])
    response = TestClient(main_module.app).get("/api/status")
    assert response.status_code == 200
    assert [item["case_id"] for item in response.json()["cases"]] == ["PUBLIC_CASE"]


def test_tenant_owned_manifest_cannot_bypass_private_case_gate() -> None:
    assert is_public_case({"sample_type": "public"}) is True
    assert is_public_case({"sample_type": "public", "tenant_id": "tenant-a"}) is False


class _FakeSessionClient:
    """在进程内模拟 Supabase Auth 与远程运行存储，不接触外网。"""

    def __init__(self) -> None:
        self.refreshed_with: str | None = None
        self.persisted_run: dict[str, Any] | None = None
        self.objects: dict[str, bytes] = {}
        self.run_caches: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _session(access: str, refresh: str) -> dict[str, Any]:
        return {"access_token": access, "refresh_token": refresh, "expires_in": 3600}

    def sign_in_with_password(self, *, email: str, password: str) -> dict[str, Any]:
        assert email == "owner@example.test"
        assert password == "correct-password"
        return self._session("access-login", "refresh-login")

    def refresh_session(self, *, refresh_token: str) -> dict[str, Any]:
        self.refreshed_with = refresh_token
        return self._session("access-rotated", "refresh-rotated")

    def verify_user(self, access_token: str) -> dict[str, Any]:
        assert access_token in {"access-login", "access-rotated"}
        return {"id": "user-1", "email": "owner@example.test"}

    def list_memberships(self, user_id: str, *, token: str) -> list[dict[str, Any]]:
        assert user_id == "user-1"
        return [{"organization_id": "tenant-1", "role": "owner", "active": True}]

    def get_analysis_run(self, run_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
        if self.persisted_run is None:
            return None
        payload = self.persisted_run
        run = payload.get("run") if isinstance(payload.get("run"), dict) else payload
        return {"run_id": run_id, "case_id": run["context"]["case_id"], "tenant_id": "tenant-1", "payload": payload}

    def persist_run(
        self,
        *,
        run: dict[str, Any],
        tenant_id: str | None,
        case_id: str,
        case_tenant_id: str | None,
        pipeline_task_id: str | None = None,
    ) -> dict[str, Any]:
        assert case_id == "REMOTE_CASE"
        assert tenant_id == "tenant-1"
        assert case_tenant_id == "tenant-1"
        self.persisted_run = run
        nested = run.get("run") if isinstance(run.get("run"), dict) else run
        return {"backend": "supabase", "run_id": nested["run_id"]}

    def persist_run_cache(self, **values: Any) -> dict[str, Any]:
        self.run_caches[str(values["cache_id"])] = dict(values)
        return dict(values)

    def get_run_cache(self, *, cache_id: str, tenant_id: str) -> dict[str, Any] | None:
        row = self.run_caches.get(cache_id)
        return row if row and row.get("tenant_id") == tenant_id else None

    def upload_private_object(self, *, bucket: str, object_path: str, content: bytes, content_type: str) -> None:
        assert bucket == "audittrace-private"
        assert content_type == "application/json"
        self.objects[object_path] = content

    def download_private_object(self, *, bucket: str, object_path: str) -> bytes:
        assert bucket == "audittrace-private"
        return self.objects[object_path]


def _enable_mock_supabase(monkeypatch: pytest.MonkeyPatch, fake: _FakeSessionClient) -> None:
    """让 main/auth 共享同一个受控假客户端，避免测试误发网络请求。"""

    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(auth_module, "get_supabase_client", lambda: fake)


def test_http_only_login_refresh_logout_contract_never_returns_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    client = TestClient(main_module.app, base_url="https://testserver")

    login = client.post("/api/auth/login", json={"email": "OWNER@example.test", "password": "correct-password"})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["tenant_id"] == "tenant-1"
    assert "access-login" not in login.text and "refresh-login" not in login.text and "correct-password" not in login.text
    cookies = login.headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert all("HttpOnly" in value and "Secure" in value and "SameSite=lax" in value for value in cookies)
    assert client.get("/api/auth/me").json()["authenticated"] is True

    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert fake.refreshed_with == "refresh-login"
    assert "access-rotated" not in refreshed.text and "refresh-rotated" not in refreshed.text
    logged_out = client.post("/api/auth/logout")
    assert logged_out.status_code == 200
    assert logged_out.json()["authenticated"] is False
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_local_supabase_http_requires_explicit_insecure_cookie_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "false")
    monkeypatch.setenv("AUDITTRACE_COOKIE_SECURE", "false")
    client = TestClient(main_module.app, base_url="http://testserver")
    login = client.post("/api/auth/login", json={"email": "owner@example.test", "password": "correct-password"})
    assert login.status_code == 200
    assert login.json()["session"]["cookie_secure"] is False
    assert all("Secure" not in value for value in login.headers.get_list("set-cookie"))
    assert client.get("/api/auth/me").json()["authenticated"] is True


def test_public_demo_ignores_insecure_cookie_override(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_COOKIE_SECURE", "false")
    login = TestClient(main_module.app, base_url="https://testserver").post(
        "/api/auth/login",
        json={"email": "owner@example.test", "password": "correct-password"},
    )
    assert login.status_code == 200
    assert login.json()["session"]["cookie_secure"] is True
    assert all("Secure" in value for value in login.headers.get_list("set-cookie"))


def test_invalid_refresh_actually_sends_both_cookie_deletions(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    client = TestClient(main_module.app, base_url="https://testserver")
    assert client.post("/api/auth/login", json={"email": "owner@example.test", "password": "correct-password"}).status_code == 200

    def reject_refresh(*, refresh_token: str) -> dict[str, Any]:
        assert refresh_token == "refresh-login"
        raise SupabaseAuthError("invalid")

    fake.refresh_session = reject_refresh  # type: ignore[method-assign]
    rejected = client.post("/api/auth/refresh")
    assert rejected.status_code == 401
    deletions = rejected.headers.get_list("set-cookie")
    assert len(deletions) == 2
    assert all("Max-Age=0" in value and "HttpOnly" in value and "Secure" in value for value in deletions)
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_local_mode_auth_mutations_return_clear_not_applicable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    client = TestClient(main_module.app)
    assert client.post("/api/auth/login", json={"email": "owner@example.test", "password": "x"}).status_code == 409
    assert client.post("/api/auth/refresh").status_code == 409
    assert client.post("/api/auth/logout").status_code == 409


def test_public_case_mutation_requires_login_and_write_role(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    public_case = {"case_id": "PUBLIC_CASE", "sample_type": "public"}
    scope = {"type": "http", "headers": [], "client": ("test", 123), "method": "POST", "path": "/"}
    with pytest.raises(HTTPException) as anonymous:
        authorize_case_write(Request(scope), public_case)
    assert anonymous.value.status_code == 401

    member_request = Request(scope)
    attach_identity(member_request, UserIdentity(user_id="member", tenant_id="tenant-1", role="member"))
    with pytest.raises(HTTPException) as read_only:
        authorize_case_write(member_request, public_case)
    assert read_only.value.status_code == 403

    reviewer_request = Request(scope)
    reviewer = UserIdentity(user_id="reviewer", tenant_id="tenant-1", role="reviewer")
    attach_identity(reviewer_request, reviewer)
    assert authorize_case_write(reviewer_request, public_case) == reviewer


def test_pipeline_task_requires_exact_tenant_and_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    scope = {"type": "http", "headers": [], "client": ("test", 123), "method": "GET", "path": "/"}
    task = {"task_id": "CNINFO-ONE", "tenant_id": "tenant-1", "requested_by": "user-1"}
    owner_request = Request(scope)
    owner = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner")
    attach_identity(owner_request, owner)
    assert authorize_pipeline_task(owner_request, task) == owner

    other_request = Request(scope)
    attach_identity(other_request, UserIdentity(user_id="user-2", tenant_id="tenant-1", role="owner"))
    with pytest.raises(HTTPException) as hidden:
        authorize_pipeline_task(other_request, task)
    assert hidden.value.status_code == 404


def test_remote_run_can_be_reviewed_cached_exported_and_reloaded_on_fresh_web(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    monkeypatch.setattr(main_module, "WORKSPACE_ROOT", tmp_path)
    case = {"case_id": "REMOTE_CASE", "sample_type": "authorized_deidentified", "tenant_id": "tenant-1"}
    identity = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner")
    monkeypatch.setattr(main_module, "_case_record", lambda _case_id, **_kwargs: case)
    monkeypatch.setattr(main_module, "_remote_case_for_run", lambda _case_id, **_kwargs: case)
    monkeypatch.setattr(main_module, "authorize_case_access", lambda _request, _case: identity)
    monkeypatch.setattr(main_module, "authorize_case_write", lambda _request, _case: identity)
    run = RunResponse(
        run_id="RUN-REMOTE-ONE",
        status="candidate",
        context={"case_id": "REMOTE_CASE", "run_schema_version": "run_output_v2", "configured_parameters": {}},
        source_validation={},
        sources=[],
        rule_results=[],
        model_check={"status": "not_configured", "detail": "mock"},
        run_completeness="complete_full_analysis",
    )
    fake.persisted_run = run.model_dump(mode="json")
    monkeypatch.setenv("AUDITTRACE_RUNTIME_NAMESPACE", "remote-web-a")
    client = TestClient(main_module.app, headers={"Authorization": "Bearer access-login"})
    assert client.get("/api/runs/RUN-REMOTE-ONE").status_code == 200
    reviewed = client.post(
        "/api/runs/RUN-REMOTE-ONE/review",
        json={"status": "保留为待核查候选", "reviewer": "测试复核人", "reviewer_type": "human", "export_approved": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert fake.persisted_run and fake.persisted_run["human_review"]["reviewer"] == "测试复核人"

    # 切换命名空间模拟全新 web 磁盘；后续链必须仅依赖远程 payload 回源。
    monkeypatch.setenv("AUDITTRACE_RUNTIME_NAMESPACE", "remote-web-b")
    restored = client.get("/api/runs/RUN-REMOTE-ONE")
    assert restored.status_code == 200
    assert restored.json()["human_review"]["export_approved"] is True
    assert client.post("/api/runs/RUN-REMOTE-ONE/cache").status_code == 200
    report = client.get("/api/runs/RUN-REMOTE-ONE/report.docx")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_supplement_record_round_trips_through_private_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    identity = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner")
    record = {"supplement_id": "SUP-REMOTE123", "tenant_id": "tenant-1", "parent_run_id": "RUN-REMOTE-ONE"}
    main_module._persist_supplement_record_remote(record, "tenant-1")
    monkeypatch.setattr(main_module, "load_supplement", lambda _root, _supplement_id: None)
    assert main_module._load_supplement_record("SUP-REMOTE123", identity) == record


def test_remote_supplement_rerun_reuses_parent_evidence_without_local_case_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = _FakeSessionClient()
    _enable_mock_supabase(monkeypatch, fake)
    monkeypatch.setattr(main_module, "WORKSPACE_ROOT", tmp_path)
    identity = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner")
    case = {"case_id": "REMOTE_CASE", "sample_type": "authorized_deidentified", "tenant_id": "tenant-1"}
    parent_source = {
        "field_id": "revenue_current",
        "field_label": "本年营业收入",
        "field_kind": "revenue",
        "year": 2024,
        "value": 100.0,
        "evidence_id": "REMOTE-REV-2024",
    }
    parent = RunResponse(
        run_id="RUN-REMOTE-PARENT",
        status="candidate",
        context={
            "case_id": "REMOTE_CASE",
            "current_year": 2024,
            "t0": "2025-04-30",
            "source_snapshot_id": "snapshot-1",
            "run_schema_version": "run_output_v2",
            "configured_parameters": {
                "r2_min_gap": 0.0,
                "planned_materiality": None,
                "r1_gap_threshold": 0.15,
                "r1_strong_gap_threshold": 0.30,
                "r1_absolute_threshold": 0.0,
            },
        },
        source_validation={},
        sources=[parent_source],
        rule_results=[],
        model_check={"status": "not_configured", "detail": "mock"},
    )
    fake.persisted_run = parent.model_dump(mode="json")
    record = {
        "supplement_id": "SUP-REMOTERERUN",
        "parent_run_id": "RUN-REMOTE-PARENT",
        "tenant_id": "tenant-1",
        "status": "ready_for_rerun",
        "bound_rule_ids": ["R1"],
        "structured_fields": {},
        "structured_evidence": [{"evidence_id": "SUP-E01", "support_status": "pending_human_confirmation"}],
        "original_filename": "structured.json",
        "as_of_date": "2025-05-31",
        "file_sha256": "A" * 64,
    }
    main_module._persist_supplement_record_remote(record, "tenant-1")
    monkeypatch.setattr(main_module, "require_authenticated", lambda _request: identity)
    monkeypatch.setattr(main_module, "authorize_case_write", lambda _request, _case: identity)
    monkeypatch.setattr(main_module, "authorize_model_transfer", lambda _request, _case: False)
    monkeypatch.setattr(main_module, "_case_record", lambda _case_id, **_kwargs: case)
    captured: dict[str, Any] = {}

    def execute_mock(**kwargs: Any) -> RunResponse:
        captured.update(kwargs)
        return RunResponse(
            run_id="RUN-SUP-REMOTE",
            status="candidate",
            context=kwargs["context"],
            source_validation={},
            sources=kwargs["sources"],
            rule_results=[],
            model_check={"status": "not_configured", "detail": "mock"},
        )

    monkeypatch.setattr(main_module, "_execute_run", execute_mock)
    response = TestClient(main_module.app).post(
        "/api/supplements/SUP-REMOTERERUN/rerun",
        json={"run_mode": "calculation_only"},
    )
    assert response.status_code == 200, response.text
    assert captured["sources"] == [parent_source]
    assert captured["context"]["original_t0"] == "2025-04-30"
    assert captured["context"]["supplement_as_of_date"] == "2025-05-31"


@pytest.mark.parametrize(
    "parameters",
    [
        {"r2_min_gap": None},
        {"r1_gap_threshold": "not-a-number"},
        {"r1_strong_gap_threshold": float("nan")},
        {"r1_absolute_threshold": float("inf")},
    ],
)
def test_legacy_supplement_parameters_fail_with_stable_conflict(parameters: dict[str, Any]) -> None:
    with pytest.raises(HTTPException) as caught:
        main_module._validated_rerun_parameters(parameters)
    assert caught.value.status_code == 409
