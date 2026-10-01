-- Fill the remaining index gaps for student/teacher responsiveness.
-- Existing migrations already cover most assignment and practice hot paths.
-- These indexes target the still-hot recommendation summary and program-video
-- lookup queries used by teacher/student recommendation surfaces.

create index if not exists idx_learning_program_recommendation_events_teacher_assignment_created_at
    on learning_program_recommendation_events(teacher_id, learning_program_assignment_id, created_at desc);

create index if not exists idx_learning_program_recommendation_events_student_assignment_created_at
    on learning_program_recommendation_events(student_id, learning_program_assignment_id, created_at desc);

create index if not exists idx_learning_program_topic_videos_teacher_created_at
    on learning_program_topic_videos(teacher_id, created_at desc);
