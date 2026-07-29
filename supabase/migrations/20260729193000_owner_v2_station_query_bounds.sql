-- Keep the station shift surface bounded at high production rates.

create or replace function public.owner_station_event_buckets(
  p_factory_id uuid,
  p_station_id uuid,
  p_project_id uuid,
  p_window_start timestamptz,
  p_window_end timestamptz
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  result jsonb;
begin
  if p_factory_id is null
    or p_station_id is null
    or p_project_id is null
    or p_window_start is null
    or p_window_end is null
    or p_window_end <= p_window_start
    or p_window_end - p_window_start > interval '36 hours'
  then
    raise exception 'valid station shift window is required'
      using errcode = '22023';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;
  if not exists (
    select 1
    from public.owner_projects project
    join public.owner_project_station_assignments assignment
      on assignment.project_id = project.id
     and assignment.factory_id = project.factory_id
    where project.id = p_project_id
      and project.factory_id = p_factory_id
      and assignment.station_id = p_station_id
      and assignment.effective_start < p_window_end
      and coalesce(assignment.effective_end, 'infinity'::timestamptz)
        > p_window_start
  ) then
    raise exception 'station project assignment not found'
      using errcode = '42501';
  end if;

  with latest_verifications as (
    select distinct on (verification.chunk_id)
      verification.chunk_id,
      verification.station_id,
      verification.source_start_at,
      verification.source_end_at,
      verification.status
    from public.owner_verification_intervals verification
    where verification.factory_id = p_factory_id
      and verification.station_id = p_station_id
      and verification.source_start_at < p_window_end
      and verification.source_end_at > p_window_start
    order by
      verification.chunk_id,
      verification.revision desc,
      verification.id desc
  ),
  buckets as (
    select
      date_bin(
        interval '15 minutes',
        production_event.occurred_at,
        p_window_start
      ) as occurred_at,
      count(*)::bigint as good_units,
      true as verified
    from public.owner_production_events production_event
    join latest_verifications verification
      on verification.chunk_id = production_event.chunk_id
     and verification.status = 'verified'
     and verification.station_id = production_event.station_id
     and production_event.occurred_at >= verification.source_start_at
     and production_event.occurred_at < verification.source_end_at
    where production_event.factory_id = p_factory_id
      and production_event.station_id = p_station_id
      and production_event.occurred_at >= p_window_start
      and production_event.occurred_at < p_window_end
      and exists (
        select 1
        from public.owner_project_station_assignments assignment
        where assignment.project_id = p_project_id
          and assignment.factory_id = p_factory_id
          and assignment.station_id = p_station_id
          and production_event.occurred_at >= assignment.effective_start
          and production_event.occurred_at
            < coalesce(assignment.effective_end, p_window_end)
      )
    group by date_bin(
      interval '15 minutes',
      production_event.occurred_at,
      p_window_start
    )
  )
  select coalesce(
    jsonb_agg(to_jsonb(bucket) order by bucket.occurred_at),
    '[]'::jsonb
  )
  into result
  from buckets bucket;

  return result;
end;
$$;

revoke all on function public.owner_station_event_buckets(
  uuid, uuid, uuid, timestamptz, timestamptz
) from public, anon;
grant execute on function public.owner_station_event_buckets(
  uuid, uuid, uuid, timestamptz, timestamptz
) to authenticated;
