"""部署时准备登记报告；失败逐份列明，不以其他版本代替原件。"""
from __future__ import annotations

import argparse
import json
import hashlib
from functools import lru_cache
from datetime import datetime, timezone
import pymupdf
from pathlib import Path

from fastapi import HTTPException
from .connectivity_extraction import load_registry, ensure_source, source_path
from .source_viewer import PDF_ACCESS_LOCK


def prepare_sources(root: Path, allow_missing_sources: bool = False) -> dict:
    results = []
    for document in load_registry(root):
        try:
            ensure_source(root, document)
            results.append({"document_id": document.document_id, "status": "available", "source_kind": document.source_kind})
        except HTTPException as error:
            results.append({"document_id": document.document_id, "status": "unavailable", "reason": error.detail})
            if not allow_missing_sources:
                raise
    return {"registered": len(results), "available": sum(r["status"] == "available" for r in results), "sources": results}


@lru_cache(maxsize=32)
def _inspect_local_pdf(path: str, expected_hash: str, expected_pages: int, size: int, modified_ns: int) -> dict:
    """按版本、长度和修改时刻缓存昂贵的逐页检查；文件改变立即重新校验。"""
    with Path(path).open("rb") as handle:
        actual = hashlib.file_digest(handle, "sha256").hexdigest()
    if actual != expected_hash:
        return {"ready": False, "status": "hash_mismatch", "reason": "原件与登记哈希不符"}
    with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
        pages = len(pdf)
        for page in pdf:
            page.get_text()
        if not pages or (expected_pages and pages != expected_pages):
            return {"ready": False, "status": "page_count_mismatch", "actual_pages": pages, "reason": "原件页数与登记不符"}
        pdf[0].get_pixmap(matrix=pymupdf.Matrix(.1, .1))
    return {"ready": True, "status": "ready", "actual_pages": pages, "reason": "哈希、页数、逐页解析及预览通过"}


def source_readiness(root: Path, *, pair_id: str | None = None) -> dict:
    """只检查本地精确版本，不在健康请求里发起下载或用站点200替代业务就绪。"""
    from fastapi import HTTPException
    grouped = {}
    documents = load_registry(root)
    if pair_id and pair_id not in {d.case_id for d in documents}:
        raise HTTPException(404, "报告对未登记")
    for document in documents:
        if pair_id and document.case_id != pair_id:
            continue
        item = {"document_id": document.document_id, "ready": False, "status": "missing",
                "expected_pages": document.pages, "source_kind": document.source_kind,
                "remote_status": "not_probed", "reason": "原件未缓存；需运行来源准备，远端连通性未测"}
        path = source_path(root, document)
        if path.is_file():
            try:
                stat = path.stat()
                item.update(_inspect_local_pdf(str(path), document.file_sha256, document.pages, stat.st_size, stat.st_mtime_ns))
            except (OSError, ValueError, RuntimeError) as error:
                item.update(status="unreadable", reason=f"原件无法解析：{type(error).__name__}")
        group = grouped.setdefault(document.case_id, {"pair_id": document.case_id, "documents": [], "report_types": []})
        group["documents"].append(item)
        group["report_types"].append(document.report_type)
    for group in grouped.values():
        group["ready"] = {"AR", "ESG"}.issubset(group.pop("report_types")) and all(d["ready"] for d in group["documents"])
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "health_kind": "business_sources",
            "ready": bool(grouped) and all(p["ready"] for p in grouped.values()), "pairs": list(grouped.values()),
            "remote_status": "not_probed", "note": "业务源就绪与服务存活分开；本接口不探测模型或外网"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing-sources", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare_sources(Path(__file__).resolve().parents[2], args.allow_missing_sources), ensure_ascii=False))
