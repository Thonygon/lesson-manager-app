-- Speed up student-facing pages: assignments, practice history/drafts,
-- linked teacher lookups, and learning-program progress.

-- Student assignment inbox and teacher-side assignment archive state sync.
create index if not exists idx_teacher_assignments_student_created_at
    on teacher_assignments(student_id, created_at desc)
    where status <> 'archived';

create index if not exists idx_teacher_assignments_teacher_source_record
    on teacher_assignments(teacher_id, assignment_type, source_type, source_record_id);

-- Student link + subject-scope loading.
create index if not exists idx_teacher_student_subjects_link_subject_status
    on teacher_student_subjects(link_id, subject_key, status);

-- Learning program assignments and progress for students.
create index if not exists idx_learning_program_assignments_student_updated_at
    on learning_program_assignments(student_user_id, updated_at desc)
    where status <> 'archived';

create index if not exists idx_learning_program_assignments_student_name_updated_at
    on learning_program_assignments(student_name, updated_at desc)
    where status <> 'archived';

create index if not exists idx_learning_program_progress_assignment_topic
    on learning_program_progress(assignment_id, topic_id);

create index if not exists idx_learning_program_progress_assignment_updated_at
    on learning_program_progress(assignment_id, updated_at desc);

-- Practice sessions: history and in-progress resume.
create index if not exists idx_practice_sessions_user_status_created_at
    on practice_sessions(user_id, status, created_at desc);

create index if not exists idx_practice_sessions_in_progress_source
    on practice_sessions(user_id, source_type, source_id, created_at desc)
    where status = 'in_progress';

-- Practice answers: draft restore and per-session answer scans.
create index if not exists idx_practice_answers_session_user_order
    on practice_answers(session_id, user_id, exercise_idx, question_idx);

-- Practice progress: student dashboards and recommendation profile reads.
create index if not exists idx_practice_progress_user_last_practiced
    on practice_progress(user_id, last_practiced desc);
