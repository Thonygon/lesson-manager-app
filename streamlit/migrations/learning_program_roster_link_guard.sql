-- A roster program may transfer only after the teacher/student connection is active.
create or replace function public.classio_link_roster_program_assignments()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    if new.linked_student_user_id is not null
       and new.linked_student_user_id is distinct from old.linked_student_user_id then
        if not exists (
            select 1 from public.teacher_student_links
             where teacher_id::text = new.user_id::text
               and student_id::text = new.linked_student_user_id::text
               and status = 'active'
        ) then
            raise exception 'A confirmed student connection is required';
        end if;
        update public.learning_program_assignments
           set student_user_id = new.linked_student_user_id,
               updated_at = now()
         where teacher_id = new.user_id
           and roster_student_id = new.id
           and student_user_id is null;
    end if;
    return new;
end;
$$;
