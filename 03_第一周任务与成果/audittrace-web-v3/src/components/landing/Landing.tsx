/**
 * Landing 展示页 · 单页滚动容器
 * 依次组装:Nav → Hero → ValueProp → CrossVerify → Innovations →
 * RuleLibrary → Workflow → Scenarios → TrustBoundary → CTA。
 * 区块顺序与 V2 计划书展示逻辑一致,滚动渐入动画由各子组件自行控制。
 */

import { Nav } from "./Nav";
import { Hero } from "./Hero";
import { ValueProp } from "./ValueProp";
import { CrossVerify, Innovations, RuleLibrary } from "./Sections1";
import { Workflow, Scenarios, TrustBoundary, CTA } from "./Sections2";

export function Landing() {
  return (
    <main className="relative min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)]">
      <Nav />
      <Hero />
      <ValueProp />
      <CrossVerify />
      <Innovations />
      <RuleLibrary />
      <Workflow />
      <Scenarios />
      <TrustBoundary />
      <CTA />
    </main>
  );
}
