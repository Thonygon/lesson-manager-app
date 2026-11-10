-- Read-only preflight for the effective Supabase schema. Run in the SQL Editor
-- after migrations, then save the result with the beta release record.
-- A failed check blocks invitations. No learner records are returned.
with required_rls(table_name) as (
  values ('profiles'), ('students'), ('classes'), ('payments'),
    ('teacher_assignments'), ('practice_sessions'), ('practice_answers'),
    ('teacher_review_requests'), ('classio_help_tickets'),
    ('classio_legal_acceptances'), ('classio_ai_runtime_approvals'),
    ('user_subscriptions'), ('admin_overrides'),
    ('classio_ai_operations'), ('classio_provider_attempts')
), rls_checks as (
  select 'RLS public.' || table_name as check_name,
    coalesce(c.relrowsecurity, false) as passed
  from required_rls r
  left join pg_class c on c.oid = to_regclass('public.' || r.table_name)
), service_tables(table_name) as (
  values ('classio_privacy_retention_runs'), ('classio_document_export_events'),
    ('classio_privacy_retention_policies'), ('classio_ai_operations'),
    ('classio_provider_attempts')
), grant_checks as (
  select 'No client read public.' || table_name as check_name,
    case when to_regclass('public.' || table_name) is null then false
      else not has_table_privilege('anon', 'public.' || table_name, 'SELECT')
        and not has_table_privilege('authenticated', 'public.' || table_name, 'SELECT') end as passed
  from service_tables
), storage_checks as (
  select 'Private Storage ' || bucket_name as check_name,
    coalesce((select not b.public from storage.buckets b where b.id = bucket_name), false) as passed
  from (values ('classio-help-screenshots')) as required(bucket_name)
), service_rpcs(function_name) as (
  values ('classio_delete_account_data'), ('classio_admin_set_access'),
    ('classio_admin_account_control'), ('classio_admin_change_staff'),
    ('classio_admin_global_account_metrics'), ('classio_admin_consumption_summary'),
    ('classio_admin_search_accounts'), ('classio_run_privacy_retention'),
    ('classio_apply_practice_regrade'), ('classio_record_app_visit'),
    ('classio_purge_app_visit_events')
), rpc_checks as (
  -- Include every overload: an unsafe legacy signature must not escape this gate.
  select 'Service-only RPC public.' || function_name as check_name,
    exists (
      select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
      where n.nspname = 'public' and p.proname = function_name
    ) and not exists (
      select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
      where n.nspname = 'public' and p.proname = function_name
        and (has_function_privilege('anon', p.oid, 'EXECUTE')
          or has_function_privilege('authenticated', p.oid, 'EXECUTE'))
    ) as passed
  from service_rpcs
), definer_checks as (
  -- SECURITY DEFINER functions need a fixed search path to prevent object shadowing.
  select 'Pinned search_path public.' || function_name as check_name,
    coalesce(bool_and(p.oid is not null and (not p.prosecdef or
      exists (select 1 from unnest(p.proconfig) setting where setting like 'search_path=%'))),
      false) as passed
  from service_rpcs r
  left join pg_proc p on p.proname = r.function_name
    and p.pronamespace = 'public'::regnamespace
  group by function_name
), suspension_checks as (
  select 'Suspension pre-request hook' as check_name,
    exists (select 1 from pg_db_role_setting s, unnest(s.setconfig) setting
      where s.setrole = 'authenticator'::regrole
        and setting = 'pgrst.db_pre_request=public.classio_check_account_request') as passed
  union all select 'Suspension gate on every public RLS table',
    not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
      where n.nspname = 'public' and c.relkind in ('r','p') and c.relrowsecurity
        and not exists (select 1 from pg_policies p where p.schemaname = 'public'
          and p.tablename = c.relname and p.policyname = 'classio_active_account_gate'
          and p.permissive = 'RESTRICTIVE'))
  union all select 'Suspension gate on Storage objects',
    exists (select 1 from pg_policies p where p.schemaname = 'storage'
      and p.tablename = 'objects' and p.policyname = 'classio_active_account_gate'
      and p.permissive = 'RESTRICTIVE')
  union all select 'Suspension session-revocation trigger',
    exists (select 1 from pg_trigger where tgrelid = 'public.profiles'::regclass
      and tgname = 'classio_revoke_sessions_on_suspend' and not tgisinternal)
)
select check_name, passed
from (
  select * from rls_checks union all select * from grant_checks
  union all select * from storage_checks union all select * from rpc_checks
  union all select * from definer_checks union all select * from suspension_checks
) checks
order by passed, check_name;
