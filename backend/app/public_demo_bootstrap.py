"""Render 构建阶段准备官方来源临时缓存和标准案例 RAG。

默认构建失败会阻止发布，避免把缺少来源或空索引的版本继续上线。
Render 可以显式传入 ``--allow-missing-sources``：仅当官方来源返回 HTTP 403 时，
允许网站以降级状态发布；标准案例保持 not_built，不能运行或冒充 RAG 就绪。
启动服务后仍保留按需补取兜底，但正常部署应直接复用构建结果。
构建步骤只处理登记的标准公开案例，不扫描仓库中的任意 PDF。
官方原件首先经过固定域名、体积和哈希校验，成功后才允许建索引。
来源缓存失败默认终止构建；允许降级时也不会复用来源缺失下的旧索引。
索引准备复用当前来源指纹，未变化时不做无意义的重复建库。
索引清单必须报告就绪、来源数量和块数量，空字段不能被忽略。
构建输出是机器可读摘要，部署日志不打印年报正文或本机绝对路径。
公开演示准备成功只说明来源和索引可用，不表示人工复核已经完成。
模型传输许可仍由案例与项目授权控制，构建阶段不会自动开启调用。
运行时兜底用于应对临时实例磁盘，不应掩盖构建产物缺失的部署错误。
工作区根依据模块位置固定解析，Render 启动目录变化不会写错缓存位置。
标准案例编号来自冻结数据模块，命令行不能临时替换为任意案例。
强制重建保持关闭，避免每次部署丢弃仍可复验的已发布版本。
除显式允许的官方 HTTP 403 降级外，任何异常都让进程失败退出。
本脚本不启动 web 服务，也不创建后台轮询进程，执行结束应自然退出。
部署就绪边界是官方来源技术校验和确定性索引成功，不是审计结论成立。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .data import CASE_ID
from .rag import prepare_index
from .source_cache import ensure_standard_sources


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def prepare_public_demo(*, allow_missing_sources: bool = False) -> dict[str, Any]:
    """校验年报并建索引；显式降级仅接受官方源的 403 拒绝。"""
    try:
        source_result = ensure_standard_sources(WORKSPACE_ROOT)
    except ValueError as error:
        if not allow_missing_sources or "HTTP 403" not in str(error):
            raise
        return {
            "public_demo_bootstrap": "degraded",
            "sources": {
                "status": "unavailable",
                "source_count": 0,
                "downloaded": [],
                "reused": [],
                "reason_code": "OFFICIAL_SOURCE_HTTP_403",
                "boundary": "官方来源站拒绝了构建环境请求；标准案例来源与 RAG 未就绪。",
            },
            "rag": {
                "status": "not_built",
                "source_count": 0,
                "chunk_count": 0,
                "rebuilt": False,
                "reason_code": "standard_corpus_missing",
            },
        }
    rag_result = prepare_index(WORKSPACE_ROOT, case_id=CASE_ID, force=False)
    return {
        "public_demo_bootstrap": "ready",
        "sources": source_result,
        "rag": {
            "status": rag_result["status"],
            "source_count": rag_result["source_count"],
            "chunk_count": rag_result["chunk_count"],
            "rebuilt": rag_result["rebuilt"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="准备公开演示的来源缓存和 RAG 索引。")
    parser.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="仅官方来源返回 HTTP 403 时允许网站以标准案例 not_built 状态部署。",
    )
    args = parser.parse_args()
    print(json.dumps(prepare_public_demo(allow_missing_sources=args.allow_missing_sources), ensure_ascii=False))


if __name__ == "__main__":
    main()
