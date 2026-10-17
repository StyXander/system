/* 合成保存结果的DOM检查，不代替真实浏览器布局或模型实跑。 */
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
(async () => {
  const {Window} = await import(process.env.HAPPY_DOM_MODULE || 'happy-dom');
  const root = path.resolve(__dirname, '..');
  const original = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  assert.equal(original.dataset_role, 'synthetic');
  const taskId = 'CONNJOB-SYNTHETIC123';
  let result = original;
  let reviewBody;
  const window = new Window({url:`http://localhost/?connectivity_task=${taskId}`,
    settings:{disableJavaScriptFileLoading:true,disableCSSFileLoading:true}});
  const html = fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
  window.document.write(html);
  window.fetch = async (url, options={}) => {
    let data;
    if(String(url).endsWith('/bootstrap')) {
      data = {pairs:[{pair_id:'SYN-PAIR',company:'合成企业',period:'2025',documents:[]}],
        rules:{'EQ-001':{name:'同口径数值'}},notice:'合成测试，无真实模型调用'};
    } else {
      if(options.method==='POST') {
        reviewBody = JSON.parse(options.body);
        result = structuredClone(result);
        result.result_revision += 1;
        result.ai_analyses[0].review_status = 'accepted';
      }
      data = {task_id:taskId,status:'completed',result,can_modify:true,steps:{},agent_steps:{}};
    }
    return {ok:true,status:200,json:async()=>data};
  };
  window.eval(fs.readFileSync(path.join(root,'assets/official-v4/connectivity.js'),'utf8'));
  await window.happyDOM.whenAsyncComplete();
  const doc=window.document;
  assert.match(doc.querySelector('#cn-fourq').textContent,/AI分析意见/);
  assert.match(doc.querySelector('#cn-detail-conclusion').textContent,/原文支持一个可能的范围调节路径/);
  assert.match(doc.querySelector('#cn-pane-conditions').textContent,/条件调节试算/);
  assert.equal(doc.querySelectorAll('#cn-exports a').length,4);
  assert.ok(doc.querySelectorAll('.cn-ai-opinion [data-reader]').length);
  doc.querySelector('#cn-review-action').value='ai_accept';
  doc.querySelector('#cn-review-action').dispatchEvent(new window.Event('change'));
  assert.ok(doc.querySelector('#cn-review-selection').hidden);
  doc.querySelector('#cn-review-reason').value='合成测试采纳为核查线索';
  doc.querySelector('#cn-review-form').dispatchEvent(new window.Event('submit',{cancelable:true}));
  await window.happyDOM.whenAsyncComplete();
  assert.equal(reviewBody.action,'ai_accept');
  assert.deepEqual(reviewBody.check_ids,[original.checks[0].check_id]);
  assert.match(doc.querySelector('#cn-detail-conclusion').textContent,/已采纳/);
  assert.equal(result.checks[0].calculation_status, original.checks[0].calculation_status);
  console.log(JSON.stringify({kind:'synthetic_dom',opinion:true,scenario:true,review:true,exports:true,layout_verified:false}));
  await window.happyDOM.close();
})().catch(error=>{console.error(error);process.exitCode=1;});
