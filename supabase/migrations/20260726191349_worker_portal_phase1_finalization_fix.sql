-- Fix PL/pgSQL ambiguity found by the live rollback fixture.

create or replace function public.validate_finalization_cardinality()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  finalization_key uuid;
  expected_count integer;
  published_count integer;
begin
  if tg_table_name = 'human_finalizations' then
    finalization_key = new.id;
  else
    finalization_key = new.finalization_id;
  end if;

  select cr.resolved_total, count(rhce.id)::integer
  into expected_count, published_count
  from public.human_finalizations hf
  join public.consensus_runs cr on cr.id = hf.consensus_run_id
  left join public.resolved_human_count_events rhce
    on rhce.finalization_id = hf.id
   and rhce.publication_status = 'published'
  where hf.id = finalization_key
  group by cr.resolved_total;

  if expected_count is null or published_count <> expected_count then
    raise exception 'published event count does not match finalized consensus' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function public.validate_finalization_cardinality()
from public, anon, authenticated;
grant execute on function public.validate_finalization_cardinality() to service_role;
