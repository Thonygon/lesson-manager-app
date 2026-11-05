-- Storage objects must be removed through the Storage API before the existing
-- account-deletion RPC marks a profile deleted. Then the database transaction
-- removes report text, responses, and ticket metadata.
drop policy if exists classio_help_screenshots_owner_read on storage.objects;
create policy classio_help_screenshots_owner_read on storage.objects for select to authenticated
using (bucket_id = 'classio-help-screenshots' and split_part(name, '/', 1) = auth.uid()::text);

drop policy if exists classio_help_screenshots_owner_delete on storage.objects;
create policy classio_help_screenshots_owner_delete on storage.objects for delete to authenticated
using (bucket_id = 'classio-help-screenshots' and split_part(name, '/', 1) = auth.uid()::text);

create or replace function public.classio_help_purge_deleted_profile()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.account_status = 'deleted' and old.account_status is distinct from 'deleted' then
    if exists (
      select 1 from storage.objects o
      where o.bucket_id = 'classio-help-screenshots'
        and split_part(o.name, '/', 1) = new.user_id
    ) then
      raise exception 'Support screenshots must be removed before account deletion' using errcode = '23514';
    end if;
    delete from public.classio_help_tickets where reporter_id = new.user_id::uuid;
  end if;
  return new;
end;
$$;
revoke all on function public.classio_help_purge_deleted_profile() from public, anon, authenticated;
drop trigger if exists classio_help_purge_on_profile_delete on public.profiles;
create trigger classio_help_purge_on_profile_delete
after update of account_status on public.profiles
for each row execute function public.classio_help_purge_deleted_profile();
