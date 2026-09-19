#!/usr/bin/env python
"""W24 目视复核用截图：按元素与首屏取景，不拍 6 万像素高的整页长条。

每个状态拍：结果区首屏（视口内）、综合审计关注卡、状态横幅；
移动端额外单独拍关注卡，用于判断六区在 390px 下是否可读。
只读：全部走已完成任务的刷新恢复通路或已产生的备用任务。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
SHOTS = OUT / "review"
TASK_KEY = "audittrace_demo_task_v1"
CASE_KEY = "audittrace_demo_case_v1"

STATES = [
    ("success", "http://127.0.0.1:8000", "DEMO-RUN-66A1B0E52840", "STD_DEV_T0"),
    ("gate_rejected", "http://127.0.0.1:8000", "DEMO-RUN-F1330AD8EA8B", "CNINFO_000858_T0_20260430"),
    ("model_failed", "http://127.0.0.1:8010", "DEMO-RUN-33AA25E68BD8", "STD_DEV_T0"),
    ("backup_real_fields", "http://127.0.0.1:8010", "DEMO-BACKUP-7FB11774EDE5", "CNINFO_000858_T0_20260430"),
    ("data_gap_w16", "http://127.0.0.1:8010", "DEMO-RUN-DEA400380695", "CNINFO_600900_T0_20260429"),
]
VIEWPORTS = [("desktop", 1440, 1000), ("tablet", 1024, 768), ("portrait", 768, 1024), ("mobile", 390, 844)]


def main() -> None:
    if SHOTS.exists():
        shutil.rmtree(SHOTS)
    SHOTS.mkdir(parents=True)
    index = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        for state, base, task_id, case_id in STATES:
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
            try:
                page.goto(f"{base}/", wait_until="networkidle")
                page.evaluate("([k,v]) => sessionStorage.setItem(k, v)", [TASK_KEY, json.dumps({"task_id": task_id, "case_id": case_id, "mode": "primary"})])
                page.evaluate("([k,v]) => localStorage.setItem(k, v)", [CASE_KEY, case_id])
                page.goto(f"{base}/?case={case_id}", wait_until="networkidle")
                page.wait_for_function("() => !document.getElementById('demo-result').hidden", timeout=60000)
            except Exception as error:  # noqa: BLE001
                index.append({"state": state, "ok": False, "error": f"{type(error).__name__}: {str(error)[:150]}"})
                context.close()
                continue
            for label, width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(400)
                page.evaluate("() => document.getElementById('demo-result').scrollIntoView({ block: 'start' })")
                first_screen = SHOTS / f"{state}__{label}__firstscreen.png"
                page.screenshot(path=str(first_screen))
                card = page.locator("#demo-attention-card")
                card.scroll_into_view_if_needed()
                page.wait_for_timeout(150)
                card_shot = SHOTS / f"{state}__{label}__attentioncard.png"
                card.screenshot(path=str(card_shot))
                index.append({
                    "state": state,
                    "ok": True,
                    "viewport": label,
                    "first_screen": first_screen.relative_to(OUT).as_posix(),
                    "attention_card": card_shot.relative_to(OUT).as_posix(),
                    "console_errors": errors,
                })
            context.close()
        browser.close()
    (OUT / "review-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in index:
        print(item["state"], item.get("viewport"), "errors" if item.get("console_errors") else "clean", item.get("error", ""))


if __name__ == "__main__":
    main()
