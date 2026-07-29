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
table_start = migration.index(
    "create table public.owner_station_downtime_intervals"
)
table_end = migration.index(
    "create table public.owner_output_adjustments",
    table_start,
)
function_start = migration.index(
    "create or replace function public.owner_record_downtime"
)
function_end = migration.index(
    "create or replace function public.owner_start_project",
    function_start,
)

scaffold = r"""
\set ON_ERROR_STOP on
begin;
create extension if not exists btree_gist;
create schema auth;
create table public.factories (
  id uuid primary key
);
create table public.profiles (
  id uuid primary key
);
create table public.stations (
  id uuid,
  factory_id uuid,
  primary key (id, factory_id)
);
create table public.owner_projects (
  id uuid,
  factory_id uuid,
  start_at timestamptz not null,
  status text not null,
  primary key (id, factory_id)
);
create table public.owner_project_station_assignments (
  factory_id uuid not null,
  project_id uuid not null,
  station_id uuid not null,
  effective_start timestamptz not null,
  effective_end timestamptz
);
create table public.owner_project_audit (
  factory_id uuid,
  project_id uuid,
  actor_user_id uuid,
  actor_type text,
  action text,
  target_type text,
  target_id uuid,
  metadata jsonb
);
create function auth.uid() returns uuid language sql stable as $$
  select '61000000-0000-0000-0000-000000000001'::uuid
$$;
create function public.owner_has_active_role(uuid, text)
returns boolean language sql stable as $$ select true $$;
insert into public.factories values
  ('11000000-0000-0000-0000-000000000001');
insert into public.profiles values
  ('61000000-0000-0000-0000-000000000001');
insert into public.stations values
  ('21000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000001'),
  ('21000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000001');
insert into public.owner_projects values
  ('41000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000001', '2026-07-29T08:00:00Z', 'open');
insert into public.owner_project_station_assignments values
  ('11000000-0000-0000-0000-000000000001', '41000000-0000-0000-0000-000000000001', '21000000-0000-0000-0000-000000000001', '2026-07-29T08:00:00Z', null);
"""

proof = r"""
do $$
begin
  perform public.owner_record_downtime(
    '11000000-0000-0000-0000-000000000001',
    '41000000-0000-0000-0000-000000000001',
    '21000000-0000-0000-0000-000000000001',
    '2026-07-29T09:00:00Z',
    '2026-07-29T09:15:00Z',
    'equipment_breakdown',
    'Press jam'
  );
  if (select count(*) from public.owner_station_downtime_intervals) <> 1
     or (
       select count(*) from public.owner_project_audit
       where action = 'owner.project.downtime_recorded'
     ) <> 1 then
    raise exception 'audited downtime write failed';
  end if;
  begin
    perform public.owner_record_downtime(
      '11000000-0000-0000-0000-000000000001',
      '41000000-0000-0000-0000-000000000001',
      '21000000-0000-0000-0000-000000000001',
      '2026-07-29T09:10:00Z',
      '2026-07-29T09:20:00Z',
      'maintenance',
      null
    );
    raise exception 'overlapping downtime was accepted';
  exception when exclusion_violation then
    null;
  end;
  begin
    perform public.owner_record_downtime(
      '11000000-0000-0000-0000-000000000001',
      '41000000-0000-0000-0000-000000000001',
      '21000000-0000-0000-0000-000000000002',
      '2026-07-29T10:00:00Z',
      '2026-07-29T10:15:00Z',
      'changeover',
      null
    );
    raise exception 'unassigned-station downtime was accepted';
  exception when check_violation then
    null;
  end;
end
$$;
rollback;
"""

output.write_text(
    scaffold
    + migration[table_start:table_end]
    + "\n"
    + migration[function_start:function_end]
    + proof,
    encoding="utf-8",
)
PY

psql "${DATABASE_URL}" -X -v ON_ERROR_STOP=1 -f "${SQL_FILE}"
printf 'OWNER_DOWNTIME_SQL_PASS\n'
