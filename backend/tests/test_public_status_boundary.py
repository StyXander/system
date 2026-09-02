"""公开状态接口只透出实时发布事实，历史登记与内部路径不得外泄。

回归的缺陷：/api/status 之前把整份 PROJECT_STATUS.json 展开返回，约 8 万字节，
里面含旧模型质量窗口、AI 预评分、outputs/ 与 .zcode 等内部产物路径，和当前
发布口径自相矛盾，也容易被评委当成对外承诺。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app import main as main_module


def _fake_request(host: str | None) -> SimpleNamespace:
    """只构造 _is_loopback_request 真正读取的 client.host 字段。"""

    client = None if host is None else SimpleNamespace(host=host)
    return SimpleNamespace(client=client)


def test_loopback_detection_covers_ipv4_ipv6_and_missing_peer() -> None:
    assert main_module._is_loopback_request(_fake_request("127.0.0.1")) is True
    assert main_module._is_loopback_request(_fake_request("::1")) is True
    assert main_module._is_loopback_request(_fake_request("localhost")) is True
    assert main_module._is_loopback_request(_fake_request("203.0.113.7")) is False
    assert main_module._is_loopback_request(_fake_request(None)) is False


def test_public_projection_drops_history_and_internal_paths() -> None:
    """白名单之外的键必须整体消失，包括旧模型窗口和内部产物路径。"""

    payload = {
        "engine_version": "0.7.1",
        "formal_scope": "审计计划阶段—销售与收款循环",
        "case_count": 15,
        "cases": [{"case_id": "STD_DEV_T0"}],
        "release": {"release_id": "RELEASE-CANDIDATE-20260828-V1"},
        "model": {
            "model_id": "deepseek-v4-flash",
            "execution_mode": "external_live",
            "frozen_release_quality_window": {"model_id": "qwen3.5-plus", "success_rate": 0.7},
        },
        # 以下都是 PROJECT_STATUS.json 的历史登记，公开响应里不能出现。
        "latest_r3_20260826": {"summary": "outputs/evaluation_v5/..."},
        "quality_evidence": {"browser_status": ".zcode/plans/plan-sess_x.md"},
        "acceptance_snapshot": {"report": "审迹智链_部署站51案例全量验收与修复记录.md"},
        "live_model_acceptance": {"run_id": "RUN-V7-CBF3D7A07C37"},
        "status_file": "registered",
    }

    projected = main_module._public_status_projection(payload)

    allowed_extras = {"ai_generated_content_notice", "case_scope"}
    assert set(projected) - allowed_extras <= set(main_module._PUBLIC_STATUS_KEYS)
    assert projected["case_scope"] in {"frozen_demo_manifest", "workspace_catalog_manifest_unavailable"}
    assert "latest_r3_20260826" not in projected
    assert "quality_evidence" not in projected
    assert "acceptance_snapshot" not in projected
    assert "live_model_acceptance" not in projected
    assert "status_file" not in projected
    assert "frozen_release_quality_window" not in projected["model"]
    assert projected["model"]["model_id"] == "deepseek-v4-flash"
    assert projected["release"] == payload["release"]
    # 冻结清单之外的案例编号必须被剔除，51 案目录不能冒充演示范围。
    if projected["case_scope"] == "frozen_demo_manifest":
        assert [case["case_id"] for case in projected["cases"]] == ["STD_DEV_T0"]
        assert projected["case_count"] == 1
    # 统一 AI 声明必须随公开响应保留。
    assert projected["ai_generated_content_notice"] == main_module.AI_GENERATED_CONTENT_NOTICE


def test_public_status_endpoint_omits_internal_artifact_paths(monkeypatch) -> None:
    """真实路由在公开演示模式下不得序列化出内部路径或旧模型状态。"""

    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("AUDITTRACE_PERSISTENCE", "local")

    client = TestClient(main_module.app)
    response = client.get("/api/status")
    assert response.status_code == 200

    body = response.json()
    serialized = json.dumps(body, ensure_ascii=False)

    forbidden_markers = [
        "outputs/",
        "artifacts/",
        ".zcode",
        "backend/runtime",
        "qwen3.5-plus",
        "ai_prescore_mean",
        "latest_r3_20260826",
        "latest_r2_20260825",
        "acceptance_snapshot",
    ]
    leaked = [marker for marker in forbidden_markers if marker in serialized]
    assert leaked == [], f"公开 /api/status 仍泄露：{leaked}"

    # 前端依赖的字段必须还在，避免裁剪把页面打断。
    for required in ("release", "current_release", "model", "cases", "case_count", "demo_mode"):
        assert required in body, f"公开 /api/status 缺少前端需要的 {required}"
    assert body["case_count"] == 15
    assert isinstance(body["cases"], list) and len(body["cases"]) == 15
