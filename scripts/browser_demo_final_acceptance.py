"""审迹智链竞赛终版·浏览器最终验收：分阶段进度、结果、证据、Agent、程序映射、
补充证据父子运行、四视口、axe、console/network、打印样式与下载。

用法（仓库根目录）：
  .agents\\tools\\browser-qa\\.venv\\Scripts\\python.exe scripts\\browser_demo_final_acceptance.py --output-dir artifacts/competition-final-enhancement-20260824/g8-browser/{viewport} --viewport 1440x1000 --headed
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from axe_inject import enable_axe, run_axe  # noqa: E402  同源注入 axe，避免被 CSP 拒绝

API_BASE = "http://127.0.0.1:8000"
RUN_WAIT_SECONDS = 240


def attach_observers(page, report):
    def on_console(message):
        entry = {"type": message.type, "text": message.text[:400]}
        report["console"].append(entry)
        if message.type in ("error", "warning"):
            print(f"[console:{message.type}] {entry['text'][:180]}", flush=True)

    def on_page_error(error):
        report["page_errors"].append(str(error)[:500])
        print(f"[page_error] {str(error)[:200]}", flush=True)

    def on_request_failed(request):
        report["failed_requests"].append(f"{request.method} {request.url[:240]} ({request.failure})")
        print(f"[failed_request] {request.method} {request.url[:160]}", flush=True)

    def on_response(response):
        if response.status >= 400:
            report["http_errors"].append(f"{response.status} {response.url[:240]}")
            print(f"[http_error] {response.status} {response.url[:160]}", flush=True)

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)


def keyboard_check(page):
    """键盘可操作性：Enter 打开、Esc 关闭并归还焦点、Space 切换折叠区。

    抽屉是原生 <dialog> + showModal()，Esc 关闭与焦点归还原生就提供；
    这里验证的是"确实可用"，不是重新实现它。
    """

    result = {}
    trigger = page.locator("#demo-open-evidence")
    trigger.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(250)
    result["enter_opens_dialog"] = page.evaluate(
        "() => Boolean(document.getElementById('demo-evidence-drawer')?.open)"
    )
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)
    result["escape_closes_dialog"] = page.evaluate(
        "() => !document.getElementById('demo-evidence-drawer')?.open"
    )
    result["focus_returns_to_trigger"] = page.evaluate(
        "() => document.activeElement?.id === 'demo-open-evidence'"
    )
    toggler = page.locator("[aria-expanded]").first
    before = toggler.get_attribute("aria-expanded")
    toggler.focus()
    page.keyboard.press("Space")
    page.wait_for_timeout(150)
    after = toggler.get_attribute("aria-expanded")
    body_id = toggler.get_attribute("aria-controls")
    result["space_toggles_aria_expanded"] = before != after
    result["aria_expanded_before_after"] = [before, after]
    if body_id:
        # 真实不变量：aria-expanded=false 时被控区域必须 hidden，true 时必须可见。
        observed = page.evaluate(
            """(id) => {
              const button = document.querySelector(`[aria-controls=\"${id}\"]`);
              const body = document.getElementById(id);
              if (!button || !body) return null;
              return {
                expanded: button.getAttribute("aria-expanded"),
                hidden: Boolean(body.hidden),
              };
            }""",
            body_id,
        )
        result["collapsible_state"] = observed
        result["hidden_matches_aria_expanded"] = bool(
            observed and observed["hidden"] == (observed["expanded"] != "true")
        )
    return result


AXE_KEYS = ("axe_executed", "axe_version", "violations", "incomplete", "passes", "contrast_nodes")


def axe_state(page, report, name, step_log=None):
    """对当前 UI 状态单独跑一次 axe，并把"工具没执行"和"页面没违规"分开登记。

    只有 axe 真的执行过才允许记违规数；否则该状态判为未验收，不能拿空的
    violations 冒充通过——这正是之前 CSP 阻止内联注入时犯过的错。
    """

    available = page.evaluate("() => Boolean(window.axe && typeof window.axe.run === 'function')")
    if not available:
        entry = {"axe_executed": False, "tool_error": "当前页面上下文没有可用的 window.axe.run"}
    else:
        try:
            scanned = run_axe(page)
            entry = {key: scanned.get(key) for key in AXE_KEYS}
            entry.setdefault("axe_executed", False)
        except Exception as error:  # noqa: BLE001
            entry = {"axe_executed": False, "tool_error": f"{type(error).__name__}: {str(error)[:200]}"}
    report["axe_states"][name] = entry
    if step_log is not None:
        step_log(
            f"axe:{name}",
            f"executed={entry.get('axe_executed')} violations={len(entry.get('violations') or [])} "
            f"incomplete={len(entry.get('incomplete') or [])}",
        )
    return entry


def print_expand_check(page):
    """打印强制展开的真实不变量：屏上折叠的区块在打印媒体下必须可见。"""

    return page.evaluate(
        """() => {
          const bodies = [...document.querySelectorAll('.demo-collapsible-body')];
          const collapsed = bodies.filter((el) => el.hidden);
          const printed = collapsed.filter((el) => el.getClientRects().length > 0);
          return {
            collapsible_bodies: bodies.length,
            collapsed_on_screen: collapsed.length,
            collapsed_printed_visible: printed.length,
            all_collapsed_printed: collapsed.length === 0 || printed.length === collapsed.length,
          };
        }"""
    )


def overflow(page):
    return page.evaluate("() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth })")


def text_of(page, selector, fallback=""):
    try:
        node = page.locator(selector).first
        if node.count() == 0:
            return fallback
        return node.inner_text()
    except Exception:
        return fallback


def hidden(page, selector):
    try:
        return page.locator(selector).first.is_hidden()
    except Exception:
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=API_BASE)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--viewport", default="1440x1000")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--skip-supplement", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    width, height = (int(part) for part in args.viewport.split("x"))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "viewport": args.viewport,
        "console": [],
        "page_errors": [],
        "failed_requests": [],
        "http_errors": [],
        "steps": [],
        "axe_states": {},
    }

    def step(name, detail):
        report["steps"].append({"name": name, "detail": detail})
        print(f"[{name}] {str(detail)[:220]}", flush=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=not args.headed)
        context = browser.new_context(viewport={"width": width, "height": height}, locale="zh-CN", reduced_motion="reduce")
        page = context.new_page()
        page.set_default_timeout(30_000)
        attach_observers(page, report)
        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=30_000)
        page.wait_for_selector("#demo-start:not([disabled])", timeout=60_000)
        step("ready", f"landing case={text_of(page, '#demo-current-case-name') or '未显示'} start_enabled=True")

        # 生产 CSP 不变：axe 走同源虚拟 URL 注入一次，后续各状态直接复用。
        report["axe_injection"] = str(enable_axe(page, ROOT).relative_to(ROOT))
        axe_state(page, report, "landing", step)

        # 定位页：知识底座真实数量
        page.locator("#demo-enter-workspace").click()
        page.wait_for_timeout(600)
        knowledge = text_of(page, "#demo-knowledge-grid")
        kb_note = text_of(page, "#demo-knowledge-note")
        report["knowledge_base"] = {"grid_head": knowledge[:400], "note": kb_note[:300]}
        step("knowledge_base", f"grid={knowledge[:120]} note={kb_note[:120]}")
        axe_state(page, report, "case_select", step)

        # 工作台
        page.locator("a.demo-positioning-enter").click()
        page.wait_for_timeout(500)
        step("workspace", "entered workspace")
        axe_state(page, report, "workspace", step)

        # 主运行：观察真实分阶段进度
        page.locator("#demo-start").first.click()
        step("running", "start clicked")
        observed = []
        running_scanned = False
        deadline = time.time() + RUN_WAIT_SECONDS
        while time.time() < deadline:
            visible = not hidden(page, "#demo-result")
            if visible:
                break
            rail = text_of(page, "#demo-stage-rail")
            if not observed or rail != observed[-1]:
                observed.append(rail)
                step("progress", f"rail={rail[:200]}")
                if rail and not running_scanned:
                    running_scanned = True
                    axe_state(page, report, "running", step)
            page.wait_for_timeout(120)
        page.wait_for_selector("#demo-result:not([hidden])", timeout=60_000)
        report["staged_progress_count"] = len(observed)
        step("result_visible", f"state={text_of(page, '#demo-result-state')}")

        result_snapshot = {
            "state_pill": text_of(page, "#demo-result-state"),
            "gate": text_of(page, "#demo-gate")[:300],
            "summary": text_of(page, "#demo-result-summary")[:600],
            "items_count": page.locator("#demo-result-items > *").count(),
            "procedure_map": text_of(page, "#demo-procedure-map")[:400],
            "procedure_version": text_of(page, "#demo-procedure-version"),
        }
        report["result_snapshot"] = result_snapshot
        page.screenshot(path=str(output_dir / "01-result.png"), full_page=True, animations="disabled")
        step("result_snapshot", "saved 01-result.png")

        result_axe = axe_state(page, report, "result", step)
        result_axe["keyboard"] = keyboard_check(page)
        step("keyboard", result_axe["keyboard"])
        # keyboard_check 用 Space 展开了一个折叠区，这里扫的就是"展开态"
        axe_state(page, report, "collapsible_expanded", step)

        # 证据抽屉
        page.locator("#demo-open-evidence").click()
        page.wait_for_selector("#demo-evidence-drawer[open]", timeout=15_000)
        report["evidence_drawer"] = {"text_head": text_of(page, "#demo-evidence-drawer-body")[:1200]}
        page.screenshot(path=str(output_dir / "02-evidence.png"), full_page=False)
        axe_state(page, report, "evidence_drawer", step)
        page.locator("#demo-evidence-drawer").evaluate("(el) => el.close()")
        # Agent 抽屉
        page.locator("#demo-open-agents").click()
        page.wait_for_selector("#demo-agent-drawer[open]", timeout=15_000)
        report["agent_drawer"] = {"text_head": text_of(page, "#demo-agent-drawer-body")[:1500]}
        page.screenshot(path=str(output_dir / "03-agents.png"), full_page=False)
        axe_state(page, report, "agent_drawer", step)
        page.locator("#demo-agent-drawer").evaluate("(el) => el.close()")

        # 补充证据父子运行
        if not args.skip_supplement:
            page.locator("#demo-supplement-rerun").click()
            page.wait_for_selector("#demo-supplement-drawer[open]", timeout=15_000)
            page.wait_for_selector(".demo-supplement-sample", timeout=15_000)
            report["supplement_samples"] = text_of(page, "#demo-supplement-samples")[:400]
            page.locator(".demo-supplement-sample").first.click()
            page.locator("#demo-supplement-apply").click()
            page.wait_for_selector("#demo-supplement-diff:not([hidden])", timeout=90_000)
            page.wait_for_timeout(800)
            diff = text_of(page, "#demo-supplement-summary")[:600]
            report["supplement_diff"] = diff
            step("supplement", f"diff={diff[:160]}")
            page.screenshot(path=str(output_dir / "04-supplement.png"), full_page=True)
            page.locator("#demo-supplement-drawer").evaluate("(el) => el.close()")

        # 打印样式快照：先验证"折叠区在打印时强制展开"这条不变量，再扫打印预览
        page.emulate_media(media="print")
        page.wait_for_timeout(400)
        report["print_expand"] = print_expand_check(page)
        step("print_expand", report["print_expand"])
        axe_state(page, report, "print_preview", step)
        page.screenshot(path=str(output_dir / "05-print-style.png"), full_page=True)
        page.emulate_media(media="screen")

        # 下载 JSON 与 CSV（真实下载事件）
        try:
            with page.expect_download(timeout=30_000) as download_info:
                page.locator("#demo-download-json").click()
            download = download_info.value
            download_path = output_dir / download.suggested_filename
            download.save_as(download_path)
            report["download_json"] = {"filename": download.suggested_filename, "bytes": download_path.stat().st_size}
            step("download_json", f"{download.suggested_filename} ({download_path.stat().st_size} bytes)")
        except Exception as error:  # noqa: BLE001
            report["download_json"] = {"error": str(error)[:200]}
            step("download_json", f"FAILED {str(error)[:120]}")

        try:
            with page.expect_download(timeout=30_000) as download_info:
                page.locator("#demo-download-csv").click()
            download = download_info.value
            download_path = output_dir / download.suggested_filename
            download.save_as(download_path)
            report["download_csv"] = {"filename": download.suggested_filename, "bytes": download_path.stat().st_size}
            step("download_csv", f"{download.suggested_filename} ({download_path.stat().st_size} bytes)")
        except Exception as error:  # noqa: BLE001
            report["download_csv"] = {"error": str(error)[:200]}
            step("download_csv", f"FAILED {str(error)[:120]}")

        # 溢出检查
        overflow_result = overflow(page)
        report["overflow"] = overflow_result
        step("overflow", f"scrollWidth={overflow_result['scrollWidth']} clientWidth={overflow_result['clientWidth']}")

        # 现场样例 11 步（热缓存企业 000001）
        if not args.skip_live:
            page.locator("#demo-open-live-sample").click()
            page.wait_for_selector("#demo-live-sample-drawer[open]", timeout=15_000)
            page.locator("#demo-live-company").fill("000001")
            page.locator("#demo-live-sample-form button[type=submit], #demo-live-submit").first.click()
            steps_seen = []
            deadline = time.time() + 240
            while time.time() < deadline:
                live_state = text_of(page, "#demo-live-task-state")
                if live_state and live_state not in steps_seen:
                    steps_seen.append(live_state)
                if live_state in ("处理完成", "失败"):
                    break
                page.wait_for_timeout(900)
            report["live_steps_seen"] = steps_seen
            report["live_result"] = text_of(page, "#demo-live-result")[:600]
            step("live_sample", f"states={steps_seen} result={report['live_result'][:120]}")
            page.screenshot(path=str(output_dir / "06-live-sample.png"), full_page=True)
            page.locator("#demo-live-sample-drawer").evaluate("(el) => el.close()")

        # 刷新恢复（现场任务一般仍在进行；若已完成则刷新后显示终态）
        if not args.skip_live:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            # 整页刷新会带走 window.axe，必须重新注入，否则后面的扫描是假的空结果。
            enable_axe(page, ROOT)
            recover = text_of(page, "#demo-gate")
            report["refresh_recovery"] = recover[:300]
            step("refresh_recovery", recover[:160])
            axe_state(page, report, "after_refresh", step)

        page.screenshot(path=str(output_dir / "07-final.png"), full_page=False)
        browser.close()

    states = report["axe_states"]
    not_executed = sorted(name for name, entry in states.items() if not entry.get("axe_executed"))
    violated = {name: entry["violations"] for name, entry in states.items() if entry.get("violations")}
    report["axe_states_covered"] = sorted(states)
    report["axe_not_executed"] = not_executed
    report["axe_violations_by_state"] = violated
    # 工具没执行与页面真违规是两件事：任一状态没跑起来就整体判为未验收。
    report["axe_acceptance"] = "accepted" if states and not not_executed and not violated else "not_accepted"
    report["print_expand_accepted"] = bool(report.get("print_expand", {}).get("all_collapsed_printed"))

    print("SUMMARY:", json.dumps(
        {
            key: report.get(key)
            for key in (
                "viewport",
                "staged_progress_count",
                "axe_acceptance",
                "axe_states_covered",
                "axe_not_executed",
                "axe_violations_by_state",
                "print_expand",
                "print_expand_accepted",
            )
        },
        ensure_ascii=False,
    )[:1400])
    with open(output_dir / "audit-summary.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return 0 if report["axe_acceptance"] == "accepted" and report["print_expand_accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
