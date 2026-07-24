/**
 * 步骤3:R1 计算与风险卡草稿
 * 根据 hook 返回的状态决定显示 RiskGate(阻断)还是 AuditCard(候选)。
 * 指标条在数字可计算后即显示;候选卡需来源准入全部通过后才显示。
 * 沿用 app.js renderRiskCard 的状态文案与准入顺序。
 */

import { motion } from "framer-motion";
import type { AuditTraceState, ReviewInfo, RiskCardState } from "../../types";
import { computeR1 } from "../../lib/calc";
import { allCoreNumbersValid, resolveRiskCardState } from "../../lib/validate";
import { MetricStrip } from "./MetricStrip";
import { RiskGate } from "./RiskGate";
import { AuditCard } from "./AuditCard";
import { Chip } from "../ui/Chip";

interface StepRiskCardProps {
  state: AuditTraceState;
  onSaveReview: (review: ReviewInfo) => boolean;
  showToast: (message: string) => void;
  onGoToData: () => void;
}

/** 根据 cardState 映射顶部状态药丸 */
function statusChip(cardState: RiskCardState): { text: string; variant: "default" | "amber" | "teal" | "coral" } {
  if (cardState.kind === "gate") {
    switch (cardState.reason) {
      case "project-incomplete":
        return { text: "待项目字段", variant: "amber" };
      case "years-not-sequential":
        return { text: "年度关系无效", variant: "amber" };
      case "context-mismatch":
        return { text: "资料年度不匹配", variant: "amber" };
      case "numbers-invalid":
        return { text: "待可计算数据", variant: "amber" };
      case "evidence-incomplete":
        return { text: "待补全来源位置", variant: "amber" };
      default:
        return { text: "待数据接入", variant: "amber" };
    }
  }
  return cardState.direction === "candidate"
    ? { text: "候选现象,待人工复核", variant: "amber" }
    : { text: "未形成 R1 方向候选", variant: "teal" };
}

export function StepRiskCard({ state, onSaveReview, showToast, onGoToData }: StepRiskCardProps) {
  const cardState = resolveRiskCardState(state);
  const numbersValid = allCoreNumbersValid(state);
  const metrics = numbersValid ? computeR1(state) : { revenueGrowth: null, arGrowth: null, gap: null };
  const chip = statusChip(cardState);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="flex flex-col gap-5"
    >
      {/* 面板头 */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="text-[var(--text-muted)] font-mono text-[10px] tracking-[0.16em]">STEP 03</span>
          <h3 className="m-0 mt-2 text-[22px] font-semibold tracking-[-0.02em] text-white">R1 计算与风险卡草稿</h3>
          <p className="m-0 mt-1.5 text-[13px] text-[var(--text-secondary)]">只有数字可计算且四项来源定位齐全时,才显示候选卡。</p>
        </div>
        <Chip variant={chip.variant} dot>{chip.text}</Chip>
      </div>

      {/* 指标条 */}
      <MetricStrip result={metrics} />

      {/* 规则口径说明 */}
      <div className="p-5 rounded-[16px] border border-[var(--line-subtle)] bg-white/[0.02]">
        <span className="text-[var(--accent-blue)] font-mono text-[10px] tracking-[0.16em]">R1-L1 当前口径</span>
        <p className="m-0 mt-2.5 text-[13px] leading-[1.85] text-[var(--text-secondary)]">
          本周只比较本年与上年的营业收入增速、应收账款增速及其差额;应收增速高于收入增速时形成待核查候选,不自动判定风险等级。
        </p>
        <p className="m-0 mt-2 text-[13px] leading-[1.85] text-[var(--text-secondary)]">
          <strong className="text-white">暂不计算周转天数:</strong>只有连续期间数据与口径一致时才启用;资料不足或公式不能统一时标记"不可比",不强行降级计算。
        </p>
      </div>

      {/* 阻断卡 或 风险卡 */}
      {cardState.kind === "gate" ? (
        <RiskGate title={cardState.title} text={cardState.text} onBackToData={onGoToData} />
      ) : (
        <AuditCard
          title={cardState.title}
          observation={cardState.observation}
          direction={cardState.direction}
          state={state}
          onSaveReview={onSaveReview}
          showToast={showToast}
        />
      )}
    </motion.div>
  );
}
