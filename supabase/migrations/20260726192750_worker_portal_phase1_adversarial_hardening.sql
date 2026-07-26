-- Hardening required by the final Opus 5 adversarial checkpoint.

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
    if counted_count < new.support_count or matching_count <> new.support_count then
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
              or exists (
                select 1
                from public.review_actions undo
                where undo.assignment_id = ra.assignment_id
                  and undo.action_type = 'undo'
                  and undo.undoes_action_id = ra.id
              )
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

create or replace function public.guard_chunk_state_transition()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.state = 'published' and new.published_at is null then
    raise exception 'published chunks require published_at' using errcode = '23514';
  end if;
  if old.published_at is not null and new.published_at is distinct from old.published_at then
    raise exception 'chunk published_at is immutable once set' using errcode = '55000';
  end if;

  if new.state is distinct from old.state and not (
    (old.state = 'ingesting' and new.state in ('transcoding', 'quarantined', 'deleted'))
    or (old.state = 'transcoding' and new.state in ('ready', 'quarantined', 'deleted'))
    or (old.state = 'ready' and new.state in ('assigned', 'quarantined', 'retained', 'deleted'))
    or (old.state = 'assigned' and new.state in ('ready', 'resolving', 'quarantined'))
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

alter table public.video_chunks
add constraint video_chunks_published_at_required
check (state <> 'published' or published_at is not null);

create or replace function public.require_reviewable_chunk()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  target_chunk_id uuid;
  target_factory_id uuid;
begin
  if tg_table_name = 'review_assignments' then
    target_chunk_id = new.chunk_id;
    target_factory_id = new.factory_id;
  else
    select ra.chunk_id, ra.factory_id
    into target_chunk_id, target_factory_id
    from public.review_assignments ra
    where ra.id = new.assignment_id;
  end if;

  if not exists (
    select 1
    from public.video_chunks vc
    where vc.id = target_chunk_id
      and vc.factory_id = target_factory_id
      and vc.assignment_eligible = true
      and vc.state in ('ready', 'assigned')
  ) then
    raise exception 'chunk is not reviewable' using errcode = '23514';
  end if;

  return new;
end;
$$;

create trigger video_chunks_guard_state_transition
before update of state, published_at on public.video_chunks
for each row execute function public.guard_chunk_state_transition();

create trigger review_assignments_chunk_gate
before insert or update of factory_id, chunk_id, status on public.review_assignments
for each row execute function public.require_reviewable_chunk();

create trigger review_actions_chunk_gate
before insert on public.review_actions
for each row execute function public.require_reviewable_chunk();

create trigger review_submissions_chunk_gate
before insert on public.review_submissions
for each row execute function public.require_reviewable_chunk();

create or replace function public.validate_finalization_cardinality()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  finalization_key uuid;
  expected_count integer;
  consensus_event_count integer;
  published_count integer;
begin
  if tg_table_name = 'human_finalizations' then
    finalization_key = new.id;
  else
    finalization_key = new.finalization_id;
  end if;

  select cr.resolved_total,
         count(distinct ce.id)::integer,
         count(distinct rhce.id)::integer
  into expected_count, consensus_event_count, published_count
  from public.human_finalizations hf
  join public.consensus_runs cr on cr.id = hf.consensus_run_id
  left join public.consensus_events ce on ce.consensus_run_id = cr.id
  left join public.resolved_human_count_events rhce
    on rhce.finalization_id = hf.id
   and rhce.consensus_event_id = ce.id
   and rhce.publication_status = 'published'
  where hf.id = finalization_key
  group by cr.resolved_total;

  if expected_count is null
     or consensus_event_count <> expected_count
     or published_count <> expected_count then
    raise exception 'published event count does not match finalized consensus' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger review_actions_reject_truncate
before truncate on public.review_actions
for each statement execute function public.reject_append_only_change();
create trigger review_submissions_reject_truncate
before truncate on public.review_submissions
for each statement execute function public.reject_append_only_change();
create trigger consensus_runs_reject_truncate
before truncate on public.consensus_runs
for each statement execute function public.reject_append_only_change();
create trigger consensus_events_reject_truncate
before truncate on public.consensus_events
for each statement execute function public.reject_append_only_change();
create trigger consensus_event_sources_reject_truncate
before truncate on public.consensus_event_sources
for each statement execute function public.reject_append_only_change();
create trigger human_finalizations_reject_truncate
before truncate on public.human_finalizations
for each statement execute function public.reject_append_only_change();
create trigger resolved_human_count_events_reject_truncate
before truncate on public.resolved_human_count_events
for each statement execute function public.reject_append_only_change();
create trigger internal_review_cases_reject_truncate
before truncate on public.internal_review_cases
for each statement execute function public.reject_append_only_change();
create trigger audit_log_reject_truncate
before truncate on public.audit_log
for each statement execute function public.reject_append_only_change();

revoke truncate on table
  public.review_actions,
  public.review_submissions,
  public.consensus_runs,
  public.consensus_events,
  public.consensus_event_sources,
  public.human_finalizations,
  public.resolved_human_count_events,
  public.internal_review_cases,
  public.audit_log
from service_role;

revoke all on function public.guard_chunk_state_transition()
from public, anon, authenticated;
revoke all on function public.require_reviewable_chunk()
from public, anon, authenticated;
grant execute on function public.guard_chunk_state_transition() to service_role;
grant execute on function public.require_reviewable_chunk() to service_role;
