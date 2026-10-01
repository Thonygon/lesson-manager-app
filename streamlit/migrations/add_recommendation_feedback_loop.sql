alter table if exists teacher_assignments
    add column if not exists learning_program_assignment_id bigint references learning_program_assignments(id) on delete set null;
alter table if exists teacher_assignments
    add column if not exists learning_program_topic_id bigint references learning_program_topics(id) on delete set null;
alter table if exists teacher_assignments
    add column if not exists recommendation_bucket text not null default '';
alter table if exists teacher_assignments
    add column if not exists recommendation_focus_kind text not null default '';
alter table if exists teacher_assignments
    add column if not exists recommendation_context jsonb not null default '{}'::jsonb;

alter table if exists teacher_assignment_attempts
    add column if not exists learning_program_assignment_id bigint references learning_program_assignments(id) on delete set null;
alter table if exists teacher_assignment_attempts
    add column if not exists learning_program_topic_id bigint references learning_program_topics(id) on delete set null;
alter table if exists teacher_assignment_attempts
    add column if not exists recommendation_bucket text not null default '';
alter table if exists teacher_assignment_attempts
    add column if not exists recommendation_focus_kind text not null default '';
alter table if exists teacher_assignment_attempts
    add column if not exists recommendation_context jsonb not null default '{}'::jsonb;

create table if not exists learning_program_recommendation_events (
    id bigserial primary key,
    teacher_id text not null references profiles(user_id) on delete cascade,
    student_id text not null references profiles(user_id) on delete cascade,
    learning_program_assignment_id bigint references learning_program_assignments(id) on delete cascade,
    program_id bigint references learning_programs(id) on delete set null,
    learning_program_topic_id bigint references learning_program_topics(id) on delete set null,
    recommendation_bucket text not null default '',
    recommendation_focus_kind text not null default '',
    resource_kind text not null default '',
    resource_record_id bigint,
    teacher_assignment_id bigint references teacher_assignments(id) on delete set null,
    assignment_attempt_id bigint references teacher_assignment_attempts(id) on delete set null,
    event_type text not null default '',
    event_weight numeric(6,3) not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_teacher_assignments_learning_program_topic
    on teacher_assignments(student_id, learning_program_assignment_id, learning_program_topic_id, updated_at desc);
create index if not exists idx_teacher_assignment_attempts_learning_program_topic
    on teacher_assignment_attempts(student_id, learning_program_assignment_id, learning_program_topic_id, created_at desc);
create index if not exists idx_learning_program_recommendation_events_scope
    on learning_program_recommendation_events(student_id, learning_program_assignment_id, learning_program_topic_id, created_at desc);
create index if not exists idx_learning_program_recommendation_events_teacher
    on learning_program_recommendation_events(teacher_id, created_at desc);

drop trigger if exists trg_learning_program_recommendation_events_updated_at on learning_program_recommendation_events;
create trigger trg_learning_program_recommendation_events_updated_at
before update on learning_program_recommendation_events
for each row execute function update_updated_at_column();

alter table learning_program_recommendation_events enable row level security;

drop policy if exists "learning program recommendation events read own" on learning_program_recommendation_events;
create policy "learning program recommendation events read own"
on learning_program_recommendation_events
for select
using (auth.uid()::text = teacher_id or auth.uid()::text = student_id);

drop policy if exists "learning program recommendation events manage own" on learning_program_recommendation_events;
create policy "learning program recommendation events manage own"
on learning_program_recommendation_events
for all
using (auth.uid()::text = teacher_id or auth.uid()::text = student_id)
with check (auth.uid()::text = teacher_id or auth.uid()::text = student_id);
