/**
 * 磁吸按钮
 * 使用 useMagnetic hook,鼠标在按钮内移动时按钮向鼠标方向位移。
 * 支持三种变体:primary(白底)、secondary(玻璃边框)、outline(透明边框)。
 * 配合 hover 时的光晕扩散效果。
 */

import { motion } from "framer-motion";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useMagnetic } from "../../hooks/useMagnetic";

type Variant = "primary" | "secondary" | "outline";

interface ButtonProps extends Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  // framer-motion 的 motion.button 重新定义了 drag / animation 事件处理器类型,
  // 与 React 原生 ButtonHTMLAttributes 不兼容,这里排除以避免类型冲突。
  "children" | "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart" | "onAnimationIteration" | "onAnimationEnd"
> {
  variant?: Variant;
  children: ReactNode;
  /** 按钮尺寸 */
  size?: "sm" | "md" | "lg";
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-white text-[var(--bg-base)] hover:bg-[var(--accent-teal)] shadow-[0_12px_30px_rgba(0,0,0,0.16)] hover:shadow-[0_16px_40px_rgba(74,222,184,0.18)]",
  secondary:
    "text-white border border-white/20 bg-white/[0.04] hover:bg-white/[0.09] hover:border-white/40",
  outline:
    "text-[var(--bg-elev-1)] border border-black/20 bg-transparent hover:bg-[var(--bg-elev-1)] hover:text-white",
};

const sizeClasses = {
  sm: "min-h-[42px] px-4 text-[13px]",
  md: "min-h-[52px] px-[22px] text-[15px]",
  lg: "min-h-[58px] px-8 text-base",
};

export function Button({ variant = "primary", size = "md", className = "", children, ...props }: ButtonProps) {
  const { magneticStyle, handleMouseMove, handleMouseLeave } = useMagnetic();

  return (
    <motion.button
      style={magneticStyle}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 400, damping: 17 }}
      className={`inline-flex items-center justify-center gap-3.5 rounded-[12px] font-semibold tracking-[0.01em] cursor-pointer transition-colors duration-200 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </motion.button>
  );
}

/** 链接式磁吸按钮(用于 <a> 标签) */
interface LinkButtonProps {
  href: string;
  variant?: Variant;
  size?: "sm" | "md" | "lg";
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

export function LinkButton({ href, variant = "primary", size = "md", children, className = "", onClick }: LinkButtonProps) {
  const { magneticStyle, handleMouseMove, handleMouseLeave } = useMagnetic();

  return (
    <motion.a
      href={href}
      onClick={onClick}
      style={magneticStyle}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 400, damping: 17 }}
      className={`inline-flex items-center justify-center gap-3.5 rounded-[12px] font-semibold tracking-[0.01em] transition-colors duration-200 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
    >
      {children}
    </motion.a>
  );
}
