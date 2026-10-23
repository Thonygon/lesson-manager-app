-- Complete all provider attempts, the operation, and the usage log in one
-- database round trip so a failed provider does not exhaust Worker subrequests.
create or replace function public.classio_finish_ai_generation(
    p_operation_id uuid,
    p_user_id text,
    p_status text,
    p_error_kind text,
    p_attempts jsonb,
    p_usage_meta jsonb
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_operation public.classio_ai_operations%rowtype;
    v_attempt jsonb;
    v_attempt_id uuid;
    v_count integer;
    v_feature text;
begin
    if auth.role() <> 'service_role' then
        raise exception 'Service role required' using errcode = '42501';
    end if;
    if p_operation_id is null or p_status not in ('success', 'failed')
       or coalesce(jsonb_typeof(p_attempts), '') <> 'array' or jsonb_array_length(p_attempts) > 2
       or coalesce(jsonb_typeof(p_usage_meta), '') <> 'object'
       or length(coalesce(p_error_kind, '')) > 80 then
        raise exception 'Invalid generation completion' using errcode = '22023';
    end if;
    select * into v_operation from public.classio_ai_operations
    where operation_id = p_operation_id for update;
    if not found or v_operation.actor_user_id::text is distinct from p_user_id
       or v_operation.source <> 'expo' or v_operation.modality <> 'text' then
        raise exception 'Generation operation is unavailable' using errcode = '22023';
    end if;
    if v_operation.status <> 'started' then
        return v_operation.status = p_status;
    end if;

    for v_attempt in select value from jsonb_array_elements(p_attempts) loop
        v_attempt_id := (v_attempt->>'attempt_id')::uuid;
        if v_attempt->>'status' not in ('success', 'failed') then
            raise exception 'Invalid provider attempt status' using errcode = '22023';
        end if;
        update public.classio_provider_attempts set
            status = v_attempt->>'status', finished_at = now(),
            model_reported = nullif(left(v_attempt->>'model_reported', 160), ''),
            http_status = (v_attempt->>'http_status')::smallint,
            provider_request_id = nullif(left(v_attempt->>'provider_request_id', 160), ''),
            input_tokens = (v_attempt->>'input_tokens')::integer,
            output_tokens = (v_attempt->>'output_tokens')::integer,
            cached_input_tokens = (v_attempt->>'cached_input_tokens')::integer,
            reasoning_tokens = (v_attempt->>'reasoning_tokens')::integer,
            usage_observed = coalesce((v_attempt->>'usage_observed')::boolean, false),
            usage_json = coalesce(v_attempt->'usage_json', '{}'::jsonb),
            error_kind = nullif(left(v_attempt->>'error_kind', 80), '')
        where attempt_id = v_attempt_id and operation_id = p_operation_id
          and status = 'started';
        get diagnostics v_count = row_count;
        if v_count <> 1 then
            raise exception 'Generation attempt is unavailable' using errcode = '22023';
        end if;
    end loop;
    update public.classio_ai_operations set status = p_status, finished_at = now(),
        error_kind = nullif(p_error_kind, '') where operation_id = p_operation_id;

    if p_user_id is not null then
        v_feature := case v_operation.feature_name
            when 'generate_plan' then 'quick_lesson_ai'
            when 'generate_worksheet' then 'quick_worksheet_ai'
            when 'generate_exam' then 'quick_exam_ai'
            when 'generate_program' then 'learning_program_ai'
            else null end;
        if v_feature is null then
            raise exception 'Unknown generation feature' using errcode = '22023';
        end if;
        insert into public.ai_usage_logs(user_id, feature_name, status, meta_json, created_at)
        values (p_user_id::uuid, v_feature, p_status, p_usage_meta, now());
    end if;
    return true;
end;
$$;

revoke all on function public.classio_finish_ai_generation(uuid, text, text, text, jsonb, jsonb)
    from public, anon, authenticated;
grant execute on function public.classio_finish_ai_generation(uuid, text, text, text, jsonb, jsonb)
    to service_role;
