-- The resolver atomically creates a validated human finalization before
-- marking an assigned chunk resolved. Permit that direct transition only when
-- the durable finalization already exists.

create or replace function public.guard_chunk_state_transition()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.state = 'published' and new.published_at is null then
    raise exception 'published chunks require published_at' using errcode = '23514';
  end if;
  if old.published_at is not null
     and new.published_at is distinct from old.published_at then
    raise exception 'chunk published_at is immutable once set' using errcode = '55000';
  end if;

  if new.state is distinct from old.state and not (
    (old.state = 'ingesting' and new.state in ('transcoding', 'quarantined', 'deleted'))
    or (old.state = 'transcoding' and new.state in ('ready', 'quarantined', 'deleted'))
    or (old.state = 'ready' and new.state in ('assigned', 'quarantined', 'retained', 'deleted'))
    or (old.state = 'assigned' and new.state in ('ready', 'resolving', 'quarantined'))
    or (
      old.state = 'assigned'
      and new.state = 'resolved'
      and exists (
        select 1 from public.human_finalizations finalization
        where finalization.chunk_id = old.id
          and finalization.factory_id = old.factory_id
      )
    )
    or (old.state = 'resolving' and new.state in ('assigned', 'resolved', 'quarantined'))
    or (old.state = 'resolved' and new.state in ('assigned', 'published', 'quarantined'))
    or (old.state = 'published' and new.state in ('retained', 'quarantined'))
    or (old.state = 'quarantined' and new.state in ('transcoding', 'retained', 'deleted'))
    or (old.state = 'retained' and new.state = 'deleted')
  ) then
    raise exception 'invalid chunk state transition from % to %', old.state, new.state
      using errcode = '23514';
  end if;

  return new;
end;
$$;
