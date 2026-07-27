-- Serve explicit rendition/source boundaries to the reviewer and ensure test
-- accounts can never lease customer-factory footage.

alter table public.factories
  add column if not exists is_test boolean not null default false;

update public.factories
set is_test = true
where lower(name) = 'factory vision qa';

update public.review_assignments assignment
set status = 'expired',
    lease_token_hash = null,
    lease_expires_at = null,
    updated_at = now()
from public.reviewer_lifecycles lifecycle,
     public.factories factory
where assignment.reviewer_id = lifecycle.user_id
  and assignment.factory_id = factory.id
  and lifecycle.is_test_account
  and not factory.is_test
  and assignment.status in ('queued', 'leased', 'draft');

create or replace function public.claim_worker_assignment(p_app_version text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  assignment_row public.review_assignments%rowtype;
  lease_token text;
  actions jsonb;
  result jsonb;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  select * into lifecycle_row
  from public.reviewer_lifecycles lifecycle
  where lifecycle.user_id = actor_id
    and lifecycle.state = 'active'
    and (
      lifecycle.is_test_account
      or coalesce(auth.jwt() ->> 'aal', '') = 'aal2'
    );
  if lifecycle_row.user_id is null then
    raise exception 'reviewer onboarding or MFA is incomplete'
      using errcode = '42501';
  end if;

  select assignment.*
  into assignment_row
  from public.review_assignments assignment
  join public.factories factory
    on factory.id = assignment.factory_id
   and factory.status = 'active'
   and (not lifecycle_row.is_test_account or factory.is_test)
  join public.factory_memberships membership
    on membership.factory_id = assignment.factory_id
   and membership.user_id = actor_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  join public.profiles profile
    on profile.id = actor_id and profile.status = 'active'
  where assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '5 minutes'
  order by assignment.updated_at desc
  limit 1
  for update of assignment;

  if assignment_row.id is null then
    select assignment.*
    into assignment_row
    from public.review_assignments assignment
    join public.factories factory
      on factory.id = assignment.factory_id
     and factory.status = 'active'
     and (not lifecycle_row.is_test_account or factory.is_test)
    join public.video_chunks chunk
      on chunk.id = assignment.chunk_id
     and chunk.factory_id = assignment.factory_id
    join public.factory_memberships membership
      on membership.factory_id = assignment.factory_id
     and membership.user_id = actor_id
     and membership.role = 'reviewer'
     and membership.status = 'active'
    join public.profiles profile
      on profile.id = actor_id and profile.status = 'active'
    where assignment.reviewer_id = actor_id
      and assignment.status = 'queued'
      and chunk.assignment_eligible
      and chunk.state in ('ready', 'assigned')
      and chunk.source_set_role = 'production'
    order by chunk.source_start_at, assignment.assigned_at
    limit 1
    for update of assignment skip locked;
  end if;

  if assignment_row.id is null then
    return jsonb_build_object('assignment', null);
  end if;

  lease_token := encode(extensions.gen_random_bytes(32), 'hex');
  update public.review_assignments
  set status = case when assignment_row.status = 'draft' then 'draft' else 'leased' end,
      lease_token_hash = encode(extensions.digest(lease_token, 'sha256'), 'hex'),
      lease_expires_at = now() + interval '15 minutes',
      leased_at = coalesce(leased_at, now()),
      app_version = p_app_version,
      updated_at = now()
  where id = assignment_row.id
  returning * into assignment_row;

  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', action.id,
        'clientActionId', action.client_action_id,
        'type', action.action_type,
        'sourceTimeMs', action.source_time_ms,
        'undoesActionId', action.undoes_action_id,
        'reasonCode', action.reason_code,
        'playbackRate', action.playback_rate,
        'createdAt', action.created_at
      ) order by action.created_at, action.id
    ),
    '[]'::jsonb
  )
  into actions
  from public.review_actions action
  where action.assignment_id = assignment_row.id;

  select jsonb_build_object(
    'id', assignment_row.id,
    'leaseToken', lease_token,
    'leaseExpiresAt', assignment_row.lease_expires_at,
    'chunk', jsonb_build_object(
      'id', chunk.id,
      'stationId', station.id,
      'stationName', station.alias,
      'factoryTimezone', factory.timezone,
      'startIso', chunk.source_start_at,
      'endIso', chunk.source_end_at,
      'sourceStartMs', chunk.source_start_ms,
      'sourceEndMs', chunk.source_end_ms,
      'renditionSourceStartMs', rendition.padded_start_ms,
      'renditionSourceEndMs', rendition.padded_end_ms,
      'sourceSha256', chunk.source_sha256,
      'renditionId', chunk.review_rendition_id,
      'mediaBucket', rendition_object.bucket_id,
      'mediaPath', rendition_object.object_path,
      'posterUrl', null
    ),
    'actions', actions,
    'coverage', (
      select jsonb_build_object(
        'pageEpoch', coverage.page_epoch,
        'ranges', coverage.ranges,
        'clientActiveMs', coverage.client_active_ms
      )
      from public.review_coverage coverage
      where coverage.assignment_id = assignment_row.id
    )
  )
  into result
  from public.video_chunks chunk
  join public.factories factory on factory.id = chunk.factory_id
  join public.stations station
    on station.id = chunk.station_id and station.factory_id = chunk.factory_id
  join public.media_renditions rendition
    on rendition.id = chunk.review_rendition_id
   and rendition.factory_id = chunk.factory_id
   and rendition.mapping_status = 'verified'
  join public.media_objects rendition_object
    on rendition_object.id = rendition.rendition_media_object_id
   and rendition_object.factory_id = chunk.factory_id
  where chunk.id = assignment_row.chunk_id;

  if result is null then
    raise exception 'verified rendition mapping is unavailable'
      using errcode = '42501';
  end if;

  insert into public.audit_log (
    factory_id, actor_user_id, actor_type, action, target_type, target_id,
    correlation_id, metadata
  ) values (
    assignment_row.factory_id, actor_id, 'user', 'worker.assignment.claimed',
    'review_assignment', assignment_row.id, gen_random_uuid(),
    jsonb_build_object('app_version', p_app_version)
  );

  return jsonb_build_object('assignment', result);
end;
$$;

create or replace function public.worker_daily_progress()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  ready_count integer;
  in_progress_count integer;
  completed_today_count integer;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  select * into lifecycle_row
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
  if lifecycle_row.user_id is null then
    raise exception 'reviewer onboarding or MFA is incomplete'
      using errcode = '42501';
  end if;

  select count(*)
  into ready_count
  from public.review_assignments assignment
  join public.factories factory
    on factory.id = assignment.factory_id
   and factory.status = 'active'
   and (not lifecycle_row.is_test_account or factory.is_test)
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
  join public.factories factory
    on factory.id = assignment.factory_id
   and factory.status = 'active'
   and (not lifecycle_row.is_test_account or factory.is_test)
  join public.factory_memberships membership
    on membership.factory_id = assignment.factory_id
   and membership.user_id = actor_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  where assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '5 minutes';

  select count(*)
  into completed_today_count
  from public.review_submissions submission
  join public.factories factory
    on factory.id = submission.factory_id
   and (not lifecycle_row.is_test_account or factory.is_test)
  join public.factory_memberships membership
    on membership.factory_id = submission.factory_id
   and membership.user_id = actor_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
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

create or replace function public.worker_claim_reviewer_qualification()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle public.reviewer_lifecycles%rowtype;
  result jsonb;
begin
  select * into lifecycle
  from public.reviewer_lifecycles
  where user_id = actor_id;
  if lifecycle.user_id is null
     or lifecycle.state <> 'qualification'
     or lifecycle.practice_completed_at is null
     or lifecycle.mfa_verified_at is null
     or (
       not lifecycle.is_test_account
       and coalesce(auth.jwt() ->> 'aal', '') <> 'aal2'
     ) then
    raise exception 'qualification access is unavailable' using errcode = '42501';
  end if;

  select jsonb_build_object(
    'qualification', jsonb_build_object(
      'chunkId', chunk.id,
      'stationName', station.alias,
      'sourceStartMs', chunk.source_start_ms,
      'sourceEndMs', chunk.source_end_ms,
      'renditionSourceStartMs', rendition.padded_start_ms,
      'renditionSourceEndMs', rendition.padded_end_ms,
      'mediaBucket', media.bucket_id,
      'mediaPath', media.object_path
    ),
    'attempts', (
      select count(*) from public.reviewer_qualification_attempts attempt
      where attempt.reviewer_id = actor_id
        and attempt.submitted_at > now() - interval '24 hours'
    )
  ) into result
  from public.video_chunks chunk
  join public.factories factory
    on factory.id = chunk.factory_id
   and (not lifecycle.is_test_account or factory.is_test)
  join public.stations station
    on station.id = chunk.station_id and station.factory_id = chunk.factory_id
  join public.media_renditions rendition
    on rendition.id = chunk.review_rendition_id
   and rendition.factory_id = chunk.factory_id
  join public.media_objects media
    on media.id = rendition.rendition_media_object_id
   and media.factory_id = chunk.factory_id
  where chunk.factory_id = lifecycle.factory_id
    and chunk.source_set_role = 'qualification'
    and not chunk.assignment_eligible
    and chunk.state not in ('quarantined', 'deleted')
    and media.status = 'verified'
    and rendition.mapping_status = 'verified'
    and exists (
      select 1 from private.reference_answers answer
      where answer.chunk_id = chunk.id
        and answer.factory_id = chunk.factory_id
        and answer.answer_type = 'qualification'
        and answer.source_sha256 = chunk.source_sha256
    )
  order by chunk.created_at desc
  limit 1;

  return coalesce(
    result,
    jsonb_build_object('qualification', null, 'reason', 'not_configured')
  );
end;
$$;
