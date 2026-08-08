-- Review requests point back to practice_sessions.source_id, which can be
-- numeric legacy ids or UUID/text resource ids.

alter table if exists public.teacher_review_requests
    alter column source_id type text
    using case
        when source_id is null then null
        else source_id::text
    end;
