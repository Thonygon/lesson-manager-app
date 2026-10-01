-- Authenticated teacher workflow parity for the Expo application.
-- Safe to rerun: functions are replaced in place and ownership is always
-- derived from auth.uid(), never from a browser-supplied user id.

create or replace function public.classio_rename_student_everywhere(
    p_old_name text,
    p_new_name text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_uid uuid := auth.uid();
    v_old text := trim(coalesce(p_old_name, ''));
    v_new text := trim(coalesce(p_new_name, ''));
    v_students integer := 0;
    v_classes integer := 0;
    v_payments integer := 0;
    v_schedules integer := 0;
    v_overrides integer := 0;
    v_programs integer := 0;
begin
    if v_uid is null then raise exception 'authentication_required'; end if;
    if v_old = '' or v_new = '' then raise exception 'student_name_required'; end if;
    if lower(v_old) = lower(v_new) then return jsonb_build_object('renamed', false, 'name', v_new); end if;
    if exists (
        select 1 from public.students
         where user_id = v_uid and lower(trim(student)) = lower(v_new)
           and lower(trim(student)) <> lower(v_old)
    ) then raise exception 'student_name_exists'; end if;

    update public.students set student = v_new where user_id = v_uid and student = v_old;
    get diagnostics v_students = row_count;
    if v_students = 0 then raise exception 'student_not_found'; end if;
    update public.classes set student = v_new where user_id = v_uid and student = v_old;
    get diagnostics v_classes = row_count;
    update public.payments set student = v_new where user_id = v_uid and student = v_old;
    get diagnostics v_payments = row_count;
    update public.schedules set student = v_new where user_id = v_uid and student = v_old;
    get diagnostics v_schedules = row_count;
    update public.calendar_overrides set student = v_new where user_id = v_uid and student = v_old;
    get diagnostics v_overrides = row_count;
    update public.learning_program_assignments set student_name = v_new where teacher_id = v_uid and student_name = v_old;
    get diagnostics v_programs = row_count;

    return jsonb_build_object(
        'renamed', true, 'name', v_new, 'students', v_students,
        'classes', v_classes, 'payments', v_payments,
        'schedules', v_schedules, 'calendar_overrides', v_overrides,
        'learning_program_assignments', v_programs
    );
end;
$$;

revoke all on function public.classio_rename_student_everywhere(text, text) from public;
grant execute on function public.classio_rename_student_everywhere(text, text) to authenticated;
