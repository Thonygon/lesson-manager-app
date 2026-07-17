-- Canonical resource exposure and outcome telemetry for ML-ready supervision.

create table if not exists resource_exposures (
    id bigserial primary key,
    exposure_id text not null,
    idempotency_key text not null,
    teacher_id text references profiles(user_id) on delete cascade,
    student_id text references profiles(user_id) on delete cascade,
    viewer_user_id text references profiles(user_id) on delete cascade,
    resource_id text not null default '',
    resource_type text not null default '',
    exposure_type text not null default ''
        check (exposure_type in (
            'assigned_resource',
            'optional_student_recommendation',
            'teacher_objective_recommendation',
            'teacher_resource_recommendation',
            'teacher_material_feed',
            'material_reuse_suggestion'
        )),
    surface text not null default '',
    position integer,
    recommendation_bucket text not null default '',
    recommendation_focus_kind text not null default '',
    learning_program_assignment_id bigint references learning_program_assignments(id) on delete set null,
    learning_program_topic_id bigint references learning_program_topics(id) on delete set null,
    shown_at timestamptz not null default timezone('utc', now()),
    model_component_id text not null default '',
    model_version text not null default '',
    heuristic_score numeric(12,6),
    learned_score numeric(12,6),
    final_score numeric(12,6),
    context_json jsonb not null default '{}'::jsonb,
    is_backfilled boolean not null default false,
    created_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists idx_resource_exposures_exposure_id
    on resource_exposures(exposure_id);
create unique index if not exists idx_resource_exposures_idempotency_key
    on resource_exposures(idempotency_key);
create index if not exists idx_resource_exposures_teacher_shown
    on resource_exposures(teacher_id, shown_at desc);
create index if not exists idx_resource_exposures_student_shown
    on resource_exposures(student_id, shown_at desc);
create index if not exists idx_resource_exposures_viewer_shown
    on resource_exposures(viewer_user_id, shown_at desc);
create index if not exists idx_resource_exposures_type_surface
    on resource_exposures(exposure_type, surface, shown_at desc);

create table if not exists resource_exposure_events (
    id bigserial primary key,
    exposure_id text not null default '',
    event_type text not null default ''
        check (event_type in (
            'opened',
            'started',
            'completed',
            'scored',
            'assigned',
            'accepted',
            'rejected',
            'ignored',
            'teacher_reviewed',
            'student_improved'
        )),
    event_at timestamptz not null default timezone('utc', now()),
    score_pct numeric(5,1),
    outcome_json jsonb not null default '{}'::jsonb,
    idempotency_key text not null,
    is_backfilled boolean not null default false,
    teacher_id text references profiles(user_id) on delete cascade,
    student_id text references profiles(user_id) on delete cascade,
    viewer_user_id text references profiles(user_id) on delete cascade,
    created_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists idx_resource_exposure_events_idempotency_key
    on resource_exposure_events(idempotency_key);
create index if not exists idx_resource_exposure_events_exposure_id
    on resource_exposure_events(exposure_id, event_at desc);
create index if not exists idx_resource_exposure_events_teacher_event
    on resource_exposure_events(teacher_id, event_at desc);
create index if not exists idx_resource_exposure_events_student_event
    on resource_exposure_events(student_id, event_at desc);

alter table if exists teacher_assignments
    add column if not exists resource_exposure_id text;
create index if not exists idx_teacher_assignments_resource_exposure_id
    on teacher_assignments(resource_exposure_id);

alter table resource_exposures enable row level security;
alter table resource_exposure_events enable row level security;

drop policy if exists "resource exposures read own" on resource_exposures;
create policy "resource exposures read own"
on resource_exposures
for select
using (
    auth.uid()::text = teacher_id
    or auth.uid()::text = student_id
    or auth.uid()::text = viewer_user_id
);

drop policy if exists "resource exposures manage own" on resource_exposures;
create policy "resource exposures manage own"
on resource_exposures
for all
using (
    auth.uid()::text = teacher_id
    or auth.uid()::text = student_id
    or auth.uid()::text = viewer_user_id
)
with check (
    auth.uid()::text = teacher_id
    or auth.uid()::text = student_id
    or auth.uid()::text = viewer_user_id
);

drop policy if exists "resource exposure events read own" on resource_exposure_events;
create policy "resource exposure events read own"
on resource_exposure_events
for select
using (
    auth.uid()::text = teacher_id
    or auth.uid()::text = student_id
    or auth.uid()::text = viewer_user_id
);

drop policy if exists "resource exposure events manage own" on resource_exposure_events;
create policy "resource exposure events manage own"
on resource_exposure_events
for all
using (
    auth.uid()::text = teacher_id
    or auth.uid()::text = student_id
    or auth.uid()::text = viewer_user_id
)
with check (
    auth.uid()::text = teacher_id
    or auth.uid()::text = student_id
    or auth.uid()::text = viewer_user_id
);
