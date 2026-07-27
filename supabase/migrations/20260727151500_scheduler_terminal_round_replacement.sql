-- Expired assignments are immutable terminal records. Replace an incomplete
-- latest round as a unit once three qualified reviewers are available.

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
  eligible_count integer;
  next_round integer;
  scheduled_count integer := 0;
  expired_count integer := 0;
  replacement_round_count integer := 0;
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
    select count(*)::integer into eligible_count
    from public.reviewer_lifecycles lifecycle
    join public.profiles profile
      on profile.id = lifecycle.user_id and profile.status = 'active'
    join public.factory_memberships membership
      on membership.user_id = lifecycle.user_id
     and membership.factory_id = lifecycle.factory_id
     and membership.role = 'reviewer'
     and membership.status = 'active'
    where lifecycle.factory_id = chunk_row.factory_id
      and lifecycle.state = 'active'
      and (
        lifecycle.is_test_account
        or exists (
          select 1 from public.reviewer_device_registrations device
          where device.user_id = lifecycle.user_id and device.status = 'active'
        )
      );
    continue when eligible_count < 3;

    for slot in 1..3 loop
      reviewer_id := public.service_pick_reviewer(chunk_row.factory_id, chunk_row.id, 1);
      if reviewer_id is null then
        raise exception 'eligible reviewer count disagrees with scheduler selection'
          using errcode = '55000';
      end if;
      insert into public.review_assignments (
        factory_id, chunk_id, rendition_id, reviewer_id, review_round, status
      ) values (
        chunk_row.factory_id, chunk_row.id, chunk_row.review_rendition_id,
        reviewer_id, 1, 'queued'
      );
      scheduled_count := scheduled_count + 1;
    end loop;
    update public.video_chunks set state = 'assigned', updated_at = now()
    where id = chunk_row.id;
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
    select count(*)::integer into eligible_count
    from public.reviewer_lifecycles lifecycle
    join public.profiles profile
      on profile.id = lifecycle.user_id and profile.status = 'active'
    join public.factory_memberships membership
      on membership.user_id = lifecycle.user_id
     and membership.factory_id = lifecycle.factory_id
     and membership.role = 'reviewer'
     and membership.status = 'active'
    where lifecycle.factory_id = round_row.factory_id
      and lifecycle.state = 'active'
      and (
        lifecycle.is_test_account
        or exists (
          select 1 from public.reviewer_device_registrations device
          where device.user_id = lifecycle.user_id and device.status = 'active'
        )
      );
    continue when eligible_count < 3;

    next_round := round_row.review_round + 1;
    update public.review_assignments
    set status = 'reassigned', updated_at = now()
    where chunk_id = round_row.chunk_id
      and review_round = round_row.review_round
      and status in ('queued', 'leased', 'draft');

    for slot in 1..3 loop
      reviewer_id := public.service_pick_reviewer(
        round_row.factory_id, round_row.chunk_id, next_round
      );
      if reviewer_id is null then
        raise exception 'replacement round could not select three reviewers'
          using errcode = '55000';
      end if;
      insert into public.review_assignments (
        factory_id, chunk_id, rendition_id, reviewer_id, review_round, status
      )
      select round_row.factory_id, round_row.chunk_id, chunk.review_rendition_id,
             reviewer_id, next_round, 'queued'
      from public.video_chunks chunk where chunk.id = round_row.chunk_id;
    end loop;

    insert into public.audit_log (
      factory_id, actor_type, action, target_type, target_id,
      correlation_id, metadata
    ) values (
      round_row.factory_id, 'system', 'review.round.replaced',
      'video_chunk', round_row.chunk_id, gen_random_uuid(),
      jsonb_build_object(
        'abandoned_review_round', round_row.review_round,
        'replacement_review_round', next_round
      )
    );
    replacement_round_count := replacement_round_count + 1;
    update public.video_chunks set state = 'assigned', updated_at = now()
    where id = round_row.chunk_id;
  end loop;

  resolved_count := public.service_resolve_ready_rounds();
  return jsonb_build_object(
    'scheduled', scheduled_count,
    'expired', expired_count,
    'replacementRounds', replacement_round_count,
    'resolved', resolved_count,
    'ranAt', now()
  );
end;
$$;

revoke all on function public.service_maintain_review_queue()
  from public, anon, authenticated;
