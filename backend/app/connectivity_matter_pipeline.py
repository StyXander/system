"""事项主管线：建档后并行调查，反证与综合复核；预算和共享写入由程序管理。

事项建档先行，财务调查与跨期调查随后并行读取同一版本。
每次共享写入在程序锁内合并，角色不能覆盖另一角色的账本。
反证与综合复核顺序执行，补查仍归同一个全局调用上限。
用户取消后保留已取得回执，已发出请求等待响应并完成结算。
缺少真实模型配置时留下未执行记录，不生成模拟协作过程。
续分析复用原事项身份和已完成结果，历史调用放在独立来源链。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
import threading
import time
import uuid

from .connectivity_matter_agents import call_matter_role, MatterCallFailure, PROMPT_VERSION
from .connectivity_matter_extraction import read_corpus, relevant_evidence, digest, search_corpus
from .connectivity_matter_schemas import MATTER_VERSION, AgentMatterResult, ROLE_NAMES, MatterEvidence
from .connectivity_matters import seed_matters, attach_events, apply_identification, integrate_result, finish_projection, missing_assessment
from .connectivity_report_sets import resolve_documents
from .connectivity_schemas import ConnectivityRun, SourceLineage, DisclosureOccurrence

_PROVIDER_SLOTS=threading.BoundedSemaphore(2)


def run_matter_pipeline(root, request, *, progress=lambda *a:None, agent_progress=lambda *a:None,
                        cancelled=lambda:False,before_model=lambda:None,resume=None,checkpoint=lambda r:None,caller=None,provider_budget=lambda r:None):
    started=time.perf_counter();report_set,documents=resolve_documents(root,request)
    run=ConnectivityRun(run_id="CONN-"+uuid.uuid4().hex[:16].upper(),company=report_set.company,
        period="—".join([report_set.periods[0],report_set.periods[-1]]) if len(report_set.periods)>1 else report_set.periods[0],
        documents=documents,execution_mode=request.mode,report_set=report_set,matter_schema_version=MATTER_VERSION,
        versions={"pair_id":request.pair_id,"report_set_id":report_set.report_set_id,"matter_prompt":PROMPT_VERSION,
                  "analysis_scope":"matter_connectivity","result_origin":"original","matter_types":list(request.matter_types)})
    progress_callback=progress
    stage_started={}
    run.versions['stage_timings']={}
    def progress(stage,status,detail):
        if status=='running':stage_started[stage]=time.perf_counter()
        row=run.versions['stage_timings'].setdefault(stage,{})
        row.update(status=status,updated_at=time.time())
        if stage in stage_started:row['duration_ms']=round((time.perf_counter()-stage_started[stage])*1000)
        progress_callback(stage,status,detail)
    if caller is not None:
        run.dataset_role="synthetic"
        run.versions["provider_origin"]="injected_test_caller"
    from .connectivity_financial_ontology import matter_rules
    run.versions["matter_rule_fingerprints"]={r["rule_id"]:digest(json.dumps(r,sort_keys=True,ensure_ascii=False)) for r in matter_rules()}
    run.source_lineage=[SourceLineage(document_id=d.document_id,producer=d.company,category=d.source_kind) for d in documents]
    if resume:
        if resume.report_set!=report_set or resume.execution_mode!=request.mode:
            raise ValueError("续分析的资料集合或模式已变化")
        for name in ("matter_evidence","matters","matter_events","matter_commitments","matter_paths","matter_relations",
                     "matter_explanations","matter_assessments","assurance_planning_reviews","matter_tasks","matter_tool_receipts","matter_rejections","matter_revisions","occurrences"):
            setattr(run,name,deepcopy(getattr(resume,name)))
        for task in run.matter_tasks:
            if task.get('status')=='running':
                task.update(status='interrupted',stop_reason='父运行已中断；本次不复用未完成角色')
        run.parent_run_id=resume.run_id;run.result_revision=resume.result_revision+1
        run.prior_provider_calls=[*resume.prior_provider_calls,*resume.provider_calls]
        run.versions["result_origin"]="incremental_retry"
    checkpoint(run)
    progress("evidence_load","running","读取多年登记原件与叙述证据")
    corpus,run.matter_coverage=read_corpus(root,documents,cancelled=cancelled)
    progress("evidence_load","completed",f"已索引{len(corpus)}个原文块，扫描页与失败覆盖单列")
    progress("rule_calculation","running","建立事项证据身份与候选，不要求存在金额")
    seeds,seed_coverage=relevant_evidence(corpus)
    if not resume:
        run.matter_evidence=seeds;run.matters=seed_matters(seeds,request.matter_types)
        for matter in run.matters:attach_events(run,matter)
    run.versions["seed_coverage"]=seed_coverage
    progress("rule_calculation","completed",f"建立{len(run.matters)}项披露候选；身份归并待调查")
    progress("knowledge_retrieval","running","准备事项检索、专业规则与补证工具")
    progress("knowledge_retrieval","completed","支持与反证分别查询，检索命中不等于关系证实")
    lock=threading.RLock();attempts=0;quota_ready=False;tool_cache={}
    call=caller or call_matter_role
    budget=request.budget
    # 消融是显式实验条件，跳过角色不能被包装为五角色全部完成。
    run.versions["ablation"]=request.ablation
    run.versions["semantic_judgment"]="模型意见与程序来源核验分列，不代表专业鉴证"
    def save():
        finish_projection(run);checkpoint(run)
    def model_call(role,payload,task_id):
        """获取进程并发槽并原子扣减本运行调用次数。
        发送前写检查点，供应商未知用量保留为空而非填零。
        在途上界与已知用量进入共享额度账本，模型不能修改预算。
        中断或失败依旧保存已取得回执，后续角色按剩余额度执行。
        """
        nonlocal attempts,quota_ready
        queued_at=time.perf_counter()
        with _PROVIDER_SLOTS:
            queue_ms=round((time.perf_counter()-queued_at)*1000)
            with lock:
                if cancelled():raise InterruptedError("用户取消事项调查")
                if attempts>=budget.max_provider_calls:raise ValueError("MODEL_CALL_BUDGET_EXHAUSTED")
                # 调查不能耗尽最后的反证和综合复核名额。
                # 留出的名额仍计入同一上限，额度不足时明确留下部分完成。
                protected=2 if role in {"A1","A2","A3"} else 1 if role=="A4" else 0
                if attempts>=max(0,budget.max_provider_calls-protected):raise ValueError("REVIEW_BUDGET_RESERVED")
                if not quota_ready:before_model();quota_ready=True
                attempts+=1
                receipt={"provider_call_id":"MCALL-"+uuid.uuid4().hex,"role":role,"task_id":task_id,
                    "status":"started","performed":False,"request_attempted":None,"queue_ms":queue_ms,
                    "started_at":time.time(),"input_characters":len(json.dumps(payload,ensure_ascii=False)),"input_tokens":None,"output_tokens":None}
                run.provider_calls.append(receipt);save()
            try:
                def preflight(record):
                    with lock:
                        # 先写待发送上界，再请求持久额度占用；占额失败不发送请求。
                        receipt.update(input_token_upper_bound=record["input_token_upper_bound"],output_token_upper_bound=record["output_token_upper_bound"],request_attempted=True)
                        try:provider_budget(run)
                        except Exception:
                            receipt["request_attempted"]=False
                            raise
                        save()
                result,record=call(role,payload) if caller else call(role,payload,preflight=preflight)
                result=AgentMatterResult.model_validate(result)
            except MatterCallFailure as error:
                with lock:receipt.update(error.record);save()
                raise
            except Exception:
                with lock:receipt.update(status="failed",failure_code="ROLE_EXECUTION_FAILED");save()
                raise
            with lock:
                receipt.update(record);save()
                provider_budget(run)
            return result
    def bounded_call(role,payload,task_id):
        # 每次重试重新进入model_call，独立记录并计入单次调用预算。
        for attempt in range(2):
            try:
                return model_call(role,payload,task_id)
            except MatterCallFailure as error:
                record=error.record
                if not attempt and record.get('failure_code')=='MODEL_SCHEMA_INVALID' and not cancelled():
                    # 重生成仍走同一调用预算；不修补供应商原值或放宽证据校验。
                    payload=deepcopy(payload)
                    payload['output_validation_feedback']={
                        'code':'MODEL_SCHEMA_INVALID',
                        'invalid_fields':record.get('invalid_fields',[]),
                        'instruction':'上次工具参数未通过JSON或Schema校验。请重新提交一个合法JSON对象，严格使用工具Schema的字段、枚举和长度；不得编造证据。'}
                    continue
                delay=record.get("retry_after_seconds",1)
                if attempt or not record.get("retryable") or delay>8 or cancelled():
                    raise
                deadline=time.monotonic()+max(1,delay)
                while time.monotonic()<deadline:
                    if cancelled():raise InterruptedError("用户取消事项调查")
                    time.sleep(min(.2,max(0,deadline-time.monotonic())))

    def payload_for(role,matter=None,extension=""):
        # 每波读同一快照；worker只提交建议，不直接覆盖另一角色的结果。
        with lock:
            if matter:
                discovered=search_corpus(corpus,matter.name+" "+" ".join(matter.aliases),limit=18)["evidence"]
                from .connectivity_matters import _all_refs
                referenced=set(matter.evidence_ids)
                for field in ('matter_paths','matter_events','matter_commitments','matter_explanations','matter_assessments'):
                    for value in getattr(run,field):
                        if value.matter_id==matter.matter_id:referenced.update(_all_refs(value.model_dump()))
                for task in run.matter_tasks:
                    if task.get('matter_id')==matter.matter_id and task.get('result'):referenced.update(_all_refs(task['result']))
                focused={b.evidence_id:b for b in run.matter_evidence if b.evidence_id in referenced}
                for value in discovered:
                    b=MatterEvidence.model_validate(value);focused.setdefault(b.evidence_id,b)
                    if not any(old.evidence_id==b.evidence_id for old in run.matter_evidence):run.matter_evidence.append(b)
                context_evidence=list(focused.values())
            else:
                if request.selected_matter_ids:
                    targets=[m for m in run.matters if m.matter_id in request.selected_matter_ids or set(m.lineage)&set(request.selected_matter_ids)]
                    selected_refs={eid for m in targets for eid in m.evidence_ids}
                    focused={b.evidence_id:b for b in run.matter_evidence if b.evidence_id in selected_refs}
                    for original in list(focused.values()):
                        for value in search_corpus(corpus,original.quote[:300],limit=12)['evidence']:
                            block=MatterEvidence.model_validate(value);focused.setdefault(block.evidence_id,block)
                            if not any(b.evidence_id==block.evidence_id for b in run.matter_evidence):run.matter_evidence.append(block)
                    context_evidence=list(focused.values())
                else:
                    context_evidence=run.matter_evidence[:90]
            return {"matter_id":matter.matter_id if matter else "","input_revision":run.result_revision,
                "as_of_date":str(report_set.as_of_date),
                "citation_instruction":"跨页内容按独立证据ID引用；原文块带adjacent_evidence_ids，可打开相邻原页补查。paths.rule_ids仅选工具返回的登记模板编号。","documents":[{key:getattr(d,key) for key in ("document_id","company_id","company","report_type","report_period","disclosure_date","file_sha256","pages")} for d in documents],
                "matter":matter.model_dump() if matter else None,
                "selection_instruction":"只围绕所选事项建档与补查，其他披露保留待调查；不要扩展为全部事项调查。" if request.selected_matter_ids else "",
                "evidence":[b.model_dump() for b in context_evidence],
                "upstream_results":list({t["role"]:{"role":t["role"],"status":t["status"],"result":t["result"]} for t in run.matter_tasks if t.get("matter_id")==getattr(matter,"matter_id",None) and t.get("result")}.values()),
                "paths":[p.model_dump() for p in run.matter_paths if matter and p.matter_id==matter.matter_id],
                "occurrences":[o.model_dump() for o in run.occurrences if o.document_id in {b.document_id for b in context_evidence} and o.pdf_page in {b.pdf_page for b in context_evidence if b.document_id==o.document_id}],
                "commitments":[c.model_dump() for c in run.matter_commitments if matter and c.matter_id==matter.matter_id],
                "events":[e.model_dump() for e in run.matter_events if matter and e.matter_id==matter.matter_id],
                "coverage_gaps":report_set.coverage_gaps,"role_extension":extension}
    def role_task(role,matter=None,extension=""):
        """运行有界的角色工具循环。
        工具申请由白名单执行，工具结果作为下一轮输入返回。
        角色不直接覆盖共享档案，最终建议经统一校验后整体合并。
        失败和轮次耗尽保留停止原因，不自动生成已完成状态。
        """
        role_started=time.perf_counter()
        payload=payload_for(role,matter,extension);task_id="MTASK-"+uuid.uuid4().hex[:16]
        task={"task_id":task_id,"role":role,"role_name":ROLE_NAMES[role],"matter_id":getattr(matter,"matter_id",""),
            "input_revision":run.result_revision,"status":"running","rounds":0,"stop_reason":""}
        with lock:run.matter_tasks.append(task);agent_progress(role,"running",ROLE_NAMES[role]);save()
        result=None
        try:
            for round_no in range(budget.max_role_rounds):
                payload['investigation_round']={'current':round_no+1,'maximum':budget.max_role_rounds,
                    'remaining_tool_rounds':budget.max_role_rounds-round_no-1}
                result=bounded_call(role,payload,task_id);task["rounds"]=round_no+1
                if not result.tool_requests:
                    task.update(status="completed",stop_reason=result.stop_reason or "本轮建议已提交");break
                returned=[]
                for request_tool in result.tool_requests:
                    from .connectivity_tool_registry import execute_tool,ToolRequest
                    marker=digest(json.dumps({"set":report_set.report_set_id,"tool":request_tool.tool_name,"arguments":request_tool.arguments},sort_keys=True,ensure_ascii=False))
                    with lock:
                        if marker in tool_cache:
                            returned.append(dict(tool_cache[marker],cache_hit=True));continue
                    try:receipt=execute_tool(root,run,ToolRequest(request_tool.tool_name,request_tool.arguments),corpus=corpus)
                    except InterruptedError:raise
                    except Exception as error:
                        receipt={"tool_name":request_tool.tool_name,"args_hash":marker,"status":"failed","result":None,
                                 "reason":"工具未完成："+type(error).__name__,"failure_code":type(error).__name__}
                    receipt.update(task_id=task_id,matter_id=getattr(matter,"matter_id",""),role=role,round=round_no+1)
                    with lock:
                        tool_cache[marker]=deepcopy(receipt)
                        run.matter_tool_receipts.append(receipt)
                        for b in (receipt.get("result") or {}).get("evidence",[]):
                            item=MatterEvidence.model_validate(b)
                            if not any(old.evidence_id==item.evidence_id for old in run.matter_evidence):run.matter_evidence.append(item)
                        for raw in (receipt.get("result") or {}).get("occurrences",[]):
                            item=DisclosureOccurrence.model_validate(raw)
                            if not any(old.occurrence_id==item.occurrence_id for old in run.occurrences):run.occurrences.append(item)
                        save()
                    returned.append(receipt)
                payload["tool_results"]=returned
                payload["previous_proposal"]=result.model_dump()
                # 工具续轮只扩充当前角色已经看到的证据，不再次发送所有事项全文。
                known={b["evidence_id"]:b for b in payload["evidence"]}
                for receipt in returned:
                    for block in (receipt.get("result") or {}).get("evidence",[]):known[block["evidence_id"]]=block
                payload["evidence"]=list(known.values())
                occurrences={o["occurrence_id"]:o for o in payload["occurrences"]}
                for receipt in returned:
                    for row in (receipt.get("result") or {}).get("occurrences",[]):occurrences[row["occurrence_id"]]=row
                payload["occurrences"]=list(occurrences.values())
                task.update(status="partial",stop_reason="达到单角色调查轮次上限，尚需综合工具反馈")
            if result and result.tool_requests and not cancelled():
                # 最后一轮取证也需要交回模型综合，不能取完证据就结束角色。
                # 只追加一次无工具收尾，仍走同一20次预算及复核名额保护。
                payload['finalize_only']=True
                payload['investigation_round']={'current':budget.max_role_rounds+1,
                    'maximum':budget.max_role_rounds+1,'remaining_tool_rounds':0}
                result=bounded_call(role,payload,task_id)
                task['rounds']=budget.max_role_rounds+1
                if result.tool_requests:
                    task.update(status='partial',stop_reason='最终综合仍申请工具，未执行额外查询；缺口保留')
                else:
                    task.update(status='completed',stop_reason=result.stop_reason or '已综合最后一轮工具回执')
            if result:
                for validation_attempt in range(2):
                    try:
                        with lock:
                            if role=="A1":
                                if result.input_revision!=run.result_revision or result.matter_id:raise ValueError("建档结果输入版本或全局身份错误")
                                apply_identification(run,result.matters)
                            elif matter:
                                if request.mode=="three_agents" and role=="A2":
                                    for component in ("A2","A3","A4"):result=integrate_result(run,matter,component,result,payload["input_revision"])
                                elif request.mode=="single_model":
                                    for component in ("A2","A3","A4","A5"):result=integrate_result(run,matter,component,result,payload["input_revision"])
                                else:result=integrate_result(run,matter,role,result,payload["input_revision"])
                            task["result"]=result.model_dump(mode="json")
                        break
                    except ValueError as error:
                        if validation_attempt or role=='A1' or request.mode!='five_agents' or cancelled():raise
                        with lock:
                            run.matter_rejections.append({'role':role,'matter_id':matter.matter_id,
                                'reason':str(error)[:200],'recovery':'one_corrective_generation'})
                            task.update(status='running',stop_reason='证据校验未通过，正在按拒绝原因纠正')
                            save()
                        payload['finalize_only']=True
                        payload['evidence_validation_feedback']={'reason':str(error)[:200],
                            'instruction':'上次建议未通过证据校验且未写入档案。仅用已有证据重新生成，年份不在引文中则留空，未知引用不得替换为猜测；不能解决的问题保留未决。'}
                        result=bounded_call(role,payload,task_id)
                        task.update(status='partial' if result.tool_requests else 'completed',
                            stop_reason='最终修正仍申请工具，缺口保留' if result.tool_requests else result.stop_reason or '已按证据校验反馈重新生成')
        except InterruptedError:
            task.update(status="cancelled",stop_reason="用户取消，已取得回执保留")
        except (ValueError,MatterCallFailure) as error:
            task.update(status="failed",stop_reason=str(error)[:200],failure_code=str(error)[:200])
            if isinstance(error,MatterCallFailure):
                task.update(retryable=error.record.get("retryable",False),retry_after_seconds=error.record.get("retry_after_seconds"),error_category=error.record.get("error_category"))
            with lock:run.matter_rejections.append({"role":role,"matter_id":getattr(matter,"matter_id",""),"reason":task["stop_reason"]})
        except Exception as error:
            task.update(status="failed",stop_reason=type(error).__name__)
        finally:
            task["duration_ms"]=round((time.perf_counter()-role_started)*1000)
            task["updated_at"]=time.time()
            with lock:
                agent_progress(role,task["status"],task["stop_reason"]);save()
        return task
    if request.mode=="calculation_only":
        progress("agent_collaboration","skipped","本次事项候选离线检查，未调用任何Agent")
        run.model_status="not_requested"
    elif not seeds:
        progress("agent_collaboration","skipped","未形成可调查事项；请检查资料与解析覆盖")
        run.model_status="five_agents_partial"
    elif caller is None and (not os.getenv("DEEPSEEK_API_KEY") or os.getenv("AUDITTRACE_DEMO_USE_EXTERNAL_MODEL","true").lower() not in {"true","1","yes","on"}):
        progress("agent_collaboration","skipped","真实模型未配置或被关闭，保留程序事项候选")
        run.model_status="five_agents_partial"
        for role in ROLE_NAMES:
            run.matter_tasks.append({"role":role,"status":"skipped","stop_reason":"MODEL_CONFIG_MISSING_OR_DISABLED"})
            agent_progress(role,"skipped","真实模型未配置或被关闭")
    else:
        progress("agent_collaboration","running","事项建档后并行调查财务与跨期信息")
        def reuse_task(task):
            agent_progress(task['role'],'reused','复用父版本已完成的角色，本次没有重复调用')
            return task
        if not resume or not any(t.get("role")=="A1" and t.get("status")=="completed" for t in run.matter_tasks):role_task("A1")
        else:reuse_task(next(t for t in reversed(run.matter_tasks) if t.get('role')=='A1' and t.get('status')=='completed'))
        selected=[m for m in run.matters if not request.selected_matter_ids or m.matter_id in request.selected_matter_ids or set(m.lineage)&set(request.selected_matter_ids)]
        resolved_ids={m.matter_id for m in selected}|{key for m in selected for key in m.lineage}
        if request.selected_matter_ids and not set(request.selected_matter_ids)<=resolved_ids:
            raise ValueError("选择了当前档案中不存在的事项")
        # 优先深查有明确项目身份或风险的事项，未深查项仍保留队列。
        selected.sort(key=lambda m:(m.identity_status=="candidate",m.matter_type!="climate_risk",m.matter_id))
        for matter in selected[:budget.max_matters]:
            if cancelled():break
            if resume and matter.investigation_status=="completed":
                for role in ('A2','A3','A4','A5'):
                    previous=next((t for t in reversed(run.matter_tasks) if t.get('matter_id')==matter.matter_id and t.get('role')==role and t.get('status')=='completed'),None)
                    if previous:reuse_task(previous)
                continue
            matter.investigation_status="running"
            if request.mode=="five_agents":
                parallel=("A2",) if request.ablation=="no_temporal" else ("A2","A3")
                if request.ablation=="no_temporal":
                    run.matter_tasks.append({"role":"A3","matter_id":matter.matter_id,"status":"skipped","stop_reason":"实验消融移除跨期角色"})
                previous={t.get("role"):t for t in run.matter_tasks if t.get("matter_id")==matter.matter_id} if resume else {}
                reusable={r:t for r,t in previous.items() if t.get("status")=="completed" and t.get("result")}
                changed=any(role not in reusable for role in parallel)
                for role in parallel:
                    if role in reusable:reuse_task(reusable[role])
                with ThreadPoolExecutor(max_workers=budget.max_parallel_calls) as pool:
                    jobs={role:pool.submit(role_task,role,matter) for role in parallel if role not in reusable}
                    tasks=[jobs[role].result() if role in jobs else reusable[role] for role in parallel]
                if request.ablation=="no_counterevidence":
                    run.matter_tasks.append({"role":"A4","matter_id":matter.matter_id,"status":"skipped","stop_reason":"实验消融移除反证角色"})
                else:
                    tasks.append(reuse_task(reusable["A4"]) if not changed and "A4" in reusable else role_task("A4",matter))
                changed=changed or "A4" not in reusable
                tasks.append(reuse_task(reusable["A5"]) if not changed and "A5" in reusable else role_task("A5",matter,"实验消融条件："+request.ablation if request.ablation!="none" else ""))
            elif request.mode=="three_agents":
                tasks=[role_task("A2",matter,"本对照角色同时调查财务路径、跨期事件与竞争解释。"),role_task("A5",matter)]
            else:
                tasks=[role_task("A5",matter,"单模型对照具有同样工具，请一次综合完成财务路径、时序、反证及assessment。")]
            assessment=next((a for a in run.matter_assessments if a.matter_id==matter.matter_id),None)
            # 一次有具体目标的反馈调查，预算仍归同一计数器。
            if assessment and assessment.next_actions and attempts<budget.max_provider_calls and request.mode=="five_agents" and request.ablation=="none":
                action=next((a for a in assessment.next_actions if a.target_role in {"A2","A3"}),None)
                # 需要内部底稿的动作只进入资料清单；公开原件没有新线索时不重复付费补查。
                available=search_corpus(corpus,action.question+" "+action.requested_material,limit=6)["evidence"] if action else []
                known_ids={b.evidence_id for b in run.matter_evidence}
                if action and any(b["evidence_id"] not in known_ids for b in available):
                    before_ids={b.evidence_id for b in run.matter_evidence}
                    before_digests={r.get("output_digest") for r in run.matter_tool_receipts if r.get("status")=="hit"}
                    tasks.append(role_task(action.target_role,matter,"定向补查任务："+action.model_dump_json()))
                    fresh={b.evidence_id for b in run.matter_evidence}-before_ids
                    fresh_receipts=[r for r in run.matter_tool_receipts if r.get("status")=="hit" and r.get("output_digest") not in before_digests]
                    if fresh or fresh_receipts:
                        tasks.append(role_task("A4",matter,"检查补查所得新证据是否改变原解释。"))
                        tasks.append(role_task("A5",matter,"按补查与反证更新结论；无新证据保留原缺口。"))
                    else:
                        tasks[-1]["stop_reason"]+="；未取得新增证据，保留原判断和缺口，停止重复复核"
            matter.investigation_status="completed" if all(t["status"]=="completed" for t in tasks) and assessment and request.ablation=="none" else "partial"
            if not any(a.matter_id==matter.matter_id for a in run.matter_assessments):
                run.matter_assessments.append(missing_assessment(matter,"综合复核未完成，见角色失败及预算记录"))
            save()
        run.versions["investigation_scope"]={"selected_matter_ids":[m.matter_id for m in selected[:budget.max_matters]],
            "pending_outside_scope":[m.matter_id for m in run.matters if m not in selected[:budget.max_matters]]}
        incomplete=any(m.investigation_status!="completed" for m in selected[:budget.max_matters]) or not any(t.get("role")=="A1" and t.get("status")=="completed" for t in run.matter_tasks)
        prefix={"five_agents":"five_agents","three_agents":"matter_three","single_model":"matter_single"}[request.mode]
        run.model_status=prefix+("_partial" if incomplete or not run.matters else "_completed")
        progress("agent_collaboration","degraded" if incomplete else "completed",run.model_status)
    progress("evidence_validation","running","校验引用、逐段支持与来源依赖")
    finish_projection(run)
    progress("evidence_validation","completed","原文身份与语义判断分列，金额可比性不由模型放行")
    progress("structured_output","running","保存事项、两线时间轴、分歧和下一步")
    if cancelled():run.versions["cancellation_requested"]=True
    run.duration_ms=round((time.perf_counter()-started)*1000)
    run.versions["budget"]={"attempts":attempts,"limit":budget.max_provider_calls,"deep_matter_limit":budget.max_matters,
                             "remaining":max(0,budget.max_provider_calls-attempts)}
    run.overview={"relation_total":0,"matter_summary":run.matter_overview}
    progress("structured_output","completed","事项结果已保存，真实调用与未调查范围单列");save()
    return run
