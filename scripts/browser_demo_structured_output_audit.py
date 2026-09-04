#!/usr/bin/env python3
"""Audit real browser exports for the judge demo and onsite sample pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
import fitz


RUN_WAIT_MS = 420_000


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_download(page, selector: str, path: Path) -> None:
    with page.expect_download(timeout=30_000) as download_info:
        page.locator(selector).click()
    download_info.value.save_as(str(path))


def pdf_text(path: Path) -> str:
    with fitz.open(path) as document:
        return "\n".join(page.get_text() for page in document)


def pdf_pages(path: Path) -> int:
    with fitz.open(path) as document:
        return document.page_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8003")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--company", default="002594")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "company": args.company,
        "console_errors": [],
        "page_errors": [],
        "failed_requests": [],
        "http_errors": [],
        "exports": {},
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="zh-CN",
            accept_downloads=True,
            reduced_motion="reduce",
        )
        page = context.new_page()
        page.set_default_timeout(30_000)
        page.on("console", lambda msg: report["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        page.on("requestfailed", lambda request: report["failed_requests"].append({"url": request.url, "failure": request.failure}))
        page.on("response", lambda response: report["http_errors"].append({"status": response.status, "url": response.url}) if response.status >= 400 else None)

        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=20_000)
        page.wait_for_selector("#demo-start:not([disabled])", timeout=45_000)
        page.locator("#demo-start").click()
        page.wait_for_selector("#demo-result:not([hidden])", timeout=RUN_WAIT_MS)
        run_id = page.locator("#demo-result-summary .is-run .demo-summary-value").inner_text().strip()
        main_rows = page.locator("#demo-structured-table-body tr").count()

        main_json = output_dir / "main-result.json"
        main_csv = output_dir / "main-result.csv"
        main_pdf = output_dir / "main-result.pdf"
        save_download(page, "#demo-download-json", main_json)
        save_download(page, "#demo-download-csv", main_csv)
        page.emulate_media(media="print")
        page.pdf(path=str(main_pdf), format="A4", print_background=True)
        page.emulate_media(media="screen")

        main_json_data = json.loads(main_json.read_text(encoding="utf-8"))
        main_csv_text = main_csv.read_text(encoding="utf-8-sig")
        main_csv_rows = list(csv.reader(main_csv_text.splitlines()))
        main_pdf_text = pdf_text(main_pdf)
        report["exports"]["main"] = {
            "run_id": run_id,
            "table_rows": main_rows,
            "json_schema": main_json_data.get("schema_version"),
            "json_has_run": main_json_data.get("run", {}).get("run_id") == run_id,
            "json_has_calculation_process": bool(main_json_data.get("calculation_process"))
            and all(item.get("calculation_process") for item in main_json_data.get("calculation_process", [])),
            "csv_has_run": run_id in main_csv_text,
            "csv_header": main_csv_rows[0] if main_csv_rows else [],
            "csv_has_calculation_process": bool(main_csv_rows)
            and "calculation_process" in main_csv_rows[0]
            and any(row[-1].strip() for row in main_csv_rows[1:] if row),
            "csv_lines": len([line for line in main_csv_text.splitlines() if line.strip()]),
            "pdf_pages": pdf_pages(main_pdf),
            "pdf_has_title": "结果摘要" in main_pdf_text and "结构化结果明细" in main_pdf_text,
            "pdf_has_ai_notice": "AI生成内容" in main_pdf_text,
            "files": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in (main_json, main_csv, main_pdf)},
        }

        # The secondary entry points are intentionally collapsed in the judge-facing
        # header; expand the native details element before opening the live sample.
        secondary_menu = page.locator("#demo-secondary-menu")
        if not secondary_menu.get_attribute("open"):
            secondary_menu.locator("summary").click()
        page.locator("#demo-open-live-sample").click()
        page.locator("#demo-live-company").fill(args.company)
        page.locator("#demo-live-sample-form").evaluate("form => form.requestSubmit()")
        page.wait_for_selector("#demo-live-output-actions:not([hidden])", timeout=RUN_WAIT_MS)
        live_task_id = page.locator("#demo-live-task-id").inner_text().strip()
        live_run_text = page.locator("#demo-live-result").inner_text()
        live_rows = page.locator("#demo-live-structured-table-body tr").count()

        live_json = output_dir / "live-sample.json"
        live_csv = output_dir / "live-sample.csv"
        live_pdf = output_dir / "live-sample.pdf"
        save_download(page, "#demo-live-download-json", live_json)
        save_download(page, "#demo-live-download-csv", live_csv)
        page.locator("body").evaluate("body => body.classList.add('print-live-sample')")
        page.emulate_media(media="print")
        page.pdf(path=str(live_pdf), format="A4", print_background=True)
        page.emulate_media(media="screen")
        page.locator("body").evaluate("body => body.classList.remove('print-live-sample')")
        page.screenshot(path=str(output_dir / "live-sample-result.png"), full_page=False, animations="disabled")

        live_json_data = json.loads(live_json.read_text(encoding="utf-8"))
        live_csv_text = live_csv.read_text(encoding="utf-8-sig")
        live_csv_rows = list(csv.reader(live_csv_text.splitlines()))
        live_pdf_text = pdf_text(live_pdf)
        report["exports"]["live"] = {
            "task_id": live_task_id,
            "state": page.locator("#demo-live-task-state").inner_text().strip(),
            "table_rows": live_rows,
            "json_schema": live_json_data.get("schema_version"),
            "json_has_task": live_json_data.get("task", {}).get("task_id") == live_task_id,
            "json_has_calculation_process": bool(live_json_data.get("calculation_process"))
            and all(item.get("calculation_process") for item in live_json_data.get("calculation_process", [])),
            "csv_has_task": live_task_id in live_csv_text,
            "csv_header": live_csv_rows[0] if live_csv_rows else [],
            "csv_has_calculation_process": bool(live_csv_rows)
            and "calculation_process" in live_csv_rows[0]
            and any(row[-1].strip() for row in live_csv_rows[1:] if row),
            "csv_lines": len([line for line in live_csv_text.splitlines() if line.strip()]),
            "pdf_pages": pdf_pages(live_pdf),
            "pdf_has_title": "评审现场样例接入" in live_pdf_text,
            "pdf_has_ai_notice": "AI生成内容" in live_pdf_text,
            "result_head": live_run_text[:1000],
            "files": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in (live_json, live_csv, live_pdf)},
        }
        context.close()
        browser.close()

    checks = [
        report["exports"]["main"]["table_rows"] > 0,
        report["exports"]["main"]["json_schema"] == "audittrace_structured_export_v1",
        report["exports"]["main"]["json_has_run"],
        report["exports"]["main"]["json_has_calculation_process"],
        report["exports"]["main"]["csv_has_run"],
        report["exports"]["main"]["csv_has_calculation_process"],
        report["exports"]["main"]["pdf_has_title"],
        report["exports"]["main"]["pdf_has_ai_notice"],
        report["exports"]["live"]["table_rows"] > 0,
        report["exports"]["live"]["json_schema"] == "audittrace_live_sample_export_v1",
        report["exports"]["live"]["json_has_task"],
        report["exports"]["live"]["json_has_calculation_process"],
        report["exports"]["live"]["csv_has_task"],
        report["exports"]["live"]["csv_has_calculation_process"],
        report["exports"]["live"]["pdf_has_title"],
        report["exports"]["live"]["pdf_has_ai_notice"],
        not report["console_errors"],
        not report["page_errors"],
        not report["failed_requests"],
        not report["http_errors"],
    ]
    report["passed"] = all(checks)
    summary_path = output_dir / "structured-output-audit.json"
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Audit written to: {summary_path}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
