-- Keep synthetic QA identities out of production scheduling at the data
-- boundary, even when an older scheduler function is invoked.

update public.reviewer_lifecycles lifecycle
set state = 'suspended',
    suspended_at = coalesce(lifecycle.suspended_at, now()),
    state_reason = 'test_account_requires_test_factory',
    updated_at = now()
from public.factories factory
where lifecycle.factory_id = factory.id
  and lifecycle.is_test_account
  and not factory.is_test
  and lifecycle.state <> 'offboarded';

create or replace function public.enforce_test_account_factory()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  target_is_test boolean;
begin
  if not new.is_test_account or new.state in ('suspended', 'offboarded') then
    return new;
  end if;

  select factory.is_test into target_is_test
  from public.factories factory
  where factory.id = new.factory_id;

  if not coalesce(target_is_test, false) then
    raise exception 'test accounts require an explicitly marked test factory'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

drop trigger if exists reviewer_lifecycles_test_factory_guard
  on public.reviewer_lifecycles;
create trigger reviewer_lifecycles_test_factory_guard
before insert or update of factory_id, is_test_account, state
on public.reviewer_lifecycles
for each row execute function public.enforce_test_account_factory();

create or replace function public.service_pick_reviewer(
  p_factory_id uuid,
  p_chunk_id uuid,
  p_review_round integer
)
returns uuid
language sql
security definer
set search_path = ''
as $$
  select lifecycle.user_id
  from public.reviewer_lifecycles lifecycle
  join public.factories factory
    on factory.id = lifecycle.factory_id
  join public.profiles profile
    on profile.id = lifecycle.user_id and profile.status = 'active'
  join public.factory_memberships membership
    on membership.user_id = lifecycle.user_id
   and membership.factory_id = lifecycle.factory_id
   and membership.role = 'reviewer'
   and membership.status = 'active'
  where lifecycle.factory_id = p_factory_id
    and lifecycle.state = 'active'
    and (not lifecycle.is_test_account or factory.is_test)
    and not exists (
      select 1 from public.review_assignments prior
      where prior.chunk_id = p_chunk_id
        and prior.review_round = p_review_round
        and prior.reviewer_id = lifecycle.user_id
    )
    and (
      lifecycle.is_test_account
      or exists (
        select 1 from public.reviewer_device_registrations device
        where device.user_id = lifecycle.user_id and device.status = 'active'
      )
    )
    and not exists (
      select 1
      from public.reviewer_device_registrations candidate_device
      join public.reviewer_device_registrations assigned_device
        on assigned_device.device_id_hash = candidate_device.device_id_hash
       and assigned_device.status = 'active'
      join public.review_assignments assigned
        on assigned.reviewer_id = assigned_device.user_id
       and assigned.chunk_id = p_chunk_id
       and assigned.review_round = p_review_round
       and assigned.status not in ('expired', 'reassigned')
      where candidate_device.user_id = lifecycle.user_id
        and candidate_device.status = 'active'
    )
  order by (
    select count(*) from public.review_assignments active_work
    where active_work.reviewer_id = lifecycle.user_id
      and active_work.status in ('queued', 'leased', 'draft')
  ), lifecycle.activated_at, lifecycle.user_id
  limit 1;
$$;

revoke all on function public.enforce_test_account_factory()
  from public, anon, authenticated;
revoke all on function public.service_pick_reviewer(uuid, uuid, integer)
  from public, anon, authenticated;
