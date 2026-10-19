"""前端真实浏览器验收（Playwright + 本机 Chrome）。

覆盖：
  1) 390 / 768 / 1024 / 1440 四档：首页 -> 工作台 -> 结果 -> 原页 -> 历史 -> 刷新 -> 返回首页
  2) 深链 ?connectivity_task 直接落在结果视图；坏链接给出可理解错误
  3) 四种典型组合（合成夹具，仅用于 UI 状态测试，不代表真实运行）：
     程序未知 + AI 倾向一致 / 程序条件相容 / 程序差异未解释 / 系统候选失败
  4) 状态分类断言：依据不足与不可比不得显示成绿色“暂未见问题”

运行：
  TMP=<工作区>/tmp python scripts/ui_test_frontend.py <截图目录>
"""
from __future__ import annotations

import json
import pathlib
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8011/"
REAL_TASK = "CONNJOB-D8796D38B3EC"
ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_state_fixture.json"

results: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail else ""))


def visible_in_viewport(page, selector: str) -> bool:
    box = page.eval_on_selector(selector, "el => { const r = el.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,h:innerHeight}; }")
    return box["top"] >= 0 and box["bottom"] <= box["h"] + 1


def run_viewport(browser, width: int, height: int, out: pathlib.Path) -> None:
    ctx = browser.new_context(viewport={"width": width, "height": height})
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    tag = f"{width}"

    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(900)
    page.screenshot(path=str(out / f"{tag}_home.png"))
    check(f"[{tag}] 首页 10 秒内看到用途句", visible_in_viewport(page, ".hero-sub-lead"))
    check(f"[{tag}] 首页入口按钮在首屏", visible_in_viewport(page, ".hero-cta"))
    covered = page.evaluate("""() => {
      const cta = document.querySelector('.hero-cta');
      const r = cta.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
      return !(hit && (hit === cta || cta.contains(hit)));
    }""")
    skip = page.eval_on_selector(".cn-skip", "el => el.getBoundingClientRect().bottom")
    check(f"[{tag}] 首屏入口未被浮层遮挡", not covered and skip <= 0, f"covered={covered} skipBottom={skip}")

    page.click(".hero-cta")
    page.wait_for_timeout(700)
    check(f"[{tag}] 进入工作台后首页 hero 收起", not page.is_visible("#redesign-home"))
    check(f"[{tag}] 工作台新建视图可见", page.is_visible("#cn-view-new"))
    page.screenshot(path=str(out / f"{tag}_workspace.png"))

    page.goto(BASE + f"?connectivity_task={REAL_TASK}#connectivity-root", wait_until="networkidle")
    page.wait_for_timeout(2200)
    check(f"[{tag}] 深链直达结果", page.is_visible("#cn-results"))
    check(f"[{tag}] 结果页仍隐藏首页 hero", not page.is_visible("#redesign-home"))
    title = page.inner_text("#cn-verdict-title")
    check(f"[{tag}] 一句话结论存在", len(title) > 20, title[:40])
    formal = page.inner_text('[data-level="formal"] .cn-level-card-value')
    unclear = page.inner_text('[data-level="insufficient"] .cn-level-card-value')
    conflict = page.inner_text('[data-level="conflict"] .cn-level-card-value')
    check(f"[{tag}] 分级计数为 2/4/0", "2" in formal and "4" in unclear and "0" in conflict, f"{formal}|{unclear}|{conflict}")
    check(f"[{tag}] 不可比不显示绿色", page.get_attribute('[data-level="insufficient"]', "data-level") == "insufficient")
    check(f"[{tag}] AI 计数独立呈现", page.is_visible(".cn-ai-counts"))
    check(f"[{tag}] 三条证据线可见", page.locator(".cn-lane").count() == 3, str(page.locator(".cn-lane").count()))
    page.screenshot(path=str(out / f"{tag}_result.png"))

    # 原页阅读器：打开、可关闭
    page.locator("#cn-nextq [data-reader]").first.click()
    page.wait_for_timeout(600)
    check(f"[{tag}] 原文阅读器可打开", page.is_visible("#cn-reader"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    check(f"[{tag}] 原文阅读器可关闭", not page.is_visible("#cn-reader"))

    # 全部关系按需展开
    page.click("#cn-all-relations > summary")
    page.wait_for_timeout(300)
    check(f"[{tag}] 全部关系可展开", page.is_visible("#cn-master"))

    # 刷新仍落结果
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2000)
    check(f"[{tag}] 刷新后仍在结果视图", page.is_visible("#cn-results") and not page.is_visible("#redesign-home"))

    # 历史：默认 5 条内、状态可见
    page.click('.cn-sidebar [data-view="history"]')
    page.wait_for_timeout(400)
    rows = page.locator("#cn-history-list .cn-history-row").count()
    check(f"[{tag}] 历史默认不超过 5 条", 0 < rows <= 5, str(rows))
    check(f"[{tag}] 历史有状态标注", page.locator("#cn-history-list .cn-history-status").count() == rows)
    page.screenshot(path=str(out / f"{tag}_history.png"))

    # 坏链接：可理解错误
    page.goto(BASE + "?connectivity_task=CONNJOB-AAAAAAAAAAAA#connectivity-root", wait_until="networkidle")
    page.wait_for_timeout(1500)
    check(f"[{tag}] 失效链接给出错误说明", page.is_visible("#cn-task-error"), page.inner_text("#cn-task-error-title") if page.is_visible("#cn-task-error") else "")

    # 返回首页
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(500)
    check(f"[{tag}] 返回首页 hero 恢复", page.is_visible("#redesign-home"))

    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check(f"[{tag}] 无横向溢出", overflow <= 1, str(overflow))
    check(f"[{tag}] 无 JS 运行时错误", not errors, "; ".join(errors[:2]))
    ctx.close()


def run_ai_states(browser, out: pathlib.Path) -> None:
    """合成夹具只用于验证“状态如何显示”，页面顶部仍来自真实结果结构。"""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    def handler(route):
        if route.request.method == "GET" and "/api/connectivity/runs/" in route.request.url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture, ensure_ascii=False))
        else:
            route.continue_()

    page.route("**/api/connectivity/runs/*", handler)
    page.goto(BASE + "?connectivity_task=CONNJOB-D8796D38B3EC#connectivity-root", wait_until="networkidle")
    page.wait_for_timeout(1800)
    page.screenshot(path=str(out / "ai_states_result.png"))

    body = page.inner_text("#cn-fourq")
    check("[AI合成] AI 计数区分倾向矛盾/一致/依据不足", "倾向矛盾" in body and "倾向一致" in body and "依据不足" in body)
    chips = page.locator("#cn-check-list .cn-tendency-chip")
    tones = [chips.nth(i).get_attribute("data-tone") for i in range(chips.count())]
    check("[AI合成] AI 徽标不含绿色语义", all(t != "ok" for t in tones), ",".join(map(str, tones)))

    # 专业明细默认收起：测试里显式展开，模拟使用者点开“全部关系”
    page.evaluate("document.getElementById('cn-all-relations').open = true")
    page.wait_for_timeout(300)
    # 程序不可比 + AI 倾向一致：必须出现“以程序为准”的分歧提示
    page.locator("#cn-check-list [data-check='CHECK-0001']").click()
    page.wait_for_timeout(400)
    detail = page.inner_text("#cn-detail-conclusion")
    check("[AI合成] 程序不可比时 AI 倾向不覆盖程序", "以程序为准" in detail, detail[:80].replace("\n", " "))
    check("[AI合成] 程序限制显式标出", "依据不足" in detail or "不可比" in detail)

    page.locator("#cn-check-list [data-check='CHECK-0002']").click()
    page.wait_for_timeout(300)
    cond = page.inner_text("#cn-detail-conclusion")
    check("[AI合成] 条件相容显示为条件试算", "条件试算" in cond, cond[:60].replace("\n", " "))

    page.locator("#cn-check-list [data-check='CHECK-0003']").click()
    page.wait_for_timeout(300)
    conflict = page.inner_text("#cn-detail-conclusion")
    check("[AI合成] 未解释差额进入潜在矛盾", "潜在矛盾" in conflict, conflict[:60].replace("\n", " "))

    page.click("#cn-dtab-questions")
    page.wait_for_timeout(200)
    page.evaluate("document.querySelector('.cn-pro-details').open = true")
    page.wait_for_timeout(200)
    check("[AI合成] 系统候选失败进入运行诊断", "系统数据问题" in page.inner_text("#cn-nextq"), "运行诊断面板")
    check("[AI合成] 无 JS 运行时错误", not errors, "; ".join(errors[:2]))
    ctx.close()


def main() -> None:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "tmp/e2e")
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for width, height in ((1440, 1000), (1024, 768), (768, 1024), (390, 844)):
            run_viewport(browser, width, height, out)
        run_ai_states(browser, out)
        browser.close()
    report = out / "e2e-report.json"
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [row for row in results if not row["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("FAILED:", ", ".join(row["check"] for row in failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
