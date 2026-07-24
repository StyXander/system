/**
 * 三项确定性指标条
 * 营业收入增速 / 应收账款增速 / 两者差额(百分点)。
 * 数值使用 Framer Motion 的 animate 函数从 0 滚动到目标值,
 * 尊重 prefers-reduced-motion(系统降低动效时瞬时显示)。
 * 口径沿用 app.js:差额使用"百分点",避免把两个增长率之差再次当作增长率。
 */

import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import type { R1CalcResult } from "../../types";

interface MetricStripProps {
  result: R1CalcResult;
}

/** 单个指标:从 0 滚动到目标百分比数值 */
function CountUpPercent({ value }: { value: number }) {
  const reduceMotion = useReducedMotion();
  // value 为比率(如 -0.2445),展示时乘以 100 并保留两位小数
  const [display, setDisplay] = useState(reduceMotion ? (value * 100).toFixed(2) : "0.00");

  useEffect(() => {
    if (reduceMotion) {
      setDisplay((value * 100).toFixed(2));
      return;
    }
    // animate 从 0 滚到 value,展示过程中乘以 100 并格式化
    const controls = animate(0, value, {
      duration: 0.8,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay((v * 100).toFixed(2)),
    });
    return () => controls.stop();
  }, [value, reduceMotion]);

  return <>{display}%</>;
}

/** 差额:从 0 滚动到目标百分点,带正负号 */
function CountUpGap({ value }: { value: number }) {
  const reduceMotion = useReducedMotion();
  const fmt = (v: number) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)} 个百分点`;
  const [display, setDisplay] = useState(reduceMotion ? fmt(value) : fmt(0));

  useEffect(() => {
    if (reduceMotion) {
      setDisplay(fmt(value));
      return;
    }
    const controls = animate(0, value, {
      duration: 0.8,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay(fmt(v)),
    });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduceMotion]);

  return <>{display}</>;
}

export function MetricStrip({ result }: MetricStripProps) {
  const { revenueGrowth, arGrowth, gap } = result;

  return (
    <div
      className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-5 rounded-[16px] border border-[var(--line-subtle)] bg-[var(--bg-elev-2)]"
      aria-label="R1 确定性计算结果"
    >
      <div className="flex flex-col gap-1.5">
        <span className="text-[var(--text-muted)] text-[12px]">营业收入增速</span>
        <strong className="text-[26px] font-semibold tracking-[-0.02em] text-white tabular-nums">
          {revenueGrowth === null ? "—" : <CountUpPercent value={revenueGrowth} />}
        </strong>
      </div>
      <div className="flex flex-col gap-1.5 sm:border-l sm:border-[var(--line-subtle)] sm:pl-5">
        <span className="text-[var(--text-muted)] text-[12px]">应收账款增速</span>
        <strong className="text-[26px] font-semibold tracking-[-0.02em] text-white tabular-nums">
          {arGrowth === null ? "—" : <CountUpPercent value={arGrowth} />}
        </strong>
      </div>
      <div className="flex flex-col gap-1.5 sm:border-l sm:border-[var(--line-subtle)] sm:pl-5">
        <span className="text-[var(--text-muted)] text-[12px]">两者差额</span>
        <strong className="text-[24px] font-semibold tracking-[-0.02em] text-[var(--accent-amber)] tabular-nums">
          {gap === null ? "—" : <CountUpGap value={gap} />}
        </strong>
        <small className="text-[var(--text-muted)] text-[10px]">应收增速 − 收入增速</small>
      </div>
    </div>
  );
}
