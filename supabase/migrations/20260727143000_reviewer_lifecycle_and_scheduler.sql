-- First-worker lifecycle: invite, onboarding, qualification, work evidence,
-- coverage, assignment maintenance, and count-majority resolution.

create extension if not exists pg_cron;

alter table public.review_assignments
  add column if not exists leased_at timestamptz;

create table public.reviewer_lifecycles (
  user_id uuid primary key references public.profiles(id) on delete restrict,
  factory_id uuid not null references public.factories(id) on delete restrict,
  email text not null,
  state text not null default 'invited'
    check (state in (
      'invited', 'mfa_required', 'terms_required', 'training',
      'qualification', 'active', 'suspended', 'offboarded'
    )),
  country_code text check (country_code is null or country_code ~ '^[A-Z]{2}$'),
  employment_classification text
    check (employment_classification is null or employment_classification in ('employee', 'contractor')),
  pay_basis text check (pay_basis is null or pay_basis in ('hourly', 'per_chunk')),
  terms_version text,
  terms_accepted_at timestamptz,
  mfa_verified_at timestamptz,
  walkthrough_completed_at timestamptz,
  practice_completed_at timestamptz,
  qualified_at timestamptz,
  activated_at timestamptz,
  suspended_at timestamptz,
  offboarded_at timestamptz,
  state_reason text,
  is_test_account boolean not null default false,
  invited_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (factory_id, user_id)
);

create table public.reviewer_invitations (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  user_id uuid not null references public.profiles(id) on delete restrict,
  email text not null,
  locale text not null check (locale in ('es-419', 'en')),
  status text not null default 'created'
    check (status in ('created', 'sent', 'accepted', 'expired', 'revoked', 'delivery_failed')),
  delivery_provider text,
  delivery_id text,
  expires_at timestamptz not null,
  invited_by uuid not null references public.profiles(id) on delete restrict,
  sent_at timestamptz,
  accepted_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, created_at)
);

create table public.reviewer_device_registrations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete restrict,
  device_id_hash text not null check (device_id_hash ~ '^[0-9a-f]{64}$'),
  status text not null default 'active' check (status in ('active', 'revoked')),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  revoked_at timestamptz,
  unique (user_id, device_id_hash)
);

create unique index reviewer_one_active_account_per_device_idx
  on public.reviewer_device_registrations (device_id_hash)
  where status = 'active';

create table public.reviewer_training_events (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  user_id uuid not null references public.profiles(id) on delete restrict,
  event_type text not null
    check (event_type in (
      'terms_accepted', 'mfa_verified', 'walkthrough_completed',
      'practice_completed', 'qualification_passed', 'qualification_failed',
      'activated', 'suspended', 'offboarded'
    )),
  training_version text,
  actor_user_id uuid references public.profiles(id) on delete restrict,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now()
);

create table public.reviewer_work_sessions (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  reviewer_id uuid not null references public.profiles(id) on delete restrict,
  device_id_hash text not null check (device_id_hash ~ '^[0-9a-f]{64}$'),
  started_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  ended_at timestamptz,
  active_seconds integer not null default 0 check (active_seconds >= 0),
  submitted_chunks integer not null default 0 check (submitted_chunks >= 0),
  close_reason text,
  created_at timestamptz not null default now()
);

create index reviewer_work_sessions_open_idx
  on public.reviewer_work_sessions (reviewer_id, started_at desc)
  where ended_at is null;

create table public.review_coverage (
  assignment_id uuid primary key references public.review_assignments(id) on delete restrict,
  factory_id uuid not null references public.factories(id) on delete restrict,
  reviewer_id uuid not null references public.profiles(id) on delete restrict,
  page_epoch uuid not null,
  ranges jsonb not null default '[]'::jsonb check (jsonb_typeof(ranges) = 'array'),
  client_active_ms bigint not null default 0 check (client_active_ms >= 0),
  started_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (assignment_id, factory_id)
    references public.review_assignments(id, factory_id) on delete restrict
);

create table public.reviewer_support_requests (
  id uuid primary key default gen_random_uuid(),
  factory_id uuid not null references public.factories(id) on delete restrict,
  reviewer_id uuid not null references public.profiles(id) on delete restrict,
  assignment_id uuid references public.review_assignments(id) on delete restrict,
  reason_code text not null check (reason_code in (
    'account', 'mfa', 'video', 'assignment', 'payment', 'privacy', 'other'
  )),
  message text not null check (length(message) between 1 and 2000),
  status text not null default 'open' check (status in ('open', 'acknowledged', 'closed')),
  created_at timestamptz not null default now(),
  closed_at timestamptz
);

create or replace function public.actor_is_ops(p_factory_id uuid default null)
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
    where membership.user_id = (select auth.uid())
      and membership.role = 'ops'
      and membership.status = 'active'
      and profile.status = 'active'
      and (p_factory_id is null or membership.factory_id = p_factory_id)
  );
$$;

create or replace function public.ops_reviewer_roster()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  result jsonb;
begin
  if not public.actor_is_ops(null) then
    raise exception 'ops access required' using errcode = '42501';
  end if;

  select jsonb_build_object(
    'factories', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', factory.id,
        'name', factory.name,
        'timezone', factory.timezone
      ) order by factory.name)
      from public.factories factory
      where factory.status = 'active'
        and public.actor_is_ops(factory.id)
    ), '[]'::jsonb),
    'reviewers', coalesce((
      select jsonb_agg(jsonb_build_object(
        'userId', lifecycle.user_id,
        'displayName', profile.display_name,
        'email', lifecycle.email,
        'locale', profile.locale,
        'factoryId', lifecycle.factory_id,
        'factoryName', factory.name,
        'state', lifecycle.state,
        'countryCode', lifecycle.country_code,
        'employmentClassification', lifecycle.employment_classification,
        'payBasis', lifecycle.pay_basis,
        'mfaVerifiedAt', lifecycle.mfa_verified_at,
        'qualifiedAt', lifecycle.qualified_at,
        'activatedAt', lifecycle.activated_at,
        'stateReason', lifecycle.state_reason,
        'queuedAssignments', (
          select count(*) from public.review_assignments assignment
          where assignment.reviewer_id = lifecycle.user_id
            and assignment.status in ('queued', 'leased', 'draft')
        ),
        'submittedAssignments', (
          select count(*) from public.review_assignments assignment
          where assignment.reviewer_id = lifecycle.user_id
            and assignment.status in ('submitted', 'problem')
        ),
        'lastSeenAt', (
          select max(session.last_seen_at) from public.reviewer_work_sessions session
          where session.reviewer_id = lifecycle.user_id
        )
      ) order by
        case lifecycle.state
          when 'active' then 0 when 'qualification' then 1 when 'training' then 2
          when 'suspended' then 3 when 'offboarded' then 4 else 2
        end,
        profile.display_name)
      from public.reviewer_lifecycles lifecycle
      join public.profiles profile on profile.id = lifecycle.user_id
      join public.factories factory on factory.id = lifecycle.factory_id
      where public.actor_is_ops(lifecycle.factory_id)
    ), '[]'::jsonb)
  ) into result;

  return result;
end;
$$;

create or replace function public.service_register_reviewer_invitation(
  p_user_id uuid,
  p_factory_id uuid,
  p_email text,
  p_display_name text,
  p_locale text,
  p_country_code text,
  p_employment_classification text,
  p_pay_basis text,
  p_expires_at timestamptz,
  p_delivery_provider text,
  p_delivery_id text
)
returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  invitation_id uuid;
  actor_id uuid := auth.uid();
begin
  if actor_id is null or not public.actor_is_ops(p_factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  if p_locale not in ('es-419', 'en') then
    raise exception 'unsupported locale' using errcode = '22023';
  end if;

  insert into public.profiles (id, display_name, locale, status)
  values (p_user_id, trim(p_display_name), p_locale, 'invited')
  on conflict (id) do update
    set display_name = excluded.display_name,
        locale = excluded.locale,
        updated_at = now();

  insert into public.factory_memberships (factory_id, user_id, role, status)
  values (p_factory_id, p_user_id, 'reviewer', 'disabled')
  on conflict (factory_id, user_id) do update
    set role = 'reviewer', status = 'disabled', updated_at = now();

  insert into public.reviewer_lifecycles (
    user_id, factory_id, email, state, country_code,
    employment_classification, pay_basis
  ) values (
    p_user_id, p_factory_id, lower(trim(p_email)), 'invited',
    nullif(upper(trim(p_country_code)), ''),
    nullif(p_employment_classification, ''),
    nullif(p_pay_basis, '')
  )
  on conflict (user_id) do update
    set email = excluded.email,
        state = 'invited',
        country_code = excluded.country_code,
        employment_classification = excluded.employment_classification,
        pay_basis = excluded.pay_basis,
        state_reason = null,
        invited_at = now(),
        updated_at = now();

  insert into public.reviewer_invitations (
    factory_id, user_id, email, locale, status, delivery_provider,
    delivery_id, expires_at, invited_by, sent_at
  ) values (
    p_factory_id, p_user_id, lower(trim(p_email)), p_locale, 'sent',
    p_delivery_provider, p_delivery_id, p_expires_at, actor_id, now()
  ) returning id into invitation_id;

  return invitation_id;
end;
$$;

create or replace function public.worker_lifecycle_state()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  result jsonb;
begin
  if actor_id is null then
    raise exception 'authentication required' using errcode = '28000';
  end if;

  select jsonb_build_object(
    'userId', lifecycle.user_id,
    'displayName', profile.display_name,
    'email', lifecycle.email,
    'locale', profile.locale,
    'state', lifecycle.state,
    'termsVersion', lifecycle.terms_version,
    'termsAcceptedAt', lifecycle.terms_accepted_at,
    'mfaVerifiedAt', lifecycle.mfa_verified_at,
    'currentAal', coalesce(auth.jwt() ->> 'aal', 'aal1'),
    'walkthroughCompletedAt', lifecycle.walkthrough_completed_at,
    'practiceCompletedAt', lifecycle.practice_completed_at,
    'qualifiedAt', lifecycle.qualified_at,
    'activatedAt', lifecycle.activated_at,
    'isTestAccount', lifecycle.is_test_account,
    'supportConfigured', current_setting('app.settings.reviewer_support_configured', true) = 'true'
  )
  into result
  from public.reviewer_lifecycles lifecycle
  join public.profiles profile on profile.id = lifecycle.user_id
  where lifecycle.user_id = actor_id;

  return coalesce(result, jsonb_build_object('state', 'unregistered'));
end;
$$;

create or replace function public.worker_record_onboarding_step(
  p_step text,
  p_terms_version text default null,
  p_device_id_hash text default null,
  p_training_version text default 'worker-v1'
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  event_name text;
begin
  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = actor_id
  for update;
  if lifecycle_row.user_id is null or lifecycle_row.state in ('suspended', 'offboarded') then
    raise exception 'reviewer onboarding is unavailable' using errcode = '42501';
  end if;

  if p_device_id_hash is not null then
    if p_device_id_hash !~ '^[0-9a-f]{64}$' then
      raise exception 'invalid device identifier' using errcode = '22023';
    end if;
    insert into public.reviewer_device_registrations (user_id, device_id_hash)
    values (actor_id, p_device_id_hash)
    on conflict (user_id, device_id_hash) do update
      set status = 'active', last_seen_at = now(), revoked_at = null;
  end if;

  if p_step = 'mfa_verified' then
    if coalesce(auth.jwt() ->> 'aal', '') <> 'aal2' and not lifecycle_row.is_test_account then
      raise exception 'verified MFA session required' using errcode = '42501';
    end if;
    update public.reviewer_lifecycles
    set mfa_verified_at = coalesce(mfa_verified_at, now()),
        state = case when terms_accepted_at is null then 'terms_required' else 'training' end,
        updated_at = now()
    where user_id = actor_id;
    event_name := 'mfa_verified';
  elsif p_step = 'terms_accepted' then
    if p_terms_version is null or length(trim(p_terms_version)) < 3 then
      raise exception 'terms version required' using errcode = '22023';
    end if;
    update public.reviewer_lifecycles
    set terms_version = p_terms_version,
        terms_accepted_at = now(),
        state = case when mfa_verified_at is null then 'mfa_required' else 'training' end,
        updated_at = now()
    where user_id = actor_id;
    event_name := 'terms_accepted';
  elsif p_step = 'walkthrough_completed' then
    if lifecycle_row.terms_accepted_at is null then
      raise exception 'terms acceptance required first' using errcode = '23514';
    end if;
    update public.reviewer_lifecycles
    set walkthrough_completed_at = now(), state = 'training', updated_at = now()
    where user_id = actor_id;
    event_name := 'walkthrough_completed';
  elsif p_step = 'practice_completed' then
    if lifecycle_row.walkthrough_completed_at is null then
      raise exception 'walkthrough required first' using errcode = '23514';
    end if;
    update public.reviewer_lifecycles
    set practice_completed_at = now(), state = 'qualification', updated_at = now()
    where user_id = actor_id;
    event_name := 'practice_completed';
  else
    raise exception 'unknown onboarding step' using errcode = '22023';
  end if;

  insert into public.reviewer_training_events (
    factory_id, user_id, event_type, training_version, actor_user_id
  ) values (
    lifecycle_row.factory_id, actor_id, event_name, p_training_version, actor_id
  );

  return public.worker_lifecycle_state();
end;
$$;

create or replace function public.ops_set_reviewer_state(
  p_user_id uuid,
  p_state text,
  p_reason text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  event_name text;
begin
  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = p_user_id
  for update;
  if lifecycle_row.user_id is null or not public.actor_is_ops(lifecycle_row.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  if p_state not in ('qualification', 'active', 'suspended', 'offboarded') then
    raise exception 'unsupported lifecycle transition' using errcode = '22023';
  end if;
  if p_state = 'active'
     and (lifecycle_row.mfa_verified_at is null
          or lifecycle_row.terms_accepted_at is null
          or lifecycle_row.practice_completed_at is null) then
    raise exception 'reviewer has not completed onboarding' using errcode = '23514';
  end if;

  update public.reviewer_lifecycles
  set state = p_state,
      qualified_at = case when p_state = 'active' then coalesce(qualified_at, now()) else qualified_at end,
      activated_at = case when p_state = 'active' then coalesce(activated_at, now()) else activated_at end,
      suspended_at = case when p_state = 'suspended' then now() else suspended_at end,
      offboarded_at = case when p_state = 'offboarded' then now() else offboarded_at end,
      state_reason = nullif(trim(p_reason), ''),
      updated_at = now()
  where user_id = p_user_id;

  update public.profiles
  set status = case when p_state = 'active' then 'active' else 'disabled' end
  where id = p_user_id;
  update public.factory_memberships
  set status = case when p_state = 'active' then 'active' else 'disabled' end,
      updated_at = now()
  where user_id = p_user_id and factory_id = lifecycle_row.factory_id;

  if p_state in ('suspended', 'offboarded') then
    update public.review_assignments
    set status = 'reassigned', updated_at = now()
    where reviewer_id = p_user_id and status in ('queued', 'leased', 'draft');
    update public.reviewer_device_registrations
    set status = 'revoked', revoked_at = now()
    where user_id = p_user_id and status = 'active';
  end if;

  event_name := case p_state
    when 'active' then 'qualification_passed'
    when 'suspended' then 'suspended'
    when 'offboarded' then 'offboarded'
    else 'qualification_failed'
  end;
  insert into public.reviewer_training_events (
    factory_id, user_id, event_type, actor_user_id, metadata
  ) values (
    lifecycle_row.factory_id, p_user_id, event_name, actor_id,
    jsonb_build_object('reason', p_reason)
  );

  return jsonb_build_object('userId', p_user_id, 'state', p_state);
end;
$$;

create or replace function public.save_worker_coverage(
  p_assignment_id uuid,
  p_lease_token text,
  p_page_epoch uuid,
  p_ranges jsonb,
  p_client_active_ms bigint
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
  invalid_count integer;
  overlap_count integer;
  covered_ms bigint;
begin
  select * into assignment_row
  from public.review_assignments assignment
  where assignment.id = p_assignment_id
    and assignment.reviewer_id = actor_id
    and assignment.status in ('leased', 'draft')
    and assignment.lease_expires_at > now() - interval '5 minutes'
    and assignment.lease_token_hash =
      encode(extensions.digest(p_lease_token, 'sha256'), 'hex')
  for update;
  if assignment_row.id is null then
    raise exception 'assignment lease is unavailable' using errcode = '42501';
  end if;
  if jsonb_typeof(p_ranges) <> 'array' or jsonb_array_length(p_ranges) > 128 then
    raise exception 'invalid coverage ranges' using errcode = '22023';
  end if;

  select * into chunk_row from public.video_chunks where id = assignment_row.chunk_id;
  select count(*) into invalid_count
  from jsonb_to_recordset(p_ranges) as range_row(start_ms bigint, end_ms bigint)
  where range_row.start_ms < chunk_row.source_start_ms
     or range_row.end_ms > chunk_row.source_end_ms
     or range_row.end_ms <= range_row.start_ms;
  if invalid_count > 0 then
    raise exception 'coverage lies outside the canonical interval' using errcode = '22023';
  end if;
  select count(*) into overlap_count
  from (
    select range_row.start_ms,
           lag(range_row.end_ms) over (order by range_row.start_ms, range_row.end_ms) as prior_end
    from jsonb_to_recordset(p_ranges) as range_row(start_ms bigint, end_ms bigint)
  ) ordered
  where ordered.prior_end is not null and ordered.start_ms < ordered.prior_end;
  if overlap_count > 0 then
    raise exception 'coverage ranges must be sorted and non-overlapping' using errcode = '22023';
  end if;

  select coalesce(sum(range_row.end_ms - range_row.start_ms), 0)
  into covered_ms
  from jsonb_to_recordset(p_ranges) as range_row(start_ms bigint, end_ms bigint);

  insert into public.review_coverage (
    assignment_id, factory_id, reviewer_id, page_epoch, ranges, client_active_ms
  ) values (
    assignment_row.id, assignment_row.factory_id, actor_id, p_page_epoch,
    p_ranges, greatest(0, p_client_active_ms)
  )
  on conflict (assignment_id) do update
    set page_epoch = excluded.page_epoch,
        ranges = excluded.ranges,
        client_active_ms = greatest(public.review_coverage.client_active_ms, excluded.client_active_ms),
        updated_at = now();

  return jsonb_build_object('coveredMs', covered_ms, 'savedAt', now());
end;
$$;

create or replace function public.worker_request_support(
  p_assignment_id uuid,
  p_reason_code text,
  p_message text
)
returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  request_id uuid;
begin
  select * into lifecycle_row from public.reviewer_lifecycles where user_id = actor_id;
  if lifecycle_row.user_id is null then
    raise exception 'reviewer is not registered' using errcode = '42501';
  end if;
  insert into public.reviewer_support_requests (
    factory_id, reviewer_id, assignment_id, reason_code, message
  ) values (
    lifecycle_row.factory_id, actor_id, p_assignment_id, p_reason_code, trim(p_message)
  ) returning id into request_id;
  return request_id;
end;
$$;

-- Existing QA identities retain their proven flow without weakening production accounts.
insert into public.reviewer_lifecycles (
  user_id, factory_id, email, state, terms_version, terms_accepted_at,
  mfa_verified_at, walkthrough_completed_at, practice_completed_at,
  qualified_at, activated_at, is_test_account
)
select profile.id, membership.factory_id, auth_user.email, 'active',
       'qa-v1', now(), now(), now(), now(), now(), now(), true
from public.profiles profile
join auth.users auth_user on auth_user.id = profile.id
join public.factory_memberships membership
  on membership.user_id = profile.id and membership.role = 'reviewer'
where auth_user.email like 'thomas+factoryvision-reviewer%-20260726@paverturf.com'
on conflict (user_id) do nothing;

alter table public.reviewer_lifecycles enable row level security;
alter table public.reviewer_invitations enable row level security;
alter table public.reviewer_device_registrations enable row level security;
alter table public.reviewer_training_events enable row level security;
alter table public.reviewer_work_sessions enable row level security;
alter table public.review_coverage enable row level security;
alter table public.reviewer_support_requests enable row level security;

alter table public.reviewer_lifecycles force row level security;
alter table public.reviewer_invitations force row level security;
alter table public.reviewer_device_registrations force row level security;
alter table public.reviewer_training_events force row level security;
alter table public.reviewer_work_sessions force row level security;
alter table public.review_coverage force row level security;
alter table public.reviewer_support_requests force row level security;

revoke all on public.reviewer_lifecycles from public, anon, authenticated;
revoke all on public.reviewer_invitations from public, anon, authenticated;
revoke all on public.reviewer_device_registrations from public, anon, authenticated;
revoke all on public.reviewer_training_events from public, anon, authenticated;
revoke all on public.reviewer_work_sessions from public, anon, authenticated;
revoke all on public.review_coverage from public, anon, authenticated;
revoke all on public.reviewer_support_requests from public, anon, authenticated;

revoke all on function public.actor_is_ops(uuid) from public, anon, authenticated;
revoke all on function public.ops_reviewer_roster() from public, anon;
revoke all on function public.service_register_reviewer_invitation(
  uuid, uuid, text, text, text, text, text, text, timestamptz, text, text
) from public, anon, authenticated;
revoke all on function public.worker_lifecycle_state() from public, anon;
revoke all on function public.worker_record_onboarding_step(text, text, text, text) from public, anon;
revoke all on function public.ops_set_reviewer_state(uuid, text, text) from public, anon;
revoke all on function public.save_worker_coverage(uuid, text, uuid, jsonb, bigint) from public, anon;
revoke all on function public.worker_request_support(uuid, text, text) from public, anon;

grant execute on function public.ops_reviewer_roster() to authenticated;
grant execute on function public.service_register_reviewer_invitation(
  uuid, uuid, text, text, text, text, text, text, timestamptz, text, text
) to authenticated;
grant execute on function public.worker_lifecycle_state() to authenticated;
grant execute on function public.worker_record_onboarding_step(text, text, text, text) to authenticated;
grant execute on function public.ops_set_reviewer_state(uuid, text, text) to authenticated;
grant execute on function public.save_worker_coverage(uuid, text, uuid, jsonb, bigint) to authenticated;
grant execute on function public.worker_request_support(uuid, text, text) to authenticated;
