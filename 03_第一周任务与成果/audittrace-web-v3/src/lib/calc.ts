/**
 * 审迹智链 AuditTrace · R1-L1 计算与金额换算
 * 从 audittrace-local-static/app.js 移植,保留原始计算口径与中文注释。
 *
 * R1-L1 当前只做增速差方向筛查:
 * 1. 营业收入同比增速
 * 2. 应收账款同比增速
 * 3. 应收增速减去收入增速后的百分点差额
 * 不设置风险阈值、不判等级、不计算概率。
 */

import type { AmountUnit, AuditTraceState, EvidenceRow, FieldDefinition, FieldId, ProjectInfo, R1CalcResult } from "../types";

/** 四项字段与 R1 最小计算口径一一对应。年度来自项目表单,代码中不写死具体案例年份。 */
export const fieldDefinitions: FieldDefinition[] = [
  { id: "revenue_current", label: "本年营业收入", yearType: "current" },
  { id: "revenue_previous", label: "上年营业收入", yearType: "previous" },
  { id: "ar_current", label: "本年应收账款", yearType: "current" },
  { id: "ar_previous", label: "上年应收账款", yearType: "previous" },
];

/** 三个金额单位都是 10 的整数次幂,使用十进制位移动避免浮点尾差。 */
export const amountUnitExponents: Record<AmountUnit, number> = Object.freeze({
  元: 0,
  万元: 4,
  百万元: 6,
});

/** 创建空数据:每项含六字段,全部为空字符串 */
export function createEmptyData(): Record<FieldId, EvidenceRow> {
  return Object.fromEntries(
    fieldDefinitions.map((field) => [
      field.id,
      {
        value: "",
        sourceFile: "",
        disclosureDate: "",
        pdfPage: "",
        printPage: "",
        locator: "",
      } satisfies EvidenceRow,
    ]),
  ) as Record<FieldId, EvidenceRow>;
}

/**
 * 十进制小数点移动:只移动小数点位置,不先转成 Number,从而保留原始金额精度。
 * 用于金额单位换算(元 ↔ 万元 ↔ 百万元)。
 * @param rawValue 原始金额字符串
 * @param places 移动位数(正=左移小数点=放大,负=右移=缩小)
 * @returns 换算后的字符串,无法解析时返回 null
 */
export function shiftDecimalString(rawValue: string, places: number): string | null {
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

/** 对一组数据整体换算金额单位 */
export function convertDataAmounts(
  data: Record<FieldId, EvidenceRow>,
  fromUnit: AmountUnit,
  toUnit: AmountUnit,
): Record<FieldId, EvidenceRow> {
  if (fromUnit === toUnit) return data;
  const fromExponent = amountUnitExponents[fromUnit];
  const toExponent = amountUnitExponents[toUnit];
  if (fromExponent === undefined || toExponent === undefined) return data;

  const result = { ...data };
  fieldDefinitions.forEach((field) => {
    const converted = shiftDecimalString(result[field.id].value, fromExponent - toExponent);
    if (converted !== null) {
      result[field.id] = { ...result[field.id], value: converted };
    }
  });
  return result;
}

/** 安全转数字:空值或非法数字统一返回 null,由计算准入门槛拦截 */
export function numericValue(state: AuditTraceState, fieldId: FieldId): number | null {
  const raw = state.data[fieldId].value;
  if (raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/** 格式化为百分比字符串 */
export function percent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

/** 格式化百分点差额(带正负号) */
export function formatGap(gap: number | null): string {
  if (gap === null) return "—";
  return `${gap >= 0 ? "+" : ""}${(gap * 100).toFixed(2)} 个百分点`;
}

/** 期间键:本年/上年,用于样例数据查找 */
export function periodKey(project: ProjectInfo): string {
  return `${project.currentYear}/${project.previousYear}`;
}

/** 本年与上年必须连续(本年 = 上年 + 1) */
export function projectYearsSequential(project: ProjectInfo): boolean {
  const current = Number(project.currentYear);
  const previous = Number(project.previousYear);
  return Number.isInteger(current) && Number.isInteger(previous) && current === previous + 1;
}

/** 项目必填字段是否完整(行业允许稍后补) */
export function projectFieldsComplete(project: ProjectInfo): boolean {
  return Boolean(project.companyName && project.analysisDate && project.currentYear && project.previousYear);
}

/**
 * R1-L1 计算:收入增速、应收增速、百分点差额
 * 上年收入或上年应收为零时,由调用方准入函数拦截,此处不额外处理除零。
 * gap > 0 只说明当前指标方向形成候选现象,不自动判定风险等级。
 */
export function computeR1(state: AuditTraceState): R1CalcResult {
  const revenueCurrent = numericValue(state, "revenue_current");
  const revenuePrevious = numericValue(state, "revenue_previous");
  const arCurrent = numericValue(state, "ar_current");
  const arPrevious = numericValue(state, "ar_previous");

  if (revenueCurrent === null || revenuePrevious === null || arCurrent === null || arPrevious === null) {
    return { revenueGrowth: null, arGrowth: null, gap: null };
  }
  if (revenuePrevious === 0 || arPrevious === 0) {
    return { revenueGrowth: null, arGrowth: null, gap: null };
  }

  const revenueGrowth = (revenueCurrent - revenuePrevious) / revenuePrevious;
  const arGrowth = (arCurrent - arPrevious) / arPrevious;
  const gap = arGrowth - revenueGrowth;

  return { revenueGrowth, arGrowth, gap };
}
