-- Trigger variables OLD/NEW are reserved in PL/pgSQL; use unambiguous aliases.
begin;

create or replace function public.classio_reject_repeated_teacher_assignment()
returns trigger language plpgsql security definer set search_path = public, pg_temp as $$
declare
    v_source text := coalesce(new.source_record_id::text, nullif(new.content_snapshot->>'id', ''));
begin
    if v_source is null then
        return new;
    end if;
    perform pg_advisory_xact_lock(
        hashtext('classio.teacher_assignment'),
        hashtext(new.teacher_id::text || ':' || new.student_id::text || ':' || new.assignment_type || ':' || v_source)
    );
    if exists (
        select 1 from public.teacher_assignments existing_assignment
        where existing_assignment.teacher_id = new.teacher_id
          and existing_assignment.student_id = new.student_id
          and existing_assignment.assignment_type = new.assignment_type
          and coalesce(existing_assignment.source_record_id::text, existing_assignment.content_snapshot->>'id') = v_source
          and (new.assignment_type <> 'lesson_plan_topic' or lower(btrim(existing_assignment.topic)) = lower(btrim(new.topic)))
    ) then
        raise exception 'Resource already assigned to this student' using errcode = '23505';
    end if;
    return new;
end;
$$;

create or replace function public.classio_reject_repeated_program_assignment()
returns trigger language plpgsql security definer set search_path = public, pg_temp as $$
begin
    perform pg_advisory_xact_lock(
        hashtext('classio.program_assignment'),
        hashtext(new.teacher_id::text || ':' || new.program_id::text)
    );
    if exists (
        select 1 from public.learning_program_assignments existing_assignment
        where existing_assignment.teacher_id = new.teacher_id
          and existing_assignment.program_id = new.program_id
          and (
              (new.roster_student_id is not null and existing_assignment.roster_student_id = new.roster_student_id)
              or (new.student_user_id is not null and existing_assignment.student_user_id = new.student_user_id)
          )
    ) then
        raise exception 'Program already assigned to this student' using errcode = '23505';
    end if;
    return new;
end;
$$;

commit;
