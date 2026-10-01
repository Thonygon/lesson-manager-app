ALTER TABLE schedules
ADD COLUMN IF NOT EXISTS start_date DATE,
ADD COLUMN IF NOT EXISTS end_date DATE;

CREATE INDEX IF NOT EXISTS idx_schedules_user_active_dates
    ON schedules (user_id, active, student, start_date, end_date);
