/**
 * 工作流程区 + 三个场景区 + 可信边界区 + 阶段路线 + CTA
 * 剩余 Landing 区块合并文件,基于计划书§8.1、§4.2、§13、§16。
 */

import { motion } from "framer-motion";
import { cardReveal, scrollReveal, staggerContainer, viewportOnce, slideInLeft, slideInRight } from "../../lib/motion";
import { workflowSteps, scenarios, trustBoundaries, roadmap } from "../../data/content";
import { LinkButton } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { GlowOrb } from "../ui/GlowOrb";

/* ============================================================
 * 工作流程(五步)
 * ============================================================ */
export function Workflow() {
  return (
    <section id="workflow" className="relative py-32" style={{ background: "var(--bg-elev-1)" }}>
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid lg:grid-cols-[1.15fr_0.65fr] items-end gap-12 mb-16"
        >
          <motion.div variants={slideInLeft}>
            <p className="kicker mb-4">工作流程 / WORKFLOW</p>
            <h2 className="m-0 text-[clamp(2.5rem,4vw,3.875rem)] leading-[1.13] font-semibold tracking-[-0.055em] text-white">
              从文件到任务卡,<br />每一步都可复核。
            </h2>
          </motion.div>
          <motion.p variants={slideInRight} className="m-0 text-[16px] leading-[1.9] text-[var(--text-secondary)]">
            首版优先跑通 R1 单规则最小链路;R3—R8 只有通过资料可得性和阶段验收后才进入原型。
          </motion.p>
        </motion.div>

        <motion.ol
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="m-0 p-0 list-none border-t border-[var(--line-subtle)]"
        >
          {workflowSteps.map((step, i) => (
            <motion.li
              key={step.index}
              variants={{
                hidden: { opacity: 0, x: -30 },
                visible: { opacity: 1, x: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
              }}
              className="min-h-[172px] grid grid-cols-[auto_1fr] sm:grid-cols-[70px_1fr] items-center gap-7 border-b border-[var(--line-subtle)] py-6 group"
            >
              <span className="text-[var(--text-muted)] font-mono text-[11px]">{step.index}</span>
              <div>
                <h3 className="m-0 mb-2.5 text-[26px] tracking-[-0.03em] text-white">{step.title}</h3>
                <p className="m-0 max-w-[720px] text-[14px] leading-[1.8] text-[var(--text-secondary)]">{step.desc}</p>
              </div>
              {i < workflowSteps.length - 1 && (
                <span className="hidden sm:grid place-items-center w-11 h-11 rounded-full border border-[var(--line-subtle)] text-[var(--text-muted)] transition-all duration-200 group-hover:rotate-[-45deg] group-hover:bg-[var(--bg-elev-2)] group-hover:text-[var(--accent-teal)] absolute right-6">
                  ↘
                </span>
              )}
            </motion.li>
          ))}
        </motion.ol>
      </div>
    </section>
  );
}

/* ============================================================
 * 三个场景
 * ============================================================ */
export function Scenarios() {
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
          <motion.p variants={scrollReveal} className="kicker mb-4">使用场景 / SCENARIOS</motion.p>
          <motion.h2 variants={scrollReveal} className="m-0 text-[clamp(2.5rem,4vw,3.875rem)] leading-[1.13] font-semibold tracking-[-0.055em] text-white">
            承接、续聘、计划,各有明确边界
          </motion.h2>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid grid-cols-1 md:grid-cols-3 gap-4"
        >
          {scenarios.map((sc) => (
            <motion.div
              key={sc.id}
              variants={cardReveal}
              whileHover={{ y: -6 }}
              className="p-7 rounded-[20px] border border-[var(--line-subtle)] glass"
            >
              <h3 className="m-0 mb-5 text-[22px] font-medium text-white">{sc.title}</h3>
              <div className="mb-5">
                <p className="kicker mb-2">系统拟提供</p>
                <p className="m-0 text-[13px] leading-[1.8] text-[var(--text-secondary)]">{sc.provides}</p>
              </div>
              <div className="pt-5 border-t border-[var(--line-subtle)]">
                <p className="kicker mb-2" style={{ color: "var(--accent-coral)" }}>不替用户做</p>
                <p className="m-0 text-[13px] leading-[1.8] text-[var(--text-muted)]">{sc.notDo}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ============================================================
 * 可信边界 + 阶段路线
 * ============================================================ */
export function TrustBoundary() {
  return (
    <section id="boundary" className="relative py-32" style={{ background: "var(--bg-elev-1)" }}>
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid lg:grid-cols-[1.15fr_0.65fr] items-end gap-12 mb-16"
        >
          <motion.div variants={slideInLeft}>
            <p className="kicker mb-4">可信边界 / TRUST</p>
            <h2 className="m-0 text-[clamp(2.5rem,4vw,3.875rem)] leading-[1.13] font-semibold tracking-[-0.055em] text-white">
              先把能证明的部分,<br />做得足够可靠。
            </h2>
          </motion.div>
          <motion.p variants={slideInRight} className="m-0 text-[16px] leading-[1.9] text-[var(--text-secondary)]">
            项目已获准进入执行准备与最小原型阶段;规则、案例、实验配置与效果结论仍须逐项验证。
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 mb-5"
        >
          {trustBoundaries.map((item) => (
            <motion.article
              key={item.index}
              variants={cardReveal}
              className="min-h-[270px] p-6 rounded-[20px] border border-[var(--line-subtle)] glass"
            >
              <span className="text-[var(--text-muted)] font-mono text-[10px]">{item.index}</span>
              <h3 className="m-0 mt-[60px] mb-3.5 text-[20px] tracking-[-0.03em] text-white">{item.title}</h3>
              <p className="m-0 text-[12px] leading-[1.8] text-[var(--text-secondary)]">{item.desc}</p>
            </motion.article>
          ))}
        </motion.div>

        {/* 进度面板 */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={cardReveal}
          className="p-10 rounded-[20px] grid lg:grid-cols-[0.7fr_1.3fr] items-center gap-10 bg-[var(--bg-elev-2)] border border-[var(--line-subtle)]"
        >
          <div>
            <span className="text-[var(--accent-teal)] font-mono text-[9px] tracking-[0.14em]">CURRENT STATUS</span>
            <h3 className="m-0 mt-3 mb-2.5 text-[25px] text-white">当前进度:M1 开发样例接入</h3>
            <p className="m-0 text-[12px] leading-[1.8] text-[var(--text-secondary)]">
              三页骨架、R1-L1 方向规则和一份年报四项字段已接入;样例数字已回 PDF 抽查,仍待另一名队员完成人工复核。
            </p>
          </div>
          <ol className="m-0 p-0 grid grid-cols-4 gap-0 list-none relative">
            <span className="absolute left-[12%] right-[12%] top-[7px] h-px bg-[#30485b]" />
            {roadmap.map((stage) => (
              <li key={stage.stage} className="relative z-10 text-center">
                <span
                  className={`block w-3.5 h-3.5 mx-auto mb-3.5 rounded-full border-3 border-[var(--bg-elev-2)] ${
                    stage.status === "complete" ? "bg-[var(--accent-teal)]" :
                    stage.status === "active" ? "bg-[var(--accent-teal)]" :
                    "bg-[#4b6274]"
                  }`}
                  style={
                    stage.status === "complete"
                      ? { boxShadow: "0 0 0 5px rgba(74,222,184,0.12)" }
                      : stage.status === "active"
                        ? { boxShadow: "0 0 0 1px var(--accent-teal), 0 0 16px rgba(74,222,184,0.55)" }
                        : { boxShadow: "0 0 0 1px #4b6274" }
                  }
                />
                <span className="text-[var(--text-secondary)] font-mono text-[10px]">{stage.stage}</span>
                <p className="m-0 mt-1.5 text-[10px] text-[var(--text-muted)]">{stage.title}</p>
              </li>
            ))}
          </ol>
        </motion.div>
      </div>
    </section>
  );
}

/* ============================================================
 * CTA 行动召唤
 * ============================================================ */
export function CTA() {
  return (
    <section className="relative overflow-hidden py-36 text-center" style={{ background: "#07111a" }}>
      <div className="absolute inset-0 grid-bg" style={{ maskImage: "radial-gradient(circle at center, black, transparent 72%)" }} />
      <GlowOrb size={500} color="rgba(91,141,239,0.1)" className="left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2" />

      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={viewportOnce}
        variants={staggerContainer}
        className="relative flex flex-col items-center"
      >
        <motion.p variants={scrollReveal} className="kicker mb-4">AUDITTRACE · V3 · LOCAL STATIC</motion.p>
        <motion.h2 variants={scrollReveal} className="m-0 max-w-[880px] text-[clamp(2.75rem,5vw,4.5rem)] leading-[1.1] tracking-[-0.06em] text-white">
          先从一条可复算、可回指的规则开始。
        </motion.h2>
        <motion.p variants={scrollReveal} className="m-0 mt-6 max-w-[700px] text-[16px] leading-[1.85] text-[var(--text-secondary)]">
          当前原型已接入第一周年报开发样例,能够固定复算增长率、执行来源准入并保留人工复核。下一步是完成跨成员复核,再冻结正式案例与后续规则口径。
        </motion.p>
        <motion.div variants={scrollReveal} className="flex justify-center gap-3 mt-9">
          <LinkButton href="#/workbench" variant="primary">
            打开交互原型
            <span aria-hidden="true">↑</span>
          </LinkButton>
          <LinkButton href="#boundary" variant="secondary">
            查看当前边界
            <span aria-hidden="true">↗</span>
          </LinkButton>
        </motion.div>
      </motion.div>
    </section>
  );
}
