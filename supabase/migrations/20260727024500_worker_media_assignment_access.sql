-- Reviewers may mint short-lived URLs only for their currently leased rendition.

drop policy if exists factory_vision_media_server_only on storage.objects;

create or replace function public.can_read_assignment_media(
  object_bucket text,
  object_name text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.media_objects media
    join public.media_renditions rendition
      on rendition.rendition_media_object_id = media.id
     and rendition.factory_id = media.factory_id
    join public.review_assignments assignment
      on assignment.rendition_id = rendition.id
     and assignment.factory_id = rendition.factory_id
    join public.factory_memberships membership
      on membership.factory_id = assignment.factory_id
     and membership.user_id = (select auth.uid())
     and membership.role = 'reviewer'
     and membership.status = 'active'
    join public.profiles profile
      on profile.id = (select auth.uid())
     and profile.status = 'active'
    where media.bucket_id = object_bucket
      and media.object_path = object_name
      and media.status = 'verified'
      and assignment.reviewer_id = (select auth.uid())
      and assignment.status in ('leased', 'draft')
      and assignment.lease_expires_at > now() - interval '5 minutes'
  );
$$;

revoke all on function public.can_read_assignment_media(text, text)
from public, anon;
grant execute on function public.can_read_assignment_media(text, text)
to authenticated;

create policy reviewer_read_active_assignment_media
on storage.objects
for select
to authenticated
using (
  bucket_id = 'review-renditions'
  and public.can_read_assignment_media(bucket_id, name)
);
