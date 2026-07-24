/**
 * 交互原型工作台
 * 深色玻璃拟态窗口,模拟"审计工作台"质感。侧栏 tab 切换三步,
 * 支持键盘方向键(← → Home End)切换,沿用 app.js setActiveStep 行为。
 * 组件层只调用 hook,不内嵌计算逻辑。
 */

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useRef, useState } from "react";
import { useAuditTraceStore } from "../../hooks/useAuditTraceStore";
import { projectFieldsComplete } from "../../lib/calc";
import { LinkButton } from "../ui/Button";
import { StepProject } from "./StepProject";
import { StepData } from "./StepData";
import { StepRiskCard } from "./StepRiskCard";
import { Toast, type ToastData } from "./Toast";

const tabs = [
  { step: 0, label: "新建项目" },
  { step: 1, label: "年报数据" },
  { step: 2, label: "风险卡草稿" },
];

export function Workbench() {
  const [state, actions] = useAuditTraceStore();
  const [step, setStep] = useState(0);
  const [toast, setToast] = useState<ToastData | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toastId = useRef(0);

  const showToast = useCallback((message: string) => {
    // 沿用 app.js:新提示覆盖旧提示,2.3 秒后自动消失
    toastId.current += 1;
    setToast({ message, id: toastId.current });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2300);
  }, []);

  const goToStep = useCallback((next: number) => setStep(next), []);

  // 侧栏键盘导航:← → Home End,沿用 app.js bindEvents 的 tab 切换
  const handleTabKey = (e: React.KeyboardEvent, index: number) => {
    const targets: Record<string, number> = {
      ArrowRight: (index + 1) % tabs.length,
      ArrowLeft: (index - 1 + tabs.length) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    };
    if (targets[e.key] === undefined) return;
    e.preventDefault();
    const next = targets[e.key];
    setStep(next);
    // 聚焦到目标 tab
    requestAnimationFrame(() => {
      document.getElementById(`workbench-tab-${next}`)?.focus();
    });
  };

  const projectDone = projectFieldsComplete(state.project);

  return (
    <section id="workbench" className="relative min-h-screen py-16 px-4 sm:px-6 lg:px-12" style={{ background: "linear-gradient(180deg, var(--bg-base), #07121c)" }}>
      <div className="mx-auto max-w-[1400px]">
        {/* 顶部返回 + 标题 */}
        <div className="flex items-center justify-between mb-6">
          <LinkButton href="#top" variant="secondary" size="sm">
            <span aria-hidden="true">←</span> 返回首页
          </LinkButton>
          <span className="text-[var(--text-muted)] font-mono text-[11px] tracking-[0.13em]">交互原型 / PROTOTYPE</span>
        </div>

        {/* 工作台窗口 */}
        <div className="rounded-[22px] glass-strong overflow-hidden" style={{ boxShadow: "var(--shadow-deep)" }}>
          {/* 顶栏 */}
          <div className="min-h-[56px] px-5 sm:px-7 flex items-center justify-between gap-4 border-b border-[var(--line-subtle)]">
            <div className="flex items-center gap-3">
              <span className="relative w-6 h-6 rounded-full border border-[var(--accent-blue)]/70 grid place-items-center">
                <span className="absolute w-1 h-1 right-0 top-0.5 rounded-full bg-[var(--accent-teal)]" style={{ boxShadow: "0 0 8px rgba(74,222,184,0.8)" }} />
              </span>
              <strong className="text-[14px] tracking-[0.02em] text-white">审迹智链工作台</strong>
            </div>
            <span className="flex items-center gap-2 text-[var(--text-secondary)] font-mono text-[10px]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-teal)]" style={{ boxShadow: "0 0 10px rgba(74,222,184,0.7)" }} />
              W1 · 三人交付已接入 · 本地离线
            </span>
          </div>

          {/* 主体:侧栏 + 内容 */}
          <div className="grid lg:grid-cols-[220px_1fr]">
            {/* 侧栏 */}
            <aside className="flex flex-col gap-5 p-5 border-b lg:border-b-0 lg:border-r border-[var(--line-subtle)] bg-[var(--bg-elev-1)]">
              <p className="m-0 text-[var(--text-muted)] font-mono text-[10px] tracking-[0.16em] uppercase">预审项目</p>
              <div className="flex lg:flex-col gap-2" role="tablist" aria-label="原型步骤">
                {tabs.map((tab) => {
                  const active = step === tab.step;
                  const done = tab.step === 0 && projectDone;
                  return (
                    <button
                      key={tab.step}
                      id={`workbench-tab-${tab.step}`}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      tabIndex={active ? 0 : -1}
                      onClick={() => setStep(tab.step)}
                      onKeyDown={(e) => handleTabKey(e, tab.step)}
                      className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-[10px] text-[13px] text-left transition-colors duration-200 border ${
                        active
                          ? "bg-[var(--accent-blue)]/[0.1] border-[var(--accent-blue)]/30 text-white"
                          : "border-transparent text-[var(--text-secondary)] hover:bg-white/[0.03] hover:text-white"
                      }`}
                    >
                      <span className={`w-5 h-5 grid place-items-center rounded-full text-[11px] font-mono ${active ? "bg-[var(--accent-blue)] text-[var(--bg-base)]" : "border border-[var(--line-strong)] text-[var(--text-muted)]"}`}>
                        {done ? "✓" : tab.step + 1}
                      </span>
                      <span className="hidden sm:inline">{tab.label}</span>
                    </button>
                  );
                })}
              </div>
              <div className="mt-auto p-4 rounded-[12px] border border-dashed border-[var(--line-strong)]">
                <span className="text-[var(--text-muted)] font-mono text-[9px] tracking-[0.16em] uppercase">责任边界</span>
                <p className="m-0 mt-2 text-[11px] leading-[1.7] text-[var(--text-muted)]">不输出舞弊概率、审计意见或自动承接决定。</p>
              </div>
            </aside>

            {/* 内容区 */}
            <div className="p-5 sm:p-7 min-h-[480px]">
              <AnimatePresence mode="sync" initial={false}>
                <motion.div
                  key={step}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -12, position: "absolute", width: "100%" }}
                  transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                >
                  {step === 0 && (
                    <StepProject
                      state={state}
                      onSaveProject={actions.saveProject}
                      onLoadSample={actions.loadSample}
                      onClearAll={actions.clearAll}
                      showToast={showToast}
                      onGoToData={() => goToStep(1)}
                    />
                  )}
                  {step === 1 && (
                    <StepData
                      state={state}
                      onUpdateField={actions.updateDataField}
                      onSaveData={actions.saveData}
                      onCopySourceFile={actions.copySourceFile}
                      showToast={showToast}
                      onGoToRisk={() => goToStep(2)}
                    />
                  )}
                  {step === 2 && (
                    <StepRiskCard
                      state={state}
                      onSaveReview={actions.saveReview}
                      showToast={showToast}
                      onGoToData={() => goToStep(1)}
                    />
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>

      <Toast toast={toast} />
    </section>
  );
}
