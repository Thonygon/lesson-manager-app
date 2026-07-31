-- ============================================================
-- CLASSIO — Store practice session resource ids as text
-- ------------------------------------------------------------
-- Resource ids are no longer guaranteed to be numeric. Exams are
-- UUID-backed in production, so practice_sessions.source_id must
-- accept either legacy numeric ids or UUID/text ids.
-- ============================================================

alter table if exists practice_sessions
    drop column if exists owner_id;

alter table if exists practice_sessions
    alter column source_id type text
    using case
        when source_id is null then null
        else source_id::text
    end;

drop index if exists idx_practice_sessions_in_progress_source;
create index if not exists idx_practice_sessions_in_progress_source
    on practice_sessions(user_id, source_type, source_id, created_at desc)
    where status = 'in_progress';
