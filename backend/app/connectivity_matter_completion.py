"""Presentation of recorded role execution versus completed investigation."""
from __future__ import annotations
import re

_LIMIT_TEXT = re.compile(
    r"remaining_tool_rounds\s*=\s*0|工具轮次(?:已用尽|为\s*0)|工具轮次.*用尽",
    re.IGNORECASE,
)

def effective_role_status(task):
    recorded = task.get("status", "not_run")
    reason = task.get("termination_reason")
    if reason in {"tool_round_limit", "provider_call_limit", "stop_reason_inconsistent"}:
        return "partial"
    # Old receipts must remain immutable. Derive an honest display state instead.
    if reason != "source_exhausted" and recorded in {"completed", "reused"} and _LIMIT_TEXT.search(str(task.get("stop_reason") or "")):
        return "partial"
    return recorded

def known_usage(calls):
    attempted = [c for c in calls if c.get("request_attempted")]
    def total(field):
        values = [c.get(field) for c in attempted]
        return sum(values) if values and all(isinstance(v, int) for v in values) else None
    return {field: total(field) for field in (
        "input_tokens", "output_tokens", "cache_hit_input_tokens", "cache_miss_input_tokens"
    )}
