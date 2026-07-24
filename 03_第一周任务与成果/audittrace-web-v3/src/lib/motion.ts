/**
 * 审迹智链 AuditTrace · Framer Motion 共用变体与过渡曲线
 * 参考 Kimi 官网动效:逐字渐入、滚动渐入、弹性过渡
 */

import type { Transition, Variants } from "framer-motion";

/** 缓动曲线:先慢后快再慢,适合文字与卡片渐入 */
export const easeOutExpo: [number, number, number, number] = [0.22, 1, 0.36, 1];

/** 弹性曲线:适合磁吸按钮与交互反馈 */
export const easeSpring: Transition = {
  type: "spring",
  stiffness: 260,
  damping: 20,
  mass: 0.8,
};

/** 逐字/逐词渐入:从模糊下方浮入 */
export const wordReveal: Variants = {
  hidden: { opacity: 0, y: 20, filter: "blur(8px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.8, ease: easeOutExpo },
  },
};

/** 容器变体:子元素逐个渐入,stagger 延迟 */
export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.04, delayChildren: 0.1 },
  },
};

/** 滚动渐入:从下方浮入,配合 whileInView 使用 */
export const scrollReveal: Variants = {
  hidden: { opacity: 0, y: 40 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: easeOutExpo },
  },
};

/** 卡片渐入:带轻微缩放 */
export const cardReveal: Variants = {
  hidden: { opacity: 0, y: 30, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.6, ease: easeOutExpo },
  },
};

/** 从左滑入 */
export const slideInLeft: Variants = {
  hidden: { opacity: 0, x: -40 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.6, ease: easeOutExpo },
  },
};

/** 从右滑入 */
export const slideInRight: Variants = {
  hidden: { opacity: 0, x: 40 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.6, ease: easeOutExpo },
  },
};

/** 淡入(无位移) */
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.5, ease: easeOutExpo },
  },
};

/** 滚动视差:使用 useScroll + useTransform 时参考的位移范围 */
export const parallaxRanges = {
  y: [80, -80],
  opacity: [0, 1],
  scale: [0.95, 1],
};

/** 视口配置:元素进入视口 100px 时触发,只触发一次 */
export const viewportOnce = { once: true, margin: "-100px" } as const;
