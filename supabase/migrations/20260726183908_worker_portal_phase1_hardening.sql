-- Follow-up hardening after the first live migration and Opus checkpoint.

create policy media_objects_server_only
on public.media_objects as restrictive for all to anon, authenticated
using (false) with check (false);
create policy media_renditions_server_only
on public.media_renditions as restrictive for all to anon, authenticated
using (false) with check (false);
create policy video_chunks_server_only
on public.video_chunks as restrictive for all to anon, authenticated
using (false) with check (false);
create policy consensus_runs_server_only
on public.consensus_runs as restrictive for all to anon, authenticated
using (false) with check (false);
create policy consensus_events_server_only
on public.consensus_events as restrictive for all to anon, authenticated
using (false) with check (false);
create policy consensus_event_sources_server_only
on public.consensus_event_sources as restrictive for all to anon, authenticated
using (false) with check (false);
create policy human_finalizations_server_only
on public.human_finalizations as restrictive for all to anon, authenticated
using (false) with check (false);
create policy internal_review_cases_server_only
on public.internal_review_cases as restrictive for all to anon, authenticated
using (false) with check (false);
create policy audit_log_server_only
on public.audit_log as restrictive for all to anon, authenticated
using (false) with check (false);

create policy reference_answers_server_only
on private.reference_answers as restrictive for all to anon, authenticated
using (false) with check (false);
create policy ai_runs_server_only
on private.ai_runs as restrictive for all to anon, authenticated
using (false) with check (false);
create policy ai_events_server_only
on private.ai_events as restrictive for all to anon, authenticated
using (false) with check (false);
create policy human_ai_comparisons_server_only
on private.human_ai_comparisons as restrictive for all to anon, authenticated
using (false) with check (false);

create or replace function public.validate_resolved_human_count_event()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.publication_status <> 'published' then
    raise exception 'owner projection rows must be published at insert' using errcode = '23514';
  end if;

  if not exists (
    select 1
    from public.human_finalizations hf
    join public.consensus_events ce
      on ce.consensus_run_id = hf.consensus_run_id
     and ce.chunk_id = hf.chunk_id
     and ce.factory_id = hf.factory_id
    where hf.id = new.finalization_id
      and ce.id = new.consensus_event_id
      and hf.factory_id = new.factory_id
      and hf.chunk_id = new.chunk_id
      and ce.source_time_ms = new.source_time_ms
  ) then
    raise exception 'owner projection does not match finalized human event' using errcode = '23514';
  end if;

  new.published_at = now();
  new.created_at = now();
  return new;
end;
$$;

revoke all on function public.validate_resolved_human_count_event()
from public, anon, authenticated;
grant execute on function public.validate_resolved_human_count_event()
to service_role;

create trigger resolved_human_count_events_validate
before insert on public.resolved_human_count_events
for each row execute function public.validate_resolved_human_count_event();

create index video_chunks_source_media_idx
  on public.video_chunks (source_media_object_id, factory_id);
create index video_chunks_rendition_idx
  on public.video_chunks (review_rendition_id, factory_id, source_media_object_id);
create index review_assignments_rendition_idx
  on public.review_assignments (rendition_id, factory_id);
create index review_actions_reviewer_idx
  on public.review_actions (reviewer_id);
create index review_submissions_rendition_idx
  on public.review_submissions (rendition_id, factory_id);
create index consensus_event_sources_action_idx
  on public.consensus_event_sources (review_action_id, assignment_id);
create index human_finalizations_factory_idx
  on public.human_finalizations (factory_id, human_final_at);
create index resolved_human_events_owner_idx
  on public.resolved_human_count_events (factory_id, published_at)
  where publication_status = 'published';
create index ai_runs_factory_chunk_idx
  on private.ai_runs (factory_id, chunk_id);
create index reference_answers_factory_chunk_idx
  on private.reference_answers (factory_id, chunk_id);
