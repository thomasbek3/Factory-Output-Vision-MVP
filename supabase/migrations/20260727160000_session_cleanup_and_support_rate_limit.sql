-- Browser shutdown is not a reliable delivery event. Close abandoned work
-- sessions server-side and bound worker support traffic.

create or replace function public.service_close_stale_work_sessions()
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  closed_count integer;
begin
  update public.reviewer_work_sessions
  set ended_at = now(),
      close_reason = 'heartbeat_timeout'
  where ended_at is null
    and last_seen_at < now() - interval '2 minutes';
  get diagnostics closed_count = row_count;
  return closed_count;
end;
$$;

create or replace function public.worker_request_support(
  p_assignment_id uuid,
  p_reason_code text,
  p_message text
)
returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  request_id uuid;
begin
  select * into lifecycle_row from public.reviewer_lifecycles where user_id = actor_id;
  if lifecycle_row.user_id is null then
    raise exception 'reviewer is not registered' using errcode = '42501';
  end if;
  if (
    select count(*) from public.reviewer_support_requests
    where reviewer_id = actor_id and created_at > now() - interval '1 hour'
  ) >= 10 then
    raise exception 'support request limit reached' using errcode = '54000';
  end if;
  insert into public.reviewer_support_requests (
    factory_id, reviewer_id, assignment_id, reason_code, message
  ) values (
    lifecycle_row.factory_id, actor_id, p_assignment_id, p_reason_code, trim(p_message)
  ) returning id into request_id;
  return request_id;
end;
$$;

revoke all on function public.service_close_stale_work_sessions()
  from public, anon, authenticated;

do $$
begin
  if not exists (
    select 1 from cron.job where jobname = 'factoryvision-work-session-cleanup'
  ) then
    perform cron.schedule(
      'factoryvision-work-session-cleanup',
      '* * * * *',
      'select public.service_close_stale_work_sessions();'
    );
  end if;
end;
$$;
