-- Record interrupted AI operations without inventing provider outcomes or cost.
-- This migration never updates operations, attempts, payments, classes or profiles.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';

create table if not exists public.classio_ai_reconciliation_cases (
    operation_id uuid primary key references public.classio_ai_operations(operation_id) on delete restrict,
    first_detected_at timestamptz not null default now(),
    last_observed_at timestamptz not null default now(),
    review_state text not null default 'unknown' check (review_state in ('unknown', 'provider_confirmed_success', 'provider_confirmed_failure')),
    reviewed_at timestamptz,
    evidence_reference text,
    check (evidence_reference is null or length(evidence_reference) <= 240),
    check ((review_state = 'unknown' and reviewed_at is null)
        or (review_state <> 'unknown' and reviewed_at is not null and evidence_reference is not null))
);

create index if not exists classio_ai_reconciliation_cases_last_seen_idx
    on public.classio_ai_reconciliation_cases(last_observed_at desc);
alter table public.classio_ai_reconciliation_cases enable row level security;
revoke all on public.classio_ai_reconciliation_cases from public, anon, authenticated;
grant select on public.classio_ai_reconciliation_cases to service_role;

create or replace function public.classio_scan_stale_ai_operations()
returns integer
language plpgsql security definer set search_path = '' as $$
declare v_detected integer;
begin
    -- A provider call is bounded to 75 seconds; 20 minutes leaves room for
    -- completion telemetry retries before a case is created.
    insert into public.classio_ai_reconciliation_cases(operation_id)
    select operation_id from public.classio_ai_operations
    where status = 'started' and started_at < now() - interval '20 minutes'
    on conflict (operation_id) do update
       set last_observed_at = now()
       where public.classio_ai_reconciliation_cases.review_state = 'unknown';
    get diagnostics v_detected = row_count;
    return v_detected;
end;
$$;
revoke all on function public.classio_scan_stale_ai_operations() from public, anon, authenticated;
grant execute on function public.classio_scan_stale_ai_operations() to service_role;

create or replace function public.classio_record_ai_reconciliation_evidence(
    p_operation_id uuid, p_result text, p_reference text
) returns boolean
language plpgsql security definer set search_path = '' as $$
declare v_case public.classio_ai_reconciliation_cases%rowtype;
begin
    if auth.role() <> 'service_role' then
        raise exception 'Service role required' using errcode = '42501';
    end if;
    if p_operation_id is null or p_result not in ('provider_confirmed_success', 'provider_confirmed_failure')
       or length(trim(coalesce(p_reference, ''))) < 8 or length(p_reference) > 240 then
        raise exception 'Provider evidence reference required' using errcode = '22023';
    end if;
    select * into v_case from public.classio_ai_reconciliation_cases
    where operation_id = p_operation_id for update;
    if not found then
        raise exception 'Reconciliation case unavailable' using errcode = '22023';
    end if;
    if v_case.review_state <> 'unknown' then
        return v_case.review_state = p_result and v_case.evidence_reference = trim(p_reference);
    end if;
    update public.classio_ai_reconciliation_cases
    set review_state = p_result, reviewed_at = now(), evidence_reference = trim(p_reference)
    where operation_id = p_operation_id;
    return true;
end;
$$;
revoke all on function public.classio_record_ai_reconciliation_evidence(uuid, text, text)
    from public, anon, authenticated;
grant execute on function public.classio_record_ai_reconciliation_evidence(uuid, text, text)
    to service_role;

create extension if not exists pg_cron with schema extensions;
select cron.schedule('classio-ai-stale-operations', '*/30 * * * *',
    'select public.classio_scan_stale_ai_operations()');
select public.classio_scan_stale_ai_operations();
commit;
