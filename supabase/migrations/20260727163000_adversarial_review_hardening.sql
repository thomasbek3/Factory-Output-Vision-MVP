-- Close adversarial-review gaps in invitation consumption, worker support,
-- qualification, ops metrics, and work-session accounting.

alter table public.reviewer_invitations
  add column invitation_token_hash text
    check (
      invitation_token_hash is null
      or invitation_token_hash ~ '^[0-9a-f]{64}$'
    );

create unique index reviewer_invitations_token_hash_idx
  on public.reviewer_invitations (invitation_token_hash)
  where invitation_token_hash is not null;

create table public.reviewer_qualification_attempts (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  reviewer_id uuid not null references public.profiles(id) on delete restrict,
  chunk_id uuid not null,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  total_count integer not null check (total_count >= 0),
  event_times_ms jsonb not null check (jsonb_typeof(event_times_ms) = 'array'),
  passed boolean not null,
  score_metrics jsonb not null check (jsonb_typeof(score_metrics) = 'object'),
  submitted_at timestamptz not null default now(),
  foreign key (chunk_id, factory_id)
    references public.video_chunks(id, factory_id) on delete restrict,
  unique (reviewer_id, chunk_id, submitted_at)
);

alter table public.reviewer_qualification_attempts enable row level security;
alter table public.reviewer_qualification_attempts force row level security;
revoke all on public.reviewer_qualification_attempts
  from public, anon, authenticated;

drop function if exists public.service_register_reviewer_invitation(
  uuid, uuid, text, text, text, text, text, text, timestamptz, text, text
);

create or replace function public.service_register_reviewer_invitation(
  p_user_id uuid,
  p_factory_id uuid,
  p_email text,
  p_display_name text,
  p_locale text,
  p_country_code text,
  p_employment_classification text,
  p_pay_basis text,
  p_expires_at timestamptz,
  p_delivery_provider text,
  p_delivery_id text,
  p_invitation_token_hash text
)
returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  invitation_id uuid;
  actor_id uuid := auth.uid();
begin
  if actor_id is null or not public.actor_is_ops(p_factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  if p_locale not in ('es-419', 'en') then
    raise exception 'unsupported locale' using errcode = '22023';
  end if;
  if p_expires_at <= now() or p_expires_at > now() + interval '24 hours' then
    raise exception 'invitation expiry is invalid' using errcode = '22023';
  end if;
  if p_invitation_token_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invitation token hash is invalid' using errcode = '22023';
  end if;

  insert into public.profiles (id, display_name, locale, status)
  values (p_user_id, trim(p_display_name), p_locale, 'invited')
  on conflict (id) do update
    set display_name = excluded.display_name,
        locale = excluded.locale,
        status = case
          when public.profiles.status = 'active' then public.profiles.status
          else 'invited'
        end,
        updated_at = now();

  insert into public.factory_memberships (factory_id, user_id, role, status)
  values (p_factory_id, p_user_id, 'reviewer', 'disabled')
  on conflict (factory_id, user_id) do update
    set role = 'reviewer',
        status = case
          when public.factory_memberships.status = 'active'
            then public.factory_memberships.status
          else 'disabled'
        end,
        updated_at = now();

  insert into public.reviewer_lifecycles (
    user_id, factory_id, email, state, country_code,
    employment_classification, pay_basis
  ) values (
    p_user_id, p_factory_id, lower(trim(p_email)), 'invited',
    nullif(upper(trim(p_country_code)), ''),
    nullif(p_employment_classification, ''),
    nullif(p_pay_basis, '')
  )
  on conflict (user_id) do update
    set email = excluded.email,
        state = public.reviewer_lifecycles.state,
        country_code = excluded.country_code,
        employment_classification = excluded.employment_classification,
        pay_basis = excluded.pay_basis,
        state_reason = null,
        invited_at = now(),
        updated_at = now();

  update public.reviewer_invitations
  set status = 'revoked', revoked_at = now()
  where user_id = p_user_id
    and status in ('created', 'sent', 'delivery_failed');

  insert into public.reviewer_invitations (
    factory_id, user_id, email, locale, status, expires_at, invited_by,
    invitation_token_hash
  ) values (
    p_factory_id, p_user_id, lower(trim(p_email)), p_locale,
    'created', p_expires_at, actor_id, p_invitation_token_hash
  ) returning id into invitation_id;

  return invitation_id;
end;
$$;

create or replace function public.worker_accept_reviewer_invitation(
  p_invitation_token text
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  invitation public.reviewer_invitations%rowtype;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  if p_invitation_token is null or length(p_invitation_token) < 32 then
    raise exception 'invitation token is invalid' using errcode = '22023';
  end if;

  select candidate.* into invitation
  from public.reviewer_invitations candidate
  where candidate.user_id = actor_id
    and candidate.invitation_token_hash =
      encode(digest(p_invitation_token, 'sha256'), 'hex')
  order by candidate.created_at desc
  limit 1
  for update;

  if invitation.id is null then
    return jsonb_build_object('accepted', false, 'reason', 'invalid');
  end if;
  if invitation.status = 'accepted' then
    return jsonb_build_object('accepted', false, 'reason', 'already_used');
  end if;
  if invitation.status = 'sent'
     and invitation.expires_at > now()
     and invitation.revoked_at is null then
    update public.reviewer_invitations
    set status = 'accepted', accepted_at = now()
    where id = invitation.id;
    return jsonb_build_object(
      'accepted', true,
      'invitationId', invitation.id
    );
  end if;
  if invitation.expires_at <= now()
     and invitation.status in ('created', 'sent', 'delivery_failed') then
    update public.reviewer_invitations
    set status = 'expired'
    where id = invitation.id;
    return jsonb_build_object('accepted', false, 'reason', 'expired');
  end if;
  return jsonb_build_object('accepted', false, 'reason', invitation.status);
end;
$$;

create or replace function public.service_expire_reviewer_invitations()
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  expired_count integer;
begin
  update public.reviewer_invitations
  set status = 'expired'
  where status in ('created', 'sent', 'delivery_failed')
    and expires_at <= now();
  get diagnostics expired_count = row_count;
  return expired_count;
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
    'supportConfigured',
      current_setting('app.settings.reviewer_support_configured', true) = 'true'
  )
  into result
  from public.reviewer_lifecycles lifecycle
  join public.profiles profile on profile.id = lifecycle.user_id
  where lifecycle.user_id = actor_id;
  return coalesce(result, jsonb_build_object('state', 'unregistered'));
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
  assignment_row public.review_assignments%rowtype;
  request_id uuid;
begin
  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = actor_id;
  if lifecycle_row.user_id is null then
    raise exception 'reviewer is not registered' using errcode = '42501';
  end if;

  if p_assignment_id is not null then
    select assignment.* into assignment_row
    from public.review_assignments assignment
    where assignment.id = p_assignment_id
      and assignment.reviewer_id = actor_id
      and assignment.factory_id = lifecycle_row.factory_id
      and assignment.status in ('queued', 'leased', 'draft', 'submitted', 'problem')
      and (
        assignment.status not in ('leased', 'draft')
        or assignment.lease_expires_at > now()
      );
    if assignment_row.id is null then
      raise exception 'support assignment is not available to this reviewer'
        using errcode = '42501';
    end if;
  end if;

  if (
    select count(*) from public.reviewer_support_requests
    where reviewer_id = actor_id
      and created_at > now() - interval '1 hour'
  ) >= 10 then
    raise exception 'support request limit reached' using errcode = '54000';
  end if;
  insert into public.reviewer_support_requests (
    factory_id, reviewer_id, assignment_id, reason_code, message
  ) values (
    lifecycle_row.factory_id, actor_id, p_assignment_id,
    p_reason_code, trim(p_message)
  ) returning id into request_id;
  return request_id;
end;
$$;

create or replace function public.worker_touch_work_session(
  p_session_id uuid,
  p_device_id_hash text,
  p_active_seconds_delta integer default 0
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  session_row public.reviewer_work_sessions%rowtype;
  server_elapsed_seconds integer := 0;
begin
  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = actor_id and state = 'active';
  if lifecycle_row.user_id is null then
    raise exception 'active reviewer required' using errcode = '42501';
  end if;
  if p_device_id_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid device identifier' using errcode = '22023';
  end if;

  if p_session_id is not null then
    select * into session_row
    from public.reviewer_work_sessions
    where id = p_session_id
      and reviewer_id = actor_id
      and ended_at is null
    for update;
  else
    select * into session_row
    from public.reviewer_work_sessions
    where reviewer_id = actor_id and ended_at is null
    for update;
  end if;

  if session_row.id is null then
    insert into public.reviewer_work_sessions (
      factory_id, reviewer_id, device_id_hash
    ) values (
      lifecycle_row.factory_id, actor_id, p_device_id_hash
    ) returning * into session_row;
  elsif session_row.device_id_hash <> p_device_id_hash then
    raise exception 'work session belongs to a different device'
      using errcode = '42501';
  elsif p_active_seconds_delta > 0 then
    server_elapsed_seconds := greatest(
      0,
      least(
        60,
        floor(extract(epoch from (
          clock_timestamp() - session_row.last_seen_at
        )))::integer
      )
    );
  end if;

  insert into public.reviewer_device_registrations (user_id, device_id_hash)
  values (actor_id, p_device_id_hash)
  on conflict (user_id, device_id_hash) do update
    set last_seen_at = now()
    where public.reviewer_device_registrations.status = 'active';

  if not exists (
    select 1 from public.reviewer_device_registrations device
    where device.user_id = actor_id
      and device.device_id_hash = p_device_id_hash
      and device.status = 'active'
  ) then
    raise exception 'active registered device required' using errcode = '42501';
  end if;

  update public.reviewer_work_sessions
  set last_seen_at = now(),
      active_seconds = active_seconds + server_elapsed_seconds
  where id = session_row.id
  returning * into session_row;

  return jsonb_build_object(
    'sessionId', session_row.id,
    'startedAt', session_row.started_at,
    'lastSeenAt', session_row.last_seen_at,
    'activeSeconds', session_row.active_seconds
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
      where submission.submitted_at >= date_trunc('day', now())
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
      'mediaBucket', media.bucket_id,
      'mediaPath', media.object_path
    ),
    'attempts', (
      select count(*) from public.reviewer_qualification_attempts attempt
      where attempt.reviewer_id = actor_id and attempt.chunk_id = chunk.id
    )
  ) into result
  from public.video_chunks chunk
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

create or replace function public.worker_submit_reviewer_qualification(
  p_chunk_id uuid,
  p_total_count integer,
  p_event_times_ms jsonb,
  p_device_id_hash text
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle public.reviewer_lifecycles%rowtype;
  chunk public.video_chunks%rowtype;
  answer private.reference_answers%rowtype;
  submitted_event_count integer;
  reference_event_count integer;
  invalid_event_count integer;
  max_event_delta_ms bigint := 0;
  passed boolean;
  metrics jsonb;
begin
  select * into lifecycle
  from public.reviewer_lifecycles
  where user_id = actor_id
  for update;
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
  if p_total_count < 0 or jsonb_typeof(p_event_times_ms) <> 'array' then
    raise exception 'qualification answer is invalid' using errcode = '22023';
  end if;
  if p_device_id_hash !~ '^[0-9a-f]{64}$'
     or not exists (
       select 1 from public.reviewer_device_registrations device
       where device.user_id = actor_id
         and device.device_id_hash = p_device_id_hash
         and device.status = 'active'
     ) then
    raise exception 'active registered device required' using errcode = '42501';
  end if;
  if (
    select count(*) from public.reviewer_qualification_attempts attempt
    where attempt.reviewer_id = actor_id
      and attempt.submitted_at > now() - interval '24 hours'
  ) >= 3 then
    raise exception 'qualification attempt limit reached' using errcode = '54000';
  end if;

  select * into chunk
  from public.video_chunks candidate
  where candidate.id = p_chunk_id
    and candidate.factory_id = lifecycle.factory_id
    and candidate.source_set_role = 'qualification'
    and not candidate.assignment_eligible;
  select reference.* into answer
  from private.reference_answers reference
  where reference.chunk_id = chunk.id
    and reference.factory_id = chunk.factory_id
    and reference.answer_type = 'qualification'
    and reference.source_sha256 = chunk.source_sha256;
  if chunk.id is null or answer.id is null then
    raise exception 'approved qualification reference is required'
      using errcode = '23514';
  end if;

  select count(*) into invalid_event_count
  from jsonb_array_elements_text(p_event_times_ms) event(value)
  where event.value !~ '^[0-9]+$'
     or event.value::bigint < chunk.source_start_ms
     or event.value::bigint > chunk.source_end_ms;
  if invalid_event_count > 0 then
    raise exception 'qualification event time is invalid' using errcode = '22023';
  end if;

  submitted_event_count := jsonb_array_length(p_event_times_ms);
  reference_event_count := jsonb_array_length(answer.event_times_ms);
  if submitted_event_count = reference_event_count and reference_event_count > 0 then
    select coalesce(max(abs(submitted.value::bigint - reference.value::bigint)), 0)
    into max_event_delta_ms
    from jsonb_array_elements_text(p_event_times_ms)
      with ordinality submitted(value, position)
    join jsonb_array_elements_text(answer.event_times_ms)
      with ordinality reference(value, position)
      using (position);
  end if;

  passed := p_total_count = answer.total_count
    and submitted_event_count = reference_event_count
    and (reference_event_count = 0 or max_event_delta_ms <= 1500);
  metrics := jsonb_build_object(
    'submittedCount', p_total_count,
    'expectedEventCount', reference_event_count,
    'submittedEventCount', submitted_event_count,
    'maxEventDeltaMs', max_event_delta_ms,
    'toleranceMs', 1500
  );

  insert into public.reviewer_qualification_attempts (
    factory_id, reviewer_id, chunk_id, source_sha256,
    total_count, event_times_ms, passed, score_metrics
  ) values (
    lifecycle.factory_id, actor_id, chunk.id, chunk.source_sha256,
    p_total_count, p_event_times_ms, passed, metrics
  );

  update public.reviewer_lifecycles
  set state = case when passed then 'active' else 'qualification' end,
      qualified_at = case when passed then now() else qualified_at end,
      activated_at = case when passed then coalesce(activated_at, now()) else activated_at end,
      state_reason = case
        when passed then null
        else 'Qualification score did not pass'
      end,
      updated_at = now()
  where user_id = actor_id;
  if passed then
    update public.profiles set status = 'active', updated_at = now()
    where id = actor_id;
    update public.factory_memberships
    set status = 'active', updated_at = now()
    where user_id = actor_id
      and factory_id = lifecycle.factory_id
      and role = 'reviewer';
  end if;

  insert into public.reviewer_training_events (
    factory_id, user_id, event_type, training_version, actor_user_id, metadata
  ) values (
    lifecycle.factory_id, actor_id,
    case when passed then 'qualification_passed' else 'qualification_failed' end,
    'qualification-v1', actor_id,
    metrics || jsonb_build_object('chunkId', chunk.id)
  );
  if passed then
    insert into public.reviewer_training_events (
      factory_id, user_id, event_type, training_version, actor_user_id, metadata
    ) values (
      lifecycle.factory_id, actor_id, 'activated',
      'qualification-v1', actor_id,
      jsonb_build_object('qualificationChunkId', chunk.id)
    );
  end if;

  return jsonb_build_object(
    'passed', passed,
    'state', case when passed then 'active' else 'qualification' end,
    'attemptNumber', (
      select count(*) from public.reviewer_qualification_attempts attempt
      where attempt.reviewer_id = actor_id
        and attempt.chunk_id = chunk.id
    )
  );
end;
$$;

revoke all on function public.service_register_reviewer_invitation(
  uuid, uuid, text, text, text, text, text, text, timestamptz, text, text, text
) from public, anon;
grant execute on function public.service_register_reviewer_invitation(
  uuid, uuid, text, text, text, text, text, text, timestamptz, text, text, text
) to authenticated;

revoke all on function public.worker_accept_reviewer_invitation(text)
  from public, anon;
grant execute on function public.worker_accept_reviewer_invitation(text)
  to authenticated;
revoke all on function public.service_expire_reviewer_invitations()
  from public, anon, authenticated;
revoke all on function public.ops_workforce_metrics()
  from public, anon;
grant execute on function public.ops_workforce_metrics()
  to authenticated;
revoke all on function public.worker_claim_reviewer_qualification()
  from public, anon;
grant execute on function public.worker_claim_reviewer_qualification()
  to authenticated;
revoke all on function public.worker_submit_reviewer_qualification(
  uuid, integer, jsonb, text
) from public, anon;
grant execute on function public.worker_submit_reviewer_qualification(
  uuid, integer, jsonb, text
) to authenticated;

do $$
begin
  if not exists (
    select 1 from cron.job where jobname = 'factoryvision-invitation-expiry'
  ) then
    perform cron.schedule(
      'factoryvision-invitation-expiry',
      '* * * * *',
      'select public.service_expire_reviewer_invitations();'
    );
  end if;
end;
$$;
