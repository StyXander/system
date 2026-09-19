"""数字主张可回查闸门 v3（创新三）。

从 Agent 最终文本与结构化 claims 中提取关键金额、比例、年份、阈值和变化值，
每个数字必须映射到确定性 metric ID、字段 evidence ID 或知识定位；
允许配置不参与财务核对的技术数字（run ID、页码、角色序号等）。
无来源数字标记 unverified_numeric_claim；关键财务数字无来源时禁止完整成功。

v3 起支持 claim-aware 校验：调用方按主张分段传入 (text, evidence_ids) 后，
每段文本只能使用「该段自己绑定的 evidence_id」所对应的年报原文片段作为来源池。
未被该主张绑定的片段即使含有同一数字，也仍然是未验证数字。
严禁把所有 RAG 片段数字并入全局白名单，那等于拆掉本闸门。
结构化 field/metric value 与配置阈值仍是全局可用来源，旧调用口径不变。

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
    """识别工程性数字（页码、附注号、比例分母等），这类数字不参与可追溯校验，避免误杀。"""
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
    """汇总证据包中全部可绑定来源；只有登记 evidence_id 的年报原文片段进入追溯范围（D4）。"""
    """汇总证据包中全部可绑定来源；只有登记了 evidence_id 的年报原文片段才进入追溯范围（D4）。"""
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


# RAG 原文片段行里真正承载年报文字的字段；按优先级取第一个非空字符串。
_RAG_TEXT_FIELDS = ("excerpt", "raw_excerpt", "content", "text")


def _rag_chunk_sources(
    evidence_bundle: dict[str, Any],
    allowed_evidence_ids: list[str] | set[str] | tuple[str, ...] | None,
) -> list[dict[str, Any]]:
    """只从「本段主张已绑定 evidence_id」的年报原文片段中抽取数字。

    rag_evidence 行的 value 恒为 None，财务数字只存在于原文摘录里；
    因此必须按 evidence_id 白名单逐段取数，不能整包并入全局来源。
    """
    allowed = {str(item) for item in (allowed_evidence_ids or []) if str(item)}
    if not allowed:
        return []
    rows = evidence_bundle.get("rag_evidence")
    if not isinstance(rows, list):
        return []
    sources: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidence_id") or "")
        # 未被本段主张绑定的片段一律跳过：这是 D4 收紧条件 2 的唯一执行点。
        if not evidence_id or evidence_id not in allowed:
            continue
        chunk_text = next(
            (str(row[field]) for field in _RAG_TEXT_FIELDS if isinstance(row.get(field), str) and row.get(field)),
            "",
        )
        if not chunk_text:
            continue
        page = row.get("pdf_page")
        label = f"年报原文第 {page} 页片段" if str(page or "").isdigit() else "年报原文片段"
        for token in extract_number_tokens(chunk_text):
            if token["normalized"] is None:
                continue
            sources.append(
                {
                    "source_type": "rag_chunk",
                    "source_ref": evidence_id,
                    "value": float(token["normalized"]),
                    "label": label,
                }
            )
    return sources


def _trace_segment(
    text: str,
    *,
    sources: list[dict[str, Any]],
    allowed_year_set: set[int],
    tolerance: float,
) -> list[dict[str, Any]]:
    """把一段 AI 文本中的数字逐个对来源做可追溯匹配，返回命中与未命中清单。
    
    匹配只接受数值等价（含金额单位换算后的等价），不接受四舍五入近似；
    找不到来源的数字原样保留进 key_unverified，绝不静默丢弃。
    """
    """对单段文本逐 token 溯源；来源池由调用方按主张绑定关系给定。"""
    # 年份只接受「当前案例已登记报告年度」作为上下文，其余年份数字一律按未验证处理；
    # 金额等价判断允许单位换算（元/万元/亿元），但不允许四舍五入近似冒充命中。
    trace: list[dict[str, Any]] = []
    for token in extract_number_tokens(text):
        if token["normalized"] is None:
            trace.append({**token, "source": None, "bound_by_claim": False, "verification_status": "unparseable"})
            continue
        # 年份是当前案例的上下文边界，不要求再伪造一个财务字段来源。
        # 只有调用方明确提供的报告年度才可走此分支；其他年份仍然是未验证数字。
        if token["kind"] == "year" and int(token["normalized"]) in allowed_year_set:
            trace.append(
                {
                    **token,
                    "source": "case.reporting_years",
                    "source_type": "case_context",
                    "bound_by_claim": False,
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
                    "bound_by_claim": False,
                    "verification_status": "unverified_numeric_claim",
                }
            )
        else:
            trace.append(
                {
                    **token,
                    "source": best["source_ref"],
                    "source_type": best["source_type"],
                    # 只有来自本段主张自行绑定的年报原文片段，才算“主张内可回查”。
                    "bound_by_claim": best["source_type"] == "rag_chunk",
                    "verification_status": "traced",
                    "calculation": f"{token['raw']} ↔ {best['label']}={best['value']}",
                }
            )
    return trace


def build_numeric_claim_trace(
    text: str,
    *,
    rule_results: list[dict[str, Any]],
    evidence_bundle: dict[str, Any],
    knowledge_trace: list[dict[str, Any]] | None = None,
    allowed_years: set[int] | list[int] | tuple[int, ...] | None = None,
    additional_sources: list[dict[str, Any]] | None = None,
    claim_evidence_bindings: list[dict[str, Any]] | None = None,
    tolerance: float = 0.005,
) -> list[dict[str, Any]]:
    """数字闸门主入口：对 AI 草稿中的关键财务数字逐条建立可追溯记录。
    
    W01 起改为 claim-aware：只校验「claim 已绑定 evidence_id 的年报原文片段数字」
    范围外的自称关键数字（队长签字 D4）。passed=false 时运行不得按完整链展示，
    前端与导出都必须保留未通过数字清单，不得改写为成功。
    """
    """构建 原数字—规范化值—来源—计算式—验证状态 轨迹。

    未传 claim_evidence_bindings 时保持旧口径：整段 text 只用全局结构化来源，
    RAG 原文数字一律不进入白名单。传入后改为逐主张分段，每段额外允许
    该段自行绑定的 RAG 片段来源；来源池比整段校验更小，而不是更大。
    """
    sources = _metric_sources(rule_results) + _evidence_sources(evidence_bundle) + [
        source for source in (additional_sources or []) if isinstance(source, dict)
    ]
    allowed_year_set = {int(year) for year in (allowed_years or []) if str(year).isdigit()}
    knowledge_trace = knowledge_trace or []
    bindings = [
        binding
        for binding in (claim_evidence_bindings or [])
        if isinstance(binding, dict) and str(binding.get("text") or "")
    ]
    if not bindings:
        return _trace_segment(
            text,
            sources=sources,
            allowed_year_set=allowed_year_set,
            tolerance=tolerance,
        )
    trace: list[dict[str, Any]] = []
    for binding in bindings:
        segment_sources = sources + _rag_chunk_sources(evidence_bundle, binding.get("evidence_ids"))
        trace.extend(
            _trace_segment(
                str(binding.get("text") or ""),
                sources=segment_sources,
                allowed_year_set=allowed_year_set,
                tolerance=tolerance,
            )
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
    claim_evidence_bindings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """数字主张可回查校验：返回轨迹、未验证数字与关键财务数字缺失标记。

    传入 claim_evidence_bindings 时以分段文本为准，text 参数不再参与校验；
    关键财务数字无来源仍然 fail-closed，不因为扩展了原文来源而放宽判定。
    """
    trace = build_numeric_claim_trace(
        text,
        rule_results=rule_results,
        evidence_bundle=evidence_bundle,
        knowledge_trace=knowledge_trace,
        allowed_years=allowed_years,
        additional_sources=additional_sources,
        claim_evidence_bindings=claim_evidence_bindings,
    )
    bindings = [
        binding
        for binding in (claim_evidence_bindings or [])
        if isinstance(binding, dict) and str(binding.get("text") or "")
    ]
    unverified = [t for t in trace if t["verification_status"] == "unverified_numeric_claim"]
    key_unverified = [
        t for t in unverified if t["kind"] in {"percentage", "percentage_point", "year"} or (t["kind"] == "number" and t["normalized"] and abs(t["normalized"]) >= 1000)
    ]
    return {
        "schema_version": "numeric_claim_trace_v3",
        # 记录本次校验口径，便于区分历史 v2 整段结果与 claim-aware 结果。
        "validation_mode": "claim_scoped" if bindings else "global_structured",
        "validated_segment_count": len(bindings) if bindings else 1,
        "trace": trace,
        "unverified_count": len(unverified),
        "key_unverified_count": len(key_unverified),
        "key_unverified": [t["raw"] for t in key_unverified],
        "passed": len(key_unverified) == 0,
        "boundary": (
            "关键财务数字无来源时禁止完整成功；技术数字（run ID、页码、角色序号）不参与核对。"
            "按主张分段校验时，年报原文数字只在当前主张确实绑定该 evidence_id 的前提下才算来源。"
        ),
    }
