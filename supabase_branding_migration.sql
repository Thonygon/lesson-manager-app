-- ============================================================
-- CLASSIO — Branding Settings Migration
-- ============================================================

-- 1) Create branding_settings table
CREATE TABLE IF NOT EXISTS branding_settings (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL UNIQUE,
    header_logo_url   TEXT DEFAULT '',
    footer_image_url  TEXT DEFAULT '',
    brand_name        TEXT DEFAULT '',
    department        TEXT DEFAULT '',
    header_enabled    BOOLEAN DEFAULT FALSE,
    footer_enabled    BOOLEAN DEFAULT FALSE,
    header_style      TEXT DEFAULT 'standard' CHECK (header_style IN ('standard', 'school')),
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now()
);

-- 2) Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_branding_settings_user_id ON branding_settings(user_id);

-- 3) Auto-update updated_at on modification
CREATE OR REPLACE FUNCTION update_branding_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_branding_updated_at ON branding_settings;
CREATE TRIGGER trg_branding_updated_at
    BEFORE UPDATE ON branding_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_branding_updated_at();

-- 4) RLS policies
ALTER TABLE branding_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY branding_select_own ON branding_settings
    FOR SELECT USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY branding_insert_own ON branding_settings
    FOR INSERT WITH CHECK (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY branding_update_own ON branding_settings
    FOR UPDATE USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

-- 5) Create storage bucket for branding assets
INSERT INTO storage.buckets (id, name, public)
VALUES ('branding', 'branding', true)
ON CONFLICT (id) DO NOTHING;

-- 6) Storage policies for branding bucket
CREATE POLICY branding_upload ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'branding'
        AND (storage.foldername(name))[1] = current_setting('request.jwt.claims', true)::json->>'sub'
    );

CREATE POLICY branding_read ON storage.objects
    FOR SELECT USING (bucket_id = 'branding');

CREATE POLICY branding_delete ON storage.objects
    FOR DELETE USING (
        bucket_id = 'branding'
        AND (storage.foldername(name))[1] = current_setting('request.jwt.claims', true)::json->>'sub'
    );
