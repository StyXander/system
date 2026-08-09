"""外部模型传输前的最小化与高风险个人信息阻断。

扫描发生在任何外部模型调用之前，命中高风险模式时保持失败关闭。
本模块只识别有限的高风险格式，不声称完成全部个人信息合规审查。
居民身份证号要求完整十八位边界，避免在更长数字中截取局部号码。
手机号模式限制中国大陆号段和数字边界，普通金额不应被误报为号码。
银行卡规则只标记疑似长数字，最终性质仍需人工结合字段语义确认。
扫描结果只返回敏感类别和结构路径，绝不回显匹配到的原始文本。
结构路径帮助资料提供者定位清理位置，同时减少敏感内容二次扩散。
字典、列表和元组递归检查，其他对象不会被强制转换成可能泄密的字符串。
字典键只作为路径标签使用，键本身如含敏感内容仍需上游命名规范约束。
命中数量设有上限，恶意载荷不能制造无界的扫描结果或响应体。
达到上限后停止递归只是资源保护，不表示剩余载荷已经安全。
空值和数值类型无需正则扫描，避免格式化过程改变原始语义。
同一路径命中多个类别时分别报告，调用方不能只处理第一项就放行。
检测规则不修改原载荷，自动遮盖可能破坏证据原文和哈希对应关系。
需要脱敏时应由资料提供方生成新版本并重新确认来源与授权。
公开年报也可能包含个人信息，公开可查不能自动推导外部模型传输许可。
模型传输范围说明明确排除原始 PDF、整份运行日志和任意本机文件。
最小化证据包只包含当前规则必要字段，不能因为方便把案例目录整体发送。
扫描未命中只表示有限模式未发现问题，不构成隐私合规批准。
最终传输仍须同时满足案例授权、运行模式和真人确认等其他闸门。
本模块的目标是减少明显泄露风险，而不是替代法律或组织合规判断。
"""

from __future__ import annotations

import re
from typing import Any


HIGH_RISK_PATTERNS: dict[str, re.Pattern[str]] = {
    "居民身份证号": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    "中国大陆手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "疑似银行卡号": re.compile(r"(?<!\d)\d{16,19}(?!\d)"),
}


def scan_sensitive_payload(payload: Any, *, max_findings: int = 20) -> list[dict[str, str]]:
    """只返回类别和结构路径，不回显敏感原文或匹配片段。"""

    findings: list[dict[str, str]] = []

    def visit(value: Any, path: str) -> None:
        """递归检查结构化载荷，同时只记录字段路径和敏感类别。"""

        if len(findings) >= max_findings:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
            return
        if not isinstance(value, str):
            return
        for label, pattern in HIGH_RISK_PATTERNS.items():
            if pattern.search(value):
                findings.append({"kind": label, "path": path or "payload"})
                if len(findings) >= max_findings:
                    return

    visit(payload, "")
    return findings


def model_transmission_scope() -> str:
    """返回前后端共用的最小模型传输范围说明。"""

    return "仅传输必要字段证据、来源元数据与RAG命中片段；不上传整本PDF或本机路径。"
