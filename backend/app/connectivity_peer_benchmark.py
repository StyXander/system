"""同业对标：只用已授权登记的同业样本，缺登记就显式拒绝，不生成任何排名。

专业边界（必须同时成立）：
- registry 为空或未获授权时返回明确缺口，不编造同业数值、不生成排名；
- 只有 metric_identity 严格同口径且单位一致的对标才允许比较；
- 每个样本必须带来源（document/source）与期间；无来源的样本条目在加载时被剔除；
- 对标结果只说明相对位置，不构成竞争力评价或投资建议。
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .connectivity_metrics import metric_identity

VERSION = "peer_benchmark_v1"
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "connectivity_peer_sources.json"


def load_registry() -> dict:
    """读取同业样本登记表；文件缺失或损坏时按空登记处理，不抛异常。"""
    if not REGISTRY_PATH.exists():
        return {"version": "peer_sources_v1", "samples": []}
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"version": "peer_sources_v1", "samples": []}
    # 无来源或无期间的条目不能作为对标依据，加载时剔除并留痕。
    valid, rejected = [], []
    for sample in registry.get("samples", []):
        if sample.get("source") and sample.get("period"):
            valid.append(sample)
        else:
            rejected.append({"company": sample.get("company", ""),
                             "reason": "缺少来源或期间；登记不完整，不进入对标。"})
    return {**registry, "samples": valid, "rejected": rejected}


def peer_benchmark(label: str, value, unit: str, *, registry: dict | None = None, context: dict | None = None) -> dict:
    """把企业指标放进已登记且通过资格检查的同业样本。

    当前企业也必须有原件身份，不能只验证比较对象。
    年度、行业、地区、组织范围、定义、分母和可比范围逐项对齐。
    相同指标名与相同单位只构成必要条件，不能替代完整资格。
    每个样本保留拒绝原因，使空排名具有可解释的具体缺口。
    同企业同年度重复条目不增加样本数量，本企业不混入同业分母。
    非有限金额与重述后的不可比口径不能进入排序。
    有效同业样本不足时只展示资格矩阵，不输出统计相对位置。
    排序结果只适用于当前指标和已登记集合，不构成评级。
    """
    registry = registry if registry is not None else load_registry()
    samples = registry.get("samples", [])
    if not registry.get("authorized", False) or not samples:
        return {"version": VERSION, "available": False,
                "registered_samples": len(samples),
                "reason": "同业样本未登记或未获授权；不生成任何同业数值对标或排名。"}
    identity = metric_identity(label)
    if not identity["metric_id"]:
        return {"version": VERSION, "available": False,
                "reason": "指标未通过严格口径登记（metric_identity 匹配失败）；拒绝跨口径对标。"}
    context = context or {}
    dimensions = ("period", "industry", "region", "scope", "metric_definition", "denominator", "comparable_range")
    comparable, qualification = [], []
    seen = set()
    for sample in samples:
        sample_identity = metric_identity(sample.get("label", ""))
        gaps = [name for name in dimensions if not context.get(name) or not sample.get(name) or sample[name] != context[name]]
        if context.get("source_verified") is not True or not context.get("document_id") or not context.get("pdf_page"):
            gaps.append("本企业原件/页码未核验")
        if sample_identity["metric_id"] != identity["metric_id"] or str(sample.get("unit") or "") != str(unit or ""):
            gaps.append("指标/单位")
        if not sample.get("source") or not sample.get("document_id") or not sample.get("pdf_page") or sample.get("source_verified") is not True:
            gaps.append("原件/页码未核验")
        if sample.get("restated") or sample.get("definition_changed"):
            gaps.append("重述/口径变化")
        try:
            sample_value = Decimal(str(sample.get("value")))
            if not sample_value.is_finite():
                gaps.append("非有限数值")
        except (InvalidOperation, TypeError, ValueError):
            gaps.append("数值不可用")
        sample_key = (sample.get("company"), sample.get("period"))
        if sample_key in seen or sample.get("company") == context.get("company"):
            gaps.append("重复样本/本企业")
        qualification.append({"company": sample.get("company"), "period": sample.get("period"), "eligible": not gaps, "gaps": gaps})
        if gaps:
            continue
        seen.add(sample_key)
        comparable.append(sample)
    try:
        own = Decimal(str(value))
        if not own.is_finite():
            raise ValueError("非有限数值")
    except (InvalidOperation, TypeError, ValueError):
        return {"version": VERSION, "available": False, "reason": "企业数值无法转为十进制。"}
    if len(comparable) < 3:
        return {"version": VERSION, "available": False,
                "metric": identity["canonical"], "comparable_samples": len(comparable),
                "qualification": qualification,
                "reason": "同口径样本不足3个；样本过少时不生成有统计意义的相对位置。"}
    ordered = sorted([*comparable, {"company": "本企业", "value": str(own)}],
                     key=lambda item: Decimal(str(item["value"])))
    rank = ordered.index(next(item for item in ordered if item["company"] == "本企业")) + 1
    return {
        "version": VERSION,
        "available": True,
        "metric": identity["canonical"],
        "metric_id": identity["metric_id"],
        "unit": unit,
        "own_value": str(own),
        "rank": rank,
        "sample_count": len(comparable),
        "samples": [{"company": item["company"], "value": str(item["value"]),
                     "period": item.get("period", ""), "source": item.get("source", "")}
                    for item in comparable],
        "qualification": qualification,
        "limitations": [
            "对标只说明该指标在已登记样本中的相对位置，不构成竞争力评价",
            "样本口径以各来源原文为准；程序未复核各企业会计政策差异",
            "不构成投资建议或评级",
        ],
    }
