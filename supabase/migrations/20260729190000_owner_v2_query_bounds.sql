-- Bound owner dashboard and history reads as durable production volume grows.

create or replace function public.owner_dashboard_truth(
  p_factory_id uuid,
  p_now_at timestamptz default now()
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
  if p_factory_id is null or p_now_at is null then
    raise exception 'factory and evaluation time are required'
      using errcode = '22023';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;

  with open_projects as (
    select
      project.id,
      project.factory_id,
      project.start_at,
      project.deadline
    from public.owner_projects project
    where project.factory_id = p_factory_id
      and project.status = 'open'
  ),
  assignments as (
    select
      assignment.id,
      assignment.project_id,
      assignment.station_id,
      assignment.effective_start,
      assignment.effective_end
    from public.owner_project_station_assignments assignment
    join open_projects project on project.id = assignment.project_id
    where assignment.factory_id = p_factory_id
      and assignment.effective_start < p_now_at
      and coalesce(assignment.effective_end, 'infinity'::timestamptz)
        > project.start_at
  ),
  latest_verifications as (
    select distinct on (verification.chunk_id)
      verification.id,
      verification.station_id,
      verification.chunk_id,
      verification.revision,
      verification.source_start_at,
      verification.source_end_at,
      verification.status
    from public.owner_verification_intervals verification
    where verification.factory_id = p_factory_id
    order by
      verification.chunk_id,
      verification.revision desc,
      verification.id desc
  ),
  relevant_verifications as (
    select distinct
      verification.id,
      verification.station_id,
      verification.chunk_id,
      verification.revision,
      verification.source_start_at,
      verification.source_end_at,
      verification.status
    from latest_verifications verification
    join assignments assignment
      on assignment.station_id = verification.station_id
    join open_projects project on project.id = assignment.project_id
    where verification.source_start_at < p_now_at
      and verification.source_end_at
        > greatest(project.start_at, assignment.effective_start)
      and verification.source_start_at
        < coalesce(
          assignment.effective_end,
            p_now_at
          )
  ),
  event_buckets as (
    select
      assignment.project_id,
      production_event.station_id,
      date_bin(
        interval '15 minutes',
        production_event.occurred_at,
        '1970-01-01T00:00:00Z'::timestamptz
      ) as occurred_at,
      count(*)::bigint as good_units,
      count(*) filter (
        where production_event.occurred_at
          >= p_now_at - interval '1 hour'
      )::bigint as recent_good_units,
      true as verified
    from public.owner_production_events production_event
    join latest_verifications verification
      on verification.chunk_id = production_event.chunk_id
     and verification.status = 'verified'
     and verification.station_id = production_event.station_id
     and production_event.occurred_at >= verification.source_start_at
     and production_event.occurred_at < verification.source_end_at
    join assignments assignment
      on assignment.station_id = production_event.station_id
     and production_event.occurred_at >= assignment.effective_start
     and production_event.occurred_at
       < coalesce(assignment.effective_end, p_now_at)
    join open_projects project on project.id = assignment.project_id
    where production_event.factory_id = p_factory_id
      and production_event.occurred_at >= project.start_at
      and production_event.occurred_at < p_now_at
    group by
      assignment.project_id,
      production_event.station_id,
      date_bin(
        interval '15 minutes',
        production_event.occurred_at,
        '1970-01-01T00:00:00Z'::timestamptz
      )
  ),
  worker_intervals as (
    select
      worker_interval.id,
      worker_interval.project_id,
      worker_interval.station_id,
      worker_interval.effective_start,
      worker_interval.effective_end,
      worker_interval.loaded_labor_rate_cents_per_hour
    from public.owner_worker_station_intervals worker_interval
    join open_projects project on project.id = worker_interval.project_id
    where worker_interval.factory_id = p_factory_id
      and worker_interval.effective_start < p_now_at
      and coalesce(worker_interval.effective_end, 'infinity'::timestamptz)
        > project.start_at
  ),
  downtime as (
    select
      downtime_interval.id,
      downtime_interval.project_id,
      downtime_interval.station_id,
      downtime_interval.effective_start,
      downtime_interval.effective_end
    from public.owner_station_downtime_intervals downtime_interval
    join open_projects project on project.id = downtime_interval.project_id
    where downtime_interval.factory_id = p_factory_id
      and downtime_interval.effective_start < p_now_at
      and downtime_interval.effective_end > project.start_at
  ),
  adjustments as (
    select
      adjustment.id,
      adjustment.project_id,
      adjustment.station_id,
      adjustment.delta_good_units,
      adjustment.occurred_at
    from public.owner_output_adjustments adjustment
    join open_projects project on project.id = adjustment.project_id
    where adjustment.factory_id = p_factory_id
      and adjustment.occurred_at >= project.start_at
      and adjustment.occurred_at < p_now_at
  )
  select jsonb_build_object(
    'assignments',
    coalesce(
      (
        select jsonb_agg(to_jsonb(row_value) order by effective_start, id)
        from assignments row_value
      ),
      '[]'::jsonb
    ),
    'events',
    coalesce(
      (
        select jsonb_agg(to_jsonb(row_value) order by occurred_at, project_id)
        from event_buckets row_value
      ),
      '[]'::jsonb
    ),
    'verifications',
    coalesce(
      (
        select jsonb_agg(
          to_jsonb(row_value)
          order by source_start_at, chunk_id
        )
        from relevant_verifications row_value
      ),
      '[]'::jsonb
    ),
    'workerIntervals',
    coalesce(
      (
        select jsonb_agg(to_jsonb(row_value) order by effective_start, id)
        from worker_intervals row_value
      ),
      '[]'::jsonb
    ),
    'downtime',
    coalesce(
      (
        select jsonb_agg(to_jsonb(row_value) order by effective_start, id)
        from downtime row_value
      ),
      '[]'::jsonb
    ),
    'adjustments',
    coalesce(
      (
        select jsonb_agg(to_jsonb(row_value) order by occurred_at, id)
        from adjustments row_value
      ),
      '[]'::jsonb
    )
  )
  into result;

  return result;
end;
$$;

create or replace function public.owner_history_filter_options(
  p_factory_id uuid
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
  if p_factory_id is null then
    raise exception 'factory is required' using errcode = '22023';
  end if;
  if not public.owner_has_active_role(p_factory_id, 'owner') then
    raise exception 'owner access denied' using errcode = '42501';
  end if;

  with latest_closeouts as (
    select distinct on (closeout.project_id)
      closeout.project_id,
      closeout.snapshot
    from public.owner_project_closeouts closeout
    where closeout.factory_id = p_factory_id
    order by
      closeout.project_id,
      closeout.revision desc,
      closeout.created_at desc,
      closeout.id desc
  ),
  project_values as (
    select distinct trim(snapshot ->> 'project_name') as value
    from latest_closeouts
    where nullif(trim(snapshot ->> 'project_name'), '') is not null
    order by value
    limit 500
  ),
  customer_values as (
    select distinct trim(snapshot ->> 'customer_name') as value
    from latest_closeouts
    where nullif(trim(snapshot ->> 'customer_name'), '') is not null
    order by value
    limit 500
  ),
  station_values as (
    select distinct trim(item.value) as value
    from latest_closeouts closeout
    cross join lateral jsonb_array_elements_text(
      case
        when jsonb_typeof(closeout.snapshot -> 'station_names') = 'array'
          then closeout.snapshot -> 'station_names'
        else '[]'::jsonb
      end
    ) item
    where nullif(trim(item.value), '') is not null
    order by value
    limit 500
  ),
  shift_values as (
    select distinct trim(item.value) as value
    from latest_closeouts closeout
    cross join lateral jsonb_array_elements_text(
      case
        when jsonb_typeof(closeout.snapshot -> 'shift_names') = 'array'
          then closeout.snapshot -> 'shift_names'
        else '[]'::jsonb
      end
    ) item
    where nullif(trim(item.value), '') is not null
    order by value
    limit 500
  ),
  team_values as (
    select distinct trim(item.value) as value
    from latest_closeouts closeout
    cross join lateral jsonb_array_elements_text(
      case
        when jsonb_typeof(closeout.snapshot -> 'team_names') = 'array'
          then closeout.snapshot -> 'team_names'
        else '[]'::jsonb
      end
    ) item
    where nullif(trim(item.value), '') is not null
    order by value
    limit 500
  )
  select jsonb_build_object(
    'projects',
    coalesce(
      (select jsonb_agg(value order by value) from project_values),
      '[]'::jsonb
    ),
    'customers',
    coalesce(
      (select jsonb_agg(value order by value) from customer_values),
      '[]'::jsonb
    ),
    'stations',
    coalesce(
      (select jsonb_agg(value order by value) from station_values),
      '[]'::jsonb
    ),
    'shifts',
    coalesce(
      (select jsonb_agg(value order by value) from shift_values),
      '[]'::jsonb
    ),
    'teams',
    coalesce(
      (select jsonb_agg(value order by value) from team_values),
      '[]'::jsonb
    )
  )
  into result;

  return result;
end;
$$;

revoke all on function public.owner_dashboard_truth(uuid, timestamptz)
  from public, anon;
revoke all on function public.owner_history_filter_options(uuid)
  from public, anon;
grant execute on function public.owner_dashboard_truth(uuid, timestamptz)
  to authenticated;
grant execute on function public.owner_history_filter_options(uuid)
  to authenticated;
