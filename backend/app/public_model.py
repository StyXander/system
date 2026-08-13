"""公开竞赛模式的模型额度、并发租约和结果缓存。

公开演示不依赖登录，但模型调用仍必须有可追溯的预算边界。
本地开发使用 SQLite；部署到 Supabase 时，调用方可以把同样的记录
迁移到服务端表，浏览器永远不会接触模型密钥或额度流水。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
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
        )


class PublicModelQuotaError(RuntimeError):
    """公开模型额度或并发租约不可用。"""

    code = "PUBLIC_MODEL_QUOTA_EXCEEDED"


class PublicModelLedger:
    """可测试的原子额度账本；运行结果只保存结构化缓存，不保存密钥。"""

    def __init__(self, workspace_root: Path, *, config: QuotaConfig | None = None) -> None:
        self.root = Path(workspace_root)
        self.config = config or QuotaConfig.from_env()
        self.path = self.root / "backend" / "runtime" / "public_model_ledger.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._inflight_lock = threading.Lock()
        self._inflight: dict[str, threading.Event] = {}
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
            recent_ip = connection.execute(
                "select count(*) from model_usage where ip_hash=? and reserved_at>=? and released=0",
                (ip_hash, now - self.config.window_seconds),
            ).fetchone()[0]
            recent_global = connection.execute(
                "select count(*) from model_usage where reserved_at>=? and released=0",
                (now - self.config.window_seconds,),
            ).fetchone()[0]
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
                return False, existing
            event = threading.Event()
            self._inflight[cache_key] = event
            return True, event

    def complete_cache_fill(self, cache_key: str) -> None:
        with self._inflight_lock:
            event = self._inflight.pop(cache_key, None)
            if event is not None:
                event.set()


def build_cache_key(*, case_id: str, year: int, rule_ids: list[str], source_snapshot_id: str | None, prompt_version: str, model_id: str, supplement_hash: str | None) -> str:
    payload = {
        "case_id": case_id,
        "year": int(year),
        "rule_ids": sorted(set(rule_ids)),
        "source_snapshot_id": source_snapshot_id or "",
        "prompt_version": prompt_version,
        "model_id": model_id,
        "supplement_hash": supplement_hash or "",
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
