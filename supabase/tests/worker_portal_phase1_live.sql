-- Run with stop-on-error semantics. For psql:
--   psql -v ON_ERROR_STOP=1 -f supabase/tests/worker_portal_phase1_live.sql
-- Supabase execute_sql also aborts and returns an error on the first uncaught failure.

begin;

insert into auth.users (id, instance_id, aud, role, email, created_at, updated_at)
values
  ('60000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'fv-reviewer-1@example.invalid', now(), now()),
  ('60000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'fv-reviewer-2@example.invalid', now(), now()),
  ('60000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'fv-reviewer-3@example.invalid', now(), now()),
  ('60000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'fv-owner@example.invalid', now(), now()),
  ('60000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'fv-other-reviewer@example.invalid', now(), now()),
  ('60000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'fv-other-owner@example.invalid', now(), now());

insert into public.factories (id, name, timezone)
values
  ('10000000-0000-0000-0000-000000000001', 'Rollback-only fixture', 'America/New_York'),
  ('10000000-0000-0000-0000-000000000002', 'Cross-tenant fixture', 'America/Chicago');

insert into public.profiles (id, display_name, locale, status)
values
  ('60000000-0000-0000-0000-000000000001', 'Reviewer 1', 'es-419', 'active'),
  ('60000000-0000-0000-0000-000000000002', 'Reviewer 2', 'es-419', 'active'),
  ('60000000-0000-0000-0000-000000000003', 'Reviewer 3', 'es-419', 'active'),
  ('60000000-0000-0000-0000-000000000004', 'Owner', 'en', 'active'),
  ('60000000-0000-0000-0000-000000000005', 'Other reviewer', 'es-419', 'active'),
  ('60000000-0000-0000-0000-000000000006', 'Other owner', 'en', 'active');

insert into public.factory_memberships (factory_id, user_id, role)
values
  ('10000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 'reviewer'),
  ('10000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 'reviewer'),
  ('10000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000003', 'reviewer'),
  ('10000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000004', 'owner'),
  ('10000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000005', 'reviewer'),
  ('10000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000006', 'owner');

insert into public.stations (id, factory_id, alias)
values ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'Station 1');

insert into public.media_objects (
  id, factory_id, station_id, bucket_id, object_path, object_sha256,
  source_sha256, content_type, byte_size, duration_ms, status, verified_at
)
values
  (
    '30000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    'factory-originals',
    'fixture/original.mp4',
    repeat('a', 64),
    repeat('a', 64),
    'video/mp4',
    1000,
    900000,
    'verified',
    now()
  ),
  (
    '30000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    'review-renditions',
    'fixture/review.mp4',
    repeat('b', 64),
    repeat('a', 64),
    'video/mp4',
    500,
    900000,
    'verified',
    now()
  );

insert into public.media_renditions (
  id, factory_id, source_media_object_id, rendition_media_object_id, version,
  source_start_ms, source_end_ms, padded_start_ms, padded_end_ms,
  frame_rate_mode, frame_count, mapping, mapping_status
)
values (
  '40000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000002',
  1,
  0,
  900000,
  0,
  900000,
  'constant',
  27000,
  '{}'::jsonb,
  'verified'
);

insert into public.video_chunks (
  id, factory_id, station_id, source_media_object_id, review_rendition_id,
  source_sha256, source_start_at, source_end_at, source_start_ms, source_end_ms,
  source_set_role, assignment_eligible, state
)
values (
  '50000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '20000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '40000000-0000-0000-0000-000000000001',
  repeat('a', 64),
  '2026-07-26 12:00:00-04',
  '2026-07-26 12:15:00-04',
  0,
  900000,
  'production',
  true,
  'ready'
);

insert into public.review_assignments (
  id, factory_id, chunk_id, rendition_id, reviewer_id, review_round,
  status, lease_expires_at, app_version
)
values
  ('70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 1, 'leased', now() + interval '1 hour', 'fixture'),
  ('70000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 1, 'leased', now() + interval '1 hour', 'fixture'),
  ('70000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000003', 1, 'leased', now() + interval '1 hour', 'fixture');

do $$
begin
  begin
    update public.video_chunks
    set state = 'ingesting'
    where id = '50000000-0000-0000-0000-000000000001';
    raise exception 'illegal chunk state regression unexpectedly succeeded';
  exception when check_violation then
    if sqlerrm <> 'invalid chunk state transition from ready to ingesting' then
      raise;
    end if;
  end;

  begin
    update public.video_chunks
    set state = 'quarantined'
    where id = '50000000-0000-0000-0000-000000000001';
    insert into public.review_assignments (
      factory_id, chunk_id, rendition_id, reviewer_id, review_round,
      status, lease_expires_at, app_version
    )
    values (
      '10000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      '40000000-0000-0000-0000-000000000001',
      '60000000-0000-0000-0000-000000000001',
      3,
      'leased',
      now() + interval '1 hour',
      'fixture'
    );
    raise exception 'quarantined chunk assignment unexpectedly succeeded';
  exception when check_violation then
    if sqlerrm <> 'chunk is not reviewable' then
      raise;
    end if;
  end;

  begin
    update public.video_chunks
    set state = 'quarantined'
    where id = '50000000-0000-0000-0000-000000000001';
    update public.review_assignments
    set status = 'expired'
    where id = '70000000-0000-0000-0000-000000000001';
    if (select status from public.review_assignments
        where id = '70000000-0000-0000-0000-000000000001') <> 'expired' then
      raise exception 'quarantined assignment did not expire';
    end if;
    raise exception 'quarantined assignment cleanup accepted';
  exception when raise_exception then
    if sqlerrm <> 'quarantined assignment cleanup accepted' then
      raise;
    end if;
  end;
end;
$$;

update public.profiles
set status = 'disabled'
where id = '60000000-0000-0000-0000-000000000001';

do $$
begin
  begin
    insert into public.review_actions (
      factory_id, assignment_id, reviewer_id, client_action_id, action_type,
      source_time_ms, app_version
    )
    values (
      '10000000-0000-0000-0000-000000000001',
      '70000000-0000-0000-0000-000000000001',
      '60000000-0000-0000-0000-000000000001',
      '89000000-0000-0000-0000-000000000001',
      'tally',
      100000,
      'fixture'
    );
    raise exception 'disabled reviewer write unexpectedly succeeded';
  exception when check_violation then
    if sqlerrm <> 'reviewer is not active' then
      raise;
    end if;
  end;
end;
$$;

update public.profiles
set status = 'active'
where id = '60000000-0000-0000-0000-000000000001';

insert into public.review_actions (
  id, factory_id, assignment_id, reviewer_id, client_action_id, action_type,
  source_time_ms, app_version
)
values
  ('80000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '81000000-0000-0000-0000-000000000001', 'tally', 100000, 'fixture'),
  ('80000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000002', '81000000-0000-0000-0000-000000000002', 'tally', 100200, 'fixture'),
  ('80000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000003', '60000000-0000-0000-0000-000000000003', '81000000-0000-0000-0000-000000000003', 'tally', 100500, 'fixture'),
  ('80000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000003', '60000000-0000-0000-0000-000000000003', '81000000-0000-0000-0000-000000000004', 'tally', 200000, 'fixture'),
  ('80000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '81000000-0000-0000-0000-000000000005', 'tally', 101000, 'fixture');

insert into public.review_actions (
  id, factory_id, assignment_id, reviewer_id, client_action_id, action_type,
  source_time_ms, undoes_action_id, app_version
)
values (
  '80000000-0000-0000-0000-000000000006',
  '10000000-0000-0000-0000-000000000001',
  '70000000-0000-0000-0000-000000000001',
  '60000000-0000-0000-0000-000000000001',
  '81000000-0000-0000-0000-000000000006',
  'undo',
  null,
  '80000000-0000-0000-0000-000000000005',
  'fixture'
);

do $$
begin
  begin
    insert into public.review_submissions (
      factory_id, assignment_id, chunk_id, reviewer_id, review_round,
      result_type, total_count, source_sha256, rendition_id, app_version,
      idempotency_key
    )
    values (
      '10000000-0000-0000-0000-000000000001',
      '70000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      '60000000-0000-0000-0000-000000000001',
      1,
      'counted',
      2,
      repeat('a', 64),
      '40000000-0000-0000-0000-000000000001',
      'fixture',
      '91000000-0000-0000-0000-000000000099'
    );
    raise exception 'mismatched submission total unexpectedly succeeded';
  exception when check_violation then
    if sqlerrm <> 'submission total does not match immutable tally actions' then
      raise;
    end if;
  end;
end;
$$;

insert into public.review_submissions (
  id, factory_id, assignment_id, chunk_id, reviewer_id, review_round,
  result_type, total_count, source_sha256, rendition_id, app_version,
  idempotency_key
)
values
  ('90000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 1, 'counted', 1, repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000001'),
  ('90000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 1, 'counted', 1, repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000002'),
  ('90000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000003', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000003', 1, 'counted', 2, repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000003');

do $$
begin
  begin
    update public.review_assignments
    set status = 'expired'
    where id = '70000000-0000-0000-0000-000000000003';
    raise exception 'submitted assignment unexpectedly became reusable';
  exception when sqlstate '55000' then
    if sqlerrm <> 'submitted and problem assignments are terminal' then
      raise;
    end if;
  end;

  begin
    update public.review_assignments
    set reviewer_id = '60000000-0000-0000-0000-000000000002'
    where id = '70000000-0000-0000-0000-000000000001';
    raise exception 'assignment identity unexpectedly changed';
  exception when sqlstate '55000' then
    if sqlerrm <> 'assignment identity is immutable' then
      raise;
    end if;
  end;

  begin
    insert into public.consensus_runs (
      factory_id, chunk_id, review_round, resolver_version, status,
      resolved_total, support_count
    )
    values (
      '10000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      1,
      'invalid-null-support',
      'resolved',
      1,
      null
    );
    raise exception 'resolved consensus unexpectedly accepted null support';
  exception when check_violation then
    null;
  end;
end;
$$;

do $$
begin
  begin
    insert into public.review_assignments (
      id, factory_id, chunk_id, rendition_id, reviewer_id, review_round,
      status, lease_expires_at, app_version
    )
    values
      ('70000000-0000-0000-0000-000000000011', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 2, 'leased', now() + interval '1 hour', 'fixture'),
      ('70000000-0000-0000-0000-000000000012', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 2, 'leased', now() + interval '1 hour', 'fixture'),
      ('70000000-0000-0000-0000-000000000013', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000003', 2, 'leased', now() + interval '1 hour', 'fixture');

    insert into public.review_submissions (
      id, factory_id, assignment_id, chunk_id, reviewer_id, review_round,
      result_type, total_count, source_sha256, rendition_id, app_version,
      idempotency_key
    )
    values
      ('90000000-0000-0000-0000-000000000011', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000011', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 2, 'counted', 0, repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000011'),
      ('90000000-0000-0000-0000-000000000012', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000012', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 2, 'counted', 0, repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000012'),
      ('90000000-0000-0000-0000-000000000013', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000013', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000003', 2, 'counted', 0, repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000013');

    insert into public.consensus_runs (
      id, factory_id, chunk_id, review_round, resolver_version,
      resolver_parameters, status, resolved_total, support_count
    )
    values (
      'a0000000-0000-0000-0000-000000000011',
      '10000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      2,
      'zero-count-fixture',
      '{"alignment_tolerance_ms": 1500}'::jsonb,
      'resolved',
      0,
      3
    );
    set constraints consensus_runs_validate immediate;

    insert into public.human_finalizations (
      id, factory_id, chunk_id, review_round, consensus_run_id
    )
    values (
      'd0000000-0000-0000-0000-000000000011',
      '10000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      2,
      'a0000000-0000-0000-0000-000000000011'
    );
    set constraints human_finalizations_cardinality immediate;
    raise exception 'zero-count fixture accepted';
  exception when raise_exception then
    if sqlerrm <> 'zero-count fixture accepted' then
      raise;
    end if;
  end;
end;
$$;

set constraints all deferred;

do $$
begin
  begin
    insert into public.review_assignments (
      id, factory_id, chunk_id, rendition_id, reviewer_id, review_round,
      status, lease_expires_at, app_version
    )
    values
      ('70000000-0000-0000-0000-000000000021', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 3, 'leased', now() + interval '1 hour', 'fixture'),
      ('70000000-0000-0000-0000-000000000022', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 3, 'leased', now() + interval '1 hour', 'fixture'),
      ('70000000-0000-0000-0000-000000000023', '10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000003', 3, 'leased', now() + interval '1 hour', 'fixture');

    insert into public.review_actions (
      id, factory_id, assignment_id, reviewer_id, client_action_id,
      action_type, source_time_ms, app_version
    )
    values
      ('80000000-0000-0000-0000-000000000021', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000021', '60000000-0000-0000-0000-000000000001', '81000000-0000-0000-0000-000000000021', 'tally', 500000, 'fixture'),
      ('80000000-0000-0000-0000-000000000022', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000022', '60000000-0000-0000-0000-000000000002', '81000000-0000-0000-0000-000000000022', 'tally', 500200, 'fixture');

    insert into public.review_submissions (
      id, factory_id, assignment_id, chunk_id, reviewer_id, review_round,
      result_type, total_count, problem_code, source_sha256, rendition_id,
      app_version, idempotency_key
    )
    values
      ('90000000-0000-0000-0000-000000000021', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000021', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 3, 'counted', 1, null, repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000021'),
      ('90000000-0000-0000-0000-000000000022', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000022', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 3, 'counted', 1, null, repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000022'),
      ('90000000-0000-0000-0000-000000000023', '10000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000023', '50000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000003', 3, 'problem', null, 'footage_obscured', repeat('a', 64), '40000000-0000-0000-0000-000000000001', 'fixture', '91000000-0000-0000-0000-000000000023');

    insert into public.consensus_runs (
      id, factory_id, chunk_id, review_round, resolver_version,
      resolver_parameters, status, resolved_total, support_count
    )
    values (
      'a0000000-0000-0000-0000-000000000021',
      '10000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      3,
      'two-counts-one-problem-fixture',
      '{"alignment_tolerance_ms": 1500}'::jsonb,
      'resolved',
      1,
      2
    );

    insert into public.consensus_events (
      id, factory_id, consensus_run_id, chunk_id, review_round,
      source_time_ms, support_count, provenance
    )
    values (
      'b0000000-0000-0000-0000-000000000021',
      '10000000-0000-0000-0000-000000000001',
      'a0000000-0000-0000-0000-000000000021',
      '50000000-0000-0000-0000-000000000001',
      3,
      500100,
      2,
      'majority'
    );

    insert into public.consensus_event_sources (
      factory_id, consensus_event_id, submission_id, review_action_id,
      assignment_id, chunk_id, review_round
    )
    values
      ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000021', '90000000-0000-0000-0000-000000000021', '80000000-0000-0000-0000-000000000021', '70000000-0000-0000-0000-000000000021', '50000000-0000-0000-0000-000000000001', 3),
      ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000021', '90000000-0000-0000-0000-000000000022', '80000000-0000-0000-0000-000000000022', '70000000-0000-0000-0000-000000000022', '50000000-0000-0000-0000-000000000001', 3);

    set constraints all immediate;
    if (select count(*) from public.review_submissions
        where review_round = 3 and result_type = 'problem') <> 1 then
      raise exception 'problem submission disappeared from resolved round';
    end if;
    raise exception 'two-counts-one-problem fixture accepted';
  exception when raise_exception then
    if sqlerrm <> 'two-counts-one-problem fixture accepted' then
      raise;
    end if;
  end;
end;
$$;

set constraints all deferred;

insert into public.consensus_runs (
  id, factory_id, chunk_id, review_round, resolver_version, status,
  resolver_parameters, resolved_total, support_count
)
values (
  'a0000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  1,
  'fixture-v1',
  'resolved',
  '{"alignment_tolerance_ms": 1500}'::jsonb,
  1,
  2
);

insert into public.consensus_events (
  id, factory_id, consensus_run_id, chunk_id, review_round, source_time_ms,
  support_count, provenance
)
values (
  'b0000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  'a0000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  1,
  100100,
  2,
  'majority'
);

do $$
begin
  begin
    insert into public.consensus_events (
      id, factory_id, consensus_run_id, chunk_id, review_round,
      source_time_ms, support_count, provenance
    )
    values (
      'b0000000-0000-0000-0000-000000000091',
      '10000000-0000-0000-0000-000000000001',
      'a0000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      1,
      100900,
      2,
      'majority'
    );
    insert into public.consensus_event_sources (
      factory_id, consensus_event_id, submission_id, review_action_id,
      assignment_id, chunk_id, review_round
    )
    values
      ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000091', '90000000-0000-0000-0000-000000000001', '80000000-0000-0000-0000-000000000005', '70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 1),
      ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000091', '90000000-0000-0000-0000-000000000002', '80000000-0000-0000-0000-000000000002', '70000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', 1);
    set constraints consensus_events_validate, consensus_event_sources_validate immediate;
    raise exception 'undone tally unexpectedly accepted as lineage';
  exception when check_violation then
    if sqlerrm <> 'consensus event lacks matching human source lineage' then
      raise;
    end if;
  end;
end;
$$;

set constraints consensus_events_validate, consensus_event_sources_validate deferred;

do $$
begin
  begin
    insert into public.consensus_events (
      id, factory_id, consensus_run_id, chunk_id, review_round,
      source_time_ms, support_count, provenance
    )
    values (
      'b0000000-0000-0000-0000-000000000092',
      '10000000-0000-0000-0000-000000000001',
      'a0000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      1,
      100200,
      2,
      'majority'
    );
    insert into public.consensus_event_sources (
      factory_id, consensus_event_id, submission_id, review_action_id,
      assignment_id, chunk_id, review_round
    )
    values
      ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000092', '90000000-0000-0000-0000-000000000001', '80000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 1),
      ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000092', '90000000-0000-0000-0000-000000000003', '80000000-0000-0000-0000-000000000003', '70000000-0000-0000-0000-000000000003', '50000000-0000-0000-0000-000000000001', 1);
    set constraints consensus_events_validate, consensus_event_sources_validate immediate;
    raise exception 'dissenting total unexpectedly accepted as lineage';
  exception when check_violation then
    if sqlerrm <> 'consensus event lacks matching human source lineage' then
      raise;
    end if;
  end;
end;
$$;

set constraints consensus_events_validate, consensus_event_sources_validate deferred;

do $$
begin
  begin
    insert into public.consensus_events (
      id, factory_id, consensus_run_id, chunk_id, review_round,
      source_time_ms, support_count, provenance
    )
    values (
      'b0000000-0000-0000-0000-000000000093',
      '10000000-0000-0000-0000-000000000001',
      'a0000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      1,
      400000,
      2,
      'majority'
    );
    insert into public.consensus_event_sources (
      factory_id, consensus_event_id, submission_id, review_action_id,
      assignment_id, chunk_id, review_round
    )
    values
      ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000093', '90000000-0000-0000-0000-000000000001', '80000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 1),
      ('10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000093', '90000000-0000-0000-0000-000000000002', '80000000-0000-0000-0000-000000000002', '70000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', 1);
    set constraints consensus_events_validate, consensus_event_sources_validate immediate;
    raise exception 'out-of-tolerance actions unexpectedly accepted as lineage';
  exception when check_violation then
    if sqlerrm <> 'consensus event lacks matching human source lineage' then
      raise;
    end if;
  end;
end;
$$;

set constraints consensus_events_validate, consensus_event_sources_validate deferred;

insert into public.consensus_event_sources (
  id, factory_id, consensus_event_id, submission_id, review_action_id,
  assignment_id, chunk_id, review_round
)
values
  ('c0000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000001', '80000000-0000-0000-0000-000000000001', '70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 1),
  ('c0000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', '90000000-0000-0000-0000-000000000002', '80000000-0000-0000-0000-000000000002', '70000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', 1);

do $$
begin
  begin
    insert into public.consensus_events (
      id, factory_id, consensus_run_id, chunk_id, review_round,
      source_time_ms, support_count, provenance
    )
    values (
      'b0000000-0000-0000-0000-000000000090',
      '10000000-0000-0000-0000-000000000001',
      'a0000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      1,
      100300,
      2,
      'majority'
    );
    insert into public.consensus_event_sources (
      factory_id, consensus_event_id, submission_id, review_action_id,
      assignment_id, chunk_id, review_round
    )
    values (
      '10000000-0000-0000-0000-000000000001',
      'b0000000-0000-0000-0000-000000000090',
      '90000000-0000-0000-0000-000000000001',
      '80000000-0000-0000-0000-000000000001',
      '70000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      1
    );
    raise exception 'review action unexpectedly sourced two consensus events';
  exception when unique_violation then
    if sqlerrm not like '%consensus_event_sources_unique_action_idx%' then
      raise;
    end if;
  end;
end;
$$;

do $$
begin
  begin
    insert into public.consensus_runs (
      id, factory_id, chunk_id, review_round, resolver_version, status
    )
    values (
      'a0000000-0000-0000-0000-000000000099',
      '10000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      1,
      'invalid-pending-event',
      'pending_seam'
    );
    insert into public.consensus_events (
      id, factory_id, consensus_run_id, chunk_id, review_round,
      source_time_ms, support_count, provenance
    )
    values (
      'b0000000-0000-0000-0000-000000000099',
      '10000000-0000-0000-0000-000000000001',
      'a0000000-0000-0000-0000-000000000099',
      '50000000-0000-0000-0000-000000000001',
      1,
      300000,
      2,
      'majority'
    );
    set constraints consensus_events_validate immediate;
    raise exception 'event on unresolved consensus unexpectedly succeeded';
  exception when check_violation then
    if sqlerrm <> 'consensus events require a resolved run' then
      raise;
    end if;
  end;
end;
$$;

set constraints all immediate;
set constraints
  human_finalizations_cardinality,
  resolved_human_events_cardinality
deferred;

do $$
begin
  begin
    insert into public.human_finalizations (
      id, factory_id, chunk_id, review_round, consensus_run_id
    )
    values (
      'd0000000-0000-0000-0000-000000000099',
      '10000000-0000-0000-0000-000000000001',
      '50000000-0000-0000-0000-000000000001',
      1,
      'a0000000-0000-0000-0000-000000000001'
    );
    set constraints human_finalizations_cardinality immediate;
    raise exception 'partial finalization unexpectedly succeeded';
  exception when check_violation then
    if sqlerrm <> 'published event count does not match finalized consensus' then
      raise;
    end if;
  end;
end;
$$;

set constraints
  human_finalizations_cardinality,
  resolved_human_events_cardinality
deferred;

insert into public.human_finalizations (
  id, factory_id, chunk_id, review_round, consensus_run_id
)
values (
  'd0000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  1,
  'a0000000-0000-0000-0000-000000000001'
);

insert into public.resolved_human_count_events (
  id, factory_id, chunk_id, finalization_id, consensus_event_id,
  source_time_ms, publication_status, published_at
)
values (
  'e0000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  'd0000000-0000-0000-0000-000000000001',
  'b0000000-0000-0000-0000-000000000001',
  100100,
  'published',
  now()
);

set constraints all immediate;

insert into public.internal_review_cases (
  id, factory_id, chunk_id, review_round, sequence, event_type, reason_code,
  actor_user_id
)
values (
  'f0000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  1,
  1,
  'opened',
  'fixture-verification',
  '60000000-0000-0000-0000-000000000004'
);

insert into public.audit_log (
  id, factory_id, actor_user_id, actor_type, action, target_type, target_id,
  correlation_id
)
values (
  'f1000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '60000000-0000-0000-0000-000000000004',
  'user',
  'fixture.verify',
  'video_chunk',
  '50000000-0000-0000-0000-000000000001',
  'f2000000-0000-0000-0000-000000000001'
);

do $$
declare
  target record;
begin
  for target in
    select *
    from (values
      ('review_actions', '80000000-0000-0000-0000-000000000001'::uuid),
      ('review_submissions', '90000000-0000-0000-0000-000000000001'::uuid),
      ('consensus_runs', 'a0000000-0000-0000-0000-000000000001'::uuid),
      ('consensus_events', 'b0000000-0000-0000-0000-000000000001'::uuid),
      ('consensus_event_sources', 'c0000000-0000-0000-0000-000000000001'::uuid),
      ('human_finalizations', 'd0000000-0000-0000-0000-000000000001'::uuid),
      ('resolved_human_count_events', 'e0000000-0000-0000-0000-000000000001'::uuid),
      ('internal_review_cases', 'f0000000-0000-0000-0000-000000000001'::uuid),
      ('audit_log', 'f1000000-0000-0000-0000-000000000001'::uuid)
    ) as rows(table_name, row_id)
  loop
    begin
      execute format('update public.%I set id = id where id = $1', target.table_name)
      using target.row_id;
      raise exception '% update unexpectedly succeeded', target.table_name;
    exception when sqlstate '55000' then
      if sqlerrm <> target.table_name || ' is append-only' then
        raise;
      end if;
    end;

    begin
      execute format('delete from public.%I where id = $1', target.table_name)
      using target.row_id;
      raise exception '% delete unexpectedly succeeded', target.table_name;
    exception when sqlstate '55000' then
      if sqlerrm <> target.table_name || ' is append-only' then
        raise;
      end if;
    end;
  end loop;
end;
$$;

do $$
begin
  begin
    truncate public.audit_log;
    raise exception 'audit_log truncate unexpectedly succeeded';
  exception when sqlstate '55000' then
    if sqlerrm <> 'audit_log is append-only' then
      raise;
    end if;
  end;
end;
$$;

-- Temporary grants make the following reads exercise RLS rather than grant denial.
grant select on public.media_objects, public.consensus_events to authenticated;

set local role authenticated;
select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);

do $$
begin
  if (select count(*) from public.review_assignments) <> 1 then
    raise exception 'reviewer assignment RLS did not return exactly one own row';
  end if;
  if (select count(*) from public.review_submissions) <> 1 then
    raise exception 'reviewer submission RLS did not return exactly one own row';
  end if;
  if (select count(*) from public.review_submissions where reviewer_id <> auth.uid()) <> 0 then
    raise exception 'reviewer can read peer submissions';
  end if;
  if (select count(*) from public.review_actions) <> 3 then
    raise exception 'reviewer action RLS did not return exactly three own action rows';
  end if;
  if (select count(*) from public.media_objects) <> 0 then
    raise exception 'reviewer RLS exposed media metadata';
  end if;
  if has_schema_privilege('authenticated', 'private', 'usage') then
    raise exception 'authenticated role unexpectedly has private schema usage';
  end if;
end;
$$;

reset role;
update public.profiles
set status = 'disabled'
where id = '60000000-0000-0000-0000-000000000001';

select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);
set local role authenticated;

do $$
begin
  if (select count(*) from public.review_assignments) <> 0
     or (select count(*) from public.review_actions) <> 0
     or (select count(*) from public.review_submissions) <> 0 then
    raise exception 'disabled reviewer retained review access';
  end if;
end;
$$;

reset role;
update public.profiles
set status = 'active'
where id = '60000000-0000-0000-0000-000000000001';

select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000005","role":"authenticated"}',
  true
);
set local role authenticated;

do $$
begin
  if (select count(*) from public.review_assignments) <> 0 then
    raise exception 'cross-tenant reviewer can read first-factory assignments';
  end if;
  if (select count(*) from public.review_submissions) <> 0 then
    raise exception 'cross-tenant reviewer can read first-factory submissions';
  end if;
end;
$$;

reset role;
select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000004","role":"authenticated"}',
  true
);
set local role authenticated;

do $$
begin
  if (select count(*) from public.resolved_human_count_events) <> 1 then
    raise exception 'owner cannot read the published human projection';
  end if;
  if (select count(*) from public.factories) <> 1
     or (select count(*) from public.stations) <> 1 then
    raise exception 'active owner cannot read own factory metadata';
  end if;
  if (select count(*) from public.consensus_events) <> 0 then
    raise exception 'owner RLS exposed raw consensus';
  end if;
end;
$$;

reset role;
select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000006","role":"authenticated"}',
  true
);
set local role authenticated;

do $$
begin
  if (select count(*) from public.resolved_human_count_events) <> 0 then
    raise exception 'cross-tenant owner can read first-factory projection';
  end if;
end;
$$;

reset role;
update public.profiles
set status = 'disabled'
where id = '60000000-0000-0000-0000-000000000004';

select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000004","role":"authenticated"}',
  true
);
set local role authenticated;

do $$
begin
  if (select count(*) from public.resolved_human_count_events) <> 0
     or (select count(*) from public.factories) <> 0
     or (select count(*) from public.stations) <> 0 then
    raise exception 'disabled owner retained tenant access';
  end if;
end;
$$;

reset role;

create temporary table phase1_fixture_result (
  phase1_live_fixture text not null,
  private_buckets_verified boolean not null,
  private_schema_denied boolean not null,
  anon_assignments_denied boolean not null,
  service_role_truncate_denied boolean not null
) on commit drop;

do $$
declare
  ledger text;
begin
  if (
    select count(*) <> 3 or not bool_and(public = false)
    from storage.buckets
    where id in ('factory-originals', 'review-renditions', 'evidence-clips')
  ) then
    raise exception 'private bucket invariant failed';
  end if;
  if has_schema_privilege('authenticated', 'private', 'usage') then
    raise exception 'private schema invariant failed';
  end if;
  if has_table_privilege('anon', 'public.review_assignments', 'select') then
    raise exception 'anonymous assignment grant invariant failed';
  end if;

  foreach ledger in array array[
    'review_actions',
    'review_submissions',
    'consensus_runs',
    'consensus_events',
    'consensus_event_sources',
    'human_finalizations',
    'resolved_human_count_events',
    'internal_review_cases',
    'audit_log'
  ]
  loop
    if has_table_privilege('service_role', 'public.' || ledger, 'truncate') then
      raise exception 'service_role retained truncate on %', ledger;
    end if;
  end loop;

  insert into phase1_fixture_result
  values ('pass', true, true, true, true);
end;
$$;

select * from phase1_fixture_result;

rollback;
