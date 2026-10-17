"""企业披露版本链：原文档、更正文档与生效关系独立登记。

版本变化只生成版本证据链，不进入正式跨报告差额，也不与系统修订混成一条时间轴。
该模块不依赖双报告运行：同一公司同一报告类型的多份登记文档即可构成版本链。
"""
from __future__ import annotations

import re

from .connectivity_engine import number
from .connectivity_schemas import ReportDocument, VersionChange, VersionRecord

VERSION_NOTE = "版本金额变化只说明财务披露版本发生变化，不能计为已解释的跨报告差异。"


def version_records_for(documents: list[ReportDocument]) -> list[VersionRecord]:
    """按披露日期排序列出各版本；媒体引述只记来源类别。"""
    ordered = sorted(documents, key=lambda doc: (doc.disclosure_date or "9999", doc.document_id))
    records = []
    for index, doc in enumerate(ordered, start=1):
        records.append(VersionRecord(version_id=f"{doc.document_id}-v{index}", document_id=doc.document_id,
            report_type=doc.report_type, version_role=doc.version_role, disclosure_date=doc.disclosure_date, metric_period=doc.metric_period,
            report_period=doc.report_period or doc.period,
            label=f"{doc.company} {doc.report_type} {doc.report_period or doc.period}",
            effective_relation=("首次公开版本" if doc.version_role == "original" else
                                "更正后生效" if doc.version_role == "correction" else "版本角色未登记"),
            source_kind="mirror" if doc.source_kind == "announcement_mirror" else "official"))
    return records


def _key(row, report_type: str) -> tuple[str, str, str, str]:
    """同一指标必须在同一报告类型内比较；AR 与 ESG 不是彼此的版本。"""
    return (report_type, re.sub(r"\s+", "", row.label), row.year, row.unit)


def build_version_chain(entries: list[dict]) -> dict:
    """entries 为 [{'document': ReportDocument, 'occurrences': [...]}]；返回记录、变化与限制说明。"""
    documents = [entry["document"] for entry in entries]
    records = version_records_for(documents)
    ordered = sorted(entries, key=lambda entry: (entry["document"].report_type,
                                                 entry["document"].disclosure_date or "9999",
                                                 entry["document"].document_id))
    # 逐版比较：前一版本 → 本版本，形成 v1→v2→v3 的链，而不是每个更正都对原始版本比。
    latest: dict[tuple, tuple] = {}
    changes: list[VersionChange] = []
    for entry in ordered:
        doc = entry["document"]
        for row in entry.get("occurrences", []):
            if not row.value:
                continue
            key = _key(row, doc.report_type)
            base = latest.get(key)
            if base and doc.version_role == "correction":
                base_doc, base_row = base
                try:
                    difference = number(row.value) - number(base_row.value)
                except ValueError:
                    difference = None
                if difference is not None:
                    changes.append(VersionChange(from_version_id=f"{base_doc.document_id}-{base_row.occurrence_id}",
                        to_version_id=f"{doc.document_id}-{row.occurrence_id}", label=row.label,
                        display_change=f"{difference}", absolute_change=f"{abs(difference)}", unit=row.unit,
                        only_version_evidence=True))
            latest[key] = (doc, row)
    return {"records": records, "changes": changes,
            "note": VERSION_NOTE,
            "limitation": ("本次未登记更正版本，版本链只有原始版本" if not changes else
                           "变化只覆盖同一标签、同一年度、同一单位的行；未匹配行不推断差值"),
            "source_kind_rule": "official 可形成版本链；mirror 单独标注；媒体引述不生成文件身份或页码"}
