-- A purpose-specific retention registry. All policies start paused and with
-- no period: no deletion starts until an accountable human approves one.
-- Teacher payments, classes and profiles are deliberately outside the purge
-- allowlist. This migration creates no destructive trigger.
create table if not exists public.classio_privacy_retention_policies (
    family text primary key,
    purpose text not null,
    retention_days integer check (retention_days between 1 and 3650),
    status text not null default 'paused' check (status in ('paused', 'approved', 'manual_review')),
    legal_hold boolean not null default false,
    approved_by uuid references auth.users(id),
    approved_at timestamptz,
    rationale text,
    updated_at timestamptz not null default now(),
    check (status <> 'approved' or (retention_days is not null and approved_by is not null and approved_at is not null and length(coalesce(rationale, '')) >= 12))
);
insert into public.classio_privacy_retention_policies (family, purpose, status) values
    ('ai_usage_logs', 'Short-lived AI quota and prompt-version diagnostics', 'paused'),
    ('diagnostics', 'Application error diagnosis after case resolution', 'paused'),
    ('export_events', 'Document download handoff telemetry', 'paused'),
    ('guest_quota', 'Anonymous Explorer daily abuse control', 'paused'),
    ('exposure_events', 'Recommendation outcome telemetry', 'paused'),
    ('generation_feedback_events', 'History of generation quality feedback', 'paused'),
    ('teacher_relevance_events', 'History of teacher relevance feedback', 'paused'),
    ('recommendation_exposures', 'Recommendation decision lineage; linked feedback needs separate review', 'manual_review'),
    ('generated_images', 'Saved educational image assets and referenced Storage objects', 'manual_review'),
    ('ml_artifacts', 'Validated model evidence and row-level experiment files', 'manual_review'),
    ('teacher_payments', 'Teacher administrative payment records', 'manual_review'),
    ('classes', 'Teacher lesson and schedule records', 'manual_review'),
    ('profiles', 'Account and role records', 'manual_review')
on conflict (family) do nothing;

create table if not exists public.classio_privacy_retention_runs (
    id bigint generated always as identity primary key,
    family text not null,
    cutoff_at timestamptz not null,
    rows_deleted integer not null check (rows_deleted >= 0),
    applied_at timestamptz not null default now()
);
create index if not exists classio_privacy_retention_runs_applied_idx
    on public.classio_privacy_retention_runs(applied_at desc);

alter table public.classio_privacy_retention_policies enable row level security;
alter table public.classio_privacy_retention_runs enable row level security;
revoke all on public.classio_privacy_retention_policies, public.classio_privacy_retention_runs from public, anon, authenticated;
grant select, insert, update on public.classio_privacy_retention_policies to service_role;
grant select, insert on public.classio_privacy_retention_runs to service_role;
grant usage, select on sequence public.classio_privacy_retention_runs_id_seq to service_role;

create or replace function public.classio_run_privacy_retention(p_apply boolean default false)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
    v_policy record;
    v_table text;
    v_time_column text;
    v_cutoff timestamptz;
    v_count integer;
    v_result jsonb := '[]'::jsonb;
    v_extra text;
begin
    if coalesce(auth.role(), '') <> 'service_role' and session_user <> 'postgres' then
        raise exception 'Service role required' using errcode = '42501';
    end if;
    for v_policy in select * from public.classio_privacy_retention_policies order by family loop
        v_table := case v_policy.family
            when 'ai_usage_logs' then 'ai_usage_logs'
            when 'diagnostics' then 'application_diagnostic_events'
            when 'export_events' then 'classio_document_export_events'
            when 'guest_quota' then 'classio_guest_generation_daily'
            when 'exposure_events' then 'resource_exposure_events'
            when 'generation_feedback_events' then 'classio_generation_intent_feedback_events'
            when 'teacher_relevance_events' then 'classio_teacher_relevance_feedback_events'
            else null end;
        if v_table is null or v_policy.retention_days is null then
            v_result := v_result || jsonb_build_array(jsonb_build_object('family', v_policy.family, 'status', v_policy.status, 'eligible', null));
            continue;
        end if;
        v_time_column := case v_policy.family
            when 'diagnostics' then 'last_seen_at'
            when 'export_events' then 'started_at'
            when 'exposure_events' then 'event_at'
            else 'created_at' end;
        v_extra := case when v_policy.family = 'diagnostics' then ' and status in (''resolved'', ''ignored'')' else '' end;
        v_cutoff := now() - make_interval(days => v_policy.retention_days);
        execute format('select count(*) from public.%I where %I < $1%s', v_table, v_time_column, v_extra)
            into v_count using v_cutoff;
        if p_apply and v_policy.status = 'approved' and not v_policy.legal_hold then
            execute format('delete from public.%I where %I < $1%s', v_table, v_time_column, v_extra)
                using v_cutoff;
            get diagnostics v_count = row_count;
            insert into public.classio_privacy_retention_runs(family, cutoff_at, rows_deleted)
                values (v_policy.family, v_cutoff, v_count);
        end if;
        v_result := v_result || jsonb_build_array(jsonb_build_object(
            'family', v_policy.family, 'status', v_policy.status,
            'legal_hold', v_policy.legal_hold, 'eligible', v_count,
            'applied', p_apply and v_policy.status = 'approved' and not v_policy.legal_hold));
    end loop;
    return v_result;
end;
$$;
revoke all on function public.classio_run_privacy_retention(boolean) from public, anon, authenticated;
grant execute on function public.classio_run_privacy_retention(boolean) to service_role;

-- The cron can run safely before a policy is approved: all families are paused.
select cron.schedule('classio-purpose-retention', '20 4 * * *',
    $$select public.classio_run_privacy_retention(true)$$);
