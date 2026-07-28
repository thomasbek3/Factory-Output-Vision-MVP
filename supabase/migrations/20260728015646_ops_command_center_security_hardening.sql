-- Close the invite authorization ordering gap, keep AI output hidden until
-- human truth is final, and add the indexes used by the ops projection.

create or replace function public.ops_assert_access()
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if not public.actor_is_ops(null) then
    raise exception 'ops access required' using errcode = '42501';
  end if;
  return true;
end;
$$;

revoke all on function public.ops_assert_access() from public, anon;
grant execute on function public.ops_assert_access() to authenticated;

alter function public.ops_command_center()
  rename to ops_command_center_internal_v1;

revoke all on function public.ops_command_center_internal_v1()
  from public, anon, authenticated;

create or replace function public.ops_command_center()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  raw_result jsonb;
  safe_labels jsonb;
begin
  if not public.actor_is_ops(null) then
    raise exception 'ops access required' using errcode = '42501';
  end if;

  raw_result := public.ops_command_center_internal_v1();
  select coalesce(jsonb_agg(
    case
      when label ->> 'humanFinalAt' is null then
        (
          label
          - 'aiRunId'
          - 'aiCodeVersion'
          - 'aiEventCount'
          - 'comparisonMetrics'
          - 'comparisonCreatedAt'
        ) || jsonb_build_object(
          'aiRunId', null,
          'aiCodeVersion', null,
          'aiEventCount', 0,
          'comparisonMetrics', null,
          'comparisonCreatedAt', null,
          'aiStatus', case
            when label ->> 'aiStatus' = 'not_run' then 'not_run'
            else 'locked_until_human_final'
          end
        )
      else label
    end
  ), '[]'::jsonb)
  into safe_labels
  from jsonb_array_elements(coalesce(raw_result -> 'labels', '[]'::jsonb)) label;

  return jsonb_set(raw_result, '{labels}', safe_labels, true);
end;
$$;

revoke all on function public.ops_command_center() from public, anon;
grant execute on function public.ops_command_center() to authenticated;

create index if not exists review_submissions_recent_ops_idx
  on public.review_submissions (submitted_at desc, factory_id);

create index if not exists review_assignments_chunk_round_status_ops_idx
  on public.review_assignments (chunk_id, review_round desc, status);

create index if not exists review_assignments_open_age_ops_idx
  on public.review_assignments (assigned_at, factory_id)
  where status in ('queued', 'leased', 'draft');
