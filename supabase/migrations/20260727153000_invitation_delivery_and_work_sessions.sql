-- Make invitation delivery state explicit and turn reviewer session evidence
-- into a bounded, server-verified heartbeat rather than trusting raw timers.

create unique index reviewer_one_open_work_session_idx
  on public.reviewer_work_sessions (reviewer_id)
  where ended_at is null;

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
    factory_id, user_id, email, locale, status, expires_at, invited_by
  ) values (
    p_factory_id, p_user_id, lower(trim(p_email)), p_locale,
    'created', p_expires_at, actor_id
  ) returning id into invitation_id;

  return invitation_id;
end;
$$;

create or replace function public.ops_mark_reviewer_invitation_delivery(
  p_invitation_id uuid,
  p_status text,
  p_delivery_provider text default null,
  p_delivery_id text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  invitation_row public.reviewer_invitations%rowtype;
begin
  select * into invitation_row
  from public.reviewer_invitations
  where id = p_invitation_id
  for update;
  if invitation_row.id is null or not public.actor_is_ops(invitation_row.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  if invitation_row.status not in ('created', 'delivery_failed') then
    raise exception 'invitation delivery is already final' using errcode = '55000';
  end if;
  if p_status not in ('sent', 'delivery_failed') then
    raise exception 'unsupported delivery status' using errcode = '22023';
  end if;
  if p_status = 'sent' and (p_delivery_provider is null or p_delivery_id is null) then
    raise exception 'delivery receipt required' using errcode = '23514';
  end if;

  update public.reviewer_invitations
  set status = p_status,
      delivery_provider = p_delivery_provider,
      delivery_id = p_delivery_id,
      sent_at = case when p_status = 'sent' then now() else null end
  where id = p_invitation_id;

  return jsonb_build_object(
    'invitationId', p_invitation_id,
    'status', p_status,
    'deliveryId', p_delivery_id
  );
end;
$$;

create or replace function public.worker_touch_work_session(
  p_session_id uuid,
  p_device_id_hash text,
  p_active_seconds_delta integer default 0
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle_row public.reviewer_lifecycles%rowtype;
  session_row public.reviewer_work_sessions%rowtype;
  bounded_delta integer;
begin
  select * into lifecycle_row
  from public.reviewer_lifecycles
  where user_id = actor_id and state = 'active';
  if lifecycle_row.user_id is null then
    raise exception 'active reviewer required' using errcode = '42501';
  end if;
  if p_device_id_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid device identifier' using errcode = '22023';
  end if;
  bounded_delta := greatest(0, least(coalesce(p_active_seconds_delta, 0), 60));

  insert into public.reviewer_device_registrations (user_id, device_id_hash)
  values (actor_id, p_device_id_hash)
  on conflict (user_id, device_id_hash) do update
    set status = 'active', last_seen_at = now(), revoked_at = null;

  if p_session_id is not null then
    select * into session_row
    from public.reviewer_work_sessions
    where id = p_session_id and reviewer_id = actor_id and ended_at is null
    for update;
  else
    select * into session_row
    from public.reviewer_work_sessions
    where reviewer_id = actor_id and ended_at is null
    for update;
  end if;

  if session_row.id is null then
    insert into public.reviewer_work_sessions (
      factory_id, reviewer_id, device_id_hash
    ) values (
      lifecycle_row.factory_id, actor_id, p_device_id_hash
    ) returning * into session_row;
  elsif session_row.device_id_hash <> p_device_id_hash then
    raise exception 'work session belongs to a different device' using errcode = '42501';
  end if;

  update public.reviewer_work_sessions
  set last_seen_at = now(),
      active_seconds = active_seconds + bounded_delta
  where id = session_row.id
  returning * into session_row;

  return jsonb_build_object(
    'sessionId', session_row.id,
    'startedAt', session_row.started_at,
    'lastSeenAt', session_row.last_seen_at,
    'activeSeconds', session_row.active_seconds
  );
end;
$$;

create or replace function public.worker_close_work_session(
  p_session_id uuid,
  p_close_reason text default 'signed_out'
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  session_row public.reviewer_work_sessions%rowtype;
begin
  update public.reviewer_work_sessions
  set ended_at = now(),
      last_seen_at = now(),
      close_reason = left(coalesce(nullif(trim(p_close_reason), ''), 'closed'), 80)
  where id = p_session_id
    and reviewer_id = actor_id
    and ended_at is null
  returning * into session_row;
  if session_row.id is null then
    return jsonb_build_object('sessionId', p_session_id, 'alreadyClosed', true);
  end if;
  return jsonb_build_object(
    'sessionId', session_row.id,
    'endedAt', session_row.ended_at,
    'activeSeconds', session_row.active_seconds,
    'alreadyClosed', false
  );
end;
$$;

create or replace function public.increment_open_work_session_submission()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  update public.reviewer_work_sessions
  set submitted_chunks = submitted_chunks + 1,
      last_seen_at = now()
  where reviewer_id = new.reviewer_id and ended_at is null;
  return new;
end;
$$;

create trigger reviewer_work_session_submission_count
after insert on public.review_submissions
for each row execute function public.increment_open_work_session_submission();

revoke all on function public.increment_open_work_session_submission()
  from public, anon, authenticated;
revoke all on function public.ops_mark_reviewer_invitation_delivery(
  uuid, text, text, text
) from public, anon;
revoke all on function public.worker_touch_work_session(
  uuid, text, integer
) from public, anon;
revoke all on function public.worker_close_work_session(
  uuid, text
) from public, anon;

grant execute on function public.ops_mark_reviewer_invitation_delivery(
  uuid, text, text, text
) to authenticated;
grant execute on function public.worker_touch_work_session(
  uuid, text, integer
) to authenticated;
grant execute on function public.worker_close_work_session(
  uuid, text
) to authenticated;
