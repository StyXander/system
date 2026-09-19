#!/usr/bin/env python
"""W24 浏览器验收：真实后端 + 真实 Chromium，4 视口 × 可零成本达成的运行状态逐一实测。

不发起任何付费模型调用：
- success / incomplete_numeric_claims / model_failed 三态由页面自身的"刷新恢复"通路读取
  本机已完成的真实任务台账（今日 13:04—13:24 产生），只读不改写；
- deterministic_backup 态由 8010（模型硬关闭）实例的"启动确定性备用演示"真实产生。

输出：本目录下 screenshots/ 与 acceptance.json（控制台、网络、溢出、抽屉、焦点、reduce-motion）。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    ("desktop-1440x1000", 1440, 1000),
    ("tablet-1024x768", 1024, 768),
    ("portrait-768x1024", 768, 1024),
    ("mobile-390x844", 390, 844),
]

# (state_key, base_url, task_id, case_id) —— task_id 为 None 表示需要现场点击产生。
# data_gap_extraction 走 8010 主按钮：该实例 DEEPSEEK_API_KEY 为空且
# AUDITTRACE_DEMO_USE_EXTERNAL_MODEL=false，模型阶段必然不发起任何外部调用，
# 用于实测 W16"抽取字段待人工回页确认"的具体诊断透传。
STATES = [
    ("success", "http://127.0.0.1:8000", "DEMO-RUN-66A1B0E52840", "STD_DEV_T0"),
    ("incomplete_numeric_claims", "http://127.0.0.1:8000", "DEMO-RUN-F1330AD8EA8B", "CNINFO_000858_T0_20260430"),
    ("model_failed_degraded", "http://127.0.0.1:8010", "DEMO-RUN-33AA25E68BD8", "STD_DEV_T0"),
    ("deterministic_backup", "http://127.0.0.1:8010", None, "CNINFO_000858_T0_20260430"),
    ("data_gap_extraction", "http://127.0.0.1:8010", "PRIMARY", "CNINFO_600900_T0_20260429"),
]

TASK_KEY = "audittrace_demo_task_v1"
CASE_KEY = "audittrace_demo_case_v1"

CHECKS_JS = """
() => {
  const zones = {
    signals: document.querySelector('#demo-attention-signals')?.childElementCount ?? -1,
    counter: document.querySelector('#demo-attention-counter')?.childElementCount ?? -1,
    review: document.querySelector('#demo-attention-review')?.childElementCount ?? -1,
    change: document.querySelector('#demo-attention-change')?.childElementCount ?? -1,
    procedures: document.querySelector('#demo-attention-procedures')?.childElementCount ?? -1,
    badges: document.querySelectorAll('#demo-attention-badges .demo-attention-badge').length,
  };
  const attention = document.getElementById('demo-attention-card');
  const chips = [...document.querySelectorAll('.demo-evidence-chip')];
  const overflowX = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  const active = document.activeElement;
  return {
    zones,
    attentionVisible: attention ? !attention.hidden : null,
    attentionStatePill: document.getElementById('demo-attention-state')?.textContent || '',
    evidenceChipCount: chips.length,
    chipSample: chips.slice(0, 3).map((n) => n.textContent.replace(/\\s+/g, ' ').trim()),
    chipHasLink: chips.slice(0, 6).filter((n) => n.querySelector('a')).length,
    executionBadge: document.getElementById('demo-execution-badge')?.textContent || '',
    executionMode: document.getElementById('demo-execution-badge')?.dataset?.mode || '',
    extractionNotice: [...document.querySelectorAll('.demo-extraction-notice')].map((n) => n.textContent.replace(/\\s+/g, ' ').trim().slice(0, 260)),
    attentionText: (document.getElementById('demo-attention-card')?.textContent || '').replace(/\\s+/g, ' ').slice(0, 320),
    overviewSource: document.getElementById('demo-audit-overview-source')?.textContent || '',
    overviewLabel: document.getElementById('demo-audit-overview-conclusion')?.textContent || '',
    resultState: document.getElementById('demo-result-state')?.textContent || '',
    resultHidden: document.getElementById('demo-result')?.hidden ?? null,
    gateTitle: document.querySelector('#demo-gate strong')?.textContent || '',
    gateDetail: document.querySelector('#demo-gate .demo-gate-detail')?.textContent || '',
    stage4: document.getElementById('demo-stage-4-note')?.textContent || '',
    overflowX,
    bodyFont: getComputedStyle(document.body).fontFamily,
    focusTag: active ? active.tagName + '#' + (active.id || '') : '',
    reducedMotionTransition: getComputedStyle(document.querySelector('.demo-stage') || document.body).transitionDuration,
  };
}
"""

# 逐条主张是否把"无证据"如实标出，以及待验证解释是否被标成假设而非事实。
CLAIM_AUDIT_JS = """
() => {
  const text = document.body.innerText;
  const hypotheses = [...document.querySelectorAll('.demo-attention-support.is-hypothesis')].length;
  const supported = [...document.querySelectorAll('.demo-attention-support.is-supported')].length;
  const missing = [...document.querySelectorAll('.demo-claim-evidence.is-missing')].length;
  const chips = [...document.querySelectorAll('.demo-evidence-chip')];
  const five = chips.filter((n) => /Evidence ID/.test(n.textContent) && /来源类型/.test(n.textContent)
    && /PDF (年度|页码)|PDF 年度|PDF 第/.test(n.textContent)).length;
  return { hypotheses, supported, missing, chips: chips.length, fiveElementChips: five,
           mentionsWaitVerify: text.includes('待验证解释') };
}
"""


def collect_page_signals(page, errors, requests_bad, api_calls):
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on("console", lambda msg: errors.append(f"console.{msg.type}: {msg.text}") if msg.type == "error" else None)
    page.on("requestfailed", lambda req: requests_bad.append({"url": req.url, "failure": str(req.failure)}))
    page.on("response", lambda res: requests_bad.append({"url": res.url, "status": res.status}) if res.status >= 400 else None)
    # 记录每个 /api 调用与状态，验收结论要能回到"哪个接口真的返回了什么"。
    page.on("response", lambda res: api_calls.append({"method": res.request.method, "url": res.url.replace("http://127.0.0.1:8010", "").replace("http://127.0.0.1:8000", ""), "status": res.status}) if "/api/" in res.url else None)


def restore_state(page, base, task_id, case_id, api_log, attempts=3):
    """用页面自身的刷新恢复通路读取已完成任务；这条通路不创建运行、不调用模型。

    恢复失败时前端会静默清掉 sessionStorage 并退回"演示就绪"，因此这里带重试，
    并把每一次 /api/demo/runs 的返回状态记进 api_log，避免只剩一句 timeout。
    """
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            page.goto(f"{base}/", wait_until="networkidle")
            page.evaluate("([k,v]) => sessionStorage.setItem(k, v)", [TASK_KEY, json.dumps({"task_id": task_id, "case_id": case_id, "mode": "primary"})])
            page.evaluate("([k,v]) => localStorage.setItem(k, v)", [CASE_KEY, case_id])
            page.goto(f"{base}/?case={case_id}", wait_until="networkidle")
            page.wait_for_function("() => !document.getElementById('demo-result').hidden", timeout=30000)
            page.evaluate("(a) => window.__w24Attempt = a", attempt)
            return
        except Exception as error:  # noqa: BLE001
            last_error = error
            api_log.append({"attempt": attempt, "error": f"{type(error).__name__}: {str(error)[:160]}"})
            page.wait_for_timeout(1500)
    raise last_error



def backup_state(page, base, case_id):
    page.goto(f"{base}/?case={case_id}", wait_until="networkidle")
    page.wait_for_selector("#demo-start:not([disabled])", timeout=30000)
    button = page.locator("#demo-backup")
    button.wait_for(state="visible", timeout=15000)
    button.click()
    page.wait_for_function("() => !document.getElementById('demo-result').hidden", timeout=90000)


def primary_state(page, base, case_id):
    """现场点主按钮产生一次真实运行；仅在模型硬关闭的实例上使用（0 次外部调用）。"""
    page.goto(f"{base}/?case={case_id}", wait_until="networkidle")
    page.wait_for_selector("#demo-start:not([disabled])", timeout=30000)
    page.click("#demo-start")
    page.wait_for_function("() => !document.getElementById('demo-result').hidden", timeout=120000)


def run():
    results = []
    with sync_playwright() as pw:
        # 本机 Playwright 未下载 headless shell；用系统已装 Chrome / Edge 做真实浏览器验收。
        for channel in ("chrome", "msedge", None):
            try:
                browser = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
                break
            except Exception as error:  # noqa: BLE001
                print(f"launch failed for channel={channel}: {type(error).__name__}")
        else:
            raise SystemExit("没有可用的真实浏览器（Chrome/Edge/Playwright chromium 全部不可用）")
        print(f"browser channel = {channel}")
        for state_key, base, task_id, case_id in STATES:
            per_state = {"state": state_key, "base": base, "case_id": case_id, "task_id": task_id, "viewports": []}
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            page = context.new_page()
            errors: list[str] = []
            bad: list[dict] = []
            api_calls: list[dict] = []
            collect_page_signals(page, errors, bad, api_calls)
            try:
                if task_id == "PRIMARY":
                    primary_state(page, base, case_id)
                elif task_id:
                    restore_state(page, base, task_id, case_id, api_calls)
                else:
                    backup_state(page, base, case_id)
                per_state["restored"] = True
            except Exception as error:  # noqa: BLE001 - 验收脚本必须把失败如实记下来
                per_state["restored"] = False
                per_state["error"] = f"{type(error).__name__}: {error}"
            # 失败也要留一份现场：总览/横幅文本与各接口状态，避免只有一句 timeout。
            try:
                page.set_viewport_size({"width": 1440, "height": 1000})
                page.wait_for_timeout(400)
                per_state["diagnostics"] = page.evaluate(CHECKS_JS)
                page.screenshot(path=str(SHOTS / f"{state_key}__diagnostics.png"), full_page=True)
            except Exception as error:  # noqa: BLE001
                per_state["diagnostics"] = f"diagnostics failed: {type(error).__name__}"
            for label, width, height in VIEWPORTS:
                if per_state["restored"]:
                    page.set_viewport_size({"width": width, "height": height})
                    page.wait_for_timeout(450)
                    checks = page.evaluate(CHECKS_JS)
                    claim = page.evaluate(CLAIM_AUDIT_JS) if label.startswith("desktop") else {}
                    # 抽屉与键盘可达性只在桌面与手机两档实测。
                    drawer = {}
                    keyboard = {}
                    if label in ("desktop-1440x1000", "mobile-390x844"):
                        for open_id, drawer_id in (("#demo-open-evidence", "demo-evidence-drawer"), ("#demo-open-agents", "demo-agent-drawer")):
                            try:
                                page.click(open_id, timeout=5000)
                                page.wait_for_selector(f"#{drawer_id}[open]", timeout=5000)
                                drawer[drawer_id] = page.evaluate(
                                    "(id) => document.getElementById(id).querySelectorAll('.demo-evidence-item, .demo-agent-card').length",
                                    drawer_id,
                                )
                                page.keyboard.press("Escape")
                            except Exception as error:  # noqa: BLE001
                                drawer[drawer_id] = f"FAIL {type(error).__name__}"
                        page.keyboard.press("Tab")
                        page.keyboard.press("Tab")
                        keyboard = page.evaluate("() => { const a=document.activeElement; const s=getComputedStyle(a); return {tag:a.tagName+(a.id?'#'+a.id:''), outline:s.outlineWidth, boxShadow:s.boxShadow.slice(0,60)}; }")
                    shot = SHOTS / f"{state_key}__{label}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    per_state["viewports"].append({
                        "viewport": label,
                        "width": width,
                        "checks": checks,
                        "claim_audit": claim,
                        "drawers": drawer,
                        "keyboard": keyboard,
                        "screenshot": shot.relative_to(OUT).as_posix(),
                    })
            per_state["console_errors"] = errors
            per_state["failed_requests"] = bad
            per_state["api_calls"] = api_calls
            per_state["final_url"] = page.url
            context.close()
            results.append(per_state)
            print(json.dumps({k: per_state[k] for k in ("state", "restored", "console_errors", "failed_requests") if k in per_state}, ensure_ascii=False)[:600])
        browser.close()
    (OUT / "acceptance.json").write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(run())
