-- Resolve the active plan, reserve one provider call, and start its economic
-- records in a single database round trip from the Expo Worker.
create or replace function public.classio_begin_ai_generation_attempt(
    p_user_id text,
    p_profile_plan text,
    p_feature_name text,
    p_provider text,
    p_model text,
    p_operation_id uuid,
    p_attempt_id uuid,
    p_attempt_no integer
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_subscription public.user_subscriptions%rowtype;
    v_plan public.plans%rowtype;
    v_plan_id text;
    v_default_limit integer;
    v_limit integer;
    v_raw_limit text;
    v_reservation jsonb;
begin
    if auth.role() <> 'service_role' then
        raise exception 'Service role required' using errcode = '42501';
    end if;
    if p_user_id is null or p_user_id !~ '^[0-9a-fA-F-]{36}$'
       or p_feature_name not in ('generate_plan', 'generate_worksheet', 'generate_exam', 'generate_program')
       or p_provider not in ('openrouter', 'gemini', 'openai')
       or length(coalesce(p_model, '')) not between 1 and 160
       or p_operation_id is null or p_attempt_id is null
       or p_attempt_no not between 1 and 2 then
        raise exception 'Invalid generation attempt' using errcode = '22023';
    end if;

    select * into v_subscription from public.user_subscriptions
    where user_id = p_user_id limit 1;
    if found and (v_subscription.manual_override is true or lower(coalesce(v_subscription.subscription_status, '')) in ('active', 'trialing')) then
        v_plan_id := coalesce(v_subscription.plan_id, 'free');
    else
        v_plan_id := coalesce(nullif(p_profile_plan, ''), 'free');
    end if;
    select * into v_plan from public.plans where id = v_plan_id and active is true limit 1;
    if not found then
        v_plan_id := 'free';
        v_plan := null;
    end if;
    if v_plan.features_json->>'ai_tools' = 'false' then
        return jsonb_build_object('allowed', false, 'status', 403, 'reason', 'permission_blocked');
    end if;
    v_default_limit := case v_plan_id when 'teacher_pro' then 250 when 'school' then 2000 when 'beta_lifetime' then 1000 else 10 end;
    v_raw_limit := v_plan.limits_json->>'ai_generations';
    v_limit := case when v_raw_limit ~ '^[0-9]{1,8}$' then v_raw_limit::integer else v_default_limit end;
    v_reservation := public.classio_reserve_ai_generation(p_user_id, v_limit);
    if (v_reservation->>'allowed')::boolean is not true then
        return jsonb_build_object('allowed', false, 'status', 429, 'reason', 'limit_reached', 'used', v_reservation->'used', 'limit', v_limit);
    end if;

    if p_attempt_no = 1 then
        insert into public.classio_ai_operations(operation_id, actor_user_id, source, feature_name, modality, status)
        values (p_operation_id, p_user_id::uuid, 'expo', p_feature_name, 'text', 'started');
    elsif not exists (
        select 1 from public.classio_ai_operations
        where operation_id = p_operation_id and actor_user_id = p_user_id::uuid
          and feature_name = p_feature_name and status = 'started'
    ) then
        raise exception 'Generation operation is unavailable' using errcode = '22023';
    end if;
    insert into public.classio_provider_attempts(attempt_id, operation_id, attempt_no, provider, model_requested, modality, status)
    values (p_attempt_id, p_operation_id, p_attempt_no, p_provider, p_model, 'text', 'started');
    return jsonb_build_object('allowed', true, 'used', v_reservation->'used', 'limit', v_limit);
end;
$$;

revoke all on function public.classio_begin_ai_generation_attempt(text, text, text, text, text, uuid, uuid, integer)
    from public, anon, authenticated;
grant execute on function public.classio_begin_ai_generation_attempt(text, text, text, text, text, uuid, uuid, integer)
    to service_role;
