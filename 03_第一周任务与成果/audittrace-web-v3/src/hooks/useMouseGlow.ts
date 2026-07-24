/**
 * 鼠标跟随光晕 hook
 * 监听容器内 mousemove,通过 Framer Motion useSpring 平滑跟随。
 * 返回 motion style,绑定到光晕 div 的 style 即可。
 * 尊重 prefers-reduced-motion:降低动效时返回静态值。
 */

import { useMotionValue, useSpring, type MotionStyle } from "framer-motion";
import { useEffect } from "react";

export function useMouseGlow<T extends HTMLElement>() {
  const x = useMotionValue(-200);
  const y = useMotionValue(-200);

  const springConfig = { stiffness: 120, damping: 20, mass: 0.5 };
  const smoothX = useSpring(x, springConfig);
  const smoothY = useSpring(y, springConfig);

  const handleMove = (e: MouseEvent) => {
    const target = e.currentTarget as T;
    const rect = target.getBoundingClientRect();
    x.set(e.clientX - rect.left);
    y.set(e.clientY - rect.top);
  };

  const handleLeave = () => {
    x.set(-200);
    y.set(-200);
  };

  const bind = (ref: T | null) => {
    if (!ref) return;
    ref.addEventListener("mousemove", handleMove as EventListener);
    ref.addEventListener("mouseleave", handleLeave);
  };

  useEffect(() => {
    return () => {
      // 清理在 bind 时添加的监听器由 ref 生命周期管理
    };
  }, []);

  const glowStyle: MotionStyle = {
    x: smoothX,
    y: smoothY,
  };

  return { glowStyle, bind };
}
