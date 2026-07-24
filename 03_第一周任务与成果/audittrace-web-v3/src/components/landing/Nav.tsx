/**
 * 固定顶栏
 * 玻璃拟态导航,包含品牌标识、锚点导航和进入工作台按钮。
 */

import { motion } from "framer-motion";
import { LinkButton } from "../ui/Button";

const navItems = [
  { label: "产品价值", href: "#value" },
  { label: "验证方法", href: "#method" },
  { label: "工作流程", href: "#workflow" },
  { label: "边界与进度", href: "#boundary" },
];

export function Nav() {
  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
      className="fixed top-0 left-0 right-0 z-[100] glass-strong"
      style={{ borderBottom: "1px solid var(--line-subtle)" }}
    >
      <div className="mx-auto min-h-[68px] flex items-center justify-between gap-8 px-6 lg:px-12 max-w-[1400px]">
        {/* 品牌 */}
        <a href="#top" className="flex items-center gap-3 flex-shrink-0" aria-label="审迹智链首页">
          <span
            className="relative w-8 h-8 rounded-full border border-[var(--accent-blue)]/70"
            style={{ boxShadow: "inset 0 0 0 7px rgba(91,141,239,0.05), 0 0 24px rgba(91,141,239,0.14)" }}
          >
            <span className="absolute w-1.5 h-1.5 right-0 top-1 rounded-full bg-[var(--accent-teal)]" style={{ boxShadow: "0 0 12px rgba(74,222,184,0.8)" }} />
          </span>
          <span className="grid gap-px">
            <strong className="text-[17px] tracking-[0.04em]">审迹智链</strong>
            <small className="text-[var(--text-muted)] font-mono text-[8px] tracking-[0.26em]">AUDITTRACE</small>
          </span>
        </a>

        {/* 桌面导航 */}
        <nav className="hidden md:flex items-center gap-6 lg:gap-10 ml-auto">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="relative py-3.5 text-sm text-[var(--text-secondary)] hover:text-white transition-colors duration-200 group"
            >
              {item.label}
              <span className="absolute left-0 right-full bottom-2 h-px bg-[var(--accent-teal)] transition-all duration-200 group-hover:right-0" />
            </a>
          ))}
        </nav>

        {/* CTA */}
        <LinkButton href="#/workbench" variant="primary" size="sm">
          查看交互原型
          <span aria-hidden="true">↗</span>
        </LinkButton>
      </div>
    </motion.header>
  );
}
