"""用隔离目录检验部署首次获取；只下载已登记公开URL，不改现有原件缓存。"""
from concurrent.futures import ThreadPoolExecutor
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "backend"))
from app.connectivity_extraction import load_registry,ensure_source


def main(document_ids=None):
    documents = load_registry(ROOT)
    if document_ids:
        unknown=set(document_ids)-{d.document_id for d in documents}
        if unknown:raise ValueError("未登记的来源："+",".join(sorted(unknown)))
        documents=[d for d in documents if d.document_id in document_ids]
    parent = ROOT / "backend/runtime/connectivity/download-verification"
    parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent,prefix="fresh-") as temporary:
        isolated = Path(temporary)
        def fetch(document):
            try:
                path = ensure_source(isolated,document)
                result = {"document_id":document.document_id,"status":"available",
                    "source_kind":document.source_kind,"bytes":path.stat().st_size}
            except Exception as error:
                cause = error.__cause__
                result = {"document_id":document.document_id,"status":"unavailable",
                    "reason":getattr(error,"detail",type(error).__name__),
                    "download_code":getattr(cause,"code",type(cause).__name__),
                    "http_status":getattr(cause,"detail",{}).get("status_code")}
            print(json.dumps(result,ensure_ascii=True),flush=True)
            return result
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(fetch,documents))
    proof = {"checked_at":datetime.now(timezone.utc).isoformat(),"source_cache_was_empty":True,
        "registered":len(results),"available":sum(r["status"]=="available" for r in results),"sources":results}
    suffix = "-selected" if document_ids else ""
    target = ROOT / f"outputs/connectivity-v1-acceptance/source-downloads{suffix}.json"
    target.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")
    return 0 if proof["registered"]==proof["available"] else 1


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--document",action="append")
    raise SystemExit(main(parser.parse_args().document))
