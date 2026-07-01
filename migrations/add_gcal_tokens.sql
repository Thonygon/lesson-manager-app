-- Add gcal_tokens column to profiles table for Google Calendar integration
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS gcal_tokens jsonb DEFAULT NULL;

COMMENT ON COLUMN profiles.gcal_tokens IS 'Stores Google Calendar OAuth2 refresh/access tokens as JSON';
