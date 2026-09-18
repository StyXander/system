#!/usr/bin/env node
/* 演示版 outcomeFromRun / degradedReason 判定单测。

   从 assets/official-v4/demo-app.js 中提取两个纯函数源码执行（不复制逻辑），
   用自洽向量覆盖 success / degraded 的四个分支 / failed_run 边界。

   历史版本只从 artifacts/ 下两个本机产物取基线向量，而 artifacts/ 整目录被
   .gitignore 排除（0 个受控文件），干净检出上本脚本必然 ENOENT 退出，门禁等于没跑。
   现在基线向量内联自洽，真实产物存在时作为附加向量执行，不存在时显式计数为 SKIPPED，
   不把"没执行"混进"通过"。

   运行：node scripts/verify_demo_outcome_judge.mjs */

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const source = readFileSync(join(root, "assets", "official-v4", "demo-app.js"), "utf-8");

function extract(name) {
  const match = source.match(new RegExp(`function ${name}\\(run\\) \\{[\\s\\S]*?\\n  \\}`));
  if (!match) {
    console.error(`无法从 demo-app.js 提取 ${name}`);
    process.exit(1);
  }
  return new Function(`return (${match[0]})`)();
}

const outcomeFromRun = extract("outcomeFromRun");
const degradedReason = extract("degradedReason");

// 自洽基线：一次真实的完整成功运行所必须具备的字段组合。
const liveSuccess = {
  run_id: "RUN-VECTOR-BASE",
  run_completeness: "complete_full_analysis",
  model_check: { status: "model_success", execution_mode: "external_live", cache_hit: false },
  execution_mode: "external_live",
  provider_call_count: 3,
  rule_results: [{ rule_id: "R1" }],
  source_validation: { issues: [] },
  agent_steps: [{ role: "challenge", status: "completed" }],
};

const vectors = [
  { name: "完整成功：complete_full_analysis + model_success + 3 次调用", run: liveSuccess, expect: "success" },
  { name: "模型失败降级：incomplete_model_chain_failed + provider_unreachable", run: { ...liveSuccess, run_completeness: "incomplete_model_chain_failed", model_check: { status: "provider_unreachable", execution_mode: "unavailable" }, execution_mode: "unavailable" }, expect: "degraded" },
  { name: "RAG 失败关闭 → failed_run", run: { ...liveSuccess, model_check: { status: "not_attempted_rag_failure" } }, expect: "failed_run" },
  { name: "无规则结果 → failed_run", run: { ...liveSuccess, rule_results: [] }, expect: "failed_run" },
  { name: "来源闸门未通过 → failed_run", run: { ...liveSuccess, source_validation: { issues: ["来源文件SHA-256不一致"] } }, expect: "failed_run" },
  { name: "回放不得冒充成功 → 降级", run: { ...liveSuccess, execution_mode: "cache_replay" }, expect: "degraded" },
  { name: "fallback 完整性不得冒充成功 → 降级", run: { ...liveSuccess, run_completeness: "complete_deterministic_fallback" }, expect: "degraded" },
  { name: "确定性备用不得冒充成功 → 降级", run: { ...liveSuccess, execution_mode: "deterministic_backup" }, expect: "degraded" },
  { name: "model_success 但本次 0 次调用 → 降级（不记成功）", run: { ...liveSuccess, provider_call_count: 0 }, expect: "degraded" },
];

// degraded 内部必须再分四类：一律写成"本次未完成真实模型调用"会在回放时
// 与同屏的"三Agent已通过硬校验 · 3/3 角色完成"直接互斥。
const reasonVectors = [
  { name: "可信历史回放", run: { ...liveSuccess, execution_mode: "cache_replay", provider_call_count: 0 }, expect: "cache_replay" },
  { name: "model_check.cache_hit 为真也算回放", run: { ...liveSuccess, model_check: { status: "model_success", cache_hit: true } }, expect: "cache_replay" },
  { name: "确定性备用", run: { ...liveSuccess, execution_mode: "deterministic_backup", provider_call_count: 0 }, expect: "deterministic_backup" },
  { name: "demo_fallback 也算确定性备用", run: { ...liveSuccess, model_check: { status: "demo_fallback" } }, expect: "deterministic_backup" },
  { name: "真实模型失败", run: { ...liveSuccess, run_completeness: "incomplete_model_chain_failed", model_check: { status: "provider_unreachable" }, execution_mode: "unavailable", provider_call_count: 0 }, expect: "model_failed" },
  { name: "自称成功却无本次调用留痕 → 证据不完整，不断言未执行", run: { ...liveSuccess, provider_call_count: 0 }, expect: "evidence_incomplete" },
  { name: "完整态含 fallback → 证据不完整", run: { ...liveSuccess, run_completeness: "complete_deterministic_fallback", provider_call_count: 2 }, expect: "evidence_incomplete" },
];

let failed = 0;
let skipped = 0;

for (const v of vectors) {
  const got = outcomeFromRun(v.run);
  const ok = got === v.expect;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  outcomeFromRun  ${v.name}  → got=${got} expect=${v.expect}`);
}

for (const v of reasonVectors) {
  const got = degradedReason(v.run).kind;
  const ok = got === v.expect;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  degradedReason  ${v.name}  → got=${got} expect=${v.expect}`);
}

// 每个 degraded 分支必须给出与该分支一致的文字，且不得把回放写成模型未调用。
const copyAssertions = [
  { kind: "cache_replay", must: "已复用历史分析结果", mustNot: "本次未完成真实模型调用" },
  { kind: "deterministic_backup", must: "未调用外部模型", mustNot: "三Agent已通过硬校验" },
  { kind: "model_failed", must: "本次未完成真实模型调用", mustNot: "已复用历史" },
  { kind: "evidence_incomplete", must: "运行证据不完整", mustNot: "本次未完成真实模型调用" },
];
for (const c of copyAssertions) {
  const block = source.match(new RegExp(`${c.kind}: \\{[\\s\\S]*?\\n    \\}`));
  if (!block) {
    console.log(`FAIL  DEGRADED_COPY 缺少 ${c.kind} 分支`);
    failed += 1;
    continue;
  }
  const text = block[0];
  const hasMust = text.includes(c.must);
  const lacksMustNot = !text.includes(c.mustNot);
  const ok = hasMust && lacksMustNot;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  DEGRADED_COPY ${c.kind}  含"${c.must}"=${hasMust} 不含"${c.mustNot}"=${lacksMustNot}`);
}

// 真实产物向量：本机有就跑，没有就显式记 SKIPPED，不计入通过。
const artifactDir = join(root, "artifacts", "competition-demo-batch4-run");
const realRunPath = join(artifactDir, "RUN-V7-317207556AD0_std_full_analysis.json");
const summaryPath = join(artifactDir, "attempt2", "run-audit-summary.json");
if (existsSync(realRunPath) && existsSync(summaryPath)) {
  const stdSuccess = JSON.parse(readFileSync(realRunPath, "utf-8")).run;
  console.log(`PASS  真实产物基线向量已加载（${stdSuccess.run_id}）`);
  const realGot = outcomeFromRun(stdSuccess);
  if (realGot !== "success") { failed += 1; }
  console.log(`${realGot === "success" ? "PASS" : "FAIL"}  真实产物  完整成功运行  → got=${realGot} expect=success`);
} else {
  skipped += 1;
  console.log("SKIPPED  真实产物向量未执行：artifacts/ 被 .gitignore 排除，本目录不在版本库内。");
}

if (failed) {
  console.error(`${failed} vector(s) failed; ${skipped} group(s) skipped`);
  process.exit(1);
}
console.log(`outcomeFromRun / degradedReason 判定单测全部通过（${vectors.length + reasonVectors.length + copyAssertions.length} 项；跳过 ${skipped} 组本机产物向量）`);
