-- Bound unauthenticated magic-link requests without storing worker emails or
-- client IP addresses. The route supplies SHA-256 hashes only.

create table private.passwordless_login_requests (
  id bigint generated always as identity primary key,
  email_hash text not null check (email_hash ~ '^[0-9a-f]{64}$'),
  ip_hash text not null check (ip_hash ~ '^[0-9a-f]{64}$'),
  requested_at timestamptz not null default now()
);

create index passwordless_login_requests_email_time_idx
  on private.passwordless_login_requests (email_hash, requested_at desc);
create index passwordless_login_requests_ip_time_idx
  on private.passwordless_login_requests (ip_hash, requested_at desc);

alter table private.passwordless_login_requests enable row level security;
alter table private.passwordless_login_requests force row level security;
revoke all on private.passwordless_login_requests from public, anon, authenticated;

create or replace function public.check_passwordless_login_rate(
  p_email_hash text,
  p_ip_hash text
)
returns boolean
language plpgsql
security definer
set search_path = public, private, pg_temp
as $$
begin
  if p_email_hash !~ '^[0-9a-f]{64}$'
     or p_ip_hash !~ '^[0-9a-f]{64}$' then
    return false;
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_email_hash, 0));

  delete from private.passwordless_login_requests
  where requested_at < now() - interval '24 hours';

  if exists (
    select 1
    from private.passwordless_login_requests request
    where request.email_hash = p_email_hash
      and request.requested_at > now() - interval '60 seconds'
  ) or (
    select count(*)
    from private.passwordless_login_requests request
    where request.email_hash = p_email_hash
      and request.requested_at > now() - interval '1 hour'
  ) >= 5 or (
    select count(*)
    from private.passwordless_login_requests request
    where request.ip_hash = p_ip_hash
      and request.requested_at > now() - interval '1 hour'
  ) >= 30 then
    return false;
  end if;

  insert into private.passwordless_login_requests (email_hash, ip_hash)
  values (p_email_hash, p_ip_hash);
  return true;
end;
$$;

revoke all on function public.check_passwordless_login_rate(text, text)
  from public, authenticated;
grant execute on function public.check_passwordless_login_rate(text, text)
  to anon;
