-- 在已有任务表上增加修订并发约束，不新建任务平台或修改历史结果。
-- 可选的数据库约束加固。应用同时使用父版本稳定幂等键，已有
-- demo_run_tasks_idempotency_idx 即可保证跨实例只写入一个直接子版本。
begin;
create unique index if not exists connectivity_single_child_idx
  on public.demo_run_tasks ((request_payload->>'parent_run_id'))
  where task_kind = 'connectivity' and request_payload->>'parent_run_id' is not null;
commit;
