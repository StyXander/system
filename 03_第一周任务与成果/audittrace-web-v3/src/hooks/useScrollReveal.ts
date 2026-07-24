/**
 * 滚动渐入封装
 * 将 Framer Motion 的 whileInView + viewport 模式封装为可复用 hook,
 * 参考 Kimi 官网滚动渐入与视差位移效果。
 *
 * - useScrollReveal(): 返回 variants + viewport,直接展开到 motion 组件
 * - useParallax(ref, range): 基于元素在视口中的进度,返回 y/opacity 位移
 *
 * 尊重 prefers-reduced-motion:系统降低动效时,渐入变为瞬时,视差返回 undefined。
 */

import {
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "framer-motion";
import type { RefObject } from "react";
import { scrollReveal, viewportOnce, easeOutExpo } from "../lib/motion";

/** 滚动渐入:直接展开到 motion 组件的 props */
export function useScrollReveal() {
  const reduceMotion = useReducedMotion();

  if (reduceMotion) {
    // 降低动效时:不渐入,直接可见
    return {
      initial: false as const,
      whileInView: "visible" as const,
      viewport: viewportOnce,
      variants: {
        hidden: { opacity: 1 },
        visible: { opacity: 1 },
      },
    };
  }

  return {
    initial: "hidden" as const,
    whileInView: "visible" as const,
    viewport: viewportOnce,
    variants: scrollReveal,
  };
}

/**
 * 滚动视差:元素进入视口时,沿 Y 轴产生位移与透明度变化。
 * @param ref 目标元素的 ref(通过 useScroll 的 target 跟踪)
 * @param range 位移范围 [起始偏移, 结束偏移],默认 [80, -80]
 * @returns { y, opacity } MotionValue,可直接绑定到 motion 组件的 style
 */
export function useParallax<T extends HTMLElement>(
  ref: RefObject<T | null>,
  range: [number, number] = [80, -80],
): { y: MotionValue<number>; opacity: MotionValue<number> } {
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref as RefObject<HTMLElement>,
    offset: ["start end", "end start"],
  });

  // 默认视口进度 0.5(正中间)时 opacity = 1,两端渐隐
  const yRaw = useTransform(scrollYProgress, [0, 1], range);
  const opacityRaw = useTransform(scrollYProgress, [0, 0.15, 0.85, 1], [0, 1, 1, 0]);

  // 弹簧平滑:lerp 0.08 与 Lenis 一致
  const y = useSpring(yRaw, { stiffness: 120, damping: 30, mass: 0.4 });
  const opacity = useSpring(opacityRaw, { stiffness: 120, damping: 30, mass: 0.4 });

  if (reduceMotion) {
    // 降低动效时:不位移,保持可见
    return { y: useMotionValue(0), opacity: useMotionValue(1) };
  }

  return { y, opacity };
}

/** 视口配置:元素进入视口 100px 时触发,只触发一次(便捷导出) */
export { viewportOnce, easeOutExpo };
