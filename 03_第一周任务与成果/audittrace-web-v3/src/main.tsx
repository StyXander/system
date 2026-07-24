/**
 * 审迹智链 Web V3 · React 挂载入口
 * 初始化 Lenis 平滑滚动,与 Framer Motion useScroll 集成(使用原生滚动位置)。
 * 尊重 prefers-reduced-motion:系统设置降低动效时关闭平滑滚动,动画近乎瞬时。
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Lenis from "lenis";
import App from "./App";
import "./index.css";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("找不到 #root 挂载节点");
}

// 平滑滚动:lerp 0.08 + smoothWheel,参考 Kimi 官网的柔和滚动质感
const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

if (!prefersReducedMotion) {
  const lenis = new Lenis({ lerp: 0.08, smoothWheel: true });

  // 与 Framer Motion useScroll 集成:Lenis 使用原生滚动位置,
  // useScroll 读取的也是原生滚动位置,二者天然兼容。
  const raf = (time: number) => {
    lenis.raf(time);
    requestAnimationFrame(raf);
  };
  requestAnimationFrame(raf);

  // 站内锚点(#value 等)用 Lenis 平滑滚动,而非浏览器瞬时跳转
  document.addEventListener("click", (event) => {
    const target = (event.target as HTMLElement)?.closest("a");
    if (!target) return;
    const href = target.getAttribute("href") || "";
    // 只处理站内锚点,不处理路由链接(#/workbench)与外部链接
    if (!href.startsWith("#") || href.startsWith("#/")) return;
    const id = href.slice(1);
    if (!id) return;
    const el = document.getElementById(id);
    if (el) {
      event.preventDefault();
      lenis.scrollTo(el, { offset: -80 });
    }
  });
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
