-- Repair the shared Streamlit/Expo schedule editor. The RPC accepts time as
-- text for client compatibility, while public.schedules.time is a SQL time.

create or replace function public.classio_edit_schedule(
  p_schedule_id bigint,
  p_student text,
  p_weekday integer,
  p_time text,
  p_duration_minutes integer,
  p_active boolean,
  p_timezone text,
  p_effective_start_date date,
  p_end_date date default null,
  p_scope text default 'future'
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor text := auth.uid()::text;
  v_existing public.schedules%rowtype;
  v_new public.schedules%rowtype;
  v_old_end date;
begin
  if nullif(v_actor, '') is null then raise exception 'Authentication required'; end if;
  if nullif(trim(coalesce(p_student, '')), '') is null then raise exception 'Student is required'; end if;
  if p_weekday < 0 or p_weekday > 6 then raise exception 'Weekday must be between 0 and 6'; end if;
  if p_time !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$' then raise exception 'Time must use HH:MM'; end if;
  if p_duration_minutes < 15 or p_duration_minutes > 360 then raise exception 'Duration must be between 15 and 360 minutes'; end if;
  if p_end_date is not null and p_end_date < p_effective_start_date then raise exception 'End date must not be before the effective date'; end if;
  if p_scope not in ('entire', 'future') then raise exception 'Unsupported edit scope'; end if;

  select * into v_existing from public.schedules
  where id = p_schedule_id and user_id::text = v_actor
  for update;
  if not found then raise exception 'Schedule not found'; end if;

  if p_scope = 'entire' or v_existing.start_date is null or p_effective_start_date <= v_existing.start_date then
    update public.schedules set
      student = trim(p_student), weekday = p_weekday, time = p_time::time,
      duration_minutes = p_duration_minutes, active = coalesce(p_active, true),
      timezone = nullif(trim(coalesce(p_timezone, '')), ''),
      start_date = p_effective_start_date, end_date = p_end_date
    where id = v_existing.id
    returning * into v_new;
    return jsonb_build_object('id', v_new.id, 'versioned', false);
  end if;

  if v_existing.end_date is not null and p_effective_start_date > v_existing.end_date then
    raise exception 'Effective date is outside the current schedule range';
  end if;
  v_old_end := p_effective_start_date - 1;
  if v_existing.start_date is not null and v_old_end < v_existing.start_date then
    raise exception 'Effective date is invalid';
  end if;

  update public.schedules set end_date = v_old_end where id = v_existing.id;
  insert into public.schedules (
    user_id, student, weekday, time, duration_minutes, active, timezone, start_date, end_date
  ) values (
    v_existing.user_id, trim(p_student), p_weekday, p_time::time, p_duration_minutes,
    coalesce(p_active, true), nullif(trim(coalesce(p_timezone, '')), ''),
    p_effective_start_date, p_end_date
  ) returning * into v_new;

  return jsonb_build_object('id', v_new.id, 'versioned', true, 'previous_id', v_existing.id);
end;
$$;

revoke all on function public.classio_edit_schedule(bigint, text, integer, text, integer, boolean, text, date, date, text) from public;
grant execute on function public.classio_edit_schedule(bigint, text, integer, text, integer, boolean, text, date, date, text) to authenticated;
