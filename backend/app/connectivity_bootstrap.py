"""部署时准备登记报告；失败逐份列明，不以其他版本代替原件。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi import HTTPException
from .connectivity_extraction import load_registry, ensure_source


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing-sources", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare_sources(Path(__file__).resolve().parents[2], args.allow_missing_sources), ensure_ascii=False))
