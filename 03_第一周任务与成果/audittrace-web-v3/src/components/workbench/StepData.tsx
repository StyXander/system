/**
 * 步骤2:年报数据与来源台账
 * 每个数字都要能回到同一份正式披露原件。输入时实时更新完整度提示,
 * 点击保存后才持久化并跳转风险页。沿用 app.js 的行状态口径与提示文案。
 */

import { motion } from "framer-motion";
import type { AuditTraceState, EvidenceRow, FieldId } from "../../types";
import { fieldDefinitions, periodKey } from "../../lib/calc";
import {
  dataContextMatchesProject,
  dataHasAnyContent,
  rowCompleteness,
  rowStatusText,
} from "../../lib/validate";
import type { RowStatus } from "../../types";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";

interface StepDataProps {
  state: AuditTraceState;
  onUpdateField: (fieldId: FieldId, key: keyof EvidenceRow, value: string) => void;
  onSaveData: () => boolean;
  onCopySourceFile: () => void;
  showToast: (message: string) => void;
  onGoToRisk: () => void;
}

const statusColor: Record<RowStatus, "default" | "amber" | "teal" | "coral"> = {
  empty: "default",
  partial: "amber",
  complete: "teal",
  blocked: "coral",
  "context-mismatch": "coral",
};

/** 计算行的完整度状态(含上下文不匹配判定) */
function rowStatus(state: AuditTraceState, fieldId: FieldId): RowStatus {
  if (!dataContextMatchesProject(state)) {
    return dataHasAnyContent(state) ? "context-mismatch" : "empty";
  }
  return rowCompleteness(state.data[fieldId], state.project.analysisDate);
}

/** 数据上下文提示文案,沿用 app.js renderDataContextStatus */
function dataContextTip(state: AuditTraceState): string {
  const hasProjectIdentity = state.project.companyName && state.project.currentYear && state.project.previousYear;
  if (!hasProjectIdentity) {
    return "请先保存公司与连续年度;数字只有绑定到对应期间后才能进入计算。";
  }
  if (!dataContextMatchesProject(state)) {
    return "当前数字与项目公司/年度不一致,已阻断计算;请重新载入或录入本期间资料。";
  }
  const originText = state.dataContext.origin === "week1_sample" ? "内置开发样例" : "人工录入区";
  return `当前资料绑定:${state.project.companyName} · ${periodKey(state.project)} · ${originText}。公司或年度变化时不会沿用旧数字。`;
}

const dataFields: Array<{ key: keyof EvidenceRow; label: string; type: string; placeholder: string }> = [
  { key: "value", label: "数值", type: "number", placeholder: "输入金额" },
  { key: "sourceFile", label: "来源文件", type: "text", placeholder: "年报文件名" },
  { key: "disclosureDate", label: "披露日期", type: "date", placeholder: "披露日期" },
  { key: "pdfPage", label: "PDF 页", type: "text", placeholder: "例如 88" },
  { key: "printPage", label: "印刷页", type: "text", placeholder: "页码或原件未标注" },
  { key: "locator", label: "原文 / 表名", type: "text", placeholder: "表名或原文位置" },
];

export function StepData({ state, onUpdateField, onSaveData, onCopySourceFile, showToast, onGoToRisk }: StepDataProps) {
  const { data, project } = state;
  const completeCount = dataContextMatchesProject(state)
    ? fieldDefinitions.filter((f) => rowCompleteness(data[f.id], project.analysisDate) === "complete").length
    : 0;

  const handleSaveData = () => {
    const saved = onSaveData();
    showToast(
      saved
        ? "数据已保存并完成确定性计算"
        : "当前浏览器未允许本地保存,但已完成本页检查",
    );
    onGoToRisk();
  };

  const handleCopySourceFile = () => {
    if (!data.revenue_current.sourceFile) {
      showToast("请先填写第一行的来源文件名");
      return;
    }
    onCopySourceFile();
    showToast("已复制文件名;日期、页码和原文位置仍需逐行核对");
  };

  const getYearLabel = (yearType: "current" | "previous") =>
    yearType === "current" ? project.currentYear || "本年" : project.previousYear || "上年";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="flex flex-col gap-5"
    >
      {/* 面板头 */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="text-[var(--text-muted)] font-mono text-[10px] tracking-[0.16em]">STEP 02</span>
          <h3 className="m-0 mt-2 text-[22px] font-semibold tracking-[-0.02em] text-white">年报数据与来源台账</h3>
          <p className="m-0 mt-1.5 text-[13px] text-[var(--text-secondary)]">每个数字都要能回到同一份正式披露原件。</p>
        </div>
        <Chip variant={completeCount === 4 ? "teal" : "amber"} dot>{completeCount} / 4 完整录入</Chip>
      </div>

      {/* 上下文提示 */}
      <div className="flex items-start gap-2.5 p-4 rounded-[12px] border border-[var(--line-subtle)] bg-white/[0.02]">
        <span className="text-[var(--accent-blue)] mt-0.5 text-[12px]">i</span>
        <p className="m-0 text-[13px] leading-[1.75] text-[var(--text-secondary)]">{dataContextTip(state)}</p>
      </div>

      {/* 数据表格 */}
      <div className="overflow-x-auto rounded-[16px] border border-[var(--line-subtle)]">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr className="bg-[var(--bg-elev-1)] text-left">
              <th className="p-3 font-medium text-[var(--text-muted)] whitespace-nowrap">字段</th>
              <th className="p-3 font-medium text-[var(--text-muted)] whitespace-nowrap">年度</th>
              {dataFields.map((col) => (
                <th key={col.key} className="p-3 font-medium text-[var(--text-muted)] whitespace-nowrap">{col.label}</th>
              ))}
              <th className="p-3 font-medium text-[var(--text-muted)] whitespace-nowrap">状态</th>
            </tr>
          </thead>
          <tbody>
            {fieldDefinitions.map((field) => {
              const row = data[field.id];
              const status = rowStatus(state, field.id);
              return (
                <tr key={field.id} className="border-t border-[var(--line-subtle)] bg-[var(--bg-elev-2)]">
                  <td className="p-3 font-medium text-white whitespace-nowrap">{field.label}</td>
                  <td className="p-3 text-[var(--text-secondary)] font-mono whitespace-nowrap">{getYearLabel(field.yearType)}</td>
                  {dataFields.map((col) => (
                    <td key={col.key} className="p-2">
                      <input
                        type={col.type}
                        value={row[col.key]}
                        step={col.type === "number" ? "any" : undefined}
                        placeholder={col.placeholder}
                        aria-label={`${field.label} ${col.placeholder}`}
                        onChange={(e) => onUpdateField(field.id, col.key, e.target.value)}
                        className="w-full min-w-[110px] h-[38px] px-2.5 rounded-[8px] bg-[var(--bg-base)] border border-[var(--line-subtle)] text-[12px] text-white placeholder:text-[var(--text-muted)] tabular-nums focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors"
                      />
                    </td>
                  ))}
                  <td className="p-3 whitespace-nowrap">
                    <Chip variant={statusColor[status]} dot>{rowStatusText(status)}</Chip>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 表脚 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <p className="m-0 text-[12px] leading-[1.7] text-[var(--text-muted)]">
          <strong className="text-[var(--text-secondary)]">不得猜测:</strong> 找不到印刷页码时记录"原件未标注";解析失败时转人工结构化录入并交叉复核。
        </p>
        <div className="flex gap-3 shrink-0">
          <Button variant="secondary" size="sm" onClick={handleCopySourceFile}>复制第一行文件名</Button>
          <Button variant="primary" size="sm" onClick={handleSaveData}>
            保存、计算并查看风险页
            <span aria-hidden="true">→</span>
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
