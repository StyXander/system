"""浏览器验收：四视口首页与工作台；真实操作链统一使用browser_flow.py。

只做观察与截图，不修改任何业务数据。结果写入 outputs/integration-20261021/。
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import os

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/integration-20261021/screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.getenv("AUDITTRACE_ACCEPTANCE_URL", "http://127.0.0.1:8901/")
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 1024, "height": 768},
    "portrait": {"width": 768, "height": 1024},
    "mobile": {"width": 390, "height": 844},
}


def shot(page, name: str) -> str:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    return str(path.name)


def main() -> int:
    report: dict = {"viewports": {}, "console_errors": []}
    with sync_playwright() as worker:
        browser = worker.chromium.launch()
        for name, size in VIEWPORTS.items():
            page = browser.new_page(viewport=size)
            page.on("console", lambda msg: report["console_errors"].append(msg.text) if msg.type == "error" else None)
            page.goto(BASE, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            files = [shot(page, f"home__{name}")]
            # 工作台首屏：确认表单与报告下拉真实可选
            page.goto(BASE + "#connectivity-root", wait_until="domcontentloaded")
            page.wait_for_timeout(900)
            files.append(shot(page, f"workbench__{name}"))
            options = page.eval_on_selector_all("#cn-pair option", "els => els.map(e => e.value).filter(Boolean)")
            report["viewports"][name] = {"files": files, "pair_options": options,
                                         "scroll_width": page.evaluate("document.documentElement.scrollWidth"),
                                         "client_width": page.evaluate("document.documentElement.clientWidth")}
            assert options, f"{name}: 报告对未加载"
            assert report["viewports"][name]["scroll_width"] <= report["viewports"][name]["client_width"], name
            page.close()

        browser.close()
    (ROOT / "outputs/integration-20261021/browser_acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: (v if k != "viewports" else list(v)) for k, v in report.items()},
                     ensure_ascii=False)[:800])
    assert not report["console_errors"], report["console_errors"]
    return 0


if __name__ == "__main__":
    sys.exit(main())
