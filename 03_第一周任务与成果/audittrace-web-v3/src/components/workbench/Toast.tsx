/**
 * 操作提示 Toast
 * 从底部滑入的玻璃拟态提示条,用于保存、换算、载入样例等操作反馈。
 * 沿用 app.js 的 showToast 行为:显示 2.3 秒后自动消失。
 */

import { AnimatePresence, motion } from "framer-motion";
import { easeOutExpo } from "../../lib/motion";

export interface ToastData {
  message: string;
  /** 自增 id,变化时触发重新进入动画 */
  id: number;
}

interface ToastProps {
  toast: ToastData | null;
}

export function Toast({ toast }: ToastProps) {
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] pointer-events-none">
      <AnimatePresence>
        {toast && (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.36, ease: easeOutExpo }}
            role="status"
            aria-live="polite"
            className="px-5 py-3.5 rounded-[14px] glass-strong text-[13px] text-[var(--text-primary)] max-w-[90vw] text-center border border-[var(--line-strong)]"
            style={{ boxShadow: "var(--shadow-card)" }}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
