-- Follow-up proof hardening: make qualification attempts append-only, remove a
-- timestamp-based invitation uniqueness hazard, and centralize session/revoke
-- authorization.

alter table public.reviewer_invitations
  drop constraint if exists reviewer_invitations_user_id_created_at_key;

create trigger reviewer_qualification_attempts_immutable
before update or delete on public.reviewer_qualification_attempts
for each row execute function public.reject_append_only_change();

create trigger reviewer_qualification_attempts_reject_truncate
before truncate on public.reviewer_qualification_attempts
for each statement execute function public.reject_append_only_change();

revoke truncate on table public.reviewer_qualification_attempts
  from public, anon, authenticated, service_role;

create or replace function public.worker_authorize_reviewer_session()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle public.reviewer_lifecycles%rowtype;
begin
  select * into lifecycle
  from public.reviewer_lifecycles
  where user_id = actor_id;
  if lifecycle.user_id is null and public.actor_is_ops(null) then
    return jsonb_build_object('authorized', true, 'state', 'ops');
  end if;
  if lifecycle.user_id is null then
    raise exception 'reviewer is not registered' using errcode = '42501';
  end if;
  if lifecycle.state = 'invited'
     and not exists (
       select 1 from public.reviewer_invitations invitation
       where invitation.user_id = actor_id
         and invitation.status = 'accepted'
         and invitation.accepted_at is not null
     ) then
    raise exception 'an accepted invitation is required' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'authorized', true,
    'state', lifecycle.state
  );
end;
$$;

create or replace function public.ops_revoke_reviewer_invitation(
  p_user_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  lifecycle public.reviewer_lifecycles%rowtype;
  revoked_count integer;
begin
  select * into lifecycle
  from public.reviewer_lifecycles
  where user_id = p_user_id;
  if lifecycle.user_id is null
     or not public.actor_is_ops(lifecycle.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;

  update public.reviewer_invitations
  set status = 'revoked', revoked_at = now()
  where user_id = p_user_id
    and status in ('created', 'sent', 'delivery_failed');
  get diagnostics revoked_count = row_count;
  if revoked_count = 0 then
    raise exception 'no open invitation is available to revoke'
      using errcode = 'P0002';
  end if;
  return jsonb_build_object(
    'userId', p_user_id,
    'revoked', revoked_count
  );
end;
$$;

create or replace function public.ops_workforce_metrics()
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
  select jsonb_build_object(
    'factories', (
      select count(*) from public.factories factory
      where factory.status = 'active' and public.actor_is_ops(factory.id)
    ),
    'stationsUp', (
      select count(*) from public.stations station
      where station.status = 'active' and public.actor_is_ops(station.factory_id)
    ),
    'stationsTotal', (
      select count(*) from public.stations station
      where station.status <> 'retired' and public.actor_is_ops(station.factory_id)
    ),
    'submissionsToday', (
      select count(*) from public.review_submissions submission
      where submission.submitted_at > now() - interval '24 hours'
        and public.actor_is_ops(submission.factory_id)
    ),
    'oldestQueueMinutes', coalesce((
      select floor(extract(epoch from (now() - min(assignment.assigned_at))) / 60)::integer
      from public.review_assignments assignment
      where assignment.status in ('queued', 'leased', 'draft')
        and public.actor_is_ops(assignment.factory_id)
    ), 0),
    'openQueueDepth', (
      select count(*) from public.review_assignments assignment
      where assignment.status in ('queued', 'leased', 'draft')
        and public.actor_is_ops(assignment.factory_id)
    ),
    'chunksTotal', (
      select count(*) from public.video_chunks chunk
      where chunk.source_set_role = 'production'
        and public.actor_is_ops(chunk.factory_id)
    )
  ) into result;
  return result;
end;
$$;

revoke all on function public.worker_authorize_reviewer_session()
  from public, anon;
grant execute on function public.worker_authorize_reviewer_session()
  to authenticated;
revoke all on function public.ops_revoke_reviewer_invitation(uuid)
  from public, anon;
grant execute on function public.ops_revoke_reviewer_invitation(uuid)
  to authenticated;
