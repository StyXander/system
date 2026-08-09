"""本地开发运行日志。

仅保存本项目DEV运行的结构化结果和人工复核状态；不保存API Key，也不把缓存伪装成本次实时调用。
运行记录用于开发回放和人工复核，不是不可篡改的正式审计档案。
每次真实运行使用独立编号，保存新结果不能覆盖另一编号的历史。
运行编号虽然由服务端生成，读写前仍限制字符以阻断路径注入。
运行目录遵循测试命名空间，自动化状态不能混入人工演示记录。
路径只由工作区、命名空间和受控编号构成，不接受调用方提供绝对路径。
保存内容使用结构化响应模型，任意调试对象不能直接序列化进记录。
模型密钥只存在环境配置，任何运行响应字段都不得复制密钥值。
供应商原始响应和请求头不进入本地记录，失败只保存稳定摘要。
加载文件不存在时返回空值，不能用最近一次运行替代请求编号。
损坏 JSON 不能被解释为成功记录，读取方必须明确处理解析失败。
人工复核只附加到对应运行，不能跨运行复用复核人和批准时间。
复核提交前必须先找到原运行，孤立复核记录不会单独创建文件。
人工处理与程序结果分别保存，复核备注不能改写原规则数值。
人工状态更新时间来自真实提交时刻，不由模型或前端默认值生成。
重复保存复核会更新当前复核对象，但原运行编号和运行内容保持不变。
本地文件写入服务单实例开发模式，不声称提供跨机器事务一致性。
公网多实例状态应由持久化后端承担，不能依赖某个 web 实例磁盘。
运行文件属于后端内部状态，公开接口只返回经过响应模型筛选的字段。
删除或归档策略不在本模块自动执行，避免后台清理误删人工复核证据。
本模块的失败关闭原则是宁可找不到记录，也不拼接或猜测一份替代结果。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
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
    try:
        path = _run_path(workspace_root, run_id)
    except ValueError:
        return None
    if not path.exists():
        return None
    return StoredRunResponse.model_validate_json(path.read_text(encoding="utf-8"))


def save_human_review(workspace_root: Path, run_id: str, review: HumanReviewRequest) -> StoredRunResponse | None:
    stored = load_run(workspace_root, run_id)
    if stored is None:
        return None
    stamped = review.model_copy(
        update={"reviewed_at": review.reviewed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")}
    )
    # 人工处理与程序筛查、AI建议分层保存；更新人工字段不能改写前两层状态。
    updated_run = stored.run.model_copy(update={"human_disposition": stamped.status})
    updated = StoredRunResponse(run=updated_run, human_review=stamped)
    _run_path(workspace_root, run_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    return updated
