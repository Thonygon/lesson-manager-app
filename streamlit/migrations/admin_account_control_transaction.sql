-- Account suspension and quota reset must commit with their audit records.
create or replace function public.classio_admin_account_control(
    p_actor_id text,
    p_target_id text,
    p_action text,
    p_status text,
    p_reason text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_today date := (now() at time zone 'UTC')::date;
begin
    if auth.role() <> 'service_role'
       or not exists (select 1 from public.profiles where user_id = p_actor_id and role = 'admin') then
        raise exception 'Admin service role required' using errcode = '42501';
    end if;
    if p_action not in ('account_status','reset_usage')
       or length(coalesce(p_reason,'')) < 1 or length(p_reason) > 800 then
        raise exception 'Invalid account control action' using errcode = '22023';
    end if;
    perform 1 from public.profiles where user_id = p_target_id for update;
    if not found then raise exception 'Target account unavailable' using errcode = '22023'; end if;

    if p_action = 'account_status' then
        if p_actor_id = p_target_id or p_status not in ('active','suspended') then
            raise exception 'Invalid account status change' using errcode = '22023';
        end if;
        update public.profiles set account_status = p_status, admin_notes = p_reason
        where user_id = p_target_id;
        insert into public.admin_overrides(user_id, override_type, reason, created_by)
        values (p_target_id, case when p_status = 'suspended' then 'suspend_user' else 'unsuspend_user' end,
                p_reason, p_actor_id);
    else
        insert into public.usage_tracking(user_id, ai_generations, pdf_exports,
                                          students_count, classes_count, monthly_reset_date)
        values (p_target_id, 0, 0, 0, 0, v_today)
        on conflict (user_id) do update set ai_generations = 0, pdf_exports = 0,
            students_count = 0, classes_count = 0, monthly_reset_date = v_today,
            updated_at = now();
        if exists (select 1 from information_schema.columns
                   where table_schema = 'public' and table_name = 'usage_tracking'
                   and column_name = 'word_exports') then
            execute 'update public.usage_tracking set word_exports = 0 where user_id = $1' using p_target_id;
        end if;
        insert into public.admin_overrides(user_id, override_type, reason, created_by)
        values (p_target_id, 'reset_usage', p_reason, p_actor_id);
    end if;
    return true;
end;
$$;
revoke all on function public.classio_admin_account_control(text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.classio_admin_account_control(text,text,text,text,text) to service_role;
