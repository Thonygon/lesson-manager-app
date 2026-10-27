-- Metadata-only record of the mode users actually received when AI was not
-- available. Do not store prompts, document content or student identities.
create table if not exists public.classio_ai_fallback_events (
    id bigint generated always as identity primary key,
    source text not null check (source in ('expo', 'streamlit', 'python_api')),
    feature_name text not null check (length(feature_name) between 1 and 80),
    requested_mode text not null check (requested_mode in ('ai', 'model')),
    effective_mode text not null check (effective_mode in ('template', 'heuristic', 'unavailable')),
    reason text not null check (length(reason) between 1 and 80),
    created_at timestamptz not null default now()
);
create index if not exists classio_ai_fallback_recent_idx
    on public.classio_ai_fallback_events(created_at desc);
alter table public.classio_ai_fallback_events enable row level security;
revoke all on public.classio_ai_fallback_events from public, anon, authenticated;
grant select on public.classio_ai_fallback_events to authenticated;
grant insert on public.classio_ai_fallback_events to service_role;
drop policy if exists classio_ai_fallback_staff_read on public.classio_ai_fallback_events;
create policy classio_ai_fallback_staff_read on public.classio_ai_fallback_events
for select to authenticated using (
    exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key in ('developer', 'data_scientist'))
    or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')
);
