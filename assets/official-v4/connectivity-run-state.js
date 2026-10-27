/* 正在执行的任务与阅读视图拥有独立的生命周期。 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;else root.AuditTraceRunState=api;
})(typeof window==='undefined'?globalThis:window,function(){
  function create(){
    return {activeRun:{task:null,timer:null,generation:0,failures:0},viewRun:{task:null,id:null,generation:0,loading:false}};
  }
  function beginView(state,id){state.viewRun.id=id;state.viewRun.task=null;state.viewRun.loading=true;return ++state.viewRun.generation;}
  function isCurrent(state,id,generation){return state.viewRun.id===id&&state.viewRun.generation===generation;}
  function acceptView(state,id,generation,task){if(!isCurrent(state,id,generation))return false;state.viewRun.task=task;state.viewRun.loading=false;return true;}
  function running(task){return ['queued','running'].includes(task?.status);}
  return{create,beginView,isCurrent,acceptView,running};
});
