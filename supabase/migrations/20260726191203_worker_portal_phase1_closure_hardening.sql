-- Closure hardening from the second Opus 5 high-effort checkpoint.

create or replace function public.guard_assignment_transition()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.factory_id is distinct from old.factory_id
     or new.chunk_id is distinct from old.chunk_id
     or new.rendition_id is distinct from old.rendition_id
     or new.reviewer_id is distinct from old.reviewer_id
     or new.review_round is distinct from old.review_round then
    raise exception 'assignment identity is immutable' using errcode = '55000';
  end if;

  if old.status in ('submitted', 'problem')
     and new.status is distinct from old.status then
    raise exception 'submitted and problem assignments are terminal' using errcode = '55000';
  end if;

  if old.status = 'queued' and new.status not in ('queued', 'leased', 'expired', 'reassigned') then
    raise exception 'invalid assignment transition' using errcode = '23514';
  elsif old.status = 'leased' and new.status not in ('leased', 'draft', 'submitted', 'problem', 'expired', 'reassigned') then
    raise exception 'invalid assignment transition' using errcode = '23514';
  elsif old.status = 'draft' and new.status not in ('draft', 'submitted', 'problem', 'expired', 'reassigned') then
    raise exception 'invalid assignment transition' using errcode = '23514';
  elsif old.status in ('expired', 'reassigned') and new.status is distinct from old.status then
    raise exception 'expired and reassigned assignments are terminal' using errcode = '55000';
  end if;

  return new;
end;
$$;

create or replace function public.validate_review_submission()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  assignment_row public.review_assignments%rowtype;
  expected_total integer;
begin
  perform 1
  from public.video_chunks
  where id = new.chunk_id and factory_id = new.factory_id
  for update;

  select *
  into assignment_row
  from public.review_assignments
  where id = new.assignment_id
  for update;

  if not found
     or assignment_row.factory_id <> new.factory_id
     or assignment_row.chunk_id <> new.chunk_id
     or assignment_row.review_round <> new.review_round
     or assignment_row.reviewer_id <> new.reviewer_id
     or assignment_row.rendition_id <> new.rendition_id
     or assignment_row.status not in ('leased', 'draft')
     or assignment_row.lease_expires_at is null
     or assignment_row.lease_expires_at <= now() then
    raise exception 'assignment is not submittable' using errcode = '23514';
  end if;

  if not exists (
    select 1
    from public.factory_memberships fm
    join public.profiles p on p.id = fm.user_id
    where fm.factory_id = new.factory_id
      and fm.user_id = new.reviewer_id
      and fm.role = 'reviewer'
      and fm.status = 'active'
      and p.status = 'active'
  ) then
    raise exception 'reviewer is not active' using errcode = '23514';
  end if;

  if new.source_sha256 <> (
    select vc.source_sha256 from public.video_chunks vc where vc.id = new.chunk_id
  ) then
    raise exception 'submission source hash does not match chunk' using errcode = '23514';
  end if;

  if (select count(*) from public.review_submissions rs
      where rs.chunk_id = new.chunk_id and rs.review_round = new.review_round) >= 3 then
    raise exception 'review round already holds three submissions' using errcode = '23514';
  end if;

  if new.result_type = 'counted' then
    select count(*)::integer
    into expected_total
    from public.review_actions tally
    where tally.assignment_id = new.assignment_id
      and tally.reviewer_id = new.reviewer_id
      and tally.action_type = 'tally'
      and not exists (
        select 1
        from public.review_actions undo
        where undo.assignment_id = new.assignment_id
          and undo.reviewer_id = new.reviewer_id
          and undo.action_type = 'undo'
          and undo.undoes_action_id = tally.id
      );

    if new.total_count <> expected_total then
      raise exception 'submission total does not match immutable tally actions' using errcode = '23514';
    end if;
  end if;

  new.submitted_at = now();
  return new;
end;
$$;

create or replace function public.validate_consensus_run()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  submission_count integer;
  counted_count integer;
  matching_count integer;
  problem_count integer;
  event_count integer;
  alignment_tolerance_ms bigint;
begin
  select count(*),
         count(*) filter (where result_type = 'counted'),
         count(*) filter (where result_type = 'counted' and total_count = new.resolved_total),
         count(*) filter (where result_type = 'problem')
  into submission_count, counted_count, matching_count, problem_count
  from public.review_submissions
  where chunk_id = new.chunk_id and review_round = new.review_round;

  if submission_count <> 3 then
    raise exception 'consensus requires exactly three submissions in one round' using errcode = '23514';
  end if;

  if new.status = 'resolved' then
    if counted_count <> 3 or matching_count <> new.support_count then
      raise exception 'resolved consensus does not match 2-of-3 human submissions' using errcode = '23514';
    end if;

    begin
      alignment_tolerance_ms = (new.resolver_parameters ->> 'alignment_tolerance_ms')::bigint;
    exception when others then
      alignment_tolerance_ms = null;
    end;
    if alignment_tolerance_ms is null or alignment_tolerance_ms <= 0 then
      raise exception 'resolved consensus requires alignment_tolerance_ms' using errcode = '23514';
    end if;

    select count(*) into event_count
    from public.consensus_events ce
    where ce.consensus_run_id = new.id;
    if event_count <> new.resolved_total then
      raise exception 'consensus event count does not match resolved total' using errcode = '23514';
    end if;
  elsif new.status = 'no_majority' and exists (
    select 1
    from public.review_submissions
    where chunk_id = new.chunk_id
      and review_round = new.review_round
      and result_type = 'counted'
    group by total_count
    having count(*) >= 2
  ) then
    raise exception 'no-majority run contains a human majority' using errcode = '23514';
  elsif new.status = 'problem' and problem_count = 0 then
    raise exception 'problem run requires a problem submission' using errcode = '23514';
  end if;

  return new;
end;
$$;

create or replace function public.validate_consensus_event()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  event_id uuid;
  source_count integer;
  distinct_submission_count integer;
  invalid_source_count integer;
  event_row public.consensus_events%rowtype;
  run_row public.consensus_runs%rowtype;
  chunk_row public.video_chunks%rowtype;
  alignment_tolerance_ms bigint;
begin
  if tg_table_name = 'consensus_events' then
    event_id = new.id;
  else
    event_id = new.consensus_event_id;
  end if;

  select * into event_row from public.consensus_events where id = event_id;
  if not found then
    return new;
  end if;

  select * into run_row from public.consensus_runs where id = event_row.consensus_run_id;
  if run_row.status <> 'resolved' then
    raise exception 'consensus events require a resolved run' using errcode = '23514';
  end if;

  select * into chunk_row from public.video_chunks where id = event_row.chunk_id;
  if event_row.source_time_ms < chunk_row.source_start_ms
     or event_row.source_time_ms >= chunk_row.source_end_ms then
    raise exception 'consensus event is outside the canonical chunk interval' using errcode = '23514';
  end if;

  begin
    alignment_tolerance_ms = (run_row.resolver_parameters ->> 'alignment_tolerance_ms')::bigint;
  exception when others then
    alignment_tolerance_ms = null;
  end;
  if alignment_tolerance_ms is null or alignment_tolerance_ms <= 0 then
    raise exception 'consensus event requires alignment_tolerance_ms' using errcode = '23514';
  end if;

  select count(*),
         count(distinct ces.submission_id),
         count(*) filter (
           where rs.chunk_id <> event_row.chunk_id
              or rs.review_round <> event_row.review_round
              or rs.result_type <> 'counted'
              or rs.total_count is distinct from run_row.resolved_total
              or ra.action_type <> 'tally'
              or abs(ra.source_time_ms - event_row.source_time_ms) > alignment_tolerance_ms
         )
  into source_count, distinct_submission_count, invalid_source_count
  from public.consensus_event_sources ces
  join public.review_submissions rs on rs.id = ces.submission_id
  join public.review_actions ra on ra.id = ces.review_action_id
  where ces.consensus_event_id = event_id;

  if source_count <> event_row.support_count
     or distinct_submission_count <> event_row.support_count
     or invalid_source_count <> 0 then
    raise exception 'consensus event lacks matching human source lineage' using errcode = '23514';
  end if;

  return new;
end;
$$;

create or replace function public.validate_finalization_cardinality()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  finalization_id uuid;
  expected_count integer;
  published_count integer;
begin
  if tg_table_name = 'human_finalizations' then
    finalization_id = new.id;
  else
    finalization_id = new.finalization_id;
  end if;

  select cr.resolved_total, count(rhce.id)::integer
  into expected_count, published_count
  from public.human_finalizations hf
  join public.consensus_runs cr on cr.id = hf.consensus_run_id
  left join public.resolved_human_count_events rhce
    on rhce.finalization_id = hf.id
   and rhce.publication_status = 'published'
  where hf.id = finalization_id
  group by cr.resolved_total;

  if expected_count is null or published_count <> expected_count then
    raise exception 'published event count does not match finalized consensus' using errcode = '23514';
  end if;
  return new;
end;
$$;

create or replace function public.validate_media_rendition_buckets()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not exists (
    select 1 from public.media_objects mo
    where mo.id = new.source_media_object_id
      and mo.factory_id = new.factory_id
      and mo.bucket_id = 'factory-originals'
  ) then
    raise exception 'rendition source must be in factory-originals' using errcode = '23514';
  end if;
  if not exists (
    select 1 from public.media_objects mo
    where mo.id = new.rendition_media_object_id
      and mo.factory_id = new.factory_id
      and mo.bucket_id = 'review-renditions'
  ) then
    raise exception 'review media must be in review-renditions' using errcode = '23514';
  end if;
  return new;
end;
$$;

create or replace function public.protect_media_object_identity()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.factory_id is distinct from old.factory_id
     or new.station_id is distinct from old.station_id
     or new.bucket_id is distinct from old.bucket_id
     or new.object_path is distinct from old.object_path
     or new.object_sha256 is distinct from old.object_sha256
     or new.source_sha256 is distinct from old.source_sha256 then
    raise exception 'media object identity is immutable' using errcode = '55000';
  end if;
  return new;
end;
$$;

create trigger media_objects_protect_identity
before update on public.media_objects
for each row execute function public.protect_media_object_identity();

create trigger media_renditions_validate_buckets
before insert or update of factory_id, source_media_object_id, rendition_media_object_id
on public.media_renditions
for each row execute function public.validate_media_rendition_buckets();

create constraint trigger human_finalizations_cardinality
after insert on public.human_finalizations
deferrable initially deferred
for each row execute function public.validate_finalization_cardinality();

create constraint trigger resolved_human_events_cardinality
after insert on public.resolved_human_count_events
deferrable initially deferred
for each row execute function public.validate_finalization_cardinality();

create unique index consensus_events_unique_source_time_idx
on public.consensus_events (consensus_run_id, source_time_ms);

drop policy factories_read_owner_or_ops on public.factories;
create policy factories_read_owner_or_ops
on public.factories for select
to authenticated
using (
  exists (
    select 1
    from public.factory_memberships fm
    join public.profiles p on p.id = fm.user_id
    where fm.factory_id = factories.id
      and fm.user_id = (select auth.uid())
      and fm.status = 'active'
      and fm.role in ('owner', 'ops')
      and p.status = 'active'
  )
);

drop policy stations_read_owner_or_ops on public.stations;
create policy stations_read_owner_or_ops
on public.stations for select
to authenticated
using (
  exists (
    select 1
    from public.factory_memberships fm
    join public.profiles p on p.id = fm.user_id
    where fm.factory_id = stations.factory_id
      and fm.user_id = (select auth.uid())
      and fm.status = 'active'
      and fm.role in ('owner', 'ops')
      and p.status = 'active'
  )
);

drop policy resolved_human_events_read_owner on public.resolved_human_count_events;
create policy resolved_human_events_read_owner
on public.resolved_human_count_events for select
to authenticated
using (
  publication_status = 'published'
  and exists (
    select 1
    from public.factory_memberships fm
    join public.profiles p on p.id = fm.user_id
    where fm.factory_id = resolved_human_count_events.factory_id
      and fm.user_id = (select auth.uid())
      and fm.status = 'active'
      and fm.role = 'owner'
      and p.status = 'active'
  )
);

revoke all on function public.validate_finalization_cardinality()
from public, anon, authenticated;
revoke all on function public.validate_media_rendition_buckets()
from public, anon, authenticated;
revoke all on function public.protect_media_object_identity()
from public, anon, authenticated;
grant execute on function public.validate_finalization_cardinality() to service_role;
grant execute on function public.validate_media_rendition_buckets() to service_role;
grant execute on function public.protect_media_object_identity() to service_role;
