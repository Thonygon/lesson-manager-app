-- ============================================================
-- CLASSIO — Teacher / Student Integration + Assignments
-- Safe additive migration for teacher relationships, subject scopes,
-- assignments, and assignment attempts.
-- ============================================================

-- Shared updated_at trigger helper
create or replace function classio_set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- ============================================================
-- 1) teacher_student_links
-- One normalized relationship row per teacher + student pair.
-- Status drives request / active / archive lifecycle.
-- ============================================================
create table if not exists teacher_student_links (
    id                 bigint generated always as identity primary key,
    teacher_id         uuid not null references auth.users(id) on delete cascade,
    student_id         uuid not null references auth.users(id) on delete cascade,
    requested_by       uuid not null references auth.users(id) on delete cascade,
    status             text not null default 'pending'
                       check (status in ('pending', 'active', 'rejected', 'archived')),
    requested_subjects jsonb not null default '[]'::jsonb,
    request_note       text not null default '',
    responded_at       timestamptz,
    responded_by       uuid references auth.users(id) on delete set null,
    archived_at        timestamptz,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),

    constraint teacher_student_links_unique_pair unique (teacher_id, student_id),
    constraint teacher_student_links_not_self check (teacher_id <> student_id)
);

drop trigger if exists trg_teacher_student_links_updated_at on teacher_student_links;
create trigger trg_teacher_student_links_updated_at
before update on teacher_student_links
for each row execute function classio_set_updated_at();

create index if not exists idx_teacher_student_links_teacher_status
    on teacher_student_links(teacher_id, status, created_at desc);
create index if not exists idx_teacher_student_links_student_status
    on teacher_student_links(student_id, status, created_at desc);

-- ============================================================
-- 2) teacher_student_subjects
-- Explicit subject scopes inside one teacher-student link.
-- Supports one teacher teaching multiple subjects to the same student.
-- ============================================================
create table if not exists teacher_student_subjects (
    id             bigint generated always as identity primary key,
    link_id         bigint not null references teacher_student_links(id) on delete cascade,
    teacher_id      uuid not null references auth.users(id) on delete cascade,
    student_id      uuid not null references auth.users(id) on delete cascade,
    subject_key     text not null,
    subject_label   text not null default '',
    status          text not null default 'active'
                    check (status in ('active', 'archived')),
    activated_at    timestamptz,
    deactivated_at  timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    constraint teacher_student_subjects_unique_scope unique (link_id, subject_key)
);

drop trigger if exists trg_teacher_student_subjects_updated_at on teacher_student_subjects;
create trigger trg_teacher_student_subjects_updated_at
before update on teacher_student_subjects
for each row execute function classio_set_updated_at();

create index if not exists idx_teacher_student_subjects_link_status
    on teacher_student_subjects(link_id, status, subject_key);
create index if not exists idx_teacher_student_subjects_teacher_student
    on teacher_student_subjects(teacher_id, student_id, status);

-- ============================================================
-- 3) teacher_assignments
-- Unified assignment table for worksheets, exams, and lesson-plan topics.
-- content_snapshot is notification-ready and keeps student-visible data
-- independent from teacher-only source documents.
-- ============================================================
create table if not exists teacher_assignments (
    id               bigint generated always as identity primary key,
    link_id          bigint not null references teacher_student_links(id) on delete restrict,
    subject_scope_id bigint references teacher_student_subjects(id) on delete set null,
    teacher_id       uuid not null references auth.users(id) on delete cascade,
    student_id       uuid not null references auth.users(id) on delete cascade,
    assignment_type  text not null
                     check (assignment_type in ('worksheet', 'exam', 'lesson_plan_topic')),
    source_type      text not null
                     check (source_type in ('worksheet_builder', 'exam_builder', 'lesson_plan_builder')),
    source_record_id bigint,
    title            text not null default '',
    subject_key      text not null default '',
    subject_label    text not null default '',
    topic            text not null default '',
    teacher_note     text not null default '',
    content_snapshot jsonb not null default '{}'::jsonb,
    status           text not null default 'assigned'
                     check (status in ('assigned', 'started', 'submitted', 'graded', 'completed', 'overdue', 'cancelled')),
    score_pct        numeric(5,1),
    total_questions  integer,
    correct_count    integer,
    due_at           timestamptz,
    assigned_at      timestamptz not null default now(),
    opened_at        timestamptz,
    viewed_at        timestamptz,
    submitted_at     timestamptz,
    graded_at        timestamptz,
    completed_at     timestamptz,
    cancelled_at     timestamptz,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

drop trigger if exists trg_teacher_assignments_updated_at on teacher_assignments;
create trigger trg_teacher_assignments_updated_at
before update on teacher_assignments
for each row execute function classio_set_updated_at();

create index if not exists idx_teacher_assignments_teacher_status
    on teacher_assignments(teacher_id, status, created_at desc);
create index if not exists idx_teacher_assignments_student_status
    on teacher_assignments(student_id, status, due_at);
create index if not exists idx_teacher_assignments_link_subject
    on teacher_assignments(link_id, subject_scope_id, status);
create index if not exists idx_teacher_assignments_due
    on teacher_assignments(due_at);
create index if not exists idx_teacher_assignments_type
    on teacher_assignments(assignment_type, source_type);

-- ============================================================
-- 4) teacher_assignment_attempts
-- Each submitted/graded assignment attempt. Future robot/notification hooks
-- can watch created_at / submitted_at / graded_at here.
-- ============================================================
create table if not exists teacher_assignment_attempts (
    id                 bigint generated always as identity primary key,
    assignment_id      bigint not null references teacher_assignments(id) on delete cascade,
    teacher_id         uuid not null references auth.users(id) on delete cascade,
    student_id         uuid not null references auth.users(id) on delete cascade,
    practice_session_id bigint references practice_sessions(id) on delete set null,
    attempt_number     integer not null default 1,
    status             text not null default 'submitted'
                       check (status in ('started', 'submitted', 'graded', 'completed')),
    score_pct          numeric(5,1),
    total_questions    integer,
    correct_count      integer,
    submission_payload jsonb not null default '{}'::jsonb,
    teacher_feedback   text not null default '',
    started_at         timestamptz,
    submitted_at       timestamptz,
    graded_at          timestamptz,
    completed_at       timestamptz,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

drop trigger if exists trg_teacher_assignment_attempts_updated_at on teacher_assignment_attempts;
create trigger trg_teacher_assignment_attempts_updated_at
before update on teacher_assignment_attempts
for each row execute function classio_set_updated_at();

create index if not exists idx_teacher_assignment_attempts_assignment
    on teacher_assignment_attempts(assignment_id, created_at desc);
create index if not exists idx_teacher_assignment_attempts_teacher
    on teacher_assignment_attempts(teacher_id, student_id, created_at desc);
create index if not exists idx_teacher_assignment_attempts_student
    on teacher_assignment_attempts(student_id, created_at desc);

-- ============================================================
-- RLS
-- ============================================================
alter table teacher_student_links enable row level security;
alter table teacher_student_subjects enable row level security;
alter table teacher_assignments enable row level security;
alter table teacher_assignment_attempts enable row level security;

-- teacher_student_links
drop policy if exists "Teacher/student read own links" on teacher_student_links;
create policy "Teacher/student read own links"
on teacher_student_links
for select
using (auth.uid() = teacher_id or auth.uid() = student_id);

drop policy if exists "Student creates own teacher requests" on teacher_student_links;
create policy "Student creates own teacher requests"
on teacher_student_links
for insert
with check (
    auth.uid() = student_id
    and auth.uid() = requested_by
    and teacher_id <> student_id
    and status = 'pending'
);

drop policy if exists "Teacher updates own teacher links" on teacher_student_links;
create policy "Teacher updates own teacher links"
on teacher_student_links
for update
using (auth.uid() = teacher_id)
with check (auth.uid() = teacher_id);

drop policy if exists "Student updates own teacher links" on teacher_student_links;
create policy "Student updates own teacher links"
on teacher_student_links
for update
using (auth.uid() = student_id)
with check (auth.uid() = student_id);

-- teacher_student_subjects
drop policy if exists "Teacher/student read own subject scopes" on teacher_student_subjects;
create policy "Teacher/student read own subject scopes"
on teacher_student_subjects
for select
using (auth.uid() = teacher_id or auth.uid() = student_id);

drop policy if exists "Teacher manages active subject scopes" on teacher_student_subjects;
create policy "Teacher manages active subject scopes"
on teacher_student_subjects
for all
using (
    auth.uid() = teacher_id
    and exists (
        select 1
        from teacher_student_links l
        where l.id = teacher_student_subjects.link_id
          and l.teacher_id = auth.uid()
    )
)
with check (
    auth.uid() = teacher_id
    and exists (
        select 1
        from teacher_student_links l
        where l.id = link_id
          and l.teacher_id = auth.uid()
    )
);

-- teacher_assignments
drop policy if exists "Teacher/student read own assignments" on teacher_assignments;
create policy "Teacher/student read own assignments"
on teacher_assignments
for select
using (auth.uid() = teacher_id or auth.uid() = student_id);

drop policy if exists "Teacher creates scoped assignments" on teacher_assignments;
create policy "Teacher creates scoped assignments"
on teacher_assignments
for insert
with check (
    auth.uid() = teacher_id
    and exists (
        select 1
        from teacher_student_links l
        where l.id = link_id
          and l.teacher_id = auth.uid()
          and l.student_id = teacher_assignments.student_id
          and l.status = 'active'
    )
    and exists (
        select 1
        from teacher_student_subjects s
        where s.id = subject_scope_id
          and s.link_id = link_id
          and s.teacher_id = auth.uid()
          and s.student_id = teacher_assignments.student_id
          and s.status = 'active'
    )
);

drop policy if exists "Teacher updates own assignments" on teacher_assignments;
create policy "Teacher updates own assignments"
on teacher_assignments
for update
using (auth.uid() = teacher_id)
with check (auth.uid() = teacher_id);

drop policy if exists "Student updates own assignments" on teacher_assignments;
create policy "Student updates own assignments"
on teacher_assignments
for update
using (auth.uid() = student_id)
with check (auth.uid() = student_id);

-- teacher_assignment_attempts
drop policy if exists "Teacher/student read own assignment attempts" on teacher_assignment_attempts;
create policy "Teacher/student read own assignment attempts"
on teacher_assignment_attempts
for select
using (auth.uid() = teacher_id or auth.uid() = student_id);

drop policy if exists "Student creates assignment attempts" on teacher_assignment_attempts;
create policy "Student creates assignment attempts"
on teacher_assignment_attempts
for insert
with check (
    auth.uid() = student_id
    and exists (
        select 1
        from teacher_assignments a
        where a.id = assignment_id
          and a.student_id = auth.uid()
          and a.teacher_id = teacher_assignment_attempts.teacher_id
    )
);

drop policy if exists "Student updates own assignment attempts" on teacher_assignment_attempts;
create policy "Student updates own assignment attempts"
on teacher_assignment_attempts
for update
using (auth.uid() = student_id)
with check (auth.uid() = student_id);

drop policy if exists "Teacher updates own assignment attempts" on teacher_assignment_attempts;
create policy "Teacher updates own assignment attempts"
on teacher_assignment_attempts
for update
using (auth.uid() = teacher_id)
with check (auth.uid() = teacher_id);
