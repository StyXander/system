"""浏览器流程验收：真实提交一次核对，观察阶段条、结果与刷新恢复。

只做观察与截图，不修改业务数据。四视口截图见 browser_acceptance.py。
"""
from __future__ import annotations

import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/integration-20261021/screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8899/"


def main() -> int:
    report: dict = {"console_errors": []}
    with sync_playwright() as worker:
        browser = worker.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda msg: report["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.goto(BASE + "#connectivity-root", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        page.select_option("#cn-pair", "000858-2025")
        page.wait_for_timeout(400)
        page.click("#cn-next")
        page.wait_for_timeout(700)
        report["step2_shot"] = _shot(page, "flow__step2_settings")
        # 运行方式在「高级设置：速度与模型调用」折叠区内，先展开再选择。
        page.click("text=高级设置")
        page.wait_for_timeout(600)
        page.select_option("#cn-mode", "calculation_only")
        page.wait_for_timeout(300)
        report["advanced_shot"] = _shot(page, "flow__step2_advanced")
        page.click("#cn-next")
        page.wait_for_timeout(700)
        report["step3_shot"] = _shot(page, "flow__step3_confirm")
        page.click("#cn-run")
        report["submitted_at"] = time.strftime("%H:%M:%S")
        started = time.monotonic()
        for _ in range(120):
            page.wait_for_timeout(2000)
            text = page.inner_text("#cn-message")
            if any(word in text for word in ("完成", "失败", "已生成", "条关系")):
                break
        report["elapsed_seconds"] = round(time.monotonic() - started, 1)
        report["message"] = page.inner_text("#cn-message")[:400]
        page.wait_for_timeout(2000)
        report["result_shot"] = _shot(page, "flow__result")
        # 展开第一条关系，验证五项前提与算式可见
        try:
            page.click(".cn-check summary", timeout=5000)
            page.wait_for_timeout(800)
            report["detail_shot"] = _shot(page, "flow__detail")
        except Exception as error:
            report["detail_error"] = type(error).__name__
        # 刷新恢复
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        report["after_reload_message"] = page.inner_text("#cn-message")[:400]
        report["reload_shot"] = _shot(page, "flow__reload")
        # 历史记录
        try:
            page.click("text=历史记录")
            page.wait_for_timeout(2000)
            report["history_shot"] = _shot(page, "flow__history")
        except Exception as error:
            report["history_error"] = type(error).__name__
        page.close()
        browser.close()
    (ROOT / "outputs/integration-20261021/browser_flow.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if not k.endswith("_shot")}, ensure_ascii=False)[:700])
    return 0


def _shot(page, name: str) -> str:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    return path.name


if __name__ == "__main__":
    raise SystemExit(main())
