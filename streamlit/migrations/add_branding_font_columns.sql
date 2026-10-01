-- ============================================================
-- CLASSIO — Add branding_font and branding_font_size columns
-- Run this migration on the branding_settings table
-- ============================================================

ALTER TABLE branding_settings
    ADD COLUMN IF NOT EXISTS branding_font TEXT DEFAULT 'dejavu',
    ADD COLUMN IF NOT EXISTS branding_font_size TEXT DEFAULT 'standard';
