import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// 离线回归只调用真实读取/渲染函数；不初始化网页、不产生API或模型请求。
const root = new URL("../", import.meta.url);
const html = readFileSync(new URL("index.html", root), "utf8");
const source = readFileSync(new URL("assets/official-v4/demo-app.js", root), "utf8");
class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {};
    this.attributes = {}; this._text = ""; this._html = "";
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  set textContent(value) { this._text = String(value ?? ""); this._html = ""; this.children = []; }
  get textContent() { return this._text + this._html + this.children.map(c => c.textContent ?? "").join("\n"); }
  set innerHTML(value) { this._html = String(value); this._text = ""; this.children = []; }
  get innerHTML() { return this._html; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = []; this._text = ""; this._html = ""; this.append(...nodes); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  removeAttribute(key) { delete this.attributes[key]; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
}
const elements = new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(m => [m[1], new Element()]));
const context = {
  document: { getElementById: id => elements.get(id), createElement: tag => new Element(tag), querySelectorAll: () => [] },
  window: { location: { protocol: "http:", origin: "http://127.0.0.1" }, addEventListener() {} },
  URL, console, HTMLDetailsElement: Element,
};
vm.createContext(context);
assert.equal((source.match(/^  initialize\(\);$/gm) || []).length, 1);
vm.runInContext(source.replace(/^  initialize\(\);$/m, "globalThis.readerTests = {renderInnovationControls, deriveAttentionCard, renderEvidenceChallenge, expandCollapsiblesForPrint, restoreCollapsiblesAfterPrint};"), context);
const reader = context.readerTests;
const get = id => elements.get(id).textContent;
const task = JSON.parse(readFileSync(new URL("scripts/fixtures/ui_hierarchy_run.json", root), "utf8"));
const realRun = task.result;
const frozen = JSON.stringify(realRun);
reader.renderInnovationControls(realRun);
assert.match(get("demo-coverage-note"), /1 不适用/);
assert.match(get("demo-coverage-details"), /CNINFO_000858_T0_20260430_REVENUE_2025/);
assert.match(get("demo-coverage-details"), /账龄/);
assert.match(get("demo-fitness-note"), /语义支持关系待复核/);
assert.equal(elements.get("demo-numeric-list").children.length, realRun.context.numeric_claim_trace.trace.length);
assert.match(get("demo-anti-example"), /待验证/);
assert.equal(JSON.stringify(realRun), frozen, "阅读层不得改写原始运行");

const missing = structuredClone(realRun);
delete missing.context.numeric_claim_trace.passed;
delete missing.context.numeric_claim_trace.key_unverified_count;
delete missing.context.numeric_claim_trace.unverified_count;
delete missing.context.evidence_fitness_violations;
delete missing.evidence_bundle.evidence_fitness_violations;
reader.renderInnovationControls(missing);
assert.match(get("demo-numeric-note"), /数量未提供/);
assert.equal(get("demo-numeric-state"), "本次未提供通过状态");
assert.match(get("demo-fitness-note"), /数量未提供/);
missing.context.numeric_claim_trace.passed = false;
missing.context.numeric_claim_trace.key_unverified_count = 0;
reader.renderInnovationControls(missing);
assert.equal(get("demo-numeric-state"), "数字核查未通过");

const empty = { context: {}, evidence_bundle: {}, rule_results: [], agent_steps: [] };
reader.renderInnovationControls(empty);
assert.equal(elements.get("demo-coverage-details").children.length, 0);
assert.equal(elements.get("demo-fitness-details").children.length, 0);
assert.match(get("demo-anti-example"), /未执行/);
assert.doesNotMatch(get("demo-numeric-state"), /全部可回查/);
const missingGrades = reader.deriveAttentionCard(empty, {});
assert.equal(missingGrades.badges.grade, null);
assert.equal(missingGrades.badges.evidenceState, null);

const noPage = structuredClone(realRun);
for (const group of ["field_evidence", "rag_evidence"]) {
  for (const row of noPage.evidence_bundle[group] || []) delete row.pdf_page;
}
reader.renderEvidenceChallenge(noPage, "success");
assert.equal(elements.get("demo-challenge-open-source").attributes["aria-disabled"], "true");
assert.equal(elements.get("demo-challenge-open-source").attributes.href, undefined);
assert.equal(elements.get("demo-evidence-challenge").dataset.state, "unlocated");

assert(html.indexOf('id="demo-attention-badges"') < html.indexOf('id="demo-primary-reading"'), "三个等级必须位于主结果前部");
assert(!/<details[^>]*>\s*<summary>查看各项完整待核查草稿/.test(html), "事项不得整块折叠");
assert.match(html, /查看完整指标与计算口径<\/summary><div class="demo-table-wrap"/);
const printDetails = [new Element("details"), new Element("details")];
printDetails[0].open = false;
printDetails[1].open = true;
context.document.querySelectorAll = () => printDetails;
reader.expandCollapsiblesForPrint();
assert(printDetails.every(item => item.open));
reader.expandCollapsiblesForPrint();
reader.restoreCollapsiblesAfterPrint();
assert.deepEqual(printDetails.map(item => item.open), [false, true]);
console.log("UI hierarchy regression ok: preserved run, coverage evidence, unknown counts, fresh summaries, missing grades and page-gated source links");
