"""浏览器流程验收：真实提交一次核对，观察阶段条、结果与刷新恢复。

只做观察与截图，不修改业务数据。四视口截图见 browser_acceptance.py。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/integration-20261021/screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.getenv("AUDITTRACE_ACCEPTANCE_URL", "http://127.0.0.1:8901/")


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
        for _ in range(180):
            page.wait_for_timeout(2000)
            text = page.inner_text("#cn-message")
            if page.locator('#cn-results').is_visible() and page.locator('[data-goto]').count():
                break
            if text.startswith("失败"):
                raise AssertionError(text)
        report["elapsed_seconds"] = round(time.monotonic() - started, 1)
        report["message"] = page.inner_text("#cn-message")[:400]
        page.wait_for_timeout(2000)
        report["result_shot"] = _shot(page, "flow__result")
        assert page.locator('[data-goto]').count(), report["message"]
        started = time.monotonic()
        page.locator('[data-goto]').first.click()
        page.locator('#cn-focus-title').wait_for(state='visible')
        report["detail_seconds"] = round(time.monotonic()-started, 3)
        report["detail_shot"] = _shot(page, "flow__detail")
        started = time.monotonic()
        page.locator('[data-reader]:visible').first.click()
        image = page.locator('#cn-reader-docs img').first
        image.wait_for(state='visible')
        page.wait_for_function("""() => { const img=document.querySelector('#cn-reader-docs img');
            return img && img.complete && img.naturalWidth > 0; }""")
        report["source_seconds"] = round(time.monotonic()-started, 3)
        report["source_shot"] = _shot(page, "flow__source")
        page.click('#cn-reader-close')
        # 刷新恢复
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        report["after_reload_message"] = page.inner_text("#cn-message")[:400]
        page.wait_for_function("document.querySelector('#connectivity-root').dataset.awView === 'result'")
        assert page.locator('#cn-focus-title').is_visible()
        report["reload_restored"] = True
        report["reload_shot"] = _shot(page, "flow__reload")
        # 历史记录
        page.locator('[data-view="history"]').first.click()
        page.locator('[data-open-task]').first.wait_for(state='visible')
        report["history_shot"] = _shot(page, "flow__history")
        page.locator('[data-open-task]').first.click()
        page.wait_for_function("document.querySelector('#connectivity-root').dataset.awView === 'result'")
        assert page.locator('#cn-focus-title').is_visible()
        report["history_restored"] = True
        assert not report["console_errors"], report["console_errors"]
        page.close()
        browser.close()
    (ROOT / "outputs/integration-20261021/browser_repair.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if not k.endswith("_shot")}, ensure_ascii=False)[:700])
    return 0


def _shot(page, name: str) -> str:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    return path.name


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        (ROOT / "outputs/integration-20261021/browser_repair.json").write_text(
            json.dumps({"passed": False, "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
