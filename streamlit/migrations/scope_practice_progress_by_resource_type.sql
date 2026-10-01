-- Keep practice progress material-aware so worksheet/exam/video-facing
-- UI can use the same resource color system without mixing aggregates.

alter table practice_progress
    add column if not exists source_type text not null default 'custom';

drop index if exists idx_practice_progress_user_scope_topic_type_level;

create unique index if not exists idx_practice_progress_user_scope_source_topic_type_level
    on practice_progress(user_id, scope_key, source_type, subject, topic, exercise_type, level);

create index if not exists idx_practice_progress_user_source_last_practiced
    on practice_progress(user_id, source_type, last_practiced desc);
