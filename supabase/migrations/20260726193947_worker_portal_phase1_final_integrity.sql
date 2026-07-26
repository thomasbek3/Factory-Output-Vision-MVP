-- Final integrity closure after corrective Opus review.

drop trigger review_assignments_chunk_gate on public.review_assignments;
create trigger review_assignments_chunk_gate
before insert or update of factory_id, chunk_id on public.review_assignments
for each row execute function public.require_reviewable_chunk();

create unique index consensus_event_sources_unique_action_idx
on public.consensus_event_sources (review_action_id);
