-- Qualification is a server-scored gate, never an ops assertion. Also register
-- active devices before assignment and schedule ready chunks without an extra
-- hour of latency.

create or replace function public.ops_set_reviewer_state(
  p_user_id uuid,
  p_state text,
  p_reason text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  event_name text;
begin
  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = p_user_id
  for update;
  if lifecycle_row.user_id is null or not public.actor_is_ops(lifecycle_row.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  if p_state not in ('qualification', 'active', 'suspended', 'offboarded') then
    raise exception 'unsupported lifecycle transition' using errcode = '22023';
  end if;
  if p_state = 'active'
     and (lifecycle_row.mfa_verified_at is null
          or lifecycle_row.terms_accepted_at is null
          or lifecycle_row.practice_completed_at is null
          or lifecycle_row.qualified_at is null) then
    raise exception 'server-scored qualification is required' using errcode = '23514';
  end if;

  update public.reviewer_lifecycles
  set state = p_state,
      activated_at = case when p_state = 'active' then coalesce(activated_at, now()) else activated_at end,
      suspended_at = case when p_state = 'suspended' then now() else suspended_at end,
      offboarded_at = case when p_state = 'offboarded' then now() else offboarded_at end,
      state_reason = nullif(trim(p_reason), ''),
      updated_at = now()
  where user_id = p_user_id;

  update public.profiles
  set status = case when p_state = 'active' then 'active' else 'disabled' end
  where id = p_user_id;
  update public.factory_memberships
  set status = case when p_state = 'active' then 'active' else 'disabled' end,
      updated_at = now()
  where user_id = p_user_id and factory_id = lifecycle_row.factory_id;

  if p_state in ('suspended', 'offboarded') then
    update public.review_assignments
    set status = 'reassigned', updated_at = now()
    where reviewer_id = p_user_id and status in ('queued', 'leased', 'draft');
    update public.reviewer_device_registrations
    set status = 'revoked', revoked_at = now()
    where user_id = p_user_id and status = 'active';
  end if;

  event_name := case p_state
    when 'active' then 'activated'
    when 'suspended' then 'suspended'
    when 'offboarded' then 'offboarded'
    else 'qualification_failed'
  end;
  insert into public.reviewer_training_events (
    factory_id, user_id, event_type, actor_user_id, metadata
  ) values (
    lifecycle_row.factory_id, p_user_id, event_name, actor_id,
    jsonb_build_object('reason', p_reason)
  );

  return jsonb_build_object('userId', p_user_id, 'state', p_state);
end;
$$;

create or replace function public.service_record_reviewer_qualification(
  p_user_id uuid,
  p_chunk_id uuid,
  p_passed boolean,
  p_metrics jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  lifecycle_row public.reviewer_lifecycles%rowtype;
  chunk_row public.video_chunks%rowtype;
begin
  if jsonb_typeof(coalesce(p_metrics, '{}'::jsonb)) <> 'object' then
    raise exception 'qualification metrics must be an object' using errcode = '22023';
  end if;
  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = p_user_id
  for update;
  select * into chunk_row
  from public.video_chunks
  where id = p_chunk_id and source_set_role = 'qualification';
  if lifecycle_row.user_id is null
     or chunk_row.id is null
     or chunk_row.factory_id <> lifecycle_row.factory_id
     or not exists (
       select 1 from private.reference_answers answer
       where answer.chunk_id = chunk_row.id
         and answer.factory_id = chunk_row.factory_id
         and answer.answer_type = 'qualification'
         and answer.source_sha256 = chunk_row.source_sha256
     ) then
    raise exception 'approved qualification reference is required' using errcode = '23514';
  end if;

  update public.reviewer_lifecycles
  set state = case when p_passed then 'qualification' else 'training' end,
      qualified_at = case when p_passed then now() else null end,
      practice_completed_at = case when p_passed then practice_completed_at else null end,
      state_reason = case when p_passed then null else 'Qualification score did not pass' end,
      updated_at = now()
  where user_id = p_user_id;

  insert into public.reviewer_training_events (
    factory_id, user_id, event_type, training_version, metadata
  ) values (
    lifecycle_row.factory_id, p_user_id,
    case when p_passed then 'qualification_passed' else 'qualification_failed' end,
    'qualification-v1',
    coalesce(p_metrics, '{}'::jsonb) || jsonb_build_object('chunk_id', p_chunk_id)
  );

  return jsonb_build_object(
    'userId', p_user_id,
    'passed', p_passed,
    'qualifiedAt', case when p_passed then now() else null end
  );
end;
$$;

create or replace function public.worker_register_active_device(
  p_device_id_hash text
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
begin
  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = actor_id and state = 'active';
  if lifecycle_row.user_id is null
     or (not lifecycle_row.is_test_account and coalesce(auth.jwt() ->> 'aal', '') <> 'aal2') then
    raise exception 'active MFA reviewer required' using errcode = '42501';
  end if;
  if p_device_id_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid device identifier' using errcode = '22023';
  end if;
  insert into public.reviewer_device_registrations (user_id, device_id_hash)
  values (actor_id, p_device_id_hash)
  on conflict (user_id, device_id_hash) do update
    set status = 'active', last_seen_at = now(), revoked_at = null;
  return jsonb_build_object('registered', true);
end;
$$;

create or replace function public.worker_lifecycle_state()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  result jsonb;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  update public.reviewer_invitations
  set status = 'accepted', accepted_at = coalesce(accepted_at, now())
  where user_id = actor_id and status in ('created', 'sent');

  select jsonb_build_object(
    'userId', lifecycle.user_id,
    'displayName', profile.display_name,
    'email', lifecycle.email,
    'locale', profile.locale,
    'state', lifecycle.state,
    'termsVersion', lifecycle.terms_version,
    'termsAcceptedAt', lifecycle.terms_accepted_at,
    'mfaVerifiedAt', lifecycle.mfa_verified_at,
    'currentAal', coalesce(auth.jwt() ->> 'aal', 'aal1'),
    'walkthroughCompletedAt', lifecycle.walkthrough_completed_at,
    'practiceCompletedAt', lifecycle.practice_completed_at,
    'qualifiedAt', lifecycle.qualified_at,
    'activatedAt', lifecycle.activated_at,
    'isTestAccount', lifecycle.is_test_account,
    'supportConfigured', current_setting('app.settings.reviewer_support_configured', true) = 'true'
  )
  into result
  from public.reviewer_lifecycles lifecycle
  join public.profiles profile on profile.id = lifecycle.user_id
  where lifecycle.user_id = actor_id;
  return coalesce(result, jsonb_build_object('state', 'unregistered'));
end;
$$;

create or replace function public.service_schedule_ready_review_chunks()
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  chunk_row public.video_chunks%rowtype;
  reviewer_id uuid;
  eligible_count integer;
  scheduled_chunks integer := 0;
  slot integer;
begin
  for chunk_row in
    select chunk.*
    from public.video_chunks chunk
    where chunk.state = 'ready'
      and chunk.assignment_eligible
      and chunk.source_set_role = 'production'
      and chunk.source_end_at <= now()
      and not exists (
        select 1 from public.review_assignments assignment where assignment.chunk_id = chunk.id
      )
    order by chunk.source_end_at
    limit 50
    for update skip locked
  loop
    select count(*)::integer into eligible_count
    from public.reviewer_lifecycles lifecycle
    join public.profiles profile
      on profile.id = lifecycle.user_id and profile.status = 'active'
    join public.factory_memberships membership
      on membership.user_id = lifecycle.user_id
     and membership.factory_id = lifecycle.factory_id
     and membership.role = 'reviewer'
     and membership.status = 'active'
    where lifecycle.factory_id = chunk_row.factory_id
      and lifecycle.state = 'active'
      and (
        lifecycle.is_test_account
        or exists (
          select 1 from public.reviewer_device_registrations device
          where device.user_id = lifecycle.user_id and device.status = 'active'
        )
      );
    continue when eligible_count < 3;
    for slot in 1..3 loop
      reviewer_id := public.service_pick_reviewer(chunk_row.factory_id, chunk_row.id, 1);
      if reviewer_id is null then
        raise exception 'ready scheduler could not select three reviewers' using errcode = '55000';
      end if;
      insert into public.review_assignments (
        factory_id, chunk_id, rendition_id, reviewer_id, review_round, status
      ) values (
        chunk_row.factory_id, chunk_row.id, chunk_row.review_rendition_id,
        reviewer_id, 1, 'queued'
      );
    end loop;
    update public.video_chunks set state = 'assigned', updated_at = now()
    where id = chunk_row.id;
    scheduled_chunks := scheduled_chunks + 1;
  end loop;
  return scheduled_chunks;
end;
$$;

revoke all on function public.service_record_reviewer_qualification(
  uuid, uuid, boolean, jsonb
) from public, anon, authenticated;
grant execute on function public.service_record_reviewer_qualification(
  uuid, uuid, boolean, jsonb
) to service_role;
revoke all on function public.worker_register_active_device(text)
  from public, anon;
grant execute on function public.worker_register_active_device(text)
  to authenticated;
revoke all on function public.service_schedule_ready_review_chunks()
  from public, anon, authenticated;

do $$
begin
  if not exists (
    select 1 from cron.job where jobname = 'factoryvision-ready-chunk-scheduler'
  ) then
    perform cron.schedule(
      'factoryvision-ready-chunk-scheduler',
      '* * * * *',
      'select public.service_schedule_ready_review_chunks();'
    );
  end if;
end;
$$;
