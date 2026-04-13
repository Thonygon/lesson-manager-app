-- Learning programs, units, topics, assignments, and progress

create table if not exists learning_programs (
    id bigserial primary key,
    user_id text references profiles(user_id) on delete cascade,
    title text not null default '',
    slug text not null default '',
    subject text not null default 'other',
    custom_subject_name text,
    learner_stage text not null default '',
    level_or_band text not null default '',
    program_language text not null default 'en',
    student_material_language text not null default 'en',
    program_overview text not null default '',
    teacher_rationale text not null default '',
    student_summary text not null default '',
    assessment_strategy text not null default '',
    resource_strategy text not null default '',
    best_practice_frameworks jsonb not null default '[]'::jsonb,
    source_type text not null default 'ai',
    generation_mode text not null default 'ai',
    visibility text not null default 'private',
    is_public boolean not null default false,
    status text not null default 'draft',
    total_units integer not null default 0,
    total_topics integer not null default 0,
    builder_config jsonb not null default '{}'::jsonb,
    program_data jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_learning_programs_user_id on learning_programs(user_id);
create index if not exists idx_learning_programs_public on learning_programs(is_public, updated_at desc);
create index if not exists idx_learning_programs_subject_stage_level on learning_programs(subject, learner_stage, level_or_band);


create table if not exists learning_program_units (
    id bigserial primary key,
    program_id bigint not null references learning_programs(id) on delete cascade,
    unit_number integer not null,
    title text not null default '',
    overview text not null default '',
    unit_objectives jsonb not null default '[]'::jsonb,
    recommended_lesson_purposes jsonb not null default '[]'::jsonb,
    recommended_worksheet_types jsonb not null default '[]'::jsonb,
    recommended_exam_exercise_types jsonb not null default '[]'::jsonb,
    estimated_lessons integer not null default 0,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint learning_program_units_unique_order unique (program_id, unit_number)
);

create index if not exists idx_learning_program_units_program_id on learning_program_units(program_id, unit_number);


create table if not exists learning_program_topics (
    id bigserial primary key,
    program_id bigint not null references learning_programs(id) on delete cascade,
    unit_id bigint not null references learning_program_units(id) on delete cascade,
    unit_number integer not null,
    topic_number integer not null,
    title text not null default '',
    subtopic text not null default '',
    lesson_focus text not null default '',
    lesson_purpose text not null default '',
    learning_objectives jsonb not null default '[]'::jsonb,
    success_criteria jsonb not null default '[]'::jsonb,
    student_can_do jsonb not null default '[]'::jsonb,
    suggested_worksheet_types jsonb not null default '[]'::jsonb,
    suggested_exam_exercise_types jsonb not null default '[]'::jsonb,
    homework_idea text not null default '',
    teacher_notes text not null default '',
    student_summary text not null default '',
    estimated_lessons integer not null default 1,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint learning_program_topics_unique_order unique (unit_id, topic_number)
);

create index if not exists idx_learning_program_topics_program_id on learning_program_topics(program_id, unit_number, topic_number);
create index if not exists idx_learning_program_topics_unit_id on learning_program_topics(unit_id, topic_number);


create table if not exists learning_program_assignments (
    id bigserial primary key,
    program_id bigint not null references learning_programs(id) on delete cascade,
    teacher_id text not null references profiles(user_id) on delete cascade,
    student_user_id text references profiles(user_id) on delete cascade,
    student_name text not null default '',
    assigned_by_user_id text references profiles(user_id) on delete set null,
    status text not null default 'assigned',
    start_on date,
    target_completion_on date,
    teacher_note text not null default '',
    assigned_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_learning_program_assignments_teacher on learning_program_assignments(teacher_id, updated_at desc);
create index if not exists idx_learning_program_assignments_student on learning_program_assignments(student_user_id, updated_at desc);
create index if not exists idx_learning_program_assignments_program on learning_program_assignments(program_id, updated_at desc);


create table if not exists learning_program_progress (
    id bigserial primary key,
    assignment_id bigint not null references learning_program_assignments(id) on delete cascade,
    topic_id bigint not null references learning_program_topics(id) on delete cascade,
    teacher_done boolean not null default false,
    student_done boolean not null default false,
    is_done boolean not null default false,
    note text not null default '',
    completed_at timestamptz,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint learning_program_progress_unique_scope unique (assignment_id, topic_id)
);

create index if not exists idx_learning_program_progress_assignment on learning_program_progress(assignment_id);
create index if not exists idx_learning_program_progress_topic on learning_program_progress(topic_id);


create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_learning_programs_updated_at on learning_programs;
create trigger trg_learning_programs_updated_at
before update on learning_programs
for each row execute function update_updated_at_column();

drop trigger if exists trg_learning_program_units_updated_at on learning_program_units;
create trigger trg_learning_program_units_updated_at
before update on learning_program_units
for each row execute function update_updated_at_column();

drop trigger if exists trg_learning_program_topics_updated_at on learning_program_topics;
create trigger trg_learning_program_topics_updated_at
before update on learning_program_topics
for each row execute function update_updated_at_column();

drop trigger if exists trg_learning_program_assignments_updated_at on learning_program_assignments;
create trigger trg_learning_program_assignments_updated_at
before update on learning_program_assignments
for each row execute function update_updated_at_column();

drop trigger if exists trg_learning_program_progress_updated_at on learning_program_progress;
create trigger trg_learning_program_progress_updated_at
before update on learning_program_progress
for each row execute function update_updated_at_column();


alter table learning_programs enable row level security;
alter table learning_program_units enable row level security;
alter table learning_program_topics enable row level security;
alter table learning_program_assignments enable row level security;
alter table learning_program_progress enable row level security;

drop policy if exists "learning programs read own or public" on learning_programs;
create policy "learning programs read own or public"
on learning_programs
for select
using (auth.uid()::text = user_id or is_public = true);

drop policy if exists "learning programs insert own" on learning_programs;
create policy "learning programs insert own"
on learning_programs
for insert
with check (auth.uid()::text = user_id);

drop policy if exists "learning programs update own" on learning_programs;
create policy "learning programs update own"
on learning_programs
for update
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

drop policy if exists "learning program units read through program access" on learning_program_units;
create policy "learning program units read through program access"
on learning_program_units
for select
using (
    exists (
        select 1
        from learning_programs p
        where p.id = learning_program_units.program_id
          and (p.user_id = auth.uid()::text or p.is_public = true)
    )
);

drop policy if exists "learning program units manage own program" on learning_program_units;
create policy "learning program units manage own program"
on learning_program_units
for all
using (
    exists (
        select 1
        from learning_programs p
        where p.id = learning_program_units.program_id
          and p.user_id = auth.uid()::text
    )
)
with check (
    exists (
        select 1
        from learning_programs p
        where p.id = learning_program_units.program_id
          and p.user_id = auth.uid()::text
    )
);

drop policy if exists "learning program topics read through program access" on learning_program_topics;
create policy "learning program topics read through program access"
on learning_program_topics
for select
using (
    exists (
        select 1
        from learning_programs p
        where p.id = learning_program_topics.program_id
          and (p.user_id = auth.uid()::text or p.is_public = true)
    )
);

drop policy if exists "learning program topics manage own program" on learning_program_topics;
create policy "learning program topics manage own program"
on learning_program_topics
for all
using (
    exists (
        select 1
        from learning_programs p
        where p.id = learning_program_topics.program_id
          and p.user_id = auth.uid()::text
    )
)
with check (
    exists (
        select 1
        from learning_programs p
        where p.id = learning_program_topics.program_id
          and p.user_id = auth.uid()::text
    )
);

drop policy if exists "learning program assignments teacher or student read" on learning_program_assignments;
create policy "learning program assignments teacher or student read"
on learning_program_assignments
for select
using (auth.uid()::text = teacher_id or auth.uid()::text = student_user_id);

drop policy if exists "learning program assignments teacher manage" on learning_program_assignments;
create policy "learning program assignments teacher manage"
on learning_program_assignments
for all
using (auth.uid()::text = teacher_id)
with check (auth.uid()::text = teacher_id);

drop policy if exists "learning program progress teacher or student read" on learning_program_progress;
create policy "learning program progress teacher or student read"
on learning_program_progress
for select
using (
    exists (
        select 1
        from learning_program_assignments a
        where a.id = learning_program_progress.assignment_id
          and (a.teacher_id = auth.uid()::text or a.student_user_id = auth.uid()::text)
    )
);

drop policy if exists "learning program progress teacher or student manage" on learning_program_progress;
create policy "learning program progress teacher or student manage"
on learning_program_progress
for all
using (
    exists (
        select 1
        from learning_program_assignments a
        where a.id = learning_program_progress.assignment_id
          and (a.teacher_id = auth.uid()::text or a.student_user_id = auth.uid()::text)
    )
)
with check (
    exists (
        select 1
        from learning_program_assignments a
        where a.id = learning_program_progress.assignment_id
          and (a.teacher_id = auth.uid()::text or a.student_user_id = auth.uid()::text)
    )
);
