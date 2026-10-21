/* Python 实际生成六状态结果，Node 运行前端分类和呈现函数核对同源合同。 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { readFileSync, existsSync } = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const ST = require(path.join(root, 'assets/official-v4/connectivity-status.js'));
const source = readFileSync(path.join(root, 'assets/official-v4/connectivity.js'), 'utf8');
const python = process.env.AUDITTRACE_PYTHON || [
  path.join(root, 'backend/.venv/Scripts/python.exe'),
  path.join(root, '../审迹智链系统/backend/.venv/Scripts/python.exe'),
].find(existsSync) || 'python';
const generated = spawnSync(python, ['-c', [
  'import json',
  'from test_round3_status_contract import status_run',
  'from app.connectivity_overview import build_overview',
  'run=status_run()',
  'run.overview=build_overview(run)',
  'print(json.dumps(run.model_dump(mode="json"),ensure_ascii=False))',
].join('\n')], { cwd: root, encoding: 'utf8', timeout: 30000,
  env: {...process.env, PYTHONIOENCODING: 'utf-8',
    PYTHONPATH: [path.join(root,'backend'),path.join(root,'backend/tests')].join(path.delimiter)} });
assert.equal(generated.status, 0, generated.stderr || generated.error?.message);
const run = JSON.parse(generated.stdout);

function extract(name, dependencies) {
  const match = source.match(new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n  \\}`));
  assert.ok(match, `未找到真实前端函数 ${name}`);
  return new Function(...Object.keys(dependencies), `return (${match[0]});`)(...Object.values(dependencies));
}
const escape = value => String(value ?? '');
const withOpinions = () => ({...run, ai_analyses: [
  {check_id:'F', verdict:'lean_consistent', status:'current'},
  {check_id:'T', verdict:'plausible_explanation', status:'current'},
  {check_id:'L', verdict:'insufficient_basis', status:'current'},
  {check_id:'I', verdict:'not_comparable', status:'current'},
  {check_id:'C', verdict:'potential_conflict', status:'current'},
  {check_id:'N', verdict:'lean_consistent', status:'needs_refresh'},
]});

test('Python 与 JS 六状态逐项 ID、数量和分母一致', () => {
  const summary = ST.summarize(run);
  for (const [key, backend] of Object.entries(run.overview.program_levels)) {
    const frontend = summary.levels[key];
    assert.deepEqual(frontend.items, backend.items, key);
    assert.equal(frontend.value, backend.value, key);
    assert.equal(frontend.denominator, backend.denominator, key);
    frontend.items.forEach(id => assert.equal(ST.programLevel(run.checks.find(c=>c.check_id===id)).key,key));
  }
  assert.equal(Object.values(summary.levels).reduce((sum,row)=>sum+row.value,0),run.checks.length);
});

test('合理解释和倾向一致分别计数，旧意见不混入当前意见', () => {
  const current = withOpinions(), summary = ST.summarize(current);
  assert.equal(summary.ai.byVerdict.lean, 1);
  assert.equal(summary.ai.byVerdict.plausible, 1);
  assert.equal(summary.ai.value, 5);
  assert.equal(ST.aiState(current,{check_id:'T'}).key,'plausible');
  assert.notEqual(ST.aiState(current,{check_id:'T'}).label,ST.aiState(current,{check_id:'F'}).label);
  for (const row of current.checks) assert.notEqual(ST.aiState(current,row).tone,'ok');
  for (const id of ['T','L','I','N']) assert.notEqual(ST.conflictState(current.checks.find(c=>c.check_id===id)).tone,'ok');
});

test('网页摘要与证据线显示独立合理解释和六级数量', () => {
  const current = withOpinions(), summary = ST.summarize(current);
  const lanes = extract('lanes',{escape});
  const laneHtml = lanes(current,summary);
  assert.match(laneHtml,/倾向一致 1 · 合理解释 1/);
  assert.match(laneHtml,/有限支持 1 · 依据不足 1/);
  assert.doesNotMatch(laneHtml,/AI 倾向“未见矛盾”/);
  const elements = new Map();
  const $ = id => {if(!elements.has(id)) elements.set(id,{});return elements.get(id);};
  const render = extract('renderOverview',{current:()=>current,$,ST,escape,state:{filter:'all'},
    keyRelations:()=>'',lanes,systemPanel:()=>'',priorityBadge:()=>'',renderRelation:()=>{}});
  render();
  const html = $('cn-fourq').innerHTML;
  assert.match(html,/合理解释 1/);
  assert.match(html,/倾向一致 1/);
  assert.match(html,/当前不可比 1/);
  for(const key of Object.keys(run.overview.program_levels)) assert.match(html,new RegExp(`data-level="${key}"`));
});

test('算术参考不能显示为条件试算，未知前提不能输出正式差额', () => {
  const block = extract('calculationBlock',{escape,levelOf:ST.programLevel,refs:()=>''});
  const trial = block(run.checks.find(c=>c.check_id==='T'));
  const insufficient = block(run.checks.find(c=>c.check_id==='I'));
  assert.match(trial,/条件试算（仅在列明假设下相容）/);
  assert.match(insufficient,/假设诊断（算术参考，不计条件试算）/);
  assert.doesNotMatch(insufficient,/正式差额：/);
  assert.match(block(run.checks.find(c=>c.check_id==='F')),/正式差额：/);
});
