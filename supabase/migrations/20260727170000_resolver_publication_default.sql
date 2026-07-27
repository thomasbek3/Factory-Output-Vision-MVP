-- The resolver inserts owner projections only after a validated human
-- finalization. Its omitted publication_status must satisfy the existing
-- fail-closed insert trigger.

alter table public.resolved_human_count_events
  alter column publication_status set default 'published';
