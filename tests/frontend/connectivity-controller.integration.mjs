/* DOM单元集成检查，不冒充真实浏览器验收。
   AUDITTRACE_TEST_NODE_MODULES=/tmp/audittrace-testdeps/node_modules node --test tests/frontend/connectivity-controller.integration.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const require=createRequire(import.meta.url);
let parseHTML;
try{({parseHTML}=require(process.env.AUDITTRACE_TEST_NODE_MODULES?`${process.env.AUDITTRACE_TEST_NODE_MODULES}/linkedom`:'linkedom'));}catch{}
const flush=async()=>{for(let i=0;i<8;i++)await new Promise(setImmediate);};
test('actual controller keeps polling A during history reads and discards late B', {skip:!parseHTML}, async()=>{
  const {window,document}=parseHTML(fs.readFileSync(new URL('../../index.html',import.meta.url),'utf8'));
  document.documentElement.dataset.connectivityWorkspaceReady='true';
  const storage=new Map(),localStorage={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
  const location={href:'http://unit.invalid/'};
  const history={replaceState:(a,b,url)=>location.href=String(url),pushState:(a,b,url)=>location.href=String(url)};
  const timers=new Map();let timerId=0;
  const setTimeout=fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout=id=>timers.delete(id);
  Object.defineProperty(window.HTMLSelectElement.prototype,'options',{get(){return [...this.querySelectorAll('option')];}});
  Object.defineProperty(window.HTMLSelectElement.prototype,'selectedOptions',{get(){return this.options.filter(o=>o.value===this.value);}});
  Object.defineProperty(window.HTMLSelectElement.prototype,'value',{get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(value){this.options.forEach(o=>{if(o.value===value)o.setAttribute('selected','');else o.removeAttribute('selected');});}});
  const calls=[],renders=[],pending={},errors=[];
  document.addEventListener('audittrace:connectivity-task-error',e=>errors.push(e.detail));
  const result=id=>({task_id:id,status:id==='CONNJOB-AAAAAAAA'?'running':'completed',version:1,can_modify:true,
    result:{run_id:'RUN-'+id,company:id,period:'2025',documents:[],duration_ms:1,result_revision:1,execution_mode:'five_agents',matter_schema_version:'v1',matters:[],versions:{}}});
  const response=data=>({ok:true,status:200,json:async()=>structuredClone(data)});
  const fetch=async(path,options={})=>{
    calls.push({path,method:options.method||'GET'});
    if(path.endsWith('/bootstrap'))return response({pairs:[{pair_id:'CASE',company:'合成企业',period:'2025',documents:[]}],rules:{},notice:'',default_mode:'five_agents'});
    if(path.endsWith('/runs')&&options.method==='POST')return response({task_id:'CONNJOB-AAAAAAAA',status:'running',company:'合成企业'});
    if(path.endsWith('/status'))return new Promise(resolve=>pending.status=resolve);
    if(path.includes('CONNJOB-BBBBBBBB/summary'))return new Promise(resolve=>pending.B=resolve);
    if(path.includes('CONNJOB-CCCCCCCC/summary'))return new Promise(resolve=>pending.C=resolve);
    if(path.includes('CONNJOB-AAAAAAAA/summary'))return response(result('CONNJOB-AAAAAAAA'));
    throw new Error('Unexpected request '+path);
  };
  window.AuditTraceStatus={};window.AuditTraceMatters={prepareRequest:async b=>b,render:t=>renders.push(t.task_id),activateLegacy:()=>{}};
  const context=vm.createContext({window,document,localStorage,location,history,navigator:{},URL,CustomEvent:window.CustomEvent,Event:window.Event,
    crypto:webcrypto,fetch,setTimeout,clearTimeout,console,structuredClone});
  for(const name of ['connectivity-run-state.js','connectivity.js'])vm.runInContext(fs.readFileSync(new URL('../../assets/official-v4/'+name,import.meta.url),'utf8'),context);
  await flush();
  document.dispatchEvent(new window.CustomEvent('audittrace:connectivity-start-run',{detail:{selected_matter_ids:['M']}}));await flush();
  assert.equal(typeof pending.status,'function');
  document.dispatchEvent(new window.CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:'CONNJOB-BBBBBBBB'}}));
  document.dispatchEvent(new window.CustomEvent('audittrace:connectivity-open-task',{detail:{task_id:'CONNJOB-CCCCCCCC'}}));await flush();
  pending.C(response(result('CONNJOB-CCCCCCCC')));await flush();
  pending.B(response(result('CONNJOB-BBBBBBBB')));await flush();
  assert.equal(renders.at(-1),'CONNJOB-CCCCCCCC',JSON.stringify(errors));assert(!renders.includes('CONNJOB-BBBBBBBB'));
  pending.status(response({task_id:'CONNJOB-AAAAAAAA',status:'running',version:2,steps:{},agent_steps:{}}));await flush();
  assert(timers.size>0,'active polling must schedule the next tick after history viewing');
  const next=[...timers.values()].at(-1);next();await flush();
  assert.equal(calls.filter(c=>c.path.endsWith('/status')).length,2);
  assert.equal(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/runs')).length,1);
  assert(!calls.some(c=>c.path.endsWith('/cancel')));
  assert(storage.has('audittrace-connectivity-active'));
  // 新页面启动时，活动任务从独立存储恢复；历史C仍是阅读视图。
  const refreshed=parseHTML(fs.readFileSync(new URL('../../index.html',import.meta.url),'utf8'));
  refreshed.document.documentElement.dataset.connectivityWorkspaceReady='true';
  const restoredCalls=[];
  refreshed.window.AuditTraceStatus={};refreshed.window.AuditTraceMatters={render:()=>{},prepareRequest:async b=>b};
  const restoredFetch=async(path,options={})=>{
    restoredCalls.push({path,method:options.method||'GET'});
    if(path.endsWith('/status'))return new Promise(()=>{});
    if(path.includes('CONNJOB-CCCCCCCC/summary'))return response(result('CONNJOB-CCCCCCCC'));
    return fetch(path,options);
  };
  const restoredContext=vm.createContext({window:refreshed.window,document:refreshed.document,localStorage,location,history,navigator:{},URL,
    CustomEvent:refreshed.window.CustomEvent,Event:refreshed.window.Event,crypto:webcrypto,fetch:restoredFetch,setTimeout,clearTimeout,console,structuredClone});
  for(const name of ['connectivity-run-state.js','connectivity.js'])vm.runInContext(fs.readFileSync(new URL('../../assets/official-v4/'+name,import.meta.url),'utf8'),restoredContext);
  await flush();
  assert(restoredCalls.some(c=>c.path.includes('CONNJOB-AAAAAAAA/status')));
  assert(restoredCalls.some(c=>c.path.includes('CONNJOB-CCCCCCCC/summary')));
  assert(!restoredCalls.some(c=>c.method==='POST'));
});
