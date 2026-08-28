"""反确认偏差搜索记录（创新四）。

不强迫模型生成固定数量的“正常解释”，只结构化记录系统是否执行了反向证据搜索：
- 是否执行反向证据搜索；
- 搜索问题；
- 命中证据；
- 找到的替代解释；
- 未找到支持证据时明确写 none_supported_by_current_evidence；
- 最终为何保留、降级或暂缓。

目标是证明系统执行了反确认偏差程序，而不是诱导模型凑解释数量。
"""

from __future__ import annotations

from typing import Any

ROUTE_QUESTIONS = {
    "risk_candidate": ("RAG-Q1", "RAG-Q2", "RAG-Q5", "RAG-Q6"),
    "negative_confirmation": ("RAG-Q1", "RAG-Q2", "RAG-Q5", "RAG-Q6"),
    "industry_review": ("RAG-Q3", "RAG-Q4", "RAG-Q6", "RAG-Q1"),
    "evidence_gap_review": ("RAG-Q5", "RAG-Q6", "RAG-Q1"),
}


def build_anti_confirmation_record(
    *,
    route: str | None,
    rag_evidence: list[dict[str, Any]],
    counter_explanations: list[dict[str, Any]],
    review_recommendation: str | None,
) -> dict[str, Any]:
    """从一次运行的证据与角色输出构建反确认偏差结构化记录。"""
    search_questions = list(ROUTE_QUESTIONS.get(route or "risk_candidate", ()))
    hits = [
        {
            "retrieval_id": row.get("retrieval_id"),
            "evidence_id": row.get("evidence_id"),
            "locator": row.get("locator") or row.get("pdf_page"),
            "score": row.get("score"),
        }
        for row in rag_evidence or []
    ]
    explanations = []
    for item in counter_explanations or []:
        if not isinstance(item, dict):
            continue
        evidence_ids = [str(e) for e in (item.get("evidence_ids") or [])]
        explanations.append(
            {
                "text": item.get("text"),
                "support_status": item.get("support_status") or "unverified_hypothesis",
                "evidence_ids": evidence_ids,
                "supported_by_current_evidence": bool(
                    evidence_ids and item.get("support_status") == "supported"
                ),
            }
        )
    supported = [e for e in explanations if e["supported_by_current_evidence"]]
    none_supported = bool(explanations) and not supported
    return {
        "schema_version": "anti_confirmation_record_v1",
        "reverse_evidence_search_performed": route is not None,
        "search_questions": search_questions,
        "hit_count": len(hits),
        "hits": hits,
        "alternative_explanations": explanations,
        "none_supported_by_current_evidence": none_supported,
        "final_recommendation": review_recommendation,
        "boundary": "本记录只证明执行了反向证据搜索与正常解释核查，不诱导模型凑解释数量；"
        "是否保留候选仍由确定性结果与人工判断决定。",
    }
