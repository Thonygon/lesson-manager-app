-- A teacher can assign a program before the learner creates a Classio account.
alter table public.learning_program_assignments
    add column if not exists roster_student_id bigint references public.students(id) on delete set null;

create index if not exists learning_program_assignments_roster_student_idx
    on public.learning_program_assignments(teacher_id, roster_student_id, updated_at desc)
    where roster_student_id is not null;

-- Linking an existing roster entry preserves its assignments and topic progress.
create or replace function public.classio_link_roster_program_assignments()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    if new.linked_student_user_id is not null
       and new.linked_student_user_id is distinct from old.linked_student_user_id then
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

drop trigger if exists classio_roster_program_linked on public.students;
create trigger classio_roster_program_linked after update of linked_student_user_id on public.students
for each row execute function public.classio_link_roster_program_assignments();

-- Recommendation evidence uses the same stable roster identity until the
-- learner links an account. Validate it against the teacher's own roster.
alter table public.resource_exposures drop constraint if exists resource_exposures_student_id_fkey;
alter table public.resource_exposure_events drop constraint if exists resource_exposure_events_student_id_fkey;
alter table public.learning_program_recommendation_events drop constraint if exists learning_program_recommendation_events_student_id_fkey;

create or replace function public.classio_validate_recommendation_student()
returns trigger language plpgsql security definer set search_path = public as $$
declare
    roster_id bigint;
begin
    if new.student_id like 'roster:%' then
        if new.student_id !~ '^roster:[1-9][0-9]*$' then
            raise exception 'Invalid roster student identity';
        end if;
        roster_id := substring(new.student_id from 8)::bigint;
        if not exists (select 1 from public.students where id = roster_id and user_id = new.teacher_id) then
            raise exception 'Roster student does not belong to teacher';
        end if;
    elsif new.student_id is not null and not exists
        (select 1 from public.profiles where user_id = new.student_id) then
        raise exception 'Student account does not exist';
    end if;
    return new;
end;
$$;

drop trigger if exists classio_validate_exposure_student on public.resource_exposures;
create trigger classio_validate_exposure_student before insert or update of student_id, teacher_id on public.resource_exposures
for each row execute function public.classio_validate_recommendation_student();
drop trigger if exists classio_validate_exposure_event_student on public.resource_exposure_events;
create trigger classio_validate_exposure_event_student before insert or update of student_id, teacher_id on public.resource_exposure_events
for each row execute function public.classio_validate_recommendation_student();
drop trigger if exists classio_validate_program_recommendation_student on public.learning_program_recommendation_events;
create trigger classio_validate_program_recommendation_student before insert or update of student_id, teacher_id on public.learning_program_recommendation_events
for each row execute function public.classio_validate_recommendation_student();
