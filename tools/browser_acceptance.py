"""浏览器验收：四视口首页 + 真实提交一次核对 + 刷新恢复。

只做观察与截图，不修改任何业务数据。结果写入 outputs/integration-20261021/。
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/integration-20261021/screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8899/"
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
    report: dict = {"viewports": {}, "flow": {}, "console_errors": []}
    with sync_playwright() as worker:
        browser = worker.chromium.launch()
        for name, size in VIEWPORTS.items():
            page = browser.new_page(viewport=size)
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
            page.close()

        # 真实提交一次（仅计算模式），观察阶段条、结果与刷新恢复
        page = browser.new_page(viewport=VIEWPORTS["desktop"])
        page.on("console", lambda msg: report["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.goto(BASE + "#connectivity-root", wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        page.select_option("#cn-pair", "000858-2025")
        page.select_option("#cn-mode", "calculation_only")
        page.click("#cn-run")
        report["flow"]["submitted_at"] = time.strftime("%H:%M:%S")
        started = time.monotonic()
        done = False
        for _ in range(90):
            page.wait_for_timeout(2000)
            text = page.inner_text("#cn-message")
            if "完成" in text or "失败" in text or "已生成" in text:
                done = True
                break
        report["flow"]["elapsed_seconds"] = round(time.monotonic() - started, 1)
        report["flow"]["finished"] = done
        report["flow"]["message"] = page.inner_text("#cn-message")[:300]
        page.wait_for_timeout(1500)
        report["flow"]["result_shot"] = shot(page, "flow__result")
        # 展开第一条关系明细
        try:
            page.click(".cn-check summary", timeout=4000)
            page.wait_for_timeout(700)
            report["flow"]["detail_shot"] = shot(page, "flow__detail")
        except Exception as error:
            report["flow"]["detail_error"] = f"{type(error).__name__}"
        # 刷新恢复
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        report["flow"]["after_reload_message"] = page.inner_text("#cn-message")[:300]
        report["flow"]["reload_shot"] = shot(page, "flow__reload")
        page.close()
        browser.close()
    (ROOT / "outputs/integration-20261021/browser_acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: (v if k != "viewports" else list(v)) for k, v in report.items()},
                     ensure_ascii=False)[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
