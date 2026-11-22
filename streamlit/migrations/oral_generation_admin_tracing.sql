-- Complete the fifth Smart Tool's economic and administrative trace.
-- This expands allowlists only; existing charges, teaching records and profiles
-- are untouched. Run after smart_tool_success_quota.sql and oral_presentations_beta.sql.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';

alter table public.classio_smart_tool_quota_charges
  drop constraint if exists classio_smart_tool_quota_charges_feature_name_check;
alter table public.classio_smart_tool_quota_charges
  add constraint classio_smart_tool_quota_charges_feature_name_check
  check (feature_name in ('generate_plan','generate_worksheet','generate_exam','generate_program','generate_oral_presentation'));

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
  v_used integer;
  v_pending integer;
  v_month timestamptz := date_trunc('month', now() at time zone 'UTC') at time zone 'UTC';
begin
  if auth.role() <> 'service_role' then raise exception 'Service role required' using errcode='42501'; end if;
  if p_user_id is null or p_user_id !~ '^[0-9a-fA-F-]{36}$'
     or p_feature_name not in ('generate_plan','generate_worksheet','generate_exam','generate_program','generate_oral_presentation')
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
      perform 1 from public.usage_tracking where user_id=p_user_id for update;
      select count(*) into v_used from public.classio_smart_tool_quota_charges
        where user_id=p_user_id::uuid and charged_at>=v_month;
      select greatest(0,v_used-coalesce(sum(credited_count),0)) into v_used
        from public.classio_smart_tool_quota_credits
        where user_id=p_user_id::uuid and credited_at>=v_month;
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
  return jsonb_build_object('allowed',true,'used',coalesce(v_used,0),'limit',v_limit);
end;
$$;
revoke all on function public.classio_begin_smart_tool_attempt(text,text,text,text,text,uuid,uuid,integer,boolean)
  from public,anon,authenticated;
grant execute on function public.classio_begin_smart_tool_attempt(text,text,text,text,text,uuid,uuid,integer,boolean)
  to service_role;

create or replace view public.classio_ai_resource_link_coverage as
select o.feature_name,
  count(*)::bigint as successful_operations,
  count(r.generation_id)::bigint as linked_resources,
  count(*) filter (where r.generation_id is null)::bigint as unlinked_operations,
  max(o.finished_at) as latest_finished_at
from public.classio_ai_operations o
left join public.classio_generation_resources r on r.generation_id = o.operation_id
where o.source = 'expo' and o.actor_user_id is not null and o.modality = 'text'
  and o.status = 'success'
  and o.feature_name in ('generate_plan','generate_worksheet','generate_exam','generate_oral_presentation')
  and o.started_at >= (
    select applied_at from public.app_schema_migrations
    where name = 'link_saved_generation_in_resource_insert.sql'
  )
group by o.feature_name;
revoke all on public.classio_ai_resource_link_coverage from public,anon,authenticated;
grant select on public.classio_ai_resource_link_coverage to service_role;

create or replace function public.classio_record_unsaved_generation_decision(p_operation_id uuid)
returns void language plpgsql security definer set search_path = '' as $$
declare v_operation public.classio_ai_operations%rowtype;
begin
  if auth.uid() is null then raise exception 'Authentication required' using errcode='42501'; end if;
  select * into v_operation from public.classio_ai_operations where operation_id=p_operation_id for update;
  if not found or v_operation.actor_user_id<>auth.uid() or v_operation.source<>'expo'
     or v_operation.modality<>'text' or v_operation.status<>'success'
     or v_operation.feature_name not in ('generate_plan','generate_worksheet','generate_exam','generate_oral_presentation') then
    raise exception 'Generation operation unavailable' using errcode='42501';
  end if;
  if exists (select 1 from public.classio_generation_resources where generation_id=p_operation_id)
     or exists (select 1 from public.lesson_plans where generation_operation_id=p_operation_id)
     or exists (select 1 from public.worksheets where generation_operation_id=p_operation_id)
     or exists (select 1 from public.quick_exams where generation_operation_id=p_operation_id)
     or exists (select 1 from public.oral_presentations where generation_operation_id=p_operation_id) then
    raise exception 'Saved generations cannot be discarded' using errcode='22023';
  end if;
  insert into public.classio_unsaved_generation_decisions(operation_id,actor_user_id,decision)
    values(p_operation_id,auth.uid(),'discarded_by_teacher') on conflict(operation_id) do nothing;
end;
$$;
revoke all on function public.classio_record_unsaved_generation_decision(uuid) from public,anon;
grant execute on function public.classio_record_unsaved_generation_decision(uuid) to authenticated,service_role;

drop trigger if exists classio_guard_discarded_oral on public.oral_presentations;
create trigger classio_guard_discarded_oral before insert on public.oral_presentations
  for each row execute function public.classio_guard_discarded_generation_save();
commit;
