-- Archived assignments remain in the audit trail but do not block a new,
-- intentional assignment. The existing partial unique indexes still protect
-- active numeric and UUID resource assignments, including restore attempts.
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
          and existing_assignment.status <> 'archived'
          and coalesce(existing_assignment.source_record_id::text, existing_assignment.content_snapshot->>'id') = v_source
          and (new.assignment_type <> 'lesson_plan_topic' or lower(btrim(existing_assignment.topic)) = lower(btrim(new.topic)))
    ) then
        raise exception 'Resource already assigned to this student' using errcode = '23505';
    end if;
    return new;
end;
$$;

commit;
