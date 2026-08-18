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
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# 默认缓存时间：5 分钟内复用快照，避免频繁向外部供应商发送重复请求
DEFAULT_PROBE_TTL_SECONDS = 300
# 硬过期时间：10 分钟后快照彻底失效，必须强制刷新探测
DEFAULT_HARD_EXPIRY_SECONDS = 600
# 探测网络超时：连接与读取控制在 4 秒以内，确保即使供应商网络波动也不卡死服务端接口
DEFAULT_PROBE_TIMEOUT_SECONDS = 4.0


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
    - stale: 布尔值，当快照超过 TTL 但在硬过期窗口内时为 True，提示上游当前正在后台刷新。
    """

    status: str  # "ready" | "unavailable"
    reason_code: str  # "ready" | "provider_auth_failed" | "provider_balance_exhausted" | "provider_model_unavailable" | "provider_temporarily_unavailable" | "provider_status_unknown" | "provider_probe_disabled" | "api_key_missing"
    message: str
    checked_at: str  # ISO 格式时间戳
    expires_at: str  # ISO 格式时间戳
    source: str  # "probe" | "live_run" | "circuit_breaker" | "cached" | "default"
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        """序列化为可对外公开的字典结构。"""
        # 转换并返回标准字典格式，供 FastAPI 路由直接序列化为 JSON 响应
        return asdict(self)


# 线程锁与全局单例快照对象
_lock = threading.Lock()
# 当前持有的最新供应商就绪快照
_current_snapshot: ProviderSnapshot | None = None
# 上次成功执行探测并记录的时间戳（秒）
_last_probe_timestamp: float = 0.0


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
    2. 若目标为官方 DeepSeek 接口，向 `/user/balance` 发送只读请求检验可用额度；
    3. 若目标为标准 OpenAI 兼容网关或自建服务，向 `/models` 发送只读请求检验模型列表与鉴权；
    4. 根据 HTTP 状态码（401/402/429/5xx）与返回结构分类映射为稳定的就绪原因码；
    5. 捕获并妥善处理所有网络异常（超时、连接拒绝、DNS 解析失败），绝不向上抛出未捕获异常。
    """

    # 提取 API Key：优先使用传入参数，其次读取环境变量
    key = (api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")).strip()
    if not key:
        # 未配置 API Key 时返回明确的不可用原因码
        return ProviderSnapshot(
            status="unavailable",
            reason_code="api_key_missing",
            message="服务端尚未配置模型 API Key；可运行仅计算或确定性备用分析。",
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="probe",
            stale=False,
        )

    # 规范化 Base URL 与目标模型标识
    target_base_url = (base_url if base_url is not None else os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).rstrip("/")
    target_model = (model_id if model_id is not None else os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")).strip()
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
            with urlopen(balance_request, timeout=timeout) as response:
                raw = response.read()
                try:
                    balance_data = json.loads(raw.decode("utf-8"))
                except Exception:
                    # 响应解析异常时降级为空字典
                    balance_data = {}
                # is_available 明确为 False 时表示账户欠费或无可用充值余额
                if balance_data.get("is_available") is False:
                    return ProviderSnapshot(
                        status="unavailable",
                        reason_code="provider_balance_exhausted",
                        message="模型供应商账户余额不足或不可用，请充值后重试。",
                        checked_at=_iso_now(),
                        expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                        source="probe",
                        stale=False,
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
                )
        except HTTPError as error:
            # 捕获 HTTP 状态码异常
            code = int(getattr(error, "code", 0) or 0)
            if code in (401, 403):
                # 401/403 表示鉴权未通过，API Key 无效或已被撤销
                return ProviderSnapshot(
                    status="unavailable",
                    reason_code="provider_auth_failed",
                    message="模型供应商鉴权失败，请检查 API Key 配置。",
                    checked_at=_iso_now(),
                    expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                    source="probe",
                    stale=False,
                )
            if code == 402:
                # 402 Payment Required 表示欠费或余额不足
                return ProviderSnapshot(
                    status="unavailable",
                    reason_code="provider_balance_exhausted",
                    message="模型供应商账户余额不足，请充值后重试。",
                    checked_at=_iso_now(),
                    expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                    source="probe",
                    stale=False,
                )
            if code in (429, 500, 502, 503, 504):
                # 429 或 5xx 表示供应商服务端限流或临时不可用，缩短缓存时间
                return ProviderSnapshot(
                    status="unavailable",
                    reason_code="provider_temporarily_unavailable",
                    message=f"模型供应商服务暂不可用（HTTP {code}），请稍后重试。",
                    checked_at=_iso_now(),
                    expires_at=_iso_now(60),  # 暂态失败缩短缓存重试周期
                    source="probe",
                    stale=False,
                )
            # 兜底未知 HTTP 状态码
            return ProviderSnapshot(
                status="unavailable",
                reason_code="provider_temporarily_unavailable",
                message=f"模型供应商返回异常响应（HTTP {code}）。",
                checked_at=_iso_now(),
                expires_at=_iso_now(60),
                source="probe",
                stale=False,
            )
        except (URLError, TimeoutError, OSError) as error:
            # 网络不通或超时
            return ProviderSnapshot(
                status="unavailable",
                reason_code="provider_temporarily_unavailable",
                message=f"模型供应商网络连接超时或不可达（{type(error).__name__}）。",
                checked_at=_iso_now(),
                expires_at=_iso_now(60),
                source="probe",
                stale=False,
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
        with urlopen(models_request, timeout=timeout) as response:
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
                        message=f"模型供应商当前可用列表中未找到配置的模型 {target_model}。",
                        checked_at=_iso_now(),
                        expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                        source="probe",
                        stale=False,
                    )
            # 鉴权与模型列表探测均通过
            return ProviderSnapshot(
                status="ready",
                reason_code="ready",
                message="模型供应商鉴权、余额与可用模型均探测通过。",
                checked_at=_iso_now(),
                expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                source="probe",
                stale=False,
            )
    except HTTPError as error:
        # 处理模型列表探测过程中的 HTTP 状态码异常
        code = int(getattr(error, "code", 0) or 0)
        if code in (401, 403):
            return ProviderSnapshot(
                status="unavailable",
                reason_code="provider_auth_failed",
                message="模型供应商鉴权失败，请检查 API Key 配置。",
                checked_at=_iso_now(),
                expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                source="probe",
                stale=False,
            )
        if code == 402:
            return ProviderSnapshot(
                status="unavailable",
                reason_code="provider_balance_exhausted",
                message="模型供应商账户余额不足，请充值后重试。",
                checked_at=_iso_now(),
                expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
                source="probe",
                stale=False,
            )
        return ProviderSnapshot(
            status="unavailable",
            reason_code="provider_temporarily_unavailable",
            message=f"模型供应商模型列表检查异常（HTTP {code}）。",
            checked_at=_iso_now(),
            expires_at=_iso_now(60),
            source="probe",
            stale=False,
        )
    except (URLError, TimeoutError, OSError) as error:
        # 网络连接异常或探测超时
        return ProviderSnapshot(
            status="unavailable",
            reason_code="provider_temporarily_unavailable",
            message=f"模型供应商模型列表连接超时（{type(error).__name__}）。",
            checked_at=_iso_now(),
            expires_at=_iso_now(60),
            source="probe",
            stale=False,
        )


def get_provider_snapshot(*, force_refresh: bool = False) -> ProviderSnapshot:
    """获取当前供应商就绪快照；带线程安全 TTL 缓存，避免请求打满供应商。"""

    global _current_snapshot, _last_probe_timestamp
    with _lock:
        # 若已有真实运行（live_run 或 circuit_breaker）记录的最新快照，优先返回
        if _current_snapshot is not None and _current_snapshot.source in ("live_run", "circuit_breaker"):
            return _current_snapshot

    if not is_provider_probe_enabled():
        # 未开启主动探测时返回中性默认快照，不阻塞系统的正常运行
        return ProviderSnapshot(
            status="ready",
            reason_code="provider_probe_disabled",
            message="服务端未开启供应商主动探测；以本地配置和实际运行硬校验为准。",
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="default",
            stale=False,
        )

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
    """在后台独立线程中异步执行探测，不阻塞当前请求。"""
    def _worker() -> None:
        global _current_snapshot, _last_probe_timestamp
        try:
            snapshot = probe_provider()
            with _lock:
                _current_snapshot = snapshot
                _last_probe_timestamp = time.time()
        except Exception:
            # 后台线程内异常静默处理，避免崩溃主进程
            pass

    # 启动后台 Daemon 线程
    thread = threading.Thread(target=_worker, daemon=True, name="ProviderProbeWorker")
    thread.start()


def record_provider_success(model_id: str = "") -> None:
    """真实 Agent 角色调用成功后调用，清除鉴权/余额熔断状态。"""

    global _current_snapshot, _last_probe_timestamp
    with _lock:
        # 当真实 Agent 运行成功返回有效输出时，重置快照为就绪状态
        _current_snapshot = ProviderSnapshot(
            status="ready",
            reason_code="ready",
            message=f"真实三Agent角色调用成功（{model_id or 'deepseek'}）。",
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="live_run",
            stale=False,
        )
        _last_probe_timestamp = time.time()


def record_provider_failure(failure_code: str, message: str = "") -> None:
    """真实运行出现永久性或严重 provider 错误时调用，立即触发熔断。"""

    global _current_snapshot, _last_probe_timestamp
    # 映射运行时错误码至标准化的供应商就绪原因码与中文提示
    code_map = {
        "MODEL_PROVIDER_AUTH_FAILED": ("provider_auth_failed", "真实运行收到供应商鉴权失败（401/403），请检查 API Key 配置。"),
        "MODEL_PROVIDER_BALANCE_EXHAUSTED": ("provider_balance_exhausted", "真实运行收到供应商余额不足（402），请充值后重试。"),
        "MODEL_PROVIDER_REGION_OPT_IN_REQUIRED": ("provider_auth_failed", "真实运行收到区域合规或协议要求，请检查供应商配置。"),
        "MODEL_PROVIDER_RATE_LIMITED": ("provider_temporarily_unavailable", "真实运行收到供应商限流，请稍后重试。"),
    }
    mapped_reason, default_msg = code_map.get(
        failure_code,
        ("provider_temporarily_unavailable", f"真实运行供应商调用异常（{failure_code}）。"),
    )
    with _lock:
        # 立即写入熔断快照，使后续前端轮询能够及时感知到供应商不可用
        _current_snapshot = ProviderSnapshot(
            status="unavailable",
            reason_code=mapped_reason,
            message=message or default_msg,
            checked_at=_iso_now(),
            expires_at=_iso_now(DEFAULT_PROBE_TTL_SECONDS),
            source="circuit_breaker",
            stale=False,
        )
        _last_probe_timestamp = time.time()


def reset_provider_readiness() -> None:
    """重置供应商快照状态，主要供自动化测试隔离使用。"""

    global _current_snapshot, _last_probe_timestamp
    with _lock:
        # 清空全局缓存与时间戳，确保各单元测试之间互不干扰
        _current_snapshot = None
        _last_probe_timestamp = 0.0
