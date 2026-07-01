-- ============================================================
-- CLASSIO — Smart Practice: Phase 1 Tables
-- Run this in the Supabase SQL Editor.
-- ============================================================

-- 1. practice_sessions — one row per completed practice attempt
CREATE TABLE IF NOT EXISTS practice_sessions (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    owner_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    source_type   TEXT NOT NULL DEFAULT 'worksheet',       -- 'worksheet' | 'exam'
    source_id     BIGINT,                                  -- FK to worksheets.id or quick_exams.id (nullable)
    title         TEXT NOT NULL DEFAULT '',
    subject       TEXT NOT NULL DEFAULT '',
    topic         TEXT NOT NULL DEFAULT '',
    learner_stage TEXT NOT NULL DEFAULT '',
    level         TEXT NOT NULL DEFAULT '',

    exercise_data JSONB NOT NULL DEFAULT '{}',             -- full unified schema snapshot
    total_questions INT NOT NULL DEFAULT 0,
    correct_count   INT NOT NULL DEFAULT 0,
    score_pct       NUMERIC(5,1) NOT NULL DEFAULT 0,
    xp_earned       INT NOT NULL DEFAULT 0,
    best_streak     INT NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'completed',     -- 'in_progress' | 'completed'

    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. practice_answers — individual answers per question
CREATE TABLE IF NOT EXISTS practice_answers (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id     BIGINT NOT NULL REFERENCES practice_sessions(id) ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    exercise_idx   INT NOT NULL DEFAULT 0,
    question_idx   INT NOT NULL DEFAULT 0,
    exercise_type  TEXT NOT NULL DEFAULT '',

    student_answer TEXT NOT NULL DEFAULT '',
    correct_answer TEXT NOT NULL DEFAULT '',
    is_correct     BOOLEAN NOT NULL DEFAULT FALSE,

    answered_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. practice_progress — aggregate accuracy per subject/topic/type
CREATE TABLE IF NOT EXISTS practice_progress (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    owner_id        UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    subject         TEXT NOT NULL DEFAULT '',
    topic           TEXT NOT NULL DEFAULT '',
    exercise_type   TEXT NOT NULL DEFAULT '',
    level           TEXT NOT NULL DEFAULT '',

    total_attempted INT NOT NULL DEFAULT 0,
    total_correct   INT NOT NULL DEFAULT 0,
    accuracy_pct    NUMERIC(5,1) NOT NULL DEFAULT 0,
    total_xp        INT NOT NULL DEFAULT 0,
    best_streak     INT NOT NULL DEFAULT 0,
    last_practiced  TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(user_id, subject, topic, exercise_type, level)
);


-- ── Row Level Security ─────────────────────────────────────────

ALTER TABLE practice_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice_answers   ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice_progress  ENABLE ROW LEVEL SECURITY;

-- practice_sessions: users see/insert their own rows
DROP POLICY IF EXISTS "Users manage own practice sessions" ON practice_sessions;
CREATE POLICY "Users manage own practice sessions"
    ON practice_sessions FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- practice_answers: users see/insert their own rows
DROP POLICY IF EXISTS "Users manage own practice answers" ON practice_answers;
CREATE POLICY "Users manage own practice answers"
    ON practice_answers FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- practice_progress: users see/insert their own rows
DROP POLICY IF EXISTS "Users manage own practice progress" ON practice_progress;
CREATE POLICY "Users manage own practice progress"
    ON practice_progress FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ── Indexes ────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_practice_sessions_user
    ON practice_sessions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_practice_answers_session
    ON practice_answers(session_id);

CREATE INDEX IF NOT EXISTS idx_practice_progress_user
    ON practice_progress(user_id, subject, topic, exercise_type);


-- ── Patch: add gamification columns if tables already exist ────
-- Safe to run multiple times (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)

ALTER TABLE practice_sessions  ADD COLUMN IF NOT EXISTS xp_earned   INT NOT NULL DEFAULT 0;
ALTER TABLE practice_sessions  ADD COLUMN IF NOT EXISTS best_streak INT NOT NULL DEFAULT 0;
ALTER TABLE practice_progress  ADD COLUMN IF NOT EXISTS total_xp    INT NOT NULL DEFAULT 0;
ALTER TABLE practice_progress  ADD COLUMN IF NOT EXISTS best_streak INT NOT NULL DEFAULT 0;
