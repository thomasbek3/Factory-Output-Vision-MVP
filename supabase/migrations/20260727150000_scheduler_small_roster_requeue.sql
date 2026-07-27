-- Keep a three-person roster productive after a lease timeout without
-- resurrecting historical rounds or bypassing the review-time gate.

create or replace function public.service_maintain_review_queue()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  chunk_row public.video_chunks%rowtype;
  round_row record;
  reviewer_id uuid;
  requeue_assignment_id uuid;
  scheduled_count integer := 0;
  expired_count integer := 0;
  requeued_count integer := 0;
  replacement_count integer := 0;
  slot integer;
  resolved_count integer;
begin
  update public.review_assignments
  set status = 'expired', updated_at = now()
  where status in ('leased', 'draft')
    and lease_expires_at < now() - interval '5 minutes';
  get diagnostics expired_count = row_count;

  for chunk_row in
    select chunk.*
    from public.video_chunks chunk
    where chunk.state = 'ready'
      and chunk.assignment_eligible
      and chunk.source_set_role = 'production'
      and chunk.source_end_at <= now() - interval '60 minutes'
      and not exists (
        select 1 from public.review_assignments assignment where assignment.chunk_id = chunk.id
      )
    order by chunk.source_end_at
    limit 50
    for update skip locked
  loop
    for slot in 1..3 loop
      reviewer_id := public.service_pick_reviewer(chunk_row.factory_id, chunk_row.id, 1);
      exit when reviewer_id is null;
      insert into public.review_assignments (
        factory_id, chunk_id, rendition_id, reviewer_id, review_round, status
      ) values (
        chunk_row.factory_id, chunk_row.id, chunk_row.review_rendition_id,
        reviewer_id, 1, 'queued'
      );
      scheduled_count := scheduled_count + 1;
    end loop;
    if (
      select count(*) from public.review_assignments
      where chunk_id = chunk_row.id and review_round = 1
    ) = 3 then
      update public.video_chunks set state = 'assigned', updated_at = now()
      where id = chunk_row.id;
    end if;
  end loop;

  for round_row in
    select assignment.factory_id, assignment.chunk_id, assignment.review_round,
           count(*) filter (
             where assignment.status not in ('expired', 'reassigned')
           ) as active_count
    from public.review_assignments assignment
    left join public.consensus_runs run
      on run.chunk_id = assignment.chunk_id and run.review_round = assignment.review_round
    where run.id is null
      and assignment.review_round = (
        select max(latest.review_round)
        from public.review_assignments latest
        where latest.chunk_id = assignment.chunk_id
      )
    group by assignment.factory_id, assignment.chunk_id, assignment.review_round
    having count(*) filter (
      where assignment.status not in ('expired', 'reassigned')
    ) < 3
    order by min(assignment.assigned_at)
  loop
    for slot in (round_row.active_count::integer + 1)..3 loop
      requeue_assignment_id := null;
      reviewer_id := null;

      select assignment.id, assignment.reviewer_id
      into requeue_assignment_id, reviewer_id
      from public.review_assignments assignment
      join public.reviewer_lifecycles lifecycle
        on lifecycle.user_id = assignment.reviewer_id
       and lifecycle.state = 'active'
      join public.profiles profile
        on profile.id = assignment.reviewer_id and profile.status = 'active'
      join public.factory_memberships membership
        on membership.user_id = assignment.reviewer_id
       and membership.factory_id = assignment.factory_id
       and membership.role = 'reviewer'
       and membership.status = 'active'
      where assignment.chunk_id = round_row.chunk_id
        and assignment.review_round = round_row.review_round
        and assignment.status = 'expired'
        and not exists (
          select 1 from public.review_submissions submission
          where submission.assignment_id = assignment.id
        )
        and (
          lifecycle.is_test_account
          or exists (
            select 1 from public.reviewer_device_registrations device
            where device.user_id = lifecycle.user_id and device.status = 'active'
          )
        )
      order by assignment.updated_at
      limit 1
      for update of assignment skip locked;

      if requeue_assignment_id is not null then
        update public.review_assignments
        set status = 'queued',
            lease_token_hash = null,
            lease_expires_at = null,
            leased_at = null,
            updated_at = now()
        where id = requeue_assignment_id;
        requeued_count := requeued_count + 1;
        continue;
      end if;

      reviewer_id := public.service_pick_reviewer(
        round_row.factory_id, round_row.chunk_id, round_row.review_round
      );
      exit when reviewer_id is null;
      insert into public.review_assignments (
        factory_id, chunk_id, rendition_id, reviewer_id, review_round, status
      )
      select round_row.factory_id, round_row.chunk_id, chunk.review_rendition_id,
             reviewer_id, round_row.review_round, 'queued'
      from public.video_chunks chunk where chunk.id = round_row.chunk_id;
      replacement_count := replacement_count + 1;
    end loop;
  end loop;

  resolved_count := public.service_resolve_ready_rounds();
  return jsonb_build_object(
    'scheduled', scheduled_count,
    'expired', expired_count,
    'requeued', requeued_count,
    'replacements', replacement_count,
    'resolved', resolved_count,
    'ranAt', now()
  );
end;
$$;

revoke all on function public.service_maintain_review_queue()
  from public, anon, authenticated;
