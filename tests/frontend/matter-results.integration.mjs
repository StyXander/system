/* DOM渲染集成检查；不替代浏览器视觉检查。依赖同controller.integration.mjs。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import vm from 'node:vm';
const require=createRequire(import.meta.url);let parseHTML;
try{({parseHTML}=require(process.env.AUDITTRACE_TEST_NODE_MODULES?`${process.env.AUDITTRACE_TEST_NODE_MODULES}/linkedom`:'linkedom'));}catch{}
const flush=async()=>{for(let i=0;i<5;i++)await new Promise(setImmediate);};
test('result renders at most ten pending candidates and loads the evidence chain only on selection',{skip:!parseHTML},async()=>{
  const {window,document}=parseHTML(fs.readFileSync(new URL('../../index.html',import.meta.url),'utf8'));
  Object.defineProperty(window.HTMLSelectElement.prototype,'options',{get(){return [...this.querySelectorAll('option')];}});
  Object.defineProperty(window.HTMLSelectElement.prototype,'value',{get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(value){this.options.forEach(o=>{if(o.value===value)o.setAttribute('selected','');else o.removeAttribute('selected');});}});
  const calls=[];
  const run={run_id:'R',company:'合成企业',period:'2025',documents:[],report_set:{as_of_date:'2026-10-27'},
    matter_schema_version:'v1',projection_layer:'summary',model_status:'five_agents_partial',
    matter_overview:{matter_total:90,investigated:1,pending:89},versions:{},
    matters:Array.from({length:90},(_,i)=>({matter_id:'M'+i,name:'合成事项'+i,investigation_status:i?'pending':'partial',identity_status:'candidate',evidence_ids:[]})),
    matter_assessments:[{matter_id:'M0',summary:'证据支持企业披露，财务归属待查',unresolved:['项目明细未取得']}],
    assurance_planning:{risk_findings:[],evidence_requests:[]}};
  const fetch=async path=>{calls.push(path);return {ok:true,json:async()=>path.endsWith('/report-sets')?{documents:[]}:{version:1,result:{...run,matters:[run.matters[0]],matter_evidence:[],matter_assessments:run.matter_assessments}}};};
  const context=vm.createContext({window,document,fetch,CustomEvent:window.CustomEvent,Event:window.Event,console,setTimeout,Date,JSON});
  vm.runInContext(fs.readFileSync(new URL('../../assets/official-v4/connectivity-matters.js',import.meta.url),'utf8'),context);await flush();
  window.AuditTraceMatters.render({task_id:'T',status:'degraded',version:1,result:run,can_modify:false});
  assert.equal(document.querySelector('.cm-candidates').hasAttribute('open'),false);
  assert.equal(document.querySelectorAll('.cm-candidates .cm-list-row').length,10);
  assert(document.querySelector('.cm-investigation-summary').textContent.includes('财务归属待查'));
  assert.equal(calls.filter(p=>p.includes('/matters/')).length,0);
  document.querySelector('[data-cm-select="M0"]').dispatchEvent(new window.Event('click',{bubbles:true}));await flush();
  assert.equal(calls.filter(p=>p.includes('/matters/')).length,1);
  assert.equal(document.querySelectorAll('.cm-evidence-chain>li').length,5);
});
