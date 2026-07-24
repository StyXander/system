/**
 * 审迹智链 AuditTrace · W2 本地静态开发预览
 * 只进行本地录入、确定性计算和界面展示，不调用模型或外部接口。
 * 页面内置标准股份开发样例（含 evidence_id），不会把样例当作冻结案例，
 * 也不会把候选现象写成审计结论。
 *
 * 第二周增量：
 * 1. 每个参与计算的数字展示来源编号 evidence_id；
 * 2. 自动计算收入增长率与应收增长率（程序复算，禁止手填结果）；
 * 3. 年份切换整组绑定数据；
 * 4. 四类异常明确拦截：字段缺失、年份错位、除数为零、缺少来源编号。
 */

// v3：新增 evidence_id 字段。旧版本地缓存无法证明来源编号，故不自动迁移。
const STORAGE_KEY = "audittrace_week2_state_v3";

// 四项字段与 R1 最小计算口径一一对应。
// 年度来自项目表单，代码中不写死具体案例年份。
const fieldDefinitions = [
  { id: "revenue_current", label: "本年营业收入", yearType: "current", metric: "REV" },
  { id: "revenue_previous", label: "上年营业收入", yearType: "previous", metric: "REV" },
  { id: "ar_current", label: "本年应收账款", yearType: "current", metric: "AR" },
  { id: "ar_previous", label: "上年应收账款", yearType: "previous", metric: "AR" },
];

// 三个金额单位都是 10 的整数次幂，使用十进制位移动避免浮点尾差。
const amountUnitExponents = Object.freeze({
  元: 0,
  万元: 4,
  百万元: 6,
});

function createEmptyData() {
  return Object.fromEntries(
    fieldDefinitions.map((field) => [
      field.id,
      {
        value: "",
        evidenceId: "",
        sourceFile: "",
        disclosureDate: "",
        pdfPage: "",
        printPage: "",
        locator: "",
      },
    ]),
  );
}

function createDefaultReview() {
  return { status: "未复核", note: "" };
}

function createEmptyDataContext() {
  return { companyName: "", currentYear: "", previousYear: "", origin: "manual" };
}

// 默认状态保持空白；金额单位默认「元」，与年报原文及 B 台账一致。
const defaultState = {
  project: {
    companyName: "",
    analysisDate: "",
    scene: "新客户业务承接",
    industry: "",
    currentYear: "",
    previousYear: "",
    amountUnit: "元",
  },
  dataContext: createEmptyDataContext(),
  data: createEmptyData(),
  review: createDefaultReview(),
};

const week1SampleCompany = "西安标准工业股份有限公司（标准股份）";

// 三组连续年度字段均已回本地 PDF 表格抽查，并由 Codex 完成独立技术交叉复核；仍待团队成员人工确认。
// 每个 evidence_id 固定绑定对应年度自身年报；切换年度时，数字、文件、日期和页码整组切换。
const week1SamplePeriods = Object.freeze({
  "2025/2024": {
    data: {
      revenue_current: {
        value: "337238620.57",
        evidenceId: "STD_REV_2025",
        sourceFile: "标准股份：标准股份2025年年度报告全文(1).pdf",
        disclosureDate: "2026-04-30",
        pdfPage: "64",
        printPage: "64（页脚印与 PDF 一致）",
        locator: "合并利润表／营业收入（2025 本期）",
      },
      revenue_previous: {
        value: "446351660.77",
        evidenceId: "STD_REV_2024",
        sourceFile: "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        disclosureDate: "2025-04-29",
        pdfPage: "67",
        printPage: "67（页脚印与 PDF 一致）",
        locator: "合并利润表／营业收入（2024 本期）",
      },
      ar_current: {
        value: "176388063.66",
        evidenceId: "STD_AR_2025",
        sourceFile: "标准股份：标准股份2025年年度报告全文(1).pdf",
        disclosureDate: "2026-04-30",
        pdfPage: "59",
        printPage: "59（页脚印与 PDF 一致）",
        locator: "合并资产负债表／应收账款（2025 期末）",
      },
      ar_previous: {
        value: "282866689.51",
        evidenceId: "STD_AR_2024",
        sourceFile: "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        disclosureDate: "2025-04-29",
        pdfPage: "62",
        printPage: "62（页脚印与 PDF 一致）",
        locator: "合并资产负债表／应收账款（2024 期末）",
      },
    },
  },
  "2024/2023": {
    data: {
      revenue_current: {
        value: "446351660.77",
        evidenceId: "STD_REV_2024",
        sourceFile: "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        disclosureDate: "2025-04-29",
        pdfPage: "67",
        printPage: "67（页脚印与 PDF 一致）",
        locator: "合并利润表／营业收入（2024 本期）",
      },
      revenue_previous: {
        value: "506925296.14",
        evidenceId: "STD_REV_2023",
        sourceFile: "标准股份：标准股份2023年年度报告.pdf",
        disclosureDate: "2024-04-18",
        pdfPage: "70",
        printPage: "70（页脚印与 PDF 一致）",
        locator: "合并利润表／营业收入（2023 本期）",
      },
      ar_current: {
        value: "282866689.51",
        evidenceId: "STD_AR_2024",
        sourceFile: "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        disclosureDate: "2025-04-29",
        pdfPage: "62",
        printPage: "62（页脚印与 PDF 一致）",
        locator: "合并资产负债表／应收账款（2024 期末）",
      },
      ar_previous: {
        value: "329742664.91",
        evidenceId: "STD_AR_2023",
        sourceFile: "标准股份：标准股份2023年年度报告.pdf",
        disclosureDate: "2024-04-18",
        pdfPage: "66",
        printPage: "66（页脚印与 PDF 一致）",
        locator: "合并资产负债表／应收账款（2023 期末）",
      },
    },
  },
  "2023/2022": {
    data: {
      revenue_current: {
        value: "506925296.14",
        evidenceId: "STD_REV_2023",
        sourceFile: "标准股份：标准股份2023年年度报告.pdf",
        disclosureDate: "2024-04-18",
        pdfPage: "70",
        printPage: "70（页脚印与 PDF 一致）",
        locator: "合并利润表／营业收入（2023 本期）",
      },
      revenue_previous: {
        value: "1050779931.05",
        evidenceId: "STD_REV_2022",
        sourceFile: "标准股份：标准股份2022年年度报告.pdf",
        disclosureDate: "2023-04-19",
        pdfPage: "63",
        printPage: "63（页脚印与 PDF 一致）",
        locator: "合并利润表／营业收入（2022 本期）",
      },
      ar_current: {
        value: "329742664.91",
        evidenceId: "STD_AR_2023",
        sourceFile: "标准股份：标准股份2023年年度报告.pdf",
        disclosureDate: "2024-04-18",
        pdfPage: "66",
        printPage: "66（页脚印与 PDF 一致）",
        locator: "合并资产负债表／应收账款（2023 期末）",
      },
      ar_previous: {
        value: "439176425.31",
        evidenceId: "STD_AR_2022",
        sourceFile: "标准股份：标准股份2022年年度报告.pdf",
        disclosureDate: "2023-04-19",
        pdfPage: "59",
        printPage: "59（页脚印与 PDF 一致）",
        locator: "合并资产负债表／应收账款（2022 期末）",
      },
    },
  },
});

const tabs = [...document.querySelectorAll(".prototype-tab")];
const panels = [...document.querySelectorAll(".prototype-panel")];
const projectForm = document.getElementById("project-form");
let state = loadState();
let toastTimer;

function cloneDefaultState() {
  return JSON.parse(JSON.stringify(defaultState));
}

// 页面升级后可能残留旧字段，只合并本版认识的数据结构。
function loadState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return cloneDefaultState();
    const parsed = JSON.parse(saved);
    const merged = cloneDefaultState();
    merged.project = { ...merged.project, ...(parsed.project || {}) };
    merged.dataContext = { ...merged.dataContext, ...(parsed.dataContext || {}) };
    merged.review = { ...merged.review, ...(parsed.review || {}) };
    fieldDefinitions.forEach((field) => {
      merged.data[field.id] = {
        ...merged.data[field.id],
        ...((parsed.data || {})[field.id] || {}),
      };
    });
    return merged;
  } catch (error) {
    console.warn("本地内容读取失败，已回到空白状态。", error);
    return cloneDefaultState();
  }
}

// 所有内容只保存在当前浏览器，不上传到任何服务。
function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch (error) {
    console.warn("浏览器不允许保存本地内容。", error);
    return false;
  }
}

function showToast(message) {
  const toast = document.getElementById("prototype-toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function escapeHtml(value) {
  // 动态输入进入表格前统一转义，避免被浏览器当作 HTML 执行。
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setActiveStep(index) {
  tabs.forEach((tab, tabIndex) => {
    const selected = tabIndex === index;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", selected ? "true" : "false");
    tab.tabIndex = selected ? 0 : -1;
  });
  panels.forEach((panel, panelIndex) => {
    const visible = panelIndex === index;
    panel.classList.toggle("hidden", !visible);
    if (visible) panel.removeAttribute("hidden");
    else panel.setAttribute("hidden", "");
  });
  if (index === 2) renderRiskCard();
}

function setProjectFormFromState() {
  // 刷新后恢复用户自己保存过的项目字段。
  document.getElementById("company-name").value = state.project.companyName;
  document.getElementById("analysis-date").value = state.project.analysisDate;
  document.getElementById("analysis-scene").value = state.project.scene;
  document.getElementById("industry").value = state.project.industry;
  document.getElementById("current-year").value = state.project.currentYear;
  document.getElementById("previous-year").value = state.project.previousYear;
  document.getElementById("amount-unit").value = state.project.amountUnit;
  document.getElementById("review-status").value = state.review.status;
  document.getElementById("review-note").value = state.review.note;
}

function shiftDecimalString(rawValue, places) {
  // 只移动十进制小数点，不先转成 Number，从而保留原始金额精度。
  const match = String(rawValue).trim().match(/^([+-]?)(\d*)(?:\.(\d*))?$/);
  if (!match || (!match[2] && !match[3])) return null;

  const sign = match[1] === "-" ? "-" : "";
  const integerPart = match[2] || "0";
  const fractionPart = match[3] || "";
  let digits = `${integerPart}${fractionPart}`;
  let decimalIndex = integerPart.length + places;

  if (decimalIndex <= 0) {
    digits = `${"0".repeat(-decimalIndex)}${digits}`;
    decimalIndex = 0;
  } else if (decimalIndex >= digits.length) {
    digits = `${digits}${"0".repeat(decimalIndex - digits.length)}`;
    decimalIndex = digits.length;
  }

  const nextInteger = (digits.slice(0, decimalIndex) || "0").replace(/^0+(?=\d)/, "");
  const nextFraction = digits.slice(decimalIndex).replace(/0+$/, "");
  const normalized = nextFraction ? `${nextInteger}.${nextFraction}` : nextInteger;
  return normalized === "0" ? "0" : `${sign}${normalized}`;
}

function convertStoredAmounts(fromUnit, toUnit) {
  if (fromUnit === toUnit) return false;
  const fromExponent = amountUnitExponents[fromUnit];
  const toExponent = amountUnitExponents[toUnit];
  if (fromExponent === undefined || toExponent === undefined) return false;

  let convertedAny = false;
  fieldDefinitions.forEach((field) => {
    const raw = state.data[field.id].value;
    if (String(raw).trim() === "") return;
    const converted = shiftDecimalString(raw, fromExponent - toExponent);
    if (converted === null) return;
    state.data[field.id].value = converted;
    convertedAny = true;
  });
  return convertedAny;
}

function periodKey(project) {
  return `${project.currentYear}/${project.previousYear}`;
}

function projectDataIdentity(project, origin = "manual") {
  return {
    companyName: project.companyName,
    currentYear: project.currentYear,
    previousYear: project.previousYear,
    origin,
  };
}

function dataContextMatchesProject() {
  return (
    state.dataContext.companyName === state.project.companyName &&
    state.dataContext.currentYear === state.project.currentYear &&
    state.dataContext.previousYear === state.project.previousYear
  );
}

function projectIdentityChanged(previousProject, nextProject) {
  return (
    previousProject.companyName !== nextProject.companyName ||
    previousProject.currentYear !== nextProject.currentYear ||
    previousProject.previousYear !== nextProject.previousYear
  );
}

function dataHasAnyContent() {
  return fieldDefinitions.some((field) =>
    Object.values(state.data[field.id]).some((value) => String(value).trim() !== ""),
  );
}

function convertDataAmounts(data, fromUnit, toUnit) {
  if (fromUnit === toUnit) return data;
  const fromExponent = amountUnitExponents[fromUnit];
  const toExponent = amountUnitExponents[toUnit];
  if (fromExponent === undefined || toExponent === undefined) return data;

  fieldDefinitions.forEach((field) => {
    const converted = shiftDecimalString(data[field.id].value, fromExponent - toExponent);
    if (converted !== null) data[field.id].value = converted;
  });
  return data;
}

function loadSamplePeriodData(project) {
  const sample = week1SamplePeriods[periodKey(project)];
  if (!sample || project.companyName !== week1SampleCompany) return false;
  const sampleData = JSON.parse(JSON.stringify(sample.data));
  state.data = convertDataAmounts(sampleData, "元", project.amountUnit);
  state.dataContext = projectDataIdentity(project, "week1_sample");
  state.review = {
    status: "未复核",
    note: `开发样例 ${periodKey(project)}：Codex 已完成金额、单位、文件、披露日期、页码和 evidence_id 的独立技术交叉复核；仍待团队成员人工确认。`,
  };
  return true;
}

function resetDataForProject(project) {
  state.data = createEmptyData();
  state.dataContext = projectDataIdentity(project, "manual");
  state.review = createDefaultReview();
}

function readProjectForm() {
  // 公司或年度改变时，数据必须整组切换或清空，禁止只替换年度标签。
  const previousProject = { ...state.project };
  const previousAmountUnit = state.project.amountUnit;
  const nextProject = {
    companyName: document.getElementById("company-name").value.trim(),
    analysisDate: document.getElementById("analysis-date").value,
    scene: document.getElementById("analysis-scene").value,
    industry: document.getElementById("industry").value.trim(),
    currentYear: document.getElementById("current-year").value.trim(),
    previousYear: document.getElementById("previous-year").value.trim(),
    amountUnit: document.getElementById("amount-unit").value,
  };
  const contextChanged = projectIdentityChanged(previousProject, nextProject);
  let samplePeriodSwitched = false;
  let staleDataCleared = false;

  if (contextChanged) {
    const canSwitchKnownSample =
      state.dataContext.origin === "week1_sample" &&
      nextProject.companyName === week1SampleCompany &&
      Boolean(week1SamplePeriods[periodKey(nextProject)]);
    if (canSwitchKnownSample) {
      samplePeriodSwitched = loadSamplePeriodData(nextProject);
    } else {
      staleDataCleared = dataHasAnyContent();
      resetDataForProject(nextProject);
    }
  }

  const amountsConverted = contextChanged
    ? false
    : convertStoredAmounts(previousAmountUnit, nextProject.amountUnit);
  state.project = nextProject;
  if (!contextChanged && !dataHasAnyContent()) {
    state.dataContext = projectDataIdentity(nextProject, "manual");
  }
  return {
    amountUnitChanged: previousAmountUnit !== nextProject.amountUnit,
    amountsConverted,
    contextChanged,
    samplePeriodSwitched,
    staleDataCleared,
  };
}

function projectYearsSequential(project = state.project) {
  const current = Number(project.currentYear);
  const previous = Number(project.previousYear);
  return Number.isInteger(current) && Number.isInteger(previous) && current === previous + 1;
}

function projectFieldsComplete() {
  // 行业允许稍后补，其余字段是建立最小项目的必要信息。
  return Boolean(
    state.project.companyName &&
      state.project.analysisDate &&
      state.project.currentYear &&
      state.project.previousYear,
  );
}

function renderProjectStatus() {
  // 完成标记来自实际字段，而不是来自用户是否点过按钮。
  const completed = projectFieldsComplete();
  const status = document.getElementById("step0-state");
  const tabDone = document.querySelector(".tab-done");
  const projectTip = document.getElementById("project-created-tip");
  status.textContent = completed ? "项目字段已保存" : "尚未开始";
  status.classList.toggle("ok", completed);
  tabDone.classList.toggle("hidden", !completed);
  projectTip.classList.toggle("hidden", !completed);
}

function renderDataContextStatus() {
  const tip = document.getElementById("data-context-tip");
  if (!tip) return;
  const hasProjectIdentity = state.project.companyName && state.project.currentYear && state.project.previousYear;
  if (!hasProjectIdentity) {
    tip.textContent = "请先保存公司与连续年度；数字只有绑定到对应期间后才能进入计算。";
    return;
  }
  if (!dataContextMatchesProject()) {
    tip.textContent = "当前数字与项目公司/年度不一致，已阻断计算；请重新载入或录入本期间资料。";
    return;
  }
  const originText = state.dataContext.origin === "week1_sample" ? "内置开发样例" : "人工录入区";
  tip.textContent = `当前资料绑定：${state.project.companyName} · ${periodKey(state.project)} · ${originText}。公司或年度变化时不会沿用旧数字。`;
}

function getYearLabel(field) {
  const year = field.yearType === "current" ? state.project.currentYear : state.project.previousYear;
  return year || (field.yearType === "current" ? "本年" : "上年");
}

function renderDataTable() {
  // 四行均从本地状态生成；第二周增加 evidence_id 列。
  const body = document.getElementById("data-table-body");
  body.innerHTML = fieldDefinitions
    .map((field) => {
      const row = state.data[field.id];
      const input = (key, type, placeholder) =>
        `<input data-key="${key}" type="${type}" value="${escapeHtml(row[key])}" placeholder="${placeholder}" aria-label="${field.label} ${placeholder}" ${type === "number" ? 'step="any"' : ""}>`;
      return `
        <tr data-field-id="${field.id}">
          <td data-label="字段"><strong>${field.label}</strong></td>
          <td data-label="年度" class="year-cell">${escapeHtml(getYearLabel(field))}</td>
          <td data-label="数值">${input("value", "number", "输入金额")}</td>
          <td data-label="来源编号">${input("evidenceId", "text", "如 STD_REV_2025")}</td>
          <td data-label="来源文件">${input("sourceFile", "text", "年报文件名")}</td>
          <td data-label="披露日期">${input("disclosureDate", "date", "披露日期")}</td>
          <td data-label="PDF 页">${input("pdfPage", "text", "例如 64")}</td>
          <td data-label="印刷页">${input("printPage", "text", "页码或原件未标注")}</td>
          <td data-label="原文 / 表名">${input("locator", "text", "表名或原文位置")}</td>
          <td data-label="状态"><span class="row-status">待接入</span></td>
        </tr>`;
    })
    .join("");

  // 输入时只更新完整度提示，点击保存后才运行并展示计算结果。
  document.querySelectorAll("#data-table-body input").forEach((input) => {
    input.addEventListener("input", () => {
      readDataTable();
      state.dataContext = projectDataIdentity(state.project, "manual");
      updateDataStatuses();
      renderDataContextStatus();
    });
  });
  updateDataStatuses();
  renderDataContextStatus();
}

function readDataTable() {
  // “已录入”不等于“已人工复核”，这里只采集输入值。
  document.querySelectorAll("#data-table-body tr").forEach((rowElement) => {
    const fieldId = rowElement.dataset.fieldId;
    rowElement.querySelectorAll("input[data-key]").forEach((input) => {
      state.data[fieldId][input.dataset.key] = input.value.trim();
    });
  });
}

function rowCompleteness(row) {
  // 每个数字必须同时具备数值、来源编号与五项定位，缺一项就不能进入风险卡。
  const required = [
    row.value,
    row.evidenceId,
    row.sourceFile,
    row.disclosureDate,
    row.pdfPage,
    row.printPage,
    row.locator,
  ];
  const filled = required.filter((value) => String(value).trim() !== "").length;
  if (filled === 0) return "empty";
  if (filled < required.length) return "partial";

  // 披露日晚于 T0 的资料不属于当前时点白名单，明确阻断而不是静默使用。
  if (state.project.analysisDate && row.disclosureDate > state.project.analysisDate) return "blocked";
  return "complete";
}

function updateDataStatuses() {
  // 行状态与总计数共用一个口径，避免页面两处显示不一致。
  let complete = 0;
  document.querySelectorAll("#data-table-body tr").forEach((rowElement) => {
    const status = dataContextMatchesProject()
      ? rowCompleteness(state.data[rowElement.dataset.fieldId])
      : dataHasAnyContent()
        ? "context-mismatch"
        : "empty";
    const badge = rowElement.querySelector(".row-status");
    badge.className = `row-status ${status}`;
    if (status === "complete") {
      badge.textContent = "完整录入，待复核";
      complete += 1;
    } else if (status === "blocked") {
      badge.textContent = "晚于 T0，已阻断";
    } else if (status === "context-mismatch") {
      badge.textContent = "公司/年度不匹配";
    } else if (status === "partial") {
      badge.textContent = "部分录入";
    } else {
      badge.textContent = "待接入";
    }
  });

  const overall = document.getElementById("data-completeness");
  overall.textContent = `${complete} / 4 完整录入`;
  overall.className = `panel-state ${complete === 4 ? "ok" : "warning"}`;
}

function numericValue(fieldId) {
  // 空值或非法数字统一返回 null，由计算准入门槛拦截。
  const raw = state.data[fieldId].value;
  if (raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

// 区分「字段缺失」与「除数为零」，对应第二周四类异常拦截。
function coreNumberIssue() {
  const labels = {
    revenue_current: "本年营业收入",
    revenue_previous: "上年营业收入",
    ar_current: "本年应收账款",
    ar_previous: "上年应收账款",
  };
  const missing = [];
  const invalid = [];
  ["revenue_current", "revenue_previous", "ar_current", "ar_previous"].forEach((id) => {
    const raw = state.data[id].value;
    if (String(raw).trim() === "") {
      missing.push(labels[id]);
      return;
    }
    if (numericValue(id) === null) invalid.push(labels[id]);
  });
  if (missing.length || invalid.length) {
    const parts = [];
    if (missing.length) parts.push(`缺少：${missing.join("、")}`);
    if (invalid.length) parts.push(`无法识别为数字：${invalid.join("、")}`);
    return { type: "missing", detail: parts.join("；") };
  }
  const zeroDenominators = [];
  if (numericValue("revenue_previous") === 0) zeroDenominators.push("上年营业收入");
  if (numericValue("ar_previous") === 0) zeroDenominators.push("上年应收账款");
  if (zeroDenominators.length) {
    return { type: "zero_denominator", detail: zeroDenominators.join("、") };
  }
  return null;
}

function allCoreNumbersValid() {
  return coreNumberIssue() === null;
}

function missingEvidenceIds() {
  return fieldDefinitions
    .filter((field) => String(state.data[field.id].evidenceId || "").trim() === "")
    .map((field) => field.label);
}

function allEvidenceRowsComplete() {
  // 候选卡准入要求四行来源都可返回原件，且没有使用 T0 后资料。
  return (
    dataContextMatchesProject() &&
    fieldDefinitions.every((field) => rowCompleteness(state.data[field.id]) === "complete")
  );
}

function percent(value) {
  return `${(value * 100).toFixed(2)}%`;
}

function renderEvidenceList() {
  // 风险卡逐项列出数值、来源编号和定位，供另一名成员回到原件核对。
  const list = document.getElementById("evidence-list");
  list.innerHTML = "";
  fieldDefinitions.forEach((field) => {
    const row = state.data[field.id];
    const item = document.createElement("div");
    item.className = "evidence-item";
    const label = document.createElement("strong");
    label.textContent = `${field.label}：${row.value} ${state.project.amountUnit}`;
    const source = document.createElement("span");
    source.textContent = [
      `来源编号 ${row.evidenceId}`,
      row.sourceFile,
      `披露于 ${row.disclosureDate}`,
      `PDF 第 ${row.pdfPage} 页`,
      `印刷页码：${row.printPage}`,
      row.locator,
    ].join("｜");
    item.append(label, source);
    list.append(item);
  });
}

function setRiskStatus(text, style = "warning") {
  const status = document.getElementById("risk-status");
  status.textContent = text;
  status.className = `panel-state ${style}`;
}

function showRiskGate(title, text) {
  document.getElementById("risk-gate-title").textContent = title;
  document.getElementById("risk-gate-text").textContent = text;
  document.getElementById("risk-gate").classList.remove("hidden");
  document.getElementById("audit-card").classList.add("hidden");
}

function renderRiskCard() {
  // 先检查项目，再检查数字，最后检查来源；任何一关失败都不显示候选卡。
  // 文案口径对齐 C_第二周页面文案_v0.1。
  const planningOnly = document.getElementById("planning-only");
  planningOnly.classList.toggle("hidden", state.project.scene !== "审计计划");

  if (!projectFieldsComplete()) {
    setMetricValues(null, null, null);
    setRiskStatus("待项目字段", "warning");
    showRiskGate("先建立项目框架", "请填写公司名称、分析截止日 T0 和两个年度，再录入年报数据。");
    return;
  }

  // 异常类型 2：年份错位（项目年度不连续）
  if (!projectYearsSequential()) {
    setMetricValues(null, null, null);
    setRiskStatus("年份错位", "warning");
    showRiskGate(
      "本年与上年必须连续",
      "请将本年设置为上年的下一年度（例如 2025 / 2024）。年度关系未通过前，系统不进行增长率计算。",
    );
    return;
  }

  // 异常类型 2：年份/公司与数字绑定不一致
  if (!dataContextMatchesProject()) {
    setMetricValues(null, null, null);
    setRiskStatus("年份错位", "warning");
    showRiskGate(
      "项目年度与数字不一致",
      "当前四项数字未绑定到所选公司与年度，系统已停止计算。请重新载入对应期间的开发样例，或按该期间重新录入资料与来源编号。",
    );
    return;
  }

  const numberIssue = coreNumberIssue();
  if (numberIssue) {
    setMetricValues(null, null, null);
    // 异常类型 1：必需字段缺失；异常类型 3：除数为零
    if (numberIssue.type === "zero_denominator") {
      setRiskStatus("除数为零", "warning");
      showRiskGate(
        "上年金额为 0，无法计算增长率",
        `${numberIssue.detail} 为 0，增长率分母无效。系统已停止计算，请核对是否录错年度或金额，勿用估算值代替。`,
      );
    } else {
      setRiskStatus("字段缺失", "warning");
      showRiskGate(
        "尚缺可计算的年报字段",
        `${numberIssue.detail}。任一项为空或无法识别为数字时，系统停止计算，不会输出默认增长率。`,
      );
    }
    return;
  }

  const revenueGrowth =
    (numericValue("revenue_current") - numericValue("revenue_previous")) /
    numericValue("revenue_previous");
  const arGrowth =
    (numericValue("ar_current") - numericValue("ar_previous")) /
    numericValue("ar_previous");
  const gap = arGrowth - revenueGrowth;

  // R1 确定性结果：收入增速、应收增速、百分点差额。
  // 公式不交给大模型；不设置风险等级；不设置固定幅度阈值。
  // gap > 0 仅表示方向形成候选现象，不等于舞弊或错报。
  setMetricValues(revenueGrowth, arGrowth, gap);

  // 异常类型 4：缺少来源编号或来源定位不完整
  if (!allEvidenceRowsComplete()) {
    const missingIds = missingEvidenceIds();
    setRiskStatus("缺少来源编号", "warning");
    const idHint =
      missingIds.length > 0
        ? `当前缺少来源编号的字段：${missingIds.join("、")}。`
        : "部分字段的来源文件、披露日期、页码或原文位置仍不完整。";
    showRiskGate(
      "数字已可计算，来源仍未通过",
      `${idHint}请为四个数字分别补齐：来源编号（evidence_id）、来源文件、披露日期、PDF 页码、印刷页码与原文位置。缺少任一项时，不生成候选风险卡。披露日晚于分析截止日 T0 的资料将被阻断。`,
    );
    return;
  }

  const company = state.project.companyName;
  const year = state.project.currentYear;
  const title = document.getElementById("risk-card-title");
  const observation = document.getElementById("risk-observation");
  const direction = document.getElementById("risk-direction");

  // R1-L1 只按增速差方向筛查，不设置风险等级或概率。
  if (gap > 0) {
    title.textContent = "应收账款增速高于收入增速，建议进一步了解";
    observation.textContent = `${year} 年，${company}应收账款增速为 ${percent(arGrowth)}，营业收入增速为 ${percent(revenueGrowth)}，前者高出 ${(gap * 100).toFixed(2)} 个百分点。按 R1 当前方向规则，形成「待进一步了解」的候选现象；是否保留须人工复核。`;
    direction.textContent = "候选现象";
    setRiskStatus("候选现象，待人工复核", "warning");
  } else {
    title.textContent = "本次未出现「应收增速高于收入增速」的方向";
    observation.textContent = `${year} 年，${company}应收账款增速为 ${percent(arGrowth)}，营业收入增速为 ${percent(revenueGrowth)}。按当前两个指标的方向，本次未形成 R1 候选；这不代表不存在其他收入确认相关风险。`;
    direction.textContent = "仅完成计算";
    setRiskStatus("未形成 R1 方向候选", "ok");
  }

  renderEvidenceList();
  document.getElementById("risk-gate").classList.add("hidden");
  document.getElementById("audit-card").classList.remove("hidden");
}

function setMetricValues(revenueGrowth, arGrowth, gap) {
  // 差额使用“百分点”，避免把两个增长率之差再次当作增长率。
  document.getElementById("revenue-growth").textContent = revenueGrowth === null ? "—" : percent(revenueGrowth);
  document.getElementById("ar-growth").textContent = arGrowth === null ? "—" : percent(arGrowth);
  document.getElementById("growth-gap").textContent =
    gap === null ? "—" : `${gap >= 0 ? "+" : ""}${(gap * 100).toFixed(2)} 个百分点`;
}

function bindEvents() {
  // 侧栏同时支持鼠标点击和键盘方向键切换。
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => setActiveStep(index));
    tab.addEventListener("keydown", (event) => {
      const targets = {
        ArrowRight: (index + 1) % tabs.length,
        ArrowLeft: (index - 1 + tabs.length) % tabs.length,
        Home: 0,
        End: tabs.length - 1,
      };
      if (targets[event.key] === undefined) return;
      event.preventDefault();
      setActiveStep(targets[event.key]);
      tabs[targets[event.key]].focus();
    });
  });

  document.querySelectorAll("[data-go-step]").forEach((button) => {
    button.addEventListener("click", () => setActiveStep(Number(button.dataset.goStep)));
  });

  projectForm.addEventListener("submit", (event) => {
    // 浏览器原生 required 校验通过后，保存项目并更新年度列。
    event.preventDefault();
    const currentYearInput = document.getElementById("current-year");
    const previousYearInput = document.getElementById("previous-year");
    const nextYears = {
      currentYear: currentYearInput.value.trim(),
      previousYear: previousYearInput.value.trim(),
    };
    if (!projectYearsSequential(nextYears)) {
      previousYearInput.setCustomValidity("上年必须正好比本年早一年，例如 2025 / 2024。");
      previousYearInput.reportValidity();
      return;
    }
    previousYearInput.setCustomValidity("");
    readDataTable();
    const unitChange = readProjectForm();
    const saved = saveState();
    renderProjectStatus();
    renderDataTable();
    renderRiskCard();
    showToast(
      saved
        ? unitChange.samplePeriodSwitched
          ? `已切换为 ${periodKey(state.project)} 开发样例；数字、来源编号与页码已同步更新`
          : unitChange.staleDataCleared
            ? "公司或年度已变化；旧数字和来源已清空，请录入本期间资料"
            : unitChange.amountsConverted
              ? `项目已保存，金额已自动换算为${state.project.amountUnit}`
              : "项目字段已保存在本浏览器"
        : "当前浏览器未允许本地保存，但本页仍可继续使用",
    );
    setActiveStep(1);
  });

  ["current-year", "previous-year"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () => {
      document.getElementById("previous-year").setCustomValidity("");
    });
  });

  document.getElementById("amount-unit").addEventListener("change", () => {
    // 用户切换单位时立即换算当前四项金额，避免只改变单位标签。
    readDataTable();
    const unitChange = readProjectForm();
    const saved = saveState();
    renderProjectStatus();
    renderDataTable();
    renderRiskCard();
    showToast(
      unitChange.amountsConverted
        ? `已等值换算为${state.project.amountUnit}；增长率不会改变`
        : saved
          ? `金额单位已改为${state.project.amountUnit}`
          : "单位已更改，但当前浏览器未允许本地保存",
    );
  });

  document.getElementById("clear-project").addEventListener("click", () => {
    // 清空会删除本浏览器中的当前录入，因此保留一次人工确认。
    if (!window.confirm("确定清空当前浏览器中保存的项目、数据和复核说明吗？")) return;
    state = cloneDefaultState();
    saveState();
    setProjectFormFromState();
    renderProjectStatus();
    renderDataTable();
    renderRiskCard();
    setActiveStep(0);
    showToast("本机保存的原型内容已清空");
  });

  document.getElementById("load-week1-sample").addEventListener("click", () => {
    // 主动点击才覆盖当前录入，避免样例数据被误当成用户自己的项目。
    if (
      projectFieldsComplete() &&
      !window.confirm("载入开发样例会覆盖当前页面中的项目和数据，是否继续？")
    ) {
      return;
    }
    const selectedPeriod = `${document.getElementById("current-year").value.trim()}/${document.getElementById("previous-year").value.trim()}`;
    const requestedPeriod = week1SamplePeriods[selectedPeriod] ? selectedPeriod : "2025/2024";
    const [currentYear, previousYear] = requestedPeriod.split("/");
    const currentScene = document.getElementById("analysis-scene").value;
    const currentIndustry = document.getElementById("industry").value.trim();
    const currentUnit = document.getElementById("amount-unit").value || "元";
    state.project = {
      companyName: week1SampleCompany,
      analysisDate: "2026-04-30",
      scene: currentScene || "审计计划",
      industry: currentIndustry || "专用设备 / 缝制机械（人工填写）",
      currentYear,
      previousYear,
      amountUnit: currentUnit,
    };
    loadSamplePeriodData(state.project);
    const saved = saveState();
    setProjectFormFromState();
    renderProjectStatus();
    renderDataTable();
    renderRiskCard();
    setActiveStep(1);
    showToast(
      saved
        ? `${requestedPeriod} 开发样例已载入；数字、来源编号与页码已按年度绑定`
        : "样例已载入本页，但当前浏览器未允许本地保存",
    );
  });

  document.getElementById("copy-source-file").addEventListener("click", () => {
    // 同一 evidence_id 固定绑定对应年度自身年报，因此只复制本年度两行的文件名。
    readDataTable();
    const firstFile = state.data.revenue_current.sourceFile;
    if (!firstFile) {
      showToast("请先填写第一行的来源文件名");
      return;
    }
    fieldDefinitions.filter((field) => field.yearType === "current").forEach((field) => {
      if (!state.data[field.id].sourceFile) state.data[field.id].sourceFile = firstFile;
    });
    state.dataContext = projectDataIdentity(state.project, "manual");
    renderDataTable();
    showToast("已复制到本年度两行；上年度须使用上年度自身年报，其他来源信息仍需逐行核对");
  });

  document.getElementById("save-data").addEventListener("click", () => {
    // 保存后运行固定公式，准入失败时风险页会明确说明缺口。
    readDataTable();
    readProjectForm();
    const saved = saveState();
    renderProjectStatus();
    updateDataStatuses();
    renderRiskCard();
    const issue = coreNumberIssue();
    showToast(
      saved
        ? issue
          ? issue.type === "zero_denominator"
            ? "数据已保存，但上年金额为 0，已停止计算"
            : "数据已保存，但因字段缺失停止计算"
          : allEvidenceRowsComplete()
            ? "数据已保存并完成确定性计算"
            : "数据已保存并完成计算门槛检查；来源未通过，未生成候选卡"
        : "当前浏览器未允许本地保存，但已完成本页检查",
    );
    setActiveStep(2);
  });

  document.getElementById("save-review").addEventListener("click", () => {
    // 程序不代替人作保留、降级或暂缓决定。
    if (!allCoreNumbersValid() || !allEvidenceRowsComplete()) {
      showToast("来源准入未通过，暂不能保存人工复核处理");
      return;
    }
    state.review.status = document.getElementById("review-status").value;
    state.review.note = document.getElementById("review-note").value.trim();
    const saved = saveState();
    showToast(saved ? "人工复核说明已保存在本浏览器" : "当前浏览器未允许本地保存");
  });
}

function initialise() {
  // 初始化先恢复输入，再根据真实状态绘制项目、数据和风险三步。
  setProjectFormFromState();
  renderProjectStatus();
  renderDataTable();
  renderRiskCard();
  bindEvents();
  setActiveStep(0);
}

initialise();
