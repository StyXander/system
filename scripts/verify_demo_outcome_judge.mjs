#!/usr/bin/env node
/* 演示版 outcomeFromRun 判定单测。

   从 assets/official-v4/demo-app.js 中提取 outcomeFromRun 纯函数源码执行（不复制逻辑），
   用两类真实运行 JSON 与构造向量验证 success/degraded/failed_run 边界。
   运行：node scripts/verify_demo_outcome_judge.mjs */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

const source = readFileSync(join(root, "assets", "official-v4", "demo-app.js"), "utf-8");
const match = source.match(/function outcomeFromRun\(run\) \{[\s\S]*?\n  \}/);
if (!match) {
  console.error("无法从 demo-app.js 提取 outcomeFromRun");
  process.exit(1);
}
const fn = new Function(`return (${match[0]})`)();

const stdSuccess = JSON.parse(
  readFileSync(
    join(root, "artifacts", "competition-demo-batch4-run", "RUN-V7-317207556AD0_std_full_analysis.json"),
    "utf-8"
  )
).run;
const stdDegraded = JSON.parse(
  readFileSync(
    join(root, "artifacts", "competition-demo-batch4-run", "attempt2", "run-audit-summary.json"),
    "utf-8"
  )
);
const degradedRunId = stdDegraded.run_response_posts?.find((p) => p.status === 200 && p.body?.run_id)?.body?.run_id;
if (!degradedRunId) {
  console.error("attempt2 摘要中缺少 POST /api/runs 响应体");
  process.exit(1);
}

const vectors = [
  {
    name: "完整成功：complete_full_analysis + model_success",
    run: stdSuccess,
    expect: "success",
  },
  {
    name: "模型失败降级：incomplete_model_chain_failed + provider_unreachable",
    run: {
      ...stdSuccess,
      run_completeness: "incomplete_model_chain_failed",
      model_check: { status: "provider_unreachable", execution_mode: "unavailable" },
      execution_mode: "unavailable",
    },
    expect: "degraded",
  },
  {
    name: "RAG 失败关闭 → failed_run",
    run: { ...stdSuccess, model_check: { status: "not_attempted_rag_failure" } },
    expect: "failed_run",
  },
  {
    name: "无规则结果 → failed_run",
    run: { ...stdSuccess, rule_results: [] },
    expect: "failed_run",
  },
  {
    name: "回放不得冒充成功 → success 拒绝，降级",
    run: { ...stdSuccess, execution_mode: "cache_replay" },
    expect: "degraded",
  },
  {
    name: "fallback 完整性不得冒充成功 → 降级",
    run: { ...stdSuccess, run_completeness: "complete_deterministic_fallback" },
    expect: "degraded",
  },
];

let failed = 0;
for (const v of vectors) {
  const got = fn(v.run);
  const ok = got === v.expect;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${v.name}  → got=${got} expect=${v.expect}`);
}
if (failed) {
  console.error(`${failed} vector(s) failed`);
  process.exit(1);
}
console.log("outcomeFromRun 判定单测全部通过");
