/* 在隔离的嵌入式 PostgreSQL 中执行真实迁移与查询，不连接生产数据库。
   npm install --prefix /tmp/audittrace-testdeps @electric-sql/pglite
   AUDITTRACE_TEST_NODE_MODULES=/tmp/audittrace-testdeps/node_modules node scripts/verify_task_center_sql.mjs */
import {createRequire} from 'node:module';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const moduleRoot=process.env.AUDITTRACE_TEST_NODE_MODULES;
const {PGlite}=require(moduleRoot?`${moduleRoot}/@electric-sql/pglite`:'@electric-sql/pglite');
const db=new PGlite();
try{
  await db.exec(`create role anon;create role authenticated;create role service_role;
    create table demo_run_tasks(task_id text primary key,case_id text,status text,created_at timestamptz,updated_at timestamptz,
    version int,result_expires_at timestamptz,run_id text,failure_code text,error text,steps jsonb,agent_steps jsonb,request_payload jsonb,result jsonb);`);
  await db.exec(fs.readFileSync(new URL('../supabase/connectivity_read_projection_migration.sql',import.meta.url),'utf8'));
  const run={run_id:'R',company:'C',period:'2025',matter_schema_version:'v1',matters:[
    {matter_id:'M1',investigation_status:'completed',evidence_ids:['E1']},
    {matter_id:'M2',investigation_status:'pending',evidence_ids:['E2']}],
    matter_paths:[{matter_id:'M1',steps:[{evidence_ids:['E3']}]}],matter_evidence:[
      {evidence_id:'E1',quote:'one'},{evidence_id:'E2',quote:'other matter full text'},{evidence_id:'E3',quote:'annual report'}],
    assurance_planning:{risk_findings:[{matter_ids:['M1'],evidence:[{evidence_id:'E1',quote:'not in summary'}]},{matter_ids:['M2']}],evidence_requests:[]}};
  await db.query('insert into demo_run_tasks(task_id,status,version,request_payload,result) values($1,$2,$3,$4,$5)',
    ['T','completed',3,JSON.stringify({kind:'connectivity',owner:'O'}),JSON.stringify(run)]);
  const read=async(kind,id='M1')=>(await db.query('select connectivity_read_projection($1,$2,$3) as value',['T',kind,id])).rows[0].value;
  const summary=await read('summary'),detail=await read('detail'),list=await read('matters');
  assert.equal(summary.version,3);assert.equal(summary.run_body.owner,'O');
  assert.equal(summary.result.assurance_planning.risk_findings.length,1);
  assert.equal(summary.result.assurance_planning.risk_findings[0].evidence[0].quote,undefined);
  assert.equal(list.result.matter_evidence,undefined);
  assert.deepEqual(detail.result.matters.map(m=>m.matter_id),['M1']);
  assert.deepEqual(detail.result.matter_evidence.map(e=>e.evidence_id),['E1','E3']);
  assert.equal((await read('detail','MISSING')).result,null);
  await db.query("update demo_run_tasks set result_expires_at=now()-interval '1 day' where task_id='T'");
  assert.equal((await read('detail')).status,'expired');assert.equal((await read('detail')).result,null);
  const permissions=await db.query("select has_function_privilege('anon','public.connectivity_read_projection(text,text,text)','execute') as anon, has_function_privilege('service_role','public.connectivity_read_projection(text,text,text)','execute') as service");
  assert.equal(permissions.rows[0].anon,false);assert.equal(permissions.rows[0].service,true);
  console.log(JSON.stringify({engine:'embedded_postgresql',migration:'executed',checks:['summary_filter','no_quote_in_summary','single_matter','referenced_evidence','missing_matter','expiry','service_role_only']},null,2));
}finally{await db.close();}
