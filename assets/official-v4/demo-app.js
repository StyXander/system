(function () {
  "use strict";

  /* 审迹智链竞赛演示版前端：单一状态机驱动的评委演示工作台。
     设计约束来自《竞赛演示版功能精简与高稳定性改造计划》§18.3 与 §19：
     - 唯一状态 demoState，按钮/阶段/结果/提示全部由它派生；
     - 主按钮在请求开始的同一同步事件内禁用，finally 中恢复；
     - 同一时刻只允许一个活动运行，双击不会产生第二次模型调用；
     - 切换案例清空旧结果，URL 只写入白名单 case_id，未知值回退默认；
     - success / degraded / failed 渲染条件互斥，确定性备用不冒充真实模型成功；
     - 不把错误对象直接插入 innerHTML，一律 escapeHtml；
     - 本机存储只保存白名单 case_id，不保存任何敏感信息；
     - 页面刷新后恢复案例选择；running 任务只轮询，尚未被领取的 queued
       任务可用同一任务编号恢复执行，不重复创建或重放模型调用。 */

  const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
  const AI_GENERATED_CONTENT_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。";
  const CASE_STORAGE_KEY = "audittrace_demo_case_v1";
  const DEMO_TASK_STORAGE_KEY = "audittrace_demo_task_v1";
  const RUN_TIMEOUT_MS = 300000;
  const LIVE_POLL_INTERVAL_MS = 1400;
  const DEMO_POLL_INTERVAL_MS = 1500;
  const LIVE_ACTIVE_STATUSES = new Set(["queued", "running", "resolving_company", "searching", "downloading", "validating", "registering", "rag_building", "indexing", "extracting_fields", "analyzing"]);
  /* 后端任务阶段与页面六阶段一一对应；进度只来自后端，前端不模拟。 */
  const FIXED_STAGE_KEYS = ["evidence_load", "rule_calculation", "knowledge_retrieval", "agent_collaboration", "evidence_validation", "structured_output"];
  const ROLE_SHORT_LABELS = { challenge: "质疑", counter: "反证", review: "复核" };
  const TASK_ACTIVE_STATUSES = new Set(["queued", "running"]);

  const STATUS_LABELS = {
    candidate: "程序候选",
    DATA_NOT_COMPARABLE: "数据跨期不可比",
    RULE_NOT_TRIGGERED: "程序未触发",
    DATA_GAP: "资料缺口",
    retain: "建议保留",
    downgrade: "建议降级",
    defer: "建议暂缓",
    not_generated: "未形成AI建议",
    complete_full_analysis: "完整分析已完成",
    complete_full_analysis_with_gaps: "完整分析已完成（有资料缺口）",
    complete_full_analysis_no_candidate: "完整分析完成，无程序候选",
    complete_public_prescreen: "公开预筛已完成",
    complete_public_prescreen_no_candidate: "公开预筛完成，无程序候选",
    complete_demo_fallback: "演示降级结果已完成",
    incomplete_calculation_only: "不完整：仅计算预检",
    incomplete_model_chain_failed: "不完整：模型链未完成",
    incomplete_model_quota: "不完整：模型额度不足",
    incomplete_rag_failure: "不完整：RAG失败",
    incomplete_model_transfer_not_allowed: "不完整：禁止模型传输",
    incomplete_sensitive_data_blocked: "不完整：敏感信息已阻断模型调用",
    model_success: "三Agent已通过硬校验",
    demo_fallback: "演示确定性草稿已生成",
    not_requested: "未请求模型",
    skipped: "跳过：前置角色未完成",
    not_applicable_no_call: "未调用模型",
    not_attempted_rag_failure: "RAG失败，完整分析未完成",
    sensitive_data_blocked: "敏感信息已阻断模型调用",
    model_transfer_not_allowed: "模型传输未获许可",
    external_live: "真实模型现场执行",
    external_cached: "真实模型缓存命中",
    cache_replay: "批准缓存回放",
    deterministic_backup: "确定性备用分析",
    unavailable: "模型不可用",
    provider_quota_exhausted: "模型供应商余额不足",
    provider_unavailable: "模型供应商暂时不可用",
    provider_unreachable: "模型调用失败",
    MODEL_PROVIDER_TIMEOUT: "模型响应超时",
    config_missing: "模型配置缺失",
    MODEL_OUTPUT_INVALID: "模型输出校验失败",
    risk_candidate: "风险候选复核",
    no_trigger_confirmed: "未触发结果已复核",
    data_gap: "数据缺口待补充",
    industry_boundary: "行业边界已复核",
    frozen: "评估版本已冻结",
    not_started: "评估尚未开始",
    queued: "等待执行",
    running: "正在执行",
    resolving_company: "确认企业",
    searching: "检索公告",
    downloading: "下载年报",
    validating: "校验资料",
    registering: "登记案例",
    rag_building: "建立 RAG",
    indexing: "建立 RAG",
    extracting_fields: "提取字段",
    analyzing: "执行分析",
    completed: "处理完成",
    failed: "处理失败",
    cancelled: "已取消",
    expired: "任务结果已过期",
    TASK_RESULT_EXPIRED: "任务结果已过期",
    TASK_INTERRUPTED_BY_INSTANCE_RESTART: "实例重启导致任务中断",
    TASK_INTERRUPTED_BY_RESTART: "服务重启导致任务中断",
    cached_ready: "缓存资料已就绪",
    passed_technical_pending_human: "技术校验通过，建议人工复核",
    needs_human: "需要人工确认",
    ready_for_analysis: "资料与分析已就绪",
    rag_ready: "RAG 已就绪",
  };

  const ROUTE_LABELS = {
    risk_candidate: "候选风险核查",
    negative_confirmation: "未触发结果复核",
    industry_review: "行业口径复核",
    evidence_gap_review: "数据缺口复核",
  };

  const METRIC_LABELS = {
    revenue_growth: "营业收入增速",
    ar_growth: "应收账款增速",
    growth_gap: "增速差",
    absolute_ar_change: "应收账款绝对变动",
    ar_to_revenue_current: "本年应收 / 收入",
    ar_to_revenue_previous: "上年应收 / 收入",
    turnover_days_current: "本年应收周转天数",
    turnover_days_previous: "上年应收周转天数",
    turnover_trend_days: "周转天数变化",
    sustained_periods: "持续期间",
    materiality_assessment: "金额重要性评价",
    materiality_multiple: "重要性倍数",
    three_year_trend_available: "三年趋势可评价",
    operating_cash_flow_growth: "经营活动现金流增速",
    cashflow_to_revenue_current: "本年经营现金流 / 收入",
    cashflow_to_revenue_previous: "上年经营现金流 / 收入",
  };

  const PERCENT_METRICS = new Set([
    "revenue_growth",
    "ar_growth",
    "ar_to_revenue_current",
    "ar_to_revenue_previous",
    "operating_cash_flow_growth",
    "cashflow_to_revenue_current",
    "cashflow_to_revenue_previous",
  ]);

  function formatMetricValue(key, value) {
    if (typeof value === "boolean") return value ? "可评价" : "暂不可评价";
    if (typeof value !== "number" || !Number.isFinite(value)) return String(value ?? "—");
    const signed = (number, digits = 2) => {
      const normalized = Math.abs(number) < 10 ** -(digits + 1) ? 0 : number;
      const formatted = Math.abs(normalized).toLocaleString("zh-CN", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
      return `${normalized < 0 ? "−" : ""}${formatted}`;
    };
    if (PERCENT_METRICS.has(key)) return `${signed(value * 100)}%`;
    if (key === "growth_gap") return `${signed(value * 100)} 个百分点`;
    if (key === "absolute_ar_change") {
      if (Math.abs(value) >= 100000000) return `${signed(value / 100000000)} 亿元`;
      if (Math.abs(value) >= 10000) return `${signed(value / 10000)} 万元`;
      return `${signed(value)} 元`;
    }
    if (key === "turnover_days_current" || key === "turnover_trend_days") return `${signed(value, 1)} 天`;
    if (key === "sustained_periods") return `${Math.round(value)} 期`;
    return signed(value);
  }

  /* 单一演示状态机：booting → ready ⇄ running → success/degraded/failed_run；
     resetting 只在重置动作内部短暂存在。 */
  const demoState = {
    phase: "booting",
    bootstrap: null,
    cases: [],
    caseIndex: new Map(),
    caseId: null,
    run: null,
    outcome: null,
    taskCreationBlocked: false,
    runAbort: null,
    techEvaluated: false,
    fixedTask: {
      taskId: null,
      task: null,
      retryOfTaskId: null,
      pollTimer: null,
      pollToken: 0,
      renderSignature: null,
    },
    liveSample: {
      taskId: null,
      task: null,
      pollTimer: null,
      pollToken: 0,
      submitting: false,
    },
  };

  /* 全局错误收集：验收时可通过 window.__audittraceDemoErrors 复核未捕获异常，
     页面自身不弹窗、不上报，只保留在本机会话内供排查。 */
  window.__audittraceDemoErrors = [];
  window.addEventListener("error", (event) => {
    window.__audittraceDemoErrors.push(`error: ${event.message}`);
  });
  window.addEventListener("unhandledrejection", (event) => {
    window.__audittraceDemoErrors.push(`rejection: ${event.reason}`);
  });

  function byId(id) {
    const node = document.getElementById(id);
    if (!node) throw new Error(`页面结构缺失：#${id}`);
    return node;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function safeHttpsUrl(value) {
    try {
      const parsed = new URL(String(value || ""), window.location.origin);
      return parsed.protocol === "https:" ? parsed.href : "";
    } catch (_error) {
      return "";
    }
  }

  function statusLabel(value) {
    return STATUS_LABELS[value] || value || "—";
  }

  function statusKind(value) {
    const text = String(value || "");
    if (/complete|passed|success|ready|retain/.test(text)) return "success";
    if (/failed|danger|quota|unreachable|invalid|blocked|not_allowed/.test(text)) return "danger";
    if (/incomplete|fallback|skipped|gap|defer|downgrade|not_requested|replay|cached/.test(text)) return "waiting";
    return "pending";
  }

  function setServiceStatus(text, kind) {
    const pill = byId("demo-service-pill");
    pill.className = `service-pill ${kind || "pending"}`;
    pill.dataset.shortStatus = kind === "success" ? "模型可用" : kind === "danger" ? "后端异常" : "模型降级";
    pill.title = text;
    byId("demo-service-status").textContent = text;
  }

  function setStageNote(stage, text) {
    const note = document.getElementById(`demo-stage-${stage}-note`);
    if (note) note.textContent = text;
  }

  function setStageState(stage, stateName) {
    const item = document.querySelector(`.demo-stage[data-stage="${stage}"]`);
    if (item) {
      item.classList.remove("current", "completed", "failed", "degraded", "skipped");
      if (stateName) item.classList.add(stateName);
    }
  }

  function resetStageRail() {
    [1, 2, 3, 4, 5, 6].forEach((stage) => {
      setStageState(stage, null);
      setStageNote(stage, "等待开始");
    });
  }

  function setGate(kind, title, detail) {
    const gate = byId("demo-gate");
    gate.className = `status-banner ${kind || "neutral"}`;
    gate.innerHTML = `<strong>${escapeHtml(title)}</strong><div class="demo-gate-detail">${escapeHtml(detail)}</div>`;
  }

  function showToast(text, kind) {
    const toast = byId("demo-toast");
    toast.className = `global-toast ${kind || ""}`.trim();
    toast.textContent = text;
    toast.hidden = false;
    window.clearTimeout(showToast._timer);
    showToast._timer = window.setTimeout(() => { toast.hidden = true; }, 6000);
  }

  function safeStorageGet(key) {
    try { return window.localStorage.getItem(key); } catch (_error) { return null; }
  }

  function safeStorageSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch (_error) { /* 本会话仍可运行 */ }
  }

  function safeSessionGet(key) {
    try { return window.sessionStorage.getItem(key); } catch (_error) { return null; }
  }

  function safeSessionSet(key, value) {
    try { window.sessionStorage.setItem(key, value); } catch (_error) { /* 本会话仍可运行 */ }
  }

  function safeSessionRemove(key) {
    try { window.sessionStorage.removeItem(key); } catch (_error) { /* 忽略 */ }
  }

  function stopFixedTaskPolling() {
    demoState.fixedTask.pollToken += 1;
    if (demoState.fixedTask.pollTimer) {
      window.clearTimeout(demoState.fixedTask.pollTimer);
      demoState.fixedTask.pollTimer = null;
    }
    demoState.fixedTask.renderSignature = null;
  }

  function renderFixedTaskProgress(task) {
    const steps = task?.steps || {};
    const agentSteps = task?.agent_steps || {};
    const signature = JSON.stringify({
      stages: FIXED_STAGE_KEYS.map((key) => [steps[key]?.status || "pending", steps[key]?.detail || "等待开始"]),
      agents: Object.entries(agentSteps).map(([role, step]) => [role, step?.status || "pending", step?.failure_code || ""]),
    });
    // Agent 阶段可能持续一两分钟；轮询结果未变化时不重复改写 DOM，
    // 避免滚动中的样式计算与布局抖动。
    if (signature === demoState.fixedTask.renderSignature) return;
    demoState.fixedTask.renderSignature = signature;
    FIXED_STAGE_KEYS.forEach((stageKey, index) => {
      const stage = steps[stageKey] || { status: "pending", detail: "等待开始" };
      const stateName = stage.status === "running" ? "current"
        : stage.status === "completed" ? "completed"
          : stage.status === "degraded" ? "degraded"
            : stage.status === "failed" ? "failed"
              : stage.status === "skipped" ? "skipped" : null;
      setStageState(index + 1, stateName);
      setStageNote(index + 1, stage.detail || "等待开始");
    });
    const finished = Object.values(agentSteps).filter((step) => step && step.status !== "pending").length;
    if (finished) {
      const summary = Object.entries(agentSteps)
        .filter(([, step]) => step && step.status !== "pending")
        .map(([role, step]) => `${ROLE_SHORT_LABELS[role] || role}${statusLabel(step.status)}`)
        .join(" · ");
      const base = steps.agent_collaboration?.detail || "三角色协作链执行中";
      setStageNote(4, `${base}（${summary}）`);
    }
  }

  function updateUrl({ replace = true } = {}) {
    const url = new URL(window.location.href);
    url.search = "";
    if (demoState.caseId) url.searchParams.set("case", demoState.caseId);
    if (replace) window.history.replaceState(null, "", url);
    else window.history.pushState(null, "", url);
  }

  function currentCase() {
    return demoState.caseIndex.get(demoState.caseId) || null;
  }

  function setPhase(phase) {
    demoState.phase = phase;
    renderControls();
  }

  function renderControls() {
    const start = byId("demo-start");
    const backup = byId("demo-backup");
    const recheck = byId("demo-recheck");
    const cancel = byId("demo-cancel");
    const reset = byId("demo-reset");
    const phase = demoState.phase;
    const continuity = demoState.bootstrap?.task_continuity || {};
    // Older local snapshots have no availability field; retain their historical
    // behavior while making a current explicit "unavailable" state fail closed.
    const taskStoreReady = continuity.availability ? continuity.availability === "ready" : true;
    const deterministicAvailable = Boolean(demoState.bootstrap?.model_readiness?.deterministic_backup_available);
    const canStartBackup = deterministicAvailable
      && (phase === "ready" || phase === "failed_run")
      && (!taskStoreReady || demoState.taskCreationBlocked)
      && Boolean(demoState.caseId);
    start.disabled = !(phase === "ready") || !demoState.caseId || !taskStoreReady || demoState.taskCreationBlocked;
    start.title = !taskStoreReady
      ? "正式演示任务台账不可用；请重新检测，或选择确定性备用演示。"
      : demoState.taskCreationBlocked
        ? "上次任务尚未创建成功；请重新检测台账或选择确定性备用演示。"
        : "创建一份正式演示任务并读取后端真实进度。";
    start.textContent = phase === "running" ? "正在分析…" : "开始审计预筛";
    backup.hidden = !canStartBackup;
    backup.disabled = !canStartBackup;
    backup.title = "确定性备用不调用外部模型，结果只保留在当前 Web 实例。";
    recheck.hidden = !(phase === "ready" || phase === "failed_run") || taskStoreReady;
    recheck.disabled = phase === "running";
    recheck.title = "重新读取 Supabase 演示任务台账可用性。";
    cancel.hidden = phase !== "running" || !demoState.fixedTask.taskId;
    cancel.disabled = Boolean(cancel.dataset.busy === "true");
    reset.hidden = !(phase === "success" || phase === "degraded" || phase === "failed_run" || phase === "failed" || phase === "interrupted" || phase === "cancelled" || phase === "expired");
    const locked = phase === "running";
    document.querySelectorAll("#demo-featured-cases .demo-case-card").forEach((card) => {
      card.disabled = locked;
    });
    byId("demo-open-all-cases").disabled = locked;
  }

  const CATEGORY_LABELS = {
    featured: "精选演示",
    "能源与资源": "能源与资源",
    "汽车与装备制造": "汽车与装备制造",
    "消费、家电与科技制造": "消费、家电与科技制造",
  };

  function renderCaseCard(caseItem, index, selected) {
    const years = (caseItem.report_years || []).join(" / ");
    const admission = caseItem.admission_status === "passed" ? "已完成准入验收" : "候选案例 · 准入验收进行中";
    const categoryLabel = CATEGORY_LABELS[caseItem.category] || caseItem.category;
    return `<button type="button" class="demo-case-card" data-demo-case="${escapeHtml(caseItem.case_id)}" aria-pressed="${selected ? "true" : "false"}">
      <span class="demo-case-index">CASE ${String(index + 1).padStart(2, "0")} · ${escapeHtml(caseItem.ticker || "")}</span>
      <h4>${escapeHtml(caseItem.company_name)}</h4>
      <span class="demo-case-meta">${escapeHtml(categoryLabel)} · ${escapeHtml(years)}</span>
      <span class="demo-case-focus">${escapeHtml(caseItem.demo_focus || "")} · ${escapeHtml(admission)}</span>
    </button>`;
  }

  function renderFeaturedCases() {
    const grid = byId("demo-featured-cases");
    const featured = demoState.cases.filter((item) => demoState.bootstrap.featured_case_ids.includes(item.case_id));
    grid.replaceChildren();
    featured.forEach((caseItem) => {
      const wrapper = document.createElement("div");
      wrapper.innerHTML = renderCaseCard(caseItem, demoState.cases.indexOf(caseItem), caseItem.case_id === demoState.caseId);
      const card = wrapper.firstElementChild;
      card.addEventListener("click", () => selectDemoCase(caseItem.case_id));
      grid.append(card);
    });
  }

  function renderAllCasesDrawer() {
    const body = byId("demo-cases-drawer-body");
    const groups = new Map();
    demoState.cases.forEach((caseItem, index) => {
      const group = caseItem.category === "featured" ? "featured" : caseItem.category;
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push({ caseItem, index });
    });
    const ordered = [
      ["featured", "精选演示"],
      ["能源与资源", "能源与资源"],
      ["汽车与装备制造", "汽车与装备制造"],
      ["消费、家电与科技制造", "消费、家电与科技制造"],
    ];
    body.replaceChildren();
    ordered.forEach(([key, label]) => {
      const members = groups.get(key) || [];
      if (!members.length) return;
      const section = document.createElement("section");
      section.className = "demo-drawer-group";
      section.setAttribute("aria-label", label);
      section.innerHTML = `<h4>${escapeHtml(label)} · ${members.length} 个</h4>`;
      const grid = document.createElement("div");
      grid.className = "demo-drawer-grid";
      members.forEach(({ caseItem, index }) => {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = renderCaseCard(caseItem, index, caseItem.case_id === demoState.caseId);
        const card = wrapper.firstElementChild;
        card.addEventListener("click", () => {
          selectDemoCase(caseItem.case_id);
          closeDrawer("demo-cases-drawer");
        });
        grid.append(card);
      });
      section.append(grid);
      body.append(section);
    });
  }

  function renderCurrentCase() {
    const caseItem = currentCase();
    byId("demo-current-case-name").textContent = caseItem ? caseItem.company_name : "未选择案例";
    const years = caseItem ? (caseItem.report_years || []).join("/") : "—";
    byId("demo-current-case-meta").textContent = caseItem
      ? `${caseItem.case_id} · ${caseItem.ticker || ""} · 报告年度 ${years}${caseItem.t0 ? ` · T0 ${caseItem.t0}` : ""}`
      : "—";
  }

  function renderFacts() {
    const bootstrap = demoState.bootstrap;
    byId("demo-fact-cases").textContent = String(bootstrap.case_count);
    const reports = bootstrap.cases.reduce((total, item) => total + (item.report_years?.length || 0), 0);
    byId("demo-fact-reports").textContent = String(reports);
    const ragReady = bootstrap.cases.filter((item) => item.rag?.status === "ready").length;
    const ragSourceReady = bootstrap.cases.filter((item) => item.rag?.source_status === "source_available").length;
    const ragRuntimeReady = bootstrap.cases.filter((item) => item.rag?.runtime_ready === true).length;
    byId("demo-fact-rag-source").textContent = `${ragSourceReady}/${bootstrap.case_count || 0}`;
    const ragFact = byId("demo-fact-rag");
    ragFact.textContent = String(ragReady);
    ragFact.title = `冻结检索材料 ${ragSourceReady}/${bootstrap.case_count || 0}；当前运行时可检索 ${ragRuntimeReady}/${bootstrap.case_count || 0}。`;
    const readiness = bootstrap.model_readiness || {};
    const modelFact = byId("demo-fact-model");
    modelFact.textContent = readiness.full_analysis_ready ? "真实模型可运行" : "降级可用";
    modelFact.title = readiness.full_analysis_ready
      ? "当前就绪快照允许真实模型运行"
      : `${readiness.full_analysis_message || "模型暂不可用"}（${readiness.full_analysis_reason_code || "unknown"}）`;
    const quality = bootstrap.model_quality || {};
    const qualityFact = byId("demo-fact-model-quality");
    qualityFact.classList.toggle("demo-quality-alert", Boolean(quality.alert));
    if (quality.status === "unavailable" || quality.alert_kind === "ledger_unavailable") {
      qualityFact.textContent = "台账不可用";
      qualityFact.title = quality.boundary || "运行时质量台账暂不可读取；不能据此判断模型成功率。";
    } else if (quality.status === "unmeasured") {
      qualityFact.textContent = "暂无样本";
      qualityFact.title = quality.boundary || "尚无真实外部三 Agent 完整运行样本。";
    } else if (typeof quality.success_rate === "number") {
      qualityFact.textContent = `${Math.round(quality.success_rate * 100)}%（${quality.success_count}/${quality.sample_count}）`;
      qualityFact.title = quality.alert
        ? `警告：最近 ${quality.sample_count} 次真实外部三 Agent 完整运行成功率低于 80%。`
        : `最近 ${quality.sample_count} 次真实外部三 Agent 完整运行成功率。`;
    } else {
      qualityFact.textContent = "不可读";
      qualityFact.title = quality.boundary || "真实模型成功率暂不可读取。";
    }
    byId("demo-positioning-case-count").textContent = String(bootstrap.case_count);
    byId("demo-positioning-report-count").textContent = String(reports);
    const liveEnabled = Boolean(bootstrap.capabilities?.onsite_live_sample);
    const liveCapability = byId("demo-live-capability");
    liveCapability.textContent = liveEnabled
      ? "本机现场模式已启用：可处理不在 15 案中的巨潮公开年报样例，并继续执行规则与三 Agent；模型未就绪时会如实降级。"
      : "共享演示保持只读：可用内置 15 案演示；处理新企业请用团队本机现场模式。";
    liveCapability.className = `form-message ${liveEnabled ? "success" : "warning"}`;
    byId("demo-live-submit").disabled = !liveEnabled;
    byId("demo-live-submit").title = liveEnabled ? "创建真实巨潮现场任务" : "共享演示只读，请在团队本机现场模式使用";
  }

  function notifyModelQuality(snapshot) {
    if (!snapshot?.alert || snapshot.alert_kind === "ledger_unavailable") return;
    if (snapshot.alert_kind && snapshot.alert_kind !== "threshold_breach") return;
    if (typeof snapshot.success_rate !== "number" || !Number.isFinite(snapshot.success_rate) || !(snapshot.sample_count > 0)) return;
    const rate = `${Math.round(snapshot.success_rate * 100)}%`;
    showToast(`模型成功率告警：最近 ${snapshot.sample_count ?? 0} 次真实外部三 Agent 完整运行仅 ${rate}，低于 80%。失败码已保留，请暂停盲目重试并检查供应商。`, "error");
  }

  function renderTechVersions() {
    const versions = demoState.bootstrap?.versions || {};
    const readiness = demoState.bootstrap?.model_readiness || {};
    byId("demo-tech-llm").textContent = `${readiness.provider_label || "DeepSeek 官方直连"} · ${readiness.model_id || "deepseek-v4-flash"}`;
    byId("demo-tech-versions").textContent = `工程 ${versions.engine || "—"} · 规则 ${versions.r1 || "—"} / ${versions.r2 || "—"} · RAG ${versions.rag_index || "—"} · Prompt ${versions.agent_prompt || "—"} · 输出 ${versions.agent_output || "—"}`;
  }

  const KNOWLEDGE_CATEGORY_LABELS = {
    annual_report: "年报",
    csrc_penalty: "监管处罚",
    exchange_inquiry: "交易所问询",
    accounting_standard: "会计准则",
    auditing_standard: "审计准则",
    tax_regulation: "税收法规",
    industry_report: "行业研报",
    news: "新闻",
    macro_indicator: "宏观指标",
  };

  function renderKnowledgeBase() {
    const knowledge = demoState.bootstrap?.knowledge_base || { draft_mode: true };
    const grid = byId("demo-knowledge-grid");
    grid.replaceChildren();
    const categories = knowledge.categories || {};
    const order = ["annual_report", "csrc_penalty", "exchange_inquiry", "accounting_standard", "auditing_standard", "tax_regulation", "industry_report", "news", "macro_indicator"];
    order.forEach((key) => {
      const category = categories[key] || { document_count: 0, verified_count: 0, coverage_status: "representative", validation_status: "pending" };
      const cell = document.createElement("div");
      cell.className = "demo-knowledge-cell";
      cell.innerHTML = `<dt>${escapeHtml(KNOWLEDGE_CATEGORY_LABELS[key] || key)}</dt><dd>${category.document_count ?? 0}<small>${category.verified_count ?? 0} 条已核验 · ${escapeHtml(category.coverage_status)}</small></dd>`;
      grid.append(cell);
    });
    const note = byId("demo-knowledge-note");
    note.textContent = `${knowledge.boundary || "知识库截止日未确认：全部类别按草案处理。"} 快照 ${knowledge.snapshot_id || "KNOWLEDGE-UNCONFIGURED-DRAFT"} · 截止日 ${knowledge.cutoff_date || "未确认"}。`;
  }

  const CATEGORY_SHORT = {
    annual_report: "年报",
    csrc_penalty: "监管处罚",
    exchange_inquiry: "交易所问询",
    accounting_standard: "会计准则",
    auditing_standard: "审计准则",
    tax_regulation: "税收法规",
    industry_report: "行业研报",
    news: "新闻",
    macro_indicator: "宏观指标",
  };

  function renderSourceLedger(run) {
    const list = byId("demo-source-ledger-list");
    list.replaceChildren();
    const regulatory = run.context?.regulatory_evidence || [];
    const trace = run.context?.knowledge_retrieval_trace || [];
    const rendered = [];
    trace.slice(0, 8).forEach((item) => {
      const li = document.createElement("li");
      const officialUrl = String(item.official_url || "");
      const link = safeHttpsUrl(officialUrl) ? `<a href="${escapeHtml(safeHttpsUrl(officialUrl))}" target="_blank" rel="noopener noreferrer">打开官方来源</a>` : "";
      li.innerHTML = `<strong>知识命中 · ${escapeHtml(item.publisher || "—")} · ${escapeHtml(CATEGORY_SHORT[item.source_category] || item.source_category || "—")}</strong><span>${escapeHtml(item.locator || "官方来源登记条目；请回到原文核验。")} ${link}</span><small>${escapeHtml(String(item.retrieval_id || ""))} · ${escapeHtml(String(item.source_id || ""))} · 快照 ${escapeHtml(String(item.snapshot_id || "—"))} · ${escapeHtml(officialUrl)}</small><small>可支持：${escapeHtml(item.claim_scope || "—")}；边界：${escapeHtml(item.boundary || "—")}</small>`;
      list.append(li);
      rendered.push(item.source_id);
    });
    regulatory.filter((item) => !rendered.includes(item.source_id)).slice(0, 12 - rendered.length).forEach((item) => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${escapeHtml(item.publisher || "—")} · ${escapeHtml(item.title || "—")}</strong><span>${escapeHtml(CATEGORY_SHORT[item.source_category] || item.source_category || "")} · 发布于 ${escapeHtml(String(item.published_at || "—"))}</span><small>${escapeHtml(String(item.sha256 || ""))} · ${escapeHtml(String(item.official_url || ""))} · ${escapeHtml(String(item.source_id || ""))}</small>`;
      list.append(li);
    });
    if (!trace.length && !regulatory.length) {
      const li = document.createElement("li");
      li.textContent = "知识库台账尚未接入监管与准则来源。";
      list.append(li);
    }
    const summary = run.context?.source_coverage_summary;
    byId("demo-source-ledger-note").textContent = `${summary?.boundary || ""} 本次实际命中 ${trace.length} 条；快照 ${run.context?.knowledge_snapshot_id || "KNOWLEDGE-UNCONFIGURED-DRAFT"} · 每条命中都标明可支持主张边界，监管、问询、行业、新闻与宏观资料不能证明当前企业事实。`;
  }

  function renderRunTrace(run) {
    const list = byId("demo-run-trace-list");
    list.replaceChildren();
    const timeline = demoState.fixedTask.task?.steps || {};
    const stageLabels = {
      evidence_load: "证据载入",
      rule_calculation: "规则计算",
      knowledge_retrieval: "知识检索",
      agent_collaboration: "三 Agent 协作",
      evidence_validation: "证据验证",
      structured_output: "结构化输出",
    };
    Object.entries(timeline).forEach(([key, item]) => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${escapeHtml(stageLabels[key] || key)} · ${escapeHtml(statusLabel(item?.status || "pending"))}</strong><span>${escapeHtml(item?.detail || "—")}</span><small>${escapeHtml(String(item?.updated_at || ""))}</small>`;
      list.append(li);
    });
    const attempts = run.context?.model_attempt_history || [];
    attempts.forEach((entry) => {
      const role = ROLE_SHORT_LABELS[entry.role] || entry.role || "Agent";
      const records = entry.attempts || [];
      const li = document.createElement("li");
      const summary = records.map((item) => `${item.kind || "call"}=${item.validation || "—"}`).join(" · ");
      li.innerHTML = `<strong>${escapeHtml(role)} 模型调用留痕 · ${escapeHtml(entry.status || "—")}</strong><span>${escapeHtml(entry.failure_code || summary || "已记录响应哈希与校验结果")}</span><small>${escapeHtml(records.map((item) => `${item.kind || "call"}: ${item.response_sha256 || "无响应哈希"}`).join(" · ") || "无可展示尝试")}</small>`;
      list.append(li);
    });
    const quality = run.context?.model_quality_snapshot;
    if (quality?.status) {
      const li = document.createElement("li");
      li.innerHTML = `<strong>模型质量窗口 · ${escapeHtml(quality.status)}</strong><span>${escapeHtml(quality.boundary || "仅统计真实外部三 Agent 完整运行")}</span><small>${escapeHtml(quality.sample_count ? `最近 ${quality.sample_count} 次：${quality.success_count}/${quality.sample_count}` : "尚无真实样本")}</small>`;
      list.append(li);
    }
    if (!list.children.length) {
      list.append(Object.assign(document.createElement("li"), { textContent: "本次任务尚未写入可展示的时间线或模型尝试记录。" }));
    }
  }

  function renderInnovationControls(run) {
    const context = run.context || {};
    const bundle = run.evidence_bundle || {};
    const matrix = context.assertion_evidence_procedure_matrix || bundle.assertion_evidence_procedure_matrix || [];
    const coverageList = byId("demo-coverage-list");
    coverageList.replaceChildren();
    const coverageCounts = matrix.reduce((counts, row) => {
      const status = String(row?.status || "gap");
      counts[status] = (counts[status] || 0) + 1;
      return counts;
    }, {});
    byId("demo-coverage-note").textContent = matrix.length
      ? `共 ${matrix.length} 个认定格：${coverageCounts.covered || 0} 已覆盖、${coverageCounts.partially_covered || 0} 部分覆盖、${coverageCounts.gap || 0} 存在缺口。`
      : "本次运行尚未形成认定—证据—程序矩阵。";
    matrix.slice(0, 6).forEach((row) => {
      const li = document.createElement("li");
      const procedures = (row.procedure_ids || []).slice(0, 3).join(" / ") || "无程序映射";
      li.innerHTML = `<strong>${escapeHtml(row.assertion || "—")}</strong> · ${escapeHtml(statusLabel(row.status) || row.status || "—")} · <code>${escapeHtml(procedures)}</code>`;
      coverageList.append(li);
    });
    if (!matrix.length) coverageList.append(Object.assign(document.createElement("li"), { textContent: "等待后端结构化结果。" }));
    byId("demo-coverage-state").textContent = matrix.length ? `程序映射 ${new Set(matrix.flatMap((row) => row.procedure_ids || [])).size} 个` : "运行后生成";

    const fitnessList = byId("demo-fitness-list");
    fitnessList.replaceChildren();
    const evidenceRows = Object.entries(bundle)
      .filter(([, rows]) => Array.isArray(rows))
      .flatMap(([, rows]) => rows)
      .filter((row) => row && row.fitness_class);
    const fitnessCounts = evidenceRows.reduce((counts, row) => {
      counts[row.fitness_class] = (counts[row.fitness_class] || 0) + 1;
      return counts;
    }, {});
    const fitnessLabels = {
      current_entity_primary_evidence: "当前企业直接证据",
      authoritative_normative_basis: "规范 / 程序依据",
      analogous_regulatory_or_industry_background: "类比 / 待验证背景",
      unverified_background: "未核验背景",
    };
    byId("demo-fitness-note").textContent = evidenceRows.length
      ? `已标注 ${evidenceRows.length} 条证据；${context.evidence_fitness_violations?.length || 0} 条越界主张被降级。`
      : "证据适配度尚未写入本次结果。";
    Object.entries(fitnessCounts).forEach(([key, count]) => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${escapeHtml(fitnessLabels[key] || key)}</strong> · ${escapeHtml(String(count))} 条`;
      fitnessList.append(li);
    });
    if (!evidenceRows.length) fitnessList.append(Object.assign(document.createElement("li"), { textContent: "等待证据包标注。" }));
    byId("demo-fitness-state").textContent = context.evidence_fitness_boundary ? "边界已编译进 Agent 输入" : "运行后生成";

    const numeric = context.numeric_claim_trace || bundle.numeric_claim_trace || {};
    const numericList = byId("demo-numeric-list");
    numericList.replaceChildren();
    const traces = Array.isArray(numeric.trace) ? numeric.trace : [];
    byId("demo-numeric-note").textContent = traces.length
      ? `共 ${traces.length} 个数字 token：${numeric.unverified_count || 0} 个未验证，关键未验证 ${numeric.key_unverified_count || 0} 个。`
      : "本次运行没有可提取的模型数字主张。";
    traces.slice(0, 5).forEach((item) => {
      const li = document.createElement("li");
      const source = item.source || "无来源";
      li.innerHTML = `<code>${escapeHtml(item.raw || "—")}</code> · ${escapeHtml(item.verification_status || "—")} · ${escapeHtml(source)}`;
      numericList.append(li);
    });
    if (!traces.length) numericList.append(Object.assign(document.createElement("li"), { textContent: "等待 Agent 草稿完成后回查。" }));
    byId("demo-numeric-state").textContent = numeric.passed === true ? "关键数字全部可回查" : numeric.key_unverified_count ? "关键数字未闭合，禁止完整成功" : "运行后生成";

    const anti = context.anti_confirmation || bundle.anti_confirmation || {};
    const antiList = byId("demo-anti-list");
    antiList.replaceChildren();
    byId("demo-anti-note").textContent = anti.reverse_evidence_search_performed
      ? `已执行反向检索：${anti.search_questions?.length || 0} 个问题，命中 ${anti.hit_count || 0} 条；正常解释 ${anti.alternative_explanations?.length || 0} 条。`
      : "本次未进入 Agent 路线，尚未执行反向检索。";
    (anti.search_questions || []).slice(0, 4).forEach((question) => {
      const li = document.createElement("li");
      li.innerHTML = `<code>${escapeHtml(question)}</code> · 反确认问题已登记`;
      antiList.append(li);
    });
    if (anti.none_supported_by_current_evidence) {
      antiList.append(Object.assign(document.createElement("li"), { textContent: "未找到当前证据支持的正常解释，已明确标记 none_supported_by_current_evidence。" }));
    }
    if (!antiList.children.length) antiList.append(Object.assign(document.createElement("li"), { textContent: "等待运行后生成反向搜索记录。" }));
    byId("demo-anti-state").textContent = anti.reverse_evidence_search_performed ? "搜索留痕已写入结果" : "运行后生成";
  }

  function renderProcedureMap() {
    const map = demoState.bootstrap?.audit_procedure_map || { procedures: [] };
    const procedures = map.procedures || [];
    const auto = byId("demo-procedure-auto");
    const aux = byId("demo-procedure-aux");
    const human = byId("demo-procedure-human");
    [auto, aux, human].forEach((list) => { list.replaceChildren(); });
    procedures.forEach((item) => {
      const group = String(item.automation_level || "");
      const target = group.includes("替代") ? auto : group.includes("辅助") ? aux : null;
      if (target) {
        const li = document.createElement("li");
        li.textContent = `${item.procedure}：${item.system_execution || ""}`;
        target.append(li);
      }
      const li = document.createElement("li");
      li.textContent = `${item.procedure}：${item.human_retained || ""}`.replace(/\s+/g, " ");
      human.append(li);
    });
    byId("demo-procedure-note").textContent = map.boundary || "边界说明以正式方案书为准。";
    byId("demo-procedure-version").textContent = `程序映射版本 ${map.schema_version || "unknown"} · ${map.scope || ""}`;
  }

  const SUPPLEMENT_STATE = { samples: [], selected: null, busy: false, parentRun: null };

  async function loadSupplementSamples() {
    const samples = byId("demo-supplement-samples");
    samples.replaceChildren();
    try {
      const response = await fetch(`${API_BASE}/api/supplement-samples`, { credentials: "include" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      SUPPLEMENT_STATE.samples = payload.samples || [];
      const empty = byId("demo-supplement-status");
      empty.hidden = true;
      renderSupplementSamples();
    } catch (error) {
      const status = byId("demo-supplement-status");
      status.hidden = false;
      status.className = "status-banner danger";
      status.innerHTML = `<strong>补充样例读取失败</strong><span>${escapeHtml(error.message)}</span>`;
    }
  }

  function renderSupplementSamples() {
    const samples = byId("demo-supplement-samples");
    samples.replaceChildren();
    const selectedId = SUPPLEMENT_STATE.selected;
    (SUPPLEMENT_STATE.samples || []).forEach((sample) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "demo-supplement-sample";
      button.setAttribute("aria-pressed", sample.sample_id === selectedId ? "true" : "false");
      button.innerHTML = `<strong>${escapeHtml(sample.title)}</strong><small>${escapeHtml(sample.material_type)} · ${escapeHtml(sample.description || "")}</small>`;
      button.addEventListener("click", () => {
        SUPPLEMENT_STATE.selected = sample.sample_id;
        renderSupplementSamples();
        byId("demo-supplement-apply").disabled = false;
      });
      samples.append(button);
    });
    if (!SUPPLEMENT_STATE.samples.length) {
      samples.append(Object.assign(document.createElement("div"), { className: "empty-state", innerHTML: "<strong>没有可用的内置补充样例</strong><p>请检查后端补充样例目录。</p>" }));
    }
  }

  async function startSupplementRerun() {
    const run = demoState.run;
    const sampleId = SUPPLEMENT_STATE.selected;
    if (!run || !sampleId || SUPPLEMENT_STATE.busy) return;
    SUPPLEMENT_STATE.busy = true;
    byId("demo-supplement-apply").disabled = true;
    const status = byId("demo-supplement-status");
    status.hidden = false;
    status.className = "status-banner neutral";
    status.innerHTML = "<strong>正在绑定补充资料并重新评估</strong><span>页面只显示后端真实状态。</span>";
    try {
      const fromSample = await fetch(`${API_BASE}/api/supplements/from-sample`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ parent_run_id: run.run_id, sample_id: sampleId, bound_rule_ids: ["R1", "R2"] }),
      });
      if (!fromSample.ok) {
        const body = await fromSample.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${fromSample.status}`);
      }
      const record = await fromSample.json();
      const rerun = await fetch(`${API_BASE}/api/supplements/${encodeURIComponent(record.supplement_id)}/rerun-task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ run_mode: "full_analysis" }),
      });
      if (!rerun.ok) {
        const body = await rerun.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${rerun.status}`);
      }
      const childTask = await rerun.json();
      SUPPLEMENT_STATE.parentRun = run;
      demoState.fixedTask.taskId = childTask.task_id;
      demoState.fixedTask.task = childTask;
      demoState.fixedTask.pollToken += 1;
      safeSessionSet(DEMO_TASK_STORAGE_KEY, JSON.stringify({ task_id: childTask.task_id, case_id: demoState.caseId }));
      resetStageRail();
      setPhase("running");
      setGate("neutral", "补充资料异步评估中", `父运行 ${run.run_id} 保留；页面将按后端六阶段读取子运行进度。`);
      renderFixedTaskProgress(childTask);
      status.className = "status-banner neutral";
      status.innerHTML = `<strong>补充评估已创建</strong><span>子任务 ${escapeHtml(childTask.task_id)} 已进入六阶段队列，页面会逐段更新。</span>`;
      void pollFixedRun(childTask.task_id, demoState.fixedTask.pollToken);
    } catch (error) {
      status.className = "status-banner danger";
      status.innerHTML = `<strong>补充评估未完成</strong><span>${escapeHtml(error.message)}</span>`;
    } finally {
      SUPPLEMENT_STATE.busy = false;
      byId("demo-supplement-apply").disabled = !SUPPLEMENT_STATE.selected;
    }
  }

  function renderSupplementDiff(childRun, parentRun) {
    const diff = byId("demo-supplement-diff");
    diff.hidden = false;
    const change = childRun.context?.recommendation_change;
    const supplement = childRun.context?.supplement_delta;
    const before = String(parentRun?.ai_recommendation || "not_generated");
    const after = String(childRun?.ai_recommendation || "not_generated");
    const recommended = statusLabel(after);
    const label = change?.label || (before === after ? "保留" : "建议发生变化");
    const fields = [
      ["父运行 ID", parentRun?.run_id || "—"],
      ["补充后运行 ID", childRun?.run_id || "—"],
      ["新增证据数量", `${supplement?.supplement_evidence_count ?? 1} 份`],
      ["建议判断", `${recommended}（${label}）`],
      ["原始字段", "未被覆盖；补充资料进入当前案例证据空间"],
      ["边界", "变化由新增证据产生，仍须真人复核后再决定是否追加程序。"],
    ];
    diff.innerHTML = `<h4>补充前后差异</h4><dl>${fields.map(([k, v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join("")}</dl>`;
    // 同源摘要进入结果区，参与打印/保存 PDF 的可追溯输出。
    const summary = byId("demo-supplement-summary");
    summary.hidden = false;
    summary.innerHTML = `<h4 id="demo-supplement-summary-title">补充证据前后差异（父运行 → 子运行）</h4><dl>${fields.map(([k, v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join("")}</dl>`;
  }

  function selectDemoCase(caseId, { fromHistory = false } = {}) {
    if (demoState.phase === "running") return;
    if (!demoState.caseIndex.has(caseId)) {
      showToast("未知案例，已回退默认案例。", "warning");
      caseId = demoState.bootstrap?.featured_case_ids?.[0] || demoState.cases[0]?.case_id;
      if (!caseId) return;
    }
    if (demoState.caseId === caseId && demoState.phase === "ready") return;
    // 切换案例前清空上一案例的结果、证据与错误状态，避免跨案例串线。
    abortActiveRun();
    demoState.caseId = caseId;
    demoState.fixedTask.retryOfTaskId = null;
    demoState.run = null;
    demoState.outcome = null;
    demoState.taskCreationBlocked = false;
    safeStorageSet(CASE_STORAGE_KEY, caseId);
    clearResultDisplay();
    resetStageRail();
    renderCurrentCase();
    renderFeaturedCases();
    renderAllCasesDrawer();
    updateUrl({ replace: fromHistory });
    if (demoState.phase !== "booting") {
      setPhase("ready");
      setGate("neutral", "已选择案例", "点击“开始审计预筛”后系统才会创建运行；选择案例本身不下载 PDF、不构建索引、不调用模型。");
    }
  }

  function abortActiveRun() {
    // 停止固定案例任务的轮询并移除刷新恢复标记；服务器上的任务与运行留痕不删除。
    stopFixedTaskPolling();
    demoState.fixedTask.taskId = null;
    safeSessionRemove(DEMO_TASK_STORAGE_KEY);
    if (demoState.runAbort) {
      // 标记为用户主动取消：中断后的 AbortError 不渲染成“请求超时”失败。
      demoState.userCancelled = true;
      demoState.runAbort.abort();
      demoState.runAbort = null;
    }
  }

  function clearResultDisplay() {
    byId("demo-result").hidden = true;
    byId("demo-result-items").replaceChildren();
    byId("demo-result-summary").replaceChildren();
    byId("demo-supplement-summary").hidden = true;
    byId("demo-supplement-summary").replaceChildren();
    byId("demo-structured-table-body").replaceChildren();
    byId("demo-source-ledger-list").replaceChildren();
    byId("demo-source-ledger-note").textContent = "运行后显示本次命中、来源定位、快照与主张边界。";
    byId("demo-run-trace-list").replaceChildren();
    ["demo-coverage-list", "demo-fitness-list", "demo-numeric-list", "demo-anti-list"].forEach((id) => byId(id).replaceChildren());
    byId("demo-coverage-note").textContent = "把审计认定、当前企业证据和可执行程序放在同一张可回查矩阵中。";
    byId("demo-fitness-note").textContent = "不同来源只能支持不同类型的主张；监管和行业资料不证明当前企业事实。";
    byId("demo-numeric-note").textContent = "模型文本中的关键数字必须回到规则、字段证据或当前案例上下文。";
    byId("demo-anti-note").textContent = "系统记录反向检索问题、命中证据和正常解释，不诱导模型凑结论。";
    ["demo-coverage-state", "demo-fitness-state", "demo-numeric-state", "demo-anti-state"].forEach((id) => { byId(id).textContent = "运行后生成"; });
    resetEvidenceAxis();
    byId("demo-evidence-drawer-body").replaceChildren(
      Object.assign(document.createElement("div"), { className: "empty-state", innerHTML: "<strong>尚无运行结果</strong><p>开始一次审计预筛后，这里会显示本次运行的字段证据与 RAG 片段。</p>" }),
    );
    byId("demo-agent-drawer-body").replaceChildren(
      Object.assign(document.createElement("div"), { className: "empty-state", innerHTML: "<strong>尚无运行结果</strong><p>开始一次审计预筛后，这里会显示三个角色的真实执行状态。</p>" }),
    );
  }

  function outcomeFromRun(run) {
    const completeness = String(run.run_completeness || "");
    const modelStatus = run.model_check?.status;
    const executionMode = run.execution_mode || run.model_check?.execution_mode || "unavailable";
    const hasRuleResults = Array.isArray(run.rule_results) && run.rule_results.length > 0;
    // 核心证据或规则失败：RAG 失败关闭、来源闸门未通过、无任何规则结果。
    if (modelStatus === "not_attempted_rag_failure" || !hasRuleResults || (run.source_validation?.issues || []).length) {
      return "failed_run";
    }
    // 真实模型链成功：模型通过硬校验且完整性为非回退的完成态。
    // 公开财报预筛路线的完成标签是 complete_public_prescreen*，与 complete_full_analysis 同级。
    const completedHonest = completeness.startsWith("complete_") && !completeness.includes("fallback");
    const cacheReplay = executionMode === "cache_replay" || run.model_check?.cache_hit === true;
    const deterministicFallback = executionMode === "deterministic_backup" || modelStatus === "demo_fallback";
    if (modelStatus === "model_success" && completedHonest && !cacheReplay && !deterministicFallback && Number(run.provider_call_count || 0) > 0) {
      return "success";
    }
    // 确定性结果可见但模型链未完成：明确降级，不冒充成功。
    return "degraded";
  }

  async function startDemoRun({ backup = false } = {}) {
    const allowedPhase = backup ? new Set(["ready", "failed_run"]) : new Set(["ready"]);
    if (!allowedPhase.has(demoState.phase) || !demoState.caseId) return;
    const caseItem = currentCase();
    if (!caseItem) return;
    const year = Math.max(...(caseItem.report_years || [2025]).map(Number));
    const retryOfTaskId = backup ? null : demoState.fixedTask.retryOfTaskId;
    const button = byId(backup ? "demo-backup" : "demo-start");
    button.disabled = true;
    button.textContent = backup ? "正在启动备用…" : "正在分析…";
    demoState.taskCreationBlocked = false;
    demoState.run = null;
    demoState.outcome = null;
    demoState.userCancelled = false;
    clearResultDisplay();
    stopFixedTaskPolling();
    resetStageRail();
    setPhase("running");
    setStageState(1, "current");
    setStageNote(1, "正在创建分阶段任务…");
    setStageNote(2, "等待后端执行");
    setStageNote(3, "等待后端执行");
    setStageNote(4, "等待后端执行");
    setStageNote(5, "等待后端执行");
    setStageNote(6, "等待后端执行");
    setGate("neutral", backup ? "正在启动确定性备用演示" : "正在执行完整分析", backup
      ? `案例 ${caseItem.case_id} · ${caseItem.company_name} · 不调用外部模型，结果只保留在当前 Web 实例。`
      : `案例 ${caseItem.case_id} · ${caseItem.company_name} · 报告年度 ${year}；页面只显示后端真实进度。`);
    try {
      const response = await fetch(`${API_BASE}${backup ? "/api/demo/backup-runs" : "/api/demo/runs"}`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": window.crypto?.randomUUID ? window.crypto.randomUUID() : `demo-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        },
        body: JSON.stringify({
          case_id: caseItem.case_id,
          current_year: year,
          scene: "审计计划",
          rule_ids: caseItem.rule_ids?.length ? caseItem.rule_ids : ["R1"],
          run_mode: "full_analysis",
          ...(backup ? { force_deterministic_backup: true } : {}),
          ...(retryOfTaskId ? { retry_of_task_id: retryOfTaskId } : {}),
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw Object.assign(new Error(body.detail || `HTTP ${response.status}`), { statusCode: response.status });
      }
      const payload = await response.json();
      const taskId = payload.task_id;
      demoState.fixedTask.taskId = taskId;
      demoState.fixedTask.retryOfTaskId = null;
      demoState.fixedTask.task = { task_id: taskId, status: payload.status, stage_schema_version: payload.stage_schema_version, steps: payload.steps || {}, agent_steps: payload.agent_steps || {} };
      demoState.fixedTask.pollToken += 1;
      safeSessionSet(DEMO_TASK_STORAGE_KEY, JSON.stringify({ task_id: taskId, case_id: demoState.caseId, mode: backup ? "backup" : "primary" }));
      renderFixedTaskProgress(demoState.fixedTask.task);
      void pollFixedRun(taskId, demoState.fixedTask.pollToken);
    } catch (error) {
      demoState.fixedTask.taskId = null;
      safeSessionRemove(DEMO_TASK_STORAGE_KEY);
      renderDemoFailure("run_http_error", backup ? "备用演示未能创建任务" : "本次分析未能创建任务", error.message, { retry: true, taskNotCreated: true });
    } finally {
      button.textContent = backup ? "启动确定性备用演示" : "开始审计预筛";
      renderControls();
    }
  }

  async function requestDemoCancel() {
    const taskId = demoState.fixedTask.taskId;
    if (!taskId || demoState.phase !== "running") return;
    const button = byId("demo-cancel");
    button.dataset.busy = "true";
    button.textContent = "正在请求取消…";
    renderControls();
    try {
      const response = await fetch(`${API_BASE}/api/demo/runs/${encodeURIComponent(taskId)}/cancel`, {
        method: "POST",
        credentials: "include",
      });
      const payload = await response.json().catch(() => ({}));
      if (response.status === 409) {
        showToast(payload.detail || "任务已进入不可中断协作阶段，继续等待当前调用结算。", "warning");
        return;
      }
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      showToast("已请求取消；页面等待后端在阶段边界确认终态。", "warning");
      void pollFixedRun(taskId, demoState.fixedTask.pollToken);
    } catch (error) {
      showToast(`取消请求失败：${error.message}`, "error");
    } finally {
      button.dataset.busy = "false";
      button.textContent = "请求取消";
      renderControls();
    }
  }

  async function pollFixedRun(taskId, token) {
    if (!taskId || token !== demoState.fixedTask.pollToken) return;
    try {
      const response = await fetch(`${API_BASE}/api/demo/runs/${encodeURIComponent(taskId)}`, { credentials: "include" });
      if (response.status === 404) {
        safeSessionRemove(DEMO_TASK_STORAGE_KEY);
        demoState.fixedTask.taskId = null;
        renderDemoFailure("TASK_NOT_FOUND", "任务已不存在", "后端没有找到该任务；页面已停止轮询，请重新创建演示任务。", { retry: true });
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const task = await response.json();
      if (token !== demoState.fixedTask.pollToken) return;
      demoState.fixedTask.task = task;
      renderFixedTaskProgress(task);
      if (TASK_ACTIVE_STATUSES.has(task.status)) {
        demoState.fixedTask.pollTimer = window.setTimeout(() => { void pollFixedRun(taskId, token); }, DEMO_POLL_INTERVAL_MS);
      } else {
        demoState.fixedTask.pollTimer = null;
        await renderFixedTaskFinal(task);
      }
    } catch (error) {
      if (token !== demoState.fixedTask.pollToken) return;
      // 轮询失败指数退避，保留最后状态：2s、4s、8s、16s 后重试。
      const backoff = Math.min(16000, 2000 * (2 ** (demoState.fixedTask.pollRetry ?? 0)));
      demoState.fixedTask.pollRetry = (demoState.fixedTask.pollRetry ?? 0) + 1;
      demoState.fixedTask.pollTimer = window.setTimeout(() => { void pollFixedRun(taskId, token); }, backoff);
      const statusItem = byId("demo-result-state");
      statusItem.className = "state waiting";
      statusItem.textContent = "网络波动：任务仍在后端执行，页面保留最后状态。";
    }
  }

  async function renderFixedTaskFinal(task) {
    try {
      let run = task?.result;
      if (["cancelled", "interrupted", "failed", "expired"].includes(task?.status)) {
        clearResultDisplay();
        const label = task.status === "cancelled"
          ? "任务已取消"
          : task.status === "interrupted"
            ? "任务因服务重启中断"
            : task.status === "expired"
              ? "任务结果已过期"
              : "任务失败，未形成结构化结果";
        const detail = task.status === "interrupted"
          ? `${task.error || "运行中 Web 实例已停止，未自动重放模型调用。"}；旧任务 ${task.task_id || "—"} 已保留，请点击重置后创建新任务。`
          : task.status === "expired"
            ? "结果超过公开保留期（默认 7 天），原始正文已按策略清理；请创建新任务。"
            : (task.error || task.failure_code || "后续阶段已跳过，结果接口拒绝导出。");
        setGate(task.status === "failed" ? "danger" : "warning", label, detail);
        if (SUPPLEMENT_STATE.parentRun) {
          const status = byId("demo-supplement-status");
          status.hidden = false;
          status.className = `status-banner ${task.status === "failed" ? "danger" : "warning"}`;
          status.innerHTML = `<strong>补充评估未形成结果</strong><span>${escapeHtml(task.error || task.failure_code || label)}；父运行仍保留。</span>`;
          SUPPLEMENT_STATE.parentRun = null;
        }
        demoState.outcome = task.status;
        demoState.fixedTask.retryOfTaskId = task.task_id || null;
        safeSessionRemove(DEMO_TASK_STORAGE_KEY);
        setPhase(task.status);
        return;
      }
      if (!run) {
        const response = await fetch(`${API_BASE}/api/demo/runs/${encodeURIComponent(task.task_id)}/result`, { credentials: "include" });
        if (response.status === 404) {
          safeSessionRemove(DEMO_TASK_STORAGE_KEY);
          renderDemoFailure("TASK_NOT_FOUND", "任务已不存在", "后端没有找到该任务；页面已停止轮询，请重新创建演示任务。", { retry: true });
          return;
        }
        if (response.status === 410) {
          await renderFixedTaskFinal({ ...task, status: "expired", failure_code: "TASK_RESULT_EXPIRED" });
          return;
        }
        if (response.status === 409) {
          // 终态与结果写入存在毫秒级竞态：下一次轮询仍会命中终态任务。
          demoState.fixedTask.pollTimer = window.setTimeout(() => { void pollFixedRun(task.task_id, demoState.fixedTask.pollToken); }, 600);
          return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        run = await response.json();
      }
      demoState.run = run;
      demoState.outcome = outcomeFromRun(run);
      renderDemoResult(run, demoState.outcome);
      if (SUPPLEMENT_STATE.parentRun && run.context?.supplement_id) {
        renderSupplementDiff(run, SUPPLEMENT_STATE.parentRun);
        const status = byId("demo-supplement-status");
        status.hidden = false;
        status.className = "status-banner success";
        status.innerHTML = `<strong>补充评估已完成</strong><span>子运行 ${escapeHtml(run.run_id)} 已生成；原年报字段未被覆盖。</span>`;
        SUPPLEMENT_STATE.parentRun = null;
      }
    } catch (error) {
      renderDemoFailure("result_read_error", "结果读取失败", error.message, { retry: true });
    }
  }

  async function restoreFixedTaskSession() {
    const raw = safeSessionGet(DEMO_TASK_STORAGE_KEY);
    if (!raw) return;
    let stored = null;
    try { stored = JSON.parse(raw); } catch (_error) { safeSessionRemove(DEMO_TASK_STORAGE_KEY); return; }
    const taskId = stored?.task_id;
    const storedCase = stored?.case_id;
    if (!taskId || !storedCase || !demoState.caseIndex.has(storedCase)) {
      safeSessionRemove(DEMO_TASK_STORAGE_KEY);
      return;
    }
    demoState.caseId = storedCase;
    renderCurrentCase();
    renderFeaturedCases();
    updateUrl();
    try {
      const response = await fetch(`${API_BASE}/api/demo/runs/${encodeURIComponent(taskId)}`, { credentials: "include" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      let task = await response.json();
      // queued 表示后台尚未开始任何阶段。若创建任务的 Web 实例恰好在
      // 领取前重启，刷新时显式重发同一案例请求；后端通过活动任务唯一键
      // 与原子租约复用原 task_id，不会重复执行已经 running 的模型调用。
      if (task.status === "queued" && stored.mode === "primary") {
        const caseItem = currentCase();
        const year = Math.max(...(caseItem?.report_years || [2025]).map(Number));
        const resumeResponse = await fetch(`${API_BASE}/api/demo/runs`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": window.crypto?.randomUUID ? window.crypto.randomUUID() : `demo-resume-${Date.now()}`,
          },
          body: JSON.stringify({
            case_id: storedCase,
            current_year: year,
            scene: "审计计划",
            rule_ids: caseItem?.rule_ids?.length ? caseItem.rule_ids : ["R1"],
            run_mode: "full_analysis",
          }),
        });
        if (resumeResponse.ok) task = await resumeResponse.json();
      }
      const restoredTaskId = task.task_id || taskId;
      demoState.fixedTask.taskId = restoredTaskId;
      demoState.fixedTask.task = task;
      setPhase("running");
      clearResultDisplay();
      resetStageRail();
      setGate("neutral", "已恢复上次演示任务", task.status === "queued"
        ? "任务仍在排队，页面继续读取后端同一任务的真实进度。"
        : "页面未重复创建任务，正在读取后端同一任务的真实进度。");
      renderFixedTaskProgress(task);
      if (TASK_ACTIVE_STATUSES.has(task.status)) {
        demoState.fixedTask.pollToken += 1;
        void pollFixedRun(restoredTaskId, demoState.fixedTask.pollToken);
      } else {
        demoState.fixedTask.pollToken += 1;
        await renderFixedTaskFinal(task);
      }
    } catch (_error) {
      safeSessionRemove(DEMO_TASK_STORAGE_KEY);
      demoState.fixedTask.taskId = null;
      setPhase("ready");
      if (String(taskId).startsWith("DEMO-BACKUP-")) {
        setGate("warning", "备用任务已随实例结束", "确定性备用只保留在当前 Web 实例；请重新检测台账，或重新启动备用演示。页面没有自动重放任何调用。");
      }
    }
  }

  function renderDemoProgress(outcome, run) {
    const modelStatus = run.model_check?.status;
    const agentsDone = (run.agent_steps || []).filter((step) => step.status === "completed").length;
    const knowledgeHits = run.context?.knowledge_retrieval_trace?.length ?? 0;
    resetStageRail();
    setStageState(1, "completed");
    setStageNote(1, `${run.evidence_bundle?.field_evidence?.length ?? 0} 条字段证据`);
    setStageState(2, "completed");
    setStageNote(2, `${run.rule_results?.length ?? 0} 条规则结果`);
    setStageState(3, knowledgeHits ? "completed" : "skipped");
    setStageNote(3, knowledgeHits ? `${knowledgeHits} 条知识命中 · 可回查定位` : "未产生知识命中");
    if (outcome === "success") {
      setStageState(4, "completed");
      setStageNote(4, `三角色完成 · ${run.provider_call_count ?? 0} 次模型调用`);
      setStageState(5, "completed");
      setStageNote(5, `${run.evidence_bundle?.field_evidence?.length ?? 0} 条字段证据可回查`);
      setStageState(6, "completed");
      setStageNote(6, "JSON / 表格 / PDF 可导出");
    } else if (outcome === "degraded") {
      setStageState(4, "degraded");
      setStageNote(4, `本次未完成真实模型调用（${statusLabel(modelStatus)}${agentsDone ? ` · ${agentsDone}/3 角色完成` : ""}）`);
      setStageState(5, "completed");
      setStageNote(5, "确定性证据与缺口已保留");
      setStageState(6, "completed");
      setStageNote(6, "降级结果可结构化导出");
    } else {
      setStageState(4, "failed");
      setStageNote(4, statusLabel(modelStatus || run.run_completeness));
      setStageState(5, "failed");
      setStageNote(5, "证据链未闭合");
      setStageState(6, "failed");
      setStageNote(6, "未形成结构化成果");
    }
  }

  function renderDemoResult(run, outcome) {
    renderDemoProgress(outcome, run);
    const caseItem = currentCase();
    const year = Math.max(...(caseItem?.report_years || [0]).map(Number));
    const statePill = byId("demo-result-state");
    statePill.className = `state ${outcome === "success" ? "success" : outcome === "degraded" ? "waiting" : "danger"}`;
    statePill.textContent = outcome === "success"
      ? "真实模型链完成"
      : outcome === "degraded"
        ? "降级：确定性结果可见，本次未完成真实模型调用"
        : "失败";
    const executionMode = run.execution_mode || run.model_check?.execution_mode || "unavailable";
    const summary = byId("demo-result-summary");
    summary.replaceChildren();
    const rows = [
      {
        label: "分析对象",
        value: caseItem?.company_name || run.context?.case_id,
        detail: `报告年度 ${year}`,
        tone: "is-primary",
      },
      { label: "运行编号", value: run.run_id, detail: "本次运行唯一标识", tone: "is-run" },
      {
        label: "运行完整性",
        value: statusLabel(run.run_completeness),
        detail: outcome === "success" ? "模型链与结果均已完成" : "请结合上方状态说明复核",
        tone: outcome === "success" ? "is-success" : "",
      },
      { label: "程序筛查", value: statusLabel(run.screening_status), detail: "固定规则先于模型执行", tone: "" },
      {
        label: "执行方式",
        value: statusLabel(executionMode),
        detail: `${(run.provider_call_count ?? 0).toLocaleString("zh-CN")} 次模型调用 · ${(run.input_tokens ?? 0).toLocaleString("zh-CN")} / ${(run.output_tokens ?? 0).toLocaleString("zh-CN")} tokens`,
        tone: "",
      },
    ];
    rows.forEach(({ label, value, detail, tone }) => {
      const cell = document.createElement("div");
      cell.className = `demo-summary-cell ${tone}`.trim();
      const span = document.createElement("span");
      span.className = "demo-summary-label";
      span.textContent = label;
      const strong = document.createElement("strong");
      strong.className = "demo-summary-value";
      strong.textContent = value;
      const small = document.createElement("small");
      small.className = "demo-summary-detail";
      small.textContent = detail;
      cell.append(span, strong, small);
      summary.append(cell);
    });
    const items = byId("demo-result-items");
    items.replaceChildren();
    const draftItems = (run.rule_results || [])
      .filter((result) => result.risk_card || result.ai_draft)
      .slice(0, 5);
    draftItems.forEach((result, index) => {
      const draft = result.ai_draft;
      const card = document.createElement("article");
      card.className = "demo-item-card";
      const claims = (draft?.claims || []).slice(0, 5);
      const gaps = [...new Set([...(draft?.data_gaps || []), ...(result.risk_card?.data_gaps || [])])].slice(0, 6);
      const metrics = Object.entries(result.metrics || {})
        .filter(([key, value]) => value !== null && value !== undefined && METRIC_LABELS[key])
        .slice(0, 4);
      const metricsHtml = metrics.map(([key, value]) => `
        <div class="demo-metric">
          <span>${escapeHtml(METRIC_LABELS[key])}</span>
          <strong>${escapeHtml(formatMetricValue(key, value))}</strong>
        </div>`).join("");
      card.innerHTML = `
        <span class="demo-item-eyebrow">待核查事项 ${String(index + 1).padStart(2, "0")} · ${escapeHtml(result.risk_card?.rule_id || result.rule_id)}</span>
        <h4>${escapeHtml(draft?.draft_title || result.risk_card?.title || result.rule_id)}</h4>
        <p>${escapeHtml(draft?.draft_observation || result.risk_card?.observation || "等待更多证据。")}</p>
        ${metricsHtml ? `<div class="demo-metric-grid" aria-label="关键指标">${metricsHtml}</div>` : ""}
        ${claims.length ? `<ul class="demo-item-facts">${claims.map((claim) => `<li>${escapeHtml(claim.text)} <small>(${escapeHtml(claim.support_status)} · ${(claim.evidence_ids || []).map(escapeHtml).join(" / ") || "无引用"})</small></li>`).join("")}</ul>` : ""}
        ${gaps.length ? `<p class="demo-item-facts"><strong>缺失资料 / 需人工核查：</strong>${gaps.map(escapeHtml).join("；")}</p>` : ""}
        <small class="demo-ai-notice">${escapeHtml(AI_GENERATED_CONTENT_NOTICE)}</small>`;
      items.append(card);
    });
    if (!draftItems.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.innerHTML = "<strong>本次运行没有形成待核查事项卡</strong><p>请查看运行完整性与模型状态；系统不会用模拟内容填补。</p>";
      items.append(empty);
    }
    byId("demo-result").hidden = false;
    if (outcome === "success") {
      setGate("success", statusLabel(run.run_completeness), `AI 分析路线：${ROUTE_LABELS[run.ai_analysis_route] || "三Agent协同复核"}；${AI_GENERATED_CONTENT_NOTICE}`);
    } else if (outcome === "degraded") {
      setGate("warning", "本次未完成真实模型调用", `确定性计算结果仍可查看（${statusLabel(run.model_check?.status)}）；失败码已保留，后续角色如实标记。${AI_GENERATED_CONTENT_NOTICE}`);
    } else {
      setGate("danger", "本次分析失败", `${statusLabel(run.model_check?.status || run.run_completeness)}；可一键重置演示后重试，或联系团队处理。`);
    }
    renderEvidenceDrawer(run);
    renderAgentDrawer(run);
    renderStructuredTable(run);
    renderEvidenceAxis(run, outcome);
    renderSourceLedger(run);
    renderRunTrace(run);
    renderInnovationControls(run);
    notifyModelQuality(run.context?.model_quality_snapshot);
    setPhase(outcome === "failed_run" ? "failed_run" : outcome);
  }

  function renderDemoFailure(code, title, detail, options) {
    resetStageRail();
    if (options?.taskNotCreated) {
      setStageNote(1, "任务未创建");
      [2, 3, 4, 5, 6].forEach((stage) => setStageNote(stage, "未启动"));
      demoState.taskCreationBlocked = true;
    } else {
      [1, 2, 3, 4, 5, 6].forEach((stage) => { setStageState(stage, "failed"); setStageNote(stage, "未完成"); });
    }
    setGate("danger", title, detail);
    demoState.outcome = "failed_run";
    setPhase("failed_run");
    if (options?.retry) showToast(`${title}（failure_code: ${code}）`, "error");
  }

  function sourceLink(caseId, documentId, page) {
    return `${API_BASE}/api/cases/${encodeURIComponent(caseId)}/sources/${encodeURIComponent(documentId)}#page=${encodeURIComponent(page || 1)}`;
  }

  function renderEvidenceDrawer(run) {
    const body = byId("demo-evidence-drawer-body");
    body.replaceChildren();
    const caseId = currentCase()?.case_id || run.context?.case_id;
    const fieldEvidence = run.evidence_bundle?.field_evidence || [];
    const ragEvidence = run.evidence_bundle?.rag_evidence || [];
    const section = (title, list, kind) => {
      if (!list.length) return null;
      const group = document.createElement("section");
      group.className = "demo-drawer-group";
      group.innerHTML = `<h4>${escapeHtml(title)} · ${list.length} 条</h4>`;
      list.slice(0, 30).forEach((item) => {
        const node = document.createElement("div");
        node.className = "demo-evidence-item";
        const meta = [
          item.evidence_id,
          item.pdf_page ? `PDF 第 ${item.pdf_page} 页` : null,
          item.disclosure_date,
          kind === "rag" ? item.rule_id : null,
        ].filter(Boolean).join(" · ");
        const link = item.document_id && caseId
          ? `<a href="${escapeHtml(sourceLink(caseId, item.document_id, item.pdf_page))}" target="_blank" rel="noopener noreferrer">打开原文 PDF</a>`
          : "";
        node.innerHTML = `<span class="demo-evidence-meta">${escapeHtml(meta)}</span><span>${escapeHtml(item.excerpt || item.term || "")}</span>${link}`;
        group.append(node);
      });
      return group;
    };
    const fieldSection = section("字段证据（本次运行使用的冻结年报数据）", fieldEvidence, "field");
    const ragSection = section("RAG 检索片段（候选原文，须回原件复核）", ragEvidence, "rag");
    if (fieldSection) body.append(fieldSection);
    if (ragSection) body.append(ragSection);
    if (!fieldSection && !ragSection) {
      body.append(Object.assign(document.createElement("div"), { className: "empty-state", innerHTML: "<strong>本次运行没有可用证据条目</strong><p>缺失项保持缺失，系统不估算、不补造。</p>" }));
    }
  }

  function renderAgentDrawer(run) {
    const body = byId("demo-agent-drawer-body");
    body.replaceChildren();
    const hero = document.createElement("figure");
    hero.className = "demo-agent-hero";
    hero.innerHTML = `<img src="/assets/official-v4/illustrations/agents-nodes.webp" alt="" width="1672" height="940" loading="lazy" decoding="async"><figcaption>三角色分工 · 挑战（质疑）→ 反证 → 复核；角色状态与失败码以下方卡片为准</figcaption>`;
    body.append(hero);
    const steps = run.agent_steps || [];
    if (!steps.length) {
      body.append(Object.assign(document.createElement("div"), { className: "empty-state", innerHTML: "<strong>本次运行没有 Agent 执行记录</strong><p>模型链未运行时会如实显示，不补造协作过程。</p>" }));
      return;
    }
    const roleMeta = {
      challenge: { name: "质疑 Agent", badge: "步骤 1 · 提出风险假设与缺口" },
      counter: { name: "反证 Agent", badge: "步骤 2 · 对立检验与正常解释" },
      review: { name: "复核 Agent", badge: "步骤 3 · 综合评估与草稿把关" },
    };
    steps.forEach((step) => {
      const meta = roleMeta[step.role] || { name: step.role, badge: "附加步骤" };
      const output = step.output;
      const card = document.createElement("article");
      card.className = "demo-evidence-item";
      const claims = (output?.claims || []).slice(0, 4).map((claim) => `<li>${escapeHtml(claim.text)} <small>(${escapeHtml(claim.support_status)} · ${(claim.evidence_ids || []).join(" / ") || "无引用"})</small></li>`).join("");
      const normals = (output?.normal_explanations || []).slice(0, 3).map((item) => `<li>${escapeHtml(item.text)}</li>`).join("");
      card.innerHTML = `
        <span class="demo-evidence-meta">${escapeHtml(meta.badge)} · ${escapeHtml(step.model_id || "")}</span>
        <strong>${escapeHtml(meta.name)} — ${escapeHtml(statusLabel(step.status))}${step.failure_code ? `（${escapeHtml(step.failure_code)}）` : ""}</strong>
        ${step.detail ? `<span>${escapeHtml(step.detail)}</span>` : ""}
        ${claims ? `<ul class="demo-item-facts">${claims}</ul>` : ""}
        ${normals ? `<ul class="demo-item-facts"><li><strong>正常解释：</strong></li>${normals}</ul>` : ""}
        ${output?.reason_for_status ? `<span>${escapeHtml(output.reason_for_status)}</span>` : ""}`;
      body.append(card);
    });
  }

  function resetEvidenceAxis() {
    document.querySelectorAll("#demo-evidence-axis-list li").forEach((item) => {
      item.classList.remove("complete", "warning");
      const note = item.querySelector("small");
      if (note) note.textContent = "等待运行";
    });
  }

  function setAxisItem(name, detail, kind = "complete") {
    const item = document.querySelector(`#demo-evidence-axis-list [data-axis="${name}"]`);
    if (!item) return;
    item.classList.remove("complete", "warning");
    item.classList.add(kind);
    const note = item.querySelector("small");
    if (note) note.textContent = detail;
  }

  function renderEvidenceAxis(run, outcome) {
    const fieldCount = run.evidence_bundle?.field_evidence?.length ?? 0;
    const ragCount = run.evidence_bundle?.rag_evidence?.length ?? 0;
    const agentsDone = (run.agent_steps || []).filter((step) => step.status === "completed").length;
    const gapCount = (run.rule_results || []).reduce((total, result) => total + new Set([...(result.risk_card?.data_gaps || []), ...(result.ai_draft?.data_gaps || [])]).size, 0);
    const metricCount = (run.rule_results || []).reduce((total, result) => total + Object.keys(result.metrics || {}).length, 0);
    setAxisItem("screening", `${statusLabel(run.screening_status)} · ${run.rule_results?.length ?? 0} 条规则结果`);
    setAxisItem("rag", `${ragCount} 次检索片段 · ${agentsDone}/3 角色完成`, outcome === "success" ? "complete" : "warning");
    setAxisItem("evidence", `${fieldCount} 条字段证据 · ${gapCount} 项资料缺口`, gapCount ? "warning" : "complete");
    setAxisItem("output", `${metricCount} 个结构化指标 · JSON / 表格 / PDF`, "complete");
  }

  function structuredMetricRows(run) {
    const rows = [];
    (run.rule_results || []).forEach((result) => {
      Object.entries(result.metrics || {}).forEach(([key, value]) => {
        if (value === null || value === undefined) return;
        rows.push({
          rule_id: result.rule_id || result.risk_card?.rule_id || "—",
          metric_key: key,
          metric_label: METRIC_LABELS[key] || key,
          formatted_value: formatMetricValue(key, value),
          raw_value: value,
          basis: PERCENT_METRICS.has(key) || key === "growth_gap" ? "比例按小数存储" : key.includes("days") ? "单位：天" : "run_output_v2 原始值",
        });
      });
    });
    return rows;
  }

  function renderStructuredTable(run) {
    const body = byId("demo-structured-table-body");
    body.replaceChildren();
    const rows = structuredMetricRows(run);
    if (!rows.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="4">本次运行没有可展示的结构化指标；系统不会补造数值。</td>';
      body.append(tr);
      return;
    }
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      [row.rule_id, row.metric_label, row.formatted_value, `${String(row.raw_value)} · ${row.basis}`].forEach((value) => {
        const td = document.createElement("td");
        td.textContent = value;
        tr.append(td);
      });
      body.append(tr);
    });
  }

  function safeDownloadName(value) {
    return String(value || "audittrace").replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "audittrace";
  }

  function downloadBlob(filename, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadRunJson() {
    if (!demoState.run || ["failed_run", "failed", "cancelled", "interrupted"].includes(demoState.outcome)) return;
    const run = demoState.run;
    const task = demoState.fixedTask.task || {};
    const payload = {
      schema_version: "audittrace_structured_export_v1",
      exported_at: new Date().toISOString(),
      ai_generated_content_notice: AI_GENERATED_CONTENT_NOTICE,
      export_boundary: "同一运行的 JSON、CSV 与打印/PDF 仅允许导出可读的 completed/degraded 结果；失败、取消和中断任务不生成结果导出。",
      run_id: run.run_id,
      task_status: task.status || demoState.outcome,
      parent_run_id: run.context?.parent_run_id || run.parent_run_id || null,
      supplement_id: run.context?.supplement_id || null,
      supplement_delta: run.context?.supplement_delta || null,
      run: run,
      progress_task_id: demoState.fixedTask.taskId,
      task_timeline: task.steps || {},
      knowledge_snapshot_id: run.context?.knowledge_snapshot_id,
      knowledge_retrieval_trace: run.context?.knowledge_retrieval_trace || [],
      knowledge_source_ledger: run.context?.knowledge_source_ledger || [],
      source_coverage_summary: run.context?.source_coverage_summary,
      model_attempt_history: run.context?.model_attempt_history || [],
      model_quality_snapshot: run.context?.model_quality_snapshot,
      audit_procedure_map_version: run.context?.audit_procedure_map_version,
      audit_procedures: run.context?.audit_procedures,
      regulatory_evidence: run.context?.regulatory_evidence,
      assertion_evidence_procedure_matrix: run.context?.assertion_evidence_procedure_matrix || run.evidence_bundle?.assertion_evidence_procedure_matrix || [],
      evidence_fitness_boundary: run.context?.evidence_fitness_boundary,
      evidence_fitness_violations: run.context?.evidence_fitness_violations || run.evidence_bundle?.evidence_fitness_violations || [],
      numeric_claim_trace: run.context?.numeric_claim_trace || run.evidence_bundle?.numeric_claim_trace || {},
      anti_confirmation: run.context?.anti_confirmation || run.evidence_bundle?.anti_confirmation || {},
      supplement_delta: run.context?.supplement_delta,
      provider_readiness_snapshot: run.context?.provider_readiness_snapshot,
    };
    downloadBlob(`${safeDownloadName(demoState.run.run_id)}.json`, JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
  }

  function csvCell(value) {
    return `"${String(value ?? "").replaceAll('"', '""')}"`;
  }

  function downloadRunCsv() {
    if (!demoState.run || ["failed_run", "failed", "cancelled", "interrupted"].includes(demoState.outcome)) return;
    const run = demoState.run;
    const task = demoState.fixedTask.task || {};
    const parentRunId = run.context?.parent_run_id || run.parent_run_id || "";
    const supplementId = run.context?.supplement_id || "";
    const rows = structuredMetricRows(demoState.run);
    const lines = [
      ["run_id", "rule_id", "metric_key", "metric_label", "formatted_value", "raw_value", "basis"].map(csvCell).join(","),
      ...rows.map((row) => [demoState.run.run_id, row.rule_id, row.metric_key, row.metric_label, row.formatted_value, row.raw_value, row.basis].map(csvCell).join(",")),
      [run.run_id, "__meta__", "task_status", "任务终态", "", task.status || demoState.outcome || "", "后端任务台账"].map(csvCell).join(","),
      [run.run_id, "__meta__", "parent_run_id", "父运行编号", "", parentRunId, "补充材料父子链"].map(csvCell).join(","),
      [run.run_id, "__meta__", "supplement_id", "补充资料编号", "", supplementId, "补充材料父子链"].map(csvCell).join(","),
      [run.run_id, "__meta__", "task_timeline", "六阶段时间线", "", JSON.stringify(task.steps || {}), "后端任务台账"].map(csvCell).join(","),
      [demoState.run.run_id, "__meta__", "knowledge_retrieval_trace", "知识检索轨迹", "", JSON.stringify(demoState.run.context?.knowledge_retrieval_trace || []), "来源、定位、快照与主张边界"].map(csvCell).join(","),
      [demoState.run.run_id, "__meta__", "model_attempt_history", "模型调用留痕", "", JSON.stringify(demoState.run.context?.model_attempt_history || []), "响应哈希、校验、失败码"].map(csvCell).join(","),
      [demoState.run.run_id, "__meta__", "source_coverage_summary", "来源覆盖摘要", "", JSON.stringify(demoState.run.context?.source_coverage_summary || {}), "代表性接入边界"].map(csvCell).join(","),
      [demoState.run.run_id, "__meta__", "assertion_evidence_procedure_matrix", "认定—证据—程序覆盖矩阵", "", JSON.stringify(demoState.run.context?.assertion_evidence_procedure_matrix || []), "覆盖状态与程序映射"].map(csvCell).join(","),
      [demoState.run.run_id, "__meta__", "evidence_fitness", "证据适配度与主张边界", "", JSON.stringify({ boundary: demoState.run.context?.evidence_fitness_boundary, violations: demoState.run.context?.evidence_fitness_violations || [] }), "来源类别限制主张范围"].map(csvCell).join(","),
      [demoState.run.run_id, "__meta__", "numeric_claim_trace", "数字主张回查", "", JSON.stringify(demoState.run.context?.numeric_claim_trace || {}), "原数字—来源—验证状态"].map(csvCell).join(","),
      [demoState.run.run_id, "__meta__", "anti_confirmation", "反确认偏差搜索", "", JSON.stringify(demoState.run.context?.anti_confirmation || {}), "反向问题、命中与正常解释"].map(csvCell).join(","),
      [run.run_id, "__meta__", "supplement_delta", "补充材料差异摘要", "", JSON.stringify(run.context?.supplement_delta || null), "新增证据、建议变化与原字段保护"].map(csvCell).join(","),
    ];
    downloadBlob(`${safeDownloadName(demoState.run.run_id)}-metrics.csv`, `\uFEFF${lines.join("\r\n")}`, "text/csv;charset=utf-8");
  }

  const LIVE_STEP_LABELS = {
    company_resolve: "确认企业与证券代码",
    announcement_search: "检索巨潮年报公告",
    document_select: "选择正式年度报告",
    download: "下载公开 PDF",
    document_validate: "校验来源、页数与哈希",
    case_register: "登记案例与来源台账",
    rag_prepare: "建立案例隔离 RAG",
    rag_smoke_test: "执行固定问题检索烟测",
    field_extract: "提取财务字段候选",
    field_validate: "校验字段与资料缺口",
    analysis_run: "执行规则与分析主链",
  };

  function liveStatusKind(status) {
    if (["failed", "cancelled"].includes(status)) return "danger";
    if (["needs_human"].includes(status)) return "waiting";
    if (["completed", "ready", "rag_ready", "ready_for_analysis"].includes(status)) return "success";
    return "pending";
  }

  function liveTaskIsActive(task) {
    if (!task) return false;
    return LIVE_ACTIVE_STATUSES.has(task.status)
      || (task.status === "ready_for_analysis" && task.request?.analysis_mode === "full_analysis");
  }

  function renderLiveTask(task) {
    demoState.liveSample.task = task;
    demoState.liveSample.taskId = task.task_id || demoState.liveSample.taskId;
    byId("demo-live-task").hidden = false;
    byId("demo-live-task-id").textContent = task.task_id || "—";
    const state = byId("demo-live-task-state");
    state.className = `state ${liveStatusKind(task.status)}`;
    state.textContent = statusLabel(task.status);
    byId("demo-live-submit").disabled = liveTaskIsActive(task) || !Boolean(demoState.bootstrap?.capabilities?.onsite_live_sample);
    const steps = byId("demo-live-steps");
    steps.replaceChildren();
    Object.entries(task.steps || {}).forEach(([name, step], index) => {
      const item = document.createElement("li");
      const stepStatus = step?.status || "pending";
      item.innerHTML = `<span>${String(index + 1).padStart(2, "0")}</span><div><strong>${escapeHtml(LIVE_STEP_LABELS[name] || name)}</strong><small>${escapeHtml(step?.detail || "等待执行")}</small></div><span class="state ${liveStatusKind(stepStatus)}">${escapeHtml(statusLabel(stepStatus))}</span>`;
      steps.append(item);
    });
    const message = byId("demo-live-message");
    const error = task.error || {};
    const reviewDetail = task.status === "needs_human" && task.result
      ? `自动处理已完成；${task.result.next_action?.label || "字段候选需要人工确认"}。这不是任务失败，正式采用前请回查年报页码与口径。`
      : "";
    const completionDetail = task.status === "completed"
      ? "现场处理已完成；结构化结果可下载，正式采用前仍需人工复核原文、页码与口径。"
      : "";
    message.className = `status-banner ${liveStatusKind(task.status) === "danger" ? "danger" : liveStatusKind(task.status) === "waiting" ? "warning" : liveStatusKind(task.status) === "success" ? "success" : "neutral"}`;
    message.innerHTML = `<strong>${escapeHtml(statusLabel(task.status))}</strong><span>${escapeHtml(error.message || reviewDetail || completionDetail || task.boundary || "正在处理真实公开样例；页面只展示后端返回的实际状态。")}</span>`;
    renderLiveResult(task);
  }

  function renderLiveResult(task) {
    const result = task.result;
    const container = byId("demo-live-result");
    const outputActions = byId("demo-live-output-actions");
    const tableWrap = byId("demo-live-table-wrap");
    const tableBody = byId("demo-live-structured-table-body");
    if (!result) {
      container.hidden = true;
      outputActions.hidden = true;
      tableWrap.hidden = true;
      tableBody.replaceChildren();
      return;
    }
    const company = result.company || task.company || {};
    const extraction = result.field_extraction || {};
    const rag = result.rag || {};
    const analysis = result.analysis || {};
    const structuredRows = structuredMetricRows(analysis);
    const hasStructuredAnalysis = Boolean(analysis.run_id) && structuredRows.length > 0;
    const reportYears = [...new Set([...(result.report_years || []), ...(result.documents || []).map((item) => item.report_year).filter(Boolean)])].sort((a, b) => Number(b) - Number(a));
    container.hidden = false;
    container.innerHTML = `<strong>${hasStructuredAnalysis ? "现场样例已形成可验证结构化结果" : "现场资料已就绪，分析主链仍在执行"}</strong><dl><div><dt>企业</dt><dd>${escapeHtml(company.company_name || "—")} · ${escapeHtml(company.ticker || "—")}</dd></div><div><dt>案例编号</dt><dd>${escapeHtml(result.case_id || task.case_id || "—")}</dd></div><div><dt>报告年度</dt><dd>${escapeHtml(reportYears.join(" / ") || "—")}</dd></div><div><dt>官方文档</dt><dd>${escapeHtml((result.documents || []).length)} 份</dd></div><div><dt>RAG</dt><dd>${escapeHtml(rag.status || "—")} · ${escapeHtml(rag.chunk_count ?? "—")} 块</dd></div><div><dt>字段提取</dt><dd>${escapeHtml(statusLabel(extraction.status || "—"))} · ${escapeHtml(extraction.row_count ?? "—")} 条</dd></div><div><dt>分析运行</dt><dd>${escapeHtml(analysis.run_id || "执行中")}</dd></div><div><dt>完整性</dt><dd>${escapeHtml(hasStructuredAnalysis ? statusLabel(analysis.run_completeness || "not_requested") : "等待分析终态")}</dd></div></dl><p>${escapeHtml(AI_GENERATED_CONTENT_NOTICE)}</p>`;
    tableBody.replaceChildren();
    if (hasStructuredAnalysis) {
      structuredRows.forEach((row) => {
        const tr = document.createElement("tr");
        [row.rule_id, row.metric_label, row.formatted_value, `${String(row.raw_value)} · ${row.basis}`].forEach((value) => {
          const td = document.createElement("td");
          td.textContent = value;
          tr.append(td);
        });
        tableBody.append(tr);
      });
    }
    tableWrap.hidden = !hasStructuredAnalysis;
    outputActions.hidden = !hasStructuredAnalysis;
  }

  async function pollLiveTask(taskId, token) {
    if (!taskId || token !== demoState.liveSample.pollToken) return;
    try {
      const response = await fetch(`${API_BASE}/api/pipelines/${encodeURIComponent(taskId)}`, { credentials: "include" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const task = await response.json();
      if (token !== demoState.liveSample.pollToken) return;
      renderLiveTask(task);
      if (liveTaskIsActive(task)) {
        demoState.liveSample.pollTimer = window.setTimeout(() => { void pollLiveTask(taskId, token); }, LIVE_POLL_INTERVAL_MS);
      } else {
        demoState.liveSample.pollTimer = null;
      }
    } catch (error) {
      if (token !== demoState.liveSample.pollToken) return;
      const message = byId("demo-live-message");
      message.className = "status-banner danger";
      message.innerHTML = `<strong>任务状态读取失败</strong><span>${escapeHtml(error.message)}；任务没有被页面删除。</span>`;
    }
  }

  async function startLiveSample(event) {
    event.preventDefault();
    if (demoState.liveSample.submitting) return;
    const form = event.currentTarget;
    const companyQuery = form.elements.company_query.value.trim();
    if (!companyQuery) return;
    demoState.liveSample.submitting = true;
    byId("demo-live-submit").disabled = true;
    byId("demo-live-task").hidden = false;
    byId("demo-live-message").className = "status-banner neutral";
    byId("demo-live-message").innerHTML = "<strong>正在创建真实任务</strong><span>不会生成模拟进度。</span>";
    try {
      const latest = form.elements.latest_year.value.trim();
      const response = await fetch(`${API_BASE}/api/pipelines/cninfo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ company_query: companyQuery, years: Number(form.elements.years.value), latest_year: latest ? Number(latest) : null, analysis_mode: "full_analysis", rule_ids: ["R1"], force_refresh: false, cache_policy: "prefer_cache", planned_materiality: null }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      renderLiveTask(payload);
      demoState.liveSample.pollToken += 1;
      void pollLiveTask(payload.task_id, demoState.liveSample.pollToken);
    } catch (error) {
      const message = byId("demo-live-message");
      message.className = "status-banner danger";
      message.innerHTML = `<strong>现场样例任务未创建</strong><span>${escapeHtml(error.message)}。共享站只读时，请切换到团队本机现场模式。</span>`;
    } finally {
      demoState.liveSample.submitting = false;
      const active = liveTaskIsActive(demoState.liveSample.task);
      byId("demo-live-submit").disabled = active || !Boolean(demoState.bootstrap?.capabilities?.onsite_live_sample);
    }
  }

  function downloadLiveSampleJson() {
    const task = demoState.liveSample.task;
    if (!task?.result) return;
    const analysis = task.result.analysis || {};
    downloadBlob(`${safeDownloadName(task.task_id)}-sample.json`, JSON.stringify({
      schema_version: "audittrace_live_sample_export_v1",
      exported_at: new Date().toISOString(),
      ai_generated_content_notice: AI_GENERATED_CONTENT_NOTICE,
      task,
      knowledge_retrieval_trace: analysis.context?.knowledge_retrieval_trace || [],
      knowledge_source_ledger: analysis.context?.knowledge_source_ledger || [],
      model_attempt_history: analysis.context?.model_attempt_history || [],
      source_coverage_summary: analysis.context?.source_coverage_summary,
      assertion_evidence_procedure_matrix: analysis.context?.assertion_evidence_procedure_matrix || [],
      evidence_fitness_boundary: analysis.context?.evidence_fitness_boundary,
      evidence_fitness_violations: analysis.context?.evidence_fitness_violations || [],
      numeric_claim_trace: analysis.context?.numeric_claim_trace || {},
      anti_confirmation: analysis.context?.anti_confirmation || {},
    }, null, 2), "application/json;charset=utf-8");
  }

  function downloadLiveSampleCsv() {
    const task = demoState.liveSample.task;
    if (!task?.result) return;
    const analysis = task.result.analysis || {};
    const rows = structuredMetricRows(analysis);
    const lines = [
      ["task_id", "run_id", "case_id", "rule_id", "metric_key", "metric_label", "formatted_value", "raw_value", "basis"].map(csvCell).join(","),
      ...rows.map((row) => [task.task_id, analysis.run_id || "", task.result.case_id || task.case_id || "", row.rule_id, row.metric_key, row.metric_label, row.formatted_value, row.raw_value, row.basis].map(csvCell).join(",")),
      [task.task_id, analysis.run_id || "", task.result.case_id || task.case_id || "", "__meta__", "knowledge_retrieval_trace", "知识检索轨迹", "", JSON.stringify(analysis.context?.knowledge_retrieval_trace || []), "来源、定位、快照与主张边界"].map(csvCell).join(","),
      [task.task_id, analysis.run_id || "", task.result.case_id || task.case_id || "", "__meta__", "model_attempt_history", "模型调用留痕", "", JSON.stringify(analysis.context?.model_attempt_history || []), "响应哈希、校验、失败码"].map(csvCell).join(","),
      [task.task_id, analysis.run_id || "", task.result.case_id || task.case_id || "", "__meta__", "source_coverage_summary", "来源覆盖摘要", "", JSON.stringify(analysis.context?.source_coverage_summary || {}), "代表性接入边界"].map(csvCell).join(","),
      [task.task_id, analysis.run_id || "", task.result.case_id || task.case_id || "", "__meta__", "assertion_evidence_procedure_matrix", "认定—证据—程序覆盖矩阵", "", JSON.stringify(analysis.context?.assertion_evidence_procedure_matrix || []), "覆盖状态与程序映射"].map(csvCell).join(","),
      [task.task_id, analysis.run_id || "", task.result.case_id || task.case_id || "", "__meta__", "numeric_claim_trace", "数字主张回查", "", JSON.stringify(analysis.context?.numeric_claim_trace || {}), "原数字—来源—验证状态"].map(csvCell).join(","),
      [task.task_id, analysis.run_id || "", task.result.case_id || task.case_id || "", "__meta__", "anti_confirmation", "反确认偏差搜索", "", JSON.stringify(analysis.context?.anti_confirmation || {}), "反向问题、命中与正常解释"].map(csvCell).join(","),
    ];
    downloadBlob(`${safeDownloadName(task.task_id)}-metrics.csv`, `\uFEFF${lines.join("\r\n")}`, "text/csv;charset=utf-8");
  }

  function printLiveSampleReport() {
    if (!demoState.liveSample.task?.result) return;
    document.body.classList.add("print-live-sample");
    const clear = () => document.body.classList.remove("print-live-sample");
    window.addEventListener("afterprint", clear, { once: true });
    window.print();
    window.setTimeout(clear, 2000);
  }

  function resetDemo() {
    abortActiveRun();
    demoState.run = null;
    demoState.outcome = null;
    demoState.taskCreationBlocked = false;
    clearResultDisplay();
    resetStageRail();
    renderCurrentCase();
    setPhase("ready");
    setGate("neutral", "演示已重置", "案例选择保留；点击“开始审计预筛”重新运行。服务器上的运行与证据记录不会被删除。");
  }

  function closeDrawer(id) {
    const dialog = document.getElementById(id);
    if (dialog?.open) dialog.close();
  }

  async function loadTechEvaluation() {
    if (demoState.techEvaluated) return;
    demoState.techEvaluated = true;
    try {
      const response = await fetch(`${API_BASE}/api/evaluations/current`, { credentials: "include" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      const label = statusLabel(payload.status);
      const cases = payload.cases?.length ?? 0;
      byId("demo-tech-evaluation").textContent = `冻结评估 ${payload.evaluation_id || "—"} · ${label} · 覆盖 ${cases} 个案例的 B0—B3 对照；专业评分由真人完成后才会更新，页面只显示真实进度。`;
    } catch (_error) {
      byId("demo-tech-evaluation").textContent = "冻结评估摘要暂时不可读取；评分状态以验收记录为准，不在页面伪造。";
    }
  }

  async function loadBootstrap() {
    try {
      const response = await fetch(`${API_BASE}/api/demo/bootstrap`, { credentials: "include" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const bootstrap = await response.json();
      if (!bootstrap.bootstrap_ready) {
        setServiceStatus("演示资源未就绪", "danger");
        setGate("danger", "演示资源未就绪", `原因码：${bootstrap.bootstrap_reason_code || "unknown"}；请重启服务或恢复演示包后再试。`);
        setPhase("failed_run");
        return;
      }
      demoState.bootstrap = bootstrap;
      demoState.cases = bootstrap.cases || [];
      demoState.caseIndex = new Map(demoState.cases.map((item) => [item.case_id, item]));
      const urlCase = new URLSearchParams(window.location.search).get("case");
      const storedCase = safeStorageGet(CASE_STORAGE_KEY);
      const preferred = demoState.cases.some((item) => item.case_id === urlCase)
        ? urlCase
        : demoState.cases.some((item) => item.case_id === storedCase)
          ? storedCase
          : bootstrap.featured_case_ids[0];
      demoState.caseId = preferred || null;
      renderFacts();
      notifyModelQuality(bootstrap.model_quality);
      renderTechVersions();
      renderKnowledgeBase();
      renderProcedureMap();
      renderCurrentCase();
      renderFeaturedCases();
      renderAllCasesDrawer();
      updateUrl();
      const readiness = bootstrap.model_readiness || {};
      const continuity = bootstrap.task_continuity || {};
      const taskStoreReady = continuity.availability ? continuity.availability === "ready" : true;
      if (taskStoreReady) demoState.taskCreationBlocked = false;
      if (!taskStoreReady) {
        setServiceStatus("后端可用 · 任务台账不可用", "danger");
      } else if (readiness.full_analysis_ready) {
        setServiceStatus("后端可用 · 任务台账可用 · 真实模型可运行", "success");
      } else {
        setServiceStatus("后端可用 · 任务台账可用 · 模型降级可用", "pending");
      }
      const featuredReady = bootstrap.featured_case_ids.every((id) => demoState.caseIndex.get(id)?.rag?.status === "ready");
      const release = bootstrap.release || {};
      const releaseBoundary = release.competition_release_ready
        ? "当前发布事实已通过自动门禁；正式发布仍以最终人工批准为准。"
        : `发布候选尚未完全放行（${release.release_status || "remediation_in_progress"}）；页面不会把历史评估或配置状态写成正式通过。`;
      if (!taskStoreReady) {
        setGate("warning", "正式任务台账暂不可用", `${continuity.boundary || "Supabase 演示任务台账暂不可读取。"} ${readiness.deterministic_backup_available ? "可以选择“启动确定性备用演示”继续展示完整流程。" : "请先恢复任务台账配置。"}`);
      } else if (!featuredReady) {
        setGate("warning", "部分精选案例 RAG 未就绪", "演示可以继续，但该案例运行会如实显示证据读取状态；团队需重建索引后重验。");
      } else {
        setGate("neutral", "演示就绪", `已选择 ${currentCase()?.company_name || "默认案例"}；点击“开始审计预筛”创建一次真实运行。${readiness.full_analysis_ready ? "" : "当前模型通道未就绪，运行会显示明确降级状态。"} ${releaseBoundary}`);
      }
      setPhase("ready");
    } catch (error) {
      setServiceStatus("本地后端不可用", "danger");
      setGate("danger", "未连接到 FastAPI", `无法读取演示启动快照：${error.message}；页面不会模拟任何结果。`);
      setPhase("failed_run");
    }
  }

  function bindEvents() {
    byId("demo-start").addEventListener("click", () => { void startDemoRun(); });
    byId("demo-backup").addEventListener("click", () => { void startDemoRun({ backup: true }); });
    byId("demo-recheck").addEventListener("click", () => { void loadBootstrap(); });
    byId("demo-cancel").addEventListener("click", () => { void requestDemoCancel(); });
    byId("demo-reset").addEventListener("click", resetDemo);
    byId("demo-rerun").addEventListener("click", () => { resetDemo(); void startDemoRun(); });
    byId("demo-open-all-cases").addEventListener("click", () => { byId("demo-cases-drawer").showModal(); });
    byId("demo-open-evidence").addEventListener("click", () => { byId("demo-evidence-drawer").showModal(); });
    byId("demo-open-agents").addEventListener("click", () => { byId("demo-agent-drawer").showModal(); });
    byId("demo-supplement-rerun").addEventListener("click", () => {
      byId("demo-supplement-drawer").showModal();
      byId("demo-supplement-apply").disabled = true;
      void loadSupplementSamples();
    });
    byId("demo-supplement-apply").addEventListener("click", () => { void startSupplementRerun(); });
    byId("demo-download-json").addEventListener("click", downloadRunJson);
    byId("demo-download-csv").addEventListener("click", downloadRunCsv);
    byId("demo-print-report").addEventListener("click", () => window.print());
    byId("demo-positioning-boundary").addEventListener("click", () => {
      byId("demo-tech-drawer").showModal();
      void loadTechEvaluation();
    });
    byId("demo-open-live-sample").addEventListener("click", () => { byId("demo-live-sample-drawer").showModal(); });
    byId("demo-live-sample-form").addEventListener("submit", (event) => { void startLiveSample(event); });
    byId("demo-live-download-json").addEventListener("click", downloadLiveSampleJson);
    byId("demo-live-download-csv").addEventListener("click", downloadLiveSampleCsv);
    byId("demo-live-print-report").addEventListener("click", printLiveSampleReport);
    byId("demo-open-tech-drawer").addEventListener("click", () => {
      byId("demo-tech-drawer").showModal();
      void loadTechEvaluation();
    });
    document.querySelectorAll("[data-demo-close]").forEach((button) => {
      button.addEventListener("click", () => {
        const dialog = button.closest("dialog");
        if (dialog?.open) dialog.close();
      });
    });
    ["demo-cases-drawer", "demo-evidence-drawer", "demo-agent-drawer", "demo-tech-drawer", "demo-live-sample-drawer", "demo-supplement-drawer"].forEach((id) => {
      const dialog = document.getElementById(id);
      dialog?.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    });
    window.addEventListener("popstate", () => {
      const requested = new URLSearchParams(window.location.search).get("case");
      if (demoState.phase === "running") {
        // 运行中历史切换不能让旧 task 的结果覆盖当前案例；把 URL 校正回任务案例。
        updateUrl({ replace: true });
        showToast("当前任务执行中，暂不能切换案例；请等待终态或取消。", "warning");
        return;
      }
      selectDemoCase(requested || demoState.bootstrap?.featured_case_ids?.[0], { fromHistory: true });
    });
  }

  async function initialize() {
    bindEvents();
    renderControls();
    await loadBootstrap();
    await restoreFixedTaskSession();
  }

  initialize();
}());
