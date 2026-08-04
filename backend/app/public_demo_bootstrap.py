"""Render 构建阶段准备官方来源临时缓存和标准案例 RAG。

构建失败会阻止发布，避免把缺少来源或空索引的版本继续上线。
启动服务后仍保留按需补取兜底，但正常部署应直接复用构建结果。
"""

from __future__ import annotations

import json
from pathlib import Path

from .data import CASE_ID
from .rag import prepare_index
from .source_cache import ensure_standard_sources


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    source_result = ensure_standard_sources(WORKSPACE_ROOT)
    rag_result = prepare_index(WORKSPACE_ROOT, case_id=CASE_ID, force=False)
    print(
        json.dumps(
            {
                "public_demo_bootstrap": "ready",
                "sources": source_result,
                "rag": {
                    "status": rag_result["status"],
                    "source_count": rag_result["source_count"],
                    "chunk_count": rag_result["chunk_count"],
                    "rebuilt": rag_result["rebuilt"],
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
