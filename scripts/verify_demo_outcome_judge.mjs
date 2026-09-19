#!/usr/bin/env node
/* 演示版 outcomeFromRun / degradedReason 判定与前端状态合同单测。

   从 assets/official-v4/demo-app.js 中提取纯函数与常量源码执行（不复制逻辑），
   用自洽向量覆盖 success / degraded 的五个分支 / failed_run 边界，
   并对 W09—W16 的呈现口径做合同断言：
   - incomplete_numeric_claims 必须落 numeric_gate_rejected，不得落 evidence_incomplete（W09）；
   - additional_procedure_required 必须是独立结论，且源码中不得再有改写（W10）；
   - 运行来源三态文案（W12）；
   - ⑥ 区六档标签与边界句逐字（W13）；
   - 无 evidence_id 的主张必须显式标注证据状态（W14）；
   - 抽取质量诊断文案不得复用泛化"资料不足"（W16）。

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
const html = readFileSync(join(root, "index.html"), "utf-8");

function extract(name) {
  const match = source.match(new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n  \\}`));
  if (!match) {
    console.error(`无法从 demo-app.js 提取 ${name}`);
    process.exit(1);
  }
  return new Function(`return (${match[0]})`)();
}

// 依赖注入版提取：用于函数体内引用了同文件其它助手的情况。
function extractWithDeps(name, deps) {
  const match = source.match(new RegExp(`function ${name}\\(([^)]*)\\) \\{[\\s\\S]*?\\n  \\}`));
  if (!match) {
    console.error(`无法从 demo-app.js 提取 ${name}`);
    process.exit(1);
  }
  const names = Object.keys(deps);
  return new Function(...names, `return (${match[0]})`)(...names.map((key) => deps[key]));
}

function extractObject(name) {
  const match = source.match(new RegExp(`const ${name} = (\\{[\\s\\S]*?\\n  \\});`));
  if (!match) {
    console.error(`无法从 demo-app.js 提取常量 ${name}`);
    process.exit(1);
  }
  return new Function(`return (${match[1]})`)();
}

const outcomeFromRun = extract("outcomeFromRun");
const degradedReason = extract("degradedReason");
const executionBadgeForRun = extract("executionBadgeForRun");
const DEGRADED_COPY = extractObject("DEGRADED_COPY");
const AUDIT_OVERVIEW_META = extractObject("AUDIT_OVERVIEW_META");
const ATTENTION_GRADE_LABELS = extractObject("ATTENTION_GRADE_LABELS");
const ATTENTION_EVIDENCE_LABELS = extractObject("ATTENTION_EVIDENCE_LABELS");
const SUPPORT_STATUS_LABELS = extractObject("SUPPORT_STATUS_LABELS");
const EVIDENCE_KIND_LABELS = extractObject("EVIDENCE_KIND_LABELS");
const PRIORITY_BOUNDARY = source.match(/const PRIORITY_BOUNDARY = "([^"]+)";/)[1];
const DETERMINISTIC_NOTE = source.match(/const DETERMINISTIC_NOTE = "([^"]+)";/)[1];
const escapeHtml = extract("escapeHtml");
const evidenceChainHtml = extractWithDeps("evidenceChainHtml", {
  escapeHtml,
  SUPPORT_STATUS_LABELS,
  currentCase: () => ({ case_id: "CNINFO_000858_T0_20260430" }),
  sourceLink: (caseId, documentId, page) => `/api/cases/${caseId}/sources/${documentId}#page=${page}`,
});
const evidenceLookup = extractWithDeps("evidenceLookup", { EVIDENCE_KIND_LABELS });
const extractionGateNotice = extract("extractionGateNotice");


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
  // W09：数字闸门拒绝发布是真实模型完成后的独立情形，绝不能被算成成功。
  { name: "incomplete_numeric_claims → 降级，不显示成功", run: { ...liveSuccess, run_completeness: "incomplete_numeric_claims" }, expect: "degraded" },
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
  // W09：真实调用已完成、只是关键数字追溯不到。这条向量直接取自
  // RUN-V7-43AD8C03C3A7 的实测留痕（provider_call_count=3、三角色 completed、
  // numeric_claim_trace.key_unverified=["41,813,685.32"]），不得再落 evidence_incomplete。
  {
    name: "incomplete_numeric_claims + model_success + 3 次真实调用 → 闸门拒绝，不是证据缺失",
    run: {
      ...liveSuccess,
      run_completeness: "incomplete_numeric_claims",
      context: { numeric_claim_trace: { passed: false, key_unverified: ["41,813,685.32"], key_unverified_count: 1 } },
    },
    expect: "numeric_gate_rejected",
    detail: { calls: 3, agentsDone: 1, unverified: ["41,813,685.32"], unverifiedCount: 1 },
  },
  {
    name: "优先读后端 numeric_gate_summary（轨 A W03 契约字段）",
    run: {
      ...liveSuccess,
      run_completeness: "incomplete_numeric_claims",
      numeric_gate_summary: { passed: false, key_unverified: ["1,234.00", "5,678.00"], unverified_count: 4, trace_count: 13 },
      context: { numeric_claim_trace: { key_unverified: ["不应被读到的回退值"], key_unverified_count: 9 } },
    },
    expect: "numeric_gate_rejected",
    detail: { calls: 3, unverified: ["1,234.00", "5,678.00"], unverifiedCount: 2 },
  },
  {
    name: "回放优先于闸门分支（cache_replay 不得被写成闸门拒绝）",
    run: {
      ...liveSuccess,
      execution_mode: "cache_replay",
      run_completeness: "incomplete_numeric_claims",
      context: { numeric_claim_trace: { key_unverified: ["1.00"], key_unverified_count: 1 } },
    },
    expect: "cache_replay",
  },
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
  const got = degradedReason(v.run);
  const ok = got.kind === v.expect;
  let detailOk = true;
  const detailProblems = [];
  if (ok && v.detail) {
    Object.entries(v.detail).forEach(([key, expected]) => {
      const actual = got[key];
      const same = Array.isArray(expected) ? JSON.stringify(actual) === JSON.stringify(expected) : actual === expected;
      if (!same) {
        detailOk = false;
        detailProblems.push(`${key}: got=${JSON.stringify(actual)} expect=${JSON.stringify(expected)}`);
      }
    });
  }
  if (!ok || !detailOk) failed += 1;
  console.log(`${ok && detailOk ? "PASS" : "FAIL"}  degradedReason  ${v.name}  → got=${got.kind} expect=${v.expect}${detailProblems.length ? ` | ${detailProblems.join("; ")}` : ""}`);
}

// W09 真话校验：闸门拒绝分支必须把真实调用次数、角色完成数与未通过数字写进文案，
// 且不得残留"没有可核验的调用留痕"那句已被证伪的话。
const gateVector = reasonVectors.find((item) => item.expect === "numeric_gate_rejected" && item.detail?.unverified);
const gateReason = degradedReason(gateVector.run);
const gateCopy = DEGRADED_COPY.numeric_gate_rejected;
const gateDetailText = gateCopy.gateDetail(gateReason, "三Agent已通过硬校验");
const gateChecks = [
  ["含真实调用次数", gateDetailText.includes(`${gateReason.calls} 次真实模型调用`)],
  ["含角色完成数", gateDetailText.includes(`${gateReason.agentsDone}/3 角色`)],
  ["含未通过数字原文", gateDetailText.includes("41,813,685.32")],
  ["含确定性结果仍可查看", gateDetailText.includes("确定性计算结果仍可查看")],
  ["不残留假话", !gateDetailText.includes("没有可核验的调用留痕")],
  ["stage 带调用数", gateCopy.stage(gateReason).includes("3")],
  ["pill 带调用数", gateCopy.pill(gateReason).includes("3 次真实模型调用")],
  ["gateTitle 逐字", gateCopy.gateTitle === "真实模型分析已完成，但未通过数字可追溯闸门"],
];
gateChecks.forEach(([label, ok]) => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  W09 闸门文案  ${label}`);
});

// 每个 degraded 分支必须给出与该分支一致的文字，且不得把回放写成模型未调用。
const copyAssertions = [
  { kind: "cache_replay", must: "已复用历史分析结果", mustNot: "本次未完成真实模型调用" },
  { kind: "deterministic_backup", must: "未调用外部模型", mustNot: "三Agent已通过硬校验" },
  { kind: "model_failed", must: "本次未完成真实模型调用", mustNot: "已复用历史" },
  { kind: "evidence_incomplete", must: "运行证据不完整", mustNot: "本次未完成真实模型调用" },
  { kind: "numeric_gate_rejected", must: "未通过数字可追溯闸门", mustNot: "没有可核验的调用留痕" },
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

// W10：additional_procedure_required 必须是独立结论，且坍缩逻辑不得残留。
const procedureMeta = AUDIT_OVERVIEW_META.additional_procedure_required;
const w10Checks = [
  ["META 有该条目", Boolean(procedureMeta)],
  ["label 逐字", procedureMeta?.label === "需执行额外程序后判断"],
  ["state 为 waiting", procedureMeta?.state === "waiting"],
  ["tone 不复用 gap", Boolean(procedureMeta) && procedureMeta.tone !== "gap"],
  ["procedureIds 不照抄 data_gap", JSON.stringify(procedureMeta?.procedureIds) !== JSON.stringify(AUDIT_OVERVIEW_META.data_gap.procedureIds)],
  ["源码已无坍缩改写", !/conclusion = dataGaps\.length \|\| requestedMaterials\.length \? "data_gap"/.test(source)],
];
w10Checks.forEach(([label, ok]) => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  W10 结论独立  ${label}`);
});

// W12：三态来源徽标文案，且必须自带文字、不靠颜色区分。
const badgeVectors = [
  { name: "external_live", run: { ...liveSuccess }, expect: "本次真实模型运行 · 3 次调用", mode: "external_live" },
  { name: "cache_replay", run: { ...liveSuccess, execution_mode: "cache_replay", provider_call_count: 0 }, expect: "已验证历史结果回放 · 本次新增 0 次调用", mode: "cache_replay" },
  { name: "deterministic_backup", run: { ...liveSuccess, execution_mode: "deterministic_backup", provider_call_count: 0 }, expect: "确定性备用链 · 未调用外部模型", mode: "deterministic_backup" },
];
badgeVectors.forEach((vector) => {
  const got = executionBadgeForRun(vector.run);
  const ok = got.label === vector.expect && got.mode === vector.mode;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  W12 来源徽标 ${vector.mode}  → got=${got.label} expect=${vector.expect}`);
});

// W13：六档标签与边界句逐字；证据三档标签；确定性标注。
const gradeExpect = {
  P1: "P1 立即扩大核查",
  P2: "P2 优先核查",
  P3: "P3 常规跟进",
  P4: "P4 维持常规程序",
  S: "S 暂缓判断",
  G: "G 暂不分级（资料或口径受限）",
};
Object.entries(gradeExpect).forEach(([key, label]) => {
  const ok = ATTENTION_GRADE_LABELS[key] === label;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  W13 优先级标签 ${key}  → got=${ATTENTION_GRADE_LABELS[key]} expect=${label}`);
});
["E1 已闭合", "E2 部分闭合", "E3 未闭合"].forEach((label, index) => {
  const key = `E${index + 1}`;
  const ok = ATTENTION_EVIDENCE_LABELS[key] === label;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  W13 证据闭合标签 ${key}`);
});
const w13Checks = [
  ["边界句逐字", PRIORITY_BOUNDARY === "本级别为审计计划阶段的程序筛查信号分级，不是审计认定，不构成审计结论或审计意见。"],
  ["确定性标注", DETERMINISTIC_NOTE === "确定性计算，非模型生成"],
  ["待验证解释标签", SUPPORT_STATUS_LABELS.unverified_hypothesis === "待验证解释"],
  ["六区容器齐备", ["demo-attention-signals", "demo-attention-counter", "demo-attention-review", "demo-attention-change", "demo-attention-procedures", "demo-attention-badges"].every((id) => html.includes(`id="${id}"`))],
];
w13Checks.forEach(([label, ok]) => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  W13 关注卡合同  ${label}`);
});

// W14：带 evidence_ids 的主张要给出五要素；不带的必须显式标注证据状态。
const lookupRun = {
  context: { case_id: "CNINFO_000858_T0_20260430" },
  evidence_bundle: {
    field_evidence: [{ evidence_id: "FIELD-A", report_year: null, year: 2025, pdf_page: 7, document_id: "DOC-2025" }],
    rag_evidence: [{ evidence_id: "RAG-A", report_year: 2025, pdf_page: 89, document_id: "DOC-2025" }],
  },
};
const lookup = evidenceLookup(lookupRun);
const boundHtml = evidenceChainHtml(lookupRun, lookup, { support_status: "unverified_hypothesis", evidence_ids: ["RAG-A"] });
const unboundHtml = evidenceChainHtml(lookupRun, lookup, { support_status: "unverified_hypothesis", evidence_ids: [] });
const unknownHtml = evidenceChainHtml(lookupRun, lookup, { support_status: null, evidence_ids: ["NOT-IN-BUNDLE"] });
const w14Checks = [
  ["五要素·Evidence ID", boundHtml.includes("Evidence ID RAG-A")],
  ["五要素·来源类型", boundHtml.includes("来源类型：RAG 检索片段")],
  ["五要素·PDF 年度", boundHtml.includes("PDF 年度 2025")],
  ["五要素·PDF 页码", boundHtml.includes("PDF 第 89 页")],
  ["五要素·查看原文", /<a href="\/api\/cases\/[^"]*\/sources\/DOC-2025#page=89"/.test(boundHtml) && boundHtml.includes("查看原文")],
  ["support_status 可见", boundHtml.includes("待验证解释")],
  ["无 evidence_id 显式标注", unboundHtml.includes("未绑定 Evidence ID") && unboundHtml.includes("不作为已核实事实")],
  ["证据不在本次包内不伪装", unknownHtml.includes("未在本次证据包登记") && unknownHtml.includes("原文入口未提供")],
];
w14Checks.forEach(([label, ok]) => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  W14 证据回链  ${label}`);
});

// W15/W16/W18：静态文案合同。
const w15_18Checks = [
  ["反确认逐字句", html.includes("本系统将反向检索与反证记录设计成强制工作流，而不是依赖一次对话中模型是否主动想到。")],
  ["无绝对化表述", !/通用大模型绝不会|绝不会这样做/.test(html + source)],
  ["护城河前移到关注卡之后", html.indexOf("demo-attention-badges") < html.indexOf("demo-enhancement-grid")],
  ["W16 抽取诊断标题逐字", extractionGateNotice({
    rule_results: [{ status: "DATA_GAP" }],
    context: { prescreen_plan: { candidate_quality_issues: ["自动提取金额的原始值仅为 1元，疑似附注号、序号或叙述数字，须人工回页确认。"], blocked_candidate_count: 5 } },
  })?.label === "自动抽取字段待人工回页确认，暂不评级"],
  ["W16 字段缺失时不假装透传", extractionGateNotice({ rule_results: [{ status: "DATA_GAP" }], context: {} }) === null],
  ["W16 无 DATA_GAP 时不触发", extractionGateNotice({
    rule_results: [{ status: "candidate" }],
    context: { prescreen_plan: { candidate_quality_issues: ["不应显示"] } },
  }) === null],
  ["W18 历史验收运行术语", html.includes("历史验收运行") && html.includes("不保证当前 HEAD 行为")],
];
w15_18Checks.forEach(([label, ok]) => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  W15/W16/W18 文案合同  ${label}`);
});

// 命名红线：新增呈现层不得出现被禁止的评级话术。
const forbidden = ["无风险", "风险评级", "信用等级", "企业风险等级", "Arbiter"];
forbidden.forEach((term) => {
  const hit = source.includes(term) || html.includes(term);
  if (hit) failed += 1;
  console.log(`${hit ? "FAIL" : "PASS"}  命名红线  未出现「${term}」`);
});

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

const contractCount = w10Checks.length + badgeVectors.length + Object.keys(gradeExpect).length + 3
  + w13Checks.length + w14Checks.length + w15_18Checks.length + forbidden.length + gateChecks.length;
if (failed) {
  console.error(`${failed} vector(s) failed; ${skipped} group(s) skipped`);
  process.exit(1);
}
console.log(`判定与前端状态合同全部通过（${vectors.length + reasonVectors.length + copyAssertions.length + contractCount} 项；跳过 ${skipped} 组本机产物向量）`);
