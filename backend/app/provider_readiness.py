"""模型供应商可用性探测、TTL 快照缓存与熔断机制。

本模块负责在公开模式下对配置的外部大模型供应商进行只读可用性探测与熔断管理。
只在服务启动或定时后台任务中以最小只读探测请求（如 /user/balance 或 /models）验证
供应商 API Key 有效性、账户可用余额与模型就绪状态，不消耗用户业务 Token。
真实三 Agent 运行中观察到的永久性失败（如 401 鉴权失败、402 余额不足）会立即写入熔断，
使得前端与就绪接口能够诚实展示当前状态，并在供应商不可用时平滑引导用户使用确定性备用分析。

审计合规与工程约束：
1. 探测绝不发送审计客户真实数据、财务底稿或商业机密；
2. 探测快照只包含脱敏后的布尔就绪状态与稳定原因码，禁止在接口或日志暴露 API Key 与账户明细；
3. 供应商不可用时不阻断系统整体运行，而是降级至确定性计算分析，确保审计师始终有底稿可用；
4. 任何探测或熔断结果均带有时间戳与快照有效期，防止 stale 状态引发误判。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import re
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


# 默认缓存时间：5 分钟内复用快照，避免频繁向外部供应商发送重复请求
DEFAULT_PROBE_TTL_SECONDS = 300
# 硬过期时间：10 分钟后快照彻底失效，必须强制刷新探测
DEFAULT_HARD_EXPIRY_SECONDS = 600
# 探测网络超时：连接与读取控制在 8 秒以内。OpenCode 边缘节点冷启动时 /models
# 首包常超过 4 秒，4 秒会被误判为不可达；8 秒仍保证接口不长时间阻塞。
DEFAULT_PROBE_TIMEOUT_SECONDS = 8.0


def provider_base_url_error(base_url: str) -> str | None:
    """校验 DEEPSEEK_BASE_URL 的形状，返回稳定原因码；合法时返回 None。

    允许值（末尾斜杠由调用方规范化）：
    - https://opencode.ai/zen/go/v1（OpenCode Go 基础地址）
    - https://api.deepseek.com（原生 DeepSeek，由调用方补 /beta）
    - 其他 https 的 OpenAI 兼容基础地址（host 含点或为本机别名）

    明确拒绝：
    - http 明文、缺失 scheme、未知主机、带查询/片段/用户信息；
    - 以 /chat/completions 结尾的完整请求地址（调用方会自行拼接该后缀）；
    - 重复的 /v1/v1 版本段。
    """
    raw = (base_url or "").strip()
    if not raw:
        return "provider_base_url_empty"
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return "provider_base_url_invalid"
    if not host or not host.isascii() or ("." not in host and host not in {"localhost", "127.0.0.1"}):
        return "provider_base_url_invalid"
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return "provider_base_url_invalid"
    path = parsed.path.rstrip("/")
    if "/chat/completions" in path:
        return "provider_base_url_invalid"
    if re.search(r"/v1/v1(?:/|$)", path):
        return "provider_base_url_invalid"
    return None


def provider_base_url_error_message(error_code: str) -> str:
    """把基础地址错误码转成可操作的中文说明；不回显密钥或完整请求地址。"""
    if error_code == "provider_base_url_empty":
        return "尚未配置 DEEPSEEK_BASE_URL；请在 .env 填写供应商基础地址，例如 https://opencode.ai/zen/go/v1。"
    return (
        "DEEPSEEK_BASE_URL 不是合法的 https 基础地址。请填写供应商基础地址"
        "（例如 https://opencode.ai/zen/go/v1），不要填写以 /chat/completions 结尾的完整请求地址，"
        "也不要填写 http 明文或重复的 /v1/v1 版本段。"
    )


def classify_provider_channel(base_url: str | None = None) -> dict[str, str]:
    """根据 Base URL 解析模型供应商通道类型、标准中文标签与主机名。

    支持通道：
    - deepseek_direct: DeepSeek 官方直连接口 (api.deepseek.com)
    - opencode_go: OpenCode Go 接口 (opencode.ai/zen/go/v1)
    - opencode_zen: OpenCode Zen 充值额度接口 (opencode.ai/zen/v1)
    - openai_compatible_other: 其他通用 OpenAI 兼容代理网关
    """
    raw_url = (base_url if base_url is not None else os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).strip()
    url_lower = raw_url.lower()

    if "api.deepseek.com" in url_lower:
        return {
            "provider_kind": "deepseek_direct",
            "provider_label": "DeepSeek 官方直连",
            "provider_host": "api.deepseek.com",
            "base_url": raw_url,
        }
    if "opencode.ai/zen/go" in url_lower or "zen/go" in url_lower:
        return {
            "provider_kind": "opencode_go",
            "provider_label": "OpenCode Go",
            "provider_host": "opencode.ai",
            "base_url": raw_url,
        }
    if "opencode.ai/zen" in url_lower or "opencode.ai" in url_lower:
        return {
            "provider_kind": "opencode_zen",
            "provider_label": "OpenCode Zen",
            "provider_host": "opencode.ai",
            "base_url": raw_url,
        }

    # 解析其他通用网关的主机名
    from urllib.parse import urlparse
    try:
        parsed = urlparse(raw_url)
        host = parsed.netloc or "custom-gateway"
    except Exception:
        host = "custom-gateway"
    return {
        "provider_kind": "openai_compatible_other",
        "provider_label": f"OpenAI 兼容网关 ({host})",
        "provider_host": host,
        "base_url": raw_url,
    }


def get_provider_error_guidance(
    failure_code: str,
    base_url: str | None = None,
    http_code: int = 0,
    detail: str = "",
) -> dict[str, str]:
    """根据失败原因与供应商通道生成针对性、可操作的中文字符串与下一步动作码。

    安全与合规要求：
    - 严禁在返回文案或动作码中回显真实 API Key 或敏感凭据；
    - 明确指出是哪个接口返回错误，避免把直连欠费误判为代销额度问题；
    - 区分 401 密钥无效、402 余额不足、403 区域协议与 429 限流。
    """
    channel_info = classify_provider_channel(base_url)
    kind = channel_info["provider_kind"]
    label = channel_info["provider_label"]

    if failure_code == "MODEL_PROVIDER_BASE_URL_INVALID" or failure_code == "provider_base_url_invalid":
        return {
            "message": provider_base_url_error_message(failure_code),
            "next_action_code": "fix_provider_base_url",
            "reason_code": "provider_base_url_invalid",
        }

    if failure_code == "MODEL_PROVIDER_BALANCE_EXHAUSTED" or http_code == 402:
        if kind == "deepseek_direct":
            msg = (
                "DeepSeek 官方直连接口返回余额不足（HTTP 402）。当前应用直连 api.deepseek.com，"
                "并未消耗 OpenCode 余额。若要使用 OpenCode，请将 Base URL 切换为 https://opencode.ai/zen/go/v1 并配置 OpenCode Key；"
                "若继续使用 DeepSeek 直连，请前往 DeepSeek 开放平台充值。"
            )
            next_action = "check_deepseek_balance_or_switch_opencode"
        elif kind == "opencode_go":
            msg = (
                "OpenCode Go 接口返回额度不足或付费限制（HTTP 402）。"
                "请确认 API Key 属于当前有额度的工作区，并确认 DeepSeek V4 Flash 已在该工作区启用。"
            )
            next_action = "check_opencode_go_workspace_quota"
        elif kind == "opencode_zen":
            msg = (
                "OpenCode Zen 接口返回余额不足（HTTP 402）。"
                "请前往 OpenCode 控制台检查 Zen 充值余额并充值。"
            )
            next_action = "check_opencode_zen_balance"
        else:
            msg = f"{label} 返回余额不足（HTTP 402），请检查账户额度或切换通道。"
            next_action = "check_provider_balance"
        return {"message": msg, "next_action_code": next_action, "reason_code": "provider_balance_exhausted"}

    if failure_code == "MODEL_PROVIDER_AUTH_FAILED" or http_code == 401:
        if kind == "deepseek_direct":
            msg = "DeepSeek 官方直连接口鉴权失败（HTTP 401）。请检查 API Key 是否为有效的 DeepSeek 官方密钥。"
            next_action = "check_deepseek_api_key"
        elif kind in ("opencode_go", "opencode_zen"):
            msg = f"{label} 接口鉴权失败（HTTP 401）。请检查 API Key 是否为有效的 OpenCode Key，并确认与当前 Base URL 通道配对。"
            next_action = "check_opencode_api_key"
        else:
            msg = f"{label} 鉴权失败（HTTP 401），请检查 API Key 配置。"
            next_action = "check_api_key"
        return {"message": msg, "next_action_code": next_action, "reason_code": "provider_auth_failed"}

    if failure_code == "MODEL_PROVIDER_REGION_OPT_IN_REQUIRED" or (http_code == 403 and ("region" in detail.lower() or "hosted in china" in detail.lower())):
        msg = (
            f"{label} 提示中国托管模型需要工作区显式同意协议（HTTP 403）。"
            "请前往 OpenCode 工作区设置页面启用中国托管模型后重试。"
        )
        next_action = "enable_china_hosted_model_in_workspace"
        return {"message": msg, "next_action_code": next_action, "reason_code": "provider_auth_failed"}

    if http_code == 403:
        msg = f"{label} 请求被拒绝（HTTP 403），请检查工作区权限或安全策略。"
        next_action = "check_workspace_permissions"
        return {"message": msg, "next_action_code": next_action, "reason_code": "provider_auth_failed"}

    if failure_code == "MODEL_PROVIDER_RATE_LIMITED" or http_code == 429:
        msg = f"{label} 暂时限流（HTTP 429），请稍后重试。"
        next_action = "retry_later"
        return {"message": msg, "next_action_code": next_action, "reason_code": "provider_temporarily_unavailable"}

    if failure_code == "MODEL_PROVIDER_TIMEOUT":
        msg = f"{label} 在完整等待窗口内未返回；本次未自动重复请求，可稍后从新任务重试。"
        return {"message": msg, "next_action_code": "retry_run", "reason_code": "provider_temporarily_unavailable"}

    if http_code in (500, 502, 503, 504):
        msg = f"{label} 服务端临时故障（HTTP {http_code}），请稍后重试。"
        next_action = "retry_later"
        return {"message": msg, "next_action_code": next_action, "reason_code": "provider_temporarily_unavailable"}

    msg = f"{label} 调用异常（{failure_code or f'HTTP {http_code}'}）。"
    next_action = "inspect_runtime_error"
    return {"message": msg, "next_action_code": next_action, "reason_code": "provider_temporarily_unavailable"}


@dataclass
class ProviderSnapshot:
    """供应商就绪快照，只包含公开状态与脱敏原因码，不包含密钥或余额数字。

    字段说明：
    - status: 整体可用状态，取值为 "ready" 或 "unavailable"；
    - reason_code: 机器可读的脱敏原因代码，供前端与上游根据具体原因展示中文引导；
    - message: 人类可读的中文字符串说明；
    - checked_at: 本次快照生成的 UTC 时间戳（ISO 8601 格式）；
    - expires_at: 本次快照的过期时间戳（ISO 8601 格式）；
    - source: 快照来源，包括 "probe"（主动探测）、"live_run"（真实调用成功反馈）、
      "circuit_breaker"（真实调用失败熔断）、"cached"（缓存复用）或 "default"（默认配置）；
    - stale: 布尔值，当快照超过 TTL 但在硬过期窗口内时为 True，提示上游当前正在后台刷新；
    - provider_kind: 通道类别代码（deepseek_direct / opencode_go / opencode_zen / openai_compatible_other）；
    - provider_label: 通道中文标签名称；
    - provider_host: 供应商域名或主机名（只读公开）；
    - model_id: 配置的模型标识；
    - paid_probe_performed: 是否发生过消耗业务 Token 的真实三 Agent 调用；
    - last_runtime_failure_code: 最近一次真实运行记录的错误码；
    - next_action_code: 引导前端或用户执行的标准下一步动作代码。
    """

    status: str  # "ready" | "unavailable"
    reason_code: str  # "ready" | "provider_auth_failed" | "provider_balance_exhausted" | "provider_model_unavailable" | "provider_temporarily_unavailable" | "provider_status_unknown" | "provider_probe_disabled" | "api_key_missing"
    message: str
    checked_at: str  # ISO 格式时间戳
    expires_at: str  # ISO 格式时间戳
    source: str  # "probe" | "live_run" | "circuit_breaker" | "cached" | "default"
    stale: bool = False
    provider_kind: str = "deepseek_direct"
    provider_label: str = "DeepSeek 官方直连"
    provider_host: str = "api.deepseek.com"
    model_id: str = "qwen3.5-plus"
    paid_probe_performed: bool = False
    last_runtime_failure_code: str | None = None
    next_action_code: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        """序列化为可对外公开的字典结构。"""
        # 转换并返回标准字典格式，供 FastAPI 路由直接序列化为 JSON 响应
        return asdict(self)


# 线程锁与全局单例快照对象（使用可重入锁 RLock 避免内部调用死锁）
_lock = threading.RLock()
# 当前持有的最新供应商就绪快照
_current_snapshot: ProviderSnapshot | None = None
# 上次成功执行探测并记录的时间戳（秒）
_last_probe_timestamp: float = 0.0
# 后台探测进行中防并发标记，防止软过期窗口期并发请求产生雷群效应
_probe_in_flight: bool = False


def _iso_now(offset_seconds: float = 0.0) -> str:
    """生成带时区的当前或未来 ISO 8601 时间戳。"""
    # 统一使用 UTC 时区格式化时间，保证跨平台和前端解析一致性
    dt = datetime.fromtimestamp(time.time() + offset_seconds, tz=timezone.utc)
    return dt.isoformat()


def is_provider_probe_enabled() -> bool:
    """检查是否启用了供应商后台主动探测。"""
    # 显式配置开关，避免离线与单测环境产生非预期的外网试探
    configured = os.getenv("AUDITTRACE_PROVIDER_PROBE_ENABLED", "").strip().lower()
    return configured in ("true", "1", "yes", "on")


def _open_with_retry(request: Request, timeout: float):
    """对只读探测做一次网络层重试，平滑供应商边缘的间歇性握手失败。

    只重试 URLError/OSError/TimeoutError 等网络问题；HTTP 状态错误（401/402/429/5xx）
    与业务失败不重试，避免把鉴权失败误报成“短暂抖动”。两次都失败时仍由上层
    归类为 provider_temporarily_unavailable，不改变诚实失败语义。
    """
    try:
        return urlopen(request, timeout=timeout)
    except (URLError, TimeoutError, OSError):
        time.sleep(0.8)
        return urlopen(request, timeout=timeout)


def probe_provider(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model_id: str | None = None,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> ProviderSnapshot:
    """向模型供应商发起无 Token 消耗的只读探测，验证 API Key 与账户可用性。

    核心探测流程：
    1. 校验 API Key 基础配置是否存在；
    2. 解析目标 Base URL 供应商通道（DeepSeek 直连、OpenCode Go、OpenCode Zen）；
    3. 若目标为官方 DeepSeek 接口，向 `/user/balance` 发送只读请求检验可用额度；
    4. 若目标为标准 OpenAI 兼容网关或自建服务，向 `/models` 发送只读请求检验模型列表与鉴权；
    5. 根据 HTTP 状态码（401/402/429/5xx）与返回结构分类映射为稳定的就绪原因码；
    6. 捕获并妥善处理所有网络异常（超时、连接拒绝、DNS 解析失败），绝不向上抛出未捕获异常。
    """

    # 提取 API Key：优先使用传入参数，其次读取环境变量
    key = (api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")).strip()
    target_base_url = (base_url if base_url is not None else os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).strip()
    target_model = (model_id if model_id is not None else os.getenv("DEEPSEEK_MODEL", "qwen3.5-plus")).strip()
    base_url_error = provider_base_url_error(target_base_url)
    if base_url_error is not None:
        return ProviderSnapshot(
            status="unavailable",
            reason_code=base_url_error,
            message=provider_base_url_error_message(base_url_error),
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="probe",
            stale=False,
            provider_kind="openai_compatible_other",
            provider_label="OpenAI 兼容网关",
            provider_host="unknown",
            model_id=target_model,
            paid_probe_performed=False,
            last_runtime_failure_code="MODEL_PROVIDER_BASE_URL_INVALID",
            next_action_code="fix_provider_base_url",
        )
    target_base_url = target_base_url.rstrip("/")
    channel_info = classify_provider_channel(target_base_url)
    p_kind = channel_info["provider_kind"]
    p_label = channel_info["provider_label"]
    p_host = channel_info["provider_host"]

    if not key:
        # 未配置 API Key 时返回明确的不可用原因码
        return ProviderSnapshot(
            status="unavailable",
            reason_code="api_key_missing",
            message=f"服务端尚未配置 {p_label} API Key；可运行仅计算或确定性备用分析。",
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="probe",
            stale=False,
            provider_kind=p_kind,
            provider_label=p_label,
            provider_host=p_host,
            model_id=target_model,
            paid_probe_performed=False,
            last_runtime_failure_code=None,
            next_action_code="configure_api_key",
        )

    is_official_deepseek = "api.deepseek.com" in target_base_url.lower()

    # 步骤 1：如果是 DeepSeek 官方接口，优先请求 /user/balance 验证余额
    if is_official_deepseek:
        balance_url = f"{target_base_url}/user/balance"
        balance_request = Request(
            balance_url,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
                "User-Agent": "AuditTrace-Probe/0.7.1",
            },
            method="GET",
        )
        try:
            with _open_with_retry(balance_request, timeout=timeout) as response:
                raw = response.read()
                try:
                    balance_data = json.loads(raw.decode("utf-8"))
                except Exception:
                    # 响应解析异常时降级为空字典
                    balance_data = {}
                # is_available 明确为 False 时表示账户欠费或无可用充值余额
                if balance_data.get("is_available") is False:
                    guidance = get_provider_error_guidance("MODEL_PROVIDER_BALANCE_EXHAUSTED", base_url=target_base_url, http_code=402)
                    return ProviderSnapshot(
                        status="unavailable",
                        reason_code="provider_balance_exhausted",
                        message=guidance["message"],
                        checked_at=_iso_now(),
                        expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                        source="probe",
                        stale=False,
                        provider_kind=p_kind,
                        provider_label=p_label,
                        provider_host=p_host,
                        model_id=target_model,
                        paid_probe_performed=False,
                        last_runtime_failure_code="MODEL_PROVIDER_BALANCE_EXHAUSTED",
                        next_action_code=guidance["next_action_code"],
                    )
                # 官方 DeepSeek 余额接口返回 200 且可用，说明鉴权与额度均就绪
                return ProviderSnapshot(
                    status="ready",
                    reason_code="ready",
                    message="模型供应商鉴权与账户可用余额均探测通过。",
                    checked_at=_iso_now(),
                    expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                    source="probe",
                    stale=False,
                    provider_kind=p_kind,
                    provider_label=p_label,
                    provider_host=p_host,
                    model_id=target_model,
                    paid_probe_performed=False,
                    last_runtime_failure_code=None,
                    next_action_code="ready",
                )
        except HTTPError as error:
            # 捕获 HTTP 状态码异常并转换为通道化中文引导
            code = int(getattr(error, "code", 0) or 0)
            if code in (401, 403):
                guidance = get_provider_error_guidance("MODEL_PROVIDER_AUTH_FAILED", base_url=target_base_url, http_code=code)
                return ProviderSnapshot(
                    status="unavailable",
                    reason_code="provider_auth_failed",
                    message=guidance["message"],
                    checked_at=_iso_now(),
                    expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                    source="probe",
                    stale=False,
                    provider_kind=p_kind,
                    provider_label=p_label,
                    provider_host=p_host,
                    model_id=target_model,
                    paid_probe_performed=False,
                    last_runtime_failure_code="MODEL_PROVIDER_AUTH_FAILED",
                    next_action_code=guidance["next_action_code"],
                )
            if code == 402:
                guidance = get_provider_error_guidance("MODEL_PROVIDER_BALANCE_EXHAUSTED", base_url=target_base_url, http_code=402)
                return ProviderSnapshot(
                    status="unavailable",
                    reason_code="provider_balance_exhausted",
                    message=guidance["message"],
                    checked_at=_iso_now(),
                    expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                    source="probe",
                    stale=False,
                    provider_kind=p_kind,
                    provider_label=p_label,
                    provider_host=p_host,
                    model_id=target_model,
                    paid_probe_performed=False,
                    last_runtime_failure_code="MODEL_PROVIDER_BALANCE_EXHAUSTED",
                    next_action_code=guidance["next_action_code"],
                )
            guidance = get_provider_error_guidance("MODEL_PROVIDER_TEMPORARILY_UNAVAILABLE", base_url=target_base_url, http_code=code)
            return ProviderSnapshot(
                status="unavailable",
                reason_code="provider_temporarily_unavailable",
                message=guidance["message"],
                checked_at=_iso_now(),
                expires_at=_iso_now(60),
                source="probe",
                stale=False,
                provider_kind=p_kind,
                provider_label=p_label,
                provider_host=p_host,
                model_id=target_model,
                paid_probe_performed=False,
                last_runtime_failure_code="MODEL_PROVIDER_TEMPORARILY_UNAVAILABLE",
                next_action_code=guidance["next_action_code"],
            )
        except (URLError, TimeoutError, OSError) as error:
            # 网络不通或超时
            return ProviderSnapshot(
                status="unavailable",
                reason_code="provider_temporarily_unavailable",
                message=f"{p_label} 网络连接超时或不可达（{type(error).__name__}）。",
                checked_at=_iso_now(),
                expires_at=_iso_now(60),
                source="probe",
                stale=False,
                provider_kind=p_kind,
                provider_label=p_label,
                provider_host=p_host,
                model_id=target_model,
                paid_probe_performed=False,
                last_runtime_failure_code="MODEL_PROVIDER_UNREACHABLE",
                next_action_code="retry_later",
            )

    # 步骤 2：请求 /models 验证密钥对模型列表的读取权限与模型就绪性
    models_url = f"{target_base_url}/models"
    models_request = Request(
        models_url,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "AuditTrace-Probe/0.7.1",
        },
        method="GET",
    )
    try:
        with _open_with_retry(models_request, timeout=timeout) as response:
            raw = response.read()
            try:
                models_data = json.loads(raw.decode("utf-8"))
            except Exception:
                models_data = {}
            model_items = models_data.get("data") if isinstance(models_data.get("data"), list) else []
            model_ids = {str(item.get("id") or "") for item in model_items if isinstance(item, dict)}

            # 若供应商返回了模型列表，且配置的模型既不在列表中也不是已知标准别名
            known_aliases = {"deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-coder"}
            if model_ids and target_model not in model_ids and target_model not in known_aliases:
                # 检查是否存在包含关系的前缀匹配
                has_match = any(target_model in mid or mid in target_model for mid in model_ids)
                if not has_match:
                    return ProviderSnapshot(
                        status="unavailable",
                        reason_code="provider_model_unavailable",
                        message=f"{p_label} 当前可用列表中未找到配置的模型 {target_model}。",
                        checked_at=_iso_now(),
                        expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                        source="probe",
                        stale=False,
                        provider_kind=p_kind,
                        provider_label=p_label,
                        provider_host=p_host,
                        model_id=target_model,
                        paid_probe_performed=False,
                        last_runtime_failure_code="MODEL_UNAVAILABLE",
                        next_action_code="check_model_id",
                    )
            # 鉴权与模型列表探测均通过
            return ProviderSnapshot(
                status="ready",
                reason_code="ready",
                message=f"{p_label} 鉴权、余额与可用模型均探测通过。",
                checked_at=_iso_now(),
                expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                source="probe",
                stale=False,
                provider_kind=p_kind,
                provider_label=p_label,
                provider_host=p_host,
                model_id=target_model,
                paid_probe_performed=False,
                last_runtime_failure_code=None,
                next_action_code="ready",
            )
    except HTTPError as error:
        # 处理模型列表探测过程中的 HTTP 状态码异常
        code = int(getattr(error, "code", 0) or 0)
        if code in (401, 403):
            guidance = get_provider_error_guidance("MODEL_PROVIDER_AUTH_FAILED", base_url=target_base_url, http_code=code)
            return ProviderSnapshot(
                status="unavailable",
                reason_code="provider_auth_failed",
                message=guidance["message"],
                checked_at=_iso_now(),
                expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                source="probe",
                stale=False,
                provider_kind=p_kind,
                provider_label=p_label,
                provider_host=p_host,
                model_id=target_model,
                paid_probe_performed=False,
                last_runtime_failure_code="MODEL_PROVIDER_AUTH_FAILED",
                next_action_code=guidance["next_action_code"],
            )
        if code == 402:
            guidance = get_provider_error_guidance("MODEL_PROVIDER_BALANCE_EXHAUSTED", base_url=target_base_url, http_code=402)
            return ProviderSnapshot(
                status="unavailable",
                reason_code="provider_balance_exhausted",
                message=guidance["message"],
                checked_at=_iso_now(),
                expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                source="probe",
                stale=False,
                provider_kind=p_kind,
                provider_label=p_label,
                provider_host=p_host,
                model_id=target_model,
                paid_probe_performed=False,
                last_runtime_failure_code="MODEL_PROVIDER_BALANCE_EXHAUSTED",
                next_action_code=guidance["next_action_code"],
            )
        guidance = get_provider_error_guidance("MODEL_PROVIDER_TEMPORARILY_UNAVAILABLE", base_url=target_base_url, http_code=code)
        return ProviderSnapshot(
            status="unavailable",
            reason_code="provider_temporarily_unavailable",
            message=guidance["message"],
            checked_at=_iso_now(),
            expires_at=_iso_now(60),
            source="probe",
            stale=False,
            provider_kind=p_kind,
            provider_label=p_label,
            provider_host=p_host,
            model_id=target_model,
            paid_probe_performed=False,
            last_runtime_failure_code="MODEL_PROVIDER_TEMPORARILY_UNAVAILABLE",
            next_action_code=guidance["next_action_code"],
        )
    except (URLError, TimeoutError, OSError) as error:
        # 网络连接异常或探测超时
        return ProviderSnapshot(
            status="unavailable",
            reason_code="provider_temporarily_unavailable",
            message=f"{p_label} 模型列表连接超时（{type(error).__name__}）。",
            checked_at=_iso_now(),
            expires_at=_iso_now(60),
            source="probe",
            stale=False,
            provider_kind=p_kind,
            provider_label=p_label,
            provider_host=p_host,
            model_id=target_model,
            paid_probe_performed=False,
            last_runtime_failure_code="MODEL_PROVIDER_UNREACHABLE",
            next_action_code="retry_later",
        )


def get_provider_snapshot(*, force_refresh: bool = False) -> ProviderSnapshot:
    """获取当前供应商就绪快照；带线程安全 TTL 缓存，避免请求打满供应商。"""

    global _current_snapshot, _last_probe_timestamp
    target_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    target_model = os.getenv("DEEPSEEK_MODEL", "qwen3.5-plus").strip()
    channel_info = classify_provider_channel(target_base_url)

    if not is_provider_probe_enabled():
        # 未开启主动探测时，配置本身或陈旧探测不能被提升为当前可运行状态。
        # 但同一服务进程中刚完成的真实 Agent 调用是更强的运行时证据，必须
        # 如实保留；否则结果页已 model_success 而状态栏仍显示“未验证”。
        # 真实失败仍优先展示，避免成功记录掩盖后续鉴权/额度问题。
        with _lock:
            if _current_snapshot is not None and _current_snapshot.source in ("live_run", "circuit_breaker"):
                return _current_snapshot
        return ProviderSnapshot(
            status="unavailable",
            reason_code="provider_probe_disabled",
            message=f"服务端未开启 {channel_info['provider_label']} 主动探测；当前真实模型可运行性尚未验证。",
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="default",
            stale=False,
            provider_kind=channel_info["provider_kind"],
            provider_label=channel_info["provider_label"],
            provider_host=channel_info["provider_host"],
            model_id=target_model,
            paid_probe_performed=False,
            last_runtime_failure_code=None,
            next_action_code="enable_provider_probe_or_run_live",
        )

    with _lock:
        # 已启用探测时，最近一次真实运行反馈仍优先于普通 TTL 缓存。
        if _current_snapshot is not None and _current_snapshot.source in ("live_run", "circuit_breaker"):
            return _current_snapshot

    now = time.time()
    with _lock:
        if not force_refresh and _current_snapshot is not None:
            age = now - _last_probe_timestamp
            if age < DEFAULT_PROBE_TTL_SECONDS:
                # 处于新鲜有效期内，直接复用当前快照
                return _current_snapshot
            if age < DEFAULT_HARD_EXPIRY_SECONDS:
                # 处于软过期窗口（5~10分钟）：返回带 stale 标记的旧快照，后台异步触发刷新
                stale_copy = ProviderSnapshot(
                    status=_current_snapshot.status,
                    reason_code=_current_snapshot.reason_code,
                    message=_current_snapshot.message,
                    checked_at=_current_snapshot.checked_at,
                    expires_at=_current_snapshot.expires_at,
                    source=_current_snapshot.source,
                    stale=True,
                    provider_kind=_current_snapshot.provider_kind,
                    provider_label=_current_snapshot.provider_label,
                    provider_host=_current_snapshot.provider_host,
                    model_id=_current_snapshot.model_id,
                    paid_probe_performed=_current_snapshot.paid_probe_performed,
                    last_runtime_failure_code=_current_snapshot.last_runtime_failure_code,
                    next_action_code=_current_snapshot.next_action_code,
                )
                # 启动后台线程异步刷新，不阻塞当前前端用户的界面加载
                _trigger_background_probe()
                return stale_copy

    # 首次加载或已超过硬过期时间：同步探测并更新快照
    new_snapshot = probe_provider()
    with _lock:
        _current_snapshot = new_snapshot
        _last_probe_timestamp = time.time()
    return new_snapshot


def _trigger_background_probe() -> None:
    """在后台独立线程中异步执行探测，不阻塞当前请求。使用原子标志防范雷群效应。"""
    global _probe_in_flight
    with _lock:
        # 如果已经有后台探测线程正在进行中，直接返回，避免并发重复请求打满供应商
        if _probe_in_flight:
            return
        _probe_in_flight = True

    def _worker() -> None:
        global _current_snapshot, _last_probe_timestamp, _probe_in_flight
        try:
            snapshot = probe_provider()
            with _lock:
                _current_snapshot = snapshot
                _last_probe_timestamp = time.time()
        except Exception:
            # 后台线程内异常静默处理，避免崩溃主进程
            pass
        finally:
            with _lock:
                # 探测结束后释放后台运行标志
                _probe_in_flight = False

    # 启动后台 Daemon 线程
    thread = threading.Thread(target=_worker, daemon=True, name="ProviderProbeWorker")
    thread.start()


def record_provider_success(model_id: str = "", base_url: str | None = None) -> None:
    """真实 Agent 角色调用成功后调用，清除鉴权/余额熔断状态。"""

    global _current_snapshot, _last_probe_timestamp
    target_base_url = (base_url if base_url is not None else os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).rstrip("/")
    channel_info = classify_provider_channel(target_base_url)
    used_model = model_id or os.getenv("DEEPSEEK_MODEL", "qwen3.5-plus")

    with _lock:
        # 当真实 Agent 运行成功返回有效输出时，重置快照为就绪状态
        _current_snapshot = ProviderSnapshot(
            status="ready",
            reason_code="ready",
            message=f"真实三Agent角色调用成功（{channel_info['provider_label']} · {used_model}）。",
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="live_run",
            stale=False,
            provider_kind=channel_info["provider_kind"],
            provider_label=channel_info["provider_label"],
            provider_host=channel_info["provider_host"],
            model_id=used_model,
            paid_probe_performed=True,
            last_runtime_failure_code=None,
            next_action_code="ready",
        )
        _last_probe_timestamp = time.time()


def record_provider_failure(failure_code: str, message: str = "", base_url: str | None = None) -> None:
    """真实运行出现永久性或严重 provider 错误时调用，立即触发熔断。"""

    global _current_snapshot, _last_probe_timestamp
    target_base_url = (base_url if base_url is not None else os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).rstrip("/")
    channel_info = classify_provider_channel(target_base_url)
    guidance = get_provider_error_guidance(failure_code, base_url=target_base_url)
    used_model = os.getenv("DEEPSEEK_MODEL", "qwen3.5-plus")

    with _lock:
        # 立即写入熔断快照，使后续前端轮询能够及时感知到供应商不可用
        _current_snapshot = ProviderSnapshot(
            status="unavailable",
            reason_code=guidance["reason_code"],
            message=message or guidance["message"],
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="circuit_breaker",
            stale=False,
            provider_kind=channel_info["provider_kind"],
            provider_label=channel_info["provider_label"],
            provider_host=channel_info["provider_host"],
            model_id=used_model,
            paid_probe_performed=True,
            last_runtime_failure_code=failure_code,
            next_action_code=guidance["next_action_code"],
        )
        _last_probe_timestamp = time.time()


def reset_provider_readiness() -> None:
    """重置供应商快照状态，主要供自动化测试隔离使用。"""

    global _current_snapshot, _last_probe_timestamp, _probe_in_flight
    with _lock:
        # 清空全局缓存与时间戳，确保各单元测试之间互不干扰
        _current_snapshot = None
        _last_probe_timestamp = 0.0
        _probe_in_flight = False
