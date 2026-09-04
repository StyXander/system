"""进度回调（on_step）异常必须留痕，但不能影响三 Agent 主链的成败状态。

回归的缺陷：以前 on_step 抛错被 `except Exception: pass` 完全吞掉，页面显示的
阶段会与真实链路静默脱节，事后既没有日志也没有计数可以判断发生过。
"""

from __future__ import annotations

import logging

import pytest

from backend.app.agents import run_agent_chain
from backend.app.schemas import RuleResult


def _candidate_rule_result() -> RuleResult:
    return RuleResult(
        rule_id="R1",
        status="candidate",
        source_validation={},
        metrics={},
        risk_card={"screening_strength": "standard"},
    )


def test_agent_step_callback_failure_is_logged_and_counted(caplog: pytest.LogCaptureFixture) -> None:
    """回调抛错时：主链仍完整结算三个角色，同时留下结构化 warning 与降级计数。"""

    def exploding_callback(_role: str, _step: object) -> bool:
        raise RuntimeError("台账写入失败")

    observer_failures: list[dict[str, object]] = []
    with caplog.at_level(logging.WARNING, logger="audittrace.agents"):
        steps = run_agent_chain(
            run_id="RUN-OBSERVER-DEGRADED",
            rule_result=_candidate_rule_result(),
            evidence_bundle=[{"evidence_id": "E1", "excerpt": "最小证据片段"}],
            enabled=True,
            api_key="test-key",
            base_url="https://model.invalid",
            model_id="test-model",
            # before_role 返回 False 让链路在不碰网络的前提下完整走到 skipped 结算。
            before_role=lambda _role: False,
            on_step=exploding_callback,
            observer_failures=observer_failures,
        )

    # 主链状态不受旁路回调失败影响：首角色授权失败，后两角色如实 skipped。
    assert [step.status for step in steps] == ["model_transfer_revoked", "skipped", "skipped"]
    assert steps[0].failure_code == "MODEL_TRANSFER_REVOKED"
    assert [step.failure_code for step in steps[1:]] == ["PREVIOUS_ROLE_FAILED"] * 2

    # 每一次被吞掉的回调异常都留下可核对的计数记录。
    assert len(observer_failures) == 3
    assert {str(item["scope"]) for item in observer_failures} == {"agent_step"}
    assert {str(item["error_type"]) for item in observer_failures} == {"RuntimeError"}
    assert {str(item["run_id"]) for item in observer_failures} == {"RUN-OBSERVER-DEGRADED"}

    # 结构化 warning 里必须能定位到 run 与角色。
    messages = [record.message for record in caplog.records if record.levelno >= logging.WARNING]
    assert any("progress_observer_failed" in message for message in messages)
    assert any("RUN-OBSERVER-DEGRADED" in message and "role=challenge" in message for message in messages)


def test_agent_step_callback_success_leaves_no_degradation_record() -> None:
    """回调正常时不得产生任何降级记录，避免把健康运行误报成降级。"""

    seen: list[str] = []

    def healthy_callback(role: str, _step: object) -> bool:
        seen.append(role)
        return True

    observer_failures: list[dict[str, object]] = []
    steps = run_agent_chain(
        run_id="RUN-OBSERVER-HEALTHY",
        rule_result=_candidate_rule_result(),
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "最小证据片段"}],
        enabled=True,
        api_key="test-key",
        base_url="https://model.invalid",
        model_id="test-model",
        before_role=lambda _role: False,
        on_step=healthy_callback,
        observer_failures=observer_failures,
    )

    assert len(steps) == 3
    assert seen == ["challenge", "counter", "review"]
    assert observer_failures == []


def test_chain_without_observer_still_works_for_existing_callers() -> None:
    """不传 observer_failures 的老调用方必须保持原行为。"""

    steps = run_agent_chain(
        run_id="RUN-OBSERVER-ABSENT",
        rule_result=_candidate_rule_result(),
        evidence_bundle=[{"evidence_id": "E1", "excerpt": "最小证据片段"}],
        enabled=True,
        api_key="test-key",
        base_url="https://model.invalid",
        model_id="test-model",
        before_role=lambda _role: False,
    )

    assert [step.status for step in steps] == ["model_transfer_revoked", "skipped", "skipped"]


def test_observer_status_is_ok_when_no_failure() -> None:
    """健康运行必须显式给出 ok，而不是缺字段，前端才能区分“没降级”和“没测”。"""
    from backend.app import main as main_module

    assert main_module._observer_status([]) == {"status": "ok", "failure_count": 0, "notice": "留痕通道正常"}


def test_observer_status_reports_degraded_with_main_chain_impact_none() -> None:
    from backend.app import main as main_module

    failures = [
        {"scope": "stage", "run_id": "RUN-X", "pipeline_task_id": "T-1", "stage": "structured_output", "error_type": "RuntimeError"},
        {"scope": "agent_step_live", "run_id": "RUN-X", "pipeline_task_id": "T-1", "role": "challenger", "error_type": "RuntimeError"},
    ]
    status = main_module._observer_status(failures)
    assert status["status"] == "degraded"
    assert status["failure_count"] == 2
    assert status["affected_stages"] == ["structured_output"]
    assert status["affected_roles"] == ["challenger"]
    assert status["main_chain_impact"] == "none"
    assert status["notice"] == "留痕通道降级，主分析未受影响"
    assert status["samples"] == failures[:5]


def test_observer_status_survives_into_persisted_task_result() -> None:
    """降级事实必须随 result 落库：顶层新字段会被 _persist 的列白名单丢掉。"""
    from backend.app import main as main_module

    assert "result" in main_module._DEMO_TASK_PERSIST_FIELDS, "依赖 demo_run_tasks._persist 的列白名单包含 result"
