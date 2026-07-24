/**
 * 逐字/逐词渐入文字
 * 参考 Kimi 官网动效:每个字符从模糊下方浮入,stagger 延迟。
 * 使用 Framer Motion 的 staggerChildren 实现逐字动画。
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { staggerContainer, wordReveal } from "../../lib/motion";

interface TextRevealProps {
  text: string;
  className?: string;
  /** 是否作为行内元素(默认 block) */
  inline?: boolean;
  /** 额外的子元素(在文字后追加) */
  children?: ReactNode;
  /** 延迟启动(秒) */
  delay?: number;
}

export function TextReveal({ text, className = "", inline = false, children, delay = 0 }: TextRevealProps) {
  // 按字符拆分(中文逐字,英文按词),保留空格
  const chars = Array.from(text);

  const containerProps = {
    variants: staggerContainer,
    initial: "hidden" as const,
    animate: "visible" as const,
    transition: { delayChildren: delay },
  };

  const Tag = inline ? motion.span : motion.div;

  return (
    <Tag className={className} {...containerProps}>
      {chars.map((char, index) => (
        <motion.span
          key={`${char}-${index}`}
          variants={wordReveal}
          style={{ display: "inline-block", whiteSpace: "pre" }}
        >
          {char}
        </motion.span>
      ))}
      {children}
    </Tag>
  );
}

/**
 * 滚动触发版:配合 whileInView,在元素进入视口时逐字渐入
 */
interface TextRevealOnViewProps extends TextRevealProps {
  /** 视口触发距离 */
  margin?: string;
}

export function TextRevealOnView({ text, className = "", inline = false, children, delay = 0, margin = "-80px" }: TextRevealOnViewProps) {
  const chars = Array.from(text);

  const containerProps = {
    variants: staggerContainer,
    initial: "hidden" as const,
    whileInView: "visible" as const,
    viewport: { once: true, margin },
    transition: { delayChildren: delay },
  };

  const Tag = inline ? motion.span : motion.div;

  return (
    <Tag className={className} {...containerProps}>
      {chars.map((char, index) => (
        <motion.span
          key={`${char}-${index}`}
          variants={wordReveal}
          style={{ display: "inline-block", whiteSpace: "pre" }}
        >
          {char}
        </motion.span>
      ))}
      {children}
    </Tag>
  );
}
