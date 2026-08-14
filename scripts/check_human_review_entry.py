"""在真实页面验收巨潮任务的两个人工复核入口与共享演示边界。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--shared-public",
        action="store_true",
        help="断言共享公开演示只允许本机草稿，不保存正式人工签字。",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        for width, height in ((1440, 1000), (390, 844)):
            console_errors: list[str] = []
            failed_requests: list[str] = []
            context = browser.new_context(
                viewport={"width": width, "height": height},
                locale="zh-CN",
                reduced_motion="reduce",
            )
            page = context.new_page()
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.on(
                "requestfailed",
                lambda request: failed_requests.append(request.url),
            )
            page.goto(
                f"{args.url.rstrip('/')}?view=project&task={args.task_id}",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            page.locator("#cninfo-next-action:not([hidden])").wait_for(timeout=30_000)
            page.locator('[data-cninfo-next-action="fields"]').wait_for()
            labels = page.locator("[data-cninfo-next-action]").all_inner_texts()
            field_label = "第 1 步：查看字段判断位置" if args.shared_public else "第 1 步：核对字段"
            review_label = "第 3 步：查看结果复核位置" if args.shared_public else "第 3 步：保存结果复核"
            assert field_label in labels
            assert review_label in labels
            action_top = page.locator("#cninfo-next-action").bounding_box()
            steps_top = page.locator("#cninfo-step-list").bounding_box()
            assert action_top and steps_top and action_top["y"] < steps_top["y"]

            page.locator('[data-cninfo-next-action="fields"]').click()
            heading = page.locator("#cninfo-field-review-heading")
            heading.wait_for(state="visible")
            page.wait_for_function(
                "document.activeElement?.id === 'cninfo-field-review-heading'",
                timeout=30_000,
            )
            instruction = page.locator("#cninfo-review-instruction").inner_text()
            assert page.locator("[data-cninfo-field-action]").count() == 18
            enabled_field_actions = page.locator(
                "[data-cninfo-field-action]:not([disabled])"
            ).count()
            if args.shared_public:
                assert "公开演示只读" in instruction
                assert enabled_field_actions == 0
            else:
                assert "操作顺序" in instruction
                assert enabled_field_actions == 18
            field_path = args.output_dir / f"{width}x{height}-field-review.png"
            page.screenshot(path=str(field_path), full_page=False, animations="disabled")

            page.goto(
                f"{args.url.rstrip('/')}?view=project&task={args.task_id}",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            page.locator('[data-cninfo-next-action="review"]').wait_for(timeout=30_000)
            page.locator('[data-cninfo-next-action="review"]').click()
            review_heading = page.locator("#review-heading")
            review_heading.wait_for(state="visible", timeout=30_000)
            assert page.locator("#wb-backend-review-status").evaluate(
                "el => document.activeElement === el"
            )
            mode_note = page.locator("#review-mode-note").inner_text()
            formal_review_disabled = page.locator("#wb-save-backend-review").is_disabled()
            if args.shared_public:
                assert "公开演示边界" in mode_note
                assert formal_review_disabled
                assert "公开演示不保存正式复核" in page.locator(
                    "#wb-save-backend-review"
                ).inner_text()
            else:
                assert "操作顺序" in mode_note
                assert not formal_review_disabled
                assert "保存本次复核" in page.locator(
                    "#wb-save-backend-review"
                ).inner_text()
            assert not page.locator("#wb-save-local-review").is_disabled()
            page.locator("#wb-backend-review-status").select_option(label="暂缓")
            page.locator("#wb-backend-reviewer").fill("浏览器验收角色")
            page.locator("#wb-backend-review-note").fill("仅验证本机演示草稿入口。")
            page.locator("#wb-save-local-review").click()
            assert "本机草稿已保存" in page.locator("#wb-backend-toast").inner_text()
            review_heading.scroll_into_view_if_needed()
            review_path = args.output_dir / f"{width}x{height}-result-review.png"
            page.screenshot(path=str(review_path), full_page=False, animations="disabled")

            reports.append(
                {
                    "viewport": f"{width}x{height}",
                    "labels": labels,
                    "field_actions": 18,
                    "formal_field_actions_enabled": enabled_field_actions,
                    "local_result_draft_saved": True,
                    "formal_result_review_disabled": formal_review_disabled,
                    "console_errors": console_errors,
                    "failed_requests": failed_requests,
                    "screenshots": [str(field_path), str(review_path)],
                }
            )
            assert not console_errors
            assert not failed_requests
            context.close()
        browser.close()

    summary = args.output_dir / "human-review-entry-summary.json"
    summary.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
