-- Streamlit and Expo share the monthly counter. Count Expo operations that
-- already hold a pending slot before granting a Streamlit provider attempt.
-- The usage_tracking row lock serializes this check with Expo's begin RPC.
create or replace function public.classio_reserve_ai_generation(
    p_user_id text,
    p_limit integer
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_used integer;
    v_pending integer;
    v_reset_date date;
    v_today date := (now() at time zone 'UTC')::date;
    v_month timestamptz := date_trunc('month', now() at time zone 'UTC') at time zone 'UTC';
begin
    if auth.role() <> 'service_role' then
        raise exception 'Service role required' using errcode = '42501';
    end if;
    if p_user_id is null or p_user_id = '' or p_limit is null or p_limit < 0 then
        raise exception 'Invalid AI reservation input' using errcode = '22023';
    end if;

    insert into public.usage_tracking (user_id, ai_generations, monthly_reset_date)
    values (p_user_id, 0, v_today)
    on conflict (user_id) do nothing;

    select ai_generations, monthly_reset_date into v_used, v_reset_date
    from public.usage_tracking
    where user_id = p_user_id
    for update;

    if v_reset_date is null or v_reset_date < date_trunc('month', now() at time zone 'UTC')::date then
        v_used := 0;
        update public.usage_tracking
        set ai_generations = 0, monthly_reset_date = v_today, updated_at = now()
        where user_id = p_user_id;
    end if;

    select count(*) into v_pending from public.classio_ai_operations
    where actor_user_id = p_user_id::uuid
      and quota_policy_version = 'smart_tool_success_v1'
      and quota_eligible
      and status = 'started'
      and started_at >= v_month
      and started_at > now() - interval '15 minutes';

    if v_used + v_pending >= p_limit then
        return jsonb_build_object('allowed', false, 'used', v_used, 'pending', v_pending);
    end if;

    update public.usage_tracking
    set ai_generations = v_used + 1, updated_at = now()
    where user_id = p_user_id;
    return jsonb_build_object('allowed', true, 'used', v_used + 1, 'pending', v_pending);
end;
$$;

revoke all on function public.classio_reserve_ai_generation(text, integer)
    from public, anon, authenticated;
grant execute on function public.classio_reserve_ai_generation(text, integer)
    to service_role;
