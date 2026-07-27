-- Authenticated worker-loop RPCs. Identity always comes from auth.uid().

create or replace function public.claim_worker_assignment(p_app_version text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  assignment_row public.review_assignments%rowtype;
  lease_token text;
  actions jsonb;
  result jsonb;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  select assignment.*
  into assignment_row
  from public.review_assignments assignment
  join public.factory_memberships membership
    on membership.factory_id = assignment.factory_id
   and membership.user_id = actor_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  join public.profiles profile
    on profile.id = actor_id
   and profile.status = 'active'
  where assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '10 minutes'
  order by assignment.updated_at desc
  limit 1
  for update of assignment;

  if assignment_row.id is null then
    select assignment.*
    into assignment_row
    from public.review_assignments assignment
    join public.video_chunks chunk
      on chunk.id = assignment.chunk_id
     and chunk.factory_id = assignment.factory_id
    join public.factory_memberships membership
      on membership.factory_id = assignment.factory_id
     and membership.user_id = actor_id
     and membership.role = 'reviewer'
     and membership.status = 'active'
    join public.profiles profile
      on profile.id = actor_id
     and profile.status = 'active'
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
      )
      order by action.created_at, action.id
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
      'startIso', chunk.source_start_at,
      'endIso', chunk.source_end_at,
      'sourceStartMs', chunk.source_start_ms,
      'sourceEndMs', chunk.source_end_ms,
      'sourceSha256', chunk.source_sha256,
      'renditionId', chunk.review_rendition_id,
      'mediaUrl', '/api/media/' || rendition_object.object_path,
      'posterUrl', null
    ),
    'actions', actions
  )
  into result
  from public.video_chunks chunk
  join public.stations station
    on station.id = chunk.station_id
   and station.factory_id = chunk.factory_id
  join public.media_renditions rendition
    on rendition.id = chunk.review_rendition_id
   and rendition.factory_id = chunk.factory_id
  join public.media_objects rendition_object
    on rendition_object.id = rendition.rendition_media_object_id
   and rendition_object.factory_id = chunk.factory_id
  where chunk.id = assignment_row.chunk_id;

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

create or replace function public.heartbeat_worker_assignment(
  p_assignment_id uuid,
  p_lease_token text
)
returns timestamptz
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  expires_at timestamptz;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  update public.review_assignments assignment
  set lease_expires_at = now() + interval '15 minutes',
      updated_at = now()
  where assignment.id = p_assignment_id
    and assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '10 minutes'
    and assignment.lease_token_hash =
      encode(extensions.digest(p_lease_token, 'sha256'), 'hex')
    and exists (
      select 1
      from public.factory_memberships membership
      join public.profiles profile on profile.id = membership.user_id
      where membership.factory_id = assignment.factory_id
        and membership.user_id = actor_id
        and membership.role = 'reviewer'
        and membership.status = 'active'
        and profile.status = 'active'
    )
  returning assignment.lease_expires_at into expires_at;

  if expires_at is null then
    raise exception 'assignment lease is unavailable' using errcode = '42501';
  end if;

  return expires_at;
end;
$$;

create or replace function public.append_worker_action(
  p_assignment_id uuid,
  p_lease_token text,
  p_client_action_id uuid,
  p_action_type text,
  p_source_time_ms bigint,
  p_undoes_client_action_id uuid,
  p_reason_code text,
  p_playback_rate numeric,
  p_app_version text
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  assignment_row public.review_assignments%rowtype;
  existing_row public.review_actions%rowtype;
  inserted_row public.review_actions%rowtype;
  target_action_id uuid;
  active_total integer;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  select assignment.*
  into assignment_row
  from public.review_assignments assignment
  join public.factory_memberships membership
    on membership.factory_id = assignment.factory_id
   and membership.user_id = actor_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  join public.profiles profile
    on profile.id = actor_id
   and profile.status = 'active'
  where assignment.id = p_assignment_id
    and assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now()
    and assignment.lease_token_hash =
      encode(extensions.digest(p_lease_token, 'sha256'), 'hex')
  for update of assignment;

  if assignment_row.id is null then
    raise exception 'assignment lease is unavailable' using errcode = '42501';
  end if;

  select *
  into existing_row
  from public.review_actions
  where assignment_id = p_assignment_id
    and client_action_id = p_client_action_id;

  if existing_row.id is not null then
    if existing_row.action_type <> p_action_type
       or existing_row.source_time_ms is distinct from p_source_time_ms
       or existing_row.reason_code is distinct from p_reason_code then
      raise exception 'client action id was reused with different content'
        using errcode = '23505';
    end if;
    inserted_row := existing_row;
  else
    if p_action_type = 'undo' then
      select id
      into target_action_id
      from public.review_actions
      where assignment_id = p_assignment_id
        and client_action_id = p_undoes_client_action_id
        and action_type = 'tally';

      if target_action_id is null then
        raise exception 'undo target is unavailable' using errcode = '23514';
      end if;
    end if;

    insert into public.review_actions (
      factory_id, assignment_id, reviewer_id, client_action_id, action_type,
      source_time_ms, undoes_action_id, reason_code, playback_rate, app_version
    ) values (
      assignment_row.factory_id, assignment_row.id, actor_id, p_client_action_id,
      p_action_type, p_source_time_ms, target_action_id, p_reason_code,
      p_playback_rate, p_app_version
    )
    returning * into inserted_row;
  end if;

  update public.review_assignments
  set status = 'draft',
      lease_expires_at = now() + interval '15 minutes',
      updated_at = now()
  where id = assignment_row.id;

  select count(*)::integer
  into active_total
  from public.review_actions tally
  where tally.assignment_id = assignment_row.id
    and tally.action_type = 'tally'
    and not exists (
      select 1
      from public.review_actions undo
      where undo.assignment_id = assignment_row.id
        and undo.action_type = 'undo'
        and undo.undoes_action_id = tally.id
    );

  return jsonb_build_object(
    'actionId', inserted_row.id,
    'clientActionId', inserted_row.client_action_id,
    'acceptedTotal', active_total,
    'savedAt', inserted_row.created_at
  );
end;
$$;

create or replace function public.submit_worker_assignment(
  p_assignment_id uuid,
  p_lease_token text,
  p_idempotency_key uuid,
  p_result_type text,
  p_problem_code text,
  p_app_version text
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  assignment_row public.review_assignments%rowtype;
  chunk_row public.video_chunks%rowtype;
  submission_row public.review_submissions%rowtype;
  active_total integer;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  select submission.*
  into submission_row
  from public.review_submissions submission
  where submission.assignment_id = p_assignment_id
    and submission.reviewer_id = actor_id;

  if submission_row.id is not null then
    return jsonb_build_object(
      'submissionId', submission_row.id,
      'totalCount', submission_row.total_count,
      'resultType', submission_row.result_type,
      'submittedAt', submission_row.submitted_at,
      'alreadySubmitted', true
    );
  end if;

  select assignment.*
  into assignment_row
  from public.review_assignments assignment
  join public.factory_memberships membership
    on membership.factory_id = assignment.factory_id
   and membership.user_id = actor_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  join public.profiles profile
    on profile.id = actor_id
   and profile.status = 'active'
  where assignment.id = p_assignment_id
    and assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '10 minutes'
    and assignment.lease_token_hash =
      encode(extensions.digest(p_lease_token, 'sha256'), 'hex')
  for update of assignment;

  if assignment_row.id is null then
    raise exception 'assignment is not submittable' using errcode = '42501';
  end if;

  select *
  into chunk_row
  from public.video_chunks
  where id = assignment_row.chunk_id;

  select count(*)::integer
  into active_total
  from public.review_actions tally
  where tally.assignment_id = assignment_row.id
    and tally.action_type = 'tally'
    and not exists (
      select 1
      from public.review_actions undo
      where undo.assignment_id = assignment_row.id
        and undo.action_type = 'undo'
        and undo.undoes_action_id = tally.id
    );

  insert into public.review_submissions (
    factory_id, assignment_id, chunk_id, reviewer_id, review_round,
    result_type, total_count, problem_code, source_sha256, rendition_id,
    app_version, idempotency_key
  ) values (
    assignment_row.factory_id, assignment_row.id, assignment_row.chunk_id,
    actor_id, assignment_row.review_round, p_result_type,
    case when p_result_type = 'counted' then active_total else null end,
    case when p_result_type = 'problem' then p_problem_code else null end,
    chunk_row.source_sha256, assignment_row.rendition_id, p_app_version,
    p_idempotency_key
  )
  returning * into submission_row;

  return jsonb_build_object(
    'submissionId', submission_row.id,
    'totalCount', submission_row.total_count,
    'resultType', submission_row.result_type,
    'submittedAt', submission_row.submitted_at,
    'alreadySubmitted', false
  );
end;
$$;

revoke all on function public.claim_worker_assignment(text) from public, anon;
revoke all on function public.heartbeat_worker_assignment(uuid, text) from public, anon;
revoke all on function public.append_worker_action(uuid, text, uuid, text, bigint, uuid, text, numeric, text) from public, anon;
revoke all on function public.submit_worker_assignment(uuid, text, uuid, text, text, text) from public, anon;

grant execute on function public.claim_worker_assignment(text) to authenticated;
grant execute on function public.heartbeat_worker_assignment(uuid, text) to authenticated;
grant execute on function public.append_worker_action(uuid, text, uuid, text, bigint, uuid, text, numeric, text) to authenticated;
grant execute on function public.submit_worker_assignment(uuid, text, uuid, text, text, text) to authenticated;
