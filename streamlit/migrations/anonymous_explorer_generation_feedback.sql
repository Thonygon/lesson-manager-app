-- Anonymous Explorer previews have no account or saved resource. Keep their
-- labels separate from authenticated resource feedback and retain no prompt.
create table if not exists public.classio_explorer_generation_feedback (
    operation_id uuid primary key references public.classio_ai_operations(operation_id) on delete cascade,
    session_hash text not null check (length(session_hash) = 64),
    feature_name text not null,
    feedback_surface text not null default 'explorer_preview' check (feedback_surface = 'explorer_preview'),
    satisfied boolean not null,
    reason text check (reason is null or reason in ('content', 'level', 'format', 'other')),
    answered_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (satisfied is not true or reason is null)
);
create index if not exists classio_explorer_generation_feedback_answered_idx
    on public.classio_explorer_generation_feedback(answered_at desc);
alter table public.classio_explorer_generation_feedback enable row level security;
revoke all on public.classio_explorer_generation_feedback from anon, authenticated;
grant select, insert, update on public.classio_explorer_generation_feedback to service_role;
