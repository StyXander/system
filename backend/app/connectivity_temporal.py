"""跨年度比较：只有同企业往年报告已登记且原件可用时才开放，否则显式缺口。

专业边界（必须同时成立）：
- 未登记往年报告时返回明确缺口，不推定"同比改善/恶化"，也不伪造往年数值；
- 两侧指标必须通过 metric_identity 严格配对（同口径、同单位），单位不同拒绝换算比较；
- 比较结果只覆盖该指标本身，不外推到企业整体表现；
- 每一侧都必须带 document_id 与 pdf_page，缺页码的结果不得作为证据。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .connectivity_metrics import metric_identity

VERSION = "connectivity_temporal_v1"


def temporal_status(run, root=None) -> dict:
    """本次运行登记了哪些报告期间；少于两个期间则跨年比较不可用。"""
    periods = sorted({(doc.report_period or doc.period, doc.company)
                      for doc in getattr(run, "documents", [])})
    companies = {company for _, company in periods}
    unique_periods = sorted({period for period, _ in periods})
    available = len(unique_periods) >= 2 and len(companies) == 1
    registered_eligible = available
    source_verified = False
    if available and root is not None:
        from .connectivity_extraction import source_path
        import hashlib
        source_verified = all(source_path(root, doc).is_file() and
            hashlib.sha256(source_path(root, doc).read_bytes()).hexdigest() == doc.file_sha256
            for doc in run.documents)
    available = available and source_verified
    return {
        "version": VERSION,
        "available": available,
        "registered_eligible": registered_eligible,
        "source_verified": source_verified,
        "registered_periods": unique_periods,
        "companies": sorted(companies),
        "reason": "" if available else ("跨年原件尚未核验或不可读取；不开放数值比较。" if registered_eligible else
        "本次运行未登记同企业其他年度报告；跨年比较不可自动执行，需先登记往年原件。"),
    }


def _decimal(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def compare_periods(current: dict, prior: dict) -> dict:
    """对同一指标的两个已登记期间值做确定性比较；两侧证据身份必须完整。

    输入同时包含指标、数值、单位、文件编号、页码和年度。
    比较身份还须声明公司、组织范围、指标定义、分母和可比范围。
    同一年度的两个数不能包装成跨年增长率。
    当前年度必须晚于基期，不自动猜测输入顺序。
    重述或口径变化先阻断直接比较，不能靠加免责声明放行。
    原件核验身份必须由上游登记流程提供，不能从页码存在反推。
    缺少必要身份时返回资格矩阵，不编造可比结论。
    有效计算仍只描述该指标，不能外推为公司整体表现。
    """
    for side, item in (("current", current), ("prior", prior)):
        if not item.get("document_id") or not item.get("pdf_page"):
            return {"version": VERSION, "available": False,
                    "reason": f"{side} 侧缺少 document_id 或 pdf_page；没有页码的比较不作为证据。"}
    current_identity = metric_identity(current.get("label", ""))
    prior_identity = metric_identity(prior.get("label", ""))
    if not current_identity["metric_id"] or current_identity["metric_id"] != prior_identity["metric_id"]:
        return {"version": VERSION, "available": False,
                "reason": "两侧指标未通过严格口径配对（metric_identity 不一致）；拒绝跨口径同比。"}
    if str(current.get("unit") or "") != str(prior.get("unit") or ""):
        return {"version": VERSION, "available": False,
                "reason": f"单位不一致（{current.get('unit')} vs {prior.get('unit')}）；程序不做单位换算比较。"}
    # 同年不同数值不是同比；重述和合并范围变化必须先取得可比重编依据。
    import re
    years = [str(item.get("period", "")) for item in (current, prior)]
    if not all(re.fullmatch(r"20\d{2}", year) for year in years) or int(years[0]) <= int(years[1]):
        return {"version": VERSION, "available": False, "reason": "比较期间必须为明确的前后年度，当前年须晚于基期。"}
    dimensions = ("company", "scope", "metric_definition", "denominator", "comparable_range")
    gaps = [name for name in dimensions if not current.get(name) or not prior.get(name) or current[name] != prior[name]]
    if gaps or any(item.get("restated") or item.get("definition_changed") for item in (current, prior)):
        return {"version": VERSION, "available": False, "reason": "跨年可比前提缺失或冲突：" + "、".join(gaps or ["重述/口径变化"]),
                "qualification": {name: {"current": current.get(name), "prior": prior.get(name)} for name in dimensions}}
    if not all(item.get("source_verified") is True for item in (current, prior)):
        return {"version": VERSION, "available": False, "reason": "两侧原件及页码尚未核验，不开放同比。"}
    current_value = _decimal(current.get("value"))
    prior_value = _decimal(prior.get("value"))
    if current_value is None or prior_value is None:
        return {"version": VERSION, "available": False, "reason": "数值无法转为十进制。"}
    if prior_value == 0:
        return {"version": VERSION, "available": False, "reason": "往年基数为0；同比比例无定义。"}
    difference = current_value - prior_value
    percent_change = difference / abs(prior_value) * Decimal(100)
    direction = "上升" if difference > 0 else ("下降" if difference < 0 else "持平")
    return {
        "version": VERSION,
        "available": True,
        "metric": current_identity["canonical"] or current.get("label", ""),
        "metric_id": current_identity["metric_id"],
        "unit": current.get("unit"),
        "current": {"period": current.get("period", ""), "value": str(current_value),
                    "document_id": current["document_id"], "pdf_page": current["pdf_page"]},
        "prior": {"period": prior.get("period", ""), "value": str(prior_value),
                  "document_id": prior["document_id"], "pdf_page": prior["pdf_page"]},
        "difference": str(difference),
        "percent_change": f"{percent_change:.4f}%",
        "direction": direction,
        "limitations": [
            "比较只覆盖该指标本身，不外推到企业整体表现",
            "两侧期间口径须与报告披露一致；程序未核对会计政策变更",
            "方向词只描述数值变化，不构成业绩评价或预测",
        ],
    }


def comparison_summary(root, run) -> dict:
    """展示登记资格和行业覆盖，缺少逐项依据时返回缺口矩阵。

    公司和期间来自登记原件元数据，不由模型补出。
    缓存文件数量只说明本机来源覆盖，不表示行业模型效果。
    跨年原件可读之后仍须通过逐指标的可比性检查。
    同业样本未满足完整身份时保留拒绝排名的明确说明。
    界面与导出消费同一份矩阵，避免各写一套样本数量。
    """
    from types import SimpleNamespace
    from .connectivity_extraction import load_registry, source_path
    from .connectivity_financial_bridge import industry_for, INDUSTRY_PROFILES
    from .connectivity_peer_benchmark import load_registry as peer_sources
    documents = load_registry(root)
    grouped = {}
    for doc in documents:
        industry = industry_for(doc.company)
        key = (doc.company, doc.period)
        row = grouped.setdefault(key, {"company": doc.company, "period": doc.period,
            "industry": INDUSTRY_PROFILES[industry]["name"], "documents": [], "cached_documents": 0})
        row["documents"].append({"document_id": doc.document_id, "report_type": doc.report_type,
                                 "source_url": doc.source_url, "source_sha256": doc.file_sha256})
        row["cached_documents"] += int(source_path(root, doc).is_file())
    temporal = temporal_status(SimpleNamespace(documents=[doc for doc in documents if doc.company == run.company]), root=root)
    peers = peer_sources()
    return {"temporal": temporal, "industry_sources": list(grouped.values()),
            "peer": {"available": False, "registered_samples": len(peers.get("samples", [])),
                     "reason": "未提供通过逐指标期间、范围、定义、分母和来源核验的同业样本，不生成排名。"},
            "notice": "登记覆盖不等于行业效果验证；跨年/同业数值须另外通过逐指标资格门禁。"}
