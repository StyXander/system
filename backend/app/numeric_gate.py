"""数字主张可回查闸门 v2（创新三）。

从 Agent 最终文本与结构化 claims 中提取关键金额、比例、年份、阈值和变化值，
每个数字必须映射到确定性 metric ID、字段 evidence ID 或知识定位；
允许配置不参与财务核对的技术数字（run ID、页码、角色序号等）。
无来源数字标记 unverified_numeric_claim；关键财务数字无来源时禁止完整成功。

导出展示“原数字—规范化值—来源—计算式—验证状态”。
"""

from __future__ import annotations

import re
from typing import Any

# 数字 token 正则：支持中文千分位、小数、百分比、百分点、年份。
_NUMBER_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])([+-]?(?:"
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?"
    r"|"
    r"\d+(?:\.\d+)?"
    r"))(\s*(?:万|亿|千|百|%|％|个百分点|个点|倍)?)"
)
# 技术数字白名单前缀：这些 token 不参与财务核对。
_TECHNICAL_PREFIXES = ("RUN-", "EVAL-", "P", "S", "C", "ID", "第", "P0", "C0")

# 财务核心数字类型（用于“关键财务数字无来源禁止完整成功”）。
KEY_NUMERIC_PATTERNS = (
    ("amount", re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?(?:万|亿|千|百)?")),
    ("percentage", re.compile(r"\d+(?:\.\d+)?\s*(?:%|％)")),
    ("percentage_point", re.compile(r"\d+(?:\.\d+)?\s*个百分点")),
    ("year", re.compile(r"(?<!\d)(20\d{2})(?!\d)")),
)


def _is_technical(raw: str) -> bool:
    return any(raw.upper().startswith(prefix.upper()) for prefix in _TECHNICAL_PREFIXES)


def normalize_number(raw: str) -> float | None:
    """把带中文单位/百分号的 token 规范化成数值（亿元按亿还原为元）。"""
    text = raw.strip()
    multiplier = 1.0
    if "亿" in text:
        multiplier = 100_000_000.0
        text = text.replace("亿", "")
    elif "万" in text:
        multiplier = 10_000.0
        text = text.replace("万", "")
    elif "千" in text:
        multiplier = 1_000.0
        text = text.replace("千", "")
    elif "百" in text and "%" not in text and "％" not in text:
        multiplier = 100.0
        text = text.replace("百", "")
    is_percent = "%" in text or "％" in text
    text = text.replace(",", "").replace("%", "").replace("％", "")
    text = text.replace("个百分点", "").replace("个点", "").replace("倍", "").strip()
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    value *= multiplier
    if is_percent:
        value = value / 100.0
    return value


def extract_number_tokens(text: str) -> list[dict[str, Any]]:
    """提取文本中的数字 token，返回 原始串、规范化值、类型。"""
    tokens: list[dict[str, Any]] = []
    for match in _NUMBER_TOKEN_RE.finditer(text):
        raw = match.group(0).strip()
        if _is_technical(raw):
            continue
        value = normalize_number(raw)
        kind = "number"
        if "%" in raw or "％" in raw:
            kind = "percentage"
        elif "个百分点" in raw or "个点" in raw:
            kind = "percentage_point"
        elif re.fullmatch(r"20\d{2}", raw.replace(",", "")):
            kind = "year"
        nearby = text[max(0, match.start() - 8) : match.start()]
        sign_hint = (
            "negative"
            if any(marker in nearby for marker in ("下降", "下滑", "减少", "降低", "降", "负") )
            else "explicit"
            if raw.startswith("-")
            else "positive_or_unknown"
        )
        tokens.append({"raw": raw, "normalized": value, "kind": kind, "sign_hint": sign_hint})
    return tokens


def _metric_sources(rule_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """收集确定性 metric 值作为数字来源。"""
    sources: list[dict[str, Any]] = []
    for rule in rule_results or []:
        for key, value in (rule.get("metrics") or {}).items():
            if isinstance(value, (int, float)) and value == value:  # 排除 NaN
                sources.append(
                    {
                        "source_type": "metric",
                        "source_ref": f"{rule.get('rule_id')}.{key}",
                        "value": value,
                        "label": key,
                    }
                )
    return sources


def _evidence_sources(evidence_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for key, rows in evidence_bundle.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get("value")
            if isinstance(value, (int, float)):
                sources.append(
                    {
                        "source_type": "evidence",
                        "source_ref": str(row.get("evidence_id") or ""),
                        "value": float(value),
                        "label": str(row.get("field_label") or key),
                    }
                )
    return sources


def build_numeric_claim_trace(
    text: str,
    *,
    rule_results: list[dict[str, Any]],
    evidence_bundle: dict[str, Any],
    knowledge_trace: list[dict[str, Any]] | None = None,
    allowed_years: set[int] | list[int] | tuple[int, ...] | None = None,
    additional_sources: list[dict[str, Any]] | None = None,
    tolerance: float = 0.005,
) -> list[dict[str, Any]]:
    """构建 原数字—规范化值—来源—计算式—验证状态 轨迹。"""
    sources = _metric_sources(rule_results) + _evidence_sources(evidence_bundle) + [
        source for source in (additional_sources or []) if isinstance(source, dict)
    ]
    allowed_year_set = {int(year) for year in (allowed_years or []) if str(year).isdigit()}
    knowledge_trace = knowledge_trace or []
    trace: list[dict[str, Any]] = []
    for token in extract_number_tokens(text):
        if token["normalized"] is None:
            trace.append({**token, "source": None, "verification_status": "unparseable"})
            continue
        # 年份是当前案例的上下文边界，不要求再伪造一个财务字段来源。
        # 只有调用方明确提供的报告年度才可走此分支；其他年份仍然是未验证数字。
        if token["kind"] == "year" and int(token["normalized"]) in allowed_year_set:
            trace.append(
                {
                    **token,
                    "source": "case.reporting_years",
                    "source_type": "case_context",
                    "verification_status": "contextual",
                    "calculation": f"{token['raw']} ↔ 当前案例报告年度",
                }
            )
            continue
        best = None
        comparison_value = token["normalized"]
        if token.get("sign_hint") == "negative" and comparison_value >= 0:
            # 中文“下降 54.55%”常省略负号，按文字方向与确定性负增长指标比较。
            comparison_value = -comparison_value
        for source in sources:
            source_value = source["value"]
            if token["kind"] == "percentage":
                source_value = source_value  # metric 百分比已按小数存储
            elif token["kind"] == "percentage_point" and abs(source_value) <= 2:
                # 规则配置和确定性指标通常以小数保存，文本中的“百分点”以 100 倍展示。
                source_value = source_value * 100
            if abs(comparison_value - source_value) <= max(tolerance, abs(source_value) * tolerance):
                best = source
                break
        if best is None:
            trace.append(
                {
                    **token,
                    "source": None,
                    "verification_status": "unverified_numeric_claim",
                }
            )
        else:
            trace.append(
                {
                    **token,
                    "source": best["source_ref"],
                    "source_type": best["source_type"],
                    "verification_status": "traced",
                    "calculation": f"{token['raw']} ↔ {best['label']}={best['value']}",
                }
            )
    return trace


def validate_numeric_claims(
    text: str,
    *,
    rule_results: list[dict[str, Any]],
    evidence_bundle: dict[str, Any],
    knowledge_trace: list[dict[str, Any]] | None = None,
    allowed_years: set[int] | list[int] | tuple[int, ...] | None = None,
    additional_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """数字主张可回查校验：返回轨迹、未验证数字与关键财务数字缺失标记。"""
    trace = build_numeric_claim_trace(
        text,
        rule_results=rule_results,
        evidence_bundle=evidence_bundle,
        knowledge_trace=knowledge_trace,
        allowed_years=allowed_years,
        additional_sources=additional_sources,
    )
    unverified = [t for t in trace if t["verification_status"] == "unverified_numeric_claim"]
    key_unverified = [
        t for t in unverified if t["kind"] in {"percentage", "percentage_point", "year"} or (t["kind"] == "number" and t["normalized"] and abs(t["normalized"]) >= 1000)
    ]
    return {
        "schema_version": "numeric_claim_trace_v2",
        "trace": trace,
        "unverified_count": len(unverified),
        "key_unverified_count": len(key_unverified),
        "key_unverified": [t["raw"] for t in key_unverified],
        "passed": len(key_unverified) == 0,
        "boundary": "关键财务数字无来源时禁止完整成功；技术数字（run ID、页码、角色序号）不参与核对。",
    }
