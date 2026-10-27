import {createRequire} from 'node:module';
import test from 'node:test';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),RS=require('../../assets/official-v4/connectivity-run-state.js');
test('history viewing leaves active generation, timer and progress untouched',()=>{
  const s=RS.create();s.activeRun={task:{task_id:'A',status:'running',stage:'A3'},generation:4,timer:123,failures:0};
  const active=s.activeRun,g=RS.beginView(s,'B');RS.acceptView(s,'B',g,{task_id:'B',status:'completed'});
  assert.equal(s.activeRun,active);assert.equal(active.timer,123);assert.equal(active.generation,4);assert.equal(active.task.stage,'A3');
});
test('late history responses cannot overwrite the latest selected task',()=>{
  const s=RS.create(),b=RS.beginView(s,'B'),c=RS.beginView(s,'C');
  assert.equal(RS.acceptView(s,'C',c,{task_id:'C'}),true);
  assert.equal(RS.acceptView(s,'B',b,{task_id:'B'}),false);
  assert.equal(s.viewRun.task.task_id,'C');
});
