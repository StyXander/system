"""生成测试清单：测试文件数、测试项数、需要联网的项目和默认离线边界。

竞赛手册要求评委能一键复现环境，因此必须说清楚"从零安装后跑的是什么、
哪些用例天生需要外网"，不能让评委在自己的机器上靠猜。
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "backend/tests"

# 需要真实外网的标志：显式标记或访问巨潮/供应商域名。
NETWORK_MARKERS = ("network", "cninfo_live", "live_smoke")
NETWORK_CALLS = ("check_knowledge_sources_live", "verify_standard_annual_report_sources", "api.deepseek.com", "static.cninfo.com")


def collected_tests() -> dict[str, list[str]]:
    """用 collect-only 拿每个文件的测试项标识，不执行任何用例。"""

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only", "backend/tests"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode not in (0, 1):
        raise SystemExit(f"收集失败：{proc.stdout[-800:]}{proc.stderr[-800:]}")
    buckets: dict[str, list[str]] = defaultdict(list)
    for line in proc.stdout.splitlines():
        match = re.match(r"(backend/tests/test_[^:]+\.py)::([^\[\s]+)", line.strip())
        if match:
            buckets[match.group(1)].append(match.group(2))
    return buckets


def file_needs_network(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return any(marker in text for marker in NETWORK_MARKERS) or any(token in text for token in NETWORK_CALLS)


def main() -> int:
    buckets = collected_tests()
    total = sum(len(items) for items in buckets.values())
    online = sorted(
        name for name in buckets
        if (ROOT / name).is_file() and file_needs_network(ROOT / name)
    )

    lines = [
        "# 测试清单",
        "",
        f"- 测试文件数：{len(buckets)}",
        f"- 测试项数：{total}",
        f"- 需要外网的测试文件数：{len(online)}",
        "",
        "## 默认离线边界",
        "",
        "`pytest backend/tests -q` 在未配置 DEEPSEEK_API_KEY、未设置 AUDITTRACE_ONSITE_LIVE_SAMPLE、"
        "且没有 .env 的干净环境下应当全部通过：真实模型调用一律被就绪门禁挡成确定性备用或失败关闭，"
        "外部抓取类用例只在显式开启现场开关时执行。",
        "",
        "## 需要外网的测试文件",
        "",
    ]
    lines += [f"- `{name}`" for name in online] or ["- 无"]
    lines += [
        "",
        "## 复现命令",
        "",
        "```bash",
        "python3 -m venv backend/.venv",
        "backend/.venv/bin/python -m pip install -r requirements-dev.txt",
        "backend/.venv/bin/python -m pytest -q",
        "```",
        "",
        "Windows PowerShell 等价命令见 README_RUN.md 第一节。",
        "",
    ]
    out = ROOT / "docs" / "TEST_INVENTORY.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写入 docs/TEST_INVENTORY.md：{len(buckets)} 个文件 / {total} 项，联网文件 {len(online)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
