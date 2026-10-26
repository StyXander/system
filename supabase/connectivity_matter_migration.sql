-- 五Agent逐请求额度占用；复用原表和service_role，保留实际或未知在途用量。

begin;

alter table public.public_model_usage add column if not exists last_activity_at timestamptz;

create or replace function public.reserve_public_model_usage(
  p_reservation_id text,
  p_client_hash text,
  p_window_seconds integer,
  p_per_ip integer,
  p_global_window integer,
  p_max_concurrent integer,
  p_daily_runs integer,
  p_reservation_ttl_seconds integer,
  p_batch boolean default false
)
returns jsonb
language plpgsql security definer set search_path = public
as $$
declare
  now_ts timestamptz := now();
  day_start timestamptz := date_trunc('day', now_ts at time zone 'Asia/Shanghai') at time zone 'Asia/Shanghai';
  recent_ip integer;
  recent_global integer;
  active_count integer;
  day_runs integer;
begin
  perform public.assert_service_role();
  if p_reservation_id is null or length(p_reservation_id) < 8 or length(p_reservation_id) > 128
     or p_client_hash is null or length(p_client_hash) <> 64 then
    return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_REQUEST_INVALID', 'message', '公开模型额度请求不合法。');
  end if;
  lock table public.public_model_usage in share row exclusive mode;
  update public.public_model_usage
  set released = (input_tokens = 0 and output_tokens = 0), settled = true
  where settled = false and released = false
    and coalesce(last_activity_at,reserved_at) < now_ts - make_interval(secs => greatest(p_reservation_ttl_seconds, 30));
  select count(*) into recent_ip
  from public.public_model_usage
  where client_hash = p_client_hash and released = false
    and reserved_at >= now_ts - make_interval(secs => greatest(p_window_seconds, 60));
  select count(*) into recent_global
  from public.public_model_usage
  where released = false
    and reserved_at >= now_ts - make_interval(secs => greatest(p_window_seconds, 60));
  select count(*) into active_count
  from public.public_model_usage
  where settled = false and released = false
    and coalesce(last_activity_at,reserved_at) >= now_ts - make_interval(secs => greatest(p_reservation_ttl_seconds, 30));
  select count(*) into day_runs
  from public.public_model_usage
  where released = false and reserved_at >= day_start;
  if not p_batch and recent_ip >= greatest(p_per_ip, 1) then
    return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_PER_CLIENT', 'message', '当前访问来源的模型额度已达上限，请稍后再试。');
  end if;
  if not p_batch and recent_global >= greatest(p_global_window, 1) then
    return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_GLOBAL_WINDOW', 'message', '公开演示模型正在排队，请稍后再试。');
  end if;
  if active_count >= greatest(p_max_concurrent, 1) then
    return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_CONCURRENT', 'message', '当前模型并发已满，请等待上一条分析完成。');
  end if;
  if day_runs >= greatest(p_daily_runs, 1) then
    return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_DAILY_RUNS', 'message', '今日公开演示额度已用完。');
  end if;
  insert into public.public_model_usage(reservation_id, client_hash, reserved_at)
  values (p_reservation_id, p_client_hash, now_ts);
  return jsonb_build_object('ok', true, 'reservation_id', p_reservation_id);
exception when unique_violation then
  return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_RESERVATION_CONFLICT', 'message', '公开模型额度请求发生并发冲突，请稍后重试。');
end;
$$;

create or replace function public.settle_public_model_usage(
  p_reservation_id text,
  p_input_tokens integer,
  p_output_tokens integer,
  p_daily_input_tokens integer,
  p_daily_output_tokens integer
)
returns jsonb
language plpgsql security definer set search_path = public
as $$
declare
  current_row public.public_model_usage;
  day_start timestamptz := date_trunc('day', now() at time zone 'Asia/Shanghai') at time zone 'Asia/Shanghai';
  used_input bigint;
  used_output bigint;
  new_input integer := greatest(coalesce(p_input_tokens, 0), 0);
  new_output integer := greatest(coalesce(p_output_tokens, 0), 0);
begin
  perform public.assert_service_role();
  lock table public.public_model_usage in share row exclusive mode;
  select * into current_row from public.public_model_usage
  where reservation_id = p_reservation_id and released = false for update;
  if current_row.reservation_id is null then
    return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_RESERVATION_MISSING', 'message', '公开模型额度预留已失效。');
  end if;
  select coalesce(sum(input_tokens), 0), coalesce(sum(output_tokens), 0)
    into used_input, used_output
  from public.public_model_usage
  where reserved_at >= day_start and released = false;
  update public.public_model_usage
  set input_tokens = new_input, output_tokens = new_output, settled = true
  where reservation_id = p_reservation_id;
  if used_input - current_row.input_tokens + new_input > greatest(p_daily_input_tokens, 1) then
    return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_INPUT_TOKENS', 'message', '今日输入 token 预算已用完。');
  end if;
  if used_output - current_row.output_tokens + new_output > greatest(p_daily_output_tokens, 1) then
    return jsonb_build_object('ok', false, 'code', 'PUBLIC_QUOTA_OUTPUT_TOKENS', 'message', '今日输出 token 预算已用完。');
  end if;
  return jsonb_build_object('ok', true, 'reservation_id', p_reservation_id);
end;
$$;

create or replace function public.checkpoint_public_model_usage(
  p_reservation_id text, p_input_tokens integer, p_output_tokens integer,
  p_daily_input_tokens integer, p_daily_output_tokens integer
) returns jsonb language plpgsql security definer set search_path=public as $$
declare
  current_row public.public_model_usage;
  day_start timestamptz := date_trunc('day',now() at time zone 'Asia/Shanghai') at time zone 'Asia/Shanghai';
  used_input bigint; used_output bigint;
begin
  perform public.assert_service_role();
  lock table public.public_model_usage in share row exclusive mode;
  select * into current_row from public.public_model_usage
    where reservation_id=p_reservation_id and released=false and settled=false for update;
  if current_row.reservation_id is null then
    return jsonb_build_object('ok',false,'code','PUBLIC_QUOTA_RESERVATION_MISSING','message','额度租约失效');
  end if;
  select coalesce(sum(input_tokens),0),coalesce(sum(output_tokens),0) into used_input,used_output
    from public.public_model_usage where reserved_at>=day_start and released=false;
  if used_input-current_row.input_tokens+greatest(p_input_tokens,0)>p_daily_input_tokens
     or used_output-current_row.output_tokens+greatest(p_output_tokens,0)>p_daily_output_tokens then
    return jsonb_build_object('ok',false,'code','PUBLIC_QUOTA_TOKENS','message','后续请求的预留将超过今日预算');
  end if;
  update public.public_model_usage set input_tokens=greatest(p_input_tokens,0),output_tokens=greatest(p_output_tokens,0),last_activity_at=now()
    where reservation_id=p_reservation_id;
  return jsonb_build_object('ok',true,'reservation_id',p_reservation_id);
end; $$;

create or replace function public.snapshot_public_model_usage(
  p_client_hash text,
  p_window_seconds integer,
  p_global_window integer,
  p_max_concurrent integer,
  p_reservation_ttl_seconds integer,
  p_daily_runs integer
)
returns jsonb
language plpgsql security definer set search_path = public
as $$
declare
  now_ts timestamptz := now();
  day_start timestamptz := date_trunc('day', now_ts at time zone 'Asia/Shanghai') at time zone 'Asia/Shanghai';
  global_count integer;
  client_count integer;
  active_count integer;
  daily_count integer;
begin
  perform public.assert_service_role();
  update public.public_model_usage
  set settled = true, released = (input_tokens = 0 and output_tokens = 0)
  where settled = false and released = false
    and coalesce(last_activity_at,reserved_at) < now_ts - make_interval(secs => greatest(p_reservation_ttl_seconds, 30));
  select count(*) into global_count from public.public_model_usage
  where released = false and reserved_at >= now_ts - make_interval(secs => greatest(p_window_seconds, 60));
  select count(*) into client_count from public.public_model_usage
  where p_client_hash is not null and client_hash = p_client_hash and released = false
    and reserved_at >= now_ts - make_interval(secs => greatest(p_window_seconds, 60));
  select count(*) into active_count from public.public_model_usage
  where settled = false and released = false
    and coalesce(last_activity_at,reserved_at) >= now_ts - make_interval(secs => greatest(p_reservation_ttl_seconds, 30));
  select count(*) into daily_count from public.public_model_usage
  where released = false and reserved_at >= day_start;
  return jsonb_build_object(
    'ok', true,
    'global_remaining_15m', greatest(0, greatest(p_global_window, 1) - global_count),
    'daily_runs_remaining', greatest(0, greatest(p_daily_runs, 1) - daily_count),
    'active', active_count,
    'client_recent', client_count,
    'max_concurrent', greatest(p_max_concurrent, 1),
    'reset_at', (day_start + interval '1 day')::text
  );
end;
$$;

revoke all on function public.checkpoint_public_model_usage(text,integer,integer,integer,integer) from public,anon,authenticated;

grant execute on function public.checkpoint_public_model_usage(text,integer,integer,integer,integer) to service_role;

commit;
