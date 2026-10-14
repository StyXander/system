(function () {
  "use strict";
  const notice = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。";
  const labels = { missing: "缺少对应资料", partial: "部分条件具备", conflicting: "登记字段冲突", rule_supported: "登记条件通过", not_applicable: "本底稿不适用" };
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const csv = value => `"${String(value ?? "").replaceAll('"', '""')}"`;
  let scenarios = [];
  const states = new Map();

  function download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = document.createElement("a");
    link.href = url; link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function rows(investigation) {
    return [
      ["类型", "编号", "认定/种类", "状态/排序", "目的/限制", "依据"],
      ...investigation.questions.map(q => ["核查事项", q.question_id, q.assertion, labels[q.state], [...q.missing_conditions, ...q.conflicts].join("；") || q.boundary, q.supporting_evidence_ids.join("；")]),
      ...investigation.material_requests.map(t => ["取证任务", t.request_id, t.assertion, t.rank, t.purpose, t.priority_reason]),
      ...investigation.evidence_decisions.map(e => ["资料用途", e.evidence_id, e.kind, e.selected ? "参与检验" : "未选择", e.uses.map(u => `${u.question_id}：${u.reason}`).join("；"), e.supports_assertions.join("；")]),
      ["来源哈希", investigation.source_snapshot_sha256, "规则哈希", investigation.rulebook_sha256, investigation.rulebook_version, notice]
    ];
  }

  function render(id) {
    const state = states.get(id), root = document.getElementById(id);
    if (!state || !root) return;
    const inv = state.checked?.investigation || state.original;
    const checkedIds = new Set(state.pendingSelectedIds || inv.evidence_decisions.filter(e => e.selected).map(e => e.evidence_id));
    root.hidden = false;
    root.innerHTML = `<div class="demo-section-heading"><div><span class="folio">ASSERTION / PURPOSE / EVIDENCE CHANGE</span><h3>${state.kind === "run" ? "本次年报对应的取证任务" : "认定级证据检验"}</h3></div><span class="state pending">独立程序检验 · 0 次模型调用</span></div>
      <p>${escape(inv.company_name)} · ${inv.source_mode === "anonymous_synthetic" ? "匿名合成验收资料，与真实企业隔离" : inv.source_mode === "registered_supplement" ? "本次授权登记的补充资料；字段与原件仍须核查" : "本次登记年报；交易与客户明细未提供"}</p>
      <p class="evidence-boundary">${escape(inv.boundary)} 专业复核未执行，语义支持未验证。</p>
      ${state.kind === "validation_scenario" ? `<label class="evidence-select">选择匿名底稿<select data-action="scenario" aria-label="选择匿名验收底稿">${scenarios.map(s => `<option value="${escape(s.base_id)}" ${s.base_id === state.baseId ? "selected" : ""}>${escape(s.title)}</option>`).join("")}</select></label>` : ""}
      ${state.kind === "validation_scenario" && state.steps?.length ? `<section class="evidence-guided" aria-label="逐步检验资料用途"><h4>用真实检验结果检查资料用途</h4><p>可按下面的操作设置资料，也可以自行勾选。每次都由后端计算条件与缺口，保留原始底稿。</p><div class="action-row">${state.steps.map((step, index) => `<button class="button quiet" type="button" data-evidence-step="${index}">${escape(step.title)}<small>${escape(step.description)}</small></button>`).join("")}</div></section>` : ""}
      <div class="evidence-decision-grid"><div><h4>最多五项核查问题</h4><ol class="evidence-questions">${inv.questions.filter(q => q.state !== "not_applicable").map(q => `<li class="evidence-question" data-question="${q.question_id}" data-state="${q.state}"><div><strong>${escape(q.assertion)} · ${escape(q.title)}</strong><span class="evidence-state">${labels[q.state]}</span></div><p>${escape([...q.conflicts, ...q.missing_conditions].join("；") || (q.state === "not_applicable" ? "该账户不在底稿范围" : "登记条件满足，仍需原件核对与专业判断"))}</p><small>依据：${escape(q.supporting_evidence_ids.join("、") || "未取得对应明细")}</small><details><summary>查看替代解释及检验字段</summary><p>待验证假设：${escape(q.alternative_explanation)}</p>${q.computed_facts.map(f => `<p>${escape(f.condition)}：${escape(JSON.stringify(f))}</p>`).join("")}</details></li>`).join("")}</ol>${inv.questions.some(q => q.state === "not_applicable") ? `<details><summary>查看本底稿不适用的认定（${inv.questions.filter(q => q.state === "not_applicable").length}项）</summary>${inv.questions.filter(q => q.state === "not_applicable").map(q => `<p>${escape(q.question_id)} · ${escape(q.assertion)} · ${escape(q.title)}：本底稿不适用。</p>`).join("")}</details>` : ""}
      <h4>优先取得的资料</h4><ol class="evidence-task-list">${inv.material_requests.slice(0, 5).map(t => `<li><strong>${escape(t.assertion)} · ${escape(t.purpose)}</strong><small>${escape(t.priority_reason)} · ${escape(t.granularity === "customer" ? "客户级" : "交易级")} · ${escape(t.request_id)}</small></li>`).join("") || "<li>本规则无新增资料任务；条件通过仍不代表审计程序完成。</li>"}</ol><details><summary>查看全部取证任务（${inv.material_requests.length}项）</summary>${inv.material_requests.map(t => `<p>${t.rank}. ${escape(t.request_id)} · ${escape(t.purpose)} · ${escape(t.boundary)}</p>`).join("")}</details></div>
      <div><h4>加入或暂时排除资料</h4><p>排除只影响这次检验，不删除原件。回款不能替代截止证据；汇总账龄不能替代客户明细。</p><div class="evidence-options">${inv.evidence_catalog.map(e => `<label><input type="checkbox" value="${escape(e.evidence_id)}" ${checkedIds.has(e.evidence_id) ? "checked" : ""}><span><strong>${escape(e.title)}</strong><small>${escape(e.evidence_id)} · ${escape(({summary:"汇总",transaction:"交易级",customer:"客户级"})[e.granularity] || e.granularity)} · 可得 ${escape(e.available_at || "未登记")}</small></span></label>`).join("") || "<p>该历史运行没有可选资料，原记录保持原样。</p>"}</div><div class="action-row"><button class="button primary" data-action="check" type="button">检验所选资料</button><button class="button quiet" data-action="restore" type="button">恢复原始选择</button></div><p role="status" aria-live="polite" class="evidence-check-status">${escape(state.message || "按底稿默认资料展示，尚未追加独立检验。")}</p>
      ${state.checked ? `<div class="evidence-change"><h4>与原始底稿相比</h4>${state.checked.changes.map(c => `<p>${escape(c.question_id)}：${labels[c.before]} → ${labels[c.after]}<br>${escape([...c.conflicts_after, ...c.missing_after].join("；") || "登记条件通过，专业判断未验证")}</p>`).join("") || "<p>事项条件没有变化；选择变化不能强行改写结论。</p>"}<small>${escape(state.checked.check_id)} · 来源及原运行保持不变</small></div>` : ""}
      <details><summary>逐份查看资料能支持什么、不能关闭什么</summary>${inv.evidence_decisions.map(e => `<article><h5>${escape(e.evidence_id)} · ${escape(e.title)}</h5><p>${e.duplicate ? "重复原件，未重复计入" : e.selected ? "参与本次检验" : "未选择"}；用途认定：${escape(e.supports_assertions.join("、") || "汇总背景，不能关闭交易明细条件")}</p>${e.uses.map(u => `<p>${escape(u.question_id)} · ${escape(u.purpose)}：${escape(u.reason)}</p>`).join("")}</article>`).join("")}</details>
      <details><summary>角色交接与版本来源</summary><p>以下角色信息来自原分析，独立检验不会新增模型角色。</p>${(state.original.counter_contribution.roles || []).map(r => `<p>${escape(r.role)}：交接${r.handoff_count}项，新增引用${r.new_reference_count}项；${escape(r.boundary)}</p>`).join("") || "<p>此底稿未记录模型交接，不补造角色贡献。</p>"}<p>规则：${escape(inv.rulebook_version)}<br>规则哈希：${escape(inv.rulebook_sha256)}<br>底稿哈希：${escape(inv.source_snapshot_sha256)}</p></details></div></div>
      <div class="action-row"><button class="button quiet" data-action="json" type="button">下载检验 JSON</button><button class="button quiet" data-action="csv" type="button">下载取证 CSV</button><button class="button quiet" data-action="word" type="button">下载检验 Word</button><button class="button quiet" data-action="print" type="button">打印此检验 / PDF</button></div><p class="evidence-boundary">${notice}</p>`;
    root.querySelector('[data-action="scenario"]')?.addEventListener("change", event => selectScenario(event.target.value, true));
    root.querySelectorAll('[data-evidence-step]').forEach(button => button.addEventListener("click", () => {
      const step = state.steps[Number(button.dataset.evidenceStep)];
      if (!step || state.busy) return;
      const selected = new Set([...state.original.default_evidence_ids, ...step.include_evidence_ids]);
      step.exclude_evidence_ids.forEach(e => selected.delete(e));
      root.querySelectorAll('input[type="checkbox"]').forEach(input => { input.checked = selected.has(input.value); });
      check(id, false, `[data-evidence-step="${button.dataset.evidenceStep}"]`);
    }));
    root.querySelectorAll('input[type="checkbox"]').forEach(input => input.addEventListener("change", () => {
      state.pendingSelectedIds = [...root.querySelectorAll('input[type="checkbox"]:checked')].map(e => e.value);
      root.querySelector(".evidence-check-status").textContent = "资料选择已改变，点击检验后更新事项与导出结果。";
      root.querySelectorAll('[data-action="json"],[data-action="csv"],[data-action="print"]').forEach(button => { button.disabled = true; });
    }));
    if (state.pendingSelectedIds) root.querySelectorAll('[data-action="json"],[data-action="csv"],[data-action="print"]').forEach(button => { button.disabled = true; });
    root.querySelector('[data-action="check"]').addEventListener("click", () => check(id));
    root.querySelector('[data-action="restore"]').addEventListener("click", () => { state.checked = null; state.pendingSelectedIds = null; state.message = "已恢复原底稿选择；未改原件，也未调用模型。"; render(id); root.querySelector('[data-action="restore"]').focus({ preventScroll: true }); });
    root.querySelector('[data-action="json"]').addEventListener("click", () => download(`${state.baseId}-evidence.json`, JSON.stringify(state.checked || { evaluation_mode: "registered_baseline", provider_call_count: 0, investigation: inv, ai_generated_content_notice: notice }, null, 2), "application/json"));
    root.querySelector('[data-action="csv"]').addEventListener("click", () => download(`${state.baseId}-evidence.csv`, `\uFEFF${rows(inv).map(r => r.map(csv).join(",")).join("\r\n")}`, "text/csv;charset=utf-8"));
    root.querySelector('[data-action="word"]').addEventListener("click", () => check(id, true));
    root.querySelector('[data-action="print"]').addEventListener("click", () => {
      const copy = root.cloneNode(true);
      copy.id = "evidence-print-copy";
      copy.querySelectorAll("details").forEach(d => { d.open = true; });
      document.getElementById(copy.id)?.remove();
      document.body.appendChild(copy);
      document.body.dataset.evidencePrint = copy.id;
      window.print();
    });
  }

  async function check(id, report = false, focusSelector = null) {
    const state = states.get(id), root = document.getElementById(id);
    if (state.busy) return;
    const selected = new Set([...root.querySelectorAll('input[type="checkbox"]:checked')].map(e => e.value));
    const defaults = new Set(state.original.default_evidence_ids);
    const body = { base_kind: state.kind, base_id: state.baseId, include_evidence_ids: [...selected].filter(e => !defaults.has(e)), exclude_evidence_ids: [...defaults].filter(e => !selected.has(e)) };
    state.pendingSelectedIds = [...selected];
    state.busy = true;
    let calculationDone = false;
    root.querySelectorAll("button,input,select").forEach(e => { e.disabled = true; });
    try {
      const options = { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify(body) };
      const response = await fetch("/api/evidence-checks", options);
      if (!response.ok) { const error = await response.json(); throw new Error(error.detail || `请求失败 ${response.status}`); }
      state.checked = await response.json();
      state.pendingSelectedIds = null;
      calculationDone = true;
      state.message = `已完成独立条件检验，${state.checked.changes.length}项发生变化；新增0次模型调用。`;
      if (report) {
        const documentResponse = await fetch("/api/evidence-checks/report", options);
        if (!documentResponse.ok) throw new Error(`Word导出失败 ${documentResponse.status}`);
        const blob = await documentResponse.blob();
        download(`${state.baseId}-evidence.docx`, blob, blob.type);
        state.message = "检验草稿已导出，专业复核未执行；本次新增0次模型调用。";
      }
    } catch (error) { state.message = `${calculationDone ? "检验完成，导出未完成" : "检验未完成"}：${error.message}。原底稿保持不变，所选资料已保留，可重试。`; }
    finally { state.busy = false; render(id); root.querySelector(focusSelector || (report ? '[data-action="word"]' : '[data-action="check"]'))?.focus({ preventScroll: true }); }
  }

  function selectScenario(baseId, focus = false) {
    const selected = scenarios.find(s => s.base_id === baseId);
    if (!selected) return;
    states.set("evidence-scenario-workbench", { kind: "validation_scenario", baseId, original: selected.investigation, steps: selected.demonstration_steps });
    render("evidence-scenario-workbench");
    if (focus) document.querySelector('#evidence-scenario-workbench [data-action="scenario"]').focus({ preventScroll: true });
  }

  async function load() {
    const root = document.getElementById("evidence-scenario-workbench");
    if (!root) return;
    try {
      const response = await fetch("/api/evidence-scenarios", { credentials: "include" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      scenarios = (await response.json()).scenarios;
      if (!scenarios.length) throw new Error("未登记匿名底稿");
      selectScenario(scenarios[0].base_id);
    } catch (error) {
      root.innerHTML = `<h3>匿名证据检验尚未加载</h3><p role="status">${escape(error.message)}；未显示模拟成功结果。</p><button class="button quiet" type="button">重新读取底稿</button>`;
      root.querySelector("button").addEventListener("click", load);
    }
  }

  window.AuditEvidenceDecisions = { mountRun(run) {
    const root = document.getElementById("evidence-run-workbench");
    if (!run.audit_investigation) { root.hidden = true; states.delete(root.id); return; }
    states.set(root.id, { kind: "run", baseId: run.run_id, original: run.audit_investigation }); render(root.id);
  }, csvRows: rows };
  window.addEventListener("afterprint", () => { document.getElementById("evidence-print-copy")?.remove(); delete document.body.dataset.evidencePrint; });
  document.querySelectorAll('[data-open-evidence]').forEach(link => link.addEventListener("click", () => {
    const section = document.getElementById("evidence-demo-section");
    section.open = true;
    section.querySelector("summary").focus({ preventScroll: true });
  }));
  if (location.hash === "#evidence-demo-section") document.getElementById("evidence-demo-section").open = true;
  load();
})();
