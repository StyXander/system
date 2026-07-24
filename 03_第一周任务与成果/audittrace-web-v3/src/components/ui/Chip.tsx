/**
 * 状态药丸
 * 用于显示状态标签,如"待核查"、"完整录入"、"已阻断"等。
 * 支持多种语义颜色变体。
 */

import clsx from "clsx";

type ChipVariant = "default" | "blue" | "teal" | "amber" | "coral";

interface ChipProps {
  children: React.ReactNode;
  variant?: ChipVariant;
  /** 是否显示色点 */
  dot?: boolean;
  className?: string;
}

const variantClasses: Record<ChipVariant, { wrap: string; dot: string }> = {
  default: {
    wrap: "border-white/[0.06] bg-white/[0.025] text-[var(--text-secondary)]",
    dot: "bg-[var(--text-muted)]",
  },
  blue: {
    wrap: "border-[var(--accent-blue)]/20 bg-[var(--accent-blue)]/[0.08] text-[#a9c8f2]",
    dot: "bg-[var(--accent-blue)]",
  },
  teal: {
    wrap: "border-[var(--accent-teal)]/20 bg-[var(--accent-teal)]/[0.08] text-[#8debc7]",
    dot: "bg-[var(--accent-teal)]",
  },
  amber: {
    wrap: "border-[var(--accent-amber)]/20 bg-[var(--accent-amber)]/[0.08] text-[#f5c870]",
    dot: "bg-[var(--accent-amber)]",
  },
  coral: {
    wrap: "border-[var(--accent-coral)]/20 bg-[var(--accent-coral)]/[0.08] text-[#f5a0a0]",
    dot: "bg-[var(--accent-coral)]",
  },
};

export function Chip({ children, variant = "default", dot = false, className = "" }: ChipProps) {
  const v = variantClasses[variant];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs whitespace-nowrap border",
        v.wrap,
        className,
      )}
    >
      {dot && <span className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0", v.dot)} />}
      {children}
    </span>
  );
}
