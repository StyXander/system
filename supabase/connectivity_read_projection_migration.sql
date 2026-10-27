-- 在发布分层读取接口前执行。仅 service_role 可调用；会话授权仍由 API 校验。
-- 不修改任务、租约或历史结果。函数在数据库内过滤单事项，避免传回完整 result。
begin;
create or replace function public.connectivity_read_projection(
  p_task_id text, p_kind text, p_matter_id text default null
) returns jsonb language plpgsql stable security invoker set search_path = public as $$
declare
  t record;
  r jsonb;
  b jsonb := '{}'::jsonb;
  meta jsonb;
  k text;
  rows jsonb;
  planning jsonb;
  entry jsonb;
  entries jsonb;
  evidence_field text;
begin
  if p_kind not in ('summary','matters','detail') then
    raise exception 'invalid projection';
  end if;
  select task_id,case_id,status,created_at,updated_at,version,result_expires_at,run_id,failure_code,error,steps,agent_steps,request_payload,result into t from public.demo_run_tasks where task_id = p_task_id;
  if not found then return null; end if;
  meta := jsonb_build_object('task_id',t.task_id,'case_id',t.case_id,'status',t.status,
    'created_at',t.created_at,'updated_at',t.updated_at,'version',t.version,
    'result_expires_at',t.result_expires_at,'run_id',t.run_id,'failure_code',t.failure_code,
    'error',t.error,'steps',t.steps,'agent_steps',t.agent_steps,
    'run_body',jsonb_build_object('kind',t.request_payload->'kind','owner',t.request_payload->'owner',
      'analysis_scope',t.request_payload->'analysis_scope','parent_task_id',t.request_payload->'parent_task_id'));
  if t.status = 'expired' or (t.status in ('completed','degraded') and t.result_expires_at <= now()) then
    return meta || jsonb_build_object('status','expired','result',null);
  end if;
  r := t.result;
  if r is null then return meta || jsonb_build_object('result',null); end if;
  foreach k in array array['run_id','company','period','documents','report_set','matter_schema_version',
    'execution_mode','model_status','result_revision','parent_run_id','matter_overview','duration_ms'] loop
    if r ? k then b := b || jsonb_build_object(k,r->k); end if;
  end loop;
  if coalesce(r->>'matter_schema_version','') = '' then
    return meta || jsonb_build_object('result', b || '{"projection_supported":false}'::jsonb);
  end if;
  b := b || jsonb_build_object('versions',coalesce((select jsonb_object_agg(key,value)
    from jsonb_each(coalesce(r->'versions','{}')) where key in ('matter_rule_fingerprints',
      'source_validity','rule_validity','budget','seed_coverage','investigation_scope','matter_types','result_origin')),'{}'));
  if p_kind in ('summary','matters') then
    select coalesce(jsonb_agg((select jsonb_object_agg(key,value) from jsonb_each(m)
      where key in ('matter_id','company_id','name','matter_type','identity_status','investigation_status','identity_basis','evidence_ids','lineage'))),'[]')
      into rows from jsonb_array_elements(coalesce(r->'matters','[]')) m;
    b := b || jsonb_build_object('matters',rows);
    if p_kind = 'summary' then
      b := b || jsonb_build_object('matter_assessments',coalesce((select jsonb_agg(a)
        from jsonb_array_elements(coalesce(r->'matter_assessments','[]')) a
        where exists(select 1 from jsonb_array_elements(coalesce(r->'matters','[]')) m
          where m->>'matter_id'=a->>'matter_id' and m->>'investigation_status'<>'pending')),'[]'),
        'assurance_planning',coalesce(r->'assurance_planning','{}'));
      planning := coalesce(r->'assurance_planning','{}');
      foreach k in array array['risk_findings','evidence_requests'] loop
        entries := '[]';
        for entry in select x from jsonb_array_elements(coalesce(planning->k,'[]')) x
          where exists(select 1 from jsonb_array_elements(coalesce(r->'matters','[]')) m
            where m->>'investigation_status'<>'pending' and coalesce(x->'matter_ids','[]') ? (m->>'matter_id')) loop
          foreach evidence_field in array array['evidence','counter_evidence'] loop
            if entry ? evidence_field then
              select coalesce(jsonb_agg((select jsonb_object_agg(key,value) from jsonb_each(e)
                where key in ('evidence_id','document_id','pdf_page','report_period','report_type'))),'[]')
                into rows from jsonb_array_elements(entry->evidence_field) e;
              entry := jsonb_set(entry,array[evidence_field],rows);
            end if;
          end loop;
          entries := entries || jsonb_build_array(entry);
        end loop;
        planning := jsonb_set(planning,array[k],entries);
      end loop;
      b := b || jsonb_build_object('assurance_planning',planning);
    end if;
  else
    select coalesce(jsonb_agg(m),'[]') into rows from jsonb_array_elements(coalesce(r->'matters','[]')) m where m->>'matter_id'=p_matter_id;
    if jsonb_array_length(rows)=0 then return meta || jsonb_build_object('result',null); end if;
    b := b || jsonb_build_object('matters',rows);
    b := b || jsonb_build_object('current_task_ids',coalesce((select jsonb_agg(c->'task_id') from jsonb_array_elements(coalesce(r->'provider_calls','[]')) c where c ? 'task_id'),'[]'));
    foreach k in array array['matter_events','matter_commitments','matter_paths','matter_relations',
      'matter_explanations','matter_assessments','matter_tasks','matter_tool_receipts','matter_rejections'] loop
      select coalesce(jsonb_agg(x),'[]') into rows from jsonb_array_elements(coalesce(r->k,'[]')) x
        where x->>'matter_id'=p_matter_id or (k='matter_tasks' and x->>'role'='A1');
      b := b || jsonb_build_object(k,rows);
    end loop;
    select coalesce(jsonb_agg(e),'[]') into rows from jsonb_array_elements(coalesce(r->'matter_evidence','[]')) e
      where (b @? ('$.**.evidence_ids[*] ? (@ == ' || to_jsonb(e->>'evidence_id')::text || ')')::jsonpath)
        or (b @? ('$.**.supporting_evidence_ids[*] ? (@ == ' || to_jsonb(e->>'evidence_id')::text || ')')::jsonpath)
        or (b @? ('$.**.counter_evidence_ids[*] ? (@ == ' || to_jsonb(e->>'evidence_id')::text || ')')::jsonpath);
    b := b || jsonb_build_object('matter_evidence',rows);
    select coalesce(jsonb_agg(n),'[]') into rows from jsonb_array_elements(coalesce(r->'matter_graph'->'nodes','[]')) n
      where n->>'matter_id'=p_matter_id or exists(select 1 from jsonb_array_elements(coalesce(b->'matter_evidence','[]')) e where e->>'evidence_id'=n->>'id')
      or exists(select 1 from jsonb_array_elements(coalesce(b->'matter_relations','[]')) e where n->>'id' in (e->>'source_id',e->>'target_id'));
    b := b || jsonb_build_object('matter_graph',jsonb_build_object('nodes',rows));
  end if;
  return meta || jsonb_build_object('result',b);
end $$;
revoke all on function public.connectivity_read_projection(text,text,text) from public, anon, authenticated;
grant execute on function public.connectivity_read_projection(text,text,text) to service_role;
commit;
