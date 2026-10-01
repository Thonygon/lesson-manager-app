-- Structured, privacy-safe application diagnostics for the Developer Workspace.

create table if not exists public.application_diagnostic_events (
    id bigserial primary key,
    event_id uuid not null default gen_random_uuid() unique,
    fingerprint text not null,
    severity text not null check (severity in ('warning', 'error', 'critical')),
    status text not null default 'open' check (status in ('open', 'acknowledged', 'resolved', 'ignored')),
    component text not null,
    operation text not null,
    page_key text,
    user_face text check (user_face is null or user_face in ('student', 'teacher', 'admin', 'developer', 'unknown')),
    environment text not null default 'production',
    release_version text not null default 'unknown',
    exception_type text,
    safe_message text,
    safe_stack text,
    context_json jsonb not null default '{}'::jsonb,
    actor_user_hash text,
    occurrence_count bigint not null default 1,
    first_seen_at timestamptz not null default timezone('utc', now()),
    last_seen_at timestamptz not null default timezone('utc', now()),
    acknowledged_by uuid references auth.users(id) on delete set null,
    acknowledged_at timestamptz,
    resolved_by uuid references auth.users(id) on delete set null,
    resolved_at timestamptz,
    resolution_note text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (fingerprint, environment, release_version)
);

create index if not exists idx_application_diagnostics_last_seen
    on public.application_diagnostic_events (last_seen_at desc);

create index if not exists idx_application_diagnostics_status_severity
    on public.application_diagnostic_events (status, severity, last_seen_at desc);

create index if not exists idx_application_diagnostics_surface
    on public.application_diagnostic_events (user_face, page_key, last_seen_at desc);

create index if not exists idx_application_diagnostics_release
    on public.application_diagnostic_events (release_version, last_seen_at desc);

create index if not exists idx_application_diagnostics_actor_seen
    on public.application_diagnostic_events (actor_user_hash, last_seen_at desc);

alter table public.application_diagnostic_events enable row level security;

create or replace function public.redact_application_diagnostic_text(p_value text, p_limit integer)
returns text
language sql
immutable
set search_path = public
as $$
    select left(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        coalesce(p_value, ''),
                        '[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',
                        '[redacted-email]',
                        'gi'
                    ),
                    '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}',
                    '[redacted-id]',
                    'g'
                ),
                '(https?://[^[:space:]?]+)\?[^[:space:]]+',
                '\1?[redacted-query]',
                'gi'
            ),
            '(api[_-]?key|authorization|bearer|password|secret|token)[[:space:]]*[:=][[:space:]]*[^[:space:],;]+',
            '\1=[redacted]',
            'gi'
        ),
        greatest(0, least(coalesce(p_limit, 1000), 12000))
    );
$$;

revoke all on function public.redact_application_diagnostic_text(text, integer) from public;

drop policy if exists "application_diagnostics_staff_select" on public.application_diagnostic_events;
create policy "application_diagnostics_staff_select"
    on public.application_diagnostic_events
    for select
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

drop policy if exists "application_diagnostics_developer_update" on public.application_diagnostic_events;
create policy "application_diagnostics_developer_update"
    on public.application_diagnostic_events
    for update
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key = 'developer'
              and user_staff_roles.is_active = true
        )
    )
    with check (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key = 'developer'
              and user_staff_roles.is_active = true
        )
    );

create or replace function public.record_application_diagnostic(
    p_event_id uuid,
    p_fingerprint text,
    p_severity text,
    p_component text,
    p_operation text,
    p_page_key text,
    p_user_face text,
    p_environment text,
    p_release_version text,
    p_exception_type text,
    p_safe_message text,
    p_safe_stack text,
    p_context_json jsonb
)
returns table(captured_event_id uuid, captured_occurrence_count bigint)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_event_id uuid;
    v_occurrence_count bigint;
    v_context jsonb;
    v_actor_hash text;
    v_fingerprint text;
begin
    if auth.uid() is null then
        raise exception 'authentication_required';
    end if;

    v_actor_hash := md5(auth.uid()::text);
    v_fingerprint := case
        when coalesce(p_fingerprint, '') ~ '^[0-9a-f]{64}$' then p_fingerprint
        else md5(coalesce(p_component, '') || '|' || coalesce(p_operation, '') || '|' || coalesce(p_exception_type, ''))
    end;
    v_context := jsonb_strip_nulls(jsonb_build_object(
        'resource_type', public.redact_application_diagnostic_text(p_context_json ->> 'resource_type', 80),
        'resource_id', public.redact_application_diagnostic_text(p_context_json ->> 'resource_id', 120),
        'http_status', public.redact_application_diagnostic_text(p_context_json ->> 'http_status', 16),
        'query_name', public.redact_application_diagnostic_text(p_context_json ->> 'query_name', 120),
        'fallback_used', public.redact_application_diagnostic_text(p_context_json ->> 'fallback_used', 16),
        'record_count', public.redact_application_diagnostic_text(p_context_json ->> 'record_count', 24),
        'correlation_id', public.redact_application_diagnostic_text(p_context_json ->> 'correlation_id', 80)
    ));

    if not exists (
        select 1
        from public.application_diagnostic_events
        where fingerprint = v_fingerprint
          and environment = left(coalesce(nullif(p_environment, ''), 'production'), 40)
          and release_version = left(coalesce(nullif(p_release_version, ''), 'unknown'), 120)
    ) and (
        select count(*)
        from public.application_diagnostic_events
        where actor_user_hash = v_actor_hash
          and last_seen_at >= timezone('utc', now()) - interval '1 minute'
    ) >= 30 then
        return query select coalesce(p_event_id, gen_random_uuid()), 0::bigint;
        return;
    end if;

    insert into public.application_diagnostic_events (
        event_id,
        fingerprint,
        severity,
        component,
        operation,
        page_key,
        user_face,
        environment,
        release_version,
        exception_type,
        safe_message,
        safe_stack,
        context_json,
        actor_user_hash
    ) values (
        coalesce(p_event_id, gen_random_uuid()),
        v_fingerprint,
        case when p_severity in ('warning', 'error', 'critical') then p_severity else 'error' end,
        public.redact_application_diagnostic_text(coalesce(nullif(p_component, ''), 'application'), 120),
        public.redact_application_diagnostic_text(coalesce(nullif(p_operation, ''), 'unknown'), 120),
        nullif(public.redact_application_diagnostic_text(coalesce(p_page_key, ''), 120), ''),
        case when p_user_face in ('student', 'teacher', 'admin', 'developer') then p_user_face else 'unknown' end,
        left(coalesce(nullif(p_environment, ''), 'production'), 40),
        left(coalesce(nullif(p_release_version, ''), 'unknown'), 120),
        nullif(public.redact_application_diagnostic_text(coalesce(p_exception_type, ''), 160), ''),
        nullif(public.redact_application_diagnostic_text(coalesce(p_safe_message, ''), 1000), ''),
        nullif(public.redact_application_diagnostic_text(coalesce(p_safe_stack, ''), 12000), ''),
        v_context,
        v_actor_hash
    )
    on conflict (fingerprint, environment, release_version)
    do update set
        severity = case
            when excluded.severity = 'critical' then 'critical'
            when excluded.severity = 'error' and application_diagnostic_events.severity = 'warning' then 'error'
            else application_diagnostic_events.severity
        end,
        status = case
            when application_diagnostic_events.status in ('resolved', 'ignored') then 'open'
            else application_diagnostic_events.status
        end,
        safe_message = excluded.safe_message,
        safe_stack = excluded.safe_stack,
        context_json = excluded.context_json,
        actor_user_hash = excluded.actor_user_hash,
        occurrence_count = application_diagnostic_events.occurrence_count + 1,
        last_seen_at = timezone('utc', now()),
        resolved_by = null,
        resolved_at = null,
        resolution_note = case
            when application_diagnostic_events.status in ('resolved', 'ignored') then null
            else application_diagnostic_events.resolution_note
        end,
        updated_at = timezone('utc', now())
    returning event_id, occurrence_count into v_event_id, v_occurrence_count;

    -- Keep aggregate diagnostics bounded without adding a separate maintenance service.
    if random() < 0.01 then
        delete from public.application_diagnostic_events
        where last_seen_at < timezone('utc', now()) - interval '90 days';
    end if;

    return query select v_event_id, v_occurrence_count;
end;
$$;

revoke all on function public.record_application_diagnostic(uuid, text, text, text, text, text, text, text, text, text, text, text, jsonb) from public;
grant execute on function public.record_application_diagnostic(uuid, text, text, text, text, text, text, text, text, text, text, text, jsonb) to authenticated;

create or replace function public.update_application_diagnostic_status(
    p_event_id uuid,
    p_status text,
    p_resolution_note text
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    v_now timestamptz := timezone('utc', now());
begin
    if not exists (
        select 1
        from public.user_staff_roles
        where user_staff_roles.user_id = auth.uid()
          and user_staff_roles.role_key = 'developer'
          and user_staff_roles.is_active = true
    ) then
        raise exception 'operational_diagnostics_manage_permission_required';
    end if;

    if p_status not in ('open', 'acknowledged', 'resolved', 'ignored') then
        raise exception 'invalid_operational_diagnostic_status';
    end if;

    update public.application_diagnostic_events
    set
        status = p_status,
        resolution_note = nullif(left(coalesce(p_resolution_note, ''), 1000), ''),
        acknowledged_by = case when p_status = 'acknowledged' then auth.uid() when p_status = 'open' then null else acknowledged_by end,
        acknowledged_at = case when p_status = 'acknowledged' then v_now when p_status = 'open' then null else acknowledged_at end,
        resolved_by = case when p_status in ('resolved', 'ignored') then auth.uid() when p_status = 'open' then null else resolved_by end,
        resolved_at = case when p_status in ('resolved', 'ignored') then v_now when p_status = 'open' then null else resolved_at end,
        updated_at = v_now
    where event_id = p_event_id;

    return found;
end;
$$;

revoke all on function public.update_application_diagnostic_status(uuid, text, text) from public;
grant execute on function public.update_application_diagnostic_status(uuid, text, text) to authenticated;

grant select on public.application_diagnostic_events to authenticated;
revoke insert, delete, update on public.application_diagnostic_events from authenticated;
