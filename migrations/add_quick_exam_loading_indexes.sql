-- Speed up heavy resource library lists and avoid statement timeouts on large tables.

create index if not exists idx_quick_exams_user_created_at
    on quick_exams(user_id, created_at desc);

create index if not exists idx_quick_exams_public_created_at
    on quick_exams(created_at desc)
    where is_public = true;

create index if not exists idx_worksheets_user_created_at
    on worksheets(user_id, created_at desc);

create index if not exists idx_worksheets_public_created_at
    on worksheets(created_at desc)
    where is_public = true;

create index if not exists idx_lesson_plans_user_created_at
    on lesson_plans(user_id, created_at desc);

create index if not exists idx_lesson_plans_public_created_at
    on lesson_plans(created_at desc)
    where is_public = true;

create index if not exists idx_learning_programs_user_updated_at
    on learning_programs(user_id, updated_at desc);

create index if not exists idx_learning_programs_public_active_updated_at
    on learning_programs(updated_at desc)
    where is_public = true and status = 'active';

create index if not exists idx_learning_program_units_program_unit_number
    on learning_program_units(program_id, unit_number);

create index if not exists idx_learning_program_topics_program_unit_topic_number
    on learning_program_topics(program_id, unit_number, topic_number);
