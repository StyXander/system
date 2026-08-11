import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const app = readFileSync(new URL("../assets/official-v4/app.js", import.meta.url), "utf8");
const styles = readFileSync(new URL("../assets/official-v4/styles.css", import.meta.url), "utf8");
const fusion = readFileSync(new URL("../assets/official-v4/fusion.css", import.meta.url), "utf8");
const backend = readFileSync(new URL("../backend/app/main.py", import.meta.url), "utf8");
const failures = [];

const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const idSet = new Set(ids);
for (const id of ids) {
  if (ids.indexOf(id) !== ids.lastIndexOf(id)) failures.push(`duplicate id: ${id}`);
}

const referencedIds = [...app.matchAll(/byId\("([^"]+)"\)/g)].map((match) => match[1]);
for (const id of new Set(referencedIds)) {
  if (!idSet.has(id)) failures.push(`app.js references missing id: ${id}`);
}

const viewMatch = app.match(/const VIEW_IDS = \[([^\]]+)\]/);
const views = viewMatch ? [...viewMatch[1].matchAll(/"([^"]+)"/g)].map((match) => match[1]) : [];
for (const view of views) {
  if (!html.includes(`data-view-panel="${view}"`)) failures.push(`missing view panel: ${view}`);
  if (!html.includes(`data-view="${view}"`)) failures.push(`missing navigation target: ${view}`);
}

for (const required of ["auth-dialog", "auth-login-form", "auth-action", "sidebar-auth-action", "cninfo-pipeline-form", "review-form"]) {
  if (!idSet.has(required)) failures.push(`missing critical control: ${required}`);
}

for (const route of [
  "/api/auth/me",
  "/api/auth/login",
  "/api/auth/refresh",
  "/api/auth/logout",
  "/api/cases/{case_id}/model-consent",
  "/api/industry-gates/{case_id}",
  "/api/pipelines/{task_id}",
  "/api/runs/{run_id}",
]) {
  if (!backend.includes(`"${route}"`)) failures.push(`backend route missing: ${route}`);
}

// 冷启动恢复不能依赖尚未读取的 state.auth；演示模式并行读取摘要目录，
// 非演示模式在认证后对失败的目录请求再按当前身份重试。
if (!app.includes("if (authRefreshPromise) return authRefreshPromise;")) failures.push("missing refresh single-flight guard");
if (!app.includes("async function api(path, options = {}, authRecovery = { attempted: false })")) failures.push("api missing per-chain auth recovery budget");
if (/response\.status === 401[^\n]+state\.auth/.test(app)) failures.push("401 refresh still depends on preloaded auth state");
const loadStart = app.indexOf("async function loadSystemAndCases(options = {})");
const loadEnd = app.indexOf("function cninfoTaskStatusLabel", loadStart);
const loadBody = loadStart >= 0 && loadEnd > loadStart ? app.slice(loadStart, loadEnd) : "";
const statusIndex = loadBody.indexOf('api("/api/status"');
const meIndex = loadBody.indexOf('api("/api/auth/me", {}, authRecovery)');
const summaryCasesIndex = loadBody.indexOf('api("/api/cases?summary=true"');
if (!(statusIndex >= 0 && summaryCasesIndex > statusIndex)) failures.push("fresh load must request the compact case summary");
if (!loadBody.includes("if (!listingResult.ok && !demoMode)")) failures.push("non-demo listing must retry after auth recovery");
if (!(meIndex > statusIndex)) failures.push("non-demo auth recovery must follow status discovery");
if (!loadBody.includes("refreshCookieSession({ silent: true })")) failures.push("refresh-cookie-only cold start recovery missing");
const oneShotBranch = app.match(/if \(isOneShotRequestBody\(options\.body\)\) \{([\s\S]*?)\n\s{6}\}/)?.[1] || "";
if (!oneShotBranch || !oneShotBranch.includes("throw error") || oneShotBranch.includes("response = await fetch")) {
  failures.push("FormData/Blob/stream branch must refresh at most once and never replay the request");
}
if (!backend.includes('"case_list_summary_v1"')) failures.push("backend compact case-list schema missing");
if (!backend.includes("GZipMiddleware")) failures.push("backend response compression middleware missing");
if (!styles.includes(".run-controls > .button") || !styles.includes("min-width: 140px") || !styles.includes("grid-template-columns: minmax(0, 1fr)")) {
  failures.push("analysis run controls lack a non-shrinking responsive layout");
}

function hasSizedRule(source, selector, minimumHeight = "40px") {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return [...source.matchAll(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`, "g"))]
    .some((match) => match[1].includes("min-width: 40px") && match[1].includes(`min-height: ${minimumHeight}`));
}

for (const [label, source, selector, height] of [
  ["fusion brand", fusion, ".fusion-brand", "40px"],
  ["visible fusion boundary link", fusion, ".fusion-nav-links a", "44px"],
  ["fusion explore link", fusion, ".fusion-scroll-cue", "40px"],
  ["workspace brand", styles, ".brand", "40px"],
]) {
  if (!hasSizedRule(source, selector, height)) failures.push(`${label} lacks a 390px-safe touch target`);
}

if (failures.length) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`frontend contract ok: ${ids.length} unique ids, ${referencedIds.length} id references, ${views.length} views`);
}
