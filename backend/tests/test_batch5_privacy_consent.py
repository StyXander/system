"""第五批：内部资料保密、模型传输同意与敏感信息阻断验收。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app import auth as auth_module
from backend.app import main as main_module
from backend.app.agents import _compact_evidence_bundle, run_agent_chain
from backend.app.auth import UserIdentity, attach_identity, authorize_model_transfer
from backend.app.cases import get_period_sources
from backend.app.privacy import scan_sensitive_payload
from backend.app.schemas import RuleResult


@pytest.fixture(autouse=True)
def _standardize_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


class _FakeConsentClient:
    def __init__(self) -> None:
        self.consent: dict[str, Any] | None = None
        self.audit_events: list[dict[str, Any]] = []

    def get_active_model_transfer_consent(
        self,
        *,
        tenant_id: str,
        case_id: str,
        case_tenant_id: str | None,
        user_id: str,
        provider: str,
        model_id: str,
        transmission_scope: str,
    ) -> dict[str, Any] | None:
        row = self.consent
        if not row or row.get("revoked_at"):
            return None
        if (
            row.get("tenant_id") != tenant_id
            or row.get("case_id") != case_id
            or row.get("case_tenant_id") != case_tenant_id
            or row.get("user_id") != user_id
            or row.get("provider") != provider
            or row.get("model_id") != model_id
            or row.get("transmission_scope") != transmission_scope
        ):
            return None
        return row

    def create_model_transfer_consent(self, **kwargs: Any) -> dict[str, Any]:
        self.consent = {
            "id": str(uuid.uuid4()),
            **kwargs,
            "revoked_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return self.consent

    def get_model_transfer_consent(self, consent_id: str) -> dict[str, Any] | None:
        return self.consent if self.consent and self.consent.get("id") == consent_id else None

    def revoke_model_transfer_consent(self, *, consent_id: str, tenant_id: str, user_id: str) -> None:
        if self.consent and self.consent.get("id") == consent_id and self.consent.get("tenant_id") == tenant_id and self.consent.get("user_id") == user_id:
            self.consent["revoked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def record_audit_event(self, **kwargs: Any) -> None:
        self.audit_events.append(kwargs)

    def create_signed_url(self, *, bucket: str, object_path: str) -> str:
        return f"https://storage.example.test/{bucket}/signed/{object_path}?token=test"


def _request() -> Request:
    return Request({"type": "http", "headers": [], "method": "GET", "path": "/"})


def test_sensitive_scanner_returns_categories_and_never_echoes_matches() -> None:
    payload = {"note": "联系人13800138000，身份证11010519491231002X", "nested": {"card": "6222021234567890123"}}
    findings = scan_sensitive_payload(payload)
    serialized = json.dumps(findings, ensure_ascii=False)
    assert {item["kind"] for item in findings} == {"中国大陆手机号", "居民身份证号", "疑似银行卡号"}
    assert "13800138000" not in serialized
    assert "11010519491231002X" not in serialized
    assert "6222021234567890123" not in serialized


def test_model_payload_is_compact_and_never_contains_pdf_path_or_full_supplement_details() -> None:
    compact = _compact_evidence_bundle(
        {
            "field_evidence": [
                {
                    "evidence_id": "E-FIELD-01",
                    "value": 123,
                    "storage_relpath": "C:/private/report.pdf",
                    "details": {"full_pdf_text": "不得传输"},
                    "excerpt": "field excerpt",
                }
            ],
            "rag_evidence": [],
            "supplement_evidence": [
                {
                    "evidence_id": "SUP-01-E01",
                    "details": {"private_text": "内部全文不应进入模型请求"},
                    "source_file": "内部补充表.xlsx",
                    "excerpt": "x" * 800,
                }
            ],
        }
    )
    serialized = json.dumps(compact, ensure_ascii=False)
    assert "storage_relpath" not in serialized
    assert "full_pdf_text" not in serialized
    assert "private_text" not in serialized
    assert len(next(item for item in compact if item["evidence_id"] == "SUP-01-E01")["excerpt"]) == 500


def test_private_case_json_removes_original_source_url_but_public_case_keeps_official_url() -> None:
    private_case = {
        "case_id": "PRIVATE_CASE",
        "sample_type": "authorized_deidentified",
        "tenant_id": "tenant-1",
        "documents": [{"document_id": "DOC-1", "source_url": "https://internal.example/report.pdf", "storage_object_path": "tenant-1/PRIVATE_CASE/DOC-1.pdf"}],
    }
    public_case = {
        "case_id": "PUBLIC_CASE",
        "sample_type": "public",
        "documents": [{"document_id": "DOC-2", "source_url": "https://static.cninfo.com.cn/finalpage/report.pdf", "storage_object_path": "public/DOC-2.pdf"}],
    }
    private_public = main_module._public_case(private_case)
    public_public = main_module._public_case(public_case)
    assert "source_url" not in private_public["documents"][0]
    assert "storage_object_path" not in private_public["documents"][0]
    assert public_public["documents"][0]["source_url"].startswith("https://static.cninfo.com.cn/")


def test_model_consent_api_creates_reads_and_revokes_a_case_scoped_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    fake = _FakeConsentClient()
    identity = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner", email="owner@example.test")
    case = {
        "case_id": "PRIVATE_CASE",
        "sample_type": "authorized_deidentified",
        "tenant_id": "tenant-1",
        "company_name": "内部企业",
        "model_transfer_allowed": False,
    }
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(main_module, "_case_record", lambda _case_id, **_kwargs: case)
    monkeypatch.setattr(main_module, "require_authenticated", lambda _request: identity)
    monkeypatch.setattr(main_module, "authorize_case_access", lambda _request, _case: identity)
    client = TestClient(main_module.app)

    before = client.get("/api/cases/PRIVATE_CASE/model-consent")
    assert before.status_code == 200
    assert before.json()["active"] is False
    assert before.json()["status"] == "not_granted"
    contract = before.json()["contract"]
    assert contract["provider"] == "api.deepseek.com"

    valid_until = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    missing_confirmation = client.post(
        "/api/cases/PRIVATE_CASE/model-consent",
        json={
            "provider": "api.deepseek.com",
            "model_id": "deepseek-v4-flash",
            "transmission_scope": "仅传输必要字段证据、来源元数据与RAG命中片段；不上传整本PDF或本机路径。",
            "purpose": "审计计划阶段预筛",
            "valid_until": valid_until,
            "confirmed": False,
        },
    )
    assert missing_confirmation.status_code == 422

    contradictory = client.post(
        "/api/cases/PRIVATE_CASE/model-consent",
        json={
            **contract,
            "provider": "attacker.example",
            "purpose": "审计计划阶段预筛",
            "valid_until": valid_until,
            "confirmed": True,
        },
    )
    assert contradictory.status_code == 422

    granted = client.post(
        "/api/cases/PRIVATE_CASE/model-consent",
        json={
            **contract,
            "purpose": "审计计划阶段公开财报风险预筛的待核查草稿",
            "valid_until": valid_until,
            "confirmed": True,
        },
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["active"] is True
    consent_id = granted.json()["consent"]["id"]
    assert fake.audit_events[-1]["event_type"] == "model_transfer_consent_created"

    after_grant = client.get("/api/cases/PRIVATE_CASE/model-consent")
    assert after_grant.json()["active"] is True
    assert after_grant.json()["consent"]["id"] == consent_id

    revoked = client.post(f"/api/model-consents/{consent_id}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["active"] is False
    assert fake.audit_events[-1]["event_type"] == "model_transfer_consent_revoked"
    assert client.get("/api/cases/PRIVATE_CASE/model-consent").json()["active"] is False

    # 已发布旧前端的中文占位值仍可过渡使用，但落库必须绑定服务端规范合同。
    legacy = client.post(
        "/api/cases/PRIVATE_CASE/model-consent",
        json={
            "provider": "当前服务端已配置供应商",
            "model_id": "configured-model",
            "transmission_scope": "仅传输字段证据、来源元数据与 RAG 命中原文片段。",
            "purpose": "审计计划阶段公开财报风险预筛的待核查草稿",
            "valid_until": valid_until,
            "confirmed": True,
        },
    )
    assert legacy.status_code == 200, legacy.text
    assert fake.consent is not None
    assert {key: fake.consent[key] for key in contract} == contract


def test_private_source_route_returns_only_a_short_signed_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    fake = _FakeConsentClient()
    identity = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner")
    case = {
        "case_id": "PRIVATE_CASE",
        "sample_type": "authorized_deidentified",
        "tenant_id": "tenant-1",
        "documents": [{
            "document_id": "DOC-1",
            "source_url": "https://internal.example/report.pdf",
            "storage_object_path": f"tenant-1/PRIVATE_CASE/DOC-1-{'A' * 64}.pdf",
        }],
    }
    monkeypatch.setattr(main_module, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(main_module, "_case_record", lambda _case_id, **_kwargs: case)
    monkeypatch.setattr(main_module, "authorize_case_access", lambda _request, _case: identity)
    response = TestClient(main_module.app).get(
        "/api/cases/PRIVATE_CASE/sources/DOC-1",
        follow_redirects=False,
    )
    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith(f"https://storage.example.test/audittrace-private/signed/tenant-1/PRIVATE_CASE/DOC-1-{'A' * 64}.pdf")
    assert "internal.example" not in location
    missing = TestClient(main_module.app).get(
        "/api/cases/PRIVATE_CASE/sources/NOT_REGISTERED",
        follow_redirects=False,
    )
    assert missing.status_code == 404


def test_model_authorization_requires_an_active_case_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "supabase")
    # 测试夹具与真实 .env 解耦：同意合同必须与服务端当前供应商/模型一致。
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    fake = _FakeConsentClient()
    fake.consent = {
        "id": str(uuid.uuid4()),
        "tenant_id": "tenant-1",
        "case_id": "PRIVATE_CASE",
        "case_tenant_id": None,
        "user_id": "user-1",
        "provider": "api.deepseek.com",
        "model_id": "deepseek-v4-flash",
        "transmission_scope": "仅传输必要字段证据、来源元数据与RAG命中片段；不上传整本PDF或本机路径。",
        "valid_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "revoked_at": None,
    }
    identity = UserIdentity(user_id="user-1", tenant_id="tenant-1", role="owner")
    monkeypatch.setattr(auth_module, "get_supabase_client", lambda: fake)
    request = _request()
    attach_identity(request, identity)
    case = {"case_id": "PRIVATE_CASE", "model_transfer_allowed": False}
    assert authorize_model_transfer(request, case) is True
    fake.consent["revoked_at"] = datetime.now(timezone.utc).isoformat()
    assert authorize_model_transfer(request, case) is False


def test_agent_chain_rechecks_consent_before_each_role_and_stops_after_revoke() -> None:
    result = RuleResult(
        rule_id="R1",
        status="candidate",
        source_validation={},
        metrics={},
        risk_card={"screening_strength": "standard"},
    )
    steps = run_agent_chain(
        run_id="RUN-RECHECK",
        rule_result=result,
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "最小证据片段"}],
        enabled=True,
        api_key="test-key",
        base_url="https://model.invalid",
        model_id="test-model",
        before_role=lambda _role: False,
    )
    assert len(steps) == 3
    assert steps[0].status == "model_transfer_revoked"
    assert steps[0].failure_code == "MODEL_TRANSFER_REVOKED"
    assert [step.status for step in steps[1:]] == ["skipped", "skipped"]
    assert all(step.failure_code == "PREVIOUS_ROLE_FAILED" for step in steps[1:])


def test_sensitive_data_blocks_external_model_before_agent_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    # 隐私闸门只在"本次真的计划外呼"时生效，而计划外呼的前提是已配置密钥。
    # 不显式给密钥就会让本测试依赖开发者本机 .env，清洁包里因为没有密钥而失真。
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-privacy-gate")
    context, sources = get_period_sources(main_module.WORKSPACE_ROOT, "STD_DEV_T0", 2023, ("R1",))
    context["model_transfer_allowed"] = True
    context["industry_gate"] = {"fit_level": "compatible", "rule_family": "general_business"}
    monkeypatch.setattr(main_module, "_run_rag_for_candidates", lambda **_kwargs: ([], [], [], None))
    monkeypatch.setattr(main_module, "run_agent_chain", lambda **_kwargs: pytest.fail("敏感信息命中后不得调用模型"))
    response = main_module._execute_run(
        context=context,
        sources=sources,
        rule_ids=["R1"],
        run_mode="full_analysis",
        r2_min_gap=0.0,
        planned_materiality=None,
        r1_gap_threshold=0.15,
        r1_strong_gap_threshold=0.30,
        r1_absolute_threshold=0.0,
        http_request=_request(),
        run_prefix="RUN-PRIVACY",
        supplement_evidence=[
            {
                "evidence_id": "SUP-PRIVATE-E01",
                "details": {"note": "脱敏前联系人 13800138000"},
                "support_status": "pending_human_confirmation",
            }
        ],
    )
    assert response.model_check.status == "sensitive_data_blocked"
    assert response.run_completeness == "incomplete_sensitive_data_blocked"
    assert response.rule_results[0].agent_steps[0].status == "sensitive_data_blocked"
    assert response.context["privacy_scan"]["finding_count"] == 1


def test_sensitive_supplement_does_not_pollute_later_runs_of_same_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同案例先跑一次被敏感信息阻断的运行，后续普通运行必须干净且能正常进入协作链。

    这条守住的是共享状态：补充证据、隐私扫描结论和模型输入缓存都只能属于当次运行。
    第二次运行按真实请求那样重新取一份 context，而不是靠"先清空所有东西"的 fixture。
    """

    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-privacy-gate")
    monkeypatch.setattr(main_module, "_run_rag_for_candidates", lambda **_kwargs: ([], [], [], None))

    blocked_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        main_module,
        "run_agent_chain",
        lambda **kwargs: blocked_calls.append(kwargs) or [],
    )

    first_context, first_sources = get_period_sources(
        main_module.WORKSPACE_ROOT, "STD_DEV_T0", 2023, ("R1",)
    )
    first_context["model_transfer_allowed"] = True
    first_context["industry_gate"] = {"fit_level": "compatible", "rule_family": "general_business"}
    blocked = main_module._execute_run(
        context=first_context,
        sources=first_sources,
        rule_ids=["R1"],
        run_mode="full_analysis",
        r2_min_gap=0.0,
        planned_materiality=None,
        r1_gap_threshold=0.15,
        r1_strong_gap_threshold=0.30,
        r1_absolute_threshold=0.0,
        http_request=_request(),
        run_prefix="RUN-PRIVACY-PARENT",
        supplement_evidence=[
            {
                "evidence_id": "SUP-PRIVATE-E02",
                "details": {"note": "脱敏前联系人 13800138000"},
                "support_status": "pending_human_confirmation",
            }
        ],
    )
    assert blocked.model_check.status == "sensitive_data_blocked"
    assert blocked_calls == []

    second_context, second_sources = get_period_sources(
        main_module.WORKSPACE_ROOT, "STD_DEV_T0", 2023, ("R1",)
    )
    second_context["model_transfer_allowed"] = True
    second_context["industry_gate"] = {"fit_level": "compatible", "rule_family": "general_business"}
    normal = main_module._execute_run(
        context=second_context,
        sources=second_sources,
        rule_ids=["R1"],
        run_mode="full_analysis",
        r2_min_gap=0.0,
        planned_materiality=None,
        r1_gap_threshold=0.15,
        r1_strong_gap_threshold=0.30,
        r1_absolute_threshold=0.0,
        http_request=_request(),
        run_prefix="RUN-PRIVACY-CHILD",
        supplement_evidence=[],
    )
    assert normal.context["privacy_scan"]["finding_count"] == 0
    assert normal.model_check.status != "sensitive_data_blocked"
    assert normal.run_completeness != "incomplete_sensitive_data_blocked"
    # 真正的隔离不变量：本次运行的整个响应里不得残留上一次的补充材料。
    # 不断言"必须进入协作链"——没有年报全文的评委包里 RAG 会先失败，那与隐私闸门无关。
    assert "13800138000" not in repr(normal)
    assert "SUP-PRIVATE-E02" not in repr(normal)
    assert all("13800138000" not in repr(call) and "SUP-PRIVATE-E02" not in repr(call) for call in blocked_calls)
