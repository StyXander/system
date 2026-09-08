"""供应商调用 ID 的唯一派生实现，供在线写入与离线复核共用。

这里刻意不依赖 FastAPI 应用对象：评委复现脚本、发布门禁和在线运行必须用同一套
派生规则，否则离线重算出的调用 ID 与运行留痕不一致，就无法证明两者同源。
供应商没有稳定的公开请求编号，因此不伪造供应商 ID；每个调用 ID 只绑定
当前 run、角色、尝试序号以及该次尝试自身的输入/响应哈希。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# 64 位十六进制才是合法 SHA-256；截断值或其他占位串一律视为缺证据。
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def derive_provider_call_ids(steps: list[Any], run_id: str) -> list[str]:
    """从每次真实尝试的脱敏哈希派生稳定调用 ID，便于 B3 证据逐项回查。

    缺少任一哈希时不生成该尝试的 ID，让正式 B3 门禁保持失败关闭，而不是用
    调用次数补齐留痕。调用次数与逐次尝试记录必须一一对应；多余或缺失记录都
    不能被截断或补齐，否则会把另一尝试的哈希误当成本次调用证据。
    """

    identifiers: list[str] = []
    for step in steps:
        if not step.provider_call_performed:
            continue
        count = int(step.provider_call_count or 0)
        if count < 1:
            return []
        history = list(step.model_attempt_history or [])
        if len(history) != count:
            return []
        for offset, attempt in enumerate(history[:count], start=1):
            if not isinstance(attempt, dict):
                return []
            # 哈希必须来自当前尝试本身。角色级字段是兼容旧响应的汇总字段，
            # 不能为超时、网络失败或其他没有响应的尝试填充伪证据。
            input_hash_value = attempt.get("input_sha256")
            response_hash_value = attempt.get("response_sha256")
            if not isinstance(input_hash_value, str) or not isinstance(response_hash_value, str):
                return []
            input_hash = input_hash_value.strip()
            response_hash = response_hash_value.strip()
            if not _SHA256_PATTERN.fullmatch(input_hash) or not _SHA256_PATTERN.fullmatch(response_hash):
                return []
            material = f"{run_id}|{step.role}|{offset}|{input_hash}|{response_hash}"
            identifiers.append(f"CALL-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:32].upper()}")
    return identifiers
