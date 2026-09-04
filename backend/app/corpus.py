"""标准股份年报全文的统一文件命名和可用性判据。"""

from __future__ import annotations

from pathlib import Path


# 下载脚本、pytest 闸门和交付包扫描必须共用这一条 glob，避免台账改名后各自失配。
STANDARD_CORPUS_GLOB = "标准股份*.pdf"


def standard_corpus_paths(root: Path) -> tuple[Path, ...]:
    """返回根目录下按名称排序的标准股份年报文件。"""

    base = Path(root)
    return tuple(sorted(base.glob(STANDARD_CORPUS_GLOB)))


def is_local_corpus_available(root: Path) -> bool:
    """判断本地是否至少存在一份年报全文，不读取配置或环境变量。"""

    return any(path.is_file() for path in standard_corpus_paths(root))


def corpus_filename(announcement_title: str) -> str:
    """把台账公告标题转换为下载脚本和闸门都能识别的文件名。"""

    title = str(announcement_title).strip()
    return title if title.lower().endswith(".pdf") else f"{title}.pdf"
