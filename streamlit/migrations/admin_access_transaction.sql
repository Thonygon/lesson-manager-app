-- Apply access and subscription changes with the mandatory audit in one transaction.
create or replace function public.classio_admin_set_access(
    p_actor_id text,
    p_target_id text,
    p_role text,
    p_plan_id text,
    p_subscription_status text,
    p_can_teach boolean,
    p_can_study boolean,
    p_account_status text,
    p_active_mode text,
    p_notes text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_now timestamptz := now();
begin
    if auth.role() <> 'service_role' then
        raise exception 'Service role required' using errcode = '42501';
    end if;
    if not exists (select 1 from public.profiles where user_id = p_actor_id and role = 'admin') then
        raise exception 'Admin access required' using errcode = '42501';
    end if;
    if p_actor_id = p_target_id and (p_role <> 'admin' or p_account_status <> 'active') then
        raise exception 'Admin cannot remove or suspend own access' using errcode = '22023';
    end if;
    if p_role not in ('teacher','student','school_admin','admin')
       or p_subscription_status not in ('free','active','trialing','past_due','canceled','cancelled','expired')
       or p_account_status not in ('active','suspended')
       or p_active_mode not in ('teacher','student','admin','developer_workspace')
       or p_can_teach is null or p_can_study is null
       or (p_active_mode = 'teacher' and not p_can_teach)
       or (p_active_mode = 'student' and not p_can_study)
       or (p_active_mode = 'admin' and p_role <> 'admin')
       or length(coalesce(p_notes,'')) > 1000 then
        raise exception 'Invalid access settings' using errcode = '22023';
    end if;
    perform 1 from public.profiles where user_id = p_target_id for update;
    if not found or not exists (select 1 from public.plans where id = p_plan_id and active = true) then
        raise exception 'Account or plan unavailable' using errcode = '22023';
    end if;
    if p_active_mode = 'developer_workspace' and p_role <> 'admin'
       and not exists (select 1 from public.user_staff_roles
                       where user_id = p_target_id::uuid and is_active = true
                       and role_key in ('developer','data_scientist')) then
        raise exception 'Developer workspace requires active staff role' using errcode = '22023';
    end if;

    insert into public.user_subscriptions(user_id, plan_id, subscription_status, manual_override, updated_at)
    values (p_target_id, p_plan_id, p_subscription_status, true, v_now)
    on conflict (user_id) do update set plan_id = excluded.plan_id,
        subscription_status = excluded.subscription_status, manual_override = true, updated_at = v_now;

    update public.profiles set role = p_role,
        primary_role = case when p_can_teach then 'teacher' else 'student' end,
        can_teach = p_can_teach, can_study = p_can_study, last_active_mode = p_active_mode,
        account_status = p_account_status, admin_notes = p_notes,
        current_plan = p_plan_id, subscription_status = p_subscription_status
    where user_id = p_target_id;

    insert into public.admin_overrides(user_id, override_type, reason, created_by, created_at)
    values (p_target_id, 'role_access',
            format('role=%s; can_teach=%s; can_study=%s; mode=%s; account=%s; plan=%s; status=%s. %s',
                   p_role, p_can_teach, p_can_study, p_active_mode, p_account_status,
                   p_plan_id, p_subscription_status, coalesce(p_notes,'')),
            p_actor_id, v_now);
    return true;
end;
$$;
revoke all on function public.classio_admin_set_access(text,text,text,text,text,boolean,boolean,text,text,text) from public, anon, authenticated;
grant execute on function public.classio_admin_set_access(text,text,text,text,text,boolean,boolean,text,text,text) to service_role;
