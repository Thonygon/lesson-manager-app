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
    v_actor_basis text;
    v_actor_hash text;
    v_fingerprint text;
begin
    v_context := jsonb_strip_nulls(jsonb_build_object(
        'resource_type', public.redact_application_diagnostic_text(p_context_json ->> 'resource_type', 80),
        'resource_id', public.redact_application_diagnostic_text(p_context_json ->> 'resource_id', 120),
        'http_status', public.redact_application_diagnostic_text(p_context_json ->> 'http_status', 16),
        'query_name', public.redact_application_diagnostic_text(p_context_json ->> 'query_name', 120),
        'fallback_used', public.redact_application_diagnostic_text(p_context_json ->> 'fallback_used', 16),
        'record_count', public.redact_application_diagnostic_text(p_context_json ->> 'record_count', 24),
        'correlation_id', public.redact_application_diagnostic_text(p_context_json ->> 'correlation_id', 80)
    ));

    v_actor_basis := coalesce(
        nullif(auth.uid()::text, ''),
        nullif(v_context ->> 'correlation_id', ''),
        nullif(p_event_id::text, ''),
        'anonymous'
    );
    v_actor_hash := md5(v_actor_basis);
    v_fingerprint := case
        when coalesce(p_fingerprint, '') ~ '^[0-9a-f]{64}$' then p_fingerprint
        else md5(coalesce(p_component, '') || '|' || coalesce(p_operation, '') || '|' || coalesce(p_exception_type, ''))
    end;

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

    if random() < 0.01 then
        delete from public.application_diagnostic_events
        where last_seen_at < timezone('utc', now()) - interval '90 days';
    end if;

    return query select v_event_id, v_occurrence_count;
end;
$$;

grant execute on function public.record_application_diagnostic(uuid, text, text, text, text, text, text, text, text, text, text, text, jsonb) to anon;
