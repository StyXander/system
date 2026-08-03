"""本地开发运行日志。

仅保存本项目DEV运行的结构化结果和人工复核状态；不保存API Key，也不把缓存伪装成本次实时调用。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from .schemas import HumanReviewRequest, RunResponse, StoredRunResponse


def _run_dir(workspace_root: Path) -> Path:
    namespace = re.sub(r"[^A-Za-z0-9_-]", "", os.getenv("AUDITTRACE_RUNTIME_NAMESPACE", ""))
    base = workspace_root / "backend" / "runtime"
    directory = (base / namespace if namespace else base) / "runs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _run_path(workspace_root: Path, run_id: str) -> Path:
    # run_id由服务端生成；仍限制字符，避免把路径控制权交给请求参数。
    if not run_id.replace("-", "").isalnum():
        raise ValueError("非法运行编号")
    return _run_dir(workspace_root) / f"{run_id}.json"


def save_run(workspace_root: Path, run: RunResponse) -> None:
    stored = StoredRunResponse(run=run)
    _run_path(workspace_root, run.run_id).write_text(
        stored.model_dump_json(indent=2), encoding="utf-8"
    )


def load_run(workspace_root: Path, run_id: str) -> StoredRunResponse | None:
    path = _run_path(workspace_root, run_id)
    if not path.exists():
        return None
    return StoredRunResponse.model_validate_json(path.read_text(encoding="utf-8"))


def save_human_review(workspace_root: Path, run_id: str, review: HumanReviewRequest) -> StoredRunResponse | None:
    stored = load_run(workspace_root, run_id)
    if stored is None:
        return None
    stamped = review.model_copy(
        update={"reviewed_at": review.reviewed_at or datetime.now().astimezone().isoformat(timespec="seconds")}
    )
    # 人工处理与程序筛查、AI建议分层保存；更新人工字段不能改写前两层状态。
    updated_run = stored.run.model_copy(update={"human_disposition": stamped.status})
    updated = StoredRunResponse(run=updated_run, human_review=stamped)
    _run_path(workspace_root, run_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    return updated
