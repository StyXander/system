/**
 * 风险卡主体
 * 来源准入全部通过后显示候选风险卡。沿用 app.js renderRiskCard 的卡结构与文案:
 * 现象 → 进一步了解 → 可能正常原因 → 缺少资料 → 四项来源引用 → (审计计划)建议程序 → 人工复核。
 * 程序不替人作保留、降级或暂缓决定。
 */

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { AuditTraceState, ReviewInfo, ReviewStatus } from "../../types";
import { fieldDefinitions } from "../../lib/calc";
import { Button } from "../ui/Button";

interface AuditCardProps {
  title: string;
  observation: string;
  direction: "candidate" | "no-candidate";
  state: AuditTraceState;
  onSaveReview: (review: ReviewInfo) => boolean;
  showToast: (message: string) => void;
}

const reviewStatusOptions: ReviewStatus[] = ["未复核", "保留为待核查候选", "降级", "暂缓"];

const reasonTags = ["新增大客户", "信用政策变化", "季节性", "行业账期拉长"];

export function AuditCard({ title, observation, direction, state, onSaveReview, showToast }: AuditCardProps) {
  const { project, data, review } = state;
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>(review.status);
  const [reviewNote, setReviewNote] = useState(review.note);

  // 载入样例等操作会更新 state.review,同步到本地表单
  useEffect(() => {
    setReviewStatus(review.status);
    setReviewNote(review.note);
  }, [review]);

  const handleSaveReview = () => {
    const saved = onSaveReview({ status: reviewStatus, note: reviewNote.trim() });
    showToast(
      saved ? "人工复核说明已保存在本浏览器" : "当前浏览器未允许本地保存",
    );
  };

  const isCandidate = direction === "candidate";

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-[20px] border border-[var(--accent-blue)]/25 glass overflow-hidden"
      style={{ boxShadow: "var(--shadow-card)" }}
    >
      {/* 头部 */}
      <header className="flex items-start justify-between gap-4 p-6 border-b border-[var(--line-subtle)]">
        <div>
          <span className="text-[var(--accent-blue)] font-mono text-[10px] tracking-[0.16em]">R1 / 收入确认</span>
          <h4 className="m-0 mt-2 text-[20px] font-semibold leading-[1.4] tracking-[-0.02em] text-white">{title}</h4>
        </div>
        <span
          className={`shrink-0 px-3 py-1.5 rounded-full text-[11px] font-mono border ${
            isCandidate
              ? "border-[var(--accent-amber)]/30 bg-[var(--accent-amber)]/[0.08] text-[var(--accent-amber)]"
              : "border-[var(--accent-teal)]/30 bg-[var(--accent-teal)]/[0.08] text-[var(--accent-teal)]"
          }`}
        >
          {isCandidate ? "候选现象" : "仅完成计算"}
        </span>
      </header>

      {/* 卡片网格 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-[var(--line-subtle)]">
        <section className="p-6 bg-[var(--bg-elev-2)]">
          <span className="text-[var(--text-muted)] font-mono text-[9px] tracking-[0.16em] uppercase">发现了什么现象</span>
          <p className="m-0 mt-2.5 text-[14px] leading-[1.85] text-[var(--text-secondary)]">{observation}</p>
        </section>
        <section className="p-6 bg-[var(--bg-elev-2)]">
          <span className="text-[var(--text-muted)] font-mono text-[9px] tracking-[0.16em] uppercase">为什么需要进一步了解</span>
          <p className="m-0 mt-2.5 text-[14px] leading-[1.85] text-[var(--text-secondary)]">
            若应收增速高于收入增速,可能需要核对信用政策、结算周期、履约条件与期后回款。该现象不能单独证明错报或舞弊。
          </p>
        </section>
        <section className="p-6 bg-[var(--bg-elev-2)]">
          <span className="text-[var(--text-muted)] font-mono text-[9px] tracking-[0.16em] uppercase">可能的正常原因</span>
          <div className="flex flex-wrap gap-2 mt-3">
            {reasonTags.map((tag) => (
              <span key={tag} className="px-2.5 py-1 rounded-full border border-[var(--line-strong)] bg-white/[0.03] text-[11px] text-[var(--text-secondary)]">
                {tag}
              </span>
            ))}
          </div>
          <p className="m-0 mt-3 text-[12px] leading-[1.7] text-[var(--text-muted)]">以上只是待核验方向,不代表已经找到支持证据。</p>
        </section>
        <section className="p-6 bg-[var(--bg-elev-2)]">
          <span className="text-[var(--text-muted)] font-mono text-[9px] tracking-[0.16em] uppercase">目前缺少什么资料</span>
          <p className="m-0 mt-2.5 text-[14px] leading-[1.85] text-[var(--text-secondary)]">
            应收账款账龄、期后回款、主要合同摘要与大额销售明细;合同和流水仅作为可选补充资料。
          </p>
        </section>

        {/* 四项来源引用 */}
        <section className="p-6 bg-[var(--bg-elev-2)] lg:col-span-2">
          <span className="text-[var(--text-muted)] font-mono text-[9px] tracking-[0.16em] uppercase">本卡引用的四项来源</span>
          <div className="mt-3 grid gap-2.5">
            {fieldDefinitions.map((field) => {
              const row = data[field.id];
              return (
                <div key={field.id} className="p-3.5 rounded-xl border border-[var(--line-subtle)] bg-white/[0.02]">
                  <strong className="text-[12px] font-medium text-white">
                    {field.label}:{row.value} {project.amountUnit}
                  </strong>
                  <p className="m-0 mt-1.5 text-[10px] leading-[1.7] text-[var(--text-muted)]">
                    {[row.sourceFile, `披露于 ${row.disclosureDate}`, `PDF 第 ${row.pdfPage} 页`, `印刷页码:${row.printPage}`, row.locator].join("｜")}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        {/* 仅审计计划场景显示:候选认定与建议程序 */}
        {project.scene === "审计计划" && (
          <section className="p-6 bg-[var(--bg-elev-2)] lg:col-span-2 border-t border-dashed border-[var(--accent-violet)]/20">
            <span className="text-[var(--accent-violet)] font-mono text-[9px] tracking-[0.16em] uppercase">仅在审计计划场景显示</span>
            <p className="m-0 mt-2.5 text-[13px] leading-[1.85] text-[var(--text-secondary)]">
              拟进一步了解信用政策和结算周期,检查期后回款,并选取相关合同摘要核对履约与收入确认条件。具体程序由项目组决定。
            </p>
          </section>
        )}
      </div>

      {/* 复核页脚 */}
      <footer className="flex flex-col sm:flex-row sm:items-end gap-4 p-6 border-t border-[var(--line-subtle)] bg-[var(--bg-elev-1)]">
        <div className="grid sm:grid-cols-[200px_1fr] gap-3 flex-1">
          <label className="grid gap-1.5">
            <span className="text-[var(--text-muted)] text-[11px]">人工复核处理</span>
            <select
              value={reviewStatus}
              onChange={(e) => setReviewStatus(e.target.value as ReviewStatus)}
              className="h-[42px] px-3 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[13px] text-white focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors"
            >
              {reviewStatusOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-1.5">
            <span className="text-[var(--text-muted)] text-[11px]">复核说明(可选)</span>
            <textarea
              value={reviewNote}
              onChange={(e) => setReviewNote(e.target.value)}
              rows={2}
              placeholder="由复核人填写理由或下一步"
              className="px-3 py-2 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[13px] text-white placeholder:text-[var(--text-muted)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors resize-none"
            />
          </label>
        </div>
        <Button variant="outline" onClick={handleSaveReview} className="shrink-0">
          保存人工复核
          <span aria-hidden="true">→</span>
        </Button>
      </footer>
    </motion.article>
  );
}
