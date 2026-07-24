/**
 * 审迹智链 AuditTrace · 类型定义
 * 对应 data-schema.json 中的项目、数据上下文、四项年报数据和人工复核字段。
 * 本地静态预览版:只做录入、计算和展示,不调用模型或外部接口。
 */

/** 金额单位:三档均为 10 的整数次幂,便于十进制位移 */
export type AmountUnit = "元" | "万元" | "百万元";

/** 审计场景:承接 / 续聘 / 计划 */
export type AuditScene = "新客户业务承接" | "续聘复核" | "审计计划";

/** 人工复核状态:程序不替人作保留、降级或暂缓决定 */
export type ReviewStatus = "未复核" | "保留为待核查候选" | "降级" | "暂缓";

/** 数据来源:人工录入 / 内置开发样例 */
export type DataOrigin = "manual" | "week1_sample";

/** 年份类型:本年 / 上年 */
export type YearType = "current" | "previous";

/** 四项 R1 字段标识 */
export type FieldId = "revenue_current" | "revenue_previous" | "ar_current" | "ar_previous";

/** 证据行:每个数字必须绑定来源文件、披露日期、页码、原文位置 */
export interface EvidenceRow {
  value: string;
  sourceFile: string;
  disclosureDate: string;
  pdfPage: string;
  printPage: string;
  locator: string;
}

/** 字段定义:R1 规则所需的四项年报字段 */
export interface FieldDefinition {
  id: FieldId;
  label: string;
  yearType: YearType;
}

/** 项目信息 */
export interface ProjectInfo {
  companyName: string;
  analysisDate: string;
  scene: AuditScene;
  industry: string;
  currentYear: string;
  previousYear: string;
  amountUnit: AmountUnit;
}

/** 数据上下文:四项数字实际绑定的公司和年度,与 project 不一致时阻断计算 */
export interface DataContext {
  companyName: string;
  currentYear: string;
  previousYear: string;
  origin: DataOrigin;
}

/** 人工复核 */
export interface ReviewInfo {
  status: ReviewStatus;
  note: string;
}

/** 行完整度状态 */
export type RowStatus = "empty" | "partial" | "complete" | "blocked" | "context-mismatch";

/** 完整的本地状态 */
export interface AuditTraceState {
  project: ProjectInfo;
  dataContext: DataContext;
  data: Record<FieldId, EvidenceRow>;
  review: ReviewInfo;
}

/** R1-L1 计算结果 */
export interface R1CalcResult {
  revenueGrowth: number | null;
  arGrowth: number | null;
  gap: number | null;
}

/** 校验关卡 */
export type GateReason =
  | "project-incomplete"
  | "years-not-sequential"
  | "context-mismatch"
  | "numbers-invalid"
  | "evidence-incomplete"
  | null;

/** 风险卡渲染状态 */
export type RiskCardState =
  | { kind: "gate"; reason: Exclude<GateReason, null>; title: string; text: string }
  | { kind: "card"; result: R1CalcResult; direction: "candidate" | "no-candidate"; title: string; observation: string };
