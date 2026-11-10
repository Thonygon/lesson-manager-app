-- Suspend without deleting user data. Existing JWTs are denied at the Data API
-- and RLS boundaries; refresh sessions are removed on the status transition.
create or replace function public.classio_account_access_allowed()
returns boolean
language sql stable security definer set search_path = ''
as $$
  select case
    when (select auth.role()) <> 'authenticated' or (select auth.uid()) is null then true
    else coalesce((
      select p.account_status = 'active'
      from public.profiles p where p.user_id = (select auth.uid())::text
    ), true)
  end
$$;
revoke all on function public.classio_account_access_allowed() from public;
grant execute on function public.classio_account_access_allowed() to anon, authenticated, service_role;

create or replace function public.classio_check_account_request()
returns void
language plpgsql stable security definer set search_path = ''
as $$
begin
  if (select auth.role()) = 'authenticated'
     and not (select public.classio_account_access_allowed()) then
    raise exception 'Account access is suspended' using errcode = '42501';
  end if;
end
$$;
revoke all on function public.classio_check_account_request() from public;
grant execute on function public.classio_check_account_request() to anon, authenticated, service_role;

-- The Data API check also covers SECURITY DEFINER RPCs that bypass table RLS.
alter role authenticator set pgrst.db_pre_request = 'public.classio_check_account_request';
notify pgrst, 'reload config';

-- Storage and other products use RLS rather than PostgREST's pre-request hook.
do $$
declare target record;
begin
  for target in
    select n.nspname, c.relname
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind in ('r', 'p') and c.relrowsecurity
  loop
    execute format('drop policy if exists classio_active_account_gate on %I.%I', target.nspname, target.relname);
    execute format('create policy classio_active_account_gate on %I.%I as restrictive for all to authenticated using ((select public.classio_account_access_allowed())) with check ((select public.classio_account_access_allowed()))', target.nspname, target.relname);
  end loop;
end
$$;
drop policy if exists classio_active_account_gate on storage.objects;
create policy classio_active_account_gate on storage.objects
as restrictive for all to authenticated
using ((select public.classio_account_access_allowed()))
with check ((select public.classio_account_access_allowed()));

create or replace function public.classio_revoke_sessions_on_suspend()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  if new.account_status = 'suspended'
     and old.account_status is distinct from 'suspended' then
    delete from auth.sessions where user_id = new.user_id::uuid;
  end if;
  return new;
end
$$;
revoke all on function public.classio_revoke_sessions_on_suspend() from public, anon, authenticated;
drop trigger if exists classio_revoke_sessions_on_suspend on public.profiles;
create trigger classio_revoke_sessions_on_suspend
after update of account_status on public.profiles
for each row execute function public.classio_revoke_sessions_on_suspend();
