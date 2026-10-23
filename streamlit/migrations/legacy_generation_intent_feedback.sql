-- Older AI library resources may have no economic operation to bind. Their
-- labels are useful but remain separate from model-attributed feedback.
create table if not exists public.classio_legacy_generation_intent_feedback (
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    resource_type text not null check (resource_type in ('plan', 'worksheet', 'exam')),
    resource_id text not null,
    feedback_surface text not null default 'resource_page' check (feedback_surface = 'resource_page'),
    satisfied boolean not null,
    reason text check (reason is null or reason in ('content', 'level', 'format', 'other')),
    answered_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (actor_user_id, resource_type, resource_id),
    check (satisfied is not true or reason is null)
);
create index if not exists classio_legacy_generation_intent_answered_idx
    on public.classio_legacy_generation_intent_feedback(answered_at desc);
create table if not exists public.classio_legacy_generation_intent_events (
    id bigint generated always as identity primary key,
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    resource_type text not null,
    resource_id text not null,
    feedback_surface text not null default 'resource_page',
    satisfied boolean not null,
    reason text,
    created_at timestamptz not null default now()
);
alter table public.classio_legacy_generation_intent_feedback enable row level security;
alter table public.classio_legacy_generation_intent_events enable row level security;
revoke all on public.classio_legacy_generation_intent_feedback,
    public.classio_legacy_generation_intent_events from anon, authenticated;
grant select, insert, update on public.classio_legacy_generation_intent_feedback to service_role;
grant select, insert on public.classio_legacy_generation_intent_events to service_role;
grant usage, select on sequence public.classio_legacy_generation_intent_events_id_seq to service_role;
