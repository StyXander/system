import {createRequire} from 'node:module';
import test from 'node:test';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{latestRoleTasks}=require('../../assets/official-v4/connectivity-matters.js');
test('role cards show only the last record for the selected matter in the current run',()=>{
  const run={run_id:'CURRENT',matter_tasks:[
    {run_id:'PARENT',role:'A2',matter_id:'M',status:'failed'},
    {run_id:'CURRENT',role:'A2',matter_id:'OTHER',status:'failed'},
    {run_id:'CURRENT',role:'A2',matter_id:'M',status:'failed'},
    {run_id:'CURRENT',role:'A2',matter_id:'M',status:'completed'},
    {run_id:'CURRENT',role:'A1',matter_id:'',status:'completed'}]};
  const roles=latestRoleTasks(run,'M');
  assert.equal(roles.A2.status,'completed');assert.equal(roles.A1.status,'completed');assert.equal(roles.A5,null);
});
test('legacy records need a current provider task ID; parent status cannot masquerade as current',()=>{
  const run={run_id:'R',current_task_ids:['new'],matter_tasks:[
    {task_id:'old',role:'A1',status:'failed'},
    {task_id:'new',role:'A1',status:'completed'}]};
  assert.equal(latestRoleTasks(run,'M').A1.status,'completed');
  run.current_task_ids=[];assert.equal(latestRoleTasks(run,'M').A1,null);
});
