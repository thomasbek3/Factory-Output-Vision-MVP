-- Owner V2 tenant and durable project fixture. All writes roll back.
begin;

insert into auth.users (id, instance_id, aud, role, email, created_at, updated_at)
values
  ('61000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'owner-a@example.invalid', now(), now()),
  ('61000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'owner-b@example.invalid', now(), now()),
  ('61000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'owner-disabled@example.invalid', now(), now()),
  ('61000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'reviewer@example.invalid', now(), now()),
  ('61000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'ops@example.invalid', now(), now());

insert into public.factories (id, name, timezone, is_test)
values
  ('11000000-0000-0000-0000-000000000001', 'Owner V2 fixture A', 'America/Los_Angeles', true),
  ('11000000-0000-0000-0000-000000000002', 'Owner V2 fixture B', 'America/New_York', false);

insert into public.profiles (id, display_name, locale, status)
values
  ('61000000-0000-0000-0000-000000000001', 'Owner A', 'en', 'active'),
  ('61000000-0000-0000-0000-000000000002', 'Owner B', 'en', 'active'),
  ('61000000-0000-0000-0000-000000000003', 'Disabled owner', 'en', 'disabled'),
  ('61000000-0000-0000-0000-000000000004', 'Reviewer', 'en', 'active'),
  ('61000000-0000-0000-0000-000000000005', 'Ops', 'en', 'active');

insert into public.factory_memberships (factory_id, user_id, role, status)
values
  ('11000000-0000-0000-0000-000000000001', '61000000-0000-0000-0000-000000000001', 'owner', 'active'),
  ('11000000-0000-0000-0000-000000000002', '61000000-0000-0000-0000-000000000002', 'owner', 'active'),
  ('11000000-0000-0000-0000-000000000001', '61000000-0000-0000-0000-000000000003', 'owner', 'active'),
  ('11000000-0000-0000-0000-000000000001', '61000000-0000-0000-0000-000000000004', 'reviewer', 'active'),
  ('11000000-0000-0000-0000-000000000001', '61000000-0000-0000-0000-000000000005', 'ops', 'active');

insert into public.reviewer_lifecycles (
  user_id, factory_id, email, state, is_test_account
)
values (
  '61000000-0000-0000-0000-000000000004',
  '11000000-0000-0000-0000-000000000001',
  'reviewer@example.invalid',
  'active',
  true
);

insert into public.stations (id, factory_id, alias, status)
values
  (
    '21000000-0000-0000-0000-000000000001',
    '11000000-0000-0000-0000-000000000001',
    'Pallet A',
    'active'
  ),
  (
    '21000000-0000-0000-0000-000000000002',
    '11000000-0000-0000-0000-000000000001',
    'Pallet B',
    'active'
  );

insert into public.media_objects (
  id, factory_id, station_id, bucket_id, object_path, object_sha256,
  source_sha256, content_type, byte_size, duration_ms, status,
  retention_until, verified_at
) values (
  '31000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  'evidence-clips',
  'owner-v2-fixture/evidence-001.mp4',
  repeat('a', 64),
  repeat('b', 64),
  'video/mp4',
  1024,
  15000,
  'verified',
  '2026-08-30T00:00:00Z',
  now()
), (
  '31000000-0000-0000-0000-000000000002',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  'evidence-clips',
  'owner-v2-fixture/teardown-evidence.mp4',
  repeat('c', 64),
  repeat('d', 64),
  'video/mp4',
  2048,
  15000,
  'verified',
  '2026-08-30T00:00:00Z',
  now()
);

insert into storage.objects (bucket_id, name, owner_id, metadata)
values
  (
    'evidence-clips',
    'owner-v2-fixture/evidence-001.mp4',
    '61000000-0000-0000-0000-000000000001',
    '{"mimetype":"video/mp4","size":1024}'::jsonb
  ),
  (
    'evidence-clips',
    'owner-v2-fixture/teardown-evidence.mp4',
    '61000000-0000-0000-0000-000000000001',
    '{"mimetype":"video/mp4","size":2048}'::jsonb
  );

do $$
declare
  fall_back_ms bigint;
  spring_forward_ms bigint;
  fall_back_interior_ms bigint;
  spring_forward_interior_ms bigint;
begin
  fall_back_ms := public.owner_scheduled_work_milliseconds(
    '2026-11-01T07:00:00Z',
    '2026-11-01T18:00:00Z',
    '{"timezone":"America/Los_Angeles","shifts":[{"weekday":7,"start":"01:00","end":"09:00"}]}'::jsonb
  );
  spring_forward_ms := public.owner_scheduled_work_milliseconds(
    '2026-03-08T08:00:00Z',
    '2026-03-08T17:00:00Z',
    '{"timezone":"America/Los_Angeles","shifts":[{"weekday":7,"start":"02:00","end":"09:00"}]}'::jsonb
  );
  fall_back_interior_ms := public.owner_scheduled_work_milliseconds(
    '2026-11-01T07:00:00Z',
    '2026-11-01T18:00:00Z',
    '{"timezone":"America/Los_Angeles","shifts":[{"weekday":7,"start":"01:30","end":"09:00"}]}'::jsonb
  );
  spring_forward_interior_ms := public.owner_scheduled_work_milliseconds(
    '2026-03-08T08:00:00Z',
    '2026-03-08T17:00:00Z',
    '{"timezone":"America/Los_Angeles","shifts":[{"weekday":7,"start":"02:30","end":"09:00"}]}'::jsonb
  );
  if fall_back_ms <> 28800000 then
    raise exception 'fall-back boundary did not use later disambiguation: %',
      fall_back_ms;
  end if;
  if spring_forward_ms <> 21600000 then
    raise exception 'spring-forward boundary did not use later disambiguation: %',
      spring_forward_ms;
  end if;
  if fall_back_interior_ms <> 27000000 then
    raise exception 'fall-back interior did not use later disambiguation: %',
      fall_back_interior_ms;
  end if;
  if spring_forward_interior_ms <> 19800000 then
    raise exception 'spring-forward interior did not use later disambiguation: %',
      spring_forward_interior_ms;
  end if;
end;
$$;

select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);
set local role authenticated;

select public.owner_upsert_worker(
  '11000000-0000-0000-0000-000000000001',
  null,
  'Fixture Worker',
  'FV-001',
  'active',
  true,
  'Operator',
  true
);
select public.owner_upsert_worker(
  '11000000-0000-0000-0000-000000000001',
  null,
  'Code-less Worker One',
  null,
  'active'
);
select public.owner_upsert_worker(
  '11000000-0000-0000-0000-000000000001',
  null,
  'Code-less Worker Two',
  null,
  'active'
);

select public.owner_start_project(
  '11000000-0000-0000-0000-000000000001',
  'Smoke Test Fixtures Inc. Run',
  'Smoke Test Fixtures Inc.',
  400,
  250,
  75,
  2250,
  19125,
  '2026-07-28T16:00:00Z',
  '2026-07-29T00:30:00Z',
  '{"timezone":"America/Los_Angeles","shifts":[{"weekday":2,"start":"09:00","end":"17:30"}]}'::jsonb,
  2500,
  'open',
  '21000000-0000-0000-0000-000000000001',
  (
    select array_agg(worker.id)
    from public.owner_workers worker
    where worker.employee_code = 'FV-001'
  )
);

-- Entitled owner baseline must be non-zero before denial checks.
do $$
declare
  dashboard_truth jsonb;
  history_options jsonb;
begin
  if (select count(*) from public.owner_projects) <> 1 then
    raise exception 'entitled owner baseline is not visible';
  end if;
  if (select count(*) from public.owner_project_audit) <> 4 then
    raise exception 'owner project creation was not audited';
  end if;
  if (
    select count(*)
    from public.owner_workers
    where employee_code is null
  ) <> 2 then
    raise exception 'multiple code-less workers were not persisted';
  end if;
  if (select count(*) from public.owner_project_station_assignments) <> 1 then
    raise exception 'project start did not create its station assignment';
  end if;
  if (select count(*) from public.owner_worker_station_intervals) <> 1 then
    raise exception 'project start did not create its worker interval';
  end if;
  dashboard_truth := public.owner_dashboard_truth(
    '11000000-0000-0000-0000-000000000001',
    '2026-07-28T20:00:00Z'
  );
  if jsonb_typeof(dashboard_truth) <> 'object'
    or jsonb_typeof(dashboard_truth -> 'assignments') <> 'array'
    or jsonb_typeof(dashboard_truth -> 'events') <> 'array'
    or jsonb_array_length(dashboard_truth -> 'assignments') <> 1
  then
    raise exception 'bounded owner dashboard truth is malformed';
  end if;
  history_options := public.owner_history_filter_options(
    '11000000-0000-0000-0000-000000000001'
  );
  if jsonb_typeof(history_options) <> 'object'
    or jsonb_typeof(history_options -> 'projects') <> 'array'
  then
    raise exception 'bounded owner history options are malformed';
  end if;
  begin
    perform public.owner_dashboard_truth(
      '11000000-0000-0000-0000-000000000002',
      '2026-07-28T20:00:00Z'
    );
    raise exception 'owner read another factory dashboard truth';
  exception when insufficient_privilege then
    null;
  end;
  if (select count(*) from public.resolved_human_count_events) <> 0 then
    raise exception 'raw resolved human events remained owner-readable';
  end if;
  begin
    perform public.ops_assert_access(null);
    raise exception 'owner reached ops authorization';
  exception when insufficient_privilege then
    null;
  end;
  begin
    perform public.worker_authorize_reviewer_session();
    raise exception 'owner reached reviewer authorization';
  exception when insufficient_privilege then
    null;
  end;
end;
$$;

-- Invalid calendars and overlapping station assignments fail atomically.
do $$
declare
  project_id uuid;
begin
  select id into project_id from public.owner_projects limit 1;

  begin
    perform public.owner_start_project(
      '11000000-0000-0000-0000-000000000001',
      'Invalid Calendar',
      'Smoke Test Fixtures Inc.',
      10, 250, 75, 2250, 1000,
      '2026-07-28T16:00:00Z',
      '2026-07-29T00:30:00Z',
      '{"timezone":"America/Los_Angeles","shifts":[{"weekday":2,"start":"09:00","end":"12:00"},{"weekday":2,"start":"11:00","end":"13:00"}]}'::jsonb,
      2500, 'open',
      '21000000-0000-0000-0000-000000000001',
      (
        select array_agg(worker.id)
        from public.owner_workers worker
        where worker.employee_code = 'FV-001'
      )
    );
    raise exception 'overlapping shift calendar was accepted';
  exception when check_violation then
    null;
  end;

  begin
    perform public.owner_start_project(
      '11000000-0000-0000-0000-000000000001',
      'Overlapping Project',
      'Smoke Test Fixtures Inc.',
      10, 250, 75, 2250, 18000,
      '2026-07-28T17:00:00Z',
      '2026-07-29T01:00:00Z',
      '{"timezone":"America/Los_Angeles","shifts":[{"weekday":2,"start":"10:00","end":"18:00"}]}'::jsonb,
      2500, 'open',
      '21000000-0000-0000-0000-000000000001',
      (
        select array_agg(worker.id)
        from public.owner_workers worker
        where worker.employee_code = 'FV-001'
      )
    );
    raise exception 'overlapping station project was accepted';
  exception when exclusion_violation then
    null;
  end;

  begin
    perform public.owner_start_project(
      '11000000-0000-0000-0000-000000000001',
      'Overlapping Worker',
      'Smoke Test Fixtures Inc.',
      10, 250, 75, 2250, 18000,
      '2026-07-28T17:00:00Z',
      '2026-07-29T01:00:00Z',
      '{"timezone":"America/Los_Angeles","shifts":[{"weekday":2,"start":"10:00","end":"18:00"}]}'::jsonb,
      2500, 'open',
      '21000000-0000-0000-0000-000000000002',
      (
        select array_agg(worker.id)
        from public.owner_workers worker
        where worker.employee_code = 'FV-001'
      )
    );
    raise exception 'overlapping worker interval was accepted';
  exception when exclusion_violation then
    null;
  end;

  if (select count(*) from public.owner_projects) <> 1 then
    raise exception 'failed project starts left partial rows';
  end if;
end;
$$;

do $$
begin
  begin
    perform public.owner_close_project(
      '11000000-0000-0000-0000-000000000001',
      (
        select id
        from public.owner_projects
        where name = 'Smoke Test Fixtures Inc. Run'
      ),
      25000,
      now() + interval '1 day'
    );
    raise exception 'future project completion was accepted';
  exception when check_violation then
    null;
  end;
  if (
    select status
    from public.owner_projects
    where name = 'Smoke Test Fixtures Inc. Run'
  ) <> 'open' then
    raise exception 'rejected future completion changed the project';
  end if;
end;
$$;

select public.owner_record_downtime(
  '11000000-0000-0000-0000-000000000001',
  (
    select id from public.owner_projects
    where name = 'Smoke Test Fixtures Inc. Run'
  ),
  '21000000-0000-0000-0000-000000000001',
  '2026-07-28T18:00:00Z',
  '2026-07-28T18:15:00Z',
  'equipment_breakdown',
  'Fixture press jam'
);

do $$
begin
  if (
    select count(*)
    from public.owner_station_downtime_intervals
    where reason_code = 'equipment_breakdown'
  ) <> 1 then
    raise exception 'audited owner downtime was not recorded';
  end if;
  if (
    select count(*)
    from public.owner_project_audit
    where action = 'owner.project.downtime_recorded'
  ) <> 1 then
    raise exception 'owner downtime audit event is missing';
  end if;
  begin
    perform public.owner_record_downtime(
      '11000000-0000-0000-0000-000000000001',
      (
        select id from public.owner_projects
        where name = 'Smoke Test Fixtures Inc. Run'
      ),
      '21000000-0000-0000-0000-000000000001',
      '2026-07-28T18:10:00Z',
      '2026-07-28T18:20:00Z',
      'maintenance',
      null
    );
    raise exception 'overlapping owner downtime was accepted';
  exception when exclusion_violation then
    null;
  end;
  begin
    perform public.owner_record_downtime(
      '11000000-0000-0000-0000-000000000001',
      (
        select id from public.owner_projects
        where name = 'Smoke Test Fixtures Inc. Run'
      ),
      '21000000-0000-0000-0000-000000000002',
      '2026-07-28T18:30:00Z',
      '2026-07-28T18:45:00Z',
      'material_shortage',
      null
    );
    raise exception 'downtime outside the assigned station was accepted';
  exception when check_violation then
    null;
  end;
end;
$$;

reset role;
set local role service_role;
select public.service_attach_owner_project_evidence(
  '11000000-0000-0000-0000-000000000001',
  (
    select id
    from public.owner_projects
    where name = 'Smoke Test Fixtures Inc. Run'
  ),
  '31000000-0000-0000-0000-000000000001',
  'closeout-verification'
);
reset role;
select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);
set local role authenticated;

select public.owner_close_project(
  '11000000-0000-0000-0000-000000000001',
  (select id from public.owner_projects limit 1),
  25000,
  '2026-07-29T00:00:00Z'
);

do $$
declare
  closeout public.owner_project_closeouts%rowtype;
begin
  select * into closeout from public.owner_project_closeouts;
  if closeout.revision <> 1
     or closeout.planned_units <> 400
     or closeout.planned_direct_labor_cents <> 19125
     or closeout.planned_material_cost_cents <> 30000
     or closeout.planned_margin_after_direct_costs_cents <> 50875
     or closeout.verified_good_units <> 0
     or closeout.production_value_cents <> 0
     or closeout.material_cost_cents <> 25000
     or closeout.direct_labor_cents <> 18000
     or closeout.margin_after_direct_costs_cents <> -43000
     or closeout.snapshot ->> 'actual_material_cost_source' <> 'owner_entered'
     or (closeout.snapshot ->> 'evidence_clip_count')::integer <> 1
     or (closeout.snapshot ->> 'evidence_retention_until')::timestamptz
       is distinct from '2026-08-30T00:00:00Z'::timestamptz
  then
    raise exception 'closeout economics are not exact';
  end if;
  if (select status from public.owner_projects limit 1) <> 'closed' then
    raise exception 'closeout did not close project';
  end if;
  if exists (
    select 1 from public.owner_worker_station_intervals
    where effective_end is distinct from '2026-07-29T00:00:00Z'
  ) then
    raise exception 'closeout did not stop labor accrual';
  end if;
  if (select count(*) from public.owner_project_audit) <> 6 then
    raise exception 'closeout audit event is missing';
  end if;
  if (
    select count(*)
    from public.owner_history_evidence(
      '11000000-0000-0000-0000-000000000001',
      closeout.id
    )
  ) <> 1 then
    raise exception 'owner closeout evidence route returned the wrong snapshot';
  end if;
  if not public.can_read_owner_evidence(
    'evidence-clips',
    'owner-v2-fixture/evidence-001.mp4'
  ) then
    raise exception 'owner evidence authorization rejected retained evidence';
  end if;
  if (
    select count(*)
    from storage.objects
    where bucket_id = 'evidence-clips'
      and name = 'owner-v2-fixture/evidence-001.mp4'
  ) <> 1 then
    raise exception 'owner could not read its retained storage object';
  end if;

  begin
    update public.owner_project_closeouts
    set material_cost_cents = 0;
    raise exception 'closeout update was accepted';
  exception
    when insufficient_privilege or sqlstate '55000' then
    null;
  end;
  begin
    delete from public.owner_project_closeouts;
    raise exception 'closeout delete was accepted';
  exception
    when insufficient_privilege or sqlstate '55000' then
    null;
  end;
end;
$$;

reset role;
update public.media_objects
set status = 'quarantined',
    retention_until = '2099-12-31T00:00:00Z'
where id = '31000000-0000-0000-0000-000000000001';
select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);
set local role authenticated;

do $$
declare
  first_closeout public.owner_project_closeouts%rowtype;
begin
  select *
  into first_closeout
  from public.owner_project_closeouts
  where revision = 1
    and project_id = (
      select id
      from public.owner_projects
      where name = 'Smoke Test Fixtures Inc. Run'
    );
  if (
    select evidence.retention_until
    from public.owner_history_evidence(
      '11000000-0000-0000-0000-000000000001',
      first_closeout.id
    ) evidence
  ) is distinct from '2026-08-30T00:00:00Z'::timestamptz then
    raise exception 'mutable media retention changed the closeout evidence snapshot';
  end if;
  if (first_closeout.snapshot ->> 'evidence_retention_until')::timestamptz
     is distinct from '2026-08-30T00:00:00Z'::timestamptz then
    raise exception 'mutable media retention changed the closeout snapshot';
  end if;
  if public.can_read_owner_evidence(
    'evidence-clips',
    'owner-v2-fixture/evidence-001.mp4'
  ) then
    raise exception 'quarantined owner evidence remained readable';
  end if;
  if (
    select count(*)
    from storage.objects
    where bucket_id = 'evidence-clips'
      and name = 'owner-v2-fixture/evidence-001.mp4'
  ) <> 0 then
    raise exception 'quarantined evidence survived storage RLS';
  end if;
  if (
    select count(*)
    from public.owner_history_evidence(
      '11000000-0000-0000-0000-000000000001',
      first_closeout.id
    )
    where status = 'quarantined'
  ) <> 1 then
    raise exception 'quarantined evidence disappeared from immutable history';
  end if;
end;
$$;

select public.owner_correct_closeout(
  '11000000-0000-0000-0000-000000000001',
  (
    select id
    from public.owner_projects
    where name = 'Smoke Test Fixtures Inc. Run'
  ),
  'correction',
  2,
  'missed-output',
  'Verified against retained evidence.',
  '2026-07-28T20:00:00Z',
  26000
);
do $$
declare
  first_revision public.owner_project_closeouts%rowtype;
  second_revision public.owner_project_closeouts%rowtype;
begin
  select * into first_revision
  from public.owner_project_closeouts
  where revision = 1
    and project_id = (
      select id from public.owner_projects
      where name = 'Smoke Test Fixtures Inc. Run'
    );
  select * into second_revision
  from public.owner_project_closeouts
  where revision = 2
    and project_id = first_revision.project_id;
  if first_revision.margin_after_direct_costs_cents <> -43000
     or second_revision.verified_good_units <> 2
     or second_revision.production_value_cents <> 500
     or second_revision.material_cost_cents <> 26000
     or second_revision.direct_labor_cents <> 18000
     or second_revision.margin_after_direct_costs_cents <> -43500
     or second_revision.snapshot ->> 'supersedes_closeout_id'
       <> first_revision.id::text
     or (
       select coalesce(sum((bucket->>'actual_units')::integer), 0)
       from jsonb_array_elements(
         second_revision.snapshot->'weekly_output'
       ) bucket
     ) <> second_revision.verified_good_units
  then
    raise exception 'closeout correction did not append exact revision 2';
  end if;
  if (select count(*) from public.owner_output_adjustments) <> 1 then
    raise exception 'closeout correction adjustment is missing';
  end if;
  if (
    select count(*)
    from (
      select evidence.id
      from public.owner_history_evidence(
        '11000000-0000-0000-0000-000000000001',
        first_revision.id
      ) evidence
      union all
      select evidence.id
      from public.owner_history_evidence(
        '11000000-0000-0000-0000-000000000001',
        second_revision.id
      ) evidence
    ) revision_evidence
  ) <> 2 then
    raise exception 'closeout correction did not preserve evidence snapshot';
  end if;
  if (select count(*) from public.owner_project_audit) <> 7 then
    raise exception 'closeout correction audit is missing';
  end if;

  begin
    update public.owner_output_adjustments
    set note = 'mutated';
    raise exception 'output adjustment update was accepted';
  exception
    when insufficient_privilege or sqlstate '55000' then
    null;
  end;
  begin
    delete from public.owner_output_adjustments;
    raise exception 'output adjustment delete was accepted';
  exception
    when insufficient_privilege or sqlstate '55000' then
    null;
  end;

  begin
    perform public.owner_correct_closeout(
      '11000000-0000-0000-0000-000000000001',
      first_revision.project_id,
      'scrap',
      -3,
      'invalid-underflow',
      null,
      '2026-07-28T20:00:00Z',
      null
    );
    raise exception 'negative corrected good-unit total was accepted';
  exception when check_violation then
    null;
  end;
  if (
    select count(*)
    from public.owner_project_closeouts
    where project_id = first_revision.project_id
  ) <> 2 then
    raise exception 'rejected correction left a closeout revision';
  end if;
end;
$$;

select public.owner_start_project(
  '11000000-0000-0000-0000-000000000001',
  'Multi-day shift-clamped run',
  'Smoke Test Fixtures Inc.',
  400,
  250,
  75,
  2250,
  72000,
  '2026-07-20T16:00:00Z',
  '2026-07-24T00:00:00Z',
  '{"timezone":"America/Los_Angeles","shifts":[{"weekday":1,"start":"09:00","end":"17:00"},{"weekday":2,"start":"09:00","end":"17:00"},{"weekday":3,"start":"09:00","end":"17:00"},{"weekday":4,"start":"09:00","end":"17:00"},{"weekday":5,"start":"09:00","end":"17:00"}]}'::jsonb,
  2500,
  'open',
  '21000000-0000-0000-0000-000000000002',
  (
    select array_agg(worker.id)
    from public.owner_workers worker
    where worker.display_name = 'Code-less Worker One'
  )
);
select public.owner_close_project(
  '11000000-0000-0000-0000-000000000001',
  (
    select id
    from public.owner_projects
    where name = 'Multi-day shift-clamped run'
  ),
  0,
  '2026-07-23T00:00:00Z'
);

do $$
declare
  closeout public.owner_project_closeouts%rowtype;
begin
  select project_closeout.*
  into closeout
  from public.owner_project_closeouts project_closeout
  join public.owner_projects project
    on project.id = project_closeout.project_id
  where project.name = 'Multi-day shift-clamped run';
  if closeout.direct_labor_cents <> 54000
     or closeout.direct_labor_cents = 162000 then
    raise exception 'multi-day actual labor was not shift-clamped: %',
      closeout.direct_labor_cents;
  end if;
  if (select count(*) from public.owner_project_audit) <> 9 then
    raise exception 'multi-day start and close were not audited';
  end if;
end;
$$;

reset role;
select set_config(
  'factoryvision_test.owner_project_id',
  (
    select id::text
    from public.owner_projects
    where factory_id = '11000000-0000-0000-0000-000000000001'
      and name = 'Smoke Test Fixtures Inc. Run'
    limit 1
  ),
  true
);
select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000002","role":"authenticated"}',
  true
);
set local role authenticated;

-- Cross-tenant owner denied.
do $$
begin
  if (select count(*) from public.owner_projects) <> 0 then
    raise exception 'cross-tenant owner read another factory project';
  end if;
  if public.can_read_owner_evidence(
    'evidence-clips',
    'owner-v2-fixture/evidence-001.mp4'
  ) or (
    select count(*)
    from storage.objects
    where bucket_id = 'evidence-clips'
  ) <> 0 then
    raise exception 'cross-tenant owner read owner evidence';
  end if;
  begin
    perform public.owner_start_project(
      '11000000-0000-0000-0000-000000000002',
      'Forbidden production teardown run',
      'Fixture B',
      1,
      100,
      10,
      1000,
      1000,
      '2026-07-28T13:00:00Z',
      '2026-07-28T14:00:00Z',
      '{"timezone":"America/New_York","shifts":[{"weekday":2,"start":"09:00","end":"10:00"}]}'::jsonb,
      null,
      'open',
      null,
      null,
      '71000000-0000-0000-0000-000000000099'
    );
    raise exception 'production factory accepted a teardown correlation';
  exception when insufficient_privilege then
    null;
  end;
  begin
    perform public.owner_close_project(
      '11000000-0000-0000-0000-000000000001',
      current_setting('factoryvision_test.owner_project_id')::uuid,
      0,
      '2026-07-29T00:00:00Z'
    );
    raise exception 'cross-tenant owner mutated another factory';
  exception when insufficient_privilege then
    null;
  end;
end;
$$;

reset role;
select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000003","role":"authenticated"}',
  true
);
set local role authenticated;

-- Disabled owner denied.
do $$
begin
  if (select count(*) from public.owner_projects) <> 0 then
    raise exception 'disabled owner retained project access';
  end if;
  if public.can_read_owner_evidence(
    'evidence-clips',
    'owner-v2-fixture/evidence-001.mp4'
  ) or (
    select count(*) from storage.objects
    where bucket_id = 'evidence-clips'
  ) <> 0 then
    raise exception 'disabled owner retained evidence access';
  end if;
end;
$$;

reset role;
select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000004","role":"authenticated"}',
  true
);
set local role authenticated;

-- Reviewer remains authorized only for reviewer work.
do $$
declare
  owner_session jsonb;
  reviewer_session jsonb;
begin
  owner_session := public.owner_authorize_session(null);
  if (owner_session ->> 'authorized')::boolean then
    raise exception 'reviewer reached owner authorization';
  end if;
  if (select count(*) from public.owner_projects) <> 0 then
    raise exception 'reviewer read owner project rows';
  end if;
  if public.can_read_owner_evidence(
    'evidence-clips',
    'owner-v2-fixture/evidence-001.mp4'
  ) or (
    select count(*) from storage.objects
    where bucket_id = 'evidence-clips'
  ) <> 0 then
    raise exception 'reviewer read owner evidence';
  end if;
  begin
    perform public.ops_assert_access(null);
    raise exception 'reviewer reached ops authorization';
  exception when insufficient_privilege then
    null;
  end;
  reviewer_session := public.worker_authorize_reviewer_session();
  if not (reviewer_session ->> 'authorized')::boolean then
    raise exception 'reviewer lost reviewer authorization';
  end if;
end;
$$;

reset role;
select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000005","role":"authenticated"}',
  true
);
set local role authenticated;

-- Ops authorization remains independent from owner authorization.
do $$
declare
  owner_session jsonb;
begin
  owner_session := public.owner_authorize_session(null);
  if (owner_session ->> 'authorized')::boolean then
    raise exception 'ops reached owner authorization';
  end if;
  if (select count(*) from public.owner_projects) <> 0 then
    raise exception 'ops read owner project rows';
  end if;
  if public.can_read_owner_evidence(
    'evidence-clips',
    'owner-v2-fixture/evidence-001.mp4'
  ) or (
    select count(*) from storage.objects
    where bucket_id = 'evidence-clips'
  ) <> 0 then
    raise exception 'ops read owner evidence';
  end if;
  if not public.ops_assert_access(null) then
    raise exception 'ops lost ops authorization';
  end if;
end;
$$;

reset role;

select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);
set local role authenticated;

select public.owner_start_project(
  '11000000-0000-0000-0000-000000000001',
  'Correlated teardown fixture',
  'Smoke Test Fixtures Inc.',
  10,
  250,
  75,
  2250,
  4500,
  '2026-07-29T16:00:00Z',
  '2026-07-29T18:00:00Z',
  '{"timezone":"America/Los_Angeles","shifts":[{"weekday":3,"start":"09:00","end":"11:00"}]}'::jsonb,
  2500,
  'open',
  '21000000-0000-0000-0000-000000000001',
  (
    select array_agg(worker.id)
    from public.owner_workers worker
    where worker.employee_code = 'FV-001'
  ),
  '71000000-0000-0000-0000-000000000001'
);

do $$
begin
  begin
    perform public.owner_teardown_test_correlation(
      '11000000-0000-0000-0000-000000000001',
      '71000000-0000-0000-0000-000000000001'
    );
    raise exception 'authenticated user executed service teardown';
  exception when insufficient_privilege then
    null;
  end;
end;
$$;

reset role;
set local role service_role;
do $$
begin
  begin
    perform public.owner_teardown_test_correlation(
      '11000000-0000-0000-0000-000000000001',
      '71000000-0000-0000-0000-000000000009'
    );
    raise exception 'wrong teardown correlation was accepted';
  exception when insufficient_privilege then
    null;
  end;
end;
$$;
select public.service_attach_owner_project_evidence(
  '11000000-0000-0000-0000-000000000001',
  (
    select id
    from public.owner_projects
    where test_correlation_id =
      '71000000-0000-0000-0000-000000000001'
  ),
  '31000000-0000-0000-0000-000000000002',
  'teardown-verification'
);
reset role;
select set_config(
  'request.jwt.claims',
  '{"sub":"61000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);
set local role authenticated;
select public.owner_close_project(
  '11000000-0000-0000-0000-000000000001',
  (
    select id
    from public.owner_projects
    where test_correlation_id =
      '71000000-0000-0000-0000-000000000001'
  ),
  0,
  '2026-07-29T18:00:00Z'
);
select public.owner_correct_closeout(
  '11000000-0000-0000-0000-000000000001',
  (
    select id
    from public.owner_projects
    where test_correlation_id =
      '71000000-0000-0000-0000-000000000001'
  ),
  'correction',
  1,
  'teardown-fixture-correction',
  'Closed fixture exercises complete teardown.',
  '2026-07-29T17:00:00Z',
  0
);
reset role;
set local role service_role;
select public.owner_teardown_test_correlation(
  '11000000-0000-0000-0000-000000000001',
  '71000000-0000-0000-0000-000000000001'
);
reset role;

do $$
begin
  if exists (
    select 1
    from public.owner_projects
    where test_correlation_id =
      '71000000-0000-0000-0000-000000000001'
  ) then
    raise exception 'correlated test project survived teardown';
  end if;
  if not exists (
    select 1
    from public.owner_test_teardown_receipts
    where test_correlation_id =
      '71000000-0000-0000-0000-000000000001'
      and deleted_assignment_count = 1
      and deleted_worker_interval_count = 1
      and deleted_adjustment_count = 1
      and deleted_closeout_count = 2
      and deleted_project_evidence_count = 1
      and deleted_closeout_evidence_count = 2
      and deleted_audit_count = 3
  ) then
    raise exception 'test teardown receipt was not retained';
  end if;
  if (
    select count(*)
    from public.audit_log
    where action = 'owner.test_correlation.torn_down'
      and correlation_id =
        '71000000-0000-0000-0000-000000000001'
  ) <> 1 then
    raise exception 'durable teardown audit receipt was not retained';
  end if;
  if current_setting(
    'factoryvision.owner_test_teardown_correlation',
    true
  ) <> '' then
    raise exception 'teardown correlation GUC was not reset';
  end if;
  if (select count(*) from public.owner_workers) <> 3 then
    raise exception 'teardown deleted shared worker records';
  end if;
  begin
    delete from public.owner_test_teardown_receipts
    where test_correlation_id =
      '71000000-0000-0000-0000-000000000001';
    raise exception 'teardown receipt delete unexpectedly succeeded';
  exception when sqlstate '55000' then
    null;
  end;
end;
$$;

-- Publication fixtures set published_at = now() in the same state update.
-- The worker fixture proves the positive event and coverage projection.

rollback;
