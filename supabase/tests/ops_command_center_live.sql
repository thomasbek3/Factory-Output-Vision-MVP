-- Run against a seeded QA project. Every mutation is rolled back.

begin;

do $$
declare
  reviewer_id uuid;
begin
  select membership.user_id
  into reviewer_id
  from public.factory_memberships membership
  join public.profiles profile on profile.id = membership.user_id
  where membership.role = 'reviewer'
    and membership.status = 'active'
    and profile.status = 'active'
  limit 1;

  if reviewer_id is null then
    raise exception 'ops proof requires an active reviewer fixture';
  end if;

  perform set_config(
    'request.jwt.claims',
    jsonb_build_object('sub', reviewer_id, 'role', 'authenticated')::text,
    true
  );

  begin
    perform public.ops_assert_access(
      (select membership.factory_id
       from public.factory_memberships membership
       where membership.user_id = reviewer_id
       limit 1)
    );
    raise exception 'non-ops reviewer reached ops_assert_access' using errcode = 'P0001';
  exception
    when sqlstate '42501' then null;
  end;

  begin
    perform public.ops_command_center();
    raise exception 'non-ops reviewer reached ops_command_center' using errcode = 'P0001';
  exception
    when sqlstate '42501' then null;
  end;
end;
$$;

do $$
declare
  ops_id uuid;
  target_chunk record;
  proof_run_id uuid := gen_random_uuid();
  payload jsonb;
  target_label jsonb;
begin
  select membership.user_id
  into ops_id
  from public.factory_memberships membership
  join public.profiles profile on profile.id = membership.user_id
  where membership.role = 'ops'
    and membership.status = 'active'
    and profile.status = 'active'
  limit 1;

  select chunk.id, chunk.factory_id, chunk.source_sha256
  into target_chunk
  from public.video_chunks chunk
  where not exists (
    select 1
    from public.human_finalizations finalization
    where finalization.chunk_id = chunk.id
  )
  order by chunk.created_at desc
  limit 1;

  if ops_id is null or target_chunk.id is null then
    raise exception 'ops proof requires ops and unfinalized chunk fixtures';
  end if;

  perform set_config(
    'request.jwt.claims',
    jsonb_build_object('sub', ops_id, 'role', 'authenticated')::text,
    true
  );

  if not public.ops_assert_access(target_chunk.factory_id) then
    raise exception 'ops assertion did not authorize fixture operator';
  end if;

  if has_function_privilege(
    'authenticated',
    'public.ops_command_center_internal_v1()',
    'execute'
  ) then
    raise exception 'authenticated can execute the internal unredacted projection';
  end if;

  insert into private.ai_runs (
    id,
    factory_id,
    chunk_id,
    source_sha256,
    model_artifact_sha256,
    code_version,
    parameters,
    started_at,
    completed_at
  ) values (
    proof_run_id,
    target_chunk.factory_id,
    target_chunk.id,
    target_chunk.source_sha256,
    repeat('a', 64),
    'ops-live-proof-rollback',
    '{}'::jsonb,
    now() - interval '1 minute',
    now()
  );

  insert into private.ai_events (ai_run_id, source_time_ms, confidence)
  values (proof_run_id, 1000, 0.99000);

  payload := public.ops_command_center();
  select label
  into target_label
  from jsonb_array_elements(payload -> 'labels') label
  where label ->> 'chunkId' = target_chunk.id::text
  limit 1;

  if target_label is null
    or target_label ->> 'aiStatus' <> 'locked_until_human_final'
    or target_label ->> 'aiRunId' is not null
    or (target_label ->> 'aiEventCount')::integer <> 0
    or target_label ->> 'aiCodeVersion' is not null
    or target_label ->> 'comparisonMetrics' is not null
  then
    raise exception 'unfinalized AI output was not fully redacted';
  end if;
end;
$$;

rollback;

select 'ops_command_center_security_passed' as receipt;
