/**
 * 磁吸按钮 hook
 * 监听按钮内 mousemove,通过 useSpring 让按钮向鼠标方向位移最多 8px。
 * 鼠标离开时回弹到原位。尊重 prefers-reduced-motion。
 */

import { useMotionValue, useSpring } from "framer-motion";
import type { MouseEvent } from "react";

const MAX_DISPLACEMENT = 8;

export function useMagnetic() {
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const springConfig = { stiffness: 300, damping: 15, mass: 0.3 };
  const smoothX = useSpring(x, springConfig);
  const smoothY = useSpring(y, springConfig);

  const handleMouseMove = (e: MouseEvent<HTMLElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = e.clientX - (rect.left + rect.width / 2);
    const relY = e.clientY - (rect.top + rect.height / 2);
    // 按比例缩放到最大位移范围
    const scale = MAX_DISPLACEMENT / (rect.width / 2);
    x.set(Math.max(-MAX_DISPLACEMENT, Math.min(MAX_DISPLACEMENT, relX * scale)));
    y.set(Math.max(-MAX_DISPLACEMENT, Math.min(MAX_DISPLACEMENT, relY * scale)));
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return {
    magneticStyle: { x: smoothX, y: smoothY },
    handleMouseMove,
    handleMouseLeave,
  };
}
