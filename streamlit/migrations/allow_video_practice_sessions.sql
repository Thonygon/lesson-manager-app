-- Allow video watches to be stored in the same practice history/progress
-- pipeline as worksheets and exams.
--
-- Without this, Supabase rejects video watch rows with:
--   practice_sessions_source_type_check

alter table public.practice_sessions
    drop constraint if exists practice_sessions_source_type_check;

alter table public.practice_sessions
    add constraint practice_sessions_source_type_check
    check (source_type in ('worksheet', 'exam', 'video', 'custom'));

