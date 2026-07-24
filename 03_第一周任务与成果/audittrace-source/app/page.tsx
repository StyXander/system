"use client";

import { FormEvent, KeyboardEvent, useState } from "react";

const methodDimensions = [
  { index: "01", title: "财务", body: "复算收入、应收、合同资产与现金流等确定性指标，保留公式与口径。" },
  { index: "02", title: "业务", body: "把异常连接到合同、履约、收入确认、应收与回款等销售循环节点。" },
  { index: "03", title: "行业", body: "仅在期间、产品与统计口径可比时，引入同行与公开行业资料进行对照。" },
  { index: "04", title: "披露", body: "核对管理层文字解释与报表结果是否一致；解释不足时保留为资料缺口。" },
];

const workflow = [
  ["01", "资料预检", "记录文件、披露日期、页码、单位与可读性；缺失项不由模型补齐。"],
  ["02", "确定性计算", "程序复算多年度指标，让审计人员能够按相同口径再次核对。"],
  ["03", "交叉验证", "首批聚焦 R1、R2，把财务信号连接到业务逻辑与公开解释。"],
  ["04", "反证挑战", "强制寻找正常原因与反对资料；找不到时明确标记待补充。"],
  ["05", "人工确认", "引用、公式和必填项通过后，才可进入待核查事项与资料清单。"],
];

const dataRows = [
  ["本年营业收入", "待导入", "—", "待替换：正式年报", "—", "未找到"],
  ["上年营业收入", "待导入", "—", "待替换：正式年报", "—", "未找到"],
  ["本年应收账款", "待导入", "—", "待替换：正式年报", "—", "未找到"],
  ["上年应收账款", "待导入", "—", "待替换：正式年报", "—", "未找到"],
];

const prototypeTabs = ["新建项目", "年报数据", "风险卡草稿"];

export default function Home() {
  const [activeStep, setActiveStep] = useState(0);
  const [projectCreated, setProjectCreated] = useState(false);
  const [reviewQueued, setReviewQueued] = useState(false);

  function handleProjectSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProjectCreated(true);
    setActiveStep(1);
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const keyTargets: Record<string, number> = {
      ArrowRight: (index + 1) % prototypeTabs.length,
      ArrowLeft: (index - 1 + prototypeTabs.length) % prototypeTabs.length,
      Home: 0,
      End: prototypeTabs.length - 1,
    };
    const next = keyTargets[event.key];
    if (next === undefined) return;
    event.preventDefault();
    setActiveStep(next);
    const tabs = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("[role='tab']");
    tabs?.[next]?.focus();
  }

  return (
    <>
      <a className="skip-link" href="#main-content">跳到主要内容</a>

      <header className="site-header">
        <div className="shell nav-shell">
          <a className="brand" href="#top" aria-label="审迹智链首页">
            <span className="brand-mark" aria-hidden="true"><i /></span>
            <span className="brand-copy"><strong>审迹智链</strong><small>AUDITTRACE</small></span>
          </a>
          <nav className="desktop-nav" aria-label="主要导航">
            <a href="#value">产品价值</a><a href="#method">验证方法</a><a href="#workflow">工作流程</a><a href="#boundary">边界与进度</a>
          </nav>
          <a className="button button-small button-primary" href="#prototype">
            <span className="desktop-label">查看交互原型</span><span className="mobile-label">查看原型</span><span aria-hidden="true">↗</span>
          </a>
        </div>
      </header>

      <main id="main-content">
        <section className="hero" id="top" aria-labelledby="hero-title">
          <div className="hero-grid" aria-hidden="true" />
          <div className="hero-glow hero-glow-one" aria-hidden="true" />
          <div className="hero-glow hero-glow-two" aria-hidden="true" />
          <div className="shell hero-layout">
            <div className="hero-copy">
              <div className="eyebrow-row">
                <span className="status-pill"><i aria-hidden="true" /> W1 · 最小原型阶段</span>
                <span className="eyebrow-text">面向事务所审计项目组</span>
              </div>
              <h1 id="hero-title">把分散的公开资料，<span>变成可复核的审计前置线索。</span></h1>
              <p className="hero-lede">审迹智链聚焦收入确认与销售收款循环，在承接、续聘和审计计划阶段，把异常信号连接到原文、计算、正常解释、资料缺口与下一步资料需求。</p>
              <div className="hero-actions">
                <a className="button button-primary" href="#prototype">体验三步原型 <span aria-hidden="true">↗</span></a>
                <a className="button button-secondary" href="#method">查看验证方法 <span aria-hidden="true">↓</span></a>
              </div>
              <p className="boundary-note"><span aria-hidden="true">◆</span>当前仅用公开资料形成待核查线索，不形成审计结论、舞弊认定或自动承接决定。</p>
            </div>

            <div className="hero-system" aria-label="风险线索形成过程示意">
              <div className="system-frame">
                <div className="system-toolbar">
                  <div className="window-dots" aria-hidden="true"><i /><i /><i /></div>
                  <span>预审任务 / 演示结构</span><span className="live-state"><i /> 待载入</span>
                </div>
                <div className="system-body">
                  <div className="source-stack">
                    <p className="system-kicker">T0 公开资料</p>
                    <article className="source-card source-card-one">
                      <span className="file-glyph" aria-hidden="true">年</span><div><strong>年度报告</strong><small>文件 · 日期 · 页码</small></div><span className="source-status">待导入</span>
                    </article>
                    <article className="source-card source-card-two">
                      <span className="file-glyph" aria-hidden="true">审</span><div><strong>审计报告</strong><small>意见 · 关键事项</small></div><span className="source-status">待导入</span>
                    </article>
                    <article className="source-card source-card-three">
                      <span className="file-glyph" aria-hidden="true">行</span><div><strong>同行资料</strong><small>口径 · 期间 · 来源</small></div><span className="source-status">可选</span>
                    </article>
                  </div>
                  <div className="signal-field" aria-hidden="true">
                    <span className="signal-line" /><span className="signal-dot signal-dot-a" /><span className="signal-dot signal-dot-b" /><span className="signal-label">交叉验证</span>
                  </div>
                  <article className="risk-preview">
                    <div className="risk-head"><span className="rule-chip">R1 · 草稿</span><span className="draft-chip">待数据验证</span></div>
                    <p className="system-kicker">待核查事项结构</p>
                    <h2>应收增长与收入增长的关系需进一步核查</h2>
                    <div className="risk-meta"><span><i className="meta-dot blue" /> 财务</span><span><i className="meta-dot teal" /> 业务</span><span><i className="meta-dot gray" /> 行业待补</span></div>
                    <div className="risk-divider" />
                    <div className="risk-evidence"><span>资料依据</span><strong>0 / 4</strong><span>正常解释</span><strong>待检索</strong></div>
                    <div className="risk-next"><span>下一步</span><p>导入年报字段，并核对账龄、期后回款与主要合同摘要。</p></div>
                  </article>
                </div>
                <div className="system-caption"><span>界面结构样例</span>未载入真实年报数据，不代表系统分析结果</div>
              </div>
              <div className="orbit orbit-one" aria-hidden="true"><i /></div><div className="orbit orbit-two" aria-hidden="true"><i /></div>
            </div>
          </div>
          <div className="shell proof-rail" aria-label="方法摘要">
            <span>来源定位</span><i /><span>确定性计算</span><i /><span>正常解释</span><i /><span>引用硬校验</span><i /><span>人工确认</span><b aria-hidden="true" />
          </div>
        </section>

        <section className="section section-light" id="value" aria-labelledby="value-title">
          <div className="shell">
            <div className="section-heading split-heading">
              <div><p className="section-kicker">产品价值 / VALUE</p><h2 id="value-title">预审不是自动下结论，<br />而是更早提出好问题。</h2></div>
              <p>公开资料通常不能证明每笔交易是否真实。审迹智链把无法回答的问题转成明确的资料依据缺口，让项目组知道下一步要核什么、向客户索取什么。</p>
            </div>
            <div className="value-grid">
              <article className="value-card value-card-featured">
                <div className="value-index">01</div><div className="mini-chain" aria-hidden="true"><span>异常信号</span><i>→</i><span>业务解释</span><i>→</i><span>核查动作</span></div><h3>从指标异常，走到销售循环节点</h3><p>不止提示“应收增速较快”，还关联信用政策、结算周期、履约条件与期后回款。</p>
              </article>
              <article className="value-card"><div className="value-index">02</div><div className="value-glyph glyph-sources" aria-hidden="true"><i /><i /><i /></div><h3>每个判断都保留回指路径</h3><p>来源、披露日期、页码、原文、单位与计算口径必须齐全；缺项只留在草稿区。</p></article>
              <article className="value-card"><div className="value-index">03</div><div className="value-glyph glyph-gap" aria-hidden="true"><i /><i /><i /></div><h3>把资料不足变成可执行清单</h3><p>账龄表、期后回款、主要合同摘要和大额销售明细，不再散落在分析笔记里。</p></article>
            </div>
          </div>
        </section>

        <section className="section section-dark" id="method" aria-labelledby="method-title">
          <div className="method-orbit" aria-hidden="true" />
          <div className="shell">
            <div className="section-heading method-heading">
              <div><p className="section-kicker section-kicker-dark">验证方法 / METHOD</p><h2 id="method-title">一条线索，需要四个维度相互约束。</h2></div>
              <p>多维触发只增加待核查的信息量，不自动提高风险等级；优先级仍交给审计人员判断。</p>
            </div>
            <div className="method-layout">
              <div className="dimension-grid">
                {methodDimensions.map((item) => <article className="dimension-card" key={item.index}><span>{item.index}</span><h3>{item.title}</h3><p>{item.body}</p></article>)}
              </div>
              <div className="method-core" aria-label="四维交叉验证结果示意">
                <div className="core-rings" aria-hidden="true"><i className="core-ring core-ring-one" /><i className="core-ring core-ring-two" /><i className="core-ring core-ring-three" /><span className="core-node node-finance">财务</span><span className="core-node node-business">业务</span><span className="core-node node-industry">行业</span><span className="core-node node-disclosure">披露</span></div>
                <div className="core-result"><small>OUTPUT</small><strong>待核查事项</strong><span>有来源 · 有反证 · 有缺口</span></div>
              </div>
            </div>
          </div>
        </section>

        <section className="section section-paper" id="workflow" aria-labelledby="workflow-title">
          <div className="shell">
            <div className="section-heading split-heading">
              <div><p className="section-kicker">工作流程 / WORKFLOW</p><h2 id="workflow-title">从文件到任务卡，<br />每一步都可复核。</h2></div>
              <p>首版优先跑通 R1 单规则最小链路；R3—R8 只有通过资料可得性和阶段验收后才进入原型。</p>
            </div>
            <ol className="workflow-list">
              {workflow.map(([index, title, body]) => <li key={index}><span className="workflow-index">{index}</span><div><h3>{title}</h3><p>{body}</p></div><span className="workflow-arrow" aria-hidden="true">↘</span></li>)}
            </ol>
          </div>
        </section>

        <section className="section prototype-section" id="prototype" aria-labelledby="prototype-title">
          <div className="prototype-glow" aria-hidden="true" />
          <div className="shell">
            <div className="section-heading prototype-heading">
              <div><p className="section-kicker section-kicker-dark">交互原型 / PROTOTYPE</p><h2 id="prototype-title">三步走完本周最小演示闭环。</h2></div>
              <p>当前版本验证页面结构与字段接口。真实年报数据、页码和计算结果将在团队资料完成后替换。</p>
            </div>
            <div className="prototype-window">
              <div className="prototype-topbar"><div className="prototype-brand"><span className="brand-mark mini" aria-hidden="true"><i /></span> 审迹智链工作台</div><div className="prototype-status"><i /> W1 · 结构演示</div></div>
              <div className="prototype-body">
                <div className="prototype-sidebar">
                  <p>预审项目</p>
                  <div className="tab-list" role="tablist" aria-label="原型步骤">
                    {prototypeTabs.map((tab, index) => (
                      <button className={activeStep === index ? "prototype-tab active" : "prototype-tab"} key={tab} type="button" role="tab" aria-selected={activeStep === index} aria-controls={`prototype-panel-${index}`} id={`prototype-tab-${index}`} tabIndex={activeStep === index ? 0 : -1} onKeyDown={(event) => handleTabKeyDown(event, index)} onClick={() => setActiveStep(index)}>
                        <span>{index + 1}</span>{tab}{index === 0 && projectCreated ? <b aria-label="已完成">✓</b> : null}
                      </button>
                    ))}
                  </div>
                  <div className="sidebar-boundary"><span>责任边界</span><p>不输出舞弊概率、审计意见或自动承接决定。</p></div>
                </div>
                <div className="prototype-content">
                  {activeStep === 0 ? (
                    <div className="prototype-panel" id="prototype-panel-0" role="tabpanel" aria-labelledby="prototype-tab-0">
                      <div className="panel-head"><div><span>STEP 01</span><h3>新建预审项目</h3><p>先确定分析对象、截止时点与使用场景。</p></div><span className="panel-state">尚未开始</span></div>
                      <form className="project-form" onSubmit={handleProjectSubmit}>
                        <label><span>公司 / 案例名称</span><input name="company" defaultValue="演示案例 A（待替换真实案例）" required /></label>
                        <label><span>分析截止日 T0</span><input name="analysisDate" type="date" defaultValue="2025-12-31" required /></label>
                        <label><span>分析场景</span><select name="scene" defaultValue="planning"><option value="acceptance">新客户业务承接</option><option value="renewal">续聘复核</option><option value="planning">审计计划</option></select></label>
                        <label><span>所属行业</span><input name="industry" placeholder="待团队确认后填写" /></label>
                        <div className="form-notice"><span aria-hidden="true">i</span>当前只使用 T0 前公开资料形成待核查线索，不形成审计结论。</div>
                        <button className="button button-primary form-submit" type="submit">建立项目框架 <span aria-hidden="true">→</span></button>
                      </form>
                    </div>
                  ) : null}

                  {activeStep === 1 ? (
                    <div className="prototype-panel" id="prototype-panel-1" role="tabpanel" aria-labelledby="prototype-tab-1">
                      <div className="panel-head"><div><span>STEP 02</span><h3>年报数据与来源台账</h3><p>每个数字都要能回到同一份正式披露原件。</p></div><span className="panel-state warning">0 / 4 已找到</span></div>
                      {projectCreated ? <div className="inline-success" role="status"><span aria-hidden="true">✓</span> 项目框架已建立。下一步请替换真实年报字段。</div> : null}
                      <div className="table-wrap">
                        <table><caption className="sr-only">R1 规则所需年报字段</caption><thead><tr><th>字段</th><th>数值</th><th>单位</th><th>来源</th><th>页码</th><th>状态</th></tr></thead>
                          <tbody>{dataRows.map((row) => <tr key={row[0]}>{row.map((cell, index) => <td key={`${row[0]}-${index}`} data-label={["字段", "数值", "单位", "来源", "页码", "状态"][index]}>{index === 5 ? <span className="missing-state"><i />{cell}</span> : cell}</td>)}</tr>)}</tbody>
                        </table>
                      </div>
                      <div className="data-footer"><p><strong>不得猜测：</strong> 找不到印刷页码时记录“原件未标注”；解析失败时转人工结构化录入并交叉复核。</p><button className="button button-outline" type="button" onClick={() => setActiveStep(2)}>查看风险卡结构 <span aria-hidden="true">→</span></button></div>
                    </div>
                  ) : null}

                  {activeStep === 2 ? (
                    <div className="prototype-panel" id="prototype-panel-2" role="tabpanel" aria-labelledby="prototype-tab-2">
                      <div className="panel-head"><div><span>STEP 03</span><h3>R1 风险卡草稿</h3><p>以下是输出结构，不是对任何真实公司的分析结论。</p></div><span className="panel-state warning">草稿 · 待验证</span></div>
                      <article className="audit-card">
                        <header><div><span>R1 / 收入确认</span><h4>应收账款增速与收入增速的关系需进一步核查</h4></div><span className="priority-chip">待计算</span></header>
                        <div className="audit-card-grid">
                          <section><span>发现了什么现象</span><p>尚未载入真实年报数字。规则将在数据齐备后比较收入与应收账款增速，并检查周转天数变化。</p></section>
                          <section><span>为什么需要进一步了解</span><p>若应收持续快于收入增长，可能需要核对信用政策、结算周期、履约条件与期后回款。</p></section>
                          <section><span>可能的正常原因</span><div className="reason-tags"><i>新增大客户</i><i>信用政策变化</i><i>季节性</i><i>行业账期拉长</i></div></section>
                          <section><span>目前缺少什么资料</span><p>真实年报数字、应收账款账龄、期后回款、主要合同摘要与大额销售明细。</p></section>
                        </div>
                        <footer><div><span>资料依据与计算</span><strong>关键字段未齐全，硬门槛暂不允许形成正式风险卡。</strong></div><button className={reviewQueued ? "button button-outline queued" : "button button-outline"} type="button" onClick={() => setReviewQueued(true)}>{reviewQueued ? "已加入人工复核" : "标记供人工复核"} <span aria-hidden="true">{reviewQueued ? "✓" : "→"}</span></button></footer>
                      </article>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="section section-light" id="boundary" aria-labelledby="boundary-title">
          <div className="shell">
            <div className="section-heading split-heading">
              <div><p className="section-kicker">可信边界 / TRUST</p><h2 id="boundary-title">先把能证明的部分，<br />做得足够可靠。</h2></div>
              <p>项目已获准进入执行准备与最小原型阶段；规则、案例、实验配置与效果结论仍须逐项验证。</p>
            </div>
            <div className="trust-grid">
              <article><span>01</span><h3>来源硬约束</h3><p>原文、页码、披露日期或关键字段缺失时，只输出资料缺口或暂缓。</p></article>
              <article><span>02</span><h3>公式由程序复算</h3><p>模型处理语义，数字与增长率由确定性程序计算并保留口径。</p></article>
              <article><span>03</span><h3>强制一次反证</h3><p>正常解释没有可核验支持时，如实写明“待补充资料”，不补造原因。</p></article>
              <article><span>04</span><h3>最终保留给人</h3><p>是否进入 Top 5、选择审计程序或形成审计结论，始终由审计人员决定。</p></article>
            </div>
            <div className="progress-panel">
              <div className="progress-copy"><span>CURRENT STATUS</span><h3>当前进度：M0 技术探路</h3><p>优先完成空白 Web 骨架、核心数据字段和一份年报的可回指录入；不使用假数据冒充分析结果。</p></div>
              <ol className="stage-track" aria-label="产品阶段"><li className="active"><i /><span>M0</span><p>骨架与字段</p></li><li><i /><span>M1</span><p>R1 最小链路</p></li><li><i /><span>M2</span><p>双规则 MVP</p></li><li><i /><span>M3</span><p>规则扩展</p></li></ol>
            </div>
          </div>
        </section>

        <section className="final-cta" aria-labelledby="cta-title">
          <div className="cta-grid" aria-hidden="true" />
          <div className="shell cta-inner">
            <p className="section-kicker section-kicker-dark">AUDITTRACE · W1</p><h2 id="cta-title">先从一条可复算、可回指的规则开始。</h2><p>当前原型已明确页面、字段和责任边界。下一版接入团队确认的一份真实年报数据与 R1 规则口径。</p>
            <div className="hero-actions cta-actions"><a className="button button-primary" href="#prototype">打开交互原型 <span aria-hidden="true">↑</span></a><a className="button button-secondary" href="#boundary">查看当前边界 <span aria-hidden="true">↗</span></a></div>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="shell footer-main"><div className="brand footer-brand"><span className="brand-mark" aria-hidden="true"><i /></span><span className="brand-copy"><strong>审迹智链</strong><small>AUDITTRACE</small></span></div><p>面向审计前置阶段的多维交叉验证与资料依据缺口识别。</p><a href="#top">返回顶部 ↑</a></div>
        <div className="shell footer-bottom"><span>V2.2 轻量执行修订版 · 2026.07</span><span>仅用于项目原型与方法验证，不构成审计结论或投资建议。</span></div>
      </footer>
    </>
  );
}
