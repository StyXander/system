"""任务6：财务穿透证据图谱。

节点：可持续事项、经济业务项目、会计处理路径、财务项目、披露页、原文证据、会计规则。
边：describes / may_affect / accounting_path / supported_by / contradicted_by / cross_referenced / unresolved。

两条算法约束：
1. 路线只能按“事项→业务→处理→财务项目→证据”顺序扩展，不跨界拼路径。
2. 每条边单独保存依据；整条路径不因平均相似度高而升级为已验证。
"""
from __future__ import annotations

from collections import defaultdict

from .models import AccountingTreatment, FinancialItem, ImpactRelation, RelationGrade, SustainabilityEvent

GRAPH_VERSION = "impact_graph_v1.0"
PATH_ORDER = ("describes", "may_affect", "accounting_path", "supported_by")
MAX_HOPS = 4


def _node(node_id: str, node_type: str, label: str, **extra) -> dict:
    return {"id": node_id, "type": node_type, "label": label[:90], **extra}


def build(events: list[SustainabilityEvent], items: list[FinancialItem],
          treatments: list[AccountingTreatment], relations: list[ImpactRelation],
          rules_by_id: dict | None = None) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_edge(source: str, target: str, edge_type: str, *, status: str = "unresolved",
                 basis: str = "", page: int | None = None, document_id: str | None = None,
                 verified: bool = False, similarity: float | None = None) -> None:
        edges.append({"id": f"{source}->{target}:{edge_type}", "source": source, "target": target,
                      "type": edge_type, "status": status, "basis": basis[:200],
                      "pdf_page": page, "document_id": document_id, "verified": verified,
                      "similarity": similarity})

    for event in events:
        nodes[event.event_id] = _node(event.event_id, "sustainability_event", event.project_name or event.quote[:30],
                                      status=event.stage.value, document_id=event.document_id,
                                      pdf_page=event.pdf_page, quote=event.quote[:200],
                                      activity_type=event.activity_type, verified=event.page_verified,
                                      missing_fields=event.missing_fields)
        if event.project_name:
            project_id = "BP-" + event.event_id
            nodes[project_id] = _node(project_id, "business_project", event.project_name,
                                      status=event.stage.value, document_id=event.document_id,
                                      pdf_page=event.pdf_page, quote=event.quote[:200], verified=event.page_verified)
            add_edge(event.event_id, project_id, "describes", status="supported",
                     basis="事项原文直接写出项目名称", page=event.pdf_page,
                     document_id=event.document_id, verified=event.page_verified)

    for treatment in treatments:
        event_id = treatment.treatment_id.split(":")[0]
        if event_id not in nodes:
            continue
        nodes[treatment.treatment_id] = _node(treatment.treatment_id, "accounting_treatment", treatment.scene,
                                              status=treatment.status, rule_id=treatment.rule_id,
                                              accounts=treatment.accounts, basis=treatment.basis[:1])
        source = "BP-" + event_id if "BP-" + event_id in nodes else event_id
        add_edge(source, treatment.treatment_id, "accounting_path", status=treatment.status,
                 basis="按会计规则库提出的候选处理路径，前提待验证")
        rule_node = "ARU-" + treatment.rule_id
        if rule_node not in nodes:
            nodes[rule_node] = _node(rule_node, "accounting_rule", treatment.scene, rule_id=treatment.rule_id,
                                     basis=treatment.basis[:2])
        add_edge(treatment.treatment_id, rule_node, "cross_referenced", status="supported",
                 basis="规则库条目（条款位置未逐条核对的不写条号）")

    for item in items:
        nodes[item.item_id] = _node(item.item_id, "financial_item",
                                    f"{item.table_title}·{item.row_header}" if item.table_title else item.row_header,
                                    status=item.value_semantics.value, document_id=item.document_id,
                                    pdf_page=item.pdf_page, quote=item.quote[:200],
                                    value=item.normalized or item.value, unit=item.unit,
                                    verified=item.page_verified, column=item.column_header)

    for relation in relations:
        if relation.financial_item_id and relation.financial_item_id in nodes:
            edge_type = {"contradicted": "contradicted_by", "supported_by": "supported_by"}.get(
                relation.relation_type, "unresolved")
            status = "verified" if relation.grade == RelationGrade.A else (
                "contradicted" if relation.grade == RelationGrade.CONTRADICTED else "unresolved")
            add_edge(relation.treatment_id or relation.event_id, relation.financial_item_id, edge_type,
                     status=status, basis=relation.explanation[:180],
                     page=nodes[relation.financial_item_id].get("pdf_page"),
                     document_id=nodes[relation.financial_item_id].get("document_id"),
                     verified=relation.grade == RelationGrade.A,
                     similarity=None)
        for evidence in relation.supporting + relation.counter:
            evidence_id = f"EV-{evidence.document_id}-{evidence.pdf_page}-{abs(hash(evidence.quote)) % 10000}"
            if evidence_id not in nodes:
                nodes[evidence_id] = _node(evidence_id, "evidence", evidence.quote[:60] or "原文证据",
                                           document_id=evidence.document_id, pdf_page=evidence.pdf_page,
                                           verified=evidence.verified, bbox=evidence.bbox)
            target = relation.financial_item_id or relation.event_id
            add_edge(target, evidence_id,
                     "contradicted_by" if evidence in relation.counter else "supported_by",
                     status="verified" if evidence.verified else "unresolved",
                     basis="原文逐字引用" if evidence.verified else "引用待核验",
                     page=evidence.pdf_page, document_id=evidence.document_id, verified=evidence.verified)

    paths = _paths(nodes, edges)
    stats = defaultdict(int)
    for node in nodes.values():
        stats[node["type"]] += 1
    for edge in edges:
        stats["edge:" + edge["type"]] += 1
    return {"version": GRAPH_VERSION, "nodes": list(nodes.values()), "edges": edges,
            "paths": paths[:24], "stats": {**dict(stats), "paths": len(paths)},
            "note": "边状态逐条登记；路径不因平均相似度高而升级为已验证。"}


def _paths(nodes: dict[str, dict], edges: list[dict], *, limit: int = 40) -> list[dict]:
    """受约束路径搜索：只按 事项→项目→处理→财务项目→证据 扩展，最多四跳。"""
    outgoing: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        outgoing[edge["source"]].append(edge)
    allowed = {"sustainability_event": "describes", "business_project": "accounting_path",
               "accounting_treatment": None, "financial_item": "supported_by"}
    results: list[dict] = []

    def walk(node_id: str, trail: list[dict], hops: int) -> None:
        if hops >= MAX_HOPS:
            results.append({"nodes": [step["target"] for step in trail],
                            "types": [nodes.get(step["target"], {}).get("type") for step in trail],
                            "edges": [step["type"] for step in trail],
                            "statuses": [step["status"] for step in trail],
                            "verified": all(step["verified"] for step in trail if step["type"] == "supported_by")})
            return
        node_type = nodes.get(node_id, {}).get("type")
        expected = {"sustainability_event": {"describes"},
                    "business_project": {"accounting_path"},
                    "accounting_treatment": {"supported_by", "contradicted_by", "unresolved", "cross_referenced"},
                    "financial_item": {"supported_by", "contradicted_by"}}.get(node_type)
        if expected is None:
            return
        moved = False
        for edge in outgoing.get(node_id, []):
            if edge["type"] not in expected:
                continue
            moved = True
            walk(edge["target"], trail + [edge], hops + 1)
        if not moved and trail:
            results.append({"nodes": [step["target"] for step in trail],
                            "types": [nodes.get(step["target"], {}).get("type") for step in trail],
                            "edges": [step["type"] for step in trail],
                            "statuses": [step["status"] for step in trail], "verified": False})

    for node_id, node in nodes.items():
        if node["type"] == "sustainability_event":
            walk(node_id, [], 0)
    results.sort(key=lambda item: (not any(status == "verified" for status in item["statuses"]), -len(item["nodes"])))
    return results[:limit]
