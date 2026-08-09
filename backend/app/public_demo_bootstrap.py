"""Render 构建阶段准备官方来源临时缓存和标准案例 RAG。

构建失败会阻止发布，避免把缺少来源或空索引的版本继续上线。
启动服务后仍保留按需补取兜底，但正常部署应直接复用构建结果。
构建步骤只处理登记的标准公开案例，不扫描仓库中的任意 PDF。
官方原件首先经过固定域名、体积和哈希校验，成功后才允许建索引。
来源缓存失败会立即终止构建，不能用上一次不明文件继续发布。
索引准备复用当前来源指纹，未变化时不做无意义的重复建库。
索引清单必须报告就绪、来源数量和块数量，空字段不能被忽略。
构建输出是机器可读摘要，部署日志不打印年报正文或本机绝对路径。
公开演示准备成功只说明来源和索引可用，不表示人工复核已经完成。
模型传输许可仍由案例与项目授权控制，构建阶段不会自动开启调用。
运行时兜底用于应对临时实例磁盘，不应掩盖构建产物缺失的部署错误。
工作区根依据模块位置固定解析，Render 启动目录变化不会写错缓存位置。
标准案例编号来自冻结数据模块，命令行不能临时替换为任意案例。
强制重建保持关闭，避免每次部署丢弃仍可复验的已发布版本。
任何异常都让进程以失败退出，使托管平台能够阻止错误版本上线。
本脚本不启动 web 服务，也不创建后台轮询进程，执行结束应自然退出。
部署就绪边界是官方来源技术校验和确定性索引成功，不是审计结论成立。
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
