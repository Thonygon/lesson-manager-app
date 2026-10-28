-- Keep every row and its attempts/reviews. Hide only repeated active cards.
-- Prefer the row with learning evidence, then usable content, then the oldest.
begin;

create table if not exists public.classio_assignment_dedup_audit (
    archived_assignment_id bigint primary key references public.teacher_assignments(id) on delete restrict,
    retained_assignment_id bigint not null references public.teacher_assignments(id) on delete restrict,
    previous_status text not null,
    archived_at timestamptz not null default now()
);
alter table public.classio_assignment_dedup_audit enable row level security;

with ranked as (
    select a.id, a.status,
           first_value(a.id) over group_window as retained_id,
           row_number() over group_window as position
    from public.teacher_assignments a
    where a.status <> 'archived' and a.source_record_id is not null
    window group_window as (
        partition by a.teacher_id, a.student_id, a.assignment_type, a.source_record_id,
                     case when a.assignment_type = 'lesson_plan_topic' then lower(btrim(a.topic)) else '' end
        order by
            case when exists (select 1 from public.teacher_review_requests r where r.assignment_id = a.id and r.status = 'requested') then 0 else 1 end,
            case when exists (select 1 from public.teacher_assignment_attempts attempt where attempt.assignment_id = a.id and attempt.status in ('in_progress','submitted')) then 0 else 1 end,
            case when a.status in ('graded','completed') then 0
                 when a.status in ('started','submitted') then 1 else 2 end,
            case when jsonb_typeof(a.content_snapshot) = 'object'
                 then length(a.content_snapshot::text) else 0 end desc,
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

create unique index if not exists teacher_assignments_one_active_resource_per_student
on public.teacher_assignments (
    teacher_id, student_id, assignment_type, source_record_id,
    (case when assignment_type = 'lesson_plan_topic' then lower(btrim(topic)) else '' end)
)
where status <> 'archived' and source_record_id is not null;

commit;
