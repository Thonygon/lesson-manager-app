-- Staff role mutation and its audit row share one database transaction.
create or replace function public.classio_admin_change_staff(
    p_actor_id text,
    p_action text,
    p_target_id text,
    p_role text,
    p_assignment_id bigint,
    p_reason text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_assignment_id bigint;
    v_target_id text;
    v_role text;
begin
    if auth.role() <> 'service_role'
       or not exists (select 1 from public.profiles where user_id = p_actor_id and role = 'admin') then
        raise exception 'Admin service role required' using errcode = '42501';
    end if;
    if p_action not in ('assign','revoke') or length(coalesce(p_reason,'')) < 1
       or length(p_reason) > 800 then
        raise exception 'Invalid staff change' using errcode = '22023';
    end if;

    if p_action = 'assign' then
        if p_role not in ('developer','data_scientist') or p_target_id is null then
            raise exception 'Invalid staff role or target' using errcode = '22023';
        end if;
        perform 1 from public.profiles where user_id = p_target_id for update;
        if not found then raise exception 'Target account unavailable' using errcode = '22023'; end if;
        insert into public.user_staff_roles(user_id, role_key, is_active, assigned_by,
                                             assigned_at, assignment_reason, metadata)
        values (p_target_id::uuid, p_role, true, p_actor_id::uuid,
                now(), p_reason, '{}'::jsonb)
        returning id into v_assignment_id;
        v_target_id := p_target_id;
        v_role := p_role;
    else
        select user_id::text, role_key into v_target_id, v_role
        from public.user_staff_roles
        where id = p_assignment_id and is_active = true for update;
        if not found then raise exception 'Active staff assignment unavailable' using errcode = '22023'; end if;
        update public.user_staff_roles set is_active = false, revoked_by = p_actor_id::uuid,
            revoked_at = now(), updated_at = now(), assignment_reason = p_reason
        where id = p_assignment_id;
        v_assignment_id := p_assignment_id;
    end if;

    insert into public.admin_overrides(user_id, override_type, reason, created_by)
    values (v_target_id,
            case when p_action = 'assign' then 'staff_role_assigned' else 'staff_role_revoked' end,
            v_role || ': ' || p_reason, p_actor_id);
    return jsonb_build_object('assignment_id', v_assignment_id, 'target_id', v_target_id, 'role', v_role);
end;
$$;
revoke all on function public.classio_admin_change_staff(text,text,text,text,bigint,text) from public, anon, authenticated;
grant execute on function public.classio_admin_change_staff(text,text,text,text,bigint,text) to service_role;
