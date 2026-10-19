(function () {
  "use strict";

  const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
  const REVIEW_KEY = "audittrace_root_workbench_review_v1";
  const SCOPE_KEY = "audittrace_root_workbench_rule_scope_v1";
  const VIEW_IDS = ["overview", "project", "rules", "analysis", "rag", "supplement", "delivery", "methods"];
  const LEGACY_VIEW_MAP = {
    project: "project",
    data: "project",
    risk: "analysis",
    library: "rules",
    rag: "rag",
    supplement: "supplement",
    delivery: "delivery",
  };
  const UNIT_MAP = {
    yuan: { label: "元", divisor: 1 },
    "ten-thousand": { label: "万元", divisor: 10000 },
    million: { label: "百万元", divisor: 1000000 },
  };
  const FIELD_LABELS = {
    revenue_current: "本年营业收入",
    revenue_previous: "上年营业收入",
    ar_current: "本年应收账款（报表列示额）",
    ar_previous: "上年应收账款（报表列示额）",
    operating_cash_flow_current: "本年经营活动现金流量净额",
    operating_cash_flow_previous: "上年经营活动现金流量净额",
    net_profit_current: "本年净利润（R2增强项）",
  };
  const METRIC_LABELS = {
    revenue_growth: "营业收入增速",
    ar_growth: "应收账款增速",
    growth_gap: "两者差额",
    operating_cash_flow_growth: "经营活动现金流量净额增速",
    cashflow_to_revenue_current: "本年经营现金流 / 营业收入",
    cashflow_to_revenue_previous: "上年经营现金流 / 营业收入",
    net_profit_cashflow_gap: "净利润—经营现金流差异",
  };
  const STATUS_LABELS = {
    candidate: "候选现象，待人工复核",
    RULE_NOT_TRIGGERED: "仅完成计算",
    DATA_NOT_COMPARABLE: "同比不宜比较",
    DATA_GAP: "资料不足",
    SOURCE_INCOMPLETE: "来源未通过",
    cache_replay: "批准缓存回放",
    model_success: "三 Agent 输出已通过工程校验",
    config_missing: "模型配置缺失",
    provider_unreachable: "模型调用失败",
    MODEL_OUTPUT_INVALID: "模型输出校验失败",
    not_requested: "本次未请求模型",
    not_applicable: "本次不适用模型",
  };

  const PERIODS = {
    "2025": {
      previous: "2024",
      t0: "2026-04-30",
      data: [
        ["revenue_current", 2025, 337238620.57, "STD_REV_2025", "标准股份：标准股份2025年年度报告全文(1).pdf", "2026-04-30", "64", "64（页脚印与 PDF 一致）", "合并利润表／营业收入（2025 本期）"],
        ["revenue_previous", 2024, 446351660.77, "STD_REV_2024", "标准股份：标准股份2024年年度报告全文（修订版）.pdf", "2025-04-29", "67", "67（页脚印与 PDF 一致）", "合并利润表／营业收入（2024 本期）"],
        ["ar_current", 2025, 176388063.66, "STD_AR_2025", "标准股份：标准股份2025年年度报告全文(1).pdf", "2026-04-30", "59", "59（页脚印与 PDF 一致）", "合并资产负债表／应收账款（2025 期末）"],
        ["ar_previous", 2024, 282866689.51, "STD_AR_2024", "标准股份：标准股份2024年年度报告全文（修订版）.pdf", "2025-04-29", "62", "62（页脚印与 PDF 一致）", "合并资产负债表／应收账款（2024 期末）"],
        ["operating_cash_flow_current", 2025, -32280442.49, "STD_CFO_2025", "标准股份：标准股份2025年年度报告全文(1).pdf", "2026-04-30", "67", "67（页脚印与 PDF 一致）", "合并现金流量表／经营活动产生的现金流量净额（2025 本期）"],
        ["operating_cash_flow_previous", 2024, 1570534.28, "STD_CFO_2024", "标准股份：标准股份2024年年度报告全文（修订版）.pdf", "2025-04-29", "71", "71（页脚印与 PDF 一致）", "合并现金流量表／经营活动产生的现金流量净额（2024 本期）"],
        ["net_profit_current", 2025, -170193631.28, "STD_NP_2025", "标准股份：标准股份2025年年度报告全文(1).pdf", "2026-04-30", "64", "64（页脚印与 PDF 一致）", "合并利润表／净利润（2025 本期）"],
      ],
    },
    "2024": {
      previous: "2023",
      t0: "2025-04-29",
      data: [
        ["revenue_current", 2024, 446351660.77, "STD_REV_2024", "标准股份：标准股份2024年年度报告全文（修订版）.pdf", "2025-04-29", "67", "67（页脚印与 PDF 一致）", "合并利润表／营业收入（2024 本期）"],
        ["revenue_previous", 2023, 506925296.14, "STD_REV_2023", "标准股份：标准股份2023年年度报告.pdf", "2024-04-18", "70", "70（页脚印与 PDF 一致）", "合并利润表／营业收入（2023 本期）"],
        ["ar_current", 2024, 282866689.51, "STD_AR_2024", "标准股份：标准股份2024年年度报告全文（修订版）.pdf", "2025-04-29", "62", "62（页脚印与 PDF 一致）", "合并资产负债表／应收账款（2024 期末）"],
        ["ar_previous", 2023, 329742664.91, "STD_AR_2023", "标准股份：标准股份2023年年度报告.pdf", "2024-04-18", "66", "66（页脚印与 PDF 一致）", "合并资产负债表／应收账款（2023 期末）"],
        ["operating_cash_flow_current", 2024, 1570534.28, "STD_CFO_2024", "标准股份：标准股份2024年年度报告全文（修订版）.pdf", "2025-04-29", "71", "71（页脚印与 PDF 一致）", "合并现金流量表／经营活动产生的现金流量净额（2024 本期）"],
        ["operating_cash_flow_previous", 2023, -29688300.25, "STD_CFO_2023", "标准股份：标准股份2023年年度报告.pdf", "2024-04-18", "74", "74（页脚印与 PDF 一致）", "合并现金流量表／经营活动产生的现金流量净额（2023 本期）"],
        ["net_profit_current", 2024, -165447424.92, "STD_NP_2024", "标准股份：标准股份2024年年度报告全文（修订版）.pdf", "2025-04-29", "68", "68（页脚印与 PDF 一致）", "合并利润表／净利润（2024 本期）"],
      ],
    },
    "2023": {
      previous: "2022",
      t0: "2024-04-18",
      data: [
        ["revenue_current", 2023, 506925296.14, "STD_REV_2023", "标准股份：标准股份2023年年度报告.pdf", "2024-04-18", "70", "70（页脚印与 PDF 一致）", "合并利润表／营业收入（2023 本期）"],
        ["revenue_previous", 2022, 1050779931.05, "STD_REV_2022", "标准股份：标准股份2022年年度报告.pdf", "2023-04-19", "63", "63（页脚印与 PDF 一致）", "合并利润表／营业收入（2022 本期）"],
        ["ar_current", 2023, 329742664.91, "STD_AR_2023", "标准股份：标准股份2023年年度报告.pdf", "2024-04-18", "66", "66（页脚印与 PDF 一致）", "合并资产负债表／应收账款（2023 期末）"],
        ["ar_previous", 2022, 439176425.31, "STD_AR_2022", "标准股份：标准股份2022年年度报告.pdf", "2023-04-19", "59", "59（页脚印与 PDF 一致）", "合并资产负债表／应收账款（2022 期末）"],
        ["operating_cash_flow_current", 2023, -29688300.25, "STD_CFO_2023", "标准股份：标准股份2023年年度报告.pdf", "2024-04-18", "74", "74（页脚印与 PDF 一致）", "合并现金流量表／经营活动产生的现金流量净额（2023 本期）"],
        ["operating_cash_flow_previous", 2022, 24322281.01, "STD_CFO_2022", "标准股份：标准股份2022年年度报告.pdf", "2023-04-19", "66", "66（页脚印与 PDF 一致）", "合并现金流量表／经营活动产生的现金流量净额（2022 本期）"],
        ["net_profit_current", 2023, -212351971.28, "STD_NP_2023", "标准股份：标准股份2023年年度报告.pdf", "2024-04-18", "71", "71（页脚印与 PDF 一致）", "合并利润表／净利润（2023 本期）"],
      ],
    },
  };

  const RULES = [
    { id: "R1", name: "应收—收入背离", detail: "应收增速相对收入偏高时，进一步看账龄、期后回款和合同结算。", meta: "本地后端可运行（四字段方向比较）", status: "已实现可运行", runnable: true },
    { id: "R2", name: "收入—经营现金流背离", detail: "收入增长但经营现金流未同步改善时，结合经营性应收应付、存货、税费和结算周期再看；跨期变号或基数过小时不做同比判断。", meta: "本地后端可运行（方向比较版，含可比性保护）", status: "工程版待专业复核", runnable: true },
    { id: "R3", name: "产销量—收入不匹配", detail: "在产品、单位、期间和合并范围可比时，核对收入规模与产能、产量、销量之间是否需要解释。", meta: "待产能产量资料", status: "候选 / 待资料", runnable: false },
    { id: "R4", name: "客户集中度与交易特征变化", detail: "关注前五大客户集中度变化及交易对手公开特征与披露规模之间是否存在待解释事项。", meta: "待客户披露与官方登记资料", status: "候选 / 待资料", runnable: false },
    { id: "R5", name: "总额法 / 净额法判断依据", detail: "围绕控制权、履约责任、定价和存货风险，检查收入政策与业务模式的判断依据是否充分。", meta: "待合同和收入政策资料", status: "候选 / 尚未验收", runnable: false },
    { id: "R6", name: "毛利率逆行业变化", detail: "在产品结构、成本范围和会计政策可比时，关注公司毛利率与行业趋势背离且缺少可核验解释的情况。", meta: "待同行与成本资料", status: "候选 / 待资料", runnable: false },
    { id: "R7", name: "管理层表述与数字不一致", detail: "管理层讨论称竞争加剧、价格承压或需求下降，但收入或毛利率显著改善且缺少解释时，保留为披露一致性线索。", meta: "待披露切片与语义复核", status: "候选 / 尚未验收", runnable: false },
    { id: "R8", name: "年末 / 第四季度收入集中", detail: "第四季度或年末收入占比异常时，结合应收、合同资产、退货折让和减值资料一起核查。", meta: "待分季度与期后资料", status: "候选 / 待资料", runnable: false },
  ];

  function lockedSourceRecord(evidenceId) {
    for (const period of Object.values(PERIODS)) {
      const record = period.data.find((item) => item[3] === evidenceId);
      if (record) return record;
    }
    return null;
  }

  function sourceDisplay(source) {
    const record = lockedSourceRecord(source.evidence_id);
    if (!record) {
      return `${source.source_file}｜披露 ${source.disclosure_date}｜PDF ${source.pdf_page || "—"} 页｜${source.locator}`;
    }
    return `${record[4]}｜披露 ${record[5]}｜PDF ${record[6]} 页｜印刷 ${record[7]}｜${record[8]}`;
  }

  function sourceHeading(source) {
    const record = lockedSourceRecord(source.evidence_id);
    const label = FIELD_LABELS[source.field_id] || source.field_id;
    return record
      ? `${source.evidence_id} · ${label}（${record[1]}）`
      : `${source.evidence_id} · ${label}`;
  }

  const state = {
    view: "overview",
    year: "2025",
    scene: "审计计划",
    unit: "yuan",
    selectedRules: ["R1", "R2"],
    run: null,
    humanReview: null,
    backendAvailable: false,
    ragStatus: null,
    ragResults: [],
    supplementId: null,
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function statusLabel(value) {
    return STATUS_LABELS[value] || value || "—";
  }

  function setStatePill(element, text, kind) {
    if (!element) return;
    element.textContent = text;
    element.className = `state ${kind}`;
  }

  function setServiceStatus(text, kind) {
    const pill = byId("service-pill");
    if (!pill) return;
    byId("service-status").textContent = text;
    pill.className = `service-pill ${kind}`;
  }

  function showMessage(element, text, kind = "") {
    if (!element) return;
    element.textContent = text;
    element.className = `form-message${kind ? ` ${kind}` : ""}`;
  }

  function beginButtonBusy(button, loadingText) {
    const originalText = button.textContent;
    const originallyDisabled = button.disabled;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.textContent = loadingText;
    return () => {
      button.textContent = originalText;
      button.disabled = originallyDisabled;
      button.removeAttribute("aria-busy");
    };
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, options);
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = body && typeof body === "object" ? body.detail : body;
      throw new Error(detail || `HTTP ${response.status}`);
    }
    return body;
  }

  function safeLocalStorageGet(key, fallback) {
    try {
      const value = JSON.parse(window.localStorage.getItem(key) || "null");
      return value ?? fallback;
    } catch (_error) {
      return fallback;
    }
  }

  function safeLocalStorageSet(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (_error) {
      // Storage can be unavailable in strict private modes. The current session
      // continues to work without pretending that persistence succeeded.
    }
  }

  function readUrlState() {
    const params = new URLSearchParams(window.location.search);
    const view = params.get("view");
    const year = params.get("year");
    const scene = params.get("scene");
    const rules = (params.get("rules") || "").split(",").filter(Boolean);
    if (VIEW_IDS.includes(view)) state.view = view;
    if (PERIODS[year]) state.year = year;
    if (scene && ["新客户业务承接", "续聘复核", "审计计划"].includes(scene)) state.scene = scene;
    if (rules.length) {
      const valid = rules.filter((id) => RULES.some((rule) => rule.id === id));
      if (valid.length) state.selectedRules = valid;
    }
    return params.get("run");
  }

  function updateUrl(mode = "replace") {
    const url = new URL(window.location.href);
    url.searchParams.set("view", state.view);
    url.searchParams.set("year", state.year);
    url.searchParams.set("scene", state.scene);
    url.searchParams.set("rules", state.selectedRules.join(","));
    if (state.run?.run_id) url.searchParams.set("run", state.run.run_id);
    else url.searchParams.delete("run");
    window.history[mode === "push" ? "pushState" : "replaceState"]({}, "", url);
  }

  function syncMobileNavigationAccessibility(open = false) {
    const sidebar = byId("primary-navigation");
    const toggle = byId("mobile-nav-toggle");
    const mobileLayout = window.matchMedia("(max-width: 1024px)").matches;
    sidebar.inert = mobileLayout && !open;
    if (!mobileLayout) {
      sidebar.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    }
  }

  function closeMobileNavigation() {
    const sidebar = byId("primary-navigation");
    const toggle = byId("mobile-nav-toggle");
    sidebar.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
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
      if (link.dataset.view === view) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    closeMobileNavigation();
    if (options.history !== false) updateUrl(options.replace ? "replace" : "push");
    if (options.focus !== false) {
      byId("main-content").focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: "instant" });
    }
  }

  function handleLegacyStep(step) {
    const view = LEGACY_VIEW_MAP[step] || "project";
    showView(view);
    document.querySelectorAll("[data-wb-step]").forEach((button) => {
      button.setAttribute("aria-selected", button.dataset.wbStep === step ? "true" : "false");
    });
    if (step === "data") {
      window.requestAnimationFrame(() => byId("source-ledger")?.scrollIntoView({ block: "start" }));
    }
  }

  function formatAmount(value) {
    const unit = UNIT_MAP[state.unit] || UNIT_MAP.yuan;
    return new Intl.NumberFormat("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(value) / unit.divisor);
  }

  function formatPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return new Intl.NumberFormat("zh-CN", {
      style: "percent",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(value));
  }

  function metricLabel(result, key) {
    if (key === "growth_gap" && result.rule_id === "R2") {
      return "收入增速与经营现金流增速差额";
    }
    return METRIC_LABELS[key] || key;
  }

  function metricValue(result, key, value) {
    if (key === "growth_gap") {
      return `${(Number(value) * 100).toFixed(2)} 个百分点`;
    }
    return formatPercent(value);
  }

  function metricFormula(result, key) {
    const formulas = {
      revenue_growth: "（本年收入 − 上年收入）/ 上年收入",
      ar_growth: "（本年应收 − 上年应收）/ 上年应收",
      operating_cash_flow_growth: "（本年经营现金流 − 上年经营现金流）/ 上年经营现金流",
      cashflow_to_revenue_current: "本年经营现金流 / 本年营业收入",
      cashflow_to_revenue_previous: "上年经营现金流 / 上年营业收入",
      net_profit_cashflow_gap: "经营现金流与净利润方向增强项",
    };
    if (key === "growth_gap") {
      return result.rule_id === "R1" ? "应收账款增速 − 收入增速" : "营业收入增速 − 经营现金流增速";
    }
    return formulas[key] || key;
  }

  function displayObservation(result) {
    const card = result.risk_card || {};
    if (result.rule_id !== "R1") return card.observation || card.title || "";
    const revenue = result.metrics?.revenue_growth;
    const receivable = result.metrics?.ar_growth;
    const gap = result.metrics?.growth_gap;
    if ([revenue, receivable].some((value) => value === null || value === undefined)) {
      return card.observation || card.title || "";
    }
    const year = state.run?.context?.current_year || state.year;
    const company = state.run?.context?.company_name || "西安标准工业股份有限公司（标准股份）";
    if (result.status === "candidate") {
      return `${year} 年，${company}应收账款增速为 ${formatPercent(receivable)}，营业收入增速为 ${formatPercent(revenue)}，前者高出 ${formatPercent(gap)}。按 R1 当前工程版形成待进一步了解候选；是否保留须人工复核。`;
    }
    return `${year} 年，${company}应收账款增速为 ${formatPercent(receivable)}，营业收入增速为 ${formatPercent(revenue)}。按当前两个指标的方向，本次未形成 R1 候选；这不代表不存在其他收入确认相关风险。`;
  }

  function displayRiskTitle(result) {
    if (result.rule_id === "R1" && result.status !== "candidate") {
      return "本次未出现“应收增速高于收入增速”的方向";
    }
    return result.risk_card?.title || result.rule_id;
  }

  function sourceUrl(filename, page) {
    return `${API_BASE}/api/sources/${encodeURIComponent(filename)}#page=${encodeURIComponent(page)}`;
  }

  function renderProject() {
    const period = PERIODS[state.year];
    const unit = UNIT_MAP[state.unit];
    byId("wb-current-year").value = state.year;
    byId("wb-scene").value = state.scene;
    byId("wb-amount-unit").value = state.unit;
    byId("wb-previous-year").textContent = period.previous;
    byId("wb-t0").textContent = period.t0;
    byId("wb-rag-t0").textContent = period.t0;
    byId("wb-sup-date").value = period.t0;
    byId("wb-amount-head").textContent = `数值（${unit.label}）`;
    byId("wb-data-unit-note").textContent = `显示金额单位：${unit.label}；计算时仍使用原始元值。每条来源都绑定到对应年度年报；披露时间晚于 T0 或定位不全时，对应规则不继续生成候选卡。`;
    byId("wb-data-status").textContent = `${period.data.length} / ${period.data.length} 来源完整`;
    byId("wb-data-body").innerHTML = period.data.map((row) => {
      const [field, year, value, evidenceId, filename, disclosed, pdfPage, printPage, locator] = row;
      return `
        <tr>
          <td>${escapeHtml(FIELD_LABELS[field])}</td>
          <td class="mono">${escapeHtml(year)}</td>
          <td class="numeric mono">${escapeHtml(formatAmount(value))}</td>
          <td class="source-id">${escapeHtml(evidenceId)}</td>
          <td>
            <strong>${escapeHtml(filename)}</strong>
            <div class="source-detail">披露 ${escapeHtml(disclosed)} · PDF ${escapeHtml(pdfPage)} 页 · 印刷 ${escapeHtml(printPage)} · ${escapeHtml(locator)}</div>
            <a class="source-link" href="${sourceUrl(filename, pdfPage)}" target="_blank" rel="noopener">回到 PDF ${escapeHtml(pdfPage)} 页</a>
          </td>
        </tr>`;
    }).join("");
  }

  function selectedRunnableRules() {
    return RULES.filter((rule) => rule.runnable && state.selectedRules.includes(rule.id)).map((rule) => rule.id);
  }

  function renderRuleLibrary() {
    byId("wb-rule-library").innerHTML = RULES.map((rule) => {
      const selected = state.selectedRules.includes(rule.id);
      const kind = rule.runnable ? (rule.id === "R1" ? "success" : "waiting") : "info";
      return `
        <article class="rule-record">
          <div class="rule-id">
            <input id="scope-${rule.id}" type="checkbox" data-rule-id="${rule.id}" ${selected ? "checked" : ""}>
            <label for="scope-${rule.id}"><strong>${rule.id}</strong><span class="sr-only">选择 ${escapeHtml(rule.name)}</span></label>
          </div>
          <div class="rule-copy">
            <span class="folio">${rule.id} · 规则库 v0.1</span>
            <h3>${escapeHtml(rule.name)}</h3>
            <p>${escapeHtml(rule.detail)}</p>
          </div>
          <div class="rule-meta">
            <span class="state ${kind}">${escapeHtml(rule.status)}</span>
            <small>${escapeHtml(rule.meta)}</small>
          </div>
        </article>`;
    }).join("");
    const runnable = selectedRunnableRules();
    const waiting = state.selectedRules.filter((id) => !runnable.includes(id));
    byId("wb-library-status").textContent = `${state.selectedRules.length} 项已选`;
    byId("wb-scope-note").textContent =
      `本次关注范围：${state.selectedRules.join("、") || "暂未选择"}。` +
      (runnable.length ? `${runnable.join("、")} 可进入当前本地后端。` : "当前没有可运行的已选规则。") +
      (waiting.length ? ` ${waiting.join("、")} 已记录为关注项，但缺字段、来源或专业复核，暂不计算也不生成风险卡。` : "");
    byId("run-scope").textContent = runnable.length
      ? `当前将运行 ${runnable.join("、")}；数据来自固定 DEV_T0 资料包。`
      : "当前没有已选择的可运行规则。";
    byId("wb-run-r1").disabled = !state.backendAvailable || !runnable.length;
  }

  function renderComparisonGraphic(result) {
    const keys = result.rule_id === "R1"
      ? ["revenue_growth", "ar_growth"]
      : result.status === "DATA_NOT_COMPARABLE"
        ? []
        : ["revenue_growth", "operating_cash_flow_growth"];
    const rows = keys.filter((key) => result.metrics[key] !== null && result.metrics[key] !== undefined);
    if (!rows.length) return "";
    const max = Math.max(...rows.map((key) => Math.abs(Number(result.metrics[key]))), 0.01);
    return `
      <div class="comparison-graphic" aria-label="${escapeHtml(result.rule_id)}指标比较图">
        ${rows.map((key) => {
          const value = Number(result.metrics[key]);
          const width = Math.min(48, Math.abs(value) / max * 48);
          const style = value >= 0
            ? `left:50%;width:${width}%`
            : `right:50%;width:${width}%`;
          return `<div class="comparison-row"><span>${escapeHtml(metricLabel(result, key))}</span><div class="comparison-track"><i class="comparison-bar" style="${style}"></i></div><strong>${formatPercent(value)}</strong></div>`;
        }).join("")}
      </div>`;
  }

  function renderAgentSteps(steps) {
    if (!steps?.length) return "";
    const roleMap = { challenge: "质疑", counter: "反证", review: "语义复核" };
    return `
      <ul class="agent-list" aria-label="Agent运行状态">
        ${steps.map((step) => `
          <li>
            <strong>${escapeHtml(roleMap[step.role] || step.role)}</strong>
            <span class="state ${step.status === "completed" ? "success" : step.status === "not_applicable" ? "info" : "waiting"}">${escapeHtml(statusLabel(step.status))}</span>
            <small>${escapeHtml(step.detail)}</small>
          </li>`).join("")}
      </ul>`;
  }

  function riskCardButton(result, index) {
    if (!result.risk_card) return "";
    const directionState = result.rule_id === "R1" && result.status !== "candidate"
      ? "<span class=\"state info\">未形成 R1 方向候选</span>"
      : "";
    return `
      <div class="risk-summary">
        <div><span class="folio">${escapeHtml(result.rule_id)} / RISK TASK</span><h5>${escapeHtml(displayRiskTitle(result))}</h5><p>${escapeHtml(displayObservation(result) || "等待取得更多资料后继续判断。")}</p>${directionState}</div>
        <button class="button quiet" type="button" data-risk-index="${index}">打开风险任务卡</button>
      </div>`;
  }

  function renderRun(run, humanReview = null) {
    state.run = run;
    state.humanReview = humanReview;
    byId("run-summary").hidden = false;
    byId("current-run-id").textContent = run.run_id;
    byId("source-gate-status").textContent = run.source_validation?.status === "passed" ? "通过技术检查" : "未通过";
    byId("model-check-status").textContent = statusLabel(run.model_check?.status);
    byId("review-summary-status").textContent = humanReview?.status || "未复核";
    byId("analysis-state").textContent = statusLabel(run.status);
    byId("analysis-state").className = `state ${run.status === "candidate" ? "waiting" : run.status === "SOURCE_INCOMPLETE" ? "danger" : "info"}`;
    byId("wb-sup-parent").value = run.run_id;
    byId("run-lookup-input").value = run.run_id;

    const issues = run.source_validation?.issues || [];
    const gate = byId("wb-gate");
    if (issues.length) {
      gate.className = "status-banner danger";
      gate.innerHTML = `<strong>后端来源准入未通过</strong><span>${escapeHtml(issues.join("、"))}。系统停止生成候选卡。</span>`;
    } else if (run.status === "candidate") {
      gate.className = "status-banner warning";
      gate.innerHTML = "<strong>后端计算完成，待人工复核</strong><span>候选现象不是舞弊认定，也不是审计结论。</span>";
    } else if (run.status === "DATA_NOT_COMPARABLE") {
      gate.className = "status-banner warning";
      gate.innerHTML = "<strong>后端计算完成，R2 同比不宜比较</strong><span>系统已阻断误导性现金流同比图，不按方向规则形成候选。</span>";
    } else {
      gate.className = "status-banner success";
      gate.innerHTML = "<strong>后端确定性计算完成</strong><span>本次未形成方向候选；这不代表不存在其他收入确认相关风险。</span>";
    }

    const resultHtml = run.rule_results.map((result, index) => {
      const metrics = Object.entries(result.metrics || {}).filter((entry) => entry[1] !== null && entry[1] !== undefined);
      return `
        <article class="result-record">
          <header class="result-head">
            <div><span class="folio">${escapeHtml(result.rule_id)} · ${escapeHtml(RULES.find((rule) => rule.id === result.rule_id)?.name || "确定性规则")}</span><h4>${escapeHtml(result.risk_card?.title || result.rule_id)}</h4><p>${escapeHtml(result.risk_card?.engineering_version || "当前工程版")}</p></div>
            <span class="state ${result.status === "candidate" ? "waiting" : result.status === "SOURCE_INCOMPLETE" ? "danger" : "info"}">${escapeHtml(statusLabel(result.status))}</span>
          </header>
          <div class="metric-ledger">
            ${metrics.length ? metrics.slice(0, 6).map(([key, value]) => `
              <div class="metric"><span>${escapeHtml(metricLabel(result, key))}</span><strong>${escapeHtml(metricValue(result, key, value))}</strong><small>${escapeHtml(metricFormula(result, key))}</small></div>`).join("") : `
              <div class="metric"><span>计算结果</span><strong>—</strong><small>未返回可展示指标。</small></div>`}
          </div>
          ${renderComparisonGraphic(result)}
          ${riskCardButton(result, index)}
          ${renderAgentSteps(result.agent_steps)}
        </article>`;
    }).join("");
    const sceneFollowup = state.scene === "审计计划"
      ? `<section class="scene-followup"><h4>审计计划场景的后续动作</h4><p>由项目组结合候选认定，考虑账龄分析、期后回款检查、合同关键结算条款和大额异常交易明细。</p></section>`
      : "";
    byId("wb-run-results").innerHTML = resultHtml + sceneFollowup;

    byId("wb-run-results").querySelectorAll("[data-risk-index]").forEach((button) => {
      button.addEventListener("click", () => openRiskDialog(Number(button.dataset.riskIndex)));
    });
    renderEvidenceRail(run, humanReview);
    renderLiveMatrix(run);
    hydrateReview(humanReview);
    renderHistory(run, humanReview);
    updateDeliveryControls();
    updateUrl("replace");
  }

  function renderEvidenceRail(run, humanReview) {
    const resultStates = run.rule_results.map((item) => `${item.rule_id} ${statusLabel(item.status)}`).join("；");
    const sourceState = run.source_validation?.status === "passed" ? `${run.sources.length} 条来源通过技术检查` : "来源闸门未通过";
    const gaps = run.rule_results.flatMap((item) => item.risk_card?.data_gaps || []);
    const review = humanReview?.status || "未复核";
    byId("evidence-rail").innerHTML = `
      <li><span>01</span><div><strong>规则</strong><small>${escapeHtml(resultStates)}</small></div></li>
      <li class="${run.source_validation?.status === "passed" ? "" : "pending"}"><span>02</span><div><strong>资料依据</strong><small>${escapeHtml(sourceState)}</small></div></li>
      <li><span>03</span><div><strong>资料依据缺口</strong><small>${escapeHtml(gaps.join("、") || "未返回资料缺口")}</small></div></li>
      <li class="${review === "未复核" ? "pending" : ""}"><span>04</span><div><strong>人工状态</strong><small>${escapeHtml(review)}</small></div></li>`;
  }

  function renderLiveMatrix(run) {
    const rows = run.rule_results.map((result) => {
      const normal = result.risk_card?.normal_explanations || [];
      const gaps = result.risk_card?.data_gaps || [];
      const finance = result.source_validation?.status === "passed" ? "已完成确定性计算" : "来源未通过";
      return `
        <tr>
          <th><span class="mono">${escapeHtml(result.rule_id)}</span><br><small>${escapeHtml(statusLabel(result.status))}</small></th>
          <td><span class="state ${result.source_validation?.status === "passed" ? "success" : "danger"}">${escapeHtml(finance)}</span></td>
          <td><span class="state waiting">待资料</span></td>
          <td><span class="state waiting">待资料</span></td>
          <td><span class="state info">年报来源可回查</span></td>
          <td>${escapeHtml(normal.join("；") || "未返回")}</td>
          <td>${escapeHtml(gaps.join("；") || "未返回")}</td>
        </tr>`;
    });
    byId("live-evidence-matrix").querySelector("tbody").innerHTML = rows.join("");
  }

  function openRiskDialog(index) {
    const result = state.run?.rule_results?.[index];
    if (!result?.risk_card) return;
    const card = result.risk_card;
    byId("risk-dialog-kicker").textContent = `${result.rule_id} / ${statusLabel(result.status)}`;
    byId("risk-dialog-title").textContent = displayRiskTitle(result);
    const list = (items) => items?.length ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "<p>未返回。</p>";
    const sources = state.run.sources || [];
    const isR1 = result.rule_id === "R1";
    const normalExplanation = isR1
      ? "<p>新增大客户、结算周期改变、季节性或行业账期普遍拉长等，均需取得可核验资料后判断。</p>"
      : list(card.normal_explanations);
    const dataGap = isR1
      ? "<p>账龄明细、期后回款、主要客户合同关键结算条款摘要及大额销售明细。</p>"
      : list(card.data_gaps);
    const requested = isR1
      ? "<p>账龄明细表、期后回款记录、主要合同摘要、信用政策变更说明（如有）。取得后，再由审计师结合资料继续判断。</p>"
      : list(card.requested_materials);
    byId("risk-dialog-body").innerHTML = `
      <section class="risk-detail-section"><h3>本次观察</h3><p>${escapeHtml(displayObservation(result))}</p></section>
      <section class="risk-detail-section"><h3>可能的正常解释</h3>${normalExplanation}</section>
      <section class="risk-detail-section"><h3>当前资料缺口</h3>${dataGap}</section>
      <section class="risk-detail-section"><h3>建议向客户索取</h3>${requested}</section>
      <section class="risk-detail-section"><h3>资料依据</h3>${sources.length ? `<ul>${sources.map((source) => `<li><strong class="mono">${escapeHtml(sourceHeading(source))}</strong><br><small>${escapeHtml(sourceDisplay(source))}</small></li>`).join("")}</ul>` : "<p>未返回来源。</p>"}</section>
      <section class="risk-detail-section"><h3>当前建议状态</h3><p>${escapeHtml(statusLabel(result.status))}；人工确认状态：${escapeHtml(state.humanReview?.status || "未复核")}。</p></section>`;
    byId("risk-dialog").showModal();
  }

  function hydrateReview(review) {
    const draft = safeLocalStorageGet(REVIEW_KEY, {});
    byId("wb-backend-review-status").value = review?.status || draft.status || "未复核";
    byId("wb-backend-reviewer").value = review?.reviewer || draft.reviewer || "";
    byId("wb-backend-review-note").value = review?.note || draft.note || "";
    byId("wb-backend-export-approved").checked = Boolean(review?.export_approved ?? draft.export_approved);
    byId("review-run-context").textContent = state.run ? `当前运行：${state.run.run_id}` : "尚未绑定运行。";
  }

  function updateDeliveryControls() {
    const hasRun = Boolean(state.run?.run_id);
    const approved = Boolean(
      state.humanReview &&
      state.humanReview.status !== "未复核" &&
      state.humanReview.export_approved
    );
    byId("wb-save-backend-review").disabled = !hasRun;
    byId("wb-cache-run").disabled = !approved;
    byId("wb-export-report").disabled = !approved;
    setStatePill(
      byId("delivery-state"),
      state.humanReview?.status || "未复核",
      approved ? "success" : "waiting"
    );
  }

  function renderHistory(run, review) {
    const values = [
      ["run_id", run.run_id],
      ["规则版本", run.context?.agent_prompt_version || "R1/R2 当前工程版"],
      ["数据快照", run.context?.source_snapshot_id || "—"],
      ["模型状态", statusLabel(run.model_check?.status)],
      ["资料范围", `${run.sources?.length || 0} 条已登记来源`],
      ["人工确认状态", review?.status || "未复核"],
      ["运行方式", run.context?.execution_mode === "cache_replay" ? "批准缓存回放" : run.context?.continuation_mode ? "补充资料局部重跑" : "本地确定性运行"],
    ];
    byId("run-history-detail").innerHTML = values.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd class="${label === "run_id" ? "mono" : ""}">${escapeHtml(value)}</dd></div>`).join("");
  }

  async function checkHealth() {
    try {
      const health = await api("/api/health");
      state.backendAvailable = health.service_status === "ready";
      const configured = health.model_status === "configured";
      setServiceStatus(configured ? "后端可用 · 模型已配置" : "后端可用 · 模型未配置", configured ? "success" : "pending");
      setStatePill(byId("project-health-state"), configured ? "本地后端已启动 · 模型已配置" : "本地后端已启动 · 模型未配置", configured ? "success" : "waiting");
      byId("backend-status-note").textContent = configured
        ? "后端状态：后端可用；模型配置存在，但不代表本次运行已完成三Agent；须在规则触发后查看本次状态。"
        : "后端状态：后端可用；模型配置缺失，确定性计算仍可运行，已触发规则不会生成 AI 草稿。";
    } catch (error) {
      state.backendAvailable = false;
      setServiceStatus("本地后端不可用", "danger");
      setStatePill(byId("project-health-state"), "后端未连接", "danger");
      byId("backend-status-note").textContent = "后端状态：后端未连接；R1/R2 不在网页内模拟计算。";
      const gate = byId("wb-gate");
      gate.className = "status-banner danger";
      gate.innerHTML = `<strong>未连接到本地后端</strong><span>R1/R2 不在网页内模拟计算。请启动 FastAPI 后重试。${escapeHtml(error.message)}</span>`;
    }
    renderRuleLibrary();
  }

  async function runSelectedRules() {
    const runnable = selectedRunnableRules();
    if (!runnable.length) return;
    const button = byId("wb-run-r1");
    const gate = byId("wb-gate");
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.textContent = "正在运行…";
    gate.className = "status-banner neutral";
    gate.innerHTML = `<strong>正在请求本地后端</strong><span>后端将复算 ${escapeHtml(runnable.join("、"))}、检查来源定位，并如实返回模型配置状态。</span>`;
    try {
      const run = await api("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: "STD_DEV_T0",
          current_year: Number(state.year),
          scene: state.scene,
          rule_ids: runnable,
          check_model: byId("check-model").checked,
          r2_min_gap: 0,
        }),
      });
      renderRun(run, null);
    } catch (error) {
      gate.className = "status-banner danger";
      gate.innerHTML = `<strong>规则运行失败</strong><span>${escapeHtml(error.message)}</span>`;
      setStatePill(byId("analysis-state"), "调用失败", "danger");
    } finally {
      button.removeAttribute("aria-busy");
      button.textContent = "运行已选可执行项 →";
      button.disabled = !state.backendAvailable || !selectedRunnableRules().length;
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
    } catch (error) {
      showMessage(byId("wb-backend-toast"), `读取失败：${error.message}`, "error");
    }
  }

  async function checkRagStatus() {
    try {
      const status = await api("/api/rag/status");
      state.ragStatus = status;
      const ready = status.status === "ready";
      setStatePill(
        byId("wb-rag-status"),
        ready ? `${status.chunk_count} 个原文块` : "索引未构建",
        ready ? "success" : "waiting"
      );
    } catch (_error) {
      setStatePill(byId("wb-rag-status"), "后端未连接", "danger");
    }
  }

  async function prepareRag() {
    const box = byId("wb-rag-results");
    const endBusy = beginButtonBusy(byId("wb-rag-prepare"), "正在构建索引…");
    box.innerHTML = "<div class=\"empty-state compact\"><strong>正在校验四份年报哈希并构建本地索引，请稍候…</strong></div>";
    try {
      const result = await api("/api/rag/prepare", { method: "POST" });
      state.ragStatus = result;
      setStatePill(byId("wb-rag-status"), `${result.chunk_count} 个原文块`, "success");
      box.innerHTML = `<div class="empty-state compact"><strong>本地索引可用</strong><p>${escapeHtml(result.index_version)}；来源 ${escapeHtml(result.source_count)} 份，原文块 ${escapeHtml(result.chunk_count)} 个；向量后端 ${escapeHtml(result.vector_backend)}。</p></div>`;
    } catch (error) {
      box.innerHTML = `<div class="empty-state compact"><strong>索引构建失败</strong><p>${escapeHtml(error.message)}</p></div>`;
    } finally {
      endBusy();
    }
  }

  function highlightExcerpt(excerpt, query) {
    let safe = escapeHtml(excerpt);
    const tokens = Array.from(new Set((query.match(/[\u3400-\u9fff]{2,}|[A-Za-z0-9_.%-]+/g) || [])))
      .sort((a, b) => b.length - a.length)
      .slice(0, 8);
    tokens.forEach((token) => {
      const escapedToken = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      safe = safe.replace(new RegExp(escapedToken, "gi"), (match) => `<mark>${match}</mark>`);
    });
    return safe;
  }

  function selectRagResult(index) {
    const item = state.ragResults[index];
    if (!item) return;
    document.querySelectorAll(".rag-result").forEach((button, buttonIndex) => {
      button.setAttribute("aria-pressed", buttonIndex === index ? "true" : "false");
    });
    const query = byId("wb-rag-query").value;
    byId("source-reader").innerHTML = `
      <span class="folio">${escapeHtml(item.chunk_id)} / SCORE ${escapeHtml(item.score)}</span>
      <h3>${escapeHtml(item.title || "年报原文")}</h3>
      <dl class="source-meta">
        <div><dt>文件名</dt><dd>${escapeHtml(item.source_file)}</dd></div>
        <div><dt>披露日期</dt><dd>${escapeHtml(item.disclosure_date)}</dd></div>
        <div><dt>PDF页码</dt><dd>${escapeHtml(item.pdf_page)}</dd></div>
        <div><dt>chunk ID</dt><dd>${escapeHtml(item.chunk_id)}</dd></div>
        <div><dt>T0状态</dt><dd>${escapeHtml(item.disclosure_date)} ≤ ${escapeHtml(PERIODS[state.year].t0)}</dd></div>
        <div><dt>文件哈希</dt><dd>${escapeHtml(item.source_sha256)}</dd></div>
      </dl>
      <p class="source-excerpt">${highlightExcerpt(item.excerpt, query)}</p>
      <a class="button quiet source-link-button" href="${sourceUrl(item.source_file, item.pdf_page)}" target="_blank" rel="noopener">打开原 PDF 第 ${escapeHtml(item.pdf_page)} 页</a>`;
  }

  async function retrieveRag(event) {
    event.preventDefault();
    const query = byId("wb-rag-query").value.trim();
    const box = byId("wb-rag-results");
    if (!query) {
      box.innerHTML = "<div class=\"empty-state compact\"><strong>请先填写要回查的事项。</strong></div>";
      return;
    }
    const endBusy = beginButtonBusy(byId("wb-rag-search"), "正在检索…");
    box.innerHTML = "<div class=\"empty-state compact\"><strong>正在按公司和 T0 边界检索…</strong></div>";
    try {
      const body = await api("/api/rag/retrieve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          t0: PERIODS[state.year].t0,
          rule_id: byId("wb-rag-rule").value,
          top_k: 5,
          case_id: "STD_DEV_T0",
          company_name: "西安标准工业股份有限公司（标准股份）",
        }),
      });
      byId("retrieval-id").textContent = body.retrieval_id;
      state.ragResults = body.results || [];
      if (!state.ragResults.length) {
        box.innerHTML = `<div class="empty-state compact"><strong>未命中符合公司与 T0 边界的原文。</strong><p>检索日志：${escapeHtml(body.retrieval_id)}。没有命中不会生成事实。</p></div>`;
        return;
      }
      box.innerHTML = state.ragResults.map((item, index) => `
        <button class="rag-result" type="button" data-rag-index="${index}" aria-pressed="false">
          <span class="folio">${escapeHtml(item.chunk_id)} · PDF ${escapeHtml(item.pdf_page)}</span>
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(item.source_file)} · score ${escapeHtml(item.score)}</small>
        </button>`).join("");
      box.querySelectorAll("[data-rag-index]").forEach((button) => {
        button.addEventListener("click", () => selectRagResult(Number(button.dataset.ragIndex)));
      });
      selectRagResult(0);
    } catch (error) {
      box.innerHTML = `<div class="empty-state compact"><strong>检索失败</strong><p>${escapeHtml(error.message)}</p></div>`;
    } finally {
      endBusy();
    }
  }

  async function registerSupplement(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = byId("supplement-message");
    if (!byId("wb-sup-parent").value.trim()) {
      showMessage(message, "请先回到规则结果运行 R1/R2，取得父运行编号。", "error");
      byId("wb-sup-parent").focus();
      return;
    }
    const boundRules = Array.from(form.querySelectorAll('input[name="bound_rule"]:checked')).map((input) => input.value);
    const formData = new FormData();
    formData.append("parent_run_id", byId("wb-sup-parent").value.trim());
    formData.append("material_type", byId("wb-sup-type").value);
    formData.append("authorized", String(byId("wb-sup-authorized").checked));
    formData.append("desensitized", String(byId("wb-sup-desensitized").checked));
    formData.append("bound_rule_ids", JSON.stringify(boundRules));
    formData.append("as_of_date", byId("wb-sup-date").value);
    formData.append("note", byId("wb-sup-note").value);
    formData.append("structured_json", byId("wb-sup-json").value);
    const file = byId("wb-sup-file").files[0];
    if (file) formData.append("file", file);
    showMessage(message, "正在执行授权、脱敏、类型、哈希和规则绑定预检…");
    const endBusy = beginButtonBusy(byId("wb-sup-register"), "正在预检…");
    try {
      const body = await api("/api/supplements", { method: "POST", body: formData });
      state.supplementId = body.supplement_id;
      const supplementStatusLabel = {
        ready_for_rerun: "预检通过，可局部重跑",
        registered_only: "已登记，无可靠结构化字段",
        rejected: "预检拒绝",
      }[body.status] || body.status;
      setStatePill(byId("wb-sup-state"), supplementStatusLabel, body.status === "ready_for_rerun" ? "success" : body.status === "rejected" ? "danger" : "waiting");
      byId("wb-sup-rerun").disabled = body.status !== "ready_for_rerun";
      byId("supplement-result").hidden = false;
      byId("parent-run-label").textContent = body.parent_run_id;
      byId("supplement-id-label").textContent = body.supplement_id;
      byId("rerun-scope-label").textContent = body.status === "ready_for_rerun" ? `仅 ${body.bound_rule_ids.join("、")} 结构化字段` : "不可重跑";
      const issues = body.issues?.join("；") || body.boundary;
      showMessage(message, `${body.supplement_id} · ${body.status}。识别字段：${Object.keys(body.structured_fields || {}).join("、") || "无"}。${issues}`, body.status === "rejected" ? "error" : "success");
    } catch (error) {
      showMessage(message, `补充资料登记失败：${error.message}`, "error");
    } finally {
      endBusy();
    }
  }

  async function rerunSupplement() {
    if (!state.supplementId) {
      showMessage(byId("supplement-message"), "没有可重跑的补充资料记录。", "error");
      return;
    }
    const endBusy = beginButtonBusy(byId("wb-sup-rerun"), "正在局部重跑…");
    showMessage(byId("supplement-message"), "正在执行补充资料局部重跑…");
    try {
      const run = await api(`/api/supplements/${encodeURIComponent(state.supplementId)}/rerun`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ check_model: false }),
      });
      renderRun(run, null);
      showMessage(byId("supplement-message"), `局部重跑完成：${run.run_id}。`, "success");
      showView("analysis");
    } catch (error) {
      showMessage(byId("supplement-message"), `局部重跑失败：${error.message}`, "error");
    } finally {
      endBusy();
    }
  }

  async function saveReview(event) {
    event.preventDefault();
    if (!state.run?.run_id) return;
    const endBusy = beginButtonBusy(byId("wb-save-backend-review"), "正在保存…");
    const review = {
      status: byId("wb-backend-review-status").value,
      reviewer: byId("wb-backend-reviewer").value.trim(),
      note: byId("wb-backend-review-note").value.trim(),
      reviewed_at: new Date().toISOString(),
      export_approved: byId("wb-backend-export-approved").checked,
    };
    safeLocalStorageSet(REVIEW_KEY, review);
    showMessage(byId("wb-backend-toast"), "正在保存本次人工复核…");
    try {
      const stored = await api(`/api/runs/${encodeURIComponent(state.run.run_id)}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(review),
      });
      renderRun(stored.run, stored.human_review);
      showMessage(byId("wb-backend-toast"), "本次人工复核已保存。", "success");
    } catch (error) {
      showMessage(byId("wb-backend-toast"), `复核保存失败：${error.message}`, "error");
    } finally {
      endBusy();
      updateDeliveryControls();
    }
  }

  async function cacheRun() {
    if (!state.run?.run_id) return;
    const endBusy = beginButtonBusy(byId("wb-cache-run"), "正在写入缓存…");
    showMessage(byId("delivery-message"), "正在写入人工批准缓存…");
    try {
      const result = await api(`/api/runs/${encodeURIComponent(state.run.run_id)}/cache`, { method: "POST" });
      byId("cache-id-input").value = result.cache_id;
      showMessage(byId("delivery-message"), `${result.cache_id} 已写入。${result.boundary}`, "success");
    } catch (error) {
      showMessage(byId("delivery-message"), `缓存写入失败：${error.message}`, "error");
    } finally {
      endBusy();
      updateDeliveryControls();
    }
  }

  async function replayCache() {
    const cacheId = byId("cache-id-input").value.trim();
    if (!cacheId) {
      showMessage(byId("delivery-message"), "请先填写已批准缓存编号。", "error");
      return;
    }
    const endBusy = beginButtonBusy(byId("cache-replay-button"), "正在回放…");
    showMessage(byId("delivery-message"), "正在回放已批准缓存；不会重新调用模型。");
    try {
      const run = await api(`/api/cache/${encodeURIComponent(cacheId)}/replay`, { method: "POST" });
      renderRun(run, null);
      showMessage(byId("delivery-message"), `缓存回放完成：${run.run_id}。本次没有重新调用模型。`, "success");
      showView("analysis");
    } catch (error) {
      showMessage(byId("delivery-message"), `缓存回放失败：${error.message}`, "error");
    } finally {
      endBusy();
    }
  }

  async function exportReport() {
    if (!state.run?.run_id) return;
    const endBusy = beginButtonBusy(byId("wb-export-report"), "正在生成…");
    showMessage(byId("delivery-message"), "正在生成 Word 备忘录…");
    try {
      const response = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(state.run.run_id)}/report.docx`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${state.run.run_id}_预审风险备忘录.docx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showMessage(byId("delivery-message"), "Word 备忘录已生成并开始下载。", "success");
    } catch (error) {
      showMessage(byId("delivery-message"), `导出失败：${error.message}`, "error");
    } finally {
      endBusy();
      updateDeliveryControls();
    }
  }

  function bindEvents() {
    document.querySelectorAll("[data-view]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        showView(link.dataset.view);
      });
    });
    document.querySelectorAll("[data-wb-step]").forEach((button) => {
      button.addEventListener("click", () => handleLegacyStep(button.dataset.wbStep));
      button.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const tabs = Array.from(document.querySelectorAll("[data-wb-step]"));
        const index = tabs.indexOf(button);
        const targetIndex = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : event.key === "ArrowRight" ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length;
        tabs[targetIndex].focus();
        handleLegacyStep(tabs[targetIndex].dataset.wbStep);
      });
    });
    document.querySelectorAll("[data-wb-go]").forEach((button) => {
      button.addEventListener("click", () => handleLegacyStep(button.dataset.wbGo));
    });
    byId("mobile-nav-toggle").addEventListener("click", () => {
      const sidebar = byId("primary-navigation");
      const open = sidebar.classList.toggle("open");
      byId("mobile-nav-toggle").setAttribute("aria-expanded", String(open));
      syncMobileNavigationAccessibility(open);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      const sidebar = byId("primary-navigation");
      if (!sidebar.classList.contains("open")) return;
      closeMobileNavigation();
      byId("mobile-nav-toggle").focus();
    });
    window.addEventListener("resize", () => {
      const open = byId("primary-navigation").classList.contains("open");
      syncMobileNavigationAccessibility(open);
    });
    byId("wb-current-year").addEventListener("change", (event) => {
      state.year = event.target.value;
      renderProject();
      updateUrl("replace");
    });
    byId("wb-scene").addEventListener("change", (event) => {
      state.scene = event.target.value;
      updateUrl("replace");
    });
    byId("wb-amount-unit").addEventListener("change", (event) => {
      state.unit = event.target.value;
      renderProject();
    });
    byId("wb-load-sample").addEventListener("click", () => {
      state.year = "2025";
      state.scene = "审计计划";
      state.unit = "yuan";
      renderProject();
      updateUrl("replace");
      setStatePill(byId("project-state"), "开发样例已载入", "info");
    });
    byId("wb-rule-library").addEventListener("change", (event) => {
      const input = event.target.closest("[data-rule-id]");
      if (!input) return;
      if (input.checked && !state.selectedRules.includes(input.dataset.ruleId)) state.selectedRules.push(input.dataset.ruleId);
      if (!input.checked) state.selectedRules = state.selectedRules.filter((id) => id !== input.dataset.ruleId);
      state.selectedRules.sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
      safeLocalStorageSet(SCOPE_KEY, state.selectedRules);
      renderRuleLibrary();
      updateUrl("replace");
    });
    byId("wb-run-r1").addEventListener("click", runSelectedRules);
    byId("wb-rag-prepare").addEventListener("click", prepareRag);
    byId("rag-form").addEventListener("submit", retrieveRag);
    byId("supplement-form").addEventListener("submit", registerSupplement);
    byId("wb-sup-rerun").addEventListener("click", rerunSupplement);
    byId("review-form").addEventListener("submit", saveReview);
    byId("wb-save-local-review").addEventListener("click", () => {
      const draft = {
        status: byId("wb-backend-review-status").value,
        reviewer: byId("wb-backend-reviewer").value,
        note: byId("wb-backend-review-note").value,
        export_approved: byId("wb-backend-export-approved").checked,
      };
      safeLocalStorageSet(REVIEW_KEY, draft);
      showMessage(byId("wb-backend-toast"), "本机复核草稿已保存；这不等于后端人工复核已提交。", "success");
    });
    byId("review-form").addEventListener("input", () => {
      safeLocalStorageSet(REVIEW_KEY, {
        status: byId("wb-backend-review-status").value,
        reviewer: byId("wb-backend-reviewer").value,
        note: byId("wb-backend-review-note").value,
        export_approved: byId("wb-backend-export-approved").checked,
      });
    });
    byId("run-lookup-form").addEventListener("submit", (event) => {
      event.preventDefault();
      loadRun(byId("run-lookup-input").value.trim());
    });
    byId("wb-cache-run").addEventListener("click", cacheRun);
    byId("cache-replay-button").addEventListener("click", replayCache);
    byId("wb-export-report").addEventListener("click", exportReport);
    byId("risk-dialog").querySelector("[data-close-dialog]").addEventListener("click", () => byId("risk-dialog").close());
    byId("risk-dialog").addEventListener("click", (event) => {
      if (event.target === byId("risk-dialog")) byId("risk-dialog").close();
    });
    window.addEventListener("popstate", () => {
      readUrlState();
      renderProject();
      renderRuleLibrary();
      showView(state.view, { history: false });
    });
  }

  async function initialize() {
    const storedScope = safeLocalStorageGet(SCOPE_KEY, ["R1", "R2"]);
    if (Array.isArray(storedScope)) {
      const valid = storedScope.filter((id) => RULES.some((rule) => rule.id === id));
      if (valid.length) state.selectedRules = valid;
    }
    const requestedRun = readUrlState();
    bindEvents();
    syncMobileNavigationAccessibility(false);
    renderProject();
    renderRuleLibrary();
    hydrateReview(null);
    showView(state.view, { history: false, focus: false });
    updateUrl("replace");
    await Promise.all([checkHealth(), checkRagStatus()]);
    if (requestedRun) await loadRun(requestedRun);
  }

  initialize();
}());
