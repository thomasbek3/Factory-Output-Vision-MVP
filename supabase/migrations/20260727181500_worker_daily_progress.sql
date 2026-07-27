-- Reviewer-only work summary for the employee landing screen. The function
-- exposes personal state only and never reveals peer, consensus, or AI data.

create or replace function public.worker_daily_progress()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  ready_count integer;
  in_progress_count integer;
  completed_today_count integer;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  perform 1
  from public.reviewer_lifecycles lifecycle
  join public.profiles profile
    on profile.id = lifecycle.user_id
   and profile.status = 'active'
  where lifecycle.user_id = actor_id
    and lifecycle.state = 'active'
    and (
      lifecycle.is_test_account
      or coalesce(auth.jwt() ->> 'aal', '') = 'aal2'
    );
  if not found then
    raise exception 'reviewer onboarding or MFA is incomplete'
      using errcode = '42501';
  end if;

  select count(*)
  into ready_count
  from public.review_assignments assignment
  join public.factory_memberships membership
    on membership.factory_id = assignment.factory_id
   and membership.user_id = actor_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  join public.video_chunks chunk
    on chunk.id = assignment.chunk_id
   and chunk.factory_id = assignment.factory_id
  where assignment.reviewer_id = actor_id
    and assignment.status = 'queued'
    and chunk.assignment_eligible
    and chunk.state in ('ready', 'assigned')
    and chunk.source_set_role = 'production';

  select count(*)
  into in_progress_count
  from public.review_assignments assignment
  where assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '5 minutes';

  select count(*)
  into completed_today_count
  from public.review_submissions submission
  join public.factories factory on factory.id = submission.factory_id
  where submission.reviewer_id = actor_id
    and (submission.submitted_at at time zone factory.timezone)::date =
        (now() at time zone factory.timezone)::date;

  return jsonb_build_object(
    'ready', ready_count,
    'inProgress', in_progress_count,
    'completedToday', completed_today_count,
    'observedAt', now()
  );
end;
$$;

revoke all on function public.worker_daily_progress() from public, anon;
grant execute on function public.worker_daily_progress() to authenticated;
