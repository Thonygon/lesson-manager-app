-- A resource remains "already sent" after the teacher archives its assignment.
-- Keep all historical rows and protect concurrent inserts from every client.
begin;

with candidates as (
    select a.id, a.status, prior.id as prior_id
    from public.teacher_assignments a
    join lateral (
        select old.id
        from public.teacher_assignments old
        where old.teacher_id = a.teacher_id
          and old.student_id = a.student_id
          and old.assignment_type = a.assignment_type
          and old.status = 'archived'
          and old.id < a.id
          and coalesce(old.source_record_id::text, old.content_snapshot->>'id') =
              coalesce(a.source_record_id::text, a.content_snapshot->>'id')
          and (a.assignment_type <> 'lesson_plan_topic' or lower(btrim(old.topic)) = lower(btrim(a.topic)))
        order by old.id
        limit 1
    ) prior on true
    where a.status in ('assigned', 'overdue')
      and coalesce(a.source_record_id::text, a.content_snapshot->>'id') is not null
      and a.opened_at is null and a.submitted_at is null
      and not exists (select 1 from public.teacher_assignment_attempts x where x.assignment_id = a.id)
      and not exists (select 1 from public.teacher_review_requests r where r.assignment_id = a.id)
), logged as (
    insert into public.classio_assignment_dedup_audit
        (archived_assignment_id, retained_assignment_id, previous_status)
    select id, prior_id, status from candidates
    on conflict (archived_assignment_id) do nothing
    returning archived_assignment_id
)
update public.teacher_assignments a
set status = 'archived', updated_at = now()
from logged where a.id = logged.archived_assignment_id;

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
        select 1 from public.teacher_assignments old
        where old.teacher_id = new.teacher_id
          and old.student_id = new.student_id
          and old.assignment_type = new.assignment_type
          and coalesce(old.source_record_id::text, old.content_snapshot->>'id') = v_source
          and (new.assignment_type <> 'lesson_plan_topic' or lower(btrim(old.topic)) = lower(btrim(new.topic)))
    ) then
        raise exception 'Resource already assigned to this student' using errcode = '23505';
    end if;
    return new;
end;
$$;

drop trigger if exists trg_classio_reject_repeated_teacher_assignment on public.teacher_assignments;
create trigger trg_classio_reject_repeated_teacher_assignment
before insert on public.teacher_assignments
for each row execute function public.classio_reject_repeated_teacher_assignment();
revoke all on function public.classio_reject_repeated_teacher_assignment() from public;

create or replace function public.classio_reject_repeated_program_assignment()
returns trigger language plpgsql security definer set search_path = public, pg_temp as $$
begin
    perform pg_advisory_xact_lock(
        hashtext('classio.program_assignment'),
        hashtext(new.teacher_id::text || ':' || new.program_id::text)
    );
    if exists (
        select 1 from public.learning_program_assignments old
        where old.teacher_id = new.teacher_id
          and old.program_id = new.program_id
          and (
              (new.roster_student_id is not null and old.roster_student_id = new.roster_student_id)
              or (new.student_user_id is not null and old.student_user_id = new.student_user_id)
          )
    ) then
        raise exception 'Program already assigned to this student' using errcode = '23505';
    end if;
    return new;
end;
$$;

drop trigger if exists trg_classio_reject_repeated_program_assignment on public.learning_program_assignments;
create trigger trg_classio_reject_repeated_program_assignment
before insert on public.learning_program_assignments
for each row execute function public.classio_reject_repeated_program_assignment();
revoke all on function public.classio_reject_repeated_program_assignment() from public;

commit;
