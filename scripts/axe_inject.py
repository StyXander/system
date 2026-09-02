"""无障碍验收的 axe 注入器：以同源脚本方式提供 axe，不放宽生产 CSP。

为什么不能继续用 add_script_tag(path=...)：Playwright 会把文件内容作为内联脚本
注入，而生产 CSP 是 script-src 'self'，内联被拒绝，axe 从未真正执行。此时把
"violations 为空"当成通过是错的，必须判为未验收。

这里改用同源虚拟 URL：用 page.route 拦截一个页面自己域名下的路径，从本地磁盘
返回 axe 正文，再以 url 方式注入。'self' 允许同源外链脚本，因此生产 CSP 一个字
都不用改，也不需要给应用新增静态路由。
"""

from __future__ import annotations

from pathlib import Path

AXE_ROUTE_PATH = "/__axe_audit/axe.min.js"
# site-packages 的目录名在不同 Python 版本会变，因此用通配解析而不是写死。
AXE_GLOBS = (
    "backend/.venv/lib/python*/site-packages/axe_playwright_python/axe.min.js",
    "backend/.venv/Lib/site-packages/axe_playwright_python/axe.min.js",
)

RUN_AXE_JS = """async () => {
  const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } });
  // 对比度节点要留下可复核的原始数据，否则"判不了"的节点只能靠人重新打开页面猜。
  const contrastData = (n) => {
    const check = (n.none && n.none[0]) || (n.any && n.any[0]) || (n.all && n.all[0]) || null;
    const d = check && check.data;
    if (!d || d.fgColor === undefined) return null;
    return {
      target: (n.target || []).join(' ').slice(0, 160),
      fg_color: d.fgColor,
      bg_color: d.bgColor,
      contrast_ratio: d.contrastRatio,
      expected_ratio: d.expectedContrastRatio,
      font_size: d.fontSize,
      font_weight: d.fontWeight,
    };
  };
  const collect = (list) => (list || []).flatMap((v) => (v.nodes || [])
    .filter((n) => v.id === 'color-contrast')
    .map((n) => Object.assign({ rule: v.id }, contrastData(n))));
  return {
    axe_executed: true,
    axe_version: axe.version || null,
    violations: (r.violations || []).map(v => ({ id: v.id, impact: v.impact || null, nodes: (v.nodes || []).length, help: v.help || '' })),
    incomplete: (r.incomplete || []).map(v => ({ id: v.id, nodes: (v.nodes || []).length })),
    passes: (r.passes || []).length,
    contrast_nodes: collect(r.incomplete).concat(collect(r.violations)).slice(0, 120),
  };
}"""


class AxeNotInstalled(RuntimeError):
    """axe 未真正在页面上执行；这种情况下禁止给出任何违规计数结论。"""


def find_axe_file(root: Path) -> Path:
    """定位随 axe-playwright-python 一起分发的 axe.min.js。"""

    for pattern in AXE_GLOBS:
        for candidate in sorted(root.glob(pattern)):
            if candidate.is_file():
                return candidate
    raise AxeNotInstalled(f"在 {root} 下找不到 axe.min.js；请先安装 requirements-dev.txt 里的 axe-playwright-python")


def enable_axe(page, root: Path) -> Path:
    """注册同源拦截并注入 axe，返回实际使用的 axe 文件。"""

    axe_path = find_axe_file(root)
    body = axe_path.read_bytes()
    page.route(f"**{AXE_ROUTE_PATH}", lambda route: route.fulfill(status=200, content_type="text/javascript", body=body))
    page.add_script_tag(url=AXE_ROUTE_PATH)
    page.wait_for_function("() => window.axe && typeof window.axe.run === 'function'", timeout=15000)
    return axe_path


def run_axe(page) -> dict:
    """执行 axe 扫描；工具本身没跑起来时抛 AxeNotInstalled 而不是返回空结果。"""

    if not page.evaluate("() => Boolean(window.axe && typeof window.axe.run === 'function')"):
        raise AxeNotInstalled("页面上没有可用的 window.axe.run；本次无障碍检查不能记为通过")
    return page.evaluate(RUN_AXE_JS)
