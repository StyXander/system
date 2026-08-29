"""公开竞赛模式的模型额度、并发租约和结果缓存。

公开演示不依赖登录，但模型调用仍必须有可追溯的预算边界。
本地开发使用 SQLite；部署到 Supabase 时，调用方可以把同样的记录
迁移到服务端表，浏览器永远不会接触模型密钥或额度流水。
额度判断在服务端完成，前端显示的剩余额度不能作为放行依据。
访客标识只保存带服务端秘密的摘要，不保存原始网络地址。
每次真实调用先建立租约，完成后再登记实际输入与输出令牌数。
供应商失败会释放租约，不能把失败请求伪装成成功缓存。
未结算租约设有短时限，工作进程异常退出后可以自动回收。
回收过期租约必须发生在窗口计数之前，否则旧租约会继续误伤访客。
十五分钟访客限额、全局限额和进程并发限额分别计算。
服务端批量预热只绕过访客窗口，不绕过每日总量和并发上限。
每日边界按北京时间计算，避免托管平台默认时区造成跨日错算。
极简容器缺少时区数据库时使用固定 UTC+8 作为受控降级。
输入和输出令牌预算分别登记，不能用调用次数替代成本控制。
结算后的令牌数来自供应商响应，不从字符数推算虚假用量。
缓存只保存已经通过结构、证据和事实语言硬校验的运行响应。
缓存身份必须包含案例、年度、规则、来源快照、模型和提示词版本。
规则阈值、确定性结果和实际模型证据通过输入指纹进入缓存身份。
人工更正字段或改变阈值后输入指纹变化，旧草稿不得继续命中。
补充资料使用独立哈希，新增资料不会覆盖无资料版本的缓存。
规则编号排序后参与哈希，同一规则集合不因请求顺序重复消耗模型。
缓存键只保存摘要，不把字段原文或补充资料内容写入索引列。
缓存响应仍保留模型调用审计信息，但新请求必须生成新运行编号。
复用时所有嵌套输出的运行编号同步更新，避免父子链引用旧运行。
新运行上下文来自当前请求，旧上下文只作为缓存来源留痕。
运行命名空间隔离测试、批量验收和正式演示的额度账本。
测试批次不能消耗正式站点额度，也不能给正式站点预热缓存。
命名空间只接受稳定字符并限制长度，不能借环境变量构造路径穿越。
SQLite 写入在进程锁和事务内完成，避免并发访客超发同一额度。
同一缓存键的并发请求使用进程内合并点，首个请求负责填充。
等待者只读取已写入的完整缓存，超时后才重新争取填充资格。
缓存内容损坏或无法通过当前响应模型校验时按未命中处理。
过期缓存读取时立即删除，不能继续作为历史成功证据返回。
额度账本与模型密钥完全分离，数据库不记录任何供应商密钥。
默认额度是安全下限，环境变量解析失败时不能解释成无限额度。
额度配置最小值为一，错误的零或负数不会关闭保护。
达到每日预算后新调用失败关闭，本地确定性计算结果仍可保留。
结算时发现超预算会把本次响应标成不可用，不能缓存为模型成功。
当前账本不能预知单次请求的最终令牌数，仍需供应商侧硬预算配合。
公开站点应使用不可预测的额度摘要秘密，并按部署环境单独配置。
本模块只处理调用额度和缓存，不替代案例授权、隐私扫描或 RAG 闸门。
调用方必须先通过来源、授权和敏感信息检查，再申请真实模型租约。
任何演示便利开关都不得绕过这些上游失败关闭条件。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class QuotaConfig:
    window_seconds: int = 900
    per_ip: int = 2
    global_window: int = 10
    max_concurrent: int = 2
    reservation_ttl_seconds: int = 180
    daily_runs: int = 60
    daily_input_tokens: int = 1_000_000
    daily_output_tokens: int = 300_000
    cache_seconds: int = 86_400
    cache_fill_ttl_seconds: int = 300

    @classmethod
    def from_env(cls) -> "QuotaConfig":
        def integer(name: str, default: int) -> int:
            try:
                return max(1, int(os.getenv(name, str(default))))
            except (TypeError, ValueError):
                return default

        return cls(
            window_seconds=integer("AUDITTRACE_MODEL_RUN_WINDOW_SECONDS", 900),
            per_ip=integer("AUDITTRACE_MODEL_RUN_LIMIT", 2),
            global_window=integer("AUDITTRACE_MODEL_RUN_GLOBAL_LIMIT", 10),
            max_concurrent=integer("AUDITTRACE_MODEL_MAX_CONCURRENT", 2),
            reservation_ttl_seconds=integer("AUDITTRACE_MODEL_RESERVATION_TTL_SECONDS", 180),
            daily_runs=integer("AUDITTRACE_MODEL_DAILY_RUN_LIMIT", 60),
            daily_input_tokens=integer("AUDITTRACE_MODEL_DAILY_INPUT_TOKENS", 1_000_000),
            daily_output_tokens=integer("AUDITTRACE_MODEL_DAILY_OUTPUT_TOKENS", 300_000),
            cache_seconds=integer("AUDITTRACE_MODEL_CACHE_SECONDS", 86_400),
            cache_fill_ttl_seconds=integer("AUDITTRACE_MODEL_CACHE_FILL_TTL_SECONDS", 300),
        )


class PublicModelQuotaError(RuntimeError):
    """公开模型额度或并发租约不可用。"""

    code = "PUBLIC_MODEL_QUOTA_EXCEEDED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        # Supabase RPC 只允许返回受控短码；保留它可以让 API/日志区分
        # IP、全局并发、每日预算和数据库不可用，而不暴露供应商或 SQL 详情。
        if code:
            self.code = str(code)[:80]


class PublicModelLedger:
    """可测试的原子额度账本；运行结果只保存结构化缓存，不保存密钥。"""

    def __init__(self, workspace_root: Path, *, config: QuotaConfig | None = None) -> None:
        self.root = Path(workspace_root)
        self.config = config or QuotaConfig.from_env()
        namespace = re.sub(r"[^A-Za-z0-9_-]", "", os.getenv("AUDITTRACE_RUNTIME_NAMESPACE", ""))[:80]
        runtime_root = self.root / "backend" / "runtime"
        self.path = (runtime_root / namespace if namespace else runtime_root) / "public_model_ledger.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._inflight_lock = threading.Lock()
        self._inflight: dict[str, tuple[threading.Event, float]] = {}
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                create table if not exists model_usage (
                    id integer primary key autoincrement,
                    ip_hash text not null,
                    reserved_at real not null,
                    reservation_id text not null unique,
                    input_tokens integer not null default 0,
                    output_tokens integer not null default 0,
                    settled integer not null default 0,
                    released integer not null default 0
                );
                create index if not exists model_usage_time_idx on model_usage(reserved_at);
                create table if not exists model_cache (
                    cache_key text primary key,
                    created_at real not null,
                    run_payload text not null
                );
                """
            )

    def _prune(self, connection: sqlite3.Connection, now: float) -> None:
        connection.execute(
            "delete from model_usage where reserved_at < ?",
            (now - max(self.config.window_seconds, 86_400),),
        )

    def _day_start(self) -> float:
        # 竞赛数据按北京时间统计，避免 Render 默认 UTC 导致跨日错算。
        try:
            local_now = datetime.now(ZoneInfo("Asia/Shanghai"))
        except Exception:
            # 极简容器可能没有 tzdata 包；固定 UTC+8 仍保持竞赛日界线稳定。
            local_now = datetime.now(timezone(timedelta(hours=8)))
        now = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return now.timestamp()

    @staticmethod
    def hash_client(client_id: str) -> str:
        secret = os.getenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "audittrace-demo-quota").encode("utf-8")
        return hmac.new(secret, str(client_id).encode("utf-8"), hashlib.sha256).hexdigest()

    def reserve(self, client_id: str) -> str:
        now = time.time()
        ip_hash = self.hash_client(client_id)
        reservation_id = secrets.token_urlsafe(18)
        with self._lock, self._connect() as connection:
            self._prune(connection, now)
            connection.execute(
                "update model_usage set released=1,settled=1 where settled=0 and released=0 and reserved_at < ?",
                (now - self.config.reservation_ttl_seconds,),
            )
            recent_ip = connection.execute(
                "select count(*) from model_usage where ip_hash=? and reserved_at>=? and released=0",
                (ip_hash, now - self.config.window_seconds),
            ).fetchone()[0]
            recent_global = connection.execute(
                "select count(*) from model_usage where reserved_at>=? and released=0",
                (now - self.config.window_seconds,),
            ).fetchone()[0]
            active = connection.execute(
                "select count(*) from model_usage where settled=0 and released=0 and reserved_at >= ?",
                (now - self.config.reservation_ttl_seconds,),
            ).fetchone()[0]
            day_runs = connection.execute(
                "select count(*) from model_usage where reserved_at>=? and released=0",
                (self._day_start(),),
            ).fetchone()[0]
            if recent_ip >= self.config.per_ip:
                raise PublicModelQuotaError("当前访问来源的模型额度已达上限，请稍后再试。")
            if recent_global >= self.config.global_window:
                raise PublicModelQuotaError("公开演示模型正在排队，请稍后再试。")
            if active >= self.config.max_concurrent:
                raise PublicModelQuotaError("当前模型并发已满，请等待上一条分析完成。")
            if day_runs >= self.config.daily_runs:
                raise PublicModelQuotaError("今日公开演示额度已用完。")
            connection.execute(
                "insert into model_usage(ip_hash,reserved_at,reservation_id) values(?,?,?)",
                (ip_hash, now, reservation_id),
            )
        return reservation_id

    def reserve_batch(self, batch_id: str) -> str:
        """Reserve one server-side prewarm run without visitor window limits.

        A prewarm batch is authenticated by the server-only endpoint before it
        reaches this ledger.  It still consumes the daily run/token budget and
        respects the process-wide concurrent limit; only per-IP and public
        fifteen-minute limits are intentionally bypassed for the operator job.
        """

        now = time.time()
        ip_hash = self.hash_client(f"server-prewarm:{batch_id}")
        reservation_id = secrets.token_urlsafe(18)
        with self._lock, self._connect() as connection:
            self._prune(connection, now)
            connection.execute(
                "update model_usage set released=1,settled=1 where settled=0 and released=0 and reserved_at < ?",
                (now - self.config.reservation_ttl_seconds,),
            )
            active = connection.execute(
                "select count(*) from model_usage where settled=0 and released=0 and reserved_at >= ?",
                (now - self.config.reservation_ttl_seconds,),
            ).fetchone()[0]
            day_runs = connection.execute(
                "select count(*) from model_usage where reserved_at>=? and released=0",
                (self._day_start(),),
            ).fetchone()[0]
            if active >= self.config.max_concurrent:
                raise PublicModelQuotaError("当前模型并发已满，请等待上一条分析完成。")
            if day_runs >= self.config.daily_runs:
                raise PublicModelQuotaError("今日公开演示额度已用完。")
            connection.execute(
                "insert into model_usage(ip_hash,reserved_at,reservation_id) values(?,?,?)",
                (ip_hash, now, reservation_id),
            )
        return reservation_id

    def settle(self, reservation_id: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "select input_tokens,output_tokens from model_usage where reservation_id=? and released=0",
                (reservation_id,),
            ).fetchone()
            if row is None:
                return
            day_input = connection.execute(
                "select coalesce(sum(input_tokens),0) from model_usage where reserved_at>=? and released=0",
                (self._day_start(),),
            ).fetchone()[0]
            day_output = connection.execute(
                "select coalesce(sum(output_tokens),0) from model_usage where reserved_at>=? and released=0",
                (self._day_start(),),
            ).fetchone()[0]
            new_input = max(0, int(input_tokens))
            new_output = max(0, int(output_tokens))
            if day_input - int(row[0]) + new_input > self.config.daily_input_tokens:
                connection.execute("update model_usage set released=1,settled=1 where reservation_id=?", (reservation_id,))
                raise PublicModelQuotaError("今日输入 token 预算已用完。")
            if day_output - int(row[1]) + new_output > self.config.daily_output_tokens:
                connection.execute("update model_usage set released=1,settled=1 where reservation_id=?", (reservation_id,))
                raise PublicModelQuotaError("今日输出 token 预算已用完。")
            connection.execute(
                "update model_usage set input_tokens=?,output_tokens=?,settled=1 where reservation_id=?",
                (new_input, new_output, reservation_id),
            )

    def release(self, reservation_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("update model_usage set released=1,settled=1 where reservation_id=?", (reservation_id,))

    def quota_snapshot(self, client_id: str | None = None) -> dict[str, Any]:
        now = time.time()
        with self._lock, self._connect() as connection:
            self._prune(connection, now)
            connection.execute(
                "update model_usage set released=1,settled=1 where settled=0 and released=0 and reserved_at < ?",
                (now - self.config.reservation_ttl_seconds,),
            )
            global_count = connection.execute(
                "select count(*) from model_usage where reserved_at>=? and released=0",
                (now - self.config.window_seconds,),
            ).fetchone()[0]
            daily_count = connection.execute(
                "select count(*) from model_usage where reserved_at>=? and released=0",
                (self._day_start(),),
            ).fetchone()[0]
            active = connection.execute(
                "select count(*) from model_usage where settled=0 and released=0 and reserved_at >= ?",
                (now - self.config.reservation_ttl_seconds,),
            ).fetchone()[0]
            return {
                "global_remaining_15m": max(0, self.config.global_window - int(global_count)),
                "daily_runs_remaining": max(0, self.config.daily_runs - int(daily_count)),
                "active": int(active),
                "max_concurrent": self.config.max_concurrent,
                "reset_at": datetime.fromtimestamp(self._day_start() + 86_400, timezone.utc).isoformat(),
            }

    def get_cache(self, cache_key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("select created_at,run_payload from model_cache where cache_key=?", (cache_key,)).fetchone()
            if row is None or time.time() - float(row[0]) > self.config.cache_seconds:
                if row is not None:
                    connection.execute("delete from model_cache where cache_key=?", (cache_key,))
                return None
            try:
                payload = json.loads(row[1])
            except json.JSONDecodeError:
                connection.execute("delete from model_cache where cache_key=?", (cache_key,))
                return None
            return payload if isinstance(payload, dict) else None

    def put_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "insert into model_cache(cache_key,created_at,run_payload) values(?,?,?) on conflict(cache_key) do update set created_at=excluded.created_at,run_payload=excluded.run_payload",
                (cache_key, time.time(), json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
            )

    def acquire_cache_fill(self, cache_key: str) -> tuple[bool, threading.Event]:
        """为同一输入建立单进程合并点，避免两个访客同时调用模型。"""

        with self._inflight_lock:
            existing = self._inflight.get(cache_key)
            if existing is not None:
                event, started_at = existing
                if time.monotonic() - started_at <= self.config.cache_fill_ttl_seconds:
                    return False, event
                # 工作进程异常中断时允许超时接管；旧等待者同时被唤醒。
                event.set()
            event = threading.Event()
            self._inflight[cache_key] = (event, time.monotonic())
            return True, event

    def complete_cache_fill(self, cache_key: str, owner_event: threading.Event | None = None) -> None:
        """只允许当前所有者释放合并点，超时旧任务不能误删新任务。"""

        with self._inflight_lock:
            current = self._inflight.get(cache_key)
            if current is None:
                return
            event, _started_at = current
            if owner_event is not None and event is not owner_event:
                return
            self._inflight.pop(cache_key, None)
            event.set()


class SupabasePublicModelLedger:
    """Supabase 版公开额度账本，保持与本地 SQLite 账本相同的调用合同。

    所有计数、并发租约、每日预算和回收都在 Postgres RPC 事务内执行；
    Web 进程只保留同一缓存键的短时 singleflight，不把额度事实放回本地。
    ``service-role`` 客户端只在服务端实例化，浏览器和公开响应永远拿不到它。
    """

    def __init__(self, client: Any | None = None, *, config: QuotaConfig | None = None) -> None:
        if client is None:
            from .supabase_adapter import get_demo_task_client

            client = get_demo_task_client()
        self.client = client
        self.config = config or QuotaConfig.from_env()
        self._inflight_lock = threading.Lock()
        self._inflight: dict[str, tuple[threading.Event, float]] = {}

    @staticmethod
    def hash_client(client_id: str) -> str:
        secret = os.getenv("AUDITTRACE_PUBLIC_QUOTA_SECRET", "audittrace-demo-quota").encode("utf-8")
        return hmac.new(secret, str(client_id).encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _quota_error(result: dict[str, Any]) -> PublicModelQuotaError:
        # RPC 只返回稳定码和短消息；不把数据库错误正文传到页面。
        message = str(result.get("message") or "公开模型额度暂不可用，请稍后重试。")[:240]
        raw_code = result.get("code")
        code = str(raw_code)[:80] if raw_code else None
        return PublicModelQuotaError(message, code=code)

    def _reserve(self, client_id: str, *, batch: bool) -> str:
        reservation_id = secrets.token_urlsafe(18)
        result = self.client.reserve_public_model_usage(
            reservation_id=reservation_id,
            client_hash=self.hash_client(client_id),
            window_seconds=self.config.window_seconds,
            per_ip=self.config.per_ip,
            global_window=self.config.global_window,
            max_concurrent=self.config.max_concurrent,
            daily_runs=self.config.daily_runs,
            reservation_ttl_seconds=self.config.reservation_ttl_seconds,
            batch=batch,
        )
        if not bool(result.get("ok")):
            raise self._quota_error(result)
        accepted = str(result.get("reservation_id") or reservation_id)
        if not accepted:
            raise PublicModelQuotaError("公开模型额度预留未返回有效编号。")
        return accepted

    def reserve(self, client_id: str) -> str:
        return self._reserve(client_id, batch=False)

    def reserve_batch(self, batch_id: str) -> str:
        return self._reserve(f"server-prewarm:{batch_id}", batch=True)

    def settle(self, reservation_id: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        result = self.client.settle_public_model_usage(
            reservation_id=reservation_id,
            input_tokens=max(0, int(input_tokens)),
            output_tokens=max(0, int(output_tokens)),
            daily_input_tokens=self.config.daily_input_tokens,
            daily_output_tokens=self.config.daily_output_tokens,
        )
        if not bool(result.get("ok")):
            raise self._quota_error(result)

    def release(self, reservation_id: str) -> None:
        self.client.release_public_model_usage(reservation_id=reservation_id)

    def quota_snapshot(self, client_id: str | None = None) -> dict[str, Any]:
        result = self.client.snapshot_public_model_usage(
            client_hash=self.hash_client(client_id) if client_id else None,
            window_seconds=self.config.window_seconds,
            global_window=self.config.global_window,
            max_concurrent=self.config.max_concurrent,
            reservation_ttl_seconds=self.config.reservation_ttl_seconds,
            daily_runs=self.config.daily_runs,
        )
        if not bool(result.get("ok", True)):
            raise self._quota_error(result)
        # 保持前端旧字段兼容，新台账不返回具体访客标识或数据库行。
        return {
            "global_remaining_15m": max(0, int(result.get("global_remaining_15m") or 0)),
            "daily_runs_remaining": max(0, int(result.get("daily_runs_remaining") or 0)),
            "active": max(0, int(result.get("active") or 0)),
            "max_concurrent": max(1, int(result.get("max_concurrent") or self.config.max_concurrent)),
            "reset_at": str(result.get("reset_at") or ""),
        }

    def get_cache(self, cache_key: str) -> dict[str, Any] | None:
        row = self.client.get_public_model_cache(cache_key_hash=cache_key)
        if not isinstance(row, dict):
            return None
        created = str(row.get("created_at") or "")
        try:
            parsed = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - parsed > timedelta(seconds=self.config.cache_seconds):
                self.client.delete_public_model_cache(cache_key_hash=cache_key)
                return None
        except ValueError:
            self.client.delete_public_model_cache(cache_key_hash=cache_key)
            return None
        payload = row.get("run_payload")
        if not isinstance(payload, dict):
            self.client.delete_public_model_cache(cache_key_hash=cache_key)
            return None
        return payload

    def put_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        self.client.put_public_model_cache(cache_key_hash=cache_key, run_payload=payload)

    def acquire_cache_fill(self, cache_key: str) -> tuple[bool, threading.Event]:
        with self._inflight_lock:
            existing = self._inflight.get(cache_key)
            if existing is not None:
                event, started_at = existing
                if time.monotonic() - started_at <= self.config.cache_fill_ttl_seconds:
                    return False, event
                event.set()
            event = threading.Event()
            self._inflight[cache_key] = (event, time.monotonic())
            return True, event

    def complete_cache_fill(self, cache_key: str, owner_event: threading.Event | None = None) -> None:
        with self._inflight_lock:
            current = self._inflight.get(cache_key)
            if current is None:
                return
            event, _started_at = current
            if owner_event is not None and event is not owner_event:
                return
            self._inflight.pop(cache_key, None)
            event.set()


def build_cache_key(
    *,
    case_id: str,
    year: int,
    rule_ids: list[str],
    source_snapshot_id: str | None,
    prompt_version: str,
    model_id: str,
    supplement_hash: str | None,
    input_fingerprint: str | None = None,
) -> str:
    payload = {
        "case_id": case_id,
        "year": int(year),
        "rule_ids": sorted(set(rule_ids)),
        "source_snapshot_id": source_snapshot_id or "",
        "prompt_version": prompt_version,
        "model_id": model_id,
        "supplement_hash": supplement_hash or "",
        "input_fingerprint": input_fingerprint or "",
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
