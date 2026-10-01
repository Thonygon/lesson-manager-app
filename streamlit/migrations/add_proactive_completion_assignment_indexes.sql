-- Speed up teacher-side warnings for resources a student completed
-- independently before the teacher assigns them.

create index if not exists idx_practice_sessions_completed_source
    on practice_sessions(user_id, source_type, source_id, completed_at desc)
    where status = 'completed';

create index if not exists idx_teacher_assignment_attempts_student_session
    on teacher_assignment_attempts(student_id, practice_session_id)
    where practice_session_id is not null;
