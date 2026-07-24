/**
 * 四维交叉验证区 + 五项核心创新区 + 八条规则库区
 * 三区块合并文件,基于计划书§7.1、§7、§6.2。
 */

import { motion } from "framer-motion";
import { cardReveal, scrollReveal, staggerContainer, viewportOnce, slideInLeft, slideInRight } from "../../lib/motion";
import { dimensions, innovations, rules } from "../../data/content";
import { Chip } from "../ui/Chip";

/* ============================================================
 * 四维交叉验证
 * ============================================================ */
export function CrossVerify() {
  return (
    <section id="method" className="relative py-32 overflow-hidden" style={{ background: "var(--bg-base)" }}>
      {/* 装饰轨道 */}
      <div
        className="absolute rounded-full border border-[var(--accent-blue)]/[0.07]"
        style={{ width: 900, height: 900, right: -490, top: 30, boxShadow: "0 0 0 130px rgba(91,141,239,0.015), 0 0 0 260px rgba(91,141,239,0.012)" }}
      />

      <div className="relative mx-auto max-w-[1400px] px-6 lg:px-12">
        {/* 标题 */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid lg:grid-cols-[1fr_minmax(340px,0.65fr)] items-end gap-12 mb-16"
        >
          <motion.div variants={slideInLeft}>
            <p className="kicker mb-4">验证方法 / METHOD</p>
            <h2 className="m-0 text-[clamp(2.5rem,4vw,3.875rem)] leading-[1.13] font-semibold tracking-[-0.055em] text-white">
              一条线索,需要四个维度相互约束。
            </h2>
          </motion.div>
          <motion.p variants={slideInRight} className="m-0 text-[16px] leading-[1.9] text-[var(--text-secondary)]">
            多维触发只增加待核查的信息量,不自动提高风险等级;优先级仍交给审计人员判断。
          </motion.p>
        </motion.div>

        <div className="grid lg:grid-cols-[1fr_minmax(420px,0.8fr)] gap-16 items-center">
          {/* 四维卡片 */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={viewportOnce}
            variants={staggerContainer}
            className="grid grid-cols-1 sm:grid-cols-2 gap-3.5"
          >
            {dimensions.map((dim) => (
              <motion.div
                key={dim.id}
                variants={cardReveal}
                whileHover={{ borderColor: "rgba(91,141,239,0.34)", background: "rgba(91,141,239,0.045)" }}
                className="min-h-[310px] p-6 rounded-[20px] border border-[var(--line-subtle)] glass"
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <span className="pt-1.5 text-[var(--text-muted)] font-mono text-[10px]">{dim.index}</span>
                </div>
                <h3 className="m-0 my-3 text-[27px] font-medium text-white">{dim.title}</h3>
                <p className="m-0 text-[13px] leading-[1.85] text-[var(--text-secondary)]">{dim.desc}</p>
              </motion.div>
            ))}
          </motion.div>

          {/* 环形可视化 */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={viewportOnce}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            className="relative min-h-[420px] grid place-items-center"
          >
            {/* 旋转环 */}
            <motion.div
              className="absolute inset-[4%]"
              animate={{ rotate: 360 }}
              transition={{ duration: 38, repeat: Infinity, ease: "linear" }}
            >
              <span className="absolute inset-1/2 border border-[var(--accent-blue)]/15 rounded-full" style={{ width: "88%", height: "88%", transform: "translate(-50%, -50%)" }} />
              <span className="absolute inset-1/2 border border-dashed border-[var(--accent-blue)]/15 rounded-full" style={{ width: "64%", height: "64%", transform: "translate(-50%, -50%)" }} />
              <span className="absolute inset-1/2 border border-[var(--accent-teal)]/15 rounded-full" style={{ width: "42%", height: "42%", transform: "translate(-50%, -50%)" }} />
            </motion.div>

            {/* 四个节点 */}
            {[
              { label: "财务", pos: "top-[3%] left-[47%]" },
              { label: "业务", pos: "right-[1%] top-[48%]" },
              { label: "行业", pos: "bottom-[4%] left-[45%]" },
              { label: "披露", pos: "left-0 top-[47%]" },
            ].map((node) => (
              <span
                key={node.label}
                className={`absolute ${node.pos} px-3 py-2 rounded-full border border-[var(--line-strong)] bg-[var(--bg-elev-2)] text-[var(--text-secondary)] text-[11px]`}
              >
                {node.label}
              </span>
            ))}

            {/* 中心结果 */}
            <div
              className="relative z-10 w-[230px] h-[230px] flex flex-col items-center justify-center rounded-full border border-[var(--accent-blue)]/28"
              style={{
                background: "radial-gradient(circle, rgba(31,79,124,0.4), rgba(8,19,30,0.6) 67%)",
                boxShadow: "0 0 80px rgba(91,141,239,0.14), inset 0 0 60px rgba(91,141,239,0.05)",
              }}
            >
              <small className="text-[var(--accent-teal)] font-mono text-[8px] tracking-[0.18em]">OUTPUT</small>
              <strong className="my-3 text-[25px] text-white">待核查事项</strong>
              <span className="text-[var(--text-secondary)] text-[10px]">有来源 · 有反证 · 有缺口</span>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ============================================================
 * 五项核心创新
 * ============================================================ */
export function Innovations() {
  return (
    <section className="relative py-32" style={{ background: "var(--bg-elev-1)" }}>
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="mb-16"
        >
          <motion.p variants={scrollReveal} className="kicker mb-4">核心创新 / INNOVATION</motion.p>
          <motion.h2 variants={scrollReveal} className="m-0 text-[clamp(2.5rem,4vw,3.875rem)] leading-[1.13] font-semibold tracking-[-0.055em] text-white">
            五项专业流程与方法创新
          </motion.h2>
          <motion.p variants={scrollReveal} className="m-0 mt-5 max-w-[720px] text-[16px] leading-[1.9] text-[var(--text-secondary)]">
            均属于专业流程、方法与工程约束创新,不主张训练了新的基础模型或提出新的底层算法。
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid gap-4"
        >
          {innovations.map((item) => (
            <motion.div
              key={item.index}
              variants={cardReveal}
              whileHover={{ y: -4 }}
              className="relative grid grid-cols-[auto_1fr] gap-6 p-7 rounded-[20px] border border-[var(--line-subtle)] glass overflow-hidden"
            >
              {/* 左侧渐变索引条 */}
              <div className="flex flex-col items-center gap-3">
                <span className="text-[var(--text-muted)] font-mono text-[11px]">{item.index}</span>
                <span className="w-px flex-1 bg-gradient-to-b from-[var(--accent-blue)] to-transparent" style={{ minHeight: 40 }} />
              </div>
              <div>
                <h3 className="m-0 mb-2.5 text-[22px] font-medium tracking-[-0.03em] text-white">{item.title}</h3>
                <p className="m-0 text-[14px] leading-[1.85] text-[var(--text-secondary)]">{item.desc}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ============================================================
 * 八条规则库
 * ============================================================ */
export function RuleLibrary() {
  return (
    <section className="relative py-32" style={{ background: "var(--bg-base)" }}>
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="mb-16"
        >
          <motion.p variants={scrollReveal} className="kicker mb-4">规则库 / RULES</motion.p>
          <motion.h2 variants={scrollReveal} className="m-0 text-[clamp(2.5rem,4vw,3.875rem)] leading-[1.13] font-semibold tracking-[-0.055em] text-white">
            八条候选交叉验证规则
          </motion.h2>
          <motion.p variants={scrollReveal} className="m-0 mt-5 max-w-[720px] text-[16px] leading-[1.9] text-[var(--text-secondary)]">
            R1、R2 为首批端到端实现对象,R3—R8 须按资料可得性和阶段验收逐条接入;未通过只保留为规则卡,不包装成已实现功能。
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5"
        >
          {rules.map((rule) => {
            const isFirst = rule.status === "首批实现";
            return (
              <motion.div
                key={rule.id}
                variants={cardReveal}
                whileHover={{ y: -4, borderColor: "rgba(91,141,239,0.3)" }}
                className={`p-5 rounded-[16px] border ${isFirst ? "border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/[0.04]" : "border-[var(--line-subtle)] bg-white/[0.02]"} ${!isFirst ? "opacity-75" : ""}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className={`font-mono text-[13px] font-semibold ${isFirst ? "text-[var(--accent-blue)]" : "text-[var(--text-muted)]"}`}>{rule.id}</span>
                  <Chip variant={isFirst ? "blue" : "default"} dot>
                    {rule.status}
                  </Chip>
                </div>
                <h3 className="m-0 mb-2 text-[16px] font-medium text-white">{rule.title}</h3>
                <p className="m-0 text-[12px] leading-[1.7] text-[var(--text-secondary)] mb-3">{rule.desc}</p>
                <div className="pt-3 border-t border-[var(--line-subtle)]">
                  <p className="m-0 text-[10px] text-[var(--text-muted)] mb-1">资料:{rule.materials}</p>
                  <p className="m-0 text-[10px] text-[var(--accent-teal)]/80">下一步:{rule.next}</p>
                </div>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
