/**
 * 首屏 Hero
 * 大标题逐字渐入,鼠标跟随光晕,背景动态光效,系统预览框。
 * 参考 Kimi 官网的首屏动效设计。
 */

import { motion, useReducedMotion } from "framer-motion";
import { useRef } from "react";
import { GlowOrb } from "../ui/GlowOrb";
import { LinkButton } from "../ui/Button";
import { TextReveal } from "../ui/TextReveal";
import { Chip } from "../ui/Chip";
import { easeOutExpo, staggerContainer, scrollReveal } from "../../lib/motion";

export function Hero() {
  const heroRef = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();

  return (
    <section
      ref={heroRef as React.RefObject<HTMLElement>}
      id="top"
      className="relative min-h-screen flex items-center overflow-hidden pt-32 pb-16"
      style={{ background: "linear-gradient(180deg, var(--bg-base) 0%, #07121c 68%, #0b1722 100%)" }}
    >
      {/* 背景网格 */}
      <div className="absolute inset-0 grid-bg opacity-40" style={{ maskImage: "linear-gradient(to bottom, black 0%, rgba(0,0,0,0.7) 55%, transparent 100%)" }} />

      {/* 扫描光带 */}
      <motion.div
        className="absolute inset-0"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(91,141,239,0.06), transparent)",
          transform: "translateX(-100%)",
        }}
        animate={reduceMotion ? {} : { x: ["-100%", "420%"] }}
        transition={{ duration: 11, repeat: Infinity, ease: "easeInOut", repeatDelay: 3 }}
      />

      {/* 漂浮光晕 */}
      <GlowOrb size={540} color="rgba(91,141,239,0.16)" className="right-[-180px] top-[120px]" duration={12} />
      <GlowOrb size={340} color="rgba(74,222,184,0.08)" className="left-[28%] bottom-[80px]" duration={16} reverse />

      <div className="relative mx-auto w-full max-w-[1400px] px-6 lg:px-12 grid lg:grid-cols-[0.9fr_1.1fr] items-center gap-12 lg:gap-16">
        {/* 左侧文案 */}
        <motion.div className="relative z-10">
          {/* eyebrow */}
          <motion.div
            className="flex items-center gap-4 mb-8"
            variants={staggerContainer}
            initial="hidden"
            animate="visible"
          >
            <motion.div variants={scrollReveal}>
              <Chip variant="default" dot>
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-teal)]" style={{ boxShadow: "0 0 12px rgba(74,222,184,0.7)" }} />
                W1 · 开发样例已接入
              </Chip>
            </motion.div>
            <motion.span variants={scrollReveal} className="text-[var(--text-muted)] font-mono text-[11px] tracking-[0.13em]">
              面向事务所审计项目组
            </motion.span>
          </motion.div>

          {/* 大标题逐字渐入 */}
          <TextReveal
            text="把分散的公开资料,"
            className="text-[clamp(2.5rem,5.35vw,4.875rem)] leading-[1.07] font-semibold tracking-[-0.065em] text-white max-w-[690px]"
          />
          <TextReveal
            text="变成可复核的审计前置线索。"
            delay={0.3}
            className="text-[clamp(2.5rem,5.35vw,4.875rem)] leading-[1.07] font-semibold tracking-[-0.065em] mt-2 text-gradient"
          />

          {/* 副标题 */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: easeOutExpo, delay: 0.8 }}
            className="max-w-[620px] mt-7 text-[18px] leading-[1.86] text-[var(--text-secondary)]"
          >
            审迹智链聚焦收入确认与销售收款循环,在承接、续聘和审计计划阶段,把异常信号连接到原文、计算、正常解释、资料缺口与下一步资料需求。
          </motion.p>

          {/* CTA 按钮 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: easeOutExpo, delay: 1.0 }}
            className="flex flex-wrap gap-3 mt-9"
          >
            <LinkButton href="#/workbench" variant="primary">
              体验三步原型
              <span aria-hidden="true">↗</span>
            </LinkButton>
            <LinkButton href="#method" variant="secondary">
              查看验证方法
              <span aria-hidden="true">↓</span>
            </LinkButton>
          </motion.div>

          {/* 边界提示 */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 1.3 }}
            className="max-w-[620px] mt-7 pt-5 border-t border-[var(--line-subtle)] text-[13px] leading-[1.75] text-[var(--text-muted)]"
          >
            <span className="mr-2 text-[var(--accent-blue)]">◆</span>
            当前仅用公开资料形成待核查线索,不形成审计结论、舞弊认定或自动承接决定。
          </motion.p>
        </motion.div>

        {/* 右侧系统预览框 */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, rotateY: -3 }}
          animate={{ opacity: 1, scale: 1, rotateY: 0 }}
          transition={{ duration: 1, ease: easeOutExpo, delay: 0.5 }}
          className="relative"
          style={{ perspective: "1000px" }}
        >
          {/* 装饰轨道 */}
          <motion.div
            className="absolute w-[210px] h-[210px] rounded-full border border-[var(--accent-blue)]/10 right-[-74px] top-[-88px] pointer-events-none"
            animate={reduceMotion ? {} : { rotate: 360 }}
            transition={{ duration: 24, repeat: Infinity, ease: "linear" }}
          >
            <span className="absolute w-[7px] h-[7px] left-[18%] top-[1%] rounded-full bg-[var(--accent-teal)]" style={{ boxShadow: "0 0 16px rgba(74,222,184,0.8)" }} />
          </motion.div>

          {/* 系统窗口 */}
          <div
            className="relative overflow-hidden rounded-[22px] glass-strong"
            style={{ boxShadow: "var(--shadow-deep), inset 0 1px 0 rgba(255,255,255,0.04)" }}
          >
            {/* 工具栏 */}
            <div className="min-h-[52px] px-5 flex items-center gap-4 border-b border-[var(--line-subtle)] text-[var(--text-muted)] font-mono text-[10px] tracking-[0.06em]">
              <span className="flex gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#486071]" />
                <span className="w-1.5 h-1.5 rounded-full bg-[#486071] opacity-65" />
                <span className="w-1.5 h-1.5 rounded-full bg-[#486071] opacity-40" />
              </span>
              <span>预审任务 / 演示结构</span>
              <span className="ml-auto flex items-center gap-2 text-[var(--text-secondary)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-teal)]" style={{ boxShadow: "0 0 12px rgba(74,222,184,0.7)" }} />
                样例可载入
              </span>
            </div>

            {/* 内容区 */}
            <div className="relative p-6 min-h-[420px]">
              {/* 来源卡片堆 */}
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(160px,0.9fr)_auto_minmax(200px,1.2fr)] gap-4 items-center">
                <div className="grid gap-2.5">
                  <p className="text-[var(--text-muted)] font-mono text-[9px] tracking-[0.16em] uppercase m-0 mb-1">T0 公开资料</p>
                  {[
                    { glyph: "年", title: "年度报告", sub: "文件 · 日期 · 页码", status: "样例已备" },
                    { glyph: "审", title: "审计报告", sub: "意见 · 关键事项", status: "待导入" },
                    { glyph: "行", title: "同行资料", sub: "口径 · 期间 · 来源", status: "可选" },
                  ].map((src, i) => (
                    <motion.div
                      key={src.title}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.5, ease: easeOutExpo, delay: 1 + i * 0.2 }}
                      className="grid grid-cols-[34px_1fr_auto] items-center gap-2.5 p-3.5 rounded-xl border border-[var(--line-subtle)] bg-white/[0.035]"
                    >
                      <span className="w-8 h-9 grid place-items-center rounded-lg border border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/10 text-[#a9c8f2] text-[11px] font-bold">
                        {src.glyph}
                      </span>
                      <div className="grid gap-1 min-w-0">
                        <strong className="text-[12px] font-medium text-[#d9e5ef]">{src.title}</strong>
                        <small className="text-[9px] text-[var(--text-muted)] truncate">{src.sub}</small>
                      </div>
                      <span className="text-[8px] font-mono text-[var(--text-muted)]">{src.status}</span>
                    </motion.div>
                  ))}
                </div>

                {/* 信号线 */}
                <div className="relative self-stretch hidden sm:block min-h-[60px]">
                  <div className="absolute left-2.5 right-2.5 top-1/2 h-px" style={{ background: "linear-gradient(90deg, rgba(91,141,239,0.1), rgba(91,141,239,0.8), rgba(74,222,184,0.4))" }} />
                  <motion.span
                    className="absolute top-[calc(50%-3px)] w-1.5 h-1.5 rounded-full bg-[var(--accent-blue)]"
                    style={{ boxShadow: "0 0 12px rgba(91,141,239,0.8)" }}
                    animate={reduceMotion ? {} : { left: ["8px", "calc(100% - 14px)"], opacity: [0, 1, 1, 0] }}
                    transition={{ duration: 3.2, repeat: Infinity, ease: "linear" }}
                  />
                  <span className="absolute left-1/2 top-[calc(50%+14px)] -translate-x-1/2 text-[7px] font-mono text-[var(--text-muted)] whitespace-nowrap">交叉验证</span>
                </div>

                {/* 风险卡预览 */}
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.6, ease: easeOutExpo, delay: 1.4 }}
                  className="p-5 rounded-2xl border border-[var(--accent-blue)]/20"
                  style={{
                    background: "linear-gradient(145deg, rgba(29,59,86,0.4), rgba(7,18,28,0.6))",
                    boxShadow: "0 24px 60px rgba(0,0,0,0.26)",
                  }}
                >
                  <div className="flex items-center justify-between gap-2.5 mb-5">
                    <span className="px-2.5 py-1.5 rounded-full bg-[var(--accent-blue)]/15 text-[#b9d2f3] text-[9px]">R1 · 草稿</span>
                    <span className="px-2.5 py-1.5 rounded-full border border-[var(--accent-amber)]/20 text-[var(--accent-amber)] text-[8px]">可复算</span>
                  </div>
                  <p className="text-[var(--text-muted)] font-mono text-[9px] tracking-[0.16em] uppercase m-0 mb-2">待核查事项结构</p>
                  <h2 className="m-0 text-[#ecf4fb] text-[17px] leading-[1.52] font-medium tracking-[-0.02em]">
                    应收增长与收入增长的关系需进一步核查
                  </h2>
                  <div className="flex flex-wrap gap-2.5 mt-4 text-[9px] text-[var(--text-muted)]">
                    <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-blue)]" /> 财务</span>
                    <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-teal)]" /> 业务</span>
                    <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-gray-600" /> 行业待补</span>
                  </div>
                  <div className="h-px my-5 bg-[var(--line-subtle)]" />
                  <div className="grid grid-cols-[1fr_auto] gap-2.5 text-[10px]">
                    <span className="text-[var(--text-muted)]">资料依据</span><strong className="text-[#a8bdce] font-medium">0 / 4</strong>
                    <span className="text-[var(--text-muted)]">正常解释</span><strong className="text-[#a8bdce] font-medium">待检索</strong>
                  </div>
                  <div className="mt-4 p-3 rounded-lg bg-[var(--accent-teal)]/[0.055]">
                    <span className="text-[var(--accent-teal)] font-mono text-[8px]">下一步</span>
                    <p className="m-0 mt-1.5 text-[#95aabc] text-[10px] leading-[1.6]">
                      导入年报字段,并核对账龄、期后回款与主要合同摘要。
                    </p>
                  </div>
                </motion.div>
              </div>
            </div>

            {/* 底部说明 */}
            <div className="min-h-[44px] px-5 flex items-center justify-between gap-3 border-t border-[var(--line-subtle)] text-[9px] text-[var(--text-muted)]">
              <span><span className="text-[var(--accent-amber)]">第一周开发样例</span>可载入经 PDF 抽查的年报字段;非冻结案例,仍待另一名队员复核</span>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
