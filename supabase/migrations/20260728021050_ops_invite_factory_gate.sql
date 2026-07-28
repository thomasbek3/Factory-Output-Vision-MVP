-- Authorize the selected factory before invite configuration or auth-admin work.

drop function public.ops_assert_access();

create or replace function public.ops_assert_access(p_factory_id uuid default null)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if not public.actor_is_ops(p_factory_id) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  return true;
end;
$$;

revoke all on function public.ops_assert_access(uuid) from public, anon;
grant execute on function public.ops_assert_access(uuid) to authenticated;
