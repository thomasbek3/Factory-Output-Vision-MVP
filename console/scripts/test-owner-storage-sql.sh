#!/usr/bin/env bash
set -euo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(cd "${CONSOLE_DIR}/.." && pwd)"
ASSIGNMENT_MIGRATION="${ROOT_DIR}/supabase/migrations/20260727025200_worker_media_policy_definer_fix.sql"
OWNER_MIGRATION="${ROOT_DIR}/supabase/migrations/20260729070000_owner_v2_core.sql"
SQL_FILE="$(mktemp)"
trap 'rm -f "${SQL_FILE}"' EXIT

: "${DATABASE_URL:?DATABASE_URL is required}"

python3 - "${ASSIGNMENT_MIGRATION}" "${OWNER_MIGRATION}" "${SQL_FILE}" <<'PY'
from pathlib import Path
import sys

assignment = Path(sys.argv[1]).read_text(encoding="utf-8")
owner = Path(sys.argv[2]).read_text(encoding="utf-8")
output = Path(sys.argv[3])

owner_evidence_start = owner.index(
    "create or replace function public.can_read_owner_evidence"
)
owner_evidence_end = owner.index(
    "create or replace function public.owner_close_project",
    owner_evidence_start,
)
owner_role_start = owner.index(
    "create or replace function public.owner_has_active_role"
)
owner_role_end = owner.index(
    "create or replace function public.owner_authorize_session",
    owner_role_start,
)
policy_start = owner.index(
    "drop policy if exists factory_vision_media_server_only"
)
policy_end = owner.index("\ndo $$", policy_start)

scaffold = r"""
\set ON_ERROR_STOP on
begin;
create role authenticated;
create role anon;
create schema auth;
create schema private;
create schema storage;

create function auth.uid() returns uuid language sql stable as $$
  select (
    nullif(current_setting('request.jwt.claims', true), '')::jsonb
      ->> 'sub'
  )::uuid
$$;
create function auth.jwt() returns jsonb language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb,
    '{}'::jsonb
  )
$$;

create table public.factories (
  id uuid primary key,
  status text not null default 'active'
);
create table public.profiles (
  id uuid primary key,
  status text not null default 'active'
);
create table public.factory_memberships (
  factory_id uuid not null,
  user_id uuid not null,
  role text not null,
  status text not null default 'active'
);
create table public.media_objects (
  id uuid primary key,
  factory_id uuid not null,
  bucket_id text not null,
  object_path text not null,
  status text not null
);
create table public.media_renditions (
  id uuid primary key,
  factory_id uuid not null,
  source_media_object_id uuid not null,
  rendition_media_object_id uuid not null,
  mapping_status text not null
);
create table public.review_assignments (
  id uuid primary key,
  factory_id uuid not null,
  rendition_id uuid not null,
  reviewer_id uuid not null,
  status text not null,
  lease_expires_at timestamptz
);
create table public.video_chunks (
  id uuid primary key,
  factory_id uuid not null,
  source_media_object_id uuid not null,
  review_rendition_id uuid not null,
  source_sha256 text not null,
  source_set_role text not null,
  assignment_eligible boolean not null,
  state text not null
);
create table public.reviewer_lifecycles (
  user_id uuid primary key,
  factory_id uuid not null,
  state text not null,
  practice_completed_at timestamptz,
  mfa_verified_at timestamptz,
  is_test_account boolean not null
);
create table private.reference_answers (
  factory_id uuid not null,
  chunk_id uuid not null,
  answer_type text not null,
  source_sha256 text not null
);
create table public.owner_closeout_evidence_attachments (
  factory_id uuid not null,
  media_object_id uuid not null,
  retention_until timestamptz
);
create table storage.objects (
  bucket_id text not null,
  name text not null
);

__OWNER_ROLE_FUNCTION__

grant usage on schema storage to authenticated;
grant select, insert, update, delete on storage.objects to authenticated;

insert into public.factories (id) values
  ('10000000-0000-0000-0000-000000000001');
insert into public.profiles (id) values
  ('60000000-0000-0000-0000-000000000001'),
  ('60000000-0000-0000-0000-000000000002'),
  ('60000000-0000-0000-0000-000000000003'),
  ('60000000-0000-0000-0000-000000000004'),
  ('60000000-0000-0000-0000-000000000005');
insert into public.factory_memberships (factory_id, user_id, role) values
  ('10000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 'reviewer'),
  ('10000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 'reviewer'),
  ('10000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000003', 'owner'),
  ('10000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000005', 'reviewer');
insert into public.media_objects values
  ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'review-renditions', 'fixture/review.mp4', 'verified'),
  ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'evidence-clips', 'fixture/evidence.mp4', 'verified'),
  ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', 'factory-originals', 'fixture/original.mp4', 'verified'),
  ('30000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000001', 'review-renditions', 'fixture/qualification.mp4', 'verified'),
  ('30000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', 'factory-originals', 'fixture/qualification-original.mp4', 'verified');
insert into public.media_renditions values
  ('40000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000001', 'verified'),
  ('40000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000005', '30000000-0000-0000-0000-000000000004', 'verified');
insert into public.review_assignments values
  ('70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 'leased', now() + interval '1 hour');
insert into public.video_chunks values
  ('50000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000001', repeat('a', 64), 'production', true, 'ready'),
  ('50000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000005', '40000000-0000-0000-0000-000000000002', repeat('b', 64), 'qualification', false, 'ready');
insert into public.reviewer_lifecycles values
  ('60000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'qualification', now(), now(), true),
  ('60000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000001', 'qualification', now(), now(), false);
insert into private.reference_answers values
  ('10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000002', 'qualification', repeat('b', 64));
insert into public.owner_closeout_evidence_attachments values
  ('10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002', now() + interval '1 day');
insert into storage.objects values
  ('review-renditions', 'fixture/review.mp4'),
  ('review-renditions', 'fixture/qualification.mp4'),
  ('evidence-clips', 'fixture/evidence.mp4'),
  ('factory-originals', 'fixture/original.mp4');

alter table storage.objects enable row level security;
"""
scaffold = scaffold.replace(
    "__OWNER_ROLE_FUNCTION__",
    owner[owner_role_start:owner_role_end],
)

proof = r"""
select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);
set local role authenticated;
do $$
begin
  if (select count(*) from storage.objects) <> 1
     or not exists (
       select 1 from storage.objects
       where bucket_id = 'review-renditions'
         and name = 'fixture/review.mp4'
     ) then
    raise exception 'assignment reviewer storage matrix failed';
  end if;
end;
$$;
reset role;

insert into public.video_chunks values
  ('50000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000005', '40000000-0000-0000-0000-000000000002', repeat('b', 64), 'production', true, 'ready');
select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000002","role":"authenticated","aal":"aal1"}',
  true
);
set local role authenticated;
do $$
begin
  if (select count(*) from storage.objects) <> 0 then
    raise exception 'mixed production and qualification lineage crossed storage matrix';
  end if;
end;
$$;
reset role;
delete from public.video_chunks
where id = '50000000-0000-0000-0000-000000000003';

select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000002","role":"authenticated","aal":"aal1"}',
  true
);
set local role authenticated;
do $$
begin
  if (select count(*) from storage.objects) <> 1
     or not exists (
       select 1 from storage.objects
       where bucket_id = 'review-renditions'
         and name = 'fixture/qualification.mp4'
     ) then
    raise exception 'qualification reviewer storage matrix failed';
  end if;
end;
$$;
reset role;

select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000005","role":"authenticated","aal":"aal1"}',
  true
);
set local role authenticated;
do $$
begin
  if (select count(*) from storage.objects) <> 0 then
    raise exception 'non-test aal1 qualification reviewer crossed storage matrix';
  end if;
end;
$$;
reset role;

select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000005","role":"authenticated","aal":"aal2"}',
  true
);
set local role authenticated;
do $$
begin
  if (select count(*) from storage.objects) <> 1
     or not exists (
       select 1 from storage.objects
       where bucket_id = 'review-renditions'
         and name = 'fixture/qualification.mp4'
     ) then
    raise exception 'non-test aal2 qualification reviewer storage matrix failed';
  end if;
end;
$$;
reset role;

select set_config(
  'request.jwt.claims',
  '{"sub":"60000000-0000-0000-0000-000000000003","role":"authenticated"}',
  true
);
set local role authenticated;
do $$
begin
  if (select count(*) from storage.objects) <> 1
     or not exists (
       select 1 from storage.objects
       where bucket_id = 'evidence-clips'
     ) then
    raise exception 'owner storage matrix failed';
  end if;
  begin
    insert into storage.objects values (
      'evidence-clips',
      'fixture/forbidden-write.mp4'
    );
    raise exception 'authenticated protected-media write succeeded';
  exception when insufficient_privilege then
    null;
  end;
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
  if (select count(*) from storage.objects) <> 0 then
    raise exception 'unentitled user crossed storage matrix';
  end if;
end;
$$;
reset role;
rollback;
"""

output.write_text(
    scaffold
    + "\n"
    + assignment
    + "\n"
    + owner[owner_evidence_start:owner_evidence_end]
    + "\n"
    + owner[policy_start:policy_end]
    + "\n"
    + proof,
    encoding="utf-8",
)
PY

psql "${DATABASE_URL}" -X -v ON_ERROR_STOP=1 -f "${SQL_FILE}"
printf 'OWNER_STORAGE_SQL_PASS\n'
