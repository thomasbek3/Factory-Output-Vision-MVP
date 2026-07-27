-- Coverage is monotonic evidence. Merge stale-page writes under a row lock so
-- an older tab can never erase intervals already observed by a newer tab.

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
  coverage_row public.review_coverage%rowtype;
  invalid_count integer;
  overlap_count integer;
  covered_ms bigint;
  merged_ranges jsonb;
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

  select * into chunk_row
  from public.video_chunks
  where id = assignment_row.chunk_id;
  select count(*) into invalid_count
  from jsonb_to_recordset(p_ranges) as range_row(start_ms bigint, end_ms bigint)
  where range_row.start_ms < chunk_row.source_start_ms
     or range_row.end_ms > chunk_row.source_end_ms
     or range_row.end_ms <= range_row.start_ms;
  if invalid_count > 0 then
    raise exception 'coverage lies outside the canonical interval'
      using errcode = '22023';
  end if;
  select count(*) into overlap_count
  from (
    select range_row.start_ms,
           lag(range_row.end_ms) over (
             order by range_row.start_ms, range_row.end_ms
           ) as prior_end
    from jsonb_to_recordset(p_ranges)
      as range_row(start_ms bigint, end_ms bigint)
  ) ordered
  where ordered.prior_end is not null
    and ordered.start_ms < ordered.prior_end;
  if overlap_count > 0 then
    raise exception 'coverage ranges must be sorted and non-overlapping'
      using errcode = '22023';
  end if;

  select * into coverage_row
  from public.review_coverage
  where assignment_id = assignment_row.id
  for update;

  with combined as (
    select range_row.start_ms, range_row.end_ms
    from jsonb_to_recordset(p_ranges)
      as range_row(start_ms bigint, end_ms bigint)
    union all
    select range_row.start_ms, range_row.end_ms
    from jsonb_to_recordset(coalesce(coverage_row.ranges, '[]'::jsonb))
      as range_row(start_ms bigint, end_ms bigint)
  ),
  ordered as (
    select start_ms, end_ms,
           max(end_ms) over (
             order by start_ms, end_ms
             rows between unbounded preceding and 1 preceding
           ) as prior_max_end
    from combined
  ),
  islands as (
    select start_ms, end_ms,
           sum(
             case
               when prior_max_end is null or start_ms > prior_max_end then 1
               else 0
             end
           ) over (order by start_ms, end_ms) as island_id
    from ordered
  ),
  merged as (
    select min(start_ms) as start_ms, max(end_ms) as end_ms
    from islands
    group by island_id
  )
  select coalesce(
    jsonb_agg(
      jsonb_build_object('start_ms', start_ms, 'end_ms', end_ms)
      order by start_ms, end_ms
    ),
    '[]'::jsonb
  ) into merged_ranges
  from merged;

  if jsonb_array_length(merged_ranges) > 128 then
    raise exception 'merged coverage contains too many ranges'
      using errcode = '22023';
  end if;
  select coalesce(sum(range_row.end_ms - range_row.start_ms), 0)
  into covered_ms
  from jsonb_to_recordset(merged_ranges)
    as range_row(start_ms bigint, end_ms bigint);

  insert into public.review_coverage (
    assignment_id, factory_id, reviewer_id, page_epoch, ranges, client_active_ms
  ) values (
    assignment_row.id, assignment_row.factory_id, actor_id, p_page_epoch,
    merged_ranges, greatest(0, p_client_active_ms)
  )
  on conflict (assignment_id) do update
    set page_epoch = excluded.page_epoch,
        ranges = merged_ranges,
        client_active_ms = greatest(
          public.review_coverage.client_active_ms,
          excluded.client_active_ms
        ),
        updated_at = now();

  return jsonb_build_object(
    'coveredMs', covered_ms,
    'ranges', merged_ranges,
    'savedAt', now()
  );
end;
$$;
