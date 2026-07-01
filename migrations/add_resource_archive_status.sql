-- ============================================================
-- CLASSIO — Resource archive lifecycle
-- Adds archive status to saved resources and source archive flags
-- to teacher assignments so archived sources can stay visible
-- without remaining retryable.
-- ============================================================

alter table if exists lesson_plans
    add column if not exists status text not null default 'active';

alter table if exists worksheets
    add column if not exists status text not null default 'active';

alter table if exists quick_exams
    add column if not exists status text not null default 'active';

alter table if exists professional_profiles
    add column if not exists status text not null default 'active';

create index if not exists idx_lesson_plans_user_status
    on lesson_plans(user_id, status, created_at desc);
create index if not exists idx_worksheets_user_status
    on worksheets(user_id, status, created_at desc);
create index if not exists idx_quick_exams_user_status
    on quick_exams(user_id, status, created_at desc);
create index if not exists idx_professional_profiles_user_status
    on professional_profiles(user_id, status, created_at desc);

alter table if exists teacher_assignments
    add column if not exists source_archived boolean not null default false;
alter table if exists teacher_assignments
    add column if not exists source_archived_at timestamptz;

alter table if exists teacher_assignments
    drop constraint if exists teacher_assignments_status_check;
alter table if exists teacher_assignments
    add constraint teacher_assignments_status_check
    check (status in ('assigned', 'started', 'submitted', 'graded', 'completed', 'overdue', 'cancelled', 'archived'));

create index if not exists idx_teacher_assignments_source_record
    on teacher_assignments(teacher_id, source_type, source_record_id);
create index if not exists idx_teacher_assignments_source_archived
    on teacher_assignments(student_id, source_archived, status);

alter table if exists learning_program_assignments
    add column if not exists source_archived boolean not null default false;
alter table if exists learning_program_assignments
    add column if not exists source_archived_at timestamptz;

update lesson_plans
set status = 'active'
where status is null or btrim(status) = '';

update worksheets
set status = 'active'
where status is null or btrim(status) = '';

update quick_exams
set status = 'active'
where status is null or btrim(status) = '';

update professional_profiles
set status = 'active'
where status is null or btrim(status) = '';
