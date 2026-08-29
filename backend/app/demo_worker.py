"""可选的 Supabase 演示任务 Worker。

当前免费 Render Blueprint 不启用本模块；只有显式把
``AUDITTRACE_DEMO_EXECUTOR_MODE=worker`` 部署到付费 Worker 后，才会从
``demo_run_tasks`` 领取 queued 任务。每个任务使用数据库租约和 CAS 收口，
实例退出不会重放供应商调用。

Worker 只处理已经通过公开案例白名单的任务。
Worker 不读取浏览器提交的 service-role 字段。
Worker 不把租约令牌写入日志或返回体。
Worker 领取任务前会检查执行模式配置。
Worker 执行边界由数据库状态机集中约束。
Worker 发现租约失效时立即停止后续写入。
Worker 不会把 interrupted 重写成 completed。
Worker 不会把 fallback 标成真实模型成功。
Worker 不会绕过 evidence 和 semantic 硬校验。
Worker 不会在供应商失败后自动切换模型。
Worker 的 once 参数只用于隔离验收和部署探针。
Worker 空闲时等待，不创建虚假运行记录。
Worker 的结果先持久化，再公开终态。
Worker 只保存脱敏错误码和运行摘要。
Worker 不保存供应商完整响应正文。
Worker 不改变历史评估或人工评分记录。
Worker 模板默认不进入当前免费部署。
Worker 启用需要赛前单独授权和成本确认。
Worker 停止后由 lease expiry 结算任务。
Worker 的所有重试都必须生成新的 retry_of_task_id。
Worker 运行手册必须说明免费与付费边界。
Worker 验收记录必须关联发布候选编号。
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable

from starlette.requests import Request

from .demo_run_tasks import SupabaseDemoRunTaskStore
from .main import WORKSPACE_ROOT, _execute_demo_run
from .supabase_adapter import get_demo_task_client


def _worker_request() -> Request:
    """构造不含用户身份的内部请求；公开任务只使用已持久化的请求摘要。"""

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/demo/runs",
            "raw_path": b"/api/demo/runs",
            "query_string": b"",
            "headers": [],
            "client": ("worker", 0),
            "server": ("worker", 0),
        }
    )


def run_worker(*, once: bool = False, idle_seconds: float = 2.0) -> int:
    """领取并执行任务；``once`` 供部署探针和隔离验收使用。"""

    if os.getenv("AUDITTRACE_DEMO_EXECUTOR_MODE", "web").strip().lower() != "worker":
        raise RuntimeError("AUDITTRACE_DEMO_EXECUTOR_MODE 必须显式设置为 worker。")
    store = SupabaseDemoRunTaskStore(get_demo_task_client())
    try:
        while True:
            task = store.claim_next()
            if task is None:
                if once:
                    return 0
                time.sleep(max(0.25, idle_seconds))
                continue
            request = _worker_request()
            executor: Callable[[dict[str, Any]], Any] = lambda current: _execute_demo_run(current, store, request)
            # Supabase store 在每个边界安装租约探针；把同一 Request 传入，
            # 让 _require_worker_lease 在主链内部也能 fail-closed。
            setattr(executor, "__audittrace_request__", request)
            store._run_wrapper(task, executor)
            if once:
                return 0
    finally:
        store.shutdown()


def main() -> int:
    once = os.getenv("AUDITTRACE_WORKER_ONCE", "false").strip().lower() in {"1", "true", "yes", "on"}
    return run_worker(once=once)


if __name__ == "__main__":
    raise SystemExit(main())
