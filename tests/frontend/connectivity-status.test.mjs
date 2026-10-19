/* 状态分类唯一来源的最小负例集：这些断言就是审查报告里被点名的错法。 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const S = require('../../assets/official-v4/connectivity-status.js');

const check = (patch = {}) => ({
  check_id: 'CHECK-0001',
  operator: 'equal',
  criteria_status: 'unknown',
  calculation_status: 'not_comparable',
  conditions: [
    {name: '主体', status: 'supported'},
    {name: '期间', status: 'supported'},
    {name: '定义', status: 'unknown'},
    {name: '范围', status: 'supported'},
    {name: '单位', status: 'supported'}
  ],
  calculation: {gate: {conclusion: '暂不能直接比较', missing: ['定义']}},
  ...patch
});

test('不可比关系不得归入“暂未发现矛盾”', () => {
  const row = check();
  assert.equal(S.programLevel(row).key, 'insufficient');
  assert.equal(S.conflictState(row).key, 'unknown');
  assert.notEqual(S.conflictState(row).tone, 'ok');
});

test('AI 的 insufficient_basis / not_comparable 不产生绿色倾向', () => {
  const run = {checks: [check()], ai_analyses: [
    {check_id: 'CHECK-0001', verdict: 'insufficient_basis', status: 'current'},
    {check_id: 'CHECK-0002', verdict: 'not_comparable', status: 'current'}
  ]};
  for (const verdict of ['insufficient_basis', 'not_comparable']) {
    const state = S.aiState(run, {check_id: 'CHECK-0001', calculation: {}});
    assert.equal(state.tone.startsWith('ai'), true);
    assert.notEqual(state.tone, 'ok');
    assert.notEqual(state.key, 'lean');
  }
});

test('AI 倾向一致与程序不可比并存时，标记 AI 不得覆盖程序', () => {
  const row = check();
  const run = {checks: [row], ai_analyses: [{check_id: row.check_id, verdict: 'lean_consistent', status: 'current'}]};
  assert.equal(S.aiState(run, row).key, 'lean');
  assert.equal(S.aiCoversProgram(run, row), true);
  assert.equal(S.conflictState(row).key, 'unknown');
});

test('正式复算完成才进入“暂未发现矛盾”', () => {
  const row = check({criteria_status: 'supported', calculation_status: 'consistent', calculation: {residual: '0'}});
  assert.equal(S.programLevel(row).key, 'formal');
  assert.equal(S.conflictState(row).key, 'none');
});

test('显示精度假设内相容只是条件试算，不是正式一致', () => {
  const row = check({criteria_status: 'supported', calculation_status: 'not_comparable',
    calculation: {gate: {conclusion: '暂不能直接比较'}, conclusion_level: 'assumption_compatible'}});
  assert.equal(S.programLevel(row).key, 'conditional');
  assert.equal(S.conflictState(row).key, 'unknown');
});

test('未解释差额进入潜在矛盾', () => {
  const row = check({criteria_status: 'supported', calculation_status: 'unexplained_difference', calculation: {residual: '183817.50'}});
  assert.equal(S.programLevel(row).key, 'conflict');
  assert.equal(S.conflictState(row).key, 'potential');
});

test('叙述类关系不参与数值矛盾分母', () => {
  const row = check({operator: 'narrative', criteria_status: 'unknown', calculation_status: 'not_applicable', calculation: {}});
  const summary = S.summarize({checks: [row]});
  assert.equal(summary.levels.not_applicable.value, 1);
  assert.equal(summary.evaluated, 0);
  assert.equal(summary.conflicts.none.denominator, 0);
});

test('四个分级计数互斥且合计等于关系总数', () => {
  const rows = [
    check({check_id: 'C1'}),
    check({check_id: 'C2', criteria_status: 'supported', calculation_status: 'consistent', calculation: {residual: '0'}}),
    check({check_id: 'C3', criteria_status: 'supported', calculation_status: 'not_comparable', calculation: {gate: {conclusion: '暂不能直接比较'}}}),
    check({check_id: 'C4', criteria_status: 'conflicting', calculation_status: 'not_comparable', calculation: {gate: {}}})
  ];
  const summary = S.summarize({checks: rows});
  const total = Object.values(summary.levels).reduce((sum, level) => sum + level.value, 0);
  assert.equal(summary.total, 4);
  assert.equal(total, 4);
  assert.equal(summary.levels.formal.value, 1);
  assert.equal(summary.levels.conflict.value, 1);
  assert.equal(summary.conflicts.unknown.value, 2);
});

test('一句话结论必须写明“暂不能判断不等于没有问题”', () => {
  const summary = S.summarize({checks: [check()], ai_analyses: []});
  const sentence = S.verdictSentence(summary);
  assert.match(sentence, /暂不能判断/);
  assert.match(sentence, /不等于“没有问题”/);
});

test('缺少 conclusion_level 的旧合同按既有状态字段降级，不报错', () => {
  const row = check({calculation: {gate: {}, residual: null}});
  assert.doesNotThrow(() => S.summarize({checks: [row]}));
  assert.equal(S.summarize({checks: [row]}).total, 1);
});

test('旧合同的 hypothetical 算术参考不能把门禁关系升级为条件试算', () => {
  const row = check({hypothetical: {residual: '0', expression: '449183817.50-449000000'}});
  assert.equal(S.programLevel(row).key, 'insufficient');
  assert.equal(S.conflictState(row).key, 'unknown');
});

test('只有真正跑过的精度假设且区间含 0 才算条件试算', () => {
  const row = check({criteria_status: 'supported', calculation_status: 'not_comparable',
    calculation: {gate: {}, assumption_check: {status: 'passed', contains_zero: true, assumption_note: '按显示两位小数建立区间'}}});
  assert.equal(S.programLevel(row).key, 'conditional');
  assert.equal(S.conflictState(row).key, 'unknown');
});

test('关系类型在范围冲突时优先显示范围冲突', () => {
  const row = check({operator: 'sum', conditions: [{name: '范围', status: 'conflicting'}]});
  assert.equal(S.relationType(row).key, 'scope_conflict');
  const pending = check({operator: 'sum', conditions: [{name: '范围', status: 'unknown'}]});
  assert.equal(S.relationType(pending).pending, '范围待证');
});
