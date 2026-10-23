"""唯一图谱后端：把财务穿透层装配为可交互图谱，含三轴边状态、原文溯源与版本失效。

职责边界（第二轮修改意见裁决）：
- 业务关系由 connectivity_financial_bridge.py 产生；本模块只做装配、序列化与失效，
  不新增第二套关系判定。
- 每条边分三轴：relation_kind（什么关联）、assertion_origin（报告/程序/模型/假设）、
  evidence_status（支持/间接支持/反驳/待核/不可比）——三者不得混用。
- 任何节点都必须能回到 `document_id + pdf_page + quote + source_sha256`；
  来源哈希变化时依赖边失效，旧运行保留历史但不冒充新证据。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

VERSION = "connectivity_graph_v1"

RELATION_META = {
    "DIRECT_RECONCILIATION": {"kind": "direct", "label": "直接证实", "color": "#1F6F5C", "dash": ""},
    "DISCLOSED_ALLOCATION": {"kind": "allocated", "label": "披露归属", "color": "#2F6F9F", "dash": ""},
    "TEMPORAL_ASSOCIATION": {"kind": "temporal", "label": "跨期关联", "color": "#6B7F99", "dash": "6 4"},
    "SEMANTIC_ASSOCIATION": {"kind": "semantic", "label": "语义关联", "color": "#7A8CA3", "dash": "3 4"},
    "HYPOTHESIZED_MECHANISM": {"kind": "mechanism", "label": "机制假设", "color": "#8A6FA8", "dash": "2 5"},
    "CONTRADICTED": {"kind": "challenged", "label": "被证据挑战", "color": "#A6403A", "dash": "8 5"},
    "INSUFFICIENT": {"kind": "gap", "label": "依据不足", "color": "#9A9488", "dash": "2 6"},
}

# 三轴之一：断言来源。程序候选与报告明示分开；模型与假设另有专属来源。
ASSERTION_ORIGIN = {
    "DIRECT_RECONCILIATION": "report",
    "DISCLOSED_ALLOCATION": "report",
    "TEMPORAL_ASSOCIATION": "program",
    "SEMANTIC_ASSOCIATION": "program",
    "HYPOTHESIZED_MECHANISM": "assumption",
    "CONTRADICTED": "program",
    "INSUFFICIENT": "program",
}

# 三轴之一：证据状态。状态词与概览语义一致，由唯一映射维护。
EVIDENCE_STATUS = {
    "pending_evidence": "pending",
    "limited_support": "indirect_supported",
    "challenged": "refuted",
    "insufficient": "not_comparable",
    "observed": "supported",
}

STATUS_LABEL = {
    "pending_evidence": "待补证",
    "limited_support": "有限支持",
    "challenged": "被反证挑战",
    "insufficient": "依据不足",
}

EVIDENCE_STATUS_LABEL = {
    "supported": "支持", "indirect_supported": "间接支持", "refuted": "反驳",
    "pending": "待核", "not_comparable": "不可比",
}


def _decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _claim_text(claim: dict) -> str:
    text = str(claim.get("text") or claim.get("quote") or "")
    return text[:160] + ("…" if len(text) > 160 else "")


def _sha_by_fact(bridge: dict) -> dict[str, str]:
    """fact_id → 原件SHA256，来自 case_facts；缺失时留空，不伪造。"""
    return {fact["fact_id"]: fact.get("file_sha256", "")
            for fact in bridge.get("case_facts", [])}


def _performance_nodes(claim: dict) -> list[dict]:
    """把主张中的非金额绩效值单列为绩效节点；金额已由财务节点表达。"""
    nodes = []
    for index, amount in enumerate(claim.get("amounts", [])):
        if amount.get("dimension") == "money":
            continue
        label = f"{amount.get('raw')}{amount.get('unit')}"
        nodes.append({
            "id": f"PERF:{claim['claim_id']}:{index}",
            "type": "performance",
            "label": label,
            "sub_label": "绩效/目标值",
            "document_id": claim["document_id"],
            "pdf_page": claim["pdf_page"],
            "quote": claim.get("quote", ""),
            "source_sha256": claim.get("source_sha256", ""),
            "verified": bool(claim.get("page_verified")),
            "value": amount.get("raw"),
            "unit": amount.get("unit"),
            "status": "observed" if claim.get("observed_or_plan") == "observed" else "plan",
        })
    return nodes


def build_impact_graph(bridge: dict) -> dict:
    """由 bridge 的 claims/nodes/edges 生成稳定图谱；孤立节点不画。"""
    claims = {item["claim_id"]: item for item in bridge.get("claims", [])}
    financial = {item["node_id"]: item for item in bridge.get("nodes", [])}
    edges = bridge.get("edges", [])
    used_claims = {edge["claim_id"] for edge in edges}
    used_financial = {edge["financial_node_id"] for edge in edges if edge.get("financial_node_id")}
    sha_map = _sha_by_fact(bridge)
    # 源文件身份属于每个端点，不能只记录ESG端。
    for claim_id, claim in claims.items():
        claim = dict(claim, source_sha256=sha_map.get(claim_id, ""))
        claims[claim_id] = claim
    nodes: dict[str, dict] = {}
    graph_edges = []

    def add_claim(claim_id: str):
        claim = claims[claim_id]
        nodes[claim_id] = {
            "id": claim_id,
            "type": "claim",
            "claim_kind": claim.get("claim_kind", ""),
            "claim_kind_canonical": claim.get("claim_kind_canonical", ""),
            "label": _claim_text(claim),
            "sub_label": {"target": "承诺/目标", "action": "行动", "performance": "绩效",
                          "commitment": "承诺"}.get(claim.get("claim_kind"), "主张"),
            "document_id": claim["document_id"],
            "pdf_page": claim["pdf_page"],
            "quote": claim.get("quote", ""),
            "verified": bool(claim.get("page_verified")),
            "source_sha256": claim.get("evidence_hash", "") and sha_map.get(claim_id, ""),
            "year": claim.get("year"),
            "value": claim.get("value"),
            "unit": claim.get("unit"),
            "status": claim.get("observed_or_plan"),
        }
        for perf in _performance_nodes(claim):
            nodes[perf["id"]] = perf
            graph_edges.append({"id": "E:" + perf["id"], "source": claim_id, "target": perf["id"],
                                "kind": "quantifies", "label": "给出绩效值", "relation_type": "PERFORMANCE_VALUE",
                                "color": "#B8B2A6", "dash": "2 4", "status": "observed",
                                "relation_kind": "PERFORMANCE_VALUE", "assertion_origin": "report",
                                "evidence_status": "supported", "invalid": False, "invalid_reason": "",
                                "source_document_id": claim["document_id"], "source_sha256": sha_map.get(claim_id, ""),
                                "pdf_page": claim["pdf_page"], "quote": claim.get("quote", ""),
                                "source_dependencies": [{"document_id": claim["document_id"], "sha256": sha_map.get(claim_id, "")}],
                                "evidence_ids": [claim_id], "why": "绩效值直接来自同一句原文"})

    def add_financial(node_id: str):
        node = financial[node_id]
        nodes[node_id] = {
            "id": node_id,
            "type": "financial",
            "label": node.get("label", "")[:80],
            "sub_label": node.get("financial_statement_line", "")[:70],
            "document_id": node["document_id"],
            "pdf_page": node["pdf_page"],
            "quote": node.get("quote", ""),
            "verified": bool(node.get("page_verified")),
            "source_sha256": sha_map.get(node_id, ""),
            "year": node.get("year"),
            "value": node.get("value"),
            "unit": node.get("unit"),
            "value_kind": node.get("value_kind"),
            "role": node.get("industry_role", ""),
            "status": "observed",
        }

    for edge in edges:
        claim_id = edge["claim_id"]
        if claim_id not in nodes:
            add_claim(claim_id)
        target = edge.get("financial_node_id")
        if target:
            if target not in nodes:
                add_financial(target)
            destination = target
        else:
            # 缺口节点：没有财务对应项时，明确画出来，而不是留白。
            gap_id = "GAP:" + claim_id
            nodes[gap_id] = {
                "id": gap_id, "type": "gap", "label": "年报未见可归属财务项目",
                "sub_label": _claim_text(claims[claim_id])[:36] if claim_id in claims else "待补证，不推定未披露",
                "document_id": None, "pdf_page": None,
                "quote": "", "verified": False, "status": "insufficient",
            }
            destination = gap_id
        meta = RELATION_META.get(edge["relation_type"], RELATION_META["INSUFFICIENT"])
        claim_node = nodes.get(claim_id, {})
        graph_edges.append({
            "id": edge["edge_id"], "source": claim_id, "target": destination,
            "kind": meta["kind"], "label": meta["label"], "relation_type": edge["relation_type"],
            # 三轴：关系种类、断言来源、证据状态；三者独立，禁止“相关”自动变“已证实”。
            "relation_kind": edge["relation_type"],
            "assertion_origin": ASSERTION_ORIGIN.get(edge["relation_type"], "program"),
            "evidence_status": EVIDENCE_STATUS.get(edge["status"], "pending"),
            "color": meta["color"], "dash": meta["dash"], "status": edge["status"],
            "same_entity": edge.get("same_entity"), "same_period": edge.get("same_period"),
            "definition_compatible": edge.get("definition_compatible"),
            "boundary_compatible": edge.get("boundary_compatible"),
            "source_document_id": claim_node.get("document_id"),
            "source_dependencies": [{"document_id": nodes[node_id].get("document_id"),
                                     "sha256": nodes[node_id].get("source_sha256", "")}
                                    for node_id in (claim_id, destination) if nodes[node_id].get("document_id")],
            "source_sha256": claim_node.get("source_sha256", ""),
            "pdf_page": claim_node.get("pdf_page"),
            "quote": claim_node.get("quote", ""),
            "evidence_ids": edge.get("evidence_ids", []),
            "missing_conditions": edge.get("missing_conditions", []),
            "why": edge.get("why", ""), "numeric_gap": edge.get("numeric_gap"),
            "confidence_label": edge.get("confidence_label", ""),
            "financial_statement_line": edge.get("financial_statement_line", ""),
            "invalid": False, "invalid_reason": "",
        })

    # 分层坐标：主张/承诺在最左，绩效在中间，财务在右，缺口在中间偏下。
    columns = [
        {"key": "claim", "label": "可持续主张", "x": 40},
        {"key": "performance", "label": "行动/绩效", "x": 300},
        {"key": "financial", "label": "财务项目", "x": 600},
    ]
    order = {"claim": 0, "performance": 1, "financial": 2, "gap": 1}
    sorted_nodes = sorted(nodes.values(), key=lambda node: (order.get(node["type"], 3),
                                                            node.get("pdf_page") or 0,
                                                            str(node.get("label"))))
    counts = {}
    for node in sorted_nodes:
        index = counts.get(node["type"], 0)
        counts[node["type"]] = index + 1
        node["column"] = order.get(node["type"], 3)
        node["y"] = 30 + index * 92
    max_rows = max(counts.values(), default=1)
    height = max(360, 30 + max_rows * 92 + 40)
    # 默认关键路径：评委首屏只看最有信息量的5—12个节点，专业全景点开才展开。
    key_prior = {"CONTRADICTED": 0, "DIRECT_RECONCILIATION": 1, "DISCLOSED_ALLOCATION": 2,
                 "HYPOTHESIZED_MECHANISM": 3, "SEMANTIC_ASSOCIATION": 4, "TEMPORAL_ASSOCIATION": 5}
    key_edges = sorted(graph_edges, key=lambda item: (key_prior.get(item["relation_type"], 9), item["id"]))
    key_node_ids: list[str] = []
    for item in key_edges:
        new_ids = [endpoint for endpoint in (item["source"], item["target"]) if endpoint not in key_node_ids]
        if len(key_node_ids) + len(new_ids) > 12:
            continue
        for endpoint in (item["source"], item["target"]):
            if endpoint not in key_node_ids:
                key_node_ids.append(endpoint)
        if len(key_node_ids) >= 12:
            break
    stats = {
        "claims": sum(node["type"] == "claim" for node in sorted_nodes),
        "performance": sum(node["type"] == "performance" for node in sorted_nodes),
        "financial": sum(node["type"] == "financial" for node in sorted_nodes),
        "gaps": sum(node["type"] == "gap" for node in sorted_nodes),
        "edges": len(graph_edges),
        "direct": sum(edge["kind"] == "direct" for edge in graph_edges),
        "semantic": sum(edge["kind"] == "semantic" for edge in graph_edges),
        "challenged": sum(edge["kind"] == "challenged" for edge in graph_edges),
        "insufficient": sum(edge["kind"] == "gap" for edge in graph_edges),
        "verified_edges": sum(edge["evidence_status"] == "supported" for edge in graph_edges),
        "refuted_edges": sum(edge["evidence_status"] == "refuted" for edge in graph_edges),
    }
    return {
        "version": VERSION,
        "industry": bridge.get("industry", "general"),
        "industry_name": bridge.get("industry_name", ""),
        "nodes": sorted_nodes,
        "edges": graph_edges,
        "columns": columns,
        "height": height,
        "key_path": key_node_ids,
        "legend": [{"kind": key, **value} for key, value in RELATION_META.items()],
        "status_labels": STATUS_LABEL,
        "evidence_status_labels": EVIDENCE_STATUS_LABEL,
        "stats": stats,
        "filters": ["only_financial", "show_gaps", "show_challenged", "by_year", "by_evidence_status"],
        "invalidations": [],
        "notice": "实线/虚线只表示证据强度与关系类型，不表示资金已经真实流转；缺口不等于企业未披露。",
    }


def invalidate_graph(graph: dict, changed_documents: dict[str, str]) -> dict:
    """来源版本失效：登记文档的新SHA与边内source_sha256比对，命中即失效并写原因。

    失效只把边标记为 invalid，不删除历史节点；旧运行保留原状，不冒充新证据。
    """
    changed = {str(doc_id): str(sha) for doc_id, sha in (changed_documents or {}).items()}
    if not changed:
        return graph
    invalidated = {item["edge_id"]: item for item in graph.get("invalidations", [])}
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    for edge in graph.get("edges", []):
        dependencies = edge.get("source_dependencies") or [
            {"document_id": nodes.get(endpoint, {}).get("document_id"), "sha256": nodes.get(endpoint, {}).get("source_sha256")}
            for endpoint in (edge.get("source"), edge.get("target")) if nodes.get(endpoint, {}).get("document_id")]
        dependencies = dependencies or [{"document_id": edge.get("source_document_id"), "sha256": edge.get("source_sha256")}]
        for dependency in dependencies:
            doc_id = str(dependency.get("document_id") or "")
            old_sha = str(dependency.get("sha256") or "")
            if doc_id not in changed or (old_sha and changed[doc_id] == old_sha):
                continue
            edge["invalid"] = True
            edge["invalid_reason"] = f"来源 {doc_id} 的原件SHA已变化，依赖该来源的边失效；历史记录保留。"
            edge.setdefault("original_evidence_status", edge.get("evidence_status"))
            edge["evidence_status"] = "not_comparable"
            edge.update(label="来源失效", color="#8b8580", dash="2 6")
            invalidated[edge["id"]] = {"edge_id": edge["id"], "document_id": doc_id,
                                       "reason": edge["invalid_reason"]}
            break
    graph.setdefault("invalidations", [])
    graph["invalidations"] = list(invalidated.values())
    if invalidated:
        stats = graph.get("stats", {})
        stats["invalidated_edges"] = len(invalidated)
    return graph


def refresh_run_sources(root, run):
    """读取/导出时验证登记和原件哈希，只返回投影副本。

    历史保存结果不直接修改，失效标记只作用于本次读取。
    登记记录消失时，原来可读的来源也应明确失效。
    文件缺失与文件换版分别保存原因，不能合成为空结果。
    原件实际字节哈希与本轮登记哈希都必须匹配历史身份。
    关联依赖覆盖两端报告，不能仅验证可持续报告一端。
    禁用失效来源支持的金额模拟，保留原运行供历史回查。
    新旧证据状态分列，失效不能抹掉历史状态发生过的事实。
    """
    import hashlib
    from .connectivity_extraction import load_registry, source_path
    child = run.model_copy(deep=True)
    current = {doc.document_id: doc for doc in load_registry(root)}
    changed = {}
    for original in run.documents:
        doc = current.get(original.document_id)
        if doc is None:
            changed[original.document_id] = "unregistered"
            continue
        path = source_path(root, doc)
        if not path.is_file():
            changed[original.document_id] = "missing"
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != original.file_sha256 or doc.file_sha256 != original.file_sha256:
            changed[original.document_id] = actual if actual != original.file_sha256 else "registry_changed"
    if changed:
        invalidate_graph(child.impact_graph, changed)
        invalid_edges = {edge["id"]: edge for edge in child.impact_graph.get("edges", []) if edge.get("invalid")}
        for edge in child.financial_edges:
            if edge.get("edge_id") in invalid_edges:
                edge.update(invalid=True, evidence_status="not_comparable",
                            invalid_reason=invalid_edges[edge["edge_id"]]["invalid_reason"])
        for node in child.impact_graph.get("nodes", []):
            if node.get("document_id") in changed:
                node.update(invalid=True, verified=False)
        child.versions["source_validity"] = {"status": "invalid", "documents": changed,
            "notice": "依赖来源已变化或不可读取；当前为历史结果，不得作为有效新证据。"}
        if child.financial_scenario:
            child.financial_scenario.update(available=False, reason="来源失效，禁用金额情景；原历史记录保留。")
    return child
