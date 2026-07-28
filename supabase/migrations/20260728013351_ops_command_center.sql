-- Give authenticated ops users one bounded, read-only projection over queue,
-- human-label lineage, factory health, and blind human-vs-AI evaluation.

create or replace function public.ops_command_center()
returns jsonb
language plpgsql
security definer
set search_path = public, private, pg_temp
as $$
declare
  result jsonb;
begin
  if not public.actor_is_ops(null) then
    raise exception 'ops access required' using errcode = '42501';
  end if;

  select jsonb_build_object(
    'summary', jsonb_build_object(
      'activeReviewers', (
        select count(*)
        from public.reviewer_lifecycles lifecycle
        where lifecycle.state = 'active'
          and public.actor_is_ops(lifecycle.factory_id)
      ),
      'submissions24h', (
        select count(*)
        from public.review_submissions submission
        where submission.submitted_at >= now() - interval '24 hours'
          and public.actor_is_ops(submission.factory_id)
      ),
      'openAssignments', (
        select count(*)
        from public.review_assignments assignment
        where assignment.status in ('queued', 'leased', 'draft')
          and public.actor_is_ops(assignment.factory_id)
      ),
      'oldestQueueMinutes', coalesce((
        select floor(extract(epoch from (now() - min(assignment.assigned_at))) / 60)::integer
        from public.review_assignments assignment
        where assignment.status in ('queued', 'leased', 'draft')
          and public.actor_is_ops(assignment.factory_id)
      ), 0),
      'openSupport', (
        select count(*)
        from public.reviewer_support_requests support
        where support.status in ('open', 'acknowledged')
          and public.actor_is_ops(support.factory_id)
      ),
      'readyForResolution', (
        select count(*)
        from (
          select submission.factory_id, submission.chunk_id, submission.review_round
          from public.review_submissions submission
          where public.actor_is_ops(submission.factory_id)
          group by submission.factory_id, submission.chunk_id, submission.review_round
          having count(*) = 3
        ) complete_round
        where not exists (
          select 1
          from public.consensus_runs run
          where run.chunk_id = complete_round.chunk_id
            and run.review_round = complete_round.review_round
        )
      ),
      'resolvedChunks', (
        select count(*)
        from public.human_finalizations finalization
        where public.actor_is_ops(finalization.factory_id)
      ),
      'aiRuns', (
        select count(*)
        from private.ai_runs ai_run
        where public.actor_is_ops(ai_run.factory_id)
      ),
      'aiComparisons', (
        select count(*)
        from private.human_ai_comparisons comparison
        join private.ai_runs ai_run on ai_run.id = comparison.ai_run_id
        where public.actor_is_ops(ai_run.factory_id)
      )
    ),
    'queue', coalesce((
      select jsonb_agg(queue_row.payload order by queue_row.oldest_at, queue_row.chunk_id)
      from (
        select
          chunk.id as chunk_id,
          min(assignment.assigned_at) as oldest_at,
          jsonb_build_object(
            'chunkId', chunk.id,
            'factoryId', factory.id,
            'factoryName', factory.name,
            'factoryTimezone', factory.timezone,
            'stationId', station.id,
            'stationAlias', station.alias,
            'sourceStartAt', chunk.source_start_at,
            'sourceEndAt', chunk.source_end_at,
            'chunkState', chunk.state,
            'reviewRound', assignment.review_round,
            'ageMinutes', floor(
              extract(epoch from (now() - min(assignment.assigned_at))) / 60
            )::integer,
            'requiredReviews', 3,
            'submittedReviews', count(*) filter (
              where assignment.status in ('submitted', 'problem')
            ),
            'openReviews', count(*) filter (
              where assignment.status in ('queued', 'leased', 'draft')
            ),
            'leasedReviews', count(*) filter (
              where assignment.status in ('leased', 'draft')
            ),
            'reviewers', coalesce(jsonb_agg(jsonb_build_object(
              'reviewerId', assignment.reviewer_id,
              'reviewerName', profile.display_name,
              'status', assignment.status,
              'assignedAt', assignment.assigned_at,
              'submittedAt', assignment.submitted_at
            ) order by profile.display_name) filter (
              where assignment.status in ('queued', 'leased', 'draft', 'submitted', 'problem')
            ), '[]'::jsonb)
          ) as payload
        from public.video_chunks chunk
        join public.factories factory on factory.id = chunk.factory_id
        join public.stations station on station.id = chunk.station_id
        join public.review_assignments assignment on assignment.chunk_id = chunk.id
        join public.profiles profile on profile.id = assignment.reviewer_id
        where public.actor_is_ops(chunk.factory_id)
          and assignment.review_round = (
            select max(current_assignment.review_round)
            from public.review_assignments current_assignment
            where current_assignment.chunk_id = chunk.id
          )
        group by
          chunk.id, factory.id, factory.name, factory.timezone,
          station.id, station.alias, assignment.review_round
        having count(*) filter (
          where assignment.status in ('queued', 'leased', 'draft')
        ) > 0
        order by oldest_at
        limit 50
      ) queue_row
    ), '[]'::jsonb),
    'labels', coalesce((
      select jsonb_agg(label_row.payload order by label_row.activity_at desc)
      from (
        select
          round_row.chunk_id,
          greatest(
            coalesce(max(submission.submitted_at), '-infinity'::timestamptz),
            max(assignment.updated_at)
          ) as activity_at,
          jsonb_build_object(
            'chunkId', chunk.id,
            'factoryId', factory.id,
            'factoryName', factory.name,
            'factoryTimezone', factory.timezone,
            'stationId', station.id,
            'stationAlias', station.alias,
            'sourceStartAt', chunk.source_start_at,
            'sourceEndAt', chunk.source_end_at,
            'chunkState', chunk.state,
            'sourceSha256', chunk.source_sha256,
            'reviewRound', round_row.review_round,
            'submissionCount', count(distinct submission.id),
            'problemCount', count(distinct submission.id) filter (
              where submission.result_type = 'problem'
            ),
            'humanTotals', coalesce(jsonb_agg(distinct jsonb_build_object(
              'submissionId', submission.id,
              'reviewerId', submission.reviewer_id,
              'reviewerName', profile.display_name,
              'resultType', submission.result_type,
              'totalCount', submission.total_count,
              'problemCode', submission.problem_code,
              'submittedAt', submission.submitted_at
            )) filter (where submission.id is not null), '[]'::jsonb),
            'consensusStatus', run.status,
            'resolvedTotal', run.resolved_total,
            'supportCount', run.support_count,
            'consensusEventCount', (
              select count(*)
              from public.consensus_events event
              where event.consensus_run_id = run.id
            ),
            'humanFinalAt', finalization.human_final_at,
            'publicationCount', (
              select count(*)
              from public.resolved_human_count_events resolved_event
              where resolved_event.finalization_id = finalization.id
                and resolved_event.publication_status = 'published'
            ),
            'exceptionType', latest_case.event_type,
            'exceptionReason', latest_case.reason_code,
            'aiRunId', ai_run.id,
            'aiStatus', case
              when ai_run.id is null then 'not_run'
              when ai_run.completed_at is null then 'running'
              when comparison.id is null then 'awaiting_comparison'
              else 'compared'
            end,
            'aiCodeVersion', ai_run.code_version,
            'aiEventCount', (
              select count(*)
              from private.ai_events ai_event
              where ai_event.ai_run_id = ai_run.id
            ),
            'comparisonMetrics', comparison.metrics,
            'comparisonCreatedAt', comparison.created_at
          ) as payload
        from (
          select distinct assignment.chunk_id, assignment.review_round
          from public.review_assignments assignment
          where public.actor_is_ops(assignment.factory_id)
        ) round_row
        join public.video_chunks chunk on chunk.id = round_row.chunk_id
        join public.factories factory on factory.id = chunk.factory_id
        join public.stations station on station.id = chunk.station_id
        join public.review_assignments assignment
          on assignment.chunk_id = round_row.chunk_id
         and assignment.review_round = round_row.review_round
        left join public.review_submissions submission
          on submission.assignment_id = assignment.id
        left join public.profiles profile on profile.id = submission.reviewer_id
        left join lateral (
          select candidate.*
          from public.consensus_runs candidate
          where candidate.chunk_id = round_row.chunk_id
            and candidate.review_round = round_row.review_round
          order by candidate.created_at desc
          limit 1
        ) run on true
        left join public.human_finalizations finalization
          on finalization.consensus_run_id = run.id
        left join lateral (
          select review_case.*
          from public.internal_review_cases review_case
          where review_case.chunk_id = round_row.chunk_id
            and review_case.review_round = round_row.review_round
          order by review_case.sequence desc
          limit 1
        ) latest_case on true
        left join lateral (
          select candidate.*
          from private.ai_runs candidate
          where candidate.chunk_id = round_row.chunk_id
          order by candidate.created_at desc
          limit 1
        ) ai_run on true
        left join lateral (
          select candidate.*
          from private.human_ai_comparisons candidate
          where candidate.ai_run_id = ai_run.id
            and candidate.consensus_run_id = run.id
            and candidate.finalization_id = finalization.id
          order by candidate.created_at desc
          limit 1
        ) comparison on true
        group by
          round_row.chunk_id, round_row.review_round,
          chunk.id, factory.id, factory.name, factory.timezone,
          station.id, station.alias, run.id, run.status, run.resolved_total,
          run.support_count, finalization.id, finalization.human_final_at,
          latest_case.event_type, latest_case.reason_code,
          ai_run.id, ai_run.completed_at, ai_run.code_version,
          comparison.id, comparison.metrics, comparison.created_at
        order by activity_at desc
        limit 50
      ) label_row
    ), '[]'::jsonb),
    'factories', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', factory.id,
        'name', factory.name,
        'timezone', factory.timezone,
        'status', factory.status,
        'isTest', factory.is_test,
        'retentionDays', factory.retention_days,
        'stations', coalesce((
          select jsonb_agg(jsonb_build_object(
            'id', station.id,
            'alias', station.alias,
            'status', station.status,
            'chunkCount', (
              select count(*) from public.video_chunks chunk
              where chunk.station_id = station.id
            ),
            'latestFootageAt', (
              select max(chunk.source_end_at) from public.video_chunks chunk
              where chunk.station_id = station.id
            ),
            'openAssignments', (
              select count(*)
              from public.review_assignments assignment
              join public.video_chunks chunk on chunk.id = assignment.chunk_id
              where chunk.station_id = station.id
                and assignment.status in ('queued', 'leased', 'draft')
            )
          ) order by station.alias)
          from public.stations station
          where station.factory_id = factory.id
        ), '[]'::jsonb)
      ) order by factory.name)
      from public.factories factory
      where public.actor_is_ops(factory.id)
    ), '[]'::jsonb)
  ) into result;

  return result;
end;
$$;

revoke all on function public.ops_command_center() from public, anon;
grant execute on function public.ops_command_center() to authenticated;
