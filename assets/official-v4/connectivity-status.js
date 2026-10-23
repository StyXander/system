/*!
 * connectivity-status.js — 前端状态分类的唯一来源。
 *
 * 只做“把后端字段翻译成使用者能读懂的状态”这件事，不产生任何业务结论：
 *   1) 程序级别：formal / conditional / limited / insufficient / conflict / not_applicable
 *   2) 矛盾三态：potential（潜在矛盾）/ none（暂未发现矛盾）/ unknown（依据不足或不可比）
 *   3) AI 倾向：独立命名空间，永不带 “ok/绿色” 语义，避免盖住程序状态
 *   4) 计数摘要：每个数字都带分母，级别互斥，合计可核回关系总数
 *
 * 契约：字段缺失时按“未提供”处理并降级展示，不猜测、不补造。
 * 兼容：浏览器挂在 window.AuditTraceStatus；Node 下走 module.exports 以便单测。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AuditTraceStatus = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // 只有这三类计算状态代表“在已支持前提下完成了数值核对”。
  const VERIFIED = new Set(['consistent', 'precision_explained', 'adjustment_explained']);
  const LEVELS = {
    formal: {key: 'formal', label: '正式复算', tone: 'verified', definition: '五项前提均有原文依据，且程序完成数值核对'},
    conditional: {key: 'conditional', label: '条件试算', tone: 'conditional', definition: '仅在写明假设（如显示精度、调节项）时相容，不等于正式确认'},
    limited: {key: 'limited', label: '有限支持', tone: 'limited', definition: '仅有表级或结构依据，或口径支持但算式不可执行，不能作为正式确认'},
    insufficient: {key: 'insufficient', label: '依据不足·不可比', tone: 'neutral', definition: '关键前提缺原文依据，程序不输出正式差额'},
    conflict: {key: 'conflict', label: '口径冲突或未解释差额', tone: 'warn', definition: '口径冲突表示不能直接比较；同口径下的未解释差额另行核查'},
    not_applicable: {key: 'not_applicable', label: '不适用数值计算', tone: 'neutral', definition: '叙述类关系，只记录文字主张，不生成算式'}
  };
  const CONFLICT = {
    potential: {key: 'potential', label: '口径冲突或未解释差额', tone: 'warn', definition: '范围或指标不同不直接说明企业披露错误；须区分口径冲突与数值差异'},
    none: {key: 'none', label: '暂未发现矛盾', tone: 'ok', definition: '前提齐备且程序完成复算，数值上未见差异'},
    unknown: {key: 'unknown', label: '依据不足·不可比', tone: 'neutral', definition: '前提不足或口径不可比，不能判断是否存在矛盾'}
  };
  const AI_STATES = {
    none: {key: 'none', label: 'AI 未研判', tone: 'ai-none', note: '本次未生成 AI 意见，程序结果不受影响'},
    stale: {key: 'stale', label: 'AI 意见待刷新', tone: 'ai-none', note: '证据或计算已变化，旧意见不作为倾向依据'},
    potential: {key: 'potential', label: 'AI 倾向：可能有矛盾', tone: 'ai-warn', note: '模型判断，可能不准确，不替代程序状态'},
    lean: {key: 'lean', label: 'AI 倾向：未见矛盾', tone: 'ai', note: '模型倾向，不等于程序已确认；依据不足时不得读成“没问题”'},
    plausible: {key: 'plausible', label: 'AI 倾向：存在合理解释', tone: 'ai', note: '解释尚需验证，不等于数值一致，也不替代程序状态'},
    insufficient: {key: 'insufficient', label: 'AI：依据不足', tone: 'ai-none', note: '模型未能取得足够依据，不构成“未发现矛盾”'},
    not_comparable: {key: 'not_comparable', label: 'AI：当前不可比', tone: 'ai-none', note: '模型认为口径不可比，与程序的不可比状态一致'}
  };
  const OPERATORS = {
    equal: {key: 'equal', label: '同值核对', note: '同一指标在两处披露应为同一个数'},
    sum: {key: 'sum', label: '组成关系', note: '合计应等于各组成项之和'},
    ratio: {key: 'ratio', label: '比例关系', note: '分子 ÷ 分母 应等于披露比例'},
    occurrences: {key: 'occurrences', label: '多位置核对', note: '同一报告内多处披露逐项比较'},
    narrative: {key: 'narrative', label: '叙述关系', note: '文字主张与绑定数值的方向/幅度核对'}
  };

  const has = value => value !== null && value !== undefined && value !== '';
  const list = value => Array.isArray(value) ? value : [];
  const conditionsOf = check => list(check && check.conditions);
  const condition = (check, name) => conditionsOf(check).find(item => item && item.name === name);

  function programLevel(check) {
    const calc = (check && check.calculation) || {};
    if (check && check.criteria_status === 'conflicting') return LEVELS.conflict;
    const declared = check && (check.conclusion_level && check.conclusion_level !== "not_assessed" ? check.conclusion_level : calc.conclusion_level);
    if (declared === "limited_support") return LEVELS.limited;
    if (declared === "insufficient_basis") return LEVELS.insufficient;
    if (declared && LEVELS[declared]) return LEVELS[declared];
    if (declared === 'unexplained_difference') return LEVELS.conflict;
    if (declared === 'formal_consistent') return check.criteria_status === 'supported' && !calc.gate ? LEVELS.formal : LEVELS.insufficient;
    if (declared === 'assumption_compatible') return LEVELS.conditional;

    if (!check) return LEVELS.insufficient;
    if (check.operator === 'narrative' || check.calculation_status === 'not_applicable') return LEVELS.not_applicable;

    const criteria = check.criteria_status;
    const status = check.calculation_status;
    const gate = calc.gate;
    if (criteria === 'conflicting' || status === 'unexplained_difference') return LEVELS.conflict;

    const assumption = calc.assumption_check;
    const bridge = calc.scenario_adjustment && list(calc.scenario_adjustment.applied).length > 0;
    // 只有“真正跑过假设检验且区间含 0”或“有据的条件调节”才算条件试算；
    // 旧合同里的 hypothetical 只是算术参考，不能把门禁拦住的关系升级成条件试算。
    const conditional = (assumption && assumption.status && assumption.status !== 'not_run' && assumption.contains_zero)
      || (!gate && bridge);
    if (conditional) return LEVELS.conditional;

    if (criteria === 'supported' && !gate) {
      if (VERIFIED.has(status)) return LEVELS.formal;
      if (status === 'not_comparable' || status === 'not_executable') return LEVELS.limited;
    }
    if (gate || criteria === 'unknown') return LEVELS.insufficient;
    if (VERIFIED.has(status)) return LEVELS.formal;
    return LEVELS.insufficient;
  }

  /* 矛盾三态：只有“正式复算完成”才算暂未发现矛盾；
     条件试算、有限支持、依据不足、不适用一律归入“依据不足·不可比”，
     绝不允许 insufficient_basis / not_comparable 落到绿色的“没问题”。 */
  function conflictState(check) {
    const level = programLevel(check).key;
    if (level === 'conflict') return CONFLICT.potential;
    if (level === 'formal') return CONFLICT.none;
    return CONFLICT.unknown;
  }

  function opinionOf(run, checkId) {
    if (!run) return null;
    return list(run.ai_analyses).find(item => item && item.check_id === checkId)
      || list(run.ai_opinions).find(item => item && item.check_id === checkId)
      || null;
  }

  function aiState(run, check) {
    const opinion = opinionOf(run, check && check.check_id);
    if (!opinion) return Object.assign({}, AI_STATES.none, {opinion: null});
    if (opinion.status === 'needs_refresh') return Object.assign({}, AI_STATES.stale, {opinion});
    const verdict = String(opinion.verdict || '').toLowerCase();
    if (['potential_conflict', 'unexplained', 'likely_error', 'human_review', 'needs_human'].includes(verdict)) {
      return Object.assign({}, AI_STATES.potential, {opinion});
    }
    if (['plausible_explanation', 'explainable_difference', 'probable_explainable'].includes(verdict)) {
      return Object.assign({}, AI_STATES.plausible, {opinion});
    }
    if (['lean_consistent', 'consistent'].includes(verdict)) {
      return Object.assign({}, AI_STATES.lean, {opinion});
    }
    if (verdict === 'not_comparable') return Object.assign({}, AI_STATES.not_comparable, {opinion});
    return Object.assign({}, AI_STATES.insufficient, {opinion});
  }

  /* AI 不得覆盖程序：程序不可比时，任何 AI 倾向都只作为旁注。 */
  function aiCoversProgram(run, check) {
    const level = programLevel(check).key;
    const ai = aiState(run, check);
    return ['insufficient', 'limited', 'conditional'].includes(level) && ['lean', 'plausible'].includes(ai.key);
  }

  function relationType(check) {
    const base = OPERATORS[check && check.operator] || {key: 'unknown', label: '关系待判定', note: '关系类型未登记'};
    const scope = condition(check, '范围');
    if (scope && scope.status === 'conflicting') return {key: 'scope_conflict', label: '范围冲突', note: '两份披露的统计范围不同，不能直接比较'};
    if (scope && scope.status === 'unknown') return Object.assign({}, base, {pending: '范围待证'});
    return base;
  }

  function coverage(check) {
    const rows = conditionsOf(check);
    return {
      total: rows.length,
      supported: rows.filter(item => item.status === 'supported').length,
      unknown: rows.filter(item => !item.status || item.status === 'unknown').length,
      conflicting: rows.filter(item => item.status === 'conflicting').length,
      missing: rows.filter(item => item.status !== 'supported').map(item => item.name)
    };
  }

  function summarize(run) {
    const checks = list(run && run.checks);
    const total = checks.length;
    const buckets = {formal: [], conditional: [], limited: [], insufficient: [], conflict: [], not_applicable: []};
    checks.forEach(check => { buckets[programLevel(check).key].push(check.check_id); });
    const levels = Object.keys(LEVELS).reduce((acc, key) => {
      acc[key] = Object.assign({}, LEVELS[key], {value: buckets[key].length, items: buckets[key], denominator: total});
      return acc;
    }, {});
    const notApplicable = levels.not_applicable.value;
    const evaluable = total - notApplicable;
    const conflicts = Object.keys(CONFLICT).reduce((acc, key) => {
      const items = checks.filter(check => conflictState(check).key === key).map(check => check.check_id);
      acc[key] = Object.assign({}, CONFLICT[key], {value: items.length, items, denominator: key === 'none' ? evaluable : total});
      return acc;
    }, {});
    const opinions = list(run && (run.ai_analyses && run.ai_analyses.length ? run.ai_analyses : run.ai_opinions));
    const current = opinions.filter(item => item && item.status !== 'needs_refresh');
    const byVerdict = {};
    current.forEach(item => { const key = aiState(run, {check_id: item.check_id}).key; byVerdict[key] = (byVerdict[key] || 0) + 1; });
    const missing = {};
    checks.forEach(check => {
      conditionsOf(check).forEach(item => {
        if (item && item.status !== 'supported') missing[item.name] = (missing[item.name] || 0) + 1;
      });
    });
    return {
      total,
      evaluated: evaluable,
      levels,
      conflicts,
      ai: {value: current.length, declared: opinions.length, denominator: total, byVerdict,
        coversProgram: checks.filter(check => aiCoversProgram(run, check)).map(check => check.check_id)},
      gaps: Object.entries(missing).sort((a, b) => b[1] - a[1]).map(([name, count]) => ({name, count})),
      system: {
        rejections: list(run && run.candidate_rejections),
        failures: list(run && run.coverage).reduce((sum, item) => sum + list(item.failed_pages).length, 0)
      }
    };
  }

  function verdictSentence(summary) {
    if (!summary || !summary.total) return '本次未生成可核对的关系；请查看搜索覆盖与运行记录。';
    const {total, levels, conflicts, ai} = summary;
    const parts = [];
    parts.push(`本次共 ${total} 项关系`);
    if (levels.formal.value) parts.push(`${levels.formal.value} 项在前提支持下完成复算且未见差异`);
    if (levels.conflict.value) parts.push(`${levels.conflict.value} 项存在口径冲突或未解释差额`);
    const unclear = [];
    if (levels.conditional.value) unclear.push(`${levels.conditional.value} 项仅在写明假设时相容`);
    if (levels.limited.value) unclear.push(`${levels.limited.value} 项仅获有限证据支持`);
    if (levels.insufficient.value) unclear.push(`${levels.insufficient.value} 项依据不足或不可比`);
    if (unclear.length) parts.push(`${unclear.join('、')}，暂不能判断`);
    if (levels.not_applicable.value) parts.push(`${levels.not_applicable.value} 项为叙述类关系，不生成算式`);
    const head = `${parts.join('；')}。`;
    const aiText = ai.value ? `本次 ${ai.value}/${total} 项有 AI 意见，AI 倾向不改变程序状态。` : '本次未生成 AI 意见，程序结果与原文仍可查看。';
    const tail = conflicts.unknown.value
      ? `“暂不能判断”不等于“没有问题”；${aiText}`
      : aiText;
    return head + tail;
  }

  return {
    LEVELS, CONFLICT, AI_STATES, OPERATORS,
    programLevel, conflictState, aiState, aiCoversProgram, relationType, coverage,
    summarize, verdictSentence, opinionOf
  };
});
