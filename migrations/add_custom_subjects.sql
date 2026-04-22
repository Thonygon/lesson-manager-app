-- Add custom_subjects column to profiles table
-- Stores the actual subject names when a teacher selects "other" as primary subject
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS custom_subjects text[] DEFAULT '{}';

COMMENT ON COLUMN profiles.custom_subjects IS 'Custom subject names entered by teacher when selecting "other" in primary subjects';
