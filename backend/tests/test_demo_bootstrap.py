from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import demo_bootstrap
from backend.app.main import app

AI_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
FEATURED_ORDER = ["STD_DEV_T0", "CNINFO_000858_T0_20260430", "CNINFO_600938_T0_20260326"]


def test_demo_bootstrap_serves_frozen_manifest_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """启动快照一次返回 15 案白名单、精选顺序与统一 AI 声明。"""

    # 竞赛演示部署始终以演示模式运行；种子案例目录只在该模式下可见。
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    payload = TestClient(app).get("/api/demo/bootstrap").json()
    assert payload["schema_version"] == "demo_bootstrap_v1"
    assert payload["bootstrap_ready"] is True
    assert payload["case_count"] == len(payload["cases"]) == 15
    ids = [case["case_id"] for case in payload["cases"]]
    assert len(set(ids)) == 15
    assert payload["featured_case_ids"] == FEATURED_ORDER
    assert set(FEATURED_ORDER) <= set(ids)
    assert payload["ai_generated_content_notice"] == AI_NOTICE
    for case in payload["cases"]:
        assert {
            "case_id",
            "ticker",
            "company_name",
            "category",
            "demo_focus",
            "report_years",
            "rule_ids",
            "admission_status",
            "rag",
        } <= set(case)
        # 准入未完成时只能如实显示 pending，不得预写 passed。
        assert case["admission_status"] in {"pending", "passed"}
        assert len(case["report_years"]) >= 3
        assert case["rag"]["status"] in {"ready", "not_built", "unavailable", "unknown"}
    featured_rag = {
        case["case_id"]: case["rag"]["status"]
        for case in payload["cases"]
        if case["case_id"] in FEATURED_ORDER
    }
    # 首页 3 个精选案例 RAG 必须就绪，否则不得进入 ready（计划 8.5 预检）。
    assert set(featured_rag.values()) == {"ready"}


def test_demo_bootstrap_reads_runtime_quality_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """启动快照每次请求只读取一次运行时质量窗口，window 与 release 共用同一快照。

    回归背景：handler 曾先后两次调用 _runtime_quality_snapshot，公开部署
    每打开一次首页就向 Supabase 重复发一轮质量事件查询；免费层与现场
    多设备观看时都会放大首屏延迟。
    """

    import backend.app.main as main_module

    calls: list[str] = []

    def fake_snapshot(model_id: str):
        calls.append(str(model_id))
        return None

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setattr(main_module, "_runtime_quality_snapshot", fake_snapshot)
    payload = TestClient(app).get("/api/demo/bootstrap").json()
    assert payload["bootstrap_ready"] is True
    assert len(calls) == 1, f"_runtime_quality_snapshot 被调用 {len(calls)} 次，应为 1 次"


def test_demo_bootstrap_leaks_no_secrets_or_local_paths() -> None:
    """启动快照不得包含凭据值、配置键名、本机绝对路径或旧运行模型输出。

    未配置密钥时 full_analysis_reason_code 合法地取值为 api_key_missing，
    它属于计划要求公开的门禁状态；把该状态码当成泄漏会让本测试只在"本机
    .env 恰好有密钥"时才通过。因此这里禁的是凭据值与配置键名本身。
    """

    payload = TestClient(app).get("/api/demo/bootstrap").json()
    text = json.dumps(payload, ensure_ascii=False)
    for banned in (
        "api_key=",
        "DEEPSEEK_API_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "sk-",
        "Bearer ",
        "base_url",
        ".env",
        "C:\\",
        "/home/",
        "reviewer",
    ):
        assert banned not in text
    # 本机真的配了凭据时，任何一项的值都不得出现在对外载荷里。
    for name in ("DEEPSEEK_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY", "OPENAI_API_KEY"):
        value = os.environ.get(name)
        assert not value or value not in text
    readiness = payload["model_readiness"]
    assert isinstance(readiness["full_analysis_ready"], bool)
    assert isinstance(readiness["deterministic_backup_available"], bool)
    assert isinstance(readiness["full_analysis_reason_code"], str)
    # 就绪白名单之外的字段（额度快照、供应商主机等）不得进入启动快照。
    assert set(readiness) == {
        "full_analysis_ready",
        "full_analysis_reason_code",
        "full_analysis_message",
        "deterministic_backup_available",
        "model_id",
        "provider_label",
    }


def test_demo_bootstrap_whitelist_matches_registry_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    """15 案白名单必须是真实注册案例的子集，不得出现未登记案例。"""

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    client = TestClient(app)
    bootstrap = client.get("/api/demo/bootstrap").json()
    listing = client.get("/api/cases?summary=true").json()
    registered = {case["case_id"] for case in listing["cases"]}
    assert set(case["case_id"] for case in bootstrap["cases"]) <= registered


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param({"schema_version": "other"}, id="schema"),
        pytest.param({"case_count": 14}, id="count"),
        pytest.param({"featured_case_ids": ["STD_DEV_T0"]}, id="featured"),
        pytest.param({"cases": []}, id="empty"),
    ],
)
def test_demo_bootstrap_blocks_on_manifest_mismatch(mutate: dict, tmp_path: Path) -> None:
    """manifest 结构不一致时返回发布阻断原因码，且不返回任何案例。"""

    manifest, failure = demo_bootstrap.load_demo_manifest()
    assert manifest is not None and failure is None
    broken = {**manifest, **mutate}
    if mutate.get("cases") == [] and "case_count" not in mutate:
        broken["case_count"] = 0
    broken_path = tmp_path / "broken_manifest.json"
    broken_path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    loaded, reason = demo_bootstrap.load_demo_manifest(broken_path)
    assert loaded is None
    assert reason is not None


def test_demo_bootstrap_blocked_payload_shape() -> None:
    """阻断快照保持最小结构，前端据此显示“演示资源未就绪”。"""

    payload = demo_bootstrap.blocked_bootstrap_payload("demo_manifest_missing")
    assert payload["bootstrap_ready"] is False
    assert payload["bootstrap_reason_code"] == "demo_manifest_missing"
    assert payload["cases"] == []
    assert payload["case_count"] == 0


def test_bootstrap_advertises_onsite_live_sample_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """现场新样例能力必须显式开启，不能让共享部署误以为可写。"""

    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "false")
    monkeypatch.delenv("AUDITTRACE_ONSITE_LIVE_SAMPLE", raising=False)
    disabled = TestClient(app).get("/api/demo/bootstrap").json()
    assert disabled["capabilities"]["onsite_live_sample"] is False
    assert disabled["capabilities"]["structured_exports"] == ["json", "table", "print_pdf"]

    monkeypatch.setenv("AUDITTRACE_ONSITE_LIVE_SAMPLE", "true")
    enabled = TestClient(app).get("/api/demo/bootstrap").json()
    assert enabled["capabilities"]["onsite_live_sample"] is True

    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    shared = TestClient(app).get("/api/demo/bootstrap").json()
    assert shared["capabilities"]["onsite_live_sample"] is False


def test_onsite_flag_allows_non_seed_pipeline_without_changing_shared_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """本机现场开关放行任务创建；共享只读默认仍由主合同覆盖。"""

    import backend.app.main as main_module

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "false")
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")
    monkeypatch.setenv("AUDITTRACE_ONSITE_LIVE_SAMPLE", "true")
    monkeypatch.setenv("AUDITTRACE_RUNTIME_NAMESPACE", "pytest-onsite-live-sample")
    monkeypatch.setattr(main_module, "_queue_pipeline_task", lambda *_args, **_kwargs: None)
    response = TestClient(app).post(
        "/api/pipelines/cninfo",
        json={"company_query": "999999", "years": 3, "analysis_mode": "rag_only", "rule_ids": ["R1"]},
    )
    assert response.status_code == 202
    assert response.json()["task_id"].startswith("CNINFO-")
