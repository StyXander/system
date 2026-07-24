/**
 * 审迹智链 AuditTrace · 五层校验链
 * 从 audittrace-local-static/app.js 移植,保留原始校验顺序与中文注释。
 *
 * 校验顺序:
 * 1. 项目字段完整(companyName / analysisDate / currentYear / previousYear)
 * 2. 年度连续(本年 = 上年 + 1)
 * 3. 数据上下文匹配(四项数字绑定的公司/年度与项目一致)
 * 4. 数字有效(四项均可解析且上年金额非零)
 * 5. 来源完整(四行均含数值+五项定位,且披露日不晚于 T0)
 *
 * 任一关卡未过,不显示候选风险卡,只显示阻断提示。
 */

import type {
  AuditTraceState,
  DataContext,
  EvidenceRow,
  ProjectInfo,
  RiskCardState,
  RowStatus,
} from "../types";
import { computeR1, fieldDefinitions, numericValue, percent, projectFieldsComplete, projectYearsSequential } from "./calc";

/** 检查单行来源完整度:空 / 部分 / 完整 / 阻断(T0 后) */
export function rowCompleteness(row: EvidenceRow, analysisDate: string): RowStatus {
  // 每个数字必须同时具备数值和五项来源定位,缺一项就不能进入风险卡。
  const required = [row.value, row.sourceFile, row.disclosureDate, row.pdfPage, row.printPage, row.locator];
  const filled = required.filter((value) => String(value).trim() !== "").length;
  if (filled === 0) return "empty";
  if (filled < required.length) return "partial";

  // 披露日晚于 T0 的资料不属于当前时点白名单,明确阻断而不是静默使用。
  if (analysisDate && row.disclosureDate > analysisDate) return "blocked";
  return "complete";
}

/** 四项数字是否全部可解析且上年金额非零 */
export function allCoreNumbersValid(state: AuditTraceState): boolean {
  const values = [
    numericValue(state, "revenue_current"),
    numericValue(state, "revenue_previous"),
    numericValue(state, "ar_current"),
    numericValue(state, "ar_previous"),
  ];
  return values.every((value) => value !== null) && values[1] !== 0 && values[3] !== 0;
}

/** 四行来源是否全部完整且未使用 T0 后资料 */
export function allEvidenceRowsComplete(state: AuditTraceState): boolean {
  return fieldDefinitions.every(
    (field) => rowCompleteness(state.data[field.id], state.project.analysisDate) === "complete",
  );
}

/** 数据上下文是否与项目一致 */
export function dataContextMatchesProject(state: AuditTraceState): boolean {
  return (
    state.dataContext.companyName === state.project.companyName &&
    state.dataContext.currentYear === state.project.currentYear &&
    state.dataContext.previousYear === state.project.previousYear
  );
}

/** 是否有任何数据内容 */
export function dataHasAnyContent(state: AuditTraceState): boolean {
  return fieldDefinitions.some((field) =>
    Object.values(state.data[field.id]).some((value) => String(value).trim() !== ""),
  );
}

/** 项目身份是否变化(公司或年度改变) */
export function projectIdentityChanged(prev: ProjectInfo, next: ProjectInfo): boolean {
  return (
    prev.companyName !== next.companyName ||
    prev.currentYear !== next.currentYear ||
    prev.previousYear !== next.previousYear
  );
}

/** 行状态对应的显示文案 */
export function rowStatusText(status: RowStatus): string {
  switch (status) {
    case "complete":
      return "完整录入,待复核";
    case "blocked":
      return "晚于 T0,已阻断";
    case "context-mismatch":
      return "公司/年度不匹配";
    case "partial":
      return "部分录入";
    default:
      return "待接入";
  }
}

/**
 * 根据当前状态决定显示阻断卡还是风险卡
 * 先检查项目,再检查年度,再检查上下文,再检查数字,最后检查来源;
 * 任何一关失败都不显示候选卡。
 */
export function resolveRiskCardState(state: AuditTraceState): RiskCardState {
  const company = state.project.companyName;
  const year = state.project.currentYear;

  if (!projectFieldsComplete(state.project)) {
    return {
      kind: "gate",
      reason: "project-incomplete",
      title: "先建立项目框架",
      text: "请填写公司名称、T0 和两个年度,再录入年报数据。",
    };
  }

  if (!projectYearsSequential(state.project)) {
    return {
      kind: "gate",
      reason: "years-not-sequential",
      title: "本年与上年必须连续",
      text: "请把本年设置为上年的下一年度,例如 2024 / 2023。未通过前停止计算。",
    };
  }

  if (!dataContextMatchesProject(state)) {
    return {
      kind: "gate",
      reason: "context-mismatch",
      title: "项目年度与数字不一致",
      text: "当前四项数字没有绑定到所选公司和年度,系统已停止计算。请返回数据页重新载入或录入对应期间资料。",
    };
  }

  if (!allCoreNumbersValid(state)) {
    return {
      kind: "gate",
      reason: "numbers-invalid",
      title: "等待四项年报数据",
      text: "请录入本年、上年的营业收入和应收账款;字段缺失、无法转成数字或上年金额为零时停止计算。",
    };
  }

  const result = computeR1(state);

  // 数字可以先复算,但来源不齐全时仍不能生成候选风险卡。
  if (!allEvidenceRowsComplete(state)) {
    return {
      kind: "gate",
      reason: "evidence-incomplete",
      title: "数字已可计算,来源仍未通过",
      text: "请为四个数字补齐来源文件、披露日期、PDF 页、印刷页和原文位置。披露日晚于 T0 的资料会被阻断。",
    };
  }

  // W1 的 R1-L1 只按增速差方向筛查,不设置风险等级或概率。
  if (result.gap !== null && result.gap > 0) {
    return {
      kind: "card",
      result,
      direction: "candidate",
      title: "应收账款增速高于收入增速,需进一步了解",
      observation: `${year} 年,${company}应收账款增速为 ${percent(result.arGrowth!)},营业收入增速为 ${percent(result.revenueGrowth!)},前者高出 ${(result.gap * 100).toFixed(2)} 个百分点。按 R1-L1 当前方向规则形成待核查候选;是否保留仍须人工复核。`,
    };
  }

  return {
    kind: "card",
    result,
    direction: "no-candidate",
    title: "本次未出现“应收增速高于收入增速”的方向",
    observation: `${year} 年,${company}应收账款增速为 ${percent(result.arGrowth!)},营业收入增速为 ${percent(result.revenueGrowth!)}。按当前两个指标的方向,本次未形成 R1 候选;这不代表不存在其他风险。`,
  };
}
