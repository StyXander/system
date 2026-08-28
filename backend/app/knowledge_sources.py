"""多源审计知识库：统一来源 Schema、四层目录与台账校验。

数据分层（G3-1）：
- case_evidence：企业年报、监管处罚决定、交易所问询函、案例补充资料；
- authoritative_rules：会计准则、审计准则、税收法规；
- industry_context：行业指标、研报、新闻、宏观指标；
- source_ledger：所有资料的来源、版本、哈希、许可与截止日期台账。

边界：
- 未核对官方列表数量的类别只能登记 coverage_status=representative；
- COMPETITION_DATA_CUTOFF_DATE 未确认时所有条目保持 validation_status=pending
  且整体视为草案，不得声称“截至比赛公告日完整”；
- 新闻/研报不覆盖权威规则；单案例证据不得进入其他案例检索空间；
- 同一文档版本变化时生成新版本号，不覆盖旧哈希。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_SCHEMA_VERSION = "knowledge_source_v1"
MANIFEST_SCHEMA_VERSION = "knowledge_sources_manifest_v1"

SOURCE_CATEGORIES = (
    "annual_report",
    "csrc_penalty",
    "exchange_inquiry",
    "accounting_standard",
    "auditing_standard",
    "tax_regulation",
    "industry_report",
    "news",
    "macro_indicator",
)

LAYER_BY_CATEGORY = {
    "annual_report": "case_evidence",
    "csrc_penalty": "case_evidence",
    "exchange_inquiry": "case_evidence",
    "accounting_standard": "authoritative_rules",
    "auditing_standard": "authoritative_rules",
    "tax_regulation": "authoritative_rules",
    "industry_report": "industry_context",
    "news": "industry_context",
    "macro_indicator": "industry_context",
}

# 必须存在的必填字段；其余字段可缺省为 null，但必须出现在输出结构中。
REQUIRED_SOURCE_FIELDS = (
    "source_id",
    "source_category",
    "publisher",
    "title",
    "official_url",
    "published_at",
    "retrieved_at",
    "document_id",
    "sha256",
    "coverage_status",
    "validation_status",
)

DEFAULT_SOURCE_FIELDS = {
    "effective_from": None,
    "effective_to": None,
    "ticker": None,
    "company_name": None,
    "industry_tags": [],
    "page_count": None,
    "license_or_compliance_note": None,
    "competition_cutoff_date": None,
    # 最小检索片段只保存可展示、可回查的必要内容，不把整篇受版权保护的材料
    # 复制进 Git 或发送给模型。正文仍以 official_url 指向的官方原文为准。
    "retrieval_excerpt": None,
    "retrieval_locator": None,
    "excerpt_sha256": None,
    "query_terms": [],
}

# 官方站点域名后缀白名单：来源必须来自权威域名，拒绝镜像站与文库。
OFFICIAL_HOST_SUFFIXES = (
    "csrc.gov.cn",
    "sse.com.cn",
    "szse.cn",
    "cninfo.com.cn",
    "mof.gov.cn",
    "cicpa.org.cn",
    "chinatax.gov.cn",
    "stats.gov.cn",
    "miit.gov.cn",
)

_COMPETITION_CUTOFF_DATE_ENV_NAME = "COMPETITION_DATA_CUTOFF_DATE"
_KNOWLEDGE_SNAPSHOT_ID_ENV_NAME = "KNOWLEDGE_SNAPSHOT_ID"
# 用户确认的本轮竞赛演示冻结日。环境变量可显式覆盖，便于正式公告日更新后
# 重新构建快照；未配置时不再回退为“未知草案”。
DEFAULT_COMPETITION_CUTOFF_DATE = "2026-08-24"
FIVE_YEAR_WINDOW_CATEGORIES = {"csrc_penalty", "exchange_inquiry"}


def knowledge_cutoff_date() -> str | None:
    """返回确认的竞赛数据截止日；仅接受 ISO 日期，缺省使用项目冻结日。"""
    value = os.getenv(_COMPETITION_CUTOFF_DATE_ENV_NAME, DEFAULT_COMPETITION_CUTOFF_DATE).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def knowledge_snapshot_id() -> str:
    """返回知识库快照 ID；未配置时使用本轮冻结的代表性语料快照。"""
    value = os.getenv(_KNOWLEDGE_SNAPSHOT_ID_ENV_NAME, "").strip()
    return value or "KNOWLEDGE-20260824-REPRESENTATIVE-V1"


def source_layer(category: str) -> str:
    """把来源类别映射到四层目录；未知类别归入 case_evidence 并留底。"""
    return LAYER_BY_CATEGORY.get(category, "case_evidence")


def normalize_source_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """把原始来源条目规范化为统一 Schema；缺字段补 null，非法字段置失败。"""
    entry = {field: raw.get(field) for field in REQUIRED_SOURCE_FIELDS}
    for field, default in DEFAULT_SOURCE_FIELDS.items():
        entry[field] = raw.get(field, default)
    source_id = str(entry.get("source_id") or "").strip()
    category = str(entry.get("source_category") or "").strip()
    if not source_id:
        source_id = "SRC-" + hashlib.sha256(
            json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12].upper()
    entry["source_id"] = source_id
    entry["source_category"] = category
    entry["validation_errors"] = []
    if category not in SOURCE_CATEGORIES:
        entry["validation_status"] = "failed"
        entry["validation_errors"].append("source_category_invalid")
    missing = [
        field for field in REQUIRED_SOURCE_FIELDS
        if field not in {"source_id", "validation_status"} and not entry.get(field)
    ]
    if missing:
        entry["validation_status"] = "failed"
        entry["validation_errors"].extend(f"missing_{field}" for field in missing)
    if entry.get("coverage_status") not in {"representative", "complete"}:
        entry["coverage_status"] = "representative"
    if entry.get("validation_status") not in {"pending", "passed", "failed"}:
        entry["validation_status"] = "pending"
    if not entry.get("retrieved_at"):
        entry["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    entry["layer"] = source_layer(category)
    return entry


def load_source_manifest(path: Path | str) -> tuple[list[dict[str, Any]], str | None]:
    """读取并规范化知识库来源清单；返回 (entries, 阻断原因码)。"""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        return [], "knowledge_manifest_missing"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], "knowledge_manifest_invalid"
    if not isinstance(payload, dict) or payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        return [], "knowledge_manifest_schema_mismatch"
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        return [], "knowledge_manifest_sources_missing"
    entries = [normalize_source_entry(item) for item in raw_sources if isinstance(item, dict)]
    return entries, None


def cutoff_window_years(anchor_date: str | None, years: int = 5) -> tuple[str, str] | None:
    """按确认的截止日向前计算“近五年”窗口；未确认时返回 None。"""
    if not anchor_date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", anchor_date):
        return None
    try:
        anchor = date.fromisoformat(anchor_date)
    except ValueError:
        return None
    try:
        start = anchor.replace(year=anchor.year - years)
    except ValueError:
        # 2 月 29 日向前推到非闰年时按 2 月 28 日处理。
        start = anchor.replace(year=anchor.year - years, month=2, day=28)
    return start.isoformat(), anchor.isoformat()


def source_is_active(entry: dict[str, Any], cutoff_date: str | None) -> bool:
    """判断来源是否能进入当前快照和检索空间，绝不以未来或过期条目补覆盖。"""
    if not cutoff_date:
        return False
    published_at = str(entry.get("published_at") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published_at):
        return False
    try:
        published = date.fromisoformat(published_at)
        cutoff = date.fromisoformat(cutoff_date)
    except ValueError:
        return False
    if published > cutoff or str(entry.get("validation_status") or "") == "failed":
        return False
    category = str(entry.get("source_category") or "")
    if category in FIVE_YEAR_WINDOW_CATEGORIES:
        window = cutoff_window_years(cutoff_date)
        if window is None:
            return False
        return published >= date.fromisoformat(window[0])
    return True


def active_source_entries(entries: list[dict[str, Any]], cutoff_date: str | None) -> list[dict[str, Any]]:
    """返回可进入当前运行的来源，保留清单中未激活资料供审计追溯。"""
    return [entry for entry in entries if source_is_active(entry, cutoff_date)]


def filter_by_cutoff(entries: list[dict[str, Any]], cutoff_date: str | None) -> list[dict[str, Any]]:
    """按当前活跃窗口过滤来源；处罚和问询还须满足精确近五年范围。"""
    return active_source_entries(entries, cutoff_date)


def coverage_group_summary(entries: list[dict[str, Any]], cutoff_date: str | None) -> dict[str, Any]:
    """按类别汇总活跃文档和核验状态；未经官方目录核对一律 representative。"""
    counts: dict[str, int] = {}
    verified: dict[str, int] = {}
    active_entries = active_source_entries(entries, cutoff_date)
    # 未确认截止日时，覆盖摘要仍可展示登记草案，供项目人员补齐；但这些条目
    # 不会进入 retrieve_knowledge，也不会被当前运行导出为活跃命中。
    summary_entries = entries if cutoff_date is None else active_entries
    for entry in summary_entries:
        category = str(entry.get("source_category") or "")
        counts[category] = counts.get(category, 0) + 1
        if str(entry.get("validation_status") or "") == "passed":
            verified[category] = verified.get(category, 0) + 1
    categories = {}
    for category in SOURCE_CATEGORIES:
        count = counts.get(category, 0)
        verified_count = verified.get(category, 0)
        categories[category] = {
            "document_count": count,
            "verified_count": verified_count,
            "coverage_status": "representative",
            "validation_status": (
                "passed" if count and verified_count == count
                else "pending" if count else "missing"
            ),
        }
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "total_sources": len(entries),
        "active_source_count": len(active_entries),
        "archived_source_count": len(entries) - len(active_entries),
        "verified_sources": sum(verified.values()),
        "cutoff_date": cutoff_date,
        "snapshot_id": knowledge_snapshot_id(),
        "draft_mode": cutoff_date is None,
        "last_checked_at": max(
            (str(entry.get("retrieved_at") or "") for entry in summary_entries),
            default=None,
        ),
        "categories": categories,
        "boundary": (
            "知识库截止日尚未确认：全部类别按草案处理，不声称截至比赛公告日完整。"
            if cutoff_date is None
            else f"截至 {cutoff_date} 的活跃登记来源；处罚与问询按精确近五年窗口过滤，未经官方列表数量核对，覆盖状态仍为 representative。"
        ),
    }
