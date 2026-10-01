create table if not exists public.experiment_report_contexts (
    id bigserial primary key,
    run_id text not null references public.ml_experiment_runs(run_id) on delete cascade,
    experiment_id text not null,
    language text not null default 'en',
    purpose_key text,
    decision_under_consideration_key text,
    audience_key text,
    business_problem text,
    decision_supported text,
    expected_value text,
    product_impact text,
    success_definition text,
    minimum_evidence_required text,
    risks text,
    next_review_trigger text,
    next_review_date date,
    responsible_person_or_team text,
    meeting_notes text,
    created_by uuid,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists idx_experiment_report_contexts_run_lang
    on public.experiment_report_contexts (run_id, language);

create index if not exists idx_experiment_report_contexts_experiment
    on public.experiment_report_contexts (experiment_id, updated_at desc);

alter table public.experiment_report_contexts enable row level security;

drop policy if exists "experiment_report_contexts_staff_select" on public.experiment_report_contexts;
create policy "experiment_report_contexts_staff_select"
    on public.experiment_report_contexts
    for select
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
        or exists (
            select 1
            from public.profiles
            where profiles.id = auth.uid()
              and profiles.role = 'admin'
        )
    );

drop policy if exists "experiment_report_contexts_staff_write" on public.experiment_report_contexts;
create policy "experiment_report_contexts_staff_write"
    on public.experiment_report_contexts
    for all
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
        or exists (
            select 1
            from public.profiles
            where profiles.id = auth.uid()
              and profiles.role = 'admin'
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
        or exists (
            select 1
            from public.profiles
            where profiles.id = auth.uid()
              and profiles.role = 'admin'
        )
    );
