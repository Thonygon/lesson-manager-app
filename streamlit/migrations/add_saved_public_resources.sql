-- A bookmark preserves the author's ownership and never copies resource content.
create table if not exists public.classio_saved_public_resources (
  user_id uuid not null references auth.users(id) on delete cascade,
  resource_kind text not null check (resource_kind in ('program', 'plan', 'worksheet', 'exam', 'video')),
  resource_id text not null check (length(resource_id) between 1 and 80),
  created_at timestamptz not null default now(),
  primary key (user_id, resource_kind, resource_id)
);

create index if not exists classio_saved_public_resources_recent_idx
  on public.classio_saved_public_resources (user_id, created_at desc);

alter table public.classio_saved_public_resources enable row level security;

create policy classio_saved_public_resources_read on public.classio_saved_public_resources
  for select to authenticated using (user_id = (select auth.uid()));
create policy classio_saved_public_resources_delete on public.classio_saved_public_resources
  for delete to authenticated using (user_id = (select auth.uid()));

revoke all on public.classio_saved_public_resources from anon, authenticated;
grant select, delete on public.classio_saved_public_resources to authenticated;

create or replace function public.classio_save_public_resource(p_kind text, p_resource_id text)
returns boolean
language plpgsql security definer set search_path = public, pg_temp
as $$
declare
  v_table text;
  v_visible boolean;
begin
  if auth.uid() is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if not exists (
    select 1 from public.profiles
    where user_id = auth.uid()::text and coalesce(can_teach, false)
  ) then
    raise exception 'Teacher account required' using errcode = '42501';
  end if;
  if p_resource_id is null or length(p_resource_id) not between 1 and 80 or p_resource_id !~ '^[0-9]+$' then
    raise exception 'Invalid resource ID' using errcode = '22023';
  end if;
  v_table := case p_kind
    when 'program' then 'learning_programs'
    when 'plan' then 'lesson_plans'
    when 'worksheet' then 'worksheets'
    when 'exam' then 'quick_exams'
    when 'video' then 'videos'
  end;
  if v_table is null then
    raise exception 'Invalid resource kind' using errcode = '22023';
  end if;
  execute format(
    'select exists(select 1 from public.%I where id::text = $1 and is_public is true and coalesce(status, ''active'') <> ''archived'')',
    v_table
  ) into v_visible using p_resource_id;
  if not v_visible then
    raise exception 'Public resource unavailable' using errcode = 'P0002';
  end if;
  insert into public.classio_saved_public_resources (user_id, resource_kind, resource_id)
    values (auth.uid(), p_kind, p_resource_id)
    on conflict do nothing;
  return true;
end;
$$;

revoke all on function public.classio_save_public_resource(text, text) from public, anon;
grant execute on function public.classio_save_public_resource(text, text) to authenticated;
