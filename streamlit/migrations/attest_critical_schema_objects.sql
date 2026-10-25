-- A checksum row alone does not prove that the migration created its objects.
-- Expose a small service-only catalog check for the recent transactional paths.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';

create or replace function public.classio_critical_schema_objects()
returns jsonb language sql security definer set search_path = '' as $$
    select jsonb_build_object(
        'stale_cases_table', to_regclass('public.classio_ai_reconciliation_cases') is not null,
        'stale_scan_rpc', to_regprocedure('public.classio_scan_stale_ai_operations()') is not null,
        'stale_evidence_rpc', to_regprocedure('public.classio_record_ai_reconciliation_evidence(uuid,text,text)') is not null,
        'stale_scan_cron', exists (
            select 1 from cron.job where jobname = 'classio-ai-stale-operations' and active
        ),
        'oidc_review_rpc', to_regprocedure('public.classio_submit_teacher_review_oidc(bigint,jsonb,text,uuid)') is not null,
        'review_progress_rpc', to_regprocedure('public.classio_refresh_teacher_review_progress(bigint)') is not null,
        'review_progress_trigger', exists (
            select 1 from pg_catalog.pg_trigger t
            join pg_catalog.pg_class c on c.oid = t.tgrelid
            join pg_catalog.pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relname = 'teacher_review_requests'
              and t.tgname = 'classio_teacher_review_progress_commit' and t.tgenabled <> 'D'
        )
    );
$$;

revoke all on function public.classio_critical_schema_objects()
    from public, anon, authenticated;
grant execute on function public.classio_critical_schema_objects() to service_role;
commit;
