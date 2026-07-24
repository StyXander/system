/**
 * 审迹智链 Web V3 · 路由根
 * 基于 hash 切换 Landing / Workbench:
 * - "#/workbench" → 交互原型工作台
 * - 其余(含站内锚点 #value/#method/#top 等)→ Landing 展示页
 * 站内锚点交给浏览器与 Lenis 处理原生滚动,不触发路由切换。
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Landing } from "./components/landing/Landing";
import { Workbench } from "./components/workbench/Workbench";

type Route = "landing" | "workbench";

/** 解析当前 hash,决定渲染哪个页面 */
function parseRoute(hash: string): Route {
  return hash.startsWith("#/workbench") ? "workbench" : "landing";
}

export default function App() {
  const [route, setRoute] = useState<Route>(() =>
    parseRoute(typeof window !== "undefined" ? window.location.hash : ""),
  );

  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  // 路由切换后处理滚动:优先滚到对应锚点,否则回到顶部
  useEffect(() => {
    if (route !== "landing") {
      window.scrollTo(0, 0);
      return;
    }
    const id = window.location.hash.replace("#", "");
    // 路由型 hash(#/...)或无锚点 → 回到顶部;站内锚点 → 滚到对应区块
    if (id && !id.startsWith("/")) {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
    }
    window.scrollTo(0, 0);
  }, [route]);

  return (
    <AnimatePresence mode="sync" initial={false}>
      <motion.div
        key={route}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      >
        {route === "workbench" ? <Workbench /> : <Landing />}
      </motion.div>
    </AnimatePresence>
  );
}
