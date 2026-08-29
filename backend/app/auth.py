"""审迹智链的本地/公网身份边界。

本地竞赛模式使用明确标记的 ``local-dev`` 身份以保持离线验收；公网模式
只接受 Supabase Bearer token，并从 organization_members 查询租户，不信任
浏览器自行提交的组织编号。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, Request

from .privacy import model_transmission_scope
from .supabase_adapter import (
    SupabaseAuthError,
    SupabaseError,
    demo_task_supabase_enabled,
    SupabaseNotConfigured,
    get_supabase_client,
    persistence_mode,
    supabase_enabled,
)


ACCESS_COOKIE_NAME = "audittrace_access"
REFRESH_COOKIE_NAME = "audittrace_refresh"
CASE_WRITE_ROLES = frozenset({"owner", "admin", "reviewer"})


def model_consent_contract() -> dict[str, str]:
    """把同意绑定到服务端当前实际供应商、模型和规范化最小传输范围。"""

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    provider = (urlparse(base_url).hostname or "api.deepseek.com").lower()
    return {
        "provider": provider,
        "model_id": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
        "transmission_scope": model_transmission_scope(),
    }


@dataclass(frozen=True)
class UserIdentity:
    """保存服务端验证后的用户、租户和角色，不接受浏览器自报租户。"""

    user_id: str
    tenant_id: str | None
    role: str
    email: str | None = None
    source: str = "supabase"

    @property
    def is_local(self) -> bool:
        """区分离线竞赛身份，避免把本地操作者误写成公网登录用户。"""

        return self.source == "local"

    def as_public_dict(self) -> dict[str, Any]:
        """只返回页面需要的身份摘要，不暴露访问令牌或服务端密钥。"""

        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "role": self.role,
            "email": self.email,
            "source": self.source,
        }


def _local_identity() -> UserIdentity:
    """为未启用 Supabase 的本地模式生成明确且不可混淆的离线身份。"""

    return UserIdentity(user_id="local-dev", tenant_id="local-dev", role="local_operator", source="local")


def bearer_token(request: Request) -> str | None:
    """严格解析 Bearer 头，拒绝含混认证格式进入后续权限判断。"""

    value = request.headers.get("authorization", "").strip()
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authorization 必须使用 Bearer token。")
    return token.strip()


def session_access_token(request: Request) -> str | None:
    """优先保留 Bearer API 合同，无 Authorization 时再读取同源 HttpOnly 会话。"""

    token = bearer_token(request)
    if token:
        return token
    cookie = str(request.cookies.get(ACCESS_COOKIE_NAME) or "").strip()
    return cookie or None


def attach_identity(request: Request, identity: UserIdentity) -> UserIdentity:
    """把已验证身份绑定到单次请求，供同一调用链重复使用。"""

    request.state.audittrace_identity = identity
    return identity


def request_identity(request: Request) -> UserIdentity | None:
    """仅接受本模块创建的身份对象，防止任意 request.state 值被信任。"""

    value = getattr(request.state, "audittrace_identity", None)
    return value if isinstance(value, UserIdentity) else None


def identity_from_access_token(access_token: str) -> UserIdentity:
    """只相信 Supabase 验签结果和成员表，不接收客户端自报的用户、租户或角色。"""

    try:
        client = get_supabase_client()
    except SupabaseNotConfigured as error:
        raise HTTPException(status_code=503, detail="公网模式尚未完成 Supabase 服务端配置。") from error
    try:
        user = client.verify_user(access_token)
        user_id = str(user.get("id") or "").strip()
        memberships = client.list_memberships(user_id, token=access_token)
    except SupabaseAuthError as error:
        raise HTTPException(status_code=401, detail="登录状态无效或已过期。") from error
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="身份服务暂时不可用，请稍后重试。") from error
    if not memberships:
        raise HTTPException(status_code=403, detail="当前账号尚未加入任何审迹智链组织。")
    membership = memberships[0]
    identity = UserIdentity(
        user_id=user_id,
        tenant_id=str(membership.get("organization_id") or "").strip() or None,
        role=str(membership.get("role") or "member"),
        email=str(user.get("email") or "").strip() or None,
    )
    if not identity.tenant_id:
        raise HTTPException(status_code=403, detail="当前账号没有有效租户归属。")
    return identity


def require_authenticated(request: Request) -> UserIdentity:
    """要求登录；公网同时接受 Bearer 与 HttpOnly Cookie，本地继续使用离线身份。"""

    existing = request_identity(request)
    if existing is not None:
        return existing
    if not supabase_enabled():
        return attach_identity(request, _local_identity())
    try:
        # 先确认公网身份依赖已经配置，避免把部署缺失误报成普通未登录。
        get_supabase_client()
    except SupabaseNotConfigured as error:
        raise HTTPException(status_code=503, detail="公网模式尚未完成 Supabase 服务端配置。") from error
    token = session_access_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="该功能需要登录后使用。")
    return attach_identity(request, identity_from_access_token(token))


def optional_authenticated(request: Request) -> UserIdentity | None:
    """公开案例允许匿名；带了 token 时仍验证 token，避免伪造半登录状态。"""

    existing = request_identity(request)
    if existing is not None:
        return existing
    if not supabase_enabled():
        return attach_identity(request, _local_identity())
    if not session_access_token(request):
        return None
    return require_authenticated(request)


def is_public_case(case: dict[str, Any]) -> bool:
    """只有无租户归属的正式公开样例才允许匿名读取。"""

    # 只要有服务端写入的租户归属，就按内部案例处理；不能让上传者把 manifest
    # 的 sample_type 写成 public 来绕过登录与租户隔离。
    return (
        str(case.get("sample_type") or "").strip().lower() == "public"
        and not str(case.get("tenant_id") or "").strip()
    )


def authorize_case_access(request: Request, case: dict[str, Any]) -> UserIdentity | None:
    """公开案例匿名可读；内部案例必须匹配服务端查询出的组织成员关系。"""

    if not supabase_enabled():
        return attach_identity(request, _local_identity())
    if is_public_case(case):
        return optional_authenticated(request)
    identity = require_authenticated(request)
    case_tenant = str(case.get("tenant_id") or case.get("owner_org_id") or "").strip()
    if not case_tenant or case_tenant != identity.tenant_id:
        raise HTTPException(status_code=404, detail="案例不存在或当前账号无权访问。")
    return identity


def authorize_case_write(request: Request, case: dict[str, Any]) -> UserIdentity:
    """公网案例变更必须由可写角色发起；公开只读匿名边界不因此收窄。"""

    if not supabase_enabled():
        return attach_identity(request, _local_identity())
    identity = require_authenticated(request)
    if identity.role not in CASE_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="当前组织角色没有案例写权限。")
    case_tenant = str(case.get("tenant_id") or case.get("owner_org_id") or "").strip()
    if case_tenant and case_tenant != identity.tenant_id:
        # 与读取接口一致使用 404，避免向其他租户确认案例编号是否存在。
        raise HTTPException(status_code=404, detail="案例不存在或当前账号无权修改。")
    return identity


def authorize_pipeline_task(request: Request, task: dict[str, Any]) -> UserIdentity:
    """公网任务同时校验租户与创建者，任务编号本身不作为访问凭证。"""

    if not supabase_enabled():
        return attach_identity(request, _local_identity())
    identity = require_authenticated(request)
    task_tenant = str(task.get("tenant_id") or "").strip()
    requested_by = str(task.get("requested_by") or "").strip()
    if not task_tenant or task_tenant != identity.tenant_id or not requested_by or requested_by != identity.user_id:
        raise HTTPException(status_code=404, detail="任务不存在或当前账号无权访问。")
    return identity


def authorize_model_transfer(request: Request, case: dict[str, Any]) -> bool:
    """返回本次是否有资格调用外部模型；公网必须存在当前案例有效同意。"""

    if not supabase_enabled():
        return bool(case.get("model_transfer_allowed"))
    identity = optional_authenticated(request)
    if identity is None or not identity.tenant_id:
        return False
    # worker 的排队身份可能在等待期间被撤销；每个 Agent 角色前都重新读取成员表。
    if identity.source == "worker":
        try:
            membership = get_supabase_client().get_active_membership(
                user_id=identity.user_id,
                tenant_id=identity.tenant_id,
            )
        except SupabaseError as error:
            raise HTTPException(status_code=503, detail="模型传输前成员状态暂时不可用。") from error
        if not membership or str(membership.get("role") or "") not in CASE_WRITE_ROLES:
            return False
    case_id = str(case.get("case_id") or "").strip()
    if not case_id:
        return False
    contract = model_consent_contract()
    try:
        consent = get_supabase_client().get_active_model_transfer_consent(
            tenant_id=identity.tenant_id,
            case_id=case_id,
            case_tenant_id=str(case.get("tenant_id") or "").strip() or None,
            user_id=identity.user_id,
            provider=contract["provider"],
            model_id=contract["model_id"],
            transmission_scope=contract["transmission_scope"],
        )
    except SupabaseError as error:
        raise HTTPException(status_code=503, detail="模型传输同意状态暂时不可用。") from error
    if consent:
        request.state.audittrace_model_consent = consent
    return bool(consent)


def identity_for_task(request: Request) -> dict[str, str | None] | None:
    """向异步任务传递最小身份字段，不复制令牌和电子邮箱。"""

    identity = request_identity(request)
    if identity is None or identity.is_local:
        return None
    return {"user_id": identity.user_id, "tenant_id": identity.tenant_id, "role": identity.role}


def configured_persistence() -> dict[str, Any]:
    """公开持久化与身份边界，供状态接口和页面一致展示。"""

    demo_mode = "supabase" if demo_task_supabase_enabled() else "local"
    executor_mode = os.getenv("AUDITTRACE_DEMO_EXECUTOR_MODE", "web").strip().lower() or "web"
    demo_supabase_configured = bool(
        os.getenv("SUPABASE_URL", "").strip()
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    ) if demo_mode == "supabase" else True
    return {
        "mode": persistence_mode(),
        "demo_task_mode": demo_mode,
        "demo_executor_mode": executor_mode,
        "demo_task_configured": demo_supabase_configured,
        "demo_quota_mode": demo_mode,
        "demo_quota_configured": demo_supabase_configured,
        "demo_completed_result_durable": demo_mode == "supabase",
        "demo_running_resume": False,
        "auth_required_for_internal": supabase_enabled(),
        "public_anonymous": True,
    }
