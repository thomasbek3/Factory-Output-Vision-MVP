-- FactoryVision worker portal Phase 1 durable domain.
-- Human truth is three blind reviews with a 2-of-3 majority. AI is isolated.

create schema if not exists private;
create extension if not exists btree_gist with schema extensions;

revoke all on schema private from public, anon, authenticated;
grant usage on schema private to service_role;

create table public.factories (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  timezone text not null,
  retention_days integer not null default 30 check (retention_days between 1 and 3650),
  status text not null default 'active' check (status in ('active', 'paused', 'closed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id)
);

create table public.profiles (
  id uuid primary key references auth.users(id) on delete restrict,
  display_name text not null,
  locale text not null default 'es-419' check (locale in ('es-419', 'en')),
  status text not null default 'active' check (status in ('invited', 'active', 'disabled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.factory_memberships (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  user_id uuid not null references public.profiles(id) on delete restrict,
  role text not null check (role in ('reviewer', 'owner', 'ops', 'ai_analyst')),
  status text not null default 'active' check (status in ('active', 'disabled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (factory_id, user_id),
  unique (id, factory_id)
);

create table public.stations (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  alias text not null,
  status text not null default 'active' check (status in ('active', 'paused', 'retired')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (factory_id, alias),
  unique (id, factory_id)
);

create table public.media_objects (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  station_id uuid not null,
  bucket_id text not null check (bucket_id in ('factory-originals', 'review-renditions', 'evidence-clips')),
  object_path text not null,
  object_sha256 text not null check (object_sha256 ~ '^[0-9a-f]{64}$'),
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  content_type text not null,
  byte_size bigint not null check (byte_size >= 0),
  duration_ms bigint check (duration_ms is null or duration_ms > 0),
  lineage jsonb not null default '[]'::jsonb check (jsonb_typeof(lineage) = 'array'),
  status text not null default 'pending' check (status in ('pending', 'verified', 'quarantined', 'deleted')),
  retention_until timestamptz,
  created_at timestamptz not null default now(),
  verified_at timestamptz,
  deleted_at timestamptz,
  foreign key (station_id, factory_id) references public.stations(id, factory_id) on delete restrict,
  unique (bucket_id, object_path),
  unique (id, factory_id)
);

create table public.media_renditions (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  source_media_object_id uuid not null,
  rendition_media_object_id uuid not null,
  version integer not null check (version > 0),
  source_start_ms bigint not null check (source_start_ms >= 0),
  source_end_ms bigint not null check (source_end_ms > source_start_ms),
  padded_start_ms bigint not null check (padded_start_ms >= 0),
  padded_end_ms bigint not null check (padded_end_ms > padded_start_ms),
  frame_rate_mode text not null check (frame_rate_mode in ('constant', 'variable')),
  frame_count bigint not null check (frame_count > 0),
  mapping jsonb not null check (jsonb_typeof(mapping) in ('array', 'object')),
  mapping_status text not null check (mapping_status in ('pending', 'verified', 'failed')),
  created_at timestamptz not null default now(),
  foreign key (source_media_object_id, factory_id) references public.media_objects(id, factory_id) on delete restrict,
  foreign key (rendition_media_object_id, factory_id) references public.media_objects(id, factory_id) on delete restrict,
  unique (source_media_object_id, version),
  unique (id, factory_id),
  unique (id, factory_id, source_media_object_id)
);

create table public.video_chunks (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  station_id uuid not null,
  source_media_object_id uuid not null,
  review_rendition_id uuid not null,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  source_start_at timestamptz not null,
  source_end_at timestamptz not null check (source_end_at > source_start_at),
  source_start_ms bigint not null check (source_start_ms >= 0),
  source_end_ms bigint not null check (source_end_ms > source_start_ms),
  source_set_role text not null default 'production'
    check (source_set_role in ('production', 'practice', 'qualification', 'resolver_calibration', 'exam', 'holdout')),
  assignment_eligible boolean not null default true,
  state text not null default 'ingesting'
    check (state in ('ingesting', 'transcoding', 'ready', 'assigned', 'resolving', 'resolved', 'published', 'quarantined', 'retained', 'deleted')),
  gap_map jsonb not null default '[]'::jsonb check (jsonb_typeof(gap_map) = 'array'),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (station_id, factory_id) references public.stations(id, factory_id) on delete restrict,
  foreign key (source_media_object_id, factory_id) references public.media_objects(id, factory_id) on delete restrict,
  foreign key (review_rendition_id, factory_id, source_media_object_id)
    references public.media_renditions(id, factory_id, source_media_object_id) on delete restrict,
  check (
    source_set_role = 'production'
    or assignment_eligible = false
  ),
  unique (factory_id, station_id, source_start_at, source_end_at, source_sha256),
  unique (id, factory_id),
  unique (id, factory_id, review_rendition_id),
  exclude using gist (
    factory_id with =,
    station_id with =,
    tstzrange(source_start_at, source_end_at, '[)') with &&
  )
);

create table public.review_assignments (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  chunk_id uuid not null,
  rendition_id uuid not null,
  reviewer_id uuid not null references public.profiles(id) on delete restrict,
  review_round integer not null default 1 check (review_round > 0),
  status text not null default 'queued'
    check (status in ('queued', 'leased', 'draft', 'submitted', 'expired', 'reassigned', 'problem')),
  lease_token_hash text,
  lease_expires_at timestamptz,
  app_version text,
  assigned_at timestamptz not null default now(),
  submitted_at timestamptz,
  updated_at timestamptz not null default now(),
  foreign key (chunk_id, factory_id) references public.video_chunks(id, factory_id) on delete restrict,
  foreign key (rendition_id, factory_id) references public.media_renditions(id, factory_id) on delete restrict,
  foreign key (chunk_id, factory_id, rendition_id)
    references public.video_chunks(id, factory_id, review_rendition_id) on delete restrict,
  check (status not in ('leased', 'draft') or lease_expires_at is not null),
  unique (chunk_id, reviewer_id, review_round),
  unique (id, factory_id),
  unique (id, factory_id, chunk_id, review_round, reviewer_id, rendition_id)
);

create table public.review_actions (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  assignment_id uuid not null,
  reviewer_id uuid not null references public.profiles(id) on delete restrict,
  client_action_id uuid not null,
  action_type text not null check (action_type in ('tally', 'undo', 'problem')),
  source_time_ms bigint check (source_time_ms is null or source_time_ms >= 0),
  undoes_action_id uuid,
  reason_code text,
  playback_rate numeric(5,2) check (playback_rate is null or playback_rate > 0),
  app_version text not null,
  created_at timestamptz not null default now(),
  foreign key (assignment_id, factory_id) references public.review_assignments(id, factory_id) on delete restrict,
  foreign key (undoes_action_id, assignment_id)
    references public.review_actions(id, assignment_id) on delete restrict,
  check (
    (action_type = 'tally' and source_time_ms is not null and undoes_action_id is null)
    or (action_type = 'undo' and undoes_action_id is not null)
    or (action_type = 'problem' and reason_code is not null)
  ),
  unique (assignment_id, client_action_id),
  unique (id, factory_id),
  unique (id, assignment_id)
);

create table public.review_submissions (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  assignment_id uuid not null,
  chunk_id uuid not null,
  reviewer_id uuid not null references public.profiles(id) on delete restrict,
  review_round integer not null check (review_round > 0),
  result_type text not null check (result_type in ('counted', 'problem')),
  total_count integer check (total_count is null or total_count >= 0),
  problem_code text,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  rendition_id uuid not null,
  app_version text not null,
  idempotency_key uuid not null,
  submitted_at timestamptz not null default now(),
  foreign key (assignment_id, factory_id, chunk_id, review_round, reviewer_id, rendition_id)
    references public.review_assignments(id, factory_id, chunk_id, review_round, reviewer_id, rendition_id) on delete restrict,
  foreign key (chunk_id, factory_id) references public.video_chunks(id, factory_id) on delete restrict,
  foreign key (rendition_id, factory_id) references public.media_renditions(id, factory_id) on delete restrict,
  check (
    (result_type = 'counted' and total_count is not null and problem_code is null)
    or (result_type = 'problem' and total_count is null and problem_code is not null)
  ),
  unique (assignment_id),
  unique (chunk_id, review_round, reviewer_id),
  unique (reviewer_id, idempotency_key),
  unique (id, factory_id),
  unique (id, assignment_id),
  unique (id, chunk_id, review_round)
);

create table public.consensus_runs (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  chunk_id uuid not null,
  review_round integer not null check (review_round > 0),
  resolver_version text not null,
  resolver_parameters jsonb not null default '{}'::jsonb check (jsonb_typeof(resolver_parameters) = 'object'),
  status text not null check (status in ('resolved', 'no_majority', 'problem', 'pending_seam')),
  resolved_total integer check (resolved_total is null or resolved_total >= 0),
  support_count smallint,
  created_at timestamptz not null default now(),
  foreign key (chunk_id, factory_id) references public.video_chunks(id, factory_id) on delete restrict,
  check (
    (status = 'resolved' and resolved_total is not null and support_count is not null and support_count in (2, 3))
    or (status <> 'resolved' and resolved_total is null and support_count is null)
  ),
  unique (chunk_id, review_round, resolver_version),
  unique (id, factory_id),
  unique (id, factory_id, chunk_id, review_round)
);

create table public.consensus_events (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  consensus_run_id uuid not null,
  chunk_id uuid not null,
  review_round integer not null check (review_round > 0),
  source_time_ms bigint not null check (source_time_ms >= 0),
  support_count smallint not null check (support_count in (2, 3)),
  provenance text not null default 'majority' check (provenance in ('majority', 'unanimous', 'seam_majority')),
  created_at timestamptz not null default now(),
  foreign key (consensus_run_id, factory_id, chunk_id, review_round)
    references public.consensus_runs(id, factory_id, chunk_id, review_round) on delete restrict,
  foreign key (chunk_id, factory_id) references public.video_chunks(id, factory_id) on delete restrict,
  unique (id, factory_id),
  unique (id, factory_id, chunk_id)
);

create table public.consensus_event_sources (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  consensus_event_id uuid not null,
  submission_id uuid not null,
  review_action_id uuid not null,
  assignment_id uuid not null,
  chunk_id uuid not null,
  review_round integer not null check (review_round > 0),
  created_at timestamptz not null default now(),
  foreign key (consensus_event_id, factory_id) references public.consensus_events(id, factory_id) on delete restrict,
  foreign key (submission_id, chunk_id, review_round)
    references public.review_submissions(id, chunk_id, review_round) on delete restrict,
  foreign key (submission_id, factory_id)
    references public.review_submissions(id, factory_id) on delete restrict,
  foreign key (submission_id, assignment_id)
    references public.review_submissions(id, assignment_id) on delete restrict,
  foreign key (review_action_id, factory_id) references public.review_actions(id, factory_id) on delete restrict,
  foreign key (review_action_id, assignment_id)
    references public.review_actions(id, assignment_id) on delete restrict,
  unique (consensus_event_id, submission_id),
  unique (id, factory_id)
);

create table public.human_finalizations (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  chunk_id uuid not null,
  review_round integer not null check (review_round > 0),
  consensus_run_id uuid not null,
  audit_selected boolean not null default false,
  audit_completed_at timestamptz,
  human_final_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  foreign key (consensus_run_id, factory_id, chunk_id, review_round)
    references public.consensus_runs(id, factory_id, chunk_id, review_round) on delete restrict,
  check (audit_selected = false or audit_completed_at is not null),
  unique (chunk_id),
  unique (consensus_run_id),
  unique (id, factory_id),
  unique (id, factory_id, chunk_id)
);

create table public.resolved_human_count_events (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  chunk_id uuid not null,
  finalization_id uuid not null,
  consensus_event_id uuid not null,
  source_time_ms bigint not null check (source_time_ms >= 0),
  publication_status text not null default 'pending'
    check (publication_status in ('pending', 'published', 'retracted')),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  foreign key (chunk_id, factory_id) references public.video_chunks(id, factory_id) on delete restrict,
  foreign key (finalization_id, factory_id, chunk_id)
    references public.human_finalizations(id, factory_id, chunk_id) on delete restrict,
  foreign key (consensus_event_id, factory_id, chunk_id)
    references public.consensus_events(id, factory_id, chunk_id) on delete restrict,
  check (
    (publication_status = 'published' and published_at is not null)
    or (publication_status <> 'published' and published_at is null)
  ),
  unique (finalization_id, consensus_event_id),
  unique (id, factory_id)
);

create table public.internal_review_cases (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  chunk_id uuid not null,
  review_round integer not null check (review_round > 0),
  sequence integer not null check (sequence > 0),
  event_type text not null
    check (event_type in ('opened', 'request_new_round', 'mark_unusable', 'resolved_by_new_round')),
  reason_code text not null,
  actor_user_id uuid references public.profiles(id) on delete restrict,
  replacement_round integer check (replacement_round is null or replacement_round > review_round),
  created_at timestamptz not null default now(),
  foreign key (chunk_id, factory_id) references public.video_chunks(id, factory_id) on delete restrict,
  check (
    (event_type = 'request_new_round' and replacement_round is not null)
    or (event_type <> 'request_new_round' and replacement_round is null)
  ),
  unique (chunk_id, review_round, sequence),
  unique (id, factory_id)
);

create table public.audit_log (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid references public.factories(id) on delete restrict,
  actor_user_id uuid references public.profiles(id) on delete restrict,
  actor_type text not null check (actor_type in ('user', 'service', 'system')),
  action text not null,
  target_type text not null,
  target_id uuid,
  correlation_id uuid not null,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now()
);

create table private.ai_runs (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  chunk_id uuid not null,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  model_artifact_sha256 text not null check (model_artifact_sha256 ~ '^[0-9a-f]{64}$'),
  code_version text not null,
  parameters jsonb not null default '{}'::jsonb check (jsonb_typeof(parameters) = 'object'),
  started_at timestamptz not null,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  foreign key (chunk_id, factory_id) references public.video_chunks(id, factory_id) on delete restrict,
  unique (chunk_id, model_artifact_sha256, code_version)
);

create table private.reference_answers (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  chunk_id uuid not null,
  answer_type text not null check (answer_type in ('practice', 'qualification', 'audit')),
  total_count integer not null check (total_count >= 0),
  event_times_ms jsonb not null check (jsonb_typeof(event_times_ms) = 'array'),
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  created_by uuid references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  foreign key (chunk_id, factory_id) references public.video_chunks(id, factory_id) on delete restrict,
  unique (chunk_id, answer_type)
);

create table private.ai_events (
  id uuid primary key default gen_random_uuid(),
  ai_run_id uuid not null references private.ai_runs(id) on delete restrict,
  source_time_ms bigint not null check (source_time_ms >= 0),
  confidence numeric(6,5) check (confidence is null or confidence between 0 and 1),
  created_at timestamptz not null default now()
);

create table private.human_ai_comparisons (
  id uuid primary key default gen_random_uuid(),
  ai_run_id uuid not null references private.ai_runs(id) on delete restrict,
  consensus_run_id uuid not null references public.consensus_runs(id) on delete restrict,
  finalization_id uuid not null references public.human_finalizations(id) on delete restrict,
  metrics jsonb not null check (jsonb_typeof(metrics) = 'object'),
  created_at timestamptz not null default now(),
  unique (ai_run_id, consensus_run_id, finalization_id)
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.reject_append_only_change()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception '% is append-only', tg_table_name using errcode = '55000';
end;
$$;

create or replace function public.validate_review_assignment()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  eligible boolean;
  current_count integer;
begin
  perform 1
  from public.video_chunks
  where id = new.chunk_id and factory_id = new.factory_id
  for update;

  select vc.assignment_eligible
  into eligible
  from public.video_chunks vc
  where vc.id = new.chunk_id and vc.factory_id = new.factory_id;

  if eligible is distinct from true then
    raise exception 'chunk is not eligible for production assignment' using errcode = '23514';
  end if;

  if not exists (
    select 1
    from public.factory_memberships fm
    join public.profiles p on p.id = fm.user_id
    where fm.factory_id = new.factory_id
      and fm.user_id = new.reviewer_id
      and fm.role = 'reviewer'
      and fm.status = 'active'
      and p.status = 'active'
  ) then
    raise exception 'reviewer lacks active factory membership' using errcode = '23514';
  end if;

  if new.status not in ('expired', 'reassigned') then
    select count(*)
    into current_count
    from public.review_assignments ra
    where ra.chunk_id = new.chunk_id
      and ra.review_round = new.review_round
      and ra.status not in ('expired', 'reassigned')
      and ra.id <> new.id;

    if current_count >= 3 then
      raise exception 'review round already has three active assignments' using errcode = '23514';
    end if;
  end if;

  return new;
end;
$$;

create or replace function public.guard_assignment_transition()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.status in ('submitted', 'problem')
     and new.status is distinct from old.status then
    raise exception 'submitted and problem assignments are terminal' using errcode = '55000';
  end if;

  if old.status = 'queued' and new.status not in ('queued', 'leased', 'expired', 'reassigned') then
    raise exception 'invalid assignment transition' using errcode = '23514';
  elsif old.status = 'leased' and new.status not in ('leased', 'draft', 'submitted', 'problem', 'expired', 'reassigned') then
    raise exception 'invalid assignment transition' using errcode = '23514';
  elsif old.status = 'draft' and new.status not in ('draft', 'submitted', 'problem', 'expired', 'reassigned') then
    raise exception 'invalid assignment transition' using errcode = '23514';
  elsif old.status in ('expired', 'reassigned') and new.status is distinct from old.status then
    raise exception 'expired and reassigned assignments are terminal' using errcode = '55000';
  end if;

  return new;
end;
$$;

create or replace function public.protect_chunk_source_identity()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.source_set_role is distinct from old.source_set_role
     or new.source_sha256 is distinct from old.source_sha256
     or new.source_start_at is distinct from old.source_start_at
     or new.source_end_at is distinct from old.source_end_at
     or new.source_start_ms is distinct from old.source_start_ms
     or new.source_end_ms is distinct from old.source_end_ms then
    raise exception 'chunk source identity is immutable' using errcode = '55000';
  end if;

  if old.assignment_eligible = false and new.assignment_eligible = true
     and exists (
       select 1 from public.review_assignments ra where ra.chunk_id = old.id
     ) then
    raise exception 'assignment eligibility cannot be restored after assignment' using errcode = '55000';
  end if;

  return new;
end;
$$;

create or replace function public.validate_review_action()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  assignment_row public.review_assignments%rowtype;
  chunk_row public.video_chunks%rowtype;
begin
  select *
  into assignment_row
  from public.review_assignments
  where id = new.assignment_id
  for update;

  if not found
     or assignment_row.factory_id <> new.factory_id
     or assignment_row.reviewer_id <> new.reviewer_id
     or assignment_row.status not in ('leased', 'draft')
     or assignment_row.lease_expires_at is null
     or assignment_row.lease_expires_at <= now() then
    raise exception 'assignment is not writable' using errcode = '23514';
  end if;

  if not exists (
    select 1
    from public.factory_memberships fm
    join public.profiles p on p.id = fm.user_id
    where fm.factory_id = new.factory_id
      and fm.user_id = new.reviewer_id
      and fm.role = 'reviewer'
      and fm.status = 'active'
      and p.status = 'active'
  ) then
    raise exception 'reviewer is not active' using errcode = '23514';
  end if;

  if exists (
    select 1 from public.review_submissions rs where rs.assignment_id = new.assignment_id
  ) then
    raise exception 'assignment was already submitted' using errcode = '55000';
  end if;

  select *
  into chunk_row
  from public.video_chunks
  where id = assignment_row.chunk_id;

  if new.action_type = 'tally'
     and (new.source_time_ms < chunk_row.source_start_ms
          or new.source_time_ms >= chunk_row.source_end_ms) then
    raise exception 'tally is outside the canonical chunk interval' using errcode = '23514';
  end if;

  if new.action_type = 'undo' and not exists (
    select 1
    from public.review_actions target
    where target.id = new.undoes_action_id
      and target.assignment_id = new.assignment_id
      and target.action_type = 'tally'
  ) then
    raise exception 'undo must target a tally in the same assignment' using errcode = '23514';
  end if;

  new.created_at = now();
  return new;
end;
$$;

create or replace function public.validate_review_submission()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  assignment_row public.review_assignments%rowtype;
  expected_total integer;
begin
  perform 1
  from public.video_chunks
  where id = new.chunk_id and factory_id = new.factory_id
  for update;

  select *
  into assignment_row
  from public.review_assignments
  where id = new.assignment_id
  for update;

  if not found
     or assignment_row.factory_id <> new.factory_id
     or assignment_row.chunk_id <> new.chunk_id
     or assignment_row.review_round <> new.review_round
     or assignment_row.reviewer_id <> new.reviewer_id
     or assignment_row.rendition_id <> new.rendition_id
     or assignment_row.status not in ('leased', 'draft')
     or assignment_row.lease_expires_at is null
     or assignment_row.lease_expires_at <= now() then
    raise exception 'assignment is not submittable' using errcode = '23514';
  end if;

  if not exists (
    select 1
    from public.factory_memberships fm
    join public.profiles p on p.id = fm.user_id
    where fm.factory_id = new.factory_id
      and fm.user_id = new.reviewer_id
      and fm.role = 'reviewer'
      and fm.status = 'active'
      and p.status = 'active'
  ) then
    raise exception 'reviewer is not active' using errcode = '23514';
  end if;

  if new.source_sha256 <> (
    select vc.source_sha256 from public.video_chunks vc where vc.id = new.chunk_id
  ) then
    raise exception 'submission source hash does not match chunk' using errcode = '23514';
  end if;

  if (select count(*) from public.review_submissions rs
      where rs.chunk_id = new.chunk_id and rs.review_round = new.review_round) >= 3 then
    raise exception 'review round already holds three submissions' using errcode = '23514';
  end if;

  if new.result_type = 'counted' then
    select count(*)::integer
    into expected_total
    from public.review_actions tally
    where tally.assignment_id = new.assignment_id
      and tally.action_type = 'tally'
      and not exists (
        select 1
        from public.review_actions undo
        where undo.assignment_id = new.assignment_id
          and undo.action_type = 'undo'
          and undo.undoes_action_id = tally.id
      );

    if new.total_count <> expected_total then
      raise exception 'submission total does not match immutable tally actions' using errcode = '23514';
    end if;
  end if;

  new.submitted_at = now();
  return new;
end;
$$;

create or replace function public.complete_review_assignment()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  update public.review_assignments
  set status = case when new.result_type = 'problem' then 'problem' else 'submitted' end,
      submitted_at = new.submitted_at
  where id = new.assignment_id;
  return new;
end;
$$;

create or replace function public.validate_consensus_run()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  submission_count integer;
  counted_count integer;
  matching_count integer;
  problem_count integer;
begin
  select count(*),
         count(*) filter (where result_type = 'counted'),
         count(*) filter (where result_type = 'counted' and total_count = new.resolved_total),
         count(*) filter (where result_type = 'problem')
  into submission_count, counted_count, matching_count, problem_count
  from public.review_submissions
  where chunk_id = new.chunk_id and review_round = new.review_round;

  if submission_count <> 3 then
    raise exception 'consensus requires exactly three submissions in one round' using errcode = '23514';
  end if;

  if new.status = 'resolved'
     and (counted_count <> 3 or matching_count <> new.support_count) then
    raise exception 'resolved consensus does not match 2-of-3 human submissions' using errcode = '23514';
  elsif new.status = 'no_majority' and exists (
    select 1
    from public.review_submissions
    where chunk_id = new.chunk_id
      and review_round = new.review_round
      and result_type = 'counted'
    group by total_count
    having count(*) >= 2
  ) then
    raise exception 'no-majority run contains a human majority' using errcode = '23514';
  elsif new.status = 'problem' and problem_count = 0 then
    raise exception 'problem run requires a problem submission' using errcode = '23514';
  end if;

  return new;
end;
$$;

create or replace function public.validate_consensus_event()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  event_id uuid;
  source_count integer;
  distinct_submission_count integer;
  invalid_source_count integer;
  event_row public.consensus_events%rowtype;
  run_row public.consensus_runs%rowtype;
begin
  if tg_table_name = 'consensus_events' then
    event_id = new.id;
  else
    event_id = new.consensus_event_id;
  end if;
  select * into event_row from public.consensus_events where id = event_id;
  if not found then
    return new;
  end if;

  select * into run_row from public.consensus_runs where id = event_row.consensus_run_id;

  select count(*),
         count(distinct ces.submission_id),
         count(*) filter (
           where rs.chunk_id <> event_row.chunk_id
              or rs.review_round <> event_row.review_round
              or rs.result_type <> 'counted'
              or rs.total_count <> run_row.resolved_total
              or ra.action_type <> 'tally'
         )
  into source_count, distinct_submission_count, invalid_source_count
  from public.consensus_event_sources ces
  join public.review_submissions rs on rs.id = ces.submission_id
  join public.review_actions ra on ra.id = ces.review_action_id
  where ces.consensus_event_id = event_id;

  if source_count <> event_row.support_count
     or distinct_submission_count <> event_row.support_count
     or invalid_source_count <> 0 then
    raise exception 'consensus event lacks matching human source lineage' using errcode = '23514';
  end if;

  return new;
end;
$$;

create or replace function public.validate_human_finalization()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not exists (
    select 1
    from public.consensus_runs cr
    where cr.id = new.consensus_run_id
      and cr.factory_id = new.factory_id
      and cr.chunk_id = new.chunk_id
      and cr.review_round = new.review_round
      and cr.status = 'resolved'
  ) then
    raise exception 'only resolved human consensus can be finalized' using errcode = '23514';
  end if;

  new.human_final_at = now();
  new.created_at = now();
  return new;
end;
$$;

create trigger factories_set_updated_at
before update on public.factories
for each row execute function public.set_updated_at();
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();
create trigger memberships_set_updated_at
before update on public.factory_memberships
for each row execute function public.set_updated_at();
create trigger stations_set_updated_at
before update on public.stations
for each row execute function public.set_updated_at();
create trigger chunks_set_updated_at
before update on public.video_chunks
for each row execute function public.set_updated_at();
create trigger chunks_protect_source_identity
before update on public.video_chunks
for each row execute function public.protect_chunk_source_identity();
create trigger assignments_set_updated_at
before update on public.review_assignments
for each row execute function public.set_updated_at();
create trigger assignments_guard_transition
before update on public.review_assignments
for each row execute function public.guard_assignment_transition();
create trigger assignments_validate
before insert or update of factory_id, chunk_id, reviewer_id, review_round, status
on public.review_assignments
for each row execute function public.validate_review_assignment();
create trigger review_actions_validate
before insert on public.review_actions
for each row execute function public.validate_review_action();
create trigger review_submissions_validate
before insert on public.review_submissions
for each row execute function public.validate_review_submission();
create trigger review_submissions_complete_assignment
after insert on public.review_submissions
for each row execute function public.complete_review_assignment();
create constraint trigger consensus_runs_validate
after insert on public.consensus_runs
deferrable initially deferred
for each row execute function public.validate_consensus_run();
create constraint trigger consensus_events_validate
after insert on public.consensus_events
deferrable initially deferred
for each row execute function public.validate_consensus_event();
create constraint trigger consensus_event_sources_validate
after insert on public.consensus_event_sources
deferrable initially deferred
for each row execute function public.validate_consensus_event();
create trigger human_finalizations_validate
before insert on public.human_finalizations
for each row execute function public.validate_human_finalization();

create trigger review_actions_append_only
before update or delete on public.review_actions
for each row execute function public.reject_append_only_change();
create trigger review_submissions_append_only
before update or delete on public.review_submissions
for each row execute function public.reject_append_only_change();
create trigger consensus_runs_append_only
before update or delete on public.consensus_runs
for each row execute function public.reject_append_only_change();
create trigger consensus_events_append_only
before update or delete on public.consensus_events
for each row execute function public.reject_append_only_change();
create trigger consensus_event_sources_append_only
before update or delete on public.consensus_event_sources
for each row execute function public.reject_append_only_change();
create trigger human_finalizations_append_only
before update or delete on public.human_finalizations
for each row execute function public.reject_append_only_change();
create trigger resolved_human_count_events_append_only
before update or delete on public.resolved_human_count_events
for each row execute function public.reject_append_only_change();
create trigger internal_review_cases_append_only
before update or delete on public.internal_review_cases
for each row execute function public.reject_append_only_change();
create trigger audit_log_append_only
before update or delete on public.audit_log
for each row execute function public.reject_append_only_change();

revoke all on function public.set_updated_at() from public, anon, authenticated;
revoke all on function public.reject_append_only_change() from public, anon, authenticated;
revoke all on function public.validate_review_assignment() from public, anon, authenticated;
revoke all on function public.guard_assignment_transition() from public, anon, authenticated;
revoke all on function public.protect_chunk_source_identity() from public, anon, authenticated;
revoke all on function public.validate_review_action() from public, anon, authenticated;
revoke all on function public.validate_review_submission() from public, anon, authenticated;
revoke all on function public.complete_review_assignment() from public, anon, authenticated;
revoke all on function public.validate_consensus_run() from public, anon, authenticated;
revoke all on function public.validate_consensus_event() from public, anon, authenticated;
revoke all on function public.validate_human_finalization() from public, anon, authenticated;
grant execute on function public.set_updated_at() to service_role;
grant execute on function public.reject_append_only_change() to service_role;
grant execute on function public.validate_review_assignment() to service_role;
grant execute on function public.guard_assignment_transition() to service_role;
grant execute on function public.protect_chunk_source_identity() to service_role;
grant execute on function public.validate_review_action() to service_role;
grant execute on function public.validate_review_submission() to service_role;
grant execute on function public.complete_review_assignment() to service_role;
grant execute on function public.validate_consensus_run() to service_role;
grant execute on function public.validate_consensus_event() to service_role;
grant execute on function public.validate_human_finalization() to service_role;

create index factory_memberships_user_active_idx
  on public.factory_memberships (user_id, factory_id, role) where status = 'active';
create index media_objects_factory_station_idx on public.media_objects (factory_id, station_id);
create index video_chunks_ready_idx
  on public.video_chunks (factory_id, source_start_at) where state = 'ready' and assignment_eligible;
create index review_assignments_reviewer_queue_idx
  on public.review_assignments (reviewer_id, status, assigned_at);
create index review_assignments_chunk_round_idx
  on public.review_assignments (chunk_id, review_round, status);
create index review_actions_assignment_time_idx
  on public.review_actions (assignment_id, created_at);
create unique index review_actions_one_undo_idx
  on public.review_actions (undoes_action_id) where action_type = 'undo';
create index review_submissions_chunk_round_idx
  on public.review_submissions (chunk_id, review_round);
create index consensus_runs_owner_idx
  on public.consensus_runs (factory_id, created_at) where status = 'resolved';
create unique index consensus_runs_one_resolved_per_chunk_idx
  on public.consensus_runs (chunk_id) where status = 'resolved';
create index internal_review_cases_queue_idx
  on public.internal_review_cases (factory_id, created_at) where event_type = 'opened';
create index audit_log_factory_time_idx on public.audit_log (factory_id, created_at desc);
create index ai_events_run_time_idx on private.ai_events (ai_run_id, source_time_ms);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('factory-originals', 'factory-originals', false, 53687091200, array['video/mp4', 'video/quicktime', 'video/x-matroska']),
  ('review-renditions', 'review-renditions', false, 5368709120, array['video/mp4', 'video/webm']),
  ('evidence-clips', 'evidence-clips', false, 1073741824, array['video/mp4', 'video/webm'])
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create policy factory_vision_media_server_only
on storage.objects
as restrictive
for all
to anon, authenticated
using (bucket_id not in ('factory-originals', 'review-renditions', 'evidence-clips'))
with check (bucket_id not in ('factory-originals', 'review-renditions', 'evidence-clips'));

alter table public.factories enable row level security;
alter table public.profiles enable row level security;
alter table public.factory_memberships enable row level security;
alter table public.stations enable row level security;
alter table public.media_objects enable row level security;
alter table public.media_renditions enable row level security;
alter table public.video_chunks enable row level security;
alter table public.review_assignments enable row level security;
alter table public.review_actions enable row level security;
alter table public.review_submissions enable row level security;
alter table public.consensus_runs enable row level security;
alter table public.consensus_events enable row level security;
alter table public.consensus_event_sources enable row level security;
alter table public.human_finalizations enable row level security;
alter table public.resolved_human_count_events enable row level security;
alter table public.internal_review_cases enable row level security;
alter table public.audit_log enable row level security;
alter table private.ai_runs enable row level security;
alter table private.reference_answers enable row level security;
alter table private.ai_events enable row level security;
alter table private.human_ai_comparisons enable row level security;

alter table public.factories force row level security;
alter table public.profiles force row level security;
alter table public.factory_memberships force row level security;
alter table public.stations force row level security;
alter table public.media_objects force row level security;
alter table public.media_renditions force row level security;
alter table public.video_chunks force row level security;
alter table public.review_assignments force row level security;
alter table public.review_actions force row level security;
alter table public.review_submissions force row level security;
alter table public.consensus_runs force row level security;
alter table public.consensus_events force row level security;
alter table public.consensus_event_sources force row level security;
alter table public.human_finalizations force row level security;
alter table public.resolved_human_count_events force row level security;
alter table public.internal_review_cases force row level security;
alter table public.audit_log force row level security;
alter table private.ai_runs force row level security;
alter table private.reference_answers force row level security;
alter table private.ai_events force row level security;
alter table private.human_ai_comparisons force row level security;

revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all tables in schema private from anon, authenticated;
revoke all on all sequences in schema private from anon, authenticated;

grant select on public.profiles to authenticated;
grant select on public.factory_memberships to authenticated;
grant select on public.factories to authenticated;
grant select on public.stations to authenticated;
grant select on public.review_assignments to authenticated;
grant select on public.review_actions to authenticated;
grant select on public.review_submissions to authenticated;
grant select on public.resolved_human_count_events to authenticated;

grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
grant all on all tables in schema private to service_role;
grant all on all sequences in schema private to service_role;

alter default privileges in schema private revoke all on tables from public, anon, authenticated;
alter default privileges in schema private revoke all on sequences from public, anon, authenticated;
alter default privileges in schema private grant all on tables to service_role;
alter default privileges in schema private grant all on sequences to service_role;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;

create policy profiles_read_self
on public.profiles for select
to authenticated
using (id = (select auth.uid()));

create policy memberships_read_self
on public.factory_memberships for select
to authenticated
using (user_id = (select auth.uid()) and status = 'active');

create policy factories_read_owner_or_ops
on public.factories for select
to authenticated
using (
  exists (
    select 1
    from public.factory_memberships fm
    where fm.factory_id = factories.id
      and fm.user_id = (select auth.uid())
      and fm.status = 'active'
      and fm.role in ('owner', 'ops')
  )
);

create policy stations_read_owner_or_ops
on public.stations for select
to authenticated
using (
  exists (
    select 1
    from public.factory_memberships fm
    where fm.factory_id = stations.factory_id
      and fm.user_id = (select auth.uid())
      and fm.status = 'active'
      and fm.role in ('owner', 'ops')
  )
);

create policy assignments_read_own
on public.review_assignments for select
to authenticated
using (
  reviewer_id = (select auth.uid())
  and exists (
    select 1
    from public.profiles p
    join public.factory_memberships fm on fm.user_id = p.id
    where p.id = (select auth.uid())
      and p.status = 'active'
      and fm.factory_id = review_assignments.factory_id
      and fm.role = 'reviewer'
      and fm.status = 'active'
  )
);

create policy review_actions_read_own
on public.review_actions for select
to authenticated
using (
  reviewer_id = (select auth.uid())
  and exists (
    select 1 from public.profiles p
    join public.factory_memberships fm on fm.user_id = p.id
    where p.id = (select auth.uid())
      and p.status = 'active'
      and fm.factory_id = review_actions.factory_id
      and fm.role = 'reviewer'
      and fm.status = 'active'
  )
);

create policy review_submissions_read_own
on public.review_submissions for select
to authenticated
using (
  reviewer_id = (select auth.uid())
  and exists (
    select 1 from public.profiles p
    join public.factory_memberships fm on fm.user_id = p.id
    where p.id = (select auth.uid())
      and p.status = 'active'
      and fm.factory_id = review_submissions.factory_id
      and fm.role = 'reviewer'
      and fm.status = 'active'
  )
);

create policy resolved_human_events_read_owner
on public.resolved_human_count_events for select
to authenticated
using (
  publication_status = 'published'
  and exists (
    select 1
    from public.factory_memberships fm
    where fm.factory_id = resolved_human_count_events.factory_id
      and fm.user_id = (select auth.uid())
      and fm.status = 'active'
      and fm.role = 'owner'
  )
);

comment on schema private is 'Server-only AI and comparison data. Browser roles have no access.';
comment on table public.internal_review_cases is 'Append-only exception events. No row can create or edit human truth.';
comment on table public.consensus_runs is 'Human-only resolver output. support_count is two or three; AI is never an input.';
