-- Read-only preflight for the effective Supabase schema. Run in the SQL Editor
-- after migrations, then save the result with the beta release record.
-- A failed check blocks invitations. No learner records are returned.
with required_rls(table_name) as (
  values ('profiles'), ('students'), ('classes'), ('payments'),
    ('teacher_assignments'), ('practice_sessions'), ('practice_answers'),
    ('teacher_review_requests'), ('classio_help_tickets'),
    ('classio_legal_acceptances'), ('classio_ai_runtime_approvals')
), rls_checks as (
  select 'RLS public.' || table_name as check_name,
    coalesce(c.relrowsecurity, false) as passed
  from required_rls r
  left join pg_class c on c.oid = to_regclass('public.' || r.table_name)
), service_tables(table_name) as (
  values ('classio_privacy_retention_runs'), ('classio_document_export_events')
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
), rpc_checks as (
  select 'No client execution of destructive account RPC' as check_name,
    case when to_regprocedure('public.classio_delete_account_data(text)') is null then false
      else not has_function_privilege('anon', 'public.classio_delete_account_data(text)', 'EXECUTE')
        and not has_function_privilege('authenticated', 'public.classio_delete_account_data(text)', 'EXECUTE') end as passed
)
select check_name, passed
from (
  select * from rls_checks union all select * from grant_checks
  union all select * from storage_checks union all select * from rpc_checks
) checks
order by passed, check_name;
