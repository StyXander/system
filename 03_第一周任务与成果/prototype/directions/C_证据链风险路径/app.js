/*
 * 审迹智链 · 三方向共用逻辑
 * 计算口径与原 prototype/app.js 保持一致，不改公式、不自定阈值。
 * 仅扩展：多视图导航、四维矩阵状态、下钻面板、系统状态、本地导出。
 */

const STORAGE_KEY = "audittrace_week1_state_v1";
const CACHE_FLAG_KEY = "audittrace_week1_cache_playback";

const fieldDefinitions = [
  { id: "revenue_current", label: "本年营业收入", yearType: "current", dim: "财务" },
  { id: "revenue_previous", label: "上年营业收入", yearType: "previous", dim: "财务" },
  { id: "ar_current", label: "本年应收账款", yearType: "current", dim: "财务" },
  { id: "ar_previous", label: "上年应收账款", yearType: "previous", dim: "财务" },
];

const defaultState = {
  project: {
    companyName: "",
    analysisDate: "",
    scene: "新客户业务承接",
    industry: "",
    currentYear: "",
    previousYear: "",
    amountUnit: "万元",
  },
  data: Object.fromEntries(
    fieldDefinitions.map((field) => [
      field.id,
      {
        value: "",
        sourceFile: "",
        disclosureDate: "",
        pdfPage: "",
        printPage: "",
        locator: "",
      },
    ]),
  ),
  review: {
    status: "未复核",
    note: "",
  },
};

let state = loadState();
let toastTimer;
let cachePlayback = false;

function $(selector) {
  return document.querySelector(selector);
}

function $all(selector) {
  return [...document.querySelectorAll(selector)];
}

function el(id) {
  return document.getElementById(id);
}

function setText(id, text) {
  const node = el(id);
  if (node) node.textContent = text;
}

function setHtml(id, html) {
  const node = el(id);
  if (node) node.innerHTML = html;
}

function cloneDefaultState() {
  return JSON.parse(JSON.stringify(defaultState));
}

function loadState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return cloneDefaultState();
    const parsed = JSON.parse(saved);
    cachePlayback = true;
    sessionStorage.setItem(CACHE_FLAG_KEY, "1");

    const merged = cloneDefaultState();
    merged.project = { ...merged.project, ...(parsed.project || {}) };
    merged.review = { ...merged.review, ...(parsed.review || {}) };
    fieldDefinitions.forEach((field) => {
      merged.data[field.id] = {
        ...merged.data[field.id],
        ...((parsed.data || {})[field.id] || {}),
      };
    });
    return merged;
  } catch (error) {
    console.warn("本地数据读取失败，已使用空白状态。", error);
    return cloneDefaultState();
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  cachePlayback = false;
  sessionStorage.removeItem(CACHE_FLAG_KEY);
}

function showToast(message) {
  const toast = $("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2400);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setInputValuesFromState() {
  if (el("company-name")) $("#company-name").value = state.project.companyName;
  if (el("analysis-date")) $("#analysis-date").value = state.project.analysisDate;
  if (el("analysis-scene")) $("#analysis-scene").value = state.project.scene;
  if (el("industry")) $("#industry").value = state.project.industry;
  if (el("current-year")) $("#current-year").value = state.project.currentYear;
  if (el("previous-year")) $("#previous-year").value = state.project.previousYear;
  if (el("amount-unit")) $("#amount-unit").value = state.project.amountUnit;
  if (el("review-status")) $("#review-status").value = state.review.status;
  if (el("review-note")) $("#review-note").value = state.review.note;
}

function readProjectForm() {
  if (!el("company-name")) return;
  state.project = {
    companyName: $("#company-name").value.trim(),
    analysisDate: $("#analysis-date").value,
    scene: $("#analysis-scene").value,
    industry: $("#industry").value.trim(),
    currentYear: $("#current-year").value.trim(),
    previousYear: $("#previous-year").value.trim(),
    amountUnit: $("#amount-unit").value,
  };
}

function renderProjectSummary() {
  const project = state.project;
  setText("project-summary-title", project.companyName || "尚未填写公司名称");
  setText("project-summary-scene", project.scene);
  setText("project-summary-date", project.analysisDate || "待填写");
  setText("project-summary-industry", project.industry || "待填写");
  setText("meta-company", project.companyName || "未命名项目");
  setText("meta-scene", project.scene || "—");
  setText("meta-date", project.analysisDate || "截止日未填");
}

function projectFieldsComplete() {
  return Boolean(
    state.project.companyName &&
      state.project.analysisDate &&
      state.project.currentYear &&
      state.project.previousYear,
  );
}

function getYearLabel(field) {
  const year = field.yearType === "current" ? state.project.currentYear : state.project.previousYear;
  return year || (field.yearType === "current" ? "本年" : "上年");
}

function rowCompleteness(row) {
  const required = [
    row.value,
    row.sourceFile,
    row.disclosureDate,
    row.pdfPage,
    row.printPage,
    row.locator,
  ];
  const count = required.filter((value) => String(value).trim() !== "").length;
  if (count === 0) return "empty";
  if (count === required.length) return "complete";
  return "partial";
}

function numericValue(fieldId) {
  const raw = state.data[fieldId].value;
  if (raw === "") return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function percent(value) {
  return `${(value * 100).toFixed(2)}%`;
}

function allCoreNumbersValid() {
  const values = [
    numericValue("revenue_current"),
    numericValue("revenue_previous"),
    numericValue("ar_current"),
    numericValue("ar_previous"),
  ];
  return values.every((value) => value !== null) && values[1] !== 0 && values[3] !== 0;
}

function hasInvalidNumbers() {
  return fieldDefinitions.some((field) => {
    const raw = state.data[field.id].value;
    if (raw === "") return false;
    return !Number.isFinite(Number(raw));
  });
}

function hasZeroDenominator() {
  const prevRev = numericValue("revenue_previous");
  const prevAr = numericValue("ar_previous");
  return prevRev === 0 || prevAr === 0;
}

function allEvidenceRowsComplete() {
  return fieldDefinitions.every((field) => rowCompleteness(state.data[field.id]) === "complete");
}

function countCompleteRows() {
  return fieldDefinitions.filter((field) => rowCompleteness(state.data[field.id]) === "complete").length;
}

function computeMetrics() {
  if (!allCoreNumbersValid()) return null;
  const revenueGrowth =
    (numericValue("revenue_current") - numericValue("revenue_previous")) /
    numericValue("revenue_previous");
  const arGrowth =
    (numericValue("ar_current") - numericValue("ar_previous")) /
    numericValue("ar_previous");
  const gap = arGrowth - revenueGrowth;
  return { revenueGrowth, arGrowth, gap };
}

/* ---------- 系统状态：空白 / 资料不全 / 校验失败 / 缓存回放 / 可计算 ---------- */
function getSystemMode() {
  if (hasInvalidNumbers()) return "validation_fail";
  if (hasZeroDenominator()) return "validation_fail";
  if (!projectFieldsComplete() && countCompleteRows() === 0) return "blank";
  if (!allCoreNumbersValid()) return "incomplete";
  if (!allEvidenceRowsComplete()) return "evidence_gap";
  if (cachePlayback || sessionStorage.getItem(CACHE_FLAG_KEY) === "1") return "cache_playback";
  if (state.review.status !== "未复核") return "reviewed";
  return "ready";
}

function renderSystemMode() {
  const mode = getSystemMode();
  const labels = {
    blank: "空白项目",
    incomplete: "资料不全",
    evidence_gap: "来源缺口",
    validation_fail: "校验失败",
    cache_playback: "缓存回放",
    ready: "可人工复核",
    reviewed: "已记录复核",
  };
  const hints = {
    blank: "尚未建立可分析输入。请先完成项目设定与年报四项数字。",
    incomplete: "核心金额未齐或上年数为空。系统只做确定性计算，不会补造数字。",
    evidence_gap: "数字可计算，但来源定位未齐，不能形成可返回原件的候选风险卡。",
    validation_fail: "存在非法数字或上年数为 0（分母无效）。请回到资料预检修正。",
    cache_playback: "当前内容来自本浏览器历史缓存回放，非实时模型结果。修改并保存后退出回放。",
    ready: "计算与来源准入已通过，等待人工保留/降级/暂缓。",
    reviewed: "已记录人工复核状态。导出仍须人工确认后使用。",
  };

  $all("[data-system-mode]").forEach((node) => {
    node.dataset.mode = mode;
    node.textContent = labels[mode];
  });
  $all("[data-system-hint]").forEach((node) => {
    node.textContent = hints[mode];
  });

  const banner = el("system-banner");
  if (banner) {
    banner.dataset.mode = mode;
    banner.classList.remove("hidden");
  }
}

function renderDataTable() {
  const body = el("data-table-body");
  if (!body) return;

  body.innerHTML = fieldDefinitions
    .map((field) => {
      const row = state.data[field.id];
      return `
        <tr data-field-id="${field.id}">
          <td>${field.label}</td>
          <td class="year-cell">${escapeHtml(getYearLabel(field))}</td>
          <td><input data-key="value" type="number" step="any" value="${escapeHtml(row.value)}" placeholder="待B填写"></td>
          <td><input data-key="sourceFile" type="text" value="${escapeHtml(row.sourceFile)}" placeholder="年报文件名"></td>
          <td><input data-key="disclosureDate" type="date" value="${escapeHtml(row.disclosureDate)}"></td>
          <td><input data-key="pdfPage" type="text" value="${escapeHtml(row.pdfPage)}" placeholder="例如 88"></td>
          <td><input data-key="printPage" type="text" value="${escapeHtml(row.printPage)}" placeholder="页码或原件未标注"></td>
          <td><input data-key="locator" type="text" value="${escapeHtml(row.locator)}" placeholder="例如 合并资产负债表"></td>
          <td><span class="row-status">待接入</span></td>
        </tr>
      `;
    })
    .join("");

  $all("#data-table-body input").forEach((input) => {
    input.addEventListener("input", () => {
      readDataTable();
      updateDataStatuses();
      renderOverview();
      renderSystemMode();
      renderPath();
    });
  });
  updateDataStatuses();
}

function readDataTable() {
  $all("#data-table-body tr").forEach((rowElement) => {
    const fieldId = rowElement.dataset.fieldId;
    rowElement.querySelectorAll("input[data-key]").forEach((input) => {
      state.data[fieldId][input.dataset.key] = input.value.trim();
    });
  });
}

function updateDataStatuses() {
  let complete = 0;
  $all("#data-table-body tr").forEach((rowElement) => {
    const fieldId = rowElement.dataset.fieldId;
    const status = rowCompleteness(state.data[fieldId]);
    const badge = rowElement.querySelector(".row-status");
    if (!badge) return;
    badge.className = `row-status ${status === "empty" ? "" : status}`;
    if (status === "complete") {
      badge.textContent = "已录入，待复核";
      complete += 1;
    } else if (status === "partial") {
      badge.textContent = "部分录入";
    } else {
      badge.textContent = "待接入";
    }
  });

  setText("complete-count", `${complete} / 4`);
  const overall = el("data-overall-status");
  if (overall) {
    if (hasInvalidNumbers() || hasZeroDenominator()) {
      overall.className = "state-chip fail";
      overall.textContent = "校验失败";
    } else if (complete === 4) {
      overall.className = "state-chip complete";
      overall.textContent = "4项已录入，待复核";
    } else if (complete > 0) {
      overall.className = "state-chip draft";
      overall.textContent = `${complete}项完整，其余待补`;
    } else {
      overall.className = "state-chip pending";
      overall.textContent = "待B接入";
    }
  }

  // 卡片式预检（方向A/C可能使用）
  $all("[data-field-card]").forEach((card) => {
    const id = card.dataset.fieldCard;
    const status = rowCompleteness(state.data[id] || {});
    card.dataset.status = status;
    const badge = card.querySelector(".card-status");
    if (badge) {
      badge.textContent =
        status === "complete" ? "已录入，待复核" : status === "partial" ? "部分录入" : "待接入";
    }
  });

  renderWorkflowState();
  renderSystemMode();
}

function renderMetrics() {
  const metrics = computeMetrics();
  if (!metrics) {
    setText("revenue-growth", "—");
    setText("ar-growth", "—");
    setText("growth-gap", "—");
    setText("formula-revenue", "待齐四个金额后再计算");
    setText("formula-ar", "待齐四个金额后再计算");
    setText("formula-gap", "待齐四个金额后再计算");
    return null;
  }
  setText("revenue-growth", percent(metrics.revenueGrowth));
  setText("ar-growth", percent(metrics.arGrowth));
  setText(
    "growth-gap",
    `${metrics.gap >= 0 ? "+" : ""}${(metrics.gap * 100).toFixed(2)}个百分点`,
  );
  setText(
    "formula-revenue",
    `（${numericValue("revenue_current")} − ${numericValue("revenue_previous")}）÷ ${numericValue("revenue_previous")} = ${percent(metrics.revenueGrowth)}`,
  );
  setText(
    "formula-ar",
    `（${numericValue("ar_current")} − ${numericValue("ar_previous")}）÷ ${numericValue("ar_previous")} = ${percent(metrics.arGrowth)}`,
  );
  setText(
    "formula-gap",
    `应收增速 − 收入增速 = ${percent(metrics.arGrowth)} − ${percent(metrics.revenueGrowth)} = ${metrics.gap >= 0 ? "+" : ""}${(metrics.gap * 100).toFixed(2)} 个百分点`,
  );
  return metrics;
}

/* 四维交叉验证矩阵：只标“可得/部分/不可评价”，不打假风险分 */
function renderOverview() {
  const metrics = renderMetrics();
  const complete = countCompleteRows();
  const financeStatus = hasInvalidNumbers() || hasZeroDenominator()
    ? "校验失败"
    : allCoreNumbersValid()
      ? "可得"
      : complete > 0
        ? "部分可得"
        : "不可评价";
  const sourceStatus = allEvidenceRowsComplete()
    ? "可得"
    : complete > 0
      ? "部分可得"
      : "不可评价";

  // 业务规模 / 行业惯例 / 管理层文字：首版无额外输入，明确“不可评价/待接入”
  const cells = {
    "matrix-finance": financeStatus,
    "matrix-business": "不可评价",
    "matrix-industry": "不可评价",
    "matrix-narrative": "不可评价",
    "matrix-source": sourceStatus,
  };

  Object.entries(cells).forEach(([id, value]) => {
    const node = el(id);
    if (!node) return;
    node.textContent = value;
    node.dataset.status =
      value === "可得" ? "ok" : value === "部分可得" ? "partial" : value === "校验失败" ? "fail" : "na";
  });

  setText(
    "overview-summary",
    !projectFieldsComplete()
      ? "项目边界未齐，矩阵仅作空工作底稿。"
      : !allCoreNumbersValid()
        ? "财务维度尚未形成可计算输入；业务/行业/叙述维度待规则与资料接入。"
        : !allEvidenceRowsComplete()
          ? "财务维度已可计算，但来源约束未过；候选风险不得跳过原件定位。"
          : metrics && metrics.gap > 0
            ? "R1 方向出现：应收增速高于收入增速。此为候选现象，非舞弊认定。"
            : "R1 方向未出现应收增速高于收入增速。不代表不存在其他风险。",
  );

  // 风险总览列表（仅 R1 当前可运行）
  const list = el("risk-overview-list");
  if (list) {
    if (!allCoreNumbersValid() || !allEvidenceRowsComplete()) {
      list.innerHTML = `<div class="empty-inline">尚无满足来源准入的候选风险卡。请先完成资料预检。</div>`;
    } else if (metrics && metrics.gap > 0) {
      list.innerHTML = `
        <button class="risk-list-item" data-go="risk-view" type="button">
          <span class="code">R1</span>
          <span class="title">应收账款增速高于收入增速，需进一步了解</span>
          <span class="meta">差额 ${metrics.gap >= 0 ? "+" : ""}${(metrics.gap * 100).toFixed(2)} 个百分点 · 待人工复核</span>
        </button>`;
      list.querySelector("[data-go]")?.addEventListener("click", () => goToView("risk-view"));
    } else {
      list.innerHTML = `<div class="empty-inline">已完成 R1 计算，当前方向未形成候选；R2–R8 待规则接入。</div>`;
    }
  }
}

function renderEvidenceList() {
  const list = el("evidence-list");
  if (!list) return;
  list.innerHTML = "";
  fieldDefinitions.forEach((field) => {
    const row = state.data[field.id];
    const item = document.createElement("div");
    item.className = "evidence-item";
    const label = document.createElement("strong");
    label.textContent = `${field.label}：${row.value || "待填写"} ${state.project.amountUnit}`;
    const source = document.createElement("span");
    source.textContent = [
      row.sourceFile || "来源文件待填",
      row.disclosureDate ? `披露于${row.disclosureDate}` : "披露日期待填",
      row.pdfPage ? `PDF第${row.pdfPage}页` : "PDF页码待填",
      row.printPage ? `印刷页码：${row.printPage}` : "印刷页码待填",
      row.locator || "原文位置待填",
    ].join("｜");
    item.append(label, source);
    list.append(item);
  });
}

function renderGaps() {
  const box = el("gap-list");
  if (!box) return;
  const gaps = [];
  fieldDefinitions.forEach((field) => {
    const row = state.data[field.id];
    const status = rowCompleteness(row);
    if (status !== "complete") {
      gaps.push(`${field.label}：来源定位${status === "empty" ? "未接入" : "不完整"}`);
    }
  });
  if (!allCoreNumbersValid()) gaps.unshift("核心金额未齐或分母无效，无法完成增长率计算");
  if (state.project.scene !== "审计计划") {
    // 业务缺口固定文案仍展示在风险卡中
  }
  const fixed = [
    "客户账龄和信用期变化明细",
    "期后回款情况",
    "主要合同结算条款",
    "大额销售明细",
  ];
  box.innerHTML = `
    <div class="gap-group"><h5>输入/来源缺口</h5><ul>${
      gaps.length ? gaps.map((g) => `<li>${escapeHtml(g)}</li>`).join("") : "<li>四项数字与来源定位已录入（仍待人工回原件复核）</li>"
    }</ul></div>
    <div class="gap-group"><h5>业务资料缺口（固定清单）</h5><ul>${fixed.map((g) => `<li>${g}</li>`).join("")}</ul></div>
  `;
}

function renderRiskCard() {
  const riskEmpty = el("risk-empty");
  const riskCard = el("risk-card");
  const riskStatus = el("risk-status");
  const planning = el("planning-only");
  if (planning) planning.classList.toggle("hidden", state.project.scene !== "审计计划");

  const metrics = renderMetrics();
  renderGaps();
  renderOverview();
  renderSystemMode();

  if (!riskEmpty || !riskCard || !riskStatus) return;

  if (hasInvalidNumbers() || hasZeroDenominator()) {
    riskStatus.className = "state-chip fail";
    riskStatus.textContent = "校验失败";
    setText("risk-empty-title", "计算校验未通过");
    setText(
      "risk-empty-text",
      hasZeroDenominator()
        ? "上年收入或上年应收账款为 0，不能作为增长率分母。请修正资料后重试。"
        : "存在无法解析为数字的金额字段。请回到资料预检修正。",
    );
    riskEmpty.classList.remove("hidden");
    riskCard.classList.add("hidden");
    return;
  }

  if (!allCoreNumbersValid()) {
    riskStatus.className = "state-chip pending";
    riskStatus.textContent = "待数据接入";
    setText("risk-empty-title", "等待 B 的年报数据");
    setText(
      "risk-empty-text",
      "录入本年/上年收入和应收账款后，这里才会生成基于真实数字的现象描述。上年数为 0 时也会停止计算。",
    );
    riskEmpty.classList.remove("hidden");
    riskCard.classList.add("hidden");
    return;
  }

  if (!allEvidenceRowsComplete()) {
    riskStatus.className = "state-chip pending";
    riskStatus.textContent = "待补全来源位置";
    setText("risk-empty-title", "数字已可计算，来源仍未补全");
    setText(
      "risk-empty-text",
      "请返回资料预检，为四个数字补齐文件名、披露日期、PDF 页码、印刷页码和原文位置。补齐后可生成候选现象，但仍须另一名成员回到原件核对。",
    );
    riskEmpty.classList.remove("hidden");
    riskCard.classList.add("hidden");
    return;
  }

  const company = state.project.companyName || "本开发样例";
  const currentYear = state.project.currentYear || "本年";

  if (metrics.gap > 0) {
    setText("risk-card-title", "应收账款增速高于收入增速，需进一步了解");
    setText(
      "risk-observation",
      `${currentYear}，${company}应收账款增速为${percent(metrics.arGrowth)}，营业收入增速为${percent(metrics.revenueGrowth)}，前者高出${(metrics.gap * 100).toFixed(2)}个百分点。该差额只是一项计算结果，是否达到提醒阈值仍待A确认。`,
    );
    riskStatus.className = "state-chip draft";
    riskStatus.textContent = "候选现象，待A与人工复核";
  } else {
    setText("risk-card-title", "本样例未出现应收增速高于收入增速的方向");
    setText(
      "risk-observation",
      `${currentYear}，${company}应收账款增速为${percent(metrics.arGrowth)}，营业收入增速为${percent(metrics.revenueGrowth)}。按当前两个指标的方向，本次未形成“应收账款增速高于收入增速”的 R1 候选；这只是一项规则计算状态，尚不能据此评价其他风险。`,
    );
    riskStatus.className = "state-chip complete";
    riskStatus.textContent = "仅完成计算，未形成R1候选";
  }

  renderEvidenceList();
  riskEmpty.classList.add("hidden");
  riskCard.classList.remove("hidden");
}

function renderPath() {
  // 方向 C：路径节点状态
  const nodes = {
    "path-project": projectFieldsComplete() ? "done" : "todo",
    "path-data": allEvidenceRowsComplete() ? "done" : countCompleteRows() > 0 ? "partial" : "todo",
    "path-calc": allCoreNumbersValid() ? "done" : hasInvalidNumbers() || hasZeroDenominator() ? "fail" : "todo",
    "path-matrix": allCoreNumbersValid() ? "partial" : "todo",
    "path-risk": allCoreNumbersValid() && allEvidenceRowsComplete() ? "done" : "todo",
    "path-review": state.review.status !== "未复核" ? "done" : "todo",
  };
  Object.entries(nodes).forEach(([id, status]) => {
    const node = el(id);
    if (!node) return;
    node.dataset.status = status;
  });
}

function renderReviewPanel() {
  setText("review-export-status", state.review.status || "未复核");
  setText(
    "review-export-note",
    state.review.note || "尚未填写复核说明。导出内容仅为本地草稿，不构成审计意见。",
  );
  const gate = el("export-gate");
  if (gate) {
    const blocked = state.review.status === "未复核" || !allEvidenceRowsComplete() || !allCoreNumbersValid();
    gate.dataset.blocked = blocked ? "true" : "false";
    setText(
      "export-gate-text",
      blocked
        ? "导出闸门未开：需完成可计算数字、来源定位，并将复核状态改为保留/降级/暂缓之一。"
        : "导出闸门已开：可下载本地预审草稿（非正式报告）。",
    );
  }
}

function renderWorkflowState(activeView = document.querySelector(".view.active")?.id) {
  const completedViews = new Set();
  if (projectFieldsComplete()) completedViews.add("project-view");
  if (allEvidenceRowsComplete()) completedViews.add("data-view");
  if (allCoreNumbersValid()) completedViews.add("overview-view");
  if (allCoreNumbersValid() && allEvidenceRowsComplete()) completedViews.add("risk-view");
  if (state.review.status !== "未复核") completedViews.add("review-view");

  $all(".workflow-step, .nav-item, .path-step, [data-view]").forEach((step) => {
    if (!step.dataset.view) return;
    step.classList.toggle("active", step.dataset.view === activeView);
    step.classList.toggle("completed", completedViews.has(step.dataset.view));
  });
  renderPath();
}

function goToView(viewId) {
  $all(".view").forEach((view) => view.classList.toggle("active", view.id === viewId));
  $all("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === viewId));

  const headingMap = {
    "project-view": "项目设定",
    "data-view": "资料预检",
    "overview-view": "风险总览与交叉验证",
    "risk-view": "R1 风险任务卡",
    "review-view": "人工确认与导出",
  };
  setText("page-heading", headingMap[viewId] || "预审工作台");

  if (viewId === "overview-view") renderOverview();
  if (viewId === "risk-view") renderRiskCard();
  if (viewId === "review-view") {
    renderRiskCard();
    renderReviewPanel();
  }

  renderWorkflowState(viewId);
  renderSystemMode();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function switchDrill(tab) {
  $all("[data-drill-tab]").forEach((btn) => btn.classList.toggle("active", btn.dataset.drillTab === tab));
  $all("[data-drill-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.drillPanel === tab);
    panel.classList.toggle("hidden", panel.dataset.drillPanel !== tab);
  });
}

function buildExportText() {
  const metrics = computeMetrics();
  const lines = [
    "审迹智链 · 预审风险草稿（本地导出）",
    "================================",
    "声明：本文件仅用公开资料形成待核查线索，不认定舞弊、不形成审计意见、不提供投资建议。",
    "",
    `公司：${state.project.companyName || "未填"}`,
    `场景：${state.project.scene}`,
    `分析截止日：${state.project.analysisDate || "未填"}`,
    `行业：${state.project.industry || "未填"}`,
    `年度：${state.project.currentYear || "本年"} / ${state.project.previousYear || "上年"}`,
    `金额单位：${state.project.amountUnit}`,
    "",
    "—— 确定性计算 ——",
    metrics
      ? `收入增长率：${percent(metrics.revenueGrowth)}\n应收账款增长率：${percent(metrics.arGrowth)}\n差额：${metrics.gap >= 0 ? "+" : ""}${(metrics.gap * 100).toFixed(2)}个百分点`
      : "金额未齐或校验失败，未计算。",
    "",
    "—— 候选现象 ——",
    el("risk-observation")?.textContent || "无",
    "",
    "—— 来源台账 ——",
    ...fieldDefinitions.map((field) => {
      const row = state.data[field.id];
      return `${field.label}: ${row.value || "空"} ${state.project.amountUnit} | ${row.sourceFile || "无文件"} | PDF ${row.pdfPage || "?"} | ${row.locator || "无定位"}`;
    }),
    "",
    "—— 人工复核 ——",
    `状态：${state.review.status}`,
    `说明：${state.review.note || "无"}`,
    "",
    `导出时间：${new Date().toISOString()}`,
    "系统模式：本地静态原型 · 无模型调用",
  ];
  return lines.join("\n");
}

function exportDraft() {
  readProjectForm();
  if (el("data-table-body")) readDataTable();
  if (el("review-status")) {
    state.review.status = $("#review-status").value;
    state.review.note = $("#review-note").value.trim();
  }
  saveState();
  renderReviewPanel();

  if (state.review.status === "未复核" || !allCoreNumbersValid() || !allEvidenceRowsComplete()) {
    showToast("导出闸门未开：请完成数字、来源与人工复核状态");
    goToView("review-view");
    return;
  }

  const blob = new Blob([buildExportText()], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `审迹智链_预审草稿_${state.project.companyName || "未命名"}.txt`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("已下载本地预审草稿（非正式报告）");
}

function bindEvents() {
  $all("[data-view]").forEach((button) => {
    button.addEventListener("click", () => goToView(button.dataset.view));
  });

  document.body.addEventListener("click", (event) => {
    const go = event.target.closest("[data-go]");
    if (go) goToView(go.dataset.go);
    const drill = event.target.closest("[data-drill-tab]");
    if (drill) switchDrill(drill.dataset.drillTab);
  });

  const form = el("project-form");
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      readProjectForm();
      saveState();
      renderProjectSummary();
      renderDataTable();
      renderOverview();
      renderRiskCard();
      showToast("项目基本信息已保存在本浏览器");
      goToView("data-view");
    });
  }

  el("clear-project")?.addEventListener("click", () => {
    const confirmed = window.confirm("确定清空当前浏览器中保存的项目、数据和复核说明吗？");
    if (!confirmed) return;
    state = cloneDefaultState();
    cachePlayback = false;
    sessionStorage.removeItem(CACHE_FLAG_KEY);
    saveState();
    setInputValuesFromState();
    renderProjectSummary();
    renderDataTable();
    renderOverview();
    renderRiskCard();
    renderReviewPanel();
    showToast("本地内容已清空");
    goToView("project-view");
  });

  el("save-data")?.addEventListener("click", () => {
    readProjectForm();
    readDataTable();
    saveState();
    updateDataStatuses();
    renderProjectSummary();
    renderOverview();
    renderRiskCard();
    showToast(
      hasInvalidNumbers() || hasZeroDenominator()
        ? "数据已保存，但校验失败"
        : allCoreNumbersValid()
          ? "数据已保存，已完成确定性计算"
          : "数据已保存，仍缺少可计算字段",
    );
    goToView(allCoreNumbersValid() ? "overview-view" : "data-view");
  });

  el("fill-source-file")?.addEventListener("click", () => {
    readDataTable();
    const firstFile = state.data[fieldDefinitions[0].id].sourceFile;
    if (!firstFile) {
      showToast("请先填写第一行的来源文件名");
      return;
    }
    fieldDefinitions.forEach((field) => {
      if (!state.data[field.id].sourceFile) state.data[field.id].sourceFile = firstFile;
    });
    renderDataTable();
    showToast("已复制来源文件名，其他定位信息仍需逐行核对");
  });

  el("save-review")?.addEventListener("click", () => {
    state.review.status = $("#review-status").value;
    state.review.note = $("#review-note").value.trim();
    saveState();
    renderReviewPanel();
    renderSystemMode();
    showToast("人工复核说明已保存在本浏览器");
  });

  el("export-draft")?.addEventListener("click", exportDraft);
}

function initialise() {
  if (sessionStorage.getItem(CACHE_FLAG_KEY) === "1") cachePlayback = true;
  setInputValuesFromState();
  renderProjectSummary();
  renderDataTable();
  renderOverview();
  renderRiskCard();
  renderReviewPanel();
  renderWorkflowState("project-view");
  renderSystemMode();
  switchDrill("observation");
  bindEvents();
}

initialise();
