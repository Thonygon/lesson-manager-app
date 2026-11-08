-- Move an already-linked account to the teacher's correct roster row atomically.
-- The displaced row is preserved: class/payment history must never be deleted here.
create or replace function public.classio_transfer_teacher_student_roster_link(
  p_link_id bigint,
  p_target_roster_id bigint
)
returns bigint
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_teacher uuid := auth.uid();
  v_link public.teacher_student_links%rowtype;
  v_target public.students%rowtype;
  v_displaced_id bigint;
  v_student_name text;
  v_student_email text;
  v_student_phone text;
begin
  if v_teacher is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  select * into v_link from public.teacher_student_links
   where id = p_link_id and teacher_id::text = v_teacher::text and status = 'active' for update;
  if not found then
    raise exception 'Active teacher connection required' using errcode = '42501';
  end if;
  select * into v_target from public.students
   where id = p_target_roster_id and user_id::text = v_teacher::text for update;
  if not found or (v_target.linked_student_user_id is not null and v_target.linked_student_user_id <> v_link.student_id) then
    raise exception 'A matching teacher-owned roster record is required' using errcode = '42501';
  end if;
  select coalesce(nullif(trim(p.display_name), ''), nullif(trim(p.username), ''), ''),
         coalesce(nullif(trim(p.email), ''), a.email, ''),
         coalesce(p.phone_number, '')
    into v_student_name, v_student_email, v_student_phone
    from auth.users a left join public.profiles p on p.user_id::text = a.id::text
   where a.id = v_link.student_id;
  if not (
    (v_student_email <> '' and lower(trim(v_target.email)) = lower(trim(v_student_email)))
    or (v_student_name <> '' and lower(trim(v_target.student)) = lower(trim(v_student_name)))
    or (length(regexp_replace(v_student_phone, '[^0-9]', '', 'g')) >= 7
        and regexp_replace(v_target.phone, '[^0-9]', '', 'g') = regexp_replace(v_student_phone, '[^0-9]', '', 'g'))
  ) then
    raise exception 'The selected roster record does not match this student' using errcode = '22023';
  end if;
  select id into v_displaced_id from public.students
   where user_id::text = v_teacher::text
     and linked_student_user_id = v_link.student_id
     and id <> p_target_roster_id
   for update;
  if found then
    update public.students
       set linked_student_user_id = null, teacher_student_link_id = null, linked_at = null
     where id = v_displaced_id and user_id::text = v_teacher::text;
  end if;
  update public.students
     set linked_student_user_id = v_link.student_id,
         teacher_student_link_id = v_link.id,
         linked_at = now(),
         student_source = case when student_source = 'classio_link' then 'classio_link' else 'classio_linked_existing' end
   where id = p_target_roster_id and user_id::text = v_teacher::text;
  return v_displaced_id;
end;
$$;

revoke all on function public.classio_transfer_teacher_student_roster_link(bigint, bigint) from public;
grant execute on function public.classio_transfer_teacher_student_roster_link(bigint, bigint) to authenticated;
