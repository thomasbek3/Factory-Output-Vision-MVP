-- Executable, rollback-only live proof for the worker workforce contract.
-- Run against a nonempty FactoryVision project after migrations. It requires
-- three active test reviewers and one verified production chunk, emits receipt
-- rows, and leaves no durable fixture data.

begin;

create temp table proof_reviewers (
  position integer primary key,
  user_id uuid not null
) on commit drop;

insert into proof_reviewers (position, user_id)
select row_number() over (order by lifecycle.user_id), lifecycle.user_id
from public.reviewer_lifecycles lifecycle
join public.profiles profile
  on profile.id = lifecycle.user_id and profile.status = 'active'
join public.factory_memberships membership
  on membership.user_id = lifecycle.user_id
 and membership.factory_id = lifecycle.factory_id
 and membership.role = 'reviewer'
 and membership.status = 'active'
where lifecycle.is_test_account
  and lifecycle.state = 'active'
order by lifecycle.user_id
limit 3;

create temp table proof_ops (
  user_id uuid primary key,
  factory_id uuid not null
) on commit drop;

insert into proof_ops (user_id, factory_id)
select lifecycle.user_id, lifecycle.factory_id
from public.reviewer_lifecycles lifecycle
where lifecycle.user_id = (
  select user_id from proof_reviewers where position = 3
);

do $$
begin
  if (select count(*) from proof_reviewers) <> 3 then
    raise exception 'live proof requires three active test reviewers';
  end if;
  if (select count(*) from proof_ops) <> 1 then
    raise exception 'live proof requires one active ops user';
  end if;
end;
$$;

create function pg_temp.proof_chunk(
  p_source_start_at timestamptz,
  p_source_set_role text,
  p_assignment_eligible boolean,
  p_state text
)
returns uuid
language plpgsql
as $$
declare
  source public.video_chunks%rowtype;
  chunk_id uuid := gen_random_uuid();
begin
  select * into source
  from public.video_chunks
  where source_set_role = 'production'
  order by created_at
  limit 1;
  if source.id is null then
    raise exception 'live proof requires one production chunk';
  end if;
  insert into public.video_chunks (
    id, factory_id, station_id, source_media_object_id, review_rendition_id,
    source_sha256, source_start_at, source_end_at, source_start_ms,
    source_end_ms, source_set_role, assignment_eligible, state, gap_map
  ) values (
    chunk_id, source.factory_id, source.station_id,
    source.source_media_object_id, source.review_rendition_id,
    source.source_sha256, p_source_start_at,
    p_source_start_at + interval '15 minutes',
    source.source_start_ms, source.source_end_ms, p_source_set_role,
    p_assignment_eligible, p_state, '[]'::jsonb
  );
  return chunk_id;
end;
$$;

create function pg_temp.proof_assignments(
  p_chunk_id uuid,
  p_key_prefix text
)
returns uuid[]
language plpgsql
as $$
declare
  chunk public.video_chunks%rowtype;
  assignment_ids uuid[] := array[gen_random_uuid(), gen_random_uuid(), gen_random_uuid()];
begin
  select * into chunk from public.video_chunks where id = p_chunk_id;
  insert into public.review_assignments (
    id, factory_id, chunk_id, rendition_id, reviewer_id, review_round,
    status, lease_token_hash, leased_at, lease_expires_at
  )
  select assignment_ids[reviewer.position], chunk.factory_id, chunk.id,
    chunk.review_rendition_id, reviewer.user_id, 1, 'leased',
    encode(
      extensions.digest(p_key_prefix || reviewer.position::text, 'sha256'),
      'hex'
    ),
    now(), now() + interval '30 minutes'
  from proof_reviewers reviewer;
  return assignment_ids;
end;
$$;

do $$
declare
  chunk_id uuid := pg_temp.proof_chunk(
    '2098-01-01T00:00:00Z', 'production', true, 'assigned'
  );
  assignments uuid[] := pg_temp.proof_assignments(chunk_id, 'majority-');
  chunk public.video_chunks%rowtype;
  reviewers uuid[];
  base_time bigint;
  run public.consensus_runs%rowtype;
begin
  select * into chunk from public.video_chunks where id = chunk_id;
  select array_agg(user_id order by position) into reviewers from proof_reviewers;
  base_time := chunk.source_start_ms + 1000;

  insert into public.review_actions (
    factory_id, assignment_id, reviewer_id, client_action_id, action_type,
    source_time_ms, playback_rate, app_version
  ) values
    (chunk.factory_id, assignments[1], reviewers[1], gen_random_uuid(),
     'tally', base_time, 5, 'workforce-live-proof'),
    (chunk.factory_id, assignments[2], reviewers[2], gen_random_uuid(),
     'tally', base_time + 500, 5, 'workforce-live-proof'),
    (chunk.factory_id, assignments[3], reviewers[3], gen_random_uuid(),
     'tally', base_time + 300, 5, 'workforce-live-proof'),
    (chunk.factory_id, assignments[3], reviewers[3], gen_random_uuid(),
     'tally', base_time + 2000, 5, 'workforce-live-proof');

  insert into public.review_submissions (
    factory_id, assignment_id, chunk_id, reviewer_id, review_round,
    result_type, total_count, source_sha256, rendition_id,
    app_version, idempotency_key
  ) values
    (chunk.factory_id, assignments[1], chunk.id, reviewers[1], 1,
     'counted', 1, chunk.source_sha256, chunk.review_rendition_id,
     'workforce-live-proof', gen_random_uuid()),
    (chunk.factory_id, assignments[2], chunk.id, reviewers[2], 1,
     'counted', 1, chunk.source_sha256, chunk.review_rendition_id,
     'workforce-live-proof', gen_random_uuid()),
    (chunk.factory_id, assignments[3], chunk.id, reviewers[3], 1,
     'counted', 2, chunk.source_sha256, chunk.review_rendition_id,
     'workforce-live-proof', gen_random_uuid());

  perform public.service_resolve_ready_rounds();
  set constraints all immediate;
  select * into run from public.consensus_runs
  where public.consensus_runs.chunk_id = chunk.id and review_round = 1;
  if run.status <> 'resolved'
     or run.resolved_total <> 1
     or run.support_count <> 2
     or (select count(*) from public.review_submissions submission
         where submission.chunk_id = chunk.id and submission.review_round = 1) <> 3
     or (select count(distinct source.submission_id)
         from public.consensus_event_sources source
         join public.consensus_events event
           on event.id = source.consensus_event_id
         where event.consensus_run_id = run.id) <> 2
     or not exists (
       select 1 from public.resolved_human_count_events projection
       where projection.chunk_id = chunk.id
         and projection.publication_status = 'published'
         and projection.published_at is not null
     ) then
    raise exception 'three-reviewer majority proof failed';
  end if;
end;
$$;

do $$
declare
  chunk_id uuid := pg_temp.proof_chunk(
    '2097-01-01T00:00:00Z', 'production', true, 'assigned'
  );
  assignments uuid[] := pg_temp.proof_assignments(chunk_id, 'no-majority-');
  chunk public.video_chunks%rowtype;
  reviewers uuid[];
  base_time bigint;
  run public.consensus_runs%rowtype;
begin
  select * into chunk from public.video_chunks where id = chunk_id;
  select array_agg(user_id order by position) into reviewers from proof_reviewers;
  base_time := chunk.source_start_ms + 1000;

  insert into public.review_actions (
    factory_id, assignment_id, reviewer_id, client_action_id, action_type,
    source_time_ms, playback_rate, app_version
  )
  select chunk.factory_id, assignments[1], reviewers[1], gen_random_uuid(),
    'tally', base_time, 5, 'workforce-live-proof'
  union all
  select chunk.factory_id, assignments[2], reviewers[2], gen_random_uuid(),
    'tally', base_time, 5, 'workforce-live-proof'
  union all
  select chunk.factory_id, assignments[2], reviewers[2], gen_random_uuid(),
    'tally', base_time + 2000, 5, 'workforce-live-proof'
  union all
  select chunk.factory_id, assignments[3], reviewers[3], gen_random_uuid(),
    'tally', base_time, 5, 'workforce-live-proof'
  union all
  select chunk.factory_id, assignments[3], reviewers[3], gen_random_uuid(),
    'tally', base_time + 2000, 5, 'workforce-live-proof'
  union all
  select chunk.factory_id, assignments[3], reviewers[3], gen_random_uuid(),
    'tally', base_time + 4000, 5, 'workforce-live-proof';

  insert into public.review_submissions (
    factory_id, assignment_id, chunk_id, reviewer_id, review_round,
    result_type, total_count, source_sha256, rendition_id,
    app_version, idempotency_key
  )
  select chunk.factory_id, assignments[reviewer.position], chunk.id,
    reviewer.user_id, 1, 'counted', reviewer.position, chunk.source_sha256,
    chunk.review_rendition_id, 'workforce-live-proof', gen_random_uuid()
  from proof_reviewers reviewer;

  perform public.service_resolve_ready_rounds();
  set constraints all immediate;
  select * into run from public.consensus_runs
  where public.consensus_runs.chunk_id = chunk.id and review_round = 1;
  if run.status <> 'no_majority'
     or run.resolved_total is not null
     or run.support_count is not null
     or not exists (
       select 1 from public.internal_review_cases review_case
       where review_case.chunk_id = chunk.id
         and review_case.reason_code = 'count_disagreement'
     )
     or exists (
       select 1 from public.human_finalizations finalization
       where finalization.chunk_id = chunk.id
     ) then
    raise exception 'three-reviewer no-majority proof failed';
  end if;
end;
$$;

do $$
declare
  qualification_reviewer_id uuid := (
    select user_id from proof_reviewers where position = 1
  );
  chunk_id uuid := pg_temp.proof_chunk(
    '2099-01-01T00:00:00Z', 'qualification', false, 'ready'
  );
  chunk public.video_chunks%rowtype;
  device_hash text;
  result jsonb;
begin
  select * into chunk from public.video_chunks where id = chunk_id;
  select device_id_hash into device_hash
  from public.reviewer_device_registrations
  where user_id = qualification_reviewer_id and status = 'active'
  limit 1;
  insert into private.reference_answers (
    factory_id, chunk_id, answer_type, total_count, event_times_ms,
    source_sha256, created_by
  ) values (
    chunk.factory_id, chunk.id, 'qualification', 1,
    jsonb_build_array(chunk.source_start_ms + 1000),
    chunk.source_sha256, qualification_reviewer_id
  );
  update public.reviewer_lifecycles
  set state = 'qualification', qualified_at = null, activated_at = null
  where user_id = qualification_reviewer_id;
  update public.profiles
  set status = 'disabled'
  where id = qualification_reviewer_id;
  update public.factory_memberships set status = 'disabled'
  where user_id = qualification_reviewer_id
    and factory_id = chunk.factory_id;
  perform set_config(
    'request.jwt.claim.sub',
    qualification_reviewer_id::text,
    true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  result := public.worker_submit_reviewer_qualification(
    chunk.id, 1, jsonb_build_array(chunk.source_start_ms + 1000), device_hash
  );
  if coalesce((result ->> 'passed')::boolean, false) is not true
     or result ->> 'state' <> 'active'
     or not exists (
       select 1 from public.reviewer_qualification_attempts attempt
       where attempt.reviewer_id = qualification_reviewer_id
         and attempt.chunk_id = chunk.id
         and attempt.passed
     ) then
    raise exception 'qualification claim-score-activate proof failed';
  end if;
end;
$$;

do $$
declare
  ops_id uuid := (select user_id from proof_ops);
  invite_factory_id uuid := (select factory_id from proof_ops);
  reviewer_id uuid := (
    select user_id from proof_reviewers where position = 1
  );
  invite_request_key uuid := gen_random_uuid();
  first_invitation_id uuid;
  second_invitation_id uuid;
  first_claim jsonb;
  second_claim jsonb;
begin
  update public.factory_memberships
  set role = 'ops', status = 'active'
  where user_id = ops_id and factory_id = invite_factory_id;
  perform set_config('request.jwt.claim.sub', ops_id::text, true);
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  first_invitation_id := public.service_register_reviewer_invitation(
    reviewer_id,
    invite_factory_id,
    'rollback-proof@example.invalid',
    'Rollback Proof Reviewer',
    'en',
    'US',
    'contractor',
    'hourly',
    now() + interval '1 hour',
    null,
    null,
    repeat('a', 64),
    invite_request_key
  );
  second_invitation_id := public.service_register_reviewer_invitation(
    reviewer_id,
    invite_factory_id,
    'rollback-proof@example.invalid',
    'Rollback Proof Reviewer',
    'en',
    'US',
    'contractor',
    'hourly',
    now() + interval '1 hour',
    null,
    null,
    repeat('a', 64),
    invite_request_key
  );
  first_claim := public.ops_claim_reviewer_invitation_delivery(
    first_invitation_id
  );
  second_claim := public.ops_claim_reviewer_invitation_delivery(
    second_invitation_id
  );
  if first_invitation_id <> second_invitation_id
     or (
       select count(*)
       from public.reviewer_invitations invitation
       where invitation.request_key = invite_request_key
     ) <> 1
     or coalesce((first_claim ->> 'claimed')::boolean, false) is not true
     or coalesce((second_claim ->> 'claimed')::boolean, true) is not false
     or second_claim ->> 'status' <> 'sending' then
    raise exception 'cross-attempt invitation idempotency proof failed';
  end if;
end;
$$;

do $$
declare
  reviewer_id uuid := (
    select user_id from proof_reviewers where position = 2
  );
  result jsonb;
  suspended_denied boolean := false;
  offboarded_denied boolean := false;
begin
  perform set_config('request.jwt.claim.sub', reviewer_id::text, true);
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  result := public.worker_authorize_reviewer_session();
  if coalesce((result ->> 'authorized')::boolean, false) is not true
     or result ->> 'state' <> 'active' then
    raise exception 'active reviewer session authorization proof failed';
  end if;

  update public.reviewer_lifecycles
  set state = 'suspended', state_reason = 'rollback proof'
  where user_id = reviewer_id;
  begin
    perform public.worker_authorize_reviewer_session();
  exception
    when sqlstate '42501' then
      suspended_denied := true;
  end;

  update public.reviewer_lifecycles
  set state = 'offboarded', state_reason = 'rollback proof'
  where user_id = reviewer_id;
  begin
    perform public.worker_authorize_reviewer_session();
  exception
    when sqlstate '42501' then
      offboarded_denied := true;
  end;

  if not suspended_denied or not offboarded_denied then
    raise exception 'suspended/offboarded session denial proof failed';
  end if;
end;
$$;

select receipt
from (
  values
    ('three_reviewers_human_2_of_3_lineage_passed'),
    ('three_reviewers_no_majority_hold_passed'),
    ('qualification_claim_score_activate_passed'),
    ('cross_attempt_invitation_idempotency_passed'),
    ('suspended_and_offboarded_session_denial_passed')
) proof(receipt);

rollback;
