/**
 * 步骤1:新建预审项目
 * 表单字段:公司、T0、场景、行业、本年/上年年度、金额单位。
 * 提交时校验年度连续,保存后进入数据页;切换单位立即等值换算。
 * 沿用 app.js readProjectForm / bindEvents 的项目逻辑与提示文案。
 */

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { AuditScene, AmountUnit, AuditTraceState, ProjectInfo } from "../../types";
import { periodKey, projectFieldsComplete } from "../../lib/calc";
import { samplePeriodKeys, week1SampleCompany, week1SamplePeriods } from "../../lib/sample";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import type { ProjectChangeInfo } from "../../hooks/useAuditTraceStore";

interface StepProjectProps {
  state: AuditTraceState;
  onSaveProject: (next: ProjectInfo) => ProjectChangeInfo;
  onLoadSample: (requestedPeriod: string, scene?: string, industry?: string) => boolean;
  onClearAll: () => void;
  showToast: (message: string) => void;
  onGoToData: () => void;
}

const sceneOptions: AuditScene[] = ["新客户业务承接", "续聘复核", "审计计划"];
const unitOptions: AmountUnit[] = ["元", "万元", "百万元"];

/** 根据 saveProject 返回的变更信息生成提示文案,沿用 app.js */
function projectToast(info: ProjectChangeInfo, unit: AmountUnit): string {
  if (info.samplePeriodSwitched) {
    return `已切换为开发样例;数字、来源文件和页码已同步更新`;
  }
  if (info.staleDataCleared) {
    return "公司或年度已变化;旧数字和来源已清空,请录入本期间资料";
  }
  if (info.amountsConverted) {
    return `项目已保存,金额已自动换算为${unit}`;
  }
  return "项目字段已保存在本浏览器";
}

export function StepProject({ state, onSaveProject, onLoadSample, onClearAll, showToast, onGoToData }: StepProjectProps) {
  // 本地表单状态,初始来自 store;store 因样例载入/清空变化时同步
  const [form, setForm] = useState<ProjectInfo>(state.project);
  const [yearError, setYearError] = useState("");

  useEffect(() => {
    setForm(state.project);
  }, [state.project]);

  const completed = projectFieldsComplete(form);

  const update = <K extends keyof ProjectInfo>(key: K, value: ProjectInfo[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (key === "currentYear" || key === "previousYear") setYearError("");
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // 本年与上年必须连续(本年 = 上年 + 1),否则阻断保存
    const current = Number(form.currentYear);
    const previous = Number(form.previousYear);
    if (!(Number.isInteger(current) && Number.isInteger(previous) && current === previous + 1)) {
      setYearError("上年必须正好比本年早一年,例如 2024 / 2023。");
      return;
    }
    const info = onSaveProject(form);
    showToast(projectToast(info, form.amountUnit));
    onGoToData();
  };

  const handleUnitChange = (unit: AmountUnit) => {
    const next = { ...form, amountUnit: unit };
    setForm(next);
    const info = onSaveProject(next);
    showToast(
      info.amountsConverted
        ? `已等值换算为${unit};增长率不会改变`
        : `金额单位已改为${unit}`,
    );
  };

  const handleLoadSample = () => {
    // 主动点击才覆盖当前录入,避免样例数据被误当成用户自己的项目
    if (projectFieldsComplete(form) && !window.confirm("载入第一周开发样例会覆盖当前页面中的项目和数据,是否继续?")) {
      return;
    }
    // 优先使用当前表单填写的年度,不存在时回退到 2025/2024
    const selected = `${form.currentYear.trim()}/${form.previousYear.trim()}`;
    const known = (week1SamplePeriods as Record<string, unknown>)[selected] ? selected : "2025/2024";
    onLoadSample(known, form.scene, form.industry);
    showToast(`${known} 开发样例已载入;数字、来源文件和页码已按年度绑定`);
  };

  const handleClear = () => {
    if (!window.confirm("确定清空当前浏览器中保存的项目、数据和复核说明吗?")) return;
    onClearAll();
    showToast("本机保存的原型内容已清空");
  };

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
          <span className="text-[var(--text-muted)] font-mono text-[10px] tracking-[0.16em]">STEP 01</span>
          <h3 className="m-0 mt-2 text-[22px] font-semibold tracking-[-0.02em] text-white">新建预审项目</h3>
          <p className="m-0 mt-1.5 text-[13px] text-[var(--text-secondary)]">先确定分析对象、截止时点与使用场景。</p>
        </div>
        <Chip variant={completed ? "teal" : "default"} dot>{completed ? "项目字段已保存" : "尚未开始"}</Chip>
      </div>

      <form onSubmit={handleSubmit} className="grid gap-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <label className="grid gap-2">
            <span className="text-[var(--text-secondary)] text-[13px]">公司 / 案例名称</span>
            <input
              value={form.companyName}
              onChange={(e) => update("companyName", e.target.value)}
              placeholder="由团队确认后填写"
              autoComplete="off"
              required
              className="h-[44px] px-3.5 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[14px] text-white placeholder:text-[var(--text-muted)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors"
            />
          </label>
          <label className="grid gap-2">
            <span className="text-[var(--text-secondary)] text-[13px]">分析截止日 T0</span>
            <input
              type="date"
              value={form.analysisDate}
              onChange={(e) => update("analysisDate", e.target.value)}
              required
              className="h-[44px] px-3.5 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[14px] text-white focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors"
            />
          </label>
          <label className="grid gap-2">
            <span className="text-[var(--text-secondary)] text-[13px]">分析场景</span>
            <select
              value={form.scene}
              onChange={(e) => update("scene", e.target.value as AuditScene)}
              className="h-[44px] px-3.5 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[14px] text-white focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors"
            >
              {sceneOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-2">
            <span className="text-[var(--text-secondary)] text-[13px]">所属行业(可稍后补)</span>
            <input
              value={form.industry}
              onChange={(e) => update("industry", e.target.value)}
              placeholder="由团队确认后填写"
              autoComplete="off"
              className="h-[44px] px-3.5 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[14px] text-white placeholder:text-[var(--text-muted)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors"
            />
          </label>
          <label className="grid gap-2">
            <span className="text-[var(--text-secondary)] text-[13px]">本年年度</span>
            <input
              type="number"
              min={2000}
              max={2100}
              value={form.currentYear}
              onChange={(e) => update("currentYear", e.target.value)}
              placeholder="例如 2025"
              required
              className="h-[44px] px-3.5 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[14px] text-white placeholder:text-[var(--text-muted)] tabular-nums focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors"
            />
          </label>
          <label className="grid gap-2">
            <span className="text-[var(--text-secondary)] text-[13px]">上年年度</span>
            <input
              type="number"
              min={2000}
              max={2100}
              value={form.previousYear}
              onChange={(e) => update("previousYear", e.target.value)}
              placeholder="例如 2024"
              required
              aria-invalid={Boolean(yearError)}
              className="h-[44px] px-3.5 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[14px] text-white placeholder:text-[var(--text-muted)] tabular-nums focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors aria-[invalid=true]:border-[var(--accent-coral)]"
            />
            {yearError && <small className="text-[var(--accent-coral)] text-[11px]">{yearError}</small>}
          </label>
          <label className="grid gap-2 sm:col-span-2">
            <span className="text-[var(--text-secondary)] text-[13px]">
              金额单位 <small className="text-[var(--text-muted)]">切换后自动换算已录入金额</small>
            </span>
            <select
              value={form.amountUnit}
              onChange={(e) => handleUnitChange(e.target.value as AmountUnit)}
              className="h-[44px] px-3.5 rounded-[10px] bg-[var(--bg-elev-2)] border border-[var(--line-subtle)] text-[14px] text-white focus:border-[var(--accent-blue)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-colors"
            >
              {unitOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </label>
        </div>

        {/* 提示 */}
        <div className="flex items-start gap-2.5 p-4 rounded-[12px] border border-[var(--line-subtle)] bg-white/[0.02]">
          <span className="text-[var(--accent-blue)] mt-0.5 text-[12px]">i</span>
          <p className="m-0 text-[13px] leading-[1.75] text-[var(--text-secondary)]">当前只使用 T0 前公开资料形成待核查线索,不形成审计结论。</p>
        </div>

        {/* 样例载入 */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-[14px] border border-[var(--accent-blue)]/20 bg-[var(--accent-blue)]/[0.04]">
          <div className="max-w-[640px]">
            <strong className="text-white text-[14px]">第一周开发样例</strong>
            <p className="m-0 mt-1 text-[12px] leading-[1.7] text-[var(--text-secondary)]">
              支持{week1SampleCompany} {samplePeriodKeys.join("、")} 三组连续年度;数字、来源文件和页码整组绑定。非冻结案例,另一名队员人工复核仍待完成。
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={handleLoadSample} type="button">载入样例</Button>
        </div>

        {/* 操作 */}
        <div className="flex justify-between gap-3 pt-1">
          <Button variant="secondary" size="sm" onClick={handleClear} type="button">清空本机内容</Button>
          <Button variant="primary" size="sm" type="submit">
            保存并进入数据页
            <span aria-hidden="true">→</span>
          </Button>
        </div>
      </form>
    </motion.div>
  );
}
