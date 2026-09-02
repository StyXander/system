"""仓库根 pytest 配置：保证干净克隆可直接收集，且每次运行使用独立临时目录。

没有本文件时，脱离 pytest.ini 的裸 pytest 会既找不到 testpaths 也导入不了
backend.app；而 pytest 默认复用同一个 pytest-of-<user> 基目录，一旦被其他
账号或沙箱令牌创建过，后续运行在清理阶段就会以 PermissionError 打断大量用例。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent

# 让 backend.app.* 在任何调用方式下都能被导入，不依赖 pytest.ini 的 pythonpath。
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """未显式给出 --basetemp 时，为本次会话分配一个全新的临时基目录。

    只有本目录是自己创建的，因此清理时永远不会碰到别人拥有的目录。
    """
    if not config.getoption("basetemp", default=None):
        config.option.basetemp = tempfile.mkdtemp(prefix="audittrace-pytest-")
