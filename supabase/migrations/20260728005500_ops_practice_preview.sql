-- Let authenticated ops users inspect the latest non-training practice chunk.

create or replace function public.ops_latest_practice_preview()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  result jsonb;
begin
  select jsonb_build_object(
    'chunkId', chunk.id,
    'stationId', station.id,
    'stationName', station.alias,
    'factoryTimezone', factory.timezone,
    'startIso', chunk.source_start_at,
    'endIso', chunk.source_end_at,
    'sourceStartMs', chunk.source_start_ms,
    'sourceEndMs', chunk.source_end_ms,
    'renditionSourceStartMs', rendition.padded_start_ms,
    'renditionSourceEndMs', rendition.padded_end_ms,
    'sourceSha256', chunk.source_sha256,
    'renditionId', rendition.id,
    'mediaBucket', media.bucket_id,
    'mediaPath', media.object_path
  )
  into result
  from public.video_chunks chunk
  join public.factories factory
    on factory.id = chunk.factory_id
   and factory.status = 'active'
  join public.stations station
    on station.id = chunk.station_id
   and station.factory_id = chunk.factory_id
  join public.media_renditions rendition
    on rendition.id = chunk.review_rendition_id
   and rendition.factory_id = chunk.factory_id
  join public.media_objects media
    on media.id = rendition.rendition_media_object_id
   and media.factory_id = chunk.factory_id
  where public.actor_is_ops(chunk.factory_id)
    and chunk.source_set_role = 'practice'
    and not chunk.assignment_eligible
    and chunk.state = 'ready'
    and rendition.mapping_status = 'verified'
    and media.status = 'verified'
  order by chunk.source_start_at desc, chunk.created_at desc
  limit 1;

  return result;
end;
$$;

revoke all on function public.ops_latest_practice_preview() from public;
revoke execute on function public.ops_latest_practice_preview() from anon;
grant execute on function public.ops_latest_practice_preview()
  to authenticated, service_role;
