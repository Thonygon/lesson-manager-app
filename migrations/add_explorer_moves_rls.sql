begin;

alter table public.explorer_moves enable row level security;

revoke all on public.explorer_moves from anon, authenticated;
grant insert on public.explorer_moves to anon;
grant select, update on public.explorer_moves to authenticated;

grant usage, select on sequence public.explorer_moves_id_seq to anon;

drop policy if exists explorer_moves_anon_insert on public.explorer_moves;
drop policy if exists explorer_moves_admin_select on public.explorer_moves;
drop policy if exists explorer_moves_admin_update on public.explorer_moves;

create policy explorer_moves_anon_insert
on public.explorer_moves
for insert
to anon
with check (
    resource_type in ('lesson_plan', 'worksheet', 'exam')
    and tool_key <> ''
    and source_section <> ''
    and anonymous_session_id <> ''
);

create policy explorer_moves_admin_select
on public.explorer_moves
for select
to authenticated
using (
    exists (
        select 1
        from public.profiles p
        where p.user_id = auth.uid()::text
          and lower(coalesce(p.role, '')) = 'admin'
    )
);

create policy explorer_moves_admin_update
on public.explorer_moves
for update
to authenticated
using (
    exists (
        select 1
        from public.profiles p
        where p.user_id = auth.uid()::text
          and lower(coalesce(p.role, '')) = 'admin'
    )
)
with check (
    exists (
        select 1
        from public.profiles p
        where p.user_id = auth.uid()::text
          and lower(coalesce(p.role, '')) = 'admin'
    )
);

commit;