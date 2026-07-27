-- Make suspension terminate reviewer authorization and make invitation
-- delivery idempotent across an operator retry, including ambiguous provider
-- outcomes.

alter table public.reviewer_invitations
  drop constraint if exists reviewer_invitations_status_check;
alter table public.reviewer_invitations
  add constraint reviewer_invitations_status_check
  check (status in (
    'created', 'sending', 'sent', 'accepted', 'expired', 'revoked',
    'delivery_failed', 'delivery_unknown'
  ));
alter table public.reviewer_invitations
  add column request_key uuid,
  add column delivery_started_at timestamptz;
update public.reviewer_invitations
set request_key = gen_random_uuid()
where request_key is null;
alter table public.reviewer_invitations
  alter column request_key set not null;
create unique index reviewer_invitations_request_key_idx
  on public.reviewer_invitations (request_key);

drop function if exists public.service_register_reviewer_invitation(
  uuid, uuid, text, text, text, text, text, text, timestamptz, text, text, text
);

create or replace function public.ops_reviewer_invitation_request(
  p_request_key uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  invitation public.reviewer_invitations%rowtype;
begin
  select * into invitation
  from public.reviewer_invitations candidate
  where candidate.request_key = p_request_key;
  if invitation.id is null then
    return null;
  end if;
  if not public.actor_is_ops(invitation.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'invitationId', invitation.id,
    'status', invitation.status,
    'deliveryId', invitation.delivery_id,
    'expiresAt', invitation.expires_at
  );
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
  p_delivery_id text,
  p_invitation_token_hash text,
  p_request_key uuid
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
  if p_expires_at <= now() or p_expires_at > now() + interval '24 hours' then
    raise exception 'invitation expiry is invalid' using errcode = '22023';
  end if;
  if p_invitation_token_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invitation token hash is invalid' using errcode = '22023';
  end if;
  if p_request_key is null then
    raise exception 'invitation request key is required' using errcode = '22023';
  end if;

  select candidate.id into invitation_id
  from public.reviewer_invitations candidate
  where candidate.request_key = p_request_key;
  if invitation_id is not null then
    return invitation_id;
  end if;

  insert into public.profiles (id, display_name, locale, status)
  values (p_user_id, trim(p_display_name), p_locale, 'invited')
  on conflict (id) do update
    set display_name = excluded.display_name,
        locale = excluded.locale,
        status = case
          when public.profiles.status = 'active' then public.profiles.status
          else 'invited'
        end,
        updated_at = now();

  insert into public.factory_memberships (factory_id, user_id, role, status)
  values (p_factory_id, p_user_id, 'reviewer', 'disabled')
  on conflict (factory_id, user_id) do update
    set role = 'reviewer',
        status = case
          when public.factory_memberships.status = 'active'
            then public.factory_memberships.status
          else 'disabled'
        end,
        updated_at = now();

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
        state = public.reviewer_lifecycles.state,
        country_code = excluded.country_code,
        employment_classification = excluded.employment_classification,
        pay_basis = excluded.pay_basis,
        state_reason = null,
        invited_at = now(),
        updated_at = now();

  update public.reviewer_invitations
  set status = 'revoked', revoked_at = now()
  where user_id = p_user_id
    and status in (
      'created', 'sending', 'sent', 'delivery_failed', 'delivery_unknown'
    );

  insert into public.reviewer_invitations (
    factory_id, user_id, email, locale, status, expires_at, invited_by,
    invitation_token_hash, request_key
  ) values (
    p_factory_id, p_user_id, lower(trim(p_email)), p_locale,
    'created', p_expires_at, actor_id, p_invitation_token_hash, p_request_key
  )
  on conflict (request_key) do nothing
  returning id into invitation_id;
  if invitation_id is null then
    select candidate.id into invitation_id
    from public.reviewer_invitations candidate
    where candidate.request_key = p_request_key;
  end if;
  return invitation_id;
end;
$$;

create or replace function public.ops_claim_reviewer_invitation_delivery(
  p_invitation_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  invitation public.reviewer_invitations%rowtype;
begin
  select * into invitation
  from public.reviewer_invitations candidate
  where candidate.id = p_invitation_id
  for update;
  if invitation.id is null
     or not public.actor_is_ops(invitation.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  if invitation.status <> 'created' then
    return jsonb_build_object(
      'claimed', false,
      'status', invitation.status
    );
  end if;
  update public.reviewer_invitations
  set status = 'sending', delivery_started_at = now()
  where id = invitation.id;
  return jsonb_build_object('claimed', true, 'status', 'sending');
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
  invitation public.reviewer_invitations%rowtype;
begin
  select * into invitation
  from public.reviewer_invitations candidate
  where candidate.id = p_invitation_id
  for update;
  if invitation.id is null
     or not public.actor_is_ops(invitation.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  if invitation.status <> 'sending' then
    raise exception 'invitation delivery is not claimed'
      using errcode = '55000';
  end if;
  if p_status not in ('sent', 'delivery_failed') then
    raise exception 'unsupported delivery status' using errcode = '22023';
  end if;
  if p_status = 'sent'
     and (p_delivery_provider is null or p_delivery_id is null) then
    raise exception 'delivery receipt required' using errcode = '23514';
  end if;

  update public.reviewer_invitations
  set status = p_status,
      delivery_provider = p_delivery_provider,
      delivery_id = p_delivery_id,
      sent_at = case when p_status = 'sent' then now() else null end
  where id = invitation.id;
  return jsonb_build_object(
    'invitationId', invitation.id,
    'status', p_status,
    'deliveryId', p_delivery_id
  );
end;
$$;

create or replace function public.service_expire_reviewer_invitations()
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  changed_count integer := 0;
  affected_count integer;
begin
  update public.reviewer_invitations
  set status = 'delivery_unknown'
  where status = 'sending'
    and delivery_started_at < now() - interval '15 minutes';
  get diagnostics affected_count = row_count;
  changed_count := changed_count + affected_count;

  update public.reviewer_invitations
  set status = 'expired'
  where status in (
    'created', 'sent', 'delivery_failed', 'delivery_unknown'
  )
    and expires_at <= now();
  get diagnostics affected_count = row_count;
  changed_count := changed_count + affected_count;
  return changed_count;
end;
$$;

create or replace function public.worker_authorize_reviewer_session()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  actor_id uuid := auth.uid();
  lifecycle public.reviewer_lifecycles%rowtype;
begin
  select * into lifecycle
  from public.reviewer_lifecycles
  where user_id = actor_id;
  if lifecycle.user_id is null and public.actor_is_ops(null) then
    return jsonb_build_object('authorized', true, 'state', 'ops');
  end if;
  if lifecycle.user_id is null then
    raise exception 'reviewer is not registered' using errcode = '42501';
  end if;
  if lifecycle.state in ('suspended', 'offboarded') then
    raise exception 'reviewer access is disabled' using errcode = '42501';
  end if;
  if lifecycle.state = 'invited'
     and not exists (
       select 1 from public.reviewer_invitations invitation
       where invitation.user_id = actor_id
         and invitation.status = 'accepted'
         and invitation.accepted_at is not null
     ) then
    raise exception 'an accepted invitation is required' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'authorized', true,
    'state', lifecycle.state
  );
end;
$$;

create or replace function public.ops_revoke_reviewer_invitation(
  p_user_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  lifecycle public.reviewer_lifecycles%rowtype;
  revoked_count integer;
begin
  select * into lifecycle
  from public.reviewer_lifecycles
  where user_id = p_user_id;
  if lifecycle.user_id is null
     or not public.actor_is_ops(lifecycle.factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  update public.reviewer_invitations
  set status = 'revoked', revoked_at = now()
  where user_id = p_user_id
    and status in (
      'created', 'sending', 'sent', 'delivery_failed', 'delivery_unknown'
    );
  get diagnostics revoked_count = row_count;
  if revoked_count = 0 then
    raise exception 'no open invitation is available to revoke'
      using errcode = 'P0002';
  end if;
  return jsonb_build_object(
    'userId', p_user_id,
    'revoked', revoked_count
  );
end;
$$;

revoke all on function public.ops_reviewer_invitation_request(uuid)
  from public, anon;
grant execute on function public.ops_reviewer_invitation_request(uuid)
  to authenticated;
revoke all on function public.service_register_reviewer_invitation(
  uuid, uuid, text, text, text, text, text, text, timestamptz, text, text, text,
  uuid
) from public, anon;
grant execute on function public.service_register_reviewer_invitation(
  uuid, uuid, text, text, text, text, text, text, timestamptz, text, text, text,
  uuid
) to authenticated;
revoke all on function public.ops_claim_reviewer_invitation_delivery(uuid)
  from public, anon;
grant execute on function public.ops_claim_reviewer_invitation_delivery(uuid)
  to authenticated;
