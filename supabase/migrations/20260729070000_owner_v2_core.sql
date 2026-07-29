-- FactoryVision Owner V2 durable economics and owner-safe production truth.

alter table public.factories
  add column if not exists verification_lag_threshold_minutes integer
  not null default 30
  check (verification_lag_threshold_minutes between 1 and 1440);

create table public.owner_projects (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  name text not null check (length(trim(name)) between 1 and 200),
  client text not null check (length(trim(client)) between 1 and 200),
  target_units integer not null check (target_units > 0),
  unit_value_cents bigint not null check (unit_value_cents >= 0),
  unit_material_cost_cents bigint not null check (unit_material_cost_cents >= 0),
  loaded_labor_rate_cents_per_hour bigint not null
    check (loaded_labor_rate_cents_per_hour >= 0),
  planned_direct_labor_cents bigint not null
    check (planned_direct_labor_cents >= 0),
  target_margin_bps integer check (target_margin_bps between -100000 and 10000),
  start_at timestamptz not null,
  deadline timestamptz not null check (deadline > start_at),
  shift_calendar jsonb not null check (jsonb_typeof(shift_calendar) = 'object'),
  test_correlation_id uuid,
  status text not null default 'draft'
    check (status in ('draft', 'open', 'paused', 'closed')),
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  closed_at timestamptz,
  check (
    (status = 'closed' and closed_at is not null)
    or (status <> 'closed' and closed_at is null)
  ),
  unique (id, factory_id)
);

create unique index owner_projects_test_correlation_idx
  on public.owner_projects (factory_id, test_correlation_id)
  where test_correlation_id is not null;

create table public.owner_project_drafts (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (factory_id, created_by),
  unique (id, factory_id)
);

create table public.owner_workers (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  display_name text not null check (length(trim(display_name)) between 1 and 200),
  employee_code text,
  primary_role text,
  status text not null default 'active'
    check (status in ('active', 'inactive')),
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (employee_code is null or length(trim(employee_code)) between 1 and 100),
  check (primary_role is null or length(trim(primary_role)) between 1 and 100),
  unique (id, factory_id),
  unique (factory_id, employee_code)
);

create table public.owner_project_station_assignments (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  project_id uuid not null,
  station_id uuid not null,
  effective_start timestamptz not null,
  effective_end timestamptz,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (effective_end is null or effective_end > effective_start),
  foreign key (project_id, factory_id)
    references public.owner_projects(id, factory_id) on delete restrict,
  foreign key (station_id, factory_id)
    references public.stations(id, factory_id) on delete restrict,
  unique (id, factory_id),
  exclude using gist (
    factory_id with =,
    station_id with =,
    tstzrange(
      effective_start,
      coalesce(effective_end, 'infinity'::timestamptz),
      '[)'
    ) with &&
  )
);

create table public.owner_worker_station_intervals (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  project_id uuid not null,
  station_id uuid not null,
  worker_id uuid not null,
  effective_start timestamptz not null,
  effective_end timestamptz,
  loaded_labor_rate_cents_per_hour bigint not null
    check (loaded_labor_rate_cents_per_hour >= 0),
  source text not null default 'manual'
    check (source in ('manual', 'badge', 'schedule', 'import')),
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (effective_end is null or effective_end > effective_start),
  foreign key (project_id, factory_id)
    references public.owner_projects(id, factory_id) on delete restrict,
  foreign key (station_id, factory_id)
    references public.stations(id, factory_id) on delete restrict,
  foreign key (worker_id, factory_id)
    references public.owner_workers(id, factory_id) on delete restrict,
  unique (id, factory_id),
  exclude using gist (
    factory_id with =,
    worker_id with =,
    tstzrange(
      effective_start,
      coalesce(effective_end, 'infinity'::timestamptz),
      '[)'
    ) with &&
  )
);

create table public.owner_station_downtime_intervals (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  project_id uuid not null,
  station_id uuid not null,
  effective_start timestamptz not null,
  effective_end timestamptz not null check (effective_end > effective_start),
  reason_code text not null,
  note text,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  foreign key (project_id, factory_id)
    references public.owner_projects(id, factory_id) on delete restrict,
  foreign key (station_id, factory_id)
    references public.stations(id, factory_id) on delete restrict,
  unique (id, factory_id),
  exclude using gist (
    factory_id with =,
    project_id with =,
    station_id with =,
    tstzrange(effective_start, effective_end, '[)') with &&
  )
);

create table public.owner_output_adjustments (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  project_id uuid not null,
  station_id uuid,
  kind text not null check (kind in ('scrap', 'rework', 'correction')),
  delta_good_units integer not null check (delta_good_units <> 0),
  reason_code text not null,
  note text,
  occurred_at timestamptz not null,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  check (
    (kind in ('scrap', 'rework') and delta_good_units < 0)
    or kind = 'correction'
  ),
  foreign key (project_id, factory_id)
    references public.owner_projects(id, factory_id) on delete restrict,
  foreign key (station_id, factory_id)
    references public.stations(id, factory_id) on delete restrict,
  unique (id, factory_id)
);

create table public.owner_project_closeouts (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  project_id uuid not null,
  revision integer not null check (revision > 0),
  planned_units integer not null check (planned_units > 0),
  planned_direct_labor_cents bigint not null,
  planned_material_cost_cents bigint not null,
  planned_margin_after_direct_costs_cents bigint not null,
  deadline_at timestamptz not null,
  completed_at timestamptz not null,
  factory_timezone text not null,
  verified_good_units integer not null check (verified_good_units >= 0),
  production_value_cents bigint not null,
  material_cost_cents bigint not null,
  direct_labor_cents bigint not null,
  margin_after_direct_costs_cents bigint not null,
  verified_through_at timestamptz,
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  foreign key (project_id, factory_id)
    references public.owner_projects(id, factory_id) on delete restrict,
  unique (project_id, revision),
  unique (id, factory_id)
);

create table public.owner_project_audit (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  project_id uuid,
  actor_user_id uuid references public.profiles(id) on delete restrict,
  actor_type text not null check (actor_type in ('user', 'service', 'system')),
  action text not null,
  target_type text not null,
  target_id uuid,
  correlation_id uuid not null default gen_random_uuid(),
  metadata jsonb not null default '{}'::jsonb
    check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now(),
  foreign key (project_id, factory_id)
    references public.owner_projects(id, factory_id) on delete restrict,
  unique (id, factory_id)
);

create table public.owner_project_evidence_attachments (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  project_id uuid not null,
  media_object_id uuid not null,
  reason_code text not null
    check (length(trim(reason_code)) between 1 and 100),
  object_sha256 text not null check (object_sha256 ~ '^[0-9a-f]{64}$'),
  retention_until timestamptz,
  attached_at timestamptz not null default now(),
  foreign key (project_id, factory_id)
    references public.owner_projects(id, factory_id) on delete restrict,
  foreign key (media_object_id, factory_id)
    references public.media_objects(id, factory_id) on delete restrict,
  unique (project_id, media_object_id),
  unique (id, factory_id)
);

create table public.owner_closeout_evidence_attachments (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  closeout_id uuid not null,
  project_id uuid not null,
  media_object_id uuid not null,
  reason_code text not null,
  object_sha256 text not null check (object_sha256 ~ '^[0-9a-f]{64}$'),
  retention_until timestamptz,
  attached_at timestamptz not null,
  created_at timestamptz not null default now(),
  foreign key (closeout_id, factory_id)
    references public.owner_project_closeouts(id, factory_id) on delete restrict,
  foreign key (project_id, factory_id)
    references public.owner_projects(id, factory_id) on delete restrict,
  foreign key (media_object_id, factory_id)
    references public.media_objects(id, factory_id) on delete restrict,
  unique (closeout_id, media_object_id),
  unique (id, factory_id)
);

create table public.owner_test_teardown_receipts (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  test_correlation_id uuid not null,
  project_id uuid not null,
  deleted_project_name text not null,
  deleted_assignment_count integer not null check (deleted_assignment_count >= 0),
  deleted_worker_interval_count integer not null check (deleted_worker_interval_count >= 0),
  deleted_downtime_count integer not null check (deleted_downtime_count >= 0),
  deleted_adjustment_count integer not null check (deleted_adjustment_count >= 0),
  deleted_closeout_count integer not null check (deleted_closeout_count >= 0),
  deleted_project_evidence_count integer not null
    check (deleted_project_evidence_count >= 0),
  deleted_closeout_evidence_count integer not null
    check (deleted_closeout_evidence_count >= 0),
  deleted_audit_count integer not null check (deleted_audit_count >= 0),
  created_at timestamptz not null default now(),
  unique (factory_id, test_correlation_id)
);

create table public.owner_production_events (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  station_id uuid not null,
  chunk_id uuid not null,
  resolved_event_id uuid not null,
  occurred_at timestamptz not null,
  source_time_ms bigint not null check (source_time_ms >= 0),
  published_at timestamptz not null,
  created_at timestamptz not null default now(),
  foreign key (station_id, factory_id)
    references public.stations(id, factory_id) on delete restrict,
  foreign key (chunk_id, factory_id)
    references public.video_chunks(id, factory_id) on delete restrict,
  foreign key (resolved_event_id, factory_id)
    references public.resolved_human_count_events(id, factory_id) on delete restrict,
  unique (resolved_event_id),
  unique (id, factory_id)
);

create table public.owner_verification_intervals (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  station_id uuid not null,
  chunk_id uuid not null,
  revision integer not null check (revision > 0),
  supersedes_id uuid,
  source_start_at timestamptz not null,
  source_end_at timestamptz not null check (source_end_at > source_start_at),
  status text not null check (
    status in (
      'verified',
      'timeline_untrusted',
      'no_published_coverage',
      'coverage_revoked'
    )
  ),
  reason_code text,
  created_at timestamptz not null default now(),
  foreign key (station_id, factory_id)
    references public.stations(id, factory_id) on delete restrict,
  foreign key (chunk_id, factory_id)
    references public.video_chunks(id, factory_id) on delete restrict,
  foreign key (supersedes_id, factory_id)
    references public.owner_verification_intervals(id, factory_id)
    on delete restrict,
  unique (chunk_id, revision),
  unique (id, factory_id)
);

create table public.owner_chunk_publication_locks (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  chunk_id uuid not null,
  published_at timestamptz not null,
  created_at timestamptz not null default now(),
  foreign key (chunk_id, factory_id)
    references public.video_chunks(id, factory_id) on delete restrict,
  unique (chunk_id),
  unique (id, factory_id)
);

create index owner_projects_factory_status_idx
  on public.owner_projects (factory_id, status, deadline);
create index owner_workers_factory_status_idx
  on public.owner_workers (factory_id, status, display_name);
create index owner_project_assignments_project_idx
  on public.owner_project_station_assignments
  (factory_id, project_id, effective_start);
create index owner_worker_intervals_project_idx
  on public.owner_worker_station_intervals
  (factory_id, project_id, effective_start);
create index owner_downtime_project_idx
  on public.owner_station_downtime_intervals
  (factory_id, project_id, effective_start);
create index owner_adjustments_project_idx
  on public.owner_output_adjustments
  (factory_id, project_id, occurred_at);
create index owner_events_station_time_idx
  on public.owner_production_events (factory_id, station_id, occurred_at);
create index owner_verification_station_time_idx
  on public.owner_verification_intervals
  (factory_id, station_id, source_start_at, source_end_at);
create index owner_audit_project_time_idx
  on public.owner_project_audit (factory_id, project_id, created_at desc);
create index owner_project_evidence_project_idx
  on public.owner_project_evidence_attachments
  (factory_id, project_id, attached_at);
create index owner_closeout_evidence_closeout_idx
  on public.owner_closeout_evidence_attachments
  (factory_id, closeout_id, created_at);

create or replace function public.validate_factory_timezone()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not exists (
    select 1 from pg_catalog.pg_timezone_names timezone_name
    where timezone_name.name = new.timezone
  ) then
    raise exception 'factory timezone is not a recognized IANA name'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

drop trigger if exists factories_validate_timezone on public.factories;
create trigger factories_validate_timezone
before insert or update of timezone on public.factories
for each row execute function public.validate_factory_timezone();

do $$
begin
  if exists (
    select 1
    from public.factories factory
    where not exists (
      select 1 from pg_catalog.pg_timezone_names timezone_name
      where timezone_name.name = factory.timezone
    )
  ) then
    raise exception 'existing factory timezone is not a recognized IANA name';
  end if;
end;
$$;

create or replace function public.owner_has_active_role(
  p_factory_id uuid,
  p_role text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.factory_memberships membership
    join public.profiles profile on profile.id = membership.user_id
    join public.factories factory on factory.id = membership.factory_id
    where membership.factory_id = p_factory_id
      and membership.user_id = auth.uid()
      and membership.role = p_role
      and membership.status = 'active'
      and profile.status = 'active'
      and factory.status = 'active'
  );
$$;

create or replace function public.owner_authorize_session(
  p_factory_id uuid default null
)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'authorized',
    count(*) > 0,
    'factories',
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', factory.id,
          'name', factory.name,
          'timezone', factory.timezone,
          'verificationLagThresholdMinutes',
            factory.verification_lag_threshold_minutes
        )
        order by factory.name
      ),
      '[]'::jsonb
    )
  )
  from public.factory_memberships membership
  join public.profiles profile on profile.id = membership.user_id
  join public.factories factory on factory.id = membership.factory_id
  where membership.user_id = auth.uid()
    and membership.role = 'owner'
    and membership.status = 'active'
    and profile.status = 'active'
    and factory.status = 'active'
    and (p_factory_id is null or factory.id = p_factory_id);
$$;

create or replace function public.owner_shift_calendar_is_valid(
  p_factory_id uuid,
  p_calendar jsonb
)
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  factory_timezone text;
  shift_value jsonb;
  weekday_value integer;
  start_minute integer;
  end_minute integer;
  candidate_range int4range;
  existing_range int4range;
  occupied_ranges int4range[] := array[]::int4range[];
begin
  select factory.timezone
  into factory_timezone
  from public.factories factory
  where factory.id = p_factory_id
    and factory.status = 'active';
  if factory_timezone is null
     or p_calendar is null
     or jsonb_typeof(p_calendar) <> 'object'
     or p_calendar->>'timezone' is distinct from factory_timezone
     or jsonb_typeof(p_calendar->'shifts') <> 'array'
     or jsonb_array_length(p_calendar->'shifts') = 0 then
    return false;
  end if;

  for shift_value in
    select value from jsonb_array_elements(p_calendar->'shifts')
  loop
    if jsonb_typeof(shift_value) <> 'object'
       or coalesce(shift_value->>'weekday', '') !~ '^[1-7]$'
       or coalesce(shift_value->>'start', '')
         !~ '^(?:[01][0-9]|2[0-3]):[0-5][0-9]$'
       or coalesce(shift_value->>'end', '')
         !~ '^(?:[01][0-9]|2[0-3]):[0-5][0-9]$' then
      return false;
    end if;

    weekday_value := (shift_value->>'weekday')::integer;
    start_minute := (weekday_value - 1) * 1440
      + split_part(shift_value->>'start', ':', 1)::integer * 60
      + split_part(shift_value->>'start', ':', 2)::integer;
    end_minute := (weekday_value - 1) * 1440
      + split_part(shift_value->>'end', ':', 1)::integer * 60
      + split_part(shift_value->>'end', ':', 2)::integer;
    if end_minute = start_minute then
      return false;
    end if;
    if end_minute < start_minute then
      end_minute := end_minute + 1440;
    end if;

    candidate_range := int4range(start_minute, least(end_minute, 10080), '[)');
    foreach existing_range in array occupied_ranges loop
      if existing_range && candidate_range then return false; end if;
    end loop;
    occupied_ranges := array_append(occupied_ranges, candidate_range);

    if end_minute > 10080 then
      candidate_range := int4range(0, end_minute - 10080, '[)');
      foreach existing_range in array occupied_ranges loop
        if existing_range && candidate_range then return false; end if;
      end loop;
      occupied_ranges := array_append(occupied_ranges, candidate_range);
    end if;
  end loop;
  return true;
end;
$$;

create or replace function public.owner_scheduled_work_milliseconds(
  p_start_at timestamptz,
  p_deadline timestamptz,
  p_calendar jsonb
)
returns bigint
language sql
stable
set search_path = ''
as $$
  with config as (
    select p_calendar->>'timezone' as timezone
  ),
  local_dates as (
    select
      generated.local_day::date as local_day,
      config.timezone
    from config
    cross join lateral pg_catalog.generate_series(
      ((p_start_at at time zone config.timezone)::date - 1)::timestamp,
      ((p_deadline at time zone config.timezone)::date)::timestamp,
      interval '1 day'
    ) generated(local_day)
  ),
  shift_bounds as (
    -- AT TIME ZONE uses the standard/later offset at DST ambiguity. The
    -- Temporal client pins the same "later" policy.
    select
      (
        local_dates.local_day + (shift_value->>'start')::time
      ) at time zone local_dates.timezone as shift_start,
      (
        local_dates.local_day
        + (shift_value->>'end')::time
        + case
            when (shift_value->>'end')::time
              <= (shift_value->>'start')::time
            then interval '1 day'
            else interval '0'
          end
      ) at time zone local_dates.timezone as shift_end
    from local_dates
    cross join lateral pg_catalog.jsonb_array_elements(
      p_calendar->'shifts'
    ) shift_value
    where extract(isodow from local_dates.local_day)::integer
      = (shift_value->>'weekday')::integer
  ),
  clipped_overlaps as (
    select
      greatest(p_start_at, shift_start) as overlap_start,
      least(p_deadline, shift_end) as overlap_end
    from shift_bounds
    where shift_end > p_start_at
      and shift_start < p_deadline
  )
  select coalesce(
    pg_catalog.round(
      pg_catalog.sum(
        extract(epoch from overlap_end - overlap_start) * 1000
      )
    )::bigint,
    0
  )
  from clipped_overlaps
  where overlap_end > overlap_start;
$$;

create or replace function public.owner_save_project_draft(
  p_factory_id uuid,
  p_payload jsonb
)
returns public.owner_project_drafts
language plpgsql
security definer
set search_path = ''
as $$
declare
  draft_row public.owner_project_drafts%rowtype;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'project draft payload must be an object'
      using errcode = '23514';
  end if;
  if pg_catalog.octet_length(p_payload::text) > 65536 then
    raise exception 'project draft payload is too large'
      using errcode = '22023';
  end if;

  insert into public.owner_project_drafts (
    factory_id, payload, created_by
  ) values (
    p_factory_id, p_payload, auth.uid()
  )
  on conflict (factory_id, created_by)
  do update set payload = excluded.payload, updated_at = now()
  returning * into draft_row;

  return draft_row;
end;
$$;

create or replace function public.owner_upsert_worker(
  p_factory_id uuid,
  p_worker_id uuid,
  p_display_name text,
  p_employee_code text,
  p_status text default 'active',
  p_employee_code_supplied boolean default true,
  p_primary_role text default null,
  p_primary_role_supplied boolean default true
)
returns public.owner_workers
language plpgsql
security definer
set search_path = ''
as $$
declare
  worker_row public.owner_workers%rowtype;
  normalized_code text;
  normalized_role text;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;
  if p_display_name is null
     or length(trim(p_display_name)) not between 1 and 200
     or p_status not in ('active', 'inactive') then
    raise exception 'worker details are invalid' using errcode = '23514';
  end if;
  normalized_code := nullif(trim(p_employee_code), '');
  if normalized_code is not null and length(normalized_code) > 100 then
    raise exception 'worker employee code is too long' using errcode = '23514';
  end if;
  normalized_role := nullif(trim(p_primary_role), '');
  if normalized_role is not null and length(normalized_role) > 100 then
    raise exception 'worker primary role is too long' using errcode = '23514';
  end if;

  if p_worker_id is null then
    insert into public.owner_workers (
      factory_id, display_name, employee_code, primary_role, status, created_by
    ) values (
      p_factory_id, trim(p_display_name), normalized_code, normalized_role,
      p_status, auth.uid()
    )
    returning * into worker_row;
  else
    update public.owner_workers worker
    set display_name = trim(p_display_name),
        employee_code = case
          when p_employee_code_supplied then normalized_code
          else worker.employee_code
        end,
        primary_role = case
          when p_primary_role_supplied then normalized_role
          else worker.primary_role
        end,
        status = p_status,
        updated_at = now()
    where worker.id = p_worker_id
      and worker.factory_id = p_factory_id
    returning * into worker_row;
    if not found then
      raise exception 'owner worker not found' using errcode = '42501';
    end if;
  end if;

  insert into public.owner_project_audit (
    factory_id, actor_user_id, actor_type, action,
    target_type, target_id, metadata
  ) values (
    p_factory_id, auth.uid(), 'user',
    case
      when p_worker_id is null then 'owner.worker.created'
      else 'owner.worker.updated'
    end,
    'owner_worker', worker_row.id,
    jsonb_build_object(
      'display_name', worker_row.display_name,
      'employee_code', worker_row.employee_code,
      'primary_role', worker_row.primary_role,
      'status', worker_row.status
    )
  );

  return worker_row;
end;
$$;

create or replace function public.owner_record_downtime(
  p_factory_id uuid,
  p_project_id uuid,
  p_station_id uuid,
  p_effective_start timestamptz,
  p_effective_end timestamptz,
  p_reason_code text,
  p_note text default null
)
returns public.owner_station_downtime_intervals
language plpgsql
security definer
set search_path = ''
as $$
declare
  downtime_row public.owner_station_downtime_intervals%rowtype;
  normalized_reason text;
  normalized_note text;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;
  normalized_reason := trim(coalesce(p_reason_code, ''));
  normalized_note := nullif(trim(coalesce(p_note, '')), '');
  if p_effective_start is null
     or p_effective_end is null
     or p_effective_end <= p_effective_start
     or length(normalized_reason) not between 1 and 100
     or length(coalesce(normalized_note, '')) > 1000 then
    raise exception 'downtime details are invalid' using errcode = '23514';
  end if;
  if not exists (
    select 1
    from public.owner_projects project
    where project.id = p_project_id
      and project.factory_id = p_factory_id
      and project.status in ('open', 'paused')
      and p_effective_start >= project.start_at
  ) then
    raise exception 'open owner project is required' using errcode = '42501';
  end if;
  if not exists (
    select 1
    from public.owner_project_station_assignments assignment
    where assignment.project_id = p_project_id
      and assignment.factory_id = p_factory_id
      and assignment.station_id = p_station_id
      and assignment.effective_start <= p_effective_start
      and (
        assignment.effective_end is null
        or assignment.effective_end >= p_effective_end
      )
  ) then
    raise exception 'downtime must be inside a project station assignment'
      using errcode = '23514';
  end if;

  insert into public.owner_station_downtime_intervals (
    factory_id, project_id, station_id, effective_start, effective_end,
    reason_code, note, created_by
  ) values (
    p_factory_id, p_project_id, p_station_id, p_effective_start,
    p_effective_end, normalized_reason, normalized_note, auth.uid()
  )
  returning * into downtime_row;

  insert into public.owner_project_audit (
    factory_id, project_id, actor_user_id, actor_type, action,
    target_type, target_id, metadata
  ) values (
    p_factory_id, p_project_id, auth.uid(), 'user',
    'owner.project.downtime_recorded', 'owner_station_downtime',
    downtime_row.id,
    jsonb_build_object(
      'station_id', p_station_id,
      'effective_start', p_effective_start,
      'effective_end', p_effective_end,
      'reason_code', normalized_reason,
      'note', normalized_note
    )
  );

  return downtime_row;
end;
$$;

create or replace function public.owner_start_project(
  p_factory_id uuid,
  p_name text,
  p_client text,
  p_target_units integer,
  p_unit_value_cents bigint,
  p_unit_material_cost_cents bigint,
  p_loaded_labor_rate_cents_per_hour bigint,
  p_planned_direct_labor_cents bigint,
  p_start_at timestamptz,
  p_deadline timestamptz,
  p_shift_calendar jsonb,
  p_target_margin_bps integer,
  p_status text,
  p_station_id uuid,
  p_worker_ids uuid[],
  p_test_correlation_id uuid default null
)
returns public.owner_projects
language plpgsql
security definer
set search_path = ''
as $$
declare
  project_row public.owner_projects%rowtype;
  worker_id uuid;
  requested_worker_count integer;
  eligible_worker_count integer;
  scheduled_work_milliseconds bigint;
  expected_planned_direct_labor_cents bigint;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;
  if p_test_correlation_id is not null and not exists (
    select 1
    from public.factories factory
    where factory.id = p_factory_id
      and factory.is_test = true
  ) then
    raise exception 'test correlation requires a test factory'
      using errcode = '42501';
  end if;
  if p_status <> 'open' then
    raise exception 'owner_start_project requires open status'
      using errcode = '23514';
  end if;
  if p_deadline <= p_start_at then
    raise exception 'project deadline must follow start'
      using errcode = '23514';
  end if;
  if not public.owner_shift_calendar_is_valid(
    p_factory_id,
    p_shift_calendar
  ) then
    raise exception 'invalid factory shift calendar'
      using errcode = '23514';
  end if;
  scheduled_work_milliseconds :=
    public.owner_scheduled_work_milliseconds(
      p_start_at,
      p_deadline,
      p_shift_calendar
    );
  if scheduled_work_milliseconds <= 0 then
    raise exception 'project window must include scheduled working time'
      using errcode = '23514';
  end if;
  if not exists (
    select 1
    from public.stations station
    where station.id = p_station_id
      and station.factory_id = p_factory_id
      and station.status = 'active'
  ) then
    raise exception 'active station is required'
      using errcode = '23514';
  end if;

  requested_worker_count := coalesce(cardinality(p_worker_ids), 0);
  if requested_worker_count < 1 then
    raise exception 'at least one worker is required'
      using errcode = '23514';
  end if;
  select count(distinct worker.id)::integer
  into eligible_worker_count
  from public.owner_workers worker
  where worker.id = any(p_worker_ids)
    and worker.factory_id = p_factory_id
    and worker.status = 'active';
  if eligible_worker_count <> requested_worker_count then
    raise exception 'workers must be unique active workers in the selected factory'
      using errcode = '23514';
  end if;
  expected_planned_direct_labor_cents := pg_catalog.round(
    (
      p_loaded_labor_rate_cents_per_hour::numeric
      * requested_worker_count::numeric
      * scheduled_work_milliseconds::numeric
    ) / 3600000
  )::bigint;
  if p_planned_direct_labor_cents is distinct from
     expected_planned_direct_labor_cents then
    raise exception 'planned direct labor does not match the scheduled plan'
      using errcode = '23514';
  end if;

  insert into public.owner_projects (
    factory_id, name, client, target_units, unit_value_cents,
    unit_material_cost_cents, loaded_labor_rate_cents_per_hour,
    planned_direct_labor_cents, target_margin_bps, start_at, deadline,
    shift_calendar, test_correlation_id, status, created_by
  ) values (
    p_factory_id, trim(p_name), trim(p_client), p_target_units,
    p_unit_value_cents, p_unit_material_cost_cents,
    p_loaded_labor_rate_cents_per_hour, p_planned_direct_labor_cents,
    p_target_margin_bps, p_start_at, p_deadline, p_shift_calendar,
    p_test_correlation_id, 'open', auth.uid()
  )
  returning * into project_row;

  insert into public.owner_project_station_assignments (
    factory_id, project_id, station_id, effective_start, created_by
  ) values (
    p_factory_id, project_row.id, p_station_id, p_start_at, auth.uid()
  );

  foreach worker_id in array p_worker_ids loop
    insert into public.owner_worker_station_intervals (
      factory_id, project_id, station_id, worker_id, effective_start,
      loaded_labor_rate_cents_per_hour, source, created_by
    ) values (
      p_factory_id, project_row.id, p_station_id, worker_id, p_start_at,
      p_loaded_labor_rate_cents_per_hour, 'manual', auth.uid()
    );
  end loop;

  insert into public.owner_project_audit (
    factory_id, project_id, actor_user_id, actor_type, action,
    target_type, target_id, correlation_id, metadata
  ) values (
    p_factory_id, project_row.id, auth.uid(), 'user', 'owner.project.started',
    'owner_project', project_row.id,
    coalesce(p_test_correlation_id, gen_random_uuid()),
    jsonb_build_object(
      'station_id', p_station_id,
      'worker_ids', p_worker_ids,
      'status', project_row.status,
      'test_correlation_id', p_test_correlation_id
    )
  );

  delete from public.owner_project_drafts draft
  where draft.factory_id = p_factory_id
    and draft.created_by = auth.uid();

  return project_row;
end;
$$;

create or replace function public.owner_test_teardown_delete_guard()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  teardown_correlation text;
begin
  teardown_correlation := current_setting(
    'factoryvision.owner_test_teardown_correlation',
    true
  );
  if tg_op = 'DELETE'
     and current_user = 'postgres'
     and teardown_correlation is not null
     and teardown_correlation <> ''
     and exists (
       select 1
       from public.owner_projects project
       join public.factories factory on factory.id = project.factory_id
       where project.id = old.project_id
         and project.factory_id = old.factory_id
         and project.test_correlation_id::text = teardown_correlation
         and factory.is_test = true
     ) then
    return old;
  end if;
  raise exception '% is append-only', tg_table_name using errcode = '55000';
end;
$$;

create or replace function public.owner_teardown_test_correlation(
  p_factory_id uuid,
  p_test_correlation_id uuid
)
returns public.owner_test_teardown_receipts
language plpgsql
security definer
set search_path = ''
as $$
declare
  project_row public.owner_projects%rowtype;
  assignment_count integer;
  worker_interval_count integer;
  downtime_count integer;
  adjustment_count integer;
  closeout_count integer;
  project_evidence_count integer;
  closeout_evidence_count integer;
  audit_count integer;
  receipt public.owner_test_teardown_receipts%rowtype;
begin
  if coalesce(current_setting('role', true), '') <> 'service_role'
     and coalesce(auth.jwt()->>'role', '') <> 'service_role' then
    raise exception 'service role access required' using errcode = '42501';
  end if;
  if p_test_correlation_id is null then
    raise exception 'test correlation is required' using errcode = '22023';
  end if;

  select project.*
  into project_row
  from public.owner_projects project
  join public.factories factory on factory.id = project.factory_id
  where project.factory_id = p_factory_id
    and project.test_correlation_id = p_test_correlation_id
    and project.status in ('open', 'closed')
    and factory.is_test = true
  for update of project;
  if not found then
    raise exception 'correlated test project not found'
      using errcode = '42501';
  end if;

  perform set_config(
    'factoryvision.owner_test_teardown_correlation',
    p_test_correlation_id::text,
    true
  );

  delete from public.owner_closeout_evidence_attachments attachment
  where attachment.factory_id = p_factory_id
    and attachment.project_id = project_row.id;
  get diagnostics closeout_evidence_count = row_count;

  delete from public.owner_project_evidence_attachments attachment
  where attachment.factory_id = p_factory_id
    and attachment.project_id = project_row.id;
  get diagnostics project_evidence_count = row_count;

  delete from public.owner_project_closeouts closeout
  where closeout.factory_id = p_factory_id
    and closeout.project_id = project_row.id;
  get diagnostics closeout_count = row_count;

  delete from public.owner_output_adjustments adjustment
  where adjustment.factory_id = p_factory_id
    and adjustment.project_id = project_row.id;
  get diagnostics adjustment_count = row_count;

  delete from public.owner_station_downtime_intervals downtime
  where downtime.factory_id = p_factory_id
    and downtime.project_id = project_row.id;
  get diagnostics downtime_count = row_count;

  delete from public.owner_worker_station_intervals worker_interval
  where worker_interval.factory_id = p_factory_id
    and worker_interval.project_id = project_row.id;
  get diagnostics worker_interval_count = row_count;

  delete from public.owner_project_station_assignments assignment
  where assignment.factory_id = p_factory_id
    and assignment.project_id = project_row.id;
  get diagnostics assignment_count = row_count;

  delete from public.owner_project_audit audit
  where audit.factory_id = p_factory_id
    and audit.project_id = project_row.id;
  get diagnostics audit_count = row_count;

  delete from public.owner_projects project
  where project.factory_id = p_factory_id
    and project.id = project_row.id;

  perform set_config(
    'factoryvision.owner_test_teardown_correlation',
    '',
    true
  );

  insert into public.owner_test_teardown_receipts (
    factory_id, test_correlation_id, project_id, deleted_project_name,
    deleted_assignment_count, deleted_worker_interval_count,
    deleted_downtime_count, deleted_adjustment_count,
    deleted_closeout_count, deleted_project_evidence_count,
    deleted_closeout_evidence_count, deleted_audit_count
  ) values (
    p_factory_id, p_test_correlation_id, project_row.id, project_row.name,
    assignment_count, worker_interval_count, downtime_count, adjustment_count,
    closeout_count, project_evidence_count, closeout_evidence_count, audit_count
  )
  returning * into receipt;

  insert into public.audit_log (
    factory_id, actor_type, action, target_type, target_id,
    correlation_id, metadata
  ) values (
    p_factory_id, 'service', 'owner.test_correlation.torn_down',
    'owner_project', project_row.id, p_test_correlation_id,
    jsonb_build_object(
      'deleted_project_name', project_row.name,
      'deleted_project_status', project_row.status,
      'deleted_assignment_count', assignment_count,
      'deleted_worker_interval_count', worker_interval_count,
      'deleted_downtime_count', downtime_count,
      'deleted_adjustment_count', adjustment_count,
      'deleted_closeout_count', closeout_count,
      'deleted_project_evidence_count', project_evidence_count,
      'deleted_closeout_evidence_count', closeout_evidence_count,
      'deleted_audit_count', audit_count
    )
  );
  return receipt;
end;
$$;

create or replace function public.service_attach_owner_project_evidence(
  p_factory_id uuid,
  p_project_id uuid,
  p_media_object_id uuid,
  p_reason_code text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  attachment_id uuid;
begin
  if p_reason_code is null
     or length(trim(p_reason_code)) not between 1 and 100 then
    raise exception 'evidence reason code is required'
      using errcode = '23514';
  end if;
  if not exists (
    select 1
    from public.owner_projects project
    where project.id = p_project_id
      and project.factory_id = p_factory_id
      and project.status = 'open'
  ) then
    raise exception 'open owner project not found'
      using errcode = '42501';
  end if;
  if not exists (
    select 1
    from public.media_objects media
    where media.id = p_media_object_id
      and media.factory_id = p_factory_id
      and media.bucket_id = 'evidence-clips'
      and media.status = 'verified'
  ) then
    raise exception 'verified evidence clip not found'
      using errcode = '42501';
  end if;

  insert into public.owner_project_evidence_attachments (
    factory_id, project_id, media_object_id, reason_code,
    object_sha256, retention_until
  )
  select
    p_factory_id, p_project_id, media.id, trim(p_reason_code),
    media.object_sha256, media.retention_until
  from public.media_objects media
  where media.id = p_media_object_id
    and media.factory_id = p_factory_id
  on conflict (project_id, media_object_id) do nothing
  returning id into attachment_id;
  if attachment_id is null then
    select attachment.id
    into attachment_id
    from public.owner_project_evidence_attachments attachment
    where attachment.project_id = p_project_id
      and attachment.media_object_id = p_media_object_id;
  end if;
  return attachment_id;
end;
$$;

create or replace function public.owner_history_evidence(
  p_factory_id uuid,
  p_closeout_id uuid
)
returns table (
  id uuid,
  object_sha256 text,
  retention_until timestamptz,
  reason_code text,
  attached_at timestamptz,
  bucket_id text,
  object_path text,
  content_type text,
  byte_size bigint,
  status text
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;
  if not exists (
    select 1
    from public.owner_project_closeouts closeout
    where closeout.id = p_closeout_id
      and closeout.factory_id = p_factory_id
  ) then
    raise exception 'owner closeout not found' using errcode = '42501';
  end if;

  return query
  select
    attachment.id,
    attachment.object_sha256,
    attachment.retention_until,
    attachment.reason_code,
    attachment.attached_at,
    media.bucket_id,
    media.object_path,
    media.content_type,
    media.byte_size,
    media.status
  from public.owner_closeout_evidence_attachments attachment
  join public.media_objects media
    on media.id = attachment.media_object_id
   and media.factory_id = attachment.factory_id
  where attachment.factory_id = p_factory_id
    and attachment.closeout_id = p_closeout_id
  order by attachment.attached_at, attachment.id;
end;
$$;

create or replace function public.can_read_owner_evidence(
  object_bucket text,
  object_name text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.media_objects media
    join public.owner_closeout_evidence_attachments attachment
      on attachment.media_object_id = media.id
     and attachment.factory_id = media.factory_id
    where media.bucket_id = object_bucket
      and media.object_path = object_name
      and media.bucket_id = 'evidence-clips'
      and media.status = 'verified'
      and (
        attachment.retention_until is null
        or attachment.retention_until > now()
      )
      and public.owner_has_active_role(media.factory_id, 'owner')
  );
$$;

create or replace function public.can_read_qualification_media(
  object_bucket text,
  object_name text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.media_objects media
    join public.media_renditions rendition
      on rendition.rendition_media_object_id = media.id
     and rendition.factory_id = media.factory_id
    join public.video_chunks chunk
      on chunk.review_rendition_id = rendition.id
     and chunk.factory_id = rendition.factory_id
    join public.reviewer_lifecycles lifecycle
      on lifecycle.factory_id = chunk.factory_id
     and lifecycle.user_id = auth.uid()
     and lifecycle.state = 'qualification'
     and lifecycle.practice_completed_at is not null
     and lifecycle.mfa_verified_at is not null
    join public.factory_memberships membership
      on membership.factory_id = lifecycle.factory_id
     and membership.user_id = lifecycle.user_id
     and membership.role = 'reviewer'
     and membership.status = 'active'
    join public.profiles profile
      on profile.id = lifecycle.user_id
     and profile.status = 'active'
    where media.bucket_id = object_bucket
      and media.object_path = object_name
      and media.bucket_id = 'review-renditions'
      and media.status = 'verified'
      and rendition.mapping_status = 'verified'
      and chunk.source_set_role = 'qualification'
      and not chunk.assignment_eligible
      and chunk.state not in ('quarantined', 'deleted')
      and not exists (
        select 1
        from public.video_chunks sibling
        where sibling.factory_id = chunk.factory_id
          and (
            sibling.review_rendition_id = chunk.review_rendition_id
            or sibling.source_media_object_id = chunk.source_media_object_id
          )
          and (
            sibling.source_set_role <> 'qualification'
            or sibling.assignment_eligible
          )
      )
      and (
        lifecycle.is_test_account
        or coalesce(auth.jwt() ->> 'aal', '') = 'aal2'
      )
      and exists (
        select 1
        from private.reference_answers answer
        where answer.chunk_id = chunk.id
          and answer.factory_id = chunk.factory_id
          and answer.answer_type = 'qualification'
          and answer.source_sha256 = chunk.source_sha256
      )
  );
$$;

create or replace function public.owner_close_project(
  p_factory_id uuid,
  p_project_id uuid,
  p_actual_material_cost_cents bigint,
  p_completed_at timestamptz default now()
)
returns public.owner_project_closeouts
language plpgsql
security definer
set search_path = ''
as $$
declare
  project_row public.owner_projects%rowtype;
  closeout_row public.owner_project_closeouts%rowtype;
  factory_timezone text;
  gross_verified_units bigint;
  adjustment_units bigint;
  verified_good_units integer;
  direct_labor_cents bigint;
  actual_direct_labor_minutes bigint;
  planned_schedule_minutes bigint;
  actual_schedule_minutes bigint;
  production_value_cents bigint;
  planned_material_cost_cents bigint;
  planned_margin_cents bigint;
  actual_margin_cents bigint;
  verification_frontier timestamptz;
  verification_advanced boolean := false;
  verification_has_gap boolean := false;
  first_missing_verification timestamptz;
  last_required_verification timestamptz;
  last_covered_verification timestamptz;
  station_names jsonb;
  team_names jsonb;
  shift_names jsonb;
  weekly_output jsonb;
  evidence_clip_count integer;
  evidence_retention_until timestamptz;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;
  if p_actual_material_cost_cents is null
     or p_actual_material_cost_cents < 0 then
    raise exception 'actual material cost must be non-negative cents'
      using errcode = '23514';
  end if;

  select project.*
  into project_row
  from public.owner_projects project
  where project.id = p_project_id
    and project.factory_id = p_factory_id
  for update;
  if not found then
    raise exception 'owner project not found' using errcode = '42501';
  end if;
  if project_row.status not in ('open', 'paused') then
    raise exception 'only an open or paused project can close'
      using errcode = '55000';
  end if;
  if p_completed_at <= project_row.start_at then
    raise exception 'completion must follow project start'
      using errcode = '23514';
  end if;
  if p_completed_at > now() + interval '5 minutes' then
    raise exception 'completion cannot be in the future'
      using errcode = '23514';
  end if;
  if exists (
    select 1
    from public.owner_project_station_assignments assignment
    where assignment.project_id = p_project_id
      and assignment.factory_id = p_factory_id
      and assignment.effective_start >= p_completed_at
  ) or exists (
    select 1
    from public.owner_worker_station_intervals worker_interval
    where worker_interval.project_id = p_project_id
      and worker_interval.factory_id = p_factory_id
      and worker_interval.effective_start >= p_completed_at
  ) then
    raise exception 'completion precedes a project assignment'
      using errcode = '23514';
  end if;

  factory_timezone := project_row.shift_calendar->>'timezone';

  with latest_verification as (
    select distinct on (verification.chunk_id)
      verification.chunk_id,
      verification.status
    from public.owner_verification_intervals verification
    where verification.factory_id = p_factory_id
    order by verification.chunk_id, verification.revision desc
  )
  select count(distinct production_event.id)
  into gross_verified_units
  from public.owner_production_events production_event
  join latest_verification verification
    on verification.chunk_id = production_event.chunk_id
   and verification.status = 'verified'
  where production_event.factory_id = p_factory_id
    and production_event.occurred_at >= project_row.start_at
    and production_event.occurred_at < p_completed_at
    and exists (
      select 1
      from public.owner_project_station_assignments assignment
      where assignment.project_id = p_project_id
        and assignment.factory_id = p_factory_id
        and assignment.station_id = production_event.station_id
        and production_event.occurred_at >= assignment.effective_start
        and (
          assignment.effective_end is null
          or production_event.occurred_at < assignment.effective_end
        )
    );

  select coalesce(sum(adjustment.delta_good_units), 0)
  into adjustment_units
  from public.owner_output_adjustments adjustment
  where adjustment.project_id = p_project_id
    and adjustment.factory_id = p_factory_id
    and adjustment.occurred_at >= project_row.start_at
    and adjustment.occurred_at <= p_completed_at;
  if coalesce(gross_verified_units, 0) + coalesce(adjustment_units, 0)
       not between 0 and 2147483647 then
    raise exception 'closeout good units are out of range'
      using errcode = '23514';
  end if;
  verified_good_units := (
    coalesce(gross_verified_units, 0) + coalesce(adjustment_units, 0)
  )::integer;

  with local_dates as (
    select date_value::date as local_date
    from pg_catalog.generate_series(
      (project_row.start_at at time zone factory_timezone)::date - 1,
      (p_completed_at at time zone factory_timezone)::date,
      interval '1 day'
    ) date_value
  ),
  shift_values as (
    select local_date, shift_value
    from local_dates
    cross join lateral jsonb_array_elements(
      project_row.shift_calendar->'shifts'
    ) shift_value
    where extract(isodow from local_date)::integer
      = (shift_value->>'weekday')::integer
  ),
  shift_ranges as (
    select tstzrange(
      (
        local_date + (shift_value->>'start')::time
      ) at time zone factory_timezone,
      (
        local_date
        + case
            when (shift_value->>'end')::time
              <= (shift_value->>'start')::time
            then 1
            else 0
          end
        + (shift_value->>'end')::time
      ) at time zone factory_timezone,
      '[)'
    ) as worked_range
    from shift_values
  ),
  labor_segments as (
    select
      worker_interval.loaded_labor_rate_cents_per_hour,
      tstzrange(
        greatest(
          worker_interval.effective_start,
          lower(shift.worked_range),
          project_row.start_at
        ),
        least(
          coalesce(worker_interval.effective_end, p_completed_at),
          upper(shift.worked_range),
          p_completed_at
        ),
        '[)'
      ) as worked_range
    from public.owner_worker_station_intervals worker_interval
    join shift_ranges shift
      on tstzrange(
        worker_interval.effective_start,
        least(
          coalesce(worker_interval.effective_end, p_completed_at),
          p_completed_at
        ),
        '[)'
      ) && shift.worked_range
    where worker_interval.project_id = p_project_id
      and worker_interval.factory_id = p_factory_id
      and worker_interval.effective_start < p_completed_at
  )
  select
    coalesce(
      round(
        sum(
          labor_segments.loaded_labor_rate_cents_per_hour::numeric
          * extract(
            epoch from (
              upper(labor_segments.worked_range)
              - lower(labor_segments.worked_range)
            )
          )
        ) / 3600
      ),
      0
    )::bigint,
    coalesce(
      round(
        sum(
          extract(
            epoch from (
              upper(labor_segments.worked_range)
              - lower(labor_segments.worked_range)
            )
          ) / 60
        )
      ),
      0
    )::bigint
  into direct_labor_cents, actual_direct_labor_minutes
  from labor_segments;

  planned_schedule_minutes :=
    public.owner_scheduled_work_milliseconds(
      project_row.start_at,
      project_row.deadline,
      project_row.shift_calendar
    ) / 60000;
  actual_schedule_minutes :=
    public.owner_scheduled_work_milliseconds(
      project_row.start_at,
      p_completed_at,
      project_row.shift_calendar
    ) / 60000;

  select coalesce(
    jsonb_agg(context.station_name order by context.station_name),
    '[]'::jsonb
  )
  into station_names
  from (
    select distinct station.alias as station_name
    from public.owner_project_station_assignments assignment
    join public.stations station
      on station.id = assignment.station_id
     and station.factory_id = assignment.factory_id
    where assignment.project_id = p_project_id
      and assignment.factory_id = p_factory_id
      and assignment.effective_start < p_completed_at
      and coalesce(assignment.effective_end, p_completed_at)
        > project_row.start_at
  ) context;

  select coalesce(
    jsonb_agg(context.worker_name order by context.worker_name),
    '[]'::jsonb
  )
  into team_names
  from (
    select distinct worker.display_name as worker_name
    from public.owner_worker_station_intervals worker_interval
    join public.owner_workers worker
      on worker.id = worker_interval.worker_id
     and worker.factory_id = worker_interval.factory_id
    where worker_interval.project_id = p_project_id
      and worker_interval.factory_id = p_factory_id
      and worker_interval.effective_start < p_completed_at
      and coalesce(worker_interval.effective_end, p_completed_at)
        > project_row.start_at
  ) context;

  select coalesce(
    jsonb_agg(context.shift_name order by context.shift_name),
    '[]'::jsonb
  )
  into shift_names
  from (
    select distinct pg_catalog.format(
      '%s-%s',
      shift_value->>'start',
      shift_value->>'end'
    ) as shift_name
    from pg_catalog.jsonb_array_elements(
      project_row.shift_calendar->'shifts'
    ) shift_value
  ) context;

  with latest_verification as (
    select distinct on (verification.chunk_id)
      verification.chunk_id,
      verification.status
    from public.owner_verification_intervals verification
    where verification.factory_id = p_factory_id
    order by verification.chunk_id, verification.revision desc
  ),
  weekly_events as (
    select
      date_trunc(
        'week',
        production_event.occurred_at at time zone factory_timezone
      )::date as local_week,
      count(distinct production_event.id)::bigint as unit_delta
    from public.owner_production_events production_event
    join latest_verification verification
      on verification.chunk_id = production_event.chunk_id
     and verification.status = 'verified'
    where production_event.factory_id = p_factory_id
      and production_event.occurred_at >= project_row.start_at
      and production_event.occurred_at < p_completed_at
      and exists (
        select 1
        from public.owner_project_station_assignments assignment
        where assignment.project_id = p_project_id
          and assignment.factory_id = p_factory_id
          and assignment.station_id = production_event.station_id
          and production_event.occurred_at >= assignment.effective_start
          and production_event.occurred_at
            < coalesce(assignment.effective_end, p_completed_at)
      )
    group by local_week
  ),
  weekly_adjustments as (
    select
      date_trunc(
        'week',
        adjustment.occurred_at at time zone factory_timezone
      )::date as local_week,
      sum(adjustment.delta_good_units)::bigint as unit_delta
    from public.owner_output_adjustments adjustment
    where adjustment.project_id = p_project_id
      and adjustment.factory_id = p_factory_id
      and adjustment.occurred_at >= project_row.start_at
      and adjustment.occurred_at <= p_completed_at
    group by local_week
  ),
  combined as (
    select local_week, unit_delta from weekly_events
    union all
    select local_week, unit_delta from weekly_adjustments
  ),
  totals as (
    select local_week, sum(unit_delta)::bigint as actual_units
    from combined
    group by local_week
  )
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'week_start', local_week,
        'label', to_char(local_week, 'Mon DD'),
        'planned_units', null,
        'actual_units', actual_units
      )
      order by local_week
    ),
    '[]'::jsonb
  )
  into weekly_output
  from totals;

  with config as (
    select project_row.shift_calendar->>'timezone' as timezone
  ),
  local_dates as (
    select
      generated.local_day::date as local_day,
      config.timezone
    from config
    cross join lateral pg_catalog.generate_series(
      (
        (project_row.start_at at time zone config.timezone)::date - 1
      )::timestamp,
      (
        (p_completed_at at time zone config.timezone)::date
      )::timestamp,
      interval '1 day'
    ) generated(local_day)
  ),
  shift_bounds as (
    select
      (
        local_dates.local_day + (shift_value->>'start')::time
      ) at time zone local_dates.timezone as shift_start,
      (
        local_dates.local_day
        + (shift_value->>'end')::time
        + case
            when (shift_value->>'end')::time
              <= (shift_value->>'start')::time
            then interval '1 day'
            else interval '0'
          end
      ) at time zone local_dates.timezone as shift_end
    from local_dates
    cross join lateral pg_catalog.jsonb_array_elements(
      project_row.shift_calendar->'shifts'
    ) shift_value
    where extract(isodow from local_dates.local_day)::integer
      = (shift_value->>'weekday')::integer
  ),
  assigned_shifts as (
    select
      assignment.station_id,
      greatest(
        project_row.start_at,
        assignment.effective_start,
        shift_bounds.shift_start
      ) as required_start,
      least(
        p_completed_at,
        coalesce(assignment.effective_end, p_completed_at),
        shift_bounds.shift_end
      ) as required_end
    from public.owner_project_station_assignments assignment
    cross join shift_bounds
    where assignment.project_id = p_project_id
      and assignment.factory_id = p_factory_id
      and shift_bounds.shift_end > project_row.start_at
      and shift_bounds.shift_start < p_completed_at
      and shift_bounds.shift_end > assignment.effective_start
      and shift_bounds.shift_start
        < coalesce(assignment.effective_end, p_completed_at)
  ),
  scheduled_by_station as (
    select
      assigned_shift.station_id,
      pg_catalog.range_agg(
        pg_catalog.tstzrange(
          assigned_shift.required_start,
          assigned_shift.required_end,
          '[)'
        )
      ) as scheduled_ranges
    from assigned_shifts assigned_shift
    where assigned_shift.required_end > assigned_shift.required_start
    group by assigned_shift.station_id
  ),
  downtime_by_station as (
    select
      downtime.station_id,
      pg_catalog.range_agg(
        pg_catalog.tstzrange(
          greatest(downtime.effective_start, project_row.start_at),
          least(downtime.effective_end, p_completed_at),
          '[)'
        )
      ) as downtime_ranges
    from public.owner_station_downtime_intervals downtime
    where downtime.project_id = p_project_id
      and downtime.factory_id = p_factory_id
      and downtime.effective_end > project_row.start_at
      and downtime.effective_start < p_completed_at
    group by downtime.station_id
  ),
  required_by_station as (
    select
      scheduled.station_id,
      scheduled.scheduled_ranges
        - coalesce(
            downtime.downtime_ranges,
            '{}'::pg_catalog.tstzmultirange
          ) as required_ranges
    from scheduled_by_station scheduled
    left join downtime_by_station downtime
      on downtime.station_id = scheduled.station_id
  ),
  latest_verification as (
    select distinct on (verification.chunk_id)
      verification.chunk_id,
      verification.station_id,
      verification.source_start_at,
      verification.source_end_at,
      verification.status
    from public.owner_verification_intervals verification
    where verification.factory_id = p_factory_id
    order by verification.chunk_id, verification.revision desc
  ),
  verification_pieces as (
    select
      verification.station_id,
      greatest(
        verification.source_start_at,
        assignment.effective_start,
        project_row.start_at
      ) as covered_start,
      least(
        verification.source_end_at,
        coalesce(assignment.effective_end, p_completed_at),
        p_completed_at
      ) as covered_end
    from latest_verification verification
    join public.owner_project_station_assignments assignment
      on assignment.project_id = p_project_id
     and assignment.factory_id = p_factory_id
     and assignment.station_id = verification.station_id
     and verification.source_end_at > assignment.effective_start
     and verification.source_start_at
       < coalesce(assignment.effective_end, p_completed_at)
    where verification.status = 'verified'
      and verification.source_end_at > project_row.start_at
      and verification.source_start_at < p_completed_at
  ),
  verified_by_station as (
    select
      verification_piece.station_id,
      pg_catalog.range_agg(
        pg_catalog.tstzrange(
          verification_piece.covered_start - interval '1 second',
          verification_piece.covered_end,
          '[)'
        )
      ) as verified_ranges
    from verification_pieces verification_piece
    where verification_piece.covered_end > verification_piece.covered_start
    group by verification_piece.station_id
  ),
  coverage_by_station as (
    select
      required.station_id,
      required.required_ranges,
      required.required_ranges
        * coalesce(
            verified.verified_ranges,
            '{}'::pg_catalog.tstzmultirange
          ) as covered_ranges
    from required_by_station required
    left join verified_by_station verified
      on verified.station_id = required.station_id
  ),
  missing_by_station as (
    select
      coverage.station_id,
      coverage.required_ranges - coverage.covered_ranges as missing_ranges,
      coverage.required_ranges,
      coverage.covered_ranges
    from coverage_by_station coverage
  ),
  station_frontiers as (
    select
      missing.station_id,
      (
        select min(pg_catalog.lower(missing_piece.value))
        from pg_catalog.unnest(
          missing.missing_ranges
        ) as missing_piece(value)
      ) as first_missing,
      (
        select max(pg_catalog.upper(required_piece.value))
        from pg_catalog.unnest(
          missing.required_ranges
        ) as required_piece(value)
      ) as last_required,
      (
        select max(pg_catalog.upper(covered_piece.value))
        from pg_catalog.unnest(
          missing.covered_ranges
        ) as covered_piece(value)
      ) as last_covered
    from missing_by_station missing
  )
  select
    min(station_frontier.first_missing),
    max(station_frontier.last_required),
    max(station_frontier.last_covered),
    coalesce(
      pg_catalog.bool_or(
        station_frontier.first_missing is not null
        and station_frontier.last_covered is not null
        and station_frontier.last_covered
          > station_frontier.first_missing + interval '1 second'
      ),
      false
    )
  into
    first_missing_verification,
    last_required_verification,
    last_covered_verification,
    verification_has_gap
  from station_frontiers station_frontier;

  verification_frontier := coalesce(
    first_missing_verification,
    last_required_verification,
    project_row.start_at
  );
  verification_advanced := verification_frontier > project_row.start_at;

  update public.owner_project_station_assignments assignment
  set effective_end = p_completed_at,
      updated_at = now()
  where assignment.project_id = p_project_id
    and assignment.factory_id = p_factory_id
    and assignment.effective_start < p_completed_at
    and (
      assignment.effective_end is null
      or assignment.effective_end > p_completed_at
    );
  update public.owner_worker_station_intervals worker_interval
  set effective_end = p_completed_at,
      updated_at = now()
  where worker_interval.project_id = p_project_id
    and worker_interval.factory_id = p_factory_id
    and worker_interval.effective_start < p_completed_at
    and (
      worker_interval.effective_end is null
      or worker_interval.effective_end > p_completed_at
    );

  production_value_cents :=
    verified_good_units::bigint * project_row.unit_value_cents;
  planned_material_cost_cents :=
    project_row.target_units::bigint * project_row.unit_material_cost_cents;
  planned_margin_cents :=
    project_row.target_units::bigint * project_row.unit_value_cents
    - planned_material_cost_cents
    - project_row.planned_direct_labor_cents;
  actual_margin_cents :=
    production_value_cents
    - p_actual_material_cost_cents
    - direct_labor_cents;

  select
    count(*)::integer,
    min(attachment.retention_until)
      filter (where attachment.retention_until is not null)
  into evidence_clip_count, evidence_retention_until
  from public.owner_project_evidence_attachments attachment
  join public.media_objects media
    on media.id = attachment.media_object_id
   and media.factory_id = attachment.factory_id
  where attachment.factory_id = p_factory_id
    and attachment.project_id = p_project_id
    and media.bucket_id = 'evidence-clips';

  update public.owner_projects project
  set status = 'closed',
      closed_at = p_completed_at
  where project.id = p_project_id
    and project.factory_id = p_factory_id;

  insert into public.owner_project_closeouts (
    factory_id, project_id, revision, planned_units,
    planned_direct_labor_cents, planned_material_cost_cents,
    planned_margin_after_direct_costs_cents, deadline_at, completed_at,
    factory_timezone, verified_good_units, production_value_cents,
    material_cost_cents, direct_labor_cents,
    margin_after_direct_costs_cents, verified_through_at, snapshot, created_by
  ) values (
    p_factory_id, p_project_id, 1, project_row.target_units,
    project_row.planned_direct_labor_cents, planned_material_cost_cents,
    planned_margin_cents, project_row.deadline, p_completed_at,
    factory_timezone, verified_good_units, production_value_cents,
    p_actual_material_cost_cents, direct_labor_cents, actual_margin_cents,
    case when verification_advanced then verification_frontier else null end,
    jsonb_build_object(
      'project_name', project_row.name,
      'customer_name', project_row.client,
      'project_start_at', project_row.start_at,
      'planned_schedule_minutes', planned_schedule_minutes,
      'actual_schedule_minutes', actual_schedule_minutes,
      'actual_direct_labor_minutes', actual_direct_labor_minutes,
      'station_names', station_names,
      'shift_names', shift_names,
      'team_names', team_names,
      'weekly_output', weekly_output,
      'evidence_clip_count', coalesce(evidence_clip_count, 0),
      'evidence_retention_until', evidence_retention_until,
      'gross_verified_units', coalesce(gross_verified_units, 0),
      'adjustment_units', coalesce(adjustment_units, 0),
      'actual_material_cost_source', 'owner_entered',
      'verification_has_gap', verification_has_gap
    ),
    auth.uid()
  )
  returning * into closeout_row;

  insert into public.owner_closeout_evidence_attachments (
    factory_id, closeout_id, project_id, media_object_id, reason_code,
    object_sha256, retention_until, attached_at
  )
  select
    attachment.factory_id, closeout_row.id, attachment.project_id,
    attachment.media_object_id, attachment.reason_code,
    attachment.object_sha256, attachment.retention_until,
    attachment.attached_at
  from public.owner_project_evidence_attachments attachment
  join public.media_objects media
    on media.id = attachment.media_object_id
   and media.factory_id = attachment.factory_id
  where attachment.factory_id = p_factory_id
    and attachment.project_id = p_project_id
    and media.bucket_id = 'evidence-clips';

  insert into public.owner_project_audit (
    factory_id, project_id, actor_user_id, actor_type, action,
    target_type, target_id, metadata
  ) values (
    p_factory_id, p_project_id, auth.uid(), 'user', 'owner.project.closed',
    'owner_project_closeout', closeout_row.id,
    jsonb_build_object(
      'revision', closeout_row.revision,
      'completed_at', p_completed_at,
      'actual_material_cost_source', 'owner_entered'
    )
  );

  return closeout_row;
end;
$$;

create or replace function public.owner_correct_closeout(
  p_factory_id uuid,
  p_project_id uuid,
  p_kind text,
  p_delta_good_units integer,
  p_reason_code text,
  p_note text,
  p_occurred_at timestamptz,
  p_actual_material_cost_cents bigint
)
returns public.owner_project_closeouts
language plpgsql
security definer
set search_path = ''
as $$
declare
  project_row public.owner_projects%rowtype;
  prior_closeout public.owner_project_closeouts%rowtype;
  adjustment_row public.owner_output_adjustments%rowtype;
  revised_closeout public.owner_project_closeouts%rowtype;
  revised_good_units bigint;
  revised_material_cents bigint;
  revised_production_value_cents bigint;
  revised_margin_cents bigint;
  revised_gross_verified_units bigint;
  revised_adjustment_units bigint;
  revised_weekly_output jsonb;
  correction_week_start text;
  correction_week_label text;
  correction_week_found boolean;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;
  if p_kind not in ('scrap', 'rework', 'correction')
     or p_delta_good_units is null
     or p_delta_good_units = 0
     or (
       p_kind in ('scrap', 'rework')
       and p_delta_good_units > 0
     )
     or p_reason_code is null
     or length(trim(p_reason_code)) not between 1 and 100 then
    raise exception 'closeout correction is invalid' using errcode = '23514';
  end if;

  select project.*
  into project_row
  from public.owner_projects project
  where project.id = p_project_id
    and project.factory_id = p_factory_id
  for update;
  if not found then
    raise exception 'owner project not found' using errcode = '42501';
  end if;
  if project_row.status <> 'closed' then
    raise exception 'only a closed project can be corrected'
      using errcode = '55000';
  end if;

  select closeout.*
  into prior_closeout
  from public.owner_project_closeouts closeout
  where closeout.project_id = p_project_id
    and closeout.factory_id = p_factory_id
  order by closeout.revision desc
  limit 1;
  if not found then
    raise exception 'project closeout not found' using errcode = '55000';
  end if;
  if p_occurred_at < project_row.start_at
     or p_occurred_at > prior_closeout.completed_at then
    raise exception 'correction time lies outside the project'
      using errcode = '23514';
  end if;
  if p_actual_material_cost_cents is not null
     and p_actual_material_cost_cents < 0 then
    raise exception 'corrected material cost must be non-negative cents'
      using errcode = '23514';
  end if;

  revised_good_units :=
    prior_closeout.verified_good_units::bigint + p_delta_good_units;
  if revised_good_units < 0 or revised_good_units > 2147483647 then
    raise exception 'corrected good units are out of range'
      using errcode = '23514';
  end if;
  revised_material_cents := coalesce(
    p_actual_material_cost_cents,
    prior_closeout.material_cost_cents
  );
  revised_production_value_cents :=
    revised_good_units * project_row.unit_value_cents;
  revised_margin_cents :=
    revised_production_value_cents
    - revised_material_cents
    - prior_closeout.direct_labor_cents;

  insert into public.owner_output_adjustments (
    factory_id, project_id, kind, delta_good_units, reason_code,
    note, occurred_at, created_by
  ) values (
    p_factory_id, p_project_id, p_kind, p_delta_good_units,
    trim(p_reason_code), nullif(trim(p_note), ''), p_occurred_at, auth.uid()
  )
  returning * into adjustment_row;

  revised_gross_verified_units := coalesce(
    (prior_closeout.snapshot->>'gross_verified_units')::bigint,
    prior_closeout.verified_good_units::bigint
      - coalesce(
          (prior_closeout.snapshot->>'adjustment_units')::bigint,
          0
        )
  );
  revised_adjustment_units := coalesce(
    (prior_closeout.snapshot->>'adjustment_units')::bigint,
    prior_closeout.verified_good_units::bigint
      - revised_gross_verified_units
  ) + p_delta_good_units;

  if coalesce(revised_gross_verified_units, 0)
       + coalesce(revised_adjustment_units, 0) <> revised_good_units then
    raise exception 'corrected closeout does not reconcile with durable events'
      using errcode = '55000';
  end if;

  correction_week_start := to_char(
    date_trunc(
      'week',
      p_occurred_at at time zone prior_closeout.factory_timezone
    )::date,
    'YYYY-MM-DD'
  );
  correction_week_label := to_char(
    correction_week_start::date,
    'Mon DD'
  );
  correction_week_found := false;
  select coalesce(
    jsonb_agg(
      case
        when weekly_row.value->>'week_start' = correction_week_start then
          pg_catalog.jsonb_set(
            weekly_row.value,
            '{actual_units}',
            pg_catalog.to_jsonb(
              coalesce(
                (weekly_row.value->>'actual_units')::bigint,
                0
              ) + p_delta_good_units
            ),
            true
          )
        else weekly_row.value
      end
      order by weekly_row.ordinality
    ),
    '[]'::jsonb
  )
  into revised_weekly_output
  from pg_catalog.jsonb_array_elements(
    coalesce(prior_closeout.snapshot->'weekly_output', '[]'::jsonb)
  ) with ordinality as weekly_row(value, ordinality);

  select exists (
    select 1
    from pg_catalog.jsonb_array_elements(revised_weekly_output) weekly_row
    where weekly_row->>'week_start' = correction_week_start
  )
  into correction_week_found;
  if not correction_week_found then
    revised_weekly_output := revised_weekly_output || jsonb_build_array(
      jsonb_build_object(
        'week_start', correction_week_start,
        'label', correction_week_label,
        'planned_units', null,
        'actual_units', p_delta_good_units
      )
    );
  end if;

  insert into public.owner_project_closeouts (
    factory_id, project_id, revision, planned_units,
    planned_direct_labor_cents, planned_material_cost_cents,
    planned_margin_after_direct_costs_cents, deadline_at, completed_at,
    factory_timezone, verified_good_units, production_value_cents,
    material_cost_cents, direct_labor_cents,
    margin_after_direct_costs_cents, verified_through_at, snapshot, created_by
  ) values (
    p_factory_id, p_project_id, prior_closeout.revision + 1,
    prior_closeout.planned_units, prior_closeout.planned_direct_labor_cents,
    prior_closeout.planned_material_cost_cents,
    prior_closeout.planned_margin_after_direct_costs_cents,
    prior_closeout.deadline_at, prior_closeout.completed_at,
    prior_closeout.factory_timezone, revised_good_units::integer,
    revised_production_value_cents, revised_material_cents,
    prior_closeout.direct_labor_cents, revised_margin_cents,
    prior_closeout.verified_through_at,
    prior_closeout.snapshot || jsonb_build_object(
      'correction_adjustment_id', adjustment_row.id,
      'supersedes_closeout_id', prior_closeout.id,
      'correction_reason_code', adjustment_row.reason_code,
      'gross_verified_units', coalesce(revised_gross_verified_units, 0),
      'adjustment_units', coalesce(revised_adjustment_units, 0),
      'weekly_output', revised_weekly_output
    ),
    auth.uid()
  )
  returning * into revised_closeout;

  insert into public.owner_closeout_evidence_attachments (
    factory_id, closeout_id, project_id, media_object_id, reason_code,
    object_sha256, retention_until, attached_at
  )
  select
    attachment.factory_id, revised_closeout.id, attachment.project_id,
    attachment.media_object_id, attachment.reason_code,
    attachment.object_sha256, attachment.retention_until,
    attachment.attached_at
  from public.owner_closeout_evidence_attachments attachment
  where attachment.factory_id = p_factory_id
    and attachment.closeout_id = prior_closeout.id;

  insert into public.owner_project_audit (
    factory_id, project_id, actor_user_id, actor_type, action,
    target_type, target_id, metadata
  ) values (
    p_factory_id, p_project_id, auth.uid(), 'user',
    'owner.project.closeout_corrected', 'owner_project_closeout',
    revised_closeout.id,
    jsonb_build_object(
      'prior_closeout_id', prior_closeout.id,
      'prior_revision', prior_closeout.revision,
      'new_revision', revised_closeout.revision,
      'adjustment_id', adjustment_row.id,
      'prior_verified_good_units', prior_closeout.verified_good_units,
      'new_verified_good_units', revised_closeout.verified_good_units,
      'prior_material_cost_cents', prior_closeout.material_cost_cents,
      'new_material_cost_cents', revised_closeout.material_cost_cents,
      'prior_margin_after_direct_costs_cents',
        prior_closeout.margin_after_direct_costs_cents,
      'new_margin_after_direct_costs_cents',
        revised_closeout.margin_after_direct_costs_cents
    )
  );

  return revised_closeout;
end;
$$;

create or replace function public.protect_owner_project_closed_state()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.status = 'closed' then
    raise exception 'closed project rows are immutable' using errcode = '55000';
  end if;
  new.updated_at = now();
  return new;
end;
$$;

create trigger owner_projects_protect_closed
before update on public.owner_projects
for each row execute function public.protect_owner_project_closed_state();

create or replace function public.require_open_owner_project()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  target_project_id uuid;
  target_factory_id uuid;
  project_status text;
  teardown_correlation text;
begin
  if tg_op = 'DELETE' then
    target_project_id := old.project_id;
    target_factory_id := old.factory_id;
  else
    target_project_id := new.project_id;
    target_factory_id := new.factory_id;
  end if;
  select project.status into project_status
  from public.owner_projects project
  where project.id = target_project_id
    and project.factory_id = target_factory_id;

  teardown_correlation := current_setting(
    'factoryvision.owner_test_teardown_correlation',
    true
  );
  if tg_op = 'DELETE'
     and current_user = 'postgres'
     and teardown_correlation is not null
     and teardown_correlation <> ''
     and exists (
       select 1
       from public.owner_projects project
       join public.factories factory on factory.id = project.factory_id
       where project.id = target_project_id
         and project.factory_id = target_factory_id
         and project.test_correlation_id::text = teardown_correlation
         and factory.is_test = true
     ) then
    return old;
  end if;

  if project_status not in ('draft', 'open', 'paused') then
    raise exception 'closed project assignments and intervals are immutable'
      using errcode = '55000';
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end;
$$;

create trigger owner_project_assignments_require_open
before insert or update or delete
on public.owner_project_station_assignments
for each row execute function public.require_open_owner_project();
create trigger owner_worker_intervals_require_open
before insert or update or delete
on public.owner_worker_station_intervals
for each row execute function public.require_open_owner_project();
create trigger owner_downtime_require_open
before insert or update or delete
on public.owner_station_downtime_intervals
for each row execute function public.require_open_owner_project();

create or replace function public.append_owner_verification_interval(
  p_factory_id uuid,
  p_station_id uuid,
  p_chunk_id uuid,
  p_source_start_at timestamptz,
  p_source_end_at timestamptz,
  p_status text,
  p_reason_code text default null
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  prior_row public.owner_verification_intervals%rowtype;
  inserted_id uuid;
begin
  perform 1
  from public.video_chunks chunk
  where chunk.id = p_chunk_id
    and chunk.factory_id = p_factory_id
  for update;
  if not found then
    raise exception 'owner verification chunk not found'
      using errcode = '42501';
  end if;

  select * into prior_row
  from public.owner_verification_intervals verification
  where verification.chunk_id = p_chunk_id
    and verification.factory_id = p_factory_id
  order by verification.revision desc
  limit 1;

  insert into public.owner_verification_intervals (
    factory_id, station_id, chunk_id, revision, supersedes_id,
    source_start_at, source_end_at, status, reason_code
  ) values (
    p_factory_id, p_station_id, p_chunk_id,
    coalesce(prior_row.revision, 0) + 1, prior_row.id,
    p_source_start_at, p_source_end_at, p_status, p_reason_code
  )
  returning id into inserted_id;
  return inserted_id;
end;
$$;

create or replace function public.owner_project_published_chunk()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  chunk_row public.video_chunks%rowtype;
  timeline_delta_ms bigint;
  expected_count integer;
  event_count integer;
begin
  chunk_row := new;
  if not (old.state = 'resolved' and new.state = 'published') then
    return new;
  end if;
  if chunk_row.source_set_role <> 'production' then
    return new;
  end if;

  select consensus.resolved_total,
         count(resolved_event.id)::integer
  into expected_count, event_count
  from public.human_finalizations finalization
  join public.consensus_runs consensus
    on consensus.id = finalization.consensus_run_id
   and consensus.factory_id = finalization.factory_id
   and consensus.chunk_id = finalization.chunk_id
  left join public.resolved_human_count_events resolved_event
    on resolved_event.finalization_id = finalization.id
   and resolved_event.factory_id = finalization.factory_id
   and resolved_event.publication_status = 'published'
  where finalization.chunk_id = chunk_row.id
    and finalization.factory_id = chunk_row.factory_id
  group by consensus.resolved_total;
  if expected_count is null or event_count <> expected_count then
    raise exception 'owner publication finalization cardinality is invalid'
      using errcode = '23514';
  end if;
  if exists (
    select 1
    from public.resolved_human_count_events resolved_event
    where resolved_event.chunk_id = chunk_row.id
      and resolved_event.factory_id = chunk_row.factory_id
      and resolved_event.publication_status = 'published'
      and (
        resolved_event.source_time_ms < chunk_row.source_start_ms
        or resolved_event.source_time_ms > chunk_row.source_end_ms
      )
  ) then
    raise exception 'owner publication event lies outside source bounds'
      using errcode = '23514';
  end if;

  timeline_delta_ms := abs(
    (extract(epoch from (chunk_row.source_end_at - chunk_row.source_start_at))
      * 1000)::bigint
    - (chunk_row.source_end_ms - chunk_row.source_start_ms)
  );
  if chunk_row.gap_map <> '[]'::jsonb or timeline_delta_ms > 1000 then
    raise exception 'untrusted source timeline cannot publish owner truth'
      using errcode = '23514';
  end if;

  insert into public.owner_chunk_publication_locks (
    factory_id, chunk_id, published_at
  ) values (
    chunk_row.factory_id, chunk_row.id, chunk_row.published_at
  )
  on conflict (chunk_id) do nothing;

  perform public.append_owner_verification_interval(
    chunk_row.factory_id,
    chunk_row.station_id,
    chunk_row.id,
    chunk_row.source_start_at,
    chunk_row.source_end_at,
    'verified',
    null
  );

  insert into public.owner_production_events (
    factory_id, station_id, chunk_id, resolved_event_id,
    occurred_at, source_time_ms, published_at
  )
  select
    chunk_row.factory_id,
    chunk_row.station_id,
    chunk_row.id,
    resolved_event.id,
    chunk_row.source_start_at
      + (resolved_event.source_time_ms - chunk_row.source_start_ms)
        * interval '1 millisecond',
    resolved_event.source_time_ms,
    resolved_event.published_at
  from public.resolved_human_count_events resolved_event
  where resolved_event.chunk_id = chunk_row.id
    and resolved_event.factory_id = chunk_row.factory_id
    and resolved_event.publication_status = 'published'
  on conflict (resolved_event_id) do nothing;

  insert into public.audit_log (
    factory_id, actor_type, action, target_type, target_id,
    correlation_id, metadata
  ) values (
    chunk_row.factory_id, 'service', 'owner.chunk.published',
    'video_chunk', chunk_row.id, gen_random_uuid(),
    jsonb_build_object('published_at', chunk_row.published_at)
  );
  return new;
end;
$$;

create trigger owner_project_published_chunk
after update of state on public.video_chunks
for each row
when (old.state = 'resolved' and new.state = 'published')
execute function public.owner_project_published_chunk();

create or replace function public.owner_project_revoked_chunk()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not (old.state = 'published' and new.state = 'quarantined') then
    return new;
  end if;
  perform public.append_owner_verification_interval(
    new.factory_id,
    new.station_id,
    new.id,
    new.source_start_at,
    new.source_end_at,
    'coverage_revoked',
    'post_publication_quarantine'
  );
  insert into public.audit_log (
    factory_id, actor_type, action, target_type, target_id,
    correlation_id, metadata
  ) values (
    new.factory_id, 'service', 'owner.chunk.coverage_revoked',
    'video_chunk', new.id, gen_random_uuid(),
    jsonb_build_object('prior_state', old.state, 'new_state', new.state)
  );
  return new;
end;
$$;

create trigger owner_project_revoked_chunk
after update of state on public.video_chunks
for each row
when (old.state = 'published' and new.state = 'quarantined')
execute function public.owner_project_revoked_chunk();

create or replace function public.guard_chunk_state_transition()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.state = 'published' and new.published_at is null then
    raise exception 'published chunks require published_at' using errcode = '23514';
  end if;
  if old.published_at is not null
     and new.published_at is distinct from old.published_at then
    raise exception 'chunk published_at is immutable once set' using errcode = '55000';
  end if;
  if old.state = 'quarantined'
     and new.state = 'transcoding'
     and exists (
       select 1
       from public.owner_chunk_publication_locks publication_lock
       where publication_lock.chunk_id = old.id
         and publication_lock.factory_id = old.factory_id
     ) then
    raise exception 'published owner chunk cannot leave quarantine'
      using errcode = '55000';
  end if;

  if new.state is distinct from old.state and not (
    (old.state = 'ingesting' and new.state in ('transcoding', 'quarantined', 'deleted'))
    or (old.state = 'transcoding' and new.state in ('ready', 'quarantined', 'deleted'))
    or (old.state = 'ready' and new.state in ('assigned', 'quarantined', 'retained', 'deleted'))
    or (old.state = 'assigned' and new.state in ('ready', 'resolving', 'quarantined'))
    or (
      old.state = 'assigned'
      and new.state = 'resolved'
      and exists (
        select 1 from public.human_finalizations finalization
        where finalization.chunk_id = old.id
          and finalization.factory_id = old.factory_id
      )
    )
    or (old.state = 'resolving' and new.state in ('assigned', 'resolved', 'quarantined'))
    or (old.state = 'resolved' and new.state in ('assigned', 'published', 'quarantined'))
    or (old.state = 'published' and new.state in ('retained', 'quarantined'))
    or (old.state = 'quarantined' and new.state in ('transcoding', 'retained', 'deleted'))
    or (old.state = 'retained' and new.state = 'deleted')
  ) then
    raise exception 'invalid chunk state transition from % to %', old.state, new.state
      using errcode = '23514';
  end if;

  return new;
end;
$$;

create or replace function public.service_publish_resolved_chunks(
  p_limit integer default 25
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  chunk_row public.video_chunks%rowtype;
  expected_count integer;
  event_count integer;
  timeline_delta_ms bigint;
  published_count integer := 0;
begin
  if p_limit < 1 or p_limit > 500 then
    raise exception 'publication batch limit is out of range'
      using errcode = '22023';
  end if;

  for chunk_row in
    select chunk.*
    from public.video_chunks chunk
    where chunk.state = 'resolved'
      and chunk.source_set_role = 'production'
    order by chunk.source_start_at
    limit p_limit
    for update skip locked
  loop
    select consensus.resolved_total,
           count(resolved_event.id)::integer
    into expected_count, event_count
    from public.human_finalizations finalization
    join public.consensus_runs consensus
      on consensus.id = finalization.consensus_run_id
     and consensus.factory_id = finalization.factory_id
     and consensus.chunk_id = finalization.chunk_id
    left join public.resolved_human_count_events resolved_event
      on resolved_event.finalization_id = finalization.id
     and resolved_event.factory_id = finalization.factory_id
     and resolved_event.publication_status = 'published'
    where finalization.chunk_id = chunk_row.id
      and finalization.factory_id = chunk_row.factory_id
    group by consensus.resolved_total;

    timeline_delta_ms := abs(
      (extract(epoch from (chunk_row.source_end_at - chunk_row.source_start_at))
        * 1000)::bigint
      - (chunk_row.source_end_ms - chunk_row.source_start_ms)
    );

    if expected_count is null or event_count <> expected_count then
      perform public.append_owner_verification_interval(
        chunk_row.factory_id, chunk_row.station_id, chunk_row.id,
        chunk_row.source_start_at, chunk_row.source_end_at,
        'no_published_coverage', 'finalization_cardinality_invalid'
      );
      update public.video_chunks
      set state = 'quarantined', updated_at = now()
      where id = chunk_row.id;
      continue;
    end if;

    if exists (
      select 1
      from public.resolved_human_count_events resolved_event
      where resolved_event.chunk_id = chunk_row.id
        and resolved_event.factory_id = chunk_row.factory_id
        and resolved_event.publication_status = 'published'
        and (
          resolved_event.source_time_ms < chunk_row.source_start_ms
          or resolved_event.source_time_ms > chunk_row.source_end_ms
        )
    ) then
      perform public.append_owner_verification_interval(
        chunk_row.factory_id, chunk_row.station_id, chunk_row.id,
        chunk_row.source_start_at, chunk_row.source_end_at,
        'no_published_coverage', 'event_outside_source_bounds'
      );
      update public.video_chunks
      set state = 'quarantined', updated_at = now()
      where id = chunk_row.id;
      continue;
    end if;

    if chunk_row.gap_map <> '[]'::jsonb or timeline_delta_ms > 1000 then
      perform public.append_owner_verification_interval(
        chunk_row.factory_id, chunk_row.station_id, chunk_row.id,
        chunk_row.source_start_at, chunk_row.source_end_at,
        'timeline_untrusted', 'gap_or_clock_drift'
      );
      update public.video_chunks
      set state = 'quarantined', updated_at = now()
      where id = chunk_row.id;
      continue;
    end if;

    update public.video_chunks
    set state = 'published',
        published_at = coalesce(published_at, now()),
        updated_at = now()
    where id = chunk_row.id;
    published_count := published_count + 1;
  end loop;

  return published_count;
end;
$$;

drop policy if exists resolved_human_events_read_owner
  on public.resolved_human_count_events;

alter table public.owner_projects enable row level security;
alter table public.owner_project_drafts enable row level security;
alter table public.owner_workers enable row level security;
alter table public.owner_project_station_assignments enable row level security;
alter table public.owner_worker_station_intervals enable row level security;
alter table public.owner_station_downtime_intervals enable row level security;
alter table public.owner_output_adjustments enable row level security;
alter table public.owner_project_closeouts enable row level security;
alter table public.owner_project_audit enable row level security;
alter table public.owner_project_evidence_attachments enable row level security;
alter table public.owner_closeout_evidence_attachments enable row level security;
alter table public.owner_production_events enable row level security;
alter table public.owner_verification_intervals enable row level security;
alter table public.owner_chunk_publication_locks enable row level security;
alter table public.owner_test_teardown_receipts enable row level security;

alter table public.owner_projects force row level security;
alter table public.owner_project_drafts force row level security;
alter table public.owner_workers force row level security;
alter table public.owner_project_station_assignments force row level security;
alter table public.owner_worker_station_intervals force row level security;
alter table public.owner_station_downtime_intervals force row level security;
alter table public.owner_output_adjustments force row level security;
alter table public.owner_project_closeouts force row level security;
alter table public.owner_project_audit force row level security;
alter table public.owner_project_evidence_attachments force row level security;
alter table public.owner_closeout_evidence_attachments force row level security;
alter table public.owner_production_events force row level security;
alter table public.owner_verification_intervals force row level security;
alter table public.owner_chunk_publication_locks force row level security;
alter table public.owner_test_teardown_receipts force row level security;

create policy owner_projects_read
on public.owner_projects for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_project_drafts_read
on public.owner_project_drafts for select to authenticated
using (
  created_by = (select auth.uid())
  and public.owner_has_active_role(factory_id, 'owner')
);
create policy owner_workers_read
on public.owner_workers for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_project_assignments_read
on public.owner_project_station_assignments for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_worker_intervals_read
on public.owner_worker_station_intervals for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_downtime_read
on public.owner_station_downtime_intervals for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_adjustments_read
on public.owner_output_adjustments for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_closeouts_read
on public.owner_project_closeouts for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_project_audit_read
on public.owner_project_audit for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_production_events_read
on public.owner_production_events for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));
create policy owner_verification_intervals_read
on public.owner_verification_intervals for select to authenticated
using (public.owner_has_active_role(factory_id, 'owner'));

grant select on public.owner_projects to authenticated;
grant select on public.owner_project_drafts to authenticated;
grant select on public.owner_workers to authenticated;
grant select on public.owner_project_station_assignments to authenticated;
grant select on public.owner_worker_station_intervals to authenticated;
grant select on public.owner_station_downtime_intervals to authenticated;
grant select on public.owner_output_adjustments to authenticated;
grant select on public.owner_project_closeouts to authenticated;
grant select on public.owner_project_audit to authenticated;
grant select on public.owner_production_events to authenticated;
grant select on public.owner_verification_intervals to authenticated;

revoke all on public.owner_project_evidence_attachments
  from public, anon, authenticated;
revoke all on public.owner_closeout_evidence_attachments
  from public, anon, authenticated;
grant all on public.owner_project_evidence_attachments to service_role;
grant all on public.owner_closeout_evidence_attachments to service_role;
revoke all on public.owner_chunk_publication_locks
  from public, anon, authenticated;
grant all on public.owner_chunk_publication_locks to service_role;
revoke all on public.owner_test_teardown_receipts
  from public, anon, authenticated;
grant select on public.owner_test_teardown_receipts to service_role;

revoke all on function public.owner_has_active_role(uuid, text)
  from public, anon;
revoke all on function public.owner_authorize_session(uuid)
  from public, anon;
revoke all on function public.owner_shift_calendar_is_valid(uuid, jsonb)
  from public, anon, authenticated;
revoke all on function public.owner_scheduled_work_milliseconds(
  timestamptz, timestamptz, jsonb
) from public, anon, authenticated;
revoke all on function public.owner_start_project(
  uuid, text, text, integer, bigint, bigint, bigint, bigint, timestamptz,
  timestamptz, jsonb, integer, text, uuid, uuid[], uuid
) from public, anon;
revoke all on function public.owner_save_project_draft(uuid, jsonb)
  from public, anon;
revoke all on function public.owner_upsert_worker(
  uuid, uuid, text, text, text, boolean, text, boolean
) from public, anon;
revoke all on function public.owner_record_downtime(
  uuid, uuid, uuid, timestamptz, timestamptz, text, text
) from public, anon;
revoke all on function public.owner_close_project(
  uuid, uuid, bigint, timestamptz
) from public, anon;
revoke all on function public.owner_correct_closeout(
  uuid, uuid, text, integer, text, text, timestamptz, bigint
) from public, anon;
grant execute on function public.owner_has_active_role(uuid, text)
  to authenticated;
grant execute on function public.owner_authorize_session(uuid)
  to authenticated;
grant execute on function public.owner_start_project(
  uuid, text, text, integer, bigint, bigint, bigint, bigint, timestamptz,
  timestamptz, jsonb, integer, text, uuid, uuid[], uuid
) to authenticated;
revoke all on function public.owner_teardown_test_correlation(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.owner_teardown_test_correlation(uuid, uuid)
  to service_role;
revoke all on function public.service_attach_owner_project_evidence(
  uuid, uuid, uuid, text
) from public, anon, authenticated;
grant execute on function public.service_attach_owner_project_evidence(
  uuid, uuid, uuid, text
) to service_role;
revoke all on function public.owner_history_evidence(uuid, uuid)
  from public, anon;
grant execute on function public.owner_history_evidence(uuid, uuid)
  to authenticated;
revoke all on function public.can_read_owner_evidence(text, text)
  from public, anon;
grant execute on function public.can_read_owner_evidence(text, text)
  to authenticated;
revoke all on function public.can_read_qualification_media(text, text)
  from public, anon;
grant execute on function public.can_read_qualification_media(text, text)
  to authenticated;
grant execute on function public.owner_save_project_draft(uuid, jsonb)
  to authenticated;
grant execute on function public.owner_upsert_worker(
  uuid, uuid, text, text, text, boolean, text, boolean
) to authenticated;
grant execute on function public.owner_record_downtime(
  uuid, uuid, uuid, timestamptz, timestamptz, text, text
) to authenticated;
grant execute on function public.owner_close_project(
  uuid, uuid, bigint, timestamptz
) to authenticated;
grant execute on function public.owner_correct_closeout(
  uuid, uuid, text, integer, text, text, timestamptz, bigint
) to authenticated;

revoke all on function public.append_owner_verification_interval(
  uuid, uuid, uuid, timestamptz, timestamptz, text, text
) from public, anon, authenticated;
revoke all on function public.owner_project_published_chunk()
  from public, anon, authenticated;
revoke all on function public.owner_project_revoked_chunk()
  from public, anon, authenticated;
revoke all on function public.service_publish_resolved_chunks(integer)
  from public, anon, authenticated;
grant execute on function public.append_owner_verification_interval(
  uuid, uuid, uuid, timestamptz, timestamptz, text, text
) to service_role;
grant execute on function public.service_publish_resolved_chunks(integer)
  to service_role;

create trigger owner_project_audit_append_only
before update or delete on public.owner_project_audit
for each row execute function public.owner_test_teardown_delete_guard();
create trigger owner_project_audit_reject_truncate
before truncate on public.owner_project_audit
for each statement execute function public.reject_append_only_change();
create trigger owner_project_evidence_append_only
before update or delete on public.owner_project_evidence_attachments
for each row execute function public.owner_test_teardown_delete_guard();
create trigger owner_project_evidence_reject_truncate
before truncate on public.owner_project_evidence_attachments
for each statement execute function public.reject_append_only_change();
create trigger owner_closeout_evidence_append_only
before update or delete on public.owner_closeout_evidence_attachments
for each row execute function public.owner_test_teardown_delete_guard();
create trigger owner_closeout_evidence_reject_truncate
before truncate on public.owner_closeout_evidence_attachments
for each statement execute function public.reject_append_only_change();
create trigger owner_project_closeouts_append_only
before update or delete on public.owner_project_closeouts
for each row execute function public.owner_test_teardown_delete_guard();
create trigger owner_project_closeouts_reject_truncate
before truncate on public.owner_project_closeouts
for each statement execute function public.reject_append_only_change();
create trigger owner_output_adjustments_append_only
before update or delete on public.owner_output_adjustments
for each row execute function public.owner_test_teardown_delete_guard();
create trigger owner_output_adjustments_reject_truncate
before truncate on public.owner_output_adjustments
for each statement execute function public.reject_append_only_change();
create trigger owner_production_events_append_only
before update or delete on public.owner_production_events
for each row execute function public.reject_append_only_change();
create trigger owner_production_events_reject_truncate
before truncate on public.owner_production_events
for each statement execute function public.reject_append_only_change();
create trigger owner_verification_intervals_append_only
before update or delete on public.owner_verification_intervals
for each row execute function public.reject_append_only_change();
create trigger owner_verification_intervals_reject_truncate
before truncate on public.owner_verification_intervals
for each statement execute function public.reject_append_only_change();
create trigger owner_chunk_publication_locks_append_only
before update or delete on public.owner_chunk_publication_locks
for each row execute function public.reject_append_only_change();
create trigger owner_chunk_publication_locks_reject_truncate
before truncate on public.owner_chunk_publication_locks
for each statement execute function public.reject_append_only_change();
create trigger owner_test_teardown_receipts_append_only
before update or delete on public.owner_test_teardown_receipts
for each row execute function public.reject_append_only_change();
create trigger owner_test_teardown_receipts_reject_truncate
before truncate on public.owner_test_teardown_receipts
for each statement execute function public.reject_append_only_change();

revoke truncate on table
  public.owner_project_audit,
  public.owner_project_evidence_attachments,
  public.owner_closeout_evidence_attachments,
  public.owner_project_closeouts,
  public.owner_output_adjustments,
  public.owner_production_events,
  public.owner_verification_intervals,
  public.owner_chunk_publication_locks,
  public.owner_test_teardown_receipts
from service_role;

drop policy if exists factory_vision_media_server_only on storage.objects;
drop policy if exists factory_vision_media_anon_server_only on storage.objects;
drop policy if exists factory_vision_media_authenticated_read on storage.objects;
drop policy if exists factory_vision_media_authenticated_insert on storage.objects;
drop policy if exists factory_vision_media_authenticated_update on storage.objects;
drop policy if exists factory_vision_media_authenticated_delete on storage.objects;
drop policy if exists owner_read_retained_evidence on storage.objects;
drop policy if exists reviewer_read_qualification_media on storage.objects;

create policy factory_vision_media_anon_server_only
on storage.objects
as restrictive
for all
to anon
using (
  bucket_id not in (
    'factory-originals', 'review-renditions', 'evidence-clips'
  )
)
with check (
  bucket_id not in (
    'factory-originals', 'review-renditions', 'evidence-clips'
  )
);

create policy factory_vision_media_authenticated_read
on storage.objects
as restrictive
for select
to authenticated
using (
  bucket_id not in (
    'factory-originals', 'review-renditions', 'evidence-clips'
  )
  or (
    bucket_id = 'review-renditions'
    and (
      public.can_read_assignment_media(bucket_id, name)
      or public.can_read_qualification_media(bucket_id, name)
    )
  )
  or (
    bucket_id = 'evidence-clips'
    and public.can_read_owner_evidence(bucket_id, name)
  )
);

create policy factory_vision_media_authenticated_insert
on storage.objects
as restrictive
for insert
to authenticated
with check (
  bucket_id not in (
    'factory-originals', 'review-renditions', 'evidence-clips'
  )
);

create policy factory_vision_media_authenticated_update
on storage.objects
as restrictive
for update
to authenticated
using (
  bucket_id not in (
    'factory-originals', 'review-renditions', 'evidence-clips'
  )
)
with check (
  bucket_id not in (
    'factory-originals', 'review-renditions', 'evidence-clips'
  )
);

create policy factory_vision_media_authenticated_delete
on storage.objects
as restrictive
for delete
to authenticated
using (
  bucket_id not in (
    'factory-originals', 'review-renditions', 'evidence-clips'
  )
);

create policy owner_read_retained_evidence
on storage.objects
for select
to authenticated
using (
  bucket_id = 'evidence-clips'
  and public.can_read_owner_evidence(bucket_id, name)
);

create policy reviewer_read_qualification_media
on storage.objects
for select
to authenticated
using (
  bucket_id = 'review-renditions'
  and public.can_read_qualification_media(bucket_id, name)
);

do $$
begin
  if not exists (
    select 1 from cron.job
    where jobname = 'factoryvision-owner-publication'
  ) then
    perform cron.schedule(
      'factoryvision-owner-publication',
      '* * * * *',
      'select public.service_publish_resolved_chunks();'
    );
  end if;
end;
$$;
