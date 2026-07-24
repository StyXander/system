/**
 * 审迹智链 AuditTrace · 状态管理与 localStorage 持久化
 * 从 audittrace-local-static/app.js 移植,改为基于 useSyncExternalStore 的外部 store。
 *
 * localStorage key 保持 audittrace_week1_state_v2,以兼容已有本地数据。
 * 所有内容只保存在当前浏览器,不上传到任何服务。
 */

import type { AuditScene, AuditTraceState, DataContext, ReviewInfo } from "../types";
import { createEmptyData } from "./calc";

/** localStorage 键名:保持 v2 以兼容第一周已有本地数据 */
export const STORAGE_KEY = "audittrace_week1_state_v2";

/** 创建默认复核状态 */
export function createDefaultReview(): ReviewInfo {
  return { status: "未复核", note: "" };
}

/** 创建空数据上下文 */
export function createEmptyDataContext(): DataContext {
  return { companyName: "", currentYear: "", previousYear: "", origin: "manual" };
}

/** 默认状态:保持空白,避免首次打开时出现貌似真实的公司或结果 */
export const defaultState: AuditTraceState = {
  project: {
    companyName: "",
    analysisDate: "",
    scene: "新客户业务承接" as AuditScene,
    industry: "",
    currentYear: "",
    previousYear: "",
    amountUnit: "万元",
  },
  dataContext: createEmptyDataContext(),
  data: createEmptyData(),
  review: createDefaultReview(),
};

/** 深拷贝默认状态 */
export function cloneDefaultState(): AuditTraceState {
  return JSON.parse(JSON.stringify(defaultState)) as AuditTraceState;
}

/**
 * 从 localStorage 加载状态
 * 页面升级后可能残留旧字段,只合并本版认识的数据结构。
 */
export function loadState(): AuditTraceState {
  try {
    const saved = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    if (!saved) return cloneDefaultState();

    const parsed = JSON.parse(saved) as Partial<AuditTraceState>;
    const merged = cloneDefaultState();
    merged.project = { ...merged.project, ...(parsed.project || {}) };
    merged.dataContext = { ...merged.dataContext, ...(parsed.dataContext || {}) };
    merged.review = { ...merged.review, ...(parsed.review || {}) };

    const parsedData = (parsed.data || {}) as Record<string, unknown>;
    (Object.keys(merged.data) as Array<keyof typeof merged.data>).forEach((fieldId) => {
      const row = parsedData[fieldId] as Record<string, unknown> | undefined;
      if (row && typeof row === "object") {
        merged.data[fieldId] = { ...merged.data[fieldId], ...row };
      }
    });

    return merged;
  } catch (error) {
    console.warn("本地内容读取失败,已回到空白状态。", error);
    return cloneDefaultState();
  }
}

/** 保存状态到 localStorage */
export function saveState(state: AuditTraceState): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch (error) {
    console.warn("浏览器不允许保存本地内容。", error);
    return false;
  }
}

/* ============================================================
 * 外部 Store:基于发布-订阅模式,配合 React 19 的 useSyncExternalStore
 * ============================================================ */

type Listener = () => void;

let currentState: AuditTraceState = loadState();
const listeners = new Set<Listener>();

/** 订阅状态变化,返回取消订阅函数 */
export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** 获取当前状态快照(供 useSyncExternalStore 使用) */
export function getSnapshot(): AuditTraceState {
  return currentState;
}

/** 更新状态并通知所有订阅者 */
export function setState(updater: (prev: AuditTraceState) => AuditTraceState): void {
  currentState = updater(currentState);
  listeners.forEach((listener) => listener());
}

/** 更新状态并持久化到 localStorage */
export function setStateAndSave(updater: (prev: AuditTraceState) => AuditTraceState): boolean {
  setState(updater);
  return saveState(currentState);
}

/** 重置为默认状态并持久化 */
export function resetState(): void {
  setState(() => cloneDefaultState());
  saveState(currentState);
}
