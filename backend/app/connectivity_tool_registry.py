"""受控Agent工具注册表：模型只能申请白名单内工具，服务端验证并执行。

安全边界（必须同时成立）：
- 不接受任意网址、任意磁盘路径、可执行代码或未登记文档；
- document_id 必须出现在本次运行已登记文档里，页码必须落在原件范围内；
- 每次调用记录 tool_name、validated_args_hash、source_hash、output_digest、耗时与结果；
- 未登记的资源（跨年报告、同业样本）返回明确缺口，不生成虚假检索命中。
"""
from __future__ import annotations
from .source_viewer import PDF_ACCESS_LOCK

import hashlib
import json
import re
import time

VERSION = "tool_registry_v1"

# 工具白名单：全部为登记报告内的只读或确定性操作。
TOOL_NAMES = (
    "search_registered_reports",
    "open_source_page",
    "lookup_ontology_rule",
    "recompute_decimal",
    "lookup_annual_comparison",
    "lookup_peer_sample",
    # 财务穿透工具：只读本次运行已生成的事项、附注项目与规则库。
    "search_esg_events",
    "search_financial_notes",
    "get_accounting_rules",
    "verify_evidence",
)


class ToolRequest:
    """一次工具申请：工具名与参数结构；参数由服务端验证，模型不能直接执行。"""

    def __init__(self, tool_name: str, arguments: dict):
        self.tool_name = str(tool_name or "").strip()
        self.arguments = dict(arguments or {})

    def validated_args_hash(self) -> str:
        payload = json.dumps({"tool": self.tool_name, "args": self.arguments},
                             ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _digest(text: str) -> str:
    return hashlib.sha256(str(text or "").encode()).hexdigest()[:16]


def _find_document(run, document_id: str):
    wanted = str(document_id or "").strip()
    for doc in getattr(run, "documents", []):
        if doc.document_id == wanted:
            return doc
    return None


def _load_page_text(root, doc, page_no: int) -> str | None:
    """打开已登记原件的指定页；页码越界返回 None，不做任何下载。"""
    try:
        from .connectivity_extraction import source_path
        import pymupdf
        path = source_path(root, doc)
        with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
            if page_no < 1 or page_no > len(pdf):
                return None
            return pdf[page_no - 1].get_text("text")
    except Exception:
        return None


def _validate_common(run, arguments: dict) -> tuple[None, None] | tuple[str, str]:
    """通用参数验证；返回 (错误码, 说明)。文档必须已登记。"""
    doc = _find_document(run, arguments.get("document_id"))
    if doc is None:
        return "UNREGISTERED_DOCUMENT", "document_id 不在本次已登记文档中；工具拒绝执行。"
    return None, None


def execute_tool(root, run, request: ToolRequest) -> dict:
    """执行白名单工具并返回统一回执；未知工具直接拒绝。"""
    started = time.perf_counter()
    receipt = {"tool_name": request.tool_name, "args_hash": request.validated_args_hash(),
               "status": "rejected", "output_digest": "", "source_hash": "",
               "elapsed_ms": 0, "result": None, "reason": ""}
    if request.tool_name not in TOOL_NAMES:
        receipt["reason"] = f"工具不在白名单：{request.tool_name}"
        return receipt
    args = request.arguments
    error = None
    if request.tool_name in {"search_registered_reports", "open_source_page"}:
        error, reason = _validate_common(run, args)
        if error:
            receipt["reason"] = reason
            return _finish(receipt, started)
        if root is not None:
            # 生产入口核实原件，不让旧登记哈希冒充换版后的文件内容。
            from .connectivity_extraction import source_path
            doc = _find_document(run, args.get("document_id"))
            path = source_path(root, doc)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != doc.file_sha256:
                receipt["reason"] = "来源原件缺失或哈希已变化；本次工具拒绝使用失效证据。"
                return _finish(receipt, started)
    if request.tool_name == "search_registered_reports":
        return _search_registered_reports(root, run, args, receipt, started)
    if request.tool_name == "open_source_page":
        return _open_source_page(root, run, args, receipt, started)
    if request.tool_name == "lookup_ontology_rule":
        return _lookup_ontology_rule(args, receipt, started)
    if request.tool_name == "recompute_decimal":
        return _recompute_decimal(args, receipt, started)
    if request.tool_name == "lookup_annual_comparison":
        return _lookup_annual_comparison(root, run, args, receipt, started)
    if request.tool_name == "search_esg_events":
        return _search_esg_events(run, args, receipt, started)
    if request.tool_name == "search_financial_notes":
        return _search_financial_notes(run, args, receipt, started)
    if request.tool_name == "get_accounting_rules":
        return _get_accounting_rules(args, receipt, started)
    if request.tool_name == "verify_evidence":
        return _verify_evidence(root, run, args, receipt, started)
    return _lookup_peer_sample(run, args, receipt, started)


def _impact(run) -> dict:
    payload = getattr(run, "financial_impact", None) or {}
    return payload if isinstance(payload, dict) else {}


def _search_esg_events(run, args, receipt, started):
    """在本次运行已抽取的可持续事项内检索；不重新访问网络。"""
    query = str(args.get("query") or "").strip()
    limit = max(1, min(int(args.get("limit") or 5), 10))
    events = _impact(run).get("events") or []
    if not query:
        receipt["reason"] = "缺少 query。"
        return _finish(receipt, started)
    from .financial_impact.textutil import compact
    key = compact(query)
    hits = [event for event in events if key in compact(
        " ".join([event.get("project_name", ""), event.get("quote", ""), event.get("activity_type", "")]))]
    receipt.update({"status": "ok", "result": {"query": query, "count": len(hits), "events": [
        {"event_id": event.get("event_id"), "document_id": event.get("document_id"),
         "project_name": event.get("project_name"),
         "pdf_page": event.get("pdf_page"), "stage": event.get("stage"),
         "amount_nature": event.get("amount_nature"), "activity_type": event.get("activity_type"),
         "quote": str(event.get("quote"))[:120]}
        for event in hits[:limit]]}})
    receipt["output_digest"] = _digest(json.dumps(receipt["result"], ensure_ascii=False, sort_keys=True))
    return _finish(receipt, started)


def _search_financial_notes(run, args, receipt, started):
    """在本次运行已解析的附注项目内检索；返回列语义，避免把余额当投入。"""
    query = str(args.get("query") or "").strip()
    limit = max(1, min(int(args.get("limit") or 5), 10))
    items = _impact(run).get("items") or []
    if not query:
        receipt["reason"] = "缺少 query。"
        return _finish(receipt, started)
    from .financial_impact.textutil import compact
    key = compact(query)
    hits = [item for item in items if key in compact(
        " ".join([str(item.get("table_title", "")), str(item.get("row_header", "")), str(item.get("quote", ""))]))]
    receipt.update({"status": "ok", "result": {"query": query, "count": len(hits), "items": [
        {"item_id": item.get("item_id"), "document_id": item.get("document_id"),
         "table_title": item.get("table_title"),
         "row_header": item.get("row_header"), "column_header": item.get("column_header"),
         "value_semantics": item.get("value_semantics"), "raw_value": item.get("raw_value"),
         "unit": item.get("unit"), "pdf_page": item.get("pdf_page"),
         "quote": str(item.get("quote"))[:120]}
        for item in hits[:limit]]}})
    receipt["output_digest"] = _digest(json.dumps(receipt["result"], ensure_ascii=False, sort_keys=True))
    return _finish(receipt, started)


def _get_accounting_rules(args, receipt, started):
    """查询会计规则库；只返回规则与依据，不返回“已确认”结论。"""
    from .financial_impact.accounting_mapping import load_rules
    activity = str(args.get("activity_type") or "").strip()
    keyword = str(args.get("keyword") or "").strip()
    rules = [rule for rule in load_rules()
             if (not activity or activity in rule.activity_types)
             and (not keyword or keyword in rule.scene or keyword in "".join(rule.accounts))]
    receipt.update({"status": "ok", "result": {"count": len(rules), "rules": [
        {"rule_id": rule.rule_id, "scene": rule.scene, "accounts": rule.accounts,
         "applies_when": rule.applies_when, "required_evidence": rule.required_evidence,
         "basis": rule.basis, "verification": rule.verification}
        for rule in rules[:5]]}})
    receipt["output_digest"] = _digest(json.dumps(receipt["result"], ensure_ascii=False, sort_keys=True))
    return _finish(receipt, started)


def _verify_evidence(root, run, args, receipt, started):
    """逐字核验：引文必须出现在指定页原文，且文档已登记。"""
    receipt["status"] = "rejected"
    error, reason = _validate_common(run, args)
    if error:
        receipt["reason"] = reason
        return _finish(receipt, started)
    quote = str(args.get("quote") or "").strip()
    page_no = int(args.get("page") or 0)
    if not quote or page_no <= 0:
        receipt["reason"] = "需要 quote 与 page。"
        return _finish(receipt, started)
    doc = _find_document(run, args.get("document_id"))
    if page_no > int(getattr(doc, "pages", 0) or 0) and int(getattr(doc, "pages", 0) or 0) > 0:
        receipt["reason"] = "页码超出原件范围。"
        return _finish(receipt, started)
    text = _load_page_text(root, doc, page_no)
    if text is None:
        receipt["reason"] = "原件不可读或页码无效。"
        return _finish(receipt, started)
    from .financial_impact.textutil import compact
    verified = compact(quote)[:80] in compact(text)
    receipt.update({"status": "ok", "verified": verified, "source_hash": doc.file_sha256,
                    "result": {"document_id": doc.document_id, "page": page_no,
                               "quote": quote[:120], "verified": verified}})
    receipt["output_digest"] = _digest(json.dumps(receipt["result"], ensure_ascii=False, sort_keys=True))
    return _finish(receipt, started)


def _finish(receipt: dict, started: float) -> dict:
    receipt["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    return receipt


def _search_registered_reports(root, run, args, receipt, started):
    """在已登记报告内检索关键词；不接受外部网络或路径。"""
    terms = [str(term).strip() for term in (args.get("terms") or []) if str(term).strip()]
    doc = _find_document(run, args.get("document_id"))
    if not terms:
        receipt["reason"] = "缺少检索词。"
        return _finish(receipt, started)
    if len(terms) > 5:
        terms = terms[:5]
    from .connectivity_extraction import source_path
    import pymupdf
    hits = []
    try:
        path = source_path(root, doc)
        with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
            receipt["source_hash"] = doc.file_sha256 or _digest(str(path))
            for index, page in enumerate(pdf):
                if time.perf_counter() - started > 10:
                    receipt["reason"] = "工具达到10秒检索上限；仅返回已检查范围，不推定未披露。"
                    break
                text = page.get_text("text")
                if not text:
                    continue
                matched = [term for term in terms if term in text]
                if matched:
                    anchor = min(text.find(term) for term in matched)
                    snippet = text[max(0, anchor - 120):anchor + 600].replace("\n", " ")
                    hits.append({"page": index + 1, "matched_terms": matched, "snippet": snippet})
                if len(hits) >= 8:
                    break
    except Exception as error:
        receipt["reason"] = f"检索失败：{type(error).__name__}"
        return _finish(receipt, started)
    receipt.update(status="hit" if hits else "no_match", result={"document_id": doc.document_id,
                   "hits": hits, "terms": terms, "quote": "\n".join(hit["snippet"] for hit in hits),
                   "matched_terms": sorted({term for hit in hits for term in hit["matched_terms"]}),
                   "evidence_refs": [{"document_id": doc.document_id, "pdf_page": hit["page"],
                                      "source_sha256": receipt["source_hash"], "quote": hit["snippet"]} for hit in hits]})
    receipt["output_digest"] = _digest(json.dumps(hits, ensure_ascii=False))
    if not hits:
        receipt["reason"] = "已检索范围内未命中；不推定企业未披露。"
    return _finish(receipt, started)


def _open_source_page(root, run, args, receipt, started):
    """打开登记原件指定页并返回原文摘录；页码必须存在。"""
    doc = _find_document(run, args.get("document_id"))
    try:
        page_no = int(args.get("page"))
    except (TypeError, ValueError):
        receipt["reason"] = "缺少有效页码。"
        return _finish(receipt, started)
    text = _load_page_text(root, doc, page_no)
    if text is None:
        receipt["reason"] = "页码超出原件范围或原件不可读。"
        return _finish(receipt, started)
    receipt["source_hash"] = doc.file_sha256 or _digest(str(doc.source_url))
    terms = [str(term) for term in args.get("terms", [])][:5]
    matched = [term for term in terms if term in text]
    anchor = min((text.find(term) for term in matched), default=0)
    quote = text[max(0, anchor - 120):anchor + 900].replace("\n", " ")
    receipt.update(status="hit", result={"document_id": doc.document_id, "page": page_no,
                                         "quote": quote, "matched_terms": matched,
                                         "evidence_refs": [{"document_id": doc.document_id, "pdf_page": page_no,
                                                            "source_sha256": receipt["source_hash"], "quote": quote}]})
    receipt["output_digest"] = _digest(quote)
    return _finish(receipt, started)


def _lookup_ontology_rule(args, receipt, started):
    """查询语义本体规则；数据来自 impact_rules.json，不接受任意查询语句。"""
    from .connectivity_financial_ontology import lookup_rule
    keyword = str(args.get("keyword") or "").strip()[:40]
    if not keyword:
        receipt["reason"] = "缺少规则检索词。"
        return _finish(receipt, started)
    hits = lookup_rule(keyword)
    receipt.update(status="hit" if hits else "no_match", result={"keyword": keyword, "rules": hits})
    receipt["output_digest"] = _digest(json.dumps(hits, ensure_ascii=False))
    return _finish(receipt, started)


def _recompute_decimal(args, receipt, started):
    """确定性十进制复算：只允许两操作数与受控算子，不执行任意表达式。"""
    from decimal import Decimal, InvalidOperation
    operator = str(args.get("operator") or "").strip()
    if operator not in {"sum", "difference", "ratio", "percent_change"}:
        receipt["reason"] = "算子不在白名单（sum/difference/ratio/percent_change）。"
        return _finish(receipt, started)
    try:
        left = Decimal(str(args.get("left")))
        right = Decimal(str(args.get("right")))
    except (InvalidOperation, TypeError, ValueError):
        receipt["reason"] = "操作数不是有效数值。"
        return _finish(receipt, started)
    if operator == "ratio" and right == 0:
        receipt["reason"] = "比率的分母为0；拒绝计算。"
        return _finish(receipt, started)
    if operator == "sum":
        value = left + right
        formula = f"{left} + {right} = {value}"
    elif operator == "difference":
        value = left - right
        formula = f"{left} - {right} = {value}"
    elif operator == "ratio":
        value = left / right
        formula = f"{left} ÷ {right} = {value}"
    else:
        if right == 0:
            receipt["reason"] = "同比基数为0；拒绝计算。"
            return _finish(receipt, started)
        value = (left - right) / abs(right) * Decimal(100)
        formula = f"({left} - {right}) ÷ |{right}| × 100 = {value}%"
    receipt.update(status="hit", result={"operator": operator, "value": str(value),
                                         "formula": formula,
                                         "note": "确定性复算只核对该算式本身；不改变任何条件门禁状态。"})
    receipt["output_digest"] = _digest(formula)
    return _finish(receipt, started)


def _lookup_annual_comparison(root, run, args, receipt, started):
    """跨年比较：仅当同企业其他年度报告已登记且原件可用时开放，否则返回明确缺口。"""
    from .connectivity_temporal import temporal_status
    company = str(args.get("company") or getattr(run, "company", "")).strip()
    status = temporal_status(run, root=root)
    receipt["source_hash"] = ""
    receipt.update(status="hit" if status["available"] else "gap",
                   result={"company": company, "registered_periods": status["registered_periods"],
                           "companies": status["companies"]},
                   reason="" if status["available"] else status["reason"])
    if status["available"]:
        receipt["reason"] = "已登记多个年度；具体比较须用 compare_periods 并核对两侧页码。"
    return _finish(receipt, started)


def _lookup_peer_sample(run, args, receipt, started):
    """同业样本：仅使用已授权登记的 peer_sources；未授权返回缺口，不伪造排名。"""
    from .connectivity_peer_benchmark import load_registry
    registry = load_registry()
    available = bool(registry.get("authorized")) and bool(registry.get("samples"))
    receipt["source_hash"] = ""
    receipt.update(status="hit" if available else "gap",
                   result={"registered_samples": len(registry.get("samples", [])),
                           "rejected": registry.get("rejected", []),
                           "registry_version": registry.get("version", "")},
                   reason="" if available else
                   "同业样本未登记授权或登记表为空；不生成任何同业数值对标。")
    return _finish(receipt, started)


def _peer_registry() -> dict:
    """读取同业来源登记表；只含授权与元数据，不含未获许可全文。"""
    from .connectivity_peer_benchmark import load_registry
    return load_registry()
