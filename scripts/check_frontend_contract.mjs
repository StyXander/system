import { readFileSync } from "node:fs";

// 竞赛演示版前端契约：校验根 index.html 与 demo-app.js 的精简演示合同。
// 依据《竞赛演示版功能精简与高稳定性改造计划》§10.1、§18.2、§18.3、§18.7：
// - 公开页面只有一个主要运行按钮，不出现登录/上传/run_id/cache_id/补充资料控件；
// - 现场样例只允许既有巨潮公开来源任务，并由服务端现场模式开关保护；
// - 页面只加载 demo-app.js，不引用旧控制台脚本与沉浸式首屏脚本；
// - 首屏初始化只读取演示启动快照，效果评估只在抽屉打开时惰性读取；
// - 旧高级接口不得被演示脚本调用；运行必须带超时与中止控制器。
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const app = readFileSync(new URL("../assets/official-v4/demo-app.js", import.meta.url), "utf8");
const styles = readFileSync(new URL("../assets/official-v4/styles.css", import.meta.url), "utf8");
const backend = readFileSync(new URL("../backend/app/main.py", import.meta.url), "utf8");
const failures = [];

const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const idSet = new Set(ids);
for (const id of ids) {
  if (ids.indexOf(id) !== ids.lastIndexOf(id)) failures.push(`duplicate id: ${id}`);
}

const referencedIds = [...app.matchAll(/byId\("([^"]+)"\)/g)].map((match) => match[1]);
const dynamicNoteIds = [...app.matchAll(/demo-stage-\$\{stage\}-note/g)].length ? ["demo-stage-1-note", "demo-stage-2-note", "demo-stage-3-note", "demo-stage-4-note", "demo-stage-5-note", "demo-stage-6-note"] : [];
for (const id of new Set([...referencedIds, ...dynamicNoteIds])) {
  if (!idSet.has(id)) failures.push(`demo-app.js references missing id: ${id}`);
}

for (const required of [
  "demo-landing", "demo-enter-workspace", "demo-positioning", "demo-positioning-boundary", "workspace-root",
  "demo-service-pill", "demo-service-status", "demo-fact-cases", "demo-fact-reports", "demo-fact-rag", "demo-fact-model", "demo-fact-model-quality",
  "demo-featured-cases", "demo-open-all-cases", "demo-current-case-name", "demo-current-case-meta",
  "demo-start", "demo-cancel", "demo-reset", "demo-stage-rail", "demo-gate",
  "demo-result", "demo-result-state", "demo-result-summary", "demo-result-items",
  "demo-open-evidence", "demo-open-agents", "demo-rerun",
  "demo-download-json", "demo-download-csv", "demo-print-report", "demo-structured-table-body", "demo-evidence-axis-list",
  "demo-coverage-list", "demo-coverage-note", "demo-coverage-state", "demo-fitness-list", "demo-fitness-note", "demo-fitness-state",
  "demo-numeric-list", "demo-numeric-note", "demo-numeric-state", "demo-anti-list", "demo-anti-note", "demo-anti-state",
  "demo-cases-drawer", "demo-evidence-drawer", "demo-agent-drawer", "demo-tech-drawer", "demo-live-sample-drawer",
  "demo-open-live-sample", "demo-live-sample-form", "demo-live-company", "demo-live-submit", "demo-live-task", "demo-live-steps", "demo-live-result",
  "demo-live-structured-table-body", "demo-live-output-actions", "demo-live-download-json", "demo-live-download-csv", "demo-live-print-report",
  "demo-tech-llm", "demo-tech-evaluation", "demo-tech-versions", "demo-toast", "main-content",
]) {
  if (!idSet.has(required)) failures.push(`missing demo control: ${required}`);
}

// 公开演示页禁止出现团队后台控件（登录、导入、字段确认、补充资料、缓存、run_id）。
for (const forbidden of [
  "auth-dialog", "auth-login-form", "cninfo-pipeline-form", "case-import-form",
  "run-lookup", "cache-id-input", "cache-replay", "supplement-form", "review-form",
  "primary-navigation", "process-stepper", "fusion-landing", "wb-run-calculation", "wb-run-backup",
]) {
  if (idSet.has(forbidden) || html.includes(`id="${forbidden}"`)) failures.push(`public demo page must not contain: ${forbidden}`);
}
if (html.includes('type="file"')) failures.push("public demo page must not contain file upload inputs");
if (/name=["'](run_id|cache_id|reviewer|password)["']/i.test(html)) failures.push("public demo page must not request technical ids or credentials");

// 页面脚本引用：只允许 demo-app.js；旧控制台与沉浸式首屏脚本不再加载。
const scripts = [...html.matchAll(/<script[^>]+src="([^"]+)"/g)].map((match) => match[1]);
if (!scripts.some((src) => src.includes("demo-app.js"))) failures.push("page must load demo-app.js");
for (const banned of ["app.js", "fusion.js"]) {
  if (scripts.some((src) => src.replace(/\?.*$/, "").endsWith(`/${banned}`))) failures.push(`page must not load old script: ${banned}`);
}
const stylesheets = [...html.matchAll(/<link[^>]+href="([^"]+)"/g)].map((match) => match[1]);
if (stylesheets.some((src) => src.includes("fusion.css"))) failures.push("page must not load fusion.css");
if (!html.includes('/assets/official-v4/cinematic/evidence-horizon.webp')) failures.push("restored cinematic homepage image is missing");
if (!html.includes('href="#demo-positioning"') || !html.includes('href="#workspace-root"')) failures.push("homepage must flow through positioning page into the demo workspace");

// 主要按钮唯一：demo-start 是唯一主运行按钮；结果操作最多三个。
const primaryButtons = [...html.matchAll(/<button[^>]*class="[^"]*button primary[^"]*"[^>]*>/g)];
if (primaryButtons.length !== 2) failures.push(`expected exactly 2 primary buttons (start + rerun), found ${primaryButtons.length}`);
if (!/<button[^>]*class="button primary"[^>]*id="demo-start"|<button[^>]*id="demo-start"[^>]*class="button primary"/.test(html)) {
  failures.push("demo-start must be a primary button");
}

// 演示脚本不得调用移出公开版的旧高级接口；补充证据只在结果后的次级入口走
// 内置样例绑定与重新评估（register 上传端点仍由页面无 file 输入 + 后端边界保护）。
for (const bannedRoute of ["/api/auth/", "/api/cases/import", "/api/cache/", "fields/confirm", "model-consent", "/api/runs/", "/deterministic-backup", "/api/rag/", "/retry"]) {
  if (app.includes(bannedRoute)) failures.push(`demo-app.js must not call removed route family: ${bannedRoute}`);
}
for (const allowed of ["/api/demo/bootstrap", "/api/demo/runs", "/api/evaluations/current", "/api/cases/", "/api/pipelines/cninfo", "/api/pipelines/", "/api/supplement-samples", "/api/supplements/"]) {
  if (!app.includes(allowed)) failures.push(`demo-app.js missing allowed route: ${allowed}`);
}

// 首屏只做 bootstrap；评估摘要只在抽屉打开时读取。
const initMatch = app.match(/async function initialize\(\) \{([\s\S]*?)\n\}/);
const initBody = initMatch ? initMatch[1] : "";
if (!initBody.includes("loadBootstrap()")) failures.push("initialize must call loadBootstrap");
if (initBody.includes("/api/evaluations")) failures.push("initialize must not fetch evaluations at first screen");
if (!app.includes("if (demoState.techEvaluated) return;")) failures.push("evaluation summary must be lazily loaded once");

// 运行保护：主按钮同步禁用、任务创建 + 轮询、token 防串线、finally 恢复。
if (!app.includes("button.disabled = true;")) failures.push("primary button must disable synchronously");
if (!app.includes("/api/demo/runs")) failures.push("fixed-case run must create an async demo task, not wait for POST /api/runs");
if (!app.includes("function pollFixedRun(taskId, token)")) failures.push("fixed-case run must poll backend task state");
if (!app.includes("token !== demoState.fixedTask.pollToken")) failures.push("task polling must be guarded by a stale-response token");
if (!app.includes("DEMO_TASK_STORAGE_KEY")) failures.push("active task must survive page refresh via sessionStorage recovery");
if (app.includes("new Object.assign")) failures.push("HTTP error construction must not call Object.assign as a constructor");
if (!/finally \{[\s\S]*?renderControls\(\)/.test(app)) failures.push("loading state must end in finally");
if (!app.includes("renderFixedTaskProgress(task)")) failures.push("running-phase stages must render backend task progress");
if (!app.includes('"evidence_load"') || !app.includes('"rule_calculation"') || !app.includes('"knowledge_retrieval"') || !app.includes('"agent_collaboration"') || !app.includes('"evidence_validation"') || !app.includes('"structured_output"')) failures.push("frontend must map all six backend stage keys");
if (!app.includes("function formatMetricValue(key, value)")) failures.push("result metrics must use a dedicated display formatter");
if (!app.includes('class="demo-metric-grid"')) failures.push("result metrics must render as visual metric cards");
for (const status of ["searching", "downloading", "validating", "indexing", "extracting_fields", "analyzing"]) {
  if (!app.match(new RegExp(`LIVE_ACTIVE_STATUSES[^;]+[\"']${status}[\"']`))) failures.push(`live task polling must keep backend status active: ${status}`);
}
if (!app.includes('completed: "处理完成"')) failures.push("live completed status needs a Chinese terminal label");
if (!app.includes('complete_public_prescreen: "公开预筛已完成"') || !app.includes('cached_ready: "缓存资料已就绪"')) failures.push("live structured terminal enums need Chinese labels");
if (!app.includes("outputActions.hidden = !hasStructuredAnalysis")) failures.push("live exports must stay hidden before structured analysis exists");
if (!app.includes('task.status === "ready_for_analysis" && task.request?.analysis_mode === "full_analysis"')) failures.push("full-analysis live polling must bridge the ready_for_analysis handoff");

// 后端演示聚合接口与状态机闸门仍在。
if (!backend.includes('"/api/demo/bootstrap"')) failures.push("backend route missing: /api/demo/bootstrap");
if (!backend.includes("blocked_bootstrap_payload")) failures.push("backend must return blocked bootstrap payload on manifest failure");

// 触控目标：主按钮沿用 .button 44px；案例卡不小于 44px。
if (!styles.includes("min-height: 44px")) failures.push("styles must keep 44px touch targets");
const caseCardRule = html.match(/\.demo-case-card \{([\s\S]*?)\}/);
if (!caseCardRule || !caseCardRule[1].includes("min-height")) failures.push("demo case cards need an explicit min-height touch target");

if (failures.length) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`frontend demo contract ok: ${ids.length} unique ids, ${referencedIds.length} id references, ${scripts.length} script(s)`);
}
