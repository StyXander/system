/**
 * 光晕球
 * 用于背景装饰的模糊光球。配合 Framer Motion 实现缓慢漂移动画。
 * 参考 Kimi 官网的柔和光效。
 */

import { motion } from "framer-motion";

interface GlowOrbProps {
  /** 直径(px) */
  size?: number;
  /** 颜色,默认蓝色 */
  color?: string;
  /** 位置 */
  className?: string;
  /** 漂移动画时长(秒),默认 12 */
  duration?: number;
  /** 是否反向漂移 */
  reverse?: boolean;
  /** 透明度 */
  opacity?: number;
}

export function GlowOrb({
  size = 540,
  color = "rgba(91, 141, 239, 0.16)",
  className = "",
  duration = 12,
  reverse = false,
  opacity = 1,
}: GlowOrbProps) {
  return (
    <motion.div
      className={`absolute rounded-full pointer-events-none ${className}`}
      style={{
        width: size,
        height: size,
        background: color,
        filter: "blur(90px)",
        opacity,
        zIndex: -2,
      }}
      animate={{
        x: [0, reverse ? -size * 0.04 : size * 0.04],
        y: [0, reverse ? size * 0.05 : -size * 0.03],
        scale: [0.92, 1.06],
      }}
      transition={{
        duration,
        repeat: Infinity,
        repeatType: "reverse",
        ease: "easeInOut",
      }}
    />
  );
}
