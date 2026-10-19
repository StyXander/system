"""UI 基线/回归截图：真实本地服务 + 已保存历史任务，不注入任何伪造业务数据。

用法：
  python scripts/ui_shots.py <输出目录> [--task CONNJOB-XXXX]

只做浏览器渲染与截图，不修改服务端状态。
"""
from __future__ import annotations

import argparse
import pathlib
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8011/"


def shot(page, path: pathlib.Path, full: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=full)
    print("shot", path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--task", default="CONNJOB-D8796D38B3EC")
    ap.add_argument("--tag", default="baseline")
    args = ap.parse_args()
    out = pathlib.Path(args.out)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for width, height, name in ((1440, 1000, "desktop"), (390, 844, "mobile")):
            ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
            page = ctx.new_page()
            page.goto(BASE, wait_until="networkidle")
            page.wait_for_timeout(1200)
            shot(page, out / f"{args.tag}_home_{name}.png")
            page.goto(BASE + f"?connectivity_task={args.task}#connectivity-root", wait_until="networkidle")
            page.wait_for_timeout(2500)
            shot(page, out / f"{args.tag}_result_{name}.png")
            # 首屏之外的整体结构（用于检查信息密度与重复模块）
            shot(page, out / f"{args.tag}_result_full_{name}.png", full=True)
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
