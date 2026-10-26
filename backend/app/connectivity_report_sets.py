"""不可变的多年资料集合，复用既有公开目录与Supabase案例元数据。

资料集合固定企业、原件指纹、报告年度与观察截至日期。
相同原件可以被多个集合引用，历史文档编号不被覆盖。
每个年度允许只取得一类报告，缺口进入显式覆盖矩阵。
同年同类型有不同版本时要求先选定版本，不能任取一份。
共享保存失败时不伪装成功，本地只镜像已完成的登记。
集合登记复用原有案例元数据，不另建权限或账号体系。
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import re
from pathlib import Path

from .connectivity_matter_schemas import ReportSet, ReportSetRequest
from .connectivity_schemas import ReportDocument


def _identity(doc):
    return (doc.company_id, doc.report_type, doc.effective_period, doc.file_sha256)


def canonical_documents(documents):
    """原件跨报告对复用；旧引用ID保持原样，只在新集合去重。"""
    chosen = {}
    for doc in sorted(documents, key=lambda d: d.document_id):
        chosen.setdefault(_identity(doc), doc)
    return list(chosen.values())


def make_report_set(documents: list[ReportDocument], as_of_date: date) -> ReportSet:
    docs = canonical_documents(documents)
    if not docs or len({d.company_id for d in docs}) != 1:
        raise ValueError("资料集合必须包含同一企业的已登记报告")
    if any(not re.fullmatch(r"[a-fA-F0-9]{64}",d.file_sha256) or not re.fullmatch(r"20\d{2}",d.effective_period) for d in docs):
        raise ValueError("资料缺少有效原件指纹或四位报告年度")
    try:
        for d in docs:date.fromisoformat(d.disclosure_date[:10])
    except ValueError as error:raise ValueError("资料发布日期无效") from error
    if any(not d.disclosure_date or d.disclosure_date[:10] > as_of_date.isoformat() for d in docs):
        raise ValueError("资料缺少发布日期或发布日晚于观察时点，请明确选择可用版本")
    versions = {}
    for doc in docs:
        key = (doc.report_type, doc.effective_period)
        if key in versions and versions[key] != doc.file_sha256:
            raise ValueError("同年度同类型包含多个版本，请先选择本次使用的版本")
        versions[key] = doc.file_sha256
    periods = sorted({d.effective_period for d in docs})
    missing = [f"{year}年缺少{kind}报告" for year in range(int(periods[0]), int(periods[-1]) + 1)
               for kind in ("AR", "ESG") if (kind, str(year)) not in versions]
    content = json.dumps({"documents": sorted(_identity(d) for d in docs), "as_of_date": as_of_date.isoformat()}, sort_keys=True)
    return ReportSet(report_set_id="CONNSET-" + hashlib.sha256(content.encode()).hexdigest()[:24].upper(),
        company_id=docs[0].company_id, company=docs[0].company,
        document_ids=sorted(d.document_id for d in docs),
        document_fingerprints={d.document_id: d.file_sha256 for d in docs},
        periods=periods, as_of_date=as_of_date, coverage_gaps=missing)


def _directory(root):
    path = root / "backend/runtime/connectivity/report_sets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _local_records(root):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(_directory(root).glob("CONNSET-*.json"))]


def report_set_records(root, *, strict_remote=False):
    from .connectivity_catalog import remote_enabled
    records = {r["report_set"]["report_set_id"]: r for r in _local_records(root)}
    state = "local"
    if remote_enabled():
        from .supabase_adapter import get_demo_task_client, SupabaseError
        try:
            rows = get_demo_task_client().select_table("cases", filters={"case_id": "like.CONNSET-*",
                "tenant_id": "is.null", "sample_type": "eq.public"}, select="case_id,metadata", service=True)
            for row in rows:
                record = (row.get("metadata") or {}).get("connectivity_report_set")
                if record:
                    records[record["report_set"]["report_set_id"]] = record
            state = "supabase"
        except SupabaseError:
            if strict_remote:
                raise
            state = "snapshot_only_remote_unavailable"
    return list(records.values()), state


def registered_set_documents(root):
    records, _ = report_set_records(root)
    return [ReportDocument.model_validate(d) for record in records for d in record.get("documents", [])]


def save_report_set(root, report_set: ReportSet, documents):
    from .connectivity_catalog import remote_enabled
    selected = [d for d in documents if d.document_id in report_set.document_ids]
    if make_report_set(selected, report_set.as_of_date) != report_set:
        raise ValueError("资料集合身份或来源指纹不一致")
    record = {"report_set": report_set.model_dump(mode="json"), "documents": [d.model_dump(mode="json") for d in selected]}
    if remote_enabled():
        from .supabase_adapter import get_demo_task_client
        get_demo_task_client().insert_table("cases", [{"case_id": report_set.report_set_id, "tenant_id": None,
            "sample_type": "public", "company_name": report_set.company, "ticker": report_set.company_id,
            "source_snapshot_id": report_set.report_set_id, "t0": str(report_set.as_of_date), "import_status": "ready",
            "metadata": {"product": "connectivity", "connectivity_report_set": record}}],
            service=True, upsert=True, on_conflict="case_scope")
    # 共享保存成功后才更新本地镜像，不将失败写入伪装为成功。
    from .connectivity_catalog import _lock
    import uuid
    with _lock:
        target = _directory(root) / (report_set.report_set_id + ".json")
        temporary = target.with_suffix("." + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
    return report_set


def create_report_set(root: Path, body: ReportSetRequest):
    from .connectivity_extraction import load_registry
    docs = {d.document_id: d for d in load_registry(root)}
    if any(key not in docs for key in body.document_ids):
        raise ValueError("资料集合包含未登记文档")
    selected = canonical_documents([docs[key] for key in body.document_ids])
    report_set = make_report_set(selected, body.as_of_date)
    return save_report_set(root, report_set, selected)


def resolve_documents(root, request):
    """按请求解析不可变集合或兼容的旧报告对。
    本次观察日期必须与集合一致，不能借重试改变信息可得时点。
    集合内元数据重新计算身份，来源字节仍交给读取器核验。
    旧报告对可以转换为事项范围，原数值入口保持独立。
    """
    from .connectivity_extraction import load_registry
    if request.report_set_id:
        records, _ = report_set_records(root)
        record = next((r for r in records if r["report_set"]["report_set_id"] == request.report_set_id), None)
        if record is None:
            raise ValueError("多年资料集合未登记")
        report_set = ReportSet.model_validate(record["report_set"])
        docs = [ReportDocument.model_validate(d) for d in record["documents"]]
        if request.as_of_date and request.as_of_date != report_set.as_of_date:
            raise ValueError("观察时点与不可变资料集合不一致，请创建新集合")
        if make_report_set(docs, report_set.as_of_date) != report_set:
            raise ValueError("资料集合来源身份已变化")
        return report_set, docs
    docs = [d for d in load_registry(root) if d.case_id == request.pair_id]
    return make_report_set(docs, request.as_of_date or date.today()), canonical_documents(docs)
