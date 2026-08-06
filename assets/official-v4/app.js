(function () {
  "use strict";

  const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
  const AI_GENERATED_CONTENT_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。";
  const REVIEW_KEY = "audittrace_review_v2";
  const SCOPE_KEY = "audittrace_rule_scope_v2";
  const VIEW_IDS = ["overview", "project", "rules", "analysis", "rag", "supplement", "delivery", "methods"];
  const LEGACY_VIEW_MAP = { project: "project", data: "project", risk: "analysis", library: "rules", rag: "rag", supplement: "supplement", delivery: "delivery" };
  const UNIT_MAP = {
    yuan: { label: "元", factor: 1 },
    thousand: { label: "千元", factor: 1000 },
    "ten-thousand": { label: "万元", factor: 10000 },
    million: { label: "百万元", factor: 1000000 },
  };
  const FIELD_KIND_LABELS = {
    revenue: "营业收入",
    accounts_receivable: "应收账款",
    accounts_receivable_allowance: "应收账款坏账准备",
    accounts_receivable_net: "应收账款净额",
    operating_cash_flow: "经营活动现金流量净额",
    net_profit: "净利润",
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
    materiality_multiple: "相对计划重要性倍数",
    materiality_assessment: "金额重要性评价",
    three_year_trend_available: "三年趋势可评价",
    operating_cash_flow_growth: "经营活动现金流增速",
    cashflow_to_revenue_current: "本年经营现金流 / 收入",
    cashflow_to_revenue_previous: "上年经营现金流 / 收入",
    net_profit_cashflow_gap: "净利润—经营现金流差异",
  };
  const STATUS_LABELS = {
    candidate: "程序候选",
    RULE_NOT_TRIGGERED: "程序未触发",
    DATA_NOT_COMPARABLE: "同比不宜比较",
    DATA_GAP: "资料不足",
    SOURCE_INCOMPLETE: "来源未通过",
    retain: "建议保留",
    downgrade: "建议降级",
    defer: "建议暂缓",
    not_generated: "未形成AI建议",
    complete_full_analysis: "完整分析已完成",
    complete_full_analysis_no_candidate: "完整分析完成，无程序候选",
    incomplete_calculation_only: "不完整：仅计算预检",
    incomplete_model_chain_failed: "不完整：模型链未完成",
    incomplete_rag_failure: "不完整：RAG失败",
    incomplete_model_transfer_not_allowed: "不完整：禁止模型传输",
    cache_replay_not_fresh_analysis: "缓存回放，非新分析",
    model_success: "三Agent已通过硬校验",
    config_missing: "模型配置缺失",
    provider_unreachable: "模型调用失败",
    MODEL_OUTPUT_INVALID: "模型输出校验失败",
    not_requested: "仅计算，未请求模型",
    not_applicable: "本次不适用",
    model_transfer_not_allowed: "模型传输未获许可",
    not_attempted_rag_failure: "RAG失败，模型未调用",
    cache_replay: "批准缓存回放",
  };
  const CNINFO_STEP_LABELS = {
    company_resolve: "确认企业",
    announcement_search: "搜索年报公告",
    document_select: "选择全文版本",
    download: "下载 PDF 原件",
    document_validate: "校验来源与 PDF",
    case_register: "登记独立案例",
    rag_prepare: "建立案例 RAG",
    rag_smoke_test: "执行 RAG 烟测",
    field_extract: "提取字段候选",
    field_validate: "校验字段闸门",
    analysis_run: "进入分析 API",
  };
  const CNINFO_STEP_ORDER = Object.keys(CNINFO_STEP_LABELS);
  const CNINFO_ACTIVE_STATUSES = new Set(["queued", "searching", "downloading", "validating", "indexing", "extracting_fields", "analyzing"]);
  const RULES = [
    { id: "R1", name: "应收—收入背离", detail: "计算增速差、绝对影响、应收占收入、周转趋势、持续期间和重要性；净额只能过渡使用。", meta: "r1_v0.4-draft / 待A专业签字", status: "主链可运行", runnable: true },
    { id: "R2", name: "收入—经营现金流辅助筛查", detail: "跨期变号或基数过小时阻断伪同比；默认不抢占 R1 主演示。", meta: "r2_v0.2-auxiliary-draft", status: "辅助工程规则", runnable: true },
    { id: "R3", name: "产销量—收入不匹配", detail: "待产品、期间与合并范围可比资料。", meta: "后续路线图", status: "未接入", runnable: false },
    { id: "R4", name: "客户集中度与交易特征变化", detail: "待客户披露与合法登记资料。", meta: "后续路线图", status: "未接入", runnable: false },
    { id: "R5", name: "总额法 / 净额法判断依据", detail: "待合同和收入政策资料。", meta: "后续路线图", status: "未接入", runnable: false },
    { id: "R6", name: "毛利率逆行业变化", detail: "待可比同行与成本资料。", meta: "后续路线图", status: "未接入", runnable: false },
    { id: "R7", name: "管理层表述与数字一致性", detail: "待披露切片与专业复核。", meta: "后续路线图", status: "未接入", runnable: false },
    { id: "R8", name: "年末 / 第四季度收入集中", detail: "待分季度与期后资料。", meta: "后续路线图", status: "未接入", runnable: false },
  ];

  const state = {
    view: "overview",
    requestedCase: null,
    caseId: null,
    cases: [],
    currentCase: null,
    year: null,
    unit: "yuan",
    selectedRules: ["R1"],
    projectStatus: null,
    run: null,
    humanReview: null,
    backendAvailable: false,
    ragStatus: null,
    ragResults: [],
    supplementId: null,
    cninfoTask: null,
    cninfoPollTimer: null,
    cninfoPollToken: 0,
  };

  function byId(id) { return document.getElementById(id); }
  function escapeHtml(value) {
    return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
  function statusLabel(value) { return STATUS_LABELS[value] || value || "—"; }
  function aiNotice(value) { return value?.ai_generated_content_notice || AI_GENERATED_CONTENT_NOTICE; }
  function statusKind(value) {
    if (["complete_full_analysis", "complete_full_analysis_no_candidate", "model_success", "retain"].includes(value)) return "success";
    if (["SOURCE_INCOMPLETE", "provider_unreachable", "MODEL_OUTPUT_INVALID", "not_attempted_rag_failure"].includes(value)) return "danger";
    if (["candidate", "downgrade", "defer"].includes(value) || String(value || "").startsWith("incomplete")) return "waiting";
    return "info";
  }
  function setStatePill(element, text, kind) {
    if (!element) return;
    element.textContent = text;
    element.className = `state ${kind}`;
  }
  function setServiceStatus(text, kind) {
    if (!byId("service-pill")) return;
    byId("service-status").textContent = text;
    byId("service-pill").className = `service-pill ${kind}`;
  }
  function showMessage(element, text, kind = "") {
    if (!element) return;
    element.textContent = text;
    element.className = `form-message${kind ? ` ${kind}` : ""}`;
  }
  function beginButtonBusy(button, loadingText) {
    const original = button.textContent;
    const disabled = button.disabled;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.textContent = loadingText;
    return () => { button.textContent = original; button.disabled = disabled; button.removeAttribute("aria-busy"); };
  }
  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, options);
    const type = response.headers.get("content-type") || "";
    const body = type.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) throw new Error((body && typeof body === "object" ? body.detail : body) || `HTTP ${response.status}`);
    return body;
  }
  function safeLocalStorageGet(key, fallback) {
    try { return JSON.parse(window.localStorage.getItem(key) || "null") ?? fallback; } catch (_error) { return fallback; }
  }
  function safeLocalStorageSet(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (_error) { /* current session still works */ }
  }

  function readUrlState() {
    const params = new URLSearchParams(window.location.search);
    const view = params.get("view");
    const rules = (params.get("rules") || "").split(",").filter(Boolean);
    if (VIEW_IDS.includes(view)) state.view = view;
    if (rules.length) {
      const valid = rules.filter((id) => RULES.some((rule) => rule.id === id && rule.runnable));
      if (valid.length) state.selectedRules = valid;
    }
    state.requestedCase = params.get("case");
    state.year = params.get("year");
    return params.get("run");
  }
  function updateUrl(mode = "replace") {
    const url = new URL(window.location.href);
    url.searchParams.set("view", state.view);
    if (state.caseId) url.searchParams.set("case", state.caseId);
    if (state.year) url.searchParams.set("year", state.year);
    url.searchParams.set("rules", state.selectedRules.join(","));
    if (state.run?.run_id) url.searchParams.set("run", state.run.run_id); else url.searchParams.delete("run");
    window.history[mode === "push" ? "pushState" : "replaceState"]({}, "", url);
  }
  function syncMobileNavigationAccessibility(open = false) {
    const sidebar = byId("primary-navigation");
    const toggle = byId("mobile-nav-toggle");
    const mobile = window.matchMedia("(max-width: 1024px)").matches;
    sidebar.inert = mobile && !open;
    if (!mobile) { sidebar.classList.remove("open"); toggle.setAttribute("aria-expanded", "false"); }
  }
  function closeMobileNavigation() {
    byId("primary-navigation").classList.remove("open");
    byId("mobile-nav-toggle").setAttribute("aria-expanded", "false");
    syncMobileNavigationAccessibility(false);
  }
  function showView(view, options = {}) {
    if (!VIEW_IDS.includes(view)) view = "overview";
    state.view = view;
    document.querySelectorAll("[data-view-panel]").forEach((panel) => {
      const active = panel.dataset.viewPanel === view;
      panel.hidden = !active;
      panel.classList.toggle("active", active);
    });
    document.querySelectorAll("#primary-navigation [data-view]").forEach((link) => {
      if (link.dataset.view === view) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
    });
    closeMobileNavigation();
    if (options.history !== false) updateUrl(options.replace ? "replace" : "push");
    if (options.focus !== false) {
      byId("main-content").focus({ preventScroll: true });
      const top = byId("fusion-landing")?.offsetHeight || byId("workspace-root")?.offsetTop || 0;
      window.scrollTo({ top, behavior: "auto" });
    }
  }
  function handleLegacyStep(step) {
    showView(LEGACY_VIEW_MAP[step] || "project");
    document.querySelectorAll("[data-wb-step]").forEach((button) => button.setAttribute("aria-selected", button.dataset.wbStep === step ? "true" : "false"));
    if (step === "data") window.requestAnimationFrame(() => byId("source-ledger")?.scrollIntoView({ block: "start" }));
  }

  function unitKeyForLabel(label) {
    return Object.keys(UNIT_MAP).find((key) => UNIT_MAP[key].label === label) || "yuan";
  }
  function formatAmount(value) {
    const baseLabel = state.currentCase?.amount_unit || "元";
    const baseFactor = Object.values(UNIT_MAP).find((item) => item.label === baseLabel)?.factor || 1;
    const target = UNIT_MAP[state.unit] || UNIT_MAP.yuan;
    return new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value) * baseFactor / target.factor);
  }
  function formatPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return new Intl.NumberFormat("zh-CN", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value));
  }
  function metricValue(key, value) {
    if (value === null || value === undefined) return "—";
    if (["revenue_growth", "ar_growth", "growth_gap", "ar_to_revenue_current", "ar_to_revenue_previous", "operating_cash_flow_growth", "cashflow_to_revenue_current", "cashflow_to_revenue_previous", "net_profit_cashflow_gap"].includes(key)) {
      return key === "growth_gap" ? `${(Number(value) * 100).toFixed(2)} 个百分点` : formatPercent(value);
    }
    if (key === "absolute_ar_change") return `${formatAmount(value)} ${UNIT_MAP[state.unit].label}`;
    if (["turnover_days_current", "turnover_days_previous", "turnover_trend_days"].includes(key)) return `${Number(value).toFixed(2)} 天`;
    if (key === "sustained_periods") return `${value} 期`;
    if (key === "materiality_multiple") return `${Number(value).toFixed(2)}×`;
    if (typeof value === "boolean") return value ? "是" : "否";
    return String(value);
  }
  function metricFormula(key) {
    const formulas = {
      revenue_growth: "（本年收入−上年收入）/上年收入",
      ar_growth: "（本年应收−上年应收）/上年应收",
      growth_gap: "应收增速−收入增速（R2为收入−现金流）",
      absolute_ar_change: "本年应收−上年应收",
      ar_to_revenue_current: "本年应收/本年收入",
      ar_to_revenue_previous: "上年应收/上年收入",
      turnover_days_current: "平均应收/本年收入×365",
      turnover_days_previous: "需第三年期初应收",
      turnover_trend_days: "本年周转天数−上年周转天数",
      sustained_periods: "连续达到草案阈值的期间",
      materiality_multiple: "绝对应收变动/计划重要性",
    };
    return formulas[key] || "程序结构化返回";
  }

  function renderHeroStatus() {
    const status = state.projectStatus || {};
    const current = state.currentCase;
    const sourceResult = status.tests?.source_repository?.latest_result || status.tests?.source_repository?.expected_result_after_package_build || "—";
    const cleanResult = status.tests?.clean_package?.latest_result || status.tests?.clean_package?.expected_result || "—";
    const sourceCount = String(sourceResult).match(/\d+(?=\s+passed)/)?.[0] || "—";
    const cleanCount = String(cleanResult).match(/\d+(?=\s+passed)/)?.[0] || "—";
    const livePassed = status.live_model_acceptance?.result === "model_success"
      && status.live_model_acceptance?.run_completeness === "complete_full_analysis";
    byId("hero-version").textContent = `${status.engine_version || "0.7.1"} · 正式 DEV`;
    byId("hero-case").textContent = current?.case_id || "NO CASE";
    byId("hero-source-count").textContent = `${current?.documents?.length || 0} REGISTERED SOURCES`;
    byId("hero-chunk-count").textContent = `${status.rag?.chunk_count || 0} SOURCE CHUNKS`;
    byId("fact-case-count").textContent = status.case_count ?? state.cases.length ?? "—";
    byId("fact-chunk-count").textContent = status.rag?.chunk_count ?? "—";
    byId("fact-engine-version").textContent = status.engine_version || "0.7.1";
    byId("fact-model-status").textContent = status.model?.status === "configured"
      ? (livePassed ? "模型已配置 · 真实三Agent技术通过" : "模型已配置 · 完整链待验收")
      : "模型未配置";
    byId("fact-test-counts").textContent = `${sourceCount} / ${cleanCount}`;
    byId("fact-test-note").textContent = livePassed ? "passed · 三Agent技术通过" : "passed · 模型链状态见验收记录";
    byId("sidebar-model").textContent = status.model?.status === "configured" ? "已配置 / 按次验收" : "未配置";
  }

  function caseRowLabel(row) {
    const basis = row.field_kind === "accounts_receivable"
      ? (row.field_basis === "gross" ? "账面余额" : "净额/列示额")
      : row.field_kind === "accounts_receivable_allowance"
        ? "坏账准备"
        : row.field_kind === "accounts_receivable_net"
          ? "净额"
          : row.statement_scope;
    return `${FIELD_KIND_LABELS[row.field_kind] || row.field_kind} · ${basis || "口径待核验"}`;
  }
  function sourceUrl(documentId, page) {
    return `${API_BASE}/api/cases/${encodeURIComponent(state.caseId)}/sources/${encodeURIComponent(documentId)}#page=${encodeURIComponent(page || 1)}`;
  }
  function rowsForCurrentPeriod() {
    if (!state.currentCase || !state.year) return [];
    const year = Number(state.year);
    return (state.currentCase.financial_fields || []).filter((row) => [year, year - 1, year - 2].includes(Number(row.year)));
  }
  function cninfoHumanReviewLabel(row) {
    const status = row.human_review?.status || "pending";
    return { confirmed: "已确认", corrected: "已修正", rejected: "已拒绝", pending: "待确认" }[status] || status;
  }
  function renderCninfoFieldReview() {
    const panel = byId("cninfo-field-review");
    if (!panel || state.currentCase?.registry_mode !== "cninfo_official_auto") {
      if (panel) panel.hidden = true;
      return;
    }
    panel.hidden = false;
    const rows = state.currentCase.financial_fields || [];
    const accepted = rows.filter((row) => ["confirmed", "corrected"].includes(row.human_review?.status)).length;
    const rejected = rows.filter((row) => row.human_review?.status === "rejected").length;
    const pending = rows.length - accepted - rejected;
    setStatePill(byId("cninfo-field-review-state"), `${accepted}/${rows.length} 已处理 · ${pending} 待确认`, accepted && !pending && !rejected ? "success" : "waiting");
    byId("cninfo-field-review-list").innerHTML = rows.length ? rows.map((row) => {
      const fieldId = row.field_id || `${row.field_kind}_${row.year}`;
      const status = row.human_review?.status || "pending";
      const source = row.document_id && row.pdf_page ? `<a class="source-link" href="${sourceUrl(row.document_id, row.pdf_page)}" target="_blank" rel="noopener">打开原件第 ${escapeHtml(row.pdf_page)} 页 ↗</a>` : "来源页待补";
      return `<article class="cninfo-field-record ${status === "rejected" ? "rejected" : status !== "pending" ? "reviewed" : "pending"}" data-cninfo-field-record="${escapeHtml(fieldId)}"><div class="cninfo-field-record-head"><div><span class="folio">${escapeHtml(fieldId)}</span><h4>${escapeHtml(FIELD_KIND_LABELS[row.field_kind] || row.field_kind)} · ${escapeHtml(row.year)}</h4><p>${escapeHtml(row.statement_scope || "合并")} · ${escapeHtml(row.field_basis || "口径待核验")} · ${escapeHtml(row.unit || "单位待核验")}</p></div><span class="state ${status === "rejected" ? "danger" : status === "pending" ? "waiting" : "success"}">${escapeHtml(cninfoHumanReviewLabel(row))}</span></div><div class="cninfo-field-evidence"><div><span>自动候选金额（元）</span><strong class="mono">${escapeHtml(row.candidate?.value ?? row.value ?? "—")}</strong></div><div><span>当前规则输入金额（元）</span><input class="cninfo-field-value-input" type="number" step="any" value="${escapeHtml(row.value ?? "")}" aria-label="${escapeHtml(fieldId)} 当前金额"></div><div><span>当前 PDF 页码</span><input class="cninfo-field-page-input" type="number" min="1" step="1" value="${escapeHtml(row.pdf_page ?? "")}" aria-label="${escapeHtml(fieldId)} PDF页码"></div><div><span>定位</span><p>${escapeHtml(row.locator || row.candidate?.locator || "—")}</p>${source}</div></div><div class="cninfo-field-record-actions"><button class="button quiet" type="button" data-cninfo-field-action="confirm" data-field-id="${escapeHtml(fieldId)}">确认候选</button><button class="button quiet" type="button" data-cninfo-field-action="correct" data-field-id="${escapeHtml(fieldId)}">按上方金额修正</button><button class="button quiet" type="button" data-cninfo-field-action="reject" data-field-id="${escapeHtml(fieldId)}">拒绝候选</button></div></article>`;
    }).join("") : '<div class="empty-state compact"><strong>尚未形成字段候选</strong><p>请先执行 full_analysis 模式的巨潮流程；rag_only 只建立 RAG，不猜测财务金额。</p></div>';
  }
  function renderProject() {
    const current = state.currentCase;
    byId("wb-case").innerHTML = state.cases.map((item) => `<option value="${escapeHtml(item.case_id)}">${escapeHtml(item.company_alias || item.company_name)} · ${escapeHtml(item.case_id)}</option>`).join("");
    if (!current) {
      byId("wb-data-body").innerHTML = '<tr><td colspan="5">没有可用案例。</td></tr>';
      return;
    }
    byId("wb-case").value = current.case_id;
    byId("wb-company").textContent = current.company_name;
    byId("wb-ticker").textContent = current.ticker || "不适用";
    byId("wb-t0").textContent = current.t0;
    byId("wb-rag-t0").textContent = current.t0;
    byId("wb-sup-date").value = current.t0;
    byId("sidebar-case").textContent = current.case_id;
    byId("wb-case-mode").textContent = `${current.sample_type} / ${current.registry_mode}`;
    byId("wb-case-permission").textContent = current.model_transfer_allowed ? "允许本次证据包进入已配置模型；仍按运行状态验收。" : "manifest 禁止模型传输，只能本地预检。";
    const years = (current.available_years || []).map(String);
    if (!years.includes(String(state.year))) state.year = years[0] || null;
    byId("wb-current-year").innerHTML = years.map((year) => `<option value="${year}">${year}</option>`).join("");
    if (state.year) byId("wb-current-year").value = state.year;
    byId("wb-previous-year").textContent = state.year ? String(Number(state.year) - 1) : "—";
    state.unit = state.unit || unitKeyForLabel(current.amount_unit);
    byId("wb-amount-unit").value = state.unit;
    const unit = UNIT_MAP[state.unit];
    byId("wb-amount-head").textContent = `数值（${unit.label}）`;
    byId("wb-data-unit-note").textContent = `案例原始单位：${current.amount_unit}；显示单位：${unit.label}。页面只读取注册字段，不从PDF猜数字。${current.field_validation?.boundary || ""}`;
    const rows = rowsForCurrentPeriod();
    byId("wb-data-status").textContent = `${rows.length} 条字段 · ${current.field_validation?.status || "待校验"}`;
    byId("wb-data-status").className = "state success";
    byId("wb-data-body").innerHTML = rows.map((row) => `
      <tr>
        <td>${escapeHtml(caseRowLabel(row))}</td>
        <td class="mono">${escapeHtml(row.year)}</td>
        <td class="numeric mono">${escapeHtml(formatAmount(row.value))}</td>
        <td><span class="source-id">${escapeHtml(row.evidence_id)}</span><div class="source-detail">${escapeHtml(row.document_id)}</div></td>
        <td><strong>${escapeHtml(row.source_file)}</strong><div class="source-detail">披露 ${escapeHtml(row.disclosure_date)} · PDF ${escapeHtml(row.pdf_page)} 页 · ${escapeHtml(row.locator)}</div><a class="source-link" href="${sourceUrl(row.document_id, row.pdf_page)}" target="_blank" rel="noopener">回到登记 PDF 第 ${escapeHtml(row.pdf_page)} 页</a></td>
      </tr>`).join("") || '<tr><td colspan="5">该期间没有可预览字段。</td></tr>';
    renderCninfoFieldReview();
    setStatePill(byId("project-state"), `${current.case_id} 已载入`, "info");
    renderHeroStatus();
  }

  async function loadCaseDetail(caseId, options = {}) {
    const normalized = String(caseId || "").toUpperCase();
    if (!normalized) return;
    setStatePill(byId("project-state"), "正在读取案例字段", "pending");
    try {
      state.currentCase = await api(`/api/cases/${encodeURIComponent(normalized)}`);
      state.caseId = state.currentCase.case_id;
      const requestedYear = options.keepYear ? state.year : null;
      const years = (state.currentCase.available_years || []).map(String);
      state.year = requestedYear && years.includes(String(requestedYear)) ? String(requestedYear) : years[0] || null;
      state.unit = unitKeyForLabel(state.currentCase.amount_unit);
      state.run = null;
      state.ragResults = [];
      renderProject();
      renderRuleLibrary();
      await checkRagStatus();
      updateUrl("replace");
    } catch (error) {
      setStatePill(byId("project-state"), "案例读取失败", "danger");
      showMessage(byId("case-import-message"), `案例读取失败：${error.message}`, "error");
    }
  }
  async function loadSystemAndCases() {
    const [status, listing] = await Promise.all([api("/api/status"), api("/api/cases")]);
    state.projectStatus = status;
    state.cases = listing.cases || [];
    const preferred = state.cases.some((item) => item.case_id === state.requestedCase) ? state.requestedCase : state.cases[0]?.case_id;
    await loadCaseDetail(preferred, { keepYear: true });
  }

  function cninfoTaskStatusLabel(value) {
    const labels = {
      queued: "已排队",
      searching: "正在搜索巨潮",
      downloading: "正在下载年报",
      validating: "正在校验 PDF",
      indexing: "正在建立 RAG",
      extracting_fields: "正在提取字段候选",
      analyzing: "正在调用分析 API",
      completed: "流程完成",
      needs_human: "需要真人处理",
      failed: "流程失败",
    };
    return labels[value] || value || "等待提交";
  }
  function cninfoStepStatusLabel(value) {
    return { pending: "等待", running: "进行中", passed: "已通过", needs_human: "待人工", failed: "失败" }[value] || value || "等待";
  }
  function cninfoStatusKind(value) {
    if (value === "completed" || value === "passed") return "success";
    if (value === "failed") return "danger";
    if (value === "needs_human" || value === "running" || CNINFO_ACTIVE_STATUSES.has(value)) return "waiting";
    return "info";
  }
  function renderCninfoTaskMeta(task) {
    const result = task.result || {};
    const company = task.company || result.company || {};
    const index = task.steps?.rag_prepare?.index || {};
    const rag = result.rag || {};
    const fields = result.field_extraction || {};
    const values = [
      ["企业", company.company_name || company.name || task.request?.company_query || "—"],
      ["证券代码", company.ticker || "—"],
      ["报告年度", (task.report_years || result.report_years || []).join(" / ") || "—"],
      ["案例编号", task.case_id || result.case_id || "—"],
      ["RAG 原文块", rag.chunk_count ?? index.chunk_count ?? "—"],
      ["检索编号", rag.smoke_retrieval_id || task.steps?.rag_smoke_test?.retrieval_id || "—"],
      ["字段候选", fields.row_count ?? "—"],
      ["尝试次数", task.attempt ?? 0],
    ];
    byId("cninfo-task-meta").innerHTML = values.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd class="${label.includes("编号") ? "mono" : ""}">${escapeHtml(value)}</dd></div>`).join("");
  }
  function renderCninfoSteps(task) {
    byId("cninfo-step-list").innerHTML = CNINFO_STEP_ORDER.map((name, index) => {
      const step = task.steps?.[name] || { status: "pending", detail: "尚未执行。" };
      const kind = cninfoStatusKind(step.status);
      const extra = step.status === "passed" && step.retrieval_id ? ` · ${step.retrieval_id}` : step.status === "passed" && step.case_id ? ` · ${step.case_id}` : "";
      return `<li class="cninfo-step ${kind}"><span class="cninfo-step-index">${String(index + 1).padStart(2, "0")}</span><div><strong>${escapeHtml(CNINFO_STEP_LABELS[name])}</strong><small>${escapeHtml(step.detail || "—")}${escapeHtml(extra)}</small></div><span class="state ${kind}">${escapeHtml(cninfoStepStatusLabel(step.status))}</span></li>`;
    }).join("");
  }
  function renderCninfoMessage(task) {
    const status = task.status;
    const message = task.error?.message || task.error?.detail?.message || "";
    const result = task.result || {};
    const banner = byId("cninfo-task-message");
    let title = cninfoTaskStatusLabel(status);
    let detail = message || `已完成 ${task.steps ? Object.values(task.steps).filter((step) => step.status === "passed").length : 0} 个可追溯步骤。`;
    let kind = cninfoStatusKind(status);
    if (status === "completed" && result.status === "rag_ready") {
      title = "RAG 建库完成，等待真人字段确认";
      detail = "年报原件、哈希和检索链已完成；RAG 结果不能直接视为审计证据。";
      kind = "success";
    } else if (status === "needs_human") {
      title = "流程已安全停在真人处理";
      detail = message || "需要确认企业、补充字段口径或完成专业/许可确认；系统没有伪装成成功。";
      kind = "waiting";
    } else if (status === "failed") {
      title = "巨潮自动流程失败";
      detail = message || "请查看失败原因；历史任务会保留，可在确认原因后重试。";
      kind = "danger";
    } else if (CNINFO_ACTIVE_STATUSES.has(status) || status === "queued") {
      title = cninfoTaskStatusLabel(status);
      detail = "页面正在读取真实后端任务状态，不使用假进度。";
      kind = "info";
    }
    banner.className = `status-banner ${kind === "info" ? "neutral" : kind}`;
    banner.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span>`;
  }
  function renderCninfoCandidates(task) {
    const container = byId("cninfo-candidates");
    const candidates = task.error?.detail?.candidates || task.error?.candidates || [];
    if (!Array.isArray(candidates) || !candidates.length) {
      container.hidden = true;
      container.innerHTML = "";
      return;
    }
    container.hidden = false;
    container.innerHTML = `<div><p class="folio">HUMAN CONFIRMATION REQUIRED</p><h5>巨潮返回了多个同名企业，请选择准确证券代码</h5><p>系统不会根据名称自行猜测企业。候选只来自本次官方股票清单查询。</p></div><div class="cninfo-candidate-list">${candidates.map((item) => `<button class="button quiet" type="button" data-cninfo-candidate="${escapeHtml(item.ticker)}"><strong>${escapeHtml(item.ticker)}</strong><span>${escapeHtml(item.company_name || item.name || "未返回企业名称")}</span><small>${escapeHtml(item.exchange || item.market || "交易所待核验")}</small></button>`).join("")}</div>`;
  }
  function renderCninfoDocuments(task) {
    const result = task.result || {};
    const documents = result.documents?.length ? result.documents : task.steps?.document_validate?.documents || [];
    if (!documents.length) return "<p class=\"empty-state compact\">尚未形成可展示的年报校验记录。</p>";
    return `<div class="cninfo-document-list">${documents.map((document) => `<article class="cninfo-document"><div><span class="folio">${escapeHtml(document.document_id || `REPORT-${document.report_year}`)}</span><h6>${escapeHtml(document.announcement_title || `${document.report_year} 年年度报告`)}</h6><p>${escapeHtml(document.report_year)} 年 · ${escapeHtml(document.page_count ?? "—")} 页 · ${escapeHtml(document.byte_count ? `${document.byte_count} bytes` : "文件大小待记录")}</p></div><div class="cninfo-document-meta"><span class="mono">SHA-256 ${escapeHtml(document.sha256 || "—")}</span>${document.source_url ? `<a class="source-link" href="${escapeHtml(document.source_url)}" target="_blank" rel="noopener">打开巨潮官方原件 ↗</a>` : ""}</div></article>`).join("")}</div>`;
  }
  function renderCninfoResult(task) {
    const container = byId("cninfo-result");
    const result = task.result;
    if (!result) {
      container.hidden = true;
      container.innerHTML = "";
      return;
    }
    const rag = result.rag || {};
    const extraction = result.field_extraction || {};
    const analysis = result.analysis || {};
    const caseId = result.case_id || task.case_id || "";
    const extractionText = extraction.row_count !== undefined ? `${extraction.row_count} 条候选 · ${extraction.status || "待人工"}` : "未进入字段提取";
    const analysisText = analysis.run_id ? `${analysis.run_id} · ${statusLabel(analysis.run_completeness)}` : result.human_review_required ? "需要真人确认后再放行" : "未请求完整分析";
    container.hidden = false;
    container.innerHTML = `<div class="cninfo-result-head"><div><p class="folio">TRACEABLE OUTPUT</p><h5>自动流程结果摘要</h5><p>结果状态：<strong>${escapeHtml(result.status || task.status)}</strong> · ${escapeHtml(aiNotice(result))}</p></div><span class="state ${cninfoStatusKind(result.status)}">${escapeHtml(result.status || task.status)}</span></div><div class="cninfo-result-stats"><div><span>RAG块数</span><strong>${escapeHtml(rag.chunk_count ?? "—")}</strong></div><div><span>检索编号</span><strong class="mono">${escapeHtml(rag.smoke_retrieval_id || "—")}</strong></div><div><span>字段候选</span><strong>${escapeHtml(extractionText)}</strong></div><div><span>分析状态</span><strong>${escapeHtml(analysisText)}</strong></div></div><h6>官方年报与校验记录</h6>${renderCninfoDocuments(task)}<p class="boundary-strip">来源可追溯不等于专业结论；完整分析前仍需确认单位、合并范围、字段页码、口径和模型传输许可。</p>${caseId ? `<button type="button" class="button quiet" data-cninfo-inline-case="${escapeHtml(caseId)}">查看该案例字段与来源台账</button>` : ""}`;
    container.querySelector("[data-cninfo-inline-case]")?.addEventListener("click", () => openCninfoCase(caseId));
  }
  function renderCninfoTask(task) {
    state.cninfoTask = task;
    byId("cninfo-pipeline-panel").hidden = false;
    byId("cninfo-task-id").textContent = task.task_id || "—";
    setStatePill(byId("cninfo-task-state"), cninfoTaskStatusLabel(task.status), cninfoStatusKind(task.status));
    renderCninfoSteps(task);
    renderCninfoTaskMeta(task);
    renderCninfoMessage(task);
    renderCninfoCandidates(task);
    renderCninfoResult(task);
    const retryable = ["failed", "needs_human"].includes(task.status);
    byId("cninfo-retry").hidden = !retryable;
    byId("cninfo-retry").textContent = task.status === "needs_human" ? "确认后重新执行" : "保留历史并重试";
    const caseId = task.case_id || task.result?.case_id || "";
    byId("cninfo-open-case").hidden = !caseId;
    byId("cninfo-open-case").dataset.caseId = caseId;
  }
  async function pollCninfoTask(taskId, token) {
    if (!taskId || token !== state.cninfoPollToken) return;
    try {
      const task = await api(`/api/pipelines/${encodeURIComponent(taskId)}`);
      if (token !== state.cninfoPollToken) return;
      renderCninfoTask(task);
      if (CNINFO_ACTIVE_STATUSES.has(task.status)) {
        state.cninfoPollTimer = window.setTimeout(() => pollCninfoTask(taskId, token), 1200);
      } else {
        state.cninfoPollTimer = null;
      }
    } catch (error) {
      if (token !== state.cninfoPollToken) return;
      const banner = byId("cninfo-task-message");
      banner.className = "status-banner danger";
      banner.innerHTML = `<strong>任务状态读取失败</strong><span>${escapeHtml(error.message)}；任务本身未被删除，可稍后重试读取。</span>`;
      state.cninfoPollTimer = window.setTimeout(() => pollCninfoTask(taskId, token), 2500);
    }
  }
  function beginCninfoPolling(taskId) {
    if (state.cninfoPollTimer) window.clearTimeout(state.cninfoPollTimer);
    state.cninfoPollToken += 1;
    const token = state.cninfoPollToken;
    pollCninfoTask(taskId, token);
  }
  async function startCninfoPipeline(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const query = form.elements.company_query.value.trim();
    if (!query) { form.elements.company_query.focus(); return; }
    if (state.cninfoPollTimer) window.clearTimeout(state.cninfoPollTimer);
    const endBusy = beginButtonBusy(byId("cninfo-pipeline-submit"), "正在排队…");
    byId("cninfo-pipeline-panel").hidden = false;
    showMessage(byId("case-import-message"), "");
    const latestYear = form.elements.latest_year.value.trim();
    const payload = {
      company_query: query,
      years: Number(form.elements.years.value),
      latest_year: latestYear ? Number(latestYear) : null,
      analysis_mode: form.elements.analysis_mode.value,
      rule_ids: ["R1"],
      force_refresh: false,
      planned_materiality: null,
    };
    try {
      const task = await api("/api/pipelines/cninfo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      renderCninfoTask(task);
      beginCninfoPolling(task.task_id);
    } catch (error) {
      renderCninfoTask({ task_id: "—", status: "failed", request: payload, steps: {}, error: { message: error.message } });
    } finally {
      endBusy();
    }
  }
  async function retryCninfoPipeline() {
    const taskId = state.cninfoTask?.task_id;
    if (!taskId || !["failed", "needs_human"].includes(state.cninfoTask?.status)) return;
    const endBusy = beginButtonBusy(byId("cninfo-retry"), "正在重新排队…");
    try {
      const queued = await api(`/api/pipelines/${encodeURIComponent(taskId)}/retry`, { method: "POST" });
      renderCninfoTask({ ...state.cninfoTask, status: "queued", attempt: queued.attempt || state.cninfoTask.attempt, steps: Object.fromEntries(CNINFO_STEP_ORDER.map((name) => [name, { status: "pending", detail: "等待重新执行。" }])) });
      beginCninfoPolling(taskId);
    } catch (error) {
      const banner = byId("cninfo-task-message");
      banner.className = "status-banner danger";
      banner.innerHTML = `<strong>重试未提交</strong><span>${escapeHtml(error.message)}</span>`;
    } finally {
      endBusy();
    }
  }
  async function confirmCninfoCandidate(ticker, button) {
    const taskId = state.cninfoTask?.task_id;
    if (!taskId) return;
    const endBusy = beginButtonBusy(button, "确认中…");
    try {
      await api(`/api/pipelines/${encodeURIComponent(taskId)}/confirm-company`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker }) });
      renderCninfoTask({ ...state.cninfoTask, status: "queued", error: null, steps: Object.fromEntries(CNINFO_STEP_ORDER.map((name) => [name, { status: "pending", detail: "等待重新执行。" }])) });
      beginCninfoPolling(taskId);
    } catch (error) {
      const banner = byId("cninfo-task-message");
      banner.className = "status-banner danger";
      banner.innerHTML = `<strong>企业确认未提交</strong><span>${escapeHtml(error.message)}</span>`;
    } finally {
      endBusy();
    }
  }
  async function submitCninfoFieldReview(button) {
    const caseId = state.currentCase?.case_id;
    const fieldId = button.dataset.fieldId;
    const record = button.closest("[data-cninfo-field-record]");
    const reviewer = byId("cninfo-field-reviewer").value.trim();
    const reason = byId("cninfo-field-reason").value.trim();
    const decision = button.dataset.cninfoFieldAction;
    if (!caseId || !fieldId || !record) return;
    if (!reviewer) {
      showMessage(byId("cninfo-field-review-message"), "请先填写真实复核人或团队角色；系统不代填真人确认。", "error");
      byId("cninfo-field-reviewer").focus();
      return;
    }
    if (["correct", "reject"].includes(decision) && !reason) {
      showMessage(byId("cninfo-field-review-message"), "修正或拒绝候选必须填写原因。", "error");
      byId("cninfo-field-reason").focus();
      return;
    }
    const payload = { field_id: fieldId, decision, reviewer, reason };
    if (decision === "correct") {
      payload.corrected_value = Number(record.querySelector(".cninfo-field-value-input").value);
      payload.corrected_pdf_page = Number(record.querySelector(".cninfo-field-page-input").value);
      if (!Number.isFinite(payload.corrected_value) || !Number.isInteger(payload.corrected_pdf_page) || payload.corrected_pdf_page < 1) {
        showMessage(byId("cninfo-field-review-message"), "修正时必须填写有效金额和 PDF 页码。", "error");
        return;
      }
    }
    const endBusy = beginButtonBusy(button, "正在保存…");
    try {
      const response = await api(`/api/cases/${encodeURIComponent(caseId)}/fields/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      state.currentCase = { ...response.case, financial_fields: response.financial_fields, field_validation: response.field_validation };
      renderProject();
      renderRuleLibrary();
      showMessage(byId("cninfo-field-review-message"), `${fieldId} 已保存为“${cninfoHumanReviewLabel(response.field)}”；历史记录已追加。`, "success");
    } catch (error) {
      showMessage(byId("cninfo-field-review-message"), `字段处理失败：${error.message}`, "error");
    } finally {
      endBusy();
    }
  }
  async function openCninfoCase(caseId) {
    if (!caseId) return;
    try {
      await loadCaseDetail(caseId, { keepYear: true });
      showView("project");
    } catch (error) {
      const banner = byId("cninfo-task-message");
      banner.className = "status-banner danger";
      banner.innerHTML = `<strong>案例读取失败</strong><span>${escapeHtml(error.message)}</span>`;
    }
  }

  function selectedRunnableRules() {
    return RULES.filter((rule) => rule.runnable && state.selectedRules.includes(rule.id)).map((rule) => rule.id);
  }
  function renderRuleLibrary() {
    byId("wb-rule-library").innerHTML = RULES.map((rule) => {
      const selected = state.selectedRules.includes(rule.id);
      return `<article class="rule-record ${rule.runnable ? "" : "roadmap-only"}">
        <div class="rule-id">${rule.runnable ? `<input id="scope-${rule.id}" type="checkbox" data-rule-id="${rule.id}" ${selected ? "checked" : ""}><label for="scope-${rule.id}"><strong>${rule.id}</strong><span class="sr-only">选择 ${escapeHtml(rule.name)}</span></label>` : `<span aria-hidden="true"><strong>${rule.id}</strong></span>`}</div>
        <div class="rule-copy"><span class="folio">${rule.id} · ${rule.runnable ? "ENGINEERING CONTRACT" : "ROADMAP ONLY"}</span><h3>${escapeHtml(rule.name)}</h3><p>${escapeHtml(rule.detail)}</p></div>
        <div class="rule-meta"><span class="state ${rule.id === "R1" ? "success" : rule.runnable ? "waiting" : "info"}">${escapeHtml(rule.status)}</span><small>${escapeHtml(rule.meta)}</small></div>
      </article>`;
    }).join("");
    const runnable = selectedRunnableRules();
    byId("wb-library-status").textContent = `${runnable.join(" / ") || "未选择"} 可运行`;
    byId("wb-scope-note").textContent = `本次运行：${runnable.join("、") || "无"}。R1 是主规则；R2 仅为辅助工程规则；R3—R8 不会进入请求。`;
    const fullButton = byId("wb-run-full");
    const calculationButton = byId("wb-run-calculation");
    const unavailable = !state.backendAvailable || !runnable.length || !state.currentCase;
    const modelTransferAllowed = Boolean(state.currentCase?.model_transfer_allowed);
    const cninfoFieldsConfirmed = state.currentCase?.registry_mode !== "cninfo_official_auto" || state.currentCase?.field_validation?.status === "human_confirmed";
    fullButton.disabled = unavailable || !modelTransferAllowed;
    calculationButton.disabled = unavailable || !cninfoFieldsConfirmed;
    fullButton.classList.toggle("primary", modelTransferAllowed);
    fullButton.classList.toggle("quiet", !modelTransferAllowed);
    calculationButton.classList.toggle("primary", !modelTransferAllowed);
    calculationButton.classList.toggle("quiet", modelTransferAllowed);
    fullButton.innerHTML = modelTransferAllowed ? '开始完整分析 <span aria-hidden="true">→</span>' : "完整分析需许可";
    fullButton.setAttribute("aria-describedby", "wb-case-permission");
    fullButton.title = modelTransferAllowed ? "执行RAG、三Agent与硬校验" : "当前案例禁止模型传输，只能运行仅计算预检";
    byId("run-scope").textContent = runnable.length
      ? `当前将运行 ${runnable.join("、")}；案例 ${state.caseId || "—"}，场景固定为审计计划。${modelTransferAllowed ? "" : " 当前案例尚未取得模型传输许可，请使用仅计算预检。"}${cninfoFieldsConfirmed ? "" : " 巨潮字段尚未完成人工确认，暂不能计算。"}`
      : "当前没有可运行规则。";
    if (!state.run && state.currentCase && !modelTransferAllowed) {
      byId("wb-gate").className = "status-banner warning";
      byId("wb-gate").innerHTML = "<strong>完整分析需真人许可</strong><span>当前真实公开案例禁止模型传输；仅计算预检与本地原文检索仍可使用。</span>";
    }
  }

  function renderAgentSteps(steps) {
    if (!steps?.length) return "";
    const roles = { challenge: "质疑", counter: "反证", review: "复核" };
    return `<ul class="agent-list" aria-label="三Agent运行轨迹">${steps.map((step) => `<li><strong>${escapeHtml(roles[step.role] || step.role)}</strong><span class="state ${statusKind(step.status)}">${escapeHtml(statusLabel(step.status))}</span><small>${escapeHtml(step.detail)}</small></li>`).join("")}</ul>`;
  }
  function renderAiDraft(result) {
    const draft = result.ai_draft;
    if (!draft) return `<section class="ai-draft missing"><span class="folio">AI CONTENT · NOT GENERATED</span><h5>未形成通过硬校验的AI草稿</h5><p>${escapeHtml(aiNotice(result))}</p><p>程序筛查与AI建议是两层状态；请查看运行完整性与失败原因。</p></section>`;
    const claims = (draft.claims || []).map((claim) => `<li><span>${escapeHtml(claim.text)}</span><small>${escapeHtml(claim.support_status)} · ${escapeHtml((claim.evidence_ids || []).join(" / "))}</small></li>`).join("");
    const normal = (draft.normal_explanations || []).map((item) => `<li><span>${escapeHtml(item.text)}</span><small>${escapeHtml(item.support_status)} · ${escapeHtml((item.evidence_ids || []).join(" / ") || "无证据")}</small></li>`).join("");
    return `<section class="ai-draft"><span class="folio">AI生成内容 · ${escapeHtml(statusLabel(result.ai_recommendation))}</span><h5>${escapeHtml(draft.draft_title || "待核查草稿")}</h5><p>${escapeHtml(aiNotice(draft))}</p><p>${escapeHtml(draft.draft_observation || "")}</p>${claims ? `<h6>事实主张与证据</h6><ul>${claims}</ul>` : ""}${normal ? `<h6>正常解释 / 待验证假设</h6><ul>${normal}</ul>` : ""}</section>`;
  }
  function riskCardButton(result, index) {
    if (!result.risk_card && !result.ai_draft) return "";
    return `<div class="risk-summary"><div><span class="folio">${escapeHtml(result.rule_id)} / SCREENING + AI</span><h5>${escapeHtml(result.ai_draft?.draft_title || result.risk_card?.title || result.rule_id)}</h5><p>${escapeHtml(result.ai_draft?.draft_observation || result.risk_card?.observation || "等待更多证据。")}</p><small>${escapeHtml(aiNotice(result.ai_draft || result))}</small></div><button class="button quiet" type="button" data-risk-index="${index}">查看证据与草稿</button></div>`;
  }
  function renderRun(run, humanReview = null) {
    state.run = run;
    state.humanReview = humanReview;
    byId("run-summary").hidden = false;
    byId("current-run-id").textContent = run.run_id;
    byId("screening-status").textContent = statusLabel(run.screening_status);
    byId("ai-recommendation-status").textContent = statusLabel(run.ai_recommendation);
    byId("review-summary-status").textContent = humanReview?.status || run.human_disposition || "未复核";
    byId("run-completeness-status").textContent = statusLabel(run.run_completeness);
    byId("model-check-status").textContent = `${run.retrievals?.length || 0} 次检索 / ${statusLabel(run.model_check?.status)}`;
    setStatePill(byId("analysis-state"), statusLabel(run.run_completeness), statusKind(run.run_completeness));
    byId("wb-sup-parent").value = run.run_id;
    byId("run-lookup-input").value = run.run_id;
    const gate = byId("wb-gate");
    const issues = run.source_validation?.issues || [];
    if (issues.length) {
      gate.className = "status-banner danger";
      gate.innerHTML = `<strong>来源闸门未通过</strong><span>${escapeHtml(issues.join("；"))}</span>`;
    } else if (String(run.run_completeness).startsWith("incomplete")) {
      gate.className = "status-banner warning";
      gate.innerHTML = `<strong>${escapeHtml(statusLabel(run.run_completeness))}</strong><span>程序筛查：${escapeHtml(statusLabel(run.screening_status))}；AI建议：${escapeHtml(statusLabel(run.ai_recommendation))}。不得把不完整运行当作完整风险卡。</span>`;
    } else {
      gate.className = "status-banner success";
      gate.innerHTML = `<strong>${escapeHtml(statusLabel(run.run_completeness))}</strong><span>${escapeHtml(aiNotice(run))}仍须人工回查 evidence ID 后处理。</span>`;
    }
    byId("wb-run-results").innerHTML = run.rule_results.map((result, index) => {
      const metrics = Object.entries(result.metrics || {}).filter(([, value]) => value !== null && value !== undefined);
      return `<article class="result-record"><header class="result-head"><div><span class="folio">${escapeHtml(result.rule_id)} · ${escapeHtml(RULES.find((rule) => rule.id === result.rule_id)?.name || "规则")}</span><h4>${escapeHtml(result.risk_card?.title || "程序筛查")}</h4><p>${escapeHtml(result.risk_card?.engineering_version || "工程规则")}</p></div><span class="state ${statusKind(result.screening_status || result.status)}">${escapeHtml(statusLabel(result.screening_status || result.status))}</span></header><div class="metric-ledger">${metrics.map(([key, value]) => `<div class="metric"><span>${escapeHtml(METRIC_LABELS[key] || key)}</span><strong>${escapeHtml(metricValue(key, value))}</strong><small>${escapeHtml(metricFormula(key))}</small></div>`).join("")}</div>${riskCardButton(result, index)}${renderAiDraft(result)}${renderAgentSteps(result.agent_steps)}</article>`;
    }).join("") + '<section class="scene-followup"><h4>审计计划场景的后续动作</h4><p>人工结合认定候选，决定账龄分析、期后回款检查、合同条款核对和大额交易测试；系统不代签。</p></section>';
    byId("wb-run-results").querySelectorAll("[data-risk-index]").forEach((button) => button.addEventListener("click", () => openRiskDialog(Number(button.dataset.riskIndex))));
    renderEvidenceRail(run, humanReview);
    renderLiveMatrix(run);
    hydrateReview(humanReview);
    renderHistory(run, humanReview);
    updateDeliveryControls();
    updateUrl("replace");
  }
  function renderEvidenceRail(run, humanReview) {
    const gaps = run.evidence_bundle?.evidence_gaps || [];
    const registered = run.evidence_bundle?.supplement_evidence?.length || 0;
    byId("evidence-rail").innerHTML = `<li><span>01</span><div><strong>程序筛查</strong><small>${escapeHtml(statusLabel(run.screening_status))}</small></div></li><li class="${run.ai_recommendation === "not_generated" ? "pending" : ""}"><span>02</span><div><strong>RAG 与 AI</strong><small>${escapeHtml(`${run.retrievals?.length || 0} 次检索；${statusLabel(run.ai_recommendation)}`)}</small></div></li><li class="${gaps.length ? "pending" : ""}"><span>03</span><div><strong>证据支持 / 缺口</strong><small>${escapeHtml(`${run.evidence_bundle?.field_evidence?.length || 0} 字段；${run.evidence_bundle?.rag_evidence?.length || 0} 片段；${registered} 条案例/补充证据；${gaps.length} 检索缺口`)}</small></div></li><li class="${(humanReview?.status || run.human_disposition) === "未复核" ? "pending" : ""}"><span>04</span><div><strong>人工处理</strong><small>${escapeHtml(humanReview?.status || run.human_disposition || "未复核")}</small></div></li>`;
  }
  function renderLiveMatrix(run) {
    byId("live-evidence-matrix").querySelector("tbody").innerHTML = run.rule_results.map((result) => {
      const ragCount = (run.evidence_bundle?.rag_evidence || []).filter((item) => item.rule_id === result.rule_id).length;
      const normal = result.ai_draft?.normal_explanations || [];
      const gaps = result.ai_draft?.data_gaps || result.risk_card?.data_gaps || [];
      const support = result.ai_draft?.claims?.length ? `${result.ai_draft.claims.length} 条主张均绑定 evidence ID` : "无AI主张";
      return `<tr><th><span class="mono">${escapeHtml(result.rule_id)}</span><br><small>${escapeHtml(statusLabel(result.screening_status || result.status))}</small></th><td><span class="state ${statusKind(result.screening_status || result.status)}">${escapeHtml(statusLabel(result.screening_status || result.status))}</span></td><td>${ragCount ? `${ragCount} 个候选片段` : "未参与 / 无命中"}</td><td>${escapeHtml(statusLabel(result.ai_recommendation))}</td><td>${escapeHtml(support)}</td><td>${escapeHtml(normal.map((item) => `${item.text}（${item.support_status}）`).join("；") || "未形成")}</td><td>${escapeHtml(gaps.join("；") || "未返回")}</td></tr>`;
    }).join("");
  }
  function openRiskDialog(index) {
    const result = state.run?.rule_results?.[index];
    if (!result) return;
    const draft = result.ai_draft;
    const list = (items, format = (item) => item) => items?.length ? `<ul>${items.map((item) => `<li>${escapeHtml(format(item))}</li>`).join("")}</ul>` : "<p>未返回。</p>";
    byId("risk-dialog-kicker").textContent = `${result.rule_id} / ${statusLabel(result.screening_status || result.status)} / ${statusLabel(result.ai_recommendation)}`;
    byId("risk-dialog-title").textContent = draft?.draft_title || result.risk_card?.title || "待核查详情";
    const sources = (state.run.evidence_bundle?.field_evidence || []).filter((item) => result.evidence_ids?.includes(item.evidence_id));
    const rag = (state.run.evidence_bundle?.rag_evidence || []).filter((item) => item.rule_id === result.rule_id);
    const registered = state.run.evidence_bundle?.supplement_evidence || [];
    byId("risk-dialog-body").innerHTML = `<section class="risk-detail-section"><h3>四层状态</h3><p>程序：${escapeHtml(statusLabel(result.screening_status || result.status))}；AI：${escapeHtml(statusLabel(result.ai_recommendation))}；人工：${escapeHtml(state.humanReview?.status || state.run.human_disposition)}；完整性：${escapeHtml(statusLabel(state.run.run_completeness))}。</p></section><section class="risk-detail-section"><h3>AI生成内容待核查草稿</h3><p><strong>${escapeHtml(aiNotice(draft || state.run))}</strong></p><p>${escapeHtml(draft?.draft_observation || "未形成通过硬校验的AI草稿。")}</p>${list(draft?.claims, (item) => `${item.text}｜${item.support_status}｜${(item.evidence_ids || []).join("/")}`)}</section><section class="risk-detail-section"><h3>正常解释 / 待验证假设</h3>${list(draft?.normal_explanations, (item) => `${item.text}｜${item.support_status}｜${(item.evidence_ids || []).join("/") || "无证据"}`)}</section><section class="risk-detail-section"><h3>资料缺口与待索取资料</h3>${list(draft?.data_gaps || result.risk_card?.data_gaps)}${list(draft?.requested_materials || result.risk_card?.requested_materials)}</section><section class="risk-detail-section"><h3>计算字段证据</h3>${list(sources, (item) => `${item.evidence_id}｜${item.document_id}｜PDF ${item.pdf_page}｜${item.locator}`)}</section><section class="risk-detail-section"><h3>案例包 / 补充证据</h3>${list(registered, (item) => `${item.evidence_id}｜${item.field_label}｜${item.document_id || item.source_file || "结构化资料"}｜PDF ${item.pdf_page || "—"}｜${item.support_status}`)}</section><section class="risk-detail-section"><h3>RAG候选原文</h3>${list(rag, (item) => `${item.evidence_id}｜${item.retrieval_id}｜PDF ${item.pdf_page}｜${item.excerpt}`)}</section>`;
    byId("risk-dialog").showModal();
  }

  function hydrateReview(review) {
    const draft = safeLocalStorageGet(REVIEW_KEY, {});
    byId("wb-backend-review-status").value = review?.status || draft.status || "未复核";
    byId("wb-backend-reviewer").value = review?.reviewer || draft.reviewer || "";
    byId("wb-backend-review-note").value = review?.note || draft.note || "";
    byId("wb-backend-export-approved").checked = Boolean(review?.export_approved ?? draft.export_approved);
    byId("review-run-context").textContent = state.run ? `当前运行：${state.run.run_id}｜${statusLabel(state.run.run_completeness)}` : "尚未绑定运行。";
  }
  function updateDeliveryControls() {
    const hasRun = Boolean(state.run?.run_id);
    const approved = Boolean(state.humanReview && state.humanReview.status !== "未复核" && state.humanReview.export_approved);
    byId("wb-save-backend-review").disabled = !hasRun;
    byId("wb-cache-run").disabled = !approved;
    byId("wb-export-report").disabled = !approved;
    setStatePill(byId("delivery-state"), state.humanReview?.status || state.run?.human_disposition || "未复核", approved ? "success" : "waiting");
  }
  function renderHistory(run, review) {
    const values = [
      ["run_id", run.run_id],
      ["版本链", `${run.engine_version} / ${run.context?.r1_version} / ${run.context?.agent_prompt_version}`],
      ["数据快照", run.context?.source_snapshot_id || "—"],
      ["模型状态", statusLabel(run.model_check?.status)],
      ["证据范围", `${run.evidence_bundle?.field_evidence?.length || 0} 字段 / ${run.evidence_bundle?.rag_evidence?.length || 0} RAG / ${run.evidence_bundle?.supplement_evidence?.length || 0} 补充`],
      ["人工处理", review?.status || run.human_disposition || "未复核"],
      ["运行方式", run.context?.execution_mode === "cache_replay" ? "缓存回放" : run.context?.continuation_mode ? "补充证据续分析" : statusLabel(run.run_completeness)],
    ];
    byId("run-history-detail").innerHTML = values.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd class="${label === "run_id" ? "mono" : ""}">${escapeHtml(value)}</dd></div>`).join("");
  }

  async function checkHealth() {
    try {
      const health = await api("/api/health");
      state.backendAvailable = health.service_status === "ready";
      const configured = health.model_status === "configured";
      setServiceStatus(configured ? "后端可用 · 模型已配置" : "后端可用 · 模型未配置", configured ? "success" : "pending");
      setStatePill(byId("project-health-state"), configured ? "后端可用 · 模型按本次运行验收" : "后端可用 · 模型未配置", configured ? "success" : "waiting");
      byId("backend-status-note").textContent = configured ? "后端状态：模型配置存在，但完整分析是否成功只看本次 run_completeness 与 Agent 硬校验。" : "后端状态：确定性预检可用；模型未配置时，程序候选不会生成AI草稿。";
    } catch (error) {
      state.backendAvailable = false;
      setServiceStatus("本地后端不可用", "danger");
      setStatePill(byId("project-health-state"), "后端未连接", "danger");
      byId("backend-status-note").textContent = "后端未连接；页面不会模拟计算或AI成功。";
      byId("wb-gate").className = "status-banner danger";
      byId("wb-gate").innerHTML = `<strong>未连接到 FastAPI</strong><span>${escapeHtml(error.message)}</span>`;
    }
    renderRuleLibrary();
  }
  async function runAnalysis(runMode) {
    const rules = selectedRunnableRules();
    if (!rules.length || !state.currentCase || !state.year) return;
    const fullButton = byId("wb-run-full");
    const calcButton = byId("wb-run-calculation");
    const clicked = runMode === "full_analysis" ? fullButton : calcButton;
    const endBusy = beginButtonBusy(clicked, runMode === "full_analysis" ? "正在执行完整链…" : "正在计算…");
    fullButton.disabled = true;
    calcButton.disabled = true;
    byId("wb-gate").className = "status-banner neutral";
    byId("wb-gate").innerHTML = `<strong>${runMode === "full_analysis" ? "正在执行完整分析" : "正在执行仅计算预检"}</strong><span>案例 ${escapeHtml(state.caseId)}；${escapeHtml(rules.join("、"))}。</span>`;
    const materialityText = byId("planned-materiality").value.trim();
    try {
      const run = await api("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: state.caseId, current_year: Number(state.year), scene: "审计计划", rule_ids: rules, run_mode: runMode, planned_materiality: materialityText ? Number(materialityText) : null }),
      });
      renderRun(run, null);
    } catch (error) {
      byId("wb-gate").className = "status-banner danger";
      byId("wb-gate").innerHTML = `<strong>运行失败</strong><span>${escapeHtml(error.message)}</span>`;
      setStatePill(byId("analysis-state"), "调用失败", "danger");
    } finally {
      endBusy();
      renderRuleLibrary();
    }
  }
  async function loadRun(runId, options = {}) {
    if (!runId) return;
    showMessage(byId("wb-backend-toast"), "正在读取运行记录…");
    try {
      const stored = await api(`/api/runs/${encodeURIComponent(runId)}`);
      renderRun(stored.run, stored.human_review);
      showMessage(byId("wb-backend-toast"), "运行记录已读取。", "success");
      if (options.openDelivery) showView("delivery");
    } catch (error) { showMessage(byId("wb-backend-toast"), `读取失败：${error.message}`, "error"); }
  }

  async function checkRagStatus() {
    if (!state.caseId) return;
    try {
      const status = await api(`/api/rag/status?case_id=${encodeURIComponent(state.caseId)}`);
      state.ragStatus = status;
      setStatePill(byId("wb-rag-status"), status.status === "ready" ? `${status.chunk_count} 个原文块` : "索引未构建", status.status === "ready" ? "success" : "waiting");
    } catch (_error) { setStatePill(byId("wb-rag-status"), "索引状态不可用", "danger"); }
  }
  async function prepareRag() {
    const endBusy = beginButtonBusy(byId("wb-rag-prepare"), "正在构建索引…");
    byId("wb-rag-results").innerHTML = '<div class="empty-state compact"><strong>正在核对来源哈希并构建案例独立索引…</strong></div>';
    try {
      const result = await api(`/api/rag/prepare?case_id=${encodeURIComponent(state.caseId)}`, { method: "POST" });
      state.ragStatus = result;
      setStatePill(byId("wb-rag-status"), `${result.chunk_count} 个原文块`, "success");
      byId("wb-rag-results").innerHTML = `<div class="empty-state compact"><strong>索引可用</strong><p>${escapeHtml(result.case_id)} · ${escapeHtml(result.index_version)}</p></div>`;
    } catch (error) { byId("wb-rag-results").innerHTML = `<div class="empty-state compact"><strong>索引构建失败</strong><p>${escapeHtml(error.message)}</p></div>`; } finally { endBusy(); }
  }
  function highlightExcerpt(excerpt, query) {
    let safe = escapeHtml(excerpt);
    const tokens = Array.from(new Set((query.match(/[\u3400-\u9fff]{2,}|[A-Za-z0-9_.%-]+/g) || []))).sort((a, b) => b.length - a.length).slice(0, 8);
    tokens.forEach((token) => { safe = safe.replace(new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), (match) => `<mark>${match}</mark>`); });
    return safe;
  }
  function selectRagResult(index) {
    const item = state.ragResults[index];
    if (!item) return;
    document.querySelectorAll(".rag-result").forEach((button, position) => button.setAttribute("aria-pressed", position === index ? "true" : "false"));
    byId("source-reader").innerHTML = `<span class="folio">${escapeHtml(item.chunk_id)} / SCORE ${escapeHtml(item.score)}</span><h3>${escapeHtml(item.title || "年报原文")}</h3><dl class="source-meta"><div><dt>文档编号</dt><dd>${escapeHtml(item.document_id)}</dd></div><div><dt>披露日期</dt><dd>${escapeHtml(item.disclosure_date)}</dd></div><div><dt>PDF页码</dt><dd>${escapeHtml(item.pdf_page)}</dd></div><div><dt>evidence ID</dt><dd>${escapeHtml(item.evidence_id)}</dd></div><div><dt>T0状态</dt><dd>${escapeHtml(item.disclosure_date)} ≤ ${escapeHtml(state.currentCase.t0)}</dd></div><div><dt>文件哈希</dt><dd>${escapeHtml(item.source_sha256)}</dd></div></dl><p class="source-excerpt">${highlightExcerpt(item.excerpt, byId("wb-rag-query").value)}</p><a class="button quiet source-link-button" href="${sourceUrl(item.document_id, item.pdf_page)}" target="_blank" rel="noopener">打开原 PDF 第 ${escapeHtml(item.pdf_page)} 页</a>`;
  }
  async function retrieveRag(event) {
    event.preventDefault();
    const query = byId("wb-rag-query").value.trim();
    if (!query) { byId("wb-rag-results").innerHTML = '<div class="empty-state compact"><strong>请先填写要回查的事项。</strong></div>'; return; }
    const endBusy = beginButtonBusy(byId("wb-rag-search"), "正在检索…");
    try {
      const body = await api("/api/rag/retrieve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, t0: state.currentCase.t0, rule_id: byId("wb-rag-rule").value, top_k: 5, case_id: state.caseId, company_name: state.currentCase.company_name }) });
      byId("retrieval-id").textContent = body.retrieval_id;
      state.ragResults = body.results || [];
      if (!state.ragResults.length) {
        byId("wb-rag-results").innerHTML = `<div class="empty-state compact"><strong>本次未命中可回查片段</strong><p>${escapeHtml(body.evidence_gap?.message || "不能据此认定年报未披露。")}</p></div>`;
        return;
      }
      byId("wb-rag-results").innerHTML = state.ragResults.map((item, index) => `<button class="rag-result" type="button" data-rag-index="${index}" aria-pressed="false"><span class="folio">${escapeHtml(item.chunk_id)} · PDF ${escapeHtml(item.pdf_page)}</span><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.document_id)} · score ${escapeHtml(item.score)}</small></button>`).join("");
      byId("wb-rag-results").querySelectorAll("[data-rag-index]").forEach((button) => button.addEventListener("click", () => selectRagResult(Number(button.dataset.ragIndex))));
      selectRagResult(0);
    } catch (error) { byId("wb-rag-results").innerHTML = `<div class="empty-state compact"><strong>检索失败</strong><p>${escapeHtml(error.message)}</p></div>`; } finally { endBusy(); }
  }

  async function importCase(event) {
    event.preventDefault();
    const file = byId("case-import-file").files[0];
    if (!file) { showMessage(byId("case-import-message"), "请选择标准案例 ZIP。", "error"); return; }
    const formData = new FormData();
    formData.append("file", file);
    formData.append("authorized", String(byId("case-import-authorized").checked));
    formData.append("desensitized", String(byId("case-import-desensitized").checked));
    const endBusy = beginButtonBusy(byId("case-import-submit"), "正在校验…");
    showMessage(byId("case-import-message"), "正在校验 manifest、哈希、路径、字段口径与个人信息…");
    try {
      const body = await api("/api/cases/import", { method: "POST", body: formData });
      state.requestedCase = body.case.case_id;
      const listing = await api("/api/cases");
      state.cases = listing.cases || [];
      await loadCaseDetail(body.case.case_id);
      showMessage(byId("case-import-message"), `${body.case.case_id} 已导入；仍待人工确认是否作为正式案例。`, "success");
    } catch (error) { showMessage(byId("case-import-message"), `导入失败：${error.message}`, "error"); } finally { endBusy(); }
  }
  async function registerSupplement(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!byId("wb-sup-parent").value.trim()) { showMessage(byId("supplement-message"), "请先运行一次分析取得父运行编号。", "error"); byId("wb-sup-parent").focus(); return; }
    const rules = Array.from(form.querySelectorAll('input[name="bound_rule"]:checked')).map((input) => input.value);
    const formData = new FormData();
    ["parent_run_id", "material_type", "as_of_date", "note", "structured_json"].forEach((name) => formData.append(name, form.elements[name].value));
    formData.append("authorized", String(byId("wb-sup-authorized").checked));
    formData.append("desensitized", String(byId("wb-sup-desensitized").checked));
    formData.append("bound_rule_ids", JSON.stringify(rules));
    const file = byId("wb-sup-file").files[0]; if (file) formData.append("file", file);
    const endBusy = beginButtonBusy(byId("wb-sup-register"), "正在预检…");
    try {
      const body = await api("/api/supplements", { method: "POST", body: formData });
      state.supplementId = body.supplement_id;
      setStatePill(byId("wb-sup-state"), body.status === "ready_for_rerun" ? "补充证据可续分析" : body.status, body.status === "ready_for_rerun" ? "success" : body.status === "rejected" ? "danger" : "waiting");
      byId("wb-sup-rerun").disabled = body.status !== "ready_for_rerun";
      byId("supplement-result").hidden = false;
      byId("parent-run-label").textContent = body.parent_run_id;
      byId("supplement-id-label").textContent = body.supplement_id;
      byId("rerun-scope-label").textContent = `${body.structured_evidence?.length || 0} 条独立证据 / ${body.field_correction_mode}`;
      showMessage(byId("supplement-message"), `${body.supplement_id} · ${body.boundary}${body.issues?.length ? ` 问题：${body.issues.join("；")}` : ""}`, body.status === "rejected" ? "error" : "success");
    } catch (error) { showMessage(byId("supplement-message"), `补充资料登记失败：${error.message}`, "error"); } finally { endBusy(); }
  }
  async function rerunSupplement() {
    if (!state.supplementId) return;
    const endBusy = beginButtonBusy(byId("wb-sup-rerun"), "正在完整续分析…");
    try {
      const run = await api(`/api/supplements/${encodeURIComponent(state.supplementId)}/rerun`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_mode: "full_analysis" }) });
      renderRun(run, null);
      const change = run.context?.recommendation_change;
      byId("rerun-scope-label").textContent = change ? `${statusLabel(change.before)} → ${statusLabel(change.after)} · ${change.label}` : "续分析完成";
      showMessage(byId("supplement-message"), `续分析完成：${run.run_id}；${statusLabel(run.run_completeness)}。`, "success");
      showView("analysis");
    } catch (error) { showMessage(byId("supplement-message"), `续分析失败：${error.message}`, "error"); } finally { endBusy(); }
  }

  async function saveReview(event) {
    event.preventDefault(); if (!state.run?.run_id) return;
    const endBusy = beginButtonBusy(byId("wb-save-backend-review"), "正在保存…");
    const review = { status: byId("wb-backend-review-status").value, reviewer: byId("wb-backend-reviewer").value.trim(), note: byId("wb-backend-review-note").value.trim(), reviewed_at: new Date().toISOString(), export_approved: byId("wb-backend-export-approved").checked, reviewer_type: "human" };
    safeLocalStorageSet(REVIEW_KEY, review);
    try { const stored = await api(`/api/runs/${encodeURIComponent(state.run.run_id)}/review`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(review) }); renderRun(stored.run, stored.human_review); showMessage(byId("wb-backend-toast"), "人工处理已保存。", "success"); } catch (error) { showMessage(byId("wb-backend-toast"), `复核保存失败：${error.message}`, "error"); } finally { endBusy(); updateDeliveryControls(); }
  }
  async function cacheRun() {
    if (!state.run?.run_id) return;
    const endBusy = beginButtonBusy(byId("wb-cache-run"), "正在写入缓存…");
    try { const result = await api(`/api/runs/${encodeURIComponent(state.run.run_id)}/cache`, { method: "POST" }); byId("cache-id-input").value = result.cache_id; showMessage(byId("delivery-message"), `${result.cache_id} 已写入。${result.boundary}`, "success"); } catch (error) { showMessage(byId("delivery-message"), `缓存写入失败：${error.message}`, "error"); } finally { endBusy(); updateDeliveryControls(); }
  }
  async function replayCache() {
    const id = byId("cache-id-input").value.trim(); if (!id) { showMessage(byId("delivery-message"), "请填写缓存编号。", "error"); return; }
    const endBusy = beginButtonBusy(byId("cache-replay-button"), "正在回放…");
    try { const run = await api(`/api/cache/${encodeURIComponent(id)}/replay`, { method: "POST" }); renderRun(run, null); showMessage(byId("delivery-message"), `缓存回放完成：${run.run_id}；没有重新运行模型。`, "success"); showView("analysis"); } catch (error) { showMessage(byId("delivery-message"), `回放失败：${error.message}`, "error"); } finally { endBusy(); }
  }
  async function exportReport() {
    if (!state.run?.run_id) return;
    const endBusy = beginButtonBusy(byId("wb-export-report"), "正在生成…");
    try {
      const response = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(state.run.run_id)}/report.docx`);
      if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `HTTP ${response.status}`); }
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = `${state.run.run_id}_预审风险备忘录_report_v2.docx`; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
      showMessage(byId("delivery-message"), "report_v2 已生成并开始下载。", "success");
    } catch (error) { showMessage(byId("delivery-message"), `导出失败：${error.message}`, "error"); } finally { endBusy(); updateDeliveryControls(); }
  }

  function bindEvents() {
    document.querySelectorAll("[data-view]").forEach((link) => link.addEventListener("click", (event) => { event.preventDefault(); showView(link.dataset.view); }));
    document.querySelectorAll("[data-wb-step]").forEach((button) => {
      button.addEventListener("click", () => handleLegacyStep(button.dataset.wbStep));
      button.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault(); const tabs = Array.from(document.querySelectorAll("[data-wb-step]")); const index = tabs.indexOf(button); const target = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : event.key === "ArrowRight" ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length; tabs[target].focus(); handleLegacyStep(tabs[target].dataset.wbStep);
      });
    });
    document.querySelectorAll("[data-wb-go]").forEach((button) => button.addEventListener("click", () => handleLegacyStep(button.dataset.wbGo)));
    byId("mobile-nav-toggle").addEventListener("click", () => { const open = byId("primary-navigation").classList.toggle("open"); byId("mobile-nav-toggle").setAttribute("aria-expanded", String(open)); syncMobileNavigationAccessibility(open); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && byId("primary-navigation").classList.contains("open")) { closeMobileNavigation(); byId("mobile-nav-toggle").focus(); } });
    window.addEventListener("resize", () => syncMobileNavigationAccessibility(byId("primary-navigation").classList.contains("open")));
    byId("wb-case").addEventListener("change", (event) => loadCaseDetail(event.target.value));
    byId("wb-current-year").addEventListener("change", (event) => { state.year = event.target.value; renderProject(); updateUrl("replace"); });
    byId("wb-amount-unit").addEventListener("change", (event) => { state.unit = event.target.value; renderProject(); });
    byId("wb-refresh-case").addEventListener("click", () => loadCaseDetail(state.caseId, { keepYear: true }));
    byId("cninfo-pipeline-form").addEventListener("submit", startCninfoPipeline);
    byId("cninfo-retry").addEventListener("click", retryCninfoPipeline);
    byId("cninfo-open-case").addEventListener("click", (event) => openCninfoCase(event.currentTarget.dataset.caseId));
    byId("cninfo-candidates").addEventListener("click", (event) => { const button = event.target.closest("[data-cninfo-candidate]"); if (button) confirmCninfoCandidate(button.dataset.cninfoCandidate, button); });
    byId("cninfo-field-review-list").addEventListener("click", (event) => { const button = event.target.closest("[data-cninfo-field-action]"); if (button) submitCninfoFieldReview(button); });
    byId("case-import-form").addEventListener("submit", importCase);
    byId("wb-rule-library").addEventListener("change", (event) => { const input = event.target.closest("[data-rule-id]"); if (!input) return; if (input.checked && !state.selectedRules.includes(input.dataset.ruleId)) state.selectedRules.push(input.dataset.ruleId); if (!input.checked) state.selectedRules = state.selectedRules.filter((id) => id !== input.dataset.ruleId); state.selectedRules.sort(); safeLocalStorageSet(SCOPE_KEY, state.selectedRules); renderRuleLibrary(); updateUrl("replace"); });
    byId("wb-run-full").addEventListener("click", () => runAnalysis("full_analysis"));
    byId("wb-run-calculation").addEventListener("click", () => runAnalysis("calculation_only"));
    byId("wb-rag-prepare").addEventListener("click", prepareRag);
    byId("rag-form").addEventListener("submit", retrieveRag);
    byId("supplement-form").addEventListener("submit", registerSupplement);
    byId("wb-sup-rerun").addEventListener("click", rerunSupplement);
    byId("review-form").addEventListener("submit", saveReview);
    byId("wb-save-local-review").addEventListener("click", () => { const draft = { status: byId("wb-backend-review-status").value, reviewer: byId("wb-backend-reviewer").value, note: byId("wb-backend-review-note").value, export_approved: byId("wb-backend-export-approved").checked }; safeLocalStorageSet(REVIEW_KEY, draft); showMessage(byId("wb-backend-toast"), "本机草稿已保存；不等于后端人工复核。", "success"); });
    byId("review-form").addEventListener("input", () => safeLocalStorageSet(REVIEW_KEY, { status: byId("wb-backend-review-status").value, reviewer: byId("wb-backend-reviewer").value, note: byId("wb-backend-review-note").value, export_approved: byId("wb-backend-export-approved").checked }));
    byId("run-lookup-form").addEventListener("submit", (event) => { event.preventDefault(); loadRun(byId("run-lookup-input").value.trim()); });
    byId("wb-cache-run").addEventListener("click", cacheRun);
    byId("cache-replay-button").addEventListener("click", replayCache);
    byId("wb-export-report").addEventListener("click", exportReport);
    byId("risk-dialog").querySelector("[data-close-dialog]").addEventListener("click", () => byId("risk-dialog").close());
    byId("risk-dialog").addEventListener("click", (event) => { if (event.target === byId("risk-dialog")) byId("risk-dialog").close(); });
    window.addEventListener("popstate", async () => { readUrlState(); if (state.requestedCase && state.requestedCase !== state.caseId) await loadCaseDetail(state.requestedCase, { keepYear: true }); renderRuleLibrary(); showView(state.view, { history: false }); });
  }

  async function initialize() {
    const storedScope = safeLocalStorageGet(SCOPE_KEY, ["R1"]);
    if (Array.isArray(storedScope)) { const valid = storedScope.filter((id) => RULES.some((rule) => rule.id === id && rule.runnable)); if (valid.length) state.selectedRules = valid; }
    const requestedRun = readUrlState();
    bindEvents();
    syncMobileNavigationAccessibility(false);
    hydrateReview(null);
    showView(state.view, { history: false, focus: false });
    try { await loadSystemAndCases(); } catch (error) { setServiceStatus("状态接口不可用", "danger"); showMessage(byId("case-import-message"), `无法读取案例：${error.message}`, "error"); }
    await checkHealth();
    updateUrl("replace");
    if (requestedRun) await loadRun(requestedRun);
  }

  initialize();
}());
