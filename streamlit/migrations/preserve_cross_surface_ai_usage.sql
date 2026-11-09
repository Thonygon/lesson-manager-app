-- Both Expo and Streamlit reserve against usage_tracking. Keep that shared
-- counter authoritative for the current month while recording Expo successes
-- separately for historical delivery reporting. This migration follows
-- smart_tool_success_quota.sql; it does not rewrite existing usage or charges.
create or replace function public.classio_begin_smart_tool_attempt(
  p_user_id text, p_profile_plan text, p_feature_name text,
  p_provider text, p_model text, p_operation_id uuid, p_attempt_id uuid,
  p_attempt_no integer, p_quota_eligible boolean
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
  v_subscription public.user_subscriptions%rowtype;
  v_plan public.plans%rowtype;
  v_plan_id text;
  v_limit integer;
  v_raw_limit text;
  v_used integer := 0;
  v_reset_date date;
  v_pending integer := 0;
  v_month timestamptz := date_trunc('month', now() at time zone 'UTC') at time zone 'UTC';
begin
  if auth.role() <> 'service_role' then raise exception 'Service role required' using errcode='42501'; end if;
  if p_user_id is null or p_user_id !~ '^[0-9a-fA-F-]{36}$'
     or p_feature_name not in ('generate_plan','generate_worksheet','generate_exam','generate_program')
     or p_provider not in ('openrouter','gemini','openai')
     or length(coalesce(p_model,'')) not between 1 and 160
     or p_operation_id is null or p_attempt_id is null
     or p_attempt_no not between 1 and 2 or p_quota_eligible is null
     or (p_feature_name <> 'generate_program' and p_quota_eligible is not true) then
    raise exception 'Invalid Smart Tool attempt' using errcode='22023';
  end if;
  if p_attempt_no = 1 then
    select * into v_subscription from public.user_subscriptions where user_id=p_user_id limit 1;
    if found and (v_subscription.manual_override is true or lower(coalesce(v_subscription.subscription_status,'')) in ('active','trialing')) then
      v_plan_id := coalesce(v_subscription.plan_id,'free');
    else v_plan_id := coalesce(nullif(p_profile_plan,''),'free'); end if;
    select * into v_plan from public.plans where id=v_plan_id and active is true limit 1;
    if not found then v_plan_id:='free'; v_plan:=null; end if;
    if v_plan.features_json->>'ai_tools'='false' then
      return jsonb_build_object('allowed',false,'status',403,'reason','permission_blocked');
    end if;
    v_limit := case v_plan_id when 'teacher_pro' then 250 when 'school' then 2000 when 'beta_lifetime' then 1000 else 10 end;
    v_raw_limit := v_plan.limits_json->>'ai_generations';
    if v_raw_limit ~ '^[0-9]{1,8}$' then v_limit:=v_raw_limit::integer; end if;
    if p_quota_eligible then
      insert into public.usage_tracking(user_id,ai_generations,monthly_reset_date)
        values(p_user_id,0,(now() at time zone 'UTC')::date)
        on conflict(user_id) do nothing;
      select ai_generations,monthly_reset_date into v_used,v_reset_date
        from public.usage_tracking where user_id=p_user_id for update;
      if v_reset_date is null or v_reset_date < date_trunc('month',now() at time zone 'UTC')::date then
        v_used:=0;
        update public.usage_tracking set ai_generations=0,
          monthly_reset_date=(now() at time zone 'UTC')::date,updated_at=now()
          where user_id=p_user_id;
      end if;
      select count(*) into v_pending from public.classio_ai_operations
        where actor_user_id=p_user_id::uuid and quota_policy_version='smart_tool_success_v1'
          and quota_eligible and status='started' and started_at>=v_month
          and started_at>now()-interval '15 minutes';
      if v_used+v_pending>=v_limit then
        return jsonb_build_object('allowed',false,'status',429,'reason','limit_reached','used',v_used,'pending',v_pending,'limit',v_limit);
      end if;
    end if;
    insert into public.classio_ai_operations(operation_id,actor_user_id,source,feature_name,modality,status,quota_policy_version,quota_eligible)
      values(p_operation_id,p_user_id::uuid,'expo',p_feature_name,'text','started','smart_tool_success_v1',p_quota_eligible);
  elsif not exists (
    select 1 from public.classio_ai_operations where operation_id=p_operation_id
      and actor_user_id=p_user_id::uuid and feature_name=p_feature_name
      and status='started' and quota_policy_version='smart_tool_success_v1'
      and quota_eligible=p_quota_eligible
  ) then raise exception 'Generation operation is unavailable' using errcode='22023'; end if;
  insert into public.classio_provider_attempts(attempt_id,operation_id,attempt_no,provider,model_requested,modality,status)
    values(p_attempt_id,p_operation_id,p_attempt_no,p_provider,p_model,'text','started');
  return jsonb_build_object('allowed',true,'used',v_used,'limit',v_limit);
end;
$$;
revoke all on function public.classio_begin_smart_tool_attempt(text,text,text,text,text,uuid,uuid,integer,boolean)
  from public,anon,authenticated;
grant execute on function public.classio_begin_smart_tool_attempt(text,text,text,text,text,uuid,uuid,integer,boolean)
  to service_role;

create or replace function public.classio_charge_smart_tool_success()
returns trigger language plpgsql security definer set search_path='' as $$
begin
  if old.status <> 'started' or new.status <> 'success'
     or new.quota_policy_version <> 'smart_tool_success_v1'
     or not new.quota_eligible or new.actor_user_id is null then return new; end if;
  insert into public.classio_smart_tool_quota_charges(operation_id,user_id,feature_name,charged_at)
    values(new.operation_id,new.actor_user_id,new.feature_name,coalesce(new.finished_at,now()))
    on conflict(operation_id) do nothing;
  -- The row update serializes with Streamlit's classio_reserve_ai_generation.
  -- An already-finished operation does not reach this trigger twice.
  update public.usage_tracking
    set ai_generations=case
          when monthly_reset_date >= date_trunc('month',now() at time zone 'UTC')::date
          then ai_generations+1 else 1 end,
        monthly_reset_date=(now() at time zone 'UTC')::date,
        updated_at=now()
    where user_id=new.actor_user_id::text;
  return new;
end;
$$;

-- Confirm that the shared counter and both function definitions exist.
do $$ begin
  if to_regprocedure('public.classio_reserve_ai_generation(text,integer)') is null
     or to_regprocedure('public.classio_begin_smart_tool_attempt(text,text,text,text,text,uuid,uuid,integer,boolean)') is null
     or to_regprocedure('public.classio_charge_smart_tool_success()') is null then
    raise exception 'Cross-surface AI quota functions are missing';
  end if;
end $$;
