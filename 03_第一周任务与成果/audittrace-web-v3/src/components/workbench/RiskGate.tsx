/**
 * 准入门槛阻断卡
 * 五层校验链任一关卡未过时显示,明确说明缺口,不生成候选风险卡。
 * 视觉:虚线边 + 琥珀色,沿用 app.js 的 showRiskGate 文案口径。
 */

import { motion } from "framer-motion";
import { Button } from "../ui/Button";

interface RiskGateProps {
  title: string;
  text: string;
  /** 点击"返回数据页补充" */
  onBackToData: () => void;
}

export function RiskGate({ title, text, onBackToData }: RiskGateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      role="status"
      className="p-7 rounded-[20px] border-2 border-dashed border-[var(--accent-amber)]/40 bg-[var(--accent-amber)]/[0.04]"
    >
      <span className="text-[var(--accent-amber)] font-mono text-[10px] tracking-[0.16em] uppercase">
        来源准入门槛
      </span>
      <h4 className="m-0 mt-3 mb-2.5 text-[22px] font-semibold tracking-[-0.02em] text-white">
        {title}
      </h4>
      <p className="m-0 mb-5 text-[14px] leading-[1.8] text-[var(--text-secondary)]">{text}</p>
      <Button variant="secondary" size="sm" onClick={onBackToData}>
        返回数据页补充
        <span aria-hidden="true">→</span>
      </Button>
    </motion.div>
  );
}
