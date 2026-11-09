-- A plan unit is one successfully delivered Smart Tool resource, independent
-- of provider retries. Program units/refinement/covers remain economic events.
alter table public.classio_ai_operations
  add column if not exists quota_policy_version text,
  add column if not exists quota_eligible boolean not null default false;

create table if not exists public.classio_smart_tool_quota_charges (
  operation_id uuid primary key references public.classio_ai_operations(operation_id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete restrict,
  feature_name text not null,
  charged_at timestamptz not null default now(),
  policy_version text not null default 'smart_tool_success_v1',
  check (feature_name in ('generate_plan','generate_worksheet','generate_exam','generate_program'))
);
create index if not exists classio_smart_tool_quota_user_date
  on public.classio_smart_tool_quota_charges(user_id, charged_at desc);
alter table public.classio_smart_tool_quota_charges enable row level security;
revoke all on public.classio_smart_tool_quota_charges from public, anon, authenticated;
grant select, insert on public.classio_smart_tool_quota_charges to service_role;

-- Existing successes count across all periods. Historic program operations
-- are charged only when their skeleton link proves they were the initial plan.
insert into public.classio_smart_tool_quota_charges(operation_id,user_id,feature_name,charged_at)
select o.operation_id,o.actor_user_id,o.feature_name,coalesce(o.finished_at,o.started_at)
from public.classio_ai_operations o
where o.actor_user_id is not null and o.source='expo' and o.status='success'
  and (o.feature_name in ('generate_plan','generate_worksheet','generate_exam')
       or (o.feature_name='generate_program' and exists (
         select 1 from public.classio_program_generation_operations p
         where p.operation_id=o.operation_id and p.unit_number is null)))
on conflict (operation_id) do nothing;

-- A support reset grants an auditable credit; it never erases generation history.
create table if not exists public.classio_smart_tool_quota_credits (
  override_id text primary key,
  user_id uuid not null references auth.users(id) on delete restrict,
  credited_count integer not null check(credited_count >= 0),
  credited_at timestamptz not null default now(),
  policy_version text not null default 'smart_tool_success_v1'
);
create index if not exists classio_smart_tool_quota_credits_user_date
  on public.classio_smart_tool_quota_credits(user_id,credited_at desc);
alter table public.classio_smart_tool_quota_credits enable row level security;
revoke all on public.classio_smart_tool_quota_credits from public,anon,authenticated;
grant select,insert on public.classio_smart_tool_quota_credits to service_role;

create or replace function public.classio_credit_smart_tool_reset()
returns trigger language plpgsql security definer set search_path='' as $$
declare v_charges integer; v_credits integer;
begin
  if new.override_type <> 'reset_usage' then return new; end if;
  select count(*) into v_charges from public.classio_smart_tool_quota_charges
    where user_id=new.user_id::uuid and charged_at>=date_trunc('month',now() at time zone 'UTC') at time zone 'UTC';
  select coalesce(sum(credited_count),0) into v_credits from public.classio_smart_tool_quota_credits
    where user_id=new.user_id::uuid and credited_at>=date_trunc('month',now() at time zone 'UTC') at time zone 'UTC';
  insert into public.classio_smart_tool_quota_credits(override_id,user_id,credited_count)
    values(new.id::text,new.user_id::uuid,greatest(0,v_charges-v_credits)) on conflict(override_id) do nothing;
  return new;
end;
$$;
drop trigger if exists classio_credit_smart_tool_reset on public.admin_overrides;
create trigger classio_credit_smart_tool_reset after insert on public.admin_overrides
for each row execute function public.classio_credit_smart_tool_reset();

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

create or replace function public.classio_charge_smart_tool_success()
returns trigger language plpgsql security definer set search_path='' as $$
declare v_used integer;
begin
  if old.status <> 'started' or new.status <> 'success'
     or new.quota_policy_version <> 'smart_tool_success_v1'
     or not new.quota_eligible or new.actor_user_id is null then return new; end if;
  insert into public.classio_smart_tool_quota_charges(operation_id,user_id,feature_name,charged_at)
    values(new.operation_id,new.actor_user_id,new.feature_name,coalesce(new.finished_at,now()))
    on conflict(operation_id) do nothing;
  select count(*) into v_used from public.classio_smart_tool_quota_charges
    where user_id=new.actor_user_id
      and charged_at>=date_trunc('month', now() at time zone 'UTC') at time zone 'UTC';
  select greatest(0,v_used-coalesce(sum(credited_count),0)) into v_used
    from public.classio_smart_tool_quota_credits
    where user_id=new.actor_user_id
      and credited_at>=date_trunc('month', now() at time zone 'UTC') at time zone 'UTC';
  update public.usage_tracking set ai_generations=v_used,
    monthly_reset_date=(now() at time zone 'UTC')::date,updated_at=now()
    where user_id=new.actor_user_id::text;
  return new;
end;
$$;
drop trigger if exists classio_charge_smart_tool_success on public.classio_ai_operations;
create trigger classio_charge_smart_tool_success
after update of status on public.classio_ai_operations
for each row execute function public.classio_charge_smart_tool_success();

-- Support metadata only; no prompt, resource content, student response or IP.
create or replace function public.classio_admin_consumption_summary(p_user_id uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_result jsonb;
begin
  if auth.role()<>'service_role' then raise exception 'Service role required' using errcode='42501'; end if;
  if p_user_id is null then raise exception 'User required' using errcode='22023'; end if;
  with periods as (
    select 'month'::text label, date_trunc('month',now() at time zone 'UTC') at time zone 'UTC' from_time
    union all select 'year',date_trunc('year',now() at time zone 'UTC') at time zone 'UTC'
    union all select 'all', '-infinity'::timestamptz
  ), counts as (
    select p.label,
      (select count(*) from public.classio_smart_tool_quota_charges c
       where c.user_id=p_user_id and c.charged_at>=p.from_time) delivered_resources,
      (select greatest(0,
         (select count(*) from public.classio_smart_tool_quota_charges c where c.user_id=p_user_id and c.charged_at>=p.from_time)
         - (select coalesce(sum(credited_count),0) from public.classio_smart_tool_quota_credits c where c.user_id=p_user_id and c.credited_at>=p.from_time))) quota_used,
      (select count(*) from public.classio_ai_operations o
       where o.actor_user_id=p_user_id and o.started_at>=p.from_time) ai_operations,
      (select count(*) from public.classio_ai_operations o
       where o.actor_user_id=p_user_id and o.started_at>=p.from_time and o.status='failed') failed_operations,
      (select count(*) from public.classio_ai_operations o
       where o.actor_user_id=p_user_id and o.started_at>=p.from_time and o.feature_name like 'refine_%') refinements,
      (select count(*) from public.classio_ai_operations o
       where o.actor_user_id=p_user_id and o.started_at>=p.from_time
         and o.feature_name='generate_program' and o.quota_policy_version='smart_tool_success_v1'
         and not o.quota_eligible) program_unit_events,
      (select count(*) from public.classio_ai_operations o
       where o.actor_user_id=p_user_id and o.started_at>=p.from_time and o.modality='image') image_events,
      (select count(*) from public.classio_provider_attempts a
       join public.classio_ai_operations o on o.operation_id=a.operation_id
       where o.actor_user_id=p_user_id and a.started_at>=p.from_time) provider_attempts,
      (select count(*) from public.classio_document_export_events e
       where e.actor_user_id=p_user_id and e.started_at>=p.from_time
         and e.format='pdf' and e.status='handoff_requested') pdf_handoffs,
      (select count(*) from public.classio_document_export_events e
       where e.actor_user_id=p_user_id and e.started_at>=p.from_time
         and e.format='docx' and e.status='handoff_requested') word_handoffs,
      (select count(*) from public.classio_document_export_events e
       where e.actor_user_id=p_user_id and e.started_at>=p.from_time
         and e.status='failed') failed_exports
    from periods p
  )
  select jsonb_build_object('as_of',now(),'timezone','UTC',
    'periods',coalesce(jsonb_agg(to_jsonb(counts) order by
      case counts.label when 'month' then 1 when 'year' then 2 else 3 end),'[]'::jsonb))
    into v_result from counts;
  return v_result;
end;
$$;
revoke all on function public.classio_admin_consumption_summary(uuid) from public,anon,authenticated;
grant execute on function public.classio_admin_consumption_summary(uuid) to service_role;

create or replace function public.classio_admin_search_accounts(p_query text)
returns table(user_id uuid,display_name text,email text,role text,account_status text,current_plan text)
language plpgsql security definer set search_path='' as $$
begin
  if auth.role()<>'service_role' then raise exception 'Service role required' using errcode='42501'; end if;
  if length(trim(coalesce(p_query,'')))<2 or length(p_query)>100 then
    raise exception 'Search must contain 2 to 100 characters' using errcode='22023';
  end if;
  return query select p.user_id::uuid,p.display_name::text,p.email::text,p.role::text,
    p.account_status::text,p.current_plan::text
  from public.profiles p
  where p.email ilike '%'||trim(p_query)||'%'
     or p.display_name ilike '%'||trim(p_query)||'%'
     or p.user_id::text=p_query
  order by p.created_at desc limit 20;
end;
$$;
revoke all on function public.classio_admin_search_accounts(text) from public,anon,authenticated;
grant execute on function public.classio_admin_search_accounts(text) to service_role;

-- One authenticated app session event, with no IP, path or device fingerprint.
-- The short-lived raw rows deduplicate retries; only country/day totals persist.
create table if not exists public.classio_app_visit_events (
  event_id uuid primary key,
  actor_user_id uuid not null references auth.users(id) on delete cascade,
  country_code text not null check(country_code ~ '^[A-Z]{2}$'),
  visited_at timestamptz not null default now()
);
create index if not exists classio_app_visit_actor_date on public.classio_app_visit_events(actor_user_id,visited_at desc);
create index if not exists classio_app_visit_retention on public.classio_app_visit_events(visited_at);
create table if not exists public.classio_app_country_daily (
  visit_day date not null,
  country_code text not null check(country_code ~ '^[A-Z]{2}$'),
  sessions integer not null default 0 check(sessions>=0),
  primary key(visit_day,country_code)
);
alter table public.classio_app_visit_events enable row level security;
alter table public.classio_app_country_daily enable row level security;
revoke all on public.classio_app_visit_events,public.classio_app_country_daily from public,anon,authenticated;
grant select,insert,delete on public.classio_app_visit_events to service_role;
grant select,insert,update on public.classio_app_country_daily to service_role;

create or replace function public.classio_record_app_visit(p_actor uuid,p_event uuid,p_country text)
returns boolean language plpgsql security definer set search_path='' as $$
declare v_rows integer;
begin
  if auth.role()<>'service_role' then raise exception 'Service role required' using errcode='42501'; end if;
  if p_actor is null or p_event is null or p_country !~ '^[A-Z]{2}$' then
    raise exception 'Invalid visit' using errcode='22023'; end if;
  if (select count(*) from public.classio_app_visit_events
      where actor_user_id=p_actor and visited_at>=now()-interval '1 day')>=100 then
    return false;
  end if;
  insert into public.classio_app_visit_events(event_id,actor_user_id,country_code)
    values(p_event,p_actor,p_country) on conflict(event_id) do nothing;
  get diagnostics v_rows=row_count;
  if v_rows=1 then
    insert into public.classio_app_country_daily(visit_day,country_code,sessions)
      values((now() at time zone 'UTC')::date,p_country,1)
      on conflict(visit_day,country_code) do update set sessions=public.classio_app_country_daily.sessions+1;
  end if;
  return v_rows=1;
end;
$$;
revoke all on function public.classio_record_app_visit(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.classio_record_app_visit(uuid,uuid,text) to service_role;

create or replace function public.classio_purge_app_visit_events()
returns void language plpgsql security definer set search_path='' as $$
begin
  if auth.role()<>'service_role' and session_user<>'postgres' then
    raise exception 'Service role required' using errcode='42501'; end if;
  delete from public.classio_app_visit_events where visited_at < now()-interval '30 days';
  delete from public.classio_app_country_daily where visit_day < (now() at time zone 'UTC')::date - 395;
end;
$$;
revoke all on function public.classio_purge_app_visit_events() from public,anon,authenticated;
grant execute on function public.classio_purge_app_visit_events() to service_role;
select cron.schedule('classio-app-visit-retention','35 4 * * *',
  $$select public.classio_purge_app_visit_events()$$);
