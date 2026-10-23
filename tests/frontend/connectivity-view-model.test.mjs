import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const V=require('../../assets/official-v4/connectivity-view-model.js');
const S=require('../../assets/official-v4/connectivity-status.js');
const base=()=>({company:'证据测试企业',period:'2025',execution_mode:'calculation_only',documents:[{document_id:'E',report_type:'ESG'},{document_id:'F',report_type:'AR'}],
  occurrences:[{occurrence_id:'e',document_id:'E',label:'研发投入',context:'研发投入由费用化和资本化构成',pdf_page:5},{occurrence_id:'f',document_id:'F',label:'研发费用',context:'研发费用为本期费用化支出',pdf_page:10}],
  checks:[{check_id:'C1',title:'研发投入构成',operator:'sum',members:[{occurrence_id:'e',role:'total'},{occurrence_id:'f',role:'component'}],
    conditions:[{name:'范围',status:'unknown',reason:'原文未说明'}],relationship_basis:'text_statement',relationship_evidence:[{occurrence_id:'e',quote:'研发投入由费用化和资本化构成'}],criteria_status:'unknown',calculation_status:'not_comparable',calculation:{},unresolved:['补查资本化支出']}],
  ai_analyses:[],program_hints:[],findings:[],provider_calls:[],agent_steps:[]});

test('双报告定位但前提不足只能呈现线索，不能升级直接关系',()=>{
  const m=V.project(base(),S);assert.equal(m.covered.length,1);assert.equal(m.supported.length,0);assert.equal(m.paths[0].edge,'indirect');assert.equal(m.gaps.length,1);
});
test('跨报告标志不能代替实际年报证据，缺失成员不会补造节点',()=>{
  const r=base();r.checks[0].cross_document=true;r.occurrences.pop();
  const p=V.project(r,S).paths[0];assert.equal(p.financial.length,0);assert.equal(p.both,false);assert.equal(p.members[1].occurrence,undefined);assert.notEqual(p.edge,'supported');
});
test('另一份报告的范围声明不能充当双报告财务关联成员',()=>{
  const r=base();r.checks[0].members=[{occurrence_id:'e',role:'total'}];
  r.checks[0].conditions[0].evidence=[{occurrence_id:'f',quote:'研发费用为本期费用化支出'}];
  const p=V.project(r,S).paths[0];assert.equal(p.both,false);assert.equal(p.financial.length,0);assert.equal(p.cited.length,2);
});
test('引文不在原文中时不能显示已支持或间接引用',()=>{
  const r=base();r.checks[0].relationship_evidence[0].quote='不存在的原文';assert.equal(V.project(r,S).paths[0].edge,'gap');
});
test('有效 AI 意见、过期待刷新意见与驳回意见严格区分',()=>{
  for(const patch of [{status:'needs_refresh'},{status:'current',review_status:'rejected'}]){
    const r=base();r.ai_analyses=[{check_id:'C1',summary:'旧模型解释',...patch}];assert.equal(V.project(r,S).paths[0].ai,null);
  }
  const r=base();r.ai_analyses=[{check_id:'C1',summary:'带条件的解释',status:'current',review_status:'unreviewed'}];assert.equal(V.project(r,S).paths[0].ai.summary,'带条件的解释');
});
test('空结果用未形成关系说明，不能包装零异常',()=>{
  const r=base();r.checks=[];const m=V.project(r,S);assert.equal(m.paths.length,0);assert.match(m.sentence,/无结果不代表零异常/);
});
test('不同企业和报告期间生成各自的结论，不保留前次上下文',()=>{
  const a=base(),b=base();b.company='另一企业';b.period='2024';b.checks=[];
  assert.notEqual(V.project(a,S).sentence,V.project(b,S).sentence);assert.match(V.project(b,S).sentence,/另一企业 2024/);
});
test('历史任务、仅计算与复用研判均保留真实来源标识',()=>{
  const job={status:'completed',result:base()};assert.match(V.provenance(job,false),/历史真实/);assert.match(V.provenance(job,true),/仅计算/);
  job.result.execution_mode='three_agents';job.result.model_status='reused_completed';assert.match(V.provenance(job,true),/无新增模型调用/);
});
test('没有回执不造三角色；失败和真实交接状态来自记录',()=>{
  const r=base();assert.deepEqual(V.collaboration(r,{}),[]);
  r.agent_steps=[{role:'A1',status:'failed'}];r.intelligence_trace=[{kind:'agent_tool_result',producer_role:'A1',consumer_role:'A2',delivered_evidence_ids:['e']}];
  const roles=V.collaboration(r,{});assert.equal(roles.length,1);assert.equal(roles[0].status,'failed');assert.deepEqual(roles[0].events[0].delivered_evidence_ids,['e']);
});
test('执行阶段别名与实际角色合并，保留失败而不补造成功',()=>{
  const r=base();r.agent_steps=[{role:'A1',status:'completed'}];
  let roles=V.collaboration(r,{agent_steps:{challenge:{status:'pending'}}});assert.equal(roles.length,1);assert.equal(roles[0].role,'A1');assert.equal(roles[0].status,'completed');
  r.agent_steps=[];r.provider_calls=[{role:'A2',performed:true,failure_code:'MODEL_PROVIDER_AUTH_FAILED'}];
  roles=V.collaboration(r,{});assert.equal(roles[0].status,'failed');
});
test('优先级采用真实来源，不能为填满界面生成三个等级',()=>{
  const r=base();let m=V.project(r,S);assert.equal(m.priorities.length,0);assert.equal(m.paths[0].priority,null);
  r.program_hints=[{check_id:'C1',priority:'high',priority_reason:'程序登记的缺口'}];m=V.project(r,S);assert.equal(m.priorities.length,1);assert.equal(m.paths[0].priorityReason,'程序登记的缺口');
});
