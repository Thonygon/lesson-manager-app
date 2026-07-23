-- Keep independent practice separate from teacher-assigned progress.
-- Existing rows remain in the "independent" scope until the app rebuilds them
-- from practice_sessions and teacher_assignment_attempts.

alter table practice_progress
    add column if not exists scope_key text not null default 'independent',
    add column if not exists teacher_id uuid references auth.users(id) on delete set null,
    add column if not exists assignment_id bigint references teacher_assignments(id) on delete set null,
    add column if not exists learning_program_assignment_id bigint
        references learning_program_assignments(id) on delete set null;

alter table practice_progress
    drop constraint if exists practice_progress_user_id_subject_topic_exercise_type_level_key;

create unique index if not exists idx_practice_progress_user_scope_topic_type_level
    on practice_progress(user_id, scope_key, subject, topic, exercise_type, level);

create index if not exists idx_practice_progress_student_teacher_subject
    on practice_progress(user_id, teacher_id, subject, last_practiced desc);
