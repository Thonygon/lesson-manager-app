-- ============================================================
-- CLASSIO — Allow UUID-backed source resource IDs in assignments
-- ------------------------------------------------------------
-- Some resource tables now use non-numeric IDs (for example UUIDs).
-- teacher_assignments.source_record_id must therefore accept either
-- legacy bigint-looking values or UUID/text values.
-- ============================================================

alter table if exists teacher_assignments
    alter column source_record_id type text
    using case
        when source_record_id is null then null
        else source_record_id::text
    end;

drop index if exists idx_teacher_assignments_source_record;
create index if not exists idx_teacher_assignments_source_record
    on teacher_assignments(teacher_id, source_type, source_record_id);
