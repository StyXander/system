"""Supabase 长任务 worker。

本地模式不启动轮询，仍由 FastAPI BackgroundTasks 支持离线竞赛验收。
公网模式由独立 Render worker 通过数据库 RPC 领取任务；租约过期后可被
其他 worker 重新领取，服务重启不会丢失排队记录。
worker 只处理已经入队的长任务，不提供绕过 API 校验的新入口。
工作区根从模块位置解析，进程启动目录不会改变案例或任务存储边界。
worker 标识默认组合主机名和进程号，便于区分并发租约持有者。
租约时长设置下限，过短配置不能造成同一任务被频繁重复领取。
领取动作由数据库原子完成，空队列时正常返回而不是制造失败任务。
领取结果必须包含任务编号和请求结构，缺失关键字段时保持失败关闭。
队列请求投影到本地任务文件时保留数据库尝试次数和原任务编号。
已认证身份从服务端队列载荷恢复，worker 不携带或转发用户访问令牌。
兼容请求对象只保存最小身份上下文，不伪造浏览器请求头或客户端地址。
任务执行复用现有主链，后台路径不能跳过来源、隐私或行业闸门。
执行完成后只上报结构化结果摘要，数据库中不保存 Python 异常对象。
错误摘要只包含异常类型和受控说明，不回显密钥、请求头或文档正文。
任务失败会明确调用失败完成接口，不能让租约到期前一直显示运行中。
上报完成失败时保留原异常边界，不能把持久化失败误报为业务成功。
循环轮询只在公网持久化模式启动，本地竞赛验收不会额外产生 worker。
单次模式最多领取一个任务，便于部署健康检查和确定性自动化测试。
空队列轮询使用可配置间隔，避免紧密循环持续占用数据库连接。
键盘中断属于正常停机信号，不应生成一条虚假的任务失败记录。
多个 worker 可以并行服务不同租约，但同一任务的幂等性仍由任务链保证。
worker 的职责是可靠执行和诚实上报，不负责替人工完成复核或导出批准。
"""

from __future__ import annotations

import argparse
import os
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from .auth import UserIdentity, attach_identity
from .main import _execute_cninfo_task
from .pipeline import load_task, materialize_task
from .supabase_adapter import (
    SupabaseError,
    SupabaseLeaseLost,
    get_supabase_client,
    install_worker_lease_guard,
    persistence_mode,
    reset_worker_lease_guard,
)


_MEMBERSHIP_ROLES = frozenset({"owner", "admin", "member", "reviewer"})


class WorkerAuthorizationRevoked(SupabaseError):
    """排队用户已失去任务执行资格；该错误不能按临时网络故障重试。"""

    code = "WORKER_AUTHORIZATION_REVOKED"
    status_code = 403


class _LeaseState:
    """在线程间共享租约状态，并把每次续租当作一次服务端 fencing 探针。"""

    def __init__(
        self,
        *,
        renew: Callable[[], None],
    ) -> None:
        self._renew = renew
        self._active = True
        self._state_lock = threading.Lock()
        # 后台心跳与主线程持久化前探针不能并发调用同一个租约 RPC；串行化后，
        # 主线程拿到 True 就代表它观察的是一次完整且最新的服务端确认。
        self._renew_lock = threading.Lock()

    def active(self) -> bool:
        """只读取本地失租标志；适合高频、无网络的阶段边界检查。"""

        with self._state_lock:
            return self._active

    def mark_lost(self) -> None:
        """租约一旦失效便不可恢复，旧 worker 不能因后续网络恢复重新获得写权。"""

        with self._state_lock:
            self._active = False

    def probe(self) -> bool:
        """向数据库续租并确认 token；任何无法确认的情况都按失败关闭处理。"""

        if not self.active():
            return False
        with self._renew_lock:
            if not self.active():
                return False
            try:
                self._renew()
            except Exception:
                # 网络错误和明确 CAS 未命中都意味着“当前无法证明仍持有租约”；
                # 适配器合同错配等意外也不能被当作仍持有租约；对昂贵模型调用
                # 和持久化而言，宁可交给新 worker 重试也不能双写。
                self.mark_lost()
                return False
        return True

    def require_current(self) -> None:
        """高成本阶段前强制服务端复核，而不是只相信上一次后台心跳。"""

        if not self.probe():
            raise SupabaseLeaseLost("worker 无法确认当前租约，已停止任务副作用。")


def _workspace_root() -> Path:
    """从模块位置解析项目根目录，避免依赖 worker 启动时的当前目录。"""

    return Path(__file__).resolve().parents[2]


class WorkerRequest:
    """给现有分析主链的最小 Request 兼容对象，不携带用户 token。"""

    def __init__(
        self,
        identity_payload: dict[str, Any] | None = None,
        *,
        task_id: str | None = None,
        lease_probe: Callable[[], bool] | None = None,
    ) -> None:
        self.headers: dict[str, str] = {}
        self.client = SimpleNamespace(host=f"worker:{socket.gethostname()}")
        self.state = SimpleNamespace()
        # 主链后续可在每个 Agent 角色或其他高成本步骤前调用同一个探针；
        # task_id 同时给远程运行提供稳定的幂等关联键，而不是依赖随机 run_id。
        self.state.audittrace_pipeline_task_id = task_id
        self.state.audittrace_worker_lease_probe = lease_probe
        if identity_payload and identity_payload.get("user_id"):
            attach_identity(
                self,
                UserIdentity(
                    user_id=str(identity_payload["user_id"]),
                    tenant_id=str(identity_payload.get("tenant_id") or "") or None,
                    role=str(identity_payload.get("role") or "member"),
                    source="worker",
                ),
            )


def _safe_error(error: Exception) -> dict[str, str]:
    """只持久化稳定错误类型，不把密钥、路径或外部响应写入队列。"""

    return {"code": "WORKER_EXECUTION_FAILED", "message": f"worker 执行失败：{type(error).__name__}。"}


def _authorization_error() -> dict[str, str]:
    """撤权只暴露稳定业务码，不向队列写入成员表或同意记录细节。"""

    return {
        "code": WorkerAuthorizationRevoked.code,
        "message": "任务发起人的组织成员资格或角色已失效，任务未执行。",
    }


def _heartbeat_interval(lease_seconds: int) -> float:
    """至少在租约三分之一处续租；上限十秒缩短撤租后旧 worker 的感知窗口。"""

    return max(1.0, min(10.0, max(30, lease_seconds) / 3.0))


def _authoritative_identity(client: Any, task: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    """用 service-role 成员表重建身份，不信任排队时保存的角色快照。"""

    tenant_id = str(task.get("tenant_id") or "").strip()
    user_id = str(task.get("requested_by") or "").strip()
    if not tenant_id or not user_id:
        raise WorkerAuthorizationRevoked("公网任务缺少权威租户或发起人。")

    snapshot = payload.get("requested_by_identity")
    if isinstance(snapshot, dict):
        snapshot_user = str(snapshot.get("user_id") or "").strip()
        snapshot_tenant = str(snapshot.get("tenant_id") or "").strip()
        if snapshot_user != user_id or snapshot_tenant != tenant_id:
            # 队列表列是 web 端认证后写入的权威归属；载荷快照只用于检错，
            # 二者不一致时不能挑选对执行更宽松的一方。
            raise WorkerAuthorizationRevoked("任务身份快照与数据库归属不一致。")

    membership = client.get_active_membership(user_id=user_id, tenant_id=tenant_id)
    if not isinstance(membership, dict) or membership.get("active") is not True:
        raise WorkerAuthorizationRevoked("任务发起人不再是有效组织成员。")
    if str(membership.get("user_id") or "").strip() != user_id:
        raise WorkerAuthorizationRevoked("成员查询返回了错误用户。")
    if str(membership.get("organization_id") or "").strip() != tenant_id:
        raise WorkerAuthorizationRevoked("成员查询返回了错误组织。")
    role = str(membership.get("role") or "").strip()
    if role not in _MEMBERSHIP_ROLES:
        raise WorkerAuthorizationRevoked("成员角色不在服务端允许集合内。")
    return {"user_id": user_id, "tenant_id": tenant_id, "role": role}


def _completed_checkpoint(task: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    """识别已完成的本地 checkpoint；只补队列完成，不再次运行模型或下载。"""

    if not isinstance(task, dict) or task.get("status") != "completed":
        return None
    saved_request = task.get("request")
    if not isinstance(saved_request, dict):
        return None
    # requested_by_identity 是认证投影而非业务输入，角色变化不应让同一任务重跑；
    # 其余请求必须完全相同，避免把旧磁盘上同编号但不同参数的结果误当 checkpoint。
    comparable_saved = {key: value for key, value in saved_request.items() if key != "requested_by_identity"}
    comparable_claimed = {key: value for key, value in payload.items() if key != "requested_by_identity"}
    if comparable_saved != comparable_claimed:
        return None
    return task


def _analysis_checkpoint(
    client: Any,
    *,
    task_id: str,
    tenant_id: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """从 task_id 唯一分析运行恢复队列投影，覆盖跨实例 crash-after-persist。"""

    loader = getattr(client, "get_analysis_run_by_pipeline_task", None)
    if not callable(loader):
        # 兼容迁移滚动发布窗口：旧 adapter 实例没有新查询时不猜测 checkpoint，
        # 继续由租约和数据库唯一索引保护，部署完成后自然启用跨实例恢复。
        return None
    row = loader(pipeline_task_id=task_id, tenant_id=tenant_id)
    if not isinstance(row, dict):
        return None
    if str(row.get("pipeline_task_id") or "").strip() != task_id:
        raise SupabaseError("分析 checkpoint 返回了错误任务编号。")
    if str(row.get("tenant_id") or "").strip() != tenant_id:
        raise SupabaseError("分析 checkpoint 返回了错误租户。")
    stored = row.get("payload")
    if not isinstance(stored, dict):
        raise SupabaseError("分析 checkpoint 缺少运行载荷。")
    analysis = stored.get("run") if isinstance(stored.get("run"), dict) else stored
    if not isinstance(analysis, dict) or not analysis.get("run_id"):
        raise SupabaseError("分析 checkpoint 运行载荷不完整。")
    context = analysis.get("context") if isinstance(analysis.get("context"), dict) else {}
    if str(context.get("pipeline_task_id") or "").strip() != task_id:
        raise SupabaseError("分析 checkpoint 上下文未绑定当前任务。")
    run_completeness = str(analysis.get("run_completeness") or "")
    terminal_status = "completed" if run_completeness.startswith("complete_") else "needs_human"
    pipeline_result = {
        "task_id": task_id,
        "status": terminal_status,
        "case_id": context.get("case_id"),
        "analysis": analysis,
        "human_review_required": True,
        "checkpoint_recovered": True,
        "checkpoint_boundary": "分析运行已按 task_id 持久化；本次只修复队列终态，未重复调用模型。",
    }
    return {
        "schema_version": "cninfo_pipeline_v1",
        "task_id": task_id,
        "status": terminal_status,
        "request": payload,
        "steps": {},
        "attempt": int(row.get("attempt") or 0),
        "result": pipeline_result,
        "errors": [],
        "checkpoint_recovered": True,
    }


def run_once(*, worker_id: str | None = None, lease_seconds: int = 120) -> bool:
    """领取并执行一条任务；返回是否实际领取到任务。"""

    client = get_supabase_client()
    worker_id = worker_id or f"audittrace-worker-{socket.gethostname()}-{os.getpid()}"
    task = client.claim_pipeline_task(worker_id=worker_id, lease_seconds=lease_seconds)
    if not task:
        return False
    task_id = str(task.get("task_id") or "")
    lease_token = str(task.get("lease_token") or "").strip()
    # 没有 token 时无法对 heartbeat/complete/fail 做 CAS；继续执行会制造一个
    # 永远不能安全上报的孤儿任务，因此让数据库租约自然过期并等待重新领取。
    if not task_id or not lease_token:
        raise SupabaseLeaseLost("数据库领取结果缺少 task_id 或 lease_token。")
    payload = task.get("request_payload") if isinstance(task.get("request_payload"), dict) else {}
    stop_heartbeat = threading.Event()

    lease = _LeaseState(
        renew=lambda: client.heartbeat_pipeline_task(
            task_id=task_id,
            worker_id=worker_id,
            lease_token=lease_token,
            lease_seconds=lease_seconds,
        )
    )

    def heartbeat() -> None:
        """定期延长数据库租约，避免长任务被其他 worker 重复领取。"""

        while not stop_heartbeat.wait(_heartbeat_interval(lease_seconds)):
            if not lease.probe():
                # 旧实现会在 CAS 未命中后继续计算；现在失租是单向状态，
                # 主线程和所有受 guard 保护的持久化都会立即看到失败。
                return

    heartbeat_thread = threading.Thread(target=heartbeat, name=f"heartbeat-{task_id}", daemon=True)
    heartbeat_thread.start()
    outcome = "complete"
    outcome_payload: dict[str, Any] = {"task_id": task_id, "status": "completed"}
    guard_token = install_worker_lease_guard(lease.probe)
    try:
        identity_payload = _authoritative_identity(client, task, payload)
        lease.require_current()
        request = WorkerRequest(
            identity_payload,
            task_id=task_id,
            lease_probe=lease.probe,
        )
        checkpoint = _completed_checkpoint(load_task(_workspace_root(), task_id), payload)
        if checkpoint is None:
            checkpoint = _analysis_checkpoint(
                client,
                task_id=task_id,
                tenant_id=identity_payload["tenant_id"],
                payload=payload,
            )
        if checkpoint is not None:
            # 典型场景是业务结果已经落盘/落库，但进程在 complete RPC 前退出；
            # 重新领取只修复队列投影，绝不重复下载、模型调用或业务持久化。
            outcome_payload = checkpoint
            if checkpoint.get("status") != "completed":
                outcome = "fail_terminal"
        else:
            # 数据库租约保护队列所有权，pipeline JSON 继续保留为可解释的本地工作日志。
            materialize_task(_workspace_root(), task_id, payload, attempt=int(task.get("attempt") or 0))
            lease.require_current()
            _execute_cninfo_task(task_id, payload, request)
            if not lease.active():
                raise SupabaseLeaseLost("执行期间 worker 租约已经失效。")
            local_task = load_task(_workspace_root(), task_id)
            outcome_payload = local_task or outcome_payload
            local_status = str((local_task or {}).get("status") or "")
            if local_status in {"failed", "needs_human"}:
                # pipeline_tasks 只公开 queued/running/completed/failed 四态；需要人工
                # 确认也必须落为 failed，之后 confirm/retry 才能以 expected_status=failed
                # 做 CAS。若误写 completed，严格状态机将无法再接受合法的企业确认。
                outcome = "fail_terminal"
            elif local_status != "completed":
                # 主链正常返回却没有终态，说明本地投影不完整；保留自动重试机会，
                # 但不能把 queued/running/空状态上报成数据库 completed。
                outcome = "fail_retry"
                outcome_payload = {
                    "code": "WORKER_INCOMPLETE_LOCAL_STATE",
                    "message": "worker 主链返回后未形成可确认的任务终态。",
                }
    except Exception as error:
        if isinstance(error, SupabaseLeaseLost):
            lease.mark_lost()
            outcome = "lease_lost"
        elif isinstance(error, WorkerAuthorizationRevoked):
            outcome = "fail_authorization"
            outcome_payload = _authorization_error()
        else:
            outcome = "fail_retry"
            outcome_payload = _safe_error(error)
    finally:
        reset_worker_lease_guard(guard_token)
        stop_heartbeat.set()
        # 正常适配器调用有受控 HTTP timeout；等待当前心跳退出，避免 complete
        # 清空 token 后旧心跳才返回并把一次成功完成误判成失租。
        heartbeat_thread.join(timeout=max(2.0, min(30.0, float(max(30, lease_seconds)))))

    if heartbeat_thread.is_alive():
        lease.mark_lost()
        return True
    if outcome == "lease_lost" or not lease.active():
        # 旧租约持有者不得调用 fail；fail 本身也是一次状态写，会覆盖新 worker 的真实结果。
        return True
    try:
        if outcome == "complete":
            client.complete_pipeline_task(
                task_id=task_id,
                worker_id=worker_id,
                lease_token=lease_token,
                result=outcome_payload,
            )
        else:
            client.fail_pipeline_task(
                task_id=task_id,
                worker_id=worker_id,
                lease_token=lease_token,
                error=outcome_payload,
                retry=outcome == "fail_retry",
            )
    except SupabaseLeaseLost:
        # complete/fail 自身也由 token fencing；CAS 未命中说明结果应由新 worker 上报。
        lease.mark_lost()
    return True


def serve(*, poll_seconds: float = 2.0, once: bool = False) -> None:
    """在公网持久化模式轮询任务，本地模式则明确拒绝误启动。"""

    if persistence_mode() != "supabase":
        raise RuntimeError("worker 只应在 AUDITTRACE_PERSISTENCE=supabase 时启动；本地模式由 web 进程处理任务。")
    if once:
        run_once()
        return
    while True:
        try:
            claimed = run_once()
        except SupabaseError:
            claimed = False
        if not claimed:
            time.sleep(max(0.5, poll_seconds))


def main() -> None:
    """解析最小命令行参数并启动受控任务轮询。"""

    parser = argparse.ArgumentParser(description="审迹智链 Supabase pipeline worker")
    parser.add_argument("--once", action="store_true", help="只领取并执行一条任务")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    serve(poll_seconds=args.poll_seconds, once=args.once)


if __name__ == "__main__":
    main()
