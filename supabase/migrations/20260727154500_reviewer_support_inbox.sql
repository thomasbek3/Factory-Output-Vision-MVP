-- Ops support inbox for authenticated worker requests.

create or replace function public.ops_reviewer_support_requests()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  result jsonb;
begin
  if not public.actor_is_ops(null) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  select coalesce(jsonb_agg(jsonb_build_object(
    'id', support.id,
    'reviewerId', support.reviewer_id,
    'reviewerName', profile.display_name,
    'reviewerEmail', lifecycle.email,
    'factoryName', factory.name,
    'assignmentId', support.assignment_id,
    'reasonCode', support.reason_code,
    'message', support.message,
    'status', support.status,
    'createdAt', support.created_at
  ) order by support.created_at), '[]'::jsonb)
  into result
  from public.reviewer_support_requests support
  join public.profiles profile on profile.id = support.reviewer_id
  join public.reviewer_lifecycles lifecycle on lifecycle.user_id = support.reviewer_id
  join public.factories factory on factory.id = support.factory_id
  where support.status <> 'closed'
    and public.actor_is_ops(support.factory_id);
  return result;
end;
$$;

create or replace function public.ops_set_reviewer_support_status(
  p_request_id uuid,
  p_status text
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  support_row public.reviewer_support_requests%rowtype;
begin
  select * into support_row
  from public.reviewer_support_requests
  where id = p_request_id
  for update;
  if support_row.id is null or not public.actor_is_ops(support_row.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  if p_status not in ('acknowledged', 'closed') then
    raise exception 'unsupported support status' using errcode = '22023';
  end if;
  update public.reviewer_support_requests
  set status = p_status,
      closed_at = case when p_status = 'closed' then now() else null end
  where id = p_request_id;
  return jsonb_build_object('requestId', p_request_id, 'status', p_status);
end;
$$;

revoke all on function public.ops_reviewer_support_requests()
  from public, anon;
revoke all on function public.ops_set_reviewer_support_status(uuid, text)
  from public, anon;
grant execute on function public.ops_reviewer_support_requests()
  to authenticated;
grant execute on function public.ops_set_reviewer_support_status(uuid, text)
  to authenticated;
