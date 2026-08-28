#!/usr/bin/env python3
"""批次 7 真实浏览器验收：四视口静态门槛与 15 案交互主链。

无障碍报告同时保留 axe violations 与 incomplete；critical/serious 的
incomplete 不再被静默计成“axe 0”。渐变导致的 color-contrast incomplete
单独列为人工复核项，必须由保守实色对比度计算和截图人工检查共同裁决。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "backend" / "competition_demo_cases.json"
DEFAULT_OUT = ROOT / "artifacts" / "competition-demo-batch7" / "browser"
# 竞赛计划要求的 1440×900 保留；1440×1000 是既有工作台基线，作为额外视口复核。
VIEWPORTS = ((1440, 900), (1440, 1000), (1024, 768), (768, 1024), (390, 844))


def text(page: Page, selector: str) -> str:
    return (page.locator(selector).first.inner_text() or "").strip()


def observers(page: Page, report: dict[str, Any]) -> None:
    page.on(
        "console",
        lambda message: report["console"].append(
            {"type": message.type, "text": (message.text or "")[:500]}
        )
        if message.type in {"error", "warning"}
        else None,
    )
    page.on("pageerror", lambda error: report["page_errors"].append(str(error)[:500]))
    page.on(
        "requestfailed",
        lambda request: report["failed_requests"].append(
            {"method": request.method, "url": request.url[:300], "error": str(request.failure)[:300]}
        ),
    )
    page.on(
        "response",
        lambda response: report["http_errors"].append(
            {"status": response.status, "url": response.url[:300]}
        )
        if response.status >= 400
        else None,
    )


def static_audit(base_url: str, output: Path) -> dict[str, Any]:
    rows = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        axe = Axe()
        for width, height in VIEWPORTS:
            context = browser.new_context(
                viewport={"width": width, "height": height}, locale="zh-CN", reduced_motion="reduce"
            )
            page = context.new_page()
            row: dict[str, Any] = {
                "viewport": f"{width}x{height}",
                "console": [],
                "page_errors": [],
                "failed_requests": [],
                "http_errors": [],
            }
            observers(page, row)
            response = page.goto(base_url, wait_until="domcontentloaded")
            page.wait_for_selector("#demo-start:not([disabled])", timeout=45_000)
            page.wait_for_load_state("networkidle", timeout=20_000)
            document_width = page.evaluate("document.documentElement.scrollWidth")
            overflow_nodes = page.evaluate(
                """() => [...document.querySelectorAll('body *')]
                .map((element) => {
                  const rect = element.getBoundingClientRect();
                  return {
                    tag: element.tagName,
                    id: element.id || null,
                    class_name: String(element.className || '').slice(0, 160),
                    left: Math.round(rect.left),
                    right: Math.round(rect.right),
                    width: Math.round(rect.width),
                  };
                })
                .filter((item) => item.right > document.documentElement.clientWidth + 1 || item.left < -1)
                .sort((a, b) => b.right - a.right)
                .slice(0, 30)"""
            )
            duplicate_ids = page.evaluate(
                """() => { const ids=[...document.querySelectorAll('[id]')].map(n=>n.id);
                return ids.filter((id,index)=>ids.indexOf(id)!==index); }"""
            )
            axe_result = axe.run(
                page,
                options={"resultTypes": ["violations", "incomplete", "passes", "inapplicable"]},
            ).response
            row.update(
                {
                    "http_status": response.status if response else None,
                    "document_width": document_width,
                    "horizontal_overflow": document_width > width,
                    "overflow_nodes": overflow_nodes,
                    "duplicate_ids": duplicate_ids,
                    "axe": {
                        "violations": axe_result["violations"],
                        "incomplete": axe_result["incomplete"],
                        "passes_count": len(axe_result["passes"]),
                    },
                }
            )
            page.screenshot(path=str(output / f"static-{width}x{height}.png"), full_page=True)
            rows.append(row)
            context.close()
        browser.close()

    blocking = []
    manual_review = []
    for row in rows:
        for finding in row["axe"]["violations"]:
            if finding.get("impact") in {"critical", "serious", "moderate"}:
                blocking.append({"viewport": row["viewport"], "kind": "violation", "id": finding["id"]})
        for finding in row["axe"]["incomplete"]:
            item = {"viewport": row["viewport"], "kind": "incomplete", "id": finding["id"], "impact": finding.get("impact")}
            if finding["id"] == "color-contrast":
                manual_review.append(item)
            elif finding.get("impact") in {"critical", "serious", "moderate"}:
                blocking.append(item)
        for key in ("console", "page_errors", "failed_requests", "http_errors"):
            if row[key]:
                blocking.append({"viewport": row["viewport"], "kind": key, "count": len(row[key])})
        if row["horizontal_overflow"] or row["duplicate_ids"]:
            blocking.append({"viewport": row["viewport"], "kind": "dom", "overflow": row["horizontal_overflow"], "duplicate_ids": row["duplicate_ids"]})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "viewports": rows,
        "blocking_findings": blocking,
        "manual_review_findings": manual_review,
        "passed_automated": not blocking,
    }


def run_case(page: Page, base_url: str, case_id: str, output: Path, label: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "case_id": case_id,
        "label": label,
        "console": [],
        "page_errors": [],
        "failed_requests": [],
        "http_errors": [],
    }
    observers(page, report)
    page.goto(f"{base_url}?case={case_id}", wait_until="domcontentloaded")
    page.wait_for_selector("#demo-start:not([disabled])", timeout=45_000)
    report["selected_name"] = text(page, "#demo-current-case-name")
    report["selected_meta"] = text(page, "#demo-current-case-meta")
    with page.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith("/api/runs"),
        timeout=420_000,
    ) as response_info:
        page.locator("#demo-start").click()
    run_response = response_info.value
    try:
        run_payload = run_response.json()
    except Exception:
        run_payload = {}
    model_check = run_payload.get("model_check") or {}
    report["run_response"] = {
        "http_status": run_response.status,
        "run_id": run_payload.get("run_id"),
        "run_completeness": run_payload.get("run_completeness"),
        "model_status": model_check.get("status"),
        "provider_call_count": run_payload.get("provider_call_count"),
        "input_tokens": run_payload.get("input_tokens"),
        "output_tokens": run_payload.get("output_tokens"),
        "cache_hit": run_payload.get("cache_hit"),
        "fresh_model_success": bool(
            model_check.get("status") == "model_success"
            and run_payload.get("run_completeness") in {
                "complete_full_analysis",
                "complete_public_prescreen",
                "complete_public_prescreen_with_gaps",
            }
            and int(run_payload.get("provider_call_count") or 0) > 0
            and not run_payload.get("cache_hit")
        ),
    }
    page.wait_for_selector("#demo-result:not([hidden])", timeout=420_000)
    report["result"] = {
        "state": text(page, "#demo-result-state"),
        "gate": text(page, "#demo-gate"),
        "summary": text(page, "#demo-result-summary"),
        "items_count": page.locator("#demo-result-items > *").count(),
        "stage_rail": text(page, "#demo-stage-rail"),
    }
    page.screenshot(path=str(output / f"{label}-result.png"), full_page=False, animations="disabled")
    page.locator("#demo-open-evidence").click()
    page.wait_for_selector("#demo-evidence-drawer[open]", timeout=15_000)
    report["evidence_head"] = text(page, "#demo-evidence-drawer-body")[:1000]
    page.locator("#demo-evidence-drawer").evaluate("el => el.close()")
    page.locator("#demo-open-agents").click()
    page.wait_for_selector("#demo-agent-drawer[open]", timeout=15_000)
    report["agents_head"] = text(page, "#demo-agent-drawer-body")[:1200]
    page.locator("#demo-agent-drawer").evaluate("el => el.close()")
    page.locator("#demo-reset").click()
    page.wait_for_timeout(700)
    report["after_reset"] = {
        "result_hidden": page.locator("#demo-result").is_hidden(),
        "start_enabled": not page.locator("#demo-start").is_disabled(),
    }
    result_ok = report["result"]["items_count"] > 0 and any(
        marker in report["result"]["state"] for marker in ("成功", "降级")
    )
    report["passed"] = bool(
        result_ok
        and report["after_reset"]["result_hidden"]
        and report["after_reset"]["start_enabled"]
        and not any(report[key] for key in ("console", "page_errors", "failed_requests", "http_errors"))
    )
    return report


def interaction_audit(base_url: str, output: Path, *, mobile_featured: bool) -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = []
    videos = output / "video"
    videos.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, locale="zh-CN", reduced_motion="reduce",
            record_video_dir=str(videos), record_video_size={"width": 1440, "height": 1000},
        )
        page = context.new_page()
        video = page.video
        for index, case in enumerate(manifest["cases"], start=1):
            label = f"desktop-{index:02d}-{case['case_id']}"
            print(f"[browser] {label}", flush=True)
            rows.append(run_case(page, base_url, case["case_id"], output, label))
        context.close()
        video_path = output / "AuditTrace-15case-backup-demo.webm"
        video.save_as(str(video_path))

        if mobile_featured:
            for index, case_id in enumerate(manifest["featured_case_ids"], start=1):
                context = browser.new_context(
                    viewport={"width": 390, "height": 844}, locale="zh-CN", reduced_motion="reduce"
                )
                page = context.new_page()
                label = f"mobile-A{index}-{case_id}"
                print(f"[browser] {label}", flush=True)
                rows.append(run_case(page, base_url, case_id, output, label))
                context.close()
        browser.close()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_runs": rows,
        "desktop_case_count": len(manifest["cases"]),
        "mobile_featured_count": len(manifest["featured_case_ids"]) if mobile_featured else 0,
        "passed": all(row["passed"] for row in rows),
        "backup_video": str(output / "AuditTrace-15case-backup-demo.webm"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--interaction-only", action="store_true")
    parser.add_argument("--mobile-featured", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    if not args.interaction_only:
        reports["static"] = static_audit(args.base_url, args.output_dir)
        (args.output_dir / "static-audit.json").write_text(
            json.dumps(reports["static"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if not args.static_only:
        reports["interaction"] = interaction_audit(
            args.base_url, args.output_dir, mobile_featured=args.mobile_featured
        )
        (args.output_dir / "interaction-audit.json").write_text(
            json.dumps(reports["interaction"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    passed = all(
        report.get("passed", report.get("passed_automated", False)) for report in reports.values()
    )
    print(json.dumps({"passed": passed, "reports": list(reports)}, ensure_ascii=False), flush=True)
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
