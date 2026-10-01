-- Supabase Disk IO review indexes.
-- These indexes are tied to observed application query patterns in dashboard,
-- analytics, calendar, and activity paths. They are intentionally limited to
-- composite indexes that match existing filters and ordering.

create index if not exists idx_classes_user_lesson_date
    on public.classes (user_id, lesson_date desc);

create index if not exists idx_payments_user_payment_date
    on public.payments (user_id, payment_date desc);

create index if not exists idx_calendar_overrides_user_student_original_date
    on public.calendar_overrides (user_id, student, original_date, id desc);

create index if not exists idx_user_activity_log_user_created_at
    on public.user_activity_log (user_id, created_at desc);