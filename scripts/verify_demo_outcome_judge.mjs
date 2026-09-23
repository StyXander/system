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

function extractString(name) {
  const match = source.match(new RegExp(`const ${name} = "([^"]+)";`));
  if (!match) {
    console.error(`无法从 demo-app.js 提取字符串常量 ${name}`);
    process.exit(1);
  }
  return match[1];
}

function extractArray(name) {
  const match = source.match(new RegExp(`const ${name} = (\\[[^\\]]*\\]);`));
  if (!match) {
    console.error(`无法从 demo-app.js 提取数组常量 ${name}`);
    process.exit(1);
  }
  return new Function(`return (${match[1]})`)();
}

function extractSet(name) {
  const match = source.match(new RegExp(`const ${name} = new Set\\(\\[([^\\]]*)\\]\\)`));
  if (!match) {
    console.error(`无法从 demo-app.js 提取集合常量 ${name}`);
    process.exit(1);
  }
  return new Function(`return new Set([${match[1]}])`)();
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
  G: "G 暂不分级（资料/口径受限）",
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

// ===== 任务三返工向量：缺失值不得被读成"已通过/无缺口"，旧运行须给出可读依据 =====
const isUnprovided = extract("isUnprovided");
const rawText = extract("rawText");
const factorValue = extract("factorValue");
const hasFactors = extract("hasFactors");
const joinChinese = extract("joinChinese");
const deriveEvidenceBasisFactors = extract("deriveEvidenceBasisFactors");
const GATE_TEXT = extractObject("GATE_TEXT");
const FACTOR_LABELS = extractObject("FACTOR_LABELS");
const COMPLETENESS_TEXT = extractObject("COMPLETENESS_TEXT");
const EVIDENCE_CONTROL_LABELS = extractObject("EVIDENCE_CONTROL_LABELS");
const UNKNOWN_FACTOR_MEANING = extractString("UNKNOWN_FACTOR_MEANING");
const EVIDENCE_REQUIRED_CONTROLS = extractArray("EVIDENCE_REQUIRED_CONTROLS");
const EVIDENCE_DECISIVE_FACTORS = extractSet("EVIDENCE_DECISIVE_FACTORS");
const PRIORITY_DECISIVE_FACTORS = extractSet("PRIORITY_DECISIVE_FACTORS");
const factorProvided = extractWithDeps("factorProvided", { isUnprovided });
const missingEvidenceControls = extractWithDeps("missingEvidenceControls", { EVIDENCE_REQUIRED_CONTROLS, factorProvided });
const missingSuffix = extractWithDeps("missingSuffix", { EVIDENCE_CONTROL_LABELS });
const explainEvidence = extractWithDeps("explainEvidence", {
  hasFactors, factorProvided, factorValue, missingEvidenceControls, missingSuffix, joinChinese,
});
const translateEvidenceFactor = extractWithDeps("translateEvidenceFactor", { GATE_TEXT, isUnprovided, UNKNOWN_FACTOR_MEANING });
const translatePriorityFactor = extractWithDeps("translatePriorityFactor", { COMPLETENESS_TEXT, isUnprovided, UNKNOWN_FACTOR_MEANING });
const mapFactorRows = extractWithDeps("mapFactorRows", { FACTOR_LABELS, rawText });
const evidenceFactorRows = extractWithDeps("evidenceFactorRows", { mapFactorRows, translateEvidenceFactor, EVIDENCE_DECISIVE_FACTORS });
const priorityFactorRows = extractWithDeps("priorityFactorRows", { mapFactorRows, translatePriorityFactor, PRIORITY_DECISIVE_FACTORS });
const EVIDENCE_BOUNDARY = extractString("EVIDENCE_BOUNDARY");

// C2：null / 缺字段是"未记录"，空集合才是"真实为 0"，两者措辞与结论都必须不同。
const partialE2 = explainEvidence("E2", [{ factor: "data_gaps", value: ["缺客户回款资料"] }]);
const nullGapRow = evidenceFactorRows([{ factor: "data_gaps", value: null }])[0];
const zeroGapRow = evidenceFactorRows([{ factor: "data_gaps", value: [] }])[0];
const nullMaterialRow = evidenceFactorRows([{ factor: "requested_materials", value: null }])[0];
const nullProxyRow = priorityFactorRows([{ factor: "blocked_row_proxy", value: null }])[0];
const nullStatusRow = priorityFactorRows([{ factor: "rule_statuses", value: null }])[0];
const claimsMissingRow = evidenceFactorRows([{ factor: "claims", value: {} }])[0];
const claimsZeroRow = evidenceFactorRows([{ factor: "claims", value: { total: 0 } }])[0];
const coveragePartialRow = evidenceFactorRows([{ factor: "coverage_matrix", value: { provided: true, rows: 5 } }])[0];
const gateMissingRow = evidenceFactorRows([{ factor: "numeric_gate" }])[0];
const e1Partial = explainEvidence("E1", [{ factor: "data_gaps", value: [] }]);
const c2Checks = [
  ["E2 缺闸门读数时不断言数字已通过", !partialE2.includes("数字校验已通过")],
  ["E2 缺读数时点名未提供", partialE2.includes("未提供")],
  ["E2 缺对应表时不写 0 项记录", !partialE2.includes("0 项记录包含当前企业")],
  ["data_gaps=null 显示未提供", nullGapRow.displayValue === "未提供" && nullGapRow.meaning.includes("不能视为没有缺口")],
  ["data_gaps=[] 才是真实 0 项", zeroGapRow.displayValue === "无" && zeroGapRow.meaning.includes("真实计数")],
  ["requested_materials=null 显示未提供", nullMaterialRow.displayValue === "未提供"],
  ["blocked_row_proxy=null 不得判成无受阻规则", nullProxyRow.displayValue === "未提供"],
  ["rule_statuses=null 不得判成无选用规则", nullStatusRow.displayValue === "未提供"],
  ["claims 缺 total 显示未提供", claimsMissingRow.displayValue === "未提供"],
  ["claims total=0 为真实 0 条", claimsZeroRow.displayValue === "0 条主张"],
  ["对应表缺直接证据行数显示未提供", coveragePartialRow.displayValue === "未提供"],
  ["闸门无读数既不判通过也不判未通过", gateMissingRow.displayValue === "未提供" && gateMissingRow.meaning.includes("不能据此断言")],
  ["E1 缺控制项时不断言主张均已绑定", !e1Partial.includes("均已绑定证据")],
  ["证据边界句与签字 §7.3 逐字一致", EVIDENCE_BOUNDARY === "证据闭合状态只描述本次运行的数字闸门、证据适配度、认定覆盖与主张绑定等控制项是否齐备，不是审计认定，不构成审计结论或审计意见。"],
];
c2Checks.forEach(([label, ok]) => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  C2 缺失值合同  ${label}`);
});

// C1：旧运行没有 evidence_state.factors，页面须从自身留痕重建依据，且不得改动原始对象。
const oldRunFixture = {
  context: {
    numeric_claim_trace: { passed: true, unverified_count: 0, key_unverified: [], key_unverified_count: 0 },
    evidence_fitness_violations: [],
    assertion_evidence_procedure_matrix: [
      { current_entity_direct_evidence: ["RAG-A" ] },
      { current_entity_direct_evidence: ["RAG-B"] },
      { current_entity_direct_evidence: ["RAG-C"] },
      { current_entity_direct_evidence: ["RAG-D"] },
      { current_entity_direct_evidence: [] },
    ],
  },
  rule_results: [{
    ai_draft: {
      claims: [{ text: "程序事实：收入增速与应收增速背离。", support_status: "supported", evidence_ids: ["PROC-R1-2025"] }],
      normal_explanations: [
        { text: "解释甲", support_status: "unverified_hypothesis", evidence_ids: [] },
        { text: "解释乙", support_status: "unverified_hypothesis", evidence_ids: [] },
      ],
      data_gaps: ["账龄结构", "期后回款", "信用政策变动", "主要客户合同结算条款"],
      requested_materials: ["账龄明细表", "期后回款记录", "信用政策说明", "主要合同关键条款摘要"],
    },
  }],
};
const fixtureBefore = JSON.stringify(oldRunFixture);
const derivedFactors = deriveEvidenceBasisFactors(oldRunFixture);
const derivedE2 = explainEvidence("E2", derivedFactors);
const c1Checks = [
  ["派生依据覆盖 6 个控制项", derivedFactors.length === 6],
  ["派生依据逐条标 derived", derivedFactors.every((item) => item.derived === true)],
  ["派生依据读出 4 项含直接证据的记录", derivedE2.includes("4 项记录包含当前企业的直接证据")],
  ["派生依据给出资料缺口条数", derivedE2.includes("4 项资料缺口")],
  ["派生依据给出待索取资料条数", derivedE2.includes("4 项待索取资料")],
  ["派生依据给出待验证解释条数", derivedE2.includes("2 条解释待验证")],
  ["派生依据不改动原始运行对象", JSON.stringify(oldRunFixture) === fixtureBefore],
  ["无因子时仍走未提供分支", explainEvidence("E2", []).includes("未随状态记录控制项读数值")],
];
c1Checks.forEach(([label, ok]) => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  C1 派生展示依据  ${label}`);
});

// 真实旧运行交叉核对：本机留痕存在时按它验一次，不存在则显式记 SKIPPED，不混进通过数。
let realRunChecks = 0;
const realOldRunPath = join(root, "outputs", "w21-w23-live-verification-20260919", "run_1_RUN-V7-A923212497D0.json");
if (existsSync(realOldRunPath)) {
  const realRun = JSON.parse(readFileSync(realOldRunPath, "utf-8")).result;
  const realFactors = deriveEvidenceBasisFactors(realRun);
  const realE2 = explainEvidence(realRun.evidence_state?.state, realFactors);
  const realChecks = [
    ["真实旧运行 闸门读数为 passed", (factorValue(realFactors, "numeric_gate") || {}).state === "passed"],
    ["真实旧运行 5 项含直接证据记录", realE2.includes("5 项记录包含当前企业的直接证据")],
    ["真实旧运行 2 条待验证解释", realE2.includes("2 条解释待验证")],
    ["真实旧运行 4 项资料缺口与 4 项待索取资料", realE2.includes("4 项资料缺口") && realE2.includes("4 项待索取资料")],
    ["真实旧运行 不再出现「未随状态记录控制项读数值」", !realE2.includes("未随状态记录控制项读数值")],
  ];
  realChecks.forEach(([label, ok]) => {
    if (!ok) failed += 1;
    console.log(`${ok ? "PASS" : "FAIL"}  C1 真实旧运行  ${label}`);
  });
  realRunChecks = realChecks.length;
} else {
  skipped += 1;
  console.log("SKIPPED  真实旧运行向量未执行：outputs/w21-w23-live-verification-20260919 不在本机。");
}

// 命名红线：呈现层不得出现被禁止的评级话术。简单字符串扫描会把"不构成无风险认定"这类
// 保护性否定边界句误判成违规，反而逼着页面删掉更严格的措辞；改为语义判定：
// 命中词只有在紧跟否定线索时才算合法，裸露使用一律违规。红线本身由自检兜底。
const forbidden = ["无风险", "风险评级", "信用等级", "企业风险等级", "Arbiter"];
const NEGATION_CUES = ["不构成", "不等于", "不代表", "不得", "并非", "没有", "不是", "不宣称", "未形成"];
function unguardedHits(text, term) {
  const hits = [];
  let index = text.indexOf(term);
  while (index !== -1) {
    const before = text.slice(Math.max(0, index - 8), index);
    if (!NEGATION_CUES.some((cue) => before.endsWith(cue))) hits.push(before + term);
    index = text.indexOf(term, index + term.length);
  }
  return hits;
}
forbidden.forEach((term) => {
  const hits = [...unguardedHits(source, term), ...unguardedHits(html, term)];
  if (hits.length) failed += 1;
  console.log(`${hits.length ? "FAIL" : "PASS"}  命名红线  无裸露「${term}」${hits.length ? ` → ${hits[0]}` : ""}`);
});
const redlineSelfChecks = [
  ["红线自检 肯定式「该企业无风险」必须判违规", unguardedHits("该企业无风险", "无风险").length === 1],
  ["红线自检 否定式「不构成无风险认定」必须放行", unguardedHits("也不构成无风险认定", "无风险").length === 0],
  ["红线自检 肯定式「风险评级」必须判违规", unguardedHits("本系统给出风险评级", "风险评级").length === 1],
];
redlineSelfChecks.forEach(([label, ok]) => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}`);
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
// 本轮返工新增的合同数：真实旧运行向量只在留痕存在时才计数，不把"没跑"混进通过数。
const reworkCount = c2Checks.length + c1Checks.length + redlineSelfChecks.length + realRunChecks;
if (failed) {
  console.error(`${failed} vector(s) failed; ${skipped} group(s) skipped`);
  process.exit(1);
}
console.log(`判定与前端状态合同全部通过（${vectors.length + reasonVectors.length + copyAssertions.length + contractCount + reworkCount} 项；跳过 ${skipped} 组本机产物向量）`);
