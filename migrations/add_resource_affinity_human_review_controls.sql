alter table if exists public.ml_experiment_runs
    add column if not exists human_review_recommended_model_name text,
    add column if not exists human_review_notes text,
    add column if not exists human_reviewed_at timestamptz,
    add column if not exists human_reviewed_by uuid references auth.users(id) on delete set null;
