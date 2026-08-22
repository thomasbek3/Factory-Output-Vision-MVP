-- Typed coverage-gate error codes for submit_worker_assignment_v2.
--
-- The three submission integrity gates previously shared SQLSTATE 23514
-- (check_violation), forcing the worker UI to distinguish them by matching
-- English exception text. This migration re-raises the same conditions with
-- distinct five-character custom error codes while keeping every exception
-- message byte-identical to 20260728012044_worker_review_speed_20x.sql, so
-- clients can branch on stable codes instead of prose. Timing thresholds,
-- gate order, MFA/lifecycle checks, and idempotency are otherwise untouched.

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

  select assignment.* into assignment_row
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
    and assignment.lease_expires_at > now() - interval '5 minutes'
    and assignment.lease_token_hash =
      encode(extensions.digest(p_lease_token, 'sha256'), 'hex')
  for update of assignment;
  if assignment_row.id is null then
    raise exception 'assignment is not submittable' using errcode = '42501';
  end if;

  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = actor_id;
  if lifecycle_row.state <> 'active'
     or (
       not lifecycle_row.is_test_account
       and coalesce(auth.jwt() ->> 'aal', '') <> 'aal2'
     ) then
    raise exception 'active reviewer with MFA required' using errcode = 'MF000';
  end if;
  select * into chunk_row
  from public.video_chunks
  where id = assignment_row.chunk_id;

  if p_result_type = 'counted' and not lifecycle_row.is_test_account then
    select * into coverage_row
    from public.review_coverage
    where assignment_id = assignment_row.id;
    if coverage_row.assignment_id is null then
      raise exception 'video coverage has not been saved'
        using errcode = 'CV000';
    end if;
    select coalesce(sum(range_row.end_ms - range_row.start_ms), 0)
    into covered_ms
    from jsonb_to_recordset(coverage_row.ranges)
      as range_row(start_ms bigint, end_ms bigint);
    usable_ms := chunk_row.source_end_ms - chunk_row.source_start_ms;
    if covered_ms * 100 < usable_ms * 98 then
      raise exception 'at least 98 percent of the video must be reviewed'
        using errcode = 'CV001';
    end if;
    minimum_elapsed := make_interval(
      secs => greatest(0, usable_ms / 20000.0 - 5)
    );
    if assignment_row.leased_at is null
       or now() - assignment_row.leased_at < minimum_elapsed then
      raise exception
        'review completed faster than the enabled playback speed permits'
        using errcode = 'CV002';
    end if;
  end if;

  select count(*)::integer into active_total
  from public.review_actions tally
  where tally.assignment_id = assignment_row.id
    and tally.action_type = 'tally'
    and not exists (
      select 1
      from public.review_actions undo
      where undo.assignment_id = tally.assignment_id
        and undo.action_type = 'undo'
        and undo.undoes_action_id = tally.id
    );

  insert into public.review_submissions (
    factory_id,
    assignment_id,
    chunk_id,
    reviewer_id,
    review_round,
    result_type,
    total_count,
    problem_code,
    source_sha256,
    rendition_id,
    app_version,
    idempotency_key
  ) values (
    assignment_row.factory_id,
    assignment_row.id,
    assignment_row.chunk_id,
    actor_id,
    assignment_row.review_round,
    p_result_type,
    case when p_result_type = 'counted' then active_total else null end,
    case when p_result_type = 'problem' then p_problem_code else null end,
    chunk_row.source_sha256,
    assignment_row.rendition_id,
    p_app_version,
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
