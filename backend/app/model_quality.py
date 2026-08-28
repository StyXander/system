"""真实外部模型成功率台账。

只记录真实三 Agent 运行；探测、缓存回放、确定性备用和单元测试都不进入分母。
台账中不包含密钥、提示词、模型原文或证据正文。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WINDOW_SIZE = 10
ALERT_THRESHOLD = 0.80
LEDGER_RELATIVE_PATH = Path("runtime") / "model-quality.json"
# 这轮提示词、事实闸门和单次语义修正组成新的可比口径。旧台账仍保留，
# 但不能被换模型后误显示为“当前代码刚跑出的成功率”。
QUALITY_PROFILE = "demo_model_quality_v2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(workspace_root: Path) -> Path:
    return workspace_root / "backend" / LEDGER_RELATIVE_PATH


def _load(workspace_root: Path) -> list[dict[str, Any]]:
    path = _path(workspace_root)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _save(workspace_root: Path, rows: list[dict[str, Any]]) -> None:
    path = _path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def is_external_three_agent_run(response: Any) -> bool:
    """识别能进入成功率窗口的真实调用，防止备用与回放污染指标。"""
    model_check = getattr(response, "model_check", None)
    steps = list(getattr(response, "agent_steps", None) or [])
    if getattr(response, "execution_mode", "") in {"cache_replay", "deterministic_backup"}:
        return False
    if not model_check or not getattr(model_check, "provider_call_count", 0):
        return False
    return any(bool(getattr(step, "provider_call_performed", False)) for step in steps)


def record_external_run(
    workspace_root: Path,
    response: Any,
    *,
    allow_test_recording: bool = False,
) -> dict[str, Any] | None:
    """幂等记录一次真实链路，并返回最近十次的告警快照。"""
    # pytest 的 TestClient 会完整走 main.py，并用内存 provider 模拟三 Agent；
    # 如果不在台账入口拦截，这些“成功”会污染现场真实成功率。质量模块自己的
    # 临时目录单测可显式 opt in，生产调用保持默认拒绝测试写入。
    if os.getenv("PYTEST_CURRENT_TEST") and not allow_test_recording:
        model_check = getattr(response, "model_check", None)
        model_id = str(getattr(response, "model_id", "") or getattr(model_check, "model_id", "")) or None
        return quality_snapshot(workspace_root, model_id=model_id)
    if not is_external_three_agent_run(response):
        return None
    rows = _load(workspace_root)
    run_id = str(getattr(response, "run_id", ""))
    if not run_id:
        return None
    model_check = getattr(response, "model_check", None)
    response_model_id = str(getattr(response, "model_id", "") or getattr(model_check, "model_id", "")) or None
    if not any(str(item.get("run_id") or "") == run_id for item in rows):
        steps = list(getattr(response, "agent_steps", None) or [])
        success = (
            str(getattr(model_check, "status", "")) == "model_success"
            and {str(getattr(step, "role", "")) for step in steps if str(getattr(step, "status", "")) == "completed"}
            == {"challenge", "counter", "review"}
        )
        rows.append(
            {
                "run_id": run_id,
                "recorded_at": _now(),
                "model_id": response_model_id,
                "quality_profile": QUALITY_PROFILE,
                "success": success,
                "failure_code": None if success else str(getattr(model_check, "failure_code", "") or "MODEL_CHAIN_NOT_COMPLETE"),
                "provider_call_count": int(getattr(model_check, "provider_call_count", 0) or 0),
            }
        )
        _save(workspace_root, rows)
    return quality_snapshot(workspace_root, model_id=response_model_id)


def quality_snapshot(workspace_root: Path, *, model_id: str | None = None) -> dict[str, Any]:
    """计算指定模型最近十次真实运行的成功率；没有样本时保持 unmeasured。"""
    rows = [
        item for item in _load(workspace_root)
        if str(item.get("quality_profile") or "") == QUALITY_PROFILE
    ]
    normalized_model_id = str(model_id or "").strip() or None
    if normalized_model_id:
        rows = [item for item in rows if str(item.get("model_id") or "") == normalized_model_id]
    recent = rows[-WINDOW_SIZE:]
    sample_count = len(recent)
    success_count = sum(1 for item in recent if item.get("success") is True)
    success_rate = (success_count / sample_count) if sample_count else None
    return {
        "window_size": WINDOW_SIZE,
        "sample_count": sample_count,
        "success_count": success_count,
        "success_rate": success_rate,
        "threshold": ALERT_THRESHOLD,
        "alert": bool(sample_count and success_rate is not None and success_rate < ALERT_THRESHOLD),
        "status": "below_threshold" if sample_count and success_rate is not None and success_rate < ALERT_THRESHOLD else "meets_threshold" if sample_count else "unmeasured",
        "model_id": normalized_model_id,
        "quality_profile": QUALITY_PROFILE,
        "boundary": "仅统计当前质量口径下的真实外部三 Agent 完整运行；不含旧口径、探测、缓存回放、确定性备用或测试。",
    }
