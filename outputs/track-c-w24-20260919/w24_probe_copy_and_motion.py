#!/usr/bin/env python
"""W24 补充探针：确认 ② 区 support_status 文字、证据 chip 的原文入口覆盖率，
以及 prefers-reduced-motion 下的动效是否真的关闭。只读，不创建运行。"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
TASK_KEY = "audittrace_demo_task_v1"

PROBE_JS = r"""
() => {
  const supports = [...document.querySelectorAll('.demo-attention-support')]
    .map((n) => ({ cls: n.className, text: n.textContent.trim(), visible: n.offsetParent !== null }));
  const chips = [...document.querySelectorAll('.demo-evidence-chip')];
  const withId = chips.filter((n) => /Evidence ID/.test(n.textContent));
  const card = document.getElementById('demo-attention-card');
  // .demo-result 带 content-visibility:auto，离屏子树会被跳过渲染，
  // 因此文案核查必须用 textContent（与布局无关），不能用 innerText。
  const cardText = (card?.textContent || '').replace(/\s+/g, '');
  return {
    supports,
    cardPresent: Boolean(card),
    cardHiddenAttr: card ? card.hidden : null,
    chipTotal: chips.length,
    chipWithEvidenceId: withId.length,
    chipWithAnchor: withId.filter((n) => n.querySelector('a')).length,
    chipNoSourceEntry: withId.filter((n) => !n.querySelector('a')).map((n) => n.textContent.replace(/\s+/g, ' ').trim().slice(0, 120)),
    cardHasWaitVerify: cardText.includes('待验证解释'),
    cardHasBoundary: cardText.includes('本级别为审计计划阶段的程序筛查信号分级，不是审计认定，不构成审计结论或审计意见。'),
    cardHasDeterministicNote: cardText.includes('确定性计算，非模型生成'),
    bodyHasForbidden: ['无风险', '风险评级', '信用等级', '企业风险等级'].some((term) => document.body.textContent.includes(term)),
    badgeTexts: [...document.querySelectorAll('#demo-attention-badges .demo-attention-badge')]
      .map((n) => n.textContent.replace(/\s+/g, ' ').trim()),
    providedBadges: document.querySelectorAll('#demo-attention-badges .demo-attention-badge[data-state="provided"]').length,
    attentionStatePill: document.getElementById('demo-attention-state')?.textContent || '',
  };
}
"""


def main() -> None:
    report = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        cases = [
            ("incomplete_numeric_claims", "http://127.0.0.1:8000", "DEMO-RUN-F1330AD8EA8B", "CNINFO_000858_T0_20260430"),
            ("success", "http://127.0.0.1:8000", "DEMO-RUN-66A1B0E52840", "STD_DEV_T0"),
            ("deterministic_backup_with_backend_fields", "http://127.0.0.1:8010", "DEMO-BACKUP-7FB11774EDE5", "CNINFO_000858_T0_20260430"),
        ]
        for state, base, task_id, case_id in cases:
            for motion in ("no-preference", "reduce"):
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    reduced_motion=motion,
                )
                page = context.new_page()
                page.goto(f"{base}/", wait_until="networkidle")
                page.evaluate(
                    "([k, v]) => sessionStorage.setItem(k, v)",
                    [TASK_KEY, json.dumps({"task_id": task_id, "case_id": case_id, "mode": "primary"})],
                )
                page.goto(f"{base}/?case={case_id}", wait_until="networkidle")
                page.wait_for_function("() => !document.getElementById('demo-result').hidden", timeout=40000)
                data = page.evaluate(PROBE_JS)
                data["state"] = state
                data["reduced_motion"] = motion
                data["stageTransition"] = page.evaluate(
                    "() => getComputedStyle(document.querySelector('.demo-stage')).transitionDuration",
                )
                report.append(data)
                if motion == "reduce":
                    page.screenshot(path=str(OUT / "screenshots" / f"probe-{state}-reduced-motion.png"), full_page=True)
                context.close()
        browser.close()
    (OUT / "probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in report:
        print("=" * 66)
        print(item["state"], "| reduced_motion =", item["reduced_motion"], "| stage transition =", item["stageTransition"])
        print("  supports:", json.dumps(item["supports"], ensure_ascii=False))
        print("  card", item["cardPresent"], "hidden", item["cardHiddenAttr"], "| 待验证解释", item["cardHasWaitVerify"], "| 边界句", item["cardHasBoundary"], "| 确定性标注", item["cardHasDeterministicNote"])
        print("  chips", item["chipWithEvidenceId"], "with anchor", item["chipWithAnchor"], "providedBadges", item["providedBadges"], "forbidden-terms", item["bodyHasForbidden"], "pill", item["attentionStatePill"])
        print("  badges", json.dumps(item["badgeTexts"], ensure_ascii=False))
        if item["chipNoSourceEntry"]:
            print("  no-entry sample:", json.dumps(item["chipNoSourceEntry"][:2], ensure_ascii=False))


if __name__ == "__main__":
    main()
