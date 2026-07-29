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

table_start = migration.index("create table public.owner_workers")
table_end = migration.index(
    "create table public.owner_project_station_assignments",
    table_start,
)
function_start = migration.index(
    "create or replace function public.owner_upsert_worker"
)
function_end = migration.index(
    "create or replace function public.owner_record_downtime",
    function_start,
)

scaffold = r"""
\set ON_ERROR_STOP on
begin;
create schema auth;
create table public.factories (id uuid primary key);
create table public.profiles (id uuid primary key);
create table public.owner_project_audit (
  factory_id uuid,
  actor_user_id uuid,
  actor_type text,
  action text,
  target_type text,
  target_id uuid,
  metadata jsonb
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
insert into public.factories values
  ('11000000-0000-0000-0000-000000000001');
insert into public.profiles values
  ('61000000-0000-0000-0000-000000000001');
"""

assertions = r"""
do $$
declare
  created public.owner_workers%rowtype;
  updated public.owner_workers%rowtype;
begin
  select * into created
  from public.owner_upsert_worker(
    '11000000-0000-0000-0000-000000000001',
    null,
    'Fixture Worker',
    'FV-001',
    'active',
    true,
    'Operator',
    true
  );
  if created.primary_role is distinct from 'Operator'
     or created.employee_code is distinct from 'FV-001' then
    raise exception 'worker role/code create contract failed';
  end if;

  select * into updated
  from public.owner_upsert_worker(
    '11000000-0000-0000-0000-000000000001',
    created.id,
    'Fixture Worker Updated',
    null,
    'active',
    false,
    null,
    false
  );
  if updated.primary_role is distinct from 'Operator'
     or updated.employee_code is distinct from 'FV-001' then
    raise exception 'omitted worker role/code did not preserve prior values';
  end if;

  perform public.owner_upsert_worker(
    '11000000-0000-0000-0000-000000000001',
    null,
    'Defaulted Worker',
    null,
    'active'
  );
end
$$;
rollback;
"""

output.write_text(
    scaffold
    + migration[table_start:table_end]
    + "\n"
    + migration[function_start:function_end]
    + assertions,
    encoding="utf-8",
)
PY

psql "${DATABASE_URL}" -X -v ON_ERROR_STOP=1 -f "${SQL_FILE}"
printf 'OWNER_WORKER_SQL_PASS\n'
