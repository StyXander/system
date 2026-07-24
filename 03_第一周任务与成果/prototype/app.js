/*
 * 审迹智链静态原型（界面 v0.5 独立视觉重做）
 * 关键原则：只做确定性计算和本地展示；没有A/B真实输入时不生成结果。
 * 所有动态数据保存在当前浏览器 localStorage 中，不上传到外部服务。
 * 视觉层变更不影响计算口径、准入门槛和本地存储键名。
 */

const STORAGE_KEY = "audittrace_week1_state_v1";

// 四个字段与 R1 的最小计算口径一一对应。
// yearType 只负责显示年份，不把某个具体年度写死在代码中。
const fieldDefinitions = [
  { id: "revenue_current", label: "本年营业收入", yearType: "current" },
  { id: "revenue_previous", label: "上年营业收入", yearType: "previous" },
  { id: "ar_current", label: "本年应收账款", yearType: "current" },
  { id: "ar_previous", label: "上年应收账款", yearType: "previous" },
];

// 默认状态不放任何示例金额，避免首次打开时出现貌似真实的结果。
// 所有“待接入”内容均由团队成员主动填写。
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

function $(selector) {
  return document.querySelector(selector);
}

function $all(selector) {
  return [...document.querySelectorAll(selector)];
}

function cloneDefaultState() {
  return JSON.parse(JSON.stringify(defaultState));
}

// 页面升级后，本地可能残留旧版字段。
// 这里从空白结构出发，只合并本版认识的字段，防止旧数据破坏页面。
function loadState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return cloneDefaultState();
    const parsed = JSON.parse(saved);

    // 只合并已知字段，避免旧版本或手工修改的数据破坏页面结构。
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
  // 第一周只保存在当前浏览器，不上传，也不调用外部接口。
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

// 短提示只反馈操作是否完成，不承担风险判断。
function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function escapeHtml(value) {
  // 数据表使用模板字符串重绘，必须先转义用户输入，避免被当成 HTML 执行。
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setInputValuesFromState() {
  // 刷新页面后，把浏览器中保存的项目与复核状态放回表单。
  $("#company-name").value = state.project.companyName;
  $("#analysis-date").value = state.project.analysisDate;
  $("#analysis-scene").value = state.project.scene;
  $("#industry").value = state.project.industry;
  $("#current-year").value = state.project.currentYear;
  $("#previous-year").value = state.project.previousYear;
  $("#amount-unit").value = state.project.amountUnit;
  $("#review-status").value = state.review.status;
  $("#review-note").value = state.review.note;
}

function readProjectForm() {
  // 项目信息只用于界面显示和场景控制，不在这里推断行业或风险。
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
  // 空字段明确写“待填写”，不使用推测值补齐。
  const project = state.project;
  $("#project-summary-title").textContent = project.companyName || "尚未填写公司名称";
  $("#project-summary-scene").textContent = project.scene;
  $("#project-summary-date").textContent = project.analysisDate || "待填写";
  $("#project-summary-industry").textContent = project.industry || "待填写";
}

function projectFieldsComplete() {
  // 流程条只把必需的项目字段视为“完成”，行业仍可在后续人工补充。
  return Boolean(
    state.project.companyName &&
      state.project.analysisDate &&
      state.project.currentYear &&
      state.project.previousYear,
  );
}

function renderWorkflowState(activeView = document.querySelector(".view.active")?.id) {
  // 顶部流程条的“完成”来自真实字段状态，而不是因为用户点过某个页面。
  const completedViews = new Set();
  if (projectFieldsComplete()) completedViews.add("project-view");
  if (allEvidenceRowsComplete()) completedViews.add("data-view");

  $all(".workflow-step").forEach((step) => {
    step.classList.toggle("active", step.dataset.view === activeView);
    step.classList.toggle("completed", completedViews.has(step.dataset.view));
  });
}

function getYearLabel(field) {
  // 用户未填年度时用“本年/上年”，保证表格仍可理解。
  const year = field.yearType === "current" ? state.project.currentYear : state.project.previousYear;
  return year || (field.yearType === "current" ? "本年" : "上年");
}

function renderDataTable() {
  // 每次重绘都从 state 生成四行，确保字段顺序与公式口径一致。
  // 动态值进入 HTML 前统一转义，状态标签由完整性函数另行计算。
  const body = $("#data-table-body");
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
    });
  });
  updateDataStatuses();
}

function readDataTable() {
  // 这里只采集输入，不把“已填写”误写成“已核验”。
  $all("#data-table-body tr").forEach((rowElement) => {
    const fieldId = rowElement.dataset.fieldId;
    rowElement.querySelectorAll("input[data-key]").forEach((input) => {
      state.data[fieldId][input.dataset.key] = input.value.trim();
    });
  });
}

function rowCompleteness(row) {
  // 一个数字只有数值与五项来源定位全部存在，才算“完整录入”。
  // 完整录入仍不是人工复核通过，页面文案会继续提示复核。
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

function updateDataStatuses() {
  // 行状态和总计数均由同一完整性函数产生，避免两处口径不一致。
  let complete = 0;
  $all("#data-table-body tr").forEach((rowElement) => {
    const fieldId = rowElement.dataset.fieldId;
    const status = rowCompleteness(state.data[fieldId]);
    const badge = rowElement.querySelector(".row-status");
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

  $("#complete-count").textContent = `${complete} / 4`;
  const overall = $("#data-overall-status");
  if (complete === 4) {
    overall.className = "state-chip complete";
    overall.textContent = "4项已录入，待复核";
  } else if (complete > 0) {
    overall.className = "state-chip draft";
    overall.textContent = `${complete}项完整，其余待补`;
  } else {
    overall.className = "state-chip pending";
    overall.textContent = "待B接入";
  }
  renderWorkflowState();
}

function numericValue(fieldId) {
  // 空字符串与非法数字统一返回 null，交给计算准入函数拦截。
  const raw = state.data[fieldId].value;
  if (raw === "") return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function percent(value) {
  // 比例统一保留两位小数，便于组员手工复算。
  return `${(value * 100).toFixed(2)}%`;
}

function allCoreNumbersValid() {
  // 四个金额缺一不可；两个上年数为 0 时不能作为增长率分母。
  // 这里仅判断是否可计算，不判断来源是否完整。
  const values = [
    numericValue("revenue_current"),
    numericValue("revenue_previous"),
    numericValue("ar_current"),
    numericValue("ar_previous"),
  ];
  return values.every((value) => value !== null) && values[1] !== 0 && values[3] !== 0;
}

function allEvidenceRowsComplete() {
  // 候选风险卡的来源准入：四行都必须具备可返回原件的位置。
  return fieldDefinitions.every((field) => rowCompleteness(state.data[field.id]) === "complete");
}

function renderRiskCard() {
  // 风险页采用两层门槛：先允许确定性计算，再检查来源完整性。
  // 任一门槛未通过都保持空状态，不调用模型生成解释。
  const riskEmpty = $("#risk-empty");
  const riskCard = $("#risk-card");
  const riskStatus = $("#risk-status");

  $("#planning-only").classList.toggle("hidden", state.project.scene !== "审计计划");

  if (!allCoreNumbersValid()) {
    $("#revenue-growth").textContent = "—";
    $("#ar-growth").textContent = "—";
    $("#growth-gap").textContent = "—";
    riskStatus.className = "state-chip pending";
    riskStatus.textContent = "待数据接入";
    $("#risk-empty-title").textContent = "等待 B 的年报数据";
    $("#risk-empty-text").textContent =
      "录入本年/上年收入和应收账款后，这里才会生成基于真实数字的现象描述。上年数为 0 时也会停止计算。";
    riskEmpty.classList.remove("hidden");
    riskCard.classList.add("hidden");
    return;
  }

  const revenueGrowth =
    (numericValue("revenue_current") - numericValue("revenue_previous")) /
    numericValue("revenue_previous");
  const arGrowth =
    (numericValue("ar_current") - numericValue("ar_previous")) /
    numericValue("ar_previous");
  const gap = arGrowth - revenueGrowth;

  // 公式全部由程序固定计算，AI 以后也不得改写这些结果。
  // 差额使用百分点显示，避免把两个增长率之差再次当作增长率。

  $("#revenue-growth").textContent = percent(revenueGrowth);
  $("#ar-growth").textContent = percent(arGrowth);
  $("#growth-gap").textContent = `${gap >= 0 ? "+" : ""}${(gap * 100).toFixed(2)}个百分点`;

  // 数字可以先完成确定性计算，但来源没有补齐时不生成候选风险卡。
  if (!allEvidenceRowsComplete()) {
    riskStatus.className = "state-chip pending";
    riskStatus.textContent = "待补全来源位置";
    $("#risk-empty-title").textContent = "数字已可计算，来源仍未补全";
    $("#risk-empty-text").textContent =
      "请返回数据页，为四个数字补齐文件名、披露日期、PDF 页码、印刷页码和原文位置。补齐后可以生成候选现象，但仍须另一名成员回到原件核对。";
    riskEmpty.classList.remove("hidden");
    riskCard.classList.add("hidden");
    return;
  }

  const company = state.project.companyName || "本开发样例";
  const currentYear = state.project.currentYear || "本年";

  // A 尚未冻结提醒阈值，所以这里只按差额方向写现象，不给风险等级。
  // gap 不大于 0 只表示当前 R1 方向未形成候选，不评价其他风险。
  if (gap > 0) {
    $("#risk-card-title").textContent = "应收账款增速高于收入增速，需进一步了解";
    $("#risk-observation").textContent = `${currentYear}，${company}应收账款增速为${percent(arGrowth)}，营业收入增速为${percent(revenueGrowth)}，前者高出${(gap * 100).toFixed(2)}个百分点。该差额只是一项计算结果，是否达到提醒阈值仍待A确认。`;
    riskStatus.className = "state-chip draft";
    riskStatus.textContent = "候选现象，待A与人工复核";
  } else {
    $("#risk-card-title").textContent = "本样例未出现应收增速高于收入增速的方向";
    $("#risk-observation").textContent = `${currentYear}，${company}应收账款增速为${percent(arGrowth)}，营业收入增速为${percent(revenueGrowth)}。按当前两个指标的方向，本次未形成“应收账款增速高于收入增速”的 R1 候选；这只是一项规则计算状态，尚不能据此评价其他风险。`;
    riskStatus.className = "state-chip complete";
    riskStatus.textContent = "仅完成计算，未形成R1候选";
  }

  renderEvidenceList();
  riskEmpty.classList.add("hidden");
  riskCard.classList.remove("hidden");
}

function renderEvidenceList() {
  // 风险卡逐项展示金额与来源，使复核人可以回到年报原件。
  // 缺失项继续显示“待填”，不会被静默隐藏。
  const list = $("#evidence-list");
  list.innerHTML = "";
  fieldDefinitions.forEach((field) => {
    const row = state.data[field.id];
    const item = document.createElement("div");
    item.className = "evidence-item";

    const label = document.createElement("strong");
    label.textContent = `${field.label}：${row.value || "待填写"} ${state.project.amountUnit}`;

    const source = document.createElement("span");
    const sourceParts = [
      row.sourceFile || "来源文件待填",
      row.disclosureDate ? `披露于${row.disclosureDate}` : "披露日期待填",
      row.pdfPage ? `PDF第${row.pdfPage}页` : "PDF页码待填",
      row.printPage ? `印刷页码：${row.printPage}` : "印刷页码待填",
      row.locator || "原文位置待填",
    ];
    source.textContent = sourceParts.join("｜");

    item.append(label, source);
    list.append(item);
  });
}

function goToView(viewId) {
  // 三个页面共用一个 HTML，通过 active 类切换，便于直接双击运行。
  $all(".view").forEach((view) => view.classList.toggle("active", view.id === viewId));
  $all("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === viewId));
  const headingMap = {
    "project-view": "新建预审项目",
    "data-view": "年报数据预检",
    "risk-view": "R1风险卡草稿",
  };
  $("#page-heading").textContent = headingMap[viewId];
  if (viewId === "risk-view") renderRiskCard();
  renderWorkflowState(viewId);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindEvents() {
  // 导航只改变当前视图，不丢失已经录入的本地状态。
  $all("[data-view]").forEach((button) => {
    button.addEventListener("click", () => goToView(button.dataset.view));
  });

  $all("[data-go]").forEach((button) => {
    button.addEventListener("click", () => goToView(button.dataset.go));
  });

  $("#project-form").addEventListener("submit", (event) => {
    // 保存项目后重绘年度和场景相关内容，再进入数据页。
    event.preventDefault();
    readProjectForm();
    saveState();
    renderProjectSummary();
    renderDataTable();
    renderRiskCard();
    showToast("项目基本信息已保存在本浏览器");
    goToView("data-view");
  });

  $("#clear-project").addEventListener("click", () => {
    // 清空属于不可逆的本地操作，必须由当前操作者再次确认。
    const confirmed = window.confirm("确定清空当前浏览器中保存的项目、数据和复核说明吗？");
    if (!confirmed) return;
    state = cloneDefaultState();
    saveState();
    setInputValuesFromState();
    renderProjectSummary();
    renderDataTable();
    renderRiskCard();
    showToast("本地内容已清空");
  });

  $("#save-data").addEventListener("click", () => {
    // 保存后立即运行固定公式；准入不通过时风险页会显示具体缺口。
    readProjectForm();
    readDataTable();
    saveState();
    updateDataStatuses();
    renderProjectSummary();
    renderRiskCard();
    showToast(allCoreNumbersValid() ? "数据已保存，已完成确定性计算" : "数据已保存，仍缺少可计算字段");
    goToView("risk-view");
  });

  $("#fill-source-file").addEventListener("click", () => {
    // 只复制相同年报的文件名，页码与原文位置仍须逐行核对。
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

  $("#save-review").addEventListener("click", () => {
    // 人工复核状态由人选择，程序不自动代替保留、降级或暂缓决定。
    state.review.status = $("#review-status").value;
    state.review.note = $("#review-note").value.trim();
    saveState();
    showToast("人工复核说明已保存在本浏览器");
  });
}

function initialise() {
  // 初始化顺序保证先恢复输入，再根据恢复后的状态绘制页面。
  setInputValuesFromState();
  renderProjectSummary();
  renderDataTable();
  renderRiskCard();
  renderWorkflowState("project-view");
  bindEvents();
}

initialise();
