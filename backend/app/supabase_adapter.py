"""可选的 Supabase Auth、Postgres、Storage 与任务队列适配层。

本地竞赛模式不导入 Supabase SDK，也不需要网络配置；只有显式设置
``AUDITTRACE_PERSISTENCE=supabase`` 后，路由和 worker 才会使用这里的
REST 接口。所有异常都转换为不含密钥、请求头和原文的稳定错误。
"""

from __future__ import annotations

import hashlib
import json
import os
import math
import re
import uuid
from contextvars import ContextVar, Token
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote

import httpx


_TABLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_BUCKET_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_STORAGE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class SupabaseError(RuntimeError):
    """Supabase 适配层的稳定错误基类。"""

    code = "SUPABASE_ERROR"
    status_code = 503


class SupabaseNotConfigured(SupabaseError):
    code = "SUPABASE_NOT_CONFIGURED"


class SupabaseAuthError(SupabaseError):
    code = "SUPABASE_AUTH_FAILED"
    status_code = 401


class SupabaseConflict(SupabaseError):
    """远程对象存在但不满足当前写入前置条件，路由应稳定映射为 409。"""

    code = "SUPABASE_CONFLICT"
    status_code = 409


class SupabaseLeaseLost(SupabaseConflict):
    """worker 的租约已过期或被新 worker 取代，旧执行者必须停止副作用。"""

    code = "SUPABASE_LEASE_LOST"


class SupabaseUnavailable(SupabaseError):
    code = "SUPABASE_UNAVAILABLE"


class SupabaseRequestError(SupabaseError):
    code = "SUPABASE_REQUEST_FAILED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_WORKER_LEASE_GUARD: ContextVar[Callable[[], bool] | None] = ContextVar(
    "audittrace_worker_lease_guard",
    default=None,
)


def install_worker_lease_guard(guard: Callable[[], bool]) -> Token[Callable[[], bool] | None]:
    """把当前 worker 的租约探针绑定到执行线程，供所有持久化写入统一 fencing。"""

    return _WORKER_LEASE_GUARD.set(guard)


def reset_worker_lease_guard(token: Token[Callable[[], bool] | None]) -> None:
    """任务结束后恢复线程上下文，避免下一个任务继承已经失效的租约。"""

    _WORKER_LEASE_GUARD.reset(token)


def assert_worker_lease() -> None:
    """有 worker 上下文时才检查；普通 web 请求不受该内部探针影响。"""

    guard = _WORKER_LEASE_GUARD.get()
    if guard is not None and not guard():
        raise SupabaseLeaseLost("worker 租约已经失效，已阻止继续写入。")


def _official_public_case(case_id: str, *, registry_mode: str | None = None, sample_type: str | None = None) -> bool:
    """巨潮官方年报是全局只读证据缓存，用户运行和同意仍按租户单独归属。"""

    normalized = case_id.upper()
    # 编号前缀和 manifest 的 sample_type 都可由上传者控制；只有服务端巨潮注册器
    # 写入的 provenance 与公开类型同时满足时，才允许提升为全局只读证据。
    return (
        normalized.startswith("CNINFO_")
        and registry_mode == "cninfo_official_auto"
        and sample_type == "public"
    )


def _case_scope_tenant(
    case_id: str,
    tenant_id: str | None,
    *,
    registry_mode: str | None = None,
    sample_type: str | None = None,
) -> str | None:
    """只把官方公开证据归入全局 scope；授权/脱敏案例永不被提升为公共缓存。"""

    if _official_public_case(case_id, registry_mode=registry_mode, sample_type=sample_type):
        return None
    return str(tenant_id or "").strip() or None


@dataclass(frozen=True)
class SupabaseConfig:
    """从环境变量读取的非敏感配置；密钥只保存在进程内，不写入日志。"""

    mode: str
    url: str | None
    anon_key: str | None
    service_role_key: str | None
    private_bucket: str
    signed_url_seconds: int
    timeout_seconds: float

    @classmethod
    def from_env(cls, *, mode_override: str | None = None) -> "SupabaseConfig":
        mode = (mode_override if mode_override is not None else os.getenv("AUDITTRACE_PERSISTENCE", "local")).strip().lower() or "local"
        # NEXT_PUBLIC_SUPABASE_URL is accepted only as a server-side compatibility
        # alias.  The public page never receives this value or the service key.
        url = (
            os.getenv("SUPABASE_URL", "").strip()
            or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
        ).rstrip("/") or None
        anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip() or None
        service_role_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_SECRET_KEY", "").strip()
        ) or None
        try:
            signed_url_seconds = max(60, min(86_400, int(os.getenv("SUPABASE_SIGNED_URL_SECONDS", "600"))))
        except ValueError:
            signed_url_seconds = 600
        try:
            timeout_seconds = max(1.0, min(60.0, float(os.getenv("SUPABASE_HTTP_TIMEOUT_SECONDS", "15"))))
        except ValueError:
            timeout_seconds = 15.0
        return cls(
            mode=mode,
            url=url,
            anon_key=anon_key,
            service_role_key=service_role_key,
            private_bucket=os.getenv("SUPABASE_PRIVATE_BUCKET", "audittrace-private").strip() or "audittrace-private",
            signed_url_seconds=signed_url_seconds,
            timeout_seconds=timeout_seconds,
        )

    @property
    def is_supabase(self) -> bool:
        return self.mode == "supabase"

    @property
    def configured(self) -> bool:
        return self.is_supabase and bool(self.url and (self.anon_key or self.service_role_key))


def persistence_mode() -> str:
    return SupabaseConfig.from_env().mode


def supabase_enabled() -> bool:
    return SupabaseConfig.from_env().is_supabase


def demo_task_supabase_enabled() -> bool:
    """独立演示任务台账开关；不改变核心案例的 local/supabase 模式。"""

    return os.getenv("AUDITTRACE_DEMO_TASK_PERSISTENCE", "local").strip().lower() == "supabase"


def get_demo_task_client() -> "SupabaseClient":
    """读取演示台账专用 Supabase 客户端，要求服务端配置完整。"""

    config = SupabaseConfig.from_env(mode_override="supabase")
    # 演示任务表完全关闭 anon/authenticated 的 RLS 读写，只能由服务端
    # service-role RPC/REST 访问；存在 anon key 不能替代 service-role key。
    if not config.url or not config.service_role_key:
        raise SupabaseNotConfigured("演示任务台账需要 SUPABASE_URL 与 SUPABASE_SERVICE_ROLE_KEY。")
    return SupabaseClient(config)


class SupabaseClient:
    """只使用官方 REST 端点，避免把服务密钥暴露给浏览器。"""

    def __init__(self, config: SupabaseConfig | None = None) -> None:
        self.config = config or SupabaseConfig.from_env()
        if not self.config.configured:
            raise SupabaseNotConfigured("Supabase 持久化模式未完成服务端配置。")

    def _headers(self, *, token: str | None = None, service: bool = False) -> dict[str, str]:
        if service:
            if not self.config.service_role_key:
                raise SupabaseNotConfigured("该 Supabase 操作需要服务端 service-role key。")
            key = self.config.service_role_key
        else:
            key = self.config.anon_key or self.config.service_role_key
        if not key:
            raise SupabaseNotConfigured("Supabase 服务端密钥未配置。")
        headers = {"apikey": key, "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif service:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        service: bool = False,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        raw_content: bool = False,
    ) -> Any:
        if not self.config.url:
            raise SupabaseNotConfigured("Supabase URL 未配置。")
        request_headers = self._headers(token=token, service=service)
        request_headers.update(headers or {})
        url = f"{self.config.url}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=self.config.timeout_seconds, follow_redirects=False) as client:
                response = client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    content=content,
                    headers=request_headers,
                )
        except httpx.HTTPError as error:
            raise SupabaseUnavailable("Supabase 服务暂时不可达。") from error
        if response.status_code in {401, 403} or (
            response.status_code == 400 and path.lstrip("/").startswith("auth/v1/token")
        ):
            # 登录与刷新失败只返回稳定身份错误，绝不把 Supabase 的原始响应或凭据回显给调用方。
            raise SupabaseAuthError("Supabase 身份验证或权限校验失败。")
        if response.status_code >= 400:
            raise SupabaseRequestError(f"Supabase 请求未完成（HTTP {response.status_code}）。")
        if not response.content:
            return None
        if raw_content:
            return bytes(response.content)
        try:
            return response.json()
        except ValueError:
            return {"text": response.text[:500]}

    def verify_user(self, access_token: str) -> dict[str, Any]:
        payload = self._request("GET", "auth/v1/user", token=access_token)
        if not isinstance(payload, dict) or not str(payload.get("id") or "").strip():
            raise SupabaseAuthError("Supabase 未返回有效用户身份。")
        return payload

    def sign_in_with_password(self, *, email: str, password: str) -> dict[str, Any]:
        """通过 Supabase Auth 密码流换取服务端会话；调用方不得把返回令牌放进 JSON。"""

        payload = self._request(
            "POST",
            "auth/v1/token?grant_type=password",
            json_body={"email": email, "password": password},
        )
        return self._validated_auth_session(payload)

    def refresh_session(self, *, refresh_token: str) -> dict[str, Any]:
        """使用 HttpOnly 刷新令牌轮换会话，不接受浏览器自报用户或租户。"""

        payload = self._request(
            "POST",
            "auth/v1/token?grant_type=refresh_token",
            json_body={"refresh_token": refresh_token},
        )
        return self._validated_auth_session(payload)

    @staticmethod
    def _validated_auth_session(payload: Any) -> dict[str, Any]:
        """验证身份服务最小响应合同，缺令牌时按服务异常失败关闭。"""

        if not isinstance(payload, dict):
            raise SupabaseUnavailable("Supabase Auth 未返回有效会话。")
        access_token = str(payload.get("access_token") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip()
        if not access_token or not refresh_token:
            raise SupabaseUnavailable("Supabase Auth 未返回完整会话。")
        return payload

    @staticmethod
    def _validate_table(table: str) -> str:
        if not _TABLE_PATTERN.fullmatch(table):
            raise SupabaseRequestError("数据库表名不在服务端白名单中。")
        return table

    @staticmethod
    def _validate_bucket(bucket: str) -> str:
        if not _BUCKET_PATTERN.fullmatch(bucket):
            raise SupabaseRequestError("Storage bucket 名称不合法。")
        return bucket

    @staticmethod
    def _validate_storage_path(object_path: str) -> str:
        normalized = object_path.strip().strip("/")
        parts = normalized.split("/") if normalized else []
        if not parts or any(part in {".", ".."} or not _STORAGE_SEGMENT_PATTERN.fullmatch(part) for part in parts):
            raise SupabaseRequestError("Storage 对象路径不合法。")
        return "/".join(parts)

    def select_table(
        self,
        table: str,
        *,
        filters: dict[str, str] | None = None,
        select: str = "*",
        token: str | None = None,
        service: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"select": select}
        for key, value in (filters or {}).items():
            if not _TABLE_PATTERN.fullmatch(key):
                raise SupabaseRequestError("数据库筛选列名不在服务端白名单中。")
            params[key] = value
        payload = self._request("GET", f"rest/v1/{self._validate_table(table)}", token=token, service=service, params=params)
        return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []

    def insert_table(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        token: str | None = None,
        service: bool = False,
        upsert: bool = False,
        on_conflict: str | None = None,
    ) -> list[dict[str, Any]]:
        # worker 一旦丢失租约，所有数据库写入在发出 HTTP 请求前统一失败关闭。
        assert_worker_lease()
        headers = {"Prefer": "return=representation"}
        path = f"rest/v1/{self._validate_table(table)}"
        if upsert:
            headers["Prefer"] = "resolution=merge-duplicates,return=representation"
            if on_conflict:
                path = f"{path}?on_conflict={quote(on_conflict, safe=',') }"
        payload = self._request(
            "POST",
            path,
            token=token,
            service=service,
            json_body=rows,
            headers=headers,
        )
        return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []

    def update_table(
        self,
        table: str,
        values: dict[str, Any],
        *,
        filters: dict[str, str],
        service: bool = False,
    ) -> list[dict[str, Any]]:
        """按白名单列执行 PATCH，并返回实际更新行；零行更新由上层按并发或不存在处理。"""

        assert_worker_lease()
        params: dict[str, str] = {}
        for key, value in filters.items():
            if not _TABLE_PATTERN.fullmatch(key):
                raise SupabaseRequestError("数据库筛选列名不在服务端白名单中。")
            params[key] = value
        payload = self._request(
            "PATCH",
            f"rest/v1/{self._validate_table(table)}",
            service=service,
            params=params,
            json_body=values,
            headers={"Prefer": "return=representation"},
        )
        return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []

    def list_memberships(self, user_id: str, *, token: str) -> list[dict[str, Any]]:
        return self.select_table(
            "organization_members",
            filters={"user_id": f"eq.{user_id}", "active": "eq.true"},
            select="organization_id,role,active",
            token=token,
        )

    def get_active_membership(self, *, user_id: str, tenant_id: str) -> dict[str, Any] | None:
        """worker 用 service role 重新确认排队用户当前仍是有效成员，拒绝信任旧身份快照。"""

        rows = self.select_table(
            "organization_members",
            filters={
                "user_id": f"eq.{user_id}",
                "organization_id": f"eq.{tenant_id}",
                "active": "eq.true",
            },
            select="organization_id,user_id,role,active",
            service=True,
        )
        return rows[0] if rows else None

    def enqueue_pipeline_task(
        self,
        *,
        task_id: str,
        request_payload: dict[str, Any],
        tenant_id: str | None,
        requested_by: str | None,
    ) -> dict[str, Any]:
        rows = self.insert_table(
            "pipeline_tasks",
            [
                {
                    "task_id": task_id,
                    "tenant_id": tenant_id,
                    "requested_by": requested_by,
                    "request_payload": request_payload,
                    "status": "queued",
                    "attempt": 0,
                    "available_at": _now(),
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            ],
            service=True,
            upsert=True,
            on_conflict="task_id",
        )
        return rows[0] if rows else {"task_id": task_id, "status": "queued"}

    def get_pipeline_task(self, task_id: str) -> dict[str, Any] | None:
        rows = self.select_table(
            "pipeline_tasks",
            filters={"task_id": f"eq.{task_id}"},
            # tenant_id/requested_by 只供 web 服务端做对象级授权，路由返回前会显式移除。
            select="task_id,tenant_id,requested_by,request_payload,status,attempt,lease_token,lease_until,result,error,updated_at,created_at",
            service=True,
        )
        return rows[0] if rows else None

    # —— 公开竞赛演示任务台账 ——
    # 这些方法与企业 pipeline_tasks 分开，避免公开任务的 degraded/cancelled/
    # interrupted 状态污染内部队列合同；全部调用均使用 service role。
    def insert_demo_run_task(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self.insert_table("demo_run_tasks", [row], service=True)
        return rows[0] if rows else row

    def get_demo_run_task(self, task_id: str) -> dict[str, Any] | None:
        rows = self.select_table(
            "demo_run_tasks",
            filters={"task_id": f"eq.{task_id}"},
            select="*",
            service=True,
        )
        return rows[0] if rows else None

    def find_active_demo_run_task(self, *, case_id: str, request_sha256: str) -> dict[str, Any] | None:
        rows = self.select_table(
            "demo_run_tasks",
            filters={
                "case_id": f"eq.{case_id}",
                "request_sha256": f"eq.{request_sha256}",
                "status": "in.(queued,running)",
            },
            select="*",
            service=True,
        )
        return rows[0] if rows else None

    def find_demo_run_task_by_idempotency(self, *, idempotency_key_sha256: str) -> dict[str, Any] | None:
        """按服务端哈希查找幂等键，重复请求始终返回同一公开任务。"""

        rows = self.select_table(
            "demo_run_tasks",
            filters={"idempotency_key_sha256": f"eq.{idempotency_key_sha256}"},
            select="*",
            service=True,
        )
        return rows[0] if rows else None

    def claim_demo_run_task(self, *, task_id: str, owner: str, lease_seconds: int) -> dict[str, Any] | None:
        payload = self._request(
            "POST",
            "rest/v1/rpc/claim_demo_run_task",
            service=True,
            json_body={"p_task_id": task_id, "p_owner": owner, "p_lease_seconds": lease_seconds},
        )
        if isinstance(payload, list):
            return payload[0] if payload and isinstance(payload[0], dict) else None
        return payload if isinstance(payload, dict) and payload.get("task_id") else None

    def heartbeat_demo_run_task(self, *, task_id: str, owner: str, lease_token: str, lease_seconds: int) -> bool:
        payload = self._request(
            "POST",
            "rest/v1/rpc/heartbeat_demo_run_task",
            service=True,
            json_body={
                "p_task_id": task_id,
                "p_owner": owner,
                "p_lease_token": lease_token,
                "p_lease_seconds": lease_seconds,
            },
        )
        return payload is True

    def demo_run_task_lease_current(self, *, task_id: str, owner: str, lease_token: str) -> bool:
        rows = self.select_table(
            "demo_run_tasks",
            filters={
                "task_id": f"eq.{task_id}",
                "lease_owner": f"eq.{owner}",
                "lease_token": f"eq.{lease_token}",
                "status": "eq.running",
                "lease_until": "gt." + _now(),
            },
            select="task_id",
            service=True,
        )
        return bool(rows)

    def claim_next_demo_run_task(self, *, owner: str, lease_seconds: int) -> dict[str, Any] | None:
        payload = self._request(
            "POST",
            "rest/v1/rpc/claim_next_demo_run_task",
            service=True,
            json_body={"p_owner": owner, "p_lease_seconds": lease_seconds},
        )
        if isinstance(payload, list):
            return payload[0] if payload and isinstance(payload[0], dict) else None
        return payload if isinstance(payload, dict) and payload.get("task_id") else None

    def interrupt_expired_demo_run_tasks(self) -> int:
        payload = self._request("POST", "rest/v1/rpc/interrupt_expired_demo_run_tasks", service=True, json_body={})
        try:
            return int(payload or 0)
        except (TypeError, ValueError):
            return 0

    def cancel_demo_run_task(self, *, task_id: str) -> dict[str, Any] | None:
        payload = self._request(
            "POST",
            "rest/v1/rpc/cancel_demo_run_task",
            service=True,
            json_body={"p_task_id": task_id},
        )
        if isinstance(payload, list):
            return payload[0] if payload and isinstance(payload[0], dict) else None
        return payload if isinstance(payload, dict) else None

    def update_demo_run_task(
        self,
        *,
        task_id: str,
        values: dict[str, Any],
        expected_version: int,
        lease_token: str | None = None,
    ) -> dict[str, Any] | None:
        filters = {"task_id": f"eq.{task_id}", "version": f"eq.{int(expected_version)}"}
        if lease_token:
            filters["lease_token"] = f"eq.{lease_token}"
        rows = self.update_table(
            "demo_run_tasks",
            {**values, "version": int(expected_version) + 1, "updated_at": _now()},
            filters=filters,
            service=True,
        )
        return rows[0] if rows else None

    def record_model_quality_event(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self.insert_table("model_quality_events", [row], service=True, upsert=True, on_conflict="run_id")
        return rows[0] if rows else row

    def list_model_quality_events(self, *, model_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """读取最近真实运行的脱敏质量事件；不读取模型原文或证据正文。"""

        bounded_limit = max(1, min(100, int(limit)))
        payload = self._request(
            "GET",
            "rest/v1/model_quality_events",
            service=True,
            params={
                "select": "run_id,task_id,case_id,model_id,route,outcome,provider_call_count,completed_roles,input_tokens,output_tokens,failure_codes,created_at",
                "model_id": f"eq.{model_id}",
                "order": "created_at.desc",
                "limit": str(bounded_limit),
            },
        )
        return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []

    def probe_demo_task_store(self) -> None:
        """Confirm the two public-demo tables are reachable with service access.

        This is intentionally read-only.  Insert/update permissions are still
        proven by the controlled smoke run after deployment, not by creating a
        synthetic task during every health request.
        """

        self.select_table("demo_run_tasks", select="task_id", service=True)
        self.select_table("model_quality_events", select="run_id", service=True)

    # —— 公开模型额度与缓存台账 ——
    # 额度检查必须在数据库事务中完成，不能把 Web 进程内 SQLite 的计数当成
    # Render 多实例之间的全局事实。RPC 只返回脱敏 JSON，不返回任何供应商内容。
    def reserve_public_model_usage(
        self,
        *,
        reservation_id: str,
        client_hash: str,
        window_seconds: int,
        per_ip: int,
        global_window: int,
        max_concurrent: int,
        daily_runs: int,
        reservation_ttl_seconds: int,
        batch: bool = False,
    ) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "rest/v1/rpc/reserve_public_model_usage",
            service=True,
            json_body={
                "p_reservation_id": reservation_id,
                "p_client_hash": client_hash,
                "p_window_seconds": int(window_seconds),
                "p_per_ip": int(per_ip),
                "p_global_window": int(global_window),
                "p_max_concurrent": int(max_concurrent),
                "p_daily_runs": int(daily_runs),
                "p_reservation_ttl_seconds": int(reservation_ttl_seconds),
                "p_batch": bool(batch),
            },
        )
        if isinstance(payload, list):
            payload = payload[0] if payload and isinstance(payload[0], dict) else {}
        return payload if isinstance(payload, dict) else {}

    def settle_public_model_usage(
        self,
        *,
        reservation_id: str,
        input_tokens: int,
        output_tokens: int,
        daily_input_tokens: int,
        daily_output_tokens: int,
    ) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "rest/v1/rpc/settle_public_model_usage",
            service=True,
            json_body={
                "p_reservation_id": reservation_id,
                "p_input_tokens": max(0, int(input_tokens)),
                "p_output_tokens": max(0, int(output_tokens)),
                "p_daily_input_tokens": int(daily_input_tokens),
                "p_daily_output_tokens": int(daily_output_tokens),
            },
        )
        if isinstance(payload, list):
            payload = payload[0] if payload and isinstance(payload[0], dict) else {}
        return payload if isinstance(payload, dict) else {}

    def release_public_model_usage(self, *, reservation_id: str) -> None:
        self._request(
            "POST",
            "rest/v1/rpc/release_public_model_usage",
            service=True,
            json_body={"p_reservation_id": reservation_id},
        )

    def snapshot_public_model_usage(
        self,
        *,
        client_hash: str | None,
        window_seconds: int,
        global_window: int,
        max_concurrent: int,
        reservation_ttl_seconds: int,
        daily_runs: int,
    ) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "rest/v1/rpc/snapshot_public_model_usage",
            service=True,
            json_body={
                "p_client_hash": client_hash,
                "p_window_seconds": int(window_seconds),
                "p_global_window": int(global_window),
                "p_max_concurrent": int(max_concurrent),
                "p_reservation_ttl_seconds": int(reservation_ttl_seconds),
                "p_daily_runs": int(daily_runs),
            },
        )
        if isinstance(payload, list):
            payload = payload[0] if payload and isinstance(payload[0], dict) else {}
        return payload if isinstance(payload, dict) else {}

    def get_public_model_cache(self, *, cache_key_hash: str) -> dict[str, Any] | None:
        rows = self.select_table(
            "public_model_cache",
            filters={"cache_key_hash": f"eq.{cache_key_hash}"},
            select="cache_key_hash,created_at,run_payload",
            service=True,
        )
        return rows[0] if rows else None

    def put_public_model_cache(self, *, cache_key_hash: str, run_payload: dict[str, Any]) -> dict[str, Any] | None:
        rows = self.insert_table(
            "public_model_cache",
            [{"cache_key_hash": cache_key_hash, "created_at": _now(), "run_payload": run_payload}],
            service=True,
            upsert=True,
            on_conflict="cache_key_hash",
        )
        return rows[0] if rows else None

    def delete_public_model_cache(self, *, cache_key_hash: str) -> None:
        self._request(
            "DELETE",
            "rest/v1/public_model_cache",
            service=True,
            params={"cache_key_hash": f"eq.{cache_key_hash}"},
        )

    def requeue_pipeline_task(
        self,
        *,
        task_id: str,
        request_payload: dict[str, Any],
        expected_status: str,
        expected_attempt: int,
    ) -> None:
        """用状态和 attempt 做 CAS；旧标签页不能把已运行任务重新清回 queued。"""

        payload = self._request(
            "POST",
            "rest/v1/rpc/requeue_pipeline_task",
            service=True,
            json_body={
                "p_task_id": task_id,
                "p_request_payload": request_payload,
                "p_expected_status": expected_status,
                "p_expected_attempt": expected_attempt,
            },
        )
        if payload is not True:
            raise SupabaseConflict("任务状态已经变化，不能重复重排。")

    def get_case_metadata(self, case_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
        """按当前租户精确取案例；未登录时只允许读取 tenant_id 为空的公开记录。"""

        scopes = [str(tenant_id).strip()] if tenant_id else []
        # 登录用户先看自己的同名私有案例，再回退到全局公开证据；匿名永不整表查询私有记录。
        scopes.append("")
        for scope in dict.fromkeys(scopes):
            rows = self.select_table(
                "cases",
                filters={
                    "case_id": f"eq.{case_id}",
                    "tenant_id": f"eq.{scope}" if scope else "is.null",
                    "import_status": "eq.ready",
                },
                select="case_scope,case_id,tenant_id,sample_type,company_name,ticker,source_snapshot_id,t0,import_status,metadata",
                service=True,
            )
            if rows:
                return rows[0]
        return None

    def list_case_metadata(self, *, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """只返回公开案例和当前租户案例，服务端不会把其他租户整表拉回。"""

        rows = self.select_table(
            "cases",
            filters={"sample_type": "eq.public", "tenant_id": "is.null", "import_status": "eq.ready"},
            select="case_scope,case_id,tenant_id,sample_type,company_name,ticker,source_snapshot_id,t0,metadata",
            service=True,
        )
        if tenant_id:
            rows.extend(
                self.select_table(
                    "cases",
                    filters={"tenant_id": f"eq.{tenant_id}", "import_status": "eq.ready"},
                    select="case_scope,case_id,tenant_id,sample_type,company_name,ticker,source_snapshot_id,t0,metadata",
                    service=True,
                )
            )
        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            if row.get("case_id"):
                unique[(str(row.get("tenant_id") or "PUBLIC"), str(row["case_id"]))] = row
        return list(unique.values())

    def get_case_bundle(self, case_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
        """恢复 web 实例没有本地磁盘时所需的案例卡片和字段证据。"""

        metadata_row = self.get_case_metadata(case_id, tenant_id=tenant_id)
        if metadata_row is None:
            return None
        resolved_tenant = str(metadata_row.get("tenant_id") or "").strip()
        scope_filters = {
            "case_id": f"eq.{case_id}",
            "tenant_id": f"eq.{resolved_tenant}" if resolved_tenant else "is.null",
        }
        metadata = metadata_row.get("metadata") if isinstance(metadata_row.get("metadata"), dict) else {}
        case = {
            **metadata,
            "case_scope": metadata_row.get("case_scope"),
            "case_id": metadata_row.get("case_id"),
            "tenant_id": metadata_row.get("tenant_id"),
            "sample_type": metadata_row.get("sample_type"),
            "company_name": metadata_row.get("company_name"),
            "company_alias": metadata.get("company_alias") or metadata_row.get("company_name"),
            "ticker": metadata_row.get("ticker") or "",
            "source_snapshot_id": metadata_row.get("source_snapshot_id"),
            "t0": metadata_row.get("t0"),
            "registry_mode": metadata.get("registry_mode") or "supabase_postgres",
            "documents": [],
            "financial_fields": [],
            "structured_evidence": [],
        }
        documents = self.select_table(
            "report_documents",
            filters=scope_filters,
            select="document_id,report_year,source_url,sha256,page_count,validation_status,storage_object_path,metadata",
            service=True,
        )
        for document in documents:
            document_metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
            case["documents"].append(
                {
                    **document_metadata,
                    "document_id": document.get("document_id"),
                    "report_year": document.get("report_year"),
                    # 内部案例的原始 URL 不作为前端/数据库公开回退地址；访问统一走私有 Storage。
                    "source_url": None if case.get("tenant_id") else document.get("source_url"),
                    "sha256": document.get("sha256"),
                    "page_count": document.get("page_count"),
                    "validation_status": document.get("validation_status"),
                    "storage_object_path": document.get("storage_object_path"),
                }
            )
        evidence = self.select_table(
            "field_evidence",
            filters=scope_filters,
            select="evidence_id,field_id,year,value,document_id,pdf_page,file_sha256,metadata",
            service=True,
        )
        for row in evidence:
            row_metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            case["financial_fields"].append(
                {
                    **row_metadata,
                    "evidence_id": row.get("evidence_id"),
                    "field_id": row.get("field_id"),
                    "year": row.get("year"),
                    "value": row.get("value"),
                    "document_id": row.get("document_id"),
                    "pdf_page": row.get("pdf_page"),
                    "file_sha256": row.get("file_sha256"),
                }
            )
        if tenant_id and not resolved_tenant and case.get("case_scope"):
            overlays = self.select_table(
                "field_review_overlays",
                filters={
                    "tenant_id": f"eq.{tenant_id}",
                    "case_scope": f"eq.{case['case_scope']}",
                },
                select="evidence_id,field_id,value,pdf_page,metadata,reviewed_by,updated_at",
                service=True,
            )
            overlays_by_evidence = {str(item.get("evidence_id") or ""): item for item in overlays}
            merged: list[dict[str, Any]] = []
            for base in case["financial_fields"]:
                overlay = overlays_by_evidence.get(str(base.get("evidence_id") or ""))
                overlay_metadata = overlay.get("metadata") if overlay and isinstance(overlay.get("metadata"), dict) else None
                merged.append({**base, **overlay_metadata} if overlay_metadata else base)
            case["financial_fields"] = merged
        case["available_report_years"] = sorted({int(item["report_year"]) for item in case["documents"] if item.get("report_year")}, reverse=True)
        case["available_years"] = metadata.get("available_years") or sorted({int(item["year"]) for item in case["financial_fields"] if item.get("year")}, reverse=True)
        case["model_transfer_allowed"] = bool(metadata.get("model_transfer_allowed"))
        return case

    def update_case_field_review(
        self,
        *,
        case: dict[str, Any],
        confirmation: dict[str, Any],
        tenant_id: str,
        reviewer_user_id: str,
    ) -> dict[str, Any]:
        """直接更新远程字段证据，并保留不可变候选快照与全部人工处理历史。"""

        if case.get("registry_mode") != "cninfo_official_auto":
            raise SupabaseConflict("只有巨潮自动案例支持字段真人确认。")
        field_id = str(confirmation.get("field_id") or "")
        rows = deepcopy(case.get("financial_fields") or [])
        row = next(
            (
                item
                for item in rows
                if str(item.get("field_id") or f"{item.get('field_kind')}_{item.get('year')}") == field_id
            ),
            None,
        )
        if row is None or not str(row.get("evidence_id") or "").strip():
            raise SupabaseConflict("未找到对应字段候选。")
        reviewer = str(confirmation.get("reviewer") or "").strip()
        decision = str(confirmation.get("decision") or "")
        reason = str(confirmation.get("reason") or "").strip()
        if not reviewer or decision not in {"confirm", "correct", "reject"}:
            raise SupabaseConflict("字段处理记录不完整。")
        if decision in {"correct", "reject"} and not reason:
            raise SupabaseConflict("修正或拒绝字段必须填写原因。")
        row["field_id"] = field_id
        if not isinstance(row.get("candidate"), dict):
            row["candidate"] = {
                "value": row.get("value"),
                "pdf_page": row.get("pdf_page"),
                "document_id": row.get("document_id"),
                "locator": row.get("locator"),
            }
        history = row.get("human_review_history")
        if not isinstance(history, list):
            history = []
        original = {
            "value": row.get("value"),
            "pdf_page": row.get("pdf_page"),
            "document_id": row.get("document_id"),
            "locator": row.get("locator"),
        }
        if decision == "correct":
            try:
                corrected_value = float(confirmation.get("corrected_value"))
                corrected_page = int(confirmation.get("corrected_pdf_page"))
            except (TypeError, ValueError) as error:
                raise SupabaseConflict("修正后的金额或 PDF 页码无效。") from error
            if not math.isfinite(corrected_value) or corrected_page < 1:
                raise SupabaseConflict("修正后的金额或 PDF 页码超出边界。")
            documents = {str(item.get("document_id") or ""): item for item in case.get("documents", [])}
            document = documents.get(str(row.get("document_id") or ""))
            if document and corrected_page > int(document.get("page_count") or 0):
                raise SupabaseConflict("修正后的 PDF 页码超过已校验原件页数。")
            row["value"] = corrected_value
            row["pdf_page"] = corrected_page
            if confirmation.get("corrected_locator"):
                row["locator"] = str(confirmation["corrected_locator"])[:300]
            row["source_review_status"] = "human_corrected"
        elif decision == "confirm":
            row["source_review_status"] = "human_confirmed"
        else:
            row["source_review_status"] = "human_rejected"
        review = {
            "status": {"confirm": "confirmed", "correct": "corrected", "reject": "rejected"}[decision],
            "decision": decision,
            "reviewer": reviewer,
            "reviewed_at": _now(),
            "reason": reason,
            "original": original,
        }
        row["human_review_history"] = [*history, deepcopy(review)]
        row["human_review"] = review
        if not str(case.get("tenant_id") or "").strip():
            case_scope = str(case.get("case_scope") or "").strip()
            if not tenant_id or not reviewer_user_id or not case_scope:
                raise SupabaseConflict("公开字段复核缺少租户 overlay 归属。")
            overlaid = self.insert_table(
                "field_review_overlays",
                [
                    {
                        "tenant_id": tenant_id,
                        "case_scope": case_scope,
                        "case_id": case.get("case_id"),
                        "evidence_id": row.get("evidence_id"),
                        "field_id": field_id,
                        "value": row.get("value"),
                        "pdf_page": row.get("pdf_page"),
                        "metadata": row,
                        "reviewed_by": reviewer_user_id,
                        "updated_at": _now(),
                    }
                ],
                service=True,
                upsert=True,
                on_conflict="tenant_id,case_scope,evidence_id",
            )
            if not overlaid:
                raise SupabaseConflict("公开字段租户复核 overlay 未写入。")
            return {"field": row, "rows": rows, "storage": "tenant_review_overlay"}
        updated = self.update_table(
            "field_evidence",
            {
                "field_id": field_id,
                "value": row.get("value"),
                "pdf_page": row.get("pdf_page"),
                "metadata": row,
            },
            filters={
                "case_id": f"eq.{case.get('case_id')}",
                "tenant_id": (
                    f"eq.{str(case.get('tenant_id')).strip()}"
                    if str(case.get("tenant_id") or "").strip()
                    else "is.null"
                ),
                "evidence_id": f"eq.{row.get('evidence_id')}",
            },
            service=True,
        )
        if not updated:
            raise SupabaseConflict("远程字段复核未写入。")
        return {"field": row, "rows": rows}

    def get_analysis_run(self, run_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
        """运行载荷按运行自身租户取回；匿名只能读取明确 tenant_id 为空的运行。"""

        scopes = [str(tenant_id).strip()] if tenant_id else []
        scopes.append("")
        for scope in dict.fromkeys(scopes):
            rows = self.select_table(
                "analysis_runs",
                filters={
                    "run_id": f"eq.{run_id}",
                    "tenant_id": f"eq.{scope}" if scope else "is.null",
                },
                select="run_id,case_id,case_tenant_id,tenant_id,pipeline_task_id,status,run_completeness,payload,updated_at",
                service=True,
            )
            if rows:
                return rows[0]
        return None

    def get_analysis_run_by_pipeline_task(
        self,
        *,
        pipeline_task_id: str,
        tenant_id: str,
    ) -> dict[str, Any] | None:
        """按租户与任务幂等键精确读取 checkpoint，禁止跨租户 task_id 猜测。"""

        if not pipeline_task_id.strip() or not tenant_id.strip():
            raise SupabaseRequestError("分析 checkpoint 缺少任务或租户编号。")
        rows = self.select_table(
            "analysis_runs",
            filters={
                "pipeline_task_id": f"eq.{pipeline_task_id}",
                "tenant_id": f"eq.{tenant_id}",
            },
            select="run_id,case_id,case_tenant_id,tenant_id,pipeline_task_id,status,run_completeness,payload,updated_at",
            service=True,
        )
        if len(rows) > 1:
            # 数据库唯一索引正常时不可能出现多行；异常数据不能任取一行并重复上报。
            raise SupabaseConflict("同一队列任务存在多个分析 checkpoint。")
        return rows[0] if rows else None

    def persist_run_cache(
        self,
        *,
        cache_id: str,
        source_run_id: str,
        case_id: str,
        case_tenant_id: str | None,
        tenant_id: str,
        created_by: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """保存人工批准缓存的完整回放载荷，令下一台 web 不依赖本机 cache 文件。"""

        if str(payload.get("cache_id") or "") != cache_id or not isinstance(payload.get("stored"), dict):
            raise SupabaseRequestError("运行缓存载荷不完整。")
        rows = self.insert_table(
            "run_caches",
            [
                {
                    "cache_id": cache_id,
                    "source_run_id": source_run_id,
                    "case_id": case_id,
                    "case_tenant_id": case_tenant_id,
                    "tenant_id": tenant_id,
                    "created_by": created_by,
                    "payload": payload,
                    "updated_at": _now(),
                }
            ],
            service=True,
            upsert=True,
            on_conflict="cache_id",
        )
        if not rows:
            raise SupabaseRequestError("运行缓存未完成公网持久化。")
        return rows[0]

    def get_run_cache(self, *, cache_id: str, tenant_id: str) -> dict[str, Any] | None:
        """按服务端验证后的租户读取缓存；随机 cache_id 不能绕过租户过滤。"""

        rows = self.select_table(
            "run_caches",
            filters={"cache_id": f"eq.{cache_id}", "tenant_id": f"eq.{tenant_id}"},
            select="cache_id,source_run_id,case_id,tenant_id,created_by,payload,created_at,updated_at",
            service=True,
        )
        return rows[0] if rows else None

    def persist_prewarm_batch(
        self,
        *,
        batch_id: str,
        tenant_id: str,
        requested_by: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """持久化批次任务清单；具体任务状态继续由 pipeline_tasks 权威记录。"""

        if str(payload.get("batch_id") or "") != batch_id or not isinstance(payload.get("tasks"), list):
            raise SupabaseRequestError("预热批次载荷不完整。")
        rows = self.insert_table(
            "cache_prewarm_batches",
            [
                {
                    "batch_id": batch_id,
                    "tenant_id": tenant_id,
                    "requested_by": requested_by,
                    "payload": payload,
                    "updated_at": _now(),
                }
            ],
            service=True,
            upsert=True,
            on_conflict="batch_id",
        )
        if not rows:
            raise SupabaseRequestError("预热批次未完成公网持久化。")
        return rows[0]

    def enqueue_prewarm_batch(
        self,
        *,
        batch_id: str,
        tenant_id: str,
        requested_by: str,
        payload: dict[str, Any],
        tasks: list[dict[str, Any]],
    ) -> None:
        """在单个数据库事务中幂等写入批次与全部队列任务。"""

        if (
            str(payload.get("batch_id") or "") != batch_id
            or not tenant_id.strip()
            or not requested_by.strip()
            or not isinstance(payload.get("tasks"), list)
            or not 1 <= len(tasks) <= 50
            or len(payload["tasks"]) != len(tasks)
        ):
            raise SupabaseRequestError("预热批次或任务清单不完整。")
        if any(
            not isinstance(task, dict)
            or not str(task.get("task_id") or "").strip()
            or not isinstance(task.get("request_payload"), dict)
            for task in tasks
        ):
            raise SupabaseRequestError("预热队列任务格式不完整。")
        response = self._request(
            "POST",
            "rest/v1/rpc/enqueue_prewarm_batch",
            service=True,
            json_body={
                "p_batch_id": batch_id,
                "p_tenant_id": tenant_id,
                "p_requested_by": requested_by,
                "p_payload": payload,
                "p_tasks": tasks,
            },
        )
        if response is not True:
            raise SupabaseConflict("预热批次幂等键已经绑定其他任务清单。")

    def get_prewarm_batch(self, *, batch_id: str, tenant_id: str, requested_by: str) -> dict[str, Any] | None:
        """批次读取同时约束租户和创建者，服务端 service role 不扩大对象可见范围。"""

        rows = self.select_table(
            "cache_prewarm_batches",
            filters={
                "batch_id": f"eq.{batch_id}",
                "tenant_id": f"eq.{tenant_id}",
                "requested_by": f"eq.{requested_by}",
            },
            select="batch_id,tenant_id,requested_by,payload,created_at,updated_at",
            service=True,
        )
        return rows[0] if rows else None

    def create_model_transfer_consent(
        self,
        *,
        tenant_id: str,
        case_id: str,
        case_tenant_id: str | None,
        user_id: str,
        provider: str,
        model_id: str,
        transmission_scope: str,
        purpose: str,
        valid_until: str,
    ) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "rest/v1/rpc/upsert_model_transfer_consent",
            service=True,
            json_body={
                "p_tenant_id": tenant_id,
                "p_case_id": case_id,
                "p_case_tenant_id": case_tenant_id,
                "p_user_id": user_id,
                "p_provider": provider,
                "p_model_id": model_id,
                "p_transmission_scope": transmission_scope,
                "p_purpose": purpose,
                "p_valid_until": valid_until,
            },
        )
        rows = [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        if not rows:
            raise SupabaseRequestError("模型传输同意记录未写入。")
        return rows[0]

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
        rows = self.select_table(
            "model_transfer_consents",
            filters={
                "tenant_id": f"eq.{tenant_id}",
                "case_id": f"eq.{case_id}",
                "case_tenant_id": f"eq.{case_tenant_id}" if case_tenant_id else "is.null",
                "user_id": f"eq.{user_id}",
                "provider": f"eq.{provider}",
                "model_id": f"eq.{model_id}",
                "transmission_scope": f"eq.{transmission_scope}",
                "revoked_at": "is.null",
                "valid_until": f"gt.{_now()}",
            },
            select="id,tenant_id,case_id,case_tenant_id,case_scope,user_id,provider,model_id,transmission_scope,purpose,valid_until,revoked_at,created_at",
            service=True,
        )
        return rows[0] if rows else None

    def get_model_transfer_consent(self, consent_id: str) -> dict[str, Any] | None:
        rows = self.select_table(
            "model_transfer_consents",
            filters={"id": f"eq.{consent_id}"},
            select="id,tenant_id,case_id,case_tenant_id,case_scope,user_id,provider,model_id,transmission_scope,purpose,valid_until,revoked_at,created_at",
            service=True,
        )
        return rows[0] if rows else None

    def revoke_model_transfer_consent(self, *, consent_id: str, tenant_id: str, user_id: str) -> None:
        self._request(
            "POST",
            "rest/v1/rpc/revoke_model_transfer_consent",
            service=True,
            json_body={"p_consent_id": consent_id, "p_tenant_id": tenant_id, "p_user_id": user_id},
        )

    def record_audit_event(
        self,
        *,
        tenant_id: str | None,
        user_id: str | None,
        event_type: str,
        case_id: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.insert_table(
            "audit_events",
            [
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "event_type": event_type,
                    "case_id": case_id,
                    "run_id": run_id,
                    "metadata": metadata or {},
                }
            ],
            service=True,
        )

    def claim_pipeline_task(self, *, worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None:
        payload = self._request(
            "POST",
            "rest/v1/rpc/claim_pipeline_task",
            service=True,
            json_body={"p_worker_id": worker_id, "p_lease_seconds": lease_seconds},
        )
        if isinstance(payload, list):
            return payload[0] if payload and isinstance(payload[0], dict) else None
        return payload if isinstance(payload, dict) and payload.get("task_id") else None

    def heartbeat_pipeline_task(
        self,
        *,
        task_id: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: int = 120,
    ) -> None:
        payload = self._request(
            "POST",
            "rest/v1/rpc/heartbeat_pipeline_task",
            service=True,
            json_body={
                "p_task_id": task_id,
                "p_worker_id": worker_id,
                "p_lease_token": lease_token,
                "p_lease_seconds": lease_seconds,
            },
        )
        if payload is not True:
            raise SupabaseLeaseLost("worker 租约已失效。")

    def complete_pipeline_task(
        self,
        *,
        task_id: str,
        worker_id: str,
        lease_token: str,
        result: dict[str, Any],
    ) -> None:
        payload = self._request(
            "POST",
            "rest/v1/rpc/complete_pipeline_task",
            service=True,
            json_body={
                "p_task_id": task_id,
                "p_worker_id": worker_id,
                "p_lease_token": lease_token,
                "p_result": result,
            },
        )
        if payload is not True:
            raise SupabaseLeaseLost("worker 完成上报时租约已失效。")

    def fail_pipeline_task(
        self,
        *,
        task_id: str,
        worker_id: str,
        lease_token: str,
        error: dict[str, Any],
        retry: bool = True,
    ) -> None:
        payload = self._request(
            "POST",
            "rest/v1/rpc/fail_pipeline_task",
            service=True,
            json_body={
                "p_task_id": task_id,
                "p_worker_id": worker_id,
                "p_lease_token": lease_token,
                "p_error": error,
                "p_retry": retry,
            },
        )
        if payload is not True:
            raise SupabaseLeaseLost("worker 失败上报时租约已失效。")

    def upload_private_object(
        self,
        *,
        bucket: str,
        object_path: str,
        content: bytes,
        content_type: str = "application/pdf",
        upsert: bool = False,
    ) -> None:
        """上传私有对象；只有服务端确认的内容寻址导入才使用幂等 upsert。"""

        assert_worker_lease()
        bucket = self._validate_bucket(bucket)
        object_path = self._validate_storage_path(object_path)
        self._request(
            "POST",
            f"storage/v1/object/{quote(bucket, safe='')}/{quote(object_path, safe='/')}",
            service=True,
            content=content,
            headers={"Content-Type": content_type, "x-upsert": "true" if upsert else "false"},
        )

    def create_signed_url(self, *, bucket: str, object_path: str, expires_in: int | None = None) -> str:
        bucket = self._validate_bucket(bucket)
        object_path = self._validate_storage_path(object_path)
        expires = max(60, min(86_400, int(expires_in or self.config.signed_url_seconds)))
        payload = self._request(
            "POST",
            f"storage/v1/object/sign/{quote(bucket, safe='')}/{quote(object_path, safe='/')}",
            service=True,
            json_body={"expiresIn": expires},
        )
        signed = payload.get("signedURL") or payload.get("signedUrl") if isinstance(payload, dict) else None
        if not signed:
            raise SupabaseRequestError("Storage 未返回短时签名 URL。")
        return str(signed) if str(signed).startswith("http") else f"{self.config.url}/storage/v1{signed}"

    def download_private_object(self, *, bucket: str, object_path: str) -> bytes:
        """由 service role 读取固定路径的私有对象；路径仍经过逐段白名单校验。"""

        bucket = self._validate_bucket(bucket)
        object_path = self._validate_storage_path(object_path)
        payload = self._request(
            "GET",
            f"storage/v1/object/{quote(bucket, safe='')}/{quote(object_path, safe='/')}",
            service=True,
            raw_content=True,
        )
        if not isinstance(payload, bytes):
            raise SupabaseRequestError("Storage 未返回可读取的对象。")
        return payload

    def persist_case_metadata(
        self,
        *,
        workspace_root: Any,
        case: dict[str, Any],
        rows: list[dict[str, Any]] | None = None,
        upload_private_documents: bool = False,
    ) -> dict[str, Any]:
        """写入案例/年报/字段元数据；PDF 只在内部案例中上传私有 bucket。"""

        case_id = str(case.get("case_id") or "")
        tenant_id = _case_scope_tenant(
            case_id,
            str(case.get("tenant_id") or "").strip() or None,
            registry_mode=str(case.get("registry_mode") or "") or None,
            sample_type=str(case.get("sample_type") or "") or None,
        )
        metadata = {
            key: case.get(key)
            for key in (
                "company_name",
                "company_alias",
                "ticker",
                "org_id",
                "market",
                "sample_type",
                "registry_mode",
                "source_snapshot_id",
                "source_review_status",
                "retention_expires_at",
                "model_transfer_allowed",
                "available_years",
                "available_report_years",
                "three_year_r1_ready",
                "human_confirmed_available_years",
                "human_confirmed_three_year_r1_ready",
                "financial_fields_status",
                "currency",
                "amount_unit",
                "statement_scope",
                "industry",
                "industry_name",
            )
            if case.get(key) is not None
        }
        case_row = {
            "case_id": case_id,
            "tenant_id": tenant_id,
            "sample_type": case.get("sample_type"),
            "company_name": case.get("company_name"),
            "ticker": case.get("ticker"),
            "source_snapshot_id": case.get("source_snapshot_id"),
            "t0": case.get("t0"),
            "metadata": metadata,
            "updated_at": _now(),
        }
        # staging 行在文档/字段未完整写入前不会被目录和读取接口返回；失败重试覆盖同一 scope。
        self.insert_table(
            "cases",
            [{**case_row, "import_status": "staging"}],
            service=True,
            upsert=True,
            on_conflict="tenant_id,case_id",
        )
        existing_paths: dict[str, str] = {}
        if tenant_id and not upload_private_documents:
            existing_documents = self.select_table(
                "report_documents",
                filters={"case_id": f"eq.{case_id}", "tenant_id": f"eq.{tenant_id}"},
                select="document_id,storage_object_path",
                service=True,
            )
            existing_paths = {
                str(item.get("document_id") or ""): str(item.get("storage_object_path") or "")
                for item in existing_documents
                if item.get("storage_object_path")
            }
        document_rows: list[dict[str, Any]] = []
        for document in case.get("documents", []):
            document_id = str(document.get("document_id") or "")
            storage_path = existing_paths.get(document_id) or None
            if tenant_id and upload_private_documents:
                relative = str(document.get("storage_relpath") or "")
                source_path = (workspace_root / relative).resolve()
                root = workspace_root.resolve()
                try:
                    source_path.relative_to(root)
                except ValueError as error:
                    raise SupabaseRequestError("内部年报路径超出工作区边界。") from error
                if not source_path.is_file():
                    raise SupabaseRequestError("内部年报本地暂存文件不存在，未上传 Storage。")
                content = source_path.read_bytes()
                actual_sha256 = hashlib.sha256(content).hexdigest().upper()
                expected_sha256 = str(document.get("sha256") or "").upper()
                if not expected_sha256 or actual_sha256 != expected_sha256:
                    raise SupabaseRequestError("内部年报实际哈希与登记值不一致，未上传 Storage。")
                storage_path = f"{tenant_id}/{case_id}/{document_id}-{actual_sha256}.pdf"
                self.upload_private_object(
                    bucket=self.config.private_bucket,
                    object_path=storage_path,
                    content=content,
                    # 路径含内容哈希，因此同内容失败重试可安全覆盖，异内容不会碰撞同一路径。
                    upsert=True,
                )
            document_rows.append(
                {
                    "case_id": case_id,
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "report_year": document.get("report_year"),
                    # 内部案例的原始 URL 不作为前端/数据库公开回退地址；访问统一走私有 Storage。
                    "source_url": None if tenant_id else document.get("source_url"),
                    "sha256": document.get("sha256"),
                    "page_count": document.get("page_count"),
                    "validation_status": document.get("validation_status"),
                    "storage_object_path": storage_path,
                    "metadata": {
                        key: document.get(key)
                        for key in ("announcement_title", "announcement_date", "disclosure_date", "byte_count", "source_file")
                        if document.get(key) is not None
                    },
                }
            )
        if document_rows:
            self.insert_table(
                "report_documents",
                document_rows,
                service=True,
                upsert=True,
                on_conflict="tenant_id,case_id,document_id",
            )
        evidence_rows = [
            {
                "case_id": case_id,
                "tenant_id": tenant_id,
                "evidence_id": row.get("evidence_id"),
                "field_id": row.get("field_id"),
                "year": row.get("year"),
                "value": row.get("value"),
                "document_id": row.get("document_id"),
                "pdf_page": row.get("pdf_page"),
                "file_sha256": row.get("file_sha256"),
                "metadata": row,
            }
            for row in (rows or [])
            if row.get("evidence_id")
        ]
        if evidence_rows:
            self.insert_table(
                "field_evidence",
                evidence_rows,
                service=True,
                upsert=True,
                on_conflict="tenant_id,case_id,evidence_id",
            )
        ready_rows = self.update_table(
            "cases",
            {"import_status": "ready", "metadata": metadata, "updated_at": _now()},
            filters={
                "case_id": f"eq.{case_id}",
                "tenant_id": f"eq.{tenant_id}" if tenant_id else "is.null",
                "import_status": "eq.staging",
            },
            service=True,
        )
        if not ready_rows:
            raise SupabaseRequestError("案例发布状态未完成。")
        return {"backend": "supabase", "case_id": case_id, "tenant_id": tenant_id, "document_count": len(document_rows), "metadata_persisted": True}

    def persist_run(
        self,
        *,
        run: dict[str, Any],
        tenant_id: str | None,
        case_id: str,
        case_tenant_id: str | None,
        pipeline_task_id: str | None = None,
    ) -> dict[str, Any]:
        """保存运行；tenant_id 是运行所有者，case_tenant_id 是已授权案例证据 scope。"""

        # 新记录保存 RunResponse；人工复核后保存 StoredRunResponse。两种形态共用同一行并保持向后兼容。
        run_payload = run.get("run") if isinstance(run.get("run"), dict) else run
        self.insert_table(
            "analysis_runs",
            [
                {
                    "run_id": run_payload.get("run_id"),
                    "case_id": case_id,
                    "case_tenant_id": case_tenant_id,
                    "tenant_id": tenant_id,
                    "pipeline_task_id": pipeline_task_id,
                    "status": run_payload.get("status"),
                    "run_completeness": run_payload.get("run_completeness"),
                    "payload": run,
                    "updated_at": _now(),
                }
            ],
            service=True,
            upsert=True,
            on_conflict="run_id",
        )
        return {"backend": "supabase", "run_id": run_payload.get("run_id"), "metadata_persisted": True}

    def persist_rag_chunks(
        self,
        *,
        case_id: str,
        tenant_id: str | None,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """分批发布一个不可混用的 RAG 快照；官方公开案例固定写入全局 scope。"""

        case_row = self.get_case_metadata(case_id, tenant_id=tenant_id)
        if case_row is None:
            raise SupabaseRequestError("RAG 对应案例尚未完成发布。")
        # scope 只取已发布案例的权威 tenant_id；调用方自报 tenant 或编号前缀不能改变归属。
        tenant_id = str(case_row.get("tenant_id") or "").strip() or None
        canonical_chunks = [
            {
                "chunk_id": str(chunk.get("chunk_id") or ""),
                "document_id": chunk.get("document_id"),
                "pdf_page": chunk.get("pdf_page"),
                "content": str(chunk.get("content") or ""),
                "metadata": chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {},
            }
            for chunk in chunks
            if chunk.get("chunk_id") and chunk.get("content")
        ]
        chunk_ids = [row["chunk_id"] for row in canonical_chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise SupabaseRequestError("RAG 快照包含重复 chunk_id。")
        digest = hashlib.sha256()
        for chunk in sorted(canonical_chunks, key=lambda item: item["chunk_id"]):
            # 快照摘要覆盖定位与元数据，防止正文相同但页码/来源变化仍复用旧留痕。
            digest.update(json.dumps(chunk, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            digest.update(b"\0")
        snapshot_id = f"RAG-SNAPSHOT-{digest.hexdigest()[:24].upper()}"
        active_rows = self.get_active_rag_chunks(case_id=case_id, tenant_id=tenant_id)
        active_by_id = {str(row.get("chunk_id") or ""): row for row in active_rows}
        if (
            canonical_chunks
            and len(active_rows) == len(canonical_chunks)
            and {str(row.get("rag_snapshot_id") or "") for row in active_rows} == {snapshot_id}
            and set(active_by_id) == set(chunk_ids)
            and all(
                all(active_by_id[row["chunk_id"]].get(key) == row.get(key) for key in ("document_id", "pdf_page", "content", "metadata"))
                for row in canonical_chunks
            )
        ):
            # 完整同内容快照已经发布时直接返回；绝不把 active 行通过 upsert
            # 逐批改成 false，否则第二批失败会永久破坏原本完整的线上索引。
            return {
                "backend": "supabase",
                "case_id": case_id,
                "tenant_id": tenant_id,
                "rag_snapshot_id": snapshot_id,
                "chunk_count": len(canonical_chunks),
                "metadata_persisted": True,
                "idempotent": True,
            }
        generation_id = f"RAG-GEN-{uuid.uuid4().hex.upper()}"
        rows = [
            {
                "case_id": case_id,
                "tenant_id": tenant_id,
                "rag_snapshot_id": snapshot_id,
                "generation_id": generation_id,
                # 新快照先以 inactive 写完，避免半批数据被读取为已发布索引。
                "active": False,
                **chunk,
            }
            for chunk in canonical_chunks
        ]
        for start in range(0, len(rows), 200):
            self.insert_table(
                "rag_chunks",
                rows[start : start + 200],
                service=True,
                upsert=True,
                on_conflict="tenant_id,case_id,generation_id,chunk_id",
            )
        if rows:
            assert_worker_lease()
            published = self._request(
                "POST",
                "rest/v1/rpc/publish_rag_snapshot",
                service=True,
                json_body={
                    "p_case_scope": case_row.get("case_scope"),
                    "p_rag_snapshot_id": snapshot_id,
                    "p_generation_id": generation_id,
                    "p_expected_count": len(rows),
                },
            )
            if published is not True:
                raise SupabaseRequestError("RAG 快照未完整发布。")
        return {
            "backend": "supabase",
            "case_id": case_id,
            "tenant_id": tenant_id,
            "rag_snapshot_id": snapshot_id,
            "generation_id": generation_id,
            "chunk_count": len(rows),
            "metadata_persisted": True,
        }

    def get_active_rag_chunks(self, *, case_id: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """只读取当前案例同一活动快照；匿名调用只会命中全局公开 scope。"""

        case_row = self.get_case_metadata(case_id, tenant_id=tenant_id)
        if case_row is None:
            return []
        resolved_tenant = str(case_row.get("tenant_id") or "").strip()
        rows = self.select_table(
            "rag_chunks",
            filters={
                "case_id": f"eq.{case_id}",
                "tenant_id": f"eq.{resolved_tenant}" if resolved_tenant else "is.null",
                "active": "eq.true",
            },
            select="case_scope,rag_snapshot_id,generation_id,chunk_id,document_id,pdf_page,content,metadata,created_at",
            service=True,
        )
        snapshots = {str(row.get("rag_snapshot_id") or "") for row in rows}
        if len(snapshots) > 1:
            # 并发发布若留下多个 active 版本，宁可报服务错误也不混合证据快照。
            raise SupabaseRequestError("RAG 活动快照状态不一致。")
        return rows

    def get_remote_rag_status(self, *, case_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        """从活动块形成跨实例状态；没有完整活动快照时明确返回 not_built。"""

        rows = self.get_active_rag_chunks(case_id=case_id, tenant_id=tenant_id)
        if not rows:
            return {
                "status": "not_built",
                "index_version": "rag-v1.2-case-isolated-hash-ngram-faiss-20260728",
                "case_id": case_id,
                "chunk_count": 0,
            }
        return {
            "status": "ready",
            "index_version": "rag-v1.2-case-isolated-hash-ngram-faiss-20260728",
            "retrieval_backend": "supabase_active_snapshot_lexical",
            "case_id": case_id,
            "case_scope": rows[0].get("case_scope"),
            "rag_snapshot_id": rows[0].get("rag_snapshot_id"),
            "generation_id": rows[0].get("generation_id"),
            "chunk_count": len(rows),
            "built_at": max(str(row.get("created_at") or "") for row in rows),
        }

    def persist_rag_retrieval(
        self,
        *,
        retrieval_id: str,
        case_id: str,
        case_tenant_id: str | None,
        owner_tenant_id: str | None,
        requested_by: str | None,
        rag_snapshot_id: str,
        payload: dict[str, Any],
    ) -> None:
        """保存远程检索留痕，使 fresh web 能按 retrieval_id 回查同一活动证据快照。"""

        self.insert_table(
            "rag_retrievals",
            [
                {
                    "retrieval_id": retrieval_id,
                    "case_id": case_id,
                    "case_tenant_id": case_tenant_id,
                    "tenant_id": owner_tenant_id,
                    "requested_by": requested_by,
                    "rag_snapshot_id": rag_snapshot_id,
                    "payload": payload,
                }
            ],
            service=True,
        )

    def get_rag_retrieval(self, retrieval_id: str, *, owner_tenant_id: str | None = None) -> dict[str, Any] | None:
        """先查当前租户留痕，再查全局公开留痕；不会按编号扫描其他租户。"""

        for scope in dict.fromkeys(([str(owner_tenant_id).strip()] if owner_tenant_id else []) + [""]):
            rows = self.select_table(
                "rag_retrievals",
                filters={
                    "retrieval_id": f"eq.{retrieval_id}",
                    "tenant_id": f"eq.{scope}" if scope else "is.null",
                },
                select="retrieval_id,case_id,case_tenant_id,case_scope,tenant_id,requested_by,rag_snapshot_id,payload,created_at",
                service=True,
            )
            if rows:
                return rows[0]
        return None

    def list_public_catalog_entries(self, *, company_query: str | None = None) -> list[dict[str, Any]]:
        """以 Postgres 全局官方案例为公网热缓存目录，不依赖某台 web 的 SQLite。"""

        rows = self.select_table(
            "cases",
            filters={"tenant_id": "is.null", "sample_type": "eq.public", "import_status": "eq.ready"},
            select="case_id,company_name,ticker,source_snapshot_id,t0,metadata,updated_at",
            service=True,
        )
        needle = str(company_query or "").strip().lower()
        entries: list[dict[str, Any]] = []
        for row in rows:
            case_id = str(row.get("case_id") or "")
            if not case_id.startswith("CNINFO_"):
                continue
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            haystack = " ".join(
                str(value or "").lower()
                for value in (row.get("ticker"), row.get("company_name"), metadata.get("company_alias"))
            )
            if needle and needle not in haystack:
                continue
            rag = self.get_remote_rag_status(case_id=case_id)
            report_years = [int(year) for year in (metadata.get("available_report_years") or [])]
            entries.append(
                {
                    "case_id": case_id,
                    "ticker": row.get("ticker"),
                    "company_name": row.get("company_name"),
                    "company_alias": metadata.get("company_alias") or row.get("company_name"),
                    "snapshot_id": row.get("source_snapshot_id"),
                    "source_fingerprint": row.get("source_snapshot_id"),
                    "report_years": report_years,
                    "available_years": metadata.get("available_years") or [],
                    "rag_index_version": rag.get("index_version"),
                    "rag_snapshot_id": rag.get("rag_snapshot_id"),
                    "chunk_count": rag.get("chunk_count", 0),
                    "cache_state": "ready" if rag.get("status") == "ready" and report_years else "incomplete",
                    "verified_at": row.get("updated_at"),
                    "storage_backend": "supabase_global_public",
                }
            )
        return entries


def get_supabase_client() -> SupabaseClient:
    return SupabaseClient()
