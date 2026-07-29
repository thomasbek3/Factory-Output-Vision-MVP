#!/usr/bin/env bash
set -euo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(cd "${CONSOLE_DIR}/.." && pwd)"
MIGRATION="${ROOT_DIR}/supabase/migrations/20260729070000_owner_v2_core.sql"
SQL_FILE="$(mktemp)"
trap 'rm -f "${SQL_FILE}"' EXIT

: "${DATABASE_URL:?DATABASE_URL is required}"

python3 - "${MIGRATION}" "${SQL_FILE}" <<'PY'
from pathlib import Path
import sys

migration = Path(sys.argv[1]).read_text(encoding="utf-8")
output = Path(sys.argv[2])

tables_start = migration.index("create table public.owner_projects")
tables_end = migration.index(
    "create table public.owner_production_events",
    tables_start,
)
schedule_start = migration.index(
    "create or replace function public.owner_scheduled_work_milliseconds"
)
schedule_end = migration.index(
    "create or replace function public.owner_save_project_draft",
    schedule_start,
)
close_start = migration.index(
    "create or replace function public.owner_close_project"
)
close_end = migration.index(
    "create or replace function public.protect_owner_project_closed_state",
    close_start,
)

scaffold = r"""
\set ON_ERROR_STOP on
begin;
create extension if not exists btree_gist;
create schema auth;
create table public.factories (
  id uuid primary key,
  timezone text not null
);
create table public.profiles (id uuid primary key);
create table public.stations (
  id uuid primary key,
  factory_id uuid not null references public.factories(id),
  alias text not null,
  unique (id, factory_id)
);
create table public.media_objects (
  id uuid primary key,
  factory_id uuid not null,
  bucket_id text not null,
  object_path text not null,
  object_sha256 text not null,
  content_type text not null,
  byte_size bigint not null,
  status text not null,
  retention_until timestamptz,
  unique (id, factory_id)
);
create or replace function auth.uid()
returns uuid
language sql
immutable
as $$ select '61000000-0000-0000-0000-000000000001'::uuid $$;
create or replace function public.owner_has_active_role(uuid, text)
returns boolean
language sql
immutable
as $$ select true $$;
create or replace function public.reject_append_only_change()
returns trigger
language plpgsql
as $$
begin
  raise exception 'append-only table cannot be changed' using errcode = '55000';
end;
$$;
"""

dependent_tables = r"""
create table public.owner_production_events (
  id uuid primary key,
  factory_id uuid not null,
  station_id uuid not null,
  chunk_id uuid not null,
  occurred_at timestamptz not null
);
create table public.owner_verification_intervals (
  id uuid primary key,
  factory_id uuid not null,
  station_id uuid not null,
  chunk_id uuid not null,
  source_start_at timestamptz not null,
  source_end_at timestamptz not null,
  status text not null,
  revision integer not null
);
"""

append_only_triggers = r"""
create trigger owner_project_audit_append_only
before update or delete on public.owner_project_audit
for each row execute function public.reject_append_only_change();
create trigger owner_project_audit_reject_truncate
before truncate on public.owner_project_audit
for each statement execute function public.reject_append_only_change();
create trigger owner_project_closeouts_append_only
before update or delete on public.owner_project_closeouts
for each row execute function public.reject_append_only_change();
create trigger owner_project_closeouts_reject_truncate
before truncate on public.owner_project_closeouts
for each statement execute function public.reject_append_only_change();
create trigger owner_output_adjustments_append_only
before update or delete on public.owner_output_adjustments
for each row execute function public.reject_append_only_change();
create trigger owner_output_adjustments_reject_truncate
before truncate on public.owner_output_adjustments
for each statement execute function public.reject_append_only_change();
create trigger owner_closeout_evidence_reject_truncate
before truncate on public.owner_closeout_evidence_attachments
for each statement execute function public.reject_append_only_change();
"""

fixture = r"""
insert into public.factories values
  ('11000000-0000-0000-0000-000000000001', 'UTC');
insert into public.profiles values
  ('61000000-0000-0000-0000-000000000001');
insert into public.stations values
  (
    '21000000-0000-0000-0000-000000000001',
    '11000000-0000-0000-0000-000000000001',
    'Press Bay North'
  ),
  (
    '21000000-0000-0000-0000-000000000002',
    '11000000-0000-0000-0000-000000000001',
    'Weld Cell West'
  );
insert into public.owner_projects (
  id, factory_id, name, client, target_units, unit_value_cents,
  unit_material_cost_cents, loaded_labor_rate_cents_per_hour,
  planned_direct_labor_cents, target_margin_bps, start_at, deadline,
  shift_calendar, status, created_by
) values (
  '41000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  'History Fixture',
  'Fixture Customer',
  2,
  10000,
  2000,
  2000,
  32000,
  1000,
  '2026-05-05T09:00:00Z',
  '2026-05-12T17:00:00Z',
  '{"timezone":"UTC","shifts":[{"weekday":2,"start":"09:00","end":"17:00"}]}'::jsonb,
  'open',
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_workers (
  id, factory_id, display_name, employee_code, primary_role, status, created_by
) values (
  '31000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  'Fixture Worker',
  'FV-001',
  'Operator',
  'active',
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_project_station_assignments (
  id, factory_id, project_id, station_id, effective_start, created_by
) values (
  '51000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '2026-05-05T09:00:00Z',
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_worker_station_intervals (
  id, factory_id, project_id, station_id, worker_id, effective_start,
  loaded_labor_rate_cents_per_hour, source, created_by
) values (
  '52000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '31000000-0000-0000-0000-000000000001',
  '2026-05-05T09:00:00Z',
  2000,
  'badge',
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_verification_intervals values (
  '53000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000001',
  '2026-05-05T09:00:00Z',
  '2026-05-05T17:00:00Z',
  'verified',
  1
);
insert into public.owner_verification_intervals values (
  '53000000-0000-0000-0000-000000000002',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000002',
  '2026-05-12T09:00:00Z',
  '2026-05-12T17:00:00Z',
  'verified',
  1
);
insert into public.owner_production_events values (
  '55000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000001',
  '2026-05-05T12:00:00Z'
);
insert into public.owner_production_events values (
  '55000000-0000-0000-0000-000000000002',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000002',
  '2026-05-12T12:00:00Z'
);

-- The closeout must retain the timezone pinned into the project calendar even
-- if the factory default changes while the project is open.
update public.factories
set timezone = 'America/New_York'
where id = '11000000-0000-0000-0000-000000000001';

select public.owner_close_project(
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000001',
  2000,
  '2026-05-12T17:00:00Z'
);

select public.owner_correct_closeout(
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000001',
  'correction',
  2,
  'verified-count-correction',
  'Correction fixture',
  '2026-05-12T12:00:00Z',
  null
);

-- A chunk published after close must not rewrite the immutable closeout
-- baseline or prevent a later owner correction.
insert into public.owner_verification_intervals values (
  '53000000-0000-0000-0000-000000000003',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000003',
  '2026-05-12T16:00:00Z',
  '2026-05-12T17:00:00Z',
  'verified',
  1
);
insert into public.owner_production_events values (
  '55000000-0000-0000-0000-000000000003',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000003',
  '2026-05-12T16:30:00Z'
);
select public.owner_correct_closeout(
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000001',
  'correction',
  1,
  'post-publication-correction',
  'Late publication does not rewrite the baseline',
  '2026-05-12T16:45:00Z',
  null
);

do $$
declare
  closeout public.owner_project_closeouts%rowtype;
  denied boolean;
begin
  select * into closeout
  from public.owner_project_closeouts
  order by revision desc
  limit 1;
  if closeout.revision <> 3 or closeout.verified_good_units <> 5 then
    raise exception 'verified closeout units were not captured';
  end if;
  if closeout.snapshot->>'project_name' <> 'History Fixture'
     or closeout.snapshot->>'customer_name' <> 'Fixture Customer' then
    raise exception 'immutable project identity snapshot is missing';
  end if;
  if closeout.snapshot->'station_names' <> '["Press Bay North"]'::jsonb
     or closeout.snapshot->'team_names' <> '["Fixture Worker"]'::jsonb then
    raise exception 'immutable station/team snapshot is missing';
  end if;
  if (closeout.snapshot->>'planned_schedule_minutes')::bigint <> 960
     or (closeout.snapshot->>'actual_schedule_minutes')::bigint <> 960
     or (closeout.snapshot->>'actual_direct_labor_minutes')::bigint <> 960 then
    raise exception 'schedule/labor duration snapshot is incorrect: %',
      closeout.snapshot;
  end if;
  if (
       select coalesce(sum((bucket->>'actual_units')::bigint), 0)
       from jsonb_array_elements(closeout.snapshot->'weekly_output') bucket
     ) <> closeout.verified_good_units
     or jsonb_array_length(closeout.snapshot->'weekly_output') <> 2 then
    raise exception 'weekly verified output snapshot is incorrect: %',
      closeout.snapshot->'weekly_output';
  end if;
  if (closeout.snapshot->>'gross_verified_units')::bigint <> 2
     or (closeout.snapshot->>'adjustment_units')::bigint <> 3 then
    raise exception 'corrected closeout reconciliation fields are stale';
  end if;
  if (closeout.snapshot->>'verification_has_gap')::boolean
     or closeout.verified_through_at <> '2026-05-12T17:00:00Z' then
    raise exception 'scheduled overnight was treated as a verification gap';
  end if;
  if closeout.factory_timezone <> 'UTC' then
    raise exception 'closeout did not retain the project timezone';
  end if;
  if (select count(*) from public.owner_project_closeouts) <> 3
     or (select count(*) from public.owner_project_audit) <> 3 then
    raise exception 'closeout correction did not append revision and audit';
  end if;

  denied := false;
  begin update public.owner_project_closeouts set revision = 9; exception when sqlstate '55000' then denied := true; end;
  if not denied then raise exception 'closeout update was not denied'; end if;
  denied := false;
  begin delete from public.owner_project_closeouts; exception when sqlstate '55000' then denied := true; end;
  if not denied then raise exception 'closeout delete was not denied'; end if;
  denied := false;
  begin
    truncate public.owner_project_closeouts,
      public.owner_closeout_evidence_attachments;
  exception when sqlstate '55000' then
    denied := true;
  end;
  if not denied then raise exception 'closeout truncate was not denied'; end if;

  denied := false;
  begin update public.owner_project_audit set action = 'changed'; exception when sqlstate '55000' then denied := true; end;
  if not denied then raise exception 'audit update was not denied'; end if;
  denied := false;
  begin delete from public.owner_project_audit; exception when sqlstate '55000' then denied := true; end;
  if not denied then raise exception 'audit delete was not denied'; end if;
  denied := false;
  begin truncate public.owner_project_audit; exception when sqlstate '55000' then denied := true; end;
  if not denied then raise exception 'audit truncate was not denied'; end if;

  denied := false;
  begin update public.owner_output_adjustments set note = 'changed'; exception when sqlstate '55000' then denied := true; end;
  if not denied then raise exception 'adjustment update was not denied'; end if;
  denied := false;
  begin delete from public.owner_output_adjustments; exception when sqlstate '55000' then denied := true; end;
  if not denied then raise exception 'adjustment delete was not denied'; end if;
  denied := false;
  begin truncate public.owner_output_adjustments; exception when sqlstate '55000' then denied := true; end;
  if not denied then raise exception 'adjustment truncate was not denied'; end if;
end
$$;

-- A true interior scheduled hole is a gap; trailing publication lag is not.
insert into public.owner_projects (
  id, factory_id, name, client, target_units, unit_value_cents,
  unit_material_cost_cents, loaded_labor_rate_cents_per_hour,
  planned_direct_labor_cents, target_margin_bps, start_at, deadline,
  shift_calendar, status, created_by
) values
(
  '41000000-0000-0000-0000-000000000002',
  '11000000-0000-0000-0000-000000000001',
  'Interior gap fixture',
  'Fixture Customer',
  1, 10000, 2000, 2000, 16000, 1000,
  '2026-05-19T09:00:00Z',
  '2026-05-19T17:00:00Z',
  '{"timezone":"UTC","shifts":[{"weekday":2,"start":"09:00","end":"17:00"}]}'::jsonb,
  'open',
  '61000000-0000-0000-0000-000000000001'
),
(
  '41000000-0000-0000-0000-000000000003',
  '11000000-0000-0000-0000-000000000001',
  'Trailing lag fixture',
  'Fixture Customer',
  1, 10000, 2000, 2000, 16000, 1000,
  '2026-05-26T09:00:00Z',
  '2026-05-26T17:00:00Z',
  '{"timezone":"UTC","shifts":[{"weekday":2,"start":"09:00","end":"17:00"}]}'::jsonb,
  'open',
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_project_station_assignments (
  id, factory_id, project_id, station_id, effective_start, effective_end,
  created_by
) values
(
  '51000000-0000-0000-0000-000000000002',
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000002',
  '21000000-0000-0000-0000-000000000001',
  '2026-05-19T09:00:00Z',
  '2026-05-19T12:00:00Z',
  '61000000-0000-0000-0000-000000000001'
),
(
  '51000000-0000-0000-0000-000000000003',
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000003',
  '21000000-0000-0000-0000-000000000001',
  '2026-05-26T09:00:00Z',
  null,
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_verification_intervals values
(
  '53000000-0000-0000-0000-000000000004',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000004',
  '2026-05-19T09:00:00Z',
  '2026-05-19T10:00:00Z',
  'verified',
  1
),
(
  '53000000-0000-0000-0000-000000000005',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000005',
  '2026-05-19T11:00:00Z',
  '2026-05-19T12:00:00Z',
  'verified',
  1
),
(
  '53000000-0000-0000-0000-000000000006',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000006',
  '2026-05-26T09:00:00Z',
  '2026-05-26T10:00:00Z',
  'verified',
  1
);
select public.owner_close_project(
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000002',
  0,
  '2026-05-19T12:00:00Z'
);
select public.owner_close_project(
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000003',
  0,
  '2026-05-26T12:00:00Z'
);
do $$
declare
  interior public.owner_project_closeouts%rowtype;
  trailing_closeout public.owner_project_closeouts%rowtype;
begin
  select * into interior
  from public.owner_project_closeouts
  where project_id = '41000000-0000-0000-0000-000000000002';
  select * into trailing_closeout
  from public.owner_project_closeouts
  where project_id = '41000000-0000-0000-0000-000000000003';
  if not (interior.snapshot->>'verification_has_gap')::boolean
     or interior.verified_through_at <> '2026-05-19T10:00:00Z' then
    raise exception 'interior scheduled verification gap was not preserved: %',
      interior.snapshot;
  end if;
  if (trailing_closeout.snapshot->>'verification_has_gap')::boolean
     or trailing_closeout.verified_through_at
       <> '2026-05-26T10:00:00Z' then
    raise exception 'trailing verification lag was mislabeled as a gap: %',
      trailing_closeout.snapshot;
  end if;
end
$$;

-- Trailing lag on one station must not become a gap merely because another
-- station has later complete coverage.
insert into public.owner_projects (
  id, factory_id, name, client, target_units, unit_value_cents,
  unit_material_cost_cents, loaded_labor_rate_cents_per_hour,
  planned_direct_labor_cents, target_margin_bps, start_at, deadline,
  shift_calendar, status, created_by
) values (
  '41000000-0000-0000-0000-000000000004',
  '11000000-0000-0000-0000-000000000001',
  'Two-station trailing lag fixture',
  'Fixture Customer',
  1, 10000, 2000, 2000, 16000, 1000,
  '2026-06-02T09:00:00Z',
  '2026-06-02T17:00:00Z',
  '{"timezone":"UTC","shifts":[{"weekday":2,"start":"09:00","end":"17:00"}]}'::jsonb,
  'open',
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_project_station_assignments (
  id, factory_id, project_id, station_id, effective_start, created_by
) values
(
  '51000000-0000-0000-0000-000000000004',
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000004',
  '21000000-0000-0000-0000-000000000001',
  '2026-06-02T09:00:00Z',
  '61000000-0000-0000-0000-000000000001'
),
(
  '51000000-0000-0000-0000-000000000005',
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000004',
  '21000000-0000-0000-0000-000000000002',
  '2026-06-02T09:00:00Z',
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_verification_intervals values
(
  '53000000-0000-0000-0000-000000000007',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000001',
  '54000000-0000-0000-0000-000000000007',
  '2026-06-02T09:00:00Z',
  '2026-06-02T12:00:00Z',
  'verified',
  1
),
(
  '53000000-0000-0000-0000-000000000008',
  '11000000-0000-0000-0000-000000000001',
  '21000000-0000-0000-0000-000000000002',
  '54000000-0000-0000-0000-000000000008',
  '2026-06-02T09:00:00Z',
  '2026-06-02T10:00:00Z',
  'verified',
  1
);
select public.owner_close_project(
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000004',
  0,
  '2026-06-02T12:00:00Z'
);
do $$
declare
  closeout public.owner_project_closeouts%rowtype;
begin
  select * into closeout
  from public.owner_project_closeouts
  where project_id = '41000000-0000-0000-0000-000000000004';
  if (closeout.snapshot->>'verification_has_gap')::boolean
     or closeout.verified_through_at <> '2026-06-02T10:00:00Z' then
    raise exception 'cross-station trailing lag became a false gap: %',
      closeout.snapshot;
  end if;
end
$$;

-- Corrections key weekly buckets by ISO week start, not a repeated display
-- label that can occur in multi-year projects.
insert into public.owner_projects (
  id, factory_id, name, client, target_units, unit_value_cents,
  unit_material_cost_cents, loaded_labor_rate_cents_per_hour,
  planned_direct_labor_cents, target_margin_bps, start_at, deadline,
  shift_calendar, status, closed_at, created_by
) values (
  '41000000-0000-0000-0000-000000000005',
  '11000000-0000-0000-0000-000000000001',
  'Repeated week label fixture',
  'Fixture Customer',
  2, 10000, 2000, 0, 0, 1000,
  '2025-05-01T09:00:00Z',
  '2026-05-10T17:00:00Z',
  '{"timezone":"UTC","shifts":[{"weekday":1,"start":"09:00","end":"17:00"}]}'::jsonb,
  'closed',
  '2026-05-10T17:00:00Z',
  '61000000-0000-0000-0000-000000000001'
);
insert into public.owner_project_closeouts (
  factory_id, project_id, revision, planned_units,
  planned_direct_labor_cents, planned_material_cost_cents,
  planned_margin_after_direct_costs_cents, deadline_at, completed_at,
  factory_timezone, verified_good_units, production_value_cents,
  material_cost_cents, direct_labor_cents,
  margin_after_direct_costs_cents, verified_through_at, snapshot, created_by
) values (
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000005',
  1, 2, 0, 4000, 16000,
  '2026-05-10T17:00:00Z',
  '2026-05-10T17:00:00Z',
  'UTC', 2, 20000, 4000, 0, 16000,
  '2026-05-10T17:00:00Z',
  '{
    "gross_verified_units": 2,
    "adjustment_units": 0,
    "weekly_output": [
      {"week_start":"2025-05-05","label":"May 04","planned_units":null,"actual_units":1},
      {"week_start":"2026-05-04","label":"May 04","planned_units":null,"actual_units":1}
    ]
  }'::jsonb,
  '61000000-0000-0000-0000-000000000001'
);
select public.owner_correct_closeout(
  '11000000-0000-0000-0000-000000000001',
  '41000000-0000-0000-0000-000000000005',
  'correction',
  1,
  'iso-week-correction',
  'Only the 2026 week changes.',
  '2026-05-05T12:00:00Z',
  null
);
do $$
declare
  closeout public.owner_project_closeouts%rowtype;
begin
  select * into closeout
  from public.owner_project_closeouts
  where project_id = '41000000-0000-0000-0000-000000000005'
  order by revision desc
  limit 1;
  if (
       select (bucket->>'actual_units')::integer
       from jsonb_array_elements(closeout.snapshot->'weekly_output') bucket
       where bucket->>'week_start' = '2025-05-05'
     ) <> 1
     or (
       select (bucket->>'actual_units')::integer
       from jsonb_array_elements(closeout.snapshot->'weekly_output') bucket
       where bucket->>'week_start' = '2026-05-04'
     ) <> 2 then
    raise exception 'weekly correction matched a repeated display label: %',
      closeout.snapshot->'weekly_output';
  end if;
end
$$;
rollback;
"""

output.write_text(
    scaffold
    + migration[tables_start:tables_end]
    + "\n"
    + dependent_tables
    + migration[schedule_start:schedule_end]
    + "\n"
    + migration[close_start:close_end]
    + "\n"
    + append_only_triggers
    + "\n"
    + fixture,
    encoding="utf-8",
)
PY

psql "${DATABASE_URL}" -X -v ON_ERROR_STOP=1 -f "${SQL_FILE}"
printf 'OWNER_HISTORY_SQL_PASS\n'
