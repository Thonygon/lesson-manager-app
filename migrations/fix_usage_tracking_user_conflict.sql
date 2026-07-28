-- Required by services/subscription_service.py:
--   upsert(..., on_conflict="user_id")
--
-- Supabase/PostgREST requires the conflict target to match a UNIQUE or
-- PRIMARY KEY constraint/index. This migration is idempotent and safe to rerun.

create unique index if not exists idx_usage_tracking_user_id_unique
    on public.usage_tracking(user_id);

