-- Private beta help desk. User reports may contain sensitive screenshots;
-- keep the bucket private and require a matching ticket before upload.
create table if not exists public.classio_help_tickets (
  id uuid primary key default gen_random_uuid(),
  ticket_number bigint generated always as identity unique,
  reporter_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('bug', 'idea', 'accessibility', 'other')),
  title text not null check (char_length(btrim(title)) between 5 and 120),
  description text not null check (char_length(btrim(description)) between 15 and 4000),
  page_path text not null default '/help' check (char_length(page_path) between 1 and 300 and left(page_path, 1) = '/'),
  screenshot_mime text check (screenshot_mime is null or screenshot_mime in ('image/png', 'image/jpeg')),
  status text not null default 'open' check (status in ('open', 'triaged', 'in_progress', 'resolved', 'closed')),
  response text check (response is null or char_length(response) <= 2000),
  handled_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (status = 'open' or handled_by is not null)
);

create index if not exists classio_help_tickets_queue_idx on public.classio_help_tickets(status, created_at desc);
create index if not exists classio_help_tickets_reporter_idx on public.classio_help_tickets(reporter_id, created_at desc);

create or replace function public.classio_help_is_staff()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.user_staff_roles r
    where r.user_id = auth.uid() and r.is_active and r.role_key = 'developer'
  ) or exists (
    select 1 from public.profiles p
    where p.user_id = auth.uid()::text and p.role = 'admin'
  );
$$;
revoke all on function public.classio_help_is_staff() from public, anon;
grant execute on function public.classio_help_is_staff() to authenticated;

create or replace function public.classio_help_ticket_guard()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or new.reporter_id is distinct from auth.uid() then
    raise exception 'Authenticated reporter required' using errcode = '42501';
  end if;
  if new.status <> 'open' or new.response is not null or new.handled_by is not null then
    raise exception 'New reports must start open' using errcode = '23514';
  end if;
  if exists (select 1 from public.classio_help_tickets t
             where t.reporter_id = auth.uid() and t.created_at > now() - interval '30 seconds')
     or (select count(*) from public.classio_help_tickets t
         where t.reporter_id = auth.uid() and t.created_at > now() - interval '1 day') >= 10 then
    raise exception 'Report rate limit reached' using errcode = 'P0001';
  end if;
  return new;
end;
$$;
drop trigger if exists classio_help_ticket_guard_insert on public.classio_help_tickets;
create trigger classio_help_ticket_guard_insert before insert on public.classio_help_tickets
for each row execute function public.classio_help_ticket_guard();

create or replace function public.classio_help_ticket_audit_update()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end;
$$;
drop trigger if exists classio_help_ticket_update on public.classio_help_tickets;
create trigger classio_help_ticket_update before update on public.classio_help_tickets
for each row execute function public.classio_help_ticket_audit_update();

alter table public.classio_help_tickets enable row level security;
revoke all on public.classio_help_tickets from public, anon, authenticated;
grant select, insert on public.classio_help_tickets to authenticated;
grant update (status, response, handled_by) on public.classio_help_tickets to authenticated;
grant usage, select on sequence public.classio_help_tickets_ticket_number_seq to authenticated;

drop policy if exists classio_help_tickets_read on public.classio_help_tickets;
create policy classio_help_tickets_read on public.classio_help_tickets for select to authenticated
using (reporter_id = auth.uid() or public.classio_help_is_staff());
drop policy if exists classio_help_tickets_insert on public.classio_help_tickets;
create policy classio_help_tickets_insert on public.classio_help_tickets for insert to authenticated
with check (reporter_id = auth.uid() and status = 'open' and response is null and handled_by is null);
drop policy if exists classio_help_tickets_staff_update on public.classio_help_tickets;
create policy classio_help_tickets_staff_update on public.classio_help_tickets for update to authenticated
using (public.classio_help_is_staff()) with check (public.classio_help_is_staff());

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('classio-help-screenshots', 'classio-help-screenshots', false, 5242880, array['image/png', 'image/jpeg'])
on conflict (id) do nothing;

drop policy if exists classio_help_screenshots_upload on storage.objects;
create policy classio_help_screenshots_upload on storage.objects for insert to authenticated
with check (
  bucket_id = 'classio-help-screenshots' and exists (
    select 1 from public.classio_help_tickets t
    where t.reporter_id = auth.uid()
      and name = t.reporter_id::text || '/' || t.id::text ||
        case t.screenshot_mime when 'image/png' then '.png' when 'image/jpeg' then '.jpg' else '.none' end
  )
);
drop policy if exists classio_help_screenshots_read on storage.objects;
create policy classio_help_screenshots_read on storage.objects for select to authenticated
using (
  bucket_id = 'classio-help-screenshots' and (
    public.classio_help_is_staff() or exists (
      select 1 from public.classio_help_tickets t
      where t.reporter_id = auth.uid()
        and name = t.reporter_id::text || '/' || t.id::text ||
          case t.screenshot_mime when 'image/png' then '.png' when 'image/jpeg' then '.jpg' else '.none' end
    )
  )
);
