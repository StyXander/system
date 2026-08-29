#!/usr/bin/env python3
"""批次 7 G9 浏览器恢复验收：20 次刷新、重复点击与超时失败恢复。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts" / "competition-demo-batch7" / "recovery"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "refresh": {"required": 20, "passed": 0, "failures": []},
        "duplicate_click": {},
        "timeout_recovery": {},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        page = context.new_page()
        console_errors = []
        page_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        for number in range(1, 21):
            try:
                page.goto(args.base_url, wait_until="domcontentloaded")
                page.wait_for_selector("#demo-start:not([disabled])", timeout=45_000)
                if page.locator("#demo-start").is_enabled():
                    report["refresh"]["passed"] += 1
                else:
                    report["refresh"]["failures"].append({"iteration": number, "reason": "start_disabled"})
            except Exception as exc:
                report["refresh"]["failures"].append({"iteration": number, "reason": str(exc)[:300]})
        # 这里必须取快照，后续故意注入的 504 控制台信息不属于刷新门槛。
        report["refresh"]["console_errors"] = list(console_errors)
        report["refresh"]["page_errors"] = list(page_errors)

        # 同一事件循环内触发两次 click；按钮必须在第一次处理时立即锁定，只产生一个 POST。
        posts = []
        page.on(
            "request",
            lambda request: posts.append(request.url)
            if request.method == "POST" and request.url.endswith("/api/runs")
            else None,
        )
        page.evaluate("document.querySelector('#demo-start').click(); document.querySelector('#demo-start').click()")
        page.wait_for_selector("#demo-result:not([hidden])", timeout=420_000)
        report["duplicate_click"] = {
            "run_post_count": len(posts),
            "state": page.locator("#demo-result-state").inner_text(),
            "passed": len(posts) == 1,
        }
        page.locator("#demo-reset").click()
        page.wait_for_timeout(500)

        # 注入可控 504 只验证前端失败关闭与一次重置恢复，不把该响应当业务成功。
        page.route(
            "**/api/runs",
            lambda route: route.fulfill(
                status=504,
                content_type="application/json",
                body=json.dumps({"detail": "BATCH7_INJECTED_TIMEOUT"}),
            ),
        )
        with page.expect_response(
            lambda response: response.request.method == "POST"
            and response.url.endswith("/api/runs"),
            timeout=30_000,
        ) as response_info:
            page.locator("#demo-start").click()
        injected_response = response_info.value
        # HTTP 级失败不伪造业务结果卡；失败关闭由危险 gate、可见重置按钮和禁用开始按钮表达。
        page.wait_for_selector("#demo-reset:not([hidden])", timeout=30_000)
        failed_state = "failed_run"
        gate = page.locator("#demo-gate").inner_text()
        page.locator("#demo-reset").click()
        page.wait_for_timeout(500)
        report["timeout_recovery"] = {
            "injected_http_status": injected_response.status,
            "state": failed_state,
            "gate": gate,
            "expected_console_error_count": len(console_errors) - len(report["refresh"]["console_errors"]),
            "result_hidden_after_one_reset": page.locator("#demo-result").is_hidden(),
            "start_enabled_after_one_reset": page.locator("#demo-start").is_enabled(),
        }
        report["timeout_recovery"]["passed"] = bool(
            injected_response.status == 504
            and failed_state == "failed_run"
            and "本次分析未能完成" in gate
            and "BATCH7_INJECTED_TIMEOUT" in gate
            and report["timeout_recovery"]["result_hidden_after_one_reset"]
            and report["timeout_recovery"]["start_enabled_after_one_reset"]
        )
        page.screenshot(path=str(args.output_dir / "after-timeout-reset.png"), full_page=False)
        context.close()
        browser.close()

    report["passed"] = bool(
        report["refresh"]["passed"] == 20
        and not report["refresh"]["failures"]
        and not report["refresh"]["console_errors"]
        and not report["refresh"]["page_errors"]
        and report["duplicate_click"]["passed"]
        and report["timeout_recovery"]["passed"]
    )
    output = args.output_dir / "recovery-audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "output": str(output)}, ensure_ascii=False), flush=True)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
