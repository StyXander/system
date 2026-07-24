/**
 * 审迹智链 AuditTrace · 标准股份三组开发样例
 * 从 audittrace-local-static/app.js 移植,保留原始数据与绑定逻辑。
 *
 * 三组连续年度字段均已回本地 PDF 表格抽查,但尚未完成另一名队员的人工复核。
 * 每组资料都绑定公司、年度、文件和页码;切换年度时整组切换,禁止只改标签。
 * 非冻结案例,仍待另一名队员复核。
 */

import type { AuditTraceState, EvidenceRow, FieldId, ProjectInfo } from "../types";
import { convertDataAmounts } from "./calc";

/** 开发样例公司名称 */
export const week1SampleCompany = "西安标准工业股份有限公司(标准股份)";

/** 样例数据:按期间键索引,每组含四项完整证据行(原始单位:元) */
export const week1SamplePeriods = Object.freeze({
  "2025/2024": {
    data: {
      revenue_current: {
        value: "337238620.57",
        sourceFile: "标准股份:标准股份2025年年度报告全文(1).pdf",
        disclosureDate: "2026-04-28",
        pdfPage: "64",
        printPage: "64(页脚印与 PDF 一致)",
        locator: "合并利润表/营业收入(2025 本期)",
      },
      revenue_previous: {
        value: "446351660.77",
        sourceFile: "标准股份:标准股份2025年年度报告全文(1).pdf",
        disclosureDate: "2026-04-28",
        pdfPage: "64",
        printPage: "64(页脚印与 PDF 一致)",
        locator: "合并利润表/营业收入(2024 上期栏)",
      },
      ar_current: {
        value: "176388063.66",
        sourceFile: "标准股份:标准股份2025年年度报告全文(1).pdf",
        disclosureDate: "2026-04-28",
        pdfPage: "59",
        printPage: "59(页脚印与 PDF 一致)",
        locator: "合并资产负债表/应收账款(2025 期末)",
      },
      ar_previous: {
        value: "282866689.51",
        sourceFile: "标准股份:标准股份2025年年度报告全文(1).pdf",
        disclosureDate: "2026-04-28",
        pdfPage: "59",
        printPage: "59(页脚印与 PDF 一致)",
        locator: "合并资产负债表/应收账款(2024 上期期末)",
      },
    } satisfies Record<FieldId, EvidenceRow>,
  },
  "2024/2023": {
    data: {
      revenue_current: {
        value: "446351660.77",
        sourceFile: "标准股份:标准股份2024年年度报告全文(修订版).pdf",
        disclosureDate: "2025-04-29",
        pdfPage: "67",
        printPage: "67(页脚印与 PDF 一致)",
        locator: "合并利润表/营业收入(2024 本期)",
      },
      revenue_previous: {
        value: "506925296.14",
        sourceFile: "标准股份:标准股份2024年年度报告全文(修订版).pdf",
        disclosureDate: "2025-04-29",
        pdfPage: "67",
        printPage: "67(页脚印与 PDF 一致)",
        locator: "合并利润表/营业收入(2023 上期栏)",
      },
      ar_current: {
        value: "282866689.51",
        sourceFile: "标准股份:标准股份2024年年度报告全文(修订版).pdf",
        disclosureDate: "2025-04-29",
        pdfPage: "62",
        printPage: "62(页脚印与 PDF 一致)",
        locator: "合并资产负债表/应收账款(2024 期末)",
      },
      ar_previous: {
        value: "329742664.91",
        sourceFile: "标准股份:标准股份2024年年度报告全文(修订版).pdf",
        disclosureDate: "2025-04-29",
        pdfPage: "62",
        printPage: "62(页脚印与 PDF 一致)",
        locator: "合并资产负债表/应收账款(2023 上期期末)",
      },
    } satisfies Record<FieldId, EvidenceRow>,
  },
  "2023/2022": {
    data: {
      revenue_current: {
        value: "506925296.14",
        sourceFile: "标准股份:标准股份2023年年度报告.pdf",
        disclosureDate: "2024-04-18",
        pdfPage: "70",
        printPage: "70(页脚印与 PDF 一致)",
        locator: "合并利润表/营业收入(2023 本期)",
      },
      revenue_previous: {
        value: "1050779931.05",
        sourceFile: "标准股份:标准股份2023年年度报告.pdf",
        disclosureDate: "2024-04-18",
        pdfPage: "70",
        printPage: "70(页脚印与 PDF 一致)",
        locator: "合并利润表/营业收入(2022 上期栏)",
      },
      ar_current: {
        value: "329742664.91",
        sourceFile: "标准股份:标准股份2023年年度报告.pdf",
        disclosureDate: "2024-04-18",
        pdfPage: "66",
        printPage: "66(页脚印与 PDF 一致)",
        locator: "合并资产负债表/应收账款(2023 期末)",
      },
      ar_previous: {
        value: "439176425.31",
        sourceFile: "标准股份:标准股份2023年年度报告.pdf",
        disclosureDate: "2024-04-18",
        pdfPage: "66",
        printPage: "66(页脚印与 PDF 一致)",
        locator: "合并资产负债表/应收账款(2022 上期期末)",
      },
    } satisfies Record<FieldId, EvidenceRow>,
  },
} as const);

/** 样例可用的期间列表 */
export const samplePeriodKeys = Object.keys(week1SamplePeriods) as Array<keyof typeof week1SamplePeriods>;

/**
 * 根据项目信息加载对应期间的开发样例
 * 样例原始单位为"元",加载时按项目当前金额单位等值换算。
 * @returns 加载成功返回 true,否则 false
 */
export function loadSamplePeriodData(state: AuditTraceState, project: ProjectInfo): boolean {
  const key = `${project.currentYear}/${project.previousYear}`;
  const sample = (week1SamplePeriods as Record<string, { data: Record<FieldId, EvidenceRow> }>)[key];
  if (!sample || project.companyName !== week1SampleCompany) return false;

  const sampleData = JSON.parse(JSON.stringify(sample.data)) as Record<FieldId, EvidenceRow>;
  state.data = convertDataAmounts(sampleData, "元", project.amountUnit);
  state.dataContext = {
    companyName: project.companyName,
    currentYear: project.currentYear,
    previousYear: project.previousYear,
    origin: "week1_sample",
  };
  state.review = {
    status: "未复核",
    note: `开发样例 ${key}:数字已回 PDF 抽查,等待另一名队员完成交叉复核。`,
  };
  return true;
}
