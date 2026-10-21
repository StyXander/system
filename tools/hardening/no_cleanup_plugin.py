"""pytest 本地插件：跳过 tmpdir 的会话结束清理。

本机沙箱对 pytest 创建的临时目录存在枚举权限问题，`cleanup_dead_symlinks`
会在会话结束时抛 PermissionError 或挂起。清理只影响临时文件，不影响用例结果。
"""
from __future__ import annotations

import _pytest.tmpdir as _tmpdir


def _noop(root):  # noqa: ANN001
    return None


_tmpdir.cleanup_dead_symlinks = _noop
