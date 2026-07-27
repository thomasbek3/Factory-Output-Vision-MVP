-- Production reviewer gates and durable one-minute maintenance.

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

  perform 1
  from public.reviewer_lifecycles lifecycle
  where lifecycle.user_id = actor_id
    and lifecycle.state = 'active'
    and (
      lifecycle.is_test_account
      or coalesce(auth.jwt() ->> 'aal', '') = 'aal2'
    );
  if not found then
    raise exception 'reviewer onboarding or MFA is incomplete' using errcode = '42501';
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
    join public.video_chunks chunk
      on chunk.id = assignment.chunk_id and chunk.factory_id = assignment.factory_id
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
    on rendition.id = chunk.review_rendition_id and rendition.factory_id = chunk.factory_id
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

create or replace function public.authorize_worker_media(
  p_assignment_id uuid,
  p_lease_token text
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  result jsonb;
begin
  select jsonb_build_object(
    'mediaBucket', object.bucket_id,
    'mediaPath', object.object_path
  ) into result
  from public.review_assignments assignment
  join public.reviewer_lifecycles lifecycle
    on lifecycle.user_id = assignment.reviewer_id and lifecycle.state = 'active'
  join public.media_renditions rendition
    on rendition.id = assignment.rendition_id and rendition.factory_id = assignment.factory_id
  join public.media_objects object
    on object.id = rendition.rendition_media_object_id and object.factory_id = assignment.factory_id
  where assignment.id = p_assignment_id
    and assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '5 minutes'
    and assignment.lease_token_hash =
      encode(extensions.digest(p_lease_token, 'sha256'), 'hex');
  if result is null then
    raise exception 'media authorization unavailable' using errcode = '42501';
  end if;
  return result;
end;
$$;

create or replace function public.submit_worker_assignment_v2(
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
  lifecycle_row public.reviewer_lifecycles%rowtype;
  coverage_row public.review_coverage%rowtype;
  active_total integer;
  covered_ms bigint;
  usable_ms bigint;
  minimum_elapsed interval;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  select submission.* into submission_row
  from public.review_submissions submission
  where submission.assignment_id = p_assignment_id and submission.reviewer_id = actor_id;
  if submission_row.id is not null then
    return jsonb_build_object(
      'submissionId', submission_row.id,
      'totalCount', submission_row.total_count,
      'resultType', submission_row.result_type,
      'submittedAt', submission_row.submitted_at,
      'alreadySubmitted', true
    );
  end if;

  select assignment.* into assignment_row
  from public.review_assignments assignment
  join public.factory_memberships membership
    on membership.factory_id = assignment.factory_id
   and membership.user_id = actor_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  join public.profiles profile on profile.id = actor_id and profile.status = 'active'
  where assignment.id = p_assignment_id
    and assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '5 minutes'
    and assignment.lease_token_hash =
      encode(extensions.digest(p_lease_token, 'sha256'), 'hex')
  for update of assignment;
  if assignment_row.id is null then
    raise exception 'assignment is not submittable' using errcode = '42501';
  end if;

  select * into lifecycle_row from public.reviewer_lifecycles where user_id = actor_id;
  if lifecycle_row.state <> 'active'
     or (not lifecycle_row.is_test_account and coalesce(auth.jwt() ->> 'aal', '') <> 'aal2') then
    raise exception 'active reviewer with MFA required' using errcode = '42501';
  end if;
  select * into chunk_row from public.video_chunks where id = assignment_row.chunk_id;

  if p_result_type = 'counted' and not lifecycle_row.is_test_account then
    select * into coverage_row from public.review_coverage where assignment_id = assignment_row.id;
    if coverage_row.assignment_id is null then
      raise exception 'video coverage has not been saved' using errcode = '23514';
    end if;
    select coalesce(sum(range_row.end_ms - range_row.start_ms), 0)
    into covered_ms
    from jsonb_to_recordset(coverage_row.ranges) as range_row(start_ms bigint, end_ms bigint);
    usable_ms := chunk_row.source_end_ms - chunk_row.source_start_ms;
    if covered_ms * 100 < usable_ms * 98 then
      raise exception 'at least 98 percent of the video must be reviewed' using errcode = '23514';
    end if;
    minimum_elapsed := make_interval(secs => greatest(0, usable_ms / 5000.0 - 5));
    if assignment_row.leased_at is null or now() - assignment_row.leased_at < minimum_elapsed then
      raise exception 'review completed faster than the enabled playback speed permits' using errcode = '23514';
    end if;
  end if;

  select count(*)::integer into active_total
  from public.review_actions tally
  where tally.assignment_id = assignment_row.id
    and tally.action_type = 'tally'
    and not exists (
      select 1 from public.review_actions undo
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
  ) returning * into submission_row;

  return jsonb_build_object(
    'submissionId', submission_row.id,
    'totalCount', submission_row.total_count,
    'resultType', submission_row.result_type,
    'submittedAt', submission_row.submitted_at,
    'alreadySubmitted', false
  );
end;
$$;

create or replace function public.service_pick_reviewer(
  p_factory_id uuid,
  p_chunk_id uuid,
  p_review_round integer
)
returns uuid
language sql
security definer
set search_path = ''
as $$
  select lifecycle.user_id
  from public.reviewer_lifecycles lifecycle
  join public.profiles profile
    on profile.id = lifecycle.user_id and profile.status = 'active'
  join public.factory_memberships membership
    on membership.user_id = lifecycle.user_id
   and membership.factory_id = lifecycle.factory_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  where lifecycle.factory_id = p_factory_id
    and lifecycle.state = 'active'
    and not exists (
      select 1 from public.review_assignments prior
      where prior.chunk_id = p_chunk_id
        and prior.review_round = p_review_round
        and prior.reviewer_id = lifecycle.user_id
    )
    and (
      lifecycle.is_test_account
      or exists (
        select 1 from public.reviewer_device_registrations device
        where device.user_id = lifecycle.user_id and device.status = 'active'
      )
    )
    and not exists (
      select 1
      from public.reviewer_device_registrations candidate_device
      join public.reviewer_device_registrations assigned_device
        on assigned_device.device_id_hash = candidate_device.device_id_hash
       and assigned_device.status = 'active'
      join public.review_assignments assigned
        on assigned.reviewer_id = assigned_device.user_id
       and assigned.chunk_id = p_chunk_id
       and assigned.review_round = p_review_round
       and assigned.status not in ('expired', 'reassigned')
      where candidate_device.user_id = lifecycle.user_id
        and candidate_device.status = 'active'
    )
  order by (
    select count(*) from public.review_assignments active_work
    where active_work.reviewer_id = lifecycle.user_id
      and active_work.status in ('queued', 'leased', 'draft')
  ), lifecycle.activated_at, lifecycle.user_id
  limit 1;
$$;

create or replace function public.service_resolve_ready_rounds()
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  target record;
  majority_total integer;
  majority_support integer;
  run_id uuid;
  event_id uuid;
  finalization_id uuid;
  event_ordinal integer;
  event_time bigint;
  event_min bigint;
  event_max bigint;
  event_support integer;
  aligned boolean;
  resolved_count integer := 0;
begin
  for target in
    select submission.factory_id, submission.chunk_id, submission.review_round
    from public.review_submissions submission
    left join public.consensus_runs run
      on run.chunk_id = submission.chunk_id and run.review_round = submission.review_round
    where run.id is null
    group by submission.factory_id, submission.chunk_id, submission.review_round
    having count(*) = 3
    order by min(submission.submitted_at)
  loop
    majority_total := null;
    majority_support := null;
    select counted.total_count, count(*)::integer
    into majority_total, majority_support
    from public.review_submissions counted
    where counted.chunk_id = target.chunk_id
      and counted.review_round = target.review_round
      and counted.result_type = 'counted'
    group by counted.total_count
    having count(*) >= 2
    order by count(*) desc, counted.total_count
    limit 1;

    aligned := majority_total is not null;
    if aligned and majority_total > 0 then
      for event_ordinal in 1..majority_total loop
        select round(avg(active.source_time_ms))::bigint,
               min(active.source_time_ms),
               max(active.source_time_ms),
               count(*)::integer
        into event_time, event_min, event_max, event_support
        from (
          select action.source_time_ms,
                 row_number() over (
                   partition by submission.id order by action.source_time_ms, action.id
                 ) as ordinal
          from public.review_submissions submission
          join public.review_actions action on action.assignment_id = submission.assignment_id
          where submission.chunk_id = target.chunk_id
            and submission.review_round = target.review_round
            and submission.result_type = 'counted'
            and submission.total_count = majority_total
            and action.action_type = 'tally'
            and not exists (
              select 1 from public.review_actions undo
              where undo.assignment_id = action.assignment_id
                and undo.action_type = 'undo'
                and undo.undoes_action_id = action.id
            )
        ) active
        where active.ordinal = event_ordinal;
        if event_support <> majority_support or event_max - event_min > 1500 then
          aligned := false;
          exit;
        end if;
      end loop;
    end if;

    if not aligned then
      insert into public.consensus_runs (
        factory_id, chunk_id, review_round, resolver_version,
        resolver_parameters, status
      ) values (
        target.factory_id, target.chunk_id, target.review_round,
        'ordinal-majority-v1', jsonb_build_object('alignment_tolerance_ms', 1500),
        'no_majority'
      );
      insert into public.internal_review_cases (
        factory_id, chunk_id, review_round, sequence, event_type, reason_code
      ) values (
        target.factory_id, target.chunk_id, target.review_round, 1, 'opened',
        case when majority_total is null then 'count_disagreement' else 'timestamp_ambiguity' end
      );
      update public.video_chunks set state = 'resolving', updated_at = now()
      where id = target.chunk_id;
      continue;
    end if;

    run_id := gen_random_uuid();
    insert into public.consensus_runs (
      id, factory_id, chunk_id, review_round, resolver_version,
      resolver_parameters, status, resolved_total, support_count
    ) values (
      run_id, target.factory_id, target.chunk_id, target.review_round,
      'ordinal-majority-v1', jsonb_build_object('alignment_tolerance_ms', 1500),
      'resolved', majority_total, majority_support
    );

    if majority_total > 0 then
      for event_ordinal in 1..majority_total loop
        select round(avg(active.source_time_ms))::bigint
        into event_time
        from (
          select action.source_time_ms,
                 row_number() over (
                   partition by submission.id order by action.source_time_ms, action.id
                 ) as ordinal
          from public.review_submissions submission
          join public.review_actions action on action.assignment_id = submission.assignment_id
          where submission.chunk_id = target.chunk_id
            and submission.review_round = target.review_round
            and submission.result_type = 'counted'
            and submission.total_count = majority_total
            and action.action_type = 'tally'
            and not exists (
              select 1 from public.review_actions undo
              where undo.assignment_id = action.assignment_id
                and undo.action_type = 'undo'
                and undo.undoes_action_id = action.id
            )
        ) active
        where active.ordinal = event_ordinal;

        insert into public.consensus_events (
          factory_id, consensus_run_id, chunk_id, review_round,
          source_time_ms, support_count, provenance
        ) values (
          target.factory_id, run_id, target.chunk_id, target.review_round,
          event_time, majority_support,
          case when majority_support = 3 then 'unanimous' else 'majority' end
        ) returning id into event_id;

        insert into public.consensus_event_sources (
          factory_id, consensus_event_id, submission_id, review_action_id,
          assignment_id, chunk_id, review_round
        )
        select target.factory_id, event_id, ranked.submission_id, ranked.action_id,
               ranked.assignment_id, target.chunk_id, target.review_round
        from (
          select submission.id as submission_id,
                 submission.assignment_id,
                 action.id as action_id,
                 row_number() over (
                   partition by submission.id order by action.source_time_ms, action.id
                 ) as ordinal
          from public.review_submissions submission
          join public.review_actions action on action.assignment_id = submission.assignment_id
          where submission.chunk_id = target.chunk_id
            and submission.review_round = target.review_round
            and submission.result_type = 'counted'
            and submission.total_count = majority_total
            and action.action_type = 'tally'
            and not exists (
              select 1 from public.review_actions undo
              where undo.assignment_id = action.assignment_id
                and undo.action_type = 'undo'
                and undo.undoes_action_id = action.id
            )
        ) ranked
        where ranked.ordinal = event_ordinal;
      end loop;
    end if;

    insert into public.human_finalizations (
      factory_id, chunk_id, review_round, consensus_run_id,
      audit_selected, human_final_at
    ) values (
      target.factory_id, target.chunk_id, target.review_round, run_id, false, now()
    ) returning id into finalization_id;

    insert into public.resolved_human_count_events (
      factory_id, chunk_id, finalization_id, consensus_event_id, source_time_ms
    )
    select target.factory_id, target.chunk_id, finalization_id, event.id, event.source_time_ms
    from public.consensus_events event
    where event.consensus_run_id = run_id;

    update public.video_chunks set state = 'resolved', updated_at = now()
    where id = target.chunk_id;
    resolved_count := resolved_count + 1;
  end loop;
  return resolved_count;
end;
$$;

create or replace function public.service_maintain_review_queue()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  chunk_row public.video_chunks%rowtype;
  round_row record;
  reviewer_id uuid;
  scheduled_count integer := 0;
  expired_count integer := 0;
  replacement_count integer := 0;
  slot integer;
  resolved_count integer;
begin
  update public.review_assignments
  set status = 'expired', updated_at = now()
  where status in ('leased', 'draft')
    and lease_expires_at < now() - interval '5 minutes';
  get diagnostics expired_count = row_count;

  for chunk_row in
    select chunk.*
    from public.video_chunks chunk
    where chunk.state = 'ready'
      and chunk.assignment_eligible
      and chunk.source_set_role = 'production'
      and chunk.source_end_at <= now() - interval '60 minutes'
      and not exists (
        select 1 from public.review_assignments assignment where assignment.chunk_id = chunk.id
      )
    order by chunk.source_end_at
    limit 50
    for update skip locked
  loop
    for slot in 1..3 loop
      reviewer_id := public.service_pick_reviewer(chunk_row.factory_id, chunk_row.id, 1);
      exit when reviewer_id is null;
      insert into public.review_assignments (
        factory_id, chunk_id, rendition_id, reviewer_id, review_round, status
      ) values (
        chunk_row.factory_id, chunk_row.id, chunk_row.review_rendition_id,
        reviewer_id, 1, 'queued'
      );
      scheduled_count := scheduled_count + 1;
    end loop;
    if (select count(*) from public.review_assignments where chunk_id = chunk_row.id and review_round = 1) = 3 then
      update public.video_chunks set state = 'assigned', updated_at = now() where id = chunk_row.id;
    end if;
  end loop;

  for round_row in
    select assignment.factory_id, assignment.chunk_id, assignment.review_round,
           count(*) filter (where assignment.status not in ('expired', 'reassigned')) as active_count
    from public.review_assignments assignment
    left join public.consensus_runs run
      on run.chunk_id = assignment.chunk_id and run.review_round = assignment.review_round
    where run.id is null
    group by assignment.factory_id, assignment.chunk_id, assignment.review_round
    having count(*) filter (where assignment.status not in ('expired', 'reassigned')) < 3
    order by min(assignment.assigned_at)
  loop
    for slot in (round_row.active_count::integer + 1)..3 loop
      reviewer_id := public.service_pick_reviewer(
        round_row.factory_id, round_row.chunk_id, round_row.review_round
      );
      exit when reviewer_id is null;
      insert into public.review_assignments (
        factory_id, chunk_id, rendition_id, reviewer_id, review_round, status
      )
      select round_row.factory_id, round_row.chunk_id, chunk.review_rendition_id,
             reviewer_id, round_row.review_round, 'queued'
      from public.video_chunks chunk where chunk.id = round_row.chunk_id;
      replacement_count := replacement_count + 1;
    end loop;
  end loop;

  resolved_count := public.service_resolve_ready_rounds();
  return jsonb_build_object(
    'scheduled', scheduled_count,
    'expired', expired_count,
    'replacements', replacement_count,
    'resolved', resolved_count,
    'ranAt', now()
  );
end;
$$;

revoke execute on function public.submit_worker_assignment(
  uuid, text, uuid, text, text, text
) from authenticated;
revoke all on function public.authorize_worker_media(uuid, text) from public, anon;
revoke all on function public.submit_worker_assignment_v2(
  uuid, text, uuid, text, text, text
) from public, anon;
revoke all on function public.service_pick_reviewer(uuid, uuid, integer)
  from public, anon, authenticated;
revoke all on function public.service_resolve_ready_rounds()
  from public, anon, authenticated;
revoke all on function public.service_maintain_review_queue()
  from public, anon, authenticated;

grant execute on function public.authorize_worker_media(uuid, text) to authenticated;
grant execute on function public.submit_worker_assignment_v2(
  uuid, text, uuid, text, text, text
) to authenticated;

do $$
begin
  if not exists (
    select 1 from cron.job where jobname = 'factoryvision-review-maintenance'
  ) then
    perform cron.schedule(
      'factoryvision-review-maintenance',
      '* * * * *',
      'select public.service_maintain_review_queue();'
    );
  end if;
end;
$$;
