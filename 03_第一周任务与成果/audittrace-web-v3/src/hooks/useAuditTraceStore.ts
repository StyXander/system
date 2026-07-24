/**
 * 审迹智链 AuditTrace · 状态 hook
 * 基于 React 19 的 useSyncExternalStore,订阅外部 store。
 * 组件层只调用此 hook,不直接操作 store 内部结构。
 */

import { useCallback, useSyncExternalStore } from "react";
import type { AuditTraceState, EvidenceRow, FieldId, ProjectInfo, ReviewInfo } from "../types";
import { convertDataAmounts } from "../lib/calc";
import { dataHasAnyContent, projectIdentityChanged } from "../lib/validate";
import { loadSamplePeriodData, week1SampleCompany, week1SamplePeriods } from "../lib/sample";
import {
  cloneDefaultState,
  createEmptyDataContext,
  getSnapshot,
  resetState,
  saveState,
  setState,
  setStateAndSave,
  subscribe,
} from "../lib/store";
import { periodKey } from "../lib/calc";

/** 读取项目表单时的变更信息 */
export interface ProjectChangeInfo {
  amountUnitChanged: boolean;
  amountsConverted: boolean;
  contextChanged: boolean;
  samplePeriodSwitched: boolean;
  staleDataCleared: boolean;
}

/** 操作函数集合 */
export interface AuditTraceActions {
  /** 更新项目字段并持久化 */
  saveProject: (next: ProjectInfo) => ProjectChangeInfo;
  /** 更新单条数据字段(不持久化,等待显式保存) */
  updateDataField: (fieldId: FieldId, key: keyof EvidenceRow, value: string) => void;
  /** 保存当前数据并持久化 */
  saveData: () => boolean;
  /** 更新复核信息并持久化 */
  saveReview: (review: ReviewInfo) => boolean;
  /** 载入开发样例 */
  loadSample: (requestedPeriod: string, scene?: string, industry?: string) => boolean;
  /** 清空所有内容 */
  clearAll: () => void;
  /** 复制第一行文件名到所有空行 */
  copySourceFile: () => void;
}

/** 状态 hook:返回当前状态与操作函数 */
export function useAuditTraceStore(): [AuditTraceState, AuditTraceActions] {
  const state = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  const saveProject = useCallback((next: ProjectInfo): ProjectChangeInfo => {
    let info: ProjectChangeInfo = {
      amountUnitChanged: false,
      amountsConverted: false,
      contextChanged: false,
      samplePeriodSwitched: false,
      staleDataCleared: false,
    };

    setStateAndSave((prev) => {
      const previousProject = { ...prev.project };
      const previousAmountUnit = previousProject.amountUnit;
      const contextChanged = projectIdentityChanged(previousProject, next);

      let newData = prev.data;
      let newDataContext = prev.dataContext;
      let newReview = prev.review;

      if (contextChanged) {
        // 公司或年度改变时,数据必须整组切换或清空,禁止只替换年度标签。
        const canSwitchKnownSample =
          prev.dataContext.origin === "week1_sample" &&
          next.companyName === week1SampleCompany &&
          Boolean(
            (week1SamplePeriods as Record<string, unknown>)[periodKey(next)],
          );
        if (canSwitchKnownSample) {
          const draft = { ...prev, project: next };
          const ok = loadSamplePeriodData(draft, next);
          if (ok) {
            newData = draft.data;
            newDataContext = draft.dataContext;
            newReview = draft.review;
            info.samplePeriodSwitched = true;
          }
        } else {
          info.staleDataCleared = dataHasAnyContent(prev);
          newData = { ...prev.data };
          // 清空每行的值
          (Object.keys(newData) as FieldId[]).forEach((fid) => {
            newData[fid] = {
              value: "",
              sourceFile: "",
              disclosureDate: "",
              pdfPage: "",
              printPage: "",
              locator: "",
            };
          });
          newDataContext = {
            companyName: next.companyName,
            currentYear: next.currentYear,
            previousYear: next.previousYear,
            origin: "manual",
          };
          newReview = { status: "未复核", note: "" };
        }
      } else {
        // 公司和年度未变,只换算金额单位
        const amountUnitChanged = previousAmountUnit !== next.amountUnit;
        if (amountUnitChanged) {
          newData = convertDataAmounts(prev.data, previousAmountUnit, next.amountUnit);
          info.amountUnitChanged = true;
          info.amountsConverted = true;
        }
        if (!dataHasAnyContent({ ...prev, data: newData })) {
          newDataContext = {
            companyName: next.companyName,
            currentYear: next.currentYear,
            previousYear: next.previousYear,
            origin: "manual",
          };
        }
      }

      info.contextChanged = contextChanged;

      return {
        ...prev,
        project: next,
        data: newData,
        dataContext: newDataContext,
        review: newReview,
      };
    });

    return info;
  }, []);

  const updateDataField = useCallback(
    (fieldId: FieldId, key: keyof EvidenceRow, value: string) => {
      setState((prev) => ({
        ...prev,
        data: {
          ...prev.data,
          [fieldId]: { ...prev.data[fieldId], [key]: value },
        },
        // 输入时标记为人工录入
        dataContext: {
          ...prev.dataContext,
          companyName: prev.project.companyName,
          currentYear: prev.project.currentYear,
          previousYear: prev.project.previousYear,
          origin: "manual",
        },
      }));
    },
    [],
  );

  const saveData = useCallback(() => {
    const state = getSnapshot();
    return saveState(state);
  }, []);

  const saveReview = useCallback((review: ReviewInfo) => {
    setState((prev) => ({ ...prev, review }));
    return saveState(getSnapshot());
  }, []);

  const loadSample = useCallback((requestedPeriod: string, scene?: string, industry?: string) => {
    const known = (week1SamplePeriods as Record<string, unknown>)[requestedPeriod]
      ? requestedPeriod
      : "2025/2024";
    const [currentYear, previousYear] = known.split("/");
    const current = getSnapshot();

    const nextProject: ProjectInfo = {
      companyName: week1SampleCompany,
      analysisDate: "2026-04-28",
      scene: (scene as ProjectInfo["scene"]) || "审计计划",
      industry: industry || "专用设备 / 缝制机械(人工填写)",
      currentYear,
      previousYear,
      amountUnit: current.project.amountUnit,
    };

    setStateAndSave((prev) => {
      const draft: AuditTraceState = { ...prev, project: nextProject };
      loadSamplePeriodData(draft, nextProject);
      return draft;
    });
    return true;
  }, []);

  const clearAll = useCallback(() => {
    resetState();
  }, []);

  const copySourceFile = useCallback(() => {
    setState((prev) => {
      const firstFile = prev.data.revenue_current.sourceFile;
      if (!firstFile) return prev;
      const newData = { ...prev.data };
      (Object.keys(newData) as FieldId[]).forEach((fid) => {
        if (!newData[fid].sourceFile) {
          newData[fid] = { ...newData[fid], sourceFile: firstFile };
        }
      });
      return {
        ...prev,
        data: newData,
        dataContext: {
          ...prev.dataContext,
          companyName: prev.project.companyName,
          currentYear: prev.project.currentYear,
          previousYear: prev.project.previousYear,
          origin: "manual",
        },
      };
    });
  }, []);

  return [
    state,
    { saveProject, updateDataField, saveData, saveReview, loadSample, clearAll, copySourceFile },
  ];
}
