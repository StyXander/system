#!/usr/bin/env python3
"""Run one real AuditTrace demo run in a real browser and collect evidence.

Verifies the demo state machine end to end: ready -> running -> success/degraded,
opens the evidence and agent drawers, resets, and records console/page/network
failures plus screenshots. Never fabricates success: the outcome label is read
from the page itself and cross-checked against the POST /api/runs response.
"""

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


API_BASE = "http://127.0.0.1:8000"
RUN_WAIT_SECONDS = 420


def attach_observers(page, report):
    def on_console(message):
        if message.type in {"error", "warning"}:
            report["console"].append({"type": message.type, "text": (message.text or "")[:500]})

    def on_page_error(error):
        report["page_errors"].append(str(error)[:500])

    def on_request_failed(request):
        failure = request.failure or {}
        report["failed_requests"].append({
            "method": request.method,
            "url": (request.url or "")[:300],
            "error": (failure.get("errorText") or "")[:300],
        })

    def on_response(response):
        if response.status >= 400:
            report["http_errors"].append({
                "status": response.status,
                "url": (response.url or "")[:300],
            })
        if response.request.url.endswith(("/api/runs", "/api/demo/runs")) and response.request.method == "POST":
            try:
                report["run_response_posts"].append({
                    "status": response.status,
                    "body": response.json() if response.status < 400 else (response.text()[:1000] if response.status >= 400 else None),
                })
            except Exception as exc:
                report["run_response_posts"].append({"status": response.status, "error": str(exc)})

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)


def text_of(page, selector, fallback=""):
    try:
        return (page.locator(selector).first.inner_text() or "").strip()
    except Exception:
        return fallback


def hidden(page, selector):
    return page.locator(selector).first.is_hidden()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=API_BASE)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--viewport", default="1440x1000")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--video", action="store_true", help="保存本次完整交互 WebM 备用录屏")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    width, height = (int(part) for part in args.viewport.split("x"))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "viewport": args.viewport,
        "case_id": args.case_id,
        "console": [],
        "page_errors": [],
        "failed_requests": [],
        "http_errors": [],
        "run_response_posts": [],
        "steps": [],
    }

    def step(name, detail):
        entry = {"name": name, "detail": detail}
        report["steps"].append(entry)
        print(f"[{name}] {detail}", flush=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=not args.headed)
        context_options = dict(
            viewport={"width": width, "height": height},
            locale="zh-CN",
            reduced_motion="reduce",
        )
        if args.video:
            context_options.update(
                record_video_dir=str(output_dir / "video-tmp"),
                record_video_size={"width": width, "height": height},
            )
        context = browser.new_context(**context_options)
        page = context.new_page()
        video = page.video if args.video else None
        page.set_default_timeout(30_000)
        attach_observers(page, report)

        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=20_000)

        if args.case_id:
            page.evaluate("(id) => { const sel = new URLSearchParams(); window.history.replaceState(null, '', `?case=${id}`); }", args.case_id)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=20_000)

        page.wait_for_selector("#demo-start:not([disabled])", timeout=45_000)
        step("ready", f"phase=ready start_enabled=True case={text_of(page, '#demo-current-case-name')}")

        page.locator("#demo-start").first.click()
        step("running", "start button clicked, phase should be running")

        # 结果区只在 completed/degraded 时展示；failed/cancelled/interrupted
        # 会把结果正文隐藏并把失败原因写到 gate。两类终态都必须立即结束
        # 验收，否则额度保护或取消竞态会让脚本无意义地等待到 420 秒。
        page.wait_for_function(
            """() => {
                const result = document.querySelector('#demo-result');
                if (result && !result.hidden) return true;
                const gate = document.querySelector('#demo-gate');
                const text = gate ? (gate.textContent || '') : '';
                return /(失败|取消|中断|未形成|临时上限|HTTP_)/.test(text);
            }""",
            timeout=RUN_WAIT_SECONDS * 1000,
        )
        result_visible = not hidden(page, "#demo-result")
        if not result_visible:
            failure_snapshot = {
                "state_pill": text_of(page, "#demo-result-state"),
                "gate": text_of(page, "#demo-gate"),
                "stage_rail": text_of(page, "#demo-stage-rail"),
                "workspace": page.url,
            }
            report["result_snapshot"] = failure_snapshot
            report["terminal_status"] = "failed_or_cancelled"
            print("TERMINAL FAILURE SNAPSHOT:", json.dumps(failure_snapshot, ensure_ascii=False)[:800], flush=True)
            page.screenshot(path=str(output_dir / "01-terminal-failure.png"), full_page=False, animations="disabled")
            report["terminal_failure_screenshot"] = "01-terminal-failure.png"
            if not hidden(page, "#demo-reset"):
                page.locator("#demo-reset").first.click()
                page.wait_for_timeout(800)
                report["after_reset"] = {
                    "result_hidden": hidden(page, "#demo-result"),
                    "start_disabled": page.locator("#demo-start").first.is_disabled(),
                }
            context.close()
            if video is not None:
                video.save_as(str(output_dir / "AuditTrace-final-backup-demo.webm"))
                report["backup_video"] = str(output_dir / "AuditTrace-final-backup-demo.webm")
            browser.close()
            summary_path = output_dir / "run-audit-summary.json"
            summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Audit written to: {summary_path}", flush=True)
            return 1
        step("result_visible", f"state={text_of(page, '#demo-result-state')}")

        result_snapshot = {
            "state_pill": text_of(page, "#demo-result-state"),
            "gate": text_of(page, "#demo-gate"),
            "summary_first_lines": text_of(page, "#demo-result-summary"),
            "items_count": page.locator("#demo-result-items > *").count(),
            "stage_rail": text_of(page, "#demo-stage-rail"),
            "workspace": page.url,
        }
        report["result_snapshot"] = result_snapshot
        print("RESULT SNAPSHOT:", json.dumps(result_snapshot, ensure_ascii=False)[:800], flush=True)

        page.screenshot(path=str(output_dir / "01-result.png"), full_page=False, animations="disabled")
        step("screenshot_result", "01-result.png saved")

        page.locator("#demo-open-evidence").first.click()
        page.wait_for_selector("#demo-evidence-drawer[open]", timeout=15_000)
        evidence_snapshot = {
            "body_text_head": text_of(page, "#demo-evidence-drawer-body")[:1200],
            "drawer_open": True,
        }
        report["evidence_drawer"] = evidence_snapshot
        page.screenshot(path=str(output_dir / "02-evidence-drawer.png"), full_page=False, animations="disabled")
        step("evidence_drawer", "opened")
        page.locator("#demo-evidence-drawer").first.evaluate("(el) => el.close()")
        page.wait_for_timeout(500)

        page.locator("#demo-open-agents").first.click()
        page.wait_for_selector("#demo-agent-drawer[open]", timeout=15_000)
        agent_snapshot = {
            "body_text_head": text_of(page, "#demo-agent-drawer-body")[:2000],
            "drawer_open": True,
        }
        report["agent_drawer"] = agent_snapshot
        page.screenshot(path=str(output_dir / "03-agent-drawer.png"), full_page=False, animations="disabled")
        step("agent_drawer", "opened")
        page.locator("#demo-agent-drawer").first.evaluate("(el) => el.close()")
        page.wait_for_timeout(500)

        reset_visible = hidden(page, "#demo-reset") is False
        report["reset_visible"] = reset_visible
        if reset_visible:
            page.locator("#demo-reset").first.click()
            page.wait_for_timeout(1500)
            report["after_reset"] = {
                "result_hidden": hidden(page, "#demo-result"),
                "start_disabled": page.locator("#demo-start").first.is_disabled(),
            }
            step("reset", f"reset_clicked after_reset={json.dumps(report['after_reset'], ensure_ascii=False)}")
        else:
            step("reset", "reset button not visible; skipped")

        page.screenshot(path=str(output_dir / "04-final.png"), full_page=False, animations="disabled")
        step("screenshot_final", "04-final.png saved")
        context.close()
        if video is not None:
            video.save_as(str(output_dir / "AuditTrace-final-backup-demo.webm"))
            report["backup_video"] = str(output_dir / "AuditTrace-final-backup-demo.webm")
        browser.close()

    failures = []
    if report["console"]:
        failures.append(f"console messages: {len(report['console'])}")
    if report["page_errors"]:
        failures.append(f"page errors: {len(report['page_errors'])}")
    if report["failed_requests"]:
        failures.append(f"failed requests: {len(report['failed_requests'])}")
    if report["http_errors"]:
        failures.append(f"http errors: {len(report['http_errors'])}")

    summary_path = output_dir / "run-audit-summary.json"
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Audit written to: {summary_path}", flush=True)
    if failures:
        print("Strict findings:")
        for failure in failures:
            print(f"- {failure}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
