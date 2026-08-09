-- 审迹智链公网模式数据库草案。
-- 执行顺序：Supabase 新项目中一次性运行本文件，再配置 Render 的服务端环境变量。
-- 服务端 service role 只给 web/worker，不进入前端；普通查询依赖 auth.uid() 与 RLS。

create extension if not exists pgcrypto;

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.organization_members (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'member', 'reviewer')),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create table if not exists public.cases (
  -- case_scope 是证据对象内部主键；相同 case_id 可在不同租户安全并存。
  case_scope text generated always as (coalesce(tenant_id::text, 'PUBLIC') || ':' || case_id) stored primary key,
  case_id text not null,
  tenant_id uuid references public.organizations(id) on delete restrict,
  sample_type text not null check (sample_type in ('public', 'authorized_deidentified', 'synthetic')),
  company_name text not null,
  ticker text,
  source_snapshot_id text,
  t0 date,
  import_status text not null default 'staging' check (import_status in ('staging', 'ready')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique nulls not distinct (tenant_id, case_id)
);

create table if not exists public.report_documents (
  case_scope text generated always as (coalesce(tenant_id::text, 'PUBLIC') || ':' || case_id) stored,
  case_id text not null,
  tenant_id uuid references public.organizations(id) on delete restrict,
  document_id text not null,
  report_year integer not null,
  source_url text,
  sha256 text not null,
  page_count integer,
  validation_status text,
  storage_object_path text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (case_scope, document_id),
  foreign key (case_scope) references public.cases(case_scope) on delete cascade,
  unique nulls not distinct (tenant_id, case_id, document_id)
);

create table if not exists public.field_evidence (
  case_scope text generated always as (coalesce(tenant_id::text, 'PUBLIC') || ':' || case_id) stored,
  case_id text not null,
  tenant_id uuid references public.organizations(id) on delete restrict,
  evidence_id text not null,
  field_id text,
  year integer,
  value numeric,
  document_id text,
  pdf_page integer,
  file_sha256 text,
  metadata jsonb not null default '{}'::jsonb,
  primary key (case_scope, evidence_id),
  foreign key (case_scope) references public.cases(case_scope) on delete cascade,
  unique nulls not distinct (tenant_id, case_id, evidence_id)
);

-- 全局公开候选不可被任一租户直接覆盖；真人决定写入租户 overlay。
create table if not exists public.field_review_overlays (
  tenant_id uuid not null references public.organizations(id) on delete cascade,
  case_scope text not null references public.cases(case_scope) on delete cascade,
  case_id text not null,
  evidence_id text not null,
  field_id text not null,
  value numeric,
  pdf_page integer,
  metadata jsonb not null,
  reviewed_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, case_scope, evidence_id)
);

create table if not exists public.rag_chunks (
  id uuid primary key default gen_random_uuid(),
  case_scope text generated always as (coalesce(tenant_id::text, 'PUBLIC') || ':' || case_id) stored,
  case_id text not null,
  tenant_id uuid references public.organizations(id) on delete restrict,
  rag_snapshot_id text not null,
  -- 同一内容快照可有多个 staging 尝试；generation 隔离失败批次与当前 active 行。
  generation_id text not null,
  active boolean not null default false,
  chunk_id text not null,
  document_id text,
  pdf_page integer,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  foreign key (case_scope) references public.cases(case_scope) on delete cascade,
  unique nulls not distinct (tenant_id, case_id, generation_id, chunk_id)
);

-- 兼容旧部署：先为历史活动行补 generation，再替换会阻止独立 staging 的旧唯一约束。
alter table public.rag_chunks add column if not exists generation_id text;
update public.rag_chunks set generation_id = rag_snapshot_id where generation_id is null;
alter table public.rag_chunks alter column generation_id set not null;
alter table public.rag_chunks drop constraint if exists rag_chunks_tenant_id_case_id_rag_snapshot_id_chunk_id_key;
create unique index if not exists rag_chunks_generation_chunk_uidx
  on public.rag_chunks (tenant_id, case_id, generation_id, chunk_id) nulls not distinct;

create table if not exists public.rag_retrievals (
  retrieval_id text primary key,
  case_scope text generated always as (coalesce(case_tenant_id::text, 'PUBLIC') || ':' || case_id) stored,
  case_id text not null,
  case_tenant_id uuid references public.organizations(id) on delete restrict,
  -- tenant_id 是发起检索的所有者；匿名公开检索才允许为空。
  tenant_id uuid references public.organizations(id) on delete cascade,
  requested_by uuid references auth.users(id) on delete set null,
  rag_snapshot_id text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  foreign key (case_scope) references public.cases(case_scope) on delete cascade
);

create table if not exists public.analysis_runs (
  run_id text primary key,
  case_scope text generated always as (coalesce(case_tenant_id::text, 'PUBLIC') || ':' || case_id) stored,
  case_id text not null,
  case_tenant_id uuid references public.organizations(id) on delete restrict,
  -- tenant_id 是运行所有者，与公开证据的 case_tenant_id 语义分离。
  tenant_id uuid references public.organizations(id) on delete restrict,
  pipeline_task_id text,
  status text not null,
  run_completeness text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (case_scope) references public.cases(case_scope) on delete cascade
);

-- 已批准缓存与分析运行分表保存；payload 保留原运行、人工复核和“非新分析”边界。
create table if not exists public.run_caches (
  cache_id text primary key,
  source_run_id text not null references public.analysis_runs(run_id) on delete cascade,
  case_scope text generated always as (coalesce(case_tenant_id::text, 'PUBLIC') || ':' || case_id) stored,
  case_id text not null,
  case_tenant_id uuid references public.organizations(id) on delete restrict,
  tenant_id uuid not null references public.organizations(id) on delete restrict,
  created_by uuid not null references auth.users(id) on delete restrict,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (case_scope) references public.cases(case_scope) on delete cascade
);

create table if not exists public.pipeline_tasks (
  task_id text primary key,
  tenant_id uuid references public.organizations(id) on delete restrict,
  requested_by uuid references auth.users(id) on delete set null,
  request_payload jsonb not null,
  status text not null default 'queued' check (status in ('queued', 'running', 'completed', 'failed')),
  attempt integer not null default 0,
  available_at timestamptz not null default now(),
  lease_until timestamptz,
  lease_token uuid,
  worker_id text,
  result jsonb,
  error jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 批次本身记录任务清单与请求快照；任务进度仍由 pipeline_tasks 的租约状态提供。
create table if not exists public.cache_prewarm_batches (
  batch_id text primary key,
  tenant_id uuid not null references public.organizations(id) on delete restrict,
  requested_by uuid not null references auth.users(id) on delete restrict,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.model_transfer_consents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.organizations(id) on delete cascade,
  case_scope text generated always as (coalesce(case_tenant_id::text, 'PUBLIC') || ':' || case_id) stored,
  case_id text not null,
  case_tenant_id uuid references public.organizations(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete restrict,
  provider text not null,
  model_id text not null,
  transmission_scope text not null,
  purpose text not null,
  valid_until timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  foreign key (case_scope) references public.cases(case_scope) on delete cascade
);

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.organizations(id) on delete restrict,
  user_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  case_id text,
  run_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists organization_members_user_idx on public.organization_members(user_id, active);
create index if not exists cases_tenant_idx on public.cases(tenant_id);
create index if not exists rag_chunks_active_scope_idx on public.rag_chunks(case_scope, active, rag_snapshot_id);
create index if not exists pipeline_tasks_claim_idx on public.pipeline_tasks(status, available_at, lease_until);
create index if not exists analysis_runs_tenant_idx on public.analysis_runs(tenant_id, updated_at desc);
create unique index if not exists analysis_runs_task_idempotency_idx
  on public.analysis_runs(tenant_id, pipeline_task_id)
  where pipeline_task_id is not null;
create index if not exists run_caches_tenant_idx on public.run_caches(tenant_id, created_at desc);
create index if not exists cache_prewarm_batches_owner_idx on public.cache_prewarm_batches(tenant_id, requested_by, created_at desc);
create unique index if not exists model_transfer_consents_active_idx
  on public.model_transfer_consents(tenant_id, case_scope, user_id, provider, model_id, transmission_scope)
  where revoked_at is null;

create or replace function public.is_org_member(target_tenant uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.organization_members m
    where m.organization_id = target_tenant
      and m.user_id = auth.uid()
      and m.active = true
  );
$$;

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.cases enable row level security;
alter table public.report_documents enable row level security;
alter table public.field_evidence enable row level security;
alter table public.field_review_overlays enable row level security;
alter table public.rag_chunks enable row level security;
alter table public.rag_retrievals enable row level security;
alter table public.analysis_runs enable row level security;
alter table public.run_caches enable row level security;
alter table public.pipeline_tasks enable row level security;
alter table public.cache_prewarm_batches enable row level security;
alter table public.model_transfer_consents enable row level security;
alter table public.audit_events enable row level security;

-- 私有 bucket 由迁移脚本幂等创建；默认不公开，并限制为当前补充资料支持的文件类型。
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'audittrace-private',
  'audittrace-private',
  false,
  15728640,
  array['application/pdf', 'application/json', 'text/plain', 'text/csv',
        'application/octet-stream',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document']::text[]
)
on conflict (id) do update set
  name = excluded.name,
  public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy organizations_member_read on public.organizations for select using (public.is_org_member(id));
create policy memberships_self_read on public.organization_members for select using (user_id = auth.uid());
create policy cases_public_or_member_read on public.cases for select using (
  import_status = 'ready' and ((sample_type = 'public' and tenant_id is null) or public.is_org_member(tenant_id))
);
create policy documents_public_or_member_read on public.report_documents for select using (
  exists (select 1 from public.cases c where c.case_scope = report_documents.case_scope and c.import_status = 'ready' and ((c.sample_type = 'public' and c.tenant_id is null) or public.is_org_member(c.tenant_id)))
);
create policy evidence_public_or_member_read on public.field_evidence for select using (
  exists (select 1 from public.cases c where c.case_scope = field_evidence.case_scope and c.import_status = 'ready' and ((c.sample_type = 'public' and c.tenant_id is null) or public.is_org_member(c.tenant_id)))
);
create policy field_review_overlays_member_read on public.field_review_overlays for select using (
  public.is_org_member(tenant_id)
);
create policy rag_public_or_member_read on public.rag_chunks for select using (
  exists (select 1 from public.cases c where c.case_scope = rag_chunks.case_scope and c.import_status = 'ready' and ((c.sample_type = 'public' and c.tenant_id is null) or public.is_org_member(c.tenant_id)))
);
create policy rag_retrievals_public_or_member_read on public.rag_retrievals for select using (
  (rag_retrievals.tenant_id is null and exists (
    select 1 from public.cases c where c.case_scope = rag_retrievals.case_scope
      and c.import_status = 'ready' and c.sample_type = 'public' and c.tenant_id is null
  ))
  or public.is_org_member(rag_retrievals.tenant_id)
);
create policy runs_public_or_member_read on public.analysis_runs for select using (
  (analysis_runs.tenant_id is null and exists (
    select 1 from public.cases c
    where c.case_scope = analysis_runs.case_scope and c.import_status = 'ready' and c.sample_type = 'public' and c.tenant_id is null
  ))
  or public.is_org_member(analysis_runs.tenant_id)
);
create policy run_caches_member_read on public.run_caches for select using (
  public.is_org_member(tenant_id)
);
create policy cache_prewarm_batches_owner_read on public.cache_prewarm_batches for select using (
  requested_by = auth.uid() and public.is_org_member(tenant_id)
);
create policy consent_member_read on public.model_transfer_consents for select using (public.is_org_member(tenant_id));
create policy audit_member_read on public.audit_events for select using (public.is_org_member(tenant_id));

-- 私有 PDF 的对象名第一段必须是租户 UUID；浏览器不能用公开 bucket 直读。
create policy audittrace_private_member_read on storage.objects
for select using (
  bucket_id = 'audittrace-private'
  and public.is_org_member(((storage.foldername(name))[1])::uuid)
);
-- 浏览器没有删除原件的业务入口，因此不创建 storage.objects DELETE policy；
-- 清理只能由受审计的 service-role 后台流程执行。

-- 队列只由服务端 service role 通过 RPC 操作，浏览器 JWT 没有直接写入权限。
create or replace function public.assert_service_role()
returns void
language plpgsql
security invoker
set search_path = public
as $$
begin
  if coalesce(current_setting('request.jwt.claim.role', true), '') <> 'service_role' then
    raise insufficient_privilege using message = 'service role required';
  end if;
end;
$$;

drop function if exists public.publish_rag_snapshot(text, text);
create or replace function public.publish_rag_snapshot(
  p_case_scope text,
  p_rag_snapshot_id text,
  p_generation_id text,
  p_expected_count integer
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare staged_count integer;
declare active_count integer;
declare affected integer;
begin
  perform public.assert_service_role();
  -- 同一案例并发发布按 case_scope 串行化；事务提交后最多只有一个活动快照。
  perform pg_advisory_xact_lock(hashtextextended(p_case_scope, 0));
  if p_expected_count <= 0 then
    return false;
  end if;
  select count(*) into staged_count
  from public.rag_chunks
  where case_scope = p_case_scope
    and rag_snapshot_id = p_rag_snapshot_id
    and generation_id = p_generation_id
    and active = false;
  if staged_count <> p_expected_count then
    -- 任一分批缺失都保持旧 active 原样；不允许“已有一行”就切换半成品。
    return false;
  end if;
  select count(*) into active_count
  from public.rag_chunks
  where case_scope = p_case_scope
    and rag_snapshot_id = p_rag_snapshot_id
    and active = true;
  if active_count = p_expected_count then
    -- 并发发布者已先完成相同内容，当前 staging 留作非活动审计副本即可。
    return true;
  end if;
  update public.rag_chunks set active = false where case_scope = p_case_scope and active = true;
  update public.rag_chunks
  set active = true
  where case_scope = p_case_scope
    and rag_snapshot_id = p_rag_snapshot_id
    and generation_id = p_generation_id;
  get diagnostics affected = row_count;
  return affected = p_expected_count;
end;
$$;

create or replace function public.upsert_model_transfer_consent(
  p_tenant_id uuid,
  p_case_id text,
  p_case_tenant_id uuid,
  p_user_id uuid,
  p_provider text,
  p_model_id text,
  p_transmission_scope text,
  p_purpose text,
  p_valid_until timestamptz
)
returns setof public.model_transfer_consents
language plpgsql
security definer
set search_path = public
as $$
declare current_row public.model_transfer_consents;
begin
  perform public.assert_service_role();
  perform pg_advisory_xact_lock(hashtextextended(
    p_tenant_id::text || ':' || coalesce(p_case_tenant_id::text, 'PUBLIC') || ':' || p_case_id || ':' || p_user_id::text || ':' || p_provider || ':' || p_model_id,
    0
  ));
  update public.model_transfer_consents
  set revoked_at = now()
  where tenant_id = p_tenant_id and case_id = p_case_id
    and case_tenant_id is not distinct from p_case_tenant_id
    and user_id = p_user_id and provider = p_provider and model_id = p_model_id
    and transmission_scope = p_transmission_scope and revoked_at is null and valid_until <= now();
  select * into current_row
  from public.model_transfer_consents
  where tenant_id = p_tenant_id and case_id = p_case_id
    and case_tenant_id is not distinct from p_case_tenant_id
    and user_id = p_user_id and provider = p_provider and model_id = p_model_id
    and transmission_scope = p_transmission_scope and revoked_at is null
  for update;
  if current_row.id is not null then
    update public.model_transfer_consents
    set valid_until = greatest(valid_until, p_valid_until), purpose = p_purpose
    where id = current_row.id returning * into current_row;
    return next current_row;
    return;
  end if;
  insert into public.model_transfer_consents (
    tenant_id, case_id, case_tenant_id, user_id, provider, model_id,
    transmission_scope, purpose, valid_until
  ) values (
    p_tenant_id, p_case_id, p_case_tenant_id, p_user_id, p_provider, p_model_id,
    p_transmission_scope, p_purpose, p_valid_until
  ) returning * into current_row;
  return next current_row;
end;
$$;

create or replace function public.claim_pipeline_task(p_worker_id text, p_lease_seconds integer)
returns setof public.pipeline_tasks
language plpgsql
security definer
set search_path = public
as $$
declare claimed public.pipeline_tasks;
begin
  perform public.assert_service_role();
  -- 正常 fail RPC 会在第三次尝试后终止，但进程若每次都在上报前崩溃，
  -- 只能由下一次 claim 原子收割；否则最老任务会被无限重领并饿死后续队列。
  update public.pipeline_tasks
  set status = 'failed',
      error = coalesce(error, '{}'::jsonb) || jsonb_build_object(
        'code', 'LEASE_RETRY_EXHAUSTED',
        'message', 'worker 连续三次在租约内未完成，任务已停止自动重领。',
        'reaped_at', now()
      ),
      lease_until = null, lease_token = null, worker_id = null, updated_at = now()
  where status = 'running' and lease_until < now() and attempt >= 3;
  select * into claimed
  from public.pipeline_tasks
  where (
      (status = 'queued' and available_at <= now())
      or (status = 'running' and lease_until < now() and attempt < 3)
    )
  order by created_at
  for update skip locked
  limit 1;
  if claimed.task_id is null then return; end if;
  update public.pipeline_tasks
  set status = 'running', worker_id = p_worker_id,
      attempt = attempt + 1,
      lease_token = gen_random_uuid(),
      lease_until = now() + make_interval(secs => greatest(p_lease_seconds, 30)),
      error = case
        when claimed.status = 'running' then coalesce(error, '{}'::jsonb) || jsonb_build_object(
          'code', 'LEASE_EXPIRED_RECLAIMED',
          'reclaimed_at', now()
        )
        else error
      end,
      updated_at = now()
  where task_id = claimed.task_id
  returning * into claimed;
  return next claimed;
end;
$$;

create or replace function public.heartbeat_pipeline_task(
  p_task_id text, p_worker_id text, p_lease_token uuid, p_lease_seconds integer
)
returns boolean language plpgsql security definer set search_path = public as $$
declare affected integer;
begin
  perform public.assert_service_role();
  update public.pipeline_tasks
  set lease_until = now() + make_interval(secs => greatest(p_lease_seconds, 30)), updated_at = now()
  where task_id = p_task_id and worker_id = p_worker_id and lease_token = p_lease_token
    and status = 'running' and lease_until > now();
  get diagnostics affected = row_count;
  return affected = 1;
end;
$$;

create or replace function public.complete_pipeline_task(
  p_task_id text, p_worker_id text, p_lease_token uuid, p_result jsonb
)
returns boolean language plpgsql security definer set search_path = public as $$
declare affected integer;
begin
  perform public.assert_service_role();
  update public.pipeline_tasks
  set status = 'completed', result = p_result, lease_until = null, lease_token = null, updated_at = now()
  where task_id = p_task_id and worker_id = p_worker_id and lease_token = p_lease_token
    and status = 'running' and lease_until > now();
  get diagnostics affected = row_count;
  return affected = 1;
end;
$$;

create or replace function public.fail_pipeline_task(
  p_task_id text, p_worker_id text, p_lease_token uuid, p_error jsonb, p_retry boolean
)
returns boolean language plpgsql security definer set search_path = public as $$
declare affected integer;
begin
  perform public.assert_service_role();
  update public.pipeline_tasks
  set status = case when p_retry and attempt < 3 then 'queued' else 'failed' end,
      error = p_error, lease_until = null, lease_token = null, worker_id = null,
      updated_at = now(), available_at = now() + interval '30 seconds'
  where task_id = p_task_id and worker_id = p_worker_id and lease_token = p_lease_token
    and status = 'running' and lease_until > now();
  get diagnostics affected = row_count;
  return affected = 1;
end;
$$;

create or replace function public.requeue_pipeline_task(
  p_task_id text, p_request_payload jsonb, p_expected_status text, p_expected_attempt integer
)
returns boolean language plpgsql security definer set search_path = public as $$
declare affected integer;
begin
  perform public.assert_service_role();
  update public.pipeline_tasks
  set status = 'queued', request_payload = p_request_payload,
      lease_until = null, lease_token = null, worker_id = null, result = null, error = null,
      available_at = now(), updated_at = now()
  where task_id = p_task_id and status = p_expected_status and attempt = p_expected_attempt;
  get diagnostics affected = row_count;
  return affected = 1;
end;
$$;

create or replace function public.enqueue_prewarm_batch(
  p_batch_id text,
  p_tenant_id uuid,
  p_requested_by uuid,
  p_payload jsonb,
  p_tasks jsonb
)
returns boolean language plpgsql security definer set search_path = public as $$
declare
  task_count integer;
  summary_count integer;
begin
  perform public.assert_service_role();
  if jsonb_typeof(p_payload) <> 'object'
     or jsonb_typeof(p_payload->'tasks') <> 'array'
     or jsonb_typeof(p_tasks) <> 'array'
     or p_payload->>'batch_id' <> p_batch_id then
    raise data_exception using message = 'invalid prewarm batch payload';
  end if;
  task_count := jsonb_array_length(p_tasks);
  summary_count := jsonb_array_length(p_payload->'tasks');
  if task_count < 1 or task_count > 50 or summary_count <> task_count then
    raise data_exception using message = 'invalid prewarm task count';
  end if;

  -- 同一幂等键并发到达时按 batch_id 串行化；函数内任一校验异常会回滚
  -- 批次和全部任务，不能留下“批次存在但只入队一部分”的中间态。
  perform pg_advisory_xact_lock(hashtextextended(p_batch_id, 0));
  if exists (
    select 1 from public.cache_prewarm_batches b
    where b.batch_id = p_batch_id
      and (b.tenant_id is distinct from p_tenant_id
           or b.requested_by is distinct from p_requested_by
           or b.payload is distinct from p_payload)
  ) then
    raise unique_violation using message = 'prewarm idempotency key payload mismatch';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(p_tasks) item
    where coalesce(item->>'task_id', '') = ''
       or jsonb_typeof(item->'request_payload') <> 'object'
       or not exists (
         select 1 from jsonb_array_elements(p_payload->'tasks') summary
         where summary->>'task_id' = item->>'task_id'
       )
  ) then
    raise data_exception using message = 'invalid prewarm task specification';
  end if;
  if exists (
    select item->>'task_id'
    from jsonb_array_elements(p_tasks) item
    group by item->>'task_id'
    having count(*) <> 1
  ) then
    raise data_exception using message = 'duplicate prewarm task id';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(p_tasks) item
    join public.pipeline_tasks existing on existing.task_id = item->>'task_id'
    where existing.tenant_id is distinct from p_tenant_id
       or existing.requested_by is distinct from p_requested_by
       or existing.request_payload is distinct from item->'request_payload'
  ) then
    raise unique_violation using message = 'prewarm task id payload mismatch';
  end if;

  insert into public.cache_prewarm_batches(batch_id, tenant_id, requested_by, payload, updated_at)
  values (p_batch_id, p_tenant_id, p_requested_by, p_payload, now())
  on conflict (batch_id) do nothing;

  insert into public.pipeline_tasks(
    task_id, tenant_id, requested_by, request_payload, status, attempt, available_at, created_at, updated_at
  )
  select item->>'task_id', p_tenant_id, p_requested_by, item->'request_payload',
         'queued', 0, now(), now(), now()
  from jsonb_array_elements(p_tasks) item
  on conflict (task_id) do nothing;
  return true;
end;
$$;

create or replace function public.revoke_model_transfer_consent(p_consent_id uuid, p_tenant_id uuid, p_user_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform public.assert_service_role();
  update public.model_transfer_consents
  set revoked_at = now()
  where id = p_consent_id and tenant_id = p_tenant_id and user_id = p_user_id and revoked_at is null;
end;
$$;

-- SECURITY DEFINER RPC 默认可能继承 PUBLIC EXECUTE；显式只授权 service_role。
revoke all on function public.assert_service_role() from public, anon, authenticated;
revoke all on function public.publish_rag_snapshot(text, text, text, integer) from public, anon, authenticated;
revoke all on function public.upsert_model_transfer_consent(uuid, text, uuid, uuid, text, text, text, text, timestamptz) from public, anon, authenticated;
revoke all on function public.claim_pipeline_task(text, integer) from public, anon, authenticated;
revoke all on function public.heartbeat_pipeline_task(text, text, uuid, integer) from public, anon, authenticated;
revoke all on function public.complete_pipeline_task(text, text, uuid, jsonb) from public, anon, authenticated;
revoke all on function public.fail_pipeline_task(text, text, uuid, jsonb, boolean) from public, anon, authenticated;
revoke all on function public.requeue_pipeline_task(text, jsonb, text, integer) from public, anon, authenticated;
revoke all on function public.enqueue_prewarm_batch(text, uuid, uuid, jsonb, jsonb) from public, anon, authenticated;
revoke all on function public.revoke_model_transfer_consent(uuid, uuid, uuid) from public, anon, authenticated;
grant execute on function public.assert_service_role() to service_role;
grant execute on function public.publish_rag_snapshot(text, text, text, integer) to service_role;
grant execute on function public.upsert_model_transfer_consent(uuid, text, uuid, uuid, text, text, text, text, timestamptz) to service_role;
grant execute on function public.claim_pipeline_task(text, integer) to service_role;
grant execute on function public.heartbeat_pipeline_task(text, text, uuid, integer) to service_role;
grant execute on function public.complete_pipeline_task(text, text, uuid, jsonb) to service_role;
grant execute on function public.fail_pipeline_task(text, text, uuid, jsonb, boolean) to service_role;
grant execute on function public.requeue_pipeline_task(text, jsonb, text, integer) to service_role;
grant execute on function public.enqueue_prewarm_batch(text, uuid, uuid, jsonb, jsonb) to service_role;
grant execute on function public.revoke_model_transfer_consent(uuid, uuid, uuid) to service_role;

-- 对象路径约定为 <tenant_id>/<case_id>/<document_id>.pdf；客户端永远只拿短时签名 URL。
