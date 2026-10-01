-- Add gcal_event_id column to calendar_overrides
-- Stores the Google Calendar event ID so we can update/delete events on reschedule/cancel
ALTER TABLE calendar_overrides
ADD COLUMN IF NOT EXISTS gcal_event_id TEXT DEFAULT NULL;
