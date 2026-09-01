create or replace function public.classio_version_schedule_from_date(
    p_schedule_id bigint,
    p_user_id text,
    p_old_schedule_end_date date,
    p_student text,
    p_weekday integer,
    p_time text,
    p_duration_minutes integer,
    p_active boolean,
    p_timezone text,
    p_start_date date,
    p_end_date date default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_actor_id text;
    v_owner_id text;
begin
    v_actor_id := nullif(auth.uid()::text, '');
    v_owner_id := coalesce(v_actor_id, nullif(trim(coalesce(p_user_id, '')), ''));

    if v_owner_id is null then
        raise exception 'schedule_owner_required';
    end if;

    if v_actor_id is not null and p_user_id is not null and v_actor_id <> p_user_id then
        raise exception 'schedule_owner_mismatch';
    end if;

    update public.schedules
       set end_date = p_old_schedule_end_date
     where id = p_schedule_id
       and user_id = v_owner_id;

    if not found then
        raise exception 'schedule_not_found';
    end if;

    insert into public.schedules (
        user_id,
        student,
        weekday,
        time,
        duration_minutes,
        active,
        timezone,
        start_date,
        end_date
    )
    values (
        v_owner_id,
        trim(coalesce(p_student, '')),
        p_weekday,
        p_time,
        p_duration_minutes,
        coalesce(p_active, true),
        nullif(trim(coalesce(p_timezone, '')), ''),
        p_start_date,
        p_end_date
    );
end;
$$;

grant execute on function public.classio_version_schedule_from_date(
    bigint,
    text,
    date,
    text,
    integer,
    text,
    integer,
    boolean,
    text,
    date,
    date
) to authenticated;
