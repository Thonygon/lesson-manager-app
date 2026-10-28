-- Some plans and exams use UUID resource IDs while source_record_id is bigint.
-- Retain the ID in content_snapshot.id and prevent repeated active copies.
begin;

with ranked as (
    select a.id, a.status,
           first_value(a.id) over group_window as retained_id,
           row_number() over group_window as position
    from public.teacher_assignments a
    where a.status <> 'archived' and a.source_record_id is null
      and nullif(a.content_snapshot->>'id', '') is not null
    window group_window as (
        partition by a.teacher_id, a.student_id, a.assignment_type,
                     a.content_snapshot->>'id',
                     case when a.assignment_type = 'lesson_plan_topic' then lower(btrim(a.topic)) else '' end
        order by
            case when exists (select 1 from public.teacher_review_requests r where r.assignment_id = a.id and r.status = 'requested') then 0 else 1 end,
            case when exists (select 1 from public.teacher_assignment_attempts attempt where attempt.assignment_id = a.id and attempt.status in ('in_progress','submitted')) then 0 else 1 end,
            case when a.status in ('graded','completed') then 0
                 when a.status in ('started','submitted') then 1 else 2 end,
            length(a.content_snapshot::text) desc,
            a.created_at asc, a.id asc
    )
)
insert into public.classio_assignment_dedup_audit (archived_assignment_id, retained_assignment_id, previous_status)
select id, retained_id, status from ranked where position > 1
on conflict (archived_assignment_id) do nothing;

update public.teacher_assignments a
set status = 'archived', updated_at = now()
from public.classio_assignment_dedup_audit audit
where a.id = audit.archived_assignment_id and a.status <> 'archived';

create unique index if not exists teacher_assignments_one_active_uuid_resource_per_student
on public.teacher_assignments (
    teacher_id, student_id, assignment_type, (content_snapshot->>'id'),
    (case when assignment_type = 'lesson_plan_topic' then lower(btrim(topic)) else '' end)
)
where status <> 'archived' and source_record_id is null
  and nullif(content_snapshot->>'id', '') is not null;

commit;
