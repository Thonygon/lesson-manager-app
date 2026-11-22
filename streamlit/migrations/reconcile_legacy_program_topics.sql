-- Reconcile the July 2026 positional backfill of program 2 against its
-- authoritative program_data topic IDs. Preserve progress and links before
-- removing superseded rows. This migration deliberately aborts on drift.
begin;

create temporary table classio_topic_reconcile_map on commit drop as
with canonical as (
  select (topic.value->>'topic_id')::bigint as id,
         unit.ordinality::integer as unit_number,
         lower(btrim(topic.value->>'title')) as title
  from public.learning_programs program
  cross join lateral jsonb_array_elements(program.program_data->'units')
    with ordinality as unit(value, ordinality)
  cross join lateral jsonb_array_elements(unit.value->'topics') as topic(value)
  where program.id = 2
), extras as (
  select topic.id, topic.unit_number, lower(btrim(topic.title)) as title
  from public.learning_program_topics topic
  where topic.program_id = 2
    and not exists (select 1 from canonical where canonical.id = topic.id)
)
select extras.id as old_id, canonical.id as new_id
from extras join canonical
  on canonical.unit_number = extras.unit_number
 and canonical.title = extras.title;

do $$
declare
  v_rows integer;
  v_canonical integer;
  v_extras integer;
  v_mapped integer;
begin
  select count(*) into v_rows from public.learning_program_topics where program_id = 2;
  select count(*) into v_canonical
  from public.learning_programs p,
       jsonb_array_elements(p.program_data->'units') u,
       jsonb_array_elements(u->'topics') t
  where p.id = 2;
  v_extras := v_rows - v_canonical;
  select count(*) into v_mapped from classio_topic_reconcile_map;
  if not ((v_rows = 84 and v_canonical = 44 and v_extras = 40 and v_mapped = 40)
       or (v_rows = 44 and v_canonical = 44 and v_extras = 0 and v_mapped = 0))
     or exists (select 1 from classio_topic_reconcile_map group by old_id having count(*) <> 1)
     or exists (select 1 from classio_topic_reconcile_map where old_id = new_id) then
    raise exception 'Program topic reconciliation requires manual review: rows %, canonical %, extras %, mapped %',
      v_rows, v_canonical, v_extras, v_mapped;
  end if;
end;
$$;

insert into public.learning_program_progress
  (assignment_id, topic_id, teacher_done, student_done, is_done, note,
   completed_at, created_at, updated_at)
select progress.assignment_id, map.new_id, progress.teacher_done,
       progress.student_done, progress.is_done, progress.note,
       progress.completed_at, progress.created_at, progress.updated_at
from public.learning_program_progress progress
join classio_topic_reconcile_map map on map.old_id = progress.topic_id
on conflict (assignment_id, topic_id) do update set
  teacher_done = public.learning_program_progress.teacher_done or excluded.teacher_done,
  student_done = public.learning_program_progress.student_done or excluded.student_done,
  is_done = public.learning_program_progress.is_done or excluded.is_done,
  note = case
    when public.learning_program_progress.note = '' then excluded.note
    when excluded.note = '' or excluded.note = public.learning_program_progress.note
      then public.learning_program_progress.note
    else public.learning_program_progress.note || E'\n' || excluded.note
  end,
  completed_at = coalesce(public.learning_program_progress.completed_at, excluded.completed_at),
  updated_at = greatest(public.learning_program_progress.updated_at, excluded.updated_at);
delete from public.learning_program_progress progress
using classio_topic_reconcile_map map where progress.topic_id = map.old_id;

insert into public.learning_program_topic_videos
  (teacher_id, program_id, topic_id, video_id, created_at, updated_at)
select link.teacher_id, link.program_id, map.new_id, link.video_id,
       link.created_at, link.updated_at
from public.learning_program_topic_videos link
join classio_topic_reconcile_map map on map.old_id = link.topic_id
on conflict (teacher_id, program_id, topic_id, video_id) do nothing;
delete from public.learning_program_topic_videos link
using classio_topic_reconcile_map map where link.topic_id = map.old_id;

update public.teacher_assignments target set learning_program_topic_id = map.new_id
from classio_topic_reconcile_map map where target.learning_program_topic_id = map.old_id;
update public.teacher_assignment_attempts target set learning_program_topic_id = map.new_id
from classio_topic_reconcile_map map where target.learning_program_topic_id = map.old_id;
update public.learning_program_recommendation_events target set learning_program_topic_id = map.new_id
from classio_topic_reconcile_map map where target.learning_program_topic_id = map.old_id;
update public.resource_exposures target set learning_program_topic_id = map.new_id
from classio_topic_reconcile_map map where target.learning_program_topic_id = map.old_id;

delete from public.learning_program_topics topic
using classio_topic_reconcile_map map where topic.id = map.old_id;

-- The former order-only uniqueness allowed the same topic to be appended at
-- another number. Reject that state at the database boundary for every writer.
create unique index if not exists learning_program_topics_unique_unit_title
  on public.learning_program_topics
  (unit_id, lower(btrim(title)));

commit;
