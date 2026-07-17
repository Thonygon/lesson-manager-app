-- ============================================================
-- CLASSIO — Phase 3.6 developer workspace and ML experiment platform
-- ============================================================

create table if not exists public.user_staff_roles (
    id bigserial primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    role_key text not null check (role_key in ('developer', 'data_scientist')),
    is_active boolean not null default true,
    assigned_by uuid references auth.users(id) on delete set null,
    assigned_at timestamptz not null default timezone('utc', now()),
    revoked_by uuid references auth.users(id) on delete set null,
    revoked_at timestamptz,
    assignment_reason text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists idx_user_staff_roles_unique_active
    on public.user_staff_roles (user_id, role_key)
    where is_active = true;

create index if not exists idx_user_staff_roles_user_active
    on public.user_staff_roles (user_id, is_active, assigned_at desc);

create table if not exists public.privileged_action_audit_log (
    id bigserial primary key,
    actor_user_id uuid references auth.users(id) on delete set null,
    actor_roles jsonb not null default '[]'::jsonb,
    action_type text not null,
    entity_type text not null,
    entity_id text not null,
    before_json jsonb,
    after_json jsonb,
    reason text,
    request_context jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_privileged_action_audit_log_created_at
    on public.privileged_action_audit_log (created_at desc);

create index if not exists idx_privileged_action_audit_log_actor
    on public.privileged_action_audit_log (actor_user_id, created_at desc);

create table if not exists public.system_jobs (
    id bigserial primary key,
    job_id text not null unique,
    job_type text not null check (job_type in ('ml_experiment_evaluation', 'ml_integrity_review')),
    job_version text not null,
    status text not null check (status in ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'STALE')),
    priority integer not null default 50,
    requested_by uuid references auth.users(id) on delete set null,
    requested_by_role text,
    requested_at timestamptz not null default timezone('utc', now()),
    started_at timestamptz,
    completed_at timestamptz,
    heartbeat_at timestamptz,
    progress_pct numeric(5,2) not null default 0,
    current_stage text,
    payload_json jsonb not null default '{}'::jsonb,
    result_json jsonb,
    warning_json jsonb,
    error_code text,
    error_message text,
    retry_count integer not null default 0,
    max_retries integer not null default 1,
    idempotency_key text not null,
    related_entity_type text,
    related_entity_id text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists idx_system_jobs_active_idempotency
    on public.system_jobs (idempotency_key)
    where status in ('QUEUED', 'RUNNING');

create index if not exists idx_system_jobs_type_status_created
    on public.system_jobs (job_type, status, created_at desc);

create table if not exists public.ml_experiments (
    id bigserial primary key,
    experiment_id text not null,
    experiment_version text not null,
    name text not null,
    business_question text not null,
    target_version text not null,
    unit_of_analysis text not null,
    primary_metric text not null,
    is_active boolean not null default true,
    definition_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (experiment_id, experiment_version)
);

create index if not exists idx_ml_experiments_active
    on public.ml_experiments (experiment_id, is_active, updated_at desc);

create table if not exists public.ml_experiment_runs (
    id bigserial primary key,
    run_id text not null unique,
    experiment_id text not null,
    experiment_version text not null,
    job_id text,
    run_status text not null check (
        run_status in (
            'DRAFT',
            'ELIGIBILITY_CHECK',
            'ELIGIBLE',
            'INELIGIBLE',
            'QUEUED',
            'RUNNING',
            'COMPLETED_PENDING_VALIDATION',
            'VALIDATED_EXPLORATORY_RUN',
            'VALIDATED_NO_ROBUST_WINNER',
            'REQUIRES_RERUN',
            'INVALID_LABEL_CONSTRUCTION',
            'FAILED',
            'SUPERSEDED',
            'ARCHIVED'
        )
    ),
    integrity_status text not null check (
        integrity_status in (
            'NOT_RUN',
            'RUNNING',
            'PASSED_EXPLORATORY',
            'PASSED_NO_ROBUST_WINNER',
            'REQUIRES_RERUN',
            'INVALID_LABEL_CONSTRUCTION',
            'FAILED'
        )
    ),
    maturity_verdict text,
    evidence_verdict text,
    operational_use text,
    academic_use text,
    is_current_validated_run boolean not null default false,
    created_at timestamptz not null default timezone('utc', now()),
    started_at timestamptz,
    completed_at timestamptz,
    initiated_by uuid references auth.users(id) on delete set null,
    environment text,
    code_version text,
    extraction_timestamp timestamptz,
    source_start_at timestamptz,
    source_end_at timestamptz,
    dataset_fingerprint text,
    source_row_count integer,
    included_row_count integer,
    positive_label_count integer,
    negative_label_count integer,
    right_censored_count integer,
    invalid_row_count integer,
    teachers_represented integer,
    students_represented integer,
    resources_represented integer,
    chronological_cutoff timestamptz,
    feature_schema_version text,
    features_used_json jsonb,
    features_excluded_json jsonb,
    primary_metric_leader text,
    thresholded_classifier_leader text,
    precision_recall_leader text,
    calibration_leader text,
    overall_model_selection text,
    artifact_root text,
    supersedes_run_id text,
    superseded_by_run_id text,
    validation_notes text,
    warning_summary text,
    failure_message text
);

create index if not exists idx_ml_experiment_runs_listing
    on public.ml_experiment_runs (experiment_id, created_at desc);

create index if not exists idx_ml_experiment_runs_status
    on public.ml_experiment_runs (experiment_id, run_status, created_at desc);

create unique index if not exists idx_ml_experiment_runs_current_validated
    on public.ml_experiment_runs (experiment_id)
    where is_current_validated_run = true;

create table if not exists public.ml_run_models (
    id bigserial primary key,
    run_id text not null references public.ml_experiment_runs(run_id) on delete cascade,
    model_name text not null,
    execution_status text not null,
    parameters_json jsonb,
    cv_metrics_json jsonb,
    holdout_metrics_json jsonb,
    confidence_intervals_json jsonb,
    confusion_matrix_json jsonb,
    predicted_positive_rate numeric,
    train_duration_ms integer,
    inference_duration_ms integer,
    failure_message text,
    created_at timestamptz not null default timezone('utc', now()),
    unique (run_id, model_name)
);

create index if not exists idx_ml_run_models_run
    on public.ml_run_models (run_id, created_at asc);

create table if not exists public.ml_run_artifacts (
    id bigserial primary key,
    run_id text not null references public.ml_experiment_runs(run_id) on delete cascade,
    artifact_type text not null,
    storage_bucket text not null,
    storage_path text not null,
    checksum text,
    content_type text,
    size_bytes bigint,
    contains_sensitive_data boolean not null default false,
    created_at timestamptz not null default timezone('utc', now()),
    unique (run_id, artifact_type, storage_path)
);

create index if not exists idx_ml_run_artifacts_run
    on public.ml_run_artifacts (run_id, created_at asc);

alter table public.user_staff_roles enable row level security;
alter table public.privileged_action_audit_log enable row level security;
alter table public.system_jobs enable row level security;
alter table public.ml_experiments enable row level security;
alter table public.ml_experiment_runs enable row level security;
alter table public.ml_run_models enable row level security;
alter table public.ml_run_artifacts enable row level security;

drop policy if exists "user_staff_roles_self_read" on public.user_staff_roles;
create policy "user_staff_roles_self_read"
    on public.user_staff_roles
    for select
    using (auth.uid() = user_id);

drop policy if exists "user_staff_roles_admin_select" on public.user_staff_roles;
create policy "user_staff_roles_admin_select"
    on public.user_staff_roles
    for select
    using (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
    );

drop policy if exists "user_staff_roles_admin_insert" on public.user_staff_roles;
create policy "user_staff_roles_admin_insert"
    on public.user_staff_roles
    for insert
    with check (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
        and role_key in ('developer', 'data_scientist')
    );

drop policy if exists "user_staff_roles_admin_update" on public.user_staff_roles;
create policy "user_staff_roles_admin_update"
    on public.user_staff_roles
    for update
    using (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
    )
    with check (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
    );

drop policy if exists "privileged_action_audit_log_select" on public.privileged_action_audit_log;
create policy "privileged_action_audit_log_select"
    on public.privileged_action_audit_log
    for select
    using (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
        or exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "privileged_action_audit_log_insert" on public.privileged_action_audit_log;
create policy "privileged_action_audit_log_insert"
    on public.privileged_action_audit_log
    for insert
    with check (auth.uid() is not null);

drop policy if exists "system_jobs_staff_select" on public.system_jobs;
create policy "system_jobs_staff_select"
    on public.system_jobs
    for select
    using (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
        or exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "system_jobs_staff_write" on public.system_jobs;
create policy "system_jobs_staff_write"
    on public.system_jobs
    for all
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    )
    with check (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "ml_experiments_staff_select" on public.ml_experiments;
create policy "ml_experiments_staff_select"
    on public.ml_experiments
    for select
    using (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
        or exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "ml_experiments_staff_write" on public.ml_experiments;
create policy "ml_experiments_staff_write"
    on public.ml_experiments
    for all
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    )
    with check (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "ml_experiment_runs_staff_select" on public.ml_experiment_runs;
create policy "ml_experiment_runs_staff_select"
    on public.ml_experiment_runs
    for select
    using (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
        or exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "ml_experiment_runs_staff_write" on public.ml_experiment_runs;
create policy "ml_experiment_runs_staff_write"
    on public.ml_experiment_runs
    for all
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    )
    with check (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "ml_run_models_staff_select" on public.ml_run_models;
create policy "ml_run_models_staff_select"
    on public.ml_run_models
    for select
    using (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
        or exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "ml_run_models_staff_write" on public.ml_run_models;
create policy "ml_run_models_staff_write"
    on public.ml_run_models
    for all
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    )
    with check (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "ml_run_artifacts_staff_select" on public.ml_run_artifacts;
create policy "ml_run_artifacts_staff_select"
    on public.ml_run_artifacts
    for select
    using (
        exists (
            select 1
            from public.profiles
            where profiles.user_id = auth.uid()::text
              and profiles.role = 'admin'
        )
        or exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "ml_run_artifacts_staff_write" on public.ml_run_artifacts;
create policy "ml_run_artifacts_staff_write"
    on public.ml_run_artifacts
    for all
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    )
    with check (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );
