"""R1 v0.4 项目队长专业口径签字记录的只读加载与状态解析。

签字记录由项目队长于 2026-08-25 明确授权生成，位于
outputs/professional-signoff/。本模块只读取与校验，不写入、不覆盖。

状态取值：
- captain_approved_for_competition_demo：记录存在、结构合法、哈希一致、
  且当前 R1 配置（规则版本、阈值、认定映射、口径常量）与签字完全一致；
- signoff_stale_requires_reapproval：记录缺失、结构非法、哈希不一致，
  或当前 R1 配置/源文件已变化，需要项目队长重新确认；
- no_signoff_record：未找到签字记录。

本状态只表示“竞赛演示口径已由项目队长批准”，禁止表述为
注册会计师专业标准批准或会计师事务所正式审计方法。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .schemas import RunRequest

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
# 发布运行时不能依赖 Render 构建包中通常被忽略的 outputs/；优先读取受 Git
# 跟踪的最小字节副本。旧 outputs 路径只作为本地历史兼容回退，不覆盖或重写。
SIGNOFF_DIR = WORKSPACE_ROOT / "outputs" / "professional-signoff"
TRACKED_SIGNOFF_FILE = WORKSPACE_ROOT / "backend" / "release_records" / "r1_signoff_20260825_r2.json"
SIGNOFF_FILE = TRACKED_SIGNOFF_FILE if TRACKED_SIGNOFF_FILE.is_file() else SIGNOFF_DIR / "R1-v0.4-captain-signoff-20260825-r2.json"

SIGNOFF_RECORD_STATUS = "captain_approved_for_competition_demo"
SIGNOFF_STALE_STATUS = "signoff_stale_requires_reapproval"
SIGNOFF_MISSING_STATUS = "no_signoff_record"

# R1 口径常量单一事实来源：与签字记录 rule_config_canonical 保持一致。
R1_MINIMUM_YEARS = 2
R1_PRIMARY_RECEIVABLE_BASIS = "gross"
R1_THREE_YEAR_TREND_OPTIONAL = True
R1_ASSERTION_MAPPING = {
    "revenue": ["发生", "截止", "准确性"],
    "accounts_receivable": ["存在", "计价和分摊"],
}

SIGNOFF_BOUNDARY = (
    "签字仅用于竞赛演示的专业筛查口径；不是会计师事务所正式审计方法，"
    "也不是审计准则，不构成审计结论或审计意见。"
)


def _sha256_utf8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_rule_version() -> str:
    """从工程 R1 版本常量解析语义版本号，避免在两个文件里散落同一字符串。"""
    from .main import R1_VERSION

    match = re.match(r"^r1_v(?P<version>\d+\.\d+)-draft$", R1_VERSION)
    return match.group("version") if match else "0.4"


def current_r1_config() -> dict[str, Any]:
    """读取当前代码中的 R1 默认配置，作为与签字配置逐项比对的唯一口径。"""
    defaults = RunRequest.model_fields
    return {
        "rule_id": "R1",
        "rule_version": current_rule_version(),
        "r1_gap_threshold": float(defaults["r1_gap_threshold"].default),
        "r1_strong_gap_threshold": float(defaults["r1_strong_gap_threshold"].default),
        "r1_absolute_threshold": float(defaults["r1_absolute_threshold"].default),
        "minimum_years": R1_MINIMUM_YEARS,
        "primary_receivable_basis": R1_PRIMARY_RECEIVABLE_BASIS,
        "three_year_trend_optional": R1_THREE_YEAR_TREND_OPTIONAL,
    }


def current_r1_config_canonical() -> str:
    # 紧凑分隔符与签字记录 rule_config_canonical 的生成方式保持一致，
    # 保证规范串按字节可复算比较。
    return json.dumps(
        current_r1_config(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def load_signoff_status() -> dict[str, Any]:
    """加载并校验签字记录，返回统一只读状态与原因。

    页面、API、结构化导出统一读取本函数结果，不另行散落硬编码状态。
    """
    result: dict[str, Any] = {
        "signoff_status": SIGNOFF_MISSING_STATUS,
        "rule_id": "R1",
        "rule_version": current_rule_version(),
        "signed_by_role": None,
        "signed_at": None,
        "scope": None,
        "signoff_id": None,
        "approved_thresholds": None,
        "approved_assertion_mapping": None,
        "boundary": SIGNOFF_BOUNDARY,
        "reason": None,
    }
    if not SIGNOFF_FILE.is_file():
        result["reason"] = "未找到 R1 项目队长签字记录，需先由项目队长确认口径。"
        return result
    try:
        record = json.loads(SIGNOFF_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        result["signoff_status"] = SIGNOFF_STALE_STATUS
        result["reason"] = "签字记录文件无法解析，视为失效。"
        return result
    if not isinstance(record, dict):
        result["signoff_status"] = SIGNOFF_STALE_STATUS
        result["reason"] = "签字记录结构非法，视为失效。"
        return result

    required = (
        "signoff_id",
        "rule_id",
        "rule_version",
        "signed_by_role",
        "signed_at",
        "status",
        "rule_config_canonical",
        "rule_config_sha256",
        "signed_payload_canonical",
        "signoff_record_sha256",
    )
    if any(record.get(key) is None for key in required):
        result["signoff_status"] = SIGNOFF_STALE_STATUS
        result["reason"] = "签字记录缺少必要字段，视为失效。"
        return result

    result.update(
        {
            "signoff_id": record["signoff_id"],
            "signed_by_role": record["signed_by_role"],
            "signed_at": record["signed_at"],
            "scope": record.get("scope"),
        }
    )

    # 记录自身防篡改：载荷规范串哈希必须与记录值一致。
    if _sha256_utf8(record["signed_payload_canonical"]) != record["signoff_record_sha256"]:
        result["signoff_status"] = SIGNOFF_STALE_STATUS
        result["reason"] = "签字载荷哈希不一致，记录可能被改写，视为失效。"
        return result
    if _sha256_utf8(record["rule_config_canonical"]) != record["rule_config_sha256"]:
        result["signoff_status"] = SIGNOFF_STALE_STATUS
        result["reason"] = "规则配置哈希不一致，视为失效。"
        return result

    # 当前 R1 配置与签字配置完全一致才保持批准。
    if current_r1_config_canonical() != record["rule_config_canonical"]:
        result["signoff_status"] = SIGNOFF_STALE_STATUS
        result["reason"] = "当前 R1 配置与签字配置不一致，需要项目队长重新确认。"
        return result

    # 记录 R1 配置定义所在源文件；任一文件变化即视为口径可能变化。
    for relative_path, recorded_hash in (record.get("source_file_sha256") or {}).items():
        source_path = WORKSPACE_ROOT / relative_path
        if not source_path.is_file() or _sha256_file(source_path) != recorded_hash:
            result["signoff_status"] = SIGNOFF_STALE_STATUS
            result["reason"] = f"R1 源文件 {relative_path} 已变化，需要项目队长重新确认。"
            return result

    if record.get("status") != SIGNOFF_RECORD_STATUS:
        result["signoff_status"] = SIGNOFF_STALE_STATUS
        result["reason"] = "签字记录状态不是已批准，视为失效。"
        return result

    result["signoff_status"] = SIGNOFF_RECORD_STATUS
    result["approved_thresholds"] = record.get("approved_thresholds")
    result["approved_assertion_mapping"] = record.get("approved_assertion_mapping")
    result["reason"] = "当前 R1 配置与项目队长 2026-08-25 签字一致，可用于竞赛演示口径。"
    return result
