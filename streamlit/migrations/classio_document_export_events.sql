-- One event per export request. handoff_requested means the app invoked the
-- browser download handoff; it does not prove that a file reached the device.
-- No filename, document content, student identifier or teacher payment is stored.
create table if not exists public.classio_document_export_events (
    event_id uuid primary key,
    actor_user_id uuid references auth.users(id) on delete set null,
    source text not null check (source in ('expo', 'streamlit')),
    format text not null check (format in ('pdf', 'docx')),
    document_kind text not null check (document_kind in ('lesson_plan', 'worksheet', 'exam', 'cv', 'cover_letter', 'student_report', 'student_history', 'dashboard_report', 'other')),
    variant text not null check (variant in ('full', 'student', 'teacher', 'answers')),
    status text not null check (status in ('started', 'handoff_requested', 'failed')),
    unit_count smallint not null default 1 check (unit_count = 1),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    error_kind text check (error_kind is null or length(error_kind) <= 80),
    schema_version smallint not null default 1 check (schema_version = 1),
    check (finished_at is null or finished_at >= started_at)
);

create index if not exists classio_document_export_events_started_idx on public.classio_document_export_events(started_at desc);
create index if not exists classio_document_export_events_actor_started_idx on public.classio_document_export_events(actor_user_id, started_at desc);
create index if not exists classio_document_export_events_format_status_idx on public.classio_document_export_events(format, status, started_at desc);

alter table public.classio_document_export_events enable row level security;
revoke all on public.classio_document_export_events from public, anon, authenticated;
grant select, insert, update on public.classio_document_export_events to service_role;
