/**
 * 产品价值区
 * 三卡布局:首卡深色特色卡(含异常→业务→核查链条),后两卡白底。
 * 滚动渐入 + hover 3D 倾斜效果。
 */

import { motion } from "framer-motion";
import { cardReveal, scrollReveal, staggerContainer, viewportOnce } from "../../lib/motion";

export function ValueProp() {
  return (
    <section
      id="value"
      className="relative py-32"
      style={{ background: "var(--bg-elev-1)" }}
    >
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        {/* 标题 */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid lg:grid-cols-[1.15fr_0.65fr] items-end gap-12 mb-16"
        >
          <motion.div variants={scrollReveal}>
            <p className="kicker mb-4">产品价值 / VALUE</p>
            <h2 className="m-0 text-[clamp(2.5rem,4vw,3.875rem)] leading-[1.13] font-semibold tracking-[-0.055em] text-white">
              预审不是自动下结论,<br />
              而是更早提出好问题。
            </h2>
          </motion.div>
          <motion.p variants={scrollReveal} className="m-0 text-[16px] leading-[1.9] text-[var(--text-secondary)]">
            公开资料通常不能证明每笔交易是否真实。审迹智链把无法回答的问题转成明确的资料依据缺口,让项目组知道下一步要核什么、向客户索取什么。
          </motion.p>
        </motion.div>

        {/* 三卡 */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
          className="grid grid-cols-1 lg:grid-cols-[1.22fr_0.89fr_0.89fr] gap-4"
        >
          {/* 特色卡 */}
          <motion.article
            variants={cardReveal}
            whileHover={{ y: -6, transition: { duration: 0.2 } }}
            className="min-h-[390px] p-7 flex flex-col rounded-[20px] border border-[var(--line-subtle)] bg-[var(--bg-elev-2)]"
          >
            <div className="text-[var(--text-muted)] font-mono text-[11px]">01</div>
            <div className="my-auto mb-3 flex items-center gap-2.5 text-[10px] text-[var(--text-secondary)]">
              <span className="p-2.5 border border-[var(--line-subtle)] rounded-lg bg-white/[0.03]">异常信号</span>
              <span className="text-[var(--accent-teal)]">→</span>
              <span className="p-2.5 border border-[var(--line-subtle)] rounded-lg bg-white/[0.03]">业务解释</span>
              <span className="text-[var(--accent-teal)]">→</span>
              <span className="p-2.5 border border-[var(--line-subtle)] rounded-lg bg-white/[0.03]">核查动作</span>
            </div>
            <h3 className="m-0 mt-auto mb-3.5 max-w-[320px] text-[25px] leading-[1.35] tracking-[-0.03em] text-white">
              从指标异常,走到销售循环节点
            </h3>
            <p className="m-0 text-[14px] leading-[1.85] text-[var(--text-secondary)]">
              不止提示"应收增速较快",还关联信用政策、结算周期、履约条件与期后回款。
            </p>
          </motion.article>

          {/* 卡 02 */}
          <motion.article
            variants={cardReveal}
            whileHover={{ y: -6, transition: { duration: 0.2 } }}
            className="min-h-[390px] p-7 flex flex-col rounded-[20px] border border-[var(--line-subtle)] glass"
          >
            <div className="text-[var(--text-muted)] font-mono text-[11px]">02</div>
            <div className="relative w-[150px] h-[120px] my-auto">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="absolute w-[78px] h-[92px] rounded-[11px] border border-[var(--line-subtle)] bg-white/[0.04]"
                  style={{
                    left: i === 0 ? 0 : i === 1 ? "28px" : "58px",
                    top: i === 0 ? "14px" : i === 1 ? "6px" : "16px",
                    transform: i === 0 ? "rotate(-8deg)" : i === 2 ? "rotate(8deg)" : "none",
                    borderColor: i === 2 ? "rgba(91,141,239,0.45)" : undefined,
                  }}
                />
              ))}
            </div>
            <h3 className="m-0 mt-auto mb-3.5 max-w-[320px] text-[25px] leading-[1.35] tracking-[-0.03em] text-white">
              每个判断都保留回指路径
            </h3>
            <p className="m-0 text-[14px] leading-[1.85] text-[var(--text-secondary)]">
              来源、披露日期、页码、原文、单位与计算口径必须齐全;缺项只留在草稿区。
            </p>
          </motion.article>

          {/* 卡 03 */}
          <motion.article
            variants={cardReveal}
            whileHover={{ y: -6, transition: { duration: 0.2 } }}
            className="min-h-[390px] p-7 flex flex-col rounded-[20px] border border-[var(--line-subtle)] glass"
          >
            <div className="text-[var(--text-muted)] font-mono text-[11px]">03</div>
            <div className="grid grid-cols-3 items-end gap-2.5 w-[150px] h-[120px] my-auto">
              <span className="block h-[40%] rounded-t-lg bg-[#b8c4cc]" />
              <span className="block h-[78%] rounded-t-lg bg-[var(--accent-blue)]" />
              <span className="block h-[56%] rounded-t-lg bg-[var(--accent-teal)]" />
            </div>
            <h3 className="m-0 mt-auto mb-3.5 max-w-[320px] text-[25px] leading-[1.35] tracking-[-0.03em] text-white">
              把资料不足变成可执行清单
            </h3>
            <p className="m-0 text-[14px] leading-[1.85] text-[var(--text-secondary)]">
              账龄表、期后回款、主要合同摘要和大额销售明细,不再散落在分析笔记里。
            </p>
          </motion.article>
        </motion.div>
      </div>
    </section>
  );
}
